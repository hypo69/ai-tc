# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Cloudflared Monitor State and Diagnostics Engine
# =============================================================================
# Description:
#   Ядро мониторинга демона Cloudflare Tunnel (cloudflared), парсинга логов,
#   проверки общедоступного хоста (kino.davidka.net), сбора телеметрии процесса
#   и эвристической/ИИ диагностики работоспособности.
#
# File: state.py
# Project: ai-windows-admin
# Package: apps.cloudflared_monitor.src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""Супервизия процесса cloudflared, разбор логов, опрос эндпоинта и диагностика."""

from __future__ import annotations

import csv
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

from logger import logger


@dataclass
class CloudflaredProcessInfo:
    """Метрики и состояние процесса демона cloudflared."""

    is_running: bool = False
    pid: Optional[int] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    num_threads: int = 0
    uptime_seconds: float = 0.0
    start_time: Optional[str] = None
    exe_path: Optional[str] = None
    cmdline: List[str] = field(default_factory=list)


@dataclass
class CloudflaredLogEntry:
    """Структурированная запись из файла лога cloudflared.log."""

    timestamp: str
    level: str  # 'INFO', 'WARN', 'ERROR', 'DEBUG'
    message: str
    connection_id: Optional[str] = None
    raw: str = ""


@dataclass
class EndpointHealth:
    """Статус и метрики отклика публичного эндпоинта туннеля."""

    url: str = "https://kino.davidka.net"
    is_reachable: bool = False
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    last_checked: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class CloudflaredAnomaly:
    """Обнаруженная проблема или аномалия в работе туннеля."""

    title: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'


@dataclass
class CloudflaredDiagnosticReport:
    """Отчет о комплексной диагностике состояния туннеля."""

    health_score: int
    status: str  # 'HEALTHY', 'DEGRADED', 'OFFLINE', 'CRITICAL'
    summary: str
    anomalies: List[CloudflaredAnomaly] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    evaluated_at: str = ""


class CloudflaredState:
    """Менеджер состояния и сборщик телеметрии для Cloudflare Tunnel."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        public_url: str = "https://kino.davidka.net",
        log_file_rel: str = "logs/cloudflared.log",
        max_log_entries: int = 200,
    ) -> None:
        """Инициализирует менеджер состояния Cloudflared.

        Args:
            project_root: Корневой путь проекта.
            public_url: Публичный URL эндпоинта для проверки.
            log_file_rel: Относительный или абсолютный путь к cloudflared.log.
            max_log_entries: Максимальное количество строк логов в памяти.
        """
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent
        self.public_url = public_url
        self.log_file = (
            Path(log_file_rel)
            if Path(log_file_rel).is_absolute()
            else self.project_root / log_file_rel
        )
        self.max_log_entries = max_log_entries

        self.process: CloudflaredProcessInfo = CloudflaredProcessInfo()
        self.endpoint: EndpointHealth = EndpointHealth(url=public_url)
        self.logs: List[CloudflaredLogEntry] = []
        self.report: Optional[CloudflaredDiagnosticReport] = None
        self.has_token: bool = False
        self.token_preview: str = ""
        self.exe_path: Optional[str] = None

        self.total_errors_in_log: int = 0
        self.total_warnings_in_log: int = 0
        self.active_connections_count: int = 0
        self.last_refreshed: str = ""

    def find_executable(self) -> Optional[str]:
        """Определяет путь к cloudflared.exe в системе.

        Returns:
            Optional[str]: Путь к бинарнику, если найден.
        """
        candidates = [
            r"C:\Users\onela\AppData\Local\bin\cloudflared.exe",
            str(self.project_root / "cloudflared.exe"),
            str(self.project_root / "bin" / "cloudflared.exe"),
        ]
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            candidates.append(str(Path(local_app_data) / "bin" / "cloudflared.exe"))

        for cand in candidates:
            if cand and Path(cand).exists():
                self.exe_path = cand
                return cand

        which_path = shutil.which("cloudflared.exe") or shutil.which("cloudflared")
        if which_path:
            self.exe_path = which_path
            return which_path

        self.exe_path = None
        return None

    def check_token(self) -> bool:
        """Проверяет наличие токена CLOUDFLARE_TUNNEL_TOKEN в .env или окружении.

        Returns:
            bool: True, если токен присутствует и не пуст.
        """
        env_file = self.project_root / ".env"
        token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")

        if not token and env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == "CLOUDFLARE_TUNNEL_TOKEN":
                            token = v.strip().strip("'\"")
                            break
            except Exception as exc:
                logger.warning(f"Ошибка чтения .env для токена cloudflared: {exc}")

        if token:
            self.has_token = True
            self.token_preview = f"{token[:4]}...{token[-4:]}" if len(token) > 10 else "***"
            return True

        self.has_token = False
        self.token_preview = "Missing"
        return False

    def inspect_process(self) -> CloudflaredProcessInfo:
        """Опрашивает процессы хоста на наличие запущенного cloudflared.

        Returns:
            CloudflaredProcessInfo: Телеметрия процесса.
        """
        if PSUTIL_AVAILABLE and psutil is not None:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if "cloudflared" in pname:
                        with proc.oneshot():
                            ctime = proc.create_time()
                            mem_info = proc.memory_info()
                            self.process = CloudflaredProcessInfo(
                                is_running=True,
                                pid=proc.pid,
                                cpu_percent=proc.cpu_percent(interval=0.0),
                                memory_mb=round(mem_info.rss / (1024 * 1024), 2),
                                memory_percent=round(proc.memory_percent(), 2),
                                num_threads=proc.num_threads(),
                                uptime_seconds=max(0.0, time.time() - ctime),
                                start_time=datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S"),
                                exe_path=proc.exe() if hasattr(proc, "exe") else self.exe_path,
                                cmdline=proc.cmdline(),
                            )
                            return self.process
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        if sys.platform == "win32":
            try:
                res = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq cloudflared*"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0 and "cloudflared" in res.stdout.lower():
                    reader = csv.reader(io.StringIO(res.stdout))
                    for row in reader:
                        if row and "cloudflared" in row[0].lower():
                            pid = int(row[1]) if len(row) > 1 and row[1].isdigit() else 0
                            mem_str = row[4].replace(" K", "").replace(",", "").replace(".", "").strip() if len(row) > 4 else "0"
                            mem_mb = round(float(mem_str) / 1024.0, 2) if mem_str.isdigit() else 0.0
                            self.process = CloudflaredProcessInfo(
                                is_running=True,
                                pid=pid,
                                memory_mb=mem_mb,
                                exe_path=self.exe_path,
                            )
                            return self.process
            except Exception as exc:
                logger.debug(f"Не удалось проверить cloudflared через tasklist: {exc}")

        self.process = CloudflaredProcessInfo(is_running=False)
        return self.process

    def parse_log_line(self, line: str) -> Optional[CloudflaredLogEntry]:
        """Разбирает одну строку из cloudflared.log.

        Args:
            line: Сырая строка журнала.

        Returns:
            Optional[CloudflaredLogEntry]: Распарсенная запись или None.
        """
        line = line.strip()
        if not line:
            return None

        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    raw_lvl = str(data.get("level", "info")).upper()
                    lvl_map = {"ERR": "ERROR", "ERROR": "ERROR", "WRN": "WARN", "WARN": "WARN", "DBG": "DEBUG", "INF": "INFO", "INFO": "INFO"}
                    level = lvl_map.get(raw_lvl, "INFO")
                    timestamp = str(data.get("time") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    msg_text = str(data.get("message") or data.get("msg") or data.get("error") or line)
                    if data.get("error") and data.get("error") != msg_text:
                        msg_text = f"{msg_text}: {data.get('error')}"
                    conn_id = str(data.get("connIndex")) if "connIndex" in data else str(data.get("connection", "")) or None
                    return CloudflaredLogEntry(timestamp=timestamp, level=level, message=msg_text, connection_id=conn_id, raw=line)
            except Exception:
                pass

        level = "INFO"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = line
        conn_id = None

        iso_match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^ ]*)\s+([A-Z]{3,5})\s+(.*)$", line)
        if iso_match:
            timestamp = iso_match.group(1)
            raw_lvl = iso_match.group(2).upper()
            message = iso_match.group(3)
            lvl_map = {"ERR": "ERROR", "ERROR": "ERROR", "WRN": "WARN", "WARN": "WARN", "DBG": "DEBUG", "INF": "INFO", "INFO": "INFO"}
            level = lvl_map.get(raw_lvl, raw_lvl)
        elif " ERR " in line or "[ERR]" in line or "level=error" in line:
            level = "ERROR"
        elif " WRN " in line or "[WRN]" in line or "level=warn" in line:
            level = "WARN"
        elif " INF " in line or "[INF]" in line or "level=info" in line:
            level = "INFO"

        conn_idx_match = re.search(r"connIndex=(\d+)", line, re.IGNORECASE)
        if conn_idx_match:
            conn_id = conn_idx_match.group(1)
        else:
            conn_guid_match = re.search(r"connection[ =]([a-f0-9\-]+)", line, re.IGNORECASE)
            if conn_guid_match:
                conn_id = conn_guid_match.group(1)

        return CloudflaredLogEntry(timestamp=timestamp, level=level, message=message, connection_id=conn_id, raw=line)

    def tail_logs(self, limit: int = 100) -> List[CloudflaredLogEntry]:
        """Считывает и парсит последние записи из cloudflared.log.

        Args:
            limit: Максимальное количество возвращаемых записей.

        Returns:
            List[CloudflaredLogEntry]: Список записей (сначала свежие).
        """
        if not self.log_file.exists():
            self.logs = []
            self.total_errors_in_log = 0
            self.total_warnings_in_log = 0
            self.active_connections_count = 0
            return []

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as exc:
            logger.warning(f"Ошибка чтения {self.log_file}: {exc}")
            return []

        parsed: List[CloudflaredLogEntry] = []
        errors = 0
        warnings = 0
        active_connections = set()

        recent_lines = lines[-min(len(lines), self.max_log_entries):]
        for l in recent_lines:
            entry = self.parse_log_line(l)
            if entry:
                parsed.append(entry)
                if entry.level == "ERROR":
                    errors += 1
                elif entry.level == "WARN":
                    warnings += 1
                if "Registered tunnel connection" in entry.message or "Connection" in entry.message:
                    if entry.connection_id:
                        active_connections.add(entry.connection_id)

        self.total_errors_in_log = errors
        self.total_warnings_in_log = warnings
        self.active_connections_count = max(len(active_connections), 1 if self.process.is_running else 0)
        self.logs = list(reversed(parsed))[:limit]
        return self.logs

    def probe_endpoint(self, timeout: float = 3.0) -> EndpointHealth:
        """Выполняет HTTP-проверку доступности публичного URL туннеля.

        Args:
            timeout: Таймаут HTTP запроса в секундах.

        Returns:
            EndpointHealth: Измерение доступности и задержки.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.public_url:
            self.endpoint = EndpointHealth(url=self.public_url, is_reachable=False, last_checked=now_str, error_message="URL не задан")
            return self.endpoint

        start_time = time.perf_counter()
        req = urllib.request.Request(self.public_url, headers={"User-Agent": "AI-Windows-Admin-CloudflaredMonitor/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
                self.endpoint = EndpointHealth(
                    url=self.public_url,
                    is_reachable=True,
                    status_code=response.status,
                    response_time_ms=elapsed_ms,
                    last_checked=now_str,
                )
        except urllib.error.HTTPError as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            self.endpoint = EndpointHealth(
                url=self.public_url,
                is_reachable=True,
                status_code=exc.code,
                response_time_ms=elapsed_ms,
                last_checked=now_str,
                error_message=f"HTTP {exc.code}: {exc.reason}",
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            self.endpoint = EndpointHealth(
                url=self.public_url,
                is_reachable=False,
                status_code=None,
                response_time_ms=elapsed_ms,
                last_checked=now_str,
                error_message=str(exc),
            )

        return self.endpoint

    def evaluate_diagnostics(self) -> CloudflaredDiagnosticReport:
        """Оценивает эвристики и вычисляет оценку здоровья туннеля.

        Returns:
            CloudflaredDiagnosticReport: Оценка состояния и рекомендации.
        """
        score = 100
        anomalies: List[CloudflaredAnomaly] = []
        recs: List[str] = []

        if not self.exe_path:
            score -= 40
            anomalies.append(CloudflaredAnomaly(title="Бинарный файл не найден", description="cloudflared.exe отсутствует в AppData\\Local\\bin и в PATH.", severity="high"))
            recs.append("Установите cloudflared или поместите файл в AppData\\Local\\bin.")

        if not self.has_token:
            score -= 40
            anomalies.append(CloudflaredAnomaly(title="Отсутствует токен Cloudflare", description="CLOUDFLARE_TUNNEL_TOKEN не задан в .env файле.", severity="critical"))
            recs.append("Укажите CLOUDFLARE_TUNNEL_TOKEN в файле .env.")

        if not self.process.is_running:
            score -= 50
            anomalies.append(CloudflaredAnomaly(title="Процесс туннеля остановлен", description="Демон cloudflared в данный момент не запущен.", severity="critical"))
            recs.append("Запустите туннель через launchers\\Run-Cloudflared.ps1 или кнопку запуска в интерфейсе.")
        else:
            if self.process.cpu_percent > 80:
                score -= 15
                anomalies.append(CloudflaredAnomaly(title="Высокая нагрузка CPU", description=f"Потребление CPU процессом cloudflared: {self.process.cpu_percent}%.", severity="medium"))
                recs.append("Проверьте трафик или наличие циклических прокси-запросов.")

        if self.endpoint.is_reachable:
            if self.endpoint.response_time_ms > 1500:
                score -= 10
                anomalies.append(CloudflaredAnomaly(title="Высокая задержка эндпоинта", description=f"Задержка отклика: {self.endpoint.response_time_ms} мс.", severity="low"))
                recs.append("Проверьте качество сетевого подключения к Cloudflare Edge.")
        else:
            if self.process.is_running:
                score -= 25
                anomalies.append(CloudflaredAnomaly(title="Публичный хост недоступен", description=f"Не удалось связаться с {self.public_url}: {self.endpoint.error_message}", severity="high"))
                recs.append("Убедитесь, что локальный веб-сервер запущен и слушает порт туннеля.")

        if self.total_errors_in_log > 10:
            score -= 20
            anomalies.append(CloudflaredAnomaly(title="Частые ошибки в логах", description=f"{self.total_errors_in_log} ошибок в буфере журнала.", severity="high"))
            recs.append("Проверьте журнал логов на сброс соединений.")
        elif self.total_errors_in_log > 0:
            score -= 5

        health_score = max(0, min(100, score))
        if health_score >= 85:
            status = "HEALTHY"
        elif health_score >= 50:
            status = "DEGRADED"
        elif self.process.is_running:
            status = "CRITICAL"
        else:
            status = "OFFLINE"

        summary = (
            f"Статус туннеля: {status} (Оценка: {health_score}/100). "
            f"Выявлено аномалий: {len(anomalies)}. "
            f"Процесс: {'АКТИВЕН (PID ' + str(self.process.pid) + ')' if self.process.is_running else 'ОСТАНОВЛЕН'}."
        )

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.report = CloudflaredDiagnosticReport(
            health_score=health_score,
            status=status,
            summary=summary,
            anomalies=anomalies,
            recommendations=recs,
            evaluated_at=now_str,
        )
        return self.report

    def refresh(self, probe_network: bool = True) -> None:
        """Выполняет полный цикл обновления состояния.

        Args:
            probe_network: Выполнять ли сетевой HTTP-опрос публичного URL.
        """
        self.find_executable()
        self.check_token()
        self.inspect_process()
        self.tail_logs()
        if probe_network:
            self.probe_endpoint()
        self.evaluate_diagnostics()
        self.last_refreshed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def start_tunnel(self) -> Tuple[bool, str]:
        """Запускает процесс cloudflared через PowerShell скрипт или напрямую.

        Returns:
            Tuple[bool, str]: (Успех, информационное сообщение).
        """
        if self.process.is_running:
            return True, f"Cloudflared уже запущен (PID {self.process.pid})"

        launcher_ps = self.project_root / "launchers" / "Run-Cloudflared.ps1"
        if launcher_ps.exists():
            try:
                subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher_ps)],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                time.sleep(1.0)
                self.inspect_process()
                return True, "Запуск туннеля инициирован через скрипт Run-Cloudflared.ps1"
            except Exception as exc:
                logger.error(f"Ошибка запуска Run-Cloudflared.ps1: {exc}")
                return False, f"Ошибка вызова скрипта запуска: {exc}"

        exe = self.find_executable()
        if not exe:
            return False, "cloudflared.exe не найден в системе"

        if not self.check_token():
            return False, "CLOUDFLARE_TUNNEL_TOKEN отсутствует в .env"

        token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.Popen(
                [exe, "--no-autoupdate", "--loglevel", "error", "--logfile", str(self.log_file), "tunnel", "run", "--token", token],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            time.sleep(1.0)
            self.inspect_process()
            return True, "Cloudflared успешно запущен напрямую"
        except Exception as exc:
            logger.error(f"Не удалось запустить cloudflared напрямую: {exc}")
            return False, f"Ошибка старта: {exc}"

    def stop_tunnel(self) -> Tuple[bool, str]:
        """Завершает все запущенные процессы cloudflared.exe.

        Returns:
            Tuple[bool, str]: (Успех, информационное сообщение).
        """
        stopped = 0
        if PSUTIL_AVAILABLE and psutil is not None:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if "cloudflared" in pname:
                        proc.terminate()
                        stopped += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        elif sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
                stopped = 1
            except Exception:
                pass

        time.sleep(0.5)
        self.inspect_process()
        if stopped > 0:
            return True, f"Остановлено процессов cloudflared: {stopped}"
        return True, "Активных процессов cloudflared не обнаружено"

    def restart_tunnel(self) -> Tuple[bool, str]:
        """Останавливает и повторно запускает туннель Cloudflare.

        Returns:
            Tuple[bool, str]: (Успех, информационное сообщение).
        """
        self.stop_tunnel()
        time.sleep(1.0)
        return self.start_tunnel()
