@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM =============================================================================
REM ai-tc USB Launcher (Автономный рантайм на флешке, БД/логи в ОС)
REM   1. Тихо (silent, без окна PowerShell) запускает службу телеметрии
REM   2. Запускает WebGUI + FastAPI + Electron через автономный runtime\python
REM
REM Использование:
REM   Start-TC.bat               - запуск с UAC (для полной диагностики Windows)
REM   Start-TC.bat --no-admin    - запуск без UAC
REM   Start-TC.bat --browser     - открыть в системном браузере
REM   Start-TC.bat --no-tlm      - не запускать телеметрию
REM =============================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\main.py" (
    set "APP_DIR=%SCRIPT_DIR%"
) else (
    set "APP_DIR=%SCRIPT_DIR%\ai-tc"
)

set "RUNTIME_DIR=%APP_DIR%\runtime"
set "PYTHON_EXE=%RUNTIME_DIR%\python\python.exe"
set "NODE_DIR=%RUNTIME_DIR%\node"
set "GEMINI_DIR=%RUNTIME_DIR%\gemini-cli"
set "BIN_DIR=%RUNTIME_DIR%\bin"
set "TLM_VBS=%APP_DIR%\Start-Telemetry-Silent.vbs"

set "NEED_ADMIN=1"
set "START_TLM=1"
set "FORWARD_ARGS="
:parse_args
if "%~1"=="" goto after_args
if /I "%~1"=="--no-admin" (
    set "NEED_ADMIN=0"
    shift
    goto parse_args
)
if /I "%~1"=="--no-tlm" (
    set "START_TLM=0"
    shift
    goto parse_args
)
set "FORWARD_ARGS=%FORWARD_ARGS% %1"
shift
goto parse_args
:after_args

if "%NEED_ADMIN%"=="1" (
    net session >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-admin%FORWARD_ARGS%' -Verb RunAs"
        exit /b 0
    )
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Автономный Python не найден: "%PYTHON_EXE%"
    pause
    exit /b 1
)

REM Настраиваем только автономные рантаймы; логи -> %ProgramData%\ai-tc\logs
set "AITC_DIR=%APP_DIR%"
set "AITC_RUNTIME_DIR=%RUNTIME_DIR%"
if not defined ProgramData set "ProgramData=C:\ProgramData"
set "AITC_LOGS_DIR=%ProgramData%\ai-tc\logs"
set "AI_TC_LOGS_DIR=%ProgramData%\ai-tc\logs"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONNOUSERSITE=1"
set "PATH=%RUNTIME_DIR%\python;%RUNTIME_DIR%\python\Scripts;%NODE_DIR%;%GEMINI_DIR%;%BIN_DIR%;%PATH%"

REM 1. Тихий запуск телеметрии (без окна PowerShell)
if "%START_TLM%"=="1" (
    if exist "%TLM_VBS%" (
        wscript.exe //B //NoLogo "%TLM_VBS%"
    )
)

REM 2. Запуск основного приложения ai-tc
cd /d "%APP_DIR%"
"%PYTHON_EXE%" "%APP_DIR%\main.py" %FORWARD_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ai-tc] Процесс завершился с кодом %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%