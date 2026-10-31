# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Regional - Manager
# =============================================================================
# Description:
#   Менеджер региональных параметров Windows, языковых пакетов (MUI),
#   часовых поясов, локалей и профилей учетных записей.
#   Централизует все операции взаимодействия с операционной системой Windows
#   в соответствии со стандартами архитектуры Windows SDK.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.regional import RegionalManager
#
#     rm = RegionalManager()
#     packs = rm.get_language_packs()
#     res = rm.install_language_pack("ru-RU")
#     tz = rm.get_current_timezone()
#     rm.set_timezone("Russian Standard Time")
#
# File: manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.regional
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:30:00
# =============================================================================

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import platform
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.common.telemetry_logger import AppTelemetryLogger
from apps.windows.sdk.modules.regional.keyboard_helper import (
    collect_language_packs_full,
    manage_language_pack_action,
)


class RegionalManager:
    """Менеджер региональных настроек, языковых пакетов и окружения Windows."""

    def __init__(self) -> None:
        """Инициализация менеджера региональных параметров и телеметрии."""
        self._telemetry_logger = AppTelemetryLogger("regional_manager")
        self._is_windows = (os.name == "nt" or platform.system().lower() == "windows")

    def _run_ps_command(self, script: str, timeout: int = 15) -> Tuple[int, str, str]:
        """Безопасный запуск PowerShell скрипта в неинтерактивном режиме.

        Args:
            script: Команда или блок команд PowerShell.
            timeout: Лимит времени выполнения в секундах.

        Returns:
            Tuple[int, str, str]: Код завершения, стандартный вывод и ошибка.
        """
        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"[RegionalManager] Таймаут PowerShell команды ({timeout}s)")
            return -1, "", f"Превышен лимит времени выполнения ({timeout}s)"
        except Exception as exc:
            logger.error(f"[RegionalManager] Исключение PowerShell: {exc}")
            return -1, "", str(exc)

    # =========================================================================
    # 1. Языковые пакеты Windows (Language Packs / MUI) и раскладки клавиатуры
    # =========================================================================

    def get_language_packs(self) -> List[Dict[str, Any]]:
        """Возвращает список целевых и физически установленных языковых пакетов и раскладок клавиатуры Windows.

        Считывает установленные MUI-пакеты из реестра, активные языки профиля
        и все подключенные/доступные клавиатурные раскладки (Preload + Substitutes)
        для приоритетной тройки языков: Русский, Иврит, Английский.

        Returns:
            List[Dict[str, Any]]: Список структур с метаданными языковых пакетов и раскладок.
        """
        return collect_language_packs_full(self._is_windows)

    def install_language_pack(self, tag: str) -> Dict[str, Any]:
        """Устанавливает или активирует языковой пакет Windows (ru-RU, he-IL, en-US).

        Args:
            tag: Код языка (например: 'ru-RU', 'he-IL', 'en-US').

        Returns:
            Dict[str, Any]: Результат с полями status, tag, name, message, is_installed, is_active.
        """
        clean_tag = tag.strip()
        if not re.match(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,4})?$", clean_tag):
            return {
                "status": "error",
                "tag": clean_tag,
                "name": clean_tag,
                "message": f"Недопустимый языковой тэг: '{clean_tag}'. Разрешены только стандартные BCP-47 коды.",
                "is_installed": False,
                "is_active": False,
            }
        res = manage_language_pack_action(self._is_windows, self._run_ps_command, clean_tag, "install")
        return {
            "status": res.get("status", "ok"),
            "tag": res.get("tag", clean_tag),
            "name": res.get("name", clean_tag),
            "message": res.get("message", ""),
            "is_installed": True,
            "is_active": True,
            "language_packs": res.get("language_packs", []),
        }

    def manage_language_pack(self, tag: str, action: str, klid: str = "") -> Dict[str, Any]:
        """Управляет языковым пакетом и раскладками клавиатуры (Русский, Иврит, Английский).

        Args:
            tag: Код языка ('ru-RU', 'he-IL', 'en-US').
            action: Операция ('install', 'activate', 'deactivate', 'set_default_input',
                    'set_display_language', 'add_layout', 'remove_layout', 'sync_trio').
            klid: 8-символьный идентификатор раскладки для 'add_layout'/'remove_layout'.

        Returns:
            Dict[str, Any]: Результат операции и актуальный список пакетов.
        """
        return manage_language_pack_action(self._is_windows, self._run_ps_command, tag, action, klid)

    # =========================================================================
    # 2. Часовые пояса (Timezones)
    # =========================================================================

    def get_current_timezone(self) -> str:
        """Возвращает идентификатор текущего часового пояса Windows."""
        if not self._is_windows:
            return "UTC"
        try:
            res = subprocess.run(["tzutil.exe", "/g"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception as exc:
            logger.debug(f"[RegionalManager] Ошибка чтения tzutil /g: {exc}")
        return ""

    def get_timezone_display_string(self) -> str:
        """Возвращает отформатированную строку часового пояса без повреждений кодировки."""
        if not self._is_windows:
            return "UTC (UTC+00:00)"
        tz_key = ""
        tz_name = ""
        try:
            class DYNAMIC_TIME_ZONE_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("Bias", ctypes.c_long),
                    ("StandardName", ctypes.c_wchar * 32),
                    ("StandardDate", ctypes.c_ushort * 8),
                    ("StandardBias", ctypes.c_long),
                    ("DaylightName", ctypes.c_wchar * 32),
                    ("DaylightDate", ctypes.c_ushort * 8),
                    ("DaylightBias", ctypes.c_long),
                    ("TimeZoneKeyName", ctypes.c_wchar * 128),
                    ("DynamicDaylightTimeDisabled", ctypes.c_bool),
                ]
            dtzi = DYNAMIC_TIME_ZONE_INFORMATION()
            res = ctypes.windll.kernel32.GetDynamicTimeZoneInformation(ctypes.byref(dtzi))
            tz_key = (dtzi.TimeZoneKeyName or "").strip()
            raw_name = (dtzi.DaylightName if res == 2 else dtzi.StandardName).strip()
            if raw_name and not raw_name.startswith("@") and "?" not in raw_name:
                tz_name = raw_name
        except Exception as exc:
            logger.debug(f"[RegionalManager] Ошибка GetDynamicTimeZoneInformation: {exc}")

        if not tz_key:
            tz_key = self.get_current_timezone() or "UTC"

        from datetime import datetime
        tz_offset = datetime.now().astimezone().strftime("%z")
        offset_str = f"UTC{tz_offset[:3]}:{tz_offset[3:]}" if tz_offset else "UTC+03:00"

        if tz_name and tz_key and tz_name != tz_key:
            return f"{tz_name} ({tz_key}) ({offset_str})"
        return f"{tz_name or tz_key} ({offset_str})"

    def get_timezones(self) -> List[Dict[str, Any]]:
        """Возвращает список всех зарегистрированных часовых поясов Windows."""
        if not self._is_windows:
            return [{"id": "UTC", "display_name": "(UTC) Coordinated Universal Time", "offset_minutes": 0}]

        ps_cmd = (
            "[System.TimeZoneInfo]::GetSystemTimeZones() | "
            "Select-Object Id, DisplayName, @{N='Offset';E={$_.BaseUtcOffset.TotalMinutes}} | "
            "ConvertTo-Json -Compress"
        )
        code, stdout, _ = self._run_ps_command(ps_cmd, timeout=6)
        tz_list: List[Dict[str, Any]] = []

        if code == 0 and stdout:
            try:
                data = json.loads(stdout)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("Id"):
                            tz_list.append({
                                "id": str(item["Id"]),
                                "display_name": str(item.get("DisplayName", item["Id"])),
                                "offset_minutes": int(item.get("Offset") or 0),
                            })
            except Exception as exc:
                logger.debug(f"[RegionalManager] Ошибка парсинга таймзон: {exc}")

        if not tz_list:
            tz_list = [
                {"id": "UTC", "display_name": "(UTC) Coordinated Universal Time", "offset_minutes": 0},
                {"id": "Russian Standard Time", "display_name": "(UTC+03:00) Moscow, St. Petersburg", "offset_minutes": 180},
                {"id": "Israel Standard Time", "display_name": "(UTC+02:00) Jerusalem", "offset_minutes": 120},
                {"id": "Eastern Standard Time", "display_name": "(UTC-05:00) Eastern Time (US & Canada)", "offset_minutes": -300},
            ]

        return tz_list

    def set_timezone(self, timezone_id: str) -> Dict[str, Any]:
        """Изменяет системный часовой пояс через утилиту tzutil.exe /s.

        Args:
            timezone_id: Идентификатор таймзоны Windows.

        Returns:
            Dict[str, Any]: Словарь со статусом, старым и новым часовым поясом.
        """
        clean_tz = timezone_id.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\.\s\(\)\+]+$", clean_tz):
            return {
                "status": "error",
                "old_timezone": "",
                "new_timezone": clean_tz,
                "message": "Недопустимый формат идентификатора часового пояса.",
            }

        old_tz = self.get_current_timezone()

        if not self._is_windows:
            return {
                "status": "ok",
                "old_timezone": old_tz,
                "new_timezone": clean_tz,
                "message": f"Эмуляция смены часового пояса на {clean_tz}",
            }

        try:
            res = subprocess.run(["tzutil.exe", "/s", clean_tz], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                logger.console(f"Часовой пояс успешно изменен: {clean_tz}")
                return {
                    "status": "ok",
                    "old_timezone": old_tz,
                    "new_timezone": clean_tz,
                    "message": f"Часовой пояс успешно изменен на '{clean_tz}'.",
                }
            err_msg = res.stderr.strip() or res.stdout.strip()
            return {
                "status": "error",
                "old_timezone": old_tz,
                "new_timezone": clean_tz,
                "message": f"Ошибка tzutil: {err_msg}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "old_timezone": old_tz,
                "new_timezone": clean_tz,
                "message": f"Исключение при установке таймзоны: {exc}",
            }

    # =========================================================================
    # 3. Системные и пользовательские локали (Locales)
    # =========================================================================

    def get_current_locales(self) -> Dict[str, str]:
        """Возвращает системную и пользовательскую локали Windows."""
        sys_loc = "ru-RU"
        usr_loc = "ru-RU"
        if not self._is_windows:
            return {"system_locale": sys_loc, "user_locale": usr_loc}

        ps_cmd = "(Get-WinSystemLocale).Name; (Get-Culture).Name"
        code, stdout, _ = self._run_ps_command(ps_cmd, timeout=4)
        if code == 0 and stdout:
            lines = [l.strip() for l in stdout.splitlines() if l.strip()]
            if len(lines) >= 1:
                sys_loc = lines[0]
            if len(lines) >= 2:
                usr_loc = lines[1]

        return {"system_locale": sys_loc, "user_locale": usr_loc}

    def set_locale(self, system_locale: str, user_locale: Optional[str] = None) -> Dict[str, Any]:
        """Устанавливает системную и пользовательскую локали Windows.

        Args:
            system_locale: Код системной локали (ANSI программы).
            user_locale: Код региональных форматов (User Culture).

        Returns:
            Dict[str, Any]: Словарь со статусом и флагом необходимости перезагрузки.
        """
        clean_sys = system_locale.strip()
        clean_usr = (user_locale or clean_sys).strip()

        if not self._is_windows:
            return {"status": "ok", "locale": clean_sys, "message": "Эмуляция установки локали", "reboot_required": True}

        ps_cmd = f"Set-WinSystemLocale -SystemLocale '{clean_sys}'; Set-Culture -CultureInfo '{clean_usr}'"
        code, stdout, stderr = self._run_ps_command(ps_cmd, timeout=10)

        if code == 0:
            logger.console(f"Системная локаль обновлена: {clean_sys}")
            return {
                "status": "ok",
                "locale": clean_sys,
                "message": f"Локаль изменена на '{clean_sys}'. Требуется перезагрузка Windows.",
                "reboot_required": True,
            }

        err = stderr or stdout
        return {"status": "error", "locale": clean_sys, "message": f"Ошибка Set-WinSystemLocale: {err}", "reboot_required": False}

    # =========================================================================
    # 4. Пользователь и учетные записи (User Account Info)
    # =========================================================================

    def get_user_account_info(self) -> Dict[str, Any]:
        """Считывает подробные параметры текущего пользователя Windows."""
        username = os.environ.get("USERNAME", "User")
        domain = os.environ.get("USERDOMAIN", platform.node())
        profile_dir = os.environ.get("USERPROFILE", "")
        full_name = ""
        first_name = ""
        last_name = ""
        description = ""
        sid_str = ""
        groups: List[str] = []
        is_admin = False
        last_logon = ""

        if self._is_windows:
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                is_admin = False

            # Чтение SID пользователя
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList") as p_key:
                    num_subkeys, _, _ = winreg.QueryInfoKey(p_key)
                    for idx in range(num_subkeys):
                        sub_name = winreg.EnumKey(p_key, idx)
                        try:
                            with winreg.OpenKey(p_key, sub_name) as s_key:
                                p_path, _ = winreg.QueryValueEx(s_key, "ProfileImagePath")
                                if p_path and os.path.normpath(p_path).lower() == os.path.normpath(profile_dir).lower():
                                    sid_str = sub_name
                                    break
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"[RegionalManager] Ошибка чтения ProfileList: {e}")

            # Чтение данных пользователя (ФИО и Должность) через Win32 NetUserGetInfo (нативный Unicode)
            try:
                class USER_INFO_10(ctypes.Structure):
                    _fields_ = [
                        ("usri10_name", wintypes.LPWSTR),
                        ("usri10_comment", wintypes.LPWSTR),
                        ("usri10_usr_comment", wintypes.LPWSTR),
                        ("usri10_full_name", wintypes.LPWSTR),
                    ]
                buf = ctypes.c_void_p()
                net_res = ctypes.windll.netapi32.NetUserGetInfo(None, username, 10, ctypes.byref(buf))
                if net_res == 0 and buf:
                    u_info = ctypes.cast(buf, ctypes.POINTER(USER_INFO_10)).contents
                    if u_info.usri10_full_name:
                        full_name = str(u_info.usri10_full_name).strip()
                    if u_info.usri10_comment:
                        description = str(u_info.usri10_comment).strip()
                    ctypes.windll.netapi32.NetApiBufferFree(buf)
            except Exception as e:
                logger.debug(f"[RegionalManager] Ошибка чтения NetUserGetInfo: {e}")

            # Фоллбек: чтение WMI Win32_UserAccount при отсутствии full_name
            if not full_name:
                try:
                    ps_cmd = (
                        f"Get-CimInstance Win32_UserAccount -Filter \"Name='{username}'\" | "
                        f"Select-Object FullName, Description, SID, AccountType | ConvertTo-Json -Compress"
                    )
                    code, stdout, _ = self._run_ps_command(ps_cmd, timeout=4)
                    if code == 0 and stdout:
                        data = json.loads(stdout)
                        if isinstance(data, dict):
                            full_name = data.get("FullName") or ""
                            if not description:
                                description = data.get("Description") or ""
                            if not sid_str:
                                sid_str = data.get("SID") or ""
                except Exception as exc:
                    logger.debug(f"[RegionalManager] Ошибка чтения Win32_UserAccount: {exc}")

            # Разбор Имени и Фамилии
            if full_name:
                parts = full_name.strip().split(maxsplit=1)
                first_name = parts[0]
                if len(parts) > 1:
                    last_name = parts[1]

            # Чтение групп безопасности через whoami
            try:
                res = subprocess.run(["whoami", "/groups", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        if not line.strip():
                            continue
                        row_parts = [p.strip(' "') for p in line.split(",")]
                        if row_parts and row_parts[0]:
                            grp_name = row_parts[0]
                            if not any(x in grp_name.upper() for x in ["NT AUTHORITY", "ОБЯЗАТЕЛЬНАЯ МЕТКА", "MANDATORY LABEL"]):
                                groups.append(grp_name)
            except Exception as exc:
                logger.debug(f"[RegionalManager] Ошибка чтения whoami /groups: {exc}")

        privilege_label = "Администратор" if is_admin else "Стандартный пользователь"
        account_type = "Локальная учетная запись"
        if domain and platform.node() and domain.lower() != platform.node().lower():
            account_type = f"Доменная учетная запись ({domain})"

        return {
            "username": username,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "description": description,
            "title": description,
            "job_title": description,
            "sid": sid_str,
            "profile_dir": profile_dir,
            "domain": domain,
            "is_admin": is_admin,
            "privilege": privilege_label,
            "account_type": account_type,
            "groups": groups,
            "last_logon": last_logon,
        }

    # =========================================================================
    # 5. Имя хоста и рабочая группа (Computer Name & Workgroup)
    # =========================================================================

    def get_workgroup(self) -> str:
        """Возвращает текущую рабочую группу или домен через NetGetJoinInformation."""
        if not self._is_windows:
            return "WORKGROUP"

        try:
            netapi32 = ctypes.windll.netapi32
            buf = wintypes.LPWSTR()
            join_type = wintypes.DWORD()
            res = netapi32.NetGetJoinInformation(None, ctypes.byref(buf), ctypes.byref(join_type))
            if res == 0 and buf.value:
                wg_name = buf.value
                netapi32.NetApiBufferFree(buf)
                return wg_name
        except Exception as exc:
            logger.debug(f"[RegionalManager] Ошибка NetGetJoinInformation: {exc}")

        return "WORKGROUP"

    def rename_computer(self, new_name: str, force: bool = True) -> Dict[str, Any]:
        """Переименовывает компьютер в операционной системе Windows.

        Args:
            new_name: Новое имя хоста (1-15 символов, буквы/цифры/дефис).
            force: Флаг принудительного выполнения.

        Returns:
            Dict[str, Any]: Результат с полями status, old_name, new_name, message.
        """
        old_name = platform.node() or "Host"
        clean_name = new_name.strip()

        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,13}[a-zA-Z0-9])?$", clean_name):
            return {
                "status": "error",
                "old_name": old_name,
                "new_name": clean_name,
                "message": "Недопустимый формат имени. Разрешены буквы, цифры и дефис, длина до 15 символов.",
            }

        if clean_name.lower() == old_name.lower():
            return {
                "status": "ok",
                "old_name": old_name,
                "new_name": clean_name,
                "message": "Имя совпадает с текущим. Изменения не требуются.",
            }

        if not self._is_windows:
            return {
                "status": "ok",
                "old_name": old_name,
                "new_name": clean_name,
                "message": f"Эмуляция переименования на {clean_name}",
            }

        ps_cmd = f"Rename-Computer -NewName '{clean_name}' -Force"
        code, stdout, stderr = self._run_ps_command(ps_cmd, timeout=10)

        if code == 0:
            logger.console(f"Имя компьютера изменено на {clean_name}")
            return {
                "status": "ok",
                "old_name": old_name,
                "new_name": clean_name,
                "message": f"Имя успешно изменено на '{clean_name}'. Требуется перезагрузка Windows.",
            }

        err = stderr or stdout
        return {
            "status": "error",
            "old_name": old_name,
            "new_name": clean_name,
            "message": f"Ошибка Rename-Computer: {err}",
        }

    def change_workgroup(self, new_workgroup: str, force: bool = True) -> Dict[str, Any]:
        """Изменяет рабочую группу компьютера через Add-Computer.

        Args:
            new_workgroup: Имя новой рабочей группы.
            force: Флаг принудительного применения.

        Returns:
            Dict[str, Any]: Результат с полями status, old_workgroup, new_workgroup, message.
        """
        old_wg = self.get_workgroup()
        clean_wg = new_workgroup.strip().upper()

        if not re.match(r"^[a-zA-Z0-9_\-]{1,15}$", clean_wg):
            return {
                "status": "error",
                "old_workgroup": old_wg,
                "new_workgroup": clean_wg,
                "message": "Имя рабочей группы должно содержать от 1 до 15 символов (A-Z, 0-9, -, _).",
            }

        if clean_wg.lower() == old_wg.lower():
            return {
                "status": "ok",
                "old_workgroup": old_wg,
                "new_workgroup": clean_wg,
                "message": "Имя рабочей группы совпадает с текущим.",
            }

        if not self._is_windows:
            return {
                "status": "ok",
                "old_workgroup": old_wg,
                "new_workgroup": clean_wg,
                "message": f"Эмуляция смены рабочей группы на {clean_wg}",
            }

        ps_cmd = f"Add-Computer -WorkGroupName '{clean_wg}' -Force"
        code, stdout, stderr = self._run_ps_command(ps_cmd, timeout=12)

        if code == 0:
            logger.console(f"Рабочая группа изменена на {clean_wg}")
            return {
                "status": "ok",
                "old_workgroup": old_wg,
                "new_workgroup": clean_wg,
                "message": f"Рабочая группа успешно изменена на '{clean_wg}'. Требуется перезагрузка.",
            }

        err = stderr or stdout
        return {
            "status": "error",
            "old_workgroup": old_wg,
            "new_workgroup": clean_wg,
            "message": f"Ошибка Add-Computer: {err}",
        }

