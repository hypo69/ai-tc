# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests for Cloudflared Monitor State & Core Logic
# =============================================================================
# Description:
#   Модульные тесты для CloudflaredState, анализа процессов, парсинга логов,
#   опроса эндпоинта kino.davidka.net и эвристической/ИИ диагностики.
#
# File: test_cloudflared_monitor.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""Модульные тесты ядра монитора Cloudflared и диагностики."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.cloudflared_monitor.src.state import (
    CloudflaredAnomaly,
    CloudflaredDiagnosticReport,
    CloudflaredLogEntry,
    CloudflaredProcessInfo,
    CloudflaredState,
    EndpointHealth,
)


class TestCloudflaredState(unittest.TestCase):
    """Набор тестов для менеджера состояния CloudflaredState."""

    def setUp(self) -> None:
        """Подготовка изолированной тестовой среды."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.log_file = self.project_root / "logs" / "cloudflared.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.state = CloudflaredState(
            project_root=self.project_root,
            public_url="https://kino.davidka.net",
            log_file_rel="logs/cloudflared.log",
        )

    def tearDown(self) -> None:
        """Очистка временных файлов."""
        self.temp_dir.cleanup()

    def test_initial_state(self) -> None:
        """Проверка начальных значений свежесозданного CloudflaredState."""
        self.assertFalse(self.state.process.is_running)
        self.assertEqual(self.state.public_url, "https://kino.davidka.net")
        self.assertEqual(len(self.state.logs), 0)
        self.assertEqual(self.state.total_errors_in_log, 0)

    def test_parse_log_line_standard_iso(self) -> None:
        """Проверка разбора строки лога стандартного ISO формата с ошибкой."""
        line = "2026-10-30T10:40:00Z ERR Connection lost with edge server connIndex=0"
        entry = self.state.parse_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.connection_id, "0")
        self.assertIn("Connection lost", entry.message)

    def test_parse_log_line_info(self) -> None:
        """Проверка разбора информационного сообщения туннеля."""
        line = "2026-10-30T10:40:05Z INF Registered tunnel connection connIndex=1 location=FRA"
        entry = self.state.parse_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.connection_id, "1")

    def test_parse_log_line_empty(self) -> None:
        """Проверка, что пустые строки возвращают None."""
        self.assertIsNone(self.state.parse_log_line(""))
        self.assertIsNone(self.state.parse_log_line("   \n"))

    def test_tail_logs(self) -> None:
        """Проверка чтения хвоста журнала и подсчета ошибок/предупреждений."""
        log_content = (
            "2026-10-30T10:40:00Z INF Starting tunnel\n"
            "2026-10-30T10:40:01Z INF Registered tunnel connection connIndex=0\n"
            "2026-10-30T10:40:02Z WRN High latency to origin\n"
            "2026-10-30T10:40:03Z ERR Failed to proxy request connIndex=0\n"
        )
        self.log_file.write_text(log_content, encoding="utf-8")

        entries = self.state.tail_logs(limit=10)
        self.assertEqual(len(entries), 4)
        self.assertEqual(self.state.total_errors_in_log, 1)
        self.assertEqual(self.state.total_warnings_in_log, 1)
        self.assertGreaterEqual(self.state.active_connections_count, 1)

    def test_check_token_missing(self) -> None:
        """Проверка обнаружения отсутствия токена в .env."""
        has_token = self.state.check_token()
        self.assertFalse(has_token)
        self.assertEqual(self.state.token_preview, "Missing")

    def test_check_token_present(self) -> None:
        """Проверка считывания валидного токена из .env."""
        env_path = self.project_root / ".env"
        env_path.write_text("CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiMTIzNDU2Nzg5MCJ9\n", encoding="utf-8")

        has_token = self.state.check_token()
        self.assertTrue(has_token)
        self.assertTrue(self.state.token_preview.startswith("eyJ"))

    def test_evaluate_diagnostics_healthy(self) -> None:
        """Проверка оценки здоровья туннеля в оптимальном состоянии."""
        self.state.exe_path = "C:/mock/cloudflared.exe"
        self.state.has_token = True
        self.state.process = CloudflaredProcessInfo(
            is_running=True, pid=1234, cpu_percent=2.5, memory_mb=45.0
        )
        self.state.endpoint = EndpointHealth(
            url="https://kino.davidka.net",
            is_reachable=True,
            status_code=200,
            response_time_ms=85.0,
        )
        self.state.total_errors_in_log = 0

        report = self.state.evaluate_diagnostics()
        self.assertEqual(report.status, "HEALTHY")
        self.assertGreaterEqual(report.health_score, 85)
        self.assertEqual(len(report.anomalies), 0)

    def test_evaluate_diagnostics_unhealthy(self) -> None:
        """Проверка обнаружения критического состояния туннеля."""
        self.state.exe_path = None
        self.state.has_token = False
        self.state.process = CloudflaredProcessInfo(is_running=False)
        self.state.endpoint = EndpointHealth(is_reachable=False)

        report = self.state.evaluate_diagnostics()
        self.assertIn(report.status, ("CRITICAL", "OFFLINE"))
        self.assertLess(report.health_score, 50)
        self.assertGreater(len(report.anomalies), 0)
        self.assertGreater(len(report.recommendations), 0)


if __name__ == "__main__":
    unittest.main()
