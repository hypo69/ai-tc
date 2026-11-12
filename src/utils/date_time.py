# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Date Time Module
# =============================================================================
# Description:
#   Утилиты работы с датой, временем, UTC ISO 8601 и проверкой временных интервалов.
#
# Usage Examples:
#   CLI:
#     python -m src.utils.date_time
#   Python API:
#     from src.utils.date_time import TimeoutCheck, utc_now_iso
#
#     service = TimeoutCheck()
#     result = service.interval()
#     print(result, utc_now_iso())
#
# File: date_time.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

"""Утилиты работы с датой, временем, UTC ISO 8601 и проверкой временных интервалов."""

from datetime import datetime, time, timezone
import threading

from logger import logger
from src.utils.printer import pprint as print


def utc_now_iso() -> str:
    """Возвращает текущее время в строгом формате UTC ISO 8601 ('YYYY-MM-DDTHH:MM:SSZ').

    Returns:
        str: Строка времени в формате UTC ISO 8601.
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class TimeoutCheck:
    """Класс для проверки вхождения текущего времени в заданный интервал и ввода с таймаутом."""

    def __init__(self) -> None:
        """Инициализирует состояние проверки интервала."""
        self.result: bool | None = None
        self.user_input: str | None = None

    def interval(self, start: time = time(23, 0), end: time = time(6, 0)) -> bool:
        """Проверяет, входит ли текущее время в указанный временной интервал.

        Args:
            start (time): Начало интервала (по умолчанию 23:00).
            end (time): Конец интервала (по умолчанию 06:00).

        Returns:
            bool: True, если текущее время находится внутри интервала, иначе False.
        """
        current_time = datetime.now().time()
        if start < end:
            self.result = start <= current_time <= end
        else:
            self.result = current_time >= start or current_time <= end
        return self.result

    def interval_with_timeout(self, timeout: int = 5, start: time = time(23, 0), end: time = time(6, 0)) -> bool:
        """Проверяет вхождение текущего времени в интервал с ограничением по времени ожидания.

        Args:
            timeout (int): Время ожидания в секундах.
            start (time): Начало интервала (по умолчанию 23:00).
            end (time): Конец интервала (по умолчанию 06:00).

        Returns:
            bool: True, если время входит в интервал и проверка завершилась до таймаута, иначе False.
        """
        thread = threading.Thread(target=self.interval, args=(start, end), daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logger.console(f'Превышен таймаут ({timeout} сек), продолжение выполнения.')
            thread.join(timeout=1.0)
            return False
        return bool(self.result)

    def get_input(self) -> None:
        """Запрашивает пользовательский ввод из стандартного потока ввода."""
        self.user_input = input('U:> ')

    def input_with_timeout(self, timeout: int = 5) -> str | None:
        """Ожидает пользовательский ввод в течение заданного таймаута.

        Args:
            timeout (int): Время ожидания ввода в секундах.

        Returns:
            str | None: Введенная строка или None при наступлении таймаута.
        """
        self.user_input = None
        thread = threading.Thread(target=self.get_input, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logger.console(f'Превышен таймаут ожидания ввода ({timeout} сек).')
            return None
        return self.user_input


if __name__ == '__main__':
    timeout_check = TimeoutCheck()
    if timeout_check.interval_with_timeout(timeout=5):
        logger.console('Текущее время входит в заданный интервал.')
    else:
        logger.console('Текущее время вне интервала или произошел таймаут.')
