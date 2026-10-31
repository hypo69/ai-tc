<#
=============================================================================
Process Name: Запуск SSH MCP Server (STDIO или Streamable HTTP)
=============================================================================
Description:
  Запуск сервера SSH MCP из пакета `.mcp\ssh_mcp` через виртуальное окружение
  проекта ai-tc.

File: start.ps1
Project: AI Windows Admin (ai-tc)
Package: .mcp.ssh_mcp.scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 17:10:00
=============================================================================

.SYNOPSIS
    Запуск SSH MCP Server в локальном (stdio) или удалённом (streamable-http) режиме.
#>
param(
    [ValidateSet("stdio", "streamable-http")]
    [string]$Transport = "stdio",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765
)

$McpDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$RootDir = Split-Path -Parent $McpDir
$PythonExe = Join-Path $RootDir "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$env:PYTHONPATH = "$McpDir;$RootDir;$env:PYTHONPATH"
& $PythonExe -m ssh_mcp --transport $Transport --host $HostAddress --port $Port
