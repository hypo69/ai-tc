# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - PowerShell / wsl.exe Runner
# =============================================================================
# Description:
#   Контролируемый read-only запуск PowerShell и wsl.exe: allowlist глаголов
#   командлетов и аргументов wsl.exe, тайм-аут, раздельные stdout/stderr, проверка
#   кода завершения, декодирование (UTF-8 / UTF-16LE), нормализация JSON
#   (одиночный объект -> список, пустой вывод -> []).
#   Пользовательский ввод в скрипты не подставляется.
#
# Usage Examples:
#   runner = PowerShellRunner(timeout_sec=20)
#   res = runner.run_json('Get-NetAdapter | Select-Object Name | ConvertTo-Json')
#   if res.ok: rows = res.data
#
# File: ps_runner.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from logger import logger

# Разрешены только читающие глаголы и служебные конвейерные командлеты.
ALLOWED_VERBS = frozenset({'Get', 'Select', 'Where', 'ForEach', 'ConvertTo', 'Sort', 'Test', 'Measure'})
# Разрешённые наборы аргументов wsl.exe.
ALLOWED_WSL_ARGS = (('--status',), ('--list', '--verbose'), ('--version',))

_CMDLET_RE = re.compile(r'\b([A-Z][A-Za-z]+)-([A-Z][A-Za-z]+)\b')
_ACCESS_DENIED_RE = re.compile(
    r'access is denied|unauthorized|not have the required permission|authorization policy|'
    r'отказано в доступе|нет необходимых разрешений|требуется повышение', re.IGNORECASE)


class ForbiddenCommandError(ValueError):
    """Попытка выполнить команду вне allowlist (изменяющую состояние системы)."""


@dataclass
class PsResult:
    """Результат вызова внешнего процесса.

    Attributes:
        ok: Код завершения 0, без тайм-аута и ошибки разбора.
        data: Нормализованный список объектов (для JSON-вызовов).
        text: Декодированный stdout (для текстовых вызовов).
        stderr: Декодированный stderr.
        return_code: Код завершения (-1 при тайм-ауте/невозможности запуска).
        timed_out: Признак тайм-аута.
        access_denied: В stderr обнаружен отказ в доступе.
        error: Краткое описание ошибки.
        duration_ms: Длительность вызова.
    """

    ok: bool
    data: List[Any] = field(default_factory=list)
    text: str = ''
    stderr: str = ''
    return_code: int = 0
    timed_out: bool = False
    access_denied: bool = False
    error: str = ''
    duration_ms: int = 0


def assert_read_only(script: str) -> None:
    """Проверяет, что все командлеты скрипта имеют разрешённый (читающий) глагол.

    Args:
        script: Текст PowerShell-скрипта.

    Raises:
        ForbiddenCommandError: Найден командлет с неразрешённым глаголом.
    """
    for verb, noun in _CMDLET_RE.findall(script):
        if verb not in ALLOWED_VERBS:
            raise ForbiddenCommandError(f'Командлет {verb}-{noun} запрещён в режиме read-only')


def decode_output(raw: bytes) -> str:
    """Декодирует вывод процесса: UTF-16LE (характерно для wsl.exe) или UTF-8.

    Args:
        raw: Байты вывода.

    Returns:
        str: Текст без нулевых символов и BOM.
    """
    if not raw:
        return ''
    if raw.startswith(b'\xff\xfe') or b'\x00' in raw:
        text = raw.decode('utf-16-le', errors='replace')
    else:
        text = raw.decode('utf-8-sig', errors='replace')
    return text.replace('\x00', '').lstrip('\ufeff')


def normalize_json_output(text: str) -> List[Any]:
    """Приводит JSON-вывод PowerShell к списку.

    Args:
        text: stdout PowerShell (результат ConvertTo-Json).

    Returns:
        List[Any]: Пустой список для пустого вывода, [obj] для одиночного объекта.

    Raises:
        ValueError: Некорректный JSON.
    """
    clean = text.strip()
    if not clean:
        return []
    parsed = json.loads(clean)
    if parsed is None:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


class PowerShellRunner:
    """Запускает PowerShell и wsl.exe строго в режиме чтения."""

    def __init__(self, timeout_sec: int = 25, wsl_timeout_sec: int = 15,
                 powershell_path: Optional[str] = None) -> None:
        """Инициализирует раннер.

        Args:
            timeout_sec: Тайм-аут PowerShell, сек.
            wsl_timeout_sec: Тайм-аут wsl.exe, сек.
            powershell_path: Явный путь к powershell.exe (иначе автообнаружение).
        """
        self.timeout_sec = timeout_sec
        self.wsl_timeout_sec = wsl_timeout_sec
        self._ps_path = powershell_path

    def powershell_executable(self) -> Optional[str]:
        """Возвращает путь к powershell.exe или None, если он не найден."""
        if self._ps_path:
            return self._ps_path
        windir = os.environ.get('SystemRoot', r'C:\Windows')
        candidate = os.path.join(windir, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        if os.path.exists(candidate):
            return candidate
        return shutil.which('powershell.exe') or shutil.which('powershell')

    def _execute(self, argv: Sequence[str], timeout: int) -> PsResult:
        """Запускает процесс с тайм-аутом и разбором результата."""
        started = time.perf_counter()
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            proc = subprocess.run(list(argv), capture_output=True, timeout=timeout,
                                  creationflags=flags, check=False, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return PsResult(ok=False, return_code=-1, timed_out=True,
                            error=f'Тайм-аут {timeout} сек.',
                            duration_ms=int((time.perf_counter() - started) * 1000))
        except OSError as exc:
            return PsResult(ok=False, return_code=-1, error=f'Не удалось запустить процесс: {exc}',
                            duration_ms=int((time.perf_counter() - started) * 1000))
        text = decode_output(proc.stdout)
        err = decode_output(proc.stderr)
        denied = bool(_ACCESS_DENIED_RE.search(err) or _ACCESS_DENIED_RE.search(text))
        return PsResult(ok=proc.returncode == 0, text=text, stderr=err, return_code=proc.returncode,
                        access_denied=denied, error='' if proc.returncode == 0 else f'Код завершения {proc.returncode}',
                        duration_ms=int((time.perf_counter() - started) * 1000))

    def run_json(self, script: str, timeout: Optional[int] = None) -> PsResult:
        """Выполняет read-only PowerShell-скрипт и разбирает JSON-вывод.

        Args:
            script: Скрипт (константа сборщика), должен выводить JSON.
            timeout: Тайм-аут, сек.

        Returns:
            PsResult: Результат; data — список объектов.

        Raises:
            ForbiddenCommandError: Скрипт содержит запрещённые командлеты.
        """
        assert_read_only(script)
        exe = self.powershell_executable()
        if not exe:
            return PsResult(ok=False, return_code=-1, error='powershell.exe не найден')
        wrapped = f"$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; " \
                  f"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; {script}"
        encoded = base64.b64encode(wrapped.encode('utf-16le')).decode('ascii')
        result = self._execute([exe, '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                               timeout or self.timeout_sec)
        if not result.ok:
            logger.warning(f'[NetworkInfra] PowerShell: {result.error}; {result.stderr.strip()[:300]}')
            return result
        try:
            result.data = normalize_json_output(result.text)
        except ValueError as exc:
            result.ok = False
            result.error = f'Некорректный JSON: {exc}'
            logger.warning(f'[NetworkInfra] {result.error}')
        return result

    def run_wsl(self, args: Sequence[str]) -> PsResult:
        """Выполняет wsl.exe с разрешённым набором аргументов (текстовый вывод).

        Args:
            args: Аргументы из ALLOWED_WSL_ARGS.

        Returns:
            PsResult: Результат; text — декодированный stdout.

        Raises:
            ForbiddenCommandError: Набор аргументов не разрешён.
        """
        if tuple(args) not in ALLOWED_WSL_ARGS:
            raise ForbiddenCommandError(f'Аргументы wsl.exe запрещены: {list(args)}')
        exe = shutil.which('wsl.exe')
        if not exe:
            return PsResult(ok=False, return_code=-1, error='wsl.exe не найден')
        return self._execute([exe, *args], self.wsl_timeout_sec)

    def which_wsl(self) -> Optional[str]:
        """Возвращает путь к wsl.exe, если он есть в системе."""
        return shutil.which('wsl.exe')

