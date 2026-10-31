# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления процессами Linux (ps / procfs / kill)
# =============================================================================
# Description:
#   Реализация операций управления процессами на платформе Linux:
#   process_list, process_get, process_start, process_stop, process_tree и
#   process_resource_usage с поддержкой PID, PPID, пользователя, CPU и RAM.
#
# File: processes.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:55:00
# =============================================================================

import shlex
from typing import Any, Dict, List
from ...transports.base import BaseTransport
from ..base import pack_raw_result


class LinuxProcessAdapter:
    """Адаптер мониторинга и управления процессами ОС Linux.

    Examples:
        >>> adapter = LinuxProcessAdapter()
    """

    @staticmethod
    async def process_list(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение списка процессов через `ps -eo pid,ppid,user,%cpu,rss,comm`.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            limit (int): Максимальное количество возвращаемых процессов.

        Returns:
            Dict[str, Any]: Список процессов в `processes`.

        Examples:
            >>> pass
        """
        cmd = f"ps -eo pid=,ppid=,user=,%cpu=,rss=,comm= | head -n {int(limit)}"
        raw = await transport.execute_command(cmd, shell="bash", timeout=20)
        procs: List[Dict[str, Any]] = []
        for line in raw.stdout.splitlines():
            parts = line.split(None, 5)
            if len(parts) >= 6:
                procs.append(
                    {
                        "pid": int(parts[0]) if parts[0].isdigit() else 0,
                        "ppid": int(parts[1]) if parts[1].isdigit() else 0,
                        "username": parts[2],
                        "cpu_percent": float(parts[3]) if parts[3].replace(".", "", 1).isdigit() else 0.0,
                        "ram_mb": round(int(parts[4]) / 1024.0, 2) if parts[4].isdigit() else 0.0,
                        "name": parts[5],
                    }
                )
        return pack_raw_result(raw, {"processes": procs})

    @staticmethod
    async def process_get(transport: BaseTransport, pid: int) -> Dict[str, Any]:
        """Получение сведений о конкретном процессе Linux по PID.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            pid (int): Идентификатор процесса.

        Returns:
            Dict[str, Any]: Сведения о процессе.

        Examples:
            >>> pass
        """
        cmd = f"ps -p {int(pid)} -o pid=,ppid=,user=,%cpu=,rss=,comm="
        raw = await transport.execute_command(cmd, shell="bash", timeout=15)
        parts = raw.stdout.strip().split(None, 5)
        info: Dict[str, Any] = {}
        if len(parts) >= 6:
            info = {
                "pid": int(parts[0]),
                "ppid": int(parts[1]),
                "username": parts[2],
                "cpu_percent": float(parts[3]),
                "ram_mb": round(int(parts[4]) / 1024.0, 2),
                "name": parts[5],
            }
        return pack_raw_result(raw, info)

    @staticmethod
    async def process_start(
        transport: BaseTransport, executable: str, arguments: List[str] = []
    ) -> Dict[str, Any]:
        """Фоновый запуск процесса на узле Linux с возвратом PID.

        Args:
            transport (BaseTransport): Активный транспорт.
            executable (str): Исполняемый файл.
            arguments (List[str]): Список аргументов.

        Returns:
            Dict[str, Any]: PID запущенного процесса.

        Examples:
            >>> pass
        """
        safe_cmd = " ".join([shlex.quote(executable)] + [shlex.quote(str(a)) for a in (arguments or [])])
        raw = await transport.execute_command(
            f"nohup {safe_cmd} >/dev/null 2>&1 & echo $!", shell="bash", timeout=15
        )
        pid_val = int(raw.stdout.strip()) if raw.stdout.strip().isdigit() else 0
        return pack_raw_result(raw, {"pid": pid_val, "executable": executable})

    @staticmethod
    async def process_stop(transport: BaseTransport, pid: int) -> Dict[str, Any]:
        """Завершение процесса Linux по PID (`kill -TERM`).

        Args:
            transport (BaseTransport): Активный транспорт.
            pid (int): Идентификатор процесса.

        Returns:
            Dict[str, Any]: Подтверждение отправки сигнала завершения.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command(
            f"kill -TERM {int(pid)}", shell="bash", timeout=15, elevate=True
        )
        return pack_raw_result(raw, {"stopped_pid": int(pid)})

    @staticmethod
    async def process_tree(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение дерева процессов Linux.

        Args:
            transport (BaseTransport): Активный транспорт.
            limit (int): Лимит записей.

        Returns:
            Dict[str, Any]: Иерархия процессов.

        Examples:
            >>> pass
        """
        listed = await LinuxProcessAdapter.process_list(transport, limit=limit)
        listed["tree"] = listed.get("processes", [])
        return listed

    @staticmethod
    async def process_resource_usage(transport: BaseTransport, top_n: int = 10) -> Dict[str, Any]:
        """Получение топ-N ресурсоёмких процессов Linux.

        Args:
            transport (BaseTransport): Активный транспорт.
            top_n (int): Количество процессов.

        Returns:
            Dict[str, Any]: Топ процессов в `top_processes`.

        Examples:
            >>> pass
        """
        listed = await LinuxProcessAdapter.process_list(transport, limit=100)
        procs = sorted(
            listed.get("processes", []),
            key=lambda x: float(x.get("ram_mb", 0.0)),
            reverse=True,
        )
        listed["top_processes"] = procs[: int(top_n)]
        return listed
