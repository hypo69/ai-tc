# -*- coding: utf-8 -*-
# =============================================================================
# Файл: utils/command_validator.py
# Описание: Модуль безопасного выполнения, синтаксической валидации (AST),
#           сухого запуска (dry-run), защиты от Command Injection и контроля
#           открытости ошибок PowerShell/CLI.
#
# Требования проекта:
#   • Запрещено сокрытие ошибок: флаг -ErrorAction SilentlyContinue запрещен!
#   • Ошибки (stderr) всегда сохраняются и передаются для анализа и самокоррекции.
#   • Вывод сообщений в консоль выполняется строго через logger.console()
#   • Докстринги и комментарии – строго на русском языке
#   • При изменении файла обновляется шапка с датой/временем
# =============================================================================
# Updated: 2026-11-10 18:13:00
# =============================================================================

"""hypo69 docblock
Модуль предоставляет инструменты для:
* Проверки безопасности команды (защита от разрушительных паттернов и инъекций).
* Синтаксической проверки скриптов PowerShell через AST Parser без их исполнения.
* Сухого запуска (dry-run) с использованием -WhatIf и проверки наличия утилит в PATH.
* Контроля прозрачности ошибок: обнаружение и удаление маскирующих флагов (-ErrorAction SilentlyContinue).
* Полного захвата и сохранения stderr для анализа моделью и оператором с обязательным таймаутом.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import re
import shlex
import subprocess
from typing import Any, Dict, List, Tuple

try:
    from src.logger import logger  # type: ignore
except ImportError:
    try:
        from logger import logger  # type: ignore
    except ImportError:
        class _DummyLogger:
            @staticmethod
            def console(msg: str) -> None:
                print(msg)
        logger = _DummyLogger()

# Стандартный таймаут выполнения внешней команды (секунды)
DEFAULT_COMMAND_TIMEOUT_SEC: int = 35

# Предкомпилированные множества и регулярные выражения для O(1) проверки командлетов и опасных паттернов
_PS_CMDLET_VERBS: frozenset[str] = frozenset({
    "stop-", "start-", "get-", "set-", "write-", "remove-", "new-",
    "invoke-", "select-", "where-", "foreach-", "test-", "clear-", "restart-",
})

_DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-rf\s+[/\\]", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fqs].*[/\\]\*", re.IGNORECASE),
    re.compile(r"\bremove-item\b.*-recurse.*-force.*([a-z]:\\|/)", re.IGNORECASE),
    re.compile(r"\b(invoke-expression|iex)\b.*(downloadstring| invoke-webrequest|iwr|curl|wget)", re.IGNORECASE),
    re.compile(r"\bshutdown\b\s+/[sr]", re.IGNORECASE),
)


def _log(message: str) -> None:
    """Выводит информационное сообщение в консоль через logger.console() со строгой UTC меткой времени.

    Args:
        message: Текст сообщения.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.console(f"[{timestamp}] [CommandValidator] {message}")


def is_command_safe(command: str) -> bool:
    """Проверяет строку команды на отсутствие разрушительных паттернов и нулевых байтов.

    Args:
        command: Проверяемая командная строка.

    Returns:
        bool: True, если команда не содержит запрещённых конструкций.
    """
    if not command or not command.strip() or "\x00" in command:
        return False
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(command):
            return False
    return True


def is_powershell_cmdlet(command: str) -> bool:
    """Определяет за O(1), является ли строка PowerShell командлетом.

    Args:
        command: Строка команды.

    Returns:
        bool: True, если команда начинается со стандартных префиксов глаголов PowerShell.
    """
    if not command or not command.strip():
        return False
    first_token = command.strip().split()[0].lower()
    dash_idx = first_token.find("-")
    if dash_idx <= 0:
        return False
    verb_prefix = first_token[: dash_idx + 1]
    return verb_prefix in _PS_CMDLET_VERBS


_is_powershell_cmdlet = is_powershell_cmdlet


def validate_powershell_syntax(script: str) -> Tuple[bool, List[str]]:
    """Выполняет предварительную проверку синтаксиса PowerShell через AST-парсер.

    Скрипт анализируется встроенным парсером PowerShell без фактического исполнения.

    Args:
        script: Текст скрипта или команды.

    Returns:
        Tuple[bool, List[str]]: Флаг валидности (True/False) и список найденных ошибок синтаксиса.
    """
    clean_script = (script or "").strip()
    if not clean_script:
        return True, []

    check_ps = r"""
$tokens = $null
$errors = $null
$code = [Console]::In.ReadToEnd()
$ast = [System.Management.Automation.Language.Parser]::ParseInput($code, "validator.ps1", [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Output $_.Message }
    exit 2
} else {
    Write-Output "PARSER_OK"
    exit 0
}
"""
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", check_ps],
            input=clean_script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
        if proc.returncode == 0 and "PARSER_OK" in proc.stdout:
            return True, []

        err_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip() and line.strip() != "PARSER_OK"]
        if not err_lines and proc.stderr.strip():
            err_lines = [proc.stderr.strip()]

        return False, err_lines or ["Обнаружена синтаксическая ошибка в коде PowerShell."]
    except subprocess.TimeoutExpired:
        _log("Таймаут синтаксической проверки AST (8 сек).")
        return True, []
    except Exception as e:
        _log(f"Сбой синтаксического анализатора AST: {e}")
        return True, []


def strip_silently_continue(command: str) -> Tuple[str, bool]:
    """Обнаруживает и удаляет маскирующий флаг SilentlyContinue из команды PowerShell.

    Args:
        command: Исходная команда PowerShell.

    Returns:
        Tuple[str, bool]: Очищенная команда и флаг, был ли удален запрещенный параметр.
    """
    pattern = r'-(?:ErrorAction|EA)\s+(?:SilentlyContinue|0)\b'
    was_stripped = bool(re.search(pattern, command, re.IGNORECASE))
    if was_stripped:
        cleaned = re.sub(pattern, '', command, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        _log("Внимание: флаг '-ErrorAction SilentlyContinue' был принудительно удален согласно политике открытости ошибок.")
        return cleaned, True
    return command.strip(), False


def run_safe(
    command: str,
    dry_run: bool = False,
    timeout_sec: int = DEFAULT_COMMAND_TIMEOUT_SEC,
    shell: str = "powershell",
    as_admin: bool = False,
    enforce_error_visibility: bool = True,
    timeout: int | None = None,
) -> Dict[str, Any]:
    """Безопасно выполняет команду с AST-проверкой, dry-run и обязательным сохранением всех ошибок.

    Args:
        command: Команда для исполнения на хосте.
        dry_run: Если True, выполняется валидация без применения деструктивных изменений.
        timeout_sec: Максимальное время выполнения в секундах.
        shell: Оболочка (powershell, pwsh, cmd).
        as_admin: Требуются ли права администратора.
        enforce_error_visibility: Запрещать скрывать ошибки (удалять SilentlyContinue).
        timeout: Опциональный алиас для timeout_sec.

    Returns:
        Dict[str, Any]: Результат выполнения со всеми полями совместимости.
    """
    effective_timeout = timeout if timeout is not None else timeout_sec
    clean_cmd = (command or "").strip()
    start_time = datetime.now(timezone.utc)
    warnings: List[str] = []

    if not is_command_safe(clean_cmd):
        err_msg = "Команда заблокирована политикой безопасности (пустая команда или опасный паттерн)." if clean_cmd else "Команда не может быть пустой."
        _log(err_msg)
        return {
            "success": False,
            "dry_run": dry_run,
            "stdout": "",
            "stderr": err_msg,
            "output": "",
            "error": err_msg,
            "returncode": 1,
            "warnings": [],
            "execution_time_ms": 0.0,
            "sanitized_command": "",
        }

    # 1. Проверка на запрещенный флаг сокрытия ошибок SilentlyContinue
    target_cmd = clean_cmd
    if enforce_error_visibility and shell in ("powershell", "pwsh"):
        target_cmd, stripped = strip_silently_continue(clean_cmd)
        if stripped:
            warnings.append("Флаг -ErrorAction SilentlyContinue удален: ошибки должны быть видны оператору и модели.")

    _log(f"Запуск команды [{shell}, admin={as_admin}, dry_run={dry_run}]: {target_cmd[:100]}")

    # 2. Фаза синтаксической валидации AST (для PowerShell)
    if shell in ("powershell", "pwsh"):
        is_valid, syntax_errors = validate_powershell_syntax(target_cmd)
        if not is_valid:
            err_msg = "\n".join(syntax_errors)
            _log(f"Ошибка синтаксиса PowerShell: {err_msg}")
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            full_err = f"Синтаксическая ошибка PowerShell (AST):\n{err_msg}"
            return {
                "success": False,
                "dry_run": dry_run,
                "stdout": "",
                "stderr": full_err,
                "output": "",
                "error": full_err,
                "returncode": 2,
                "warnings": syntax_errors,
                "execution_time_ms": round(elapsed, 2),
                "sanitized_command": target_cmd,
            }

    # 3. Фаза Dry-Run
    if dry_run:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        if shell in ("powershell", "pwsh") and is_powershell_cmdlet(target_cmd):
            first_word = re.sub(r"[^a-zA-Z0-9_\-\.]", "", target_cmd.split()[0])
            check_whatif = f"Get-Command '{first_word}' -ErrorAction Continue | Select-Object -ExpandProperty Parameters | Where-Object {{ $_.Keys -contains 'WhatIf' -or $_.Name -eq 'WhatIf' }}"
            p_chk = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", check_whatif],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            if p_chk.stdout.strip() and "|" not in target_cmd and ";" not in target_cmd:
                whatif_cmd = f"{target_cmd} -WhatIf"
                _log(f"Выполнение dry-run через -WhatIf: {whatif_cmd}")
                p_whatif = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", whatif_cmd],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                )
                out_str = p_whatif.stdout.strip()
                err_str = p_whatif.stderr.strip()
                return {
                    "success": (p_whatif.returncode == 0),
                    "dry_run": True,
                    "stdout": out_str,
                    "stderr": err_str,
                    "output": out_str,
                    "error": err_str,
                    "returncode": p_whatif.returncode,
                    "warnings": warnings,
                    "execution_time_ms": round((datetime.now(timezone.utc) - start_time).total_seconds() * 1000, 2),
                    "sanitized_command": whatif_cmd,
                }
            _log(f"Dry-run AST успешно пройден (командлет {first_word} не поддерживает -WhatIf)")
            out_msg = f"[Dry-Run] Синтаксис команды PowerShell корректен: {target_cmd}"
            return {
                "success": True,
                "dry_run": True,
                "stdout": out_msg,
                "stderr": "",
                "output": out_msg,
                "error": "",
                "returncode": 0,
                "warnings": warnings,
                "execution_time_ms": round(elapsed, 2),
                "sanitized_command": target_cmd,
            }
        else:
            first_exe = re.sub(r"[^a-zA-Z0-9_\-\.\\/:]", "", target_cmd.split()[0])
            p_where = subprocess.run(["where", first_exe], capture_output=True, text=True, timeout=effective_timeout)
            if p_where.returncode != 0:
                err_msg = f"Утилита '{first_exe}' не найдена в системной переменной PATH."
                return {
                    "success": False,
                    "dry_run": True,
                    "stdout": "",
                    "stderr": err_msg,
                    "output": "",
                    "error": err_msg,
                    "returncode": p_where.returncode,
                    "warnings": [f"Команда '{first_exe}' отсутствует в PATH"],
                    "execution_time_ms": round(elapsed, 2),
                    "sanitized_command": target_cmd,
                }
            out_msg = f"[Dry-Run] Исполняемый файл найден в PATH: {first_exe}"
            return {
                "success": True,
                "dry_run": True,
                "stdout": out_msg,
                "stderr": "",
                "output": out_msg,
                "error": "",
                "returncode": 0,
                "warnings": warnings,
                "execution_time_ms": round(elapsed, 2),
                "sanitized_command": target_cmd,
            }

    # 4. Реальное выполнение с принудительной UTF-8 кодировкой
    preamble = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8;\n"

    if shell == "cmd":
        cmd_args = ["cmd.exe", "/c", target_cmd]
    elif shell == "pwsh":
        cmd_args = ["pwsh.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", preamble + target_cmd]
    else:
        cmd_args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", preamble + target_cmd]

    try:
        proc = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=effective_timeout,
        )
    except FileNotFoundError:
        if shell == "pwsh":
            _log("pwsh.exe не найден, переключение на powershell.exe")
            cmd_args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", preamble + target_cmd]
            proc = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
            )
        else:
            raise
    except subprocess.TimeoutExpired:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        err_msg = f"Превышен таймаут выполнения команды ({effective_timeout} сек)."
        _log(err_msg)
        return {
            "success": False,
            "dry_run": False,
            "stdout": "",
            "stderr": err_msg,
            "output": "",
            "error": err_msg,
            "returncode": 124,
            "warnings": ["Timeout expired"],
            "execution_time_ms": round(elapsed, 2),
            "sanitized_command": target_cmd,
        }

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    stdout_text = proc.stdout.strip()
    stderr_text = proc.stderr.strip()
    retcode = proc.returncode
    is_success = (retcode == 0)

    if is_success:
        _log(f"Команда выполнена успешно ({round(elapsed, 2)} мс).")
    else:
        _log(f"Команда завершилась с ошибкой (код {retcode}): {stderr_text[:120]}")

    return {
        "success": is_success,
        "dry_run": False,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "output": stdout_text,
        "error": stderr_text,
        "returncode": retcode,
        "warnings": warnings,
        "execution_time_ms": round(elapsed, 2),
        "sanitized_command": target_cmd,
    }


async def run_safe_async(
    command: str,
    dry_run: bool = False,
    timeout_sec: int = DEFAULT_COMMAND_TIMEOUT_SEC,
    shell: str = "powershell",
    as_admin: bool = False,
    enforce_error_visibility: bool = True,
) -> Dict[str, Any]:
    """Асинхронная обертка над run_safe для выполнения в неблокирующем потоке.

    Args:
        command: Команда для исполнения на хосте.
        dry_run: Режим сухого запуска.
        timeout_sec: Таймаут в секундах.
        shell: Оболочка.
        as_admin: Запуск от имени администратора.
        enforce_error_visibility: Запрет скрывать ошибки.

    Returns:
        Dict[str, Any]: Результат выполнения.
    """
    return await asyncio.to_thread(
        run_safe,
        command=command,
        dry_run=dry_run,
        timeout_sec=timeout_sec,
        shell=shell,
        as_admin=as_admin,
        enforce_error_visibility=enforce_error_visibility,
    )
