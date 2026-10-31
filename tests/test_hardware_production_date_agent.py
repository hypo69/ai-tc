# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Test Hardware Production Date Agent
# =============================================================================
# Description:
#   Модульные тесты для специализированного агента декодирования даты производства
#   аппаратных компонентов (HardwareProductionDateAgent).
#
# File: test_hardware_production_date_agent.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 16:01:00
# =============================================================================

from __future__ import annotations
"""Тесты агента декодирования дат производства оборудования по серийным номерам."""

import pytest
from apps.windows.telemetry.production_date_agent import HardwareProductionDateAgent, clean_serial


def test_clean_serial_sanitization() -> None:
    """Проверка отсечения фиктивных и невалидных серийных номеров."""
    assert clean_serial("") == ""
    assert clean_serial("None") == ""
    assert clean_serial("N/A") == ""
    assert clean_serial("00000000") == ""
    assert clean_serial("Default string") == ""
    assert clean_serial("To Be Filled By O.E.M.") == ""
    assert clean_serial("ab") == ""
    assert clean_serial("  SN12345678  ") == "SN12345678"


def test_decode_asus_serial() -> None:
    """Проверка декодирования серийного номера ASUS (год и месяц)."""
    agent = HardwareProductionDateAgent()

    # N8... -> 2022 год, 8 месяц (Август)
    res = agent.decode_serial(vendor="ASUS", serial_number="N8M0KC000000000")
    assert res is not None
    assert res["production_date"] == "2022-08"
    assert "ASUS Serial Decoder" in res["production_source"]
    assert res["confidence"] == "high"

    # M1... -> 2021 год, 1 месяц (Январь)
    res_jan = agent.decode_serial(vendor="ASUSTeK", serial_number="M1M0KC123456")
    assert res_jan is not None
    assert res_jan["production_date"] == "2021-01"

    # PA... -> 2023 год, 10 месяц (Октябрь, A=10)
    res_oct = agent.decode_serial(vendor="ASUS", serial_number="PAM0KC999999")
    assert res_oct is not None
    assert res_oct["production_date"] == "2023-10"


def test_decode_gigabyte_serial() -> None:
    """Проверка декодирования серийного номера GIGABYTE (SNyyww)."""
    agent = HardwareProductionDateAgent()

    # SN2142000000 -> 2021 год, 42 неделя
    res = agent.decode_serial(vendor="GIGABYTE", serial_number="SN214201234567")
    assert res is not None
    assert res["production_date"] == "2021-W42"
    assert "GIGABYTE Serial Decoder" in res["production_source"]
    assert res["confidence"] == "high"


def test_decode_msi_serial() -> None:
    """Проверка декодирования серийного номера MSI."""
    agent = HardwareProductionDateAgent()

    # 601-7B86-010B1911000000 -> 2019 год, 11 месяц
    res = agent.decode_serial(vendor="MSI", serial_number="601-7B86-010B1911000000")
    assert res is not None
    assert res["production_date"] == "2019-11"
    assert "MSI Serial Decoder" in res["production_source"]


def test_decode_dell_ppid_and_servicetag() -> None:
    """Проверка декодирования Dell PPID и Service Tag."""
    agent = HardwareProductionDateAgent()

    # PPID: CN-012345-67890-1A2-0000 (1=2021, A=Октябрь, 2=2 число)
    ppid = "CN-0ABCDE-12345-1A2-0001"
    res_ppid = agent.decode_serial(vendor="Dell", serial_number=ppid)
    assert res_ppid is not None
    assert res_ppid["production_date"] == "2021-10"
    assert "Dell PPID" in res_ppid["production_source"]

    # 7-значный Service Tag
    res_st = agent.decode_serial(vendor="Dell", serial_number="8XYZ123")
    assert res_st is not None
    assert "8XYZ123" in res_st["production_date"]
    assert "dell.com/support" in res_st["production_source"]


def test_decode_hp_serial() -> None:
    """Проверка декодирования 10-значного серийного номера HP."""
    agent = HardwareProductionDateAgent()

    # 4-й символ = 1 (2021), 5-6 = 45 (неделя)
    sn_hp = "CNU1450000"
    res = agent.decode_serial(vendor="HP", serial_number=sn_hp)
    assert res is not None
    assert res["production_date"] == "2021-W45"
    assert "HP Serial Number Decoder" in res["production_source"]


def test_decode_edid_and_spd() -> None:
    """Проверка считывания фабричных дат монитора из EDID и памяти из SPD."""
    agent = HardwareProductionDateAgent()

    # Монитор с полями EDID
    mon_props = {
        "Название дисплея (EDID)": "Dell U2720Q",
        "Год выпуска (EDID)": 2021,
        "Неделя выпуска (EDID)": 36,
    }
    res_mon = agent.decode_serial(vendor="Dell", properties=mon_props, category="Monitors & Displays")
    assert res_mon is not None
    assert res_mon["production_date"] == "2021-W36"
    assert "EDID Hardware ROM" in res_mon["production_source"]

    # Модуль RAM с датой SPD
    ram_props = {
        "Производитель": "Kingston",
        "Дата выпуска модуля (SPD)": "2020-W48",
    }
    res_ram = agent.decode_serial(vendor="Kingston", properties=ram_props, category="Memory Module (RAM)")
    assert res_ram is not None
    assert res_ram["production_date"] == "2020-W48"
    assert "SPD" in res_ram["production_source"]

