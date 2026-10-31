# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - runners_basic
# =============================================================================
# Description:
#   Сценарии быстрой проверки и аудита логов.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: runners_basic.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List


from logger import logger

__root__ = Path(__file__).resolve().parents[3]


from .models import ScenarioRunResult
from .models import ScenarioStepResult


# -----------------------------------------------------------------------------
# Scenario Runners
# -----------------------------------------------------------------------------

async def _run_quick_check_scenario() -> ScenarioRunResult:
    """Выполняет экспресс-проверку окружения (Smoke Test)."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Проверка среды исполнения Python
    step1_start = time.perf_counter()
    try:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        step1_dur = (time.perf_counter() - step1_start) * 1000
        steps.append(ScenarioStepResult(
            name="Среда исполнения Python и ОС",
            status="ok" if sys.version_info >= (3, 10) else "warn",
            duration_ms=round(step1_dur, 2),
            details=f"Python {py_ver}, ОС: {os_info}",
            recommendation="Рекомендуется Python 3.12+" if sys.version_info < (3, 12) else None,
            data={"python_version": py_ver, "os": os_info}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Среда исполнения Python и ОС",
            status="error",
            duration_ms=0.0,
            details=f"Ошибка проверки: {e}",
            recommendation="Проверьте системные переменные PATH."
        ))

    # Шаг 2: Проверка конфигурационных файлов
    step2_start = time.perf_counter()
    try:
        cfg_tc_path = __root__ / "config_tc.json"
        cfg_main_path = __root__ / "config.json"
        env_path = __root__ / ".env"
        details_list = []
        if cfg_tc_path.exists():
            details_list.append("config_tc.json [OK]")
        if cfg_main_path.exists():
            details_list.append("config.json [OK]")
        if env_path.exists():
            details_list.append(".env [OK]")
        else:
            details_list.append(".env [Отсутствует]")

        step2_dur = (time.perf_counter() - step2_start) * 1000
        steps.append(ScenarioStepResult(
            name="Конфигурационные файлы проекта",
            status="ok" if cfg_tc_path.exists() or cfg_main_path.exists() else "warn",
            duration_ms=round(step2_dur, 2),
            details=" | ".join(details_list),
            recommendation="Создайте файл .env на основе .env.example при необходимости API-ключей." if not env_path.exists() else None,
            data={"config_tc": cfg_tc_path.exists(), "config": cfg_main_path.exists(), "env": env_path.exists()}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Конфигурационные файлы проекта",
            status="error",
            duration_ms=0.0,
            details=f"Ошибка чтения конфигурации: {e}"
        ))

    # Шаг 3: Проверка дискового пространства
    step3_start = time.perf_counter()
    try:
        total, used, free = shutil.disk_usage(__root__)
        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        step3_dur = (time.perf_counter() - step3_start) * 1000
        status_disk = "ok" if free_gb >= 2.0 else ("warn" if free_gb >= 0.5 else "error")
        steps.append(ScenarioStepResult(
            name="Дисковое пространство рабочей директории",
            status=status_disk,
            duration_ms=round(step3_dur, 2),
            details=f"Свободно {free_gb:.2f} ГБ из {total_gb:.2f} ГБ",
            recommendation="Освободите место на диске для корректной записи логов и кэша." if status_disk != "ok" else None,
            data={"free_gb": round(free_gb, 2), "total_gb": round(total_gb, 2)}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Дисковое пространство рабочей директории",
            status="warn",
            duration_ms=0.0,
            details=f"Не удалось получить дисковое пространство: {e}"
        ))

    # Шаг 4: Проверка статуса логов ядра
    step4_start = time.perf_counter()
    try:
        logs_dir = __root__ / "logs"
        error_count = 0
        warn_count = 0
        if logs_dir.exists():
            for lf in logs_dir.glob("*.log"):
                try:
                    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()[-200:]
                        for line in lines:
                            if "ERROR" in line or "[CRITICAL]" in line:
                                error_count += 1
                            elif "WARN" in line or "[WARNING]" in line:
                                warn_count += 1
                except Exception:
                    pass
        step4_dur = (time.perf_counter() - step4_start) * 1000
        log_status = "ok" if error_count == 0 else ("warn" if error_count < 10 else "error")
        steps.append(ScenarioStepResult(
            name="Экспресс-анализ журналов логов",
            status=log_status,
            duration_ms=round(step4_dur, 2),
            details=f"Обнаружено критических ошибок: {error_count}, предупреждений: {warn_count}",
            recommendation="Запустите сценарий 'Аудит логов' для подробной диагностики выявленных ошибок." if error_count > 0 else None,
            data={"error_count": error_count, "warn_count": warn_count}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Экспресс-анализ журналов логов",
            status="warn",
            duration_ms=0.0,
            details=f"Не удалось прочитать директорию logs: {e}"
        ))

    # Шаг 5: Проверка активных микроприложений (/apps)
    step5_start = time.perf_counter()
    try:
        from apps.windows.api.server import load_tc_config
        tc_cfg = load_tc_config()
        apps_sec = tc_cfg.get("apps", {})
        enabled_apps = apps_sec.get("enabled", []) if isinstance(apps_sec, dict) else []
        step5_dur = (time.perf_counter() - step5_start) * 1000
        steps.append(ScenarioStepResult(
            name="Конфигурация микросервисов Test Computer",
            status="ok",
            duration_ms=round(step5_dur, 2),
            details=f"Активных приложений: {len(enabled_apps)} ({', '.join(enabled_apps[:6])}{'...' if len(enabled_apps) > 6 else ''})",
            data={"enabled_count": len(enabled_apps), "active_apps": enabled_apps}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Конфигурация микросервисов Test Computer",
            status="warn",
            duration_ms=0.0,
            details=f"Ошибка чтения статуса приложений: {e}"
        ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    if overall_status == "ok":
        summary = "Все базовые компоненты системы и среды функционируют штатно. Рекомендуется продолжить работу."
    elif overall_status == "warn":
        summary = f"Система запущена с {warn_cnt} некритическими замечаниями. Ознакомьтесь с рекомендациями по шагам."
    else:
        summary = f"Обнаружены критические сбои ({failed_cnt} ошибок). Требуется устранение неполадок перед началом работы."

    return ScenarioRunResult(
        scenario_id="quick_check",
        title="Быстрая проверка (Smoke Test)",
        status=overall_status,
        started_at=started_at,
        duration_ms=round(total_dur, 2),
        total_steps=len(steps),
        passed_steps=passed_cnt,
        warn_steps=warn_cnt,
        failed_steps=failed_cnt,
        steps=steps,
        summary=summary,
    )


async def _run_log_audit_scenario() -> ScenarioRunResult:
    """Выполняет аудит лог-файлов и системных журналов."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Инвентаризация файлов журналов
    s1_start = time.perf_counter()
    logs_dir = __root__ / "logs"
    found_files = []
    total_log_size_mb = 0.0
    if logs_dir.exists():
        for f in logs_dir.glob("*.log"):
            sz = f.stat().st_size / (1024 * 1024)
            total_log_size_mb += sz
            found_files.append({"name": f.name, "size_mb": round(sz, 2)})

    s1_dur = (time.perf_counter() - s1_start) * 1000
    steps.append(ScenarioStepResult(
        name="Инвентаризация файлов журналов в /logs",
        status="ok" if found_files else "warn",
        duration_ms=round(s1_dur, 2),
        details=f"Найдено файлов: {len(found_files)}, общий размер: {total_log_size_mb:.2f} МБ",
        recommendation="При отсутствии лог-файлов убедитесь, что логирование активно в config.json." if not found_files else None,
        data={"files": found_files, "total_size_mb": round(total_log_size_mb, 2)}
    ))

    # Шаг 2: Анализ ошибок приложения
    s2_start = time.perf_counter()
    recent_errors: List[str] = []
    recent_warnings: List[str] = []
    if logs_dir.exists():
        for lf in logs_dir.glob("*.log"):
            try:
                with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-300:]
                    for line in lines:
                        clean_line = line.strip()
                        if "ERROR" in clean_line or "[CRITICAL]" in clean_line:
                            if len(recent_errors) < 10:
                                recent_errors.append(f"[{lf.name}] {clean_line[:120]}")
                        elif "WARN" in clean_line:
                            if len(recent_warnings) < 10:
                                recent_warnings.append(f"[{lf.name}] {clean_line[:120]}")
            except Exception:
                pass

    s2_dur = (time.perf_counter() - s2_start) * 1000
    err_status = "ok" if len(recent_errors) == 0 else ("warn" if len(recent_errors) < 5 else "error")
    steps.append(ScenarioStepResult(
        name="Сканирование свежих записей на ошибки и сбои",
        status=err_status,
        duration_ms=round(s2_dur, 2),
        details=f"Свежих ошибок: {len(recent_errors)}, предупреждений: {len(recent_warnings)}",
        recommendation="Изучите список ошибок во вкладке 'Анализатор логов'." if recent_errors else None,
        data={"errors_sample": recent_errors, "warnings_sample": recent_warnings}
    ))

    # Шаг 3: Проверка Windows Event Logs (если доступно)
    s3_start = time.perf_counter()
    win_events_checked = False
    win_event_errors = 0
    if platform.system() == "Windows":
        try:
            from apps.windows.sdk.core.audits.eventlog_collector import EventLogCollector
            collector = EventLogCollector()
            events = collector.fetch_events(channel="Application", limit=30, level="Error")
            win_event_errors = len(events)
            win_events_checked = True
        except Exception as e:
            logger.debug(f"EventLogCollector skipped: {e}")

    s3_dur = (time.perf_counter() - s3_start) * 1000
    if win_events_checked:
        we_status = "ok" if win_event_errors == 0 else "warn"
        steps.append(ScenarioStepResult(
            name="Журнал событий Windows (Application EventLog)",
            status=we_status,
            duration_ms=round(s3_dur, 2),
            details=f"Ошибок за последнее время: {win_event_errors}",
            recommendation="Проверьте системные службы Windows." if win_event_errors > 0 else None,
            data={"win_error_count": win_event_errors}
        ))
    else:
        steps.append(ScenarioStepResult(
            name="Журнал событий Windows (Application EventLog)",
            status="ok",
            duration_ms=round(s3_dur, 2),
            details="Сбор журналов Windows EventLog пропущен или запущен на не-Windows хосте."
        ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    if overall_status == "ok":
        summary = "Аудит логов завершен успешно: критических сбоев и аномалий в журналах не выявлено."
    elif overall_status == "warn":
        summary = f"Аудит логов выявил {warn_cnt} предупреждений. Рекомендуется периодический просмотр свежих записей."
    else:
        summary = "В журналах логов обнаружены критические ошибки. Требуется детальный анализ причин сбоя."

    return ScenarioRunResult(
        scenario_id="log_audit",
        title="Аудит логов",
        status=overall_status,
        started_at=started_at,
        duration_ms=round(total_dur, 2),
        total_steps=len(steps),
        passed_steps=passed_cnt,
        warn_steps=warn_cnt,
        failed_steps=failed_cnt,
        steps=steps,
        summary=summary,
    )

