<#
=============================================================================
Process Name: ai-tc Automation - Install Tlm Task
=============================================================================
Description:
  Корневой скрипт установки службы системной телеметрии (tlm.ps1)
  в Планировщик заданий Windows (Task Scheduler) с автозапуском
  при старте компьютера от имени администратора.

File: install-tlm-task.ps1
Project: ai-tc
Package: root
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 05:00:00
=============================================================================

.SYNOPSIS
    Установка сценария tlm.ps1 в Windows Task Scheduler при старте ПК.

.DESCRIPTION
    Передает вызов в apps/windows/telemetry/launchers/Install-TelemetryTask.ps1
    с сохранением переданных параметров.

.EXAMPLE
    .\install-tlm-task.ps1
    Установка фонового задания сбора телеметрии при старте компьютера.

.EXAMPLE
    .\install-tlm-task.ps1 -Status
    Проверка статуса задания в планировщике.

.EXAMPLE
    .\install-tlm-task.ps1 -Uninstall
    Удаление задания из планировщика.
#>

$scriptDir = $PSScriptRoot
$targetLauncher = Join-Path $scriptDir "apps\windows\telemetry\launchers\Install-TelemetryTask.ps1"

if (-not (Test-Path $targetLauncher)) {
    Write-Error "Скрипт установки задачи не найден по пути: $targetLauncher"
    exit 1
}

& $targetLauncher @args
