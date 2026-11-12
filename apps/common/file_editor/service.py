# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - Backend Service
# =============================================================================
# Description:
#   Сервисный уровень универсального редактора файлов (apps/common/file_editor).
#   Обеспечивает:
#   - Чтение любых типов файлов (код, текст, Markdown, CSV/TSV, .ipynb, SVG,
#     изображения, PDF, аудио/видео, бинарные файлы с Base64 и Hex-дампом).
#   - Сохранение текстовых файлов (с контролем кодировки и CRLF/LF).
#   - Побайтовый патч бинарных файлов из Hex-редактора и сохранение Base64.
#   - Форматирование и валидацию синтаксиса (JSON, XML, CSV, .ipynb и др.).
#   - Построчное сравнение (Unified Diff) буфера редактора с версией на диске.
#
# File: service.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:20
# =============================================================================

from __future__ import annotations
"""Сервис чтения, записи, форматирования, диффинга и бинарного патчинга файлов."""

import base64
import csv
import difflib
import io
import json
import os
import re
import xml.dom.minidom
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.common.file_editor.catalog import SupportedFileCatalog
from apps.common.file_editor.models import (
    EditorMode,
    FileDiffRequest,
    FileFormatRequest,
    FileSaveRequest,
)

# Максимальный размер файла для чтения целиком в ОЗУ (50 МБ)
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


class FileEditorService:
    """Универсальный сервис файлового редактора с поддержкой всех форматов VS Code."""

    def __init__(self, base_root: Optional[Path] = None) -> None:
        """Инициализирует сервис редактора файлов.

        Args:
            base_root: Опциональный корневой каталог для автономного режима (тестов или прямого доступа).
        """
        self._base_root = base_root.resolve() if base_root else None
        self._wm: Any = None

    def _get_workspace_manager(self) -> Any:
        """Лениво возвращает экземпляр WorkspaceManager, если доступен стек ai_assistant."""
        if self._wm is None:
            try:
                from apps.ai_assistant.core.workspace_manager import WorkspaceManager
                self._wm = WorkspaceManager()
            except Exception as exc:
                logger.warning(f"[FileEditorService] WorkspaceManager недоступен: {exc}")
        return self._wm

    def resolve_workspace_and_file(
        self,
        rel_path: str,
        workspace_id: Optional[str] = None,
    ) -> Tuple[str, Path, str, Path]:
        """Разрешает рабочее пространство и проверяет безопасность относительного пути.

        Args:
            rel_path: Относительный путь к файлу внутри рабочей области.
            workspace_id: Идентификатор рабочего пространства (опционально).

        Returns:
            Кортеж `(resolved_ws_id, ws_root_path, clean_rel_path, target_file_path)`.

        Raises:
            ValueError: При пустом пути или попытке выхода за пределы каталога (path traversal).
        """
        clean_rel = (rel_path or "").replace("\x00", "").strip().replace("\\", "/").strip("/")
        parts = [p for p in clean_rel.split("/") if p and p != "."]
        if not parts or ".." in parts:
            raise ValueError("Недопустимый относительный путь к файлу.")
        clean_rel = "/".join(parts)

        if self._base_root is not None:
            ws_root = self._base_root
            resolved_ws = workspace_id or "custom"
        else:
            wm = self._get_workspace_manager()
            if wm is not None:
                target_ws = workspace_id or wm.store.get_active_workspace_id()
                if not target_ws:
                    all_ws = wm.list_workspaces()
                    target_ws = all_ws[0]["workspace_id"] if all_ws else "demo"
                _, ws_root = wm._get_or_create_workspace(target_ws)
                resolved_ws = target_ws
            else:
                from header import __root__
                safe_ws_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "", (workspace_id or "demo")).strip(".") or "demo"
                ws_base = (__root__ / "data" / "workspaces").resolve()
                ws_root = (ws_base / safe_ws_id).resolve()
                try:
                    ws_root.relative_to(ws_base)
                except ValueError:
                    raise ValueError(f"Недопустимый идентификатор рабочего пространства: {workspace_id}")
                ws_root.mkdir(parents=True, exist_ok=True)
                resolved_ws = safe_ws_id

        ws_root_resolved = ws_root.resolve()
        target = (ws_root_resolved / clean_rel).resolve()
        try:
            target.relative_to(ws_root_resolved)
        except ValueError:
            raise ValueError(f"Путь '{rel_path}' выходит за пределы рабочей директории.")

        return resolved_ws, ws_root_resolved, clean_rel, target

    @staticmethod
    def compute_fnv1a_32(data: bytes) -> int:
        """Вычисляет 32-битный хеш FNV-1a (идентичный функции `fnv1a_hash` в Wasm-ядре)."""
        h = 2166136261
        for b in data:
            h ^= b
            h = (h * 16777619) & 0xFFFFFFFF
        return h

    def read_file(
        self,
        rel_path: str,
        workspace_id: Optional[str] = None,
        max_hex_preview_bytes: int = 262144,
    ) -> Dict[str, Any]:
        """Считывает любой файл и подготавливает полный пакет данных для Wasm-редактора.

        Args:
            rel_path: Относительный путь к файлу.
            workspace_id: Идентификатор рабочего пространства.
            max_hex_preview_bytes: Лимит байтов для передачи в Base64 (по умолчанию 256 КБ).

        Returns:
            Словарь с метаданными типа файла, текстовым и/или Base64-содержимым и хешем.

        Raises:
            FileNotFoundError: Если целевой файл не существует.
            ValueError: Если путь указывает на директорию.
        """
        resolved_ws, _, clean_rel, target = self.resolve_workspace_and_file(rel_path, workspace_id)
        if not target.exists():
            raise FileNotFoundError(f"Файл '{clean_rel}' не найден в рабочем пространстве '{resolved_ws}'.")
        if target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' указывает на директорию, а не на файл.")

        stat_size = target.stat().st_size
        if stat_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Размер файла '{clean_rel}' ({stat_size} байт) превышает максимально допустимый лимит редактора ({MAX_FILE_SIZE_BYTES} байт)."
            )

        raw_bytes = target.read_bytes()
        size_bytes = len(raw_bytes)
        is_binary_detected = b"\x00" in raw_bytes[:8192]
        descriptor = SupportedFileCatalog.get_descriptor(clean_rel, is_binary_detected=is_binary_detected)

        is_binary = is_binary_detected or descriptor.is_binary_default
        line_ending = "CRLF" if b"\r\n" in raw_bytes[:8192] else "LF"
        fnv1a_hex = f"{self.compute_fnv1a_32(raw_bytes):08x}"

        content_text: Optional[str] = None
        lines_count = 0
        if not is_binary:
            content_text = raw_bytes.decode("utf-8", errors="replace")
            lines_count = max(1, len(content_text.splitlines()))

        # Передаём Base64-представление для бинарных файлов, картинок, PDF и режима Hex-редактора
        slice_bytes = raw_bytes[:max_hex_preview_bytes]
        b64_data = base64.b64encode(slice_bytes).decode("ascii")

        return {
            "status": "ok",
            "workspace_id": resolved_ws,
            "rel_path": clean_rel,
            "file_name": target.name,
            "size": size_bytes,
            "is_binary": is_binary,
            "line_ending": line_ending,
            "encoding": "utf-8",
            "lines_count": lines_count,
            "fnv1a_hash": fnv1a_hex,
            "descriptor": descriptor.model_dump(),
            "content": content_text,
            "base64_content": b64_data,
            "truncated_binary": size_bytes > max_hex_preview_bytes,
        }

    def save_file(self, req: FileSaveRequest) -> Dict[str, Any]:
        """Сохраняет текстовый или бинарный файл (включая побайтовые Hex-патчи) и создаёт Git-коммит.

        Args:
            req: Запрос `FileSaveRequest` с новыми данными или списком байтовых правок.

        Returns:
            Словарь с обновлённым размером, хешем FNV-1a и статусом фиксации в Git.
        """
        resolved_ws, ws_root, clean_rel, target = self.resolve_workspace_and_file(
            req.rel_path,
            req.workspace_id,
        )
        if target.exists() and target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является директорией.")

        target.parent.mkdir(parents=True, exist_ok=True)

        # 1. Побайтовый патч существующего файла из Hex-редактора
        if req.hex_patches:
            if target.exists() and target.stat().st_size > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"Размер файла '{clean_rel}' превышает лимит ({MAX_FILE_SIZE_BYTES} байт) для побайтового патча."
                )
            current = bytearray(target.read_bytes() if target.exists() else b"")
            for patch in req.hex_patches:
                if patch.offset >= MAX_FILE_SIZE_BYTES:
                    raise ValueError(f"Смещение байта {patch.offset} превышает максимально допустимый размер файла.")
                if patch.offset >= len(current):
                    current.extend(b"\x00" * (patch.offset - len(current) + 1))
                current[patch.offset] = patch.value & 0xFF
            final_bytes = bytes(current)
        # 2. Запись бинарного содержимого из Base64 (например, после редактирования изображения на Canvas)
        elif req.base64_content is not None:
            raw_b64 = req.base64_content
            if "," in raw_b64 and raw_b64.startswith("data:"):
                raw_b64 = raw_b64.split(",", 1)[1]
            final_bytes = base64.b64decode(raw_b64)
            if len(final_bytes) > MAX_FILE_SIZE_BYTES:
                raise ValueError(f"Размер сохраняемых данных превышает лимит ({MAX_FILE_SIZE_BYTES} байт).")
        # 3. Запись текстового содержимого с учётом выбранного типа переводов строк (LF / CRLF)
        elif req.content is not None:
            normalized = req.content.replace("\r\n", "\n")
            if req.line_ending.upper() == "CRLF":
                normalized = normalized.replace("\n", "\r\n")
            final_bytes = normalized.encode(req.encoding or "utf-8")
            if len(final_bytes) > MAX_FILE_SIZE_BYTES:
                raise ValueError(f"Размер сохраняемого текста превышает лимит ({MAX_FILE_SIZE_BYTES} байт).")
        else:
            raise ValueError("Не передано содержимое для сохранения (content, base64_content или hex_patches).")

        # Атомарная запись через временный файл для защиты от повреждения при сбое
        tmp_target = target.with_name(f".{target.name}.tmp")
        try:
            tmp_target.write_bytes(final_bytes)
            os.replace(tmp_target, target)
        finally:
            if tmp_target.exists():
                try:
                    tmp_target.unlink()
                except OSError:
                    pass

        commit_msg = (
            req.commit_message.strip()
            if req.commit_message and req.commit_message.strip()
            else f"Обновлён в Wasm File Editor: {clean_rel}"
        )

        # Если используется WorkspaceManager и включён флаг commit_to_git — фиксируем изменения в Git
        wm = self._get_workspace_manager()
        if req.commit_to_git and wm is not None and self._base_root is None:
            try:
                wm._ensure_git_repo(ws_root)
                wm._run_git(ws_root, ["add", clean_rel])
                wm._run_git(ws_root, ["commit", "-m", commit_msg])
                if req.content is not None:
                    wm.import_document(
                        workspace_id=resolved_ws,
                        document_id=clean_rel,
                        content=req.content,
                        commit_message=commit_msg,
                    )
            except Exception as exc:
                logger.warning(f"[FileEditorService] Предупреждение Git при сохранении {clean_rel}: {exc}")

        fnv1a_hex = f"{self.compute_fnv1a_32(final_bytes):08x}"
        logger.info(f"[FileEditorService] Сохранён файл '{clean_rel}' ({len(final_bytes)} байт) в '{resolved_ws}'")
        return {
            "status": "ok",
            "workspace_id": resolved_ws,
            "rel_path": clean_rel,
            "size": len(final_bytes),
            "fnv1a_hash": fnv1a_hex,
            "commit_message": commit_msg,
        }

    @staticmethod
    def format_buffer(req: FileFormatRequest) -> Dict[str, Any]:
        """Форматирует и валидирует текстовый буфер в зависимости от типа файла.

        Args:
            req: Запрос `FileFormatRequest` с исходным текстом и расширением файла.

        Returns:
            Словарь с отформатированным содержимым и списком диагностических сообщений.
        """
        ext = (req.extension or "").lstrip(".").lower()
        text = req.content
        diagnostics: List[str] = []

        # 1. JSON, JSONL, Jupyter Notebook (.ipynb)
        if ext in {"json", "jsonc", "ipynb"}:
            try:
                parsed = json.loads(text)
                formatted = json.dumps(parsed, ensure_ascii=False, indent=req.indent_size) + "\n"
                return {"status": "ok", "formatted": formatted, "valid": True, "diagnostics": []}
            except json.JSONDecodeError as je:
                diagnostics.append(f"Синтаксическая ошибка JSON (строка {je.lineno}, столбец {je.colno}): {je.msg}")
                return {"status": "error", "formatted": text, "valid": False, "diagnostics": diagnostics}

        # 2. XML и SVG
        if ext in {"xml", "svg", "xsd", "xsl"}:
            try:
                dom = xml.dom.minidom.parseString(text.encode("utf-8"))
                pretty = dom.toprettyxml(indent=" " * req.indent_size)
                clean_lines = [line for line in pretty.splitlines() if line.strip()]
                return {
                    "status": "ok",
                    "formatted": "\n".join(clean_lines) + "\n",
                    "valid": True,
                    "diagnostics": [],
                }
            except Exception as xe:
                diagnostics.append(f"Ошибка разбора XML/SVG: {xe}")
                return {"status": "error", "formatted": text, "valid": False, "diagnostics": diagnostics}

        # 3. Табличные файлы CSV / TSV (нормализация колонок и кавычек)
        if ext in {"csv", "tsv"}:
            delimiter = "\t" if ext == "tsv" else ","
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            out = io.StringIO()
            writer = csv.writer(out, delimiter=delimiter, lineterminator="\n")
            for row in reader:
                writer.writerow([cell.strip() for cell in row])
            return {"status": "ok", "formatted": out.getvalue(), "valid": True, "diagnostics": []}

        # 4. Для исходного кода и Markdown: удаление висячих пробелов справа и нормализация пустых строк в конце
        cleaned_lines = [line.rstrip() for line in text.splitlines()]
        formatted_code = "\n".join(cleaned_lines) + ("\n" if cleaned_lines else "")
        return {"status": "ok", "formatted": formatted_code, "valid": True, "diagnostics": []}

    def compute_diff(self, req: FileDiffRequest) -> Dict[str, Any]:
        """Вычисляет построчный Unified Diff между сохранённой на диске версией и буфером редактора."""
        _, _, clean_rel, target = self.resolve_workspace_and_file(req.rel_path, req.workspace_id)
        original_text = ""
        if target.exists() and target.is_file():
            if target.stat().st_size > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"Размер файла '{clean_rel}' превышает допустимый лимит ({MAX_FILE_SIZE_BYTES} байт) для вычисления Diff."
                )
            original_text = target.read_bytes().decode("utf-8", errors="replace")

        orig_lines = original_text.splitlines()
        mod_lines = req.modified_content.splitlines()
        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=f"a/{clean_rel}",
                tofile=f"b/{clean_rel}",
                lineterm="",
            )
        )
        added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
        return {
            "status": "ok",
            "rel_path": clean_rel,
            "has_changes": bool(diff_lines),
            "added_lines": added,
            "removed_lines": removed,
            "unified_diff": "\n".join(diff_lines),
        }
