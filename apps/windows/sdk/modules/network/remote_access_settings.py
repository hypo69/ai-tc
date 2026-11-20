# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Network - Remote Access Settings
# =============================================================================
# Description:
#   Модуль диагностики и настройки входящего удалённого доступа Windows:
#   сетевой профиль (Private), служба и брандмауэр SMB (TCP 445),
#   служба и брандмауэр WinRM / PowerShell Remoting (TCP 5985),
#   а также политика реестра UAC Remote Restrictions
#   (LocalAccountTokenFilterPolicy).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.remote_access_settings import (
#         WindowsRemoteAccessManager,
#     )
#
#     mgr = WindowsRemoteAccessManager()
#     status = mgr.get_status()
#     result = mgr.apply_action('enable_all')
#
# File: remote_access_settings.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 20:40:00
# =============================================================================

from __future__ import annotations
"""Диагностика и настройка входящего удалённого доступа Windows (SMB 445 / WinRM 5985)."""

import ctypes
import json
import socket
import subprocess
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from logger import logger

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]


RemoteAccessActionType = Literal[
    'enable_all',
    'disable_all',
    'set_private_profile',
    'enable_smb',
    'disable_smb',
    'enable_winrm',
    'disable_winrm',
    'enable_smb_firewall',
    'disable_smb_firewall',
    'enable_winrm_firewall',
    'disable_winrm_firewall',
    'enable_uac_remote',
    'disable_uac_remote',
]

_UAC_REG_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
_UAC_REG_VALUE = 'LocalAccountTokenFilterPolicy'
_CUSTOM_SMB_RULE_NAME = 'AI-TC Inbound SMB (TCP 445)'
_CUSTOM_WINRM_RULE_NAME = 'AI-TC Inbound WinRM (TCP 5985)'


class NetworkProfileInfo(BaseModel):
    """Информация о сетевом профиле активного адаптера Windows."""

    name: str = Field(default='', description='Имя сетевого подключения')
    interface_alias: str = Field(default='', description='Псевдоним сетевого интерфейса')
    interface_index: int = Field(default=0, description='Индекс сетевого интерфейса')
    category: str = Field(default='Unknown', description='Категория сети: Public, Private, DomainAuthenticated')


class ServiceStatusInfo(BaseModel):
    """Состояние системной службы Windows."""

    name: str = Field(description='Системное имя службы')
    status: str = Field(default='Unknown', description='Текущее состояние (Running / Stopped / Unknown)')
    start_type: str = Field(default='Unknown', description='Тип запуска (Automatic / Manual / Disabled)')
    running: bool = Field(default=False, description='Запущена ли служба в данный момент')


class RemoteAccessStatus(BaseModel):
    """Сводное состояние готовности ПК к входящему удалённому входу (SMB 445 / WinRM 5985)."""

    is_admin: bool = Field(default=False, description='Запущен ли процесс с правами администратора')
    hostname: str = Field(default='', description='Сетевое имя текущего компьютера')
    network_profiles: List[NetworkProfileInfo] = Field(default_factory=list, description='Активные сетевые профили')
    has_public_profile: bool = Field(default=False, description='Есть ли активные интерфейсы в профиле Public')
    smb_service: ServiceStatusInfo = Field(
        default_factory=lambda: ServiceStatusInfo(name='LanmanServer'),
        description='Состояние службы Сервер (LanmanServer)',
    )
    winrm_service: ServiceStatusInfo = Field(
        default_factory=lambda: ServiceStatusInfo(name='WinRM'),
        description='Состояние службы WinRM',
    )
    port_445_listening: bool = Field(default=False, description='Прослушивается ли локально порт TCP 445 (SMB)')
    port_5985_listening: bool = Field(default=False, description='Прослушивается ли локально порт TCP 5985 (WinRM)')
    smb_firewall_enabled: bool = Field(default=False, description='Разрешён ли входящий SMB (TCP 445) в брандмауэре')
    winrm_firewall_enabled: bool = Field(default=False, description='Разрешён ли входящий WinRM (TCP 5985) в брандмауэре')
    uac_remote_allowed: bool = Field(
        default=False,
        description='Установлен ли LocalAccountTokenFilterPolicy = 1 (удалённый вход локальных админов)',
    )
    ready_for_smb: bool = Field(default=False, description='Готов ли ПК к входящему подключению по SMB 445')
    ready_for_winrm: bool = Field(default=False, description='Готов ли ПК к входящему подключению по WinRM 5985')


class RemoteAccessApplyRequest(BaseModel):
    """Запрос на применение настройки удалённого доступа."""

    action: RemoteAccessActionType = Field(description='Идентификатор применяемого действия')


class RemoteAccessStepResult(BaseModel):
    """Результат одного шага настройки удалённого доступа."""

    step: str = Field(description='Название шага')
    success: bool = Field(description='Успешность выполнения шага')
    message: str = Field(default='', description='Подробности или текст ошибки')


class RemoteAccessActionResult(BaseModel):
    """Итоговый ответ после применения действия удалённого доступа."""

    success: bool = Field(description='Общая успешность операции')
    action: str = Field(description='Выполненное действие')
    message: str = Field(description='Сводное сообщение для пользователя')
    requires_admin: bool = Field(default=False, description='Требуются ли права администратора')
    steps: List[RemoteAccessStepResult] = Field(default_factory=list, description='Лог выполненных шагов')
    status: RemoteAccessStatus = Field(description='Актуальное состояние после выполнения операции')


class WindowsRemoteAccessManager:
    """Менеджер диагностики и настройки входящего удалённого доступа Windows (SMB 445 / WinRM 5985)."""

    def __init__(self, timeout_sec: float = 15.0) -> None:
        """Инициализирует менеджер удалённого доступа.

        Args:
            timeout_sec: Таймаут выполнения команд PowerShell в секундах.
        """
        self.timeout_sec = timeout_sec

    @staticmethod
    def is_admin() -> bool:
        """Проверяет, запущен ли текущий процесс с правами администратора Windows.

        Returns:
            bool: True, если процесс имеет права администратора.
        """
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def is_local_port_listening(port: int, timeout: float = 0.35) -> bool:
        """Проверяет, прослушивается ли указанный TCP-порт на локальном хосте.

        Args:
            port: Номер TCP-порта (например, 445 или 5985).
            timeout: Таймаут подключения в секундах.

        Returns:
            bool: True, если локальный порт принимает соединения.
        """
        for host in ('127.0.0.1', '::1'):
            family = socket.AF_INET6 if ':' in host else socket.AF_INET
            try:
                with socket.socket(family, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout)
                    if sock.connect_ex((host, port)) == 0:
                        return True
            except OSError:
                continue
        return False

    @staticmethod
    def read_uac_remote_allowed() -> bool:
        """Считывает политику реестра LocalAccountTokenFilterPolicy.

        Returns:
            bool: True, если LocalAccountTokenFilterPolicy == 1.
        """
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _UAC_REG_PATH, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, _UAC_REG_VALUE)
                return int(value) == 1
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.debug(f'[RemoteAccess] Не удалось прочитать {_UAC_REG_VALUE}: {exc}')
            return False

    def _run_powershell(self, script: str, timeout: Optional[float] = None) -> tuple[bool, str, str]:
        """Безопасно запускает PowerShell-команду без интерактивных запросов.

        Args:
            script: Текст скрипта PowerShell.
            timeout: Индивидуальный таймаут в секундах.

        Returns:
            tuple[bool, str, str]: (успех, stdout, stderr).
        """
        cmd = [
            'powershell.exe',
            '-NoProfile',
            '-NonInteractive',
            '-ExecutionPolicy',
            'Bypass',
            '-Command',
            f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {script}',
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout or self.timeout_sec,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            return proc.returncode == 0, (proc.stdout or '').strip(), (proc.stderr or '').strip()
        except subprocess.TimeoutExpired:
            return False, '', f'Таймаут выполнения PowerShell ({timeout or self.timeout_sec} с)'
        except OSError as exc:
            return False, '', str(exc)

    def _query_system_snapshot(self) -> Dict[str, Any]:
        """Одним вызовом PowerShell собирает профили сети, статусы служб и правила брандмауэра.

        Returns:
            Dict[str, Any]: Словарь с диагностическими данными Windows.
        """
        ps_script = r"""
$profiles = @()
try {
    $rawProfiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue
    foreach ($p in $rawProfiles) {
        $profiles += @{
            name = [string]$p.Name
            interface_alias = [string]$p.InterfaceAlias
            interface_index = [int]$p.InterfaceIndex
            category = [string]$p.NetworkCategory
        }
    }
} catch {}

function Get-SvcInfo($svcName) {
    $s = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if ($null -eq $s) {
        return @{ name = $svcName; status = 'NotFound'; start_type = 'Unknown'; running = $false }
    }
    return @{
        name = $svcName
        status = [string]$s.Status
        start_type = [string]$s.StartType
        running = ($s.Status -eq 'Running')
    }
}

function Test-InboundPortFirewall($port, $ruleNames) {
    try {
        foreach ($rn in $ruleNames) {
            $r = Get-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue | Where-Object {
                $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow'
            }
            if ($r) { return $true }
        }
        $byDisplay = Get-NetFirewallRule -DisplayName $ruleNames -ErrorAction SilentlyContinue | Where-Object {
            $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow'
        }
        if ($byDisplay) { return $true }
        $portFilters = Get-NetFirewallPortFilter -Protocol TCP -ErrorAction SilentlyContinue | Where-Object {
            $_.LocalPort -contains [string]$port
        }
        if ($portFilters) {
            $rules = $portFilters | Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object {
                $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow'
            }
            if ($rules) { return $true }
        }
    } catch {}
    return $false
}

$result = @{
    network_profiles = $profiles
    smb_service = (Get-SvcInfo 'LanmanServer')
    winrm_service = (Get-SvcInfo 'WinRM')
    smb_firewall_enabled = (Test-InboundPortFirewall '445' @('FPS-SMB-In-TCP', 'AI-TC Inbound SMB (TCP 445)'))
    winrm_firewall_enabled = (Test-InboundPortFirewall '5985' @('WINRM-HTTP-In-TCP', 'WINRM-HTTP-In-TCP-PUBLIC', 'AI-TC Inbound WinRM (TCP 5985)'))
}
$result | ConvertTo-Json -Depth 5 -Compress
"""
        ok, stdout, stderr = self._run_powershell(ps_script, timeout=15.0)
        if not ok or not stdout:
            logger.warning(f'[RemoteAccess] Ошибка опроса состояния Windows: {stderr}')
            return {}
        try:
            parsed = json.loads(stdout)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError as exc:
            logger.warning(f'[RemoteAccess] Невалидный JSON от PowerShell: {exc}')
            return {}

    def get_status(self) -> RemoteAccessStatus:
        """Возвращает полное состояние настроек входящего удалённого доступа на текущем ПК.

        Returns:
            RemoteAccessStatus: Текущая диагностика SMB 445, WinRM 5985, брандмауэра, профиля сети и UAC.
        """
        snapshot = self._query_system_snapshot()
        raw_profiles = snapshot.get('network_profiles') or []
        if isinstance(raw_profiles, dict):
            raw_profiles = [raw_profiles]

        profiles = [
            NetworkProfileInfo(
                name=str(p.get('name', '')),
                interface_alias=str(p.get('interface_alias', '')),
                interface_index=int(p.get('interface_index', 0) or 0),
                category=str(p.get('category', 'Unknown')),
            )
            for p in raw_profiles
            if isinstance(p, dict)
        ]

        smb_svc_data = snapshot.get('smb_service') or {'name': 'LanmanServer'}
        winrm_svc_data = snapshot.get('winrm_service') or {'name': 'WinRM'}
        smb_service = ServiceStatusInfo(**smb_svc_data)
        winrm_service = ServiceStatusInfo(**winrm_svc_data)

        port_445 = self.is_local_port_listening(445)
        port_5985 = self.is_local_port_listening(5985)
        smb_fw = bool(snapshot.get('smb_firewall_enabled', False))
        winrm_fw = bool(snapshot.get('winrm_firewall_enabled', False))
        uac_allowed = self.read_uac_remote_allowed()
        has_public = any(p.category.lower() == 'public' for p in profiles)

        return RemoteAccessStatus(
            is_admin=self.is_admin(),
            hostname=socket.gethostname(),
            network_profiles=profiles,
            has_public_profile=has_public,
            smb_service=smb_service,
            winrm_service=winrm_service,
            port_445_listening=port_445,
            port_5985_listening=port_5985,
            smb_firewall_enabled=smb_fw,
            winrm_firewall_enabled=winrm_fw,
            uac_remote_allowed=uac_allowed,
            ready_for_smb=bool(smb_service.running and port_445 and smb_fw),
            ready_for_winrm=bool(winrm_service.running and port_5985 and winrm_fw),
        )

    def _set_private_profile(self) -> RemoteAccessStepResult:
        """Переключает активные сетевые профили из Public в Private."""
        ps = r"""
$pub = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq 'Public' }
if (-not $pub) {
    Write-Output 'NO_PUBLIC'
    exit 0
}
foreach ($p in $pub) {
    Set-NetConnectionProfile -InterfaceIndex $p.InterfaceIndex -NetworkCategory Private -ErrorAction Stop
}
Write-Output 'UPDATED'
"""
        ok, stdout, stderr = self._run_powershell(ps)
        if ok:
            msg = 'Все активные сети уже в частном/доменном профиле' if 'NO_PUBLIC' in stdout else 'Сетевой профиль переключён на Private'
            return RemoteAccessStepResult(step='Сетевой профиль (Private)', success=True, message=msg)
        return RemoteAccessStepResult(step='Сетевой профиль (Private)', success=False, message=stderr or 'Не удалось изменить профиль сети')

    def _set_smb_firewall(self, enable: bool) -> RemoteAccessStepResult:
        """Включает или отключает входящие правила брандмауэра для SMB (TCP 445)."""
        if enable:
            ps = f"""
$enabledAny = $false
$builtin = Get-NetFirewallRule -Name 'FPS-SMB-In-TCP' -ErrorAction SilentlyContinue
if ($builtin) {{
    Enable-NetFirewallRule -Name 'FPS-SMB-In-TCP' -ErrorAction Stop
    $enabledAny = $true
}}
$custom = Get-NetFirewallRule -DisplayName '{_CUSTOM_SMB_RULE_NAME}' -ErrorAction SilentlyContinue
if ($custom) {{
    Enable-NetFirewallRule -DisplayName '{_CUSTOM_SMB_RULE_NAME}' -ErrorAction Stop
    $enabledAny = $true
}} elseif (-not $enabledAny) {{
    New-NetFirewallRule -DisplayName '{_CUSTOM_SMB_RULE_NAME}' -Direction Inbound -Protocol TCP -LocalPort 445 -Action Allow -Profile Private,Domain -ErrorAction Stop | Out-Null
}}
Write-Output 'OK'
"""
            step_name = 'Брандмауэр SMB (TCP 445)'
            ok_msg = 'Входящий порт SMB (TCP 445) открыт в брандмауэре'
        else:
            ps = f"""
$builtin = Get-NetFirewallRule -Name 'FPS-SMB-In-TCP' -ErrorAction SilentlyContinue
if ($builtin) {{ Disable-NetFirewallRule -Name 'FPS-SMB-In-TCP' -ErrorAction SilentlyContinue }}
$custom = Get-NetFirewallRule -DisplayName '{_CUSTOM_SMB_RULE_NAME}' -ErrorAction SilentlyContinue
if ($custom) {{ Disable-NetFirewallRule -DisplayName '{_CUSTOM_SMB_RULE_NAME}' -ErrorAction SilentlyContinue }}
Write-Output 'OK'
"""
            step_name = 'Брандмауэр SMB (TCP 445)'
            ok_msg = 'Входящие правила SMB (TCP 445) отключены в брандмауэре'

        ok, _, stderr = self._run_powershell(ps)
        return RemoteAccessStepResult(step=step_name, success=ok, message=ok_msg if ok else (stderr or 'Ошибка настройки правила SMB 445'))

    def _set_winrm_firewall(self, enable: bool) -> RemoteAccessStepResult:
        """Включает или отключает входящие правила брандмауэра для WinRM (TCP 5985)."""
        if enable:
            ps = f"""
$enabledAny = $false
$builtin = Get-NetFirewallRule -Name 'WINRM-HTTP-In-TCP' -ErrorAction SilentlyContinue
if ($builtin) {{
    Enable-NetFirewallRule -Name 'WINRM-HTTP-In-TCP' -ErrorAction Stop
    $enabledAny = $true
}}
$custom = Get-NetFirewallRule -DisplayName '{_CUSTOM_WINRM_RULE_NAME}' -ErrorAction SilentlyContinue
if ($custom) {{
    Enable-NetFirewallRule -DisplayName '{_CUSTOM_WINRM_RULE_NAME}' -ErrorAction Stop
    $enabledAny = $true
}} elseif (-not $enabledAny) {{
    New-NetFirewallRule -DisplayName '{_CUSTOM_WINRM_RULE_NAME}' -Direction Inbound -Protocol TCP -LocalPort 5985 -Action Allow -Profile Private,Domain -ErrorAction Stop | Out-Null
}}
Write-Output 'OK'
"""
            step_name = 'Брандмауэр WinRM (TCP 5985)'
            ok_msg = 'Входящий порт WinRM (TCP 5985) открыт в брандмауэре'
        else:
            ps = f"""
foreach ($rn in @('WINRM-HTTP-In-TCP', 'WINRM-HTTP-In-TCP-PUBLIC')) {{
    $r = Get-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue
    if ($r) {{ Disable-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue }}
}}
$custom = Get-NetFirewallRule -DisplayName '{_CUSTOM_WINRM_RULE_NAME}' -ErrorAction SilentlyContinue
if ($custom) {{ Disable-NetFirewallRule -DisplayName '{_CUSTOM_WINRM_RULE_NAME}' -ErrorAction SilentlyContinue }}
Write-Output 'OK'
"""
            step_name = 'Брандмауэр WinRM (TCP 5985)'
            ok_msg = 'Входящие правила WinRM (TCP 5985) отключены в брандмауэре'

        ok, _, stderr = self._run_powershell(ps)
        return RemoteAccessStepResult(step=step_name, success=ok, message=ok_msg if ok else (stderr or 'Ошибка настройки правила WinRM 5985'))

    def _set_smb_service(self, enable: bool) -> RemoteAccessStepResult:
        """Включает или останавливает службу LanmanServer (SMB)."""
        if enable:
            ps = "Set-Service -Name LanmanServer -StartupType Automatic -ErrorAction Stop; Start-Service -Name LanmanServer -ErrorAction Stop"
            ok_msg = 'Служба LanmanServer (SMB) переведена в Авто и запущена'
        else:
            ps = "Stop-Service -Name LanmanServer -Force -ErrorAction Stop"
            ok_msg = 'Служба LanmanServer (SMB) остановлена'
        ok, _, stderr = self._run_powershell(ps)
        return RemoteAccessStepResult(step='Служба SMB (LanmanServer)', success=ok, message=ok_msg if ok else (stderr or 'Ошибка управления службой LanmanServer'))

    def _set_winrm_service(self, enable: bool) -> RemoteAccessStepResult:
        """Включает (Enable-PSRemoting) или отключает службу WinRM (порт 5985)."""
        if enable:
            ps = (
                "Set-Service -Name WinRM -StartupType Automatic -ErrorAction Stop; "
                "Start-Service -Name WinRM -ErrorAction Stop; "
                "Enable-PSRemoting -Force -SkipNetworkProfileCheck -ErrorAction Stop | Out-Null"
            )
            ok_msg = 'WinRM и PowerShell Remoting (TCP 5985) включены'
        else:
            ps = (
                "Disable-PSRemoting -Force -ErrorAction SilentlyContinue | Out-Null; "
                "Stop-Service -Name WinRM -Force -ErrorAction Stop; "
                "Set-Service -Name WinRM -StartupType Manual -ErrorAction SilentlyContinue"
            )
            ok_msg = 'Служба WinRM и PowerShell Remoting отключены'
        ok, _, stderr = self._run_powershell(ps, timeout=25.0)
        return RemoteAccessStepResult(step='Служба WinRM (TCP 5985)', success=ok, message=ok_msg if ok else (stderr or 'Ошибка управления службой WinRM'))

    def _set_uac_remote_allowed(self, allow: bool) -> RemoteAccessStepResult:
        """Устанавливает значение реестра LocalAccountTokenFilterPolicy (1 или 0)."""
        target_val = 1 if allow else 0
        step_name = 'UAC Remote Restrictions (LocalAccountTokenFilterPolicy)'
        if winreg is None:
            return RemoteAccessStepResult(step=step_name, success=False, message='Модуль winreg недоступен на данной ОС')
        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, _UAC_REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, _UAC_REG_VALUE, 0, winreg.REG_DWORD, target_val)
            msg = (
                'LocalAccountTokenFilterPolicy = 1 (удалённый вход локальных администраторов разрешён)'
                if allow
                else 'LocalAccountTokenFilterPolicy = 0 (стандартное ограничение UAC восстановлено)'
            )
            return RemoteAccessStepResult(step=step_name, success=True, message=msg)
        except OSError as exc:
            return RemoteAccessStepResult(step=step_name, success=False, message=f'Ошибка записи реестра: {exc}')

    def apply_action(self, action: RemoteAccessActionType) -> RemoteAccessActionResult:
        """Применяет выбранную настройку входящего удалённого доступа.

        Args:
            action: Идентификатор действия из RemoteAccessActionType.

        Returns:
            RemoteAccessActionResult: Подробный результат и обновлённое состояние системы.
        """
        if not self.is_admin():
            status = self.get_status()
            return RemoteAccessActionResult(
                success=False,
                action=action,
                message='Для изменения системных настроек (брандмауэр, службы, реестр) запустите сервер AI-TC от имени администратора.',
                requires_admin=True,
                steps=[],
                status=status,
            )

        steps: List[RemoteAccessStepResult] = []

        if action == 'enable_all':
            steps.append(self._set_private_profile())
            steps.append(self._set_smb_service(True))
            steps.append(self._set_smb_firewall(True))
            steps.append(self._set_winrm_service(True))
            steps.append(self._set_winrm_firewall(True))
            steps.append(self._set_uac_remote_allowed(True))
        elif action == 'disable_all':
            steps.append(self._set_smb_firewall(False))
            steps.append(self._set_winrm_firewall(False))
            steps.append(self._set_winrm_service(False))
            steps.append(self._set_uac_remote_allowed(False))
        elif action == 'set_private_profile':
            steps.append(self._set_private_profile())
        elif action == 'enable_smb':
            steps.append(self._set_smb_service(True))
            steps.append(self._set_smb_firewall(True))
        elif action == 'disable_smb':
            steps.append(self._set_smb_firewall(False))
        elif action == 'enable_winrm':
            steps.append(self._set_winrm_service(True))
            steps.append(self._set_winrm_firewall(True))
        elif action == 'disable_winrm':
            steps.append(self._set_winrm_firewall(False))
            steps.append(self._set_winrm_service(False))
        elif action == 'enable_smb_firewall':
            steps.append(self._set_smb_firewall(True))
        elif action == 'disable_smb_firewall':
            steps.append(self._set_smb_firewall(False))
        elif action == 'enable_winrm_firewall':
            steps.append(self._set_winrm_firewall(True))
        elif action == 'disable_winrm_firewall':
            steps.append(self._set_winrm_firewall(False))
        elif action == 'enable_uac_remote':
            steps.append(self._set_uac_remote_allowed(True))
        elif action == 'disable_uac_remote':
            steps.append(self._set_uac_remote_allowed(False))

        all_ok = all(s.success for s in steps) if steps else False
        failed = [s for s in steps if not s.success]
        if all_ok:
            summary = '; '.join(s.message for s in steps if s.message) or 'Настройки успешно применены'
        else:
            summary = 'Выполнено с ошибками: ' + '; '.join(f'{s.step}: {s.message}' for s in failed)

        status = self.get_status()
        return RemoteAccessActionResult(
            success=all_ok,
            action=action,
            message=summary,
            requires_admin=False,
            steps=steps,
            status=status,
        )


__all__ = [
    'NetworkProfileInfo',
    'RemoteAccessActionResult',
    'RemoteAccessActionType',
    'RemoteAccessApplyRequest',
    'RemoteAccessStatus',
    'RemoteAccessStepResult',
    'ServiceStatusInfo',
    'WindowsRemoteAccessManager',
]
