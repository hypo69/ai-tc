# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - apps
# =============================================================================
# Description:
#   Эндпойнты статуса и конфигурации приложений /apps.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: apps.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:35:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from fastapi import HTTPException, Request
from pydantic import BaseModel

from header import __root__
from src.config import ai_cfg
from logger import logger
from apps.windows.api.auth import require_admin_user
from .routers import router_apps


# ============================================================================
# /apps Configuration & Status Endpoints
# ============================================================================


APPS_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "scenarios",
        "key": "scenarios",
        "tab": "tab-scenarios",
        "folder": "scenarios",
        "aliases": ["scenarios", "scenario", "tab-scenarios", "сценарии"],
        "name": "Test & Automation Scenarios",
        "ru_name": "Сценарии",
        "icon": "🎬",
    },
    {
        "id": "chat",
        "key": "chat",
        "tab": "tab-chat",
        "folder": "chat",
        "aliases": ["chat", "tab-chat", "dialog", "ai_chat"],
        "name": "AI Chat Assistant",
        "ru_name": "Чат ИИ",
        "icon": "💬",
    },
    {
        "id": "network_terminal",
        "key": "network_terminal",
        "tab": "tab-network",
        "folder": "network_terminal",
        "aliases": ["network_terminal", "network", "tab-network"],
        "name": "Network Analyzer Terminal",
        "ru_name": "Сетевой терминал",
        "icon": "🌐",
    },
    {
        "id": "system_inspector",
        "key": "system_inspector",
        "tab": "tab-hardware-load-inspector",
        "folder": "system_inspector",
        "aliases": ["system_inspector", "inspector", "tab-hardware-load-inspector", "tab-system-load-inspector", "tab-system-inspector", "system_load_inspector", "hardware_load_inspector"],
        "name": "System Inspector",
        "ru_name": "Потребление ресурсов",
        "icon": "🖥️",
    },
    {
        "id": "about_system",
        "key": "about_system",
        "tab": "tab-about-system",
        "folder": "about_system_tab",
        "aliases": ["about_system", "system_info", "sysinfo", "tab-about-system", "about"],
        "name": "About System",
        "ru_name": "О Системе",
        "icon": "ℹ️",
    },
    {
        "id": "windows_sysadmin",
        "key": "windows_sysadmin",
        "tab": "tab-windows-admin",
        "folder": "windows_sysadmin",
        "aliases": ["windows_sysadmin", "windows_admin", "windowsadmin", "sysadmin", "tab-windows-admin"],
        "name": "Windows System Administrator",
        "ru_name": "Windows Sysadmin",
        "icon": "🛡️",
    },
    {
        "id": "user_assistant",
        "key": "user_assistant",
        "tab": "tab-user-assistant",
        "folder": "user_assistant",
        "aliases": ["user_assistant", "assistant", "userassistant", "tab-user-assistant"],
        "name": "User Assistant",
        "ru_name": "User Assistant",
        "icon": "🗓️",
    },
    {
        "id": "system_control_center",
        "key": "system_control_center",
        "tab": "tab-system-control",
        "folder": "system_control_center",
        "aliases": ["system_control_center", "system_control", "control_center", "tab-system-control"],
        "name": "System Control Center",
        "ru_name": "System Control Center",
        "icon": "🛠️",
    },
    {
        "id": "system_log_viewer",
        "key": "system_log_viewer",
        "tab": "tab-system-logs",
        "folder": "system_log_viewer",
        "aliases": ["system_log_viewer", "system_logs", "system_log", "log_viewer", "logs_viewer", "tab-system-logs", "log_analyzer", "application_log_analyzer"],
        "name": "System Log Viewer",
        "ru_name": "Анализатор логов (All Logs)",
        "icon": "📜",
    },
    {
        "id": "research_and_statistic",
        "key": "research_and_statistic",
        "tab": "tab-research",
        "folder": "research_and_statistic",
        "aliases": ["research_and_statistic", "research_stat", "research", "tab-research"],
        "name": "Research & Statistics Desk",
        "ru_name": "Анализ данных и статистика",
        "icon": "📈",
    },
    {
        "id": "software_audit",
        "key": "software_audit",
        "tab": "tab-software-audit",
        "folder": "software_audit",
        "aliases": ["software_audit", "software", "audit_software", "installed_software", "tab-software-audit"],
        "name": "Software Audit",
        "ru_name": "Аудит программного обеспечения",
        "icon": "📊",
    },
    {
        "id": "registry_editor",
        "key": "registry_editor",
        "tab": "tab-registry-editor",
        "folder": "registry_editor",
        "aliases": ["registry_editor", "registry_viewer", "registry", "regedit", "reg_viewer", "tab-registry-editor", "tab-registry-viewer"],
        "name": "Registry Editor",
        "ru_name": "Редактор реестра (Registry Editor)",
        "icon": "🗝️",
    },
    {
        "id": "windows_startup_auditor",
        "key": "windows_startup_auditor",
        "tab": "tab-startup-auditor",
        "folder": "windows/startup",
        "aliases": ["windows_startup_auditor", "startup_auditor", "startup", "autoruns", "tab-startup-auditor"],
        "name": "Windows Startup Auditor",
        "ru_name": "Аудит автозапуска Windows",
        "icon": "🚀",
    },
    {
        "id": "boot_and_servicing",
        "key": "boot_and_servicing",
        "tab": "tab-boot-recovery",
        "folder": "boot_recovery_tab",
        "aliases": ["boot_winre", "sfc_dism", "sfc", "dism", "winre", "boot", "boot_recovery", "servicing_integrity"],
        "name": "Boot, WinRE & System Servicing (SFC/DISM)",
        "ru_name": "🚀 Загрузка, WinRE и обслуживание SFC/DISM",
        "icon": "🚀",
    },
    {
        "id": "windows_defender",
        "key": "windows_defender",
        "tab": "tab-defender",
        "folder": "windows_defender",
        "aliases": ["windows_defender", "defender", "tab-defender"],
        "name": "Windows Defender Security",
        "ru_name": "Безопасность Windows Defender",
        "icon": "🛡️",
    },
    {
        "id": "windows_backup_manager",
        "key": "windows_backup_manager",
        "tab": "tab-windows-backup",
        "folder": "windows_backup_manager",
        "aliases": ["windows_backup_manager", "backup_manager", "windows_backup", "backup", "tab-windows-backup"],
        "name": "Windows Backup & Libraries",
        "ru_name": "Резервное копирование и библиотеки Windows",
        "icon": "💾",
    },
    {
        "id": "software_transparency_scanner",
        "key": "software_transparency_scanner",
        "tab": "tab-software-transparency",
        "folder": "software_transparency_scanner",
        "aliases": ["software_transparency_scanner", "transparency_scanner", "software_transparency", "tab-software-transparency"],
        "name": "Software Transparency Scanner",
        "ru_name": "Инвентаризатор и прозрачность ПО (AI Transparency)",
        "icon": "🔍",
    },
    {
        "id": "hardware_monitor",
        "key": "hardware_monitor",
        "tab": "tab-hardware-monitor",
        "folder": "windows",
        "aliases": ["hardware_monitor", "hardware", "sensors", "hw_monitor", "tab-hardware-monitor"],
        "name": "Hardware & Sensors Monitor",
        "ru_name": "Монитор оборудования и сенсоров",
        "icon": "⚡",
    },
]


def get_apps_status(profile: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve enabled/disabled status for all /apps applications based on active configuration file."""
    import os
    cfg_env = os.getenv("AIWINDOWSADMIN_CONFIG") or os.getenv("CONFIG_FILE")
    active_path: Optional[Path] = None
    if profile in ("tc", "test-computer", "test_computer", "apps_tc"):
        for candidate in [__root__ / "config_tc.json", __root__ / "tc.json"]:
            if candidate.exists():
                active_path = candidate
                break
    elif cfg_env:
        p = Path(cfg_env)
        active_path = p if p.is_absolute() else (__root__ / cfg_env)

    if not active_path or not active_path.exists():
        for candidate in [__root__ / "config_tc.json", __root__ / "tc.json"]:
            if candidate.exists() and not (__root__ / "config.json").exists():
                active_path = candidate
                break
        if not active_path or not active_path.exists():
            active_path = __root__ / "config.json"

    apps_cfg: Any = {}
    config_filename = active_path.name if active_path else "config.json"
    if active_path and active_path.exists():
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                root_cfg = json.load(f)
                apps_cfg = root_cfg.get("apps", {})
        except Exception as e:
            logger.error(f"Error reading apps config from {active_path}: {e}")

    result_apps: Dict[str, Any] = {}

    # Анализ формата конфигурации apps (списки enabled/disabled, плоский список или legacy dict)
    enabled_set: Optional[set] = None
    disabled_set: set = set()
    enable_all = True

    if isinstance(apps_cfg, list):
        # Формат плоского списка активных приложений (например, config_tc.json)
        enabled_set = {str(item).strip().lower() for item in apps_cfg if item}
        enable_all = False
    elif isinstance(apps_cfg, dict):
        has_enabled_key = "enabled" in apps_cfg and isinstance(apps_cfg["enabled"], list)
        has_disabled_key = "disabled" in apps_cfg and isinstance(apps_cfg["disabled"], list)

        if has_enabled_key:
            enabled_set = {str(item).strip().lower() for item in apps_cfg["enabled"] if item}
        if has_disabled_key:
            disabled_set = {str(item).strip().lower() for item in apps_cfg["disabled"] if item}

        if "enable_all" in apps_cfg and isinstance(apps_cfg["enable_all"], bool):
            enable_all = apps_cfg["enable_all"]
        else:
            enable_all = True
    else:
        enable_all = True

    for app in APPS_REGISTRY:
        app_id = app["id"]
        key = app["key"]
        aliases = {a.lower() for a in app.get("aliases", [app_id, key, app["folder"], app["tab"]])}

        # 1. Проверка явного исключения в disabled
        if aliases.intersection(disabled_set):
            is_enabled = False
        # 2. Проверка включения в список enabled
        elif enabled_set is not None and aliases.intersection(enabled_set):
            is_enabled = True
        # 3. Проверка индивидуального булева флага в словаре
        elif isinstance(apps_cfg, dict) and key in apps_cfg and isinstance(apps_cfg[key], bool):
            is_enabled = apps_cfg[key]
        elif isinstance(apps_cfg, dict) and app_id in apps_cfg and isinstance(apps_cfg[app_id], bool):
            is_enabled = apps_cfg[app_id]
        else:
            is_enabled = bool(enable_all)

        # Проверка локального config.json микроприложения на явное отключение
        local_cfg_paths = [
            __root__ / "apps" / app["folder"] / "config.json",
            __root__ / "src" / "apps" / app["folder"] / "config.json",
        ]
        for lcp in local_cfg_paths:
            if lcp.exists():
                try:
                    with open(lcp, "r", encoding="utf-8") as lf:
                        local_data = json.load(lf)
                        if local_data.get("enabled") is False or local_data.get("active") is False:
                            is_enabled = False
                except Exception:
                    pass

        result_apps[app_id] = {
            "id": app_id,
            "key": key,
            "tab": app["tab"],
            "folder": app["folder"],
            "name": app["name"],
            "ru_name": app["ru_name"],
            "icon": app["icon"],
            "enabled": is_enabled,
        }

    # Включение дополнительных приложений из списка enabled_set (например, cloudflared_monitor)
    for extra_id in (enabled_set or set()):
        if extra_id not in result_apps:
            result_apps[extra_id] = {
                "id": extra_id,
                "key": extra_id,
                "tab": f"tab-{extra_id.replace('_', '-')}",
                "folder": extra_id,
                "name": extra_id,
                "ru_name": extra_id,
                "icon": "📱",
                "enabled": True,
            }

    ai_cfg = {}
    if active_path and active_path.exists():
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                root_data = json.load(f)
                ai_cfg = root_data.get("ai_providers_and_models_configuration") or root_data.get("ai", {})
        except Exception:
            pass

    return {
        "status": "ok",
        "config_file": config_filename,
        "enable_all": enable_all,
        "apps": result_apps,
        "ai": ai_cfg,
    }


class AppConfigUpdateRequest(BaseModel):
    """Payload for updating /apps application configuration."""
    config: Dict[str, Any]


@router_apps.get('/status')
async def get_public_apps_status_endpoint(profile: Optional[str] = None) -> Dict[str, Any]:
    """Get enabled/disabled status for all /apps applications."""
    return get_apps_status(profile=profile)


@router_apps.get('/{app_name}/config')
async def get_app_config(app_name: str, request: Request) -> Dict[str, Any]:
    """Get configuration for specified application under /apps."""
    require_admin_user(request)

    safe_name = "".join(c for c in app_name if c.isalnum() or c in ("_", "-"))
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid application name")

    candidates = [
        __root__ / "src" / "apps" / safe_name / "config.json",
        __root__ / "apps" / safe_name / "config.json",
    ]

    for path in candidates:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return {"status": "ok", "app": safe_name, "config": json.load(f), "path": str(path)}
            except Exception as e:
                logger.error(f"Error reading app config {path}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to read configuration: {e}")

    raise HTTPException(status_code=404, detail=f"Application config for '{safe_name}' not found")


@router_apps.post('/{app_name}/config')
async def set_app_config(app_name: str, data: AppConfigUpdateRequest, request: Request) -> Dict[str, Any]:
    """Update configuration for specified application under /apps."""
    require_admin_user(request)

    safe_name = "".join(c for c in app_name if c.isalnum() or c in ("_", "-"))
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid application name")

    candidates = [
        __root__ / "src" / "apps" / safe_name / "config.json",
        __root__ / "apps" / safe_name / "config.json",
    ]

    target_paths = [p for p in candidates if p.exists()]
    if not target_paths:
        target_paths = [__root__ / "apps" / safe_name / "config.json"]

    for path in target_paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving app config {path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")

    return {"status": "ok", "app": safe_name, "config": data.config, "message": "Конфигурация успешно сохранена"}

