# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Convertors Money Module
# =============================================================================
# Description:
#   Конвертер денежных величин и финансовых значений:
#   - Безопасное преобразование строковых и числовых представлений в Decimal.
#   - Конвертация между базовыми единицами (рубли, доллары и т.д.) и неделимыми
#     минимальными единицами (копейки, центы, сатоши в int) для защиты от
#     погрешностей двоичных чисел с плавающей точкой (IEEE 754 / float).
#   - Нормализация валютных строк (очистка символов валют, пробелов, учет
#     американского и европейского форматов разделителей).
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.money import (
#         money2decimal,
#         money2minor,
#         minor2decimal,
#     )
#
#     dec = money2decimal("$1,250.50")       # Decimal('1250.50')
#     minor = money2minor(dec)               # 125050
#     dec2 = minor2decimal(minor)            # Decimal('1250.50')
#
# File: money.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:25:30
# =============================================================================

from __future__ import annotations
"""Модуль конвертации денежных величин в тип Decimal и неделимые целочисленные единицы."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Union


def money2decimal(val: Union[str, int, float, Decimal], precision: int = 2) -> Decimal:
    """Преобразует строковое или числовое денежное значение в Decimal с квантованием.

    Очищает строку от пробелов, кавычек, символов валют ($ € ₽ £ ₪ ¥ 元 ₹)
    и корректно обрабатывает десятичные разделители (запятая/точка, европейский
    и американский форматы).

    Args:
        val: Входное денежное значение (строка, целое число, Decimal или float).
        precision: Количество знаков после запятой (по умолчанию 2).

    Returns:
        Decimal: Точное денежное значение с округлением ROUND_HALF_UP.

    Raises:
        ValueError: Если строку невозможно распознать как корректную денежную сумму.
        TypeError: При передаче неподдерживаемого типа (например, bool или None).
    """
    if val is None:
        raise ValueError("Денежное значение не может быть None")

    if isinstance(val, bool):
        raise TypeError("Логический тип (bool) недопустим для денежных величин")

    if isinstance(val, (int, Decimal)):
        clean_str = str(val)
    elif isinstance(val, float):
        clean_str = str(val)
    elif isinstance(val, str):
        s = val.strip()
        if not s:
            raise ValueError("Пустая строка не является денежным значением")
        # Удаляем валютные символы, кавычки и любые типы пробельных символов
        s = re.sub(r"[\s\$\€\₽\£\₪\¥\元\₹]", "", s)
        # Обработка разделителей тысяч и десятичных долей:
        # 1. Формат "1,250.50" -> "1250.50"
        # 2. Формат "1.250,50" -> "1250.50"
        # 3. Формат "1250,50" -> "1250.50"
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                # Европейский формат: 1.250,50
                s = s.replace(".", "").replace(",", ".")
            else:
                # Американский формат: 1,250.50
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        clean_str = s
    else:
        raise TypeError(f"Неподдерживаемый тип денежной величины: {type(val)}")

    try:
        dec = Decimal(clean_str)
        if not dec.is_finite():
            raise ValueError(f"Неконечное денежное значение недопустимо: '{val}'")
        quantum = Decimal("10") ** -precision
        return dec.quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Невозможно преобразовать '{val}' в Decimal: {exc}") from exc


def money2minor(
    val: Union[str, int, float, Decimal],
    minor_units_per_major: int = 100,
) -> int:
    """Конвертирует денежную сумму в минимальные неделимые единицы (копейки, центы, сатоши).

    Args:
        val: Денежное значение (строка, Decimal, целое число, float).
        minor_units_per_major: Количество неделимых единиц в одной базовой (100 для копеек/центов).

    Returns:
        int: Целочисленная сумма в минимальных неделимых единицах.
    """
    dec = val if isinstance(val, Decimal) else money2decimal(val)
    scaled = dec * Decimal(minor_units_per_major)
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


def minor2decimal(
    minor_val: int,
    minor_units_per_major: int = 100,
) -> Decimal:
    """Конвертирует неделимые единицы (копейки, центы) обратно в Decimal.

    Args:
        minor_val: Целочисленное значение в неделимых единицах.
        minor_units_per_major: Количество неделимых единиц в одной базовой (100).

    Returns:
        Decimal: Десятичная сумма Decimal с точностью до 2 знаков.

    Raises:
        TypeError: Если передан не целочисленный тип.
    """
    if not isinstance(minor_val, (int, Decimal)) or isinstance(minor_val, bool):
        raise TypeError(f"minor_val должен быть int, получено: {type(minor_val)}")
    dec = Decimal(int(minor_val)) / Decimal(minor_units_per_major)
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Алиасы для единообразия и совместимости
to_decimal_money = money2decimal
money_to_minor_units = money2minor
minor_units_to_decimal = minor2decimal

__all__ = [
    "minor2decimal",
    "minor_units_to_decimal",
    "money2decimal",
    "money2minor",
    "money_to_minor_units",
    "to_decimal_money",
]
