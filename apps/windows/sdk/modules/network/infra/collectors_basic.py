# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Basic Collectors
# =============================================================================
# Description:
#   Независимые сборщики базовой сетевой инвентаризации Windows:
#   NetworkAdapterCollector, IpConfigurationCollector, RouteTableCollector.
#   Не зависят от Hyper-V и WSL. Все вызовы PowerShell — read-only (Get-*).
#
# Usage Examples:
#   result = NetworkAdapterCollector(runner).collect()
#   if result.status == 'ok': print(len(result.items))
#
# File: collectors_basic.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from logger import logger

from .classification import (as_list, classify_adapter, family_of_prefix, normalize_mac,
                             prefix_to_mask)
from .models import (CollectorResult, KIND_ADAPTER, KIND_IP, KIND_ROUTE, STATUS_DATA_UNAVAILABLE,
                     STATUS_ERROR, STATUS_OK, STATUS_PARTIAL, STATUS_SOURCE_UNAVAILABLE, make_item,
                     now_iso)
from .ps_runner import ForbiddenCommandError, PowerShellRunner, PsResult

_ENUM = "@{{n='{0}';e={{[string]$_.{0}}}}}"


def enum_prop(name: str) -> str:
    """Возвращает calculated-property PowerShell, приводящее перечисление к строке."""
    return _ENUM.format(name)


class BaseCollector:
    """Базовый класс сборщика: общий каркас, учёт времени, статусов и ошибок."""

    name = ''
    source = ''

    def __init__(self, runner: PowerShellRunner) -> None:
        """Инициализирует сборщик.

        Args:
            runner: Контролируемый раннер PowerShell (внедряется явно, подменяется в тестах).
        """
        self.runner = runner

    def collect(self, ctx: Optional[Dict[str, CollectorResult]] = None) -> CollectorResult:
        """Выполняет сбор; локальный сбой не выбрасывается наружу, а фиксируется в результате.

        Args:
            ctx: Результаты ранее выполненных сборщиков (для зависимых сборщиков).

        Returns:
            CollectorResult: Результат со статусом, объектами и ошибками.
        """
        result = CollectorResult(name=self.name, source=self.source, started_at=now_iso())
        t0 = time.perf_counter()
        try:
            self._collect(result, ctx or {})
        except ForbiddenCommandError:
            raise
        except Exception as exc:  # noqa: BLE001 — сбой одного сборщика не должен ронять остальные
            result.status = STATUS_ERROR
            result.errors.append(f'Внутренняя ошибка сборщика: {exc}')
            logger.error(f'[NetworkInfra] {self.name}: внутренняя ошибка: {exc}')
        result.finished_at = now_iso()
        result.duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(f'[NetworkInfra] {self.name}: статус={result.status}, объектов={len(result.items)}, '
                    f'{result.duration_ms} мс, ошибок={len(result.errors)}')
        return result

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        """Реализуется потомками."""
        raise NotImplementedError

    def _query(self, result: CollectorResult, script: str, label: str) -> Optional[PsResult]:
        """Выполняет запрос; при сбое фиксирует ошибку и возвращает None.

        Args:
            result: Результат сборщика (дополняется ошибками).
            script: Read-only скрипт.
            label: Метка запроса для сообщений.

        Returns:
            Optional[PsResult]: Успешный результат либо None (None — осознанный признак сбоя).
        """
        res = self.runner.run_json(script)
        if res.ok:
            return res
        suffix = ' (нужны повышенные права)' if res.access_denied else ''
        detail = res.stderr.strip().splitlines()[0][:200] if res.stderr.strip() else res.error
        result.errors.append(f'{label}: {detail}{suffix}')
        if res.access_denied:
            result.needs_elevation = True
        return None

    @staticmethod
    def _failure_status(result: CollectorResult) -> str:
        """Статус при сбое обязательного запроса."""
        if result.needs_elevation:
            return STATUS_DATA_UNAVAILABLE
        return STATUS_SOURCE_UNAVAILABLE


def apply_classification(items: List[Dict[str, Any]], switch_names: Optional[List[str]] = None) -> None:
    """Проставляет класс адаптера, признаки и уверенность (повторно, когда известны коммутаторы).

    Args:
        items: Объекты адаптеров.
        switch_names: Имена виртуальных коммутаторов Hyper-V.
    """
    for item in items:
        cls, signals, confidence = classify_adapter(item['raw'], switch_names)
        item['props'].update({'adapter_class': cls, 'signals': signals, 'confidence': confidence,
                              'is_virtual': cls not in ('physical', 'unknown')})


class NetworkAdapterCollector(BaseCollector):
    """Сборщик сетевых адаптеров (Get-NetAdapter)."""

    name = 'adapters'
    source = 'PowerShell: Get-NetAdapter'

    _SCRIPT = ("Get-NetAdapter | Select-Object Name,InterfaceDescription,ifIndex,InterfaceGuid,MacAddress,"
               f"{enum_prop('Status')},LinkSpeed,{enum_prop('MediaConnectionState')},"
               f"{enum_prop('PhysicalMediaType')},ifType,Virtual,HardwareInterface,ComponentID,DriverProvider "
               "| ConvertTo-Json -Depth 3 -Compress")

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        res = self._query(result, self._SCRIPT, 'Get-NetAdapter')
        if res is None:
            result.status = self._failure_status(result)
            return
        stamp = now_iso()
        for raw in res.data:
            guid = str(raw.get('InterfaceGuid') or '').strip('{}').lower()
            mac = normalize_mac(raw.get('MacAddress'))
            name = str(raw.get('Name') or '')
            item_id = guid or (f'mac:{mac}' if mac else f'name:{name.lower()}')
            props = {'name': name, 'description': raw.get('InterfaceDescription') or '',
                     'interface_index': raw.get('ifIndex'), 'interface_guid': guid, 'mac': mac,
                     'if_type': raw.get('ifType'), 'media_type': raw.get('PhysicalMediaType') or '',
                     'status': raw.get('Status') or 'Unknown', 'media_state': raw.get('MediaConnectionState') or '',
                     'link_speed': raw.get('LinkSpeed') or '', 'hardware_interface': raw.get('HardwareInterface'),
                     'driver_provider': raw.get('DriverProvider') or ''}
            result.items.append(make_item(KIND_ADAPTER, item_id, name, 'Get-NetAdapter', props, raw, stamp))
        apply_classification(result.items)
        result.status = STATUS_OK


class IpConfigurationCollector(BaseCollector):
    """Сборщик IP-конфигурации интерфейсов: адреса, DNS, шлюзы, метрики."""

    name = 'ip_config'
    source = 'PowerShell: Get-NetIPAddress, Get-DnsClientServerAddress, Get-NetIPInterface, Get-NetIPConfiguration'

    _ADDR = ("Get-NetIPAddress | Select-Object InterfaceIndex,InterfaceAlias,IPAddress,PrefixLength,"
             f"{enum_prop('AddressFamily')},{enum_prop('Type')},{enum_prop('PrefixOrigin')},"
             f"{enum_prop('SuffixOrigin')},{enum_prop('AddressState')} | ConvertTo-Json -Depth 3 -Compress")
    _DNS = ("Get-DnsClientServerAddress | Select-Object InterfaceIndex,InterfaceAlias,"
            f"{enum_prop('AddressFamily')},ServerAddresses | ConvertTo-Json -Depth 3 -Compress")
    _METRIC = ("Get-NetIPInterface | Select-Object InterfaceIndex,InterfaceAlias,"
               f"{enum_prop('AddressFamily')},InterfaceMetric,{enum_prop('ConnectionState')},"
               f"{enum_prop('Dhcp')},NlMtu | ConvertTo-Json -Depth 3 -Compress")
    _GATEWAY = ("Get-NetIPConfiguration | Select-Object InterfaceIndex,InterfaceAlias,"
                "@{n='Gateway4';e={@($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })}},"
                "@{n='Gateway6';e={@($_.IPv6DefaultGateway | ForEach-Object { $_.NextHop })}} "
                "| ConvertTo-Json -Depth 3 -Compress")

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        addr = self._query(result, self._ADDR, 'Get-NetIPAddress')
        if addr is None:
            result.status = self._failure_status(result)
            return
        dns = self._query(result, self._DNS, 'Get-DnsClientServerAddress')
        metric = self._query(result, self._METRIC, 'Get-NetIPInterface')
        gateway = self._query(result, self._GATEWAY, 'Get-NetIPConfiguration')
        optional_failed = dns is None or metric is None or gateway is None

        ifaces: Dict[Any, Dict[str, Any]] = {}

        def entry(idx: Any, alias: Any) -> Dict[str, Any]:
            return ifaces.setdefault(idx, {'alias': alias or '', 'interface_index': idx, 'interface_id': f'if:{idx}',
                                           'ipv4': [], 'ipv6': [], 'dns': [], 'gateways': [], 'metric_v4': None,
                                           'metric_v6': None, 'dhcp_v4': '', 'mtu_v4': None, 'connection_state': ''})

        raw_by_idx: Dict[Any, Dict[str, Any]] = {}
        for row in addr.data:
            e = entry(row.get('InterfaceIndex'), row.get('InterfaceAlias'))
            fam = family_of_prefix(row.get('IPAddress'))
            rec = {'address': row.get('IPAddress'), 'prefix_length': row.get('PrefixLength'),
                   'mask': prefix_to_mask(row.get('PrefixLength'), fam), 'state': row.get('AddressState') or '',
                   'type': row.get('Type') or '', 'origin': row.get('PrefixOrigin') or ''}
            e['ipv4' if fam == 'IPv4' else 'ipv6'].append(rec)
            raw_by_idx.setdefault(row.get('InterfaceIndex'), {'addresses': []})['addresses'].append(row)
        if dns is not None:
            for row in dns.data:
                e = entry(row.get('InterfaceIndex'), row.get('InterfaceAlias'))
                for server in as_list(row.get('ServerAddresses')):
                    if server not in e['dns']:
                        e['dns'].append(server)
        if metric is not None:
            for row in metric.data:
                e = entry(row.get('InterfaceIndex'), row.get('InterfaceAlias'))
                if str(row.get('AddressFamily')) in ('IPv6', '23'):
                    e['metric_v6'] = row.get('InterfaceMetric')
                else:
                    e['metric_v4'] = row.get('InterfaceMetric')
                    e['dhcp_v4'] = row.get('Dhcp') or ''
                    e['mtu_v4'] = row.get('NlMtu')
                    e['connection_state'] = row.get('ConnectionState') or ''
        if gateway is not None:
            for row in gateway.data:
                e = entry(row.get('InterfaceIndex'), row.get('InterfaceAlias'))
                for gw in as_list(row.get('Gateway4')) + as_list(row.get('Gateway6')):
                    if gw and gw not in e['gateways']:
                        e['gateways'].append(gw)
        stamp = now_iso()
        for idx, props in ifaces.items():
            result.items.append(make_item(KIND_IP, f'if:{idx}', props['alias'], 'Get-NetIPAddress', props,
                                          raw_by_idx.get(idx, {}), stamp))
        result.status = STATUS_PARTIAL if optional_failed else STATUS_OK


class RouteTableCollector(BaseCollector):
    """Сборщик таблицы маршрутизации IPv4/IPv6 (Get-NetRoute)."""

    name = 'routes'
    source = 'PowerShell: Get-NetRoute'

    _SCRIPT = ("Get-NetRoute | Select-Object DestinationPrefix,NextHop,InterfaceIndex,InterfaceAlias,RouteMetric,"
               f"InterfaceMetric,{enum_prop('Protocol')},{enum_prop('State')} | ConvertTo-Json -Depth 3 -Compress")

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        res = self._query(result, self._SCRIPT, 'Get-NetRoute')
        if res is None:
            result.status = self._failure_status(result)
            return
        stamp = now_iso()
        for row in res.data:
            prefix = str(row.get('DestinationPrefix') or '')
            next_hop = str(row.get('NextHop') or '')
            route_metric = row.get('RouteMetric') or 0
            if_metric = row.get('InterfaceMetric') or 0
            props = {'destination_prefix': prefix, 'next_hop': next_hop, 'family': family_of_prefix(prefix),
                     'interface_index': row.get('InterfaceIndex'), 'interface_alias': row.get('InterfaceAlias') or '',
                     'interface_id': f"if:{row.get('InterfaceIndex')}", 'route_metric': route_metric,
                     'interface_metric': if_metric, 'effective_metric': route_metric + if_metric,
                     'protocol': row.get('Protocol') or '',
                     'is_default': prefix in ('0.0.0.0/0', '::/0'),
                     'on_link': next_hop in ('0.0.0.0', '::', '')}
            item_id = f"{prefix}|{next_hop}|if:{row.get('InterfaceIndex')}"
            result.items.append(make_item(KIND_ROUTE, item_id, prefix, 'Get-NetRoute', props, row, stamp))
        result.status = STATUS_OK

