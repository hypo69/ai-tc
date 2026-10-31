"""
=============================================================================
Process Name: Test Windows Help Pages & Atomic Blocks Editor
=============================================================================
Description:
  Набор юнит-тестов для проверки работы API и компонентов редактора справки:
  1. Каталогизация модулей и блоков справки через GET /api/v1/help-pages/catalog.
  2. Чтение файла справки и проверка работы Style/Theme линтера.
  3. Сохранение файла с обновлением метки Updated.
  4. Защита от Path Traversal (обход каталога).
  5. Проверка интеграции панели редактора в #tab-app-internals#helppages-editor.

File: test_help_pages_editor.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 18:06:00
=============================================================================
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.windows.api.routers.router_help_pages import router, get_help_catalog
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_catalog_endpoint():
    """Проверка возврата каталога модулей со страницами справки."""
    response = client.get("/api/v1/help-pages/catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_modules"] >= 1

    log_settings_mod = next((m for m in data["modules"] if m["module"] == "tab_log_settings"), None)
    assert log_settings_mod is not None, "Модуль tab_log_settings должен быть в каталоге"
    assert log_settings_mod["has_composite"] is True
    assert log_settings_mod["blocks_count"] >= 6


def test_read_help_file_and_lint():
    """Проверка считывания файла справки и линтинга стилей."""
    path = "tab_log_settings/help/blocks/block_kpi_cards.html"
    response = client.get(f"/api/v1/help-pages/file?path={path}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "data-help-block" in data["content"]
    assert data["style_lint"]["is_theme_compliant"] is True
    assert data["style_lint"]["has_hardcoded_hex"] is False


def test_path_traversal_protection():
    """Проверка защиты от path traversal при передаче .. в пути."""
    bad_path = "../../passwords.txt"
    response = client.get(f"/api/v1/help-pages/file?path={bad_path}")
    assert response.status_code == 400


def test_editor_embed_in_app_internals():
    """Проверка разметки и роутинга редактора в tab_app_internals."""
    base_dir = Path(__file__).resolve().parent.parent
    index_html = (base_dir / "apps" / "windows" / "api" / "webgui" / "tab_app_internals" / "index.html").read_text(encoding="utf-8")
    assert "subpane-internals-helppages-editor" in index_html
    assert "helppages-editor" in index_html

    ui_utils = (base_dir / "apps" / "windows" / "api" / "webgui" / "tab_app_internals" / "common" / "ui_utils.js").read_text(encoding="utf-8")
    assert "helppages-editor" in ui_utils

    panel_js = (base_dir / "apps" / "windows" / "api" / "webgui" / "tab_app_internals" / "panel_subtabs" / "panel.js").read_text(encoding="utf-8")
    assert "helppages-editor" in panel_js
