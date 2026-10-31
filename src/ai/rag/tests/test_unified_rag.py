# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Unified RAG Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для TextRAG, PixelRAG, LogRAG и UnifiedKnowledgeHub.
#
# Usage Examples:
#   pytest src/ai/rag/tests/test_unified_rag.py -v
#
# File: test_unified_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:30:30
# =============================================================================

from __future__ import annotations
"""Модульные тесты для TextRAG, PixelRAG, LogRAG, CodebaseRAG и UnifiedKnowledgeHub."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.rag.codebase_rag import CodebaseRAG
from src.ai.rag.text_rag import TextRAG
from src.ai.rag.pixel_rag import PixelRAG
from src.ai.rag.log_rag import LogRAG
from src.ai.rag.router import init_router
from src.ai.rag.unified_hub import UnifiedKnowledgeHub
from apps.windows.wikillm.models import ArtifactType, KnowledgeEntity, KnowledgeSource


def test_text_rag_crud_and_search(tmp_path: Path) -> None:
    """Проверка добавления документов, сохранения и поиска в TextRAG."""
    index_path = tmp_path / "test_text_index"
    rag = TextRAG(db_path=index_path, dimension=64)

    docs = [
        {"id": "doc1", "text": "Ошибка инициализации DirectML в Windows 11", "meta": {"category": "ml"}},
        {"id": "doc2", "text": "Настройка сетевого интерфейса и DNS серверов", "meta": {"category": "network"}},
    ]
    added = rag.add_documents(docs)
    assert added == 2
    assert rag.count() == 2

    results = rag.search("DirectML Windows", top_k=2)
    assert len(results) > 0
    assert results[0]["id"] == "doc1"

    # Удаление документа
    rag.delete_document("doc1")
    assert rag.count() == 1


def test_pixel_rag_indexing_and_search(tmp_path: Path) -> None:
    """Проверка индексации скриншотов и поиска в PixelRAG."""
    pixel_rag = PixelRAG(storage_dir=tmp_path / "pixels")
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    entry = pixel_rag.index_image_bytes(
        data=img_bytes,
        filename="bsod_dialog.png",
        title="Скриншот экрана критической ошибки",
        ocr_text="CRITICAL_PROCESS_DIED 0x000000EF",
        metadata={"source": "telemetry"},
    )
    assert entry["id"].startswith("img_")
    assert pixel_rag.get_status()["total_images"] == 1

    # Поиск по OCR тексту
    search_res = pixel_rag.search_by_text("CRITICAL_PROCESS", top_k=2)
    assert len(search_res) == 1
    assert search_res[0]["filename"] == "bsod_dialog.png"

    # Визуальный поиск по байтам
    visual_res = pixel_rag.search_by_visual(img_bytes, top_k=2)
    assert len(visual_res) == 1
    assert visual_res[0]["score"] >= 0.95


def test_log_rag_chunking_and_wiki_linkage(tmp_path: Path) -> None:
    """Проверка добавления лог-чанков и связывания с базой знаний в LogRAG."""
    log_rag = LogRAG(storage_dir=tmp_path / "logs")
    chunk = log_rag.add_log_chunk(
        chunk_id="chunk_10016",
        title="DistributedCOM DCOM Permission Error",
        content="The application-specific permission settings do not grant Local Activation permission for the COM Server application",
        channel="System",
        provider="DistributedCOM",
        event_ids=[10016],
    )
    assert chunk["id"] == "chunk_10016"

    # Поиск по чанкам
    search_res = log_rag.search_chunks("DistributedCOM permission", top_k=2)
    assert len(search_res) == 1
    assert search_res[0]["id"] == "chunk_10016"

    # Проверка создания сущности в WikiStorage
    ent = log_rag.wiki_storage.get_entity("windows_event:DistributedCOM:10016")
    assert ent is not None
    assert ent.diagnostic_info is not None
    assert len(ent.diagnostic_info.symptoms) > 0


@pytest.mark.asyncio
async def test_unified_knowledge_hub_resolution(tmp_path: Path) -> None:
    """Проверка сквозного разрешения через UnifiedKnowledgeHub."""
    hub = UnifiedKnowledgeHub(base_dir=tmp_path / "unified")

    # Сохраняем сущность в WikiLLM
    test_ent = KnowledgeEntity(
        canonical_key="win32:0x80070490",
        entity_type=ArtifactType.WINDOWS_ERROR,
        name="ERROR_NOT_FOUND",
        summary="Элемент не найден в хранилище компонентов Windows.",
        provenance_source=KnowledgeSource.DOCUMENTED,
    )
    hub.wikillm.storage.save_entity(test_ent)

    # Добавляем текстовый документ
    hub.text_rag.add_documents([
        {"id": "kb1", "text": "Инструкция по устранению ошибки 0x80070490 через DISM", "meta": {}}
    ])

    # Разрешение через Hub
    res = await hub.resolve_query("0x80070490", sync_gemini=False)
    assert res["source"] == "wikillm"
    assert res["wikillm"]["canonical_key"] == "win32:0x80070490"
    assert len(res["text_rag_matches"]) > 0

    # Мульти-поиск
    all_res = hub.search_all("0x80070490")
    assert all_res["total_found"] >= 1


@pytest.mark.asyncio
async def test_codebase_rag_ast_indexing_and_diagnosis(tmp_path: Path) -> None:
    """Проверка индексации AST Python и Markdown-документации, поиска символов и выдачи заключений по логам и ошибкам."""
    src_dir = tmp_path / "sample_proj"
    src_dir.mkdir(parents=True, exist_ok=True)

    py_file = src_dir / "payment_processor.py"
    py_file.write_text(
        '''"""Модуль обработки платежных транзакций."""

class PaymentProcessor:
    """Процессор расчетов и комиссий."""

    def calculate_fee(self, amount: float, rate: float) -> float:
        """Расчет комиссии по ставке.

        Выбрасывает ZeroDivisionError при нулевом делителе.
        """
        if rate < 0:
            raise ValueError("Ставка комиссии не может быть отрицательной")
        return amount / rate
''',
        encoding="utf-8",
    )

    md_file = src_dir / "README.md"
    md_file.write_text(
        "# Платежный шлюз\n\nКласс `PaymentProcessor` отвечает за расчет комиссий в `payment_processor.py`.\n",
        encoding="utf-8",
    )

    code_rag = CodebaseRAG(storage_dir=tmp_path / "code_idx", dimension=64)
    stats = code_rag.build_index(project_root=src_dir, index_name="test_code")
    assert stats["total_files"] == 2
    assert stats["total_symbols"] >= 2
    assert stats["total_chunks"] >= 3

    # Поиск AST-символа
    syms = code_rag.search_symbols("calculate_fee", index_name="test_code")
    assert len(syms) >= 1
    assert syms[0]["symbol"] == "PaymentProcessor.calculate_fee"
    assert syms[0]["path"] == "payment_processor.py"

    # Диагностика по списку логов и стек-трейсу (детерминированный AST режим)
    conclusion = await code_rag.diagnose(
        question="Почему падает расчет комиссии?",
        logs=[
            "2026-10-31 18:00:01 [INFO] Запуск транзакции ID=99",
            "2026-10-31 18:00:02 [ERROR] Сбой в payment_processor.py:14",
        ],
        error_message='File "payment_processor.py", line 14, in calculate_fee\nZeroDivisionError: float division by zero',
        index_name="test_code",
        use_llm=False,
    )

    assert conclusion.severity == "error"
    assert "ZeroDivisionError" in conclusion.root_cause
    assert len(conclusion.affected_locations) > 0
    assert conclusion.affected_locations[0].file_path == "payment_processor.py"
    assert "calculate_fee" in conclusion.affected_locations[0].symbol_name
    assert len(conclusion.remediation_steps) >= 1


def test_codebase_rag_fastapi_router_endpoints(tmp_path: Path) -> None:
    """Проверка REST API эндпоинтов /api/rag/codebase/*."""
    proj_dir = tmp_path / "api_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "worker.py").write_text(
        "def run_worker_task(task_id: int) -> bool:\n    '''Запуск воркера.'''\n    if task_id <= 0:\n        raise RuntimeError('Invalid task_id')\n    return True\n",
        encoding="utf-8",
    )

    hub = UnifiedKnowledgeHub(base_dir=tmp_path / "hub_data")
    app = FastAPI()
    app.include_router(init_router(hub))
    client = TestClient(app)

    # 1. Сборка индекса через POST /api/rag/codebase/build
    build_resp = client.post(
        "/api/rag/codebase/build",
        json={"project_root": str(proj_dir), "index_name": "codebase"},
    )
    assert build_resp.status_code == 200
    assert build_resp.json()["result"]["total_symbols"] == 1

    # 2. Список индексов через GET /api/rag/codebase/indexes
    idx_resp = client.get("/api/rag/codebase/indexes")
    assert idx_resp.status_code == 200
    assert len(idx_resp.json()["indexes"]) == 1

    # 3. Поиск символов через POST /api/rag/codebase/symbols
    sym_resp = client.post(
        "/api/rag/codebase/symbols",
        json={"symbol": "run_worker_task", "index_name": "codebase"},
    )
    assert sym_resp.status_code == 200
    assert sym_resp.json()["total_found"] == 1

    # 4. Заключение по ошибке и логам через POST /api/rag/codebase/diagnose
    diag_resp = client.post(
        "/api/rag/codebase/diagnose",
        json={
            "question": "Из-за чего останавливается воркер?",
            "logs": ["[CRITICAL] worker.py:4 task_id=0 rejected"],
            "error_message": 'File "worker.py", line 4, in run_worker_task\nRuntimeError: Invalid task_id',
            "index_name": "codebase",
            "use_llm": False,
        },
    )
    assert diag_resp.status_code == 200
    payload = diag_resp.json()
    assert "RuntimeError" in payload["root_cause"]
    assert payload["affected_locations"][0]["file_path"] == "worker.py"


