# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts - Check System Health
# =============================================================================
# Description:
#   Скрипт/модуль системы AI-Windows-Admin (`check_system_health`).
#
# Usage Examples:
#   CLI:
#     python -m scripts.check_system_health
#   Python API:
#     from scripts.check_system_health import check_health
#
#     res = check_health()
#
# File: check_system_health.py
# Project: ai-windows-admin
# Package: scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:30
# =============================================================================

"""Скрипт/модуль системы AI-Windows-Admin (`check_system_health`)."""

from logger import logger
import requests
import json
import datetime
from pathlib import Path
SERVER_URL = 'https://localhost:8000'

def check_health():
    logger.console(f'Проверка состояния системы на {SERVER_URL}...')
    try:
        response = requests.get(f'{SERVER_URL}/', verify=False, timeout=5)
        status = {'timestamp': datetime.datetime.now().isoformat(), 'server_url': SERVER_URL, 'status_code': response.status_code, 'healthy': response.status_code == 200}
        logger.console(f"Результат: статус {response.status_code}, здорова: {status['healthy']}")
        return status
    except requests.exceptions.RequestException as e:
        logger.console(f'Ошибка подключения к серверу: {e}')
        return {'timestamp': datetime.datetime.now().isoformat(), 'server_url': SERVER_URL, 'error': str(e), 'healthy': False}
if __name__ == '__main__':
    report = check_health()
    report_file = Path('logs/health_report.json')
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    logger.console(f'Отчет сохранен в {report_file}')
