# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Regional SDK Module
# =============================================================================
# Description:
#   Комплексное тестирование модуля RegionalManager из состава Windows SDK
#   (apps.windows.sdk.modules.regional): языковые пакеты, часовые пояса,
#   локали, информация о пользователе, имя хоста и рабочая группа.
#
# File: test_regional_sdk_module.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:41:00
# =============================================================================

from __future__ import annotations

import pytest

from apps.windows.sdk import windows_sdk, RegionalManager
from apps.windows.sdk.modules.regional.models import (
    LanguagePackModel,
    TimezoneModel,
    LocaleModel,
    UserAccountModel,
)


def test_windows_sdk_facade_regional_property():
    """Проверка доступности RegionalManager через фасад windows_sdk.modules.regional."""
    assert hasattr(windows_sdk.modules, "regional")
    rm = windows_sdk.modules.regional
    assert isinstance(rm, RegionalManager)


def test_regional_manager_get_language_packs():
    """Проверка получения списка языковых пакетов через RegionalManager."""
    rm = RegionalManager()
    packs = rm.get_language_packs()
    assert isinstance(packs, list)
    assert len(packs) >= 3

    tags = [p["tag"].lower() for p in packs]
    assert "ru-ru" in tags
    assert "he-il" in tags
    assert "en-us" in tags

    for p in packs:
        model = LanguagePackModel(**p)
        assert model.tag
        assert model.name
        assert model.native_name
        assert isinstance(model.is_installed, bool)
        assert isinstance(model.is_active, bool)


def test_regional_manager_install_language_pack_validation():
    """Проверка валидации языкового тега при установке пакета."""
    rm = RegionalManager()
    res_bad = rm.install_language_pack("invalid;injection")
    assert res_bad["status"] == "error"
    assert "Недопустимый языковой тэг" in res_bad["message"]
    assert res_bad["is_installed"] is False

    res_good_format = rm.install_language_pack("ru-RU")
    assert res_good_format["status"] == "ok"
    assert res_good_format["tag"] == "ru-RU"


def test_regional_manager_get_timezones():
    """Проверка получения списка часовых поясов."""
    rm = RegionalManager()
    tz_list = rm.get_timezones()
    assert isinstance(tz_list, list)
    assert len(tz_list) > 0
    for t in tz_list:
        model = TimezoneModel(**t)
        assert model.id
        assert model.display_name


def test_regional_manager_get_current_timezone():
    """Проверка получения текущего часового пояса."""
    rm = RegionalManager()
    cur_tz = rm.get_current_timezone()
    assert isinstance(cur_tz, str)


def test_regional_manager_set_timezone_validation():
    """Проверка валидации идентификатора часового пояса."""
    rm = RegionalManager()
    res = rm.set_timezone("Invalid!@#$Timezone")
    assert res["status"] == "error"
    assert "Недопустимый формат" in res["message"]


def test_regional_manager_get_current_locales():
    """Проверка получения системной и пользовательской локалей."""
    rm = RegionalManager()
    locs = rm.get_current_locales()
    assert isinstance(locs, dict)
    assert "system_locale" in locs
    assert "user_locale" in locs
    assert len(locs["system_locale"]) > 0


def test_regional_manager_get_user_account_info():
    """Проверка сбора информации о пользователе через RegionalManager."""
    rm = RegionalManager()
    info = rm.get_user_account_info()
    model = UserAccountModel(**info)
    assert model.username
    assert isinstance(model.groups, list)
    assert isinstance(model.is_admin, bool)


def test_regional_manager_get_workgroup():
    """Проверка получения имени рабочей группы."""
    rm = RegionalManager()
    wg = rm.get_workgroup()
    assert isinstance(wg, str)
    assert len(wg) > 0


def test_regional_manager_rename_computer_validation():
    """Проверка валидации имени хоста при переименовании."""
    rm = RegionalManager()
    res = rm.rename_computer("Invalid Name! With Spaces")
    assert res["status"] == "error"
    assert "Недопустимый формат имени" in res["message"]


def test_regional_manager_change_workgroup_validation():
    """Проверка валидации имени рабочей группы."""
    rm = RegionalManager()
    res = rm.change_workgroup("VERY_LONG_INVALID_WORKGROUP_NAME_THAT_EXCEEDS_15_CHARS")
    assert res["status"] == "error"
    assert "должно содержать от 1 до 15 символов" in res["message"]

