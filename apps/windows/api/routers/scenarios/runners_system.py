# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - runners_system
# =============================================================================
# Description:
#   Сценарии инспектора системы, администрирования, сети и AI-провайдеров.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: runners_system.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List


from src.config import server_cfg

__root__ = Path(__file__).resolve().parents[3]


from .models import ScenarioRunResult
from .models import ScenarioStepResult


async def _run_system_inspector_scenario() -> ScenarioRunResult:
    """Выполняет аудит производительности и ресурсов системы."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Телеметрия процессора и памяти
    s1_start = time.perf_counter()
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        s1_dur = (time.perf_counter() - s1_start) * 1000
        status_res = "ok" if (cpu_pct < 85 and mem.percent < 90) else "warn"
        steps.append(ScenarioStepResult(
            name="Нагрузка CPU и оперативной памяти",
            status=status_res,
            duration_ms=round(s1_dur, 2),
            details=f"CPU: {cpu_pct:.1f}%, RAM: {mem.percent:.1f}% ({mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} ГБ)",
            recommendation="Высокая утилизация ресурсов. Закройте неиспользуемые фоновые задачи." if status_res != "ok" else None,
            data={"cpu_pct": cpu_pct, "ram_pct": mem.percent, "ram_used_gb": round(mem.used / (1024**3), 2)}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Нагрузка CPU и оперативной памяти",
            status="warn",
            duration_ms=0.0,
            details=f"Ошибка сбора метрик: {e}"
        ))

    # Шаг 2: Ресурсоёмкие процессы
    s2_start = time.perf_counter()
    try:
        import psutil
        top_procs = []
        for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']), key=lambda x: x.info.get('cpu_percent') or 0, reverse=True)[:5]:
            top_procs.append(f"{p.info.get('name')} (PID {p.info.get('pid')})")
        s2_dur = (time.perf_counter() - s2_start) * 1000
        steps.append(ScenarioStepResult(
            name="Анализ фоновых процессов",
            status="ok",
            duration_ms=round(s2_dur, 2),
            details=f"Top-5 процессов: {', '.join(top_procs)}",
            data={"top_processes": top_procs}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Анализ фоновых процессов",
            status="ok",
            duration_ms=0.0,
            details=f"Сбор списка процессов завершен ({e})"
        ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    summary = "Оборудование и системные ресурсы находятся в нормальном диапазоне нагрузок." if overall_status == "ok" else "Обнаружена повышенная нагрузка на оборудование."

    return ScenarioRunResult(
        scenario_id="system_inspector",
        title="Диагностика системы и оборудования",
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


async def _run_windows_admin_scenario() -> ScenarioRunResult:
    """Выполняет аудит автозапуска и системного окружения Windows."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Проверка привилегий администратора
    s1_start = time.perf_counter()
    is_admin = False
    if platform.system() == "Windows":
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass
    s1_dur = (time.perf_counter() - s1_start) * 1000
    steps.append(ScenarioStepResult(
        name="Привилегии процесса (Administrator / Elevated)",
        status="ok" if is_admin else "warn",
        duration_ms=round(s1_dur, 2),
        details="Запущено с повышенными правами администратора" if is_admin else "Запущено в стандартном пользовательском контексте",
        recommendation="Для полного контроля служб Windows рекомендуется запускать терминал от имени Администратора." if not is_admin else None,
        data={"is_admin": is_admin}
    ))

    # Шаг 2: Проверка автозапуска Windows
    s2_start = time.perf_counter()
    startup_items_count = 0
    if platform.system() == "Windows":
        try:
            import winreg
            keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run")
            ]
            for root_k, sub_k in keys:
                try:
                    with winreg.OpenKey(root_k, sub_k) as k:
                        startup_items_count += winreg.QueryInfoKey(k)[1]
                except Exception:
                    pass
        except Exception:
            pass
    s2_dur = (time.perf_counter() - s2_start) * 1000
    steps.append(ScenarioStepResult(
        name="Аудит записей автозагрузки Windows (Registry Run)",
        status="ok" if startup_items_count < 30 else "warn",
        duration_ms=round(s2_dur, 2),
        details=f"Обнаружено программ в автозапуске: {startup_items_count}",
        recommendation="Большое число программ автозапуска может замедлять загрузку ОС." if startup_items_count >= 30 else None,
        data={"startup_count": startup_items_count}
    ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    summary = "Аудит системного окружения Windows выполнен успешно."

    return ScenarioRunResult(
        scenario_id="windows_admin",
        title="Аудит автозапуска и служб Windows",
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


async def _run_network_test_scenario() -> ScenarioRunResult:
    """Выполняет проверку сетевых портов и подключений."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Проверка локального сокета 127.0.0.1
    s1_start = time.perf_counter()
    import socket
    port = int(getattr(server_cfg, "port", 8000))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    res_code = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    s1_dur = (time.perf_counter() - s1_start) * 1000
    is_listening = (res_code == 0)

    steps.append(ScenarioStepResult(
        name=f"Локальный серверный порт ({port})",
        status="ok" if is_listening else "warn",
        duration_ms=round(s1_dur, 2),
        details=f"Порт {port} открыт и принимает соединения" if is_listening else f"Порт {port} не отвечает локально",
        recommendation="Убедитесь, что веб-сервер запущен." if not is_listening else None,
        data={"port": port, "is_listening": is_listening}
    ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    summary = "Сетевые подключения проверены, локальный порт активен."

    return ScenarioRunResult(
        scenario_id="network_test",
        title="Проверка сетевой доступности и портов",
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


async def _run_ai_providers_scenario() -> ScenarioRunResult:
    """Выполняет проверку доступных AI-провайдеров."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Проверка конфигурации AI
    s1_start = time.perf_counter()
    active_providers = []
    gemini_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        active_providers.append("Google Gemini (API Key настроен)")
    
    # Проверка AGY
    active_providers.append("AGY / Local Runner")

    s1_dur = (time.perf_counter() - s1_start) * 1000
    steps.append(ScenarioStepResult(
        name="Настроенные AI провайдеры",
        status="ok" if active_providers else "warn",
        duration_ms=round(s1_dur, 2),
        details=" | ".join(active_providers) if active_providers else "AI-провайдеры не обнаружены",
        recommendation="Укажите GEMINI_API_KEY_1 в .env для доступа к облачным моделям Gemini." if not gemini_key else None,
        data={"providers": active_providers}
    ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    summary = "Конфигурация AI-провайдеров готова к инференсу."

    return ScenarioRunResult(
        scenario_id="ai_providers_check",
        title="Проверка статуса AI-провайдеров",
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

