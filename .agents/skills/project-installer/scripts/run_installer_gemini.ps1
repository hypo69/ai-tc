<#
=============================================================================
Process Name: AI-Windows-Admin Automation - Run Installer Gemini
=============================================================================
Description:
  Запуск интерактивного установщика AI Windows Admin через Gemini CLI
  с моделью gemini-3.1-flash-lite.

Usage Examples:
  PowerShell Execution:
    .\run_installer_gemini.ps1

File: run_installer_gemini.ps1
Project: ai-windows-admin
Package: .agents/skills/project-installer/scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 19:10:00
=============================================================================
.SYNOPSIS
    Интерактивный запуск установщика проекта через Gemini CLI.
.DESCRIPTION
    Инициализирует процесс пошаговой установки и верификации через Gemini CLI.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir

# Динамический поиск корня проекта по маркеру __root__ или header.py
$currentDir = $skillDir
$projectRoot = $null
while ($currentDir -and (Test-Path $currentDir)) {
    if ((Test-Path (Join-Path $currentDir "__root__")) -or ((Test-Path (Join-Path $currentDir "header.py")) -and (Test-Path (Join-Path $currentDir "config.json")))) {
        $projectRoot = $currentDir
        break
    }
    $parent = Split-Path -Parent $currentDir
    if ($parent -eq $currentDir) { break }
    $currentDir = $parent
}

if (-not $projectRoot) {
    $projectRoot = (Get-Item $skillDir).Parent.Parent.Parent.FullName
}

$instructionFile = Join-Path $skillDir "INSTALL-INSTRUCTION.md"
if (-not (Test-Path $instructionFile)) {
    $instructionFile = Join-Path $projectRoot "INSTALL-INSTRUCTION.md"
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "🤖 Запуск установщика Gemini CLI (gemini-3.1-flash-lite)" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Корень проекта: $projectRoot" -ForegroundColor Gray
Write-Host "Инструкция:     $instructionFile" -ForegroundColor Gray
Write-Host ""

$prompt = "Ты интерактивный установщик AI Windows Admin. Прочти и выполни инструкции из '$instructionFile'. Пошагово проведи установку, выполни pre-flight проверки, запусти телеметрию tlm.ps1, создай venv, установи requirements.txt, настрой .env и в конце запусти verify_installation.py."

# Выполнение Gemini CLI с моделью gemini-3.1-flash-lite
gemini --model "gemini-3.1-flash-lite" --prompt "$prompt"
