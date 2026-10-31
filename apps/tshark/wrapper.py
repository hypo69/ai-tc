# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Tshark - Wrapper
# =============================================================================
# Description:
#   Обертка для запуска утилиты TShark, захвата пакетов и чтения дампов PCAP.
#
# Usage Examples:
#   Python API:
#     from apps.tshark.wrapper import TSharkWrapper
#
#     wrapper = TSharkWrapper()
#     if wrapper.is_available():
#         interfaces = wrapper.list_interfaces()
#
# File: wrapper.py
# Project: ai-windows-admin
# Package: apps.tshark
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:41:00
# =============================================================================

from __future__ import annotations
"""Обертка для запуска утилиты TShark, захвата пакетов и чтения дампов PCAP."""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import AsyncGenerator, List, Optional, Union

from logger import logger
from .models import CaptureFilter, NetworkInterface, PacketSummary


class TSharkWrapper:
    """Управление исполняемым файлом TShark и выполнение сетевого захвата."""

    def __init__(self, tshark_path: Optional[str] = None) -> None:
        """Инициализация обертки TShark.

        Args:
            tshark_path (Optional[str]): Явный путь к tshark.exe.
        """
        self.tshark_path: Optional[str] = tshark_path or self._find_tshark()

    def _find_tshark(self) -> Optional[str]:
        """Поиск исполняемого файла tshark в локальной bin/, PATH и системных директориях Windows.

        Returns:
            Optional[str]: Путь к tshark.exe или None, если утилита не найдена.
        """
        # 1. Приоритетный поиск в локальной директории bin проекта
        project_root = Path(__file__).resolve().parents[2]
        local_bin_paths = [
            project_root / "bin" / "tshark" / "tshark.exe",
            project_root / "bin" / "wireshark" / "tshark.exe",
            project_root / "bin" / "tshark.exe",
            Path.cwd() / "bin" / "tshark" / "tshark.exe",
            Path.cwd() / "bin" / "wireshark" / "tshark.exe",
            Path.cwd() / "bin" / "tshark.exe",
        ]
        for lp in local_bin_paths:
            if lp.is_file():
                return str(lp)

        # 2. Поиск в системном PATH
        which_path = shutil.which("tshark")
        if which_path and os.path.isfile(which_path):
            return which_path

        # 3. Поиск по переменной окружения WIRESHARK_PATH
        env_path = os.environ.get("WIRESHARK_PATH")
        if env_path:
            candidate = os.path.join(env_path, "tshark.exe")
            if os.path.isfile(candidate):
                return candidate

        # 4. Стандартные системные пути установки Wireshark в Windows
        standard_paths = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
        for sp in standard_paths:
            if os.path.isfile(sp):
                return sp

        return None

    def is_available(self) -> bool:
        """Проверка доступности исполняемого файла TShark в операционной системе.

        Returns:
            bool: True, если утилита найдена и готова к использованию.
        """
        return bool(self.tshark_path and os.path.isfile(self.tshark_path))

    def list_interfaces(self) -> List[NetworkInterface]:
        """Получение списка доступных сетевых интерфейсов для захвата трафика.

        Returns:
            List[NetworkInterface]: Список обнаруженных адаптеров.
        """
        if not self.is_available():
            logger.debug("[TSharkWrapper] TShark не установлен, список интерфейсов недоступен")
            return []

        try:
            res = subprocess.run(
                [self.tshark_path, "-D"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            interfaces: List[NetworkInterface] = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^(\d+)\.\s+(\S+)(?:\s+\((.*)\))?", line)
                if match:
                    iface_id = match.group(1)
                    iface_name = match.group(2)
                    iface_desc = match.group(3) or iface_name
                    interfaces.append(
                        NetworkInterface(
                            id=iface_id,
                            name=iface_name,
                            description=iface_desc,
                        )
                    )
            return interfaces
        except Exception as ex:
            logger.error(f"[TSharkWrapper] Ошибка при вызове tshark -D: {ex}")
            return []

    def _parse_field_line(self, line: str, fallback_index: int = 1) -> Optional[PacketSummary]:
        """Парсинг строки вывода TShark (-T fields) в структурированный PacketSummary."""
        parts = line.strip("\r\n").split("\t")
        if len(parts) < 6:
            return None

        try:
            pkt_num = int(parts[0]) if parts[0].isdigit() else fallback_index
            raw_time = parts[1].strip()
            if raw_time:
                try:
                    epoch = float(raw_time)
                    iso_time = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                except ValueError:
                    iso_time = raw_time
            else:
                iso_time = datetime.now(timezone.utc).isoformat()

            src = parts[2].strip() or "0.0.0.0"
            dst = parts[3].strip() or "0.0.0.0"
            proto = parts[4].strip() or "UNKNOWN"
            length = int(parts[5]) if parts[5].isdigit() else 0

            def parse_port(val: str) -> Optional[int]:
                if not val:
                    return None
                val_clean = val.split(",")[0].strip()
                return int(val_clean) if val_clean.isdigit() else None

            src_port = parse_port(parts[6]) if len(parts) > 6 and parts[6] else (
                parse_port(parts[7]) if len(parts) > 7 and parts[7] else None
            )
            dst_port = parse_port(parts[8]) if len(parts) > 8 and parts[8] else (
                parse_port(parts[9]) if len(parts) > 9 and parts[9] else None
            )
            info = parts[10].strip() if len(parts) > 10 else ""

            return PacketSummary(
                packet_number=pkt_num,
                timestamp=iso_time,
                source=src,
                destination=dst,
                protocol=proto,
                length=length,
                source_port=src_port,
                destination_port=dst_port,
                info=info,
            )
        except Exception:
            return None

    def read_pcap(
        self,
        path: str,
        max_packets: int = 500,
        display_filter: str = "",
    ) -> List[PacketSummary]:
        """Чтение и разбор файла дампа трафика PCAP / PCAPNG.

        Args:
            path (str): Путь к файлу сетевого дампа.
            max_packets (int): Максимальное число считываемых пакетов.
            display_filter (str): Дополнительный фильтр Wireshark (display filter).

        Returns:
            List[PacketSummary]: Разобранные пакеты.
        """
        if not self.is_available():
            logger.warning("[TSharkWrapper] Чтение PCAP невозможно: TShark не установлен")
            return []

        if not os.path.isfile(path):
            logger.error(f"[TSharkWrapper] PCAP файл не найден: {path}")
            return []

        cmd = [
            self.tshark_path,
            "-r", path,
            "-c", str(max_packets),
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_epoch",
            "-e", "_ws.col.Source",
            "-e", "_ws.col.Destination",
            "-e", "_ws.col.Protocol",
            "-e", "frame.len",
            "-e", "tcp.srcport",
            "-e", "udp.srcport",
            "-e", "tcp.dstport",
            "-e", "udp.dstport",
            "-e", "_ws.col.Info",
        ]

        if display_filter:
            cmd.extend(["-Y", display_filter])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            packets: List[PacketSummary] = []
            idx = 1
            for line in res.stdout.splitlines():
                pkt = self._parse_field_line(line, fallback_index=idx)
                if pkt:
                    packets.append(pkt)
                    idx += 1
            return packets
        except Exception as ex:
            logger.error(f"[TSharkWrapper] Ошибка при чтении PCAP файла {path}: {ex}")
            return []

    async def live_capture_stream(
        self,
        filter_config: Union[CaptureFilter, str] = "1",
    ) -> AsyncGenerator[PacketSummary, None]:
        """Асинхронный генератор потока пакетов в реальном времени.

        Args:
            filter_config: Параметры фильтрации или идентификатор интерфейса.

        Yields:
            PacketSummary: Потоковые захваченные пакеты.
        """
        if not self.is_available():
            logger.warning("[TSharkWrapper] Живой захват невозможен: TShark не установлен")
            return

        iface = filter_config.interface if isinstance(filter_config, CaptureFilter) else str(filter_config)
        disp_filter = filter_config.display_filter if isinstance(filter_config, CaptureFilter) else ""

        cmd = [
            self.tshark_path,
            "-i", iface,
            "-l",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_epoch",
            "-e", "_ws.col.Source",
            "-e", "_ws.col.Destination",
            "-e", "_ws.col.Protocol",
            "-e", "frame.len",
            "-e", "tcp.srcport",
            "-e", "udp.srcport",
            "-e", "tcp.dstport",
            "-e", "udp.dstport",
            "-e", "_ws.col.Info",
        ]

        if disp_filter:
            cmd.extend(["-Y", disp_filter])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        idx = 1
        try:
            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                pkt = self._parse_field_line(line, fallback_index=idx)
                if pkt:
                    idx += 1
                    yield pkt
        except asyncio.CancelledError:
            pass
        finally:
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass

