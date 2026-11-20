"""
=============================================================================
Process Name: Test NightView Warm Paper Styling Standard
=============================================================================
Description:
    Модульные тесты соответствия шаблона NightView (Тёплая бумага) и единого стандарта
    стилизации меню, подменю, блоков и заголовков таблиц (.panel-title):
    - Цвет заголовков панелей и таблиц (.panel-title) соответствует синему акценту меню (--nav-active / #1d4ed8).
    - Иконки внутри заголовков (.panel-title i) наследуют синий цвет заголовка.
    - В теме nightview и nightview-70 токен --panel-header-color равен #1d4ed8.
    - Единый стандарт оформления меню и подменю (на базе верхнего меню) закреплен в CSS:
      контейнеры, неактивные элементы, ховер и активное состояние.
    - Унификация блоков (карточки, панели, заголовки) на системных токенах без нагромождения стилей.

File: test_nightview_styling_standard.py
Project: ai-tc
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 12:56:00
=============================================================================
"""

import json
from pathlib import Path
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"
_THEMES_DIR = _WEBGUI_DIR / "themes"
_CSS_DIR = _WEBGUI_DIR / "css"


def test_nightview_theme_tokens_panel_header_color() -> None:
    """Проверяет установку токена --panel-header-color в цвет меню (#1d4ed8) в теме NightView."""
    theme_file = _THEMES_DIR / "nightview" / "theme.json"
    assert theme_file.exists(), f"Файл темы {theme_file} не найден"
    data = json.loads(theme_file.read_text(encoding="utf-8"))
    tokens = data.get("tokens", {})

    assert tokens.get("--nav-active") == "#1d4ed8", "В теме nightview --nav-active должен быть #1d4ed8"
    assert tokens.get("--panel-header-color") == "#1d4ed8", "В теме nightview --panel-header-color должен быть равен синему цвету меню #1d4ed8"


def test_nightview_70_theme_tokens_panel_header_color() -> None:
    """Проверяет установку токена --panel-header-color в цвет меню (#1d4ed8) в теме NightView 70%."""
    theme_file = _THEMES_DIR / "nightview-70" / "theme.json"
    assert theme_file.exists(), f"Файл темы {theme_file} не найден"
    data = json.loads(theme_file.read_text(encoding="utf-8"))
    tokens = data.get("tokens", {})

    assert tokens.get("--nav-active") == "#1d4ed8", "В теме nightview-70 --nav-active должен быть #1d4ed8"
    assert tokens.get("--panel-header-color") == "#1d4ed8", "В теме nightview-70 --panel-header-color должен быть равен синему цвету меню #1d4ed8"


def test_css_themes_and_variables_nightview_panel_header_color() -> None:
    """Проверяет CSS-переменные темы NightView в themes.css и variables.css."""
    themes_css = (_CSS_DIR / "themes.css").read_text(encoding="utf-8")
    variables_css = (_CSS_DIR / "variables.css").read_text(encoding="utf-8")

    # В блоке nightview токен --panel-header-color должен быть синим (#1d4ed8)
    assert "--panel-header-color: #1d4ed8;" in themes_css, "themes.css должен содержать --panel-header-color: #1d4ed8;"
    assert "--panel-header-color:     #1d4ed8;" in variables_css or "--panel-header-color: #1d4ed8;" in variables_css, "variables.css должен содержать --panel-header-color: #1d4ed8;"


def test_panel_title_color_and_icon_inheritance() -> None:
    """Проверяет синий цвет заголовков таблиц (.panel-title) и наследование цвета иконками."""
    nav_css = (_CSS_DIR / "nav.css").read_text(encoding="utf-8")
    global_overrides = (_CSS_DIR / "global-overrides.css").read_text(encoding="utf-8")

    # В nav.css или global-overrides.css .panel-title должен использовать цвет панели/акцента
    assert ".panel-title" in nav_css
    assert "color: var(--panel-header-color, var(--nav-active))" in nav_css or "color: var(--panel-header-color, var(--nav-active, var(--text-color)))" in global_overrides
    # Иконки внутри .panel-title должны наследовать цвет (color: inherit !important)
    assert ".panel-title i" in nav_css or ".panel-title i" in global_overrides
    assert "color: inherit !important;" in nav_css or "color: inherit !important;" in global_overrides


def test_unified_nav_and_subtabs_standard() -> None:
    """Проверяет единый стандарт меню, подменю и блоков в nav.css по образцу верхнего меню."""
    nav_css = (_CSS_DIR / "nav.css").read_text(encoding="utf-8")

    # Контейнеры
    assert ".main-nav-container" in nav_css
    assert ".subnav-container" in nav_css
    # Подменю и вкладки
    assert '[role="tablist"]:not(.nav-tabs)' in nav_css
    assert ".nav-pills" in nav_css
    # Стили ховера и активности
    assert "var(--nav-hover-bg)" in nav_css
    assert "var(--nav-active)" in nav_css
    # Блоки и карточки
    assert ".winadmin-panel" in nav_css
    assert ".ui-card" in nav_css
    assert "var(--surface-1)" in nav_css
    assert "var(--surface-2)" in nav_css
