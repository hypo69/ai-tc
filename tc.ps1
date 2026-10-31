<#
=============================================================================
Process Name: ai-tc Automation - Tc Launcher
=============================================================================
Description:
  Сценарий запуска Test Computer (TC).
  По умолчанию запуск Cloudflare Tunnel и SSL отключен.
  Стартовый интерфейс открывает вкладку #tab-about-system.
  Делегирует старт сервера и интерфейса файлу main.py.

Usage Examples:
  .\tc.ps1
  .\tc.ps1 -NoBrowser
  .\tc.ps1 -WithCloudflare
  .\tc.ps1 -SSL

File: tc.ps1
Project: ai-tc
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 15:50:00
=============================================================================
#>

[CmdletBinding()]
param (
    [switch]$WithCloudflare,
    [switch]$Cloudflare,
    [switch]$NoCloudflare,
    [switch]$RestartCloudflare,
    [switch]$SSL,
    [switch]$UseSSL,
    [Alias('PanelId', 'SubTab', 'SubPanel')]
    [string]$Panel,
    [Alias('TabId')]
    [string]$Tab,
    [string]$PublicUrl = "https://kino.davidka.net",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Корневая директория проекта
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ([string]::IsNullOrEmpty($scriptDir)) {
    $scriptDir = $PSScriptRoot
}
if ([string]::IsNullOrEmpty($scriptDir)) {
    $scriptDir = (Get-Location).Path
}

# =============================================================================
# 1. КОНТРОЛЬ И ПОДКЛЮЧЕНИЕ CLOUDFLARE TUNNEL (kino.davidka.net)
# =============================================================================
$shouldStartCloudflare = ($WithCloudflare -or $Cloudflare -or $RestartCloudflare) -and (-not $NoCloudflare)

if ($shouldStartCloudflare) {
    $cfLauncher = Join-Path $scriptDir "launchers\Run-Cloudflared.ps1"
    $runningCf = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'cloudflared.exe' }

    if ($RestartCloudflare -or -not $runningCf) {
        if (Test-Path $cfLauncher) {
            Write-Host "  [☁️ Cloudflare] Запуск туннеля для $PublicUrl..." -ForegroundColor Cyan
            try {
                & $cfLauncher
            } catch {
                Write-Host "  [WARN] Ошибка запуска Cloudflare Tunnel: $_" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [WARN] Скрипт launchers\Run-Cloudflared.ps1 не найден." -ForegroundColor Yellow
        }
    } else {
        $cfPids = ($runningCf | ForEach-Object { $_.ProcessId }) -join ', '
        Write-Host "  [☁️ Cloudflare] Туннель активен (PID: $cfPids) -> $PublicUrl" -ForegroundColor Green
    }
} else {
    Write-Host "  [☁️ Cloudflare] Запуск туннеля отключен" -ForegroundColor DarkGray
}

# =============================================================================
# 2. МАРШРУТИЗАЦИЯ ВКЛАДКИ И ПАНЕЛИ
# =============================================================================
$t_ = if ($Tab) { $Tab.Trim().Trim('#') } else { "tab-about-system" }
if ($t_ -eq "tab-process-manager") {
    $t_ = "tab-processes-load-inspector"
}
$targetTab = if ($Panel) {
    $cleanPanel = $Panel.Trim().Trim('#')
    "${t_}#${cleanPanel}"
} else {
    $t_
}

# =============================================================================
# 3. ОПРЕДЕЛЕНИЕ ИНТЕРПРЕТАТОРА PYTHON И ЗАПУСК MAIN.PY
# =============================================================================
$mainPath = Join-Path $scriptDir "main.py"
if (-not (Test-Path $mainPath)) {
    Write-Error "Файл main.py не найден по пути $mainPath"
    exit 1
}

$venvPython = Join-Path $scriptDir "venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

# Формирование аргументов запуска
$runArgs = @()
if ($SSL -or $UseSSL) {
    $runArgs += "--ssl"
} else {
    $runArgs += "--no-ssl"
}

if ($ForwardArgs -and $ForwardArgs.Count -gt 0) {
    $runArgs += $ForwardArgs
}

# Запуск main.py с передачей аргументов
& $pythonExe $mainPath @runArgs

