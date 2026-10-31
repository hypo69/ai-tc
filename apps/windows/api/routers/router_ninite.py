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
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 19:30:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер для управления установщиком и автообновлением Ninite."""

import datetime
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from logger import logger

router = APIRouter(prefix="/api/ninite", tags=["Ninite Auto-Updater"])

# Стандартные пути размещения Ninite
NINITE_PROGRAM_FILES = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ninite"
NINITE_PROGRAM_DATA = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AI-Windows-Admin" / "ninite"
TASK_NAME = "NiniteAutoUpdate"


def _get_ninite_exe_path() -> Path:
    """Возвращает целевой путь к исполнимому файлу ninite.exe."""
    primary = NINITE_PROGRAM_FILES / "ninite.exe"
    if primary.exists():
        return primary
    fallback = NINITE_PROGRAM_DATA / "ninite.exe"
    if fallback.exists():
        return fallback
    return primary


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
    """Загрузка инсталлятора Ninite и сохранение в целевую директорию."""
    target_dir = NINITE_PROGRAM_FILES
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        target_dir = NINITE_PROGRAM_DATA
        target_dir.mkdir(parents=True, exist_ok=True)

    dest_path = target_dir / "ninite.exe"
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"[NiniteRouter] Файл ninite.exe сохранен: {dest_path}")
        return {"success": True, "message": f"Файл ninite.exe успешно сохранен в {dest_path}"}
    except Exception as exc:
        logger.error(f"[NiniteRouter] Ошибка сохранения инсталлятора: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сохранить файл: {exc}",
        )


@router.post("/schedule")
async def configure_ninite_schedule(req: ScheduleRequest) -> Dict[str, Any]:
    """Регистрация или обновление задачи NiniteAutoUpdate в Windows Task Scheduler."""
    exe_path = _get_ninite_exe_path()
    if not exe_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Исполняемый файл ninite.exe не найден. Сначала загрузите файл установщика.",
        )

    action_cmd = f'"{exe_path}" /silent'
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
    """Принудительный запуск обновления программ через Ninite."""
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

    try:
        subprocess.Popen([str(exe_path), "/silent"], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
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

