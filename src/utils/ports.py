# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Ports Module
# =============================================================================
# Description:
#   Модуль централизованного управления сетевыми портами и топологией сервисов на основе config.json.
#
#   Зачем нужен этот модуль:
#     1. Единый источник правды (SSOT): предотвращает конфликты адресов и обеспечивает
#        централизованную конфигурацию сетевых портов всей экосистемы (config.json).
#     2. Исключение жесткого кодирования (No Hardcoding): устраняет «магические числа»
#        номеров портов из исходного кода FastAPI-серверов, CLI-лончеров, терминалов и роутеров.
#     3. Динамическое разрешение коллизий (Dynamic Port Fallback): при включенном режиме
#        dynamic_ports или занятости назначенного статического порта автоматически находит
#        и выделяет свободный TCP-порт в операционной системе.
#     4. Оркестрация микросервисов и AI-сред: координирует сетевые адреса для основного сервера,
#        автономных доменных приложений (/apps/windows, network_terminal, system_inspector)
#        и локальных сред инференса LLM.
#
# Usage Examples:
#   Python API:
#     from src.utils.ports import get_port, load_ports_config, get_all_ports
#
#     # Получить порт конкретного сервиса или приложения:
#     server_port = get_port('server', default=8001)
#     windows_port = get_port('windows', default=8001)
#     ollama_port = get_port('ollama', default=11434)
#
#     # Загрузить всю структуру конфигурации:
#     cfg = load_ports_config()
#
# File: ports.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Модуль централизованного доступа к конфигурации сетевых портов (config.json)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
from header import __root__
from logger import logger
from src.utils.jjson import j_loads_ns

PORTS_FILE: Path = __root__ / 'config.json'


def load_ports_config(config_file: Optional[Path] = None) -> SimpleNamespace:
    """Загрузить конфигурацию портов из config.json в виде SimpleNamespace.

    Args:
        config_file: Необязательный путь к файлу конфигурации.

    Returns:
        SimpleNamespace: Объект конфигурации.
    """
    target_file = config_file or PORTS_FILE
    if not target_file.exists():
        logger.warning(f'Файл конфигурации не найден: {target_file}')
        return SimpleNamespace(dynamic_ports=False, server=SimpleNamespace(port=8001, main=8001), apps=SimpleNamespace(), services=SimpleNamespace())
    try:
        return j_loads_ns(target_file)
    except Exception as e:
        logger.error(f'Ошибка загрузки конфигурации из {target_file}: {e}')
        return SimpleNamespace(dynamic_ports=False, server=SimpleNamespace(port=8001, main=8001), apps=SimpleNamespace(), services=SimpleNamespace())


def is_dynamic_ports_enabled(config_file: Optional[Path] = None) -> bool:
    """Проверить, включен ли режим динамических портов (dynamic_ports).

    Args:
        config_file: Необязательный путь к файлу конфигурации.

    Returns:
        bool: True, если динамические порты включены, иначе False.
    """
    cfg = load_ports_config(config_file=config_file)
    dynamic_val = getattr(cfg, 'dynamic_ports', None)
    if dynamic_val is not None:
        return bool(dynamic_val)
    server_sec = getattr(cfg, 'server', None)
    if server_sec and hasattr(server_sec, 'dynamic_ports'):
        return bool(getattr(server_sec, 'dynamic_ports', False))
    return False


def get_all_ports(config_file: Optional[Path] = None) -> Dict[str, int]:
    """Получить плоский словарь со всеми сопоставлениями 'имя -> порт' из config.json.

    Args:
        config_file: Необязательный путь к файлу конфигурации.

    Returns:
        Dict[str, int]: Словарь имен сервисов/приложений и назначенных им портов.
    """
    target_file = config_file or PORTS_FILE
    if not target_file.exists():
        return {'server': 8001, 'main': 8001}
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f'Не удалось прочитать {target_file}: {e}')
        return {'server': 8001, 'main': 8001}

    flat_ports: Dict[str, int] = {}

    def _extract_dict_ports(d: Any) -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, int) and not isinstance(v, bool):
                    flat_ports[k] = v
                elif isinstance(v, dict):
                    if 'port' in v and isinstance(v['port'], int) and not isinstance(v['port'], bool):
                        flat_ports[k] = v['port']
                    _extract_dict_ports(v)

    # Обработка секции server
    if 'server' in data and isinstance(data['server'], dict):
        srv_port = data['server'].get('port')
        if isinstance(srv_port, int) and not isinstance(srv_port, bool):
            flat_ports['server'] = srv_port
            flat_ports['main'] = srv_port

    for section_key in ('apps', 'services', 'static_ports', 'ports'):
        if section_key in data and isinstance(data[section_key], dict):
            _extract_dict_ports(data[section_key])

    return flat_ports


def get_port(
    name: str,
    default: Optional[int] = None,
    config_file: Optional[Path] = None,
    host: str = '127.0.0.1',
    dynamic_fallback: bool = False,
) -> Optional[int]:
    """Получить номер порта для заданного приложения, сервера или сервиса.

    Args:
        name: Название микроприложения (напр. 'windows', 'tc'), сервера ('server' / 'main') или сервиса ('ollama').
        default: Значение по умолчанию, если порт не найден.
        config_file: Необязательный путь к файлу config.json.
        host: Хост для проверки занятости при динамическом выделении.
        dynamic_fallback: Если True или если dynamic_ports=True в config.json, при занятом статическом порте выделяется свободный.

    Returns:
        Optional[int]: Номер порта или default.
    """
    ports = get_all_ports(config_file=config_file)
    assigned_port: Optional[int] = None
    if name in ports:
        assigned_port = ports[name]
    elif name in ('server', 'main', 'tc', 'windows') and ('server' in ports or 'main' in ports):
        assigned_port = ports.get('server') or ports.get('main')
    else:
        assigned_port = default

    if assigned_port is None:
        return None

    dynamic_active = dynamic_fallback or is_dynamic_ports_enabled(config_file=config_file)
    if dynamic_active:
        from src.utils.get_free_port import _is_port_in_use, get_free_port
        if _is_port_in_use(host, assigned_port):
            try:
                free_port = get_free_port(host)
                logger.info(f"Статический порт {assigned_port} для '{name}' занят. Динамически выделен порт {free_port}")
                return free_port
            except Exception as e:
                logger.warning(f"Не удалось выделить динамический порт для '{name}': {e}")
    return assigned_port
