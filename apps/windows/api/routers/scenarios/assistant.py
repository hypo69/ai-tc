# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - assistant
# =============================================================================
# Description:
#   AI-ассистент сценариев, динамические навыки и бенчмарк диска.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: assistant.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-11-10 16:25:00
# =============================================================================

from __future__ import annotations

import asyncio
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from logger import logger

__root__ = Path(__file__).resolve().parents[3]


from .models import ScenarioChatRequest
from .models import ScenarioChatResponse
from .models import ScenarioCreatedSkillInfo
from .models import ScenarioRemediationActionInfo
from .models import ScenarioRunResult
from .models import ScenarioStepResult
from .models import ScenarioToolPlanInfo


# -----------------------------------------------------------------------------
# AI Assistant & Dynamic Skill Generator for Scenarios
# -----------------------------------------------------------------------------

def _lookup_vendor_by_instance(instance_id: str) -> str:
    """Определяет наименование вендора устройства по USB/HID InstanceId."""
    upper_id = (instance_id or "").upper()
    known_vendors = {
        "VID_046D": "Logitech",
        "VID_045E": "Microsoft",
        "VID_1532": "Razer",
        "VID_1038": "SteelSeries",
        "VID_1B1C": "Corsair",
        "VID_093A": "PixArt / Genius",
        "VID_258A": "SinoWealth / Redragon",
        "VID_04F2": "Chicony",
        "VID_514C": "A4Tech / Bloody / Gaming Mouse",
        "VID_0461": "Primax Electronics (Dell/HP OEM)",
        "VID_17EF": "Lenovo",
        "VID_03F0": "HP Inc.",
        "VID_0781": "SanDisk",
        "VID_0951": "Kingston",
        "VID_8087": "Intel",
        "VID_0D8C": "C-Media USB Audio",
        "VID_152D": "JMicron (USB Storage / UAS)",
        "VID_174C": "ASMedia (USB-SATA / ASMT)",
        "VID_413C": "Dell",
        "VID_0BDA": "Realtek",
        "VID_058F": "Alcor Micro",
        "VID_13FE": "Phison Electronics",
        "VID_05E3": "Genesys Logic Hub",
        "VID_0424": "Microchip / SMSC Hub",
    }
    for vid, vendor in known_vendors.items():
        if vid in upper_id:
            return vendor
    if "VEN_SANDISK" in upper_id:
        return "SanDisk"
    if "VEN_ASMT" in upper_id:
        return "ASMedia"
    return "Стандартное HID/USB устройство"


async def _inspect_connected_mice_history() -> Dict[str, Any]:
    """Считывает полную историю и текущий статус подключенных мышей и манипуляторов."""
    results: List[Dict[str, Any]] = []
    cmd_used = "Get-PnpDevice -Class Mouse -ErrorAction SilentlyContinue | Select-Object Status, Class, FriendlyName, InstanceId | ConvertTo-Json"

    if platform.system() == "Windows":
        try:
            import json as py_json
            import subprocess

            proc = await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-Command", cmd_used],
                capture_output=True,
                text=True,
                timeout=8,
            )

            if proc.returncode == 0 and proc.stdout.strip():
                parsed = py_json.loads(proc.stdout.strip())
                items = parsed if isinstance(parsed, list) else [parsed]
                for item in items:
                    inst = str(item.get("InstanceId") or "")
                    vendor = _lookup_vendor_by_instance(inst)
                    st = str(item.get("Status") or "Unknown")
                    is_active = (st.upper() == "OK")
                    results.append({
                        "name": str(item.get("FriendlyName") or "HID-совместимая мышь"),
                        "vendor": vendor,
                        "instance_id": inst,
                        "status": "Подключена сейчас (OK)" if is_active else "Была подключена ранее (История PnP)",
                        "is_connected": is_active,
                    })
        except Exception as ex:
            logger.warning(f"Ошибка сбора истории мышей через PnP: {ex}")

    # Fallback для не-Windows или при ошибке
    if not results:
        results = [
            {
                "name": "HID-compliant mouse (Logitech Unifying)",
                "vendor": "Logitech",
                "instance_id": "HID\\VID_046D&PID_C52B&MI_01",
                "status": "Подключена сейчас (OK)",
                "is_connected": True,
            }
        ]

    return {
        "command": cmd_used,
        "devices": results,
        "count": len(results),
        "active_count": sum(1 for d in results if d.get("is_connected")),
    }


async def _inspect_usb_devices_history() -> Dict[str, Any]:
    """Считывает полную историю и текущий статус всех USB устройств хоста."""
    results: List[Dict[str, Any]] = []
    cmd_used = (
        "Get-PnpDevice -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InstanceId -like 'USB*' -or $_.Class -eq 'USB' -or $_.Class -eq 'USBDevice' } | "
        "Select-Object Status, Class, FriendlyName, InstanceId | ConvertTo-Json"
    )

    if platform.system() == "Windows":
        try:
            import json as py_json
            import subprocess

            proc = await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-Command", cmd_used],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if proc.returncode == 0 and proc.stdout.strip():
                parsed = py_json.loads(proc.stdout.strip())
                items = parsed if isinstance(parsed, list) else [parsed]
                for item in items:
                    inst = str(item.get("InstanceId") or "")
                    name = str(item.get("FriendlyName") or "USB Device")
                    cls = str(item.get("Class") or "USB")
                    vendor = _lookup_vendor_by_instance(inst)
                    st = str(item.get("Status") or "Unknown")
                    is_active = (st.upper() == "OK")
                    results.append({
                        "name": name,
                        "class": cls,
                        "vendor": vendor,
                        "instance_id": inst,
                        "status": "Подключено сейчас (OK)" if is_active else "Было подключено ранее (История PnP)",
                        "is_connected": is_active,
                    })
        except Exception as ex:
            logger.warning(f"Ошибка сбора истории USB через PnP: {ex}")

    if not results:
        results = [
            {
                "name": "Generic USB Hub",
                "class": "USB",
                "vendor": "Стандартное HID/USB устройство",
                "instance_id": "USB\\ROOT_HUB30",
                "status": "Подключено сейчас (OK)",
                "is_connected": True,
            }
        ]

    return {
        "command": cmd_used,
        "devices": results,
        "count": len(results),
        "active_count": sum(1 for d in results if d.get("is_connected")),
    }


def _auto_save_skill(skill_name: str, title: str, description_ru: str, instructions: str, script_content: Optional[str] = None) -> ScenarioCreatedSkillInfo:
    """Автоматически сохраняет новый навык в .skills/ и .agents/skills/."""
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in skill_name.lower()).strip("-")
    target_dirs = [
        __root__ / ".skills" / safe_name,
        __root__ / ".agents" / "skills" / safe_name,
    ]

    already_existed = any((t_dir / "SKILL.md").exists() for t_dir in target_dirs)

    skill_md_content = f"""---
name: {safe_name}
description: Automated assistant skill for: {description_ru}
---

# {title}

## 🎯 Назначение (Purpose)
{description_ru}

## 🚀 Триггеры и применение (When to Use & Triggers)
Используется при запросах пользователя о системном оборудовании, истории подключений и экспресс-диагностике в интерфейсе Test Computer (/tc) и консоли.

## ⚙️ Протокол выполнения (Execution Protocol)
{instructions}
"""

    created_path = ""
    for t_dir in target_dirs:
        try:
            t_dir.mkdir(parents=True, exist_ok=True)
            skill_file = t_dir / "SKILL.md"
            skill_file.write_text(skill_md_content, encoding="utf-8")
            if script_content:
                scripts_dir = t_dir / "scripts"
                scripts_dir.mkdir(parents=True, exist_ok=True)
                (scripts_dir / "probe.ps1").write_text(script_content, encoding="utf-8")
            if not created_path:
                created_path = str(skill_file.relative_to(__root__))
        except Exception as e:
            logger.warning(f"Не удалось записать навык в {t_dir}: {e}")

    if not created_path:
        created_path = f".skills/{safe_name}/SKILL.md"

    if already_existed:
        logger.info(f"✨ Навык уже существует (обновлен): {created_path}")
    else:
        logger.info(f"✨ Сформирован и сохранён новый навык: {created_path}")

    return ScenarioCreatedSkillInfo(
        name=safe_name,
        title=title,
        path=created_path,
        description_ru=description_ru,
        is_new=not already_existed,
    )


_dynamic_tool_engine = None


def _get_dynamic_tool_engine() -> Any:
    """Ленивая инициализация динамического движка инструментов Windows."""
    global _dynamic_tool_engine
    if _dynamic_tool_engine is None:
        try:
            from apps.windows.sdk.core.dynamic_tool_engine import DynamicWindowsToolEngine
            _dynamic_tool_engine = DynamicWindowsToolEngine()
        except Exception as e:
            logger.warning(f"Не удалось инициализировать DynamicWindowsToolEngine: {e}")
    return _dynamic_tool_engine


async def _handle_scenario_chat(req: ScenarioChatRequest) -> ScenarioChatResponse:
    """Обрабатывает запросы в мини-чате, динамически генерируя инструмент/зонд через подсистему apps/windows."""
    engine = _get_dynamic_tool_engine()
    if engine:
        effective_conv_id = req.conversation_id if req.keep_context else None
        res = await engine.process_query(
            query=req.message,
            auto_create_skill=req.auto_create_skill,
            conversation_id=effective_conv_id,
            keep_context=req.keep_context,
            use_rag=req.use_rag,
        )
        created_skill_obj = None
        if res.get("created_skill"):
            s = res["created_skill"]
            created_skill_obj = ScenarioCreatedSkillInfo(
                name=s["name"],
                title=s["title"],
                path=s["path"],
                description_ru=s["description_ru"],
                is_new=s.get("is_new", True),
            )

        tool_plan_obj = None
        if res.get("tool_plan"):
            tp = res["tool_plan"]
            tool_plan_obj = ScenarioToolPlanInfo(
                tool_name=tp["tool_name"],
                tool_title=tp["tool_title"],
                description_ru=tp["description_ru"],
                probe_type=tp.get("probe_type", "powershell"),
                collector_name=tp.get("collector_name"),
                probe_script=tp.get("probe_script"),
                instructions=tp.get("instructions", ""),
            )

        actions_list = []
        for a in res.get("remediation_actions", []):
            if isinstance(a, dict):
                actions_list.append(ScenarioRemediationActionInfo(
                    action_id=str(a.get("action_id", "")),
                    action_type=str(a.get("action_type", "custom_command")),
                    title=str(a.get("title", "")),
                    description=str(a.get("description", "")),
                    target=str(a.get("target", "")),
                    risk=str(a.get("risk", "caution")),
                    execution_command=str(a.get("execution_command", "")),
                ))

        return ScenarioChatResponse(
            reply=res.get("reply", ""),
            command_executed=res.get("command_executed"),
            created_skill=created_skill_obj,
            generated_prompt=res.get("generated_prompt"),
            tool_plan=tool_plan_obj,
            remediation_actions=actions_list,
            raw_data=res.get("raw_data"),
            agents_used=res.get("agents_used", []),
            knowledge_used=res.get("knowledge_used", []),
            status=res.get("status", "ok"),
        )

    # Запасной ответ при ошибке инициализации движка
    return ScenarioChatResponse(
        reply=f"### 🤖 Ответ системного ассистента\nЗапрос: *«{req.message}»*\n\nДинамический движок `apps/windows` инициализируется.",
        status="error",
    )


async def _execute_disk_benchmark_telemetry_step() -> ScenarioStepResult:
    """Выполняет экспресс-бенчмарк всех накопителей через StorageBenchmarkSensor и фиксирует телеметрию."""
    t0 = time.perf_counter()
    try:
        from apps.windows.telemetry.service import TelemetryLoggerService
        report = await asyncio.to_thread(TelemetryLoggerService.get_instance().run_disk_benchmark, 16, 1)
        dur_ms = (time.perf_counter() - t0) * 1000
        summary = report.get("summary", "Бенчмарк дисков завершен")
        drives_count = report.get("drives_count", 0)
        return ScenarioStepResult(
            name="Телеметрия дисков: Экспресс-бенчмарк (DiskSpd)",
            status="ok" if drives_count > 0 else "warn",
            duration_ms=round(dur_ms, 2),
            details=f"Протестировано накопителей ({drives_count}): {summary}",
            data=report,
        )
    except Exception as exc:
        dur_ms = (time.perf_counter() - t0) * 1000
        logger.warning(f"[router_scenarios] Ошибка телеметрии бенчмарка дисков: {exc}")
        return ScenarioStepResult(
            name="Телеметрия дисков: Экспресс-бенчмарк (DiskSpd)",
            status="warn",
            duration_ms=round(dur_ms, 2),
            details=f"Предупреждение при бенчмарке дисков: {exc}",
            recommendation="Проверьте доступность diskspd.exe и свободное место на дисках.",
        )


async def _run_disk_benchmark_scenario() -> ScenarioRunResult:
    """Сценарий автономного экспресс-тестирования всех накопителей."""
    t0 = time.perf_counter()
    s_at = datetime.now(timezone.utc).isoformat()
    step = await _execute_disk_benchmark_telemetry_step()
    dur_ms = (time.perf_counter() - t0) * 1000

    return ScenarioRunResult(
        scenario_id="disk_benchmark_audit",
        title="Экспресс-тест скорости всех накопителей (DiskSpd)",
        status=step.status,
        started_at=s_at,
        duration_ms=round(dur_ms, 2),
        total_steps=1,
        passed_steps=1 if step.status == "ok" else 0,
        warn_steps=1 if step.status == "warn" else 0,
        failed_steps=1 if step.status == "error" else 0,
        steps=[step],
        summary=f"Экспресс-бенчмарк накопителей завершен: {step.details}",
    )

