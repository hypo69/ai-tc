# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - LAN Discovery API
# =============================================================================
# Description:
#   Модульные тесты эндпоинтов автоматического обнаружения компьютеров в LAN,
#   опроса подсетей, кеша соседей ядра и проверки портов узла.
#
# File: test_lan_discovery_api.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 18:35:00
# =============================================================================

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.sdk.modules.network import router
from apps.windows.sdk.modules.network.lan_scanner import LanDevice


@pytest.fixture
def api_client():
    """Фикстура создания тестового клиента FastAPI приложения."""
    app = create_app()
    return TestClient(app)


def test_get_subnets(api_client):
    """Тест эндпоинта /api/network/subnets."""
    mock_ifaces = [{'name': 'Ethernet', 'ip': '192.168.1.100', 'cidr': '192.168.1.0/24'}]
    mock_gateways = {'192.168.1.1'}

    with patch.object(router._lan_scanner, "get_local_interfaces_info", return_value=mock_ifaces), \
         patch.object(router._lan_scanner, "get_default_gateways", return_value=mock_gateways):
        resp = api_client.get("/api/network/subnets")
        assert resp.status_code == 200
        data = resp.json()
        assert "subnets" in data
        assert "gateways" in data
        assert len(data["subnets"]) == 1
        assert data["subnets"][0]["cidr"] == "192.168.1.0/24"
        assert "192.168.1.1" in data["gateways"]


def test_get_devices_cache(api_client):
    """Тест эндпоинта /api/network/devices (чтение кеша соседей)."""
    mock_devs = [
        LanDevice(
            ip="192.168.1.1",
            hostname="router.lan",
            mac="00:11:22:33:44:55",
            vendor="MikroTik",
            state="Online",
            is_gateway=True,
            is_local=False,
            discovery_methods=["arp_cache"],
        ),
        LanDevice(
            ip="192.168.1.50",
            hostname="workstation-pc",
            mac="00:22:33:44:55:66",
            vendor="Dell Inc",
            state="Online",
            is_gateway=False,
            is_local=True,
            discovery_methods=["local_interface"],
        ),
    ]

    with patch.object(router._lan_scanner, "discover_devices", return_value=mock_devs):
        resp = api_client.get("/api/network/devices?scan=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["devices"]) == 2
        assert data["devices"][0]["ip"] == "192.168.1.1"
        assert data["devices"][0]["is_gateway"] is True
        assert data["devices"][1]["hostname"] == "workstation-pc"


def test_post_devices_scan(api_client):
    """Тест эндпоинта /api/network/devices/scan (активное глубокое сканирование)."""
    mock_devs = [
        LanDevice(
            ip="192.168.1.10",
            hostname="printer.lan",
            mac="00:33:44:55:66:77",
            vendor="Hewlett Packard",
            state="Online",
            discovery_methods=["arp_sweep"],
            latency_ms=1.5,
        )
    ]

    with patch.object(router._lan_scanner, "discover_devices", return_value=mock_devs):
        resp = api_client.post("/api/network/devices/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["total"] == 1
        assert data["devices"][0]["ip"] == "192.168.1.10"
        assert data["devices"][0]["vendor"] == "Hewlett Packard"


def test_probe_device_ports(api_client):
    """Тест эндпоинта экспресс-проверки портов /api/network/devices/probe."""
    resp = api_client.get("/api/network/devices/probe?ip=127.0.0.1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "127.0.0.1"
    assert "open_ports" in data
    assert "details" in data
    assert isinstance(data["open_ports"], list)
    assert isinstance(data["details"], list)
    assert len(data["details"]) == 8  # SMB, RDP, HTTP, HTTPS, SSH, WinRM, WSD, NetBIOS

