"""
=============================================================================
Process Name: Test Regional Modal Layout and Badge Scaling Standards
=============================================================================
Description:
    Модульные тесты для проверки исправлений верстки модального окна
    региональных настроек (#aboutRegionalSettingsModal), полного исключения цвета cyan
    в бейджах темы NightView и регулирования масштаба бейджей (+8%).

File: test_regional_modal_and_badge_scaling.py
Project: ai-tc
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-16 05:48:00
=============================================================================
"""

import json
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_nightview_badge_tokens_no_cyan() -> None:
    """Проверяет отсутствие циан-токенов (#0284c7, #0dcaf0) в бейджах NightView."""
    theme_file = _WEBGUI_DIR / "themes" / "nightview" / "theme.json"
    assert theme_file.exists(), f"Файл {theme_file} не найден"
    data = json.loads(theme_file.read_text(encoding="utf-8"))
    tokens = data.get("tokens", {})

    assert tokens.get("--ui-info") == "#184674"
    assert tokens.get("--badge-info-text") == "#184674"
    assert tokens.get("--status-info-text") == "#184674"
    assert tokens.get("--bs-info") == "#184674"
    assert "0284c7" not in tokens.get("--badge-info-bg", "")
    assert "0284c7" not in tokens.get("--badge-info-border", "")


def test_badge_size_scaling_plus_eight_percent() -> None:
    """Проверяет наличие регулируемого масштаба бейджей (--badge-scale: 1.08) и увеличение на 8%."""
    variables_file = _WEBGUI_DIR / "css" / "variables.css"
    assert variables_file.exists()
    content = variables_file.read_text(encoding="utf-8")

    assert "--badge-scale: 1.08;" in content
    assert "var(--badge-scale, 1.08)" in content

    components_file = _WEBGUI_DIR / "css" / "components.css"
    assert components_file.exists()
    comp_content = components_file.read_text(encoding="utf-8")
    assert "--badge-scale" in comp_content

    overrides_file = _WEBGUI_DIR / "css" / "overrides.css"
    assert overrides_file.exists()
    ovr_content = overrides_file.read_text(encoding="utf-8")
    assert "--badge-scale" in ovr_content
    # Проверка оверрайдов для исключения cyan в NightView
    assert '[data-theme="nightview"] .badge.bg-info' in ovr_content
    assert '[data-theme="nightview"] .ui-badge-info' in ovr_content


def test_regional_modal_html_and_js_layout() -> None:
    """Проверяет верстку модального окна и генератора карточек языковых пакетов."""
    modal_html_file = _WEBGUI_DIR / "tab_about_system" / "index.html"
    assert modal_html_file.exists()
    html_content = modal_html_file.read_text(encoding="utf-8")

    # Проверка отсутствия hardcoded btn-info text-dark в модальном окне
    assert 'id="btn-reg-save-tz"' in html_content
    assert 'id="btn-reg-save-loc"' in html_content
    assert 'id="btn-reg-sync-trio"' in html_content
    assert 'class="btn btn-sm btn-info text-dark' not in html_content

    # Проверка модуля локализации localization.js
    loc_js_file = _WEBGUI_DIR / "tab_about_system" / "panel_regional_network" / "localization.js"
    assert loc_js_file.exists()
    js_content = loc_js_file.read_text(encoding="utf-8")

    # Использование SVG-флагов вместо сырого текста emoji
    assert "lang-flag-svg" in js_content
    # Использование классов дизайн-системы ui-badge вместо жестко заданных рамок
    assert "ui-badge" in js_content
    assert "ui-badge-success" in js_content
    assert "ui-badge-info" in js_content
    # Карточки с flexbox и гармоничной высотой
    assert "lang-pack-card" in js_content
