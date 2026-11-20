<#
=============================================================================
Process Name: ai-tc Automation - Probe
=============================================================================
Description:
  PowerShell-сценарий автоматизации и системного обслуживания (probe).

Usage Examples:
  PowerShell Execution:
    .\probe.ps1

File: probe.ps1
Project: ai-tc
Package: .skills/usb-device-auditor/scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 05:00:00
=============================================================================
#>

Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*USB*' } | Select-Object Status, Class, FriendlyName, InstanceId | ConvertTo-Json