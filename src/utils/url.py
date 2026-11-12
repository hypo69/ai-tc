# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Url Module
# =============================================================================
# Description:
#   Извлечение параметров запроса из URL, валидация URL и безопасное сокращение ссылок.
#
# Usage Examples:
#   CLI:
#     python -m src.utils.url
#   Python API:
#     from src.utils.url import extract_url_params
#
#     res = extract_url_params("https://example.com?a=1")
#
# File: url.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

"""Извлечение параметров запроса из URL, валидация URL и безопасное сокращение ссылок."""

import re
from urllib.parse import parse_qs, quote, urlparse

import requests

from logger import logger
from src.utils.printer import pprint as print

try:
    import validators
except ImportError:
    validators = None

_URL_PATTERN = re.compile(
    r'^(https?://)?(([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?([/?#].*)?$',
    re.IGNORECASE,
)
_ALLOWED_SCHEMES = {'http', 'https'}
_DEFAULT_HTTP_TIMEOUT = (5.0, 10.0)


def extract_url_params(url: str) -> dict | None:
    """Извлекает query-параметры из строки URL.

    Args:
        url (str): Строка URL для разбора.

    Returns:
        dict | None: Словарь query-параметров и их значений или None, если параметров нет.
    """
    if not url or not isinstance(url, str):
        logger.error('Функция extract_url_params получила пустой или невалидный URL')
        return None
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    if params:
        return {k: v if len(v) > 1 else v[0] for k, v in params.items()}
    logger.error('Функция extract_url_params вернула пустой результат')
    return None


def is_url(text: str) -> bool:
    """Проверяет, является ли переданная строка валидным URL (http/https).

    Args:
        text (str): Строка для проверки.

    Returns:
        bool: True, если строка является валидным URL, иначе False.
    """
    if not text or not isinstance(text, str):
        return False
    parsed = urlparse(text.strip())
    if parsed.scheme and parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False
    if validators is not None:
        return bool(validators.url(text))
    return bool(_URL_PATTERN.match(text.strip()))


def url_shortener(long_url: str) -> str | None:
    """Сокращает длинный URL через сервис TinyURL с явными таймаутами (connect, read).

    Args:
        long_url (str): Длинный URL для сокращения.

    Returns:
        str | None: Сокращенный URL или None при ошибке.
    """
    if not is_url(long_url):
        logger.error(f'Попытка сократить невалидный URL: {long_url!r}')
        return None
    encoded_url = quote(long_url.strip(), safe=':/?&=#%')
    api_url = f'https://tinyurl.com/api-create.php?url={encoded_url}'
    try:
        with requests.get(api_url, timeout=_DEFAULT_HTTP_TIMEOUT) as response:
            if response.status_code == 200 and response.text:
                return response.text.strip()
    except requests.RequestException as ex:
        logger.error(f'Сетевая ошибка в url_shortener: {ex}')
        return None
    logger.error('Функция url_shortener вернула пустой результат')
    return None


if __name__ == '__main__':
    url_input = input('Введите URL: ')
    if is_url(url_input):
        params = extract_url_params(url_input)
        if params:
            logger.console('Параметры URL:')
            for key, value in params.items():
                logger.console(f'{key}: {value}')
        else:
            logger.console('URL не содержит параметров.')
        shorten = input('Сократить этот URL? (y/n): ').strip().lower()
        if shorten == 'y':
            short_url = url_shortener(url_input)
            if short_url:
                logger.console(f'Сокращенный URL: {short_url}')
            else:
                logger.console('Ошибка при сокращении URL.')
    else:
        logger.console('Введенная строка не является валидным URL.')
