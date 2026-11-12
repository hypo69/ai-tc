# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Roadmap TZ v18.0 Features Suite
# =============================================================================
# Description:
#   Комплексный автоматический тестовый набор для проверки всех 5 требований
#   технического задания v18.0 из директории roadmap.
#
# Usage Examples:
#   CLI:
#     python -m unittest tests/test_v18_features.py
#
# File: test_v18_features.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:03:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации требований ТЗ v18.0 (18.1 - 18.5)."""

import asyncio
from pathlib import Path
import unittest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestV18FeaturesSuite(unittest.TestCase):
    """Тестирование функционала технического задания v18.0."""

    def test_18_1_wikillm_settings_and_editor_ui(self) -> None:
        """18.1 Проверка настроек WikiLLM (db_path, генерация) и контейнера редактора."""
        html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "tab_app_internals" / "index.html"
        if not html_file.is_file():
            html_file = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "app_internals_tab" / "index.html"
        self.assertTrue(html_file.is_file(), "Файл tab_app_internals/index.html не найден")
        content = html_file.read_text(encoding="utf-8")

        self.assertIn('id="wikillm-cfg-db-path"', content)
        self.assertIn('id="wikillm-cfg-temperature"', content)
        self.assertIn('id="wikillm-cfg-context-window"', content)
        self.assertIn('id="wikillm-cfg-auto-index"', content)
        self.assertIn('id="wikillm_editor-container"', content)

        # Проверка API роутера WikiLLM
        from apps.windows.api.routers.router_wikillm_editor import get_wikillm_settings, save_wikillm_settings, WikiSettingsSchema
        settings = asyncio.run(get_wikillm_settings())
        settings_dict = settings.model_dump() if hasattr(settings, "model_dump") else dict(settings)
        self.assertIn("db_path", settings_dict)
        self.assertIn("temperature", settings_dict)

        updated = asyncio.run(save_wikillm_settings(WikiSettingsSchema(
            db_path="data/test_wikillm.db",
            temperature=0.7,
            context_window=4096,
            auto_indexing=True,
        )))
        self.assertEqual(updated.temperature, 0.7)
        self.assertEqual(updated.db_path, "data/test_wikillm.db")

    def test_18_2_heavy_telemetry_and_triggers(self) -> None:
        """18.2 Проверка триггерных режимов и последовательного запуска тяжелых коллекторов."""
        from apps.windows.telemetry.telemetry_config import get_trigger_mode, is_sequential_heavy_enabled, get_all_intervals
        trigger_mode = get_trigger_mode()
        self.assertIn(trigger_mode, ["ON_STARTUP", "ON_DEMAND", "ON_STARTUP_OR_DEMAND", "INTERVAL_BASED"])
        is_seq = is_sequential_heavy_enabled()
        self.assertIsInstance(is_seq, bool)

        intervals = get_all_intervals()
        self.assertIn("trigger_mode", intervals)
        self.assertIn("sequential_heavy_execution", intervals)

        # Проверка эндпоинта последовательного сбора
        from apps.windows.api.routers.router_telemetry_config import collect_heavy_sequentially
        res = asyncio.run(collect_heavy_sequentially())
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("results", res)

        # Проверка UI селекторов
        tc_html = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "tab_telemetry_control" / "index.html"
        if not tc_html.is_file():
            tc_html = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "telemetry_control_tab" / "index.html"
        self.assertTrue(tc_html.is_file())
        tc_content = tc_html.read_text(encoding="utf-8")
        self.assertIn('id="tc-ctrl-trigger-mode"', tc_content)
        self.assertIn('id="tc-ctrl-sequential-heavy"', tc_content)

    def test_18_3_agy_key_pool_management(self) -> None:
        """18.3 Проверка роутера и UI управления пулом ключей Google Antigravity (AGY)."""
        from apps.windows.api.routers.router_keys import (
            list_agy_keys,
            add_agy_key,
            delete_agy_key,
            reset_agy_keys,
            test_agy_key,
            AGYKeyPayload,
        )
        # Добавление ключа
        add_res = asyncio.run(add_agy_key(AGYKeyPayload(
            name="test_v18_agy_key",
            key="AIzaSyDummyAGYKey1234567890",
        )))
        self.assertEqual(add_res.get("status"), "success")

        # Получение ключей
        keys_list = asyncio.run(list_agy_keys())
        self.assertTrue(any(k.get("name") == "test_v18_agy_key" for k in keys_list))

        # Тестирование ключа
        test_res = asyncio.run(test_agy_key({"key_name": "test_v18_agy_key"}))
        self.assertTrue(test_res.get("valid"))

        # Сброс квот
        reset_res = asyncio.run(reset_agy_keys())
        self.assertEqual(reset_res.get("status"), "success")

        # Удаление тестового ключа
        del_res = asyncio.run(delete_agy_key("test_v18_agy_key"))
        self.assertEqual(del_res.get("status"), "success")

        # Проверка UI в tab_models/index.html
        models_html = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "tab_models" / "index.html"
        self.assertTrue(models_html.is_file())
        models_content = models_html.read_text(encoding="utf-8")
        self.assertIn('id="agy-keys-table"', models_content)
        self.assertIn('id="btn-agy-add-key"', models_content)
        self.assertIn('id="btn-agy-refresh-keys"', models_content)

    def test_18_4_taskbar_window_copilot(self) -> None:
        """18.4 Проверка ИИ-Copilot для таблицы открытых окон."""
        from apps.windows.sdk.modules.taskbar.router import get_window_copilot
        res = asyncio.run(get_window_copilot(
            hwnd=12345,
            title="Visual Studio Code",
            process_name="code.exe",
            pid=9999,
        ))
        self.assertEqual(res.get("hwnd"), 12345)
        self.assertEqual(res.get("risk_level"), "SAFE")
        self.assertIn("code.exe", res.get("ai_explanation", ""))
        self.assertIn("recommended_action", res)

        # Проверка UI
        tb_html = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "taskbar_tab" / "index.html"
        self.assertTrue(tb_html.is_file())
        tb_content = tb_html.read_text(encoding="utf-8")
        self.assertIn('id="taskbarWindowAiCopilotModal"', tb_content)

        tb_js = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "taskbar_tab" / "main.js"
        self.assertTrue(tb_js.is_file())
        tb_js_content = tb_js.read_text(encoding="utf-8")
        self.assertIn("aiCopilot", tb_js_content)
        self.assertIn("openTaskbarWindowCopilotModal", tb_js_content)

    def test_18_5_windows_admin_principal_copilot(self) -> None:
        """18.5 Проверка замены досье Principal на интерактивный ИИ-Ассистент."""
        from apps.windows.sdk.modules.accounts_identity.router import get_principal_copilot, explain_identity
        import getpass
        cur_user = getpass.getuser()

        copilot_res = asyncio.run(get_principal_copilot(cur_user))
        self.assertIn("risk_rating", copilot_res)
        self.assertIn("ai_analysis", copilot_res)
        self.assertIn("recommended_actions", copilot_res)
        self.assertIsInstance(copilot_res["recommended_actions"], list)

        # Проверка обогащенного Principal
        principal = asyncio.run(explain_identity(cur_user))
        self.assertIsNotNone(principal.ai_copilot)
        self.assertEqual(principal.ai_copilot.get("principal"), principal.name)

        # Проверка UI
        admin_html = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "windows_admin_tab" / "index.html"
        self.assertTrue(admin_html.is_file())
        admin_content = admin_html.read_text(encoding="utf-8")
        self.assertIn('Windows Admin AI Copilot Modal', admin_content)
        self.assertIn('id="dossier-ai-copilot-pane"', admin_content)

        admin_js = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "windows_admin_tab" / "main.js"
        self.assertTrue(admin_js.is_file())
        admin_js_content = admin_js.read_text(encoding="utf-8")
        self.assertIn("dossier-ai-copilot-content", admin_js_content)
        self.assertIn("recommended_actions", admin_js_content)


if __name__ == "__main__":
    unittest.main()

