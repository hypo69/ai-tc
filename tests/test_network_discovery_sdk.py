# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Network Discovery SDK & API
# =============================================================================
# Description:
#   Модульные тесты функциональности сетевого обнаружения Windows,
#   управления категориями профилей (Public / Private) и соответствующих
#   REST API эндпоинтов.
#
# File: test_network_discovery_sdk.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 05:35:00
# =============================================================================

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from apps.windows.sdk import windows_sdk, NetworkDiscoveryManager, WindowsNetworkDiscovery
from apps.windows.sdk.modules.network.discovery import NetworkDiscoveryManager as DirectNDM
from apps.windows.api.server import create_app


def test_network_discovery_exports():
    """Проверка доступности экспорта NetworkDiscoveryManager и фасада в Windows SDK."""
    assert NetworkDiscoveryManager is not None
    assert WindowsNetworkDiscovery is NetworkDiscoveryManager
    assert isinstance(windows_sdk.modules.network_discovery, NetworkDiscoveryManager)


def test_inspect_mocked():
    """Тест комплексной инспекции состояния сетевого обнаружения с моком PowerShell."""
    mgr = NetworkDiscoveryManager()

    mock_profiles = [
        {
            "Name": "Network",
            "InterfaceAlias": "Ethernet",
            "InterfaceIndex": 3,
            "NetworkCategory": "Public",
            "IPv4Connectivity": "Internet",
        }
    ]
    mock_services = {
        "FDResPub": {"Name": "FDResPub", "Status": "Running", "StartType": "Automatic"},
        "fdPHost": {"Name": "fdPHost", "Status": "Running", "StartType": "Manual"},
    }
    mock_firewall = {
        "total_rules": 4,
        "enabled_rules": 4,
        "is_enabled": True,
        "group_identifier": "@FirewallAPI.dll,-32752",
    }

    with patch.object(mgr, "get_connection_profiles", return_value=mock_profiles), \
         patch.object(mgr, "get_services_state", return_value=mock_services), \
         patch.object(mgr, "get_firewall_rules_state", return_value=mock_firewall):

        status = mgr.inspect()
        assert status["status"] == "ok"
        assert status["is_discovery_enabled"] is True
        assert status["current_category"] == "Public"
        assert status["primary_interface_index"] == 3
        assert status["primary_profile"]["InterfaceAlias"] == "Ethernet"


def test_set_network_category_invalid():
    """Тест валидации недопустимого имени категории."""
    mgr = NetworkDiscoveryManager()
    res = mgr.set_network_category("UnknownCategory", interface_index=3)
    assert res["status"] == "error"
    assert "Недопустимая категория" in res["message"]


def test_set_network_category_success():
    """Тест успешного переключения категории сетевого профиля."""
    mgr = NetworkDiscoveryManager()

    with patch.object(mgr, "_run_ps_command", return_value=(0, "OK", "")):
        res = mgr.set_network_category("Private", interface_index=5)
        assert res["status"] == "ok"
        assert res["category"] == "Private"
        assert res["interface_index"] == 5


def test_enable_network_discovery():
    """Тест операции включения сетевого обнаружения."""
    mgr = NetworkDiscoveryManager()

    mock_inspect = {
        "status": "ok",
        "is_discovery_enabled": True,
        "current_category": "Private",
        "primary_interface_index": 3,
    }

    with patch.object(mgr, "_run_ps_command", return_value=(0, "OK", "")), \
         patch.object(mgr, "set_network_category", return_value={"status": "ok"}), \
         patch.object(mgr, "inspect", return_value=mock_inspect):

        res = mgr.enable(interface_index=3, set_private=True)
        assert res["status"] == "ok"
        assert "Сетевое обнаружение успешно включено" in res["message"]
        assert len(res["actions"]) > 0
        assert res["state"]["is_discovery_enabled"] is True


def test_disable_network_discovery():
    """Тест операции отключения сетевого обнаружения."""
    mgr = NetworkDiscoveryManager()

    mock_inspect = {
        "status": "ok",
        "is_discovery_enabled": False,
        "current_category": "Public",
        "primary_interface_index": 3,
    }

    with patch.object(mgr, "_run_ps_command", return_value=(0, "OK", "")), \
         patch.object(mgr, "set_network_category", return_value={"status": "ok"}), \
         patch.object(mgr, "inspect", return_value=mock_inspect):

        res = mgr.disable(interface_index=3, set_public=True)
        assert res["status"] == "ok"
        assert "Сетевое обнаружение успешно отключено" in res["message"]
        assert res["state"]["is_discovery_enabled"] is False


@pytest.fixture
def api_client():
    """Фикстура создания тестового клиента FastAPI приложения."""
    app = create_app()
    return TestClient(app)


def test_api_network_profile_endpoints(api_client):
    """Тестирование REST эндпоинтов управления сетевым профилем."""
    mock_inspect_data = {
        "status": "ok",
        "is_discovery_enabled": False,
        "current_category": "Public",
        "primary_interface_index": 3,
        "primary_profile": {"Name": "Ethernet", "InterfaceIndex": 3},
        "profiles": [{"Name": "Ethernet", "InterfaceIndex": 3, "NetworkCategory": "Public"}],
        "services": {},
        "firewall": {},
    }

    # 1. GET /api/v1/system/network-profile
    with patch.object(NetworkDiscoveryManager, "inspect", return_value=mock_inspect_data):
        resp = api_client.get("/api/v1/system/network-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["current_category"] == "Public"
        assert data["is_discovery_enabled"] is False

    # 2. POST /api/v1/system/network-profile/category
    with patch.object(NetworkDiscoveryManager, "set_network_category", return_value={
        "status": "ok",
        "interface_index": 3,
        "category": "Private",
        "message": "Успешно",
    }):
        resp = api_client.post(
            "/api/v1/system/network-profile/category",
            json={"category": "Private", "interface_index": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["category"] == "Private"

    # 3. POST /api/v1/system/network-discovery/toggle
    with patch.object(NetworkDiscoveryManager, "enable", return_value={
        "status": "ok",
        "message": "Включено",
        "actions": ["Правила активированы"],
        "state": {"is_discovery_enabled": True, "current_category": "Private"},
    }):
        resp = api_client.post(
            "/api/v1/system/network-discovery/toggle",
            json={"enabled": True, "set_category": "Private", "interface_index": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["is_discovery_enabled"] is True
        assert data["current_category"] == "Private"

