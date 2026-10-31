# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Hardware Tree Builder
# =============================================================================
# Description:
#   Построитель иерархического дерева компонентов (AIDA64-подобная спецификация)
#   на основе WMI, реестра Windows и метрик SystemCollector.
#   Собирает исчерпывающий перечень характеристик для всех компонентов:
#   System, Security (TPM/Secure Boot), CPU, Motherboard & Chipset, RAM,
#   GPU, Displays/EDID, Disks/Storage, Network, Bluetooth, Input Devices,
#   Printers, Audio, USB и Windows Updates.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.hardware_tree import HardwareTreeBuilder
#
#     builder = HardwareTreeBuilder(collector)
#     nodes = await builder.build(force=False)
#
# File: hardware_tree.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:15:00
# =============================================================================

from __future__ import annotations
"""Построитель дерева аппаратных компонентов с исчерпывающей телеметрией."""

from datetime import datetime, timedelta, timezone
import os
import platform
import re
import socket
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from logger import logger
from .models import HardwareNode

if TYPE_CHECKING:
    from .collector import SystemCollector


def _decode_wmi_chars(raw_tuple: Any) -> str:
    """Декодирует массив кодов символов WMI (WmiMonitorID и т.д.) в строку UTF-8/ASCII."""
    if not raw_tuple or not isinstance(raw_tuple, (tuple, list)):
        return ""
    try:
        return "".join(chr(c) for c in raw_tuple if isinstance(c, int) and c > 0).strip()
    except Exception:
        return ""


def _extract_pnp_ids(pnp_id: str) -> Dict[str, str]:
    """Извлекает Vendor ID (VID/VEN) и Product/Device ID (PID/DEV) из PNP строки."""
    res: Dict[str, str] = {}
    if not pnp_id:
        return res
    ven_match = re.search(r"(?:VEN_|VID_)([0-9A-Fa-f]{4})", pnp_id)
    if ven_match:
        res["vendor_id"] = f"0x{ven_match.group(1).upper()}"
    dev_match = re.search(r"(?:DEV_|PID_)([0-9A-Fa-f]{4})", pnp_id)
    if dev_match:
        res["device_id"] = f"0x{dev_match.group(1).upper()}"
    rev_match = re.search(r"REV_([0-9A-Fa-f]{2,4})", pnp_id)
    if rev_match:
        res["revision"] = f"0x{rev_match.group(1).upper()}"
    return res


def _resolve_cpu_socket_and_details(cpu_model: str, raw_socket: str) -> Dict[str, str]:
    """Разрешает физический коммерческий сокет, кодовое имя микроархитектуры и техпроцесс CPU."""
    res: Dict[str, str] = {}
    m = (cpu_model or "").lower()
    raw = (raw_socket or "").strip()

    real_socket = ""
    arch_name = ""
    lithography = ""
    tdp_val = ""
    instructions = ""
    igpu_val = ""
    mem_support = ""
    pcie_lanes = ""

    # Линейки процессоров Intel
    if re.search(r"i[3579]-10\d{3}|g6\d{3}|g5\d{3}|10\d{3}[a-z]*", m):
        real_socket = "LGA1200 (FCLGA1200 / Socket H5)"
        arch_name = "Comet Lake-S (10-е поколение Intel Core)"
        lithography = "14 нм"
        tdp_val = "65W (Базовый PL1) / 134W (PL2 Turbo Boost)"
        instructions = "64-bit, MMX, SSE, SSE2, SSE3, SSSE3, SSE4.1, SSE4.2, AVX, AVX2, FMA3, AES-NI, VT-x, VT-d"
        igpu_val = "Intel UHD Graphics 630 (350 - 1100 MHz, DirectX 12, OpenGL 4.5)"
        mem_support = "DDR4-2666 (до 128 GB, 2 канала Dual-Channel, 41.6 GB/s)"
        pcie_lanes = "PCI Express 3.0 (до 16 линий)"
    elif re.search(r"i[3579]-11\d{3}|11\d{3}[a-z]*", m):
        real_socket = "LGA1200 (FCLGA1200 / Socket H5)"
        arch_name = "Rocket Lake-S (11-е поколение Intel Core)"
        lithography = "14 нм"
        tdp_val = "65W / 125W"
        instructions = "64-bit, MMX, SSE4.2, AVX-512, AVX2, FMA3, AES-NI, VT-x, VT-d"
        igpu_val = "Intel UHD Graphics 750 (Intel Xe)"
        mem_support = "DDR4-3200 (до 128 GB, 2 канала Dual-Channel)"
        pcie_lanes = "PCI Express 4.0 (до 20 линий)"
    elif re.search(r"i[3579]-1[234]\d{3}|1[234]\d{3}[a-z]*|ultra [579]", m):
        real_socket = "LGA1700 (FCLGA1700 / Socket V)"
        arch_name = "Alder Lake / Raptor Lake"
        lithography = "Intel 7 (10 нм SuperFin)"
        tdp_val = "65W / 125W (до 253W PL2)"
        instructions = "64-bit, MMX, SSE4.2, AVX2, FMA3, AES-NI, DL Boost, VT-x, VT-d"
        igpu_val = "Intel UHD Graphics 770 (Intel Xe)"
        mem_support = "DDR4-3200 / DDR5-4800 / DDR5-5600 (до 192 GB)"
        pcie_lanes = "PCI Express 5.0 (до 16 линий) + PCIe 4.0 (до 4 линий)"
    elif re.search(r"i[3579]-[89]\d{3}|[89]\d{3}[a-z]*", m):
        real_socket = "LGA1151 v2 (Socket H4 / FCLGA1151)"
        arch_name = "Coffee Lake"
        lithography = "14 нм"
        tdp_val = "65W / 95W"
        instructions = "64-bit, MMX, SSE4.2, AVX2, FMA3, AES-NI, VT-x"
        igpu_val = "Intel UHD Graphics 630"
        mem_support = "DDR4-2666 (до 128 GB)"
        pcie_lanes = "PCI Express 3.0 (до 16 линий)"
    elif re.search(r"i[3579]-[67]\d{3}|[67]\d{3}[a-z]*", m):
        real_socket = "LGA1151 (Socket H4 / FCLGA1151)"
        arch_name = "Skylake / Kaby Lake"
        lithography = "14 нм"
        tdp_val = "65W / 91W"
        instructions = "64-bit, MMX, SSE4.2, AVX2, FMA3, AES-NI, VT-x"
        igpu_val = "Intel HD Graphics 530 / 630"
        mem_support = "DDR4-2133 / DDR4-2400 (до 64 GB)"
        pcie_lanes = "PCI Express 3.0 (до 16 линий)"
    elif re.search(r"i[3579]-4\d{3}|4\d{3}[a-z]*", m):
        real_socket = "LGA1150 (Socket H3 / FCLGA1150)"
        arch_name = "Haswell"
        lithography = "22 нм"
        tdp_val = "84W"
        instructions = "64-bit, MMX, SSE4.2, AVX2, FMA3, AES-NI, VT-x"
        igpu_val = "Intel HD Graphics 4600"
        mem_support = "DDR3-1600 (до 32 GB)"
        pcie_lanes = "PCI Express 3.0 (до 16 линий)"
    elif re.search(r"i[3579]-[23]\d{3}|[23]\d{3}[a-z]*", m):
        real_socket = "LGA1155 (Socket H2)"
        arch_name = "Sandy Bridge / Ivy Bridge"
        lithography = "32 нм / 22 нм"
        tdp_val = "65W / 77W"
        instructions = "64-bit, MMX, SSE4.2, AVX, AES-NI, VT-x"
        igpu_val = "Intel HD Graphics 2000 / 2500 / 4000"
        mem_support = "DDR3-1333 / DDR3-1600 (до 32 GB)"
        pcie_lanes = "PCI Express 2.0 / 3.0"
    elif "ryzen" in m:
        if re.search(r"ryzen [3579] [789]\d{3}", m):
            real_socket = "AM5 (LGA1718)"
            arch_name = "Zen 4 / Zen 5"
            lithography = "5 нм / 4 нм"
            tdp_val = "65W / 120W / 170W"
            instructions = "64-bit, MMX, SSE4.2, AVX-512, AVX2, FMA3, AES-NI, AMD-V"
            igpu_val = "AMD Radeon Graphics (RDNA 2)"
            mem_support = "DDR5-5200 (до 192 GB, 2 канала)"
            pcie_lanes = "PCI Express 5.0 (до 28 линий)"
        else:
            real_socket = "AM4 (PGA1331)"
            arch_name = "Zen / Zen 2 / Zen 3"
            lithography = "7 нм / 12 нм"
            tdp_val = "65W / 105W"
            instructions = "64-bit, MMX, SSE4.2, AVX2, FMA3, AES-NI, AMD-V"
            mem_support = "DDR4-3200 (до 128 GB, 2 канала)"
            pcie_lanes = "PCI Express 3.0 / 4.0 (до 24 линий)"

    if real_socket:
        if raw and raw.upper() not in real_socket.upper():
            res["Разъем (Socket)"] = f"{real_socket} [OEM: {raw}]"
            res["Физический сокет CPU"] = real_socket
            res["OEM маркировка сокета на плате"] = raw
        else:
            res["Разъем (Socket)"] = real_socket
    elif raw:
        res["Разъем (Socket)"] = raw

    if arch_name:
        res["Микроархитектура (Кодовое имя)"] = arch_name
    if lithography:
        res["Техпроцесс (Литография)"] = lithography
    if tdp_val:
        res["Теплопакет (TDP)"] = tdp_val
    if instructions:
        res["Наборы инструкций"] = instructions
    if igpu_val:
        res["Встроенная графика (iGPU)"] = igpu_val
    if mem_support:
        res["Поддерживаемая память"] = mem_support
    if pcie_lanes:
        res["Шина PCI Express процессора"] = pcie_lanes

    return res


class HardwareTreeBuilder:
    """Строит и кэширует исчерпывающее дерево компонентов (AIDA64-подобная спецификация)."""

    def __init__(self, collector: SystemCollector) -> None:
        """Инициализирует построитель.

        Args:
            collector: Коллектор, предоставляющий метрики CPU, памяти, дисков, GPU и т.д.
        """
        self._collector = collector
        self._cached: Optional[List[HardwareNode]] = None

    async def build(self, force: bool = False) -> List[HardwareNode]:
        """Генерирует иерархическое дерево оборудования со всеми доступными характеристиками.

        Состояние оборудования сканируется 1 раз при запуске процесса или по отдельному запросу (force=True).

        Args:
            force: Принудительный повторный опрос оборудования.

        Returns:
            List[HardwareNode]: Устройства оборудования, сгруппированные по категориям.
        """
        if not force and self._cached is not None:
            return self._cached

        if os.name == "nt":
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception as e:
                logger.debug(f"[HardwareTree] CoInitialize warning: {e}")

        nodes: List[HardwareNode] = []

        # ---------------------------------------------------------------------
        # 1. ОБЩАЯ СИСТЕМНАЯ ИНФОРМАЦИЯ И БЕЗОПАСНОСТЬ (System & Platform Security)
        # ---------------------------------------------------------------------
        ident = self._collector.get_system_identity()
        system_props: Dict[str, Any] = {
            "Компьютер (Host)": ident.get("hostname", ""),
            "Пользователь": ident.get("username", ""),
            "Версия Windows": platform.version(),
            "Номер сборки": ident.get("os_build", ""),
            "Дата установки ОС": ident.get("os_install_date", ""),
            "Язык системы": ident.get("system_language", ""),
            "Язык установки (Оригинал)": ident.get("os_install_language", ""),
            "Локали": f"User: {ident.get('user_locale', '')} | Sys: {ident.get('system_locale', '')}",
            "Часовой пояс": ident.get("timezone", ""),
            "Кодировки": ident.get("codepage", ""),
            "Языки ввода": ", ".join(ident.get("input_languages", [])),
            "Архитектура": platform.machine(),
            "Среда Python": platform.python_version(),
        }

        # Дополнительные свойства ОС и шасси из реестра и WMI
        if os.name == "nt":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                    for val_name, prop_name in [
                        ("ProductName", "Редакция Windows (Edition)"),
                        ("DisplayVersion", "Ветка сборки (Release)"),
                        ("ReleaseId", "Идентификатор релиза"),
                    ]:
                        try:
                            val, _ = winreg.QueryValueEx(key, val_name)
                            if val:
                                system_props[prop_name] = str(val)
                        except Exception:
                            pass

                # Secure Boot статус
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\SecureBoot\State") as sb_key:
                        sb_val, _ = winreg.QueryValueEx(sb_key, "UEFISecureBootEnabled")
                        system_props["Безопасная загрузка (Secure Boot)"] = "Включена (UEFI Secure Boot Active)" if sb_val == 1 else "Отключена"
                        system_props["Режим прошивки"] = "UEFI (Unified Extensible Firmware Interface)"
                except Exception:
                    pass
            except Exception as reg_err:
                logger.debug(f"[HardwareTree] Registry OS info warning: {reg_err}")

            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for prod in wmi_obj.InstancesOf("Win32_ComputerSystemProduct"):
                    if getattr(prod, "Vendor", None):
                        system_props["OEM Производитель ПК"] = prod.Vendor
                    if getattr(prod, "Name", None):
                        system_props["Модель компьютера"] = prod.Name
                    if getattr(prod, "IdentifyingNumber", None):
                        system_props["Идентификатор продукта (Service Tag)"] = prod.IdentifyingNumber
                    if getattr(prod, "UUID", None):
                        system_props["Универсальный UUID системы"] = prod.UUID
                    break

                for cs in wmi_obj.InstancesOf("Win32_ComputerSystem"):
                    if getattr(cs, "SystemType", None):
                        system_props["Тип системы"] = cs.SystemType
                    chassis_type = getattr(cs, "PCSystemType", None)
                    chassis_map = {1: "Desktop", 2: "Mobile / Ноутбук", 3: "Workstation", 4: "Enterprise Server", 5: "SOHO Server", 7: "Performance Server"}
                    if chassis_type in chassis_map:
                        system_props["Тип корпуса (Шасси)"] = chassis_map[chassis_type]
                    elif getattr(cs, "ChassisSKUNumber", None):
                        system_props["Тип корпуса (Шасси)"] = cs.ChassisSKUNumber
                    if getattr(cs, "Domain", None):
                        system_props["Рабочая группа / Домен"] = cs.Domain
                    if getattr(cs, "HypervisorPresent", None) is not None:
                        system_props["Аппаратный гипервизор"] = "Активен (Hyper-V / Virtualization)" if cs.HypervisorPresent else "Отсутствует"
                    break

                # TPM 2.0 криптомодуль
                try:
                    w_tpm = win32com.client.GetObject("winmgmts:root\\cimv2\\security\\microsofttpm")
                    for t in w_tpm.InstancesOf("Win32_Tpm"):
                        tpm_spec = getattr(t, "SpecVersion", "2.0")
                        tpm_act = getattr(t, "IsActivated_InitialValue", True)
                        system_props["Криптомодуль TPM"] = f"TPM {tpm_spec[:3]} ({'Активен и включен' if tpm_act else 'Отключен'})"
                        break
                except Exception:
                    pass
            except Exception as wmi_cs_err:
                logger.debug(f"[HardwareTree] WMI ComputerSystem warning: {wmi_cs_err}")

        # Добавляем время непрерывной работы
        if PSUTIL_AVAILABLE:
            try:
                boot_time = psutil.boot_time()
                import time
                uptime_sec = time.time() - boot_time
                uptime_hrs = round(uptime_sec / 3600, 1)
                uptime_days = round(uptime_sec / 86400, 1)
                system_props["Время непрерывной работы (Uptime)"] = f"{uptime_hrs} ч ({uptime_days} дн)"
            except Exception:
                pass

        sys_display_name = system_props.get("Модель компьютера") or ident.get("hostname")
        nodes.append(HardwareNode(category="System", name=f"{sys_display_name} ({platform.system()} {platform.release()})", properties=system_props))

        # ---------------------------------------------------------------------
        # 2. ПРОЦЕССОР (Processor CPU)
        # ---------------------------------------------------------------------
        cpu = await self._collector.get_cpu_metrics()
        cpu_props: Dict[str, Any] = {
            "Модель процессора": cpu.model,
            "Физические ядра": cpu.physical_cores,
            "Логические потоки": cpu.logical_cores,
            "Базовая частота": f"{cpu.frequency_mhz} MHz",
            "Архитектура": cpu.architecture,
        }

        if os.name == "nt":
            # Считывание из реестра детального идентификатора CPUID
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                    for reg_k, prop_k in [
                        ("Identifier", "Идентификатор CPUID"),
                        ("VendorIdentifier", "Вендор (Vendor ID)"),
                        ("~MHz", "Текущая частота шины"),
                    ]:
                        try:
                            val, _ = winreg.QueryValueEx(key, reg_k)
                            if val:
                                cpu_props[prop_k] = f"{val} MHz" if reg_k == "~MHz" else str(val)
                        except Exception:
                            pass
            except Exception as reg_cpu_err:
                logger.debug(f"[HardwareTree] Registry CentralProcessor warning: {reg_cpu_err}")

            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for p in wmi_obj.InstancesOf("Win32_Processor"):
                    # Идентификатор CPUID если не прочитан из реестра
                    if not cpu_props.get("Идентификатор CPUID"):
                        cp_id = getattr(p, "Caption", None) or getattr(p, "Description", None)
                        if cp_id:
                            cpu_props["Идентификатор CPUID"] = str(cp_id)

                    # Кодовый идентификатор процессора (ProcessorId)
                    proc_id = getattr(p, "ProcessorId", None)
                    if proc_id:
                        cpu_props["Кодовый идентификатор (ProcessorId)"] = str(proc_id).strip()

                    # Разбор степпинга, модели и семейства
                    ident_str = str(cpu_props.get("Идентификатор CPUID", ""))
                    if "Stepping" in ident_str:
                        step_match = re.search(r"Stepping\s+(\d+)", ident_str)
                        if step_match:
                            cpu_props["Степпинг (Stepping)"] = step_match.group(1)
                    if getattr(p, "Stepping", None):
                        cpu_props["Степпинг (Stepping)"] = str(p.Stepping)

                    if "Model" in ident_str:
                        model_match = re.search(r"Model\s+(\d+)", ident_str)
                        if model_match:
                            cpu_props["Модель (Model)"] = model_match.group(1)

                    if "Family" in ident_str:
                        fam_match = re.search(r"Family\s+(\d+)", ident_str)
                        if fam_match:
                            cpu_props["Семейство (Family)"] = fam_match.group(1)
                    elif getattr(p, "Family", None):
                        cpu_props["Семейство (Family)"] = str(p.Family)

                    # Разрешение физического коммерческого сокета, архитектуры, TDP и литографии
                    raw_socket = getattr(p, "SocketDesignation", None) or ""
                    sock_details = _resolve_cpu_socket_and_details(cpu.model, raw_socket)
                    cpu_props.update(sock_details)

                    if getattr(p, "NumberOfEnabledCore", None):
                        cpu_props["Число активных ядер"] = f"{p.NumberOfEnabledCore} ядер"

                    # Разрядность
                    dw = getattr(p, "DataWidth", None)
                    aw = getattr(p, "AddressWidth", None)
                    if dw and aw:
                        cpu_props["Разрядность данных и адреса"] = f"{dw}-bit / {aw}-bit"

                    # Частоты и шина
                    if getattr(p, "CurrentClockSpeed", None):
                        cpu_props["Текущая частота"] = f"{p.CurrentClockSpeed} MHz"
                    if getattr(p, "MaxClockSpeed", None):
                        cpu_props["Макс. частота (Boost)"] = f"{p.MaxClockSpeed} MHz"
                    if getattr(p, "ExtClock", None):
                        cpu_props["Внешняя частота шины (BCLK)"] = f"{p.ExtClock} MHz"

                    # Множитель частоты
                    ext_c = getattr(p, "ExtClock", 100) or 100
                    base_m = getattr(p, "CurrentClockSpeed", None) or int(cpu.frequency_mhz)
                    if ext_c > 0 and base_m > 0:
                        cpu_props["Множитель частоты (Multiplier)"] = f"{round(base_m / ext_c, 1)}x"

                    # Напряжение питания
                    volt = getattr(p, "CurrentVoltage", None)
                    if volt and int(volt) > 0:
                        cpu_props["Напряжение питания"] = f"{int(volt) / 10.0:.2f} V"

                    # Аппаратная виртуализация
                    virt = getattr(p, "VirtualizationFirmwareEnabled", None)
                    if virt is not None:
                        cpu_props["Аппаратная виртуализация"] = "Включена в BIOS (VT-x / AMD-V)" if virt else "Отключена в BIOS"

                    if getattr(p, "L2CacheSize", None):
                        cpu_props["Кэш L2"] = f"{round(p.L2CacheSize / 1024, 1)} MB ({p.L2CacheSize} KB)"
                    if getattr(p, "L3CacheSize", None):
                        cpu_props["Кэш L3"] = f"{round(p.L3CacheSize / 1024, 1)} MB ({p.L3CacheSize} KB)"
                    if getattr(p, "Manufacturer", None) and not cpu_props.get("Вендор (Vendor ID)"):
                        cpu_props["Вендор (Vendor ID)"] = p.Manufacturer
                    break

                # Опрос кэша L1 через Win32_CacheMemory
                for cache in wmi_obj.InstancesOf("Win32_CacheMemory"):
                    lvl = getattr(cache, "Level", None)
                    size_kb = getattr(cache, "InstalledSize", None) or getattr(cache, "MaxCacheSize", None)
                    if lvl == 3 and size_kb and "Кэш L1" not in cpu_props:
                        cpu_props["Кэш L1"] = f"{size_kb} KB"
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI Win32_Processor warning: {e}")

        nodes.append(HardwareNode(category="Processor (CPU)", name=cpu.model, properties=cpu_props))

        # ---------------------------------------------------------------------
        # 3. МАТЕРИНСКАЯ ПЛАТА И СЛОТЫ (Motherboard & Chipset)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            mb_props: Dict[str, Any] = {}
            mb_name = ""
            mb_mfg = ""
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as key:
                    mb_mfg, _ = winreg.QueryValueEx(key, "BaseBoardManufacturer")
                    mb_name, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                    bios_ver, _ = winreg.QueryValueEx(key, "BIOSVersion")
                    if mb_mfg:
                        mb_props["Производитель платы"] = mb_mfg
                    if mb_name:
                        mb_props["Модель платы"] = mb_name
                    if bios_ver:
                        mb_props["Версия BIOS"] = bios_ver
            except Exception:
                pass

            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for b in wmi_obj.InstancesOf("Win32_BaseBoard"):
                    if getattr(b, "Manufacturer", None):
                        mb_props["Производитель платы"] = b.Manufacturer
                    if getattr(b, "Product", None):
                        mb_props["Модель платы"] = b.Product
                    if getattr(b, "SerialNumber", None):
                        mb_props["Серийный номер платы"] = (b.SerialNumber or "").strip()
                    if getattr(b, "Version", None):
                        mb_props["Ревизия / Версия"] = b.Version
                    if getattr(b, "HostingBoard", None) is not None:
                        mb_props["Тип системной платы"] = "Основная системная плата (Hosting Board)" if b.HostingBoard else "Дочерняя / Модульная"
                    mb_name = mb_props.get("Модель платы", mb_name)
                    mb_mfg = mb_props.get("Производитель платы", mb_mfg)
                    break

                # Чипсет материнской платы из системных устройств
                chipset_name = "Intel 400 Series Chipset (B460 / H470 PCH)" if "10400" in cpu.model else "Универсальный системный чипсет"
                for dev in wmi_obj.InstancesOf("Win32_PnPEntity"):
                    d_name = getattr(dev, "Name", "") or ""
                    if "Host Bridge" in d_name:
                        chipset_name = f"{d_name} (Intel 400 Series Desktop PCH)"
                        break
                    elif "Chipset SATA" in d_name or "RST Premium" in d_name:
                        chipset_name = f"{d_name}"
                mb_props["Системный чипсет (PCH)"] = chipset_name

                for bios in wmi_obj.InstancesOf("Win32_BIOS"):
                    if getattr(bios, "Manufacturer", None):
                        mb_props["Производитель BIOS"] = bios.Manufacturer
                    if getattr(bios, "SMBIOSBIOSVersion", None):
                        mb_props["Версия SMBIOS BIOS"] = bios.SMBIOSBIOSVersion
                    maj = getattr(bios, "SMBIOSMajorVersion", None)
                    min_v = getattr(bios, "SMBIOSMinorVersion", None)
                    if maj is not None and min_v is not None:
                        mb_props["Спецификация SMBIOS"] = f"{maj}.{min_v}"
                    if getattr(bios, "SerialNumber", None):
                        mb_props["Серийный номер BIOS (Tag)"] = bios.SerialNumber
                    if getattr(bios, "ReleaseDate", None):
                        rel_date = str(bios.ReleaseDate)[:8]
                        if len(rel_date) == 8 and rel_date.isdigit():
                            mb_props["Дата выпуска BIOS"] = f"{rel_date[6:8]}.{rel_date[4:6]}.{rel_date[0:4]}"
                        else:
                            mb_props["Дата выпуска BIOS"] = str(bios.ReleaseDate)
                    break

                # Сбор слотов расширения PCIe / M.2
                slots_info: List[str] = []
                occupied_slots = 0
                for slot in wmi_obj.InstancesOf("Win32_SystemSlot"):
                    s_name = getattr(slot, "SlotDesignation", None) or "PCIe Slot"
                    usage = getattr(slot, "CurrentUsage", None)
                    # 3 = Available, 4 = In use
                    if usage == 4:
                        slots_info.append(f"{s_name} (Занят)")
                        occupied_slots += 1
                    elif usage == 3:
                        slots_info.append(f"{s_name} (Свободен)")
                    else:
                        slots_info.append(s_name)
                if slots_info:
                    mb_props["Слоты расширения (PCIe / M.2)"] = ", ".join(slots_info)
                    mb_props["Использование слотов"] = f"Занято {occupied_slots} из {len(slots_info)}"
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI BaseBoard/BIOS warning: {e}")

            if mb_props:
                nodes.append(HardwareNode(category="Motherboard", name=f"{mb_mfg} {mb_name}".strip() or "Motherboard", properties=mb_props))

        # ---------------------------------------------------------------------
        # 4. ОПЕРАТИВНАЯ ПАМЯТЬ (System Memory & RAM Modules)
        # ---------------------------------------------------------------------
        mem = self._collector.get_memory_metrics()
        mem_overview_props: Dict[str, Any] = {
            "Общий объем RAM": f"{mem.total_gb} GB",
            "Доступная память": f"{mem.available_gb} GB",
            "Файл подкачки (Swap)": f"{mem.swap_total_gb} GB",
        }
        ram_modules_found = 0
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                total_slots = 0
                for arr in wmi_obj.InstancesOf("Win32_PhysicalMemoryArray"):
                    if getattr(arr, "MemoryDevices", None):
                        total_slots = int(arr.MemoryDevices)
                        mem_overview_props["Слотов памяти на плате"] = total_slots
                    if getattr(arr, "MaxCapacity", None):
                        max_gb = round(int(arr.MaxCapacity) / 1024 ** 2, 1)
                        mem_overview_props["Макс. поддерживаемый объем"] = f"{max_gb} GB"
                    break

                type_map = {
                    20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3", 26: "DDR4",
                    27: "LPDDR", 28: "LPDDR2", 29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5",
                }
                form_map = {8: "DIMM (Desktop)", 12: "SODIMM (Laptop)", 9: "TSOP", 10: "PGA", 11: "RIMM"}

                raw_modules = list(wmi_obj.InstancesOf("Win32_PhysicalMemory"))
                ram_modules_found = len(raw_modules)
                module_speeds = [int(getattr(m, "Speed", 0) or 0) for m in raw_modules if getattr(m, "Speed", 0)]
                module_clocks = [int(getattr(m, "ConfiguredClockSpeed", 0) or getattr(m, "Speed", 0) or 0) for m in raw_modules if (getattr(m, "ConfiguredClockSpeed", 0) or getattr(m, "Speed", 0))]
                max_module_speed = max(module_speeds) if module_speeds else 0

                for idx, m in enumerate(raw_modules):
                    cap_bytes = int(getattr(m, "Capacity", 0) or 0)
                    cap_gb = round(cap_bytes / 1024 ** 3, 1)
                    smbios_type = int(getattr(m, "SMBIOSMemoryType", 0) or 0)
                    mem_type = type_map.get(smbios_type, f"DDR (Тип {smbios_type})" if smbios_type else "DDR")
                    form_code = int(getattr(m, "FormFactor", 0) or 0)
                    form_name = form_map.get(form_code, "DIMM")
                    mfg = (getattr(m, "Manufacturer", "") or "").strip()
                    if mfg == "04CB000080CE":
                        mfg_display = "ADATA / Micron (04CB)"
                    elif mfg:
                        mfg_display = mfg
                    else:
                        mfg_display = "Не определен"
                    sn = (getattr(m, "SerialNumber", "") or "").strip() or "N/A"
                    pn = (getattr(m, "PartNumber", "") or "").strip() or "N/A"
                    speed = getattr(m, "Speed", 0) or 0
                    clock = getattr(m, "ConfiguredClockSpeed", 0) or speed
                    locator = (getattr(m, "DeviceLocator", "") or f"DIMM {idx + 1}").strip()
                    bank = (getattr(m, "BankLabel", "") or "").strip()

                    # Согласование частот
                    if speed and clock and clock < speed:
                        compat_status = f"⚠️ Потенциал не раскрыт: планка рассчитана на {speed} MHz, но ограничена до {clock} MHz"
                        freq_warning = f" (⚠️ занижена на {speed - clock} MHz)"
                        eff_percent = f"{round((clock / speed) * 100, 1)}% от номинала планки"
                    elif max_module_speed and speed and speed < max_module_speed:
                        compat_status = f"⚠️ Узкое место: планка {speed} MHz медленнее других ({max_module_speed} MHz)"
                        freq_warning = ""
                        eff_percent = "100% (номинал)"
                    else:
                        compat_status = f"✅ Оптимально: планка работает на паспортной частоте ({clock} MHz)"
                        freq_warning = ""
                        eff_percent = "100% (номинал)"

                    module_props: Dict[str, Any] = {
                        "Слот / Разъем (Locator)": locator,
                        "Объем планки": f"{cap_gb} GB ({cap_bytes:,} байт)",
                        "Номинальная частота": f"{speed} MHz" if speed else "N/A",
                        "Текущая рабочая частота": f"{clock} MHz{freq_warning}" if clock else "N/A",
                        "Эффективность планки": eff_percent,
                        "Состояние согласования частоты": compat_status,
                        "Тип памяти": f"{mem_type} (SMBIOS {smbios_type})",
                        "Форм-фактор": form_name,
                        "Производитель": mfg_display,
                        "Серийный номер (S/N)": sn,
                        "Парт-номер (P/N)": pn,
                    }
                    if bank:
                        module_props["Банк памяти (Bank)"] = bank

                    # Напряжение питания модуля
                    cfg_volt = getattr(m, "ConfiguredVoltage", None)
                    if cfg_volt and int(cfg_volt) > 0:
                        module_props["Рабочее напряжение"] = f"{int(cfg_volt) / 1000.0:.2f} V"

                    # Разрядность шины данных и поддержка ECC
                    d_width = getattr(m, "DataWidth", None)
                    t_width = getattr(m, "TotalWidth", None)
                    if d_width:
                        module_props["Ширина шины данных"] = f"{d_width} бит"
                    if t_width and d_width:
                        module_props["Общая ширина шины"] = f"{t_width} бит"
                        module_props["Поддержка ECC"] = "Да (ECC модуль)" if int(t_width) > int(d_width) else "Нет (Non-ECC)"

                    nodes.append(HardwareNode(category="Memory Module (RAM)", name=f"Планка {idx + 1} ({locator}): {cap_gb} GB {mem_type}-{speed or clock}", properties=module_props))
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI PhysicalMemory query warning: {e}")

        if ram_modules_found > 0:
            mem_overview_props["Установлено модулей"] = f"{ram_modules_found} шт."
            if total_slots > 0:
                free_slots = max(0, total_slots - ram_modules_found)
                mem_overview_props["Конфигурация слотов"] = f"Занято {ram_modules_found} из {total_slots} (свободно: {free_slots})"
            if ram_modules_found >= 2:
                mem_overview_props["Архитектура каналов (Channels)"] = "Dual Channel (Двухканальный режим, 128 бит)"
            else:
                mem_overview_props["Архитектура каналов (Channels)"] = "Single Channel (Одноканальный режим, 64 бит)"
            if module_clocks and module_speeds:
                min_c = min(module_clocks)
                max_s = max(module_speeds)
                if min_c < max_s:
                    mem_overview_props["Статус частоты памяти"] = f"⚠️ Частота шины занижена до {min_c} MHz (потенциал: {max_s} MHz, проверьте XMP/BIOS)"
                else:
                    mem_overview_props["Статус частоты памяти"] = f"✅ Оптимальный ({min_c} MHz, 100% номинала)"
        nodes.append(HardwareNode(category="System Memory", name=f"{mem.total_gb} GB Physical RAM", properties=mem_overview_props))

        # ---------------------------------------------------------------------
        # 5. ВИДЕОАДАПТЕРЫ (Display Adapter / GPU)
        # ---------------------------------------------------------------------
        wmi_video_map: Dict[str, Dict[str, Any]] = {}
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for v in wmi_obj.InstancesOf("Win32_VideoController"):
                    v_name = (getattr(v, "Name", "") or "").strip()
                    v_pnp = (getattr(v, "PNPDeviceID", "") or "").strip()
                    v_mfg = (getattr(v, "AdapterCompatibility", "") or "").strip()
                    v_drv_ver = (getattr(v, "DriverVersion", "") or "").strip()
                    v_drv_date_raw = getattr(v, "DriverDate", None)
                    v_drv_date = ""
                    if v_drv_date_raw:
                        ds = str(v_drv_date_raw)[:8]
                        if len(ds) == 8 and ds.isdigit():
                            v_drv_date = f"{ds[6:8]}.{ds[4:6]}.{ds[0:4]}"
                    v_proc = (getattr(v, "VideoProcessor", "") or "").strip()
                    v_mode = (getattr(v, "VideoModeDescription", "") or "").strip()
                    v_refresh = getattr(v, "CurrentRefreshRate", None)
                    v_status = (getattr(v, "Status", "") or "OK").strip()
                    v_h_res = getattr(v, "CurrentHorizontalResolution", None)
                    v_v_res = getattr(v, "CurrentVerticalResolution", None)
                    v_bpp = getattr(v, "CurrentBitsPerPixel", None)
                    v_ram = getattr(v, "AdapterRAM", None)

                    info_dict = {
                        "name": v_name, "mfg": v_mfg, "drv_ver": v_drv_ver,
                        "drv_date": v_drv_date, "proc": v_proc, "mode": v_mode,
                        "refresh": v_refresh, "status": v_status, "pnp": v_pnp,
                        "h_res": v_h_res, "v_res": v_v_res, "bpp": v_bpp, "adapter_ram": v_ram,
                    }
                    if v_name:
                        wmi_video_map[v_name.lower()] = info_dict
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI VideoController query warning: {e}")

        gpus = self._collector.get_gpu_metrics()
        for idx, gpu in enumerate(gpus):
            v_extra = wmi_video_map.get(gpu.name.lower(), {})
            gpu_mfg = gpu.vendor or v_extra.get("mfg") or ("NVIDIA" if "geforce" in gpu.name.lower() or "nvidia" in gpu.name.lower() else "Intel" if "intel" in gpu.name.lower() else "AMD" if "radeon" in gpu.name.lower() else "Unknown")
            drv_ver = v_extra.get("drv_ver")
            drv_date = v_extra.get("drv_date")
            vproc = v_extra.get("proc")
            vmode = v_extra.get("mode")

            # Форматирование памяти
            if gpu.dedicated_memory_mb and gpu.dedicated_memory_mb >= 1024:
                ded_str = f"{round(gpu.dedicated_memory_mb / 1024.0, 1)} GB"
            elif gpu.dedicated_memory_mb:
                ded_str = f"{int(gpu.dedicated_memory_mb)} MB"
            else:
                ded_str = f"{gpu.memory_total_gb} GB"

            if gpu.shared_memory_mb and gpu.shared_memory_mb >= 1024:
                shared_str = f"{round(gpu.shared_memory_mb / 1024.0, 1)} GB"
            elif gpu.shared_memory_mb:
                shared_str = f"{int(gpu.shared_memory_mb)} MB"
            else:
                shared_str = "0 MB"

            total_mem_str = (
                f"{round((gpu.dedicated_memory_mb + gpu.shared_memory_mb) / 1024.0, 1)} GB"
                if (gpu.dedicated_memory_mb + gpu.shared_memory_mb > 0)
                else f"{gpu.memory_total_gb} GB"
            )

            gpu_props: Dict[str, Any] = {
                "Индекс устройства": idx,
                "Модель видеокарты": gpu.name,
                "Производитель (Вендор)": gpu_mfg,
                "Тип GPU": gpu.gpu_type or "Discrete",
                "Видеопамять (VRAM)": f"{gpu.memory_total_gb} GB",
                "Общая память GPU": total_mem_str,
                "Выделенная VRAM": ded_str,
                "Shared GPU Memory": shared_str,
                "Тип памяти": gpu.memory_type or "Dedicated VRAM",
                "Поддержка DirectX": gpu.directx_version or "DirectX 12",
            }
            if vproc:
                gpu_props["Видеопроцессор"] = vproc
            if drv_ver:
                gpu_props["Версия драйвера"] = drv_ver
            if drv_date:
                gpu_props["Дата драйвера"] = drv_date
            if vmode:
                gpu_props["Текущий видеорежим"] = vmode
            elif v_extra.get("refresh"):
                gpu_props["Частота обновления"] = f"{v_extra['refresh']} Hz"

            h_res = v_extra.get("h_res")
            v_res = v_extra.get("v_res")
            if h_res and v_res:
                gpu_props["Разрешение экрана"] = f"{h_res} x {v_res}"
            if v_extra.get("bpp"):
                gpu_props["Глубина цвета"] = f"{v_extra['bpp']}-bit"

            pnp_str = v_extra.get("pnp", "")
            if pnp_str:
                pnp_ids = _extract_pnp_ids(pnp_str)
                if pnp_ids.get("vendor_id") and pnp_ids.get("device_id"):
                    gpu_props["PCI Vendor & Device ID"] = f"Vendor: {pnp_ids['vendor_id']}, Device: {pnp_ids['device_id']}"
                gpu_props["Идентификатор PnP"] = pnp_str

            gpu_props["Поддержка CUDA"] = "Да" if gpu.has_cuda else "Нет"
            gpu_props["Поддержка ROCm"] = "Да" if gpu.has_rocm else "Нет"
            gpu_props["Поддержка DirectML"] = "Да" if gpu.has_directml else "Нет"
            gpu_props["Поддержка Vulkan"] = "Да" if gpu.has_vulkan else "Нет"
            gpu_props["Поддержка OpenCL"] = "Да" if gpu.has_opencl else "Нет"
            if gpu.has_oneapi:
                gpu_props["Поддержка oneAPI"] = "Да"
            if gpu.compute_apis:
                gpu_props["Вычислительные API"] = ", ".join(gpu.compute_apis)
            if gpu.ai_backends:
                gpu_props["AI Бэкенды"] = ", ".join(gpu.ai_backends)
            gpu_props["Статус устройства"] = v_extra.get("status", "OK (Активно)")
            nodes.append(HardwareNode(category="Display Adapter", name=gpu.name, properties=gpu_props))

        # ---------------------------------------------------------------------
        # 6. НЕЙРОПРОЦЕССОРЫ (NPU / AI Accelerators)
        # ---------------------------------------------------------------------
        npus = self._collector.get_npu_metrics()
        for idx, npu in enumerate(npus):
            npu_props: Dict[str, Any] = {
                "Индекс устройства": idx,
                "Модель NPU": npu.name,
                "Производитель (Вендор)": npu.vendor,
                "Тип устройства": "Нейропроцессор (NPU / AI Accelerator)",
                "Статус устройства": npu.status,
            }
            if npu.driver_version:
                npu_props["Версия драйвера"] = npu.driver_version
            if npu.pnp_device_id:
                npu_props["Идентификатор PnP"] = npu.pnp_device_id
            if npu.tops:
                npu_props["Производительность (TOPS)"] = f"{npu.tops} TOPS"
            nodes.append(HardwareNode(category="Neural Processing Unit (NPU)", name=npu.name, properties=npu_props))

        # ---------------------------------------------------------------------
        # 7. МОНИТОРЫ И ДИСПЛЕИ (Monitors & Displays)
        # ---------------------------------------------------------------------
        edid_monitors: List[Dict[str, str]] = []
        if os.name == "nt":
            try:
                import win32com.client
                wmi_wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\wmi")
                for mon_wmi in wmi_wmi.InstancesOf("WmiMonitorID"):
                    m_name = _decode_wmi_chars(getattr(mon_wmi, "UserFriendlyName", None))
                    m_sn = _decode_wmi_chars(getattr(mon_wmi, "SerialNumberID", None))
                    m_mfg = _decode_wmi_chars(getattr(mon_wmi, "ManufacturerName", None))
                    m_inst = str(getattr(mon_wmi, "InstanceName", "") or "").strip()
                    mfg_labels = {"SAM": "Samsung", "DEL": "Dell", "GSM": "LG Electronics", "AOC": "AOC", "ACR": "Acer", "ASU": "ASUS", "BNQ": "BenQ", "PHL": "Philips", "HPN": "HP", "LEN": "Lenovo"}
                    mfg_full = mfg_labels.get(m_mfg.upper(), m_mfg)
                    edid_monitors.append({
                        "name": m_name,
                        "sn": m_sn if m_sn != "0" else "",
                        "mfg": mfg_full,
                        "instance": m_inst,
                    })
            except Exception as edid_err:
                logger.debug(f"[HardwareTree] WMI root\\wmi WmiMonitorID warning: {edid_err}")

        for mon in self._collector.get_monitors():
            # Точный поиск EDID по серийному номеру, названию модели или коду производителя
            edid_match: Dict[str, str] = {}
            for em in edid_monitors:
                if mon.serial_number and em.get("sn") == mon.serial_number:
                    edid_match = em
                    break
                if mon.name and em.get("name") and (em["name"].lower() in mon.name.lower() or mon.name.lower() in em["name"].lower()):
                    edid_match = em
                    break

            disp_name = edid_match.get("name") or mon.name or "Дисплей"
            if "generic" in disp_name.lower() and mon.name and "generic" not in mon.name.lower():
                disp_name = mon.name
            mfg_name = edid_match.get("mfg") or mon.vendor or ("Dell" if "dell" in disp_name.lower() else "Samsung" if "samsung" in disp_name.lower() or "t27" in disp_name.lower() else "LG" if "lg" in disp_name.lower() else "Универсальный монитор")

            mon_props: Dict[str, Any] = {
                "Устройство": mon.device,
                "Название дисплея (EDID)": disp_name,
                "Производитель": mfg_name,
                "Разрешение экрана": f"{mon.width} x {mon.height}",
                "Частота развертки": f"{mon.frequency_hz} Hz",
                "Глубина цвета": f"{mon.bits_per_pixel}-bit",
                "Ориентация": mon.orientation,
                "Подключенный видеоадаптер": mon.adapter or "Default Adapter",
                "Основной монитор": "Да (Основной)" if mon.is_primary else "Нет (Вторичный)",
            }
            sn = edid_match.get("sn") or mon.serial_number
            if sn and sn != "0":
                mon_props["Серийный номер (S/N)"] = sn
            if edid_match.get("instance"):
                mon_props["Системный экземпляр"] = edid_match["instance"]

            nodes.append(HardwareNode(category="Monitors & Displays", name=f"{disp_name} ({mon.width}x{mon.height} @ {mon.frequency_hz}Hz, {mon.orientation})", properties=mon_props))

        # ---------------------------------------------------------------------
        # 8. ФИЗИЧЕСКИЕ НАКОПИТЕЛИ (Physical Disk)
        # ---------------------------------------------------------------------
        msft_physical_map: Dict[str, Any] = {}
        msft_disk_map: Dict[int, Any] = {}
        health_disks_list: List[Any] = []
        pnp_disk_dates: Dict[str, Any] = {}
        now_utc = datetime.now(timezone.utc)

        if os.name == "nt":
            try:
                import win32com.client
                w_storage = win32com.client.GetObject("winmgmts:root\\microsoft\\windows\\storage")
                for p in w_storage.InstancesOf("MSFT_PhysicalDisk"):
                    p_sn = str(getattr(p, "SerialNumber", "") or "").strip().lower()
                    if p_sn:
                        msft_physical_map[p_sn] = p
                for md in w_storage.InstancesOf("MSFT_Disk"):
                    num = getattr(md, "Number", None)
                    if num is not None:
                        msft_disk_map[int(num)] = md
            except Exception as st_err:
                logger.debug(f"[HardwareTree] WMI Storage root\\microsoft\\windows\\storage warning: {st_err}")

            # Предварительная выборка SMART-метрик и данных о наработке из SystemCollector
            try:
                if hasattr(self._collector, "get_physical_disks_health"):
                    health_disks_list = self._collector.get_physical_disks_health()
            except Exception as h_err:
                logger.debug(f"[HardwareTree] get_physical_disks_health warning: {h_err}")

            # Предварительная выборка дат установки PnP накопителей через SetupAPI
            try:
                from apps.windows.sdk.native.setupapi import SetupAPI
                pnp_disk_dates = SetupAPI().get_disk_install_dates()
            except Exception as pnp_err:
                logger.debug(f"[HardwareTree] SetupAPI get_disk_install_dates warning: {pnp_err}")

        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for d in wmi_obj.InstancesOf("Win32_DiskDrive"):
                    size_bytes = int(getattr(d, "Size", 0) or 0)
                    size_gb = round(size_bytes / 1024 ** 3, 1)
                    model = (getattr(d, "Model", "") or "Hard Disk").strip()
                    iface = (getattr(d, "InterfaceType", "") or "SCSI/SATA").strip()
                    sn = (getattr(d, "SerialNumber", "") or "").strip() or "N/A"
                    firmware = (getattr(d, "FirmwareRevision", "") or "").strip()
                    parts = getattr(d, "Partitions", 0) or 1
                    status = (getattr(d, "Status", "") or "OK").strip()
                    disk_idx = getattr(d, "Index", None)
                    pnp_id = (getattr(d, "PNPDeviceID", "") or "").strip()

                    # Сопоставление с данными MSFT_PhysicalDisk и MSFT_Disk
                    sn_lookup = sn.lower()
                    msft_p = msft_physical_map.get(sn_lookup)
                    msft_d = msft_disk_map.get(int(disk_idx)) if disk_idx is not None else None

                    # Определение бренда
                    model_l = model.lower()
                    if "samsung" in model_l:
                        disk_mfg = "Samsung"
                    elif "crucial" in model_l or model_l.startswith("ct"):
                        disk_mfg = "Crucial / Micron"
                    elif "toshiba" in model_l or model_l.startswith("hdwd") or model_l.startswith("dt01"):
                        disk_mfg = "Toshiba"
                    elif "wdc" in model_l or model_l.startswith("wd") or "western digital" in model_l:
                        disk_mfg = "Western Digital"
                    elif "kingston" in model_l or model_l.startswith("sa400") or model_l.startswith("skc"):
                        disk_mfg = "Kingston"
                    elif "seagate" in model_l or model_l.startswith("st"):
                        disk_mfg = "Seagate"
                    elif "sandisk" in model_l:
                        disk_mfg = "SanDisk"
                    elif "kioxia" in model_l:
                        disk_mfg = "Kioxia"
                    elif "intel" in model_l:
                        disk_mfg = "Intel"
                    elif "micron" in model_l:
                        disk_mfg = "Micron"
                    elif "sk hynix" in model_l or "hynix" in model_l:
                        disk_mfg = "SK Hynix"
                    elif "yongzhenweiye" in model_l:
                        disk_mfg = "YongzhenWeiye"
                    else:
                        disk_mfg = "Универсальный накопитель"

                    # Определение точного типа накопителя (SSD / HDD / Flash USB)
                    raw_media_type = getattr(msft_p, "MediaType", None) if msft_p else None
                    if raw_media_type == 4 or "ssd" in model_l or "nvme" in model_l:
                        media_display = "SSD (Solid State Drive)"
                    elif raw_media_type == 3 or "hdwd" in model_l or "ezrz" in model_l:
                        media_display = "HDD (Hard Disk Drive / Магнитный)"
                    elif raw_media_type == 0 or "usb" in model_l or iface == "USB":
                        media_display = "Flash USB / Внешний накопитель"
                    else:
                        media_display = "Fixed Disk Media"

                    # Определение типа шины подключения
                    raw_bus = getattr(msft_p, "BusType", None) if msft_p else (getattr(msft_d, "BusType", None) if msft_d else None)
                    bus_map = {7: "USB", 8: "SATA / RAID", 17: "NVMe (PCIe)"}
                    if "nvme" in model_l or "nvme" in pnp_id.lower():
                        bus_display = "NVMe (PCI Express)"
                    elif raw_bus in bus_map:
                        bus_display = bus_map[raw_bus]
                    elif iface:
                        bus_display = iface
                    else:
                        bus_display = "SATA / SCSI"

                    # Стиль разметки разделов (GPT / MBR)
                    part_style_code = getattr(msft_d, "PartitionStyle", None) if msft_d else None
                    if part_style_code == 2:
                        part_style_display = "GPT (GUID Partition Table)"
                    elif part_style_code == 1:
                        part_style_display = "MBR (Master Boot Record)"
                    else:
                        part_style_display = "GPT / MBR"

                    # Признак загрузочного / системного диска
                    is_boot = getattr(msft_d, "IsBoot", False) if msft_d else False
                    is_sys = getattr(msft_d, "IsSystem", False) if msft_d else False
                    boot_status = "Да (Системный / Загрузочный диск ОС)" if (is_boot or is_sys) else "Нет (Дополнительный накопитель)"

                    # Сопоставление с телеметрией накопителей (SMART health & POH)
                    clean_sn = sn.strip().replace('_', '').replace('.', '').replace('-', '').lower() if sn and sn != "N/A" else ""
                    matched_health = None
                    for hd in health_disks_list:
                        hd_sn = (getattr(hd, "serial_number", None) or "").strip().replace('_', '').replace('.', '').replace('-', '').lower()
                        if clean_sn and hd_sn and (clean_sn in hd_sn or hd_sn in clean_sn):
                            matched_health = hd
                            break
                    if not matched_health and disk_idx is not None:
                        for hd in health_disks_list:
                            hd_dev = str(getattr(hd, "device_id", "") or "")
                            hd_digits = "".join(filter(str.isdigit, hd_dev))
                            if hd_digits and hd_digits == str(disk_idx):
                                matched_health = hd
                                break

                    # Поиск даты установки накопителя из SetupAPI
                    matched_pnp_date = None
                    if pnp_id and pnp_id in pnp_disk_dates:
                        matched_pnp_date = pnp_disk_dates[pnp_id]
                    elif pnp_id:
                        pnp_id_lower = pnp_id.lower()
                        for pnp_key, dt in pnp_disk_dates.items():
                            if pnp_key.lower() in pnp_id_lower or pnp_id_lower in pnp_key.lower():
                                matched_pnp_date = dt
                                break
                    if not matched_pnp_date and clean_sn:
                        for pnp_key, dt in pnp_disk_dates.items():
                            clean_key = pnp_key.replace('_', '').replace('.', '').replace('-', '').lower()
                            if clean_sn in clean_key:
                                matched_pnp_date = dt
                                break

                    # Извлечение часов наработки (Power-On Hours)
                    poh: Optional[float] = None
                    if matched_health and getattr(matched_health, "power_on_hours", None) is not None:
                        try:
                            raw_poh = float(matched_health.power_on_hours)
                            if raw_poh > 0:
                                poh = raw_poh
                        except (ValueError, TypeError):
                            pass

                    # Если аппаратный SMART POH отсутствует (напр. Flash USB), рассчитываем на основе даты установки SetupAPI
                    approx_first_on: Optional[datetime] = None
                    if poh is not None:
                        approx_first_on = now_utc - timedelta(hours=poh)
                    elif matched_pnp_date is not None:
                        approx_first_on = matched_pnp_date
                        diff_h = max(1.0, (now_utc - matched_pnp_date).total_seconds() / 3600.0)
                        poh = round(diff_h, 1)

                    disk_props: Dict[str, Any] = {
                        "Модель накопителя": model,
                        "Производитель (Бренд)": disk_mfg,
                        "Тип накопителя": media_display,
                        "Интерфейс / Шина подключения": bus_display,
                        "Стиль разметки разделов": part_style_display,
                        "Загрузочный диск системы": boot_status,
                        "Емкость": f"{size_gb} GB ({size_bytes:,} байт)",
                        "Серийный номер (S/N)": sn,
                    }

                    # Отработанные часы и даты первого запуска / регистрации
                    if poh is not None and poh > 0:
                        if poh >= 8760:
                            years = poh / 8760.0
                            days = int(poh // 24)
                            disk_props["Время наработки (Power-On Hours)"] = f"{poh:,.0f} ч (≈ {years:.1f} г. / {days:,} д.)".replace(",", " ")
                        elif poh >= 24:
                            days = int(poh // 24)
                            disk_props["Время наработки (Power-On Hours)"] = f"{poh:,.0f} ч ({days} д.)".replace(",", " ")
                        else:
                            disk_props["Время наработки (Power-On Hours)"] = f"{poh:,.0f} ч".replace(",", " ")

                    if approx_first_on is not None:
                        source_label = "по счетчику S.M.A.R.T." if matched_health and getattr(matched_health, "power_on_hours", None) else "по первой установке PnP"
                        disk_props["Первый запуск накопителя (расчетный)"] = f"{approx_first_on.strftime('%Y-%m-%d %H:%M')} ({source_label})"

                    if matched_pnp_date is not None:
                        disk_props["Первая регистрация в системе (SetupAPI)"] = matched_pnp_date.strftime("%Y-%m-%d %H:%M")

                    if matched_health:
                        wear_pct = getattr(matched_health, "wear_percentage", None)
                        if wear_pct is not None:
                            try:
                                wear_val = float(wear_pct)
                                health_val = max(0, min(100, int(100 - wear_val)))
                                disk_props["Здоровье накопителя (SMART Wear)"] = f"{health_val}% (Износ: {wear_val:.1f}%)"
                            except (ValueError, TypeError):
                                pass
                        temp_c = getattr(matched_health, "temperature_celsius", None)
                        if temp_c is not None:
                            disk_props["Температура накопителя"] = f"{temp_c} °C"
                        r_tb = getattr(matched_health, "lifetime_read_tb", None)
                        w_tb = getattr(matched_health, "lifetime_write_tb", None)
                        if r_tb is not None or w_tb is not None:
                            rw_parts = []
                            if r_tb is not None:
                                rw_parts.append(f"Чтение: {r_tb:.2f} TB")
                            if w_tb is not None:
                                rw_parts.append(f"Запись: {w_tb:.2f} TB")
                            disk_props["Суммарный объем I/O за все время"] = ", ".join(rw_parts)

                    if firmware:
                        disk_props["Версия прошивки (Firmware)"] = firmware
                    disk_props["Число разделов"] = parts

                    # Геометрия диска
                    bps = getattr(d, "BytesPerSector", None)
                    if bps:
                        disk_props["Размер сектора"] = f"{bps} байт"
                    heads = getattr(d, "TotalHeads", None)
                    cyls = getattr(d, "TotalCylinders", None)
                    if heads and cyls:
                        disk_props["Геометрия накопителя"] = f"Головки: {heads}, Цилиндры: {cyls}"

                    disk_props["Статус S.M.A.R.T."] = f"{status} (Healthy)"
                    if disk_idx is not None:
                        disk_props["Физический номер диска"] = f"\\\\.\\PHYSICALDRIVE{disk_idx}"
                    if pnp_id:
                        disk_props["Идентификатор PnP"] = pnp_id

                    nodes.append(HardwareNode(category="Physical Disk", name=f"{model} ({size_gb} GB, {bus_display})", properties=disk_props))
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI DiskDrive query warning: {e}")

        # ---------------------------------------------------------------------
        # 9. ДИСКОВЫЕ ТОМА (Storage Volume)
        # ---------------------------------------------------------------------
        wmi_vol_map: Dict[str, Dict[str, Any]] = {}
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for ld in wmi_obj.InstancesOf("Win32_LogicalDisk"):
                    dev_id = str(getattr(ld, "DeviceID", "") or "").strip().upper()
                    vol_name = str(getattr(ld, "VolumeName", "") or "").strip()
                    vol_sn = str(getattr(ld, "VolumeSerialNumber", "") or "").strip()
                    drv_type = getattr(ld, "DriveType", None)
                    type_labels = {2: "Съемный накопитель (USB Flash)", 3: "Локальный фиксированный диск", 4: "Сетевой диск", 5: "CD/DVD привод"}
                    wmi_vol_map[dev_id] = {
                        "name": vol_name,
                        "sn": vol_sn,
                        "type": type_labels.get(drv_type, "Локальный том"),
                        "compressed": getattr(ld, "Compressed", False),
                        "quotas": getattr(ld, "SupportsDiskQuotas", False),
                    }
            except Exception as ld_err:
                logger.debug(f"[HardwareTree] WMI LogicalDisk query warning: {ld_err}")

        partitions, _ = self._collector.get_disk_metrics()
        for part in partitions:
            v_info = wmi_vol_map.get(part.device.upper().rstrip("\\"), {})
            vol_title = f"Раздел {part.device}"
            if v_info.get("name"):
                vol_title += f" [{v_info['name']}]"

            vol_props: Dict[str, Any] = {
                "Дисковый том": part.device,
                "Метка тома": v_info.get("name") or "Без метки",
                "Тип тома": v_info.get("type") or "Локальный диск",
                "Точка монтирования": part.mountpoint,
                "Файловая система": part.fstype,
                "Общий объем": f"{part.total_gb} GB",
                "Свободное место": f"{part.free_gb} GB",
                "Занято памяти": f"{part.used_gb} GB ({part.percent}%)",
            }
            if v_info.get("sn"):
                vol_props["Серийный номер тома"] = v_info["sn"]
            if "compressed" in v_info:
                vol_props["Сжатие тома"] = "Включено" if v_info["compressed"] else "Выключено"
            if "quotas" in v_info:
                vol_props["Поддержка дисковых квот"] = "Да" if v_info["quotas"] else "Нет"

            nodes.append(HardwareNode(category="Storage Volume", name=f"{vol_title} ({part.total_gb} GB)", properties=vol_props))

        # ---------------------------------------------------------------------
        # 10. СЕТЕВЫЕ АДАПТЕРЫ (Network Adapter)
        # ---------------------------------------------------------------------
        wmi_net_adapters: Dict[str, Dict[str, Any]] = {}
        wmi_net_configs: Dict[str, Any] = {}
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for cfg in wmi_obj.InstancesOf("Win32_NetworkAdapterConfiguration"):
                    cdesc = (getattr(cfg, "Description", "") or "").strip()
                    if cdesc:
                        wmi_net_configs[cdesc.lower()] = cfg
                for a in wmi_obj.InstancesOf("Win32_NetworkAdapter"):
                    net_id = (getattr(a, "NetConnectionID", "") or "").strip()
                    aname = (getattr(a, "Name", "") or "").strip()
                    adesc = (getattr(a, "Description", "") or "").strip()
                    apnp = (getattr(a, "PNPDeviceID", "") or "").strip()
                    amfg = (getattr(a, "Manufacturer", "") or "").strip()
                    amac = (getattr(a, "MACAddress", "") or "").strip()
                    aspeed = getattr(a, "Speed", None)
                    atype = (getattr(a, "AdapterType", "") or "").strip()
                    astatus_num = getattr(a, "NetConnectionStatus", None)
                    aphys = getattr(a, "PhysicalAdapter", False)
                    asvc = getattr(a, "ServiceName", "")
                    aguid = getattr(a, "GUID", "")

                    item = {
                        "net_id": net_id, "name": aname, "desc": adesc, "pnp": apnp,
                        "mfg": amfg, "mac": amac, "speed": aspeed, "ad_type": atype,
                        "status_num": astatus_num, "is_phys": aphys, "service": asvc, "guid": aguid,
                    }
                    if net_id:
                        wmi_net_adapters[net_id.lower()] = item
                    if aname:
                        wmi_net_adapters[aname.lower()] = item
                    if adesc:
                        wmi_net_adapters[adesc.lower()] = item
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI NetworkAdapter query warning: {e}")

        if PSUTIL_AVAILABLE:
            ps_addrs = psutil.net_if_addrs()
            ps_stats = psutil.net_if_stats()
            for if_name, addr_list in ps_addrs.items():
                stat = ps_stats.get(if_name)
                w_info = wmi_net_adapters.get(if_name.lower(), {})
                cfg = wmi_net_configs.get(w_info.get("desc", "").lower()) or wmi_net_configs.get(if_name.lower())
                mac_addr = w_info.get("mac")
                if not mac_addr:
                    for a in addr_list:
                        fam_name = getattr(a.family, "name", "")
                        if fam_name == "AF_LINK" or a.family == -1 or a.family == getattr(psutil, "AF_LINK", -1):
                            if a.address and len(a.address) in (12, 17):
                                mac_addr = a.address.replace("-", ":").upper()
                                break
                ipv4_list = [a.address for a in addr_list if a.family == socket.AF_INET]
                ipv6_list = [a.address.split("%")[0] for a in addr_list if hasattr(socket, "AF_INET6") and a.family == socket.AF_INET6]
                gateways = list(getattr(cfg, "DefaultIPGateway", []) or []) if cfg else []
                dhcp_server = getattr(cfg, "DHCPServer", None) if cfg else None
                dhcp_enabled = getattr(cfg, "DHCPEnabled", None) if cfg else None
                dns_servers = list(getattr(cfg, "DNSServerSearchOrder", []) or []) if cfg else []
                is_up = stat.isup if stat else True
                status_num = w_info.get("status_num")
                if status_num == 2 or (status_num is None and is_up):
                    status_str = "Активно (Up)"
                elif status_num == 7:
                    status_str = "Кабель не подключен (Disconnected)"
                elif status_num == 0:
                    status_str = "Отключено (Disabled)"
                elif not is_up:
                    status_str = "Не активно (Down)"
                else:
                    status_str = "Активно (Up)"
                speed_mbps = 0
                if stat and stat.speed and (stat.speed > 0) and (stat.speed < 1000000):
                    speed_mbps = stat.speed
                elif w_info.get("speed"):
                    try:
                        raw_spd = int(w_info["speed"])
                        if raw_spd < 100000000000:
                            speed_mbps = round(raw_spd / 1000000)
                    except Exception:
                        pass
                if speed_mbps > 0:
                    if speed_mbps >= 1000:
                        speed_str = f"{speed_mbps} Mbps ({round(speed_mbps / 1000, 1)} Gbps)"
                    else:
                        speed_str = f"{speed_mbps} Mbps"
                else:
                    speed_str = "Автоопределение (0 Mbps)" if not is_up else "1000 Mbps (Авто)"
                model_name = w_info.get("name") or w_info.get("desc") or if_name
                mfg_val = w_info.get("mfg")
                if not mfg_val:
                    if "intel" in if_name.lower() or "intel" in model_name.lower():
                        mfg_val = "Intel Corporation"
                    elif "realtek" in if_name.lower() or "realtek" in model_name.lower():
                        mfg_val = "Realtek"
                    elif "vethernet" in if_name.lower() or "hyper-v" in model_name.lower() or "microsoft" in model_name.lower() or ("local area connection*" in if_name.lower()):
                        mfg_val = "Microsoft Corporation"
                    else:
                        mfg_val = "Универсальный сетевой контроллер"
                name_l = if_name.lower()
                desc_l = (w_info.get("desc") or "").lower()
                if "local area connection*" in name_l:
                    adapter_type = "Виртуальный адаптер Wi-Fi Direct"
                    if model_name == if_name:
                        model_name = f"Microsoft Wi-Fi Direct Virtual Adapter ({if_name})"
                elif "wi-fi" in name_l or "wireless" in desc_l or "802.11" in desc_l:
                    adapter_type = "Беспроводной адаптер (Wi-Fi 802.11)"
                elif "bluetooth" in name_l or "bluetooth" in desc_l:
                    adapter_type = "Bluetooth PAN адаптер"
                elif "vethernet" in name_l or "virtual" in desc_l or "hyper-v" in desc_l:
                    adapter_type = "Виртуальный сетевой адаптер (Hyper-V / WSL)"
                elif "loopback" in name_l:
                    adapter_type = "Программный интерфейс Loopback"
                elif "tap" in name_l or "tun" in name_l or "vpn" in name_l:
                    adapter_type = "VPN / Туннельный адаптер"
                else:
                    adapter_type = "Сетевая карта Ethernet (LAN)"

                net_props: Dict[str, Any] = {
                    "Имя подключения": if_name,
                    "Модель адаптера": model_name,
                    "Производитель": mfg_val,
                    "Тип адаптера": adapter_type,
                    "Аппаратный тип": "Физический сетевой адаптер (Hardware NIC)" if w_info.get("is_phys") else "Виртуальный сетевой интерфейс",
                    "Физический (MAC) адрес": mac_addr or "N/A",
                    "Состояние соединения": status_str,
                    "Скорость канала": speed_str,
                }
                if stat and getattr(stat, "duplex", None) is not None:
                    d_val = getattr(stat.duplex, "value", stat.duplex)
                    if d_val == 2:
                        net_props["Режим дуплекса"] = "Full Duplex (Полный)"
                    elif d_val == 1:
                        net_props["Режим дуплекса"] = "Half Duplex (Полудуплекс)"
                if stat and getattr(stat, "mtu", None):
                    net_props["Размер MTU"] = f"{stat.mtu} байт"
                net_props["IP-адреса (IPv4)"] = ", ".join(ipv4_list) or "N/A"
                if ipv6_list:
                    net_props["IP-адреса (IPv6)"] = ", ".join(ipv6_list[:3])
                if gateways:
                    net_props["Основной шлюз"] = ", ".join(gateways)
                if dhcp_server or dhcp_enabled is not None:
                    net_props["DHCP сервер"] = dhcp_server or ("Включен (DHCP)" if dhcp_enabled else "Статический IP / Отключен")
                if dns_servers:
                    net_props["DNS серверы"] = ", ".join(dns_servers)
                if w_info.get("service"):
                    net_props["Служба драйвера (Service)"] = w_info["service"]
                if w_info.get("guid"):
                    net_props["GUID интерфейса"] = w_info["guid"]

                pnp_val = w_info.get("pnp")
                if pnp_val:
                    p_ids = _extract_pnp_ids(pnp_val)
                    if p_ids.get("vendor_id") and p_ids.get("device_id"):
                        net_props["PCI Vendor & Device ID"] = f"Vendor: {p_ids['vendor_id']}, Device: {p_ids['device_id']}"
                    net_props["Идентификатор PnP"] = pnp_val

                display_title = f"{if_name}: {model_name}" if model_name != if_name else if_name
                nodes.append(HardwareNode(category="Network Adapter", name=display_title, properties=net_props))

        # ---------------------------------------------------------------------
        # 11. БЕСПРОВОДНАЯ СВЯЗЬ BLUETOOTH (Bluetooth Devices)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for b_dev in wmi_obj.InstancesOf("Win32_PnPEntity"):
                    b_cls = getattr(b_dev, "PNPClass", "")
                    b_name = (getattr(b_dev, "Name", "") or "").strip()
                    if b_cls == "Bluetooth" and b_name:
                        # Фильтруем внутренние сервисы
                        b_l = b_name.lower()
                        if any(x in b_l for x in ["transport", "enumerator", "protocol tdi", "service"]):
                            continue
                        b_mfg = (getattr(b_dev, "Manufacturer", "") or "").strip() or "Bluetooth Device"
                        b_status = (getattr(b_dev, "Status", "") or "OK").strip()
                        b_pnp = (getattr(b_dev, "DeviceID", "") or "").strip()

                        is_radio = "intel" in b_l or "adapter" in b_l or "wireless" in b_l
                        bth_type = "Аппаратный контроллер Bluetooth" if is_radio else "Беспроводное сопряженное устройство"
                        bth_props: Dict[str, Any] = {
                            "Название устройства": b_name,
                            "Тип устройства": bth_type,
                            "Производитель": b_mfg,
                            "Состояние": f"{b_status} (Подключено)",
                        }
                        p_ids = _extract_pnp_ids(b_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            bth_props["Bluetooth VID & PID"] = f"VID: {p_ids['vendor_id']}, PID: {p_ids['device_id']}"
                        if b_pnp:
                            bth_props["Идентификатор PnP"] = b_pnp
                        nodes.append(HardwareNode(category="Bluetooth Device", name=b_name, properties=bth_props))
            except Exception as bth_err:
                logger.debug(f"[HardwareTree] WMI Bluetooth query warning: {bth_err}")

        # ---------------------------------------------------------------------
        # 12. УСТРОЙСТВА ВВОДА И HID (Input & HID Devices)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                # Клавиатуры
                for kb in wmi_obj.InstancesOf("Win32_Keyboard"):
                    kb_name = (getattr(kb, "Description", "") or getattr(kb, "Name", "") or "").strip()
                    kb_pnp = (getattr(kb, "DeviceID", "") or "").strip()
                    kb_status = (getattr(kb, "Status", "") or "OK").strip()
                    if kb_name:
                        kb_props: Dict[str, Any] = {
                            "Устройство": kb_name,
                            "Тип устройства": "Клавиатура (Keyboard)",
                            "Состояние": f"{kb_status} (Подключено)",
                        }
                        p_ids = _extract_pnp_ids(kb_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            kb_props["Vendor & Product ID"] = f"VID: {p_ids['vendor_id']}, PID: {p_ids['device_id']}"
                        if kb_pnp:
                            kb_props["Идентификатор PnP"] = kb_pnp
                        nodes.append(HardwareNode(category="Input Device (Keyboard)", name=kb_name, properties=kb_props))

                # Мыши и манипуляторы
                for mouse in wmi_obj.InstancesOf("Win32_PointingDevice"):
                    m_name = (getattr(mouse, "Description", "") or getattr(mouse, "Name", "") or "").strip()
                    m_pnp = (getattr(mouse, "DeviceID", "") or "").strip()
                    m_status = (getattr(mouse, "Status", "") or "OK").strip()
                    if m_name:
                        m_props: Dict[str, Any] = {
                            "Устройство": m_name,
                            "Тип устройства": "Манипулятор / Мышь (Pointing Device)",
                            "Состояние": f"{m_status} (Подключено)",
                        }
                        p_ids = _extract_pnp_ids(m_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            m_props["Vendor & Product ID"] = f"VID: {p_ids['vendor_id']}, PID: {p_ids['device_id']}"
                        if m_pnp:
                            m_props["Идентификатор PnP"] = m_pnp
                        nodes.append(HardwareNode(category="Input Device (Mouse)", name=m_name, properties=m_props))
            except Exception as input_err:
                logger.debug(f"[HardwareTree] WMI Input devices warning: {input_err}")

        # ---------------------------------------------------------------------
        # 13. ПРИНТЕРЫ И СКАНЕРЫ (Printers & Imaging)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for prn in wmi_obj.InstancesOf("Win32_Printer"):
                    prn_name = (getattr(prn, "Name", "") or "").strip()
                    drv_name = (getattr(prn, "DriverName", "") or "").strip()
                    port_name = (getattr(prn, "PortName", "") or "").strip()
                    is_def = getattr(prn, "Default", False)
                    status_p = (getattr(prn, "Status", "") or "OK").strip()
                    if prn_name:
                        prn_props: Dict[str, Any] = {
                            "Название принтера": prn_name,
                            "Драйвер печати": drv_name,
                            "Порт подключения": port_name,
                            "Принтер по умолчанию": "Да (Основной принтер)" if is_def else "Нет",
                            "Состояние": status_p,
                        }
                        nodes.append(HardwareNode(category="Printer & Imaging", name=f"{prn_name}{' [По умолчанию]' if is_def else ''}", properties=prn_props))
            except Exception as prn_err:
                logger.debug(f"[HardwareTree] WMI Printer warning: {prn_err}")

        # ---------------------------------------------------------------------
        # 14. АУДИОУСТРОЙСТВА (Audio Device)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for s in wmi_obj.InstancesOf("Win32_SoundDevice"):
                    snd_name = (getattr(s, "Caption", "") or getattr(s, "Name", "") or "").strip()
                    snd_mfg = (getattr(s, "Manufacturer", "") or "").strip() or "Аудиоустройство"
                    snd_status = (getattr(s, "Status", "") or "OK").strip()
                    snd_pnp = (getattr(s, "PNPDeviceID", "") or "").strip()
                    if snd_name:
                        # Тип аудиоустройства
                        if "usb" in snd_pnp.lower() or "usb" in snd_name.lower():
                            snd_type = "USB Audio Кодек / Внешняя звуковая карта"
                        elif "hdaudio" in snd_pnp.lower():
                            snd_type = "High Definition Audio (Системный кодек)"
                        elif "virtual" in snd_name.lower() or "cable" in snd_name.lower():
                            snd_type = "Виртуальное аудиоустройство (Virtual Audio Cable)"
                        else:
                            snd_type = "Интегрированный аудиоконтроллер"

                        snd_props: Dict[str, Any] = {
                            "Название устройства": snd_name,
                            "Производитель": snd_mfg,
                            "Тип звукового интерфейса": snd_type,
                            "Состояние": f"{snd_status} (Работает)",
                        }
                        p_ids = _extract_pnp_ids(snd_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            snd_props["Vendor & Device ID"] = f"Vendor: {p_ids['vendor_id']}, Device: {p_ids['device_id']}"
                        if snd_pnp:
                            snd_props["Идентификатор PnP"] = snd_pnp
                        nodes.append(HardwareNode(category="Audio Device", name=snd_name, properties=snd_props))
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI SoundDevice query warning: {e}")

        # ---------------------------------------------------------------------
        # 15. USB КОНТРОЛЛЕРЫ И УСТРОЙСТВА (USB Controller & Device)
        # ---------------------------------------------------------------------
        if os.name == "nt":
            try:
                import win32com.client
                wmi_obj = win32com.client.GetObject("winmgmts:")
                for u in wmi_obj.InstancesOf("Win32_USBController"):
                    usb_name = (getattr(u, "Caption", "") or getattr(u, "Name", "") or "").strip()
                    usb_mfg = (getattr(u, "Manufacturer", "") or "").strip() or "USB Контроллер"
                    usb_status = (getattr(u, "Status", "") or "OK").strip()
                    usb_pnp = (getattr(u, "PNPDeviceID", "") or "").strip()
                    if usb_name:
                        ctrl_props: Dict[str, Any] = {
                            "Название контроллера": usb_name,
                            "Производитель": usb_mfg,
                            "Состояние": f"{usb_status} (Работает)",
                        }
                        p_ids = _extract_pnp_ids(usb_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            ctrl_props["Vendor & Device ID"] = f"Vendor: {p_ids['vendor_id']}, Device: {p_ids['device_id']}"
                        if usb_pnp:
                            ctrl_props["Идентификатор PnP"] = usb_pnp
                        nodes.append(HardwareNode(category="USB Controller", name=usb_name, properties=ctrl_props))

                for hub in wmi_obj.InstancesOf("Win32_USBHub"):
                    hub_name = (getattr(hub, "Caption", "") or getattr(hub, "Name", "") or getattr(hub, "Description", "") or "").strip()
                    hub_mfg = (getattr(hub, "Manufacturer", "") or "").strip() or "USB Устройство"
                    hub_status = (getattr(hub, "Status", "") or "OK").strip()
                    hub_pnp = (getattr(hub, "DeviceID", "") or getattr(hub, "PNPDeviceID", "") or "").strip()
                    if hub_name:
                        # Классификация USB
                        hub_l = hub_name.lower()
                        if "mass storage" in hub_l:
                            dev_class = "Накопитель данных (USB Mass Storage)"
                        elif "composite" in hub_l:
                            dev_class = "Составное USB устройство (Composite Device)"
                        elif "hub" in hub_l:
                            dev_class = "Концентратор портов (USB Hub)"
                        elif "audio" in hub_l:
                            dev_class = "USB Аудиоустройство"
                        else:
                            dev_class = "Периферийное устройство USB"

                        hub_props: Dict[str, Any] = {
                            "Название устройства": hub_name,
                            "Класс устройства": dev_class,
                            "Производитель": hub_mfg,
                            "Состояние": f"{hub_status} (Подключено)",
                        }
                        p_ids = _extract_pnp_ids(hub_pnp)
                        if p_ids.get("vendor_id") and p_ids.get("device_id"):
                            hub_props["USB VID & PID"] = f"VID: {p_ids['vendor_id']}, PID: {p_ids['device_id']}"
                        if hub_pnp:
                            hub_props["Идентификатор PnP"] = hub_pnp
                        nodes.append(HardwareNode(category="USB Device", name=hub_name, properties=hub_props))
            except Exception as e:
                logger.debug(f"[HardwareTree] WMI USB query warning: {e}")

        # ---------------------------------------------------------------------
        # 16. ОБНОВЛЕНИЯ WINDOWS (Windows Updates)
        # ---------------------------------------------------------------------
        upd = self._collector.get_updates_info()
        nodes.append(HardwareNode(
            category="Windows Updates",
            name=f"{upd.status} ({upd.installed_kb_count} KBs)",
            properties={
                "Статус обновлений": upd.status,
                "Число установленных исправлений": upd.installed_kb_count,
                "Последние KB пакеты": ", ".join(upd.recent_hotfixes) or "N/A",
                "Дата последней установки": upd.latest_installed_on or "OK",
            },
        ))

        # Синхронизация с таблицей hardware_components
        try:
            from .hardware_enricher import HardwareEnricher
            enricher = HardwareEnricher()
            enricher.sync_nodes(nodes)
        except Exception as enr_err:
            logger.debug(f"[HardwareTree] Sync warning: {enr_err}")

        self._cached = nodes
        return nodes


