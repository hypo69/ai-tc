# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Net User Tool
# =============================================================================
# Description:
#   Модульные тесты для инструмента управления пользователями NetUserTool
#   (просмотр, настройка флагов пароля, блокировка и удаление через net user).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_net_user_tool.py -v
#
# File: test_net_user_tool.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты для инструмента управления локальными пользователями NetUserTool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from apps.windows.sdk.core.models import RiskLevel
from apps.windows.sdk.core.tools.registry import ToolRegistry
from apps.windows.sdk.core.tools.system_tools import register_system_tools
from apps.windows.sdk.core.tools.net_user_tool import NetUserTool


MOCK_NET_USER_LIST = """
User accounts for \\DELL-VOSTRO

-------------------------------------------------------------------------------
Administrator            DefaultAccount           Guest                    
onela                    user                     WDAGUtilityAccount       
The command completed successfully.
"""

MOCK_NET_USER_GET = """
User name                    user
Full Name                    Test User
Comment                      Temporary account
Account active               Yes
Account expires              Never
Password last set            20/10/2026 12:00:00
Password expires             Never
Password changeable          20/10/2026 12:00:00
Password required            No
User may change password     Yes
Workstations allowed         All
Local Group Memberships      *Users                
Global Group memberships     *None                 
The command completed successfully.
"""


@pytest.fixture
def registry() -> ToolRegistry:
    """Фикстура инициализированного реестра инструментов."""
    reg = ToolRegistry()
    register_system_tools(reg)
    return reg


def test_net_user_tool_registered(registry: ToolRegistry) -> None:
    """Проверяет регистрацию NetUserTool в системном реестре."""
    assert registry.has("net_user")
    tool = registry.get("net_user")
    assert tool is not None
    assert isinstance(tool, NetUserTool)
    assert tool.name == "net_user"
    assert "net user" in tool.description.lower()


@pytest.mark.asyncio
async def test_net_user_list_parsing() -> None:
    """Проверяет получение и разбор списка локальных пользователей."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = MOCK_NET_USER_LIST
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(action="list")
        assert result.status == "ok"
        assert result.risk_level == RiskLevel.SAFE
        assert "users" in result.data
        users = result.data["users"]
        assert "Administrator" in users
        assert "user" in users
        assert "onela" in users


@pytest.mark.asyncio
async def test_net_user_get_parsing() -> None:
    """Проверяет получение детальных атрибутов пользователя и парсинг флагов."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = MOCK_NET_USER_GET
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(action="get", username="user")
        assert result.status == "ok"
        assert result.risk_level == RiskLevel.SAFE
        info = result.data
        assert info.get("User name") == "user"
        assert info.get("Account active") == "Yes"
        assert info.get("Password required") == "No"
        assert "*Users" in info.get("Local Group Memberships", "")


@pytest.mark.asyncio
async def test_net_user_set_password_required() -> None:
    """Проверяет команду установки флага обязательности пароля (/passwordreq:yes)."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(action="set_password_required", username="user", password_required=True)
        assert result.status == "ok"
        assert result.command_executed == 'net user user /passwordreq:yes'
        assert result.risk_level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_net_user_set_active_blocking() -> None:
    """Проверяет блокировку учетной записи (/active:no)."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(action="set_active", username="user", active=False)
        assert result.status == "ok"
        assert result.command_executed == 'net user user /active:no'
        assert result.risk_level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_net_user_delete_destructive() -> None:
    """Проверяет опасную команду безвозвратного удаления пользователя (/delete)."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(action="delete", username="user", confirm_destructive=True)
        assert result.status == "ok"
        assert result.command_executed == 'net user user /delete'
        assert result.risk_level == RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_net_user_modify_multiple_parameters() -> None:
    """Проверяет пакетное изменение параметров net user (action='modify')."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(
            action="modify",
            username="admin_user",
            active=True,
            password_required=False,
            password_changeable=True,
            logon_password_change=False,
            expires="never",
            full_name="Главный Администратор",
            comment="Основной аккаунт",
            domain=True,
        )
        assert result.status == "ok"
        cmd = result.command_executed
        assert "net user admin_user" in cmd
        assert "/active:yes" in cmd
        assert "/passwordreq:no" in cmd
        assert "/passwordchg:yes" in cmd
        assert "/logonpasswordchg:no" in cmd
        assert "/expires:never" in cmd
        assert '/fullname:"Главный Администратор"' in cmd
        assert '/comment:"Основной аккаунт"' in cmd
        assert "/domain" in cmd


@pytest.mark.asyncio
async def test_net_user_individual_parameter_actions() -> None:
    """Проверяет отдельные команды установки параметров учетной записи."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        # 1. set_password_changeable
        res1 = await tool.execute(action="set_password_changeable", username="user", password_changeable=False)
        assert res1.status == "ok"
        assert res1.command_executed == "net user user /passwordchg:no"

        # 2. set_logon_password_change
        res2 = await tool.execute(action="set_logon_password_change", username="user", logon_password_change=True)
        assert res2.status == "ok"
        assert res2.command_executed == "net user user /logonpasswordchg:yes"

        # 3. set_expires
        res3 = await tool.execute(action="set_expires", username="user", expires="12/31/2026")
        assert res3.status == "ok"
        assert res3.command_executed == "net user user /expires:12/31/2026"

        # 4. set_fullname
        res4 = await tool.execute(action="set_fullname", username="user", full_name="Иван Иванов")
        assert res4.status == "ok"
        assert res4.command_executed == 'net user user /fullname:"Иван Иванов"'

        # 5. set_comment
        res5 = await tool.execute(action="set_comment", username="user", comment="Тестовый оператор")
        assert res5.status == "ok"
        assert res5.command_executed == 'net user user /comment:"Тестовый оператор"'


@pytest.mark.asyncio
async def test_net_user_create_with_full_options() -> None:
    """Проверяет создание пользователя с расширенными параметрами."""
    tool = NetUserTool()
    with patch("asyncio.to_thread") as mock_exec:
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.stdout = "The command completed successfully."
        proc_mock.stderr = ""
        mock_exec.return_value = proc_mock

        result = await tool.execute(
            action="create",
            username="new_operator",
            password="SecurePassword123!",
            active=True,
            password_required=True,
            password_changeable=False,
            full_name="Оператор Системы",
            comment="Учетная запись дежурного",
            expires="never",
        )
        assert result.status == "ok"
        cmd = result.command_executed
        assert "net user new_operator SecurePassword123! /add" in cmd
        assert "/active:yes" in cmd
        assert "/passwordreq:yes" in cmd
        assert "/passwordchg:no" in cmd
        assert '/fullname:"Оператор Системы"' in cmd
        assert '/comment:"Учетная запись дежурного"' in cmd
        assert "/expires:never" in cmd


