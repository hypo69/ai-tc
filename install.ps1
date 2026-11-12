<#
=============================================================================
Process Name: AI-Windows-Admin (AI-TC) - Master Installer Script
=============================================================================
Description:
  Главный скрипт автоматической установки, настройки окружения и верификации
  платформы AI Windows Admin (AI-TC) для Windows.
  Поддерживает как локальный запуск из клонированного репозитория, так и
  однострочный запуск через интернет (irm ... | iex) с автоматическим
  скачиванием Git, клонированием репозитория, созданием venv и проверкой.

Usage Examples:
  Local Execution:
    .\install.ps1
    .\install.ps1 -Profile core
    .\install.ps1 -InstallPortableGemini -UseAiAssistant

  One-Line Remote Execution:
    irm https://raw.githubusercontent.com/hypo69/AI-TC/master/install.ps1 | iex

File: install.ps1
Project: ai-windows-admin
Package: root
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 12:40:00
=============================================================================
.SYNOPSIS
    Установщик платформы AI Windows Admin (AI-TC).
.DESCRIPTION
    Выполняет полный цикл развертывания согласно INSTALL-INSTRUCTION.md:
    проверка/установка Git и Python, клонирование репозитория (при удаленном запуске),
    разблокировка скриптов, старт телеметрии (tlm.ps1), создание venv,
    установка зависимостей, инициализация .env и финальная верификация.
#>

[CmdletBinding()]
param(
    [Parameter(HelpMessage = "Целевая директория установки (используется при запуске вне репозитория)")]
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "AI-TC"),

    [Parameter(HelpMessage = "Профиль зависимостей: full, core, ai, light, test")]
    [ValidateSet("full", "core", "ai", "light", "test")]
    [string]$Profile = "full",

    [Parameter(HelpMessage = "Пропустить запуск фоновой службы телеметрии tlm.ps1")]
    [switch]$SkipTelemetry,

    [Parameter(HelpMessage = "Установить портативный Node.js и Gemini CLI (AI-Portable)")]
    [switch]$InstallPortableGemini,

    [Parameter(HelpMessage = "Запустить интерактивный ИИ-ассистент установки через Gemini CLI")]
    [switch]$UseAiAssistant
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$RepoUrl = "https://github.com/hypo69/AI-TC.git"

function Write-Step {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "`n=========================================================" -ForegroundColor DarkCyan
    Write-Host "==> $Message" -ForegroundColor Cyan
    Write-Host "=========================================================" -ForegroundColor DarkCyan
}

function Write-Ok {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Refresh-SessionPath {
    <#
    .SYNOPSIS
        Обновляет переменную PATH текущей сессии PowerShell из реестра Windows.
    #>
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Ensure-GitInstalled {
    <#
    .SYNOPSIS
        Проверяет наличие Git и автоматически скачивает/устанавливает его при отсутствии.
    #>
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $gitVer = (& git --version) 2>&1
        Write-Ok "Git уже установлен: $gitVer"
        return
    }

    Write-Step "Git не найден. Автоматическое скачивание и установка Git..."

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Установка Git через winget..." -ForegroundColor Gray
        & winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent
    }
    else {
        Write-Host "Загрузка установщика Git for Windows с GitHub Releases..." -ForegroundColor Gray
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/git-for-windows/git/releases/latest" -TimeoutSec 60
        $asset = $release.assets | Where-Object { $_.name -match "^Git-.*-64-bit\.exe$" } | Select-Object -First 1
        if (-not $asset) {
            throw "Не удалось найти 64-битный установщик Git на GitHub Releases."
        }
        $installerPath = Join-Path $env:TEMP $asset.name
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $installerPath
        Write-Host "Запуск тихой установки Git..." -ForegroundColor Gray
        Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP-" -Wait
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    }

    Refresh-SessionPath

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        $defaultGitCmd = "C:\Program Files\Git\cmd"
        if (Test-Path $defaultGitCmd) {
            $env:Path += ";$defaultGitCmd"
        }
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Не удалось автоматически установить Git. Установите Git вручную с https://git-scm.com/ и повторите запуск."
    }

    Write-Ok "Git успешно установлен: $(& git --version)"
}

function Resolve-PythonCommand {
    <#
    .SYNOPSIS
        Находит рабочий интерпретатор Python 3.10+ (исключая заглушки Microsoft Store).
    #>
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("-3.14", "-3.13", "-3.12", "-3.11", "-3.10", "-3")) {
            try {
                $check = & py $ver -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $check) {
                    return @("py", $ver)
                }
            }
            catch {}
        }
    }

    foreach ($cmd in @("python", "python3")) {
        $cmdInfo = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($cmdInfo -and ($cmdInfo.Source -notmatch "WindowsApps")) {
            try {
                $check = & $cmdInfo.Source -c "import sys; assert sys.version_info >= (3, 10); print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $check) {
                    return @($cmdInfo.Source)
                }
            }
            catch {}
        }
    }

    return $null
}

# ---------------------------------------------------------------------------
# 1. Определение рабочей директории и клонирование репозитория при необходимости
# ---------------------------------------------------------------------------
Write-Step "Этап 0: Подготовка репозитория и окружения AI Windows Admin (AI-TC)"

$CandidateRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$IsInsideRepo = (Test-Path (Join-Path $CandidateRoot "header.py")) -and (Test-Path (Join-Path $CandidateRoot "config.json"))

if ($IsInsideRepo) {
    $ProjectRoot = $CandidateRoot
    Write-Ok "Запуск выполнен из существующего каталога проекта: $ProjectRoot"
}
else {
    Ensure-GitInstalled
    $ProjectRoot = [IO.Path]::GetFullPath($InstallDir)

    if (-not (Test-Path (Join-Path $ProjectRoot ".git"))) {
        Write-Host "Клонирование репозитория $RepoUrl в $ProjectRoot ..." -ForegroundColor Cyan
        & git clone $RepoUrl $ProjectRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Ошибка при клонировании репозитория из $RepoUrl"
        }
    }
    else {
        Write-Ok "Репозиторий уже существует в $ProjectRoot. Обновление (git pull)..."
        Push-Location $ProjectRoot
        & git pull --ff-only
        Pop-Location
    }
}

Set-Location $ProjectRoot

# Разблокировка файлов PowerShell и CMD после скачивания из интернета
Get-ChildItem -Path $ProjectRoot -Recurse -File -Include "*.ps1", "*.cmd" -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue
Write-Ok "Скрипты проекта разблокированы (Unblock-File)."

# ---------------------------------------------------------------------------
# 2. Первоочередной запуск фоновой службы телеметрии (tlm.ps1)
# ---------------------------------------------------------------------------
if (-not $SkipTelemetry) {
    $TlmScript = Join-Path $ProjectRoot "tlm.ps1"
    if (Test-Path $TlmScript) {
        Write-Step "Запуск фоновой службы телеметрии (tlm.ps1)"
        try {
            Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$TlmScript`"" -WindowStyle Hidden
            Write-Ok "Фоновый сборщик телеметрии (tlm.ps1) запущен."
        }
        catch {
            Write-Warn "Не удалось запустить tlm.ps1 в фоновом режиме: $($_.Exception.Message)"
        }
    }
}

# ---------------------------------------------------------------------------
# 3. Проверка интерпретатора Python (Pre-Flight Check)
# ---------------------------------------------------------------------------
Write-Step "Этап 1: Проверка интерпретатора Python (3.10 – 3.14)"

Ensure-GitInstalled
$PyCmd = Resolve-PythonCommand

if (-not $PyCmd) {
    Write-Warn "Интерпретатор Python 3.10+ не обнаружен."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Попытка автоматической установки Python 3.12 через winget..." -ForegroundColor Cyan
        & winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements --silent
        Refresh-SessionPath
        $PyCmd = Resolve-PythonCommand
    }
}

if (-not $PyCmd) {
    throw "Python 3.10–3.14 не найден. Установите Python с https://www.python.org/downloads/ (отметив 'Add python.exe to PATH') и перезапустите install.ps1."
}

$PyExe = $PyCmd[0]
$PyArgs = if ($PyCmd.Count -gt 1) { $PyCmd[1..($PyCmd.Count - 1)] } else { @() }
$PyVerOutput = & $PyExe @PyArgs --version
Write-Ok "Используется интерпретатор: $PyVerOutput ($($PyCmd -join ' '))"

# ---------------------------------------------------------------------------
# 4. Создание виртуального окружения (venv) и установка зависимостей
# ---------------------------------------------------------------------------
Write-Step "Этап 2: Создание виртуального окружения (venv) и установка пакетов"

$VenvDir = Join-Path $ProjectRoot "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Создание виртуального окружения в $VenvDir ..." -ForegroundColor Gray
    & $PyExe @PyArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        throw "Не удалось создать виртуальное окружение Python в $VenvDir"
    }
    Write-Ok "Виртуальное окружение venv успешно создано."
}
else {
    Write-Ok "Виртуальное окружение venv уже существует."
}

Write-Host "Обновление pip, setuptools и wheel..." -ForegroundColor Gray
& $VenvPython -m pip install --upgrade pip setuptools wheel --quiet
Write-Ok "Базовые инструменты упаковки обновлены."

$ReqFile = switch ($Profile) {
    "full"  { Join-Path $ProjectRoot "requirements.txt" }
    "core"  { Join-Path $ProjectRoot "install\req\requirements-core.txt" }
    "ai"    { Join-Path $ProjectRoot "install\req\requirements-ai.txt" }
    "light" { Join-Path $ProjectRoot "install\req\requirements-light.txt" }
    "test"  { Join-Path $ProjectRoot "install\req\requirements-test.txt" }
}

if (-not (Test-Path $ReqFile)) {
    throw "Файл зависимостей не найден: $ReqFile"
}

Write-Host "Установка зависимостей профиля '$Profile' из $ReqFile ..." -ForegroundColor Cyan
& $VenvPip install -r $ReqFile
if ($LASTEXITCODE -ne 0) {
    throw "Ошибка при установке зависимостей из $ReqFile"
}
Write-Ok "Зависимости профиля '$Profile' успешно установлены."

# ---------------------------------------------------------------------------
# 5. Настройка файла секретов (.env) и SSL-сертификатов
# ---------------------------------------------------------------------------
Write-Step "Этап 3: Настройка конфигурации (.env) и локальных SSL-сертификатов"

$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item -Path $EnvExample -Destination $EnvFile -Force
        Write-Ok "Создан файл .env из шаблона .env.example."

        # Автоматическая генерация случайного JWT_SECRET, если он не задан
        try {
            $jwtSecret = & $VenvPython -c "import secrets; print(secrets.token_urlsafe(48))"
            if ($LASTEXITCODE -eq 0 -and $jwtSecret) {
                $envContent = Get-Content -Path $EnvFile -Raw -Encoding UTF8
                if ($envContent -match "JWT_SECRET=change_me") {
                    $envContent = $envContent -replace "JWT_SECRET=change_me[^\r\n]*", "JWT_SECRET=$jwtSecret"
                    Set-Content -Path $EnvFile -Value $envContent -Encoding UTF8
                    Write-Ok "Сгенерирован криптостойкий JWT_SECRET в .env."
                }
            }
        }
        catch {
            Write-Warn "Не удалось автоматически обновить JWT_SECRET в .env: $($_.Exception.Message)"
        }
    }
    else {
        Write-Warn "Шаблон .env.example не найден. Создайте файл .env вручную."
    }
}
else {
    Write-Ok "Файл секретов .env уже существует."
}

$SslGenerator = Join-Path $ProjectRoot "scripts\maintenance\generate_ssl_certs.py"
if (Test-Path $SslGenerator) {
    Write-Host "Проверка и генерация локальных SSL-сертификатов..." -ForegroundColor Gray
    try {
        & $VenvPython $SslGenerator
    }
    catch {
        Write-Warn "Генерация SSL-сертификатов пропущена: $($_.Exception.Message)"
    }
}

# Регистрация переменных среды пользователя для быстрого доступа
[System.Environment]::SetEnvironmentVariable("AITC_DIR", $ProjectRoot, "User")
[System.Environment]::SetEnvironmentVariable("AIWINDOWSADMIN_DIR", $ProjectRoot, "User")
$env:AITC_DIR = $ProjectRoot
$env:AIWINDOWSADMIN_DIR = $ProjectRoot
Write-Ok "Переменные среды AITC_DIR и AIWINDOWSADMIN_DIR зарегистрированы ($ProjectRoot)."

# ---------------------------------------------------------------------------
# 6. Опциональная установка Portable Gemini CLI
# ---------------------------------------------------------------------------
if ($InstallPortableGemini) {
    $PortableScript = Join-Path $ProjectRoot "Install-GeminiCli-Portable.ps1"
    if (Test-Path $PortableScript) {
        Write-Step "Установка портативного Node.js и Gemini CLI (AI-Portable)"
        & $PortableScript -Force
    }
}

# ---------------------------------------------------------------------------
# 7. Финальная проверка целостности (verify_installation.py)
# ---------------------------------------------------------------------------
Write-Step "Этап 4: Проверка целостности установки (verify_installation.py)"

$VerifierScript = Join-Path $ProjectRoot ".agents\skills\project-installer\scripts\verify_installation.py"
if (Test-Path $VerifierScript) {
    & $VenvPython $VerifierScript
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Верификация завершилась с предупреждениями или ошибками (код: $LASTEXITCODE)."
    }
    else {
        Write-Ok "Проверка целостности успешно пройдена!"
    }
}

if ($UseAiAssistant) {
    $AiInstallerScript = Join-Path $ProjectRoot ".agents\skills\project-installer\scripts\run_installer_gemini.ps1"
    if (Test-Path $AiInstallerScript) {
        Write-Step "Запуск интерактивного ИИ-установщика Gemini CLI"
        & $AiInstallerScript
    }
}

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "🎉 Установка AI Windows Admin (AI-TC) успешно завершена!" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Рабочая директория: $ProjectRoot" -ForegroundColor Gray
Write-Host "Не забудьте указать GEMINI_API_KEY в файле: $EnvFile" -ForegroundColor Yellow
Write-Host "`nДля запуска платформы выполните:" -ForegroundColor Cyan
Write-Host "  .\tc.ps1" -ForegroundColor White
Write-Host "  или: .\venv\Scripts\python.exe main.py" -ForegroundColor White
Write-Host "Веб-интерфейс будет доступен по адресу: http://127.0.0.1:8001/tc`n" -ForegroundColor Cyan
