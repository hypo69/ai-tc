# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Core - Electron Engine Adapter
# =============================================================================
# Description:
#   Адаптер десктопной графической оболочки Electron (Chromium + Node.js runtime).
#   Обеспечивает обнаружение рантайма Electron, запуск окна приложения,
#   мониторинг запущенных экземпляров и их корректное завершение.
#
# Usage Examples:
#   Python API:
#     from apps.windows.core.engine_adapter import ElectronEngineAdapter
#     adapter = ElectronEngineAdapter()
#     info = adapter.launch_shell("http://127.0.0.1:8000/tc")
#
# File: engine_adapter.py
# Project: ai-tc
# Package: apps.windows.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 06:45:00
# =============================================================================

from __future__ import annotations
"""Адаптер десктопной графической оболочки Electron для системы ai-tc."""

import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from logger import logger

# Определение базовой директории проекта ai-tc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ElectronEngineAdapter:
    """Адаптер десктопной графической оболочки Electron (Chromium + Node.js + IPC)."""

    engine_id: str = "electron"
    label: str = "Electron Shell (Chromium + Node.js)"

    def __init__(self, electron_app_dir: Optional[Path] = None) -> None:
        """Инициализирует адаптер Electron с путем к каталогу оболочки.

        Args:
            electron_app_dir: Путь к директории с main.js и package.json.
        """
        default_dir = _PROJECT_ROOT / "apps" / "windows" / "electron"
        self.app_dir = (electron_app_dir or default_dir).resolve()

    def _find_electron_binary(self) -> Optional[str]:
        """Ищет исполняемый файл Electron в проекте, смежных проектах или глобально.

        Returns:
            Optional[str]: Путь к бинарнику или исполняемой команде, либо None.
        """
        is_windows = os.name == "nt"
        exe_name = "electron.exe" if is_windows else "electron"
        cmd_name = "electron.cmd" if is_windows else "electron"

        candidates = []
        runtime_dir_env = os.environ.get("AITC_RUNTIME_DIR", "").strip()
        if runtime_dir_env:
            rdir = Path(runtime_dir_env)
            candidates.extend([
                rdir / "electron" / exe_name,
                rdir / "electron" / "dist" / exe_name,
            ])
        candidates.extend([
            _PROJECT_ROOT / "runtime" / "electron" / exe_name,
            _PROJECT_ROOT / "runtime" / "electron" / "dist" / exe_name,
        ])
        candidates.extend([
            # 1. Локальный node_modules текущей директории приложения
            self.app_dir / "node_modules" / "electron" / "dist" / exe_name,
            self.app_dir / "node_modules" / ".bin" / cmd_name,
            # 2. Соседний проект AI-Assistant (переиспользование рантайма)
            _PROJECT_ROOT.parent / "AI-Assistant" / "apps" / "ai_assistant" / "electron" / "node_modules" / "electron" / "dist" / exe_name,
            _PROJECT_ROOT.parent / "AI-Assistant" / "apps" / "ai_assistant" / "electron" / "node_modules" / ".bin" / cmd_name,
        ])

        for cand in candidates:
            if cand.exists():
                return str(cand.resolve())

        # 3. Глобальный исполняемый файл в PATH
        global_el = shutil.which("electron")
        if global_el:
            return global_el

        # 4. Команда npx
        npx_bin = shutil.which("npx.cmd" if is_windows else "npx") or shutil.which("npx")
        if npx_bin:
            return npx_bin

        return None

    def is_available(self) -> bool:
        """Проверяет доступность рантайма Electron и файлов оболочки.

        Returns:
            bool: True, если оболочка готова к запуску.
        """
        has_shell_files = (self.app_dir / "package.json").exists() and (self.app_dir / "main.js").exists()
        has_binary = self._find_electron_binary() is not None
        return bool(has_shell_files and has_binary)

    def get_running_pids(self) -> List[int]:
        """Возвращает список PID запущенных процессов Electron данной оболочки.

        Returns:
            List[int]: Список идентификаторов процессов.
        """
        pids: List[int] = []
        app_dir_norm = str(self.app_dir).lower().replace("\\", "/")
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if "electron" not in pname:
                        continue
                    exe = (proc.info.get("exe") or "").lower().replace("\\", "/")
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower().replace("\\", "/")
                    if app_dir_norm in exe or app_dir_norm in cmdline:
                        pids.append(int(proc.info["pid"]))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.debug(f"[ElectronEngineAdapter] Ошибка опроса процессов: {exc}")
        return pids

    def terminate_running_instances(self) -> int:
        """Завершает активные экземпляры процессов оболочки Electron.

        Returns:
            int: Количество завершенных процессов.
        """
        pids = self.get_running_pids()
        if not pids:
            return 0
        terminated = 0
        try:
            import psutil

            procs = []
            for pid in pids:
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    procs.append(p)
                    terminated += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            _, alive = psutil.wait_procs(procs, timeout=2.0)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as exc:
            logger.warning(f"[ElectronEngineAdapter] Ошибка при завершении процессов: {exc}")
        return terminated

    def launch_shell(
        self,
        url: str,
        force_fresh: bool = False,
        profile_path: Optional[Path] = None,
        cache_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Запускает десктопную оболочку Electron с переходом на URL веб-интерфейса.

        Args:
            url: URL веб-приложения для отображения.
            force_fresh: Флаг принудительного завершения предыдущих экземпляров.
            profile_path: Пользовательский каталог профиля Chromium.
            cache_path: Каталог дискового кэша Chromium.

        Returns:
            Dict[str, Any]: Словарь с результатом запуска процесса.
        """
        if force_fresh:
            self.terminate_running_instances()

        if profile_path is None or str(profile_path) == ".":
            profile_path = (_PROJECT_ROOT / "data" / "chromium" / "profiles").resolve()
        if cache_path is None or str(cache_path) == ".":
            cache_path = (_PROJECT_ROOT / "data" / "chromium" / "cache").resolve()

        profile_path.mkdir(parents=True, exist_ok=True)
        cache_path.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        # Исключаем переопределение интерпретатора родителем VS Code / Antigravity
        env.pop("ELECTRON_RUN_AS_NODE", None)
        env["AI_TC_BACKEND_URL"] = url
        env["AI_TC_CHROMIUM_PROFILE"] = str(profile_path)
        env["AI_TC_CHROMIUM_CACHE"] = str(cache_path)

        extra_args: List[str] = [
            f"--user-data-dir={profile_path}",
            f"--disk-cache-dir={cache_path}",
        ]

        binary = self._find_electron_binary()
        if not binary:
            logger.warning("[ElectronEngineAdapter] Бинарный файл Electron не найден.")
            return {
                "status": "failed",
                "engine": self.engine_id,
                "error": "Рантайм Electron не найден на компьютере",
            }

        if "npx" in binary.lower():
            cmd = [binary, "-y", "electron", str(self.app_dir), *extra_args, url]
        else:
            cmd = [binary, str(self.app_dir), *extra_args, url]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.app_dir),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {
                "status": "launched",
                "engine": self.engine_id,
                "pid": proc.pid,
                "url": url,
                "command": " ".join(cmd),
                "process": proc,
            }
        except Exception as exc:
            logger.warning(f"[ElectronEngineAdapter] Ошибка запуска процесса Electron: {exc}")
            return {
                "status": "failed",
                "engine": self.engine_id,
                "error": str(exc),
            }
