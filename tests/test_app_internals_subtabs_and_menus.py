# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test App Internals Subtabs and Menus
# =============================================================================
# Description:
#   Тесты для интерфейса и бэкенда вкладки «Внутренняя кухня» (App Internals):
#   - Проверка разметки меню субвкладок и подменю блоков (канон «Меню — всегда меню»);
#   - Проверка четкого разделения двух баз знаний:
#     1) Подсказки по системе (локальный SQLite файл);
#     2) База инструментов агента (сервер Hostinger, цепочка размышлений);
#   - Проверка мгновенных тултипов и атрибутов интернационализации (data-i18n);
#   - Проверка эндпоинтов параметров рантайма и проверки SQLite.
#
# File: test_app_internals_subtabs_and_menus.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:15:00
# =============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from apps.windows.db.paths import resolve_system_knowledge_db_path, get_dynamic_path_config
from apps.windows.wikillm.storage import WikiStorage


def test_app_internals_html_menu_structure():
    """Проверяет соблюдение стандарта меню панелей и подменю блоков в index.html."""
    html_path = Path("apps/windows/api/webgui/tab_app_internals/index.html")
    assert html_path.exists(), f"Файл {html_path} не найден"
    html_content = html_path.read_text(encoding="utf-8")

    # 1. Проверка канонических комментариев
    assert "<!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->" in html_content
    assert "<!-- Подменю блоков внутри панели. Выбранный блок добавляется в URL как #block-<id> -->" in html_content

    # 2. Проверка субпанелей Уровня 1
    assert 'data-panel-id="telemetry"' in html_content
    assert 'data-panel-id="models"' in html_content
    assert 'data-panel-id="logs"' in html_content
    assert 'data-panel-id="etw"' in html_content
    assert 'data-panel-id="settings"' in html_content
    assert 'data-panel-id="wikillm-system"' in html_content
    assert 'data-panel-id="instruments"' in html_content

    # 3. Проверка блоков Уровня 2 для базы системных подсказок
    assert 'data-block-id="block-sys-storage"' in html_content
    assert 'data-block-id="block-sys-params"' in html_content
    assert 'data-block-id="block-sys-articles"' in html_content

    # 4. Проверка блоков Уровня 2 для базы инструментов агента (Hostinger)
    assert 'data-block-id="block-inst-hostinger"' in html_content
    assert 'data-block-id="block-inst-runtime"' in html_content
    assert 'data-block-id="block-inst-catalog"' in html_content

    # 5. Проверка статических тултипов без модели
    assert 'data-i18n-title="internals.subtabSystemKnowledgeTitle"' in html_content
    assert 'data-i18n-title="internals.subtabInstrumentsTitle"' in html_content
    assert 'data-i18n-title="internals.blockSysStorageTitle"' in html_content
    assert 'data-i18n-title="internals.blockInstHostingerTitle"' in html_content
    assert 'data-i18n-title="internals.blockInstRuntimeTitle"' in html_content
    assert 'data-i18n-title="internals.blockInstCatalogTitle"' in html_content


def test_locales_contain_internals_keys():
    """Проверяет наличие всех ключей локализации меню во всех языковых словарях."""
    for lang in ["ru", "en", "he", "uk"]:
        loc_path = Path(f"apps/windows/api/webgui/locales/{lang}.json")
        assert loc_path.exists(), f"Словарь {loc_path} не найден"
        with open(loc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "internals" in data, f"Раздел 'internals' отсутствует в {lang}.json"
        internals = data["internals"]
        assert "subtabSystemKnowledgeLabel" in internals
        assert "subtabSystemKnowledgeTitle" in internals
        assert "subtabInstrumentsLabel" in internals
        assert "subtabInstrumentsTitle" in internals
        assert "blockSysStorageLabel" in internals
        assert "blockSysStorageTitle" in internals
        assert "blockInstHostingerLabel" in internals
        assert "blockInstHostingerTitle" in internals
        assert "blockInstRuntimeLabel" in internals
        assert "blockInstRuntimeTitle" in internals
        assert "blockInstCatalogLabel" in internals
        assert "blockInstCatalogTitle" in internals


def test_ai_instruments_runtime_config_api():
    """Проверяет REST API сохранения и получения параметров цепочки размышлений."""
    from apps.windows.api.routers.router_ai_instruments import init_router
    from fastapi import FastAPI

    app = FastAPI()
    router = init_router()
    app.include_router(router)
    client = TestClient(app)

    # 1. Получение текущей конфигурации
    res = client.get("/api/v1/ai-instruments/runtime/config")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "runtime" in data

    # 2. Сохранение обновленной конфигурации
    payload = {
        "execution_timeout": 25,
        "elevate_powershell": True,
        "safe_ops_enabled": True,
        "auto_extract_from_reasoning": True,
        "title_prefix": "Расследование инцидента",
    }
    save_res = client.post("/api/v1/ai-instruments/runtime/config", json=payload)
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["success"] is True
    assert save_data["runtime"]["execution_timeout"] == 25
    assert save_data["runtime"]["title_prefix"] == "Расследование инцидента"

    # 3. Повторное чтение
    verify_res = client.get("/api/v1/ai-instruments/runtime/config")
    assert verify_res.status_code == 200
    assert verify_res.json()["runtime"]["title_prefix"] == "Расследование инцидента"


def test_sqlite_db_check_adapter():
    """Проверяет обработку локальной базы данных SQLite в адаптере БД."""
    from apps.windows.db.db_adapter import db_adapter

    res = db_adapter.check_connection({"engine": "sqlite", "connection_type": "sqlite"})
    assert "ok" in res
    assert res.get("engine") == "sqlite"
    assert "sqlite_info" in res


def test_resolve_system_knowledge_db_path_dynamic():
    """Проверяет динамическое раскрытие пути %ProgramData%/{app_name}/windows/knowledge.db."""
    dyn_cfg = get_dynamic_path_config()
    assert "programdata" in dyn_cfg
    assert dyn_cfg["app_name"] == "ai-tc"

    # Проверка нормального пути
    p = resolve_system_knowledge_db_path("%ProgramData%/{app_name}/windows/knowledge.db")
    assert "windows" in str(p)
    assert ("knowledge.db" in str(p) or "knowelege.db" in str(p))

    # Проверка пути с опечаткой knowelege.db (как указал пользователь в запросе)
    p_typo = resolve_system_knowledge_db_path("%Programdata%\\ai-tc\\windows\\knowelege.db")
    assert "windows" in str(p_typo)

    # Проверка работы WikiStorage с динамическим путем
    storage = WikiStorage()
    assert storage.db_path.exists()
    assert storage.ping() is True


def test_wikillm_db_config_endpoint_returns_dynamic_paths():
    """Проверяет, что REST эндпоинт GET /api/v1/wikillm/db/config возвращает динамические пути."""
    from apps.windows.api.routers.router_wikillm_editor import router as wikillm_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(wikillm_router)
    client = TestClient(app)

    res = client.get("/api/v1/wikillm/db/config")
    assert res.status_code == 200
    data = res.json()
    assert "sqlite" in data
    assert "dynamic_paths" in data
    assert "resolved_path" in data["sqlite"]
    assert Path(data["sqlite"]["resolved_path"]).exists()

