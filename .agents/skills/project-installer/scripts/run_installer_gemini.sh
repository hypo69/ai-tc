#!/usr/bin/env bash
# =============================================================================
# Process Name: ai-tc Automation - Run Installer Gemini (Bash)
# Updated: 2026-11-12 05:00:00
# Author: hypo69
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SKILL_DIR")")")"

INSTRUCTION_FILE="$SKILL_DIR/INSTALL-INSTRUCTION.md"
if [ ! -f "$INSTRUCTION_FILE" ]; then
    INSTRUCTION_FILE="$PROJECT_ROOT/INSTALL-INSTRUCTION.md"
fi

echo "========================================================="
echo "🤖 Запуск установщика Gemini CLI (gemini-3.1-flash-lite)"
echo "========================================================="
echo "Корень проекта: $PROJECT_ROOT"
echo "Инструкция:     $INSTRUCTION_FILE"
echo ""

PROMPT="Ты интерактивный установщик ai-tc. Прочти и выполни инструкции из '$INSTRUCTION_FILE'. Пошагово проведи установку, выполни pre-flight проверки, настрой venv, requirements.txt, .env и запусти верификацию verify_installation.py."

gemini --model "gemini-3.1-flash-lite" --prompt "$PROMPT"
