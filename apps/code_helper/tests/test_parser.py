# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper Tests - Parser
# =============================================================================
# Description:
#   Модульные тесты для AST-парсера исходного кода и секционного парсера Markdown.
#
# File: test_parser.py
# Project: ai-windows-admin
# Package: apps.code_helper.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты парсера исходного кода Python и Markdown."""

from pathlib import Path
import pytest
from apps.code_helper.parser import CodeParser


def test_parser_python_functions_and_classes(tmp_path: Path) -> None:
    """Тестирование извлечения классов, методов и функций из Python файла."""
    sample_code = """
import os
from typing import List

class Calculator:
    '''Класс калькулятора.'''
    def __init__(self, val: int = 0) -> None:
        self.val = val

    def add(self, x: int) -> int:
        '''Сложение.'''
        return self.val + x

async def fetch_data(url: str) -> str:
    '''Асинхронное получение данных.'''
    return url
"""
    test_file = tmp_path / "sample.py"
    test_file.write_text(sample_code.strip(), encoding="utf-8")

    parser = CodeParser()
    chunks, symbols = parser.parse_python_file(test_file, "sample.py", index_name="test_idx")

    # Проверка извлечения чанков
    assert len(chunks) >= 3
    chunk_names = {c.symbol_name for c in chunks}
    assert "Calculator" in chunk_names
    assert "Calculator.add" in chunk_names
    assert "fetch_data" in chunk_names

    # Проверка извлечения символов
    sym_map = {s.symbol: s for s in symbols}
    assert "Calculator" in sym_map
    assert "Calculator.add" in sym_map
    assert "fetch_data" in sym_map

    assert sym_map["Calculator.add"].symbol_type == "method"
    assert sym_map["fetch_data"].symbol_type == "async_function"
    assert "def add(self, x: int) -> int" in sym_map["Calculator.add"].signature


def test_parser_syntax_error_fallback(tmp_path: Path) -> None:
    """Тестирование корректной обработки файлов с нарушенным синтаксисом."""
    broken_code = "def broken_func(:\n    invalid syntax"
    test_file = tmp_path / "broken.py"
    test_file.write_text(broken_code, encoding="utf-8")

    parser = CodeParser()
    chunks, symbols = parser.parse_python_file(test_file, "broken.py", index_name="test_idx")

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "module"
    assert chunks[0].file_path == "broken.py"


def test_parser_markdown_sections(tmp_path: Path) -> None:
    """Тестирование секционного разбиения документации Markdown."""
    md_content = """# Главный заголовок
Вводная информация о проекте.

## Раздел 1: Установка
Команда установки: pip install.

## Раздел 2: Использование
Инструкция по использованию.
"""
    test_file = tmp_path / "DOCS.md"
    test_file.write_text(md_content.strip(), encoding="utf-8")

    parser = CodeParser()
    chunks = parser.parse_markdown_file(test_file, "DOCS.md", index_name="test_idx")

    assert len(chunks) >= 2
    symbols = [c.symbol_name for c in chunks]
    assert any("Раздел 1" in s for s in symbols)
    assert any("Раздел 2" in s for s in symbols)
