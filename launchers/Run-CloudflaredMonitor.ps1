<#
.SYNOPSIS
    Лаунчер микросервиса / дашборда Cloudflared Monitor.

.DESCRIPTION
    Запускает apps.cloudflared_monitor в фоновом режиме или в отдельном окне.
    По умолчанию слушает порт 8104.

.PARAMETER Action
    Действие: 'start' (по умолчанию), 'stop', 'restart', 'status'.

.PARAMETER Mode
    Режим: 'server' (FastAPI микросервис) или 'dashboard' (TUI).

.PARAMETER Port
    TCP порт сервера (по умолчанию: 8104).

.PARAMETER HostAddress
    Сетевой адрес (по умолчанию: 127.0.0.1).

.PARAMETER Foreground
    Запуск непосредственно в текущем терминале.

.PARAMETER NewWindow
    Запуск в отдельном окне консоли.
#>

[CmdletBinding()]
param (
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'start',

    [ValidateSet('server', 'dashboard')]
    [string]$Mode = 'server',

    [int]$Port = 8104,

    [Alias('Host', 'Address', 'IP')]
    [string]$HostAddress = '127.0.0.1',

    [Alias('f', 'Interactive', 'Console')]
    [switch]$Foreground,

    [Alias('Window', 'SeparateWindow')]
    [switch]$NewWindow,

    [Alias('h', '-help')]
    [switch]$Help
)

$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir) -and $env:AIBREADBOARD_DIR -and (Test-Path $env:AIBREADBOARD_DIR)) {
    $scriptDir = $env:AIBREADBOARD_DIR
}
if ([string]::IsNullOrEmpty($scriptDir) -and $MyInvocation.MyCommand.Path) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrEmpty($scriptDir)) {
    $scriptDir = (Get-Location).Path
}

$projectRoot = $scriptDir
if ((Split-Path -Leaf $projectRoot) -eq "launchers" -or -not (Test-Path (Join-Path $projectRoot "main.py"))) {
    $parent = Split-Path -Parent $projectRoot
    if (Test-Path (Join-Path $parent "main.py")) {
        $projectRoot = $parent
    }
}
$env:AIBREADBOARD_DIR = $projectRoot
$env:ASSIST_DIR = $projectRoot

if ($Help) {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║       Run-CloudflaredMonitor.ps1 — СПРАВКА И ПАРАМЕТРЫ        ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Параметры:" -ForegroundColor Yellow
    Write-Host "  .\launchers\Run-CloudflaredMonitor.ps1 [-Action start|stop|restart|status] [-Mode server|dashboard] [-NewWindow]"
    Write-Host ""
    exit 0
}

$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $venvPython) {
        $venvPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
}

function Get-AppProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'apps\.cloudflared_monitor'
    }
}

$runningProcs = Get-AppProcesses

if ($Action -eq 'status') {
    if ($runningProcs) {
        $pids = ($runningProcs | ForEach-Object { $_.ProcessId }) -join ', '
        Write-Host "✅ Cloudflared Monitor запущен (PID: $pids, Port: $Port)" -ForegroundColor Green
    } else {
        Write-Host "❌ Cloudflared Monitor не запущен." -ForegroundColor Yellow
    }
    exit 0
}

if ($Action -in @('stop', 'restart')) {
    if ($runningProcs) {
        Write-Host "🛑 Остановка Cloudflared Monitor..." -ForegroundColor Yellow
        $runningProcs | ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "    [OK] Остановлен PID $($_.ProcessId)" -ForegroundColor DarkGray
            } catch {}
        }
        Start-Sleep -Seconds 1
    } else {
        Write-Host "ℹ️ Cloudflared Monitor не был запущен." -ForegroundColor DarkGray
    }
    if ($Action -eq 'stop') {
        exit 0
    }
}

if ($Action -in @('start', 'restart')) {
    $existing = Get-AppProcesses
    if ($existing) {
        $pids = ($existing | ForEach-Object { $_.ProcessId }) -join ', '
        Write-Host "✅ Cloudflared Monitor уже запущен (PID: $pids)" -ForegroundColor Green
        exit 0
    }

    $appArgs = "-m apps.cloudflared_monitor --mode $Mode --host $HostAddress --port $Port"

    if ($Foreground) {
        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "  ☁️ CLOUDFLARED MONITOR ЗАПУЩЕН (ИНТЕРАКТИВНЫЙ РЕЖИМ)          " -ForegroundColor Green
        Write-Host "  Адрес:  http://${HostAddress}:${Port}                         " -ForegroundColor DarkGray
        Write-Host "  Python: $venvPython                                           " -ForegroundColor DarkGray
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
        Push-Location $projectRoot
        & $venvPython -m apps.cloudflared_monitor --mode $Mode --host $HostAddress --port $Port
        Pop-Location
        exit $LASTEXITCODE
    }

    if ($NewWindow) {
        Write-Host "    Запуск Cloudflared Monitor в отдельном окне..." -ForegroundColor Cyan
        $hasWt = Get-Command wt.exe -ErrorAction SilentlyContinue
        $hasPwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
        $shellExe = if ($hasPwsh) { "pwsh.exe" } else { "powershell.exe" }
        $thisScript = $MyInvocation.MyCommand.Path
        if (-not $thisScript) {
            $thisScript = Join-Path $projectRoot "launchers\Run-CloudflaredMonitor.ps1"
        }

        if ($hasWt) {
            $proc = Start-Process wt.exe -ArgumentList "-d `"$projectRoot`" --title `"Cloudflared Monitor ($Port)`" $shellExe -NoExit -ExecutionPolicy Bypass -File `"$thisScript`" -Mode $Mode -HostAddress $HostAddress -Port $Port -Foreground" -PassThru
        } else {
            $proc = Start-Process $shellExe -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$thisScript`" -Mode $Mode -HostAddress $HostAddress -Port $Port -Foreground" -WorkingDirectory $projectRoot -PassThru
        }
    } else {
        $logsDir = Join-Path $projectRoot "logs"
        if (-not (Test-Path $logsDir)) {
            New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        }
        $logOutPath = Join-Path $logsDir "cloudflared_monitor.log"
        $logErrPath = Join-Path $logsDir "cloudflared_monitor_stderr.log"

        Write-Host "    Запуск Cloudflared Monitor в фоновом режиме..." -ForegroundColor Cyan
        $proc = Start-Process $venvPython -ArgumentList "$appArgs" -WorkingDirectory $projectRoot -PassThru -WindowStyle Minimized -RedirectStandardOutput $logOutPath -RedirectStandardError $logErrPath
    }

    if ($proc) {
        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "  ✅ CLOUDFLARED MONITOR УСПЕШНО ЗАПУЩЕН!                        " -ForegroundColor Green
        Write-Host "  Адрес:  http://${HostAddress}:${Port}                         " -ForegroundColor Green
        Write-Host "  Режим:  $Mode                                                 " -ForegroundColor DarkGray
        Write-Host "  PID:    $($proc.Id)                                           " -ForegroundColor DarkGray
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "[ERROR] Не удалось запустить процесс Cloudflared Monitor." -ForegroundColor Red
        exit 1
    }
}
