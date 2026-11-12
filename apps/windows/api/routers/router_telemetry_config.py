# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Telemetry Config
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для чтения, редактирования, валидации и сохранения
#   файла конфигурации телеметрии (%APPDATA%\AI-Windows-Admin\apps\windows\telemetry\config.json)
#   с мгновенным применением изменений на лету.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_telemetry_config import init_router
#
#     router = init_router()
#
# File: router_telemetry_config.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 20:36:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для управления конфигурацией телеметрии."""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager, get_default_telemetry_config_path

TELEMETRY_TASK_NAME = "AI-Windows-Admin-Telemetry"


class TelemetryConfigUpdateRequest(BaseModel):
    """Модель запроса на обновление структурированной конфигурации телеметрии."""
    config: Dict[str, Any] = Field(..., description="Новые параметры конфигурации JSON")


class TelemetryRawConfigUpdateRequest(BaseModel):
    """Модель запроса на сохранение сырого JSON текста конфигурации."""
    raw_json: str = Field(..., description="Сырой текст JSON конфигурации")


class TelemetryTaskInstallRequest(BaseModel):
    """Модель запроса на регистрацию фоновой службы телеметрии в Windows Task Scheduler."""
    mode: Literal["hybrid", "minimal", "full"] = Field(
        default="hybrid",
        description="Режим сбора телеметрии для задачи планировщика",
    )
    interval: Optional[float] = Field(
        default=None,
        ge=0.5,
        description="Интервал быстрого опроса в секундах",
    )
    heavy_interval: Optional[float] = Field(
        default=None,
        ge=1.0,
        description="Интервал тяжелых коллекторов в секундах",
    )
    top_processes: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Лимит Top-процессов",
    )
    run_as_current_user: bool = Field(
        default=False,
        description="Запускать задачу от текущего пользователя вместо NT AUTHORITY\\SYSTEM",
    )


def init_router() -> APIRouter:
    """Инициализирует и возвращает роутер API управления конфигурацией телеметрии.

    Returns:
        APIRouter: Сконфигурированный FastAPI роутер.
    """
    router = APIRouter(prefix="/api/windows/telemetry/config", tags=["windows-telemetry-config"])

    @router.get("")
    async def get_telemetry_config() -> Dict[str, Any]:
        """Получает текущую активную конфигурацию телеметрии из %APPDATA%.

        Returns:
            Dict[str, Any]: Словарь с конфигурацией, путем к файлу и временем изменения.
        """
        cfg_mgr = TelemetryConfigManager()
        cfg_mgr.check_and_reload()
        cfg_path = Path(cfg_mgr.config_path)
        
        last_modified = ""
        if cfg_path.is_file():
            try:
                mtime = cfg_path.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            except Exception:
                pass

        return {
            "success": True,
            "config_path": str(cfg_path),
            "last_modified": last_modified,
            "config": cfg_mgr.get_config(),
            "intervals": cfg_mgr.get_all_intervals(),
        }

    @router.get("/raw")
    async def get_raw_telemetry_config() -> Dict[str, Any]:
        """Возвращает сырой текст файла конфигурации JSON.

        Returns:
            Dict[str, Any]: Сырой текст JSON и метаданные.
        """
        cfg_path = get_default_telemetry_config_path()
        if not cfg_path.is_file():
            # Попытка инициализировать файл из шаблона
            bundled_template = Path(__file__).resolve().parents[2] / "telemetry" / "config.json"
            if bundled_template.is_file():
                try:
                    cfg_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bundled_template, cfg_path)
                except Exception as e:
                    logger.warning(f"Не удалось скопировать шаблон конфигурации: {e}")
                    cfg_path = bundled_template

        try:
            content = cfg_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Ошибка чтения файла конфигурации телеметрии {cfg_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Не удалось прочитать файл конфигурации: {e}")

        return {
            "success": True,
            "config_path": str(cfg_path),
            "raw_json": content,
        }

    @router.post("")
    @router.put("")
    async def save_telemetry_config(payload: TelemetryConfigUpdateRequest) -> Dict[str, Any]:
        """Сохраняет структурированную конфигурацию в файл %APPDATA% и инициирует горячую перезагрузку.

        Args:
            payload: Данные новой конфигурации.

        Returns:
            Dict[str, Any]: Результат операции и обновленные интервалы.
        """
        cfg_mgr = TelemetryConfigManager()
        saved = cfg_mgr.save_config(payload.config)
        if not saved:
            raise HTTPException(status_code=500, detail="Не удалось сохранить файл конфигурации")

        cfg_mgr.reload()
        logger.info(f"✅ Конфигурация телеметрии успешно обновлена через веб-интерфейс: {cfg_mgr.config_path}")

        return {
            "success": True,
            "message": "Конфигурация успешно сохранена и применена на лету",
            "config_path": cfg_mgr.config_path,
            "config": cfg_mgr.get_config(),
            "intervals": cfg_mgr.get_all_intervals(),
        }

    @router.post("/compact-now")
    async def run_compaction_now() -> Dict[str, Any]:
        """Запускает принудительное каскадное усреднение снимков телеметрии (5с -> 30с -> 3м -> 10м -> 36ч)."""
        try:
            from apps.windows.telemetry.sqlite import TelemetryStorage
            storage = TelemetryStorage.get_instance()
            storage.flush()
            cfg_mgr = TelemetryConfigManager()
            stats = storage.run_tiered_compaction(thorough_mode=cfg_mgr.is_thorough_mode())
            return {
                "success": True,
                "message": "Каскадное усреднение телеметрии выполнено",
                "stats": stats,
            }
        except Exception as ex:
            logger.error(f"Ошибка каскадного усреднения телеметрии: {ex}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(ex))

    @router.post("/raw")
    async def save_raw_telemetry_config(payload: TelemetryRawConfigUpdateRequest) -> Dict[str, Any]:
        """Валидирует и сохраняет сырой текст JSON конфигурации в %APPDATA%.

        Args:
            payload: Сырой текст JSON.

        Returns:
            Dict[str, Any]: Результат валидации и сохранения.
        """
        try:
            parsed_data = json.loads(payload.raw_json)
        except json.JSONDecodeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка синтаксиса JSON: строка {err.lineno}, колонка {err.colno}: {err.msg}",
            )

        if not isinstance(parsed_data, dict):
            raise HTTPException(status_code=400, detail="Конфигурация верхнего уровня должна быть JSON-объектом")

        cfg_mgr = TelemetryConfigManager()
        target_path = Path(cfg_mgr.config_path)
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                json.dumps(parsed_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Ошибка записи сырой конфигурации в {target_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения на диск: {e}")

        cfg_mgr.reload()
        logger.info(f"✅ Сырой JSON конфигурации телеметрии успешно сохранен и применен: {target_path}")

        return {
            "success": True,
            "message": "Сырой JSON валидирован, сохранен и применен на лету",
            "config_path": str(target_path),
            "config": cfg_mgr.get_config(),
        }

    @router.post("/reset")
    async def reset_telemetry_config_to_default() -> Dict[str, Any]:
        """Сбрасывает конфигурацию телеметрии к значениям по умолчанию из исходного шаблона.

        Returns:
            Dict[str, Any]: Результат сброса.
        """
        bundled_template = Path(__file__).resolve().parents[2] / "telemetry" / "config.json"
        if not bundled_template.is_file():
            raise HTTPException(status_code=404, detail="Исходный шаблон config.json не найден в пакете модуля")

        target_path = get_default_telemetry_config_path()
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_template, target_path)
        except Exception as e:
            logger.error(f"Не удалось сбросить конфигурацию телеметрии: {e}")
            raise HTTPException(status_code=500, detail=f"Не удалось скопировать шаблон: {e}")

        cfg_mgr = TelemetryConfigManager(config_path=str(target_path))
        cfg_mgr.reload()
        logger.info(f"↺ Конфигурация телеметрии сброшена к исходному шаблону: {target_path}")

        return {
            "success": True,
            "message": "Конфигурация телеметрии успешно сброшена к значениям по умолчанию",
            "config_path": str(target_path),
            "config": cfg_mgr.get_config(),
            "intervals": cfg_mgr.get_all_intervals(),
        }

    @router.get("/task-scheduler/status")
    async def get_telemetry_task_status() -> Dict[str, Any]:
        """Возвращает статус задачи телеметрии в Windows Task Scheduler."""
        task_status = await asyncio.to_thread(_query_telemetry_task_status, TELEMETRY_TASK_NAME)
        return {
            "success": True,
            "task": task_status,
        }

    @router.post("/task-scheduler/install")
    async def install_telemetry_task(
        payload: Optional[TelemetryTaskInstallRequest] = None,
    ) -> Dict[str, Any]:
        """Регистрирует службу телеметрии в Windows Task Scheduler с автозапуском при старте ПК."""
        req = payload or TelemetryTaskInstallRequest()
        try:
            return await asyncio.to_thread(_install_telemetry_task_sync, req)
        except FileNotFoundError as exc:
            logger.error(f"[TelemetryConfig] Скрипт установки задачи не найден: {exc}")
            raise HTTPException(status_code=404, detail=str(exc))
        except subprocess.TimeoutExpired:
            logger.error("[TelemetryConfig] Превышен таймаут установки задачи телеметрии в Task Scheduler")
            raise HTTPException(
                status_code=504,
                detail="Превышено время ожидания установки задания в Task Scheduler (возможно, ожидается подтверждение UAC)",
            )
        except Exception as exc:
            logger.error(f"[TelemetryConfig] Ошибка установки задачи телеметрии в Task Scheduler: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    router.post("/collect-heavy-sequentially")(collect_heavy_sequentially)

    # Прямой алиас по корневому пути /api/windows/telemetry/collect-heavy-sequentially
    direct_alias_router = APIRouter()
    direct_alias_router.post("/api/windows/telemetry/collect-heavy-sequentially", include_in_schema=False)(collect_heavy_sequentially)

    router.include_router(direct_alias_router)
    return router


def _get_powershell51_executable() -> str:
    """Возвращает путь к системному Windows PowerShell 5.1 (powershell.exe)."""
    sys_root = os.environ.get("SystemRoot") or r"C:\Windows"
    ps51 = Path(sys_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(ps51) if ps51.is_file() else "powershell.exe"


def _query_telemetry_task_status(task_name: str = TELEMETRY_TASK_NAME) -> Dict[str, Any]:
    """Опрашивает состояние задания телеметрии через schtasks.exe.

    Args:
        task_name: Имя задачи в Windows Task Scheduler.

    Returns:
        Dict[str, Any]: Структурированный статус задачи в планировщике.
    """
    try:
        proc = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="replace",
            timeout=15,
        )
        if proc.returncode != 0:
            return {
                "exists": False,
                "task_name": task_name,
                "state": "NotScheduled",
                "enabled": False,
            }

        state = "Ready"
        enabled = True
        run_as_user = ""
        schedule_type = ""
        task_to_run = ""
        last_run_time = ""
        next_run_time = ""
        last_result = ""

        for raw_line in (proc.stdout or "").splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key_low = key.strip().lower()
            val_clean = val.strip()
            if key_low in ("status", "состояние"):
                state = val_clean
            elif key_low in ("scheduled task state", "состояние запланированной задачи"):
                enabled = "disable" not in val_clean.lower() and "отключ" not in val_clean.lower()
            elif key_low in ("run as user", "запуск от имени"):
                run_as_user = val_clean
            elif key_low in ("schedule type", "тип расписания"):
                schedule_type = val_clean
            elif key_low in ("task to run", "запускаемая задача"):
                task_to_run = val_clean
            elif key_low in ("last run time", "время прошлого запуска"):
                last_run_time = val_clean
            elif key_low in ("next run time", "время следующего запуска"):
                next_run_time = val_clean
            elif key_low in ("last result", "прошлый результат"):
                last_result = val_clean

        return {
            "exists": True,
            "task_name": task_name,
            "state": state,
            "enabled": enabled,
            "run_as_user": run_as_user,
            "schedule_type": schedule_type,
            "task_to_run": task_to_run,
            "last_run_time": last_run_time,
            "next_run_time": next_run_time,
            "last_result": last_result,
        }
    except Exception as exc:
        logger.debug(f"[TelemetryConfig] Ошибка опроса schtasks для '{task_name}': {exc}")
        return {
            "exists": False,
            "task_name": task_name,
            "state": "Unknown",
            "enabled": False,
            "error": str(exc),
        }


def _install_telemetry_task_sync(req: TelemetryTaskInstallRequest) -> Dict[str, Any]:
    """Выполняет регистрацию службы телеметрии в Windows Task Scheduler через Install-TelemetryTask.ps1.

    Args:
        req: Параметры регистрации задачи в планировщике.

    Returns:
        Dict[str, Any]: Итоговый статус установки и сведения о задаче.

    Raises:
        FileNotFoundError: Если скрипт Install-TelemetryTask.ps1 не найден.
        RuntimeError: Если регистрация задачи завершилась с ошибкой.
    """
    installer_path = Path(__file__).resolve().parents[2] / "telemetry" / "launchers" / "Install-TelemetryTask.ps1"
    if not installer_path.is_file():
        raise FileNotFoundError(f"Скрипт установки задачи не найден: {installer_path}")

    cfg = TelemetryConfigManager().get_config()
    interval_val = float(req.interval if req.interval is not None else (cfg.get("interval_seconds") or 5.0))
    heavy_val = float(req.heavy_interval if req.heavy_interval is not None else (cfg.get("heavy_interval_seconds") or 60.0))
    top_proc_val = int(req.top_processes if req.top_processes is not None else (cfg.get("top_processes") or 10))

    cmd = [
        _get_powershell51_executable(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(installer_path),
        "-TaskName",
        TELEMETRY_TASK_NAME,
        "-Mode",
        req.mode,
        "-Interval",
        str(interval_val),
        "-HeavyInterval",
        str(heavy_val),
        "-TopProcesses",
        str(top_proc_val),
        "-Force",
    ]
    if req.run_as_current_user:
        cmd.append("-RunAsCurrentUser")

    logger.info(f"[TelemetryConfig] Регистрация службы телеметрии '{TELEMETRY_TASK_NAME}' в Task Scheduler...")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )

    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()
    if proc.returncode != 0:
        err_detail = stderr_text or stdout_text or f"Код возврата PowerShell: {proc.returncode}"
        raise RuntimeError(f"Сбой регистрации задания в Task Scheduler: {err_detail}")

    task_status = _query_telemetry_task_status(TELEMETRY_TASK_NAME)
    if not task_status.get("exists"):
        raise RuntimeError(
            "Задача не обнаружена в Task Scheduler после запуска установщика "
            "(возможно, отменён запрос UAC или отсутствуют права администратора)."
        )

    logger.info(
        f"✅ Служба телеметрии '{TELEMETRY_TASK_NAME}' установлена в Task Scheduler (состояние: {task_status.get('state')})"
    )
    return {
        "success": True,
        "message": f"Телеметрия установлена как служба в Task Scheduler ('{TELEMETRY_TASK_NAME}') с запуском при старте ПК",
        "task": task_status,
        "output": stdout_text,
    }


async def collect_heavy_sequentially(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Последовательный (по одному) запуск тяжелых коллекторов (WMI, SMART, порты, дескрипторы)."""
    import time
    collectors = (payload or {}).get("collectors", ["wmi", "smart", "ports", "handles"])
    results: Dict[str, Any] = {}

    for name in collectors:
        t0 = time.perf_counter()
        try:
            if name == "wmi":
                from apps.windows.telemetry.sensors import _probe_acpi_thermal_zones
                items = _probe_acpi_thermal_zones()
                results[name] = {"status": "OK", "items_count": len(items), "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
            elif name == "smart":
                from apps.windows.telemetry.sensors import _probe_storage_sensors
                items = _probe_storage_sensors()
                results[name] = {"status": "OK", "items_count": len(items), "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
            elif name == "ports":
                import psutil
                conns = psutil.net_connections(kind="inet")
                results[name] = {"status": "OK", "items_count": len(conns), "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
            elif name == "handles":
                from apps.windows.telemetry.deep_diagnostics import DeepDiagnosticsEngine
                leaks = DeepDiagnosticsEngine().collect_process_leaks()
                results[name] = {"status": "OK", "items_count": len(leaks.get("top_processes", [])), "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
            else:
                results[name] = {"status": "SKIPPED", "items_count": 0, "elapsed_ms": 0.0}
        except Exception as exc:
            logger.debug(f"Ошибка при последовательном запуске тяжелого коллектора '{name}': {exc}")
            results[name] = {"status": "ERROR", "error": str(exc), "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}

    return {
        "status": "SUCCESS",
        "success": True,
        "count": len(results),
        "results": results,
    }



