# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Settings
# =============================================================================
# Description:
#   Настройки модуля диагностики сетевой инфраструктуры. Значения читаются из
#   секции "infra" файла apps/windows/sdk/modules/network/config.json;
#   при отсутствии ключей используются значения по умолчанию.
#
# File: settings.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from logger import logger

_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config.json'


@dataclass(frozen=True)
class InfraSettings:
    """Параметры диагностики сети.

    Attributes:
        ps_timeout_sec: Тайм-аут одного вызова PowerShell, сек.
        wsl_timeout_sec: Тайм-аут одного вызова wsl.exe, сек.
        cache_ttl_sec: Время жизни кэша последнего сбора, сек.
        retention_max_snapshots: Максимум хранимых снимков.
        retention_days: Максимальный возраст снимка, дней.
        max_workers: Число параллельных независимых сборщиков.
        db_path: Путь к SQLite-файлу истории.
    """

    ps_timeout_sec: int = 25
    wsl_timeout_sec: int = 15
    cache_ttl_sec: int = 30
    retention_max_snapshots: int = 200
    retention_days: int = 90
    max_workers: int = 5
    db_path: str = ''

    def resolved_db_path(self) -> Path:
        """Возвращает путь к БД истории (по умолчанию %APPDATA%/ai-tc/network_infra)."""
        if self.db_path:
            return Path(self.db_path)
        root = Path(os.getenv('APPDATA', str(Path.home() / 'AppData' / 'Roaming')))
        return root / 'ai-tc' / 'network_infra' / 'network_infra.db'


def load_settings(config_path: Path = _CONFIG_PATH) -> InfraSettings:
    """Загружает настройки из config.json.

    Args:
        config_path: Путь к config.json модуля network.

    Returns:
        InfraSettings: Настройки; при ошибке чтения — значения по умолчанию.
    """
    defaults = InfraSettings()
    try:
        raw: Dict[str, Any] = json.loads(config_path.read_text(encoding='utf-8')).get('infra', {})
    except (OSError, ValueError) as exc:
        logger.warning(f'[NetworkInfra] Не удалось прочитать настройки {config_path}: {exc}')
        return defaults
    known = {k: raw[k] for k in defaults.__dataclass_fields__ if k in raw}
    return InfraSettings(**{**defaults.__dict__, **known})

