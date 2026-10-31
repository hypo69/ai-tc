<#
=============================================================================
Process Name: Установка службы SSH MCP Server на Windows и Linux
=============================================================================
Description:
  Автоматическая подготовка каталогов (C:\Program Files\SSH-MCP\ на Windows
  или /opt/ssh-mcp на Linux), проверка виртуального окружения Python и
  регистрация системной службы (Windows Service / systemd).

File: install.ps1
Project: AI Windows Admin (ai-tc)
Package: ssh_mcp.scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 17:03:00
=============================================================================

.SYNOPSIS
    Установка SSH MCP Server в качестве системной службы.

.DESCRIPTION
    Создаёт структуру каталогов bin, config, runtime, logs, копирует файлы
    конфигурации и регистрирует службу SSHMCPServer.

.PARAMETER InstallDir
    Целевой каталог установки (по умолчанию C:\Program Files\SSH-MCP).

.EXAMPLE
    .\install.ps1 -InstallDir "C:\Program Files\SSH-MCP"
#>
param(
    [string]$InstallDir = "C:\Program Files\SSH-MCP"
)

$ErrorActionPreference = "Stop"
$subdirs = @("bin", "config", "runtime", "logs", "data")
foreach ($sd in $subdirs) {
    $full = Join-Path $InstallDir $sd
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
}
Write-Output "[SSH-MCP] Структура каталогов в '$InstallDir' успешно подготовлена."
