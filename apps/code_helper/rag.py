# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - Autonomous Codebase RAG & Diagnostic Engine
# =============================================================================
# Description:
#   Автономный движок семантического поиска по коду, AST-навигации и
#   структурированной диагностики сбоев и ошибок (Root Cause Analysis).
#
# File: rag.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Автономный RAG-движок для индексации кода, поиска и диагностики ошибок."""

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from logger import logger
from .models import (
    CodeLocation,
    CodeRemediationStep,
    DiagnosticConclusion,
    IndexStats,
)
from .parser import CodeParser
from .storage import CodeHelperStorage

_TRACEBACK_FILE_LINE_RE = re.compile(
    r'(?:File\s+"([^"]+\.py)"|([a-zA-Z0-9_./\\\-]+\.py))(?:\s*,\s*line\s+|\s*:\s*)(\d+)',
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(r"\b([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Warning|Fault))\s*:\s*(.+)")
_SYMBOL_CANDIDATE_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,64})\b")


class CodeHelperRAG:
    """Автономный RAG-движок для анализа кода и выдачи заключений."""

    def __init__(
        self,
        storage: Optional[CodeHelperStorage] = None,
        parser: Optional[CodeParser] = None,
        chat_model: Any = None,
    ) -> None:
        """Инициализация RAG-движка.

        Args:
            storage: Экземпляр хранилища CodeHelperStorage.
            parser: Экземпляр парсера CodeParser.
            chat_model: Опциональная модель чата LLM.
        """
        self.storage: CodeHelperStorage = storage or CodeHelperStorage()
        self.parser: CodeParser = parser or CodeParser()
        self.chat_model: Any = chat_model

    def build_index(
        self,
        project_root: Union[str, Path] = ".",
        index_name: str = "codebase",
        include_dirs: Optional[List[str]] = None,
        include_markdown: bool = True,
    ) -> IndexStats:
        """Сканирует проект, разбирает код в AST и сохраняет индекс в базу данных Hostinger / SQLite."""
        start_t = time.perf_counter()
        root_path = Path(project_root).resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"Корневой каталог не найден: {root_path}")

        scan_roots: List[Path] = []
        if include_dirs:
            for d in include_dirs:
                cand = (root_path / d).resolve()
                if cand.exists():
                    scan_roots.append(cand)
        if not scan_roots:
            scan_roots = [root_path]

        all_chunks = []
        all_symbols = []
        scanned_files = 0

        for s_root in scan_roots:
            files_iter = [s_root] if s_root.is_file() else list(s_root.rglob("*"))
            for fpath in files_iter:
                if not fpath.is_file():
                    continue
                try:
                    rel = fpath.relative_to(root_path).as_posix()
                except ValueError:
                    rel = fpath.name

                if self.parser.should_skip(Path(rel)):
                    continue

                suffix = fpath.suffix.lower()
                if suffix == ".py":
                    c_list, s_list = self.parser.parse_python_file(fpath, rel, index_name=index_name)
                    all_chunks.extend(c_list)
                    all_symbols.extend(s_list)
                    scanned_files += 1
                elif include_markdown and suffix == ".md":
                    md_chunks = self.parser.parse_markdown_file(fpath, rel, index_name=index_name)
                    all_chunks.extend(md_chunks)
                    scanned_files += 1

        elapsed = round(time.perf_counter() - start_t, 2)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        stats = IndexStats(
            name=index_name,
            project_root=str(root_path),
            total_files=scanned_files,
            total_chunks=len(all_chunks),
            total_symbols=len(all_symbols),
            elapsed_seconds=elapsed,
            updated_at=now_str,
            storage_engine=self.storage.active_engine,
        )

        self.storage.save_index(stats, all_chunks, all_symbols)
        logger.info(
            f"[CodeHelperRAG] Индекс '{index_name}' собран: {scanned_files} файлов, "
            f"{len(all_chunks)} чанков, {len(all_symbols)} символов за {elapsed}с. "
            f"Хранилище: {self.storage.active_engine}"
        )
        return stats

    def search_code(self, query: str, index_name: str = "codebase", top_k: int = 5) -> List[Dict[str, Any]]:
        """Семантический и текстуальный поиск по фрагментам кода."""
        raw_results = self.storage.search_chunks(query, index_name=index_name, top_k=top_k * 2)
        if not raw_results:
            return []

        q_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        scored = []
        for r in raw_results:
            text = f"{r.get('symbol_name', '')} {r.get('content', '')} {r.get('file_path', '')}".lower()
            score = 0.3
            for term in q_terms:
                if term in r.get("symbol_name", "").lower():
                    score += 0.4
                elif term in text:
                    score += 0.15
            score = min(score, 1.0)
            item = dict(r)
            item["relevance_score"] = round(score, 2)
            scored.append(item)

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def search_symbols(self, symbol_query: str, index_name: str = "codebase", limit: int = 15) -> List[Dict[str, Any]]:
        """Поиск по именам классов, функций и методов."""
        return self.storage.search_symbols(symbol_query, index_name=index_name, limit=limit)

    def extract_signals(self, error_message: str, logs: List[str]) -> Dict[str, Any]:
        """Извлечение путей к файлам, строк, исключений и имен символов."""
        full_text = f"{error_message}\n" + "\n".join(logs)
        locations: List[Tuple[str, int]] = []
        for match in _TRACEBACK_FILE_LINE_RE.finditer(full_text):
            fpath = match.group(1) or match.group(2)
            line_no = int(match.group(3))
            locations.append((fpath.replace("\\", "/"), line_no))

        exceptions = []
        for match in _EXCEPTION_RE.finditer(full_text):
            exceptions.append({"type": match.group(1), "message": match.group(2).strip()})

        symbols = []
        for word in _SYMBOL_CANDIDATE_RE.findall(full_text):
            if word not in {"File", "line", "Traceback", "None", "True", "False", "Error", "Exception"}:
                symbols.append(word)

        return {
            "locations": locations[:10],
            "exceptions": exceptions[:5],
            "candidate_symbols": list(dict.fromkeys(symbols))[:15],
        }

    async def diagnose(
        self,
        question: str = "",
        logs: Optional[List[str]] = None,
        error_message: str = "",
        index_name: str = "codebase",
        top_k: int = 6,
        use_llm: bool = True,
    ) -> DiagnosticConclusion:
        """Синтез структурированного заключения по вопросу, ошибке или трейсбеку."""
        start_t = time.perf_counter()
        logs_list = logs or []
        signals = self.extract_signals(error_message, logs_list)

        search_query = error_message or (" ".join(logs_list[:3]) if logs_list else question)
        matched_chunks = self.search_code(search_query, index_name=index_name, top_k=top_k)

        affected: List[CodeLocation] = []
        for loc_file, loc_line in signals.get("locations", []):
            base_name = Path(loc_file).name
            matched_syms = self.search_symbols(base_name, index_name=index_name, limit=3)
            sym_name = matched_syms[0].get("symbol", "") if matched_syms else ""
            affected.append(
                CodeLocation(
                    file_path=loc_file,
                    symbol_name=sym_name,
                    symbol_type="function" if sym_name else "file",
                    start_line=loc_line,
                    end_line=loc_line + 5,
                    relevance_score=0.95,
                    snippet=f"Ошибка зафиксирована на строке {loc_line}",
                )
            )

        for chunk in matched_chunks[:3]:
            if not any(a.file_path == chunk.get("file_path") for a in affected):
                affected.append(
                    CodeLocation(
                        file_path=chunk.get("file_path", ""),
                        symbol_name=chunk.get("symbol_name", ""),
                        symbol_type=chunk.get("symbol_type", "module"),
                        start_line=chunk.get("start_line", 1),
                        end_line=chunk.get("end_line", 1),
                        relevance_score=chunk.get("relevance_score", 0.7),
                        snippet=chunk.get("snippet", "")[:300],
                    )
                )

        # Детерминированный синтез заключения
        exc_info = signals.get("exceptions", [])
        if exc_info:
            first_exc = exc_info[0]
            summary = f"Обнаружено исключение {first_exc['type']}: {first_exc['message']}"
            root_cause = f"Сбой вызван {first_exc['type']} в процессе выполнения операции."
            severity = "error"
        elif error_message:
            summary = f"Анализ инцидента: {error_message[:120]}"
            root_cause = "Обнаружено аварийное завершение или некорректные входные параметры."
            severity = "error"
        else:
            summary = f"Ответ на вопрос по архитектуре: {question[:120]}"
            root_cause = "Архитектурный анализ кодовой базы."
            severity = "info"

        explanation = (
            f"На основе AST-индексации найдено {len(affected)} релевантных участков кода. "
            f"База знаний хранит {len(matched_chunks)} связанных чанков. "
            f"Первичная локализация указывает на файлы: {', '.join(a.file_path for a in affected[:3])}."
        )

        steps: List[CodeRemediationStep] = []
        if affected:
            primary_file = affected[0].file_path
            steps.append(
                CodeRemediationStep(
                    title="Проверка точки сбоя",
                    description=f"Проверьте строку {affected[0].start_line} в файле {primary_file}.",
                    target_file=primary_file,
                    suggested_code="# Добавьте валидацию входных данных или блок try/except",
                )
            )
        steps.append(
            CodeRemediationStep(
                title="Запуск верификационных тестов",
                description="Выполните запуск модульных тестов с покрытием для подтверждения исправления.",
                target_file="",
                suggested_code="pytest tests/ -v",
            )
        )

        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        conclusion = DiagnosticConclusion(
            summary=summary,
            root_cause=root_cause,
            explanation=explanation,
            severity=severity,
            confidence=0.88 if affected else 0.65,
            affected_locations=affected,
            remediation_steps=steps,
            extracted_signals=signals,
            source_mode="deterministic_ast",
            execution_time_ms=elapsed_ms,
        )

        self.storage.save_diagnostic(conclusion, query=question, error_message=error_message)
        return conclusion
