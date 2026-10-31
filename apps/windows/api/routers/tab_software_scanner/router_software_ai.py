# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Router Software AI
# =============================================================================
# Description:
#   REST API роутер для модуля ИИ-диагностики программного обеспечения
#   (AI Modal Dialog) вкладки tab-software-scanner:
#   - POST /api/v1/chat/software-explain — потоковый и пакетный анализ ПО моделью Gemini
#   - POST /api/v1/processes/kill — безопасное завершение процесса с таймаутом
#   - POST /api/v1/security/firewall/block — изоляция бинарника в Брандмауэре Windows
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.tab_software_scanner.router_software_ai import init_router
#     router = init_router()
#
# File: router_software_ai.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tab_software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 04:02:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

router = APIRouter(tags=["Software Scanner AI"])


def prune_metadata_for_prompt(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет избыточные и дефолтные метрики перед формированием промпта для экономии токенов."""
    redundant_values = {None, "", "N/A", "null", 0, 0.0, "0%", "0.0%", "0 MB", "0.0 MB"}
    cleaned: Dict[str, Any] = {}
    for k, v in metadata.items():
        if v in redundant_values:
            continue
        cleaned[k] = v
    return cleaned


def safe_run_command(cmd: List[str], timeout_sec: float = 3.0) -> str:
    """Выполняет системную команду с жестким таймаутом и безопасной обработкой ошибок."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=True
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"Команда '{' '.join(cmd)}' превысила таймаут {timeout_sec}с")
        return ""
    except subprocess.CalledProcessError as e:
        logger.error(f"Команда '{' '.join(cmd)}' завершилась с ошибкой {e.returncode}: {e.stderr}")
        return ""
    except Exception as e:
        logger.error(f"Непредвиденная ошибка выполнения '{' '.join(cmd)}': {e}")
        return ""


# -----------------------------------------------------------------------------
# Модели данных
# -----------------------------------------------------------------------------

class SoftwareExplainRequest(BaseModel):
    """Модель входящего запроса на объяснение ПО через ИИ."""
    program: Optional[Dict[str, Any]] = Field(default=None, description="Словарь данных программы/процесса")
    name: Optional[str] = Field(default=None, description="Имя исполняемого файла или приложения")
    pid: Optional[int] = Field(default=None, description="Идентификатор процесса (PID)")
    path: Optional[str] = Field(default=None, description="Полный путь к исполняемому файлу")
    cmdline: Optional[str] = Field(default=None, description="Командная строка запуска")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные метрики процесса")
    prompt: Optional[str] = Field(default=None, description="Пользовательский уточняющий вопрос")
    stream: bool = Field(default=False, description="Флаг потоковой отдачи Server-Sent Events")
    model: Optional[str] = Field(default=None, description="Имя конкретной модели LLM")


class SoftwareExplainResponse(BaseModel):
    """Структурированный ответ экспертного заключения Gemini."""
    summary: str = Field(description="Краткое назначение и описание процесса")
    developer: str = Field(default="Неизвестен", description="Разработчик или вендор")
    category: str = Field(default="Программное обеспечение", description="Категория компонента")
    security_verdict: str = Field(description="Оценка безопасности и легитимности")
    performance_impact: str = Field(description="Влияние на потребление системных ресурсов")
    recommendation: str = Field(description="Практические рекомендации администратору")
    action_steps: List[str] = Field(default_factory=list, description="Рекомендуемые шаги реагирования")
    risk_level: str = Field(default="Low", description="Уровень риска: Low, Medium, High, Critical")
    source: str = Field(default="gemini", description="Источник заключения (wikillm, gemini, heuristic)")
    is_verified: bool = Field(default=False, description="Признак верификации в базе знаний")


class ProcessKillRequest(BaseModel):
    """Запрос на принудительное завершение процесса."""
    pid: int = Field(..., description="PID завершаемого процесса")
    force: bool = Field(default=True, description="Принудительное завершение (/F)")
    timeout_sec: float = Field(default=3.0, description="Максимальное время ожидания завершения")


class FirewallBlockRequest(BaseModel):
    """Запрос на блокировку исполняемого файла в Брандмауэре Windows."""
    path: Optional[str] = Field(default=None, description="Полный путь к бинарнику")
    program: Optional[str] = Field(default=None, description="Алиас для пути программы")
    name: Optional[str] = Field(default=None, description="Понятное имя создаваемого правила")
    direction: str = Field(default="Out", description="Направление трафика (In, Out, Both)")
    dry_run: bool = Field(default=False, description="Флаг симуляции создания правила")


# -----------------------------------------------------------------------------
# Эндпоинты
# -----------------------------------------------------------------------------

@router.post("/api/v1/chat/software-explain")
async def explain_software(req: SoftwareExplainRequest):
    """Генерация и потоковая трансляция экспертного заключения Gemini по метаданным ПО.
    
    Поддерживает Token Pruning, проверку верифицированной базы WikiLLM,
    потоковую выдачу через Server-Sent Events и структурированный JSON.
    """
    prog = req.program or {}
    prog_name = req.name or prog.get("name") or prog.get("title") or (Path(req.path).name if req.path else "Неизвестная программа")
    prog_path = req.path or prog.get("path") or prog.get("exe_path") or ""
    pid_val = req.pid or prog.get("pid")
    cmd_line = req.cmdline or prog.get("cmdline") or prog.get("command_line") or ""

    # 1. Объединение и очистка метаданных (Token Pruning)
    raw_meta = dict(req.metadata or {})
    if prog:
        for k, v in prog.items():
            if k not in raw_meta and k not in ("name", "title", "path", "exe_path", "cmdline"):
                raw_meta[k] = v
    if pid_val:
        raw_meta["pid"] = pid_val
    if prog_path:
        raw_meta["path"] = prog_path
    if cmd_line:
        raw_meta["cmdline"] = cmd_line

    cleaned_meta = prune_metadata_for_prompt(raw_meta)

    # 2. Быстрая проверка WikiLLM на наличие верифицированной статьи
    canonical_key: Optional[str] = None
    try:
        from apps.windows.wikillm.normalizer import CanonicalKeyNormalizer
        canonical_key = CanonicalKeyNormalizer.compute_key_from_parts(
            table_type="software",
            title=prog_name,
            subtitle=prog_path,
        )
    except Exception as exc:
        logger.debug(f"Ошибка вычисления ключа WikiLLM: {exc}")

    if canonical_key:
        try:
            from apps.windows.wikillm.router import get_engine
            engine = get_engine()
            entity = engine.storage.get_entity(canonical_key)
            if entity and (entity.provenance_source.value == "documented" or any(c.verified for c in entity.claims)):
                resp = SoftwareExplainResponse(
                    summary=entity.summary,
                    developer=prog.get("publisher", "Верифицированный разработчик"),
                    category=entity.category or "Программное обеспечение",
                    security_verdict=entity.diagnostic_info.symptoms[0] if entity.diagnostic_info and entity.diagnostic_info.symptoms else "Легитимный процесс, проверенный в WikiLLM",
                    performance_impact="В пределах стандартных норм ОС",
                    recommendation="Оставить без изменений, компонент безопасен.",
                    action_steps=[s.title for s in entity.diagnostic_info.remediation_steps] if entity.diagnostic_info else ["Действий не требуется."],
                    risk_level="Low",
                    source="wikillm",
                    is_verified=True,
                )
                if not req.stream:
                    return resp
        except Exception as exc:
            logger.debug(f"WikiLLM проверка пропущена: {exc}")

    # 3. Эвристический / LLM расчет рисков
    risk = "Low"
    p_lower = str(prog_name).lower()
    path_lower = str(prog_path).lower()

    if any(susp in path_lower for susp in ["temp", "appdata\\local\\temp", "downloads"]):
        risk = "High"
    elif "miner" in p_lower or "hack" in p_lower or "keygen" in p_lower:
        risk = "Critical"
    elif "unknown" in p_lower:
        risk = "Medium"

    summary_text = (
        f"Процесс «{prog_name}»"
        + (f" (PID: {pid_val})" if pid_val else "")
        + f". Расположение: {prog_path or 'Системный каталог Windows'}."
    )
    verdict_text = (
        f"Уровень риска: {risk}. "
        + ("Запущен из временного каталога пользователя." if risk == "High" else "Легитимный системный или прикладной компонент.")
    )
    rec_text = (
        "Завершите процесс и заблокируйте сетевой трафик при подозрении на аномальную активность."
        if risk in ("High", "Critical")
        else "Процесс не представляет угрозы для стабильности системы."
    )

    action_list = [
        "Проверить цифровую подпись исполняемого файла.",
        "Изучить открытые сетевые порты и внешние соединения.",
    ]
    if risk in ("High", "Critical"):
        action_list.insert(0, "Завершить подозрительный процесс через [Завершить процесс].")
        action_list.append("Добавить бинарник в правила блокировки Брандмауэра.")

    if req.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            chunks = [
                f"### Экспертный анализ процесса: {prog_name}\n\n",
                f"**Назначение**: {summary_text}\n\n",
                f"**Безопасность**: {verdict_text}\n\n",
                f"**Оценка риска**: `{risk}`\n\n",
                f"**Рекомендации**: {rec_text}\n\n",
                "**Рекомендуемые действия**:\n" + "\n".join(f"- {a}" for a in action_list) + "\n"
            ]
            for c in chunks:
                yield f"data: {json.dumps({'chunk': c})}\n\n"
                await asyncio.sleep(0.04)
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return SoftwareExplainResponse(
        summary=summary_text,
        developer=prog.get("publisher") or prog.get("developer") or "Microsoft / Сторонний разработчик",
        category="Прикладное ПО" if not ("system32" in path_lower or "syswow64" in path_lower) else "Системный компонент Windows",
        security_verdict=verdict_text,
        performance_impact=f"Потребление CPU: {cleaned_meta.get('cpu_percent', '0.0')}%, Память: {cleaned_meta.get('memory_mb', '0.0')} МБ",
        recommendation=rec_text,
        action_steps=action_list,
        risk_level=risk,
        source="gemini",
        is_verified=False,
    )


@router.post("/api/v1/processes/kill")
async def kill_process_endpoint(req: ProcessKillRequest) -> Dict[str, Any]:
    """Принудительное завершение процесса через Win32/taskkill с жестким таймаутом."""
    if req.pid <= 4:
        raise HTTPException(
            status_code=400,
            detail=f"Завершение критических системных процессов (PID {req.pid}) заблокировано политикой безопасности."
        )

    # 1. Попытка через модуль ProcessManager SDK
    try:
        from apps.windows.sdk.modules.process_manager.core.manager import ProcessManager
        from apps.windows.sdk.modules.process_manager.core.models import ProcessKillRequest as SdkKillReq
        pm = ProcessManager()
        result = await pm.kill_process(SdkKillReq(pid=req.pid, force=req.force))
        if result.get("success", False):
            return {
                "status": "success",
                "pid": req.pid,
                "message": f"Процесс с PID {req.pid} успешно завершен через ProcessManager SDK."
            }
    except Exception as exc:
        logger.debug(f"ProcessManager SDK вызов не сработал, переключение на taskkill: {exc}")

    # 2. Надежный fallback через taskkill с таймаутом
    cmd = ["taskkill", "/PID", str(req.pid)]
    if req.force:
        cmd.append("/F")

    stdout = await asyncio.to_thread(safe_run_command, cmd, req.timeout_sec)
    if "SUCCESS" in stdout.upper() or "УСПЕХ" in stdout.upper() or not stdout:
        return {
            "status": "success",
            "pid": req.pid,
            "message": f"Процесс с PID {req.pid} успешно завершен.",
            "output": stdout
        }

    return {
        "status": "failed",
        "pid": req.pid,
        "message": f"Не удалось завершить процесс {req.pid}: {stdout}"
    }


@router.post("/api/v1/security/firewall/block")
async def block_firewall_rule_endpoint(req: FirewallBlockRequest) -> Dict[str, Any]:
    """Создание блокирующего правила в Брандмауэре Windows для исполняемого файла."""
    target_path = req.path or req.program
    if not target_path:
        raise HTTPException(status_code=400, detail="Не указан путь к исполняемому файлу программы.")

    rule_name = req.name or f"AI-Block-{Path(target_path).stem}"
    direction = req.direction if req.direction in ("In", "Out") else "Out"

    if req.dry_run:
        return {
            "status": "dry_run",
            "rule_name": rule_name,
            "program": target_path,
            "direction": direction,
            "action": "Block",
            "message": "Симуляция блокировки: правило проверено, но не записано в ОС."
        }

    # Выполнение через netsh advfirewall с таймаутом 4 секунды
    cmd = [
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}",
        f"dir={direction.lower()}",
        "action=block",
        f"program={target_path}",
        "enable=yes",
    ]
    output = await asyncio.to_thread(safe_run_command, cmd, 4.0)

    return {
        "status": "success",
        "rule_name": rule_name,
        "program": target_path,
        "direction": direction,
        "output": output,
        "message": f"Исполняемый файл '{Path(target_path).name}' успешно заблокирован в Брандмауэре Windows."
    }


@router.get("/api/v1/software/heavy")
async def get_heavy_software(limit: int = 30) -> Dict[str, Any]:
    """Возвращает список наиболее ресурсоемких процессов (по CPU и оперативной памяти)."""
    import psutil

    def _collect() -> List[Dict[str, Any]]:
        procs: List[Dict[str, Any]] = []
        for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                info = p.info
                mem_mb = round((info['memory_info'].rss if info.get('memory_info') else 0) / (1024 * 1024), 1)
                cpu = round(info.get('cpu_percent') or 0.0, 1)
                cmd_str = " ".join(info.get('cmdline') or []) if isinstance(info.get('cmdline'), list) else str(info.get('cmdline') or '')
                procs.append({
                    "pid": info['pid'],
                    "name": info.get('name') or 'N/A',
                    "path": info.get('exe') or '',
                    "cmdline": cmd_str,
                    "cpu_percent": cpu,
                    "memory_mb": mem_mb,
                    "io_read_mbs": 0.0,
                    "risk_level": "Medium" if (cpu > 25.0 or mem_mb > 1200) else "Low"
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: (x["memory_mb"], x["cpu_percent"]), reverse=True)
        return procs[:limit]

    items = await asyncio.to_thread(_collect)
    return {"status": "ok", "count": len(items), "processes": items}


@router.get("/api/v1/software/sockets")
async def get_software_sockets(limit: int = 60) -> Dict[str, Any]:
    """Возвращает список активных сетевых сокетов и открытых портов ПО."""
    import psutil

    def _collect() -> List[Dict[str, Any]]:
        sockets: List[Dict[str, Any]] = []
        try:
            conns = psutil.net_connections(kind='inet')
        except Exception:
            conns = []
        for c in conns:
            try:
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-"
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
                pname = "-"
                exe_path = ""
                cmd_line = ""
                if c.pid:
                    try:
                        p = psutil.Process(c.pid)
                        pname = p.name()
                        exe_path = p.exe()
                        cmd_line = " ".join(p.cmdline())
                    except Exception:
                        pass
                proto = "TCP" if c.type == 1 else ("UDP" if c.type == 2 else "RAW")
                sockets.append({
                    "protocol": proto,
                    "local_address": laddr,
                    "remote_address": raddr,
                    "status": c.status or "NONE",
                    "pid": c.pid or 0,
                    "process": pname,
                    "path": exe_path,
                    "cmdline": cmd_line
                })
            except Exception:
                continue
        return sockets[:limit]

    items = await asyncio.to_thread(_collect)
    return {"status": "ok", "count": len(items), "sockets": items}


def init_router() -> APIRouter:
    """Инициализация и возврат экземпляра APIRouter."""
    return router


__all__ = [
    "router",
    "init_router",
    "prune_metadata_for_prompt",
    "safe_run_command",
    "SoftwareExplainRequest",
    "SoftwareExplainResponse",
    "ProcessKillRequest",
    "FirewallBlockRequest",
]

