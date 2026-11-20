# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Recovery
# =============================================================================
# Description:
#   FastAPI REST API роутер для интеграции и запуска внешних комплексов
#   восстановления данных (R-Studio Technician Portable, Windows File Recovery).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_recovery import init_router
#     router = init_router()
#
#   HTTP API:
#     GET  /api/v1/recovery/status
#     POST /api/v1/recovery/launch
#
# File: router_recovery.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

"""FastAPI роутер проверки статуса и запуска утилит восстановления данных (R-Studio)."""

import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

router = APIRouter(prefix="/api/v1/recovery", tags=["File Recovery Tools"])

# Относительный и абсолютные пути к исполняемому файлу R-Studio
_RELATIVE_RSTUDIO_PATH = Path("bin") / "R-Studio_Technician_9.5.191810_Portable" / "R-Studio_9.5.exe"


def _find_recovery_executable() -> tuple[Optional[Path], str]:
    """Выполняет поиск исполняемого файла утилиты восстановления данных.

    Returns:
        tuple[Optional[Path], str]: Кортеж (абсолютный_путь_или_None, относительный_путь_для_ui).
    """
    root_path = Path(__root__)
    preferred_path = root_path / _RELATIVE_RSTUDIO_PATH
    if preferred_path.is_file():
        return preferred_path, str(_RELATIVE_RSTUDIO_PATH)

    # Кандидаты внутри директории bin
    bin_dir = root_path / "bin"
    if bin_dir.is_dir():
        for candidate in bin_dir.rglob("*.exe"):
            c_name = candidate.name.lower()
            if "r-studio" in c_name or "rstudio" in c_name:
                try:
                    rel = str(candidate.relative_to(root_path))
                except ValueError:
                    rel = candidate.name
                return candidate, rel

    # Стандартные каталоги установки Windows
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    sys_candidates = [
        Path(program_files) / "R-Studio" / "R-Studio.exe",
        Path(program_files) / "R-Studio Network Edition" / "R-Studio.exe",
        Path(program_files_x86) / "R-Studio" / "R-Studio.exe",
        Path(program_files_x86) / "R-Studio Network Edition" / "R-Studio.exe",
    ]
    for sys_path in sys_candidates:
        if sys_path.is_file():
            return sys_path, str(sys_path)

    return None, str(_RELATIVE_RSTUDIO_PATH)


class RecoveryToolInfo(BaseModel):
    """Модель сведений об исполняемом файле утилиты восстановления."""
    name: str = Field(default="R-Studio Technician Portable", description="Наименование утилиты")
    exists: bool = Field(default=False, description="Признак физического присутствия файла на диске")
    path: Optional[str] = Field(default=None, description="Абсолютный путь к исполняемому файлу")
    relative_path: str = Field(default="", description="Относительный или отображаемый путь")
    size_bytes: int = Field(default=0, description="Размер файла в байтах")
    modified_time: Optional[str] = Field(default=None, description="Время последней модификации (ISO-8601)")
    version: str = Field(default="9.5", description="Версия утилиты")


class RecoveryStatusResponse(BaseModel):
    """Ответ со статусом доступности инструмента восстановления."""
    tool: RecoveryToolInfo = Field(..., description="Параметры утилиты")


class RecoveryLaunchResponse(BaseModel):
    """Ответ на команду запуска утилиты восстановления."""
    success: bool = Field(..., description="Признак успешного запуска")
    message: str = Field(..., description="Пользовательское сообщение о результате")
    pid: Optional[int] = Field(default=None, description="PID запущенного процесса Windows")
    detail: Optional[str] = Field(default=None, description="Дополнительные технические детали")


@router.get("/status", response_model=RecoveryStatusResponse)
async def get_recovery_status() -> RecoveryStatusResponse:
    """Возвращает статус доступности утилиты восстановления файлов (R-Studio)."""
    exe_path, rel_path = _find_recovery_executable()
    if exe_path and exe_path.is_file():
        stat_info = exe_path.stat()
        mtime_iso = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        tool_info = RecoveryToolInfo(
            name="R-Studio Technician Portable",
            exists=True,
            path=str(exe_path),
            relative_path=rel_path,
            size_bytes=stat_info.st_size,
            modified_time=mtime_iso,
            version="9.5",
        )
    else:
        tool_info = RecoveryToolInfo(
            name="R-Studio Technician Portable",
            exists=False,
            path=None,
            relative_path=rel_path,
            size_bytes=0,
            modified_time=None,
            version="9.5",
        )
    return RecoveryStatusResponse(tool=tool_info)


@router.post("/launch", response_model=RecoveryLaunchResponse)
async def launch_recovery_tool() -> RecoveryLaunchResponse:
    """Запускает утилиту восстановления файлов (R-Studio) в неблокирующем режиме."""
    exe_path, rel_path = _find_recovery_executable()
    if not exe_path or not exe_path.is_file():
        logger.warning(f"[RecoveryRouter] Исполняемый файл R-Studio не найден: {rel_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Исполняемый файл R-Studio не найден по пути: {rel_path}. "
                "Поместите R-Studio Technician Portable в каталог bin\\R-Studio_Technician_9.5.191810_Portable\\R-Studio_9.5.exe"
            ),
        )

    try:
        proc = subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            shell=False,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        logger.console(f"[RecoveryRouter] Успешный запуск R-Studio (PID {proc.pid}) из {exe_path}", text_color="green")
        return RecoveryLaunchResponse(
            success=True,
            message="Программа восстановления файлов R-Studio успешно запущена",
            pid=proc.pid,
        )
    except Exception as exc:
        logger.error(f"[RecoveryRouter] Ошибка запуска {exe_path}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка операционной системы при запуске R-Studio: {exc}",
        )


def init_router() -> APIRouter:
    """Возвращает инициализированный APIRouter утилит восстановления."""
    return router
