# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - AST & Markdown Code Parser
# =============================================================================
# Description:
#   Специализированный парсер исходного кода Python через AST и секций Markdown.
#   Извлекает классы, методы, функции, docstrings, сигнатуры и формирует
#   смысловые чанки для базы знаний.
#
# File: parser.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Модуль AST-парсинга кода Python и документации Markdown."""

import ast
import hashlib
import time
from pathlib import Path
from typing import Any, List, Set, Tuple, Union

from logger import logger
from .models import CodeChunk, CodeSymbol

_DEFAULT_EXCLUDED: Set[str] = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "site-packages",
}


class CodeParser:
    """Парсер исходного кода и Markdown-документации."""

    def __init__(self, excluded_dirs: Optional[Set[str]] = None) -> None:
        """Инициализация парсера.

        Args:
            excluded_dirs: Множество каталогов для исключения из сканирования.
        """
        self.excluded_dirs = set(excluded_dirs) if excluded_dirs else set(_DEFAULT_EXCLUDED)

    def should_skip(self, path: Path) -> bool:
        """Проверяет, должен ли путь быть пропущен при сканировании."""
        for part in path.parts:
            if part in self.excluded_dirs or part.startswith("~"):
                return True
        return False

    @staticmethod
    def compute_hash(text: str) -> str:
        """Вычисляет SHA-256 хеш содержимого блока."""
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]

    @staticmethod
    def format_signature(node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]) -> str:
        """Формирует текстовую сигнатуру функции, метода или класса."""
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            bases_str = f"({', '.join(bases)})" if bases else ""
            return f"class {node.name}{bases_str}"

        args_repr: List[str] = []
        for arg in node.args.args:
            ann = ast.unparse(arg.annotation) if arg.annotation else ""
            args_repr.append(f"{arg.arg}: {ann}" if ann else arg.arg)

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{prefix} {node.name}({', '.join(args_repr)}){ret}"

    def parse_python_file(
        self, file_path: Path, rel_path: str, index_name: str = "codebase"
    ) -> Tuple[List[CodeChunk], List[CodeSymbol]]:
        """Парсит Python файл через AST, создавая чанки и символы.

        Args:
            file_path: Абсолютный путь к файлу.
            rel_path: Относительный путь в проекте.
            index_name: Имя целевого индекса.

        Returns:
            Кортеж (список чанков, список символов).
        """
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug(f"[CodeParser] Ошибка чтения {file_path}: {exc}")
            return [], []

        if not source.strip():
            return [], []

        lines = source.splitlines()
        chunks: List[CodeChunk] = []
        symbols: List[CodeSymbol] = []
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError:
            # При ошибке синтаксиса индексируем весь файл как общий модуль
            content = f"File: {rel_path}\n\n{source[:3500]}"
            chunks.append(
                CodeChunk(
                    chunk_id=f"{rel_path}:1-{len(lines)}",
                    index_name=index_name,
                    file_path=rel_path,
                    symbol_name=file_path.stem,
                    symbol_type="module",
                    start_line=1,
                    end_line=len(lines),
                    content=content,
                    signature=f"module {file_path.stem}",
                    docstring="",
                    snippet=source[:500],
                    content_hash=self.compute_hash(content),
                    updated_at=now_str,
                )
            )
            return chunks, symbols

        # Сбор импортов
        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        module_doc = ast.get_docstring(tree) or ""
        if module_doc:
            content = f"Module: {rel_path}\nImports: {', '.join(imports[:15])}\nDocstring: {module_doc}"
            chunks.append(
                CodeChunk(
                    chunk_id=f"{rel_path}::module",
                    index_name=index_name,
                    file_path=rel_path,
                    symbol_name=file_path.stem,
                    symbol_type="module",
                    start_line=1,
                    end_line=min(len(lines), 40),
                    content=content,
                    signature=f"module {file_path.stem}",
                    docstring=module_doc,
                    snippet=module_doc[:500],
                    content_hash=self.compute_hash(content),
                    updated_at=now_str,
                )
            )

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c, s = self._extract_function(node, lines, rel_path, imports, index_name, parent_class="")
                chunks.append(c)
                symbols.append(s)
            elif isinstance(node, ast.ClassDef):
                c_list, s_list = self._extract_class(node, lines, rel_path, imports, index_name)
                chunks.extend(c_list)
                symbols.extend(s_list)

        return chunks, symbols

    def _extract_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        lines: List[str],
        rel_path: str,
        imports: List[str],
        index_name: str,
        parent_class: str = "",
    ) -> Tuple[CodeChunk, CodeSymbol]:
        """Извлечение функции или метода в модель CodeChunk и CodeSymbol."""
        sig = self.format_signature(node)
        doc = ast.get_docstring(node) or ""
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        body_slice = lines[start_line - 1 : min(end_line, start_line + 40)]
        body_snippet = "\n".join(body_slice)

        full_name = f"{parent_class}.{node.name}" if parent_class else node.name
        sym_type = "method" if parent_class else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        content = (
            f"File: {rel_path}:{start_line}-{end_line}\n"
            f"Symbol: {full_name}\n"
            f"Signature: {sig}\n"
            f"Docstring: {doc}\n"
            f"Code:\n{body_snippet[:1800]}"
        )

        chunk = CodeChunk(
            chunk_id=f"{rel_path}::{full_name}:{start_line}",
            index_name=index_name,
            file_path=rel_path,
            symbol_name=full_name,
            symbol_type=sym_type,
            start_line=start_line,
            end_line=end_line,
            content=content,
            signature=sig,
            docstring=doc[:600],
            snippet=body_snippet[:800],
            content_hash=self.compute_hash(content),
            updated_at=now_str,
        )

        symbol = CodeSymbol(
            symbol_id=f"{rel_path}::{full_name}",
            index_name=index_name,
            symbol=full_name,
            short_name=node.name,
            symbol_type=sym_type,
            file_path=rel_path,
            signature=sig,
            docstring=doc[:600],
            start_line=start_line,
            end_line=end_line,
            related_symbols=imports[:6],
            snippet=body_snippet[:800],
            updated_at=now_str,
        )

        return chunk, symbol

    def _extract_class(
        self,
        node: ast.ClassDef,
        lines: List[str],
        rel_path: str,
        imports: List[str],
        index_name: str,
    ) -> Tuple[List[CodeChunk], List[CodeSymbol]]:
        """Извлечение класса и его методов."""
        sig = self.format_signature(node)
        doc = ast.get_docstring(node) or ""
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        class_slice = lines[start_line - 1 : min(end_line, start_line + 35)]
        class_preview = "\n".join(class_slice)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        bases = [ast.unparse(b) for b in node.bases]

        content = (
            f"File: {rel_path}:{start_line}-{end_line}\n"
            f"Class: {sig}\n"
            f"Docstring: {doc}\n"
            f"Methods: {', '.join(methods)}\n"
            f"Preview:\n{class_preview[:1500]}"
        )

        cls_chunk = CodeChunk(
            chunk_id=f"{rel_path}::{node.name}:{start_line}",
            index_name=index_name,
            file_path=rel_path,
            symbol_name=node.name,
            symbol_type="class",
            start_line=start_line,
            end_line=end_line,
            content=content,
            signature=sig,
            docstring=doc[:600],
            snippet=class_preview[:800],
            content_hash=self.compute_hash(content),
            updated_at=now_str,
        )

        cls_symbol = CodeSymbol(
            symbol_id=f"{rel_path}::{node.name}",
            index_name=index_name,
            symbol=node.name,
            short_name=node.name,
            symbol_type="class",
            file_path=rel_path,
            signature=sig,
            docstring=doc[:600],
            start_line=start_line,
            end_line=end_line,
            related_symbols=methods + bases + imports[:4],
            snippet=class_preview[:800],
            updated_at=now_str,
        )

        chunks: List[CodeChunk] = [cls_chunk]
        symbols: List[CodeSymbol] = [cls_symbol]

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m_c, m_s = self._extract_function(
                    item, lines, rel_path, imports, index_name, parent_class=node.name
                )
                chunks.append(m_c)
                symbols.append(m_s)

        return chunks, symbols

    def parse_markdown_file(
        self, file_path: Path, rel_path: str, index_name: str = "codebase"
    ) -> List[CodeChunk]:
        """Парсинг Markdown документации с разбиением по заголовкам."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        if not content.strip():
            return []

        lines = content.splitlines()
        chunks: List[CodeChunk] = []
        current_title = file_path.name
        current_lines: List[str] = []
        section_start = 1
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        for idx, line in enumerate(lines, start=1):
            if line.startswith("#"):
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        c_text = f"Doc: {rel_path} | {current_title}\n{sec_text[:2000]}"
                        chunks.append(
                            CodeChunk(
                                chunk_id=f"{rel_path}::{current_title}:{section_start}",
                                index_name=index_name,
                                file_path=rel_path,
                                symbol_name=current_title,
                                symbol_type="doc",
                                start_line=section_start,
                                end_line=idx - 1,
                                content=c_text,
                                signature=f"# {current_title}",
                                docstring=sec_text[:400],
                                snippet=sec_text[:600],
                                content_hash=self.compute_hash(c_text),
                                updated_at=now_str,
                            )
                        )
                current_title = line.lstrip("#").strip() or file_path.name
                current_lines = [line]
                section_start = idx
            else:
                current_lines.append(line)

        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                c_text = f"Doc: {rel_path} | {current_title}\n{sec_text[:2000]}"
                chunks.append(
                    CodeChunk(
                        chunk_id=f"{rel_path}::{current_title}:{section_start}",
                        index_name=index_name,
                        file_path=rel_path,
                        symbol_name=current_title,
                        symbol_type="doc",
                        start_line=section_start,
                        end_line=len(lines),
                        content=c_text,
                        signature=f"# {current_title}",
                        docstring=sec_text[:400],
                        snippet=sec_text[:600],
                        content_hash=self.compute_hash(c_text),
                        updated_at=now_str,
                    )
                )

        return chunks
