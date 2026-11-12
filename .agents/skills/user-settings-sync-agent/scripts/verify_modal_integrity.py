# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: User Settings Modal Integrity & Compatibility Auditor
# =============================================================================
# Description:
#   Автоматический инструмент аудита и проверки целостности единого модального
#   окна пользовательских настроек (#userSettingsModal: темы, языки, модель ИИ,
#   OAuth, 90vw стандарт). Проверяет контракты DOM, наличие ключевых элементов,
#   локализацию и синхронизацию между AI-TC, AI-Assistant и AI-Breadboard.
#
# Usage Examples:
#   CLI:
#     py .agents/skills/user-settings-sync-agent/scripts/verify_modal_integrity.py
#
# File: verify_modal_integrity.py
# Project: ai-windows-admin
# Package: .agents.skills.user-settings-sync-agent.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:55:00
# =============================================================================

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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

REQUIRED_DOM_IDS = [
    "userSettingsModal",
    "userSettingsModalLabel",
    "modal-user-settings-body",
    "user-settings-auth-card",
    "user-settings-guest-card",
    "modal-lang-selector",
    "modal-theme-selector",
    "modal-model-ping-section",
    "model-ping-input",
    "btn-model-ping-send",
    "modal-btn-open-theme-editor",
    "btn-open-cache-manager",
    "user-settings-active-model-badge",
    "user-settings-active-model-badge-top",
]

REQUIRED_THEMES = [
    "system",
    "dark",
    "theme-dark-slate",
    "theme-cyberpunk",
    "terminal",
    "nordic-frost",
    "solarized-dark",
    "theme-high-contrast",
    "light",
    "nightview",
    "nightview-70",
    "brick",
    "theme-light-enterprise",
]

REQUIRED_LANGS = ["ru-RU", "en-US", "he-IL", "uk-UA"]

REQUIRED_JS_FUNCTIONS = [
    "ensureUserSettingsModal",
    "initUserSettings",
    "refreshUserProfile",
    "refreshActiveModelBadge",
    "openModelsTab",
    "isUserAdmin",
    "executeUserAction",
]


def audit_modal_html(html_path: Path) -> List[str]:
    """Проверяет соответствие разметки компонента user_settings_modal.html контрактам."""
    errors: List[str] = []
    if not html_path.is_file():
        return [f"Файл не найден: {html_path}"]

    content = html_path.read_text(encoding="utf-8")

    # 1. Проверка обязательных DOM ID
    for el_id in REQUIRED_DOM_IDS:
        if f'id="{el_id}"' not in content and f"id='{el_id}'" not in content:
            errors.append(f"Отсутствует обязательный элемент #{el_id} в {html_path}")

    # 2. Проверка селектора тем
    for theme_id in REQUIRED_THEMES:
        if f'value="{theme_id}"' not in content and f"value='{theme_id}'" not in content:
            errors.append(f"Тема '{theme_id}' не представлена в селекторе тем в {html_path}")

    # 3. Проверка селектора языков
    for lang_code in REQUIRED_LANGS:
        if lang_code not in content:
            errors.append(f"Языковая локаль '{lang_code}' не найдена в {html_path}")

    # 4. Проверка связки с вкладкой tab-models
    if 'data-tab="tab-models"' not in content or "openModelsTab" not in content:
        errors.append(f"Бейдж активной модели не содержит переход на tab-models в {html_path}")

    return errors


def audit_user_settings_js(js_path: Path) -> List[str]:
    """Проверяет наличие экспортов и ключевой логики в userSettings.js."""
    errors: List[str] = []
    if not js_path.is_file():
        return [f"Файл не найден: {js_path}"]

    content = js_path.read_text(encoding="utf-8")

    for fn_name in REQUIRED_JS_FUNCTIONS:
        if fn_name not in content:
            errors.append(f"Функция {fn_name}() не найдена в {js_path}")

    for win_export in ["window.openModelsTab", "window.refreshActiveModelBadge", "window.initUserSettings"]:
        if win_export not in content:
            errors.append(f"Глобальный экспорт {win_export} отсутствует в {js_path}")

    return errors


def audit_locales(locales_dir: Path) -> List[str]:
    """Проверяет наличие переводов ключей userSettings во всех локалях."""
    errors: List[str] = []
    if not locales_dir.is_dir():
        return [f"Каталог локалей не найден: {locales_dir}"]

    required_keys = [
        "title",
        "language",
        "theme",
        "activeModelBadgeTitle",
        "themeNightview70",
        "themeNightview",
        "modelPingTitle",
        "themeEditorBtn",
        "cacheManagerBtn",
    ]

    for lang in ["ru", "en", "he", "uk"]:
        lang_file = locales_dir / f"{lang}.json"
        if not lang_file.is_file():
            errors.append(f"Языковой файл отсутствует: {lang_file}")
            continue

        try:
            data = json.loads(lang_file.read_text(encoding="utf-8"))
            us = data.get("userSettings", {})
            for rk in required_keys:
                if rk not in us:
                    errors.append(f"Ключ userSettings.{rk} отсутствует в {lang_file.name}")
        except Exception as e:
            errors.append(f"Ошибка парсинга {lang_file}: {e}")

    return errors


def check_cross_project_sync() -> List[str]:
    """Проверяет совпадение эталонных файлов в apps/common/webgui между всеми проектами."""
    errors: List[str] = []
    target_files = [
        Path("components/user_settings_modal.html"),
        Path("js/userSettings.js"),
        Path("locales/ru.json"),
    ]

    ref_proj = "AI-TC"
    ref_root = PROJECTS[ref_proj] / "apps" / "common" / "webgui"

    for rel_path in target_files:
        ref_file = ref_root / rel_path
        if not ref_file.is_file():
            errors.append(f"Эталонный файл отсутствует в {ref_proj}: {ref_file}")
            continue

        ref_bytes = ref_file.read_bytes()

        for proj_name, proj_root in PROJECTS.items():
            if proj_name == ref_proj:
                continue
            other_file = proj_root / "apps" / "common" / "webgui" / rel_path
            if not other_file.is_file():
                errors.append(f"Файл {rel_path} отсутствует в проекте {proj_name}")
                continue
            if other_file.read_bytes() != ref_bytes:
                errors.append(f"Рассинхронизация {rel_path}: содержимое в {proj_name} отличается от {ref_proj}")

    return errors


def run_full_audit() -> bool:
    """Запускает комплексный аудит целостности модального окна настроек во всех проектах."""
    all_errors: List[str] = []

    print("════════════════════════════════════════════════════════════════════════════")
    print(" АУДИТ ЦЕЛОСТНОСТИ МОДАЛЬНОГО ОКНА НАСТРОЕК (#userSettingsModal) ")
    print("════════════════════════════════════════════════════════════════════════════")

    for proj_name, proj_root in PROJECTS.items():
        if not proj_root.is_dir():
            print(f"⚠️  Проект {proj_name} не найден по пути {proj_root}, пропускаем.")
            continue

        common_webgui = proj_root / "apps" / "common" / "webgui"
        print(f"\n🔍 Проверка проекта: {proj_name} ({common_webgui})")

        modal_path = common_webgui / "components" / "user_settings_modal.html"
        js_path = common_webgui / "js" / "userSettings.js"
        locales_dir = common_webgui / "locales"

        html_errs = audit_modal_html(modal_path)
        js_errs = audit_user_settings_js(js_path)
        loc_errs = audit_locales(locales_dir)

        proj_errors = html_errs + js_errs + loc_errs
        if proj_errors:
            print(f"  ❌ Обнаружено ошибок: {len(proj_errors)}")
            for err in proj_errors:
                print(f"     - {err}")
            all_errors.extend(proj_errors)
        else:
            print("  ✅ Все контракты DOM, скриптов и локализации соблюдены.")

    print("\n🔍 Проверка кросс-проектной синхронизации (AI-TC vs AI-Assistant vs AI-Breadboard)...")
    sync_errors = check_cross_project_sync()
    if sync_errors:
        print(f"  ❌ Ошибки синхронизации: {len(sync_errors)}")
        for err in sync_errors:
            print(f"     - {err}")
        all_errors.extend(sync_errors)
    else:
        print("  ✅ Все общие компоненты синхронизированы на 100%.")

    print("\n════════════════════════════════════════════════════════════════════════════")
    if all_errors:
        print(f"ИТОГ: НАЙДЕНО {len(all_errors)} ОШИБОК! Запустите sync_user_settings.py для исправления.")
        return False
    else:
        print("ИТОГ: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО. Совместимость подтверждена.")
        return True


if __name__ == "__main__":
    success = run_full_audit()
    sys.exit(0 if success else 1)
