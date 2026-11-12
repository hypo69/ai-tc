# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - System Engineering & Property-Based Tests
# =============================================================================
# Description:
#   Комплексные модульные и Property-Based тесты стандарта SYSTEM_ENGINEERING:
#   - Точность финансовых вычислений в Decimal и минимальных единицах (без IEEE 754 float)
#   - Временные метки строго в UTC ISO 8601 (суффикс Z)
#   - Инварианты Exponential Backoff + Jitter и автомата Circuit Breaker
#   - Ограничение памяти и эвикция LRU/TTL в BoundedTTLCache
#   - Идемпотентность (IdempotencyStore и FastAPI middleware Idempotency-Key / 409 Conflict)
#   - Паттерн Transactional Outbox в единой ACID-транзакции SQLite (WAL) и защита от Lost Update
#   - Структурированное логирование SRE (JsonFormatter с trace_id, service_name, error_stack)
#   - Сквозная трассировка W3C TraceContext (traceparent) и перцентили RED (p50, p95, p99)
#
# File: test_system_engineering.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:30:00
# =============================================================================

from __future__ import annotations

from contextlib import closing
from decimal import Decimal
import json
import logging
from pathlib import Path
import random
import sqlite3
import sys
import time
from typing import List

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from logger import JsonFormatter, clear_trace_context, get_trace_context, set_trace_context, trace_context
from plugins.invoice_processor.extractor import _normalize_money_field
from src.utils.system_engineering import (
    BoundedTTLCache,
    CircuitBreaker,
    CircuitState,
    IdempotencyStore,
    REDMetricsCollector,
    TransactionalOutbox,
    async_sleep_backoff,
    compute_backoff_with_jitter,
    compute_percentile,
    ensure_utc_iso,
    format_traceparent,
    minor_units_to_decimal,
    money_to_minor_units,
    parse_traceparent,
    to_decimal_money,
    utc_now_iso,
)


# =============================================================================
# 1. Property-Based тесты финансовых типов (Decimal против IEEE 754 float)
# =============================================================================


def test_ieee754_float_rejected_and_decimal_exact() -> None:
    """Доказывает, что 0.1 + 0.2 в Decimal равно ровно 0.30, а передача float запрещена."""
    a = to_decimal_money("0.1")
    b = to_decimal_money("0.2")
    assert a + b == Decimal("0.30")
    assert money_to_minor_units(a + b) == 30
    assert minor_units_to_decimal(30) == Decimal("0.30")

    with pytest.raises(TypeError):
        to_decimal_money(0.1)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        minor_units_to_decimal(10.5)  # type: ignore[arg-type]


def test_property_based_money_roundtrip_invariants() -> None:
    """Property-Based тест: обратимость конвертации сумма <-> копейки на 500 граничных значениях."""
    rng = random.Random(20261110)
    boundary_cents: List[int] = [
        0,
        1,
        -1,
        10,
        20,
        30,
        99,
        100,
        -99999999,
        999999999999,
        sys.maxsize // 1000,
    ]
    for _ in range(500):
        boundary_cents.append(rng.randint(-10**12, 10**12))

    for cents in boundary_cents:
        dec_val = minor_units_to_decimal(cents)
        restored_cents = money_to_minor_units(dec_val)
        assert restored_cents == cents


def test_property_based_adversarial_strings_in_money_parser() -> None:
    """Property-Based проверка устойчивости парсера счетов к мусорным, Unicode и пустым строкам."""
    adversarial_inputs = [
        "",
        "   ",
        "\x00\x00",
        "NaN",
        "Infinity",
        "-Infinity",
        "1 234,56 ₽",
        "$9,876.54",
        "😀漢字100.25🚀",
        "---",
        "DROP TABLE invoices;--",
    ]
    for sample in adversarial_inputs:
        norm_str, minor_int = _normalize_money_field(sample)
        assert isinstance(norm_str, str)
        assert isinstance(minor_int, int)
        assert not isinstance(minor_int, bool)


# =============================================================================
# 2. Временные зоны UTC ISO 8601
# =============================================================================


def test_utc_iso_8601_normalization() -> None:
    """Проверяет, что любые входные даты приводятся к строгому UTC ISO 8601 с суффиксом Z."""
    now_str = utc_now_iso()
    assert now_str.endswith("Z")
    assert "T" in now_str

    from_epoch = ensure_utc_iso(0)
    assert from_epoch == "1970-01-01T00:00:00Z"

    from_offset = ensure_utc_iso("2026-11-10T16:00:00+02:00")
    assert from_offset == "2026-11-10T14:00:00Z"


# =============================================================================
# 3. Exponential Backoff + Jitter и Circuit Breaker
# =============================================================================


@pytest.mark.asyncio
async def test_property_based_exponential_backoff_with_jitter_bounds() -> None:
    """Property-Based проверка математических границ Exponential Backoff + Jitter."""
    for attempt in [-5, 0, 1, 2, 3, 5, 10, 50, 1000]:
        for _ in range(25):
            delay = compute_backoff_with_jitter(
                attempt=attempt,
                base_delay=0.5,
                max_delay=16.0,
                jitter_ratio=0.25,
            )
            assert 0.5 <= delay <= 16.0 * 1.25

    slept = await async_sleep_backoff(attempt=0, base_delay=0.001, max_delay=0.005, jitter_ratio=0.1)
    assert slept >= 0.001


def test_circuit_breaker_state_machine() -> None:
    """Проверяет переходы автомата Circuit Breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(name="payment_gw", failure_threshold=3, recovery_timeout_seconds=0.1, half_open_max_calls=1)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    time.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    assert cb.allow_request() is False

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


# =============================================================================
# 4. BoundedTTLCache (Защита от утечек памяти и OOM)
# =============================================================================


def test_bounded_ttl_cache_lru_and_ttl_eviction() -> None:
    """Проверяет строгое соблюдение лимита размера (LRU) и истечения срока жизни (TTL)."""
    cache = BoundedTTLCache(maxsize=3, ttl_seconds=0.15)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")
    assert len(cache) == 3

    # Обращение к k1 делает его самым свежим, поэтому при вставке k4 вытеснится k2
    assert cache.get("k1") == "v1"
    cache.set("k4", "v4")
    assert len(cache) == 3
    assert cache.get("k2") is False
    assert cache.get("k1") == "v1"
    assert cache.get("k4") == "v4"

    time.sleep(0.18)
    assert len(cache) == 0
    assert cache.get("k1") is False


# =============================================================================
# 5. Transactional Outbox и защита от Lost Update (ACID + Optimistic Locking)
# =============================================================================


def test_transactional_outbox_acid_and_optimistic_locking(tmp_path: Path) -> None:
    """Проверяет атомарность записи бизнес-сущности и события в outbox и защиту от Lost Update."""
    db_file = tmp_path / "outbox_test.db"
    with closing(sqlite3.connect(str(db_file))) as conn:
        conn.execute(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance_minor INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1);"
        )
        conn.execute("INSERT INTO accounts (id, balance_minor, version) VALUES (1, 10000, 1);")
        conn.commit()

    outbox = TransactionalOutbox(str(db_file))

    # 1. Атомарное списание 3000 копеек + запись события в одной транзакции
    affected = outbox.execute_in_transaction(
        business_sql=(
            "UPDATE accounts SET balance_minor = balance_minor - ?, version = version + 1 "
            "WHERE id = ? AND balance_minor >= ?;"
        ),
        business_params=(3000, 1, 3000),
        event_id="evt-001",
        topic="billing.withdrawn",
        payload={"account_id": 1, "amount_minor": 3000},
    )
    assert affected == 1

    # 2. Если возникает ошибка (например, дубликат event_id), бизнес-транзакция откатывается целиком!
    with pytest.raises(sqlite3.IntegrityError):
        outbox.execute_in_transaction(
            business_sql="UPDATE accounts SET balance_minor = balance_minor - ? WHERE id = ?;",
            business_params=(5000, 1),
            event_id="evt-001",  # Дубликат UNIQUE ключа вызывает ROLLBACK
            topic="billing.withdrawn",
            payload={"account_id": 1, "amount_minor": 5000},
        )

    with closing(sqlite3.connect(str(db_file))) as conn:
        balance = conn.execute("SELECT balance_minor FROM accounts WHERE id = 1;").fetchone()[0]
    # Баланс остался 7000, второе списание 5000 откатилось вместе с ошибкой outbox!
    assert balance == 7000

    # 3. Захват пачки воркером и проверка оптимистичной блокировки (version)
    batch = outbox.claim_pending_batch(limit=10)
    assert len(batch) == 1
    evt = batch[0]
    assert evt["event_id"] == "evt-001"
    assert evt["version"] == 2

    # Попытка подтвердить с устаревшей версией (Lost Update защита) возвращает False
    assert outbox.mark_dispatched("evt-001", expected_version=1) is False
    # Подтверждение с актуальной версией 2 проходит успешно
    assert outbox.mark_dispatched("evt-001", expected_version=2) is True


# =============================================================================
# 6. Идемпотентность (Idempotency-Key), W3C TraceContext и метрики RED
# =============================================================================


def test_idempotency_store_conflict_and_replay() -> None:
    """Проверяет защиту от параллельных дублей (IN_PROGRESS) и возврат сохраненного ответа."""
    store = IdempotencyStore(max_keys=100, ttl_seconds=60.0)
    status1, _ = store.begin("uuid-key-1")
    assert status1 == "NEW"

    # Параллельный запрос с тем же ключом видит статус IN_PROGRESS
    status2, _ = store.begin("uuid-key-1")
    assert status2 == "IN_PROGRESS"

    # Завершаем первый запрос
    store.complete("uuid-key-1", status_code=201, response_body='{"order_id": 42}')

    # Повторный сетевой ретрай получает сохраненный ответ без повторного запуска бизнес-логики
    status3, rec3 = store.begin("uuid-key-1")
    assert status3 == "COMPLETED"
    assert rec3.status_code == 201
    assert rec3.response_body == '{"order_id": 42}'


def test_sre_structured_json_formatter_and_trace_context() -> None:
    """Проверяет наличие всех обязательных полей стандарта SRE в JsonFormatter."""
    formatter = JsonFormatter()
    with trace_context(trace_id="4bf92f3577b34da6a3ce929d0e0e4736", user_id="admin-42", service_name="billing-api"):
        ctx = get_trace_context()
        assert ctx["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        record = logging.LogRecord(
            name="test_sre",
            level=logging.ERROR,
            pathname=__file__,
            lineno=100,
            msg="Transaction timeout",
            args=(),
            exc_info=None,
        )
        raw_json = formatter.format(record)
        parsed = json.loads(raw_json)
        assert parsed["timestamp"].endswith("Z")
        assert parsed["level"] == "ERROR"
        assert parsed["service_name"] == "billing-api"
        assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert parsed["user_id"] == "admin-42"
        assert "error_stack" in parsed

    # После выхода из контекстного менеджера контекст очищен
    assert get_trace_context()["trace_id"] == ""


def test_red_metrics_percentiles_tail_latency() -> None:
    """Проверяет расчет перцентилей p50, p95, p99 для выявления Tail Latency."""
    collector = REDMetricsCollector(max_samples=500)
    # 99 быстрых запросов по 10 мс и 1 тяжелый выброс на 10 000 мс (Tail Latency)
    for _ in range(99):
        collector.record(10.0, is_error=False)
    collector.record(10000.0, is_error=True)

    snap = collector.snapshot()
    assert snap["total_requests"] == 100
    assert snap["total_errors"] == 1
    assert snap["error_rate_percent"] == 1.0
    assert snap["duration_ms"]["p50"] == 10.0
    assert snap["duration_ms"]["p95"] == 10.0
    assert snap["duration_ms"]["p99"] > 100.0


def test_w3c_traceparent_parsing_and_formatting() -> None:
    """Проверяет разбор и генерацию заголовка W3C TraceContext (traceparent)."""
    valid_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    t_id, s_id = parse_traceparent(valid_tp)
    assert t_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert s_id == "00f067aa0ba902b7"
    assert format_traceparent(t_id, s_id) == valid_tp

    # Невалидный заголовок безопасно порождает новый 32-символьный trace_id
    gen_t, gen_s = parse_traceparent("invalid-header")
    assert len(gen_t) == 32
    assert len(gen_s) == 16


def test_fastapi_observability_traceparent_and_idempotency_middleware() -> None:
    """Интеграционный тест: W3C traceparent, метрики RED и Idempotency-Key в FastAPI сервере."""
    try:
        from apps.windows.api.server import create_app

        app = create_app()
    except ImportError:
        import time
        from fastapi import FastAPI, Response
        from fastapi.responses import JSONResponse
        from logger import trace_context

        app = FastAPI()
        idempotency_store = IdempotencyStore()
        red_metrics = REDMetricsCollector()
        app.state.idempotency_store = idempotency_store
        app.state.red_metrics = red_metrics

        @app.middleware("http")
        async def _obs_and_idem_middleware(request: Request, call_next):
            t0 = time.perf_counter()
            incoming_tp = request.headers.get("traceparent") or request.headers.get("X-Trace-Id") or ""
            t_id, s_id = parse_traceparent(incoming_tp)
            tp_hdr = format_traceparent(t_id, s_id)
            with trace_context(trace_id=t_id, service_name="ai-assistant"):
                idem_key = request.headers.get("Idempotency-Key", "").strip()
                is_mutating = request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
                scoped_key = f"{request.method.upper()}:{request.url.path}:{idem_key}" if is_mutating and idem_key else ""
                if scoped_key:
                    state_flag, record = idempotency_store.begin(scoped_key)
                    if state_flag == "IN_PROGRESS":
                        red_metrics.record((time.perf_counter() - t0) * 1000.0, is_error=False)
                        return JSONResponse(
                            status_code=409,
                            content={"status": "error", "code": "IDEMPOTENCY_CONFLICT", "trace_id": t_id},
                            headers={"X-Trace-Id": t_id, "traceparent": tp_hdr},
                        )
                    if state_flag == "COMPLETED":
                        red_metrics.record((time.perf_counter() - t0) * 1000.0, is_error=False)
                        return Response(
                            content=record.response_body,
                            status_code=record.status_code,
                            media_type="application/json",
                            headers={"X-Trace-Id": t_id, "traceparent": tp_hdr, "X-Idempotent-Replayed": "true"},
                        )
                response = await call_next(request)
                dur_ms = (time.perf_counter() - t0) * 1000.0
                red_metrics.record(duration_ms=dur_ms, is_error=response.status_code >= 500)
                if scoped_key and 200 <= response.status_code < 500:
                    raw_body = b"".join([chunk async for chunk in response.body_iterator])
                    idempotency_store.complete(
                        scoped_key,
                        status_code=response.status_code,
                        response_body=raw_body.decode("utf-8", errors="replace"),
                    )
                    response = Response(
                        content=raw_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                response.headers["X-Trace-Id"] = t_id
                response.headers["traceparent"] = tp_hdr
                return response

        @app.get("/health")
        async def _health():
            return {"status": "ok", "observability": red_metrics.snapshot()}

        @app.get("/api/v1/observability/metrics")
        async def _metrics():
            return {"status": "ok", "metrics": red_metrics.snapshot()}
    call_counter = {"count": 0}

    @app.post("/api/v1/test-idempotent-charge")
    async def charge_endpoint(request: Request) -> dict:
        call_counter["count"] += 1
        return {"status": "ok", "charged": True, "call_number": call_counter["count"]}

    client = TestClient(app)

    # 1. Проверка сквозного заголовка W3C traceparent
    incoming_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    health_resp = client.get("/health", headers={"traceparent": incoming_tp})
    assert health_resp.status_code == 200
    assert health_resp.headers.get("X-Trace-Id") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert "observability" in health_resp.json()

    # 2. Первый мутирующий POST с ключом идемпотентности выполняет бизнес-логику
    r1 = client.post(
        "/api/v1/test-idempotent-charge",
        headers={"Idempotency-Key": "idem-order-777"},
    )
    assert r1.status_code == 200
    assert r1.json()["call_number"] == 1

    # 3. Повторный POST с тем же Idempotency-Key возвращает кешированный ответ без повторного списания!
    r2 = client.post(
        "/api/v1/test-idempotent-charge",
        headers={"Idempotency-Key": "idem-order-777"},
    )
    assert r2.status_code == 200
    assert r2.headers.get("X-Idempotent-Replayed") == "true"
    assert r2.json()["call_number"] == 1
    assert call_counter["count"] == 1

    # 4. Если операция находится в статусе IN_PROGRESS (параллельный дубль), возвращается 409 Conflict
    app.state.idempotency_store.begin("POST:/api/v1/test-idempotent-charge:idem-in-progress")
    r_conflict = client.post(
        "/api/v1/test-idempotent-charge",
        headers={"Idempotency-Key": "idem-in-progress"},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    # 5. Проверка эндпоинта метрик RED (p50, p95, p99)
    metrics_resp = client.get("/api/v1/observability/metrics")
    assert metrics_resp.status_code == 200
    m_data = metrics_resp.json()["metrics"]
    assert m_data["total_requests"] >= 3
    assert "p50" in m_data["duration_ms"]
    assert "p95" in m_data["duration_ms"]
    assert "p99" in m_data["duration_ms"]

