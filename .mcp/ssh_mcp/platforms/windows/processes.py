# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления процессами Windows
# =============================================================================
# Description:
#   Реализация операций process_list, process_get, process_start, process_stop,
#   process_tree и process_resource_usage с поддержкой PID, PPID, имени,
#   пользователя, CPU, RAM и времени запуска (Раздел 4.4 ТЗ).
#
# File: processes.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:52:45
# =============================================================================

from typing import Any, Dict, List
import psutil

from ...transports.base import BaseTransport
from ...transports.local_transport import LocalTransport
from .executor import WindowsExecutor


class WindowsProcessAdapter:
    """Адаптер мониторинга и управления процессами ОС Windows.

    Examples:
        >>> adapter = WindowsProcessAdapter()
    """

    @staticmethod
    async def process_list(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение списка процессов с PID, PPID, именем, CPU и RAM.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            limit (int): Максимальное число процессов в выборке.

        Returns:
            Dict[str, Any]: Список процессов в ключе `processes`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            items: List[Dict[str, Any]] = []
            for p in psutil.process_iter(["pid", "ppid", "name", "username", "memory_info", "create_time"]):
                try:
                    info = p.info
                    mem_mb = round((info.get("memory_info").rss if info.get("memory_info") else 0) / (1024 * 1024), 2)
                    items.append(
                        {
                            "pid": int(info.get("pid") or 0),
                            "ppid": int(info.get("ppid") or 0),
                            "name": str(info.get("name") or ""),
                            "username": str(info.get("username") or ""),
                            "ram_mb": mem_mb,
                            "started_at": int(info.get("create_time") or 0),
                        }
                    )
                    if len(items) >= limit:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"processes": items}

        ps = (
            f"Get-CimInstance Win32_Process | Select-Object -First {int(limit)} "
            "@{N='pid';E={$_.ProcessId}}, @{N='ppid';E={$_.ParentProcessId}}, "
            "@{N='name';E={$_.Name}}, @{N='ram_mb';E={[math]::Round($_.WorkingSetSize/1MB,2)}} "
            "| ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"processes": res.get("items", [res] if "pid" in res else [])}

    @staticmethod
    async def process_get(transport: BaseTransport, pid: int) -> Dict[str, Any]:
        """Получение детальной информации о процессе по его PID.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            pid (int): Идентификатор процесса.

        Returns:
            Dict[str, Any]: Детальные атрибуты процесса.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            p = psutil.Process(int(pid))
            return {
                "pid": p.pid,
                "ppid": p.ppid(),
                "name": p.name(),
                "status": p.status(),
                "ram_mb": round(p.memory_info().rss / (1024 * 1024), 2),
                "started_at": int(p.create_time()),
            }
        ps = (
            f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}'; "
            "@{pid=$p.ProcessId; ppid=$p.ParentProcessId; name=$p.Name; "
            "ram_mb=[math]::Round($p.WorkingSetSize/1MB,2)} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def process_start(
        transport: BaseTransport, executable: str, arguments: List[str] = []
    ) -> Dict[str, Any]:
        """Запуск нового процесса на узле Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            executable (str): Имя или путь исполняемого файла.
            arguments (List[str]): Список аргументов запуска.

        Returns:
            Dict[str, Any]: Сведения о запущенном процессе (`pid`, `executable`).

        Examples:
            >>> pass
        """
        safe_exec = executable.replace("'", "''")
        if arguments:
            args_str = ",".join("'" + str(a).replace("'", "''") + "'" for a in arguments)
            ps = f"$p = Start-Process -FilePath '{safe_exec}' -ArgumentList @({args_str}) -PassThru; @{{pid=$p.Id; executable='{safe_exec}'}} | ConvertTo-Json -Compress"
        else:
            ps = f"$p = Start-Process -FilePath '{safe_exec}' -PassThru; @{{pid=$p.Id; executable='{safe_exec}'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def process_stop(transport: BaseTransport, pid: int) -> Dict[str, Any]:
        """Принудительная остановка процесса по PID.

        Args:
            transport (BaseTransport): Активный транспорт.
            pid (int): Идентификатор процесса.

        Returns:
            Dict[str, Any]: Статус завершения процесса.

        Examples:
            >>> pass
        """
        ps = f"Stop-Process -Id {int(pid)} -Force -ErrorAction Stop; @{{stopped_pid={int(pid)}}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def process_tree(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Построение иерархии родительских и дочерних процессов (PID -> PPID).

        Args:
            transport (BaseTransport): Активный транспорт.
            limit (int): Максимальное количество узлов дерева.

        Returns:
            Dict[str, Any]: Дерево процессов в ключе `tree`.

        Examples:
            >>> pass
        """
        listed = await WindowsProcessAdapter.process_list(transport, limit=limit)
        procs = listed.get("processes", [])
        return {"tree": procs}

    @staticmethod
    async def process_resource_usage(transport: BaseTransport, top_n: int = 10) -> Dict[str, Any]:
        """Получение топ-N процессов по потреблению оперативной памяти.

        Args:
            transport (BaseTransport): Активный транспорт.
            top_n (int): Количество возвращаемых процессов.

        Returns:
            Dict[str, Any]: Список наиболее ресурсоёмких процессов.

        Examples:
            >>> pass
        """
        listed = await WindowsProcessAdapter.process_list(transport, limit=100)
        procs = sorted(
            listed.get("processes", []),
            key=lambda item: float(item.get("ram_mb", 0.0)),
            reverse=True,
        )
        return {"top_processes": procs[: int(top_n)]}
