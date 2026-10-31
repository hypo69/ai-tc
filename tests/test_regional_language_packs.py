# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests for Regional Language Packs & Keyboard Layouts
# =============================================================================
# Description:
#   Модульные тесты управления тройкой языковых пакетов (Русский, Иврит, Английский),
#   чтения раскладок клавиатуры из реестра Windows и API-эндпоинтов.
#
# File: test_regional_language_packs.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:35:00
# =============================================================================

import pytest
from apps.windows.sdk.modules.regional.keyboard_helper import (
    collect_language_packs_full,
    get_detailed_language_packs,
    manage_language_pack_action,
    TARGET_LANGUAGES,
)
from apps.windows.sdk.modules.regional import RegionalManager
from apps.windows.api.routers.about_system.models import (
    LanguagePackInfo,
    ManageLanguagePackRequest,
    ManageLanguagePackResponse,
)


def test_get_detailed_language_packs_returns_priority_trio():
    """Проверяет, что возвращаются все три приоритетных языковых пакета (ru-RU, he-IL, en-US)."""
    packs = get_detailed_language_packs()
    assert isinstance(packs, list)
    assert len(packs) >= 3

    tags = {p["tag"] for p in packs}
    assert {"ru-RU", "he-IL", "en-US"}.issubset(tags)

    for p in packs:
        if p["tag"] in ("ru-RU", "he-IL", "en-US"):
            assert "lcid" in p
            assert "is_installed" in p
            assert "is_active" in p
            assert "is_display_language" in p
            assert "is_default_input" in p
            assert isinstance(p["keyboard_layouts"], list)
            assert isinstance(p["available_layouts"], list)
            assert len(p["available_layouts"]) >= 1

        # Валидация через Pydantic-модель роутера
        model = LanguagePackInfo(**p)
        assert model.tag


def test_regional_manager_get_language_packs():
    """Проверяет интеграцию RegionalManager с детектором языковых пакетов и раскладок."""
    mgr = RegionalManager()
    packs = mgr.get_language_packs()
    assert len(packs) >= 3
    tags = {p["tag"] for p in packs}
    assert {"ru-RU", "he-IL", "en-US"}.issubset(tags)

    ru_pack = next(p for p in packs if p["tag"] == "ru-RU")
    assert ru_pack["lcid"].upper() == "0419"
    assert isinstance(ru_pack["keyboard_layouts"], list)
    assert isinstance(ru_pack["available_layouts"], list)


def test_manage_language_pack_validation():
    """Проверяет отказ при неизвестном действии и валидацию KLID."""
    dummy_ps = lambda cmd, t: (0, "", "")
    res_bad_action = manage_language_pack_action(True, dummy_ps, "ru-RU", "unknown_op")
    assert res_bad_action["status"] == "error"

    res_bad_klid = manage_language_pack_action(True, dummy_ps, "ru-RU", "add_layout", "invalid_klid")
    assert res_bad_klid["status"] == "error"

    req = ManageLanguagePackRequest(tag="he-IL", action="add_layout", klid="0002040D")
    assert req.tag == "he-IL"
    assert req.action == "add_layout"
    assert req.klid == "0002040D"

