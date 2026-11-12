# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Get Free Port Module
# =============================================================================
# Description:
#   Проверка доступности TCP-портов на хосте и выделение свободного порта.
#
# Usage Examples:
#   Python API:
#     from src.utils.get_free_port import get_free_port
#
#     res = get_free_port("127.0.0.1")
#
# File: get_free_port.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:40:00
# =============================================================================

"""Проверка доступности TCP-портов на хосте и выделение свободного порта."""

import socket
from typing import List, Tuple, Union

from logger import logger


def _is_port_in_use(host: str, port: int) -> bool:
    """Проверяет, занят ли указанный TCP-порт на заданном хосте.

    Args:
        host (str): Хост для проверки ('localhost', '127.0.0.1' и др.).
        port (int): Номер TCP-порта.

    Returns:
        bool: True, если порт занят, иначе False.
    """
    target_host = '127.0.0.1' if host in ('localhost', '') else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((target_host, port))
            return False
        except OSError:
            return True


def _parse_port_range(port_range_str: str) -> Tuple[int, int]:
    """Разбирает строку диапазона портов вида 'min-max'.

    Args:
        port_range_str (str): Строка диапазона портов.

    Returns:
        Tuple[int, int]: Кортеж (min_port, max_port).

    Raises:
        ValueError: Если формат диапазона некорректен.
    """
    try:
        parts = port_range_str.split('-')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f'Incorrect range format: {port_range_str}')
        min_port = int(parts[0])
        max_port = int(parts[1])
        if min_port >= max_port or min_port < 1 or max_port > 65535:
            raise ValueError(f'Incorrect range: {port_range_str}')
        return (min_port, max_port)
    except ValueError as e:
        logger.error(f'Ошибка разбора диапазона портов: {port_range_str}')
        raise ValueError(f'Error parsing range: {port_range_str}') from e


def get_free_port(host: str, port_range: Union[str, List[str]] = '') -> int:
    """Ищет и выделяет первый свободный TCP-порт в заданном диапазоне или во всем пуле.

    Args:
        host (str): Адрес хоста для проверки доступности порта.
        port_range (Union[str, List[str]]): Диапазон(ы) портов ('min-max' или список строк).

    Returns:
        int: Номер свободного TCP-порта.

    Raises:
        ValueError: Если свободный порт не найден или диапазон указан неверно.
    """
    if port_range:
        if isinstance(port_range, str):
            min_port, max_port = _parse_port_range(port_range)
            for port in range(min_port, max_port + 1):
                if not _is_port_in_use(host, port):
                    return port
            raise ValueError(f'Free port in range {port_range} not found')
        elif isinstance(port_range, list):
            for item in port_range:
                if not isinstance(item, str):
                    continue
                try:
                    min_port, max_port = _parse_port_range(item)
                    for port in range(min_port, max_port + 1):
                        if not _is_port_in_use(host, port):
                            return port
                except ValueError:
                    continue
            raise ValueError(f'Free port in ranges {port_range} not found')
        else:
            raise ValueError(f'Incorrect range type: {type(port_range)}')
    else:
        for port in range(1024, 65536):
            if not _is_port_in_use(host, port):
                return port
        raise ValueError('Free port not found')
