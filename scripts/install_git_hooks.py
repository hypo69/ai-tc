"""
=============================================================================
Process Name: Git Hooks Installer - WebGUI Menu Maintainer Verification
=============================================================================
Description:
  Устанавливает клиентские pre-commit Git-хуки для автоматической проверки
  соответствия меню WebGUI стандарту SUBTABS_AND_BLOCKS_MENU.md.

File: install_git_hooks.py
Package: scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 13:40:00
=============================================================================
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT_DIR / ".git" / "hooks"

PRE_COMMIT_SCRIPT = """#!/bin/sh
# =============================================================================
# Git Pre-Commit Hook: WebGUI Menu Architecture Standard Verification
# =============================================================================

echo "🔍 [Pre-Commit] Проверка стандартов меню WebGUI (menu_auditor)..."

if command -v py >/dev/null 2>&1; then
    PY_CMD="py"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
else
    PY_CMD="python"
fi

$PY_CMD .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py audit
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo ""
    echo "❌ [Pre-Commit Error] Обнаружены нарушения стандарта меню WebGUI!"
    echo "💡 Запустите команду автоисправления перед коммитом:"
    echo "   $PY_CMD .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py fix"
    echo ""
    exit 1
fi

echo "✅ [Pre-Commit] Все меню WebGUI соответствуют стандарту."
exit 0
"""


def install_hooks() -> None:
    if not HOOKS_DIR.parent.is_dir():
        print(f"❌ Директория .git не найдена по пути: {HOOKS_DIR.parent}")
        sys.exit(1)

    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    pre_commit_file = HOOKS_DIR / "pre-commit"

    pre_commit_file.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8", newline="\n")
    print(f"✅ Git pre-commit хук успешно установлен в: {pre_commit_file}")


if __name__ == "__main__":
    install_hooks()
