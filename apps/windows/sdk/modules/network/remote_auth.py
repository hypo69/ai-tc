# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Network - Remote Authenticator
# =============================================================================
# Description:
#   Модуль безопасной аутентификации на удалённых компьютерах в локальной сети
#   через нативный Windows SMB (Win32 API WNetAddConnection2W / NetShareEnum)
#   и WinRM (PowerShell Remoting) с защитой от инъекций и таймаутами.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.remote_auth import WindowsRemoteAuthenticator
#
#     auth = WindowsRemoteAuthenticator()
#     result = auth.authenticate('192.168.1.10', 'Administrator', 'secret')
#
# File: remote_auth.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 17:15:00
# =============================================================================

from __future__ import annotations
"""Модуль аутентификации на удалённых компьютерах в локальной сети (SMB / WinRM)."""

import ctypes
import ipaddress
import json
import os
import socket
import subprocess
import time
from ctypes import wintypes
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logger import logger


# Коды ошибок Win32 API для сетевой аутентификации (WNetAddConnection2W)
WIN32_AUTH_ERRORS: Dict[int, str] = {
    0: 'Успешное подключение',
    5: 'Доступ запрещён (проверьте права пользователя или UAC Remote Restrictions)',
    53: 'Сетевой путь не найден (служба SMB/порт 445 недоступна на удалённом ПК)',
    67: 'Сетевое имя не найдено',
    86: 'Указан неверный сетевой пароль',
    1219: 'Конфликт учётных данных: уже открыто подключение к этому серверу под другим пользователем',
    1311: 'Серверы входа в сеть недоступны',
    1326: 'Неверное имя пользователя или пароль',
    1327: 'Ограничение учётной записи (например, запрещён вход с пустым паролем по сети)',
    1331: 'Учётная запись отключена на удалённом компьютере',
    1909: 'Учётная запись заблокирована на удалённом компьютере',
    2202: 'Указано недопустимое имя пользователя',
}


class RemoteLoginRequest(BaseModel):
    """Модель запроса аутентификации на удалённом компьютере."""

    ip: str = Field(description='IPv4-адрес удалённого компьютера')
    username: str = Field(min_length=1, max_length=256, description='Имя пользователя (User, DOMAIN\\User или .\\User)')
    password: str = Field(default='', max_length=512, description='Пароль учётной записи')
    protocol: str = Field(default='auto', description='Протокол входа: auto, smb, winrm')


class RemoteLoginResult(BaseModel):
    """Результат попытки входа на удалённый компьютер."""

    success: bool = Field(description='Успешность аутентификации')
    ip: str = Field(description='IP-адрес целевого узла')
    username: str = Field(description='Имя пользователя')
    protocol_used: str = Field(description='Использованный протокол (smb, winrm, none)')
    message: str = Field(description='Человекочитаемый результат операции')
    error_code: Optional[int] = Field(default=None, description='Системный код ошибки (при неудаче)')
    latency_ms: float = Field(default=0.0, description='Время выполнения проверки в миллисекундах')
    details: Dict[str, Any] = Field(default_factory=dict, description='Дополнительные сведения (шары SMB, имя ПК, ОС)')


class _NETRESOURCEW(ctypes.Structure):
    """Структура Win32 NETRESOURCEW для функции WNetAddConnection2W."""

    _fields_ = [
        ('dwScope', wintypes.DWORD),
        ('dwType', wintypes.DWORD),
        ('dwDisplayType', wintypes.DWORD),
        ('dwUsage', wintypes.DWORD),
        ('lpLocalName', wintypes.LPWSTR),
        ('lpRemoteName', wintypes.LPWSTR),
        ('lpComment', wintypes.LPWSTR),
        ('lpProvider', wintypes.LPWSTR),
    ]


class _SHARE_INFO_1(ctypes.Structure):
    """Структура Win32 SHARE_INFO_1 для функции NetShareEnum."""

    _fields_ = [
        ('shi1_netname', wintypes.LPWSTR),
        ('shi1_type', wintypes.DWORD),
        ('shi1_remark', wintypes.LPWSTR),
    ]


class WindowsRemoteAuthenticator:
    """Нативный клиент проверки и установления сеанса входа на удалённых Windows-ПК."""

    @staticmethod
    def validate_ip(ip: str) -> str:
        """Проверяет корректность IP-адреса (Fail-Fast и защита от инъекций).

        Args:
            ip: Строка с IP-адресом.

        Returns:
            str: Нормализованный IP-адрес.

        Raises:
            ValueError: Если строка не является валидным IPv4/IPv6 адресом.
        """
        cleaned = (ip or '').strip()
        parsed = ipaddress.ip_address(cleaned)
        return str(parsed)

    @staticmethod
    def is_port_open(ip: str, port: int, timeout_sec: float = 1.5) -> bool:
        """Проверяет доступность TCP-порта на целевом хосте с таймаутом.

        Args:
            ip: IP-адрес хоста.
            port: Номер TCP-порта.
            timeout_sec: Таймаут подключения в секундах.

        Returns:
            bool: True, если порт открыт и принимает соединения.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout_sec)
                return sock.connect_ex((ip, port)) == 0
        except Exception:
            return False

    def _wnet_add_connection(self, remote_name: str, username: str, password: str) -> int:
        """Вызывает Win32 API WNetAddConnection2W для подключения к сетевому ресурсу.

        Args:
            remote_name: UNC-путь ресурса (например, \\\\192.168.1.10\\IPC$).
            username: Имя пользователя.
            password: Пароль пользователя.

        Returns:
            int: Код возврата Win32 API (0 при успехе).
        """
        mpr = ctypes.windll.mpr
        mpr.WNetAddConnection2W.argtypes = [
            ctypes.POINTER(_NETRESOURCEW),
            wintypes.LPWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        mpr.WNetAddConnection2W.restype = wintypes.DWORD

        nr = _NETRESOURCEW()
        nr.dwType = 0  # RESOURCETYPE_ANY
        nr.lpLocalName = None
        nr.lpRemoteName = remote_name
        nr.lpProvider = None

        return int(mpr.WNetAddConnection2W(ctypes.byref(nr), password, username, 0))

    def _wnet_cancel_connection(self, remote_name: str) -> int:
        """Закрывает существующее сетевое подключение через WNetCancelConnection2W.

        Args:
            remote_name: UNC-путь ресурса.

        Returns:
            int: Код возврата Win32 API.
        """
        try:
            mpr = ctypes.windll.mpr
            mpr.WNetCancelConnection2W.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.BOOL]
            mpr.WNetCancelConnection2W.restype = wintypes.DWORD
            return int(mpr.WNetCancelConnection2W(remote_name, 0, True))
        except Exception:
            return -1

    def _enum_remote_shares(self, ip: str) -> List[str]:
        """Получает список общих сетевых папок удалённого компьютера через NetShareEnum.

        Args:
            ip: IP-адрес удалённого компьютера.

        Returns:
            List[str]: Список имён общих ресурсов.
        """
        shares: List[str] = []
        buf_ptr = ctypes.c_void_p()
        entries_read = wintypes.DWORD(0)
        total_entries = wintypes.DWORD(0)
        resume_handle = wintypes.DWORD(0)

        try:
            netapi32 = ctypes.windll.netapi32
            netapi32.NetShareEnum.argtypes = [
                wintypes.LPWSTR,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
            ]
            netapi32.NetShareEnum.restype = wintypes.DWORD
            netapi32.NetApiBufferFree.argtypes = [ctypes.c_void_p]
            netapi32.NetApiBufferFree.restype = wintypes.DWORD

            status = netapi32.NetShareEnum(
                f'\\\\{ip}',
                1,
                ctypes.byref(buf_ptr),
                0xFFFFFFFF,  # MAX_PREFERRED_LENGTH
                ctypes.byref(entries_read),
                ctypes.byref(total_entries),
                ctypes.byref(resume_handle),
            )
            if status == 0 and buf_ptr.value:
                arr_type = _SHARE_INFO_1 * entries_read.value
                arr = ctypes.cast(buf_ptr, ctypes.POINTER(arr_type)).contents
                for item in arr:
                    if item.shi1_netname:
                        shares.append(str(item.shi1_netname))
        except Exception as ex:
            logger.debug(f'[RemoteAuth] Не удалось перечислить шары {ip}: {ex}')
        finally:
            if buf_ptr.value:
                try:
                    ctypes.windll.netapi32.NetApiBufferFree(buf_ptr)
                except Exception:
                    pass

        return shares

    def authenticate_smb(self, ip: str, username: str, password: str) -> RemoteLoginResult:
        """Выполняет нативный вход по SMB на ресурс \\\\<ip>\\IPC$.

        Args:
            ip: Валидный IP-адрес удалённого ПК.
            username: Имя пользователя.
            password: Пароль.

        Returns:
            RemoteLoginResult: Результат попытки входа по SMB.
        """
        started = time.perf_counter()

        if not self.is_port_open(ip, 445, timeout_sec=1.5):
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return RemoteLoginResult(
                success=False,
                ip=ip,
                username=username,
                protocol_used='smb',
                message='Порт SMB (445) недоступен на удалённом компьютере',
                error_code=53,
                latency_ms=elapsed,
            )

        remote_ipc = f'\\\\{ip}\\IPC$'
        effective_user = username if ('\\' in username or '@' in username) else f'{ip}\\{username}'
        code = self._wnet_add_connection(remote_ipc, effective_user, password)

        # Если конфликт существующей сессии — сбрасываем её и пробуем повторно
        if code == 1219:
            self._wnet_cancel_connection(remote_ipc)
            code = self._wnet_add_connection(remote_ipc, effective_user, password)

        elapsed = round((time.perf_counter() - started) * 1000, 1)

        if code == 0:
            shares = self._enum_remote_shares(ip)
            logger.info(f'[RemoteAuth] Успешный вход по SMB на {ip} (пользователь: {username})')
            return RemoteLoginResult(
                success=True,
                ip=ip,
                username=username,
                protocol_used='smb',
                message=f'Успешный вход на {ip} по протоколу SMB (IPC$)',
                error_code=0,
                latency_ms=elapsed,
                details={
                    'unc_path': f'\\\\{ip}',
                    'shares': shares,
                    'shares_count': len(shares),
                },
            )

        err_msg = WIN32_AUTH_ERRORS.get(code, f'Ошибка сетевой аутентификации Windows (код {code})')
        logger.warning(f'[RemoteAuth] Ошибка входа по SMB на {ip} (пользователь: {username}, код: {code})')
        return RemoteLoginResult(
            success=False,
            ip=ip,
            username=username,
            protocol_used='smb',
            message=err_msg,
            error_code=code,
            latency_ms=elapsed,
        )

    def authenticate_winrm(
        self,
        ip: str,
        username: str,
        password: str,
        timeout_sec: float = 10.0,
    ) -> RemoteLoginResult:
        """Выполняет проверку входа через PowerShell Remoting (WinRM, порт 5985).

        Учётные данные передаются строго через переменные окружения дочернего процесса
        (без подстановки пароля в командную строку).

        Args:
            ip: Валидный IP-адрес удалённого ПК.
            username: Имя пользователя.
            password: Пароль.
            timeout_sec: Таймаут выполнения команды.

        Returns:
            RemoteLoginResult: Результат попытки входа через WinRM.
        """
        started = time.perf_counter()

        if not self.is_port_open(ip, 5985, timeout_sec=1.5):
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return RemoteLoginResult(
                success=False,
                ip=ip,
                username=username,
                protocol_used='winrm',
                message='Порт WinRM (5985) недоступен на удалённом компьютере',
                error_code=53,
                latency_ms=elapsed,
            )

        ps_script = (
            "$ErrorActionPreference = 'Stop'; "
            "$secPass = ConvertTo-SecureString $env:AITC_REM_PASS -AsPlainText -Force; "
            "$cred = New-Object System.Management.Automation.PSCredential($env:AITC_REM_USER, $secPass); "
            "$res = Invoke-Command -ComputerName $env:AITC_REM_IP -Credential $cred -ScriptBlock { "
            "  @{ computer = $env:COMPUTERNAME; user = $env:USERNAME; os = (Get-CimInstance Win32_OperatingSystem).Caption } "
            "}; "
            "$res | ConvertTo-Json -Compress"
        )

        child_env = os.environ.copy()
        child_env['AITC_REM_IP'] = ip
        child_env['AITC_REM_USER'] = username if ('\\' in username or '@' in username) else f'{ip}\\{username}'
        child_env['AITC_REM_PASS'] = password

        try:
            proc = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=child_env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            elapsed = round((time.perf_counter() - started) * 1000, 1)

            if proc.returncode == 0 and proc.stdout.strip():
                info: Dict[str, Any] = {}
                try:
                    info = json.loads(proc.stdout.strip())
                except Exception:
                    info = {'raw': proc.stdout.strip()}

                logger.info(f'[RemoteAuth] Успешный вход по WinRM на {ip} (пользователь: {username})')
                return RemoteLoginResult(
                    success=True,
                    ip=ip,
                    username=username,
                    protocol_used='winrm',
                    message=f'Успешный вход на {ip} через WinRM (PowerShell Remoting)',
                    error_code=0,
                    latency_ms=elapsed,
                    details=info,
                )

            stderr_clean = (proc.stderr or proc.stdout or '').strip().splitlines()
            short_err = stderr_clean[0] if stderr_clean else 'Не удалось выполнить вход через WinRM'
            return RemoteLoginResult(
                success=False,
                ip=ip,
                username=username,
                protocol_used='winrm',
                message=f'WinRM: {short_err[:240]}',
                error_code=proc.returncode,
                latency_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return RemoteLoginResult(
                success=False,
                ip=ip,
                username=username,
                protocol_used='winrm',
                message=f'Превышен таймаут ожидания ответа WinRM ({timeout_sec}с)',
                error_code=1460,
                latency_ms=elapsed,
            )
        except Exception as ex:
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return RemoteLoginResult(
                success=False,
                ip=ip,
                username=username,
                protocol_used='winrm',
                message=f'Ошибка запуска WinRM: {ex}',
                error_code=-1,
                latency_ms=elapsed,
            )

    def authenticate(
        self,
        ip: str,
        username: str,
        password: str,
        protocol: str = 'auto',
        timeout_sec: float = 10.0,
    ) -> RemoteLoginResult:
        """Выполняет аутентификацию на удалённом компьютере выбранным или автоматическим протоколом.

        Args:
            ip: IP-адрес удалённого узла.
            username: Имя пользователя.
            password: Пароль.
            protocol: Режим подключения ('auto', 'smb', 'winrm').
            timeout_sec: Таймаут сетевой операции.

        Returns:
            RemoteLoginResult: Подробный результат попытки входа.
        """
        valid_ip = self.validate_ip(ip)
        clean_user = (username or '').strip()
        if not clean_user:
            raise ValueError('Имя пользователя не может быть пустым')

        proto = (protocol or 'auto').strip().lower()
        if proto == 'smb':
            return self.authenticate_smb(valid_ip, clean_user, password)
        if proto == 'winrm':
            return self.authenticate_winrm(valid_ip, clean_user, password, timeout_sec=timeout_sec)

        # Автоматический режим: сначала пробуем SMB (445), если порт закрыт — WinRM (5985)
        smb_res = self.authenticate_smb(valid_ip, clean_user, password)
        if smb_res.success:
            return smb_res

        # Если SMB отклонил учётные данные (1326 / 86 / 1327 / 1331 / 5), нет смысла скрывать причину
        if smb_res.error_code in (5, 86, 1326, 1327, 1331, 1909):
            return smb_res

        # Если порт 445 закрыт — пробуем WinRM (5985)
        winrm_res = self.authenticate_winrm(valid_ip, clean_user, password, timeout_sec=timeout_sec)
        if winrm_res.success:
            return winrm_res

        return RemoteLoginResult(
            success=False,
            ip=valid_ip,
            username=clean_user,
            protocol_used='auto',
            message=f'Не удалось войти: SMB — {smb_res.message}; WinRM — {winrm_res.message}',
            error_code=smb_res.error_code,
            latency_ms=round(smb_res.latency_ms + winrm_res.latency_ms, 1),
        )


__all__ = [
    'RemoteLoginRequest',
    'RemoteLoginResult',
    'WindowsRemoteAuthenticator',
    'WIN32_AUTH_ERRORS',
]
