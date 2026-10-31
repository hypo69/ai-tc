# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - TC Launcher
# =============================================================================
# Description:
#   Тесты базовой линии для точки входа tc.py: нормализация BCP 47,
#   освобождение порта, разбор аргументов и dry-run запуск.
#
# File: test_tc_launcher.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 19:46:00
# =============================================================================

from __future__ import annotations

import pytest

import tc


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('ru-ru', 'ru-RU'),
        ('en_us', 'en-US'),
        ('he', 'he-IL'),
        ('PT', 'pt-BR'),
        ("'de-de'", 'de-DE'),
        ('xx', 'xx-XX'),
    ],
)
def test_normalize_bcp47_tag(raw: str, expected: str) -> None:
    """Тег нормализуется к виду язык-РЕГИОН, регион по умолчанию подставляется."""
    assert tc.normalize_bcp47_tag(raw) == expected


def test_normalize_bcp47_tag_invalid_returned_clean() -> None:
    """Невалидный тег возвращается без изменений (после очистки)."""
    assert tc.normalize_bcp47_tag(' not a tag ') == 'not a tag'


def test_free_port_when_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Свободный порт: процессы не завершаются, результат True."""
    monkeypatch.setattr(tc, 'get_process_on_port', lambda port: None)
    killed: list[int] = []
    monkeypatch.setattr(tc, 'kill_process', lambda pid, force=False: killed.append(pid) or True)
    assert tc.free_port_if_occupied(8001) is True
    assert killed == []


@pytest.mark.parametrize('kill_result', [True, False])
def test_free_port_when_occupied(monkeypatch: pytest.MonkeyPatch, kill_result: bool) -> None:
    """Занятый порт: процесс завершается принудительно, результат равен итогу kill_process."""
    monkeypatch.setattr(tc, 'get_process_on_port', lambda port: (42, 'python.exe'))
    calls: list[tuple[int, bool]] = []

    def fake_kill(pid: int, force: bool = False) -> bool:
        calls.append((pid, force))
        return kill_result

    monkeypatch.setattr(tc, 'kill_process', fake_kill)
    assert tc.free_port_if_occupied(8001) is kill_result
    assert calls == [(42, True)]


def test_parse_args_defaults() -> None:
    """Значения по умолчанию соответствуют константам модуля."""
    args = tc.parse_args([])
    assert args.host == tc.DEFAULT_HOST
    assert args.port == tc.DEFAULT_PORT
    assert args.region is None
    assert args.dry_run is False


def test_run_tc_dry_run_replaces_foreign_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """dry-run возвращает 0 и не запускает uvicorn; внешний хост подменяется на localhost."""
    monkeypatch.setattr(tc, 'free_port_if_occupied', lambda port: True)
    messages: list[str] = []
    monkeypatch.setattr(tc.logger, 'info', lambda msg, *a, **k: messages.append(str(msg)))
    assert tc.run_tc(host='0.0.0.0', port=8123, region='ru-ru', dry_run=True, ssl=False) == 0
    assert any(f'http://{tc.DEFAULT_HOST}:8123/tc?region=ru-RU' in m for m in messages)


def test_run_tc_ssl_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка конфигурации HTTPS/SSL при передаче флага ssl=True."""
    monkeypatch.setattr(tc, 'free_port_if_occupied', lambda port: True)
    messages: list[str] = []
    monkeypatch.setattr(tc.logger, 'info', lambda msg, *a, **k: messages.append(str(msg)))
    assert tc.run_tc(host='127.0.0.1', port=8001, dry_run=True, ssl=True) == 0
    assert any(f'https://{tc.DEFAULT_HOST}:8001/tc' in m for m in messages)


