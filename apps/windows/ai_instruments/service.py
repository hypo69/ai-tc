# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments - Service
# =============================================================================
# Description:
#   Координатор и сервис изолированной базы данных инструментов ИИ-агента
#   (ai_instruments.db). Обеспечивает сохранение, извлечение из цепочки рассуждений,
#   поиск и безопасное выполнение инструментов агента на хосте Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai_instruments.service import AIInstrumentsService
#
#     srv = AIInstrumentsService()
#     res = srv.execute_instrument("inst_restart_spooler")
#
# File: service.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:43:30
# =============================================================================

from __future__ import annotations

"""Сервис управления базой инструментов ИИ-агента (ai_instruments.db)."""

import csv
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from logger import logger
from src.utils.csv import read_csv_file, save_csv_file
from .default_catalog import DEFAULT_AGENT_INSTRUMENTS
from .models import AIInstrument, AIInstrumentCreate, get_current_iso_time
from .storage import AIInstrumentsStorage


class AIInstrumentsService:
    """Сервис жизненного цикла инструментов агента."""

    def __init__(self, storage: Optional[AIInstrumentsStorage] = None) -> None:
        """Инициализирует сервис инструментов.

        Args:
            storage: Экземпляр хранилища AIInstrumentsStorage.
        """
        self.storage = storage or AIInstrumentsStorage()

    def save_instrument(self, item: AIInstrumentCreate) -> AIInstrument:
        """Сохраняет инструмент в базе данных ai_instruments.db.

        Args:
            item: Данные для создания инструмента.

        Returns:
            AIInstrument: Сохраненный объект инструмента.
        """
        tool_id = item.tool_id or f"inst_{uuid.uuid4().hex[:12]}"
        now = get_current_iso_time()
        inst = AIInstrument(
            tool_id=tool_id,
            name=item.name.strip(),
            tool_type=item.tool_type.strip().lower(),
            command=item.command.strip(),
            description=item.description or "",
            target_entity=item.target_entity or "",
            parameters_schema=item.parameters_schema or {},
            risk_level=item.risk_level or "safe",
            author_agent=item.author_agent or "reasoning_chain",
            tags=item.tags or ["#agent_tool"],
            created_at=now,
            updated_at=now,
        )
        saved = self.storage.save_instrument(inst)
        logger.info(f"[AIInstrumentsService] Инструмент '{saved.name}' ({saved.tool_id}) сохранен в ai_instruments.db")
        return saved

    def get_instrument(self, tool_id: str) -> Optional[AIInstrument]:
        """Возвращает инструмент по ID."""
        return self.storage.get_instrument(tool_id)

    def list_instruments(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_type: Optional[str] = None,
        target_entity: Optional[str] = None,
    ) -> List[AIInstrument]:
        """Возвращает список инструментов с фильтрацией."""
        return self.storage.list_instruments(
            limit=limit,
            offset=offset,
            tool_type=tool_type,
            target_entity=target_entity,
        )

    def search_instruments(self, query: str, limit: int = 20) -> List[AIInstrument]:
        """Ищет инструменты по запросу."""
        return self.storage.search_instruments(query, limit=limit)

    def delete_instrument(self, tool_id: str) -> bool:
        """Удаляет инструмент."""
        return self.storage.delete_instrument(tool_id)

    def export_to_csv(
        self,
        file_path: Union[str, Path],
        tool_type: Optional[str] = None,
        target_entity: Optional[str] = None,
    ) -> int:
        """Экспортирует каталог инструментов в CSV-файл через src.utils.csv.save_csv_file.

        Args:
            file_path (Union[str, Path]): Путь для сохранения CSV-файла.
            tool_type (Optional[str]): Фильтр по типу инструмента.
            target_entity (Optional[str]): Фильтр по целевой сущности.

        Returns:
            int: Количество экспортированных инструментов.
        """
        items = self.storage.list_instruments(
            limit=5000,
            offset=0,
            tool_type=tool_type,
            target_entity=target_entity,
        )
        fieldnames = [
            "tool_id",
            "name",
            "tool_type",
            "command",
            "description",
            "target_entity",
            "parameters_schema",
            "risk_level",
            "author_agent",
            "tags",
            "execution_count",
            "last_executed_at",
            "created_at",
            "updated_at",
        ]
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if not items:
            with target.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return 0

        rows: List[Dict[str, Any]] = []
        for it in items:
            rows.append(
                {
                    "tool_id": it.tool_id,
                    "name": it.name,
                    "tool_type": it.tool_type,
                    "command": it.command,
                    "description": it.description or "",
                    "target_entity": it.target_entity or "",
                    "parameters_schema": json.dumps(it.parameters_schema or {}, ensure_ascii=False),
                    "risk_level": it.risk_level or "safe",
                    "author_agent": it.author_agent or "reasoning_chain",
                    "tags": ", ".join(it.tags) if isinstance(it.tags, list) else str(it.tags or "#agent_tool"),
                    "execution_count": str(it.execution_count or 0),
                    "last_executed_at": it.last_executed_at or "",
                    "created_at": it.created_at or "",
                    "updated_at": it.updated_at or "",
                }
            )

        ok = save_csv_file(rows, target, mode="w")
        if not ok:
            raise RuntimeError(f"Не удалось сохранить каталог инструментов в CSV: {target}")
        logger.info(f"[AIInstrumentsService] Экспортировано {len(rows)} инструментов в CSV: {target}")
        return len(rows)

    def import_from_csv(self, file_path: Union[str, Path]) -> List[AIInstrument]:
        """Импортирует инструменты в базу данных из CSV-файла через src.utils.csv.read_csv_file.

        Args:
            file_path (Union[str, Path]): Путь к исходному CSV-файлу.

        Returns:
            List[AIInstrument]: Список сохраненных или обновленных инструментов.
        """
        raw_rows = read_csv_file(file_path)
        if raw_rows is None:
            raise ValueError(f"Не удалось прочитать CSV-файл инструментов: {file_path}")

        imported: List[AIInstrument] = []
        now = get_current_iso_time()

        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or "").strip()
            command = (row.get("command") or "").strip()
            if not name or not command:
                continue

            tool_id = (row.get("tool_id") or "").strip() or f"inst_{uuid.uuid4().hex[:12]}"
            tool_type = (row.get("tool_type") or "powershell").strip().lower() or "powershell"
            description = (row.get("description") or "").strip()
            target_entity = (row.get("target_entity") or "").strip()
            risk_level = (row.get("risk_level") or "safe").strip().lower() or "safe"
            author_agent = (row.get("author_agent") or "csv_import").strip() or "csv_import"

            schema_raw = (row.get("parameters_schema") or "").strip()
            parameters_schema: Dict[str, Any] = {}
            if schema_raw:
                try:
                    parsed_schema = json.loads(schema_raw)
                    if isinstance(parsed_schema, dict):
                        parameters_schema = parsed_schema
                except Exception:
                    parameters_schema = {}

            tags_raw = (row.get("tags") or "").strip()
            tags: List[str] = ["#agent_tool"]
            if tags_raw:
                if tags_raw.startswith("["):
                    try:
                        parsed_tags = json.loads(tags_raw)
                        if isinstance(parsed_tags, list) and parsed_tags:
                            tags = [str(t).strip() for t in parsed_tags if str(t).strip()]
                    except Exception:
                        pass
                else:
                    parts = [p.strip() for p in tags_raw.split(",") if p.strip()]
                    if parts:
                        tags = [p if p.startswith("#") else f"#{p}" for p in parts]

            try:
                execution_count = int(row.get("execution_count") or 0)
            except ValueError:
                execution_count = 0

            last_executed_at = (row.get("last_executed_at") or "").strip() or None
            created_at = (row.get("created_at") or "").strip() or now

            inst = AIInstrument(
                tool_id=tool_id,
                name=name,
                tool_type=tool_type,
                command=command,
                description=description,
                target_entity=target_entity,
                parameters_schema=parameters_schema,
                risk_level=risk_level,
                author_agent=author_agent,
                tags=tags,
                execution_count=execution_count,
                last_executed_at=last_executed_at,
                created_at=created_at,
                updated_at=now,
            )
            saved = self.storage.save_instrument(inst)
            imported.append(saved)

        logger.info(f"[AIInstrumentsService] Импортировано {len(imported)} инструментов из CSV: {file_path}")
        return imported

    def seed_default_instruments(self, force: bool = False) -> List[AIInstrument]:
        """Синхронизирует базу со стандартным каталогом инструментов из apps/windows/sdk и .agents/skills.

        Args:
            force: Принудительно перезаписать все стандартные инструменты, даже если они уже есть в БД.

        Returns:
            List[AIInstrument]: Список добавленных или обновлённых инструментов.
        """
        existing_ids = set()
        if not force:
            try:
                existing = self.storage.list_instruments(limit=500)
                existing_ids = {it.tool_id for it in existing}
                if len(existing_ids) >= len(DEFAULT_AGENT_INSTRUMENTS):
                    return []
            except Exception as ex:
                logger.warning(f"[AIInstrumentsService] Ошибка проверки инструментов перед синхронизацией: {ex}")
                return []

        seeded: List[AIInstrument] = []
        for raw in DEFAULT_AGENT_INSTRUMENTS:
            if not force and raw.get("tool_id") in existing_ids:
                continue
            try:
                item = AIInstrumentCreate(**raw)
                saved = self.save_instrument(item)
                seeded.append(saved)
            except Exception as ex:
                logger.warning(f"[AIInstrumentsService] Не удалось сохранить базовый инструмент {raw.get('tool_id')}: {ex}")
        return seeded

    def extract_and_save_from_text(
        self,
        text: str,
        target_entity: str = "",
        title_prefix: str = "Инструмент агента",
        author: str = "reasoning_chain",
    ) -> List[AIInstrument]:
        """Извлекает PowerShell/CMD скрипты из цепочки рассуждений или советов и сохраняет их в ai_instruments.db.

        Args:
            text: Текст ответа модели или блок developer_advice.
            target_entity: Канонический ключ или имя сущности.
            title_prefix: Базовый заголовок для именования инструментов.
            author: Имя агента-источника.

        Returns:
            List[AIInstrument]: Список сохраненных инструментов.
        """
        if not text:
            return []

        saved_tools: List[AIInstrument] = []
        # Поиск блоков ```powershell ... ``` или ```cmd ... ```
        pattern = re.compile(r"```(powershell|pwsh|ps1|cmd|bat)?\s*([\s\S]*?)```", re.IGNORECASE)
        matches = pattern.findall(text)

        idx = 1
        for lang, code in matches:
            clean_code = code.strip()
            if not clean_code:
                continue

            tool_type = "cmd" if lang.lower() in ("cmd", "bat") else "powershell"
            first_line = clean_code.splitlines()[0][:50].replace("#", "").strip()
            tool_name = f"{title_prefix}: {first_line}" if first_line else f"{title_prefix} #{idx}"

            item = AIInstrumentCreate(
                name=tool_name,
                tool_type=tool_type,
                command=clean_code,
                description=f"Автоматически извлечен из цепочки рассуждений для {target_entity or 'системы'}",
                target_entity=target_entity,
                author_agent=author,
                tags=["#reasoning_extracted", f"#{tool_type}"],
            )
            saved = self.save_instrument(item)
            saved_tools.append(saved)
            idx += 1

        return saved_tools

    def execute_instrument(
        self,
        tool_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_sec: int = 35,
        as_admin: bool = False,
    ) -> Dict[str, Any]:
        """Выполняет инструмент из базы ai_instruments.db на хосте Windows.

        Args:
            tool_id: Идентификатор инструмента.
            parameters: Параметры для подстановки.
            timeout_sec: Таймаут выполнения в секундах.
            as_admin: Запуск от имени Администратора.

        Returns:
            Dict[str, Any]: Результат выполнения (exit_code, stdout, stderr, duration_ms).
        """
        inst = self.get_instrument(tool_id)
        if not inst:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Инструмент '{tool_id}' не найден в ai_instruments.db",
                "duration_ms": 0.0,
            }

        cmd_to_run = inst.command
        if parameters:
            for k, v in parameters.items():
                cmd_to_run = cmd_to_run.replace(f"{{{k}}}", str(v))

        shell_type = inst.tool_type.lower()
        start_time = time.perf_counter()

        try:
            if as_admin:
                temp_dir = tempfile.gettempdir()
                uid = uuid.uuid4().hex[:8]
                out_file = os.path.join(temp_dir, f"inst_out_{uid}.txt")
                wrapper_ps1 = os.path.join(temp_dir, f"inst_wrap_{uid}.ps1")

                inner = f'cmd.exe /c "{cmd_to_run}"' if shell_type == "cmd" else f"& {{ {cmd_to_run} }}"
                wrapper_code = f"""[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'
try {{
    {inner} *>&1 | Out-File -FilePath "{out_file}" -Encoding utf8
    $code = $LASTEXITCODE
    if ($null -eq $code) {{ $code = 0 }}
    exit $code
}} catch {{
    $_ | Out-File -FilePath "{out_file}" -Append -Encoding utf8
    exit 1
}}
"""
                with open(wrapper_ps1, "w", encoding="utf-8") as f:
                    f.write(wrapper_code)

                runner_args = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f'Start-Process powershell.exe -ArgumentList \'-NoProfile\', \'-ExecutionPolicy\', \'Bypass\', \'-File\', \'"{wrapper_ps1}"\' -Verb RunAs -Wait',
                ]
                proc = subprocess.run(runner_args, capture_output=True, text=True, timeout=timeout_sec)
                output = ""
                if os.path.exists(out_file):
                    with open(out_file, "r", encoding="utf-8", errors="replace") as f:
                        output = f.read()
                    try:
                        os.remove(out_file)
                    except Exception:
                        pass
                try:
                    os.remove(wrapper_ps1)
                except Exception:
                    pass

                exit_code = proc.returncode
                stdout_res = output.strip()
                stderr_res = proc.stderr.strip()
            else:
                if shell_type == "cmd":
                    args = ["cmd.exe", "/c", f"chcp 65001 >nul & {cmd_to_run}"]
                elif shell_type == "pwsh":
                    args = ["pwsh.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd_to_run}"]
                else:
                    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd_to_run}"]

                proc = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_sec,
                    shell=False,
                )
                exit_code = proc.returncode
                stdout_res = proc.stdout.strip()
                stderr_res = proc.stderr.strip()

            duration = round((time.perf_counter() - start_time) * 1000, 2)
            success = (exit_code == 0)
            self.storage.record_execution(tool_id)

            return {
                "success": success,
                "exit_code": exit_code,
                "stdout": stdout_res,
                "stderr": stderr_res,
                "duration_ms": duration,
                "tool_id": tool_id,
            }
        except subprocess.TimeoutExpired:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Превышен таймаут выполнения ({timeout_sec}с)",
                "duration_ms": duration,
                "tool_id": tool_id,
            }
        except Exception as ex:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Ошибка запуска инструмента: {ex}",
                "duration_ms": duration,
                "tool_id": tool_id,
            }

