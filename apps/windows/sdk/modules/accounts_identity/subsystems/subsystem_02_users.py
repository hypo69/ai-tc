# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows - Subsystem 02 Users
# =============================================================================
# Description:
#   Подсистема 02: Управление локальными и доменными пользователями
#   Windows SAM (CRUD, включение/отключение, атрибуты, парольные флаги).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.accounts_identity.subsystems.subsystem_02_users import UsersSubsystem
#
#     subsys = UsersSubsystem()
#     users = subsys.list_users()
#
# File: subsystem_02_users.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.accounts_identity.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 15:25:00
# =============================================================================

"""Подсистема управления учетными записями пользователей Windows SAM."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.modules.accounts_identity.models import (
    AccountDetails,
    UserUacConfig,
    UserUacUpdateRequest,
)
from apps.windows.sdk.modules.accounts_identity.win32_bridge import Win32IdentityBridge


class UsersSubsystem:
    """Подсистема операций над учетными записями пользователей."""

    def __init__(self, bridge: Optional[Win32IdentityBridge] = None) -> None:
        """
        Инициализация подсистемы пользователей.

        Args:
            bridge: Мост вызовов Windows API.
        """
        self.bridge = bridge or Win32IdentityBridge()

    def list_users(self) -> List[AccountDetails]:
        """13. Возвращает список всех локальных пользователей."""
        ps_cmd = (
            "Get-LocalUser | Select-Object Name, SID, FullName, Description, Enabled, "
            "AccountExpires, PasswordRequired, PasswordLastSet, PasswordExpires, "
            "UserMayChangePassword, PasswordNeverExpires, LastLogon"
        )
        raw_users = self.bridge.run_powershell_json(ps_cmd)
        results: List[AccountDetails] = []
        if raw_users:
            items = [raw_users] if isinstance(raw_users, dict) else raw_users
            for item in items:
                if not isinstance(item, dict):
                    continue
                sid_val = str(item.get("SID", {}).get("Value", item.get("SID", "")))
                name = item.get("Name", "")
                full_name = item.get("FullName") or ""
                description = item.get("Description") or ""
                enabled = bool(item.get("Enabled", True))
                pwd_req = bool(item.get("PasswordRequired", True))
                pwd_never = bool(item.get("PasswordNeverExpires", False))
                user_may_chg = bool(item.get("UserMayChangePassword", True))

                results.append(
                    AccountDetails(
                        name=name,
                        sid=sid_val,
                        full_name=full_name,
                        description=description,
                        enabled=enabled,
                        password_required=pwd_req,
                        password_never_expires=pwd_never,
                        cannot_change_password=not user_may_chg,
                        account_expires=str(item.get("AccountExpires")) if item.get("AccountExpires") else None,
                        password_last_set=str(item.get("PasswordLastSet")) if item.get("PasswordLastSet") else None,
                        password_expires=str(item.get("PasswordExpires")) if item.get("PasswordExpires") else None,
                        last_logon=str(item.get("LastLogon")) if item.get("LastLogon") else None,
                    )
                )

        if not results:
            # Фоллбэк через штатный net user
            _, out, _ = self.bridge.run_command(["net", "user"])
            for line in out.splitlines():
                if "---" in line or "command completed" in line.lower() or "команда выполнена" in line.lower():
                    continue
                for name in line.split():
                    if name.strip():
                        sid_info = self.bridge.lookup_name_to_sid(name)
                        sid_val = sid_info[0] if sid_info else ""
                        results.append(AccountDetails(name=name, sid=sid_val))
        return results

    def get_user_info(self, name_or_sid: str) -> Optional[AccountDetails]:
        """14, 15. Извлекает исчерпывающую информацию о пользователе."""
        users = self.list_users()
        for u in users:
            if u.name.lower() == name_or_sid.lower() or u.sid == name_or_sid:
                return u
        # Попытка поиска по SID через bridge
        sid_info = self.bridge.lookup_sid_to_name(name_or_sid) if name_or_sid.startswith("S-1-") else None
        if sid_info:
            return AccountDetails(name=sid_info[0], sid=name_or_sid)
        return None

    def get_user_sid(self, username: str) -> Optional[str]:
        """16. Возвращает строковый SID по имени пользователя."""
        info = self.bridge.lookup_name_to_sid(username)
        return info[0] if info else None

    def get_name_by_sid(self, sid_str: str) -> Optional[str]:
        """17. Возвращает имя пользователя по SID."""
        info = self.bridge.lookup_sid_to_name(sid_str)
        return info[0] if info else None

    def create_user(self, name: str, password: Optional[str] = None, full_name: str = "", description: str = "") -> bool:
        """18. Создает нового локального пользователя."""
        cmd = f"New-LocalUser -Name '{name}' -FullName '{full_name}' -Description '{description}'"
        if password:
            cmd = f"$pwd = ConvertTo-SecureString '{password}' -AsPlainText -Force; New-LocalUser -Name '{name}' -Password $pwd -FullName '{full_name}' -Description '{description}'"
        else:
            cmd += " -NoPassword"
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", cmd])
        return ret == 0

    def delete_user(self, name: str) -> bool:
        """19. Удаляет локального пользователя."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Remove-LocalUser -Name '{name}'"])
        return ret == 0

    def enable_user(self, name: str) -> bool:
        """22. Включает учетную запись."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Enable-LocalUser -Name '{name}'"])
        return ret == 0

    def disable_user(self, name: str) -> bool:
        """23. Отключает учетную запись."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Disable-LocalUser -Name '{name}'"])
        return ret == 0

    def rename_user(self, old_name: str, new_name: str) -> bool:
        """21. Переименовывает учетную запись пользователя."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Rename-LocalUser -Name '{old_name}' -NewName '{new_name}'"])
        return ret == 0

    def set_full_name(self, name: str, full_name: str) -> bool:
        """24. Устанавливает полное имя пользователя."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-LocalUser -Name '{name}' -FullName '{full_name}'"])
        return ret == 0

    def set_description(self, name: str, description: str) -> bool:
        """25. Устанавливает описание учетной записи."""
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-LocalUser -Name '{name}' -Description '{description}'"])
        return ret == 0

    def set_account_expiration(self, name: str, expires: Optional[str]) -> bool:
        """26. Устанавливает дату истечения учетной записи."""
        if expires:
            cmd = f"Set-LocalUser -Name '{name}' -AccountExpires (Get-Date '{expires}')"
        else:
            cmd = f"Set-LocalUser -Name '{name}' -AccountNeverExpires"
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", cmd])
        return ret == 0

    def set_cannot_change_password(self, name: str, cannot_change: bool) -> bool:
        """28. Запрещает или разрешает пользователю менять пароль."""
        val = "$false" if cannot_change else "$true"
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-LocalUser -Name '{name}' -UserMayChangePassword {val}"])
        return ret == 0

    def set_password_never_expires(self, name: str, never_expires: bool) -> bool:
        """29. Управляет бессрочным действием пароля."""
        val = "$true" if never_expires else "$false"
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-LocalUser -Name '{name}' -PasswordNeverExpires {val}"])
        return ret == 0

    def get_user_uac(self, name_or_sid: str) -> Optional[UserUacConfig]:
        """Возвращает конфигурацию UAC для указанного пользователя."""
        user = self.get_user_info(name_or_sid)
        if not user:
            return None

        username = user.name
        is_builtin_admin = username.lower() == "administrator" or (user.sid and user.sid.endswith("-500"))

        groups: List[str] = []
        try:
            ps_cmd = (
                f"$u = '{username}'; "
                "Get-LocalGroup | Where-Object { "
                "  (Get-LocalGroupMember -Group $_.Name -ErrorAction SilentlyContinue | Where-Object { $_.Name -like \"*\\$u\" -or $_.Name -eq $u }) "
                "} | Select-Object -ExpandProperty Name"
            )
            raw = self.bridge.run_powershell_json(ps_cmd)
            if isinstance(raw, str):
                groups = [raw]
            elif isinstance(raw, list):
                groups = [str(x) for x in raw if x]
        except Exception as e:
            logger.debug(f"Ошибка получения групп для {username}: {e}")

        if not groups:
            _, out, _ = self.bridge.run_command(["net", "user", username])
            for line in out.splitlines():
                if "членства в группах" in line.lower() or "group memberships" in line.lower():
                    g_part = line.split("*", 1)[-1] if "*" in line else ""
                    groups = [g.strip() for g in g_part.replace("*", "").split() if g.strip()]

        is_admin = any("admin" in g.lower() or "администр" in g.lower() for g in groups)
        uac_role = "admin" if is_admin else "standard"

        enable_lua = True
        prompt_on_secure_desktop = True
        consent_prompt_behavior_admin = 5
        consent_prompt_behavior_user = 3
        filter_admin_token = False
        enable_virtualization = True

        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                num_values = winreg.QueryInfoKey(key)[1]
                vals = dict([winreg.EnumValue(key, i)[:2] for i in range(num_values)])
                enable_lua = bool(vals.get("EnableLUA", 1))
                prompt_on_secure_desktop = bool(vals.get("PromptOnSecureDesktop", 1))
                consent_prompt_behavior_admin = int(vals.get("ConsentPromptBehaviorAdmin", 5))
                consent_prompt_behavior_user = int(vals.get("ConsentPromptBehaviorUser", 3))
                filter_admin_token = bool(vals.get("FilterAdministratorToken", 0))
                enable_virtualization = bool(vals.get("EnableVirtualization", 1))
        except Exception as e:
            logger.debug(f"Ошибка чтения параметров UAC из реестра: {e}")

        password_expired = False
        try:
            _, net_out, _ = self.bridge.run_command(["net", "user", username])
            for line in net_out.splitlines():
                l_lower = line.lower()
                if "password expires" in l_lower or "срок действия пароля" in l_lower:
                    if "must be changed" in l_lower or "требуется смена" in l_lower or "не задан" in l_lower:
                        password_expired = True
                        break
        except Exception:
            pass

        return UserUacConfig(
            username=username,
            sid=user.sid,
            is_admin=is_admin,
            uac_role=uac_role,
            is_builtin_admin=is_builtin_admin,
            filter_admin_token=filter_admin_token,
            enable_lua=enable_lua,
            consent_prompt_behavior_admin=consent_prompt_behavior_admin,
            consent_prompt_behavior_user=consent_prompt_behavior_user,
            prompt_on_secure_desktop=prompt_on_secure_desktop,
            enable_virtualization=enable_virtualization,
            enabled=user.enabled,
            password_never_expires=user.password_never_expires,
            cannot_change_password=user.cannot_change_password,
            password_required=user.password_required,
            password_expired=password_expired,
            groups=groups,
        )

    def update_user_uac(self, name_or_sid: str, req: UserUacUpdateRequest) -> UserUacConfig:
        """Обновляет параметры UAC и учетной записи для пользователя."""
        user = self.get_user_info(name_or_sid)
        if not user:
            raise ValueError(f"Пользователь '{name_or_sid}' не найден")
        username = user.name

        # 1. Изменение роли UAC (Admin vs Standard)
        if req.uac_role in ("admin", "standard"):
            target_admin_group = "Administrators"
            try:
                groups_raw = self.bridge.run_powershell_json("(Get-LocalGroup | Where-Object { $_.SID -like '*-544' }).Name")
                if groups_raw and isinstance(groups_raw, str):
                    target_admin_group = groups_raw.strip()
            except Exception:
                pass

            if req.uac_role == "admin":
                self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Add-LocalGroupMember -Group '{target_admin_group}' -Member '{username}' -ErrorAction SilentlyContinue"])
            elif req.uac_role == "standard":
                self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Remove-LocalGroupMember -Group '{target_admin_group}' -Member '{username}' -ErrorAction SilentlyContinue"])
                self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Add-LocalGroupMember -Group 'Users' -Member '{username}' -ErrorAction SilentlyContinue"])

        # 2. Обновление флагов учетной записи SAM
        if req.enabled is not None:
            if req.enabled:
                self.enable_user(username)
            else:
                self.disable_user(username)

        if req.password_never_expires is not None:
            self.set_password_never_expires(username, req.password_never_expires)

        if req.cannot_change_password is not None:
            self.set_cannot_change_password(username, req.cannot_change_password)

        if req.password_required is not None:
            val = "$true" if req.password_required else "$false"
            self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-LocalUser -Name '{username}' -PasswordRequired {val} -ErrorAction SilentlyContinue"])

        if req.password_expired is not None:
            val = "yes" if req.password_expired else "no"
            self.bridge.run_command(["net", "user", username, f"/logonpasswordchg:{val}"])

        # 3. Обновление параметров реестра UAC
        def _set_reg_val(val_name: str, val_int: int) -> None:
            import winreg
            try:
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, val_name, 0, winreg.REG_DWORD, val_int)
            except Exception as e:
                logger.debug(f"winreg не удалось записать {val_name}: {e}, попытка через PowerShell")
                self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", f"Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -Name '{val_name}' -Value {val_int} -Type DWord -Force -ErrorAction SilentlyContinue"])

        if req.filter_admin_token is not None:
            _set_reg_val("FilterAdministratorToken", 1 if req.filter_admin_token else 0)

        if req.consent_prompt_behavior_admin is not None:
            _set_reg_val("ConsentPromptBehaviorAdmin", int(req.consent_prompt_behavior_admin))

        if req.consent_prompt_behavior_user is not None:
            _set_reg_val("ConsentPromptBehaviorUser", int(req.consent_prompt_behavior_user))

        if req.prompt_on_secure_desktop is not None:
            _set_reg_val("PromptOnSecureDesktop", 1 if req.prompt_on_secure_desktop else 0)

        if req.enable_virtualization is not None:
            _set_reg_val("EnableVirtualization", 1 if req.enable_virtualization else 0)

        updated_config = self.get_user_uac(username)
        if not updated_config:
            raise ValueError(f"Не удалось получить обновленные параметры для '{username}'")
        return updated_config


