# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Codebase AST & Diagnostic RAG Engine
# =============================================================================
# Description:
#   Движок AST-индексации исходного кода Python и Markdown-документации,
#   гибридного семантического поиска и генерации структурированных заключений
#   (Root Cause Analysis & Remediation) по вопросам, спискам логов и ошибкам.
#
#   Зачем нужен этот модуль:
#     1. Глубокое понимание кодовой базы: парсинг AST-деревьев Python (классы,
#        функции, методы, сигнатуры, docstrings, импорты и граф вызовов) +
#        секционное чанкирование Markdown-документации.
#     2. Локализация сбоев по логам и трейсбекам: автоматическое извлечение
#        путей к файлам, номеров строк, типов исключений и имен символов из
#        сырых логов и сообщений об ошибках с приоритизацией точных совпадений.
#     3. Выдача детерминированного инженерного заключения: синтез ответа через
#        UnifiedChatModel или эвристический анализатор в строгом формате
#        Pydantic (первопричина, затронутые файлы/строки, объяснение и шаги
#        исправления).
#
#   Режимы работы:
#     - 'hybrid_llm': Векторный/AST поиск + генерация заключения через UnifiedChatModel.
#     - 'deterministic_ast': Локальный анализ на базе AST, графа символов и документации
#       без обращения к внешним LLM (fallback или офлайн-режим).
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.codebase_rag import CodebaseRAG
#
#     rag = CodebaseRAG()
#     rag.build_index(project_root=".", include_dirs=["src/ai/rag"])
#     conclusion = await rag.diagnose(
#         error_message="ZeroDivisionError in calculate_ratio at math_utils.py:42",
#         logs=["[ERROR] math_utils.py:42 - division by zero"]
#     )
#     print(conclusion.root_cause)
#
# File: codebase_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:27:00
# =============================================================================

from __future__ import annotations
"""Движок AST-индексации кода и генерации диагностических заключений по логам и ошибкам."""

import ast
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from logger import logger
from .text_rag import TextRAG


_EXCLUDED_DIRS: Set[str] = {
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

_TRACEBACK_FILE_LINE_RE = re.compile(
    r'(?:File\s+"([^"]+\.py)"|([a-zA-Z0-9_./\\\-]+\.py))(?:\s*,\s*line\s+|\s*:\s*)(\d+)',
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Warning|Fault))\s*:\s*(.+)"
)
_SYMBOL_CANDIDATE_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,64})\b")


class AffectedCodeLocation(BaseModel):
    """Описание затронутого участка исходного кода или документации."""

    file_path: str = Field(description="Относительный путь к файлу в проекте")
    symbol_name: str = Field(default="", description="Имя функции, класса или метода")
    symbol_type: str = Field(default="module", description="Тип узла (class, function, method, doc)")
    start_line: int = Field(default=1, ge=1, description="Начальная строка в файле")
    end_line: int = Field(default=1, ge=1, description="Конечная строка в файле")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Оценка релевантности участка")
    snippet: str = Field(default="", description="Фрагмент исходного кода или сигнатура")


class CodeRemediationStep(BaseModel):
    """Рекомендуемый шаг по исправлению ошибки или устранению проблемы в коде."""

    title: str = Field(description="Краткий заголовок действия")
    description: str = Field(description="Подробное техническое описание исправления")
    target_file: str = Field(default="", description="Целевой файл для внесения изменений")
    suggested_code: str = Field(default="", description="Пример исправленного кода или команды")


class CodeDiagnosticConclusion(BaseModel):
    """Итоговое структурированное заключение RAG-анализатора по кодовой базе."""

    summary: str = Field(description="Краткое резюме заключения (1-2 предложения)")
    root_cause: str = Field(description="Выявленная первопричина проблемы или ответ на вопрос по архитектуре")
    explanation: str = Field(description="Развернутое техническое объяснение на основе найденного кода")
    severity: str = Field(default="error", description="Уровень критичности (info, warning, error, critical)")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Уверенность в заключении")
    affected_locations: List[AffectedCodeLocation] = Field(
        default_factory=list,
        description="Список затронутых файлов, функций и строк кода",
    )
    remediation_steps: List[CodeRemediationStep] = Field(
        default_factory=list,
        description="Пошаговый план исправления или проверки",
    )
    extracted_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Извлеченные из логов и ошибки сигналы (исключения, файлы, символы)",
    )
    source_mode: str = Field(
        default="deterministic_ast",
        description="Режим формирования заключения (hybrid_llm или deterministic_ast)",
    )
    execution_time_ms: float = Field(default=0.0, description="Время выполнения анализа в мс")


class CodebaseRAG:
    """RAG-движок для индексации кода (AST + Документация) и диагностики ошибок и логов.

    Обеспечивает построение именованных индексов кодовой базы, точный поиск по AST-символам,
    семантический поиск через TextRAG и выдачу диагностических заключений `CodeDiagnosticConclusion`.

    Attributes:
        storage_dir (Path): Базовая директория хранения индексов кода.
        dimension (int): Размерность векторов для TextRAG.
        chat_model (Any): Опциональный экземпляр UnifiedChatModel для LLM-синтеза.
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = False,
        dimension: int = 3072,
        chat_model: Any = False,
    ) -> None:
        """Инициализация движка CodebaseRAG.

        Args:
            storage_dir (Optional[Path]): Директория хранения индексов кода.
                                          Значение по умолчанию: False (используется data/rag/codebase).
            dimension (int): Размерность эмбеддингов TextRAG.
                             Значение по умолчанию: 3072.
            chat_model (Any): Экземпляр модели чата для генерации заключений.
                              Значение по умолчанию: False.

        Examples:
            >>> rag = CodebaseRAG(dimension=64)
            >>> print(rag.dimension)
            64
        """
        self.storage_dir: Path = Path(storage_dir) if storage_dir else Path("data/rag/codebase")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.dimension: int = dimension
        self.chat_model: Any = chat_model
        self._text_rags: Dict[str, TextRAG] = {}
        self._symbols_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._load_existing_indexes()

    def _get_index_dir(self, index_name: str = "codebase") -> Path:
        """Получение директории конкретного именованного индекса.

        Args:
            index_name (str): Имя индекса. Значение по умолчанию: 'codebase'.

        Returns:
            Path: Путь к папке индекса.

        Examples:
            >>> rag = CodebaseRAG()
            >>> p = rag._get_index_dir("my_idx")
            >>> print(p.name)
            my_idx
        """
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", index_name.strip() or "codebase")
        idx_dir = self.storage_dir / safe_name
        idx_dir.mkdir(parents=True, exist_ok=True)
        return idx_dir

    def _get_text_rag(self, index_name: str = "codebase") -> TextRAG:
        """Получение или инициализация векторного хранилища TextRAG для заданного индекса.

        Args:
            index_name (str): Имя индекса. Значение по умолчанию: 'codebase'.

        Returns:
            TextRAG: Экземпляр векторного индекса.

        Examples:
            >>> rag = CodebaseRAG(dimension=64)
            >>> tr = rag._get_text_rag("codebase")
            >>> print(tr.dimension)
            64
        """
        if index_name not in self._text_rags:
            idx_dir = self._get_index_dir(index_name)
            self._text_rags[index_name] = TextRAG(
                db_path=idx_dir / "chunks_index",
                dimension=self.dimension,
            )
        return self._text_rags[index_name]

    def _load_existing_indexes(self) -> None:
        """Загрузка метаданных и таблиц символов всех ранее построенных индексов на диске.

        Examples:
            >>> rag = CodebaseRAG()
            >>> rag._load_existing_indexes()
        """
        if not self.storage_dir.exists():
            return

        for sub in self.storage_dir.iterdir():
            if not sub.is_dir():
                continue
            idx_name = sub.name
            sym_file = sub / "symbols.json"
            stat_file = sub / "stats.json"
            if sym_file.exists():
                try:
                    self._symbols_cache[idx_name] = json.loads(sym_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning(f"[CodebaseRAG] Ошибка чтения символов {sym_file}: {exc}")
                    self._symbols_cache[idx_name] = []
            if stat_file.exists():
                try:
                    self._stats_cache[idx_name] = json.loads(stat_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning(f"[CodebaseRAG] Ошибка чтения статистики {stat_file}: {exc}")

    @staticmethod
    def _should_skip_path(path: Path) -> bool:
        """Проверка, нужно ли пропустить файл или директорию при сканировании проекта.

        Args:
            path (Path): Проверяемый путь.

        Returns:
            bool: True, если путь служебный или начинается с тильды '~'.

        Examples:
            >>> CodebaseRAG._should_skip_path(Path("__pycache__/foo.py"))
            True
        """
        for part in path.parts:
            if part in _EXCLUDED_DIRS or part.startswith("~"):
                return True
        return False

    @staticmethod
    def _format_signature(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Формирование строки сигнатуры функции или метода из узла AST.

        Args:
            node (Union[ast.FunctionDef, ast.AsyncFunctionDef]): Узел AST функции.

        Returns:
            str: Строковое представление сигнатуры с типами аргументов и возврата.

        Examples:
            >>> tree = ast.parse("def add(a: int, b: int) -> int: return a + b")
            >>> sig = CodebaseRAG._format_signature(tree.body[0])
            >>> print(sig)
            def add(a: int, b: int) -> int
        """
        args_repr: List[str] = []
        for arg in node.args.args:
            ann = ast.unparse(arg.annotation) if arg.annotation else ""
            args_repr.append(f"{arg.arg}: {ann}" if ann else arg.arg)
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{prefix} {node.name}({', '.join(args_repr)}){ret}"

    def _parse_python_file(
        self,
        file_path: Path,
        rel_path: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Парсинг Python-файла через AST на чанки кода и записи символов.

        Args:
            file_path (Path): Абсолютный путь к файлу `.py`.
            rel_path (str): Относительный путь от корня проекта.

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: Кортеж (список чанков для TextRAG, список символов AST).

        Examples:
            >>> rag = CodebaseRAG()
            >>> chunks, symbols = rag._parse_python_file(Path("header.py"), "header.py")
            >>> print(isinstance(chunks, list))
            True
        """
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug(f"[CodebaseRAG] Не удалось прочитать {file_path}: {exc}")
            return [], []

        if not source.strip():
            return [], []

        lines = source.splitlines()
        chunks: List[Dict[str, Any]] = []
        symbols: List[Dict[str, Any]] = []

        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError:
            # Если синтаксис поврежден, индексируем как единый текстовый чанк файла
            chunks.append({
                "id": f"{rel_path}:1-{len(lines)}",
                "text": f"File: {rel_path}\n\n{source[:4000]}",
                "meta": {
                    "path": rel_path,
                    "symbol": file_path.stem,
                    "type": "module",
                    "start_line": 1,
                    "end_line": len(lines),
                },
            })
            return chunks, symbols

        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        module_doc = ast.get_docstring(tree) or ""
        if module_doc:
            chunks.append({
                "id": f"{rel_path}::module",
                "text": f"Module: {rel_path}\nImports: {', '.join(imports[:15])}\nDocstring: {module_doc}",
                "meta": {
                    "path": rel_path,
                    "symbol": file_path.stem,
                    "type": "module",
                    "start_line": 1,
                    "end_line": min(len(lines), 40),
                    "imports": imports[:25],
                },
            })

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c_doc, s_doc = self._extract_function_node(node, lines, rel_path, imports, parent_class="")
                chunks.append(c_doc)
                symbols.append(s_doc)
            elif isinstance(node, ast.ClassDef):
                cls_chunks, cls_symbols = self._extract_class_node(node, lines, rel_path, imports)
                chunks.extend(cls_chunks)
                symbols.extend(cls_symbols)

        if not chunks:
            chunks.append({
                "id": f"{rel_path}:1-{len(lines)}",
                "text": f"File: {rel_path}\n{source[:3500]}",
                "meta": {
                    "path": rel_path,
                    "symbol": file_path.stem,
                    "type": "module",
                    "start_line": 1,
                    "end_line": len(lines),
                },
            })

        return chunks, symbols

    def _extract_function_node(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        lines: List[str],
        rel_path: str,
        imports: List[str],
        parent_class: str = "",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Извлечение метаданных и кода функции или метода из узла AST.

        Args:
            node (Union[ast.FunctionDef, ast.AsyncFunctionDef]): Узел функции.
            lines (List[str]): Строки исходного файла.
            rel_path (str): Относительный путь к файлу.
            imports (List[str]): Импорты модуля.
            parent_class (str): Имя родительского класса (для методов). Значение по умолчанию: ''.

        Returns:
            Tuple[Dict[str, Any], Dict[str, Any]]: Чанк для векторного поиска и запись символа AST.

        Examples:
            >>> rag = CodebaseRAG()
            >>> tree = ast.parse("def ping() -> str:\\n    return 'pong'")
            >>> ch, sym = rag._extract_function_node(tree.body[0], ["def ping() -> str:", "    return 'pong'"], "a.py", [])
            >>> print(sym["symbol"])
            ping
        """
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        full_name = f"{parent_class}.{node.name}" if parent_class else node.name
        sym_type = "method" if parent_class else "function"
        sig = self._format_signature(node)
        doc = ast.get_docstring(node) or ""
        code_slice = "\n".join(lines[max(0, start_line - 1) : min(len(lines), end_line)])

        calls: List[str] = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name):
                    calls.append(sub.func.id)
                elif isinstance(sub.func, ast.Attribute):
                    calls.append(sub.func.attr)
        unique_calls = list(dict.fromkeys(calls))[:15]

        chunk_text = (
            f"File: {rel_path}:{start_line}-{end_line}\n"
            f"Symbol: {full_name} ({sym_type})\n"
            f"Signature: {sig}\n"
            f"Docstring: {doc}\n"
            f"Calls: {', '.join(unique_calls)}\n"
            f"Code:\n{code_slice[:2500]}"
        )
        chunk = {
            "id": f"{rel_path}::{full_name}",
            "text": chunk_text,
            "meta": {
                "path": rel_path,
                "symbol": full_name,
                "type": sym_type,
                "signature": sig,
                "docstring": doc[:500],
                "start_line": start_line,
                "end_line": end_line,
                "calls": unique_calls,
                "snippet": code_slice[:1200],
            },
        }
        symbol_entry = {
            "symbol": full_name,
            "short_name": node.name,
            "type": sym_type,
            "path": rel_path,
            "signature": sig,
            "docstring": doc[:600],
            "start_line": start_line,
            "end_line": end_line,
            "related_symbols": unique_calls + imports[:8],
            "snippet": code_slice[:1200],
        }
        return chunk, symbol_entry

    def _extract_class_node(
        self,
        node: ast.ClassDef,
        lines: List[str],
        rel_path: str,
        imports: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Извлечение класса и всех его методов из узла AST.

        Args:
            node (ast.ClassDef): Узел класса AST.
            lines (List[str]): Строки исходного файла.
            rel_path (str): Относительный путь к файлу.
            imports (List[str]): Список импортов файла.

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: Список чанков и список символов класса.

        Examples:
            >>> rag = CodebaseRAG()
            >>> tree = ast.parse("class Box:\\n    def open(self): pass")
            >>> chs, syms = rag._extract_class_node(tree.body[0], ["class Box:", "    def open(self): pass"], "box.py", [])
            >>> print(len(syms))
            2
        """
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        bases = [ast.unparse(b) for b in node.bases] if node.bases else []
        sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
        doc = ast.get_docstring(node) or ""
        header_end = min(end_line, start_line + 35)
        class_preview = "\n".join(lines[max(0, start_line - 1) : header_end])

        method_names = [
            m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        chunks: List[Dict[str, Any]] = [{
            "id": f"{rel_path}::{node.name}",
            "text": (
                f"File: {rel_path}:{start_line}-{end_line}\n"
                f"Class: {sig}\n"
                f"Docstring: {doc}\n"
                f"Methods: {', '.join(method_names)}\n"
                f"Preview:\n{class_preview[:2000]}"
            ),
            "meta": {
                "path": rel_path,
                "symbol": node.name,
                "type": "class",
                "signature": sig,
                "docstring": doc[:500],
                "start_line": start_line,
                "end_line": end_line,
                "snippet": class_preview[:1200],
            },
        }]
        symbols: List[Dict[str, Any]] = [{
            "symbol": node.name,
            "short_name": node.name,
            "type": "class",
            "path": rel_path,
            "signature": sig,
            "docstring": doc[:600],
            "start_line": start_line,
            "end_line": end_line,
            "related_symbols": method_names + bases + imports[:5],
            "snippet": class_preview[:1200],
        }]

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c_doc, s_doc = self._extract_function_node(
                    item, lines, rel_path, imports, parent_class=node.name
                )
                chunks.append(c_doc)
                symbols.append(s_doc)

        return chunks, symbols

    def _parse_markdown_file(self, file_path: Path, rel_path: str) -> List[Dict[str, Any]]:
        """Разбиение файла документации Markdown (`.md`) на смысловые секции по заголовкам.

        Args:
            file_path (Path): Абсолютный путь к `.md` файлу.
            rel_path (str): Относительный путь в проекте.

        Returns:
            List[Dict[str, Any]]: Список чанков документации для индексации.

        Examples:
            >>> rag = CodebaseRAG()
            >>> chunks = rag._parse_markdown_file(Path("README.md"), "README.md")
            >>> print(isinstance(chunks, list))
            True
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        if not content.strip():
            return []

        lines = content.splitlines()
        chunks: List[Dict[str, Any]] = []
        current_title = file_path.name
        current_lines: List[str] = []
        section_start = 1

        for idx, line in enumerate(lines, start=1):
            if line.startswith("#"):
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        chunks.append({
                            "id": f"{rel_path}::{current_title}:{section_start}",
                            "text": f"Doc: {rel_path} | Section: {current_title}\n{sec_text[:2500]}",
                            "meta": {
                                "path": rel_path,
                                "symbol": current_title,
                                "type": "doc",
                                "start_line": section_start,
                                "end_line": idx - 1,
                                "snippet": sec_text[:1000],
                            },
                        })
                current_title = line.lstrip("#").strip() or file_path.name
                current_lines = [line]
                section_start = idx
            else:
                current_lines.append(line)

        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                chunks.append({
                    "id": f"{rel_path}::{current_title}:{section_start}",
                    "text": f"Doc: {rel_path} | Section: {current_title}\n{sec_text[:2500]}",
                    "meta": {
                        "path": rel_path,
                        "symbol": current_title,
                        "type": "doc",
                        "start_line": section_start,
                        "end_line": len(lines),
                        "snippet": sec_text[:1000],
                    },
                })

        return chunks

    def build_index(
        self,
        project_root: Union[str, Path] = ".",
        index_name: str = "codebase",
        include_dirs: Optional[List[str]] = False,
        include_markdown: bool = True,
    ) -> Dict[str, Any]:
        """Сканирование кодовой базы, разбор AST Python и Markdown-документации и сборка RAG-индекса.

        Args:
            project_root (Union[str, Path]): Корневая директория проекта.
                                             Значение по умолчанию: '.'.
            index_name (str): Имя создаваемого или обновляемого индекса.
                              Значение по умолчанию: 'codebase'.
            include_dirs (Optional[List[str]]): Опциональный список поддиректорий для индексации.
                                                Значение по умолчанию: False (весь проект).
            include_markdown (bool): Индексировать ли `.md` файлы документации.
                                     Значение по умолчанию: True.

        Returns:
            Dict[str, Any]: Статистика построенного индекса (число файлов, чанков, символов AST, время).

        Examples:
            >>> rag = CodebaseRAG(dimension=64)
            >>> stats = rag.build_index(project_root="src/ai/rag", index_name="rag_pkg")
            >>> print(stats["total_files"] > 0)
            True
        """
        start_t = time.perf_counter()
        root_path = Path(project_root).resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"Корневая директория проекта не найдена: {root_path}")

        scan_roots: List[Path] = []
        if include_dirs:
            for d in include_dirs:
                candidate = (root_path / d).resolve()
                if candidate.exists():
                    scan_roots.append(candidate)
        if not scan_roots:
            scan_roots = [root_path]

        all_chunks: List[Dict[str, Any]] = []
        all_symbols: List[Dict[str, Any]] = []
        total_files = 0

        for s_root in scan_roots:
            if s_root.is_file():
                files_iter = [s_root]
            else:
                files_iter = list(s_root.rglob("*"))

            for fpath in files_iter:
                if not fpath.is_file():
                    continue
                try:
                    rel = fpath.relative_to(root_path).as_posix()
                except ValueError:
                    rel = fpath.name

                if self._should_skip_path(Path(rel)):
                    continue

                suffix = fpath.suffix.lower()
                if suffix == ".py":
                    f_chunks, f_symbols = self._parse_python_file(fpath, rel)
                    all_chunks.extend(f_chunks)
                    all_symbols.extend(f_symbols)
                    total_files += 1
                elif include_markdown and suffix == ".md":
                    md_chunks = self._parse_markdown_file(fpath, rel)
                    all_chunks.extend(md_chunks)
                    total_files += 1

        text_rag = self._get_text_rag(index_name)
        text_rag.clear()
        if all_chunks:
            text_rag.add_documents(all_chunks, batch_size=64)

        elapsed = round(time.perf_counter() - start_t, 2)
        idx_dir = self._get_index_dir(index_name)
        stats_data = {
            "name": index_name,
            "scope": "global",
            "project_root": str(root_path),
            "total_files": total_files,
            "total_chunks": len(all_chunks),
            "total_symbols": len(all_symbols),
            "elapsed_seconds": elapsed,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        (idx_dir / "symbols.json").write_text(
            json.dumps(all_symbols, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (idx_dir / "stats.json").write_text(
            json.dumps(stats_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self._symbols_cache[index_name] = all_symbols
        self._stats_cache[index_name] = stats_data
        logger.info(
            f"[CodebaseRAG] Индекс '{index_name}' построен за {elapsed}с: "
            f"файлов={total_files}, чанков={len(all_chunks)}, символов={len(all_symbols)}"
        )
        return stats_data

    def list_indexes(self) -> List[Dict[str, Any]]:
        """Получение списка всех доступных индексов кодовой базы и их метрик.

        Returns:
            List[Dict[str, Any]]: Список метаданных индексов.

        Examples:
            >>> rag = CodebaseRAG()
            >>> indexes = rag.list_indexes()
            >>> print(isinstance(indexes, list))
            True
        """
        self._load_existing_indexes()
        return list(self._stats_cache.values())

    def search_symbols(
        self,
        symbol_query: str,
        index_name: str = "codebase",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Поиск функций, классов и методов по таблице AST-символов.

        Args:
            symbol_query (str): Имя или часть имени искомого символа.
            index_name (str): Имя индекса кода. Значение по умолчанию: 'codebase'.
            limit (int): Максимальное число результатов. Значение по умолчанию: 10.

        Returns:
            List[Dict[str, Any]]: Список совпавших AST-символов с путями, сигнатурами и docstrings.

        Examples:
            >>> rag = CodebaseRAG()
            >>> res = rag.search_symbols("CodebaseRAG")
            >>> print(isinstance(res, list))
            True
        """
        q = (symbol_query or "").strip().lower()
        if not q:
            return []

        symbols = self._symbols_cache.get(index_name, [])
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for sym in symbols:
            full_s = sym.get("symbol", "").lower()
            short_s = sym.get("short_name", "").lower()
            path_s = sym.get("path", "").lower()

            if q == full_s or q == short_s:
                scored.append((1.0, sym))
            elif short_s.startswith(q) or full_s.startswith(q):
                scored.append((0.85, sym))
            elif q in full_s or q in path_s:
                scored.append((0.65, sym))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def search_code(
        self,
        query: str,
        index_name: str = "codebase",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Гибридный поиск по кодовой базе (AST-символы + векторный и лексический поиск TextRAG).

        Args:
            query (str): Поисковый запрос, фрагмент лога или сообщение об ошибке.
            index_name (str): Имя целевого индекса. Значение по умолчанию: 'codebase'.
            top_k (int): Максимальное количество возвращаемых фрагментов кода. Значение по умолчанию: 5.

        Returns:
            List[Dict[str, Any]]: Отсортированный по релевантности список чанков кода.

        Examples:
            >>> rag = CodebaseRAG(dimension=64)
            >>> matches = rag.search_code("разбор AST дерева")
            >>> print(isinstance(matches, list))
            True
        """
        q_clean = (query or "").strip()
        if not q_clean:
            return []

        text_rag = self._get_text_rag(index_name)
        sem_results = text_rag.search(q_clean, top_k=max(top_k * 2, 10))
        signals = self.extract_diagnostic_signals(q_clean)

        file_hints = [f.lower() for f in signals.get("files", [])]
        symbol_hints = [s.lower() for s in signals.get("symbols", [])]
        line_hints = signals.get("file_lines", {})

        merged: Dict[str, Dict[str, Any]] = {}

        # 1. Добавляем прямые попадания по извлеченным из ошибки/запроса файлам и символам
        for sym in self._symbols_cache.get(index_name, []):
            sym_path = sym.get("path", "")
            sym_path_low = sym_path.lower()
            sym_name_low = sym.get("short_name", "").lower()
            full_name_low = sym.get("symbol", "").lower()

            bonus = 0.0
            for fh in file_hints:
                if sym_path_low.endswith(fh) or fh in sym_path_low:
                    bonus += 0.55
                    target_line = line_hints.get(fh, 0)
                    if target_line and sym.get("start_line", 0) <= target_line <= sym.get("end_line", 0):
                        bonus += 0.35

            if sym_name_low in symbol_hints or full_name_low in symbol_hints:
                bonus += 0.45

            if bonus > 0:
                cid = f"{sym_path}::{sym.get('symbol', '')}"
                score = min(1.0, round(0.4 + bonus, 4))
                merged[cid] = {
                    "id": cid,
                    "text": (
                        f"File: {sym_path}:{sym.get('start_line', 1)}-{sym.get('end_line', 1)}\n"
                        f"Symbol: {sym.get('symbol', '')}\n"
                        f"Signature: {sym.get('signature', '')}\n"
                        f"Docstring: {sym.get('docstring', '')}\n"
                        f"Code:\n{sym.get('snippet', '')}"
                    ),
                    "meta": {
                        "path": sym_path,
                        "symbol": sym.get("symbol", ""),
                        "type": sym.get("type", "function"),
                        "signature": sym.get("signature", ""),
                        "docstring": sym.get("docstring", ""),
                        "start_line": sym.get("start_line", 1),
                        "end_line": sym.get("end_line", 1),
                        "snippet": sym.get("snippet", ""),
                    },
                    "score": score,
                    "similarity_score": score,
                }

        # 2. Объединяем с результатами векторного поиска TextRAG
        for r in sem_results:
            cid = r["id"]
            base_score = float(r.get("score", 0.0))
            meta = r.get("meta", {})
            r_path = str(meta.get("path", "")).lower()
            r_sym = str(meta.get("symbol", "")).lower()

            boost = 0.0
            if any(fh in r_path for fh in file_hints):
                boost += 0.3
            if any(sh == r_sym or sh in r_sym for sh in symbol_hints):
                boost += 0.25

            final_score = min(1.0, round(base_score + boost, 4))
            if cid not in merged or final_score > merged[cid]["score"]:
                merged[cid] = {
                    "id": cid,
                    "text": r["text"],
                    "meta": meta,
                    "score": final_score,
                    "similarity_score": final_score,
                }

        sorted_res = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_res[:top_k]

    @staticmethod
    def extract_diagnostic_signals(raw_input: str) -> Dict[str, Any]:
        """Извлечение диагностических сигналов (путей к файлам, номеров строк, исключений, символов) из логов и ошибок.

        Args:
            raw_input (str): Объединенный текст вопроса, списка логов и сообщения об ошибке.

        Returns:
            Dict[str, Any]: Словарь с распознанными сигналами (`exceptions`, `files`, `file_lines`, `symbols`).

        Examples:
            >>> sig = CodebaseRAG.extract_diagnostic_signals('File "src/app.py", line 25, in run\\nValueError: bad cfg')
            >>> print(sig["exceptions"][0]["type"])
            ValueError
        """
        if not raw_input:
            return {"exceptions": [], "files": [], "file_lines": {}, "symbols": []}

        exceptions: List[Dict[str, str]] = []
        for match in _EXCEPTION_RE.finditer(raw_input):
            exceptions.append({
                "type": match.group(1),
                "message": match.group(2).strip()[:300],
            })

        files: List[str] = []
        file_lines: Dict[str, int] = {}
        for match in _TRACEBACK_FILE_LINE_RE.finditer(raw_input):
            raw_f = (match.group(1) or match.group(2) or "").replace("\\", "/").strip()
            line_no = int(match.group(3) or 1)
            if raw_f:
                norm_f = raw_f.lower()
                if raw_f not in files:
                    files.append(raw_f)
                file_lines[norm_f] = line_no

        # Также ищем упоминания .py или .md файлов без номеров строк
        for m_file in re.finditer(r"\b([a-zA-Z0-9_./\\\-]+\.(?:py|md))\b", raw_input):
            f_str = m_file.group(1).replace("\\", "/")
            if f_str not in files:
                files.append(f_str)

        stopwords = {
            "the", "and", "for", "with", "from", "line", "file", "error", "traceback",
            "most", "recent", "call", "last", "info", "warning", "critical", "debug",
            "none", "true", "false", "self", "return", "async", "await", "def", "class",
        }
        symbols: List[str] = []
        for m_sym in _SYMBOL_CANDIDATE_RE.finditer(raw_input):
            cand = m_sym.group(1)
            if cand.lower() not in stopwords and not cand.isdigit():
                if "_" in cand or (any(c.isupper() for c in cand[1:]) and any(c.islower() for c in cand)):
                    if cand not in symbols:
                        symbols.append(cand)

        return {
            "exceptions": exceptions[:10],
            "files": files[:15],
            "file_lines": file_lines,
            "symbols": symbols[:25],
        }

    async def diagnose(
        self,
        question: str = "",
        logs: Optional[List[str]] = False,
        error_message: str = "",
        index_name: str = "codebase",
        top_k: int = 6,
        use_llm: bool = True,
    ) -> CodeDiagnosticConclusion:
        """Формирование структурированного инженерного заключения на основе вопроса, логов или ошибки.

        Алгоритм:
        1. Объединяет входные данные (`question`, `logs`, `error_message`) и извлекает сигналы
           (стек-трейсы, файлы, строки, типы исключений, идентификаторы функций/классов).
        2. Выполняет гибридный поиск релевантных AST-узлов и документации в индексе `index_name`.
        3. Синтезирует заключение через LLM (`UnifiedChatModel`) или детерминированный AST-анализатор.

        Args:
            question (str): Вопрос пользователя по коду или поведению системы.
                            Значение по умолчанию: ''.
            logs (Optional[List[str]]): Список строк логов или событий.
                                        Значение по умолчанию: False.
            error_message (str): Текст ошибки или стек-трейс (Traceback).
                                 Значение по умолчанию: ''.
            index_name (str): Имя используемого индекса кода.
                              Значение по умолчанию: 'codebase'.
            top_k (int): Количество извлекаемых фрагментов кода для контекста.
                         Значение по умолчанию: 6.
            use_llm (bool): Использовать ли LLM для генерации вывода при доступности.
                            Значение по умолчанию: True.

        Returns:
            CodeDiagnosticConclusion: Структурированное заключение с первопричиной, локациями в коде и шагами исправления.

        Exceptions:
            ValueError: Если все три входных параметра (`question`, `logs`, `error_message`) пусты.

        Examples:
            >>> import asyncio
            >>> rag = CodebaseRAG(dimension=64)
            >>> res = asyncio.run(rag.diagnose(error_message="ValueError: invalid port", use_llm=False))
            >>> print(isinstance(res.root_cause, str))
            True
        """
        start_t = time.perf_counter()
        log_list: List[str] = list(logs) if logs else []
        combined_parts: List[str] = []
        if question.strip():
            combined_parts.append(f"Question: {question.strip()}")
        if error_message.strip():
            combined_parts.append(f"Error: {error_message.strip()}")
        if log_list:
            combined_parts.append("Logs:\n" + "\n".join(log_list[:50]))

        if not combined_parts:
            raise ValueError("Необходимо передать хотя бы один из параметров: question, logs или error_message.")

        combined_query = "\n\n".join(combined_parts)
        signals = self.extract_diagnostic_signals(combined_query)
        matches = self.search_code(combined_query, index_name=index_name, top_k=top_k)

        locations: List[AffectedCodeLocation] = []
        for m in matches:
            meta = m.get("meta", {})
            locations.append(
                AffectedCodeLocation(
                    file_path=str(meta.get("path", m.get("id", "unknown"))),
                    symbol_name=str(meta.get("symbol", "")),
                    symbol_type=str(meta.get("type", "module")),
                    start_line=max(1, int(meta.get("start_line", 1) or 1)),
                    end_line=max(1, int(meta.get("end_line", 1) or 1)),
                    relevance_score=float(m.get("score", 0.0)),
                    snippet=str(meta.get("snippet") or m.get("text", ""))[:1000],
                )
            )

        if use_llm:
            llm_conclusion = await self._synthesize_with_llm(
                question=question,
                logs=log_list,
                error_message=error_message,
                signals=signals,
                locations=locations,
                start_t=start_t,
            )
            if llm_conclusion:
                return llm_conclusion

        return self._build_deterministic_conclusion(
            question=question,
            logs=log_list,
            error_message=error_message,
            signals=signals,
            locations=locations,
            start_t=start_t,
        )

    async def _synthesize_with_llm(
        self,
        question: str,
        logs: List[str],
        error_message: str,
        signals: Dict[str, Any],
        locations: List[AffectedCodeLocation],
        start_t: float,
    ) -> Union[CodeDiagnosticConclusion, bool]:
        """Синтез диагностического заключения с помощью LLM на основе найденного AST-контекста.

        Args:
            question (str): Вопрос пользователя.
            logs (List[str]): Список логов.
            error_message (str): Сообщение об ошибке.
            signals (Dict[str, Any]): Извлеченные диагностические сигналы.
            locations (List[AffectedCodeLocation]): Найденные фрагменты кода из базы знаний.
            start_t (float): Метка времени начала расчета.

        Returns:
            Union[CodeDiagnosticConclusion, bool]: Объект заключения или False, если LLM недоступна.

        Examples:
            >>> # Вызывается внутри метода diagnose() при use_llm=True
            >>> pass
        """
        model = self.chat_model
        if not model:
            return False

        context_blocks: List[str] = []
        for idx, loc in enumerate(locations, start=1):
            context_blocks.append(
                f"--- КОНТЕКСТ КОДА #{idx}: {loc.file_path} (строки {loc.start_line}-{loc.end_line}, символ: {loc.symbol_name}) ---\n"
                f"{loc.snippet}"
            )
        context_str = "\n\n".join(context_blocks) if context_blocks else "Контекст в базе знаний кода не найден."

        system_prompt = (
            "Ты — главный архитектор и систему-диагност кода проекта AI Windows Admin. "
            "На основе входных данных (вопрос, список логов, сообщение об ошибке) и найденных в базе знаний "
            "участков исходного кода сформируй техническое заключение строго в формате JSON без markdown-оберток:\n"
            "{\n"
            '  "summary": "Краткое резюме (1-2 предложения)",\n'
            '  "root_cause": "Точная первопричина ошибки или ответ на вопрос с привязкой к коду",\n'
            '  "explanation": "Подробное техническое объяснение механизма работы или сбоя",\n'
            '  "severity": "info|warning|error|critical",\n'
            '  "confidence": 0.92,\n'
            '  "remediation_steps": [\n'
            '    {"title": "Шаг 1", "description": "Что исправить", "target_file": "path/to/file.py", "suggested_code": "код"}\n'
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"Вопрос: {question or 'Не указан'}\n"
            f"Ошибка / Traceback: {error_message or 'Не указана'}\n"
            f"Логи:\n{chr(10).join(logs[:30]) if logs else 'Не указаны'}\n\n"
            f"Извлеченные сигналы: {json.dumps(signals, ensure_ascii=False)}\n\n"
            f"Найденные фрагменты в базе знаний о коде:\n{context_str}\n\n"
            "Сформируй JSON-заключение:"
        )

        try:
            raw_res: str = ""
            if hasattr(model, "ask"):
                raw_res = await model.ask(user_prompt, system_instruction=system_prompt, temperature=0.1) or ""
            elif hasattr(model, "chat"):
                raw_res = await model.chat(user_prompt, system_instruction=system_prompt, temperature=0.1) or ""

            if not raw_res:
                return False

            clean_json = raw_res.strip()
            if "```" in clean_json:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_json)
                if m:
                    clean_json = m.group(1).strip()

            parsed = json.loads(clean_json)
            if not isinstance(parsed, dict):
                return False

            steps = [
                CodeRemediationStep(
                    title=str(s.get("title", "Исправление кода")),
                    description=str(s.get("description", "")),
                    target_file=str(s.get("target_file", "")),
                    suggested_code=str(s.get("suggested_code", "")),
                )
                for s in parsed.get("remediation_steps", [])
                if isinstance(s, dict) and s.get("title")
            ]

            elapsed_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            return CodeDiagnosticConclusion(
                summary=str(parsed.get("summary", "Диагностическое заключение сформировано.")),
                root_cause=str(parsed.get("root_cause", "Первопричина определена на базе анализа кода.")),
                explanation=str(parsed.get("explanation", "")),
                severity=str(parsed.get("severity", "error" if error_message else "info")),
                confidence=float(parsed.get("confidence", 0.88)),
                affected_locations=locations,
                remediation_steps=steps,
                extracted_signals=signals,
                source_mode="hybrid_llm",
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            logger.warning(f"[CodebaseRAG] Ошибка LLM-синтеза заключения, переход на детерминированный режим: {exc}")
            return False

    def _build_deterministic_conclusion(
        self,
        question: str,
        logs: List[str],
        error_message: str,
        signals: Dict[str, Any],
        locations: List[AffectedCodeLocation],
        start_t: float,
    ) -> CodeDiagnosticConclusion:
        """Построение детерминированного инженерного заключения по базе знаний AST без участия внешнего LLM.

        Args:
            question (str): Вопрос пользователя.
            logs (List[str]): Список строк логов.
            error_message (str): Сообщение об ошибке.
            signals (Dict[str, Any]): Извлеченные сигналы (исключения, файлы, символы).
            locations (List[AffectedCodeLocation]): Найденные локации в коде.
            start_t (float): Время старта обработки.

        Returns:
            CodeDiagnosticConclusion: Полностью заполненное заключение на базе AST-анализа.

        Examples:
            >>> rag = CodebaseRAG()
            >>> c = rag._build_deterministic_conclusion("Как работает X?", [], "", {}, [], time.perf_counter())
            >>> print(c.source_mode)
            deterministic_ast
        """
        exceptions = signals.get("exceptions", [])
        top_loc = locations[0] if locations else False

        has_error = bool(error_message.strip() or exceptions or any("err" in l.lower() or "crit" in l.lower() for l in logs))
        severity = "error" if has_error else "info"

        if exceptions and top_loc:
            exc_info = exceptions[0]
            summary = (
                f"Локализовано исключение {exc_info['type']} в модуле {top_loc.file_path} "
                f"(символ `{top_loc.symbol_name}`, строки {top_loc.start_line}-{top_loc.end_line})."
            )
            root_cause = (
                f"Сбой `{exc_info['type']}: {exc_info['message']}` возникает при выполнении "
                f"`{top_loc.symbol_name}` в файле `{top_loc.file_path}`."
            )
        elif has_error and top_loc:
            summary = (
                f"Проблема локализована в компоненте `{top_loc.symbol_name}` "
                f"({top_loc.file_path}:{top_loc.start_line}-{top_loc.end_line})."
            )
            root_cause = (
                f"Анализ логов и ошибки указывает на участок кода `{top_loc.symbol_name}` "
                f"в `{top_loc.file_path}`: {error_message or (logs[0] if logs else question)}"
            )
        elif top_loc:
            summary = (
                f"В базе знаний о коде найден целевой компонент `{top_loc.symbol_name}` "
                f"({top_loc.file_path}:{top_loc.start_line}-{top_loc.end_line})."
            )
            root_cause = (
                f"Запрос сопоставлен с реализацией `{top_loc.symbol_name}` ({top_loc.symbol_type}) "
                f"в модуле `{top_loc.file_path}`."
            )
        else:
            summary = "Прямых совпадений в текущем индексе кода не обнаружено."
            root_cause = (
                "В проиндексированной кодовой базе не найдено символов или файлов, "
                "соответствующих переданному запросу или логам."
            )

        explanation_parts: List[str] = []
        if top_loc:
            explanation_parts.append(
                f"Наиболее релевантный узел базы знаний — `{top_loc.symbol_name}` ({top_loc.symbol_type}) "
                f"в файле `{top_loc.file_path}` (строки {top_loc.start_line}–{top_loc.end_line}, "
                f"релевантность {top_loc.relevance_score})."
            )
            if len(locations) > 1:
                related_list = ", ".join(
                    f"`{loc.symbol_name}` ({loc.file_path}:{loc.start_line})" for loc in locations[1:4]
                )
                explanation_parts.append(f"Связанные компоненты в кодовой базе: {related_list}.")
        if exceptions:
            explanation_parts.append(
                "Из входных данных выделены исключения: "
                + ", ".join(f"{e['type']} ({e['message']})" for e in exceptions)
                + "."
            )
        if not explanation_parts:
            explanation_parts.append(
                "Рекомендуется выполнить переиндексацию целевой директории проекта через `build_index()`."
            )

        steps: List[CodeRemediationStep] = []
        if top_loc:
            steps.append(
                CodeRemediationStep(
                    title=f"Проверка реализации `{top_loc.symbol_name}`",
                    description=(
                        f"Проверьте входные предусловия (Fail-Fast) и обработку крайних случаев "
                        f"в `{top_loc.file_path}` на строках {top_loc.start_line}-{top_loc.end_line}."
                    ),
                    target_file=top_loc.file_path,
                    suggested_code=top_loc.snippet[:400],
                )
            )
        if exceptions:
            exc_type = exceptions[0]["type"]
            steps.append(
                CodeRemediationStep(
                    title=f"Устранение причины `{exc_type}`",
                    description=(
                        f"Добавьте валидацию входных параметров перед вызовом проблемной операции, "
                        f"порождающей `{exc_type}: {exceptions[0]['message']}`."
                    ),
                    target_file=top_loc.file_path if top_loc else "",
                )
            )
        if not steps:
            steps.append(
                CodeRemediationStep(
                    title="Актуализация AST-индекса кодовой базы",
                    description="Запустите построение индекса `CodebaseRAG.build_index()` для целевых пакетов проекта.",
                )
            )

        elapsed_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
        return CodeDiagnosticConclusion(
            summary=summary,
            root_cause=root_cause,
            explanation=" ".join(explanation_parts),
            severity=severity,
            confidence=round(top_loc.relevance_score, 2) if top_loc and top_loc.relevance_score > 0 else 0.5,
            affected_locations=locations,
            remediation_steps=steps,
            extracted_signals=signals,
            source_mode="deterministic_ast",
            execution_time_ms=elapsed_ms,
        )
