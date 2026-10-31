# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests for Cloudflared Monitor FastAPI Router
# =============================================================================
# Description:
#   Модульные тесты для REST API эндпоинтов apps/cloudflared_monitor/router.py.
#   Тестирование /status, /logs, /metrics, /diagnostic, /test-endpoint и прав админа.
#
# File: test_router_cloudflared_monitor.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""Модульные тесты FastAPI роутера Cloudflared Monitor."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.cloudflared_monitor.router import get_state, init_router


class TestCloudflaredMonitorRouter(unittest.TestCase):
    """Набор тестов для эндпоинтов роутера Cloudflared Monitor."""

    def setUp(self) -> None:
        """Инициализация тестового клиента FastAPI."""
        self.app = FastAPI()
        self.app.include_router(init_router())
        self.client = TestClient(self.app)

    def test_init_router(self) -> None:
        """Проверка корректной инициализации APIRouter."""
        router = init_router()
        self.assertIsNotNone(router)
        self.assertEqual(router.prefix, "/api/cloudflared")

    def test_get_status(self) -> None:
        """Проверка эндпоинта GET /api/cloudflared/status."""
        response = self.client.get("/api/cloudflared/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_running", data)
        self.assertIn("has_token", data)
        self.assertIn("public_url", data)
        self.assertIn("health_score", data)

    def test_get_logs(self) -> None:
        """Проверка эндпоинта GET /api/cloudflared/logs."""
        response = self.client.get("/api/cloudflared/logs?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("logs", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["logs"], list)

    def test_get_metrics(self) -> None:
        """Проверка эндпоинта GET /api/cloudflared/metrics."""
        response = self.client.get("/api/cloudflared/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("process", data)
        self.assertIn("network", data)
        self.assertIn("log_stats", data)

    def test_get_diagnostic(self) -> None:
        """Проверка эндпоинта GET /api/cloudflared/diagnostic."""
        response = self.client.get("/api/cloudflared/diagnostic")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("health_score", data)
        self.assertIn("status", data)
        self.assertIn("anomalies", data)
        self.assertIn("recommendations", data)

    def test_test_endpoint(self) -> None:
        """Проверка эндпоинта POST /api/cloudflared/test-endpoint."""
        response = self.client.post("/api/cloudflared/test-endpoint")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("url", data)
        self.assertIn("is_reachable", data)

    def test_lifecycle_admin_auth_forbidden(self) -> None:
        """Проверка отклонения запроса жизненного цикла при отсутствии прав админа."""
        with patch("apps.cloudflared_monitor.router.require_admin_user", side_effect=HTTPException(status_code=403, detail="Admin required")):
            res_start = self.client.post("/api/cloudflared/start")
            self.assertEqual(res_start.status_code, 403)

            res_stop = self.client.post("/api/cloudflared/stop")
            self.assertEqual(res_stop.status_code, 403)

            res_restart = self.client.post("/api/cloudflared/restart")
            self.assertEqual(res_restart.status_code, 403)

    def test_lifecycle_authorized_success(self) -> None:
        """Проверка успешного управления демоном туннеля администратором."""
        state = get_state()
        with patch("apps.cloudflared_monitor.router.require_admin_user", return_value=None):
            with patch.object(state, "start_tunnel", return_value=(True, "Запущен")):
                res_start = self.client.post("/api/cloudflared/start")
                self.assertEqual(res_start.status_code, 200)
                self.assertTrue(res_start.json()["success"])

            with patch.object(state, "stop_tunnel", return_value=(True, "Остановлен")):
                res_stop = self.client.post("/api/cloudflared/stop")
                self.assertEqual(res_stop.status_code, 200)
                self.assertTrue(res_stop.json()["success"])

            with patch.object(state, "restart_tunnel", return_value=(True, "Перезапущен")):
                res_restart = self.client.post("/api/cloudflared/restart")
                self.assertEqual(res_restart.status_code, 200)
                self.assertTrue(res_restart.json()["success"])


if __name__ == "__main__":
    unittest.main()
