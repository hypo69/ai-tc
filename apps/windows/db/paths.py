# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows DB - System Knowledge Paths
# =============================================================================
# Description:
#   Динамическое разрешение путей к базе данных системных подсказок WikiLLM
#   (%ProgramData%\{app_name}\apps\windows\knowledge.db)
#   на основе настроек из конфигурационных файлов config.json без хардкода.
#
# Usage Examples:
#   Python API:
#     from apps.windows.db.paths import resolve_system_knowledge_db_path, migrate_system_knowledge_db
#
#     db_path = resolve_system_knowledge_db_path()
#     print(f"Путь к базе знаний: {db_path}")
#     res = migrate_system_knowledge_db()
#
# File: paths.py
# Project: ai-windows-admin
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 12:40:00
# =============================================================================

from __future__ import annotations

"""Модуль динамического разрешения путей и безопасной миграции базы данных подсказок WikiLLM."""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def get_config_search_paths() -> list[Path]:
    """Возвращает список путей для поиска файлов конфигурации проекта.

    Returns:
        list[Path]: Список существующих или потенциальных файлов конфигурации.
    """
    candidates = [
        Path("apps/windows/api/config.json"),
        Path("config.json"),
        Path("apps/windows/wikillm/config.json"),
    ]
    return [p for p in candidates if p.is_file()]


def load_merged_system_config() -> Dict[str, Any]:
    """Считывает и объединяет параметры конфигурации из доступных config.json.

    Returns:
        Dict[str, Any]: Объединенный словарь параметров конфигурации.
    """
    merged: Dict[str, Any] = {}
    for cfg_path in get_config_search_paths():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged.update(data)
        except Exception as ex:
            logger.debug(f"[Paths] Ошибка чтения {cfg_path}: {ex}")
    return merged


def get_dynamic_path_config() -> Dict[str, str]:
    """Извлекает базовые переменные путей из конфигурации или системного окружения.

    Динамические параметры:
      - programdata: путь к директории %ProgramData% (настраивается в config.json: paths.programdata)
      - app_name: имя приложения/подсистемы (настраивается в config.json: paths.app_name или app_name)
      - template: шаблон пути к базе системных подсказок

    Returns:
        Dict[str, str]: Словарь с параметрами 'programdata', 'app_name', 'template'.
    """
    cfg = load_merged_system_config()
    paths_cfg = cfg.get("paths", {})

    # 1. Разрешение programdata строго из конфига с fallback на системное окружение
    raw_programdata = (
        paths_cfg.get("programdata")
        or os.environ.get("ProgramData")
        or os.environ.get("ALLUSERSPROFILE")
        or "C:/ProgramData"
    )
    expanded_programdata = os.path.expandvars(str(raw_programdata)).replace("\\", "/")

    # 2. Разрешение app_name строго из конфига
    app_name = (
        paths_cfg.get("app_name")
        or cfg.get("app_name")
        or cfg.get("app", {}).get("app_name")
        or os.environ.get("APP_NAME")
        or "ai-tc"
    )

    # 3. Шаблон пути к базе знаний подсказок строго из конфига
    db_template = (
        paths_cfg.get("system_knowledge_db")
        or cfg.get("database", {}).get("sqlite", {}).get("path")
        or cfg.get("wikillm", {}).get("db_path")
        or "%ProgramData%/{app_name}/apps/windows/knowledge.db"
    )

    return {
        "programdata": expanded_programdata,
        "app_name": str(app_name),
        "template": str(db_template),
    }


def resolve_system_knowledge_db_path(raw_path: Optional[str] = None) -> Path:
    """Разрешает динамический путь к файлу базы данных подсказок по системе.

    Выполняет подстановку динамических переменных на основе конфигурации:
      - %ProgramData% / {programdata}
      - {app_name} / %APP_NAME%
      - любых других системных переменных среды через expandvars.

    Также поддерживает поиск файла с вариативным именем (knowledge.db / knowelege.db)
    и автоматическую миграцию из старого расположения.

    Args:
        raw_path: Явно переданный путь или шаблон (опционально).

    Returns:
        Path: Абсолютный разрешенный путь к файлу базы данных SQLite.
    """
    dyn_cfg = get_dynamic_path_config()
    template = raw_path if (raw_path and str(raw_path).strip()) else dyn_cfg["template"]

    # Подстановка динамических параметров
    resolved_str = template.replace("{programdata}", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("{app_name}", dyn_cfg["app_name"])
    resolved_str = resolved_str.replace("%ProgramData%", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("%programdata%", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("%APP_NAME%", dyn_cfg["app_name"])
    resolved_str = resolved_str.replace("%app_name%", dyn_cfg["app_name"])
    resolved_str = os.path.expandvars(resolved_str)

    target_path = Path(resolved_str).resolve()

    # Если файл уже существует по целевому пути
    if target_path.is_file():
        return target_path

    # Проверка альтернативного написания (knowelege.db vs knowledge.db) в той же целевой директории
    parent_dir = target_path.parent
    if parent_dir.is_dir():
        alt_names = ["knowledge.db", "knowelege.db"]
        for alt in alt_names:
            candidate = parent_dir / alt
            if candidate.is_file():
                return candidate

    # Автоматическое создание целевой директории
    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        logger.warning(f"[Paths] Не удалось создать директорию {parent_dir}: {ex}")

    # Поиск файлов в старых расположениях для автоматической миграции
    old_base_dir = Path(dyn_cfg["programdata"]) / dyn_cfg["app_name"] / "windows"
    legacy_candidates = [
        old_base_dir / "knowledge.db",
        old_base_dir / "knowelege.db",
        Path("data/windows_wikillm/knowledge.db"),
        Path("data/windows_wikillm/knowelege.db"),
        Path("data/wikillm.db"),
    ]
    for leg in legacy_candidates:
        if leg.is_file() and leg.resolve() != target_path:
            try:
                # Если файл лежит в старом ProgramData-каталоге, переносим его в целевой путь
                if leg.parent == old_base_dir:
                    shutil.move(str(leg), str(target_path))
                    logger.info(f"[Paths] База знаний успешно перемещена: {leg} -> {target_path}")
                else:
                    shutil.copy2(leg, target_path)
                    logger.info(f"[Paths] Скопирована исходная база подсказок: {leg} -> {target_path}")
                break
            except Exception as ex:
                logger.warning(f"[Paths] Ошибка переноса/копирования {leg} -> {target_path}: {ex}")

    return target_path


def migrate_system_knowledge_db(
    source_template: Optional[str] = None,
    target_template: Optional[str] = None,
) -> Dict[str, Any]:
    """Выполняет безопасный перенос базы знаний WikiLLM строго по путям из конфигурации.

    Параметры берутся из конфигурации без хардкода:
      - Исходный каталог: %ProgramData%/{app_name}/windows/knowledge.db (или source_template)
      - Целевой каталог: берется из конфига (%ProgramData%/{app_name}/apps/windows/knowledge.db)

    Args:
        source_template: Пользовательский шаблон исходного расположения (опционально).
        target_template: Пользовательский шаблон целевого расположения (опционально).

    Returns:
        Dict[str, Any]: Результат операции переноса (ok, source, target, message).
    """
    dyn_cfg = get_dynamic_path_config()

    # 1. Определение целевого пути строго из конфигурации
    raw_target = target_template or dyn_cfg["template"]
    target_path = resolve_system_knowledge_db_path(raw_target)

    # 2. Определение исходного пути
    if source_template and str(source_template).strip():
        source_path = resolve_system_knowledge_db_path(source_template)
    else:
        # Стандартное старое расположение
        old_dir = Path(dyn_cfg["programdata"]) / dyn_cfg["app_name"] / "windows"
        source_path = old_dir / "knowledge.db"
        if not source_path.is_file() and (old_dir / "knowelege.db").is_file():
            source_path = old_dir / "knowelege.db"

    logger.info(f"[Paths] Запрос на перенос базы знаний: {source_path} -> {target_path}")

    # Если целевой путь совпадает с исходным
    if source_path.resolve() == target_path.resolve():
        msg = f"Исходный и целевой пути совпадают: {target_path}"
        logger.info(f"[Paths] {msg}")
        return {"ok": True, "source": str(source_path), "target": str(target_path), "message": msg}

    # Если исходный файл не существует
    if not source_path.is_file():
        # Проверяем, возможно база уже находится по целевому пути
        if target_path.is_file():
            msg = f"База знаний уже находится по целевому пути: {target_path}"
            logger.info(f"[Paths] {msg}")
            if hasattr(logger, "console"):
                logger.console(f"[DatabaseMigration] {msg}")
            return {"ok": True, "source": str(source_path), "target": str(target_path), "message": msg}

        # Проверяем резервный локальный источник
        fallback_source = Path("data/windows_wikillm/knowledge.db")
        if fallback_source.is_file():
            source_path = fallback_source
        else:
            err = f"Исходный файл базы знаний не найден ни по адресу {source_path}, ни в резервных источниках."
            logger.error(f"[Paths] {err}")
            return {"ok": False, "source": str(source_path), "target": str(target_path), "error": err}

    # 3. Подготовка целевой директории
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 4. Перенос файла базы данных
    try:
        shutil.copy2(source_path, target_path)

        # Перенос сопутствующих журналов WAL/SHM при наличии
        for ext in ["-wal", "-shm", "-journal"]:
            src_sidecar = Path(str(source_path) + ext)
            if src_sidecar.is_file():
                tgt_sidecar = Path(str(target_path) + ext)
                shutil.copy2(src_sidecar, tgt_sidecar)
                logger.debug(f"[Paths] Скопирован сопутствующий файл: {src_sidecar} -> {tgt_sidecar}")

        # 5. Верификация целостности перенесенной базы данных через SQLite
        with sqlite3.connect(str(target_path)) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            check_result = cur.fetchone()
            if not check_result or check_result[0].lower() != "ok":
                raise RuntimeError(f"Целостность перенесенной базы нарушена: {check_result}")

        # 6. Удаление исходных файлов после успешной верификации
        # Удаляем только если исходный файл не в репозитории data/
        if "data" not in source_path.parts:
            try:
                source_path.unlink(missing_ok=True)
                for ext in ["-wal", "-shm", "-journal"]:
                    Path(str(source_path) + ext).unlink(missing_ok=True)
                # Если старая папка windows пуста, удаляем её
                old_parent = source_path.parent
                if old_parent.is_dir() and not any(old_parent.iterdir()):
                    old_parent.rmdir()
                    logger.debug(f"[Paths] Удалена пустая исходная папка: {old_parent}")
            except Exception as del_err:
                logger.warning(f"[Paths] Не удалось удалить исходный файл {source_path}: {del_err}")

        success_msg = f"База знаний успешно перенесена: {source_path} -> {target_path}"
        logger.info(f"[Paths] {success_msg}")
        if hasattr(logger, "console"):
            logger.console(f"[DatabaseMigration] {success_msg}")

        return {
            "ok": True,
            "source": str(source_path),
            "target": str(target_path),
            "size_bytes": target_path.stat().st_size,
            "message": success_msg,
        }
    except Exception as exc:
        err_msg = f"Ошибка при переносе базы знаний {source_path} -> {target_path}: {exc}"
        logger.error(f"[Paths] {err_msg}")
        return {"ok": False, "source": str(source_path), "target": str(target_path), "error": err_msg}
