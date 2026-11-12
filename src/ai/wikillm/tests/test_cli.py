# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm Tests - Test Cli
# =============================================================================
# Description:
#   Тесты для CLI интерфейса и конфигуратора WikiLLM.
#
# Usage Examples:
#   Python API:
#     from src.ai.wikillm.tests.test_cli import test_config_defaults
#
#     res = test_config_defaults()
#
# File: test_cli.py
# Project: ai-windows-admin
# Package: src.ai.wikillm.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Тесты для CLI интерфейса и конфигуратора WikiLLM."""

import argparse
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from src.ai.wikillm.cli import _async_cli_main
from src.ai.wikillm.config import WikiLLMConfig, load_config


def test_config_defaults() -> None:
    """Проверка загрузки конфигурации по умолчанию."""
    cfg = load_config(None)
    assert cfg.database_path == "data/windows_wikillm/knowledge.db"
    assert cfg.min_confidence_threshold == 0.70
    assert cfg.enable_semantic_search is True


@pytest.mark.asyncio
async def test_cli_search_and_stats(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Проверка команд search и stats в CLI."""
    db_file = str(tmp_path / "cli_test.db")
    args_stats = argparse.Namespace(command="stats", db=db_file)
    await _async_cli_main(args_stats)
    captured = capsys.readouterr()
    assert "lookup_stats" in captured.out

    args_search = argparse.Namespace(command="search", query="test", limit=5, db=db_file)
    await _async_cli_main(args_search)
    captured = capsys.readouterr()
    assert "Найдено результатов" in captured.out


@pytest.mark.asyncio
async def test_cli_index_code(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Проверка команды index-code в CLI."""
    db_file = str(tmp_path / "code_test.db")
    test_code_dir = tmp_path / "code_sample"
    test_code_dir.mkdir()
    sample_file = test_code_dir / "sample.py"
    sample_file.write_text("class Demo:\n    '''Демо класс.'''\n    def run(self):\n        pass\n", encoding="utf-8")
    
    args = argparse.Namespace(command="index-code", path=str(test_code_dir), db=db_file)
    await _async_cli_main(args)
    captured = capsys.readouterr()
    assert "Успешно проиндексировано" in captured.out


