# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: RAG Document Cleaner Plugin Controller
# =============================================================================
# Description:
#   Плагин для очистки, нормализации и чанкинга разнородных документов для RAG.
#
# File: plugin.py
# Project: ai-breadboard
# Package: plugins.rag_cleaner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:39:10
# =============================================================================

from __future__ import annotations
"""Плагин очистки и подготовки документов для векторных баз знаний RAG."""

import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from header import __root__
from logger import logger
from plugins.base import BasePlugin
from .cleaner import RAGDocumentCleanerCore


class RAGCleanerPlugin(BasePlugin):
    """Плагин очистки, нормализации и чанкинга документов для RAG."""

    name: str = "rag_cleaner"
    title: str = "RAG Document Cleaner & Ingestor"
    version: str = "1.0.0"
    description: str = "Sanitizes and chunks heterogeneous files (PDF, DOCX, ZIP, HTML, CSV, JSON, TXT) for RAG."
    icon: str = "🞩"
    category: str = "tools"
    enabled: bool = True
    is_system: bool = False
    scope: str = "user"

    def __init__(self, ai_model: Any = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Инициализирует плагин очистки документов для RAG."""
        super().__init__(ai_model=ai_model, config=config)
        min_chunk = self.config.get("min_chunk_len", 20)
        max_chunk = self.config.get("max_chunk_len", 1500)
        self.cleaner = RAGDocumentCleanerCore(min_chunk_len=min_chunk, max_chunk_len=max_chunk)

    async def initialize(self) -> bool:
        """Выполняет инициализацию плагина."""
        logger.info("Плагин RAG Cleaner успешно инициализирован.")
        return True

    async def handle(self, message: str, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Обрабатывает запрос на очистку файла или директории."""
        yield {"status": "started", "text": f"Processing RAG cleaning for: {message}"}
        path = Path(message.strip())
        if path.exists():
            chunks = self.cleaner.process_target(path)
            yield {"status": "complete", "count": len(chunks), "chunks": chunks[:5]}
        else:
            yield {"status": "error", "text": f"Path not found: {message}"}

    def get_manifest(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Возвращает манифест плагина с поддерживаемыми расширениями и действиями."""
        manifest = super().get_manifest(*args, **kwargs)
        manifest.update({
            "supported_extensions": [".zip", ".tar", ".gz", ".tgz", ".docx", ".pdf", ".html", ".htm", ".csv", ".json", ".txt", ".md"],
            "actions": [
                {
                    "name": "clean_file",
                    "description": "Clean and chunk a single file or archive into RAG chunks.",
                    "parameters": {"file_path": "string"}
                },
                {
                    "name": "clean_directory",
                    "description": "Clean and chunk all documents in a directory into RAG chunks.",
                    "parameters": {"dir_path": "string", "output_jsonl": "string (optional)"}
                }
            ]
        })
        return manifest

    async def execute_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполняет административное действие по очистке файла или каталога."""
        params = params or {}
        if action == "clean_file":
            file_path = params.get("file_path")
            if not file_path:
                return {"success": False, "error": "Missing 'file_path' parameter."}
            chunks = list(self.cleaner.process_file(file_path))
            return {"success": True, "count": len(chunks), "chunks": chunks}

        elif action == "clean_directory":
            dir_path = params.get("dir_path")
            if not dir_path:
                return {"success": False, "error": "Missing 'dir_path' parameter."}
            chunks = self.cleaner.process_target(dir_path)
            out_file = params.get("output_jsonl")
            if out_file:
                out_path = Path(out_file).resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = out_path.with_name(f".{out_path.name}.tmp")
                try:
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        for c in chunks:
                            f.write(json.dumps(c, ensure_ascii=False) + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_path, out_path)
                finally:
                    if tmp_path.exists():
                        try:
                            tmp_path.unlink()
                        except OSError:
                            pass
            return {"success": True, "count": len(chunks), "saved_to": out_file, "chunks": chunks[:5]}

        return {"success": False, "error": f"Unknown action: {action}"}

    def get_tools(self) -> List[Dict[str, Any]]:
        """Возвращает декларации инструментов для LLM."""
        return [
            {
                "name": "clean_and_chunk_documents_for_rag",
                "description": "Cleans, normalizes, and extracts semantic chunks from user uploaded files or archives for RAG embeddings.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_path": {
                            "type": "string",
                            "description": "Path to file, archive (.zip/.tar), or folder to clean."
                        }
                    },
                    "required": ["target_path"]
                }
            }
        ]
