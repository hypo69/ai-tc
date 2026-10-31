# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Models
# =============================================================================
# Description:
#   Единая нормализованная модель сетевой инфраструктуры: статусы данных,
#   результат сборщика, объект инвентаря, диагностический результат и изменение.
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

# Статусы данных источника (передаются в API и UI).
STATUS_OK = 'ok'                          # данные успешно получены
STATUS_PARTIAL = 'partial'                # данные получены частично
STATUS_SOURCE_UNAVAILABLE = 'source_unavailable'  # источник недоступен
STATUS_NOT_INSTALLED = 'not_installed'    # компонент не установлен
STATUS_DATA_UNAVAILABLE = 'data_unavailable'      # компонент есть, сведения недоступны (права и т.п.)
STATUS_ERROR = 'error'                    # сбор завершился ошибкой
STATUS_UNKNOWN = 'unknown'                # состояние не определено

ALL_STATUSES = (STATUS_OK, STATUS_PARTIAL, STATUS_SOURCE_UNAVAILABLE, STATUS_NOT_INSTALLED,
                STATUS_DATA_UNAVAILABLE, STATUS_ERROR, STATUS_UNKNOWN)

# Статусы, при которых список объектов источника считается полным.
COMPLETE_STATUSES = (STATUS_OK,)

# Уровни важности диагностики.
SEVERITIES = ('info', 'warning', 'error', 'critical')

# Типы объектов инвентаря.
KIND_ADAPTER = 'adapter'
KIND_IP = 'ip_address'
KIND_IP_IFACE = 'ip_interface'
KIND_ROUTE = 'route'
KIND_SWITCH = 'virtual_switch'
KIND_VNIC = 'virtual_adapter'
KIND_NAT = 'nat'
KIND_WSL = 'wsl_environment'
KIND_WSL_DISTRO = 'wsl_distro'

# Соответствие типа объекта источнику (для оценки полноты при сравнении).
KIND_SOURCE = {
    KIND_ADAPTER: 'adapters',
    KIND_IP: 'ip_config',
    KIND_IP_IFACE: 'ip_config',
    KIND_ROUTE: 'routes',
    KIND_SWITCH: 'hyperv',
    KIND_VNIC: 'hyperv',
    KIND_NAT: 'nat',
    KIND_WSL: 'wsl',
    KIND_WSL_DISTRO: 'wsl',
}


def now_iso() -> str:
    """Возвращает текущее время UTC в ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def make_item(kind: str, item_id: str, name: str, source: str, props: Dict[str, Any],
              raw: Any, collected_at: str, status: str = STATUS_OK) -> Dict[str, Any]:
    """Формирует объект инвентаря с общими полями (ТЗ § 6.1).

    Args:
        kind: Тип объекта (KIND_*).
        item_id: Устойчивый идентификатор (см. стратегию в README).
        name: Отображаемое имя.
        source: Источник данных (например, 'Get-NetAdapter').
        props: Нормализованные свойства (участвуют в сравнении снимков).
        raw: Исходные данные источника.
        collected_at: Время сбора.
        status: Статус доступности объекта.

    Returns:
        Dict[str, Any]: Словарь объекта.
    """
    return {'id': item_id, 'kind': kind, 'name': name, 'source': source, 'status': status,
            'collected_at': collected_at, 'props': props, 'raw': raw}


@dataclass
class CollectorResult:
    """Результат работы одного сборщика.

    Attributes:
        name: Ключ источника ('adapters', 'ip_config', 'routes', 'hyperv', 'nat', 'wsl').
        source: Человекочитаемое описание источников данных.
        status: Один из STATUS_*.
        items: Нормализованные объекты.
        extra: Дополнительные наборы (например, виртуальные адаптеры хоста).
        errors: Сообщения об ошибках/ограничениях.
        notes: Пояснения к интерпретации результата.
        needs_elevation: Признак того, что для полных данных нужны повышенные права.
        started_at: Время начала.
        finished_at: Время завершения.
        duration_ms: Длительность, мс.
    """

    name: str
    source: str
    status: str = STATUS_UNKNOWN
    items: List[Dict[str, Any]] = field(default_factory=list)
    extra: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    needs_elevation: bool = False
    started_at: str = ''
    finished_at: str = ''
    duration_ms: int = 0

    def to_dict(self, include_items: bool = True) -> Dict[str, Any]:
        """Сериализует результат; без объектов — только метаданные источника."""
        data = asdict(self)
        if not include_items:
            data.pop('items')
            data.pop('extra')
            data['items_count'] = len(self.items)
        return data


@dataclass
class Finding:
    """Диагностический результат (ТЗ § 3.7)."""

    rule_code: str
    title: str
    description: str
    severity: str
    affected: List[str]
    facts: Dict[str, Any]
    source: str
    checked_at: str
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует результат диагностики."""
        return asdict(self)


@dataclass
class NetworkChange:
    """Изменение между снимками (тип: added / removed / changed)."""

    change_type: str
    kind: str
    object_id: str
    name: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует изменение."""
        return asdict(self)

