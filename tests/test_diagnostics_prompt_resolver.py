# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Prompt Resolver
# =============================================================================
# Description:
#   Тесты механизма разрешения и привязки системных инструкций и промптов
#   к идентификаторам панелей (panel_id) и типам таблиц (table_type).
#
# File: test_diagnostics_prompt_resolver.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 12:15:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
import pytest
from apps.windows.api.diagnostics_prompt_manager import (
    DiagnosticsPromptManager,
    DEFAULT_PROMPTS,
)


def test_get_template_by_table_type(tmp_path: Path) -> None:
    """Проверка возврата стандартного шаблона по table_type."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)
    tmpl = mgr.get_template("cpu")
    assert tmpl.table_type == "cpu"
    assert "процессора" in tmpl.name.lower()
    assert not tmpl.is_customized


def test_get_template_by_panel_id_fallback_to_table_type(tmp_path: Path) -> None:
    """Если кастомного файла для panel_id нет, резолвер откатывается к table_type."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)
    tmpl = mgr.get_template("security_event", panel_id="panel-system-control-3")
    assert tmpl.table_type == "security_event"
    assert "безопасности" in tmpl.name.lower()
    assert not tmpl.is_customized


def test_save_and_resolve_by_panel_id(tmp_path: Path) -> None:
    """Сохранение кастомной инструкции для конкретной панели имеет приоритет."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)
    panel_id = "panel-system-control-defender-filter"

    # Сохраняем индивидуальную инструкцию именно для этой панели
    saved = mgr.save_template(
        target_key=panel_id,
        system_instruction="Ты — эксперт по анализу журналов Microsoft Defender.",
        prompt_template="Анализ события Defender: {title}\n{metadata}",
        name="Инструкция для панели Defender",
    )
    assert saved.table_type == panel_id
    assert saved.is_customized

    # Проверяем, что get_template с указанием panel_id возвращает именно ее
    resolved = mgr.get_template("security_event", panel_id=panel_id)
    assert resolved.table_type == panel_id
    assert resolved.system_instruction == "Ты — эксперт по анализу журналов Microsoft Defender."
    assert resolved.is_customized

    # А для другой панели или без panel_id возвращается стандартный security_event
    default_tmpl = mgr.get_template("security_event", panel_id="panel-system-control-other")
    assert default_tmpl.table_type == "security_event"
    assert not default_tmpl.is_customized


def test_reset_template_by_panel_id(tmp_path: Path) -> None:
    """Сброс шаблона конкретной панели удаляет файл и откатывается к базовому типу."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)
    panel_id = "panel-proc-top-cpu"

    mgr.save_template(
        target_key=panel_id,
        system_instruction="Кастомная инструкция для топ CPU",
        prompt_template="Шаблон: {title}",
        name="Топ CPU Процессы",
    )

    # Проверяем наличие
    assert (tmp_path / f"{panel_id}.json").exists()

    # Сбрасываем
    reset_tmpl = mgr.reset_template(panel_id, fallback_table_type="process")
    assert not (tmp_path / f"{panel_id}.json").exists()
    assert reset_tmpl.table_type == "process"
    assert not reset_tmpl.is_customized


def test_resolve_power_session_and_panel_system_control_4(tmp_path: Path) -> None:
    """Проверка разрешения промпта сессий питания для table_type и panel-system-control-4."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)

    # 1. По table_type 'power_session'
    tmpl_session = mgr.get_template("power_session")
    assert tmpl_session.table_type == "power_session"
    assert "сессий питания" in tmpl_session.name.lower()
    assert "kernel-power" in tmpl_session.system_instruction.lower()
    assert "{raw_data}" in tmpl_session.prompt_template

    # 2. Алиасы power, power_lifecycle, power_sessions
    for alias in ["power", "power_lifecycle", "power_sessions"]:
        alias_tmpl = mgr.get_template(alias)
        assert alias_tmpl.table_type == "power_session"

    # 3. По идентификатору панели panel-system-control-4
    tmpl_panel4 = mgr.get_template("generic", panel_id="panel-system-control-4")
    assert "panel-system-control-4" in tmpl_panel4.table_type
    assert "сесси" in tmpl_panel4.name.lower()
    assert "kernel-power" in tmpl_panel4.system_instruction.lower()


def test_resolve_power_event_and_panel_system_control_5(tmp_path: Path) -> None:
    """Проверка разрешения промпта событий питания для table_type и panel-system-control-5."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)

    tmpl_event = mgr.get_template("power_event")
    assert tmpl_event.table_type == "power_event"
    assert "событий питания" in tmpl_event.name.lower()

    tmpl_panel5 = mgr.get_template("generic", panel_id="panel-system-control-5")
    assert "panel-system-control-5" in tmpl_panel5.table_type
    assert "событий питания" in tmpl_panel5.name.lower()


def test_prompt_i18n_localization(tmp_path: Path) -> None:
    """Проверка мультиязычности i18n для шаблонов промптов."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)

    # Запрос на английском языке
    tmpl_en = mgr.get_template("power_session", lang="en")
    assert "Power Session" in tmpl_en.name
    assert "You are a lead Windows system engineer" in tmpl_en.system_instruction

    # Запрос на русском языке (дефолт)
    tmpl_ru = mgr.get_template("power_session", lang="ru")
    assert "Аудит сессий питания" in tmpl_ru.name
    assert "Ты — ведущий системный инженер" in tmpl_ru.system_instruction


def test_resolve_help_and_app_log(tmp_path: Path) -> None:
    """Проверка разрешения шаблонов help (справка) и app_log (журналы приложений)."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)

    # 1. Шаблон help и алиасы
    tmpl_help = mgr.get_template("help")
    assert tmpl_help.table_type == "help"
    assert "справка" in tmpl_help.name.lower()
    for alias in ["doc", "docs"]:
        assert mgr.get_template(alias).table_type == "help"

    # 2. Шаблон app_log и алиасы
    tmpl_log = mgr.get_template("app_log")
    assert tmpl_log.table_type == "app_log"
    assert "журналов" in tmpl_log.name.lower()
    for alias in ["app_logs", "application_log", "log"]:
        assert mgr.get_template(alias).table_type == "app_log"

    # 3. Поддержка panel-app-logs и watcher_help
    tmpl_watcher = mgr.get_template("help", panel_id="watcher_help")
    assert tmpl_watcher.table_type == "help"


def test_resolve_process_manager_panel(tmp_path: Path) -> None:
    """Проверка разрешения шаблона для панели диспетчера процессов и приложений."""
    mgr = DiagnosticsPromptManager(storage_dir=tmp_path)

    # По panel_id
    tmpl = mgr.get_template("process", panel_id="panel-process-manager-dispetcher-protsessov-i-prilozhen")
    assert tmpl.table_type == "process"
    assert "диспетчер процессов" in tmpl.name.lower()
    assert "windows internals" in tmpl.system_instruction.lower()
    assert "{raw_data}" in tmpl.prompt_template

    # Английская локализация
    tmpl_en = mgr.get_template("process", panel_id="panel-process-manager-dispetcher-protsessov-i-prilozhen", lang="en")
    assert "Task Manager" in tmpl_en.name
    assert "Windows Internals" in tmpl_en.system_instruction


