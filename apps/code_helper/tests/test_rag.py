# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper Tests - RAG Engine
# =============================================================================
# Description:
#   Модульные тесты для RAG-движка анализа кода и диагностики ошибок.
#
# File: test_rag.py
# Project: ai-windows-admin
# Package: apps.code_helper.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты автономного RAG-движка Code Helper."""

from pathlib import Path
import pytest
from apps.code_helper.rag import CodeHelperRAG
from apps.code_helper.storage import CodeHelperStorage


@pytest.mark.asyncio
async def test_rag_build_and_search(tmp_path: Path) -> None:
    """Тестирование полного цикла сборки индекса и семантического поиска."""
    code_file = tmp_path / "service.py"
    code_file.write_text(
        """
def start_worker(worker_id: int) -> bool:
    '''Запуск фонового обработчика задач.'''
    return worker_id > 0
""",
        encoding="utf-8",
    )

    db_path = tmp_path / "rag_test.db"
    storage = CodeHelperStorage(
        config={"storage": {"engine": "sqlite", "sqlite": {"path": str(db_path)}}}
    )
    rag = CodeHelperRAG(storage=storage)

    stats = rag.build_index(project_root=tmp_path, index_name="unit_test")
    assert stats.total_files == 1
    assert stats.total_chunks >= 1
    assert stats.total_symbols >= 1

    results = rag.search_code("start_worker", index_name="unit_test")
    assert len(results) >= 1
    assert results[0]["symbol_name"] == "start_worker"
    assert results[0]["relevance_score"] > 0.5

    symbols = rag.search_symbols("start_worker", index_name="unit_test")
    assert len(symbols) >= 1
    assert symbols[0]["short_name"] == "start_worker"


@pytest.mark.asyncio
async def test_rag_diagnose_error_traceback(tmp_path: Path) -> None:
    """Тестирование автоматической диагностики и локализации сбоя по трейсбеку."""
    module_code = tmp_path / "math_ops.py"
    module_code.write_text(
        """
def compute_division(a: int, b: int) -> float:
    '''Функция деления чисел.'''
    return a / b
""",
        encoding="utf-8",
    )

    db_path = tmp_path / "rag_diag.db"
    storage = CodeHelperStorage(
        config={"storage": {"engine": "sqlite", "sqlite": {"path": str(db_path)}}}
    )
    rag = CodeHelperRAG(storage=storage)
    rag.build_index(project_root=tmp_path, index_name="diag_idx")

    traceback_err = """
Traceback (most recent call last):
  File "math_ops.py", line 4, in compute_division
ZeroDivisionError: division by zero
"""
    conclusion = await rag.diagnose(
        error_message=traceback_err,
        logs=["[ERROR] math_ops.py:4 - ZeroDivisionError"],
        index_name="diag_idx",
    )

    assert conclusion.severity == "error"
    assert "ZeroDivisionError" in conclusion.summary
    assert len(conclusion.affected_locations) >= 1
    assert conclusion.affected_locations[0].file_path == "math_ops.py"
    assert conclusion.affected_locations[0].start_line == 4
    assert len(conclusion.remediation_steps) >= 1
