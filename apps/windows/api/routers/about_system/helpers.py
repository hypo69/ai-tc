# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - helpers
# =============================================================================
# Description:
#   Вспомогательные функции панели «О системе».
#   Вынесено из router_about_system.py (этап 4 оптимизации).
#
# File: helpers.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-20 18:41:00
# =============================================================================

from __future__ import annotations

import json
import os
import platform
import re
from datetime import datetime
from typing import Any, Dict


from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage


from apps.windows.sdk import windows_sdk


def get_windows_install_date() -> str:
    """Возвращает дату установки Windows из реестра в формате 'DD.MM.YYYY HH:MM'."""
    if os.name == "nt":
        try:
            import winreg

            for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ):
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                        0,
                        access,
                    ) as key:
                        try:
                            val, _ = winreg.QueryValueEx(key, "InstallDate")
                            if val and int(val) > 0:
                                return datetime.fromtimestamp(int(val)).strftime("%d.%m.%Y %H:%M")
                        except Exception:
                            pass
                        try:
                            val, _ = winreg.QueryValueEx(key, "InstallTime")
                            if val and int(val) > 0:
                                epoch_sec = (int(val) / 10000000.0) - 11644473600.0
                                if epoch_sec > 0:
                                    return datetime.fromtimestamp(epoch_sec).strftime("%d.%m.%Y %H:%M")
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception as ex:
            logger.debug(f"[router_about_system] Ошибка чтения InstallDate из реестра: {ex}")
    return ""


def get_windows_workgroup() -> str:
    """Возвращает текущее имя рабочей группы (Workgroup) или домена Windows через Windows SDK."""
    return windows_sdk.modules.regional.get_workgroup()


def _format_uptime_human(seconds: float) -> str:
    """Форматирует секунды аптайма в человекочитаемую строку."""
    sec = int(max(0.0, seconds))
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    return f"{hours}h {minutes}m"


def _get_latest_snapshot_dict(storage: TelemetryStorage) -> Dict[str, Any]:
    """Извлекает и десериализует последний снимок из таблицы system_snapshots."""
    snapshots = storage.get_snapshots(limit=1)
    if not snapshots:
        return {}

    snap_row = dict(snapshots[0])
    raw_json_str = snap_row.get("raw_json")
    if raw_json_str:
        try:
            return json.loads(raw_json_str)
        except Exception as err:
            logger.debug(f"[router_about_system] Ошибка парсинга raw_json снимка: {err}")

    disks_str = snap_row.get("disks_json")
    if disks_str and isinstance(disks_str, str):
        try:
            snap_row["disks"] = json.loads(disks_str)
        except Exception as err:
            logger.debug(f"[router_about_system] Ошибка парсинга disks_json снимка: {err}")

    return snap_row


def _get_cpu_brand_name() -> str:
    """Получение коммерческого названия процессора (Brand Name) из реестра Windows или WMI."""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if val and val.strip():
                    return val.strip()
        except Exception:
            pass
    model = platform.processor() or ""
    if not model or "Intel64" in model or "AMD64" in model:
        return "Intel Core Processor" if "Intel" in model else "AMD Processor"
    return model


def get_current_user_account_info() -> Dict[str, Any]:
    """Возвращает сведения о текущей учетной записи пользователя Windows через Windows SDK."""
    return windows_sdk.modules.regional.get_user_account_info()


def get_windows_language_packs() -> list[dict[str, Any]]:
    """Возвращает список целевых и установленных языковых пакетов Windows через Windows SDK."""
    return windows_sdk.modules.regional.get_language_packs()


def install_windows_language_pack(tag: str) -> dict[str, Any]:
    """Устанавливает или активирует языковой пакет Windows через Windows SDK."""
    return windows_sdk.modules.regional.install_language_pack(tag)


def get_clean_system_timezone() -> str:
    """Возвращает чистое наименование часового пояса без повреждений кодировки."""
    try:
        return windows_sdk.modules.regional.get_timezone_display_string()
    except Exception:
        return "UTC+03:00"




