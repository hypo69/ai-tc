# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Root - Tc Launcher
# =============================================================================
# Description:
#   Точка входа и лончер внутреннего сервера Windows System API (Terminal Controller / TC)
#   с поддержкой BCP 47 локалей/регионов (?region=ru-RU) и автоматическим освобождением
#   занятых портов.
#
#   Зачем нужен этот модуль:
#     1. Запуск низкоуровневого Windows API: поднимает FastAPI сервер модуля apps/windows/api (порт 8001).
#     2. Автоматическое освобождение портов: проверяет и завершает зависшие процессы на целевом порту.
#     3. Локализация BCP 47: парсинг и нормализация кода региона (ru-ru -> ru-RU) с формированием ссылки TC UI.
#
# Usage Examples:
#   CLI:
#     py tc.py
#     py tc.py --region ru-ru
#     py tc.py --port 8001 --host 127.0.0.1
#   Python API:
#     from tc import run_tc
#
#     run_tc(port=8001, region="ru-RU")
#
# File: tc.py
# Project: ai-tc
# Package: root
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 15:50:00
# =============================================================================

from __future__ import annotations
"""Точка входа и консольный лончер для Windows System API (TC)."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# =============================================================================
# UTF-8 Encoding Fix for Windows Console
# =============================================================================
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import header
from header import __root__
from logger import logger, get_uvicorn_log_config
from scripts.cli.utils import get_process_on_port, kill_process

# =============================================================================
# Глобальные константы конфигурации
# =============================================================================
DEFAULT_HOST: str = '127.0.0.1'
DEFAULT_PORT: int = 8001
DEFAULT_LOG_LEVEL: str = 'info'
ALLOWED_HOSTS: tuple[str, ...] = ('127.0.0.1', 'localhost', '::1')
WINDOWS_CONFIG_REL_PATH: Path = Path('apps') / 'windows' / 'config.json'
INTERNAL_APP_MODULE: str = 'apps.windows.api.internal_app:create_internal_app'

DEFAULT_BCP47_REGIONS: Dict[str, str] = {
    'ru': 'RU',
    'he': 'IL',
    'uk': 'UA',
    'en': 'US',
    'de': 'DE',
    'fr': 'FR',
    'es': 'ES',
    'pt': 'BR',
    'zh': 'CN',
    'ja': 'JP',
}


def normalize_bcp47_tag(tag: str) -> str:
    """Нормализует код языка и региона по стандарту BCP 47 (например, ru-ru -> ru-RU).

    Args:
        tag (str): Исходный тег локали или языка (например, 'ru-ru', 'en_us', 'he').

    Returns:
        str: Нормализованный BCP 47 тег (например, 'ru-RU', 'en-US', 'he-IL').
    """
    clean_tag = tag.strip().strip("'\"`").replace('_', '-')
    match = re.match(r'^([a-zA-Z]{2,3})(?:-([a-zA-Z]{2,4}))?$', clean_tag)
    if not match:
        return clean_tag

    lang_part = match.group(1).lower()
    if match.group(2):
        reg_part = match.group(2).upper()
    elif lang_part in DEFAULT_BCP47_REGIONS:
        reg_part = DEFAULT_BCP47_REGIONS[lang_part]
    else:
        reg_part = lang_part.upper()

    return f'{lang_part}-{reg_part}'


def free_port_if_occupied(port: int) -> bool:
    """Проверяет занятость сетевого порта и освобождает его при необходимости.

    Args:
        port (int): Номер порта для проверки и освобождения.

    Returns:
        bool: True, если порт свободен или был успешно освобожден; False в случае ошибки.
    """
    proc_info = get_process_on_port(port)
    if proc_info:
        pid, proc_name = proc_info
        logger.warning(f'  [WARN] Порт {port} занят процессом {proc_name} (PID: {pid}). Завершение...')
        if kill_process(pid, force=True):
            logger.info(f'  [OK] Занятый порт {port} успешно освобождён (PID: {pid})')
            return True
        logger.warning(f'  [WARN] Не удалось завершить PID {pid}')
        return False
    return True


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки.

    Args:
        args (Optional[List[str]]): Список аргументов для парсинга (по умолчанию sys.argv[1:]).

    Returns:
        argparse.Namespace: Распарсенные аргументы.
    """
    parser = argparse.ArgumentParser(
        description='AI-Windows-Admin Windows System API (TC) Launcher',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--host', '-H',
        default=DEFAULT_HOST,
        help='IP-адрес для прослушивания (только localhost)',
    )
    parser.add_argument(
        '--port', '-P',
        type=int,
        default=DEFAULT_PORT,
        help='Порт внутреннего сервиса Windows API',
    )
    parser.add_argument(
        '--region', '--locale', '--lang', '--language-region',
        dest='region',
        default=None,
        help='Код языка/региона по стандарту BCP 47 (например: ru-RU, en-US, he-IL)',
    )
    parser.add_argument(
        '--reload',
        action='store_true',
        default=False,
        help='Включить hot-reload (для разработки)',
    )
    parser.add_argument(
        '--log-level',
        default=DEFAULT_LOG_LEVEL,
        choices=['critical', 'error', 'warning', 'info', 'debug', 'trace'],
        help='Уровень логирования uvicorn',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Выполнить подготовку без запуска цикла сервера uvicorn',
    )
    parser.add_argument(
        '--ssl',
        dest='ssl',
        action='store_true',
        default=None,
        help='Принудительно включить HTTPS (SSL)',
    )
    parser.add_argument(
        '--no-ssl',
        dest='ssl',
        action='store_false',
        help='Принудительно отключить HTTPS (SSL)',
    )
    parser.add_argument(
        '--ssl-cert',
        dest='ssl_cert',
        default=None,
        help='Путь к сертификату SSL (.pem)',
    )
    parser.add_argument(
        '--ssl-key',
        dest='ssl_key',
        default=None,
        help='Путь к приватному ключу SSL (.pem)',
    )
    return parser.parse_args(args)


def run_tc(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    region: Optional[str] = None,
    reload: bool = False,
    log_level: str = DEFAULT_LOG_LEVEL,
    dry_run: bool = False,
    ssl: Optional[bool] = None,
    ssl_cert: Optional[str] = None,
    ssl_key: Optional[str] = None,
) -> int:
    """Выполняет подготовку окружения и запуск Windows System API сервиса.

    Args:
        host (str): Сетевой адрес хоста.
        port (int): Порт сервиса.
        region (Optional[str]): Необязательный BCP 47 тег локали.
        reload (bool): Флаг горячей перезагрузки uvicorn.
        log_level (str): Уровень логирования uvicorn.
        dry_run (bool): Тестовый режим без блокирующего запуска uvicorn.
        ssl (Optional[bool]): Принудительно включить/выключить SSL.
        ssl_cert (Optional[str]): Путь к сертификату SSL.
        ssl_key (Optional[str]): Путь к приватному ключу SSL.

    Returns:
        int: Код возврата процесса (0 - успех, 1 - ошибка).
    """
    # 1. Принудительное ограничение хоста на localhost
    if host not in ALLOWED_HOSTS:
        logger.warning(
            f'  [WARN] Внутренний сервис не может слушать на {host}. '
            f'Принудительно используется {DEFAULT_HOST}.'
        )
        host = DEFAULT_HOST

    # 2. Настройка профиля конфигурации
    windows_config = __root__ / WINDOWS_CONFIG_REL_PATH
    if windows_config.exists():
        os.environ['AIWINDOWSADMIN_CONFIG'] = str(windows_config)
        os.environ['CONFIG_FILE'] = str(windows_config)
        logger.info(f'  [⚙️ Config Profile]: {windows_config}')

    # Определение SSL параметров из конфигурации
    server_cfg: Dict[str, Any] = {}
    root_cfg_path = __root__ / 'config.json'
    if root_cfg_path.is_file():
        try:
            with open(root_cfg_path, 'r', encoding='utf-8') as f:
                server_cfg = json.load(f).get('server', {})
        except Exception:
            pass

    if ssl is not None:
        use_ssl = bool(ssl)
    else:
        use_ssl = (
            server_cfg.get('protocol', '').lower() == 'https'
            or server_cfg.get('use_ssl') is True
        )

    ssl_certfile = ssl_cert or server_cfg.get('ssl_certfile')
    ssl_keyfile = ssl_key or server_cfg.get('ssl_keyfile')

    if use_ssl:
        if not ssl_certfile or not Path(os.path.expanduser(ssl_certfile)).is_file():
            default_cert = Path.home() / '.certs' / 'localhost+2.pem'
            if default_cert.is_file():
                ssl_certfile = str(default_cert)
        else:
            ssl_certfile = str(Path(os.path.expanduser(ssl_certfile)).resolve())

        if not ssl_keyfile or not Path(os.path.expanduser(ssl_keyfile)).is_file():
            default_key = Path.home() / '.certs' / 'localhost+2-key.pem'
            if default_key.is_file():
                ssl_keyfile = str(default_key)
        else:
            ssl_keyfile = str(Path(os.path.expanduser(ssl_keyfile)).resolve())

        if ssl_certfile and ssl_keyfile and Path(ssl_certfile).is_file() and Path(ssl_keyfile).is_file():
            logger.info(f'  [🔒 SSL Active]: Cert={ssl_certfile}')
            logger.info(f'  [🔑 SSL Active]: Key={ssl_keyfile}')
        else:
            logger.warning('  [WARN] SSL включен, но файлы сертификатов не найдены в ~/.certs! Запуск в HTTP.')
            use_ssl = False

    # 3. Обработка BCP 47 локали
    region_query = ''
    if region:
        normalized_tag = normalize_bcp47_tag(region)
        region_query = f'?region={normalized_tag}'
        logger.info(f'  [🌐 BCP 47 Locale]: {normalized_tag}')

    # 4. Освобождение занятого порта
    free_port_if_occupied(port)

    # 5. Информационный баннер
    proto = 'https' if use_ssl else 'http'
    logger.info(f'  [Windows Internal API] Запуск на {proto}://{host}:{port}')
    logger.info(f'  [Windows Internal API] TC UI: {proto}://{host}:{port}/tc{region_query}')
    logger.info(f'  [Windows Internal API] Health: {proto}://{host}:{port}/health')
    logger.info(f'  [Windows Internal API] Docs:   {proto}://{host}:{port}/docs')

    if dry_run:
        return 0

    # 6. Запуск uvicorn
    try:
        import uvicorn
    except ImportError:
        logger.error('[ERROR] uvicorn не установлен. Установите: pip install uvicorn')
        return 1

    try:
        uvicorn_kwargs: Dict[str, Any] = {
            'factory': True,
            'host': host,
            'port': port,
            'reload': reload,
            'log_level': log_level,
            'log_config': get_uvicorn_log_config('windows_api.log'),
            'server_header': False,
            'access_log': True,
        }
        if use_ssl and ssl_certfile and ssl_keyfile:
            uvicorn_kwargs['ssl_certfile'] = ssl_certfile
            uvicorn_kwargs['ssl_keyfile'] = ssl_keyfile

        uvicorn.run(
            INTERNAL_APP_MODULE,
            **uvicorn_kwargs,
        )
        return 0
    except KeyboardInterrupt:
        logger.info('  [INFO] Windows System API сервер остановлен.')
        return 0
    except Exception as exc:
        logger.error(f'[ERROR] Ошибка запуска сервера Windows API: {exc}')
        return 1


def main() -> int:
    """Главная точка входа лончера при запуске из консоли.

    Returns:
        int: Код возврата (0 - успешно, ненулевой - ошибка).
    """
    args = parse_args()
    return run_tc(
        host=args.host,
        port=args.port,
        region=args.region,
        reload=args.reload,
        log_level=args.log_level,
        dry_run=args.dry_run,
        ssl=args.ssl,
        ssl_cert=args.ssl_cert,
        ssl_key=args.ssl_key,
    )


if __name__ == '__main__':
    sys.exit(main())

