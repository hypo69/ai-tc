"""
=============================================================================
Модуль тестирования: Механизм самопроверки и прозрачности ошибок (command_validator)
=============================================================================
Описание:
  Проверка функций модуля utils/command_validator.py:
  - Синтаксическая валидация через PowerShell AST Parser (validate_powershell_syntax).
  - Запрет сокрытия ошибок: обнаружение и удаление -ErrorAction SilentlyContinue (strip_silently_continue).
  - Прозрачность ошибок: обязательное сохранение stderr без замалчивания.
  - Поддержка чистой кодировки UTF-8.

Файл: tests/test_command_validator.py
Автор: hypo69
Updated: 2026-10-28 23:25:00
=============================================================================
"""

import pytest
from utils.command_validator import (
    validate_powershell_syntax,
    strip_silently_continue,
    run_safe,
    is_powershell_cmdlet,
)


def test_validate_powershell_syntax_valid():
    """Проверяет валидный синтаксис PowerShell через AST парсер."""
    is_valid, errs = validate_powershell_syntax("Get-Service -Name hns | Select-Object Name, Status")
    assert is_valid is True
    assert len(errs) == 0


def test_validate_powershell_syntax_invalid():
    """Проверяет обнаружение синтаксической ошибки (незакрытая скобка)."""
    is_valid, errs = validate_powershell_syntax("Get-Service -Name (hns | Select-Object")
    assert is_valid is False
    assert len(errs) > 0


def test_strip_silently_continue():
    """Проверяет принудительное удаление запрещенного флага сокрытия ошибок SilentlyContinue."""
    cmd_with_ea = "Get-Service -Name vmnet -ErrorAction SilentlyContinue | Select-Object Name"
    cleaned, stripped = strip_silently_continue(cmd_with_ea)
    assert stripped is True
    assert "SilentlyContinue" not in cleaned
    assert cleaned == "Get-Service -Name vmnet | Select-Object Name"

    # Проверка сокращенного варианта -EA 0
    cmd_short = "Get-Process -EA 0"
    cleaned_short, stripped_short = strip_silently_continue(cmd_short)
    assert stripped_short is True
    assert "-EA 0" not in cleaned_short


def test_is_powershell_cmdlet():
    """Проверяет определение командлетов PowerShell."""
    assert is_powershell_cmdlet("Get-Service hns") is True
    assert is_powershell_cmdlet("Stop-Process -Name explorer") is True
    assert is_powershell_cmdlet("cmd.exe /c dir") is False
    assert is_powershell_cmdlet("ping 127.0.0.1") is False


def test_run_safe_dry_run():
    """Проверяет сухой запуск команды без реального выполнения."""
    res = run_safe("Get-Service -Name hns", dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["returncode"] == 0


def test_run_safe_preserves_error_visibility_and_utf8():
    """
    Проверяет сценарий пользователя: запрос списка служб, где часть не существует (vmnet, vmsvichext).
    Ошибки не должны замалчиваться: stderr обязательно содержит текст ошибки, а кодировка UTF-8 чистая.
    """
    cmd = "Get-Service -Name vmnet, vmsvichext, hns | Select-Object Name, DisplayName, Status, StartType"
    res = run_safe(cmd, dry_run=False, enforce_error_visibility=True)

    # Ошибка должна быть честно видна в stderr
    assert res["stderr"] != ""
    assert "Cannot find any service" in res["stderr"] or "vmnet" in res["stderr"]
    # Служба hns должна быть в stdout
    assert "hns" in res["stdout"]
    # Проверяем отсутствие битой OEM-кодировки
    assert "╨" not in res["stdout"]
    assert "╤" not in res["stdout"]

