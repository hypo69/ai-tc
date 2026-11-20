# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows - Subsystem 05 Authentication & Policy
# =============================================================================
# Description:
#   Подсистема 05: Политики безопасности паролей, блокировки аккаунтов,
#   параметры системного доступа SAM ([System Access]), ограничения часов входа
#   и рабочих станций (Logon Restrictions).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.accounts_identity.subsystems.subsystem_05_auth import AuthPolicySubsystem
#
#     subsys = AuthPolicySubsystem()
#     policy = subsys.get_password_policy()
#
# File: subsystem_05_auth.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.accounts_identity.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 15:29:00
# =============================================================================

"""Подсистема политик аутентификации, паролей SAM и ограничений входа."""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from typing import Dict, Optional, Tuple

from logger import logger
from apps.windows.sdk.modules.accounts_identity.models import (
    PasswordPolicy,
    PasswordPolicyUpdateRequest,
)
from apps.windows.sdk.modules.accounts_identity.win32_bridge import Win32IdentityBridge

# Запрещенные символы в именах учетных записей Windows SAM
_INVALID_SAM_NAME_RE = re.compile(r'["/\\\[\]:;|=,+*?<>@\r\n]')


class AuthPolicySubsystem:
    """Подсистема управления политиками паролей, блокировки и системного доступа SAM."""

    def __init__(self, bridge: Optional[Win32IdentityBridge] = None) -> None:
        """
        Инициализация подсистемы аутентификации.

        Args:
            bridge: Мост вызовов Windows API.
        """
        self.bridge = bridge or Win32IdentityBridge()

    def _export_secedit_system_access(self) -> Dict[str, str]:
        """
        Экспортирует секцию [System Access] локальной политики безопасности через secedit.

        Returns:
            Словарь вида {Key: RawValue} или пустой словарь при недоступности secedit.
        """
        result: Dict[str, str] = {}
        token = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        tmp_cfg = os.path.join(tempfile.gettempdir(), f"sec_sam_{token}.inf")
        try:
            ret, _, err = self.bridge.run_command(
                ["secedit", "/export", "/cfg", tmp_cfg, "/areas", "SECURITYPOLICY", "/quiet"]
            )
            if ret != 0 or not os.path.exists(tmp_cfg):
                logger.debug(f"[AuthPolicySubsystem] secedit /export вернул код {ret}: {err}")
                return result

            raw_bytes = b""
            with open(tmp_cfg, "rb") as fb:
                raw_bytes = fb.read()

            if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = raw_bytes.decode("utf-16", errors="replace")
            else:
                text = raw_bytes.decode("utf-8-sig", errors="replace")

            in_section = False
            for line in text.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith(";"):
                    continue
                if line_str.lower() == "[system access]":
                    in_section = True
                    continue
                if line_str.startswith("[") and in_section:
                    break
                if in_section and "=" in line_str:
                    k, v = line_str.split("=", 1)
                    result[k.strip()] = v.strip()
        except Exception as exc:
            logger.debug(f"[AuthPolicySubsystem] Ошибка экспорта secedit SECURITYPOLICY: {exc}")
        finally:
            if os.path.exists(tmp_cfg):
                try:
                    os.remove(tmp_cfg)
                except OSError:
                    pass
        return result

    @staticmethod
    def _parse_int(value: Optional[str], default: int) -> int:
        """Безопасно преобразует строковое значение в целое число."""
        if value is None:
            return default
        try:
            return int(value.strip())
        except ValueError:
            return default

    @staticmethod
    def _parse_bool(value: Optional[str], default: bool = False) -> bool:
        """Преобразует флаг secedit ('0'/'1') в булево значение."""
        if value is None:
            return default
        return value.strip() == "1"

    def _parse_net_accounts(self, out: str, policy: PasswordPolicy, fill_missing_only: bool) -> None:
        """
        Парсит вывод команды `net accounts` для заполнения роли компьютера и fallback-полей.

        Args:
            out: Стандартный вывод команды `net accounts`.
            policy: Заполняемая модель политики.
            fill_missing_only: Если True, обновляет только computer_role.
        """
        for line in out.splitlines():
            line_str = line.strip()
            low = line_str.lower()
            if "computer role" in low or "роль компьютера" in low:
                parts = line_str.split(":", 1)
                if len(parts) > 1:
                    policy.computer_role = parts[1].strip()
                continue

            if fill_missing_only:
                continue

            if "minimum password length" in low or "минимальная длина пароля" in low:
                m = re.search(r"\d+", line_str)
                if m:
                    policy.min_password_length = int(m.group())
            elif "maximum password age" in low or "максимальный срок действия пароля" in low:
                if "unlimited" in low or "неогранич" in low or "бессроч" in low:
                    policy.max_password_age_days = 0
                else:
                    m = re.search(r"\d+", line_str)
                    if m:
                        policy.max_password_age_days = int(m.group())
            elif "minimum password age" in low or "минимальный срок действия пароля" in low:
                m = re.search(r"\d+", line_str)
                if m:
                    policy.min_password_age_days = int(m.group())
            elif "length of password history" in low or "длина истории паролей" in low:
                if "none" in low or "нет" in low:
                    policy.password_history_length = 0
                else:
                    m = re.search(r"\d+", line_str)
                    if m:
                        policy.password_history_length = int(m.group())
            elif "lockout threshold" in low or "порог блокировки" in low:
                if "never" in low or "никогда" in low:
                    policy.lockout_threshold = 0
                else:
                    m = re.search(r"\d+", line_str)
                    if m:
                        policy.lockout_threshold = int(m.group())
            elif "lockout duration" in low or "продолжительность блокировки" in low:
                m = re.search(r"\d+", line_str)
                if m:
                    policy.lockout_duration_minutes = int(m.group())
            elif "lockout observation window" in low or "окно наблюдения" in low:
                m = re.search(r"\d+", line_str)
                if m:
                    policy.lockout_window_minutes = int(m.group())
            elif "force user logoff" in low or "принудительный выход" in low:
                policy.force_logoff_when_hour_expire = not ("never" in low or "никогда" in low)

    def get_password_policy(self) -> PasswordPolicy:
        """
        38-41, 44, 46. Получает полные параметры локальной политики паролей,
        блокировок и системного доступа SAM.

        Returns:
            PasswordPolicy: Актуальная конфигурация политики SAM.
        """
        policy = PasswordPolicy()
        sec_map = self._export_secedit_system_access()

        if sec_map:
            policy.min_password_length = self._parse_int(sec_map.get("MinimumPasswordLength"), 0)
            raw_max_age = self._parse_int(sec_map.get("MaximumPasswordAge"), 42)
            policy.max_password_age_days = 0 if raw_max_age < 0 else raw_max_age
            policy.min_password_age_days = max(0, self._parse_int(sec_map.get("MinimumPasswordAge"), 0))
            policy.password_history_length = max(0, self._parse_int(sec_map.get("PasswordHistorySize"), 0))
            policy.password_complexity = self._parse_bool(sec_map.get("PasswordComplexity"), False)
            policy.reversible_encryption = self._parse_bool(sec_map.get("ClearTextPassword"), False)

            policy.lockout_threshold = max(0, self._parse_int(sec_map.get("LockoutBadCount"), 0))
            raw_lockout_dur = self._parse_int(sec_map.get("LockoutDuration"), 30)
            policy.lockout_duration_minutes = 0 if raw_lockout_dur < 0 else raw_lockout_dur
            policy.lockout_window_minutes = max(0, self._parse_int(sec_map.get("ResetLockoutCount"), 30))
            policy.allow_admin_lockout = self._parse_bool(sec_map.get("AllowAdministratorLockout"), False)

            policy.force_logoff_when_hour_expire = self._parse_bool(sec_map.get("ForceLogoffWhenHourExpire"), False)
            policy.require_logon_to_change_password = self._parse_bool(sec_map.get("RequireLogonToChangePassword"), False)
            policy.lsa_anonymous_name_lookup = self._parse_bool(sec_map.get("LSAAnonymousNameLookup"), False)

            if "EnableAdminAccount" in sec_map:
                policy.enable_admin_account = self._parse_bool(sec_map.get("EnableAdminAccount"))
            if "EnableGuestAccount" in sec_map:
                policy.enable_guest_account = self._parse_bool(sec_map.get("EnableGuestAccount"))
            if "NewAdministratorName" in sec_map:
                policy.new_admin_name = sec_map["NewAdministratorName"].strip().strip('"')
            if "NewGuestName" in sec_map:
                policy.new_guest_name = sec_map["NewGuestName"].strip().strip('"')

        _, out, _ = self.bridge.run_command(["net", "accounts"])
        if out:
            self._parse_net_accounts(out, policy, fill_missing_only=bool(sec_map))

        return policy

    @staticmethod
    def _validate_sam_account_name(name: str, field_label: str) -> str:
        """Проверяет корректность имени встроенной учетной записи SAM."""
        cleaned = name.strip()
        if not cleaned:
            raise ValueError(f"{field_label} не может быть пустым.")
        if len(cleaned) > 20:
            raise ValueError(f"{field_label} не может превышать 20 символов.")
        if _INVALID_SAM_NAME_RE.search(cleaned):
            raise ValueError(f"{field_label} содержит недопустимые символы.")
        return cleaned

    def update_password_policy(
        self,
        req: PasswordPolicyUpdateRequest,
    ) -> Tuple[bool, str, PasswordPolicy]:
        """
        Валидирует и атомарно применяет параметры политики SAM через `secedit /configure`.

        Args:
            req: Запрос с изменяемыми параметрами политики SAM.

        Returns:
            Кортеж (success, message, updated_policy).

        Raises:
            ValueError: При нарушении логических ограничений политики Windows SAM.
        """
        current = self.get_password_policy()

        eff_max_age = req.max_password_age_days if req.max_password_age_days is not None else current.max_password_age_days
        eff_min_age = req.min_password_age_days if req.min_password_age_days is not None else current.min_password_age_days
        if eff_max_age > 0 and eff_min_age >= eff_max_age:
            raise ValueError(
                f"Минимальный срок действия пароля ({eff_min_age} дн.) должен быть строго меньше максимального ({eff_max_age} дн.)."
            )

        eff_threshold = req.lockout_threshold if req.lockout_threshold is not None else current.lockout_threshold
        eff_duration = req.lockout_duration_minutes if req.lockout_duration_minutes is not None else current.lockout_duration_minutes
        eff_window = req.lockout_window_minutes if req.lockout_window_minutes is not None else current.lockout_window_minutes
        if eff_threshold > 0 and eff_duration > 0 and eff_window > eff_duration:
            raise ValueError(
                f"Окно сброса блокировки ({eff_window} мин.) не может превышать длительность блокировки ({eff_duration} мин.)."
            )

        lines: list[str] = []
        if req.min_password_length is not None:
            lines.append(f"MinimumPasswordLength = {req.min_password_length}")
        if req.max_password_age_days is not None:
            secedit_max_age = -1 if req.max_password_age_days == 0 else req.max_password_age_days
            lines.append(f"MaximumPasswordAge = {secedit_max_age}")
        if req.min_password_age_days is not None:
            lines.append(f"MinimumPasswordAge = {req.min_password_age_days}")
        if req.password_history_length is not None:
            lines.append(f"PasswordHistorySize = {req.password_history_length}")
        if req.password_complexity is not None:
            lines.append(f"PasswordComplexity = {1 if req.password_complexity else 0}")
        if req.reversible_encryption is not None:
            lines.append(f"ClearTextPassword = {1 if req.reversible_encryption else 0}")

        if req.lockout_threshold is not None:
            lines.append(f"LockoutBadCount = {req.lockout_threshold}")
        if eff_threshold > 0:
            if req.lockout_duration_minutes is not None:
                secedit_dur = -1 if req.lockout_duration_minutes == 0 else req.lockout_duration_minutes
                lines.append(f"LockoutDuration = {secedit_dur}")
            if req.lockout_window_minutes is not None:
                lines.append(f"ResetLockoutCount = {req.lockout_window_minutes}")
        if req.allow_admin_lockout is not None:
            lines.append(f"AllowAdministratorLockout = {1 if req.allow_admin_lockout else 0}")

        if req.force_logoff_when_hour_expire is not None:
            lines.append(f"ForceLogoffWhenHourExpire = {1 if req.force_logoff_when_hour_expire else 0}")
        if req.require_logon_to_change_password is not None:
            lines.append(f"RequireLogonToChangePassword = {1 if req.require_logon_to_change_password else 0}")
        if req.lsa_anonymous_name_lookup is not None:
            lines.append(f"LSAAnonymousNameLookup = {1 if req.lsa_anonymous_name_lookup else 0}")
        if req.enable_admin_account is not None:
            lines.append(f"EnableAdminAccount = {1 if req.enable_admin_account else 0}")
        if req.enable_guest_account is not None:
            lines.append(f"EnableGuestAccount = {1 if req.enable_guest_account else 0}")
        if req.new_admin_name is not None:
            clean_admin = self._validate_sam_account_name(req.new_admin_name, "Имя встроенного Администратора")
            lines.append(f'NewAdministratorName = "{clean_admin}"')
        if req.new_guest_name is not None:
            clean_guest = self._validate_sam_account_name(req.new_guest_name, "Имя встроенного Гостя")
            lines.append(f'NewGuestName = "{clean_guest}"')

        if not lines:
            return True, "Параметры политики SAM не изменялись.", current

        inf_content = (
            "[Unicode]\r\n"
            "Unicode=yes\r\n"
            "[System Access]\r\n"
            + "\r\n".join(lines)
            + "\r\n[Version]\r\n"
            'signature="$CHICAGO$"\r\n'
            "Revision=1\r\n"
        )

        token = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        tmp_dir = tempfile.gettempdir()
        tmp_cfg = os.path.join(tmp_dir, f"sec_sam_apply_{token}.inf")
        tmp_db = os.path.join(tmp_dir, f"sec_sam_apply_{token}.sdb")
        tmp_jfm = os.path.join(tmp_dir, f"sec_sam_apply_{token}.jfm")
        tmp_log = os.path.join(tmp_dir, f"sec_sam_apply_{token}.log")

        try:
            with open(tmp_cfg, "w", encoding="utf-16") as f:
                f.write(inf_content)

            ret, out, err = self.bridge.run_command(
                [
                    "secedit",
                    "/configure",
                    "/db",
                    tmp_db,
                    "/cfg",
                    tmp_cfg,
                    "/areas",
                    "SECURITYPOLICY",
                    "/log",
                    tmp_log,
                    "/quiet",
                ]
            )
            if ret != 0:
                detail = (err or out or "").strip()
                logger.warning(f"[AuthPolicySubsystem] secedit /configure вернул код {ret}: {detail}")
                return (
                    False,
                    f"Не удалось применить политику SAM (код {ret}). Требуются права администратора.{(' ' + detail) if detail else ''}",
                    current,
                )
            updated = self.get_password_policy()
            return True, "Политика безопасности SAM успешно обновлена.", updated
        except Exception as exc:
            logger.error(f"[AuthPolicySubsystem] Ошибка применения политики SAM: {exc}")
            return False, f"Ошибка применения политики SAM: {exc}", current
        finally:
            for path in (tmp_cfg, tmp_db, tmp_jfm, tmp_log):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def set_password_policy(
        self,
        min_length: Optional[int] = None,
        max_age_days: Optional[int] = None,
        history_length: Optional[int] = None,
        lockout_threshold: Optional[int] = None,
    ) -> bool:
        """45. Обновляет базовые параметры политики паролей (NetUserModalsSet / secedit)."""
        req = PasswordPolicyUpdateRequest(
            min_password_length=min_length,
            max_password_age_days=max_age_days,
            password_history_length=history_length,
            lockout_threshold=lockout_threshold,
        )
        ok, _, _ = self.update_password_policy(req)
        if ok:
            return True

        # Fallback на net accounts
        args = ["net", "accounts"]
        if min_length is not None:
            args.append(f"/minpwlen:{min_length}")
        if max_age_days is not None:
            args.append("/maxpwage:UNLIMITED" if max_age_days == 0 else f"/maxpwage:{max_age_days}")
        if history_length is not None:
            args.append(f"/uniquepw:{history_length}")
        if lockout_threshold is not None:
            args.append(f"/lockoutthreshold:{lockout_threshold}")

        if len(args) == 2:
            return True
        ret, _, _ = self.bridge.run_command(args)
        return ret == 0

    def reset_user_password(self, username: str, new_password: str) -> bool:
        """43. Административный сброс пароля пользователя."""
        cmd = f"$pwd = ConvertTo-SecureString '{new_password}' -AsPlainText -Force; Set-LocalUser -Name '{username}' -Password $pwd"
        ret, _, _ = self.bridge.run_command(["powershell.exe", "-NoProfile", "-Command", cmd])
        return ret == 0

    def get_logon_hours(self, username: str) -> Optional[str]:
        """47. Возвращает разрешенные часы входа."""
        _, out, _ = self.bridge.run_command(["net", "user", username])
        for line in out.splitlines():
            if "logon hours allowed" in line.lower() or "разрешенные часы входа" in line.lower():
                parts = line.split(":", 1)
                return parts[1].strip() if len(parts) > 1 else ""
        return "All"

    def set_logon_hours(self, username: str, times_str: str) -> bool:
        """48. Устанавливает разрешенные часы входа (например: 'M-F,8am-5pm')."""
        ret, _, _ = self.bridge.run_command(["net", "user", username, f"/times:{times_str}"])
        return ret == 0

    def get_logon_workstations(self, username: str) -> Optional[str]:
        """49. Возвращает разрешенные рабочие станции."""
        _, out, _ = self.bridge.run_command(["net", "user", username])
        for line in out.splitlines():
            if "workstations allowed" in line.lower() or "разрешенные рабочие станции" in line.lower():
                parts = line.split(":", 1)
                return parts[1].strip() if len(parts) > 1 else ""
        return "All"

    def set_logon_workstations(self, username: str, workstations_str: str) -> bool:
        """50. Устанавливает список рабочих станций для входа."""
        ret, _, _ = self.bridge.run_command(["net", "user", username, f"/workstations:{workstations_str}"])
        return ret == 0
