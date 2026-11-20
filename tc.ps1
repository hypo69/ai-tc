<#
=============================================================================
Process Name: ai-tc Automation - Tc Launcher
=============================================================================
Description:
  Минималистичный PowerShell-лончер для ai-tc (Test Computer).
  Активирует виртуальное окружение Python и передает все аргументы напрямую в main.py.

Usage Examples:
  .\tc.ps1
  .\tc.ps1 --engine electron
  .\tc.ps1 --browser
  .\tc.ps1 --no-browser
  .\tc.ps1 --tab tab-network

File: tc.ps1
Project: ai-tc
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 12:45:00
=============================================================================
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = $PSScriptRoot }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$env:PYTHONUTF8 = '1'

# 1. Активация виртуального окружения Python
$venvDir = Join-Path $scriptDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
    $env:VIRTUAL_ENV = $venvDir
    $venvScripts = Join-Path $venvDir "Scripts"
    if ($env:PATH -notlike "*$venvScripts*") {
        $env:PATH = "$venvScripts;$env:PATH"
    }
} else {
    $pythonExe = "python"
}

$venvActivate = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    try { . $venvActivate } catch {}
}

# 2. Делегирование запуска в main.py со всеми аргументами командной строки
$mainPath = Join-Path $scriptDir "main.py"
& $pythonExe $mainPath @Args
