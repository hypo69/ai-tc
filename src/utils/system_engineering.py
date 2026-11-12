# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - System Engineering & Resilience Core
# =============================================================================
# Description:
#   Фундаментальные механизмы системной инженерии (Beyond Vibe Coding):
#   - Экспоненциальная задержка с джиттером (Exponential Backoff + Jitter)
#   - Автоматический выключатель (Circuit Breaker: Closed -> Open -> Half-Open)
#   - Ограниченный кэш с политикой вытеснения LRU и временем жизни (BoundedTTLCache)
#   - Контроллер идемпотентности мутирующих операций (IdempotencyStore / 409 Conflict)
#   - Паттерн Transactional Outbox в единой ACID-транзакции SQLite (WAL) с версионированием
#   - Точные финансовые вычисления (Decimal / минимальные неделимые единицы int)
#   - Строгое время UTC ISO 8601 и трассировка W3C TraceContext (traceparent)
#   - Сборщик метрик RED (Rate, Errors, Duration) с расчетом перцентилей p50, p95, p99
#
# Examples:
#   >>> from src.utils.system_engineering import (
#   ...     CircuitBreaker, BoundedTTLCache, REDMetricsCollector, to_decimal_money
#   ... )
#   >>> str(to_decimal_money("0.1") + to_decimal_money("0.2"))
#   '0.30'
#
# File: system_engineering.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:15:00
# =============================================================================

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from enum import Enum
import json
import math
import random
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Tuple

_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)


# =============================================================================
# 1. Временные зоны UTC ISO 8601 и Финансовая точность (Decimal / Minor Units)
# =============================================================================


def utc_now_iso() -> str:
    """Возвращает текущее время строго в UTC формате ISO 8601 с суффиксом Z.

    Returns:
        str: Строка вида '2026-11-10T14:15:00.123456Z'.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_utc_iso(value: str | float | int | datetime = "") -> str:
    """Нормализует дату/время или Unix timestamp к строгому формату UTC ISO 8601.

    Args:
        value: Входное представление времени (строка ISO, timestamp или datetime).

    Returns:
        str: Строка времени в UTC ISO 8601 с суффиксом Z.
    """
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(cleaned)
            dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return utc_now_iso()
    return utc_now_iso()


def to_decimal_money(amount: str | int | Decimal, precision: str = "0.01") -> Decimal:
    """Преобразует денежную величину в точный Decimal с банковским округлением.

    Почему: числа IEEE 754 (float) имеют бесконечную двоичную периодическую дробь
    для 0.1 и 0.2 (0.1 + 0.2 != 0.3), что недопустимо в финансовых расчетах.

    Args:
        amount: Строковое, целочисленное или Decimal представление суммы.
        precision: Шаг квантования (по умолчанию '0.01').

    Returns:
        Decimal: Квантованное значение с округлением ROUND_HALF_EVEN.

    Raises:
        TypeError: Если передан float (защита от потери точности IEEE 754).
        ValueError: Если строка не может быть преобразована в число.
    """
    if isinstance(amount, float):
        raise TypeError("Использование float для денежных расчетов запрещено стандартом SYSTEM_ENGINEERING")
    if isinstance(amount, bool):
        raise TypeError("Булевы значения не могут использоваться как денежная величина")

    raw_str = str(amount).strip().replace(",", ".").replace(" ", "")
    raw_str = re.sub(r"[^\d.\-+]", "", raw_str)
    if not raw_str or raw_str in ("-", "+", "."):
        return Decimal("0.00").quantize(Decimal(precision), rounding=ROUND_HALF_EVEN)
    try:
        dec = Decimal(raw_str)
        if not dec.is_finite():
            raise ValueError("Сумма должна быть конечным числом")
        return dec.quantize(Decimal(precision), rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError(f"Некорректный формат денежной величины: {amount!r}") from exc


def money_to_minor_units(amount: str | int | Decimal, minor_factor: int = 100) -> int:
    """Переводит сумму в минимальные неделимые единицы (копейки, центы).

    Args:
        amount: Сумма в основных единицах валюты (не float).
        minor_factor: Количество минимальных единиц в одной основной (100 для центов/копеек).

    Returns:
        int: Целое количество неделимых единиц.
    """
    dec = to_decimal_money(amount)
    scaled = (dec * Decimal(minor_factor)).to_integral_value(rounding=ROUND_HALF_EVEN)
    return int(scaled)


def minor_units_to_decimal(minor_units: int, minor_factor: int = 100, precision: str = "0.01") -> Decimal:
    """Переводит сумму из минимальных неделимых единиц (копеек/центов) в Decimal.

    Args:
        minor_units: Целое количество минимальных единиц.
        minor_factor: Делитель валюты (по умолчанию 100).
        precision: Точность представления.

    Returns:
        Decimal: Сумма в основных единицах.
    """
    if isinstance(minor_units, float) or isinstance(minor_units, bool):
        raise TypeError("Минимальные неделимые единицы должны быть строго типа int")
    return (Decimal(int(minor_units)) / Decimal(minor_factor)).quantize(
        Decimal(precision), rounding=ROUND_HALF_EVEN
    )


# =============================================================================
# 2. Exponential Backoff + Jitter и Circuit Breaker (Release It!)
# =============================================================================


def compute_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    jitter_ratio: float = 0.25,
) -> float:
    """Вычисляет задержку повтора по формуле Exponential Backoff + Random Jitter.

    Почему: мгновенные или синхронные повторы от сотен клиентов создают эффект
    «громоподобного стада» (Thundering Herd) и добивают восстанавливающийся сервис.

    Args:
        attempt: Номер попытки (начиная с 1).
        base_delay: Базовая задержка в секундах.
        max_delay: Верхний потолок экспоненциальной задержки.
        jitter_ratio: Доля случайного шума от вычисленной задержки (0.0..1.0).

    Returns:
        float: Итоговое время ожидания в секундах (>= 0.0).
    """
    safe_attempt = max(0, min(int(attempt), 30))
    safe_base = max(0.001, float(base_delay))
    safe_max = max(safe_base, float(max_delay))
    safe_jitter_ratio = max(0.0, min(float(jitter_ratio), 1.0))

    exp_delay = min(safe_max, safe_base * (2 ** safe_attempt))
    jitter = random.uniform(0.0, exp_delay * safe_jitter_ratio)
    return round(exp_delay + jitter, 4)


async def async_sleep_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    jitter_ratio: float = 0.25,
) -> float:
    """Неблокирующее ожидание в Event Loop с экспоненциальной задержкой и джиттером.

    Args:
        attempt: Номер текущей попытки.
        base_delay: Базовая задержка в секундах.
        max_delay: Максимальная задержка в секундах.
        jitter_ratio: Коэффициент джиттера.

    Returns:
        float: Фактически выполненная задержка в секундах.
    """
    delay = compute_backoff_with_jitter(
        attempt=attempt,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter_ratio=jitter_ratio,
    )
    await asyncio.sleep(delay)
    return delay


class CircuitState(str, Enum):
    """Состояния автоматического выключателя (Circuit Breaker)."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Исключение, выбрасываемое при разомкнутом (OPEN) состоянии Circuit Breaker."""


class CircuitBreaker:
    """Потокобезопасный автоматический выключатель для изоляции сбойных зависимостей.

    Реализует конечный автомат:
    - CLOSED: запросы проходят штатно; при достижении порога ошибок переходит в OPEN.
    - OPEN: мгновенный отказ (Fail-Fast) без сетевых вызовов до истечения recovery_timeout.
    - HALF_OPEN: пропускает пробный запрос; при успехе замыкается в CLOSED, при сбое — снова в OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout_seconds = max(0.1, float(recovery_timeout_seconds))
        self.half_open_max_calls = max(1, int(half_open_max_calls))

        self._lock = threading.RLock()
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._half_open_calls: int = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Текущее состояние выключателя с учетом таймера перехода в HALF_OPEN."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if (time.monotonic() - self._opened_at) >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def allow_request(self) -> bool:
        """Проверяет, разрешено ли выполнение очередного вызова к внешнему сервису."""
        with self._lock:
            current = self.state
            if current == CircuitState.CLOSED:
                return True
            if current == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            return False

    def record_success(self) -> CircuitState:
        """Фиксирует успешный вызов и возвращает выключатель в замкнутое состояние CLOSED."""
        with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED
            return self._state

    def record_failure(self) -> CircuitState:
        """Фиксирует ошибку вызова и при превышении порога размыкает цепь в OPEN."""
        with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
            return self._state

    def snapshot(self) -> Dict[str, Any]:
        """Возвращает диагностический срез состояния выключателя."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
            }


# =============================================================================
# 3. Ограниченный кэш с TTL и LRU-эвикцией (Защита от утечек памяти и OOM)
# =============================================================================


class BoundedTTLCache:
    """Потокобезопасный кэш фиксированного размера с временем жизни записей (TTL) и LRU.

    Почему: глобальные словари без лимита размера и TTL приводят к бесконечному
    росту Resident Set Size (RSS), свопингу и аварийному завершению процесса OOM Killer.
    """

    def __init__(self, maxsize: int = 512, ttl_seconds: float = 300.0) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_seconds = max(0.1, float(ttl_seconds))
        self._store: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def _evict_expired(self, now: float) -> int:
        """Удаляет просроченные записи из начала очереди."""
        removed = 0
        expired_keys = [k for k, (exp, _) in self._store.items() if exp <= now]
        for k in expired_keys:
            self._store.pop(k, False)
            removed += 1
        return removed

    def get(self, key: str, default: Any = False) -> Any:
        """Возвращает значение по ключу с обновлением позиции LRU или default."""
        now = time.monotonic()
        with self._lock:
            if key not in self._store:
                return default
            expires_at, value = self._store[key]
            if expires_at <= now:
                self._store.pop(key, False)
                return default
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl_override: float = 0.0) -> int:
        """Сохраняет значение с контролем верхней границы размера кэша."""
        now = time.monotonic()
        effective_ttl = float(ttl_override) if ttl_override > 0 else self.ttl_seconds
        expires_at = now + effective_ttl
        with self._lock:
            self._evict_expired(now)
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (expires_at, value)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)
            return len(self._store)

    def delete(self, key: str) -> bool:
        """Удаляет ключ из кэша."""
        with self._lock:
            if key in self._store:
                self._store.pop(key, False)
                return True
            return False

    def clear(self) -> int:
        """Очищает кэш и возвращает число удаленных элементов."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def __len__(self) -> int:
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            return len(self._store)


# =============================================================================
# 4. Идемпотентность (Idempotency-Key) и защита от параллельных дублей
# =============================================================================


class IdempotencyConflictError(RuntimeError):
    """Исключение параллельного выполнения запроса с тем же ключом идемпотентности (HTTP 409)."""


@dataclass
class IdempotencyRecord:
    """Запись состояния выполнения операции по ключу Idempotency-Key."""

    key: str
    status: str = "IN_PROGRESS"
    status_code: int = 200
    response_body: str = ""
    created_at: float = field(default_factory=time.monotonic)


class IdempotencyStore:
    """Хранилище ключей идемпотентности с защитой от гонки параллельных ретраев.

    При первом запросе ключ захватывается со статусом IN_PROGRESS.
    Если параллельный дубль приходит до завершения первого запроса, возвращается
    конфликт (409 Conflict). Если первый запрос уже завершился (COMPLETED),
    возвращается сохраненный результат без повторного выполнения бизнес-логики.
    """

    def __init__(self, max_keys: int = 2048, ttl_seconds: float = 3600.0) -> None:
        self._cache = BoundedTTLCache(maxsize=max_keys, ttl_seconds=ttl_seconds)
        self._lock = threading.RLock()

    def begin(self, key: str) -> Tuple[str, IdempotencyRecord]:
        """Атомарно регистрирует начало выполнения операции по ключу.

        Args:
            key: Значение заголовка Idempotency-Key.

        Returns:
            Tuple[str, IdempotencyRecord]: Статус ('NEW', 'IN_PROGRESS', 'COMPLETED') и запись.
        """
        clean_key = str(key).strip()
        if not clean_key:
            raise ValueError("Ключ идемпотентности не может быть пустым")
        with self._lock:
            existing = self._cache.get(clean_key, default=False)
            if isinstance(existing, IdempotencyRecord):
                return (existing.status, existing)
            record = IdempotencyRecord(key=clean_key, status="IN_PROGRESS")
            self._cache.set(clean_key, record)
            return ("NEW", record)

    def complete(self, key: str, status_code: int, response_body: str) -> IdempotencyRecord:
        """Фиксирует успешное завершение идемпотентной операции и сохраняет ответ."""
        clean_key = str(key).strip()
        with self._lock:
            record = IdempotencyRecord(
                key=clean_key,
                status="COMPLETED",
                status_code=int(status_code),
                response_body=str(response_body),
            )
            self._cache.set(clean_key, record)
            return record

    def abort(self, key: str) -> bool:
        """Освобождает ключ при необработанном сбое, чтобы разрешить повторную попытку."""
        return self._cache.delete(str(key).strip())


# =============================================================================
# 5. Паттерн Transactional Outbox и защита от Lost Update в SQLite (WAL)
# =============================================================================


class TransactionalOutbox:
    """Реализация паттерна Transactional Outbox поверх SQLite в режиме WAL.

    Гарантирует:
    1. Отсутствие проблемы двойной записи (Dual-Write): бизнес-изменение и событие
       сохраняются в одной локальной ACID-транзакции (BEGIN IMMEDIATE).
    2. Защиту от Lost Update при параллельном чтении воркерами через оптимистическую
       блокировку (колонка version = version + 1).
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """Создает соединение SQLite с включенным режимом WAL и таймаутом блокировки."""
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_schema(self) -> bool:
        """Создает таблицу outbox_events и B-Tree индекс для быстрой выборки."""
        with self._lock:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS outbox_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL UNIQUE,
                            topic TEXT NOT NULL,
                            payload_json TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'PENDING',
                            attempts INTEGER NOT NULL DEFAULT 0,
                            version INTEGER NOT NULL DEFAULT 1,
                            next_attempt_at REAL NOT NULL DEFAULT 0.0,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_outbox_status_next
                        ON outbox_events (status, next_attempt_at);
                        """
                    )
                    conn.execute("COMMIT;")
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise
        return True

    def execute_in_transaction(
        self,
        business_sql: str,
        business_params: Tuple[Any, ...] | Dict[str, Any],
        event_id: str,
        topic: str,
        payload: Dict[str, Any],
    ) -> int:
        """Выполняет бизнес-запрос и запись в outbox в единой ACID-транзакции.

        Args:
            business_sql: Параметризованный SQL-запрос изменения доменной таблицы.
            business_params: Параметры для business_sql.
            event_id: Уникальный идентификатор события (UUID).
            topic: Канал/топик назначения.
            payload: Словарь полезных данных события.

        Returns:
            int: Количество измененных строк бизнес-запроса.
        """
        now_iso = utc_now_iso()
        payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    cur = conn.execute(business_sql, business_params)
                    affected = int(cur.rowcount or 0)
                    conn.execute(
                        """
                        INSERT INTO outbox_events (
                            event_id, topic, payload_json, status, attempts, version,
                            next_attempt_at, created_at, updated_at
                        ) VALUES (?, ?, ?, 'PENDING', 0, 1, 0.0, ?, ?);
                        """,
                        (str(event_id), str(topic), payload_str, now_iso, now_iso),
                    )
                    conn.execute("COMMIT;")
                    return affected
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise

    def claim_pending_batch(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Захватывает пакет готовых к отправке событий с оптимистической блокировкой версии."""
        now_ts = time.time()
        now_iso = utc_now_iso()
        claimed: List[Dict[str, Any]] = []
        with self._lock:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    rows = conn.execute(
                        """
                        SELECT id, event_id, topic, payload_json, attempts, version
                        FROM outbox_events
                        WHERE status = 'PENDING' AND next_attempt_at <= ?
                        ORDER BY id ASC
                        LIMIT ?;
                        """,
                        (now_ts, max(1, int(limit))),
                    ).fetchall()
                    for row in rows:
                        cur = conn.execute(
                            """
                            UPDATE outbox_events
                            SET status = 'PROCESSING',
                                version = version + 1,
                                updated_at = ?
                            WHERE id = ? AND version = ? AND status = 'PENDING';
                            """,
                            (now_iso, row["id"], row["version"]),
                        )
                        if cur.rowcount == 1:
                            claimed.append(
                                {
                                    "id": row["id"],
                                    "event_id": row["event_id"],
                                    "topic": row["topic"],
                                    "payload": json.loads(row["payload_json"]),
                                    "attempts": row["attempts"],
                                    "version": row["version"] + 1,
                                }
                            )
                    conn.execute("COMMIT;")
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise
        return claimed

    def mark_dispatched(self, event_id: str, expected_version: int) -> bool:
        """Помечает событие как успешно отправленное с проверкой версии (Optimistic Lock)."""
        now_iso = utc_now_iso()
        with self._lock:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    cur = conn.execute(
                        """
                        UPDATE outbox_events
                        SET status = 'DISPATCHED',
                            version = version + 1,
                            updated_at = ?
                        WHERE event_id = ? AND version = ?;
                        """,
                        (now_iso, str(event_id), int(expected_version)),
                    )
                    conn.execute("COMMIT;")
                    return cur.rowcount == 1
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise

    def mark_failed_with_backoff(self, event_id: str, expected_version: int, attempt: int) -> bool:
        """Возвращает событие в очередь PENDING с расчетом задержки Exponential Backoff + Jitter."""
        delay = compute_backoff_with_jitter(attempt=attempt, base_delay=0.5, max_delay=30.0)
        next_ts = time.time() + delay
        now_iso = utc_now_iso()
        with self._lock:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    cur = conn.execute(
                        """
                        UPDATE outbox_events
                        SET status = 'PENDING',
                            attempts = attempts + 1,
                            version = version + 1,
                            next_attempt_at = ?,
                            updated_at = ?
                        WHERE event_id = ? AND version = ?;
                        """,
                        (next_ts, now_iso, str(event_id), int(expected_version)),
                    )
                    conn.execute("COMMIT;")
                    return cur.rowcount == 1
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise


# =============================================================================
# 6. Наблюдаемость (Observability): W3C TraceContext и метрики RED (p50/p95/p99)
# =============================================================================


def generate_trace_id() -> str:
    """Генерирует 128-битный идентификатор трассировки W3C (32 hex-символа)."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Генерирует 64-битный идентификатор спана W3C (16 hex-символов)."""
    return secrets.token_hex(8)


def parse_traceparent(header_val: str = "") -> Tuple[str, str]:
    """Извлекает trace_id и span_id из заголовка W3C traceparent или генерирует новые."""
    cleaned = str(header_val).strip().lower()
    match = _TRACEPARENT_RE.match(cleaned)
    if match:
        trace_id = match.group("trace_id")
        span_id = match.group("span_id")
        if trace_id != "0" * 32 and span_id != "0" * 16:
            return (trace_id, span_id)
    return (generate_trace_id(), generate_span_id())


def format_traceparent(trace_id: str, span_id: str = "", sampled: bool = True) -> str:
    """Форматирует заголовок W3C traceparent ('00-<trace_id>-<span_id>-01')."""
    t_id = str(trace_id).strip().lower()
    if len(t_id) != 32:
        t_id = generate_trace_id()
    s_id = str(span_id).strip().lower()
    if len(s_id) != 16:
        s_id = generate_span_id()
    flags = "01" if sampled else "00"
    return f"00-{t_id}-{s_id}-{flags}"


def compute_percentile(sorted_values: List[float], percentile: float) -> float:
    """Вычисляет заданный перцентиль (0..100) по отсортированному списку значений."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return round(float(sorted_values[0]), 3)
    rank = max(0.0, min(100.0, float(percentile))) / 100.0 * (n - 1)
    low_idx = int(math.floor(rank))
    high_idx = int(math.ceil(rank))
    if low_idx == high_idx:
        return round(float(sorted_values[low_idx]), 3)
    weight = rank - low_idx
    interpolated = sorted_values[low_idx] * (1.0 - weight) + sorted_values[high_idx] * weight
    return round(float(interpolated), 3)


class REDMetricsCollector:
    """Сборщик телеметрии по методологии Google SRE RED (Rate, Errors, Duration p50/p95/p99).

    Почему: среднее арифметическое задержки скрывает Tail Latency (хвост распределения
    p95/p99, где прячутся блокировки БД и паузы сборщика мусора).
    """

    def __init__(self, max_samples: int = 2000) -> None:
        self.max_samples = max(10, int(max_samples))
        self._lock = threading.RLock()
        self._durations_ms: deque[float] = deque(maxlen=self.max_samples)
        self._timestamps: deque[float] = deque(maxlen=self.max_samples)
        self._total_requests: int = 0
        self._total_errors: int = 0

    def record(self, duration_ms: float, is_error: bool = False) -> None:
        """Фиксирует длительность обработки запроса и факт ошибки (HTTP >= 500)."""
        safe_dur = max(0.0, float(duration_ms))
        now = time.monotonic()
        with self._lock:
            self._durations_ms.append(safe_dur)
            self._timestamps.append(now)
            self._total_requests += 1
            if is_error:
                self._total_errors += 1

    def snapshot(self) -> Dict[str, Any]:
        """Возвращает агрегированные метрики RED с перцентилями p50, p95, p99."""
        with self._lock:
            samples = sorted(self._durations_ms)
            total = self._total_requests
            errors = self._total_errors
            if len(self._timestamps) >= 2:
                window_sec = max(0.001, self._timestamps[-1] - self._timestamps[0])
                rps = round(len(self._timestamps) / window_sec, 2)
            else:
                rps = float(len(self._timestamps))

        error_rate = round((errors / total) * 100.0, 2) if total > 0 else 0.0
        return {
            "total_requests": total,
            "total_errors": errors,
            "error_rate_percent": error_rate,
            "rate_rps": rps,
            "samples_count": len(samples),
            "duration_ms": {
                "p50": compute_percentile(samples, 50.0),
                "p95": compute_percentile(samples, 95.0),
                "p99": compute_percentile(samples, 99.0),
            },
        }
