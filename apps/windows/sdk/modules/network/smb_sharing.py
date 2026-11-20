# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Network - SMB & File Sharing Manager
# =============================================================================
# Description:
#   Модуль диагностики и управления общим доступом к файлам и принтерам Windows
#   (File and Printer Sharing / SMB): конфигурация SMB1/SMB2/3
#   (Get-SmbServerConfiguration), службы LanmanServer и LanmanWorkstation,
#   языконезависимая группа правил брандмауэра (@FirewallAPI.dll,-28502),
#   инвентаризация общих папок (Get-SmbShare), прав доступа (Get-SmbShareAccess)
#   и активных входящих SMB-сессий (Get-SmbSession).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.smb_sharing import WindowsSmbSharingManager
#
#     mgr = WindowsSmbSharingManager()
#     status = mgr.get_status()
#     sessions = mgr.get_sessions()
#
# File: smb_sharing.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:52:00
# =============================================================================

from __future__ import annotations
"""Диагностика и управление общим доступом к файлам и принтерам Windows (SMB)."""

import ctypes
import json
import re
import subprocess
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from apps.common.telemetry_logger import AppTelemetryLogger
from logger import logger


PsRunnerFn = Callable[[str], Tuple[int, str, str]]
IsAdminFn = Callable[[], bool]

_SAFE_SHARE_NAME_RE = re.compile(r'^[A-Za-zА-Яа-яЁё0-9 _.-]{1,80}$')
_SAFE_ACCOUNT_RE = re.compile(r'^[A-Za-zА-Яа-яЁё0-9 _.\\@-]{1,120}$')
_PROTECTED_SHARES = frozenset({'ADMIN$', 'IPC$', 'PRINT$'})


def _ps_quote(value: str) -> str:
    """Экранирует строку для безопасной подстановки в одинарные кавычки PowerShell."""
    return "'" + value.replace("'", "''") + "'"


def _default_is_admin() -> bool:
    """Проверяет, запущен ли текущий процесс с правами администратора Windows."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _default_ps_runner(script: str, timeout: float = 20.0) -> Tuple[int, str, str]:
    """Безопасно запускает PowerShell-скрипт в неинтерактивном режиме."""
    try:
        res = subprocess.run(
            [
                'powershell.exe',
                '-NoProfile',
                '-NonInteractive',
                '-ExecutionPolicy',
                'Bypass',
                '-Command',
                f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {script}',
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return res.returncode, (res.stdout or '').strip(), (res.stderr or '').strip()
    except subprocess.TimeoutExpired:
        return -1, '', f'Таймаут выполнения PowerShell ({timeout} с)'
    except OSError as exc:
        return -1, '', str(exc)


class SmbServerConfig(BaseModel):
    """Конфигурация протокола SMB на сервере Windows (Get-SmbServerConfiguration)."""

    available: bool = Field(default=False, description='Удалось ли прочитать конфигурацию SMB')
    smb1_enabled: Optional[bool] = Field(default=None, description='Включён ли устаревший протокол SMB 1.0')
    smb2_enabled: Optional[bool] = Field(default=None, description='Включён ли протокол SMB 2/3')
    require_security_signature: Optional[bool] = Field(default=None, description='Требуется ли цифровая подпись SMB')
    encrypt_data: Optional[bool] = Field(default=None, description='Включено ли шифрование трафика SMB')


class SmbServiceState(BaseModel):
    """Состояние системной службы SMB (LanmanServer / LanmanWorkstation)."""

    name: str = Field(description='Системное имя службы')
    display_name: str = Field(default='', description='Отображаемое имя службы')
    status: str = Field(default='Unknown', description='Текущее состояние службы')
    start_type: str = Field(default='Unknown', description='Тип запуска службы')
    running: bool = Field(default=False, description='Запущена ли служба')


class SmbFirewallSummary(BaseModel):
    """Состояние правил брандмауэра группы File and Printer Sharing (@FirewallAPI.dll,-28502)."""

    group_identifier: str = Field(default='@FirewallAPI.dll,-28502', description='Языконезависимый ID группы правил')
    total_rules: int = Field(default=0, description='Общее количество правил в группе')
    enabled_rules: int = Field(default=0, description='Количество включённых правил')
    inbound_enabled: int = Field(default=0, description='Количество включённых входящих правил')
    profiles_enabled: List[str] = Field(default_factory=list, description='Профили, для которых разрешены правила')
    is_enabled: bool = Field(default=False, description='Включён ли общий доступ в брандмауэре')


class SmbShareInfo(BaseModel):
    """Информация об опубликованной общей папке Windows (Get-SmbShare)."""

    name: str = Field(description='Сетевое имя общего ресурса')
    path: str = Field(default='', description='Локальный путь на диске')
    description: str = Field(default='', description='Описание общего ресурса')
    scope_name: str = Field(default='*', description='Область действия ресурса')
    is_special: bool = Field(default=False, description='Является ли ресурс системным (C$, ADMIN$, IPC$)')


class SmbShareAccessEntry(BaseModel):
    """Запись прав доступа к общей папке (Get-SmbShareAccess)."""

    account_name: str = Field(description='Учётная запись или группа Windows')
    access_control_type: str = Field(default='Allow', description='Тип правила (Allow / Deny)')
    access_right: str = Field(default='Read', description='Уровень доступа (Read / Change / Full)')


class SmbSessionInfo(BaseModel):
    """Активная входящая SMB-сессия клиента (Get-SmbSession)."""

    session_id: str = Field(default='', description='Идентификатор SMB-сессии')
    client_computer_name: str = Field(default='', description='IP-адрес или имя клиента')
    client_user_name: str = Field(default='', description='Имя пользователя клиента')
    num_opens: int = Field(default=0, description='Количество открытых файлов')
    dialect: str = Field(default='', description='Версия протокола SMB (например, 3.1.1)')


class SmbSharingStatus(BaseModel):
    """Сводное состояние общего доступа к файлам и принтерам (SMB)."""

    is_admin: bool = Field(default=False, description='Запущен ли процесс от имени администратора')
    server_config: SmbServerConfig = Field(default_factory=SmbServerConfig, description='Параметры SMB1/SMB2/3')
    lanman_server: SmbServiceState = Field(
        default_factory=lambda: SmbServiceState(name='LanmanServer'),
        description='Служба публикации ресурсов SMB (Server)',
    )
    lanman_workstation: SmbServiceState = Field(
        default_factory=lambda: SmbServiceState(name='LanmanWorkstation'),
        description='Служба подключения к ресурсам SMB (Workstation)',
    )
    firewall: SmbFirewallSummary = Field(default_factory=SmbFirewallSummary, description='Правила брандмауэра SMB')
    shares: List[SmbShareInfo] = Field(default_factory=list, description='Опубликованные сетевые ресурсы')
    user_shares_count: int = Field(default=0, description='Количество пользовательских (не системных) шар')
    smb1_warning: bool = Field(default=False, description='Предупреждение: включён небезопасный протокол SMB 1.0')
    ready_for_file_sharing: bool = Field(default=False, description='Готов ли ПК к общему доступу к файлам')


class SmbToggleRequest(BaseModel):
    """Запрос на включение или отключение File and Printer Sharing."""

    enable: bool = Field(description='True — включить общий доступ, False — отключить')
    profiles: List[Literal['Private', 'Domain']] = Field(
        default_factory=lambda: ['Private', 'Domain'],
        description='Доверенные профили брандмауэра (Public запрещён по умолчанию)',
    )
    start_server_service: bool = Field(default=True, description='Управлять ли службой LanmanServer при включении')


class SmbCreateShareRequest(BaseModel):
    """Запрос на публикацию новой общей папки Windows."""

    name: str = Field(description='Имя общего сетевого ресурса')
    path: str = Field(description='Локальный путь к существующей папке')
    description: str = Field(default='', description='Описание ресурса')
    read_access: List[str] = Field(default_factory=list, description='Учётные записи с правом чтения')
    full_access: List[str] = Field(default_factory=list, description='Учётные записи с полным доступом')


class SmbActionResult(BaseModel):
    """Результат операции управления общим доступом SMB."""

    success: bool = Field(description='Успешность операции')
    action: str = Field(description='Выполненное действие')
    message: str = Field(description='Пояснение результата')
    requires_admin: bool = Field(default=False, description='Требуются ли права администратора')
    snapshot_id: Optional[str] = Field(default=None, description='Идентификатор снимка для отката')
    status: Optional[SmbSharingStatus] = Field(default=None, description='Обновлённое состояние SMB')


class WindowsSmbSharingManager:
    """Менеджер диагностики и управления общим доступом к файлам и принтерам Windows."""

    FIREWALL_GROUP_INVARIANT: str = '@FirewallAPI.dll,-28502'
    SERVICE_SERVER: str = 'LanmanServer'
    SERVICE_WORKSTATION: str = 'LanmanWorkstation'

    def __init__(
        self,
        ps_runner: Optional[PsRunnerFn] = None,
        is_admin_fn: Optional[IsAdminFn] = None,
    ) -> None:
        """Инициализирует менеджер общего доступа SMB.

        Args:
            ps_runner: Функция запуска PowerShell (для DI и тестов).
            is_admin_fn: Функция проверки прав администратора (для DI и тестов).
        """
        self._ps_runner: PsRunnerFn = ps_runner or _default_ps_runner
        self._is_admin_fn: IsAdminFn = is_admin_fn or _default_is_admin
        self._telemetry_logger = AppTelemetryLogger('network_smb_sharing')

    @staticmethod
    def _parse_json_list(raw: str) -> List[Dict[str, Any]]:
        """Безопасно парсит JSON от PowerShell в список словарей."""
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        return []

    @staticmethod
    def _is_special_share(name: str, share_type: Any = None) -> bool:
        """Определяет, является ли общая папка системной/административной."""
        upper = name.strip().upper()
        if upper in _PROTECTED_SHARES or upper.endswith('$'):
            return True
        if isinstance(share_type, (int, float)) and int(share_type) >= 2147483648:
            return True
        return False

    def get_status(self) -> SmbSharingStatus:
        """Собирает полную диагностику SMB1/2/3, служб, правил брандмауэра и общих папок.

        Returns:
            SmbSharingStatus: Сводное состояние File & Printer Sharing.
        """
        ps_script = r"""
$smbCfg = $null
try {
    $c = Get-SmbServerConfiguration -ErrorAction Stop
    $smbCfg = @{
        available = $true
        smb1_enabled = [bool]$c.EnableSMB1Protocol
        smb2_enabled = [bool]$c.EnableSMB2Protocol
        require_security_signature = [bool]$c.RequireSecuritySignature
        encrypt_data = [bool]$c.EncryptData
    }
} catch {
    $smbCfg = @{ available = $false }
}

function Get-Svc($svcName) {
    $s = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if ($null -eq $s) {
        return @{ name = $svcName; display_name = ''; status = 'NotFound'; start_type = 'Unknown'; running = $false }
    }
    return @{
        name = $svcName
        display_name = [string]$s.DisplayName
        status = [string]$s.Status
        start_type = [string]$s.StartType
        running = ($s.Status -eq 'Running')
    }
}

$fwRules = @()
try {
    $rawFw = Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue | Where-Object {
        $_.Group -eq '@FirewallAPI.dll,-28502' -or
        $_.DisplayGroup -like '*File and Printer Sharing*' -or
        $_.DisplayGroup -like '*Общий доступ к файлам и принтерам*'
    }
    foreach ($r in $rawFw) {
        $fwRules += @{
            enabled = ($r.Enabled -eq 'True' -or $r.Enabled -eq 1)
            direction = [string]$r.Direction
            profile = [string]$r.Profile
        }
    }
} catch {}

$shares = @()
try {
    $rawShares = Get-SmbShare -ErrorAction SilentlyContinue
    foreach ($sh in $rawShares) {
        $shares += @{
            name = [string]$sh.Name
            path = [string]$sh.Path
            description = [string]$sh.Description
            scope_name = [string]$sh.ScopeName
            special = [bool]$sh.Special
        }
    }
} catch {}

@{
    server_config = $smbCfg
    lanman_server = (Get-Svc 'LanmanServer')
    lanman_workstation = (Get-Svc 'LanmanWorkstation')
    firewall_rules = $fwRules
    shares = $shares
} | ConvertTo-Json -Depth 5 -Compress
"""
        code, stdout, stderr = self._ps_runner(ps_script)
        data: Dict[str, Any] = {}
        if code == 0 and stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError as exc:
                logger.warning(f'[SmbSharing] Невалидный JSON от PowerShell: {exc}')
        elif stderr:
            logger.warning(f'[SmbSharing] Ошибка опроса состояния SMB: {stderr}')

        cfg_raw = data.get('server_config') or {}
        server_config = SmbServerConfig(**cfg_raw) if isinstance(cfg_raw, dict) else SmbServerConfig()

        srv_raw = data.get('lanman_server') or {'name': self.SERVICE_SERVER}
        wks_raw = data.get('lanman_workstation') or {'name': self.SERVICE_WORKSTATION}
        lanman_server = SmbServiceState(**srv_raw)
        lanman_workstation = SmbServiceState(**wks_raw)

        raw_fw = data.get('firewall_rules') or []
        if isinstance(raw_fw, dict):
            raw_fw = [raw_fw]
        total_rules = len(raw_fw)
        enabled_rules = 0
        inbound_enabled = 0
        profiles_set: set[str] = set()
        for rule in raw_fw:
            if not isinstance(rule, dict):
                continue
            if rule.get('enabled') in (True, 1, 'True', '1'):
                enabled_rules += 1
                if str(rule.get('direction', '')).lower() == 'inbound':
                    inbound_enabled += 1
                for prof in str(rule.get('profile', '')).split(','):
                    clean = prof.strip()
                    if clean and clean != 'Any':
                        profiles_set.add(clean)
                    elif clean == 'Any':
                        profiles_set.update({'Domain', 'Private', 'Public'})

        firewall = SmbFirewallSummary(
            group_identifier=self.FIREWALL_GROUP_INVARIANT,
            total_rules=total_rules,
            enabled_rules=enabled_rules,
            inbound_enabled=inbound_enabled,
            profiles_enabled=sorted(profiles_set),
            is_enabled=inbound_enabled > 0,
        )

        raw_shares = data.get('shares') or []
        if isinstance(raw_shares, dict):
            raw_shares = [raw_shares]
        shares: List[SmbShareInfo] = []
        for sh in raw_shares:
            if not isinstance(sh, dict) or not sh.get('name'):
                continue
            name = str(sh['name'])
            is_special = bool(sh.get('special')) or self._is_special_share(name)
            shares.append(
                SmbShareInfo(
                    name=name,
                    path=str(sh.get('path') or ''),
                    description=str(sh.get('description') or ''),
                    scope_name=str(sh.get('scope_name') or '*'),
                    is_special=is_special,
                )
            )

        user_shares_count = sum(1 for s in shares if not s.is_special)
        smb1_warning = bool(server_config.smb1_enabled is True)
        smb2_ok = server_config.smb2_enabled is not False
        ready = bool(lanman_server.running and firewall.is_enabled and smb2_ok)

        return SmbSharingStatus(
            is_admin=self._is_admin_fn(),
            server_config=server_config,
            lanman_server=lanman_server,
            lanman_workstation=lanman_workstation,
            firewall=firewall,
            shares=shares,
            user_shares_count=user_shares_count,
            smb1_warning=smb1_warning,
            ready_for_file_sharing=ready,
        )

    def get_sessions(self) -> List[SmbSessionInfo]:
        """Возвращает список активных входящих SMB-сессий (Get-SmbSession).

        Returns:
            List[SmbSessionInfo]: Активные подключения клиентов к SMB-серверу.
        """
        ps_script = (
            "Get-SmbSession -ErrorAction SilentlyContinue | ForEach-Object { "
            "[PSCustomObject]@{ "
            "session_id=[string]$_.SessionId; "
            "client_computer_name=[string]$_.ClientComputerName; "
            "client_user_name=[string]$_.ClientUserName; "
            "num_opens=[int]$_.NumOpens; "
            "dialect=[string]$_.Dialect "
            "} } | ConvertTo-Json -Compress"
        )
        code, stdout, _ = self._ps_runner(ps_script)
        if code != 0 or not stdout:
            return []
        return [SmbSessionInfo(**item) for item in self._parse_json_list(stdout)]

    def get_share_access(self, share_name: str) -> List[SmbShareAccessEntry]:
        """Возвращает таблицу прав доступа для указанной общей папки (Get-SmbShareAccess).

        Args:
            share_name: Имя общей папки.

        Returns:
            List[SmbShareAccessEntry]: Список прав пользователей/групп.
        """
        clean_name = share_name.strip()
        if not clean_name or not _SAFE_SHARE_NAME_RE.match(clean_name.rstrip('$')):
            raise ValueError(f'Недопустимое имя общего ресурса: {share_name}')

        ps_script = (
            f"Get-SmbShareAccess -Name {_ps_quote(clean_name)} -ErrorAction SilentlyContinue | ForEach-Object {{ "
            "[PSCustomObject]@{ "
            "account_name=[string]$_.AccountName; "
            "access_control_type=[string]$_.AccessControlType; "
            "access_right=[string]$_.AccessRight "
            "} } | ConvertTo-Json -Compress"
        )
        code, stdout, _ = self._ps_runner(ps_script)
        if code != 0 or not stdout:
            return []
        return [SmbShareAccessEntry(**item) for item in self._parse_json_list(stdout)]

    def toggle_file_sharing(
        self,
        enable: bool,
        profiles: Optional[List[str]] = None,
        start_server_service: bool = True,
        snapshot_id: Optional[str] = None,
    ) -> SmbActionResult:
        """Включает или отключает File and Printer Sharing через @FirewallAPI.dll,-28502.

        Публичный профиль (Public) исключается для защиты от несанкционированного доступа.

        Args:
            enable: True для включения, False для отключения.
            profiles: Целевые доверенные профили ('Private', 'Domain').
            start_server_service: Запускать ли службу LanmanServer при включении.
            snapshot_id: Необязательный ID снимка для записи в аудит.

        Returns:
            SmbActionResult: Результат операции и обновлённое состояние.
        """
        action_name = 'enable_file_sharing' if enable else 'disable_file_sharing'
        if not self._is_admin_fn():
            return SmbActionResult(
                success=False,
                action=action_name,
                message='Для управления правилами File and Printer Sharing требуются права администратора.',
                requires_admin=True,
                snapshot_id=snapshot_id,
                status=self.get_status(),
            )

        safe_profiles = [p for p in (profiles or ['Private', 'Domain']) if p in ('Private', 'Domain')]
        if not safe_profiles:
            safe_profiles = ['Private', 'Domain']
        profiles_expr = ','.join(safe_profiles)

        if enable:
            svc_part = (
                "Set-Service -Name LanmanServer -StartupType Automatic -ErrorAction Stop; "
                "Start-Service -Name LanmanServer -ErrorAction Stop; "
                if start_server_service
                else ''
            )
            ps_script = (
                f"{svc_part}"
                "$rules = Get-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -ErrorAction SilentlyContinue; "
                f"if ($rules) {{ $rules | Where-Object {{ $_.Profile -match '{'|'.join(safe_profiles)}' }} | "
                "Enable-NetFirewallRule -ErrorAction Stop } "
                f"else {{ Enable-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -ErrorAction Stop }}; "
                "Write-Output 'OK'"
            )
            ok_msg = f'Общий доступ к файлам и принтерам включён для профилей: {profiles_expr}'
        else:
            ps_script = (
                "Disable-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -ErrorAction SilentlyContinue; "
                "Write-Output 'OK'"
            )
            ok_msg = 'Правила брандмауэра File and Printer Sharing отключены'

        code, _, stderr = self._ps_runner(ps_script)
        success = code == 0
        message = ok_msg if success else (stderr or 'Не удалось изменить параметры File and Printer Sharing')

        self._telemetry_logger.log_event(
            event_type=action_name,
            status='SUCCESS' if success else 'FAILED',
            details={'profiles': safe_profiles, 'snapshot_id': snapshot_id, 'message': message},
        )
        if success:
            logger.console(f'[SmbSharing] {message}')

        return SmbActionResult(
            success=success,
            action=action_name,
            message=message,
            requires_admin=False,
            snapshot_id=snapshot_id,
            status=self.get_status(),
        )

    def create_share(self, req: SmbCreateShareRequest) -> SmbActionResult:
        """Создаёт новую общую папку Windows (New-SmbShare) с валидацией параметров.

        Args:
            req: Параметры создаваемой общей папки.

        Returns:
            SmbActionResult: Результат создания общего ресурса.
        """
        if not self._is_admin_fn():
            return SmbActionResult(
                success=False,
                action='create_share',
                message='Для публикации общей папки требуются права администратора Windows.',
                requires_admin=True,
                status=self.get_status(),
            )

        name = req.name.strip()
        path = req.path.strip()
        if not _SAFE_SHARE_NAME_RE.match(name) or self._is_special_share(name):
            return SmbActionResult(
                success=False,
                action='create_share',
                message=f'Недопустимое имя общей папки: {name}',
                status=self.get_status(),
            )
        if not path or any(ch in path for ch in ('\n', '\r', ';', '|', '`', '$')):
            return SmbActionResult(
                success=False,
                action='create_share',
                message='Недопустимый локальный путь к папке.',
                status=self.get_status(),
            )

        args = [f'-Name {_ps_quote(name)}', f'-Path {_ps_quote(path)}']
        if req.description.strip():
            args.append(f'-Description {_ps_quote(req.description.strip())}')

        read_list = [acc.strip() for acc in req.read_access if _SAFE_ACCOUNT_RE.match(acc.strip())]
        full_list = [acc.strip() for acc in req.full_access if _SAFE_ACCOUNT_RE.match(acc.strip())]
        if read_list:
            args.append('-ReadAccess ' + ','.join(_ps_quote(a) for a in read_list))
        if full_list:
            args.append('-FullAccess ' + ','.join(_ps_quote(a) for a in full_list))
        if not read_list and not full_list:
            args.append("-ReadAccess 'Authenticated Users'")

        ps_script = f"New-SmbShare {' '.join(args)} -ErrorAction Stop | Out-Null; Write-Output 'OK'"
        code, _, stderr = self._ps_runner(ps_script)
        success = code == 0
        message = f"Общая папка '{name}' опубликована ({path})" if success else (stderr or 'Ошибка создания общей папки')

        self._telemetry_logger.log_event(
            event_type='smb_create_share',
            status='SUCCESS' if success else 'FAILED',
            details={'name': name, 'path': path, 'message': message},
        )
        return SmbActionResult(
            success=success,
            action='create_share',
            message=message,
            requires_admin=False,
            status=self.get_status(),
        )

    def remove_share(self, share_name: str) -> SmbActionResult:
        """Удаляет пользовательскую общую папку (Remove-SmbShare), защищая системные ресурсы.

        Args:
            share_name: Имя удаляемой общей папки.

        Returns:
            SmbActionResult: Результат удаления.
        """
        if not self._is_admin_fn():
            return SmbActionResult(
                success=False,
                action='remove_share',
                message='Для удаления общей папки требуются права администратора Windows.',
                requires_admin=True,
                status=self.get_status(),
            )

        name = share_name.strip()
        if not name or self._is_special_share(name) or not _SAFE_SHARE_NAME_RE.match(name):
            return SmbActionResult(
                success=False,
                action='remove_share',
                message=f"Удаление системного или некорректного ресурса '{name}' запрещено.",
                status=self.get_status(),
            )

        ps_script = f"Remove-SmbShare -Name {_ps_quote(name)} -Force -ErrorAction Stop; Write-Output 'OK'"
        code, _, stderr = self._ps_runner(ps_script)
        success = code == 0
        message = f"Общая папка '{name}' удалена" if success else (stderr or 'Ошибка удаления общей папки')

        self._telemetry_logger.log_event(
            event_type='smb_remove_share',
            status='SUCCESS' if success else 'FAILED',
            details={'name': name, 'message': message},
        )
        return SmbActionResult(
            success=success,
            action='remove_share',
            message=message,
            requires_admin=False,
            status=self.get_status(),
        )


__all__ = [
    'SmbActionResult',
    'SmbCreateShareRequest',
    'SmbFirewallSummary',
    'SmbServerConfig',
    'SmbServiceState',
    'SmbSessionInfo',
    'SmbShareAccessEntry',
    'SmbShareInfo',
    'SmbSharingStatus',
    'SmbToggleRequest',
    'WindowsSmbSharingManager',
]
