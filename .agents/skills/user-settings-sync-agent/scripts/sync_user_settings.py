# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: User Settings Modal Multi-Project Synchronizer
# =============================================================================
# Description:
#   Автоматизированный скрипт синхронизации и каскадного распространения
#   изменений единого модального окна пользовательских настроек (#userSettingsModal)
#   между всеми проектами экосистемы: AI-TC, AI-Assistant и AI-Breadboard.
#   Выполняет глубокое слияние словарей локалей, синхронизацию разметки,
#   клиентского контроллера userSettings.js и статических страниц index.html.
#
# Usage Examples:
#   CLI:
#     py .agents/skills/user-settings-sync-agent/scripts/sync_user_settings.py
#     py .agents/skills/user-settings-sync-agent/scripts/sync_user_settings.py --source AI-TC
#
# File: sync_user_settings.py
# Project: ai-windows-admin
# Package: .agents.skills.user-settings-sync-agent.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:58:00
# =============================================================================

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECTS = {
    "AI-TC": Path(r"C:\Users\onela\AppData\Local\AI-TC"),
    "AI-Assistant": Path(r"C:\Users\onela\AppData\Local\AI-Assistant"),
    "AI-Breadboard": Path(r"C:\Users\onela\AppData\Local\AI-Breadboard"),
}


def deep_merge(base: dict, update: dict) -> dict:
    """Рекурсивное слияние словарей без потери исходных ключей."""
    merged = dict(base)
    for k, v in update.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def sync_all_projects(source_name: str = "AI-TC") -> bool:
    """Выполняет полную двустороннюю гармонизацию и синхронизацию во все проекты."""
    source_root = PROJECTS.get(source_name)
    if not source_root or not source_root.is_dir():
        print(f"❌ Исходный проект {source_name} не найден!")
        return False

    src_common = source_root / "apps" / "common" / "webgui"
    print(f"🚀 Запуск синхронизации на базе источника: {source_name} ({src_common})")

    # 1. Глубокое слияние словарей локалей по всем доступным проектам
    print("📦 1. Гармонизация и слияние языковых локалей...")
    for lang in ["ru", "en", "he", "uk"]:
        merged_locale: Dict[str, Any] = {}
        # Сбор данных со всех проектов
        for proj_name, proj_path in PROJECTS.items():
            loc_file = proj_path / "apps" / "common" / "webgui" / "locales" / f"{lang}.json"
            if loc_file.is_file():
                try:
                    data = json.loads(loc_file.read_text(encoding="utf-8"))
                    merged_locale = deep_merge(merged_locale, data)
                except Exception as e:
                    print(f"  ⚠️ Ошибка чтения {loc_file}: {e}")

        # Запись объединенного словаря во все проекты
        for proj_name, proj_path in PROJECTS.items():
            if proj_path.is_dir():
                loc_dest = proj_path / "apps" / "common" / "webgui" / "locales" / f"{lang}.json"
                loc_dest.parent.mkdir(parents=True, exist_ok=True)
                loc_dest.write_text(json.dumps(merged_locale, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ Локаль {lang}.json синхронизирована (ключей: {len(merged_locale)})")

    # 2. Синхронизация user_settings_modal.html
    print("📦 2. Распространение компонента user_settings_modal.html...")
    src_modal = src_common / "components" / "user_settings_modal.html"
    if not src_modal.is_file():
        print(f"❌ Исходный файл компонента не найден: {src_modal}")
        return False

    modal_content = src_modal.read_text(encoding="utf-8")
    for proj_name, proj_path in PROJECTS.items():
        if proj_path.is_dir():
            target_modal = proj_path / "apps" / "common" / "webgui" / "components" / "user_settings_modal.html"
            target_modal.parent.mkdir(parents=True, exist_ok=True)
            target_modal.write_text(modal_content, encoding="utf-8")

    # В AI-TC также синхронизируем локальный webgui/components
    tc_local_modal = PROJECTS["AI-TC"] / "apps" / "windows" / "api" / "webgui" / "components" / "user_settings_modal.html"
    tc_local_modal.parent.mkdir(parents=True, exist_ok=True)
    tc_local_modal.write_text(modal_content, encoding="utf-8")
    print("  ✅ Компонент user_settings_modal.html обновлен во всех репозиториях.")

    # 3. Синхронизация контроллера userSettings.js
    print("📦 3. Распространение контроллера userSettings.js...")
    src_js = src_common / "js" / "userSettings.js"
    if not src_js.is_file():
        print(f"❌ Исходный файл контроллера не найден: {src_js}")
        return False

    js_content = src_js.read_text(encoding="utf-8")
    for proj_name, proj_path in PROJECTS.items():
        if proj_path.is_dir():
            target_js = proj_path / "apps" / "common" / "webgui" / "js" / "userSettings.js"
            target_js.parent.mkdir(parents=True, exist_ok=True)
            target_js.write_text(js_content, encoding="utf-8")

    tc_local_js = PROJECTS["AI-TC"] / "apps" / "windows" / "api" / "webgui" / "js" / "userSettings.js"
    tc_local_js.parent.mkdir(parents=True, exist_ok=True)
    tc_local_js.write_text(js_content, encoding="utf-8")
    print("  ✅ Контроллер userSettings.js обновлен во всех репозиториях.")

    # 4. Обновление статических index.html в AI-TC
    print("📦 4. Актуализация статической разметки в index.html и admin/index.html...")
    start_tag = '<div aria-hidden="true" aria-labelledby="userSettingsModalLabel"'
    start_idx = modal_content.find(start_tag)
    if start_idx != -1:
        modal_snippet = modal_content[start_idx:].strip()
        tc_webgui = PROJECTS["AI-TC"] / "apps" / "windows" / "api" / "webgui"

        # admin/index.html
        admin_index = tc_webgui / "admin" / "index.html"
        if admin_index.is_file():
            atxt = admin_index.read_text(encoding="utf-8")
            old_start = atxt.find(start_tag)
            if old_start != -1:
                atxt = atxt[:old_start] + modal_snippet + "\n</body>\n</html>"
                admin_index.write_text(atxt, encoding="utf-8")
                print("  ✅ admin/index.html актуализирован.")

        # index.html
        main_index = tc_webgui / "index.html"
        if main_index.is_file():
            mtxt = main_index.read_text(encoding="utf-8")
            old_start = mtxt.find(start_tag)
            if old_start != -1:
                next_sec = '<!-- Cache Manager Modal -->'
                old_end = mtxt.find(next_sec, old_start)
                if old_end != -1:
                    mtxt = mtxt[:old_start] + modal_snippet + "\n" + mtxt[old_end:]
                    main_index.write_text(mtxt, encoding="utf-8")
                    print("  ✅ index.html актуализирован.")

    # 5. Запуск аудита для подтверждения
    print("\n🔍 5. Запуск валидационного аудита...")
    from verify_modal_integrity import run_full_audit
    return run_full_audit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Синхронизатор модального окна настроек пользователя")
    parser.add_argument("--source", default="AI-TC", choices=["AI-TC", "AI-Assistant", "AI-Breadboard"], help="Исходный проект для эталона")
    args = parser.parse_args()

    success = sync_all_projects(args.source)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
