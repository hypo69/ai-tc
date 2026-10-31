# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - runners_update
# =============================================================================
# Description:
#   Сценарий безопасного обновления (Safe Update Guard).
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: runners_update.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List


__root__ = Path(__file__).resolve().parents[3]


from .models import ScenarioRunResult
from .models import ScenarioStepResult


async def _run_safe_update_guard_scenario() -> ScenarioRunResult:
    """Выполняет комплексную безопасную подготовку к установке крупных обновлений Windows (Feature Updates / 26H2)."""
    start_time = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: List[ScenarioStepResult] = []

    # Шаг 1: Проверка свободного места на диске C: (минимум 25 ГБ для обновления 26H2)
    s1_start = time.perf_counter()
    try:
        total, used, free = shutil.disk_usage("C:\\")
        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        s1_dur = (time.perf_counter() - s1_start) * 1000
        status_disk = "ok" if free_gb >= 25.0 else ("warn" if free_gb >= 15.0 else "error")
        steps.append(ScenarioStepResult(
            name="Проверка свободного места для установки обновления (Диск C:)",
            status=status_disk,
            duration_ms=round(s1_dur, 2),
            details=f"Свободно {free_gb:.2f} ГБ из {total_gb:.2f} ГБ (требуется от 25 ГБ для Windows 11 26H2)",
            recommendation="Освободите место на диске C: перед запуском установки крупного обновления." if status_disk != "ok" else None,
            data={"free_gb": round(free_gb, 2), "required_gb": 25.0}
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Проверка свободного места на диске C:",
            status="error",
            duration_ms=0.0,
            details=f"Ошибка проверки диска: {e}"
        ))

    # Шаг 2: Диагностика среды восстановления Windows RE (WinRE)
    s2_start = time.perf_counter()
    try:
        from apps.windows.sdk.modules.system_checkpoints.core.winre_manager import WinREManager
        winre_mgr = WinREManager()
        winre_stat = await asyncio.to_thread(winre_mgr.get_status)
        s2_dur = (time.perf_counter() - s2_start) * 1000
        winre_ok = winre_stat.enabled
        steps.append(ScenarioStepResult(
            name="Аудит среды восстановления Windows RE (reagentc)",
            status="ok" if winre_ok else "warn",
            duration_ms=round(s2_dur, 2),
            details=f"Среда WinRE: {'Включена и активна' if winre_ok else 'Отключена / Недоступна'}. Путь: {winre_stat.location or 'Стандартный'}",
            recommendation="Включите WinRE командами `reagentc /enable` в командной строке от Администратора." if not winre_ok else None,
            data=winre_stat.to_dict()
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Аудит среды восстановления Windows RE",
            status="warn",
            duration_ms=0.0,
            details=f"Ошибка опроса WinRE: {e}"
        ))

    # Шаг 3: Проверка и создание точки восстановления Windows (VSS)
    s3_start = time.perf_counter()
    try:
        from apps.windows.sdk.core.system_restore import WindowsSystemRestoreManager
        sr_mgr = WindowsSystemRestoreManager()
        prot_stat = sr_mgr.check_protection_status()

        if prot_stat.get("system_protection_enabled", False):
            res_sr = await asyncio.to_thread(
                sr_mgr.create_restore_point,
                description="Подготовка к обновлению Windows 11 26H2",
                restore_point_type="WINDOWS_UPDATE"
            )
            s3_dur = (time.perf_counter() - s3_start) * 1000
            sr_success = res_sr.get("success", False)
            steps.append(ScenarioStepResult(
                name="Создание нативной точки восстановления Windows (VSS)",
                status="ok" if sr_success else "warn",
                duration_ms=round(s3_dur, 2),
                details=res_sr.get("message", "Точка восстановления обработана."),
                recommendation=res_sr.get("error") if not sr_success else None,
                data=res_sr
            ))
        else:
            s3_dur = (time.perf_counter() - s3_start) * 1000
            steps.append(ScenarioStepResult(
                name="Создание нативной точки восстановления Windows (VSS)",
                status="warn",
                duration_ms=round(s3_dur, 2),
                details="Защита системы (System Protection) отключена для диска C:.",
                recommendation="Включите защиту системы в свойствах 'Защита системы' (SystemPropertiesProtection).",
                data=prot_stat
            ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Создание нативной точки восстановления Windows (VSS)",
            status="error",
            duration_ms=0.0,
            details=f"Исключение при вызове VSS: {e}"
        ))

    # Шаг 4: Регистрация контрольной точки PRE_UPDATE в координаторе
    s4_start = time.perf_counter()
    try:
        from apps.windows.sdk.modules.system_checkpoints.core.checkpoint_coordinator import CheckpointCoordinator
        from apps.windows.sdk.modules.system_checkpoints.models import CheckpointCreateRequest, CheckpointType

        coord = CheckpointCoordinator()
        chk_req = CheckpointCreateRequest(
            checkpoint_type=CheckpointType.PRE_UPDATE,
            title="Перед обновлением Windows 11 26H2",
            description="Автоматическая контрольная точка перед установкой накопительного/крупного обновления 26H2",
            create_restore_point=False,
            create_wim_image=False,
        )
        res_chk = await asyncio.to_thread(coord.create_checkpoint, chk_req)
        s4_dur = (time.perf_counter() - s4_start) * 1000
        steps.append(ScenarioStepResult(
            name="Регистрация контрольной точки в каталоге system_checkpoints",
            status="ok" if res_chk.get("success", False) else "warn",
            duration_ms=round(s4_dur, 2),
            details=f"Контрольная точка зарегистрирована ID: {res_chk.get('checkpoint_id', 'N/A')}",
            data=res_chk
        ))
    except Exception as e:
        steps.append(ScenarioStepResult(
            name="Регистрация контрольной точки в каталоге system_checkpoints",
            status="warn",
            duration_ms=0.0,
            details=f"Не удалось зарегистрировать запись в каталоге: {e}"
        ))

    total_dur = (time.perf_counter() - start_time) * 1000
    failed_cnt = sum(1 for s in steps if s.status == "error")
    warn_cnt = sum(1 for s in steps if s.status == "warn")
    passed_cnt = sum(1 for s in steps if s.status == "ok")
    overall_status = "error" if failed_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")

    if overall_status == "ok":
        summary = "Подготовка к обновлению Windows завершена успешно: создана точка восстановления, проверена WinRE и свободное место на диске."
    elif overall_status == "warn":
        summary = f"Подготовка к обновлению завершена с {warn_cnt} предупреждениями. Проверьте рекомендации перед переходом к установке."
    else:
        summary = "Обнаружены критические препятствия перед обновлением. Не рекомендуем запускать обновление до устранения ошибок."

    return ScenarioRunResult(
        scenario_id="safe_update_guard",
        title="Безопасная подготовка к обновлению Windows (Safe Update Guard)",
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

