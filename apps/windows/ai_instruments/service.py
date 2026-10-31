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
# Updated: 2026-10-31 17:47:00
# =============================================================================

from __future__ import annotations

"""Сервис управления базой инструментов ИИ-агента (ai_instruments.db)."""

import os
import re
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from logger import logger
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

