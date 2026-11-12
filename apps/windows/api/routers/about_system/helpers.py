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
# Updated: 2026-11-01 15:25:00
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


def format_wmi_date(date_str: Optional[str]) -> Optional[str]:
    """Преобразует дату формата WMI /Date(ms)/ или ISO в читаемую строку 'YYYY-MM-DD HH:MM:SS'."""
    if not date_str:
        return None
    raw = str(date_str).strip()
    if not raw or raw.lower() in ("never", "none", "null", "бессрочно", "никогда"):
        return "Никогда"
    m = re.search(r"\d{10,13}", raw)
    if m:
        try:
            val = int(m.group())
            sec = val / 1000.0 if len(m.group()) >= 12 else float(val)
            dt = datetime.fromtimestamp(sec)
            if dt.year > 2099:
                return "Никогда"
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return raw


def get_user_password_details(username: str) -> Dict[str, Any]:
    """
    Возвращает информацию о состоянии пароля пользователя и параметрах политики.

    Args:
        username: Имя локального пользователя.

    Returns:
        Словарь с флагами пароля, датами и глобальной политикой.
    """
    res = {
        "password_required": True,
        "password_never_expires": False,
        "cannot_change_password": False,
        "password_last_set": None,
        "password_expires": None,
        "bad_password_count": 0,
        "min_password_length": 0,
        "max_password_age_days": 42,
        "lockout_threshold": 0,
    }
    try:
        from apps.windows.sdk.modules.accounts_identity import get_accounts_identity_service
        srv = get_accounts_identity_service()
        user_acc = srv.get_user(username)
        if user_acc:
            res["password_required"] = user_acc.password_required
            res["password_never_expires"] = user_acc.password_never_expires
            res["cannot_change_password"] = user_acc.cannot_change_password
            res["password_last_set"] = format_wmi_date(user_acc.password_last_set)
            if user_acc.password_never_expires:
                res["password_expires"] = "Никогда (бессрочный)"
            else:
                res["password_expires"] = format_wmi_date(user_acc.password_expires)
            res["bad_password_count"] = user_acc.bad_password_count

        policy = srv.get_password_policy()
        if policy:
            res["min_password_length"] = policy.min_password_length
            res["max_password_age_days"] = policy.max_password_age_days
            res["lockout_threshold"] = policy.lockout_threshold
    except Exception as exc:
        logger.debug(f"[router_about_system] Ошибка сбора сведений о пароле: {exc}")
    return res


def change_user_password_helper(username: str, new_password: str) -> Dict[str, Any]:
    """Смена или установка нового пароля локального пользователя."""
    target_user = username.strip() or os.environ.get("USERNAME", "User")
    if not re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", target_user):
        return {"status": "error", "username": target_user, "message": "Недопустимое имя пользователя."}
    if not new_password:
        return {"status": "error", "username": target_user, "message": "Пароль не может быть пустым."}
    try:
        from apps.windows.sdk.modules.accounts_identity import get_accounts_identity_service
        srv = get_accounts_identity_service()
        policy = srv.get_password_policy()
        if policy and len(new_password) < policy.min_password_length:
            return {
                "status": "error",
                "username": target_user,
                "message": f"Пароль должен содержать не менее {policy.min_password_length} символов (политика хоста).",
            }
        success = srv.reset_user_password(target_user, new_password)
        if success:
            return {"status": "ok", "username": target_user, "message": f"Пароль пользователя '{target_user}' успешно изменен."}
        return {
            "status": "error",
            "username": target_user,
            "message": f"Не удалось изменить пароль пользователя '{target_user}'. Проверьте права администратора и сложность пароля.",
        }
    except Exception as exc:
        logger.error(f"[router_about_system] Ошибка смены пароля: {exc}", exc_info=True)
        return {"status": "error", "username": target_user, "message": f"Внутренняя ошибка: {exc}"}


def set_password_policy_helper(
    min_length: Optional[int] = None,
    max_age_days: Optional[int] = None,
    lockout_threshold: Optional[int] = None,
) -> Dict[str, Any]:
    """Настройка глобальной политики безопасности паролей хоста."""
    try:
        from apps.windows.sdk.modules.accounts_identity import get_accounts_identity_service
        srv = get_accounts_identity_service()
        success = srv.set_password_policy(
            min_length=min_length,
            max_age_days=max_age_days,
            lockout_threshold=lockout_threshold,
        )
        if success:
            return {"status": "ok", "message": "Глобальная политика безопасности паролей успешно обновлена."}
        return {"status": "error", "message": "Не удалось применить политику паролей. Требуются права администратора."}
    except Exception as exc:
        logger.error(f"[router_about_system] Ошибка изменения политики паролей: {exc}", exc_info=True)
        return {"status": "error", "message": f"Внутренняя ошибка: {exc}"}






