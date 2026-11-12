# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - User Security Modal & Drill-Down Tests
# =============================================================================
# Description:
#   Модульные тесты проверки функционала модального окна безопасности, смены
#   пароля, политик SAM и запуска параметров Windows (PIN, Windows Hello)
#   через кнопку Drill-Down с красной дрелью (red_drill.png) в tab_windows_admin.
#
# Usage Examples:
#   pytest tests/test_user_security_modal.py -v
#
# File: test_user_security_modal.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 15:52:00
# =============================================================================

"""Модульные тесты для проверки функционала безопасности пользователя и модального окна Drill-Down."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from apps.windows.sdk.modules.accounts_identity.models import (
    UserUacConfig,
    UserUacUpdateRequest,
)
from apps.windows.sdk.modules.sysadmin.router import (
    ChangePasswordRequest,
    LaunchSettingRequest,
    change_account_password,
    launch_system_setting,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_user_security_modal_dom_structure() -> None:
    """Проверяет корректность разметки единого модального окна #userSecurityModal с вкладками в index.html."""
    html_file = _WEBGUI_DIR / "tab_windows_admin" / "index.html"
    assert html_file.exists(), f"Файл {html_file} не найден"
    content = html_file.read_text(encoding="utf-8")

    # Проверка наличия единого модального окна
    assert 'id="userSecurityModal"' in content, "Модальное окно #userSecurityModal не найдено"
    assert 'id="user-security-modal-username"' in content, "Элемент имени пользователя не найден"
    assert 'id="user-security-modal-loading"' in content, "Индикатор загрузки не найден"
    assert 'id="user-security-modal-content"' in content, "Контейнер контента не найден"

    # Проверка двух вкладок: Безопасность и UAC
    assert 'id="sec-tab-btn-security"' in content, "Вкладка безопасности #sec-tab-btn-security не найдена"
    assert 'id="sec-tab-btn-uac"' in content, "Вкладка UAC #sec-tab-btn-uac не найдена"
    assert 'id="sec-pane-security"' in content, "Панель безопасности #sec-pane-security не найдена"
    assert 'id="sec-pane-uac"' in content, "Панель UAC #sec-pane-uac не найдена"

    # Проверка первой колонки Drill-Down таблицы пользователей
    assert 'title="Безопасность и параметры учетной записи (Drill-Down)"' in content
    assert 'colspan="9"' in content

    # Проверка элементов вкладки безопасности и паролей
    assert 'id="sec-user-new-password"' in content
    assert 'id="sec-user-confirm-password"' in content
    assert 'id="btn-sec-change-password"' in content
    assert 'id="sec-toggle-password-visibility"' in content
    assert 'id="sec-policy-enabled"' in content
    assert 'id="sec-policy-never-expires"' in content
    assert 'id="sec-policy-cannot-change"' in content
    assert 'id="sec-policy-must-change"' in content
    assert 'id="sec-policy-pwd-required"' in content
    assert 'id="sec-role-admin"' in content
    assert 'id="sec-role-standard"' in content
    assert 'id="btn-sec-save-policies"' in content

    # Проверка кнопок запуска системных параметров Windows (PIN, Hello)
    assert 'data-target="ms-settings:signinoptions"' in content
    assert 'data-target="ms-settings:signinoptions-launchfaceenrollment"' in content
    assert 'data-target="ms-settings:signinoptions-launchfingerprintenrollment"' in content
    assert 'data-target="ms-settings:signinoptions-launchpinreset"' in content
    assert 'data-target="netplwiz"' in content
    assert 'data-target="lusrmgr.msc"' in content
    assert 'data-target="secpol.msc"' in content

    # Проверка элементов объединенной вкладки UAC
    assert 'id="uac-info-sid"' in content
    assert 'id="uac-info-lua"' in content
    assert 'id="uac-info-role"' in content
    assert 'id="uac-role-admin"' in content
    assert 'id="uac-role-standard"' in content
    assert 'id="uac-filter-admin-token"' in content
    assert 'id="uac-prompt-admin"' in content
    assert 'id="uac-prompt-user"' in content
    assert 'id="uac-secure-desktop"' in content
    assert 'id="uac-enable-virt"' in content
    assert 'id="btn-save-user-uac"' in content


def test_user_security_drilldown_button_in_panel_js() -> None:
    """Проверяет вызов безопасности через красную дрель и отсутствие отдельной кнопки UAC в действиях."""
    panel_js = _WEBGUI_DIR / "tab_windows_admin" / "panel_users" / "panel.js"
    assert panel_js.exists(), f"Файл {panel_js} не найден"
    content = panel_js.read_text(encoding="utf-8")

    assert "btn-user-security-drilldown" in content, "Класс кнопки вызова безопасности отсутствует в panel.js"
    assert "red_drill.png" in content, "Иконка red_drill.png отсутствует в строке таблицы panel.js"
    assert "openUserSecurityModal" in content, "Вызов openUserSecurityModal отсутствует в panel.js"

    # Проверка: отдельная кнопка UAC в действиях удалена (все объединено в красной дрели)
    action_block = content[content.find('style="text-align: right;"'):content.find('style="text-align: right;"') + 300]
    assert 'btn-open-user-uac' not in action_block, "Лишняя кнопка UAC все еще присутствует в действиях"


def test_security_modal_module_exports() -> None:
    """Проверяет наличие модуля security_modal.js и экспортируемых функций."""
    modal_js = _WEBGUI_DIR / "tab_windows_admin" / "panel_users" / "security_modal.js"
    assert modal_js.exists(), f"Файл {modal_js} не найден"
    content = modal_js.read_text(encoding="utf-8")

    assert "openUserSecurityModal(" in content
    assert "handleSaveSecurityPolicies(" in content
    assert "handleChangePassword(" in content
    assert "launchWindowsSetting(" in content
    assert "initUserSecurityModalEvents(" in content


def test_user_uac_password_expired_models() -> None:
    """Проверяет поддержку поля password_expired в моделях конфигурации."""
    cfg = UserUacConfig(
        username="test_user",
        password_expired=True,
    )
    assert cfg.password_expired is True

    req = UserUacUpdateRequest(
        password_expired=True,
    )
    assert req.password_expired is True


@pytest.mark.asyncio
async def test_change_password_api_success() -> None:
    """Проверяет успешный вызов эндпоинта смены пароля пользователя."""
    mock_srv = MagicMock()
    mock_srv.engine.auth.reset_user_password.return_value = True

    with patch(
        "apps.windows.sdk.modules.accounts_identity.get_accounts_identity_service",
        return_value=mock_srv,
    ):
        payload = ChangePasswordRequest(new_password="NewSecurePass!2026")
        res = await change_account_password("test_user", payload)
        assert res["success"] is True
        assert res["username"] == "test_user"
        mock_srv.engine.auth.reset_user_password.assert_called_once_with("test_user", "NewSecurePass!2026")


@pytest.mark.asyncio
async def test_launch_setting_api_validation() -> None:
    """Проверяет валидацию разрешенных целей запуска системных апплетов."""
    # 1. Корректный URI ms-settings:signinoptions
    with patch("os.startfile") as mock_start:
        req = LaunchSettingRequest(target="ms-settings:signinoptions")
        res = await launch_system_setting(req)
        assert res["success"] is True
        assert res["target"] == "ms-settings:signinoptions"
        mock_start.assert_called_once_with("ms-settings:signinoptions")

    # 2. Недопустимая цель должна вызывать HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        bad_req = LaunchSettingRequest(target="powershell.exe -Command calc")
        await launch_system_setting(bad_req)
    assert exc_info.value.status_code == 400
