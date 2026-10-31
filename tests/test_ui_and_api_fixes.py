# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - UI and API Fixes Suite (TZ v3)
# =============================================================================
# Description:
#   Комплексный автоматический тестовый набор для проверки 16 исправлений
#   пользовательского интерфейса и REST API согласно ТЗ v3 (Часть 1 ТЗ).
#
# Usage Examples:
#   CLI:
#     python -m unittest tests/test_ui_and_api_fixes.py
#
# File: test_ui_and_api_fixes.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 14:23:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации 16 исправлений UI и API по ТЗ v3."""

import asyncio
import inspect
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestUIAndAPIFixes(unittest.TestCase):
    """Набор тестов для проверки 16 исправлений UI и API (ТЗ v3 Часть 1)."""

    def test_01_about_system_modal_routing(self) -> None:
        """1. Модальное окно профиля: отсутствие конфликта хэша SPA data-tab и перехват клика."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "about_system_tab" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл about_system_tab/index.html не найден")
        content = html_file.read_text(encoding="utf-8")
        self.assertNotIn('data-tab="pane-usr"', content, "Найдена нежелательная привязка data-tab='pane-usr'")
        self.assertIn('data-reg-tab="pane-usr"', content, "Отсутствует корректный атрибут data-reg-tab='pane-usr'")

        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "about_system_tab" / "main.js"
        self.assertTrue(js_file.is_file(), "Файл about_system_tab/main.js не найден")
        js_content = js_file.read_text(encoding="utf-8")
        self.assertIn("stopPropagation", js_content, "Отсутствует перехват всплытия stopPropagation()")

    def test_02_panel_telemetry_research_mapping(self) -> None:
        """2. Наличие маппинга tab-telemetry-research в PANEL_SQL_REGISTRY."""
        from apps.windows.api.routers.router_panel import PANEL_SQL_REGISTRY
        self.assertIn("tab-telemetry-research", PANEL_SQL_REGISTRY, "tab-telemetry-research не зарегистрирован")
        entry = PANEL_SQL_REGISTRY["tab-telemetry-research"]
        self.assertEqual(entry["table"], "sensor_polls")
        self.assertIn("SELECT", entry["sql"].upper())

    def test_03_system_logs_single_initialization(self) -> None:
        """3. Защита от дублирования панелей фильтрации в tab-system-logs."""
        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "system_logs_tab" / "main.js"
        self.assertTrue(js_file.is_file(), "Файл system_logs_tab/main.js не найден")
        js_content = js_file.read_text(encoding="utf-8")
        self.assertIn("isInitialized", js_content, "Отсутствует флаг защиты от повторной инициализации")

    def test_04_hardware_inspector_margins(self) -> None:
        """4. Наличие отступа px-3 у родительского контейнера hardware inspector."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "hardware_inspector" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл hardware_inspector/index.html не найден")
        content = html_file.read_text(encoding="utf-8")
        self.assertIn("px-3", content, "Отсутствует класс px-3 для отступа")

    def test_05_cpu_all_cores_rendering(self) -> None:
        """5. Рендеринг всех логических ядер CPU по длине logical_cores."""
        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "hardware_inspector" / "cpu_view.js"
        self.assertTrue(js_file.is_file(), "Файл cpu_view.js не найден")
        content = js_file.read_text(encoding="utf-8")
        self.assertIn("logical_cores", content, "Отсутствует цикл по logical_cores")

    def test_06_gpu_detailed_plotly_charts(self) -> None:
        """6. Детализация счетчиков GPU: VRAM, Copy Engine, 3D Subsystems."""
        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "hardware_inspector" / "gpu_view.js"
        self.assertTrue(js_file.is_file(), "Файл gpu_view.js не найден")
        content = js_file.read_text(encoding="utf-8")
        self.assertIn("vram", content.lower())
        self.assertIn("copy engine", content.lower())
        self.assertIn("3d subsystem", content.lower())

    def test_07_smart_temperature_parsing(self) -> None:
        """7. Извлечение SMART-температуры из атрибутов 190 и 194."""
        from apps.windows.api.routers.router_storage_load import extract_smart_temperature

        # Тест атрибута 194 (Temperature Celsius)
        disk_wdc = {
            "model": "WDC WD10EZEX",
            "smart_attributes": {
                194: {"raw": 37, "val": 63}
            }
        }
        self.assertEqual(extract_smart_temperature(disk_wdc), 37.0)

        # Тест атрибута 190 (Airflow Temperature)
        disk_toshiba = {
            "model": "TOSHIBA DT01ACA100",
            "smart_attributes": {
                190: {"raw": 42, "val": 58}
            }
        }
        self.assertEqual(extract_smart_temperature(disk_toshiba), 42.0)

    def test_08_speedtest_controls_alignment(self) -> None:
        """8. Выравнивание кнопки Speedtest через CSS-класс d-flex justify-content-start."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "speedtest" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл speedtest/index.html не найден")
        content = html_file.read_text(encoding="utf-8")
        self.assertIn("speedtest-controls-grid", content)
        self.assertIn("justify-content-start", content)

    def test_09_terminal_config_endpoint_and_styles(self) -> None:
        """9. Маршрут /terminal/config.json и использование var(--bs-body-color)."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "terminal" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл terminal/index.html не найден")
        content = html_file.read_text(encoding="utf-8")
        self.assertIn("var(--bs-body-color)", content)
        self.assertIn("/terminal/config.json", content)

    def test_10_wikillm_settings_subtab_and_save_button(self) -> None:
        """10. Пункт №6 Настройки WikiLLM в навигации и кнопка сохранения в футере рядом с Повторить."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "app_internals_tab" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл app_internals_tab/index.html не найден")
        content = html_file.read_text(encoding="utf-8")
        self.assertIn("6. Настройки WikiLLM", content)
        self.assertIn("wikillm-btn-save", content)
        self.assertIn("wikillm-btn-retry", content)

    def test_11_wikillm_async_background_enrichment(self) -> None:
        """11. Фоновое обогащение WikiLLM через asyncio.create_task при отсутствии описания."""
        from apps.windows.api.services.wikillm_service import WikiLLMService

        mock_storage = MagicMock()
        mock_storage.get_entity.return_value = None

        service = WikiLLMService(storage=mock_storage)

        async def run_test() -> None:
            # При первом запросе описание отсутствует -> запускается asyncio.create_task
            result = await service.get_event_description(4624, "Security", auto_enrich=True)
            self.assertIsNone(result, "При первом запросе должно возвращаться None до завершения фоновой задачи")
            # Даем фоновой таске отработать
            await asyncio.sleep(0.05)
            # При повторном запросе описание уже обогащено
            desc = await service.get_event_description(4624, "Security", auto_enrich=False)
            self.assertIsNotNone(desc)
            self.assertIn("4624", desc)

        asyncio.run(run_test())

    def test_12_sysmon_channel_inspection(self) -> None:
        """12. Проверка активности Sysmon через канал Windows Event Log win32evtlog."""
        from apps.windows.api.services.sysmon_inspector import SysmonInspector

        # Мокируем модуль win32evtlog, где канал существует
        mock_evtlog = MagicMock()
        mock_evtlog.EvtOpenChannelConfig.return_value = 12345

        inspector = SysmonInspector(evtlog_module=mock_evtlog)
        self.assertTrue(inspector.check_channel_via_win32evtlog())

        status = inspector.inspect()
        self.assertTrue(status.is_installed, "Sysmon должен считаться установленным при активном журнале")
        self.assertTrue(status.channel_active, "Канал Sysmon должен быть активен")
        self.assertNotEqual(status.status_text, "Не установлен")

    def test_13_firewall_panel_profiles_rendering(self) -> None:
        """13. Отрисовка статусов профилей Брандмауэра Domain, Private, Public."""
        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "defender" / "firewall.js"
        self.assertTrue(js_file.is_file(), "Файл defender/firewall.js не найден")
        content = js_file.read_text(encoding="utf-8")
        self.assertIn("fw-domain-status", content)
        self.assertIn("fw-private-status", content)
        self.assertIn("fw-public-status", content)
        self.assertIn("fw-rules-count", content)

    def test_14_cfa_allowed_apps_management(self) -> None:
        """14. Добавление и удаление разрешенных приложений CFA через API и модальное окно."""
        from apps.windows.sdk.modules.defender.core.cfa_manager import ControlledFolderAccessManager

        mock_svc = MagicMock()
        mock_svc._run_powershell_raw.return_value = ""

        cfa_mgr = ControlledFolderAccessManager(defender_service=mock_svc)
        success_add = cfa_mgr.add_allowed_application("C:\\Games\\Doom.exe")
        self.assertTrue(success_add)
        mock_svc._run_powershell_raw.assert_called_with('Add-MpPreference -ControlledFolderAccessAllowedApplications "C:\\Games\\Doom.exe"')

        success_rem = cfa_mgr.remove_allowed_application("C:\\Games\\Doom.exe")
        self.assertTrue(success_rem)
        mock_svc._run_powershell_raw.assert_called_with('Remove-MpPreference -ControlledFolderAccessAllowedApplications "C:\\Games\\Doom.exe"')

        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "defender" / "cfa.html"
        self.assertTrue(html_file.is_file(), "Файл defender/cfa.html не найден")
        html_content = html_file.read_text(encoding="utf-8")
        self.assertIn("cfaAddAppModal", html_content)
        self.assertIn("cfa-app-path-input", html_content)

    def test_15_internals_log_center_routing(self) -> None:
        """15. Лог-центр во Внутренней кухне: направить на /api/v1/internals/logs/app.log."""
        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "app_internals_tab" / "main.js"
        self.assertTrue(js_file.is_file(), "Файл app_internals_tab/main.js не найден")
        content = js_file.read_text(encoding="utf-8")
        self.assertIn("/api/v1/internals/logs/app.log", content)
        self.assertIn("app_logs_tab", content)

    def test_16_windows_backup_and_group_rollover(self) -> None:
        """16. Панель бэкапа (алиасы в router_panel.py) и динамический Rollover участников."""
        from apps.windows.api.routers.router_panel import PANEL_SQL_REGISTRY
        self.assertIn("panel-windows-backup", PANEL_SQL_REGISTRY)
        self.assertIn("windows_admin-backup", PANEL_SQL_REGISTRY)

        js_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "windows_admin_tab" / "main.js"
        self.assertTrue(js_file.is_file(), "Файл windows_admin_tab/main.js не найден")
        content = js_file.read_text(encoding="utf-8")
        self.assertIn("_handleGroupRollover", content)
        self.assertIn("/members", content)

    def test_17_telemetry_research_endpoints(self) -> None:
        """17. Регистрация и доступность роутов исследования телеметрии /apps/telemetry_research/*."""
        from apps.windows.analytics.server import init_router
        router = init_router()
        route_paths = [r.path for r in router.routes]
        self.assertIn("/apps/telemetry_research/sources", route_paths)
        self.assertIn("/apps/telemetry_research/run-research", route_paths)
        self.assertIn("/apps/telemetry_research/records", route_paths)

    def test_18_storage_wear_and_defender_syntax_integrity(self) -> None:
        """18. Корректность синтаксиса и экспорта функций в storage_wear_tab и defender_tab."""
        sw_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "storage_wear_tab" / "main.js"
        self.assertTrue(sw_file.is_file())
        sw_content = sw_file.read_text(encoding="utf-8")
        self.assertNotIn("matchedLetters.forEach(let =>", sw_content, "let не должен использоваться как идентификатор")
        self.assertIn("matchedLetters.forEach(letter =>", sw_content)

        def_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "defender_tab" / "main.js"
        self.assertTrue(def_file.is_file())
        def_content = def_file.read_text(encoding="utf-8")
        self.assertIn("window.renderFirewallProfileStatuses = renderFirewallProfileStatuses", def_content)

    def test_19_ai_modal_dialog_focus_and_timeouts(self) -> None:
        """19. Предотвращение блокировки WAI-ARIA aria-hidden и увеличенные таймауты загрузки промптов."""
        modal_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "ai_modal_dialog" / "main.js"
        self.assertTrue(modal_file.is_file())
        content = modal_file.read_text(encoding="utf-8")
        self.assertIn("hide.bs.modal", content)
        self.assertIn("document.activeElement.blur()", content)
        self.assertNotIn("safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(opts.tableType)}${panelQuery}`, {}, 4000)", content)


if __name__ == "__main__":
    unittest.main()

