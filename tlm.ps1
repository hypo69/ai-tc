<#
=============================================================================
Process Name: ai-tc Automation - Tlm
=============================================================================
Description:
  Корневая точка входа (CLI-алиас) для управления службой системной телеметрии.

  Зачем нужен этот скрипт:
    1. Удобный короткий алиас: быстрый запуск подсистемы телеметрии из корня репозитория.
    2. Прозрачное проксирование: передает любые флаги и параметры (TUI, Background, SQLite и др.)
       напрямую во внутренний диспетчер apps/windows/telemetry/launchers/Run-Telemetry.ps1.

File: tlm.ps1
Project: ai-tc
Package: root
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-28 00:10:00
=============================================================================

.SYNOPSIS
    Корневой интерфейс запуска службы системной телеметрии ai-tc.

.DESCRIPTION
    Выполняет запуск сборщика телеметрии в интерактивном, TUI или фоновом режиме.

.EXAMPLE
    .\tlm.ps1
    Запуск службы телеметрии в стандартном консольном режиме.

.EXAMPLE
    .\tlm.ps1 -TUI
    Запуск интерактивного терминального дашборда мониторинга ресурсов.

.EXAMPLE
    .\tlm.ps1 -Background
    Запуск фоновой службы сбора метрик Windows.
#>

$scriptDir = $PSScriptRoot
$targetLauncher = Join-Path $scriptDir "apps\windows\telemetry\launchers\Run-Telemetry.ps1"

if (-not (Test-Path $targetLauncher)) {
    Write-Error "Внутренний лончер телеметрии не найден по пути: $targetLauncher"
    exit 1
}

& $targetLauncher @args
