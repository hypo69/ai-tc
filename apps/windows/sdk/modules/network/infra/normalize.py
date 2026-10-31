# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Cross-Source Normalization
# =============================================================================
# Description:
#   Согласование данных независимых сборщиков: устойчивые идентификаторы
#   интерфейсов (InterfaceGuid вместо InterfaceIndex), повторная классификация
#   адаптеров с учётом коммутаторов Hyper-V, связывание NAT с коммутаторами,
#   обогащённое представление адаптеров (IP, DNS, шлюзы) для API.
#
#   Стратегия идентификации: адаптер — InterfaceGuid, иначе MAC, иначе имя;
#   IP-адрес — <id интерфейса>|<адрес>; маршрут — <префикс>|<next hop>|<id интерфейса>;
#   коммутатор — Id, иначе имя; NAT — имя; дистрибутив WSL — имя в нижнем регистре.
#
# File: normalize.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import copy
from typing import Any, Dict, List

from .classification import link_nat_to_interfaces
from .collectors_basic import apply_classification
from .models import CollectorResult, STATUS_OK, STATUS_PARTIAL

_USABLE = (STATUS_OK, STATUS_PARTIAL)


def finalize_identities(results: Dict[str, CollectorResult]) -> None:
    """Заменяет временные ключи if:<InterfaceIndex> на устойчивые (InterfaceGuid).

    Args:
        results: Результаты сборщиков по имени источника (изменяются на месте).
    """
    adapters = results.get('adapters')
    index_to_id: Dict[Any, str] = {}
    if adapters:
        for item in adapters.items:
            idx = item['props'].get('interface_index')
            if idx is not None:
                index_to_id[idx] = item['id']
    for key in ('ip_config', 'routes'):
        res = results.get(key)
        if not res:
            continue
        for item in res.items:
            props = item['props']
            idx = props.get('interface_index')
            iface_id = index_to_id.get(idx) or f"alias:{(props.get('alias') or props.get('interface_alias') or idx)}".lower()
            props['interface_id'] = iface_id
            if key == 'ip_config':
                item['id'] = iface_id
            else:
                item['id'] = f"{props['destination_prefix']}|{props['next_hop']}|{iface_id}"


def refine_classification(results: Dict[str, CollectorResult]) -> None:
    """Повторно классифицирует адаптеры, когда известны имена коммутаторов Hyper-V."""
    adapters, hyperv = results.get('adapters'), results.get('hyperv')
    if adapters and hyperv and hyperv.status in _USABLE:
        apply_classification(adapters.items, [s['props']['name'] for s in hyperv.items])


def link_nat(results: Dict[str, CollectorResult]) -> None:
    """Заполняет у NAT связанные интерфейсы и коммутаторы по совпадению IP с внутренним префиксом."""
    nat, ip_cfg = results.get('nat'), results.get('ip_config')
    if not nat or not ip_cfg:
        return
    for item in nat.items:
        links = link_nat_to_interfaces(item['props']['internal_prefix'], ip_cfg.items)
        item['props']['related_interfaces'] = sorted({lnk['alias'] for lnk in links})
        item['props']['related_switches'] = sorted({lnk['switch'] for lnk in links if lnk['switch']})


def adapters_view(results: Dict[str, CollectorResult]) -> List[Dict[str, Any]]:
    """Строит обогащённый список адаптеров (IP, DNS, шлюзы, метрики) для API/UI.

    Args:
        results: Результаты сборщиков.

    Returns:
        List[Dict[str, Any]]: Копии объектов адаптеров с полем props.ip.
    """
    adapters, ip_cfg = results.get('adapters'), results.get('ip_config')
    ip_by_id = {i['id']: i['props'] for i in (ip_cfg.items if ip_cfg else [])}
    view: List[Dict[str, Any]] = []
    for item in (adapters.items if adapters else []):
        copy_item = copy.deepcopy(item)
        ip = ip_by_id.get(item['id'], {})
        copy_item['props']['ip'] = {k: ip.get(k, [] if k in ('ipv4', 'ipv6', 'dns', 'gateways') else None)
                                    for k in ('ipv4', 'ipv6', 'dns', 'gateways', 'metric_v4', 'metric_v6', 'dhcp_v4')}
        copy_item['sources'] = ['Get-NetAdapter'] + (['Get-NetIPAddress/Get-DnsClientServerAddress'] if ip else [])
        view.append(copy_item)
    return view

