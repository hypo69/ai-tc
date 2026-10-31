<#
=============================================================================
Process Name: ai-tc Launcher - Assist
=============================================================================
Description:
  Точка входа и лончер микросервиса AI Assistant (порт 8002).
  Автоматически проверяет занятость порта и принудительно освобождает его
  перед запуском, предотвращая ошибки сокета WinError 10048.

Usage Examples:
  .\assist.ps1
  .\assist.ps1 serve --port 8002

File: assist.ps1
Project: ai-tc
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-28 00:10:00
=============================================================================
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
} else {
    Write-Host "[ERROR] Не найден файл активации виртуального окружения: $venvActivate" -ForegroundColor Red
    exit 1
}

# 1. Определение целевого порта (по умолчанию 8002)
$targetPort = 8002
for ($i = 0; $i -lt $Args.Count; $i++) {
    if ($Args[$i] -eq '--port' -and ($i + 1) -lt $Args.Count) {
        $parsedPort = 0
        if ([int]::TryParse($Args[$i + 1], [ref]$parsedPort) -and $parsedPort -gt 0) {
            $targetPort = $parsedPort
        }
    }
}

# 2. Принудительное освобождение порта, если он занят
$occupiedPids = @()
try {
    $occupiedPids = Get-NetTCPConnection -LocalPort $targetPort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
} catch {}

if (-not $occupiedPids) {
    $netstatOutput = netstat -aon 2>$null | Select-String -Pattern "^\s*TCP\s+\S+:${targetPort}\s+\S+\s+LISTENING\s+(\d+)"
    foreach ($m in $netstatOutput) {
        if ($m.Matches[0].Groups[1].Value) {
            $occupiedPids += [int]$m.Matches[0].Groups[1].Value
        }
    }
    $occupiedPids = $occupiedPids | Select-Object -Unique
}

foreach ($pid_ in $occupiedPids) {
    if ($pid_ -and $pid_ -ne $PID) {
        try {
            Stop-Process -Id $pid_ -Force -ErrorAction Stop
            Write-Host "[OK] Занятый порт $targetPort успешно принудительно освобождён (PID $pid_)" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Не удалось завершить PID ${pid_}: $_" -ForegroundColor Yellow
        }
    }
}

# Ожидание освобождения сокета системой
$waitLoops = 10
while ($waitLoops -gt 0) {
    $isBusy = $false
    try {
        if (Get-NetTCPConnection -LocalPort $targetPort -State Listen -ErrorAction SilentlyContinue) {
            $isBusy = $true
        }
    } catch {}
    if (-not $isBusy) { break }
    Start-Sleep -Milliseconds 200
    $waitLoops--
}

# 3. Запуск Python‑модуля ai_assistant
$pythonExe = "python"
$modulePath = "apps.ai_assistant.__main__"
Write-Host "[INFO] Запуск Python‑модуля $modulePath на порту $targetPort" -ForegroundColor Cyan
& $pythonExe -m $modulePath @Args
