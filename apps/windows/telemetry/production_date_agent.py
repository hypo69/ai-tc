# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Hardware Production Date Agent
# =============================================================================
# Description:
#   Специализированный агент и алгоритмический декодер для определения даты
#   производства аппаратных компонентов по их серийному номеру (Serial Number),
#   парт-номеру (P/N), модели и вендору.
#
#   Поддерживает мгновенный алгоритмический анализ для популярных вендоров
#   (ASUS, Gigabyte, MSI, ASRock, Dell, HP, Lenovo, Samsung, Seagate, WD, Intel, AMD, EDID, SPD)
#   с интеллектуальным AI-fallback через GoogleGenerativeAI для сложных случаев.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.production_date_agent import HardwareProductionDateAgent
#
#     agent = HardwareProductionDateAgent()
#     res = agent.decode_serial(vendor="ASUS", serial_number="M80M00000000")
#     print(res)  # {'production_date': '2021-08', 'source': 'ASUS Serial Decoder', ...}
#
# File: production_date_agent.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 15:55:00
# =============================================================================

from __future__ import annotations
"""Специализированный агент определения даты производства оборудования по серийному номеру."""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from logger import logger

# Невалидные/фиктивные значения серийных номеров WMI/SMBIOS
INVALID_SERIALS = {
    "", "none", "n/a", "null", "unknown", "0", "00000000", "000000000000",
    "default string", "to be filled by o.e.m.", "to be filled by oem",
    "system serial number", "chassis serial number", "base board serial number",
    "123456789", "not applicable", "undefined",
}


def clean_serial(serial: Optional[str]) -> str:
    """Очищает и нормализует строку серийного номера.

    Args:
        serial: Исходная строка серийного номера.

    Returns:
        str: Очищенный серийный номер в верхнем регистре или пустая строка при невалидности.
    """
    if not serial or not isinstance(serial, str):
        return ""
    s = serial.strip()
    if s.lower() in INVALID_SERIALS or len(s) < 3:
        return ""
    return s


class HardwareProductionDateAgent:
    """Агент анализа и декодирования даты производства аппаратных компонентов."""

    def __init__(self) -> None:
        """Инициализирует агента даты производства."""
        pass

    def decode_serial(
        self,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        serial_number: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Алгоритмически декодирует дату выпуска по серийному номеру и характеристикам устройства.

        Args:
            vendor: Производитель оборудования (ASUS, GIGABYTE, Dell и т.д.).
            model: Модель устройства.
            serial_number: Серийный номер компонента.
            properties: Словарь собранных параметров компонента.
            category: Категория оборудования.

        Returns:
            Optional[Dict[str, Any]]: Словарь с датой, источником и уверенностью, либо None.
        """
        props = properties or {}
        sn = clean_serial(
            serial_number
            or props.get("Серийный номер (S/N)")
            or props.get("Серийный номер")
            or props.get("Serial Number")
            or props.get("Серийный номер платы")
            or props.get("Серийный номер накопителя")
            or props.get("Серийный номер BIOS (Tag)")
            or props.get("Серийный номер дисплея (EDID)")
        )

        v_clean = (vendor or props.get("Производитель") or props.get("Производитель платы") or "").strip().upper()
        m_clean = (model or props.get("Модель") or props.get("Модель платы") or "").strip().upper()
        cat_clean = (category or "").strip().lower()

        # 1. Проверка прямых дат в свойствах (EDID для мониторов, BIOS date, SPD для RAM)
        edid_date = self._decode_edid_date(props)
        if edid_date:
            return edid_date

        spd_date = self._decode_spd_date(props)
        if spd_date:
            return spd_date

        if not sn:
            return None

        # 2. ASUS (Материнские платы, видеокарты, ноутбуки)
        if "ASUS" in v_clean or "ASUSTEK" in v_clean:
            res = self._decode_asus(sn)
            if res:
                return res

        # 3. GIGABYTE (Материнские платы, видеокарты)
        if "GIGABYTE" in v_clean or sn.startswith("SN2") or sn.startswith("SN1"):
            res = self._decode_gigabyte(sn)
            if res:
                return res

        # 4. MSI (Micro-Star International)
        if "MSI" in v_clean or "MICRO-STAR" in v_clean or "601-" in sn:
            res = self._decode_msi(sn)
            if res:
                return res

        # 5. DELL (Service Tag или PPID)
        if "DELL" in v_clean or re.match(r"^[A-Z]{2}-0[A-Z0-9]{5}-", sn):
            res = self._decode_dell(sn)
            if res:
                return res

        # 6. HP / Hewlett-Packard / HPE
        if "HP" in v_clean or "HEWLETT" in v_clean:
            res = self._decode_hp(sn)
            if res:
                return res

        # 7. SAMSUNG (SSD, Память, Мониторы)
        if "SAMSUNG" in v_clean:
            res = self._decode_samsung(sn)
            if res:
                return res

        # 8. SEAGATE (Накопители HDD / SSD)
        if "SEAGATE" in v_clean or "storage" in cat_clean or "disk" in cat_clean:
            res = self._decode_seagate(sn, props)
            if res:
                return res

        # 9. WESTERN DIGITAL (WD)
        if "WESTERN DIGITAL" in v_clean or "WDC" in v_clean:
            res = self._decode_wd(sn, props)
            if res:
                return res

        # 10. LENOVO (ПК, ThinkPad, ThinkStation)
        if "LENOVO" in v_clean or "THINKPAD" in m_clean:
            res = self._decode_lenovo(sn)
            if res:
                return res

        # 11. INTEL (Процессоры, SSD)
        if "INTEL" in v_clean and ("cpu" in cat_clean or "processor" in cat_clean):
            res = self._decode_intel_fpo(sn, props)
            if res:
                return res

        # 12. Универсальная попытка декодирования паттернов SNyyww
        generic_res = self._decode_generic_patterns(sn)
        if generic_res:
            return generic_res

        return None

    def _decode_asus(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер серийных номеров ASUS.

        1-й символ = Год: C=2012, D=2013, E=2014, F=2015, G=2016, H=2017, J=2018,
                          K=2019, L=2020, M=2021, N=2022, P=2023, R=2024, S=2025, T=2026.
        2-й символ = Месяц: 1-9 = Jan-Sep, A=Oct, B=Nov, C=Dec.
        """
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()
        if len(clean) < 10:
            return None

        year_map = {
            "C": 2012, "D": 2013, "E": 2014, "F": 2015, "G": 2016, "H": 2017,
            "J": 2018, "K": 2019, "L": 2020, "M": 2021, "N": 2022, "P": 2023,
            "R": 2024, "S": 2025, "T": 2026, "V": 2027, "W": 2028,
        }
        month_map = {
            "1": "01", "2": "02", "3": "03", "4": "04", "5": "05", "6": "06",
            "7": "07", "8": "08", "9": "09", "A": "10", "B": "11", "C": "12",
        }

        y_code = clean[0]
        m_code = clean[1]

        if y_code in year_map and m_code in month_map:
            year = year_map[y_code]
            month = month_map[m_code]
            return {
                "production_date": f"{year}-{month}",
                "production_source": f"ASUS Serial Decoder ({y_code}{m_code}...)",
                "confidence": "high",
                "details": f"Символ '{y_code}' = {year} год, символ '{m_code}' = месяц {month}.",
            }
        return None

    def _decode_gigabyte(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер серийных номеров GIGABYTE.

        Формат: SNyyWWxxxxxx (например: SN2142... -> 2021 год, 42-я неделя).
        """
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()
        match = re.search(r"(?:SN)?(1[5-9]|2[0-9])([0-5][0-9])\d{5,}", clean)
        if match:
            yy = int(match.group(1))
            ww = int(match.group(2))
            if 1 <= ww <= 53:
                year = 2000 + yy
                return {
                    "production_date": f"{year}-W{ww:02d}",
                    "production_source": f"GIGABYTE Serial Decoder (SN{yy}{ww:02d}...)",
                    "confidence": "high",
                    "details": f"{year} год, {ww}-я производственная неделя.",
                }
        return None

    def _decode_msi(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер серийных номеров MSI.

        Формат: 601-xxxx-xxxByyMMxxxxxx или ...KyyWWxxxxxx.
        """
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()
        # Поиск паттерна B + yy + MM (год и месяц)
        m_bym = re.search(r"B(1[5-9]|2[0-9])(0[1-9]|1[0-2])\d{4,}", clean)
        if m_bym:
            year = 2000 + int(m_bym.group(1))
            month = m_bym.group(2)
            return {
                "production_date": f"{year}-{month}",
                "production_source": f"MSI Serial Decoder (B{m_bym.group(1)}{month}...)",
                "confidence": "high",
                "details": f"{year} год, {month}-й месяц.",
            }

        # Поиск паттерна K + yy + WW (год и неделя)
        m_kww = re.search(r"K(1[5-9]|2[0-9])([0-5][0-9])\d{4,}", clean)
        if m_kww:
            year = 2000 + int(m_kww.group(1))
            week = int(m_kww.group(2))
            if 1 <= week <= 53:
                return {
                    "production_date": f"{year}-W{week:02d}",
                    "production_source": f"MSI Serial Decoder (K{m_kww.group(1)}{week:02d}...)",
                    "confidence": "high",
                    "details": f"{year} год, {week}-я неделя.",
                }
        return None

    def _decode_dell(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер серийных номеров и PPID Dell.

        PPID формат: CN-0XXXXX-XXXXX-YMD-XXXX.
        Service Tag: 7-значный код (например 8XYZ123) с формированием ссылки на портал поддержки.
        """
        clean = sn.strip().upper()
        # Проверка 20-23 значного Dell PPID
        ppid_match = re.search(r"[A-Z]{2}-0[A-Z0-9]{5}-[A-Z0-9]{5}-([0-9])([1-9A-C])([1-9A-V])", clean)
        if ppid_match:
            y_char = ppid_match.group(1)
            m_char = ppid_match.group(2)
            d_char = ppid_match.group(3)

            # Год (0-9 -> 2020 или 2010 в зависимости от текущей декады)
            cur_year = datetime.now().year
            last_digit = int(y_char)
            # Если 0, 1, 2, ... то 2020, 2021, 2022...
            year = 2020 + last_digit if last_digit <= (cur_year % 10 + 2) else 2010 + last_digit

            month_map = {"1": "01", "2": "02", "3": "03", "4": "04", "5": "05", "6": "06",
                         "7": "07", "8": "08", "9": "09", "A": "10", "B": "11", "C": "12"}
            month = month_map.get(m_char, "01")
            return {
                "production_date": f"{year}-{month}",
                "production_source": f"Dell PPID Date Decoder ({y_char}{m_char}{d_char})",
                "confidence": "high",
                "details": f"Декодировано из заводского Dell PPID: {year} год, {month} месяц.",
            }

        # 7-символьный Service Tag Dell
        if len(clean) == 7 and re.match(r"^[A-Z0-9]{7}$", clean):
            return {
                "production_date": f"Service Tag: {clean}",
                "production_source": f"Dell Warranty Portal (https://www.dell.com/support/home/product-support/servicetag/{clean}/overview)",
                "confidence": "medium",
                "details": f"Dell Service Tag '{clean}'. Точная дата отгрузки (Ship Date) доступна на портале Dell Support.",
            }
        return None

    def _decode_hp(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер 10-значных серийных номеров HP / Compaq.

        4-й символ = Год (последняя цифра), 5-й и 6-й символы = Неделя года (01-52).
        """
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()
        if len(clean) == 10:
            y_char = clean[3]
            ww_str = clean[4:6]
            if y_char.isdigit() and ww_str.isdigit():
                ww = int(ww_str)
                if 1 <= ww <= 53:
                    y_digit = int(y_char)
                    cur_year = datetime.now().year
                    year = 2020 + y_digit if y_digit <= (cur_year % 10 + 2) else 2010 + y_digit
                    return {
                        "production_date": f"{year}-W{ww:02d}",
                        "production_source": f"HP Serial Number Decoder ({clean})",
                        "confidence": "high",
                        "details": f"Символ года '{y_char}' -> {year}, недели '{ww_str}' -> {ww}-я производственная неделя.",
                    }
        return None

    def _decode_samsung(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер 15-значных серийных номеров Samsung (SSD / Память).

        В серийниках Samsung 4-й или 5-й символ кодирует год, а следующий — месяц.
        Года: J=2017, K=2018, M=2019, N=2020, R=2021, T=2022, W=2023, X=2024, Y=2025.
        Месяцы: 1..9 = Jan..Sep, A=Oct, B=Nov, C=Dec.
        """
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()
        year_codes = {
            "H": 2016, "J": 2017, "K": 2018, "M": 2019, "N": 2020,
            "R": 2021, "T": 2022, "W": 2023, "X": 2024, "Y": 2025,
        }
        month_codes = {
            "1": "01", "2": "02", "3": "03", "4": "04", "5": "05", "6": "06",
            "7": "07", "8": "08", "9": "09", "A": "10", "B": "11", "C": "12",
        }

        # Проверяем позиции 3-4 (0-indexed) или 4-5
        for pos in (3, 4):
            if len(clean) > pos + 1:
                yc = clean[pos]
                mc = clean[pos + 1]
                if yc in year_codes and mc in month_codes:
                    year = year_codes[yc]
                    month = month_codes[mc]
                    return {
                        "production_date": f"{year}-{month}",
                        "production_source": f"Samsung Serial Decoder (Позиция {pos + 1}: {yc}{mc})",
                        "confidence": "high",
                        "details": f"Символ '{yc}' = {year} год, символ '{mc}' = {month} месяц.",
                    }
        return None

    def _decode_seagate(self, sn: str, props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Декодер даты накопителей Seagate по Date Code (YYWD / YYWWD)."""
        date_code = str(props.get("Date Code") or props.get("Код даты") or "").strip()
        if not date_code and len(sn) == 5 and sn.isdigit():
            date_code = sn

        if date_code and date_code.isdigit() and len(date_code) in (4, 5):
            yy = int(date_code[:2])
            ww = int(date_code[2:4]) if len(date_code) == 5 else int(date_code[2:3])
            # Фискальный год Seagate начинается в июле предшествующего года
            cal_year = 2000 + yy - 1
            return {
                "production_date": f"{cal_year}-W{ww:02d}",
                "production_source": f"Seagate Date Code Decoder ({date_code})",
                "confidence": "high",
                "details": f"Фискальный код Seagate {date_code}: {cal_year} год, {ww}-я неделя.",
            }
        return None

    def _decode_wd(self, sn: str, props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Декодер накопителей Western Digital (WD)."""
        dom = str(props.get("DOM") or props.get("Date of Manufacture") or props.get("Дата производства") or "").strip()
        if dom and re.match(r"^\d{4}[-/.]\d{2}", dom):
            clean_dom = re.sub(r"[-/.]", "-", dom)[:7]
            return {
                "production_date": clean_dom,
                "production_source": "Western Digital DOM Label",
                "confidence": "high",
                "details": f"Дата указана на этикетке накопителя: {clean_dom}",
            }
        return None

    def _decode_lenovo(self, sn: str) -> Optional[Dict[str, Any]]:
        """Декодер Lenovo по серийному номеру с формированием ссылки на гарантийный портал."""
        clean = sn.strip().upper()
        if 7 <= len(clean) <= 10 and re.match(r"^[A-Z0-9]+$", clean):
            return {
                "production_date": f"Lenovo SN: {clean}",
                "production_source": f"Lenovo Support (https://pcsupport.lenovo.com/products/{clean})",
                "confidence": "medium",
                "details": f"Серийный номер Lenovo '{clean}'. Гарантия и дата выпуска проверяются на портале поддержки Lenovo.",
            }
        return None

    def _decode_intel_fpo(self, sn: str, props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Декодер Intel FPO (Batch Number) процессоров.

        1-я цифра = Год выпуска (последняя цифра), 2-3 цифры = Неделя выпуска.
        """
        fpo = str(props.get("FPO") or props.get("Batch Number") or props.get("Номер партии") or sn).strip().upper()
        fpo_clean = re.sub(r"[^A-Z0-9]", "", fpo)
        match = re.search(r"^[A-Z]?([0-9])([0-5][0-9])[A-Z0-9]+", fpo_clean)
        if match:
            y_digit = int(match.group(1))
            ww = int(match.group(2))
            if 1 <= ww <= 53:
                cur_year = datetime.now().year
                year = 2020 + y_digit if y_digit <= (cur_year % 10 + 2) else 2010 + y_digit
                return {
                    "production_date": f"{year}-W{ww:02d}",
                    "production_source": f"Intel FPO Batch Decoder ({fpo})",
                    "confidence": "high",
                    "details": f"Партия Intel FPO: {year} год, {ww}-я производственная неделя.",
                }
        return None

    def _decode_edid_date(self, props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Извлекает дату выпуска монитора из стандартных полей EDID."""
        year = props.get("Год выпуска (EDID)") or props.get("Year of Manufacture") or props.get("EDID Year")
        week = props.get("Неделя выпуска (EDID)") or props.get("Week of Manufacture") or props.get("EDID Week")

        if year and str(year).isdigit():
            y_int = int(year)
            if 1995 <= y_int <= datetime.now().year + 1:
                if week and str(week).isdigit() and 1 <= int(week) <= 53:
                    w_int = int(week)
                    return {
                        "production_date": f"{y_int}-W{w_int:02d}",
                        "production_source": f"EDID Hardware ROM (Неделя {w_int}, {y_int} год)",
                        "confidence": "high",
                        "details": f"Считано из фабричного энергонезависимого блока EDID монитора.",
                    }
                return {
                    "production_date": f"{y_int}",
                    "production_source": f"EDID Hardware ROM ({y_int} год)",
                    "confidence": "high",
                    "details": f"Считано из фабричного блока EDID монитора.",
                }
        return None

    def _decode_spd_date(self, props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Извлекает дату выпуска модуля оперативной памяти RAM из SPD / WMI."""
        m_date = props.get("Дата выпуска модуля (SPD)") or props.get("ManufactureDate")
        if m_date:
            m_str = str(m_date).strip()
            # Формат 2021-W42, 2021-42, 2021/42 или 2021W42
            match = re.search(r"(20[12][0-9])[-/. _]*(?:[Ww])?([0-5][0-9])", m_str)
            if match:
                y = match.group(1)
                w = match.group(2)
                return {
                    "production_date": f"{y}-W{w}",
                    "production_source": "SPD JEDEC EEPROM (Win32_PhysicalMemory)",
                    "confidence": "high",
                    "details": f"Записано в микросхеме SPD планки памяти при производстве.",
                }
        return None

    def _decode_generic_patterns(self, sn: str) -> Optional[Dict[str, Any]]:
        """Универсальный поиск шаблонов даты в серийном номере (SN2021W42, 2145..., etc.)."""
        clean = re.sub(r"[^A-Za-z0-9]", "", sn).upper()

        # Шаблон SN + 4 цифры года + 2 цифры месяца или недели
        m_long = re.search(r"(?:SN)?(20[12][0-9])(0[1-9]|1[0-2])\d{4,}", clean)
        if m_long:
            year = m_long.group(1)
            month = m_long.group(2)
            return {
                "production_date": f"{year}-{month}",
                "production_source": f"Generic Serial Date Pattern ({year}-{month})",
                "confidence": "medium",
                "details": f"Выявлен стандартный паттерн даты в серийном номере: {year} год, {month} месяц.",
            }
        return None

    async def resolve_production_date_async(
        self,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        serial_number: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """Определяет дату выпуска компонента: сначала алгоритмически, затем через AI-fallback.

        Args:
            vendor: Производитель оборудования.
            model: Модель компонента.
            serial_number: Серийный номер.
            properties: Словарь собранных параметров.
            category: Категория компонента.
            use_ai: Разрешать ли обращение к GoogleGenerativeAI при неудаче декодеров.

        Returns:
            Dict[str, Any]: Словарь с результатом ('production_date', 'production_source', 'confidence', 'details').
        """
        # 1. Алгоритмический декодер
        rule_res = self.decode_serial(
            vendor=vendor,
            model=model,
            serial_number=serial_number,
            properties=properties,
            category=category,
        )
        if rule_res and rule_res.get("confidence") == "high":
            return rule_res

        # Если уверенность medium или нет результата, но use_ai выключен — возвращаем что есть
        if not use_ai:
            return rule_res or {
                "production_date": "N/A",
                "production_source": "Не определено",
                "confidence": "none",
                "details": "Серийный номер не соответствует известным алгоритмическим шаблонам вендоров.",
            }

        # 2. Интеллектуальный AI-агент через GoogleGenerativeAI
        sn_clean = clean_serial(serial_number or (properties or {}).get("Серийный номер (S/N)"))
        if not sn_clean:
            return rule_res or {
                "production_date": "N/A",
                "production_source": "Серийный номер отсутствует",
                "confidence": "none",
                "details": "Аппаратный компонент не предоставил валидного серийного номера.",
            }

        try:
            from src.ai.gemini.generative_ai import GoogleGenerativeAI
            ai = GoogleGenerativeAI()

            prompt = (
                f"Ты эксперт-исследователь аппаратного обеспечения компьютеров и алгоритмов кодирования серийных номеров вендоров.\n"
                f"Твоя задача: по предоставленным данным определить дату производства (Manufacture Date / Production Date / Date Code) аппаратного компонента.\n\n"
                f"Данные компонента:\n"
                f"- Категория: {category or 'Hardware'}\n"
                f"- Производитель (Вендор): {vendor or 'Unknown'}\n"
                f"- Модель: {model or 'Unknown'}\n"
                f"- Серийный номер (S/N): {sn_clean}\n"
                f"- Дополнительные свойства: {json.dumps(properties or {}, ensure_ascii=False)[:600]}\n\n"
                f"Инструкция:\n"
                f"1. Внимательно проанализируй структуру серийного номера (префикс, контрольные символы, позиции даты вендора).\n"
                f"2. Если структура серийного номера кодирует год/неделю или год/месяц (как у ASUS, Gigabyte, MSI, Samsung, Seagate, HP, Dell и др.), вычисли дату.\n"
                f"3. Если дату невозможно определить гарантированно, укажи приблизительный период выпуска модели или 'N/A'.\n\n"
                f"Верни СТРОГО валидный JSON следующего формата:\n"
                f'{{\n'
                f'  "production_date": "YYYY-MM" или "YYYY-Www" или "YYYY" (или "N/A"),\n'
                f'  "production_source": "Краткое название источника / правила вендора",\n'
                f'  "confidence": "high" или "medium" или "low",\n'
                f'  "details": "Пояснение: какие именно символы серийного номера или документация указывают на эту дату"\n'
                f'}}\n'
            )

            logger.console(f"[ProductionDateAgent] Запрос к AI модели для '{vendor} {model}' (S/N: {sn_clean})...")
            raw_res = await ai.ask(prompt)
            logger.console(f"[ProductionDateAgent] Ответ AI модели:\n{raw_res}")

            if raw_res:
                text_clean = str(raw_res).strip()
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_clean, re.DOTALL)
                parsed: Dict[str, Any] = {}
                if json_match:
                    parsed = json.loads(json_match.group(1))
                elif "{" in text_clean and "}" in text_clean:
                    start = text_clean.find("{")
                    end = text_clean.rfind("}") + 1
                    parsed = json.loads(text_clean[start:end])

                if parsed and parsed.get("production_date") and parsed["production_date"] != "N/A":
                    return {
                        "production_date": str(parsed["production_date"]).strip(),
                        "production_source": str(parsed.get("production_source") or "AI Hardware Serial Agent").strip(),
                        "confidence": str(parsed.get("confidence") or "medium").strip(),
                        "details": str(parsed.get("details") or "").strip(),
                    }
        except Exception as ai_err:
            logger.console(f"[ProductionDateAgent] Ошибка AI-опроса для S/N {sn_clean}: {ai_err}")

        # Fallback на rule_res, если AI не дал ответа
        return rule_res or {
            "production_date": "N/A",
            "production_source": "Не определено",
            "confidence": "none",
            "details": "Не удалось определить дату производства по серийному номеру.",
        }

