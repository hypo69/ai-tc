# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Forensics Module - Acquisition Layer
# =============================================================================
# Description:
#   Уровень сбора цифровых доказательств (Acquisition Layer):
#   - Артефакты выполнения: Prefetch (MAM decompress), UserAssist (ROT13)
#   - Аппаратные доказательства: история USBSTOR (серийные номера, вендоры)
#   - Жизненный цикл ОС: события загрузки, выключения, перезагрузок и BSOD
#   - Аутентификация: аудит входов в систему (Logon/Logoff)
#   - Криптографическое хеширование SHA-256 каждого источника доказательств
#
# Usage Examples:
#   from apps.windows.sdk.modules.forensics.acquisition import ForensicAcquisitionEngine
#
#   engine = ForensicAcquisitionEngine()
#   usb = engine.collect_usb_artifacts()
#   execs = engine.collect_execution_artifacts()
#
# File: acquisition.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.forensics
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations
"""Уровень сбора цифровых доказательств (Forensic Acquisition Layer)."""

import codecs
import ctypes
import glob
import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from .models import (
    ExecutionArtifact,
    RebootIncident,
    SecurityLogonEvidence,
    UsbEvidence,
)

try:
    import winreg
except ImportError:
    winreg = None

try:
    import win32evtlog
except ImportError:
    win32evtlog = None


def compute_sha256(data: bytes | str) -> str:
    """Вычисляет криптографический хеш SHA-256 для обеспечения неизменности доказательства."""
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    return hashlib.sha256(data).hexdigest()


class ForensicAcquisitionEngine:
    """Диспетчер сбора цифровых доказательств Windows (Acquisition Layer)."""

    @classmethod
    def decompress_mam_prefetch(cls, raw_data: bytes) -> Optional[bytes]:
        """Распаковывает сжатый Windows 10/11 MAM Prefetch буфер через RtlDecompressBufferEx."""
        if len(raw_data) < 8 or raw_data[:4] != b"MAM\x04":
            return raw_data if len(raw_data) >= 8 else None

        try:
            uncompressed_size = int.from_bytes(raw_data[4:8], "little")
            out_buf = ctypes.create_string_buffer(uncompressed_size)
            decomp_size = ctypes.c_ulong(0)
            work_space_size = ctypes.c_ulong(0)
            fragment_size = ctypes.c_ulong(0)

            # COMPRESSION_FORMAT_XPRESS_HUFF = 0x0004
            ntdll = ctypes.windll.ntdll
            ntdll.RtlGetCompressionWorkSpaceSize(0x0004, ctypes.byref(work_space_size), ctypes.byref(fragment_size))
            work_space = ctypes.create_string_buffer(work_space_size.value)

            res = ntdll.RtlDecompressBufferEx(
                0x0004,
                out_buf,
                uncompressed_size,
                raw_data[8:],
                len(raw_data) - 8,
                ctypes.byref(decomp_size),
                work_space,
            )
            if res == 0:
                return out_buf.raw[: decomp_size.value]
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Ошибка распаковки MAM Prefetch: {ex}")
        return None

    @classmethod
    def collect_prefetch_artifacts(cls, limit: int = 150) -> List[ExecutionArtifact]:
        """Извлекает артефакты запуска из каталога C:\\Windows\\Prefetch."""
        artifacts: List[ExecutionArtifact] = []
        try:
            pf_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch")
            if not os.path.exists(pf_dir):
                return artifacts

            pf_files = glob.glob(os.path.join(pf_dir, "*.pf"))
            # Сортируем по времени модификации (самые свежие запуски в начале)
            pf_files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)

            for pf_path in pf_files[:limit]:
                try:
                    stat = os.stat(pf_path)
                    mod_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    base_name = os.path.basename(pf_path)

                    # Извлечение имени и хэша из имени файла, например: CMD.EXE-0BDC4164.pf
                    parts = base_name.rsplit(".", 1)[0].rsplit("-", 1)
                    prog_name = parts[0]
                    pf_hash = parts[1] if len(parts) > 1 else ""

                    run_count = 1
                    try:
                        with open(pf_path, "rb") as f:
                            raw = f.read(256)
                            if raw.startswith(b"MAM\x04"):
                                # Быстро читаем полный файл для распаковки
                                f.seek(0)
                                full_raw = f.read()
                                decomp = cls.decompress_mam_prefetch(full_raw)
                                if decomp and len(decomp) >= 0xD4:
                                    run_count = int.from_bytes(decomp[0xD0:0xD4], "little")
                                    # В версии Win 10/11 имя лежит по смещению 0x10
                                    extracted_name = decomp[0x10:0x5C].decode("utf-16-le", errors="ignore").split("\x00")[0]
                                    if extracted_name:
                                        prog_name = extracted_name
                            elif len(raw) >= 0xD4 and raw[:4] in (b"SCCA", b"\x17\x00\x00\x00", b"\x1a\x00\x00\x00", b"\x1e\x00\x00\x00"):
                                run_count = int.from_bytes(raw[0xD0:0xD4], "little")
                    except Exception:
                        pass

                    file_sha = compute_sha256(f"{base_name}_{stat.st_mtime}_{stat.st_size}")
                    artifacts.append(
                        ExecutionArtifact(
                            name=prog_name,
                            source="Prefetch",
                            path=pf_path,
                            run_count=max(1, run_count),
                            last_run_time=mod_dt,
                            hash_val=pf_hash or file_sha[:16],
                        )
                    )
                except Exception as file_err:
                    logger.debug(f"[Forensics:Acquisition] Ошибка чтения {pf_path}: {file_err}")
                    continue
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Ошибка сбора Prefetch: {ex}")
        return artifacts

    @classmethod
    def collect_userassist_artifacts(cls, limit: int = 50) -> List[ExecutionArtifact]:
        """Извлекает артефакты запусков программ из реестра Windows UserAssist (ROT13)."""
        artifacts: List[ExecutionArtifact] = []
        if not winreg:
            return artifacts

        ua_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ua_path, 0, winreg.KEY_READ) as root_key:
                num_guids, _, _ = winreg.QueryInfoKey(root_key)
                for i in range(num_guids):
                    guid_str = winreg.EnumKey(root_key, i)
                    count_path = f"{ua_path}\\{guid_str}\\Count"
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, count_path, 0, winreg.KEY_READ) as count_key:
                            num_vals, _, _ = winreg.QueryInfoKey(count_key)
                            for j in range(num_vals):
                                enc_name, val_bytes, _ = winreg.EnumValue(count_key, j)
                                if not isinstance(val_bytes, (bytes, bytearray)) or len(val_bytes) < 16:
                                    continue

                                plain_name = codecs.decode(enc_name, "rot_13")
                                if plain_name.startswith("UEME_") or plain_name.endswith(".lnk"):
                                    continue

                                run_count = int.from_bytes(val_bytes[4:8], "little") if len(val_bytes) >= 8 else 0
                                if run_count <= 0:
                                    continue

                                focus_ms = int.from_bytes(val_bytes[12:16], "little") if len(val_bytes) >= 16 else 0
                                focus_sec = focus_ms // 1000
                                focus_str = f"{focus_sec // 3600:02d}:{(focus_sec % 3600) // 60:02d}:{focus_sec % 60:02d}"

                                # Последнее время выполнения из структуры FILETIME (байты 60..68)
                                last_run_iso = ""
                                if len(val_bytes) >= 68:
                                    filetime = int.from_bytes(val_bytes[60:68], "little")
                                    if filetime > 0:
                                        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
                                        last_dt = epoch + datetime.resolution * (filetime // 10)
                                        last_run_iso = last_dt.isoformat()

                                clean_prog = plain_name.replace("\\", "/").split("/")[-1]
                                artifacts.append(
                                    ExecutionArtifact(
                                        name=clean_prog or plain_name,
                                        source="UserAssist",
                                        path=plain_name,
                                        run_count=run_count,
                                        last_run_time=last_run_iso or datetime.now(timezone.utc).isoformat(),
                                        hash_val=compute_sha256(plain_name)[:16],
                                        focus_duration=focus_str,
                                    )
                                )
                    except OSError:
                        continue
            artifacts.sort(key=lambda a: a.run_count, reverse=True)
            return artifacts[:limit]
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Ошибка сбора UserAssist: {ex}")
            return artifacts

    @classmethod
    def collect_usb_artifacts(cls) -> List[UsbEvidence]:
        """Извлекает полную историю подключения USB-накопителей из реестра USBSTOR."""
        usb_list: List[UsbEvidence] = []
        if not winreg:
            return usb_list

        base_path = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path, 0, winreg.KEY_READ) as key:
                num_subkeys, _, _ = winreg.QueryInfoKey(key)
                for i in range(num_subkeys):
                    device_key_name = winreg.EnumKey(key, i)
                    # Парсинг Disk&Ven_SanDisk&Prod_Cruzer_Glide_3.0&Rev_1.00
                    vendor = "Unknown"
                    product = device_key_name
                    revision = ""
                    for part in device_key_name.split("&"):
                        if part.startswith("Ven_"):
                            vendor = part.replace("Ven_", "").replace("_", " ")
                        elif part.startswith("Prod_"):
                            product = part.replace("Prod_", "").replace("_", " ")
                        elif part.startswith("Rev_"):
                            revision = part.replace("Rev_", "")

                    dev_path = f"{base_path}\\{device_key_name}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_path, 0, winreg.KEY_READ) as dev_key:
                            inst_count, _, _ = winreg.QueryInfoKey(dev_key)
                            for j in range(inst_count):
                                inst_id = winreg.EnumKey(dev_key, j)
                                serial = inst_id.split("&")[0]

                                friendly_name = f"{vendor} {product}".strip()
                                inst_path = f"{dev_path}\\{inst_id}"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path, 0, winreg.KEY_READ) as inst_k:
                                        try:
                                            fn, _ = winreg.QueryValueEx(inst_k, "FriendlyName")
                                            if fn:
                                                friendly_name = str(fn)
                                        except OSError:
                                            pass
                                except OSError:
                                    pass

                                usb_list.append(
                                    UsbEvidence(
                                        device_id=f"USBSTOR\\{device_key_name}\\{inst_id}",
                                        vendor=vendor,
                                        product=product,
                                        revision=revision,
                                        serial_number=serial,
                                        friendly_name=friendly_name,
                                        last_connected=datetime.now(timezone.utc).isoformat(),
                                    )
                                )
                    except OSError:
                        continue
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Ошибка сбора USBSTOR: {ex}")
        return usb_list

    @classmethod
    def collect_lifecycle_reboots(cls, limit: int = 50) -> List[RebootIncident]:
        """Извлекает хронологию перезагрузок, выключений и сбоев из System Event Log."""
        reboots: List[RebootIncident] = []
        if not win32evtlog:
            return reboots

        target_map = {
            1074: ("graceful", "User32: Плановое выключение / перезагрузка процесса или пользователя"),
            41: ("dirty_shutdown", "Kernel-Power: Внезапное отключение питания или зависание ядра"),
            6008: ("dirty_shutdown", "EventLog: Неожиданное завершение работы системы"),
            1001: ("crash_bsod", "WER: Системный сбой (BSOD / BugCheck)"),
            12: ("boot", "Kernel-General: Запуск ядра операционной системы"),
            13: ("shutdown", "Kernel-General: Корректное завершение работы ОС"),
            6005: ("boot", "EventLog: Служба журнала запущена (загрузка завершена)"),
            6006: ("shutdown", "EventLog: Служба журнала остановлена (штатное выключение)"),
            7045: ("service_driver", "SCM: Установка нового системного драйвера или службы"),
        }

        try:
            hand = win32evtlog.OpenEventLog(None, "System")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

            while len(reboots) < limit:
                events = win32evtlog.ReadEventLog(hand, flags, 0)
                if not events:
                    break

                for e in events:
                    eid = int(e.EventID & 0xFFFF)
                    if eid in target_map:
                        sh_type, desc = target_map[eid]
                        t_gen = e.TimeGenerated
                        iso_t = t_gen.isoformat() if hasattr(t_gen, "isoformat") else str(t_gen)

                        inserts = e.StringInserts or []
                        detail_str = "; ".join(str(s) for s in inserts[:4]) if inserts else desc
                        initiator = str(inserts[0]) if inserts else e.SourceName

                        reboots.append(
                            RebootIncident(
                                timestamp=iso_t,
                                event_id=eid,
                                shutdown_type=sh_type,
                                source=e.SourceName,
                                reason=desc,
                                initiator=initiator,
                                details=detail_str,
                            )
                        )
                        if len(reboots) >= limit:
                            break
            win32evtlog.CloseEventLog(hand)
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Ошибка сбора жизненного цикла системы: {ex}")
        return reboots

    @classmethod
    def collect_security_logons(cls, limit: int = 40) -> List[SecurityLogonEvidence]:
        """Извлекает факты входа/выхода пользователей из журнала Security.evtx."""
        logons: List[SecurityLogonEvidence] = []
        if not win32evtlog:
            return logons

        logon_type_names = {
            2: "Interactive (Консоль/Клавиатура)",
            3: "Network (Сетевой доступ)",
            4: "Batch (Пакетный запуск)",
            5: "Service (Системная служба)",
            7: "Unlock (Разблокировка экрана)",
            10: "RemoteInteractive (RDP / Удаленный рабочий стол)",
        }

        try:
            hand = win32evtlog.OpenEventLog(None, "Security")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

            while len(logons) < limit:
                events = win32evtlog.ReadEventLog(hand, flags, 0)
                if not events:
                    break

                for e in events:
                    eid = int(e.EventID & 0xFFFF)
                    if eid in (4624, 4625, 4634, 4647):
                        t_gen = e.TimeGenerated
                        iso_t = t_gen.isoformat() if hasattr(t_gen, "isoformat") else str(t_gen)
                        inserts = e.StringInserts or []

                        username = inserts[5] if len(inserts) > 5 else "SYSTEM"
                        domain = inserts[6] if len(inserts) > 6 else ""
                        raw_ltype = int(inserts[8]) if len(inserts) > 8 and str(inserts[8]).isdigit() else 2
                        ip = inserts[18] if len(inserts) > 18 else ""

                        logons.append(
                            SecurityLogonEvidence(
                                timestamp=iso_t,
                                event_id=eid,
                                username=username,
                                domain=domain,
                                logon_type=logon_type_names.get(raw_ltype, f"Type {raw_ltype}"),
                                ip_address=ip if ip and ip != "-" else "127.0.0.1",
                                status="Success" if eid in (4624, 4634, 4647) else "Failure",
                            )
                        )
                        if len(logons) >= limit:
                            break
            win32evtlog.CloseEventLog(hand)
        except Exception as ex:
            logger.debug(f"[Forensics:Acquisition] Security.evtx недоступен (требуются права администратора): {ex}")
        return logons
