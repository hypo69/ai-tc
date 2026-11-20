# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Electron Engine Adapter
# =============================================================================
# Description:
#   Тесты для модуля ElectronEngineAdapter и интеграции запуска GUI в main.py.
#
# File: test_electron_engine_adapter.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from apps.windows.core.engine_adapter import ElectronEngineAdapter
import main


def test_electron_adapter_initialization() -> None:
    """Проверка инициализации адаптера и путей по умолчанию."""
    adapter = ElectronEngineAdapter()
    assert adapter.engine_id == "electron"
    assert adapter.app_dir.name == "electron"
    assert adapter.app_dir.exists()


def test_electron_adapter_find_binary() -> None:
    """Проверка обнаружения бинарного файла Electron в системе."""
    adapter = ElectronEngineAdapter()
    binary = adapter._find_electron_binary()
    assert binary is not None
    assert "electron" in binary.lower() or "npx" in binary.lower()


def test_electron_adapter_is_available() -> None:
    """Проверка готовности оболочки к запуску."""
    adapter = ElectronEngineAdapter()
    assert adapter.is_available() is True


def test_electron_adapter_launch_shell_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверка формирования команды и переменных окружения при запуске shell."""
    adapter = ElectronEngineAdapter()
    mock_popen = MagicMock()
    mock_popen.pid = 9999

    called_cmd = []
    called_env = {}

    def fake_popen(cmd, cwd=None, env=None, stdout=None, stderr=None):
        called_cmd.extend(cmd)
        called_env.update(env or {})
        return mock_popen

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    res = adapter.launch_shell(
        url="http://127.0.0.1:8000/tc#tab-about-system",
        profile_path=tmp_path / "profile",
        cache_path=tmp_path / "cache",
        force_fresh=False,
    )

    assert res["status"] == "launched"
    assert res["pid"] == 9999
    assert res["engine"] == "electron"
    assert called_env.get("AI_TC_BACKEND_URL") == "http://127.0.0.1:8000/tc#tab-about-system"
    assert "ELECTRON_RUN_AS_NODE" not in called_env


def test_main_parse_arguments_default_electron() -> None:
    """Проверка значения по умолчанию движка в аргументах main.py (по умолчанию electron)."""
    with patch("sys.argv", ["main.py"]):
        args = main.parse_arguments()
        assert args.engine == "electron"
        assert args.tab == "tab-about-system"


def test_main_parse_arguments_custom_tab_and_engine() -> None:
    """Проверка передачи вкладки и альтернативного движка в main.py."""
    with patch("sys.argv", ["main.py", "--engine", "browser", "--tab", "tab-network"]):
        args = main.parse_arguments()
        assert args.engine == "browser"
        assert args.tab == "tab-network"


def test_main_parse_arguments_engine_shortcuts() -> None:
    """Проверка флагов-ярлыков: --browser, --electron, --headless."""
    with patch("sys.argv", ["main.py", "--browser"]):
        args = main.parse_arguments()
        assert args.browser is True

    with patch("sys.argv", ["main.py", "--headless"]):
        args = main.parse_arguments()
        assert args.headless is True


def test_resolve_tab_url_formats() -> None:
    """Проверка корректной сборки URL с вкладками и панелями."""
    base = "http://127.0.0.1:8000/tc"
    assert main.resolve_tab_url(base) == "http://127.0.0.1:8000/tc#tab-about-system"
    assert main.resolve_tab_url(base, tab="tab-network") == "http://127.0.0.1:8000/tc#tab-network"
    assert main.resolve_tab_url(base, tab="tab-network", panel="ports") == "http://127.0.0.1:8000/tc#tab-network#ports"
    assert main.resolve_tab_url(base, tab="tab-process-manager") == "http://127.0.0.1:8000/tc#tab-processes-load-inspector"
