# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper Tests - Storage
# =============================================================================
# Description:
#   Модульные тесты для подсистемы хранения базы знаний кода.
#
# File: test_storage.py
# Project: ai-windows-admin
# Package: apps.code_helper.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты менеджера хранения CodeHelperStorage."""

from pathlib import Path
import pytest
from apps.code_helper.models import (
    CodeChunk,
    CodeSymbol,
    DiagnosticConclusion,
    IndexStats,
)
from apps.code_helper.storage import CodeHelperStorage


def test_storage_sqlite_operations(tmp_path: Path) -> None:
    """Тестирование сохранения и выборки индексов, чанков и символов."""
    db_file = tmp_path / "test_code.db"
    storage = CodeHelperStorage(
        config={
            "storage": {
                "engine": "sqlite",
                "sqlite": {"path": str(db_file)},
                "hostinger": {},
            }
        }
    )

    assert storage.active_engine == "sqlite"

    stats = IndexStats(
        name="test_index",
        project_root=str(tmp_path),
        total_files=2,
        total_chunks=2,
        total_symbols=1,
        elapsed_seconds=0.15,
        updated_at="2026-11-01 12:00:00",
        storage_engine="sqlite",
    )

    chunks = [
        CodeChunk(
            chunk_id="test.py::func_a:1",
            index_name="test_index",
            file_path="test.py",
            symbol_name="func_a",
            symbol_type="function",
            start_line=1,
            end_line=5,
            content="def func_a(): return 42",
            signature="def func_a() -> int",
            snippet="return 42",
            content_hash="hash123",
            updated_at="2026-11-01 12:00:00",
        )
    ]

    symbols = [
        CodeSymbol(
            symbol_id="test.py::func_a",
            index_name="test_index",
            symbol="func_a",
            short_name="func_a",
            symbol_type="function",
            file_path="test.py",
            signature="def func_a() -> int",
            docstring="Тестовая функция",
            start_line=1,
            end_line=5,
            related_symbols=[],
            snippet="return 42",
            updated_at="2026-11-01 12:00:00",
        )
    ]

    storage.save_index(stats, chunks, symbols)

    indexes = storage.list_indexes()
    assert len(indexes) == 1
    assert indexes[0]["name"] == "test_index"

    found_chunks = storage.search_chunks("func_a", index_name="test_index")
    assert len(found_chunks) == 1
    assert found_chunks[0]["symbol_name"] == "func_a"

    found_syms = storage.search_symbols("func_a", index_name="test_index")
    assert len(found_syms) == 1
    assert found_syms[0]["symbol"] == "func_a"


def test_storage_save_diagnostic(tmp_path: Path) -> None:
    """Тестирование сохранения диагностических заключений."""
    db_file = tmp_path / "test_diag.db"
    storage = CodeHelperStorage(
        config={
            "storage": {
                "engine": "sqlite",
                "sqlite": {"path": str(db_file)},
            }
        }
    )

    conclusion = DiagnosticConclusion(
        summary="Ошибка деления на ноль",
        root_cause="ZeroDivisionError в модуле math_tool",
        explanation="Переменная divisor равна нулю при вызове calc()",
        severity="error",
        confidence=0.9,
    )

    storage.save_diagnostic(conclusion, query="деление на ноль", error_message="ZeroDivisionError")

    with storage._connect_sqlite() as conn:
        rows = conn.execute("SELECT * FROM code_diagnostics").fetchall()
        assert len(rows) == 1
        assert rows[0]["summary"] == "Ошибка деления на ноль"
