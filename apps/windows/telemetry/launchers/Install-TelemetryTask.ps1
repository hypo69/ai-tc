<#
=============================================================================
Process Name: ai-tc Automation - Install TelemetryTask
=============================================================================
Description:
  Установка, настройка и управление задачей сбора системной телеметрии (tlm.ps1)
  в Планировщике заданий Windows (Task Scheduler).
  Регистрирует задание с триггером запуска при старте компьютера (AtStartup)
  от имени администратора (NT AUTHORITY\SYSTEM / Highest Privileges).

REQUIREMENTS:
  - PowerShell 5.1 (Windows PowerShell) — ОБЯЗАТЕЛЬНО.
  - Среда, в которой НЕ установлен и НЕ поддерживается PowerShell 7 (pwsh.exe).
  - Запуск от имени Администратора.

Usage Examples:
  PowerShell 5.1 Execution (от имени Администратора):
    # Установка задачи в планировщик с запуском при старте системы:
    .\Install-TelemetryTask.ps1

    # Проверка статуса зарегистрированного задания:
    .\Install-TelemetryTask.ps1 -Status

    # Принудительный немедленный запуск задания:
    .\Install-TelemetryTask.ps1 -Start

    # Остановка выполняющегося задания:
    .\Install-TelemetryTask.ps1 -Stop

    # Удаление задания из Task Scheduler:
    .\Install-TelemetryTask.ps1 -Uninstall

File: Install-TelemetryTask.ps1
Project: ai-tc
Package: apps/windows/telemetry/launchers
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 05:00:00
=============================================================================
.SYNOPSIS
    Регистрация сценария телеметрии tlm.ps1 в Windows Task Scheduler при загрузке системы.
    Скрипт предназначен ИСКЛЮЧИТЕЛЬНО для PowerShell 5.1 (Windows PowerShell).

.DESCRIPTION
    Создает задание в Планировщике Windows с триггером AtStartup и наивысшим уровнем привилегий (Highest).
    По умолчанию настраивает запуск в контексте NT AUTHORITY\SYSTEM в скрытом окне с фоновым флагом -Background.
    
    ВНИМАНИЕ: Этот скрипт НЕ совместим с PowerShell 7 (pwsh.exe).
    Используйте только Windows PowerShell 5.1.
#>

[CmdletBinding(DefaultParameterSetName = 'Install')]
param (
    [Parameter(ParameterSetName = 'Install')]
    [Parameter(ParameterSetName = 'Uninstall')]
    [Parameter(ParameterSetName = 'Status')]
    [Parameter(ParameterSetName = 'Start')]
    [Parameter(ParameterSetName = 'Stop')]
    [string]$TaskName = 'ai-tc-telemetry',

    [Parameter(ParameterSetName = 'Install')]
    [ValidateSet('hybrid', 'minimal', 'full')]
    [string]$Mode = 'hybrid',

    [Parameter(ParameterSetName = 'Install')]
    [float]$Interval = 5.0,

    [Parameter(ParameterSetName = 'Install')]
    [float]$HeavyInterval = 60.0,

    [Parameter(ParameterSetName = 'Install')]
    [int]$TopProcesses = 10,

    [Parameter(ParameterSetName = 'Install')]
    [switch]$RunAsCurrentUser,

    [Parameter(ParameterSetName = 'Uninstall')]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = 'Status')]
    [switch]$Status,

    [Parameter(ParameterSetName = 'Start')]
    [switch]$Start,

    [Parameter(ParameterSetName = 'Stop')]
    [switch]$Stop,

    [switch]$Force,

    [Alias('h', '-help')]
    [switch]$Help
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# =============================================================================
# 0. ПРОВЕРКА ВЕРСИИ POWERSHELL (СТРОГО 5.1)
# =============================================================================
if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5) {
    Write-Error "❌ КРИТИЧЕСКАЯ ОШИБКА: Этот скрипт требует PowerShell 5.1 (Windows PowerShell)."
    Write-Error "   Текущая версия: $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition))."
    Write-Error "   PowerShell 7 (pwsh.exe) в этой среде не установлен и не поддерживается."
    exit 1
}

# =============================================================================
# 1. ПРОВЕРКА ПРАВ АДМИНИСТРАТОРА И ЭСКАЛАЦИЯ (UAC ELEVATION)
# =============================================================================
function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-AdminPrivileges {
    param ([string]$ActionDescription = "Управление заданиями планировщика")
    if (-not (Test-IsAdministrator)) {
        Write-Warning "⚠️ Для выполнения операции '$ActionDescription' требуются права Администратора."

        if ($Host.Name -notmatch "ServerRemoteHost" -and $PSCommandPath) {
            Write-Host "🔄 Перезапуск PowerShell 5.1 с правами Администратора (UAC)..." -ForegroundColor Yellow
            $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            if ($PSBoundParameters.Count -gt 0) {
                foreach ($key in $PSBoundParameters.Keys) {
                    $val = $PSBoundParameters[$key]
                    if ($val -is [System.Management.Automation.SwitchParameter]) {
                        if ($val.IsPresent) { $argList += " -$key" }
                    } else {
                        $argList += " -$key `"$val`""
                    }
                }
            }
            try {
                # Жёстко указываем powershell.exe (PS 5.1)
                Start-Process "powershell.exe" -Verb RunAs -ArgumentList $argList -Wait
                exit 0
            } catch {
                Write-Error "❌ Не удалось запросить повышение прав администратора: $_"
                exit 1
            }
        } else {
            Write-Error "❌ Пожалуйста, запустите PowerShell 5.1 от имени Администратора."
            exit 1
        }
    }
}

# =============================================================================
# 2. ОПРЕДЕЛЕНИЕ ПУТЕЙ ПРОЕКТА И СКРИПТА TLM.PS1
# =============================================================================
$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir) -and $MyInvocation.MyCommand.Path) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrEmpty($scriptDir)) {
    $scriptDir = (Get-Location).Path
}

# Поиск корня проекта
$projectRoot = $scriptDir
while ($projectRoot -and -not (Test-Path (Join-Path $projectRoot "tlm.ps1")) -and -not (Test-Path (Join-Path $projectRoot "pyproject.toml"))) {
    $parent = Split-Path -Parent $projectRoot
    if ($parent -eq $projectRoot) { break }
    $projectRoot = $parent
}
if (-not (Test-Path (Join-Path $projectRoot "tlm.ps1"))) {
    Write-Error "❌ Не удалось найти корень проекта (файл tlm.ps1 отсутствует в родительских директориях)."
    exit 1
}

$tlmScript = Join-Path $projectRoot "tlm.ps1"

# Жёстко указываем системный путь к Windows PowerShell 5.1
$powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path $powershellExe)) {
    Write-Error "❌ Системный PowerShell 5.1 не найден по пути: $powershellExe"
    exit 1
}

# =============================================================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ СТАТУСА И УПРАВЛЕНИЯ
# =============================================================================
function Get-TelemetryTask {
    param ([string]$Name)
    return (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue)
}

function Show-TelemetryTaskStatus {
    param ([string]$Name)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   📊 Планировщик заданий Windows: Статус '$Name'" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Cyan

    $task = Get-TelemetryTask -Name $Name
    if ($null -eq $task) {
        Write-Host "  • Состояние:      ❌ Задание НЕ зарегистрировано в системе" -ForegroundColor Red
        Write-Host "  • Рекомендация:   Для установки выполните: .\Install-TelemetryTask.ps1" -ForegroundColor Yellow
        Write-Host "============================================================" -ForegroundColor Cyan
        return
    }

    $info = Get-ScheduledTaskInfo -TaskName $Name -ErrorAction SilentlyContinue
    $statusColor = switch ($task.State) {
        'Running' { 'Green' }
        'Ready'   { 'Cyan' }
        'Disabled' { 'Yellow' }
        default   { 'White' }
    }

    Write-Host "  • Состояние задачи:       $($task.State)" -ForegroundColor $statusColor
    Write-Host "  • Учетная запись:         $($task.Principal.UserId)" -ForegroundColor White
    Write-Host "  • Уровень привилегий:     $($task.Principal.RunLevel)" -ForegroundColor White
    Write-Host "  • Режим входа:            $($task.Principal.LogonType)" -ForegroundColor White

    if ($task.Triggers) {
        $triggerTypes = ($task.Triggers | ForEach-Object { $_.CimClass.CimClassName -replace 'MSFT_Task','' }) -join ', '
        Write-Host "  • Триггеры запуска:       $triggerTypes" -ForegroundColor White
    }

    if ($info) {
        $lastRun = if ($info.LastRunTime -and $info.LastRunTime -ne [datetime]::MinValue) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { "Никогда" }
        $nextRun = if ($info.NextRunTime -and $info.NextRunTime -ne [datetime]::MinValue) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { "По расписанию/триггеру" }
        Write-Host "  • Последний запуск:       $lastRun (Код: $($info.LastTaskResult))" -ForegroundColor DarkGray
        Write-Host "  • Следующий запуск:       $nextRun" -ForegroundColor DarkGray
    }

    if ($task.Actions) {
        foreach ($act in $task.Actions) {
            Write-Host "  • Исполняемый файл:       $($act.Execute)" -ForegroundColor DarkGray
            Write-Host "  • Аргументы команды:      $($act.Arguments)" -ForegroundColor DarkGray
            Write-Host "  • Рабочий каталог:        $($act.WorkingDirectory)" -ForegroundColor DarkGray
        }
    }

    Write-Host "============================================================" -ForegroundColor Cyan
}

# =============================================================================
# 4. ОБРАБОТКА ДЕЙСТВИЙ (STATUS, UNINSTALL, START, STOP)
# =============================================================================
if ($Status) {
    Show-TelemetryTaskStatus -Name $TaskName
    exit 0
}

if ($Stop) {
    Assert-AdminPrivileges -ActionDescription "Остановка задания планировщика"
    $task = Get-TelemetryTask -Name $TaskName
    if (-not $task) {
        Write-Host "️ Задание '$TaskName' не найдено." -ForegroundColor Yellow
        exit 0
    }
    Write-Host "🛑 Остановка задания '$TaskName'..." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host "✅ Задание '$TaskName' остановлено." -ForegroundColor Green
    exit 0
}

if ($Start) {
    Assert-AdminPrivileges -ActionDescription "Запуск задания планировщика"
    $task = Get-TelemetryTask -Name $TaskName
    if (-not $task) {
        Write-Error "❌ Задание '$TaskName' не зарегистрировано в планировщике."
        exit 1
    }
    Write-Host "🚀 Немедленный запуск задания '$TaskName'..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 1
    Show-TelemetryTaskStatus -Name $TaskName
    exit 0
}

if ($Uninstall) {
    Assert-AdminPrivileges -ActionDescription "Удаление задания планировщика"
    $task = Get-TelemetryTask -Name $TaskName
    if ($task) {
        Write-Host "🗑️ Остановка и удаление задания '$TaskName'..." -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "✅ Задание '$TaskName' успешно удалено из Task Scheduler." -ForegroundColor Green
    } else {
        Write-Host "ℹ️ Задание '$TaskName' не найдено в планировщике." -ForegroundColor DarkGray
    }
    exit 0
}

# =============================================================================
# 5. УСТАНОВКА ЗАДАЧИ В TASK SCHEDULER (AT STARTUP / ADMIN)
# =============================================================================
Assert-AdminPrivileges -ActionDescription "Регистрация задания в Task Scheduler"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " ⚙️ Установка службы телеметрии (tlm.ps1) в Task Scheduler" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  • Задача:             $TaskName" -ForegroundColor DarkCyan
Write-Host "  • Сценарий:           $tlmScript" -ForegroundColor DarkCyan
Write-Host "  • Корень проекта:     $projectRoot" -ForegroundColor DarkCyan
Write-Host "  • Шелл выполнения:    $powershellExe (PS 5.1)" -ForegroundColor DarkCyan
Write-Host "  • Режим сбора метрик: $Mode" -ForegroundColor DarkCyan
Write-Host "  • Интервалы:          быстрый ${Interval}с | тяжелый ${HeavyInterval}с" -ForegroundColor DarkCyan
Write-Host ""

# 1. Формирование аргументов запуска (WindowStyle Hidden валиден только для PS 5.1)
$taskArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$tlmScript`" -Background -Mode $Mode -Interval $Interval -HeavyInterval $HeavyInterval -TopProcesses $TopProcesses"

# 2. Создание действия (Action)
$action = New-ScheduledTaskAction -Execute $powershellExe -Argument $taskArgs -WorkingDirectory $projectRoot

# 3. Создание триггера (Trigger: AtStartup)
$trigger = New-ScheduledTaskTrigger -AtStartup

# 4. Настройка прав (Principal)
if ($RunAsCurrentUser) {
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    Write-Host "  • Контекст безопасности: Пользователь '$currentUser' (Highest Available)" -ForegroundColor Yellow
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
} else {
    Write-Host "  • Контекст безопасности: NT AUTHORITY\SYSTEM (Наивысшие системные права / Boot)" -ForegroundColor Green
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}

# 5. Настройки задания (Settings)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -Priority 7

# 6. Регистрация задания
$existingTask = Get-TelemetryTask -Name $TaskName
if ($existingTask) {
    Write-Host "🔄 Обновление существующей задачи '$TaskName'..." -ForegroundColor Yellow
} else {
    Write-Host "➕ Создание новой задачи '$TaskName'..." -ForegroundColor Green
}

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "ai-tc Фоновый сервис системной телеметрии (запуск tlm.ps1 при старте компьютера с правами администратора)." `
        -Force | Out-Null

    Write-Host "✅ Задание '$TaskName' успешно зарегистрировано в Task Scheduler!" -ForegroundColor Green
} catch {
    Write-Error "❌ Ошибка при регистрации задания в Task Scheduler: $_"
    exit 1
}

# 7. Запуск задания для проверки
Write-Host "🚀 Немедленный запуск задания для проверки работоспособности..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2

Show-TelemetryTaskStatus -Name $TaskName