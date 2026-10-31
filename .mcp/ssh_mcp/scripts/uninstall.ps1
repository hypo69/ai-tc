<#
=============================================================================
Process Name: Удаление службы SSH MCP Server
=============================================================================
Description:
  Остановка и удаление зарегистрированной службы SSHMCPServer с сохранением
  журналов аудита.

File: uninstall.ps1
Project: AI Windows Admin (ai-tc)
Package: ssh_mcp.scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 17:03:15
=============================================================================

.SYNOPSIS
    Удаление системной службы SSH MCP Server.
#>
param(
    [string]$ServiceName = "SSHMCPServer"
)

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Write-Output "[SSH-MCP] Служба '$ServiceName' успешно удалена."
} else {
    Write-Output "[SSH-MCP] Служба '$ServiceName' не зарегистрирована."
}
