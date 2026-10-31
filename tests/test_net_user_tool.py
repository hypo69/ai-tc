# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Net User Tool
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
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 17:15:00
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

