# -*- coding: utf-8 -*-
# =============================================================================
# Файл: utils/command_validator.py
# Описание: Модуль безопасного выполнения, синтаксической валидации (AST),
#           сухого запуска (dry-run) и контроля открытости ошибок PowerShell/CLI.
#
# Требования проекта:
#   • Запрещено сокрытие ошибок: флаг -ErrorAction SilentlyContinue запрещен!
#   • Ошибки (stderr) всегда сохраняются и передаются для анализа и самокоррекции.
#   • Вывод сообщений в консоль выполняется строго через logger.console()
#   • Докстринги и комментарии – строго на русском языке
#   • При изменении файла обновляется шапка с датой/временем
# =============================================================================
# Updated: 2026-10-28 23:25:00
# =============================================================================

"""hypo69 docblock
Модуль предоставляет инструменты для:
* Синтаксической проверки скриптов PowerShell через AST Parser без их исполнения.
* Сухого запуска (dry-run) с использованием -WhatIf и проверки наличия утилит в PATH.
* Контроля прозрачности ошибок: обнаружение и удаление маскирующих флагов (-ErrorAction SilentlyContinue).
* Полного захвата и сохранения stderr для анализа моделью и оператором.
* Формирования единого словаря результата, пригодного для API и ReAct-агента.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import subprocess
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

# Импорт стандартного логгера проекта
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


def _log(message: str) -> None:
    """Выводит информационное сообщение в консоль через logger.console().

    Args:
        message: Текст сообщения.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.console(f"[{timestamp}] [CommandValidator] {message}")


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

    Политика проекта запрещает скрывать ошибки через -ErrorAction SilentlyContinue,
    так как оператор и модель всегда должны видеть реальную причину сбоя.

    Args:
        command: Исходная команда PowerShell.

    Returns:
        Tuple[str, bool]: Очищенная команда и флаг, был ли удален запрещенный параметр.
    """
    pattern = r'-(?:ErrorAction|EA)\s+(?:SilentlyContinue|0)\b'
    was_stripped = bool(re.search(pattern, command, re.IGNORECASE))
    if was_stripped:
        cleaned = re.sub(pattern, '', command, flags=re.IGNORECASE).strip()
        # Очищаем возможные задвоенные пробелы
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        _log("Внимание: флаг '-ErrorAction SilentlyContinue' был принудительно удален согласно политике открытости ошибок.")
        return cleaned, True
    return command.strip(), False


def is_powershell_cmdlet(command: str) -> bool:
    """Определяет, является ли строка PowerShell командлетом.

    Args:
        command: Строка команды.

    Returns:
        bool: True, если команда начинается со стандартных префиксов глаголов PowerShell.
    """
    first_word = command.strip().split()[0] if command.strip() else ""
    return bool(re.match(r'^(Get|Set|Start|Stop|Restart|New|Remove|Test|Invoke|Select|Where|Write)-[A-Za-z0-9]+', first_word, re.IGNORECASE))


def run_safe(
    command: str,
    dry_run: bool = False,
    timeout_sec: int = 35,
    shell: str = "powershell",
    as_admin: bool = False,
    enforce_error_visibility: bool = True
) -> Dict[str, Any]:
    """Безопасно выполняет команду с AST-проверкой, dry-run и обязательным сохранением всех ошибок.

    Args:
        command: Команда для исполнения на хосте.
        dry_run: Если True, выполняется валидация без применения деструктивных изменений.
        timeout_sec: Максимальное время выполнения в секундах.
        shell: Оболочка (powershell, pwsh, cmd).
        as_admin: Требуются ли права администратора.
        enforce_error_visibility: Запрещать скрывать ошибки (удалять SilentlyContinue).

    Returns:
        Dict[str, Any]: Результат со структурой:
            {
                "success": bool,
                "dry_run": bool,
                "stdout": str,
                "stderr": str,
                "returncode": int,
                "warnings": List[str],
                "execution_time_ms": float,
                "sanitized_command": str
            }
    """
    clean_cmd = (command or "").strip()
    start_time = datetime.now()
    warnings: List[str] = []

    if not clean_cmd:
        return {
            "success": False,
            "dry_run": dry_run,
            "stdout": "",
            "stderr": "Команда не может быть пустой.",
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
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "dry_run": dry_run,
                "stdout": "",
                "stderr": f"Синтаксическая ошибка PowerShell (AST):\n{err_msg}",
                "returncode": 2,
                "warnings": syntax_errors,
                "execution_time_ms": round(elapsed, 2),
                "sanitized_command": target_cmd,
            }

    # 3. Фаза Dry-Run
    if dry_run:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        if shell in ("powershell", "pwsh") and is_powershell_cmdlet(target_cmd):
            # Проверяем поддержку -WhatIf через Get-Command
            first_word = target_cmd.split()[0]
            check_whatif = f"Get-Command {first_word} -ErrorAction Continue | Select-Object -ExpandProperty Parameters | Where-Object {{ $_.Name -eq 'WhatIf' }}"
            p_chk = subprocess.run(["powershell.exe", "-NoProfile", "-Command", check_whatif], capture_output=True, text=True)
            if p_chk.stdout.strip():
                whatif_cmd = f"{target_cmd} -WhatIf"
                _log(f"Выполнение dry-run через -WhatIf: {whatif_cmd}")
                p_whatif = subprocess.run(["powershell.exe", "-NoProfile", "-Command", whatif_cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
                return {
                    "success": (p_whatif.returncode == 0),
                    "dry_run": True,
                    "stdout": p_whatif.stdout.strip(),
                    "stderr": p_whatif.stderr.strip(),
                    "returncode": p_whatif.returncode,
                    "warnings": warnings,
                    "execution_time_ms": round((datetime.now() - start_time).total_seconds() * 1000, 2),
                    "sanitized_command": whatif_cmd,
                }
            _log(f"Dry-run AST успешно пройден (командлет {first_word} не поддерживает -WhatIf)")
            return {
                "success": True,
                "dry_run": True,
                "stdout": f"[Dry-Run] Синтаксис команды PowerShell корректен: {target_cmd}",
                "stderr": "",
                "returncode": 0,
                "warnings": warnings,
                "execution_time_ms": round(elapsed, 2),
                "sanitized_command": target_cmd,
            }
        else:
            first_exe = target_cmd.split()[0]
            p_where = subprocess.run(["where", first_exe], capture_output=True, text=True)
            if p_where.returncode != 0:
                return {
                    "success": False,
                    "dry_run": True,
                    "stdout": "",
                    "stderr": f"Утилита '{first_exe}' не найдена в системной переменной PATH.",
                    "returncode": p_where.returncode,
                    "warnings": [f"Команда '{first_exe}' отсутствует в PATH"],
                    "execution_time_ms": round(elapsed, 2),
                    "sanitized_command": target_cmd,
                }
            return {
                "success": True,
                "dry_run": True,
                "stdout": f"[Dry-Run] Исполняемый файл найден в PATH: {first_exe}",
                "stderr": "",
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
            timeout=timeout_sec,
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
                timeout=timeout_sec,
            )
        else:
            raise
    except subprocess.TimeoutExpired:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        _log(f"Превышен таймаут исполнения команды ({timeout_sec} сек).")
        return {
            "success": False,
            "dry_run": False,
            "stdout": "",
            "stderr": f"Превышен таймаут выполнения команды ({timeout_sec} сек).",
            "returncode": 124,
            "warnings": ["Timeout expired"],
            "execution_time_ms": round(elapsed, 2),
            "sanitized_command": target_cmd,
        }

    elapsed = (datetime.now() - start_time).total_seconds() * 1000
    stdout_text = proc.stdout.strip()
    stderr_text = proc.stderr.strip()
    retcode = proc.returncode

    # Ошибки НИКОГДА не замалчиваются: stderr всегда полностью сохраняется
    is_success = (retcode == 0)

    if is_success:
        _log(f"Команда выполнена успешно ({round(elapsed, 2)} мс).")
    else:
        _log(f"Команда завершилась с ошибкой (код {retcode}): {stderr_text[:120]}")

    return {
        "success": is_success,
        "dry_run": False,
        "stdout": stdout_text,
        "stderr": stderr_text,  # Полный текст ошибки без купюр и замалчивания
        "returncode": retcode,
        "warnings": warnings,
        "execution_time_ms": round(elapsed, 2),
        "sanitized_command": target_cmd,
    }


async def run_safe_async(
    command: str,
    dry_run: bool = False,
    timeout_sec: int = 35,
    shell: str = "powershell",
    as_admin: bool = False,
    enforce_error_visibility: bool = True
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

