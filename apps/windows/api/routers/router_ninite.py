# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Ninite
# =============================================================================
# Description:
#   FastAPI роутер для управления автоматическим развертыванием и обновлением
#   программного обеспечения через Ninite и службу расписания Windows Task Scheduler.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_ninite import init_router
#
#     router = init_router()
#
# File: router_ninite.py
# Project: ai-tc
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 17:10:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер для управления установщиком и автообновлением Ninite."""

import asyncio
import datetime
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from logger import logger

router = APIRouter(prefix="/api/v1/ninite", tags=["Ninite Auto-Updater"])

# Стандартные пути размещения Ninite и отчетов/логов
NINITE_PROGRAM_FILES = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ninite"
NINITE_PROGRAM_DATA = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "ai-tc" / "ninite"
NINITE_EXE_NAME = "ninite.exe"
TASK_NAME = "NiniteAutoUpdate"


def _get_ninite_exe_path() -> Path:
    """Возвращает целевой путь к исполнимому файлу ninite.exe."""
    primary = NINITE_PROGRAM_FILES / NINITE_EXE_NAME
    if primary.exists():
        return primary
    fallback = NINITE_PROGRAM_DATA / NINITE_EXE_NAME
    if fallback.exists():
        return fallback
    return primary


def _write_and_replace_ninite(target_dir: Path, content: bytes) -> Tuple[Path, bool]:
    """
    Атомарно сохраняет байты установщика в `target_dir / ninite.exe`.

    Если `ninite.exe` уже существует (в том числе с атрибутом Read-Only),
    снимает защиту от записи и атомарно заменяет его новым файлом через `os.replace`.

    Args:
        target_dir (Path): Целевая директория размещения `ninite.exe`.
        content (bytes): Бинарное содержимое загруженного установщика.

    Returns:
        Tuple[Path, bool]: Кортеж `(путь_к_файлу, был_ли_заменён_существующий)`.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_path = target_dir / NINITE_EXE_NAME
    replaced = dest_path.exists()

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target_dir,
            prefix="ninite_",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(content)
            tmp_file.flush()

        if replaced:
            try:
                os.chmod(dest_path, stat.S_IWRITE)
            except OSError:
                pass

        os.replace(tmp_path, dest_path)
        tmp_path = None
        return dest_path, replaced
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _save_ninite_binary(content: bytes) -> Tuple[Path, bool]:
    """
    Сохраняет установщик Ninite с переименованием в `ninite.exe` в Program Files.

    При отсутствии файла в `Program Files` и ошибке прав доступа выполняет
    fallback-сохранение в `ProgramData`. Если же файл в `Program Files` уже
    существует, но недоступен для перезаписи, пробрасывает `PermissionError`,
    чтобы избежать рассинхронизации с устаревшей копией.

    Args:
        content (bytes): Бинарное содержимое файла установщика.

    Returns:
        Tuple[Path, bool]: Итоговый путь к `ninite.exe` и флаг замены.
    """
    primary_dest = NINITE_PROGRAM_FILES / NINITE_EXE_NAME
    try:
        return _write_and_replace_ninite(NINITE_PROGRAM_FILES, content)
    except OSError as primary_exc:
        if primary_dest.exists():
            raise PermissionError(
                f"Не удалось заменить существующий файл {primary_dest} "
                f"(требуются права администратора или файл занят): {primary_exc}"
            ) from primary_exc
        logger.warning(
            f"[NiniteRouter] Нет доступа к {NINITE_PROGRAM_FILES} ({primary_exc}), "
            f"выполняется сохранение в {NINITE_PROGRAM_DATA}"
        )
        return _write_and_replace_ninite(NINITE_PROGRAM_DATA, content)


def _get_task_status() -> Dict[str, Any]:
    """Проверяет состояние регламентной задачи NiniteAutoUpdate через schtasks."""
    try:
        cmd = ["schtasks.exe", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="cp866", errors="replace")
        if proc.returncode != 0:
            return {"exists": False, "state": "NotScheduled", "task_name": TASK_NAME}

        output = proc.stdout
        state = "Ready"
        last_run = "нет"
        next_run = "По расписанию"

        for line in output.splitlines():
            line_clean = line.strip()
            if "Состояние:" in line_clean or "Status:" in line_clean:
                state = line_clean.split(":", 1)[-1].strip()
            elif "Время прошлого запуска:" in line_clean or "Last Run Time:" in line_clean:
                last_run = line_clean.split(":", 1)[-1].strip()
            elif "Время следующего запуска:" in line_clean or "Next Run Time:" in line_clean:
                next_run = line_clean.split(":", 1)[-1].strip()

        return {
            "exists": True,
            "state": state,
            "task_name": TASK_NAME,
            "last_run_time": last_run,
            "next_run_time": next_run,
        }
    except Exception as exc:
        logger.debug(f"[NiniteRouter] Ошибка опроса schtasks: {exc}")
        return {"exists": False, "state": "Unknown", "task_name": TASK_NAME}


class ScheduleRequest(BaseModel):
    """Модель запроса настройки расписания Ninite."""
    interval: int = Field(default=2, ge=1, le=12, description="Интервал в неделях")
    time: str = Field(default="20:00", description="Время запуска ЧЧ:ММ")


@router.get("/status")
async def get_ninite_status() -> Dict[str, Any]:
    """Возвращает статус наличия ninite.exe и регламентной задачи Windows Task Scheduler."""
    exe_path = _get_ninite_exe_path()
    file_info = {
        "installed": exe_path.exists(),
        "path": str(exe_path),
        "size_bytes": exe_path.stat().st_size if exe_path.exists() else 0,
        "modified_time": (
            datetime.datetime.fromtimestamp(exe_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            if exe_path.exists()
            else None
        ),
    }

    task_info = _get_task_status()

    log_path = NINITE_PROGRAM_DATA / "ninite_update.log"
    log_content = ""
    if log_path.exists():
        try:
            log_content = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        except Exception:
            log_content = "Лог недоступен для чтения."

    return {
        "file": file_info,
        "task": task_info,
        "log": log_content or "Логи автоматического обновления отсутствуют.",
        "schedule": {"interval_weeks": 2, "time": "20:00"},
    }


@router.post("/upload")
async def upload_ninite_installer(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Загрузка инсталлятора Ninite, переименование в `ninite.exe` и сохранение в целевую директорию.

    Если `ninite.exe` уже существует в `Program Files\\Ninite`, существующий файл
    атомарно заменяется новым установщиком с именем `ninite.exe`.
    """
    original_name = Path(file.filename or NINITE_EXE_NAME).name
    if not original_name.lower().endswith(".exe"):
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ожидается исполняемый файл установщика Ninite (.exe).",
        )

    try:
        content = await file.read()
    finally:
        await file.close()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Загруженный файл установщика пуст.",
        )

    try:
        dest_path, replaced = await asyncio.to_thread(_save_ninite_binary, content)
    except PermissionError as exc:
        logger.error(f"[NiniteRouter] Нет прав для замены ninite.exe: {exc}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"[NiniteRouter] Ошибка сохранения инсталлятора: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сохранить файл: {exc}",
        )

    if replaced:
        message = f"Существующий файл ninite.exe заменён новым ({original_name} → {NINITE_EXE_NAME}) в {dest_path}"
        logger.info(f"[NiniteRouter] {message}")
    else:
        message = f"Файл {original_name} переименован в {NINITE_EXE_NAME} и сохранён в {dest_path}"
        logger.info(f"[NiniteRouter] {message}")

    return {
        "success": True,
        "replaced": replaced,
        "original_filename": original_name,
        "saved_filename": NINITE_EXE_NAME,
        "path": str(dest_path),
        "size_bytes": len(content),
        "message": message,
    }


@router.post("/schedule")
async def configure_ninite_schedule(req: ScheduleRequest) -> Dict[str, Any]:
    """Регистрация или обновление задачи NiniteAutoUpdate в Windows Task Scheduler с логированием."""
    exe_path = _get_ninite_exe_path()
    if not exe_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Исполняемый файл ninite.exe не найден. Сначала загрузите файл установщика.",
        )

    NINITE_PROGRAM_DATA.mkdir(parents=True, exist_ok=True)
    log_path = NINITE_PROGRAM_DATA / "ninite_update.log"
    # Передача пути к файлу лога аргументом к ключу /silent
    action_cmd = f'"{exe_path}" /silent "{log_path}"'
    cmd = [
        "schtasks.exe",
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        action_cmd,
        "/SC",
        "WEEKLY",
        "/MO",
        str(req.interval),
        "/ST",
        req.time,
        "/RL",
        "HIGHEST",
        "/F",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="cp866", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        logger.info(f"[NiniteRouter] Задача {TASK_NAME} запланирована: интервал {req.interval} нед, время {req.time}")
        return {"success": True, "message": f"Расписание обновлено: каждые {req.interval} нед. в {req.time}"}
    except Exception as exc:
        logger.error(f"[NiniteRouter] Ошибка создания задачи schtasks: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания задачи: {exc}",
        )


@router.post("/run-now")
async def run_ninite_now() -> Dict[str, Any]:
    """Принудительный запуск обновления программ через Ninite с сохранением лога."""
    task_info = _get_task_status()
    if task_info.get("exists"):
        try:
            cmd = ["schtasks.exe", "/Run", "/TN", TASK_NAME]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="cp866", errors="replace")
            if proc.returncode == 0:
                return {"success": True, "message": "Регламентная задача запущена в фоне"}
        except Exception as exc:
            logger.debug(f"[NiniteRouter] Сбой schtasks /Run: {exc}")

    exe_path = _get_ninite_exe_path()
    if not exe_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл ninite.exe не найден для запуска.",
        )

    NINITE_PROGRAM_DATA.mkdir(parents=True, exist_ok=True)
    log_path = NINITE_PROGRAM_DATA / "ninite_update.log"
    try:
        subprocess.Popen([str(exe_path), "/silent", str(log_path)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return {"success": True, "message": "Процесс ninite.exe /silent успешно инициирован"}
    except Exception as exc:
        logger.error(f"[NiniteRouter] Ошибка запуска ninite.exe: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запуска: {exc}",
        )


def init_router() -> APIRouter:
    """Инициализация и получение роутера Ninite."""
    return router


__all__ = ["router", "init_router"]
