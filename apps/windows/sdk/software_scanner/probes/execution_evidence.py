# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Execution Evidence Probe
# =============================================================================
# Description:
#   Зонд доказательств запуска программ (Execution Evidence): анализ записей
#   реестра UserAssist (ROT13), каталога Prefetch (*.pf) и Recent Items.
#
# File: execution_evidence.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд анализа артефактов и истории запусков ПО в Windows."""

import codecs
from datetime import datetime, timezone
import os
import struct
import sys
from typing import Any, List
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class ExecutionEvidenceProbe:
    """Зонд сбора доказательств фактического запуска приложений."""

    def __init__(self) -> None:
        self._winreg = self._get_winreg()

    @staticmethod
    def _get_winreg() -> Any:
        if sys.platform.startswith("win"):
            import winreg
            return winreg
        return None

    def scan_userassist(self) -> List[EvidenceItem]:
        """Сбор и декодирование записей UserAssist из HKCU (ROT13)."""
        items: List[EvidenceItem] = []
        if not self._winreg:
            return items

        ua_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
        try:
            with self._winreg.OpenKey(self._winreg.HKEY_CURRENT_USER, ua_path, 0, self._winreg.KEY_READ) as ua_key:
                num_guids, _, _ = self._winreg.QueryInfoKey(ua_key)
                for i in range(num_guids):
                    guid_name = self._winreg.EnumKey(ua_key, i)
                    count_path = f"{ua_path}\\{guid_name}\\Count"
                    try:
                        with self._winreg.OpenKey(self._winreg.HKEY_CURRENT_USER, count_path, 0, self._winreg.KEY_READ) as count_key:
                            num_vals, _, _ = self._winreg.QueryInfoKey(count_key)
                            for v_idx in range(num_vals):
                                try:
                                    val_name, val_data, val_type = self._winreg.EnumValue(count_key, v_idx)
                                    decoded_name = codecs.decode(val_name, "rot_13")

                                    # Пропускаем служебные GUID
                                    if not decoded_name.strip() or decoded_name.startswith("{"):
                                        continue

                                    run_count = 0
                                    focus_seconds = 0
                                    last_exec_iso = None

                                    if val_type == self._winreg.REG_BINARY and len(val_data) >= 72:
                                        run_count = struct.unpack_from("<I", val_data, 4)[0]
                                        focus_ms = struct.unpack_from("<I", val_data, 12)[0]
                                        focus_seconds = round(focus_ms / 1000.0)

                                        # FILETIME в смещении 60 (8 байт)
                                        filetime = struct.unpack_from("<Q", val_data, 60)[0]
                                        if filetime > 0:
                                            # Конвертация FILETIME (100-нс интервалы с 1601-01-01)
                                            timestamp = (filetime - 116444736000000000) / 10000000
                                            if timestamp > 0:
                                                try:
                                                    last_exec_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                                                except (ValueError, OSError):
                                                    pass

                                    # Очистка имени программы/пути
                                    clean_name = decoded_name.split("\\")[-1]
                                    if clean_name.endswith(".lnk"):
                                        clean_name = clean_name[:-4]

                                    items.append(EvidenceItem(
                                        evidence_type=EvidenceType.USERASSIST,
                                        source="UserAssist_ROT13",
                                        path=decoded_name,
                                        product_name=clean_name,
                                        last_execution=last_exec_iso,
                                        run_count=run_count,
                                        focus_seconds=focus_seconds,
                                        confidence=ConfidenceLevel.HIGH,
                                        raw_details={"guid": guid_name, "raw_name": decoded_name},
                                    ))
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except OSError as ex:
            logger.debug(f"[ExecutionEvidenceProbe] Ошибка сбора UserAssist: {ex}")

        return items

    def scan_prefetch(self) -> List[EvidenceItem]:
        """Сбор артефактов Prefetch (*.pf) из C:\\Windows\\Prefetch."""
        items: List[EvidenceItem] = []
        prefetch_dir = r"C:\Windows\Prefetch"
        if not os.path.isdir(prefetch_dir):
            return items

        try:
            for entry in os.scandir(prefetch_dir):
                if entry.is_file() and entry.name.upper().endswith(".PF"):
                    pf_name = entry.name
                    # Имя обычно в формате APP.EXE-HASH.pf
                    parts = pf_name.rsplit("-", 1)
                    exe_name = parts[0] if len(parts) == 2 else pf_name[:-3]

                    try:
                        stat = entry.stat()
                        mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        items.append(EvidenceItem(
                            evidence_type=EvidenceType.PREFETCH,
                            source="Windows_Prefetch",
                            path=entry.path,
                            product_name=exe_name,
                            last_execution=mtime_iso,
                            run_count=1,
                            confidence=ConfidenceLevel.HIGH,
                            raw_details={"pf_filename": pf_name, "size_bytes": stat.st_size},
                        ))
                    except (OSError, PermissionError):
                        continue
        except PermissionError:
            logger.debug("[ExecutionEvidenceProbe] Доступ к C:\\Windows\\Prefetch ограничен (требуются права администратора)")
        except Exception as ex:
            logger.debug(f"[ExecutionEvidenceProbe] Ошибка сбора Prefetch: {ex}")

        return items

    def scan_recent_items(self) -> List[EvidenceItem]:
        """Сбор ярлыков недавно открывавшихся программ из Recent."""
        items: List[EvidenceItem] = []
        recent_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
        if not os.path.isdir(recent_dir):
            return items

        try:
            for entry in os.scandir(recent_dir):
                if entry.is_file() and entry.name.endswith(".lnk"):
                    try:
                        stat = entry.stat()
                        mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        items.append(EvidenceItem(
                            evidence_type=EvidenceType.SHORTCUT,
                            source="Recent_Items",
                            path=entry.path,
                            product_name=entry.name[:-4],
                            last_execution=mtime_iso,
                            confidence=ConfidenceLevel.LOW,
                            raw_details={"recent_lnk": entry.name},
                        ))
                    except (OSError, PermissionError):
                        continue
        except Exception as ex:
            logger.debug(f"[ExecutionEvidenceProbe] Ошибка Recent Items: {ex}")

        return items

    def scan_all(self) -> List[EvidenceItem]:
        """Полный сбор доказательств запуска."""
        results: List[EvidenceItem] = []
        results.extend(self.scan_userassist())
        results.extend(self.scan_prefetch())
        results.extend(self.scan_recent_items())
        return results


__all__ = ["ExecutionEvidenceProbe"]

