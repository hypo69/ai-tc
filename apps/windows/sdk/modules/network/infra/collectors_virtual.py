# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Virtual Infrastructure Collectors
# =============================================================================
# Description:
#   Сборщики виртуальной сетевой инфраструктуры: HyperVSwitchCollector,
#   NatConfigurationCollector, WslNetworkCollector. Проверяют наличие командлета/
#   компонента до запроса и отличают «не установлено» / «нет прав» / «ошибка» /
#   «объектов нет». WSL-сборщик не выполняет запросов, если WSL не установлен.
#
# Usage Examples:
#   result = HyperVSwitchCollector(runner).collect()
#   result = WslNetworkCollector(runner).collect(ctx={'adapters': adapters_result})
#
# File: collectors_virtual.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .classification import as_list, link_nat_to_interfaces, normalize_mac, normalize_switch_type
from .collectors_basic import BaseCollector, enum_prop
from .models import (CollectorResult, KIND_NAT, KIND_SWITCH, KIND_VNIC, KIND_WSL, KIND_WSL_DISTRO,
                     STATUS_DATA_UNAVAILABLE, STATUS_ERROR, STATUS_NOT_INSTALLED, STATUS_OK,
                     STATUS_PARTIAL, STATUS_SOURCE_UNAVAILABLE, make_item, now_iso)
from .ps_runner import PowerShellRunner

_NOT_INSTALLED_RE = re.compile(r'is not installed|не установлен|wsl\.exe --install', re.IGNORECASE)
_NO_DISTROS_RE = re.compile(r'no installed distributions|нет установленных дистрибутивов', re.IGNORECASE)
_RUNNING_RE = re.compile(r'running|выполня', re.IGNORECASE)
_STOPPED_RE = re.compile(r'stopped|остановлен', re.IGNORECASE)
_WSLCONFIG_KEYS = ('networkingMode', 'localhostForwarding', 'dnsTunneling', 'firewall', 'autoProxy')


class HyperVSwitchCollector(BaseCollector):
    """Сборщик виртуальных коммутаторов Hyper-V, адаптеров хоста и VLAN."""

    name = 'hyperv'
    source = 'PowerShell: Get-VMSwitch, Get-VMNetworkAdapter -ManagementOS, Get-VMNetworkAdapterVlan'

    _PROBE = "Get-Command Get-VMSwitch -ErrorAction SilentlyContinue | Select-Object Name | ConvertTo-Json -Compress"
    _SWITCH = ("Get-VMSwitch | Select-Object Name,"
               f"{enum_prop('Id')},{enum_prop('SwitchType')},NetAdapterInterfaceDescription,"
               "@{n='NetAdapterInterfaceGuid';e={@($_.NetAdapterInterfaceGuid | ForEach-Object { [string]$_ })}},"
               f"AllowManagementOS,IovEnabled,{enum_prop('BandwidthReservationMode')},Notes "
               "| ConvertTo-Json -Depth 3 -Compress")
    _VNIC = ("Get-VMNetworkAdapter -ManagementOS | Select-Object Name,SwitchName,MacAddress,"
             "@{n='Status';e={@($_.Status | ForEach-Object { [string]$_ })}} | ConvertTo-Json -Depth 3 -Compress")
    _VLAN = ("Get-VMNetworkAdapterVlan -ManagementOS | Select-Object "
             "@{n='AdapterName';e={$_.ParentAdapter.Name}},"
             f"{enum_prop('OperationMode')},AccessVlanId,NativeVlanId,"
             "@{n='AllowedVlanIdList';e={@($_.AllowedVlanIdList)}} | ConvertTo-Json -Depth 3 -Compress")

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        probe = self.runner.run_json(self._PROBE)
        if not probe.ok:
            result.status = STATUS_SOURCE_UNAVAILABLE
            result.errors.append(f'Проверка наличия Hyper-V не выполнена: {probe.error}')
            return
        if not probe.data:
            result.status = STATUS_NOT_INSTALLED
            result.notes.append('Модуль Hyper-V PowerShell (Get-VMSwitch) не найден: компонент не установлен '
                                'или не поддерживается редакцией Windows. Это не означает отсутствие сети.')
            return
        sw = self._query(result, self._SWITCH, 'Get-VMSwitch')
        if sw is None:
            result.status = STATUS_DATA_UNAVAILABLE if result.needs_elevation else STATUS_ERROR
            return
        vnic = self._query(result, self._VNIC, 'Get-VMNetworkAdapter -ManagementOS')
        vlan = self._query(result, self._VLAN, 'Get-VMNetworkAdapterVlan -ManagementOS')
        vlan_by_adapter = {str(v.get('AdapterName')): v for v in (vlan.data if vlan else [])}
        host_by_switch: Dict[str, List[Dict[str, Any]]] = {}
        vnics: List[Dict[str, Any]] = []
        stamp = now_iso()
        for row in (vnic.data if vnic else []):
            v = vlan_by_adapter.get(str(row.get('Name')), {})
            props = {'name': row.get('Name') or '', 'switch_name': row.get('SwitchName') or '',
                     'mac': normalize_mac(row.get('MacAddress')), 'status': as_list(row.get('Status')),
                     'vlan_mode': v.get('OperationMode') or '', 'vlan_access_id': v.get('AccessVlanId'),
                     'vlan_native_id': v.get('NativeVlanId'), 'vlan_allowed': as_list(v.get('AllowedVlanIdList'))}
            vnics.append(make_item(KIND_VNIC, f"vnic:{props['switch_name']}|{props['name']}".lower(),
                                   props['name'], 'Get-VMNetworkAdapter', props, row, stamp))
            host_by_switch.setdefault(props['switch_name'], []).append(props)
        for row in sw.data:
            sid = str(row.get('Id') or '').strip('{}').lower()
            stype = normalize_switch_type(row.get('SwitchType'))
            name = str(row.get('Name') or '')
            props = {'name': name, 'id': sid, 'switch_type': stype, 'mode': stype.lower(),
                     'bound_adapter_description': row.get('NetAdapterInterfaceDescription') or '',
                     'bound_adapter_guids': [str(g).strip('{}').lower() for g in as_list(row.get('NetAdapterInterfaceGuid'))],
                     'allow_management_os': row.get('AllowManagementOS'), 'iov_enabled': row.get('IovEnabled'),
                     'bandwidth_mode': row.get('BandwidthReservationMode') or '', 'notes': row.get('Notes') or '',
                     'host_adapters': host_by_switch.get(name, [])}
            result.items.append(make_item(KIND_SWITCH, sid or f'name:{name.lower()}', name, 'Get-VMSwitch', props, row, stamp))
        result.extra['virtual_adapters'] = vnics
        result.status = STATUS_PARTIAL if (vnic is None or vlan is None) else STATUS_OK


class NatConfigurationCollector(BaseCollector):
    """Сборщик NAT-конфигураций, доступных через модуль NetNat (WinNAT)."""

    name = 'nat'
    source = 'PowerShell: Get-NetNat, Get-NetNatStaticMapping'

    _PROBE = "Get-Command Get-NetNat -ErrorAction SilentlyContinue | Select-Object Name | ConvertTo-Json -Compress"
    _NAT = ("Get-NetNat | Select-Object Name,InternalIPInterfaceAddressPrefix,ExternalIPInterfaceAddressPrefix,"
            f"Active,{enum_prop('Store')},IcmpQueryTimeout,TcpEstablishedConnectionTimeout,"
            "TcpTransientConnectionTimeout,UdpIdleSessionTimeout,UdpInboundRefresh | ConvertTo-Json -Depth 3 -Compress")
    _MAP = ("Get-NetNatStaticMapping | Select-Object NatName,StaticMappingID,"
            f"{enum_prop('Protocol')},ExternalIPAddress,ExternalPort,InternalIPAddress,InternalPort "
            "| ConvertTo-Json -Depth 3 -Compress")

    _LIMITATION = ('Get-NetNat отражает только WinNAT. NAT, который создают ICS (Default Switch) и сеть WSL2 '
                   '(через HNS), может не отображаться: пустой результат не означает отсутствие NAT вообще.')

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        probe = self.runner.run_json(self._PROBE)
        if not probe.ok:
            result.status = STATUS_SOURCE_UNAVAILABLE
            result.errors.append(f'Проверка модуля NetNat не выполнена: {probe.error}')
            return
        if not probe.data:
            result.status = STATUS_SOURCE_UNAVAILABLE
            result.notes.append('Командлет Get-NetNat недоступен (модуль NetNat отсутствует). ' + self._LIMITATION)
            return
        nat = self._query(result, self._NAT, 'Get-NetNat')
        if nat is None:
            result.status = STATUS_DATA_UNAVAILABLE if result.needs_elevation else STATUS_ERROR
            return
        mappings = self._query(result, self._MAP, 'Get-NetNatStaticMapping') if nat.data else None
        stamp = now_iso()
        for row in nat.data:
            name = str(row.get('Name') or '')
            own = [m for m in (mappings.data if mappings else []) if m.get('NatName') == name]
            props = {'name': name, 'internal_prefix': row.get('InternalIPInterfaceAddressPrefix') or '',
                     'external_prefix': row.get('ExternalIPInterfaceAddressPrefix') or '', 'active': row.get('Active'),
                     'store': row.get('Store') or '', 'static_mappings': own,
                     'timeouts': {k: row.get(k) for k in ('IcmpQueryTimeout', 'TcpEstablishedConnectionTimeout',
                                                          'TcpTransientConnectionTimeout', 'UdpIdleSessionTimeout',
                                                          'UdpInboundRefresh')},
                     'related_switches': [], 'related_interfaces': []}
            result.items.append(make_item(KIND_NAT, f'nat:{name.lower()}', name, 'Get-NetNat', props, row, stamp))
        result.notes.append(self._LIMITATION)
        result.status = STATUS_PARTIAL if (nat.data and mappings is None) else STATUS_OK


def parse_wsl_list(text: str) -> List[Dict[str, Any]]:
    """Разбирает вывод `wsl --list --verbose` независимо от локализации.

    Args:
        text: Декодированный stdout.

    Returns:
        List[Dict[str, Any]]: [{'name', 'state', 'state_raw', 'version', 'is_default'}].
    """
    distros: List[Dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        raw = line.rstrip()
        if not raw.strip():
            continue
        is_default = raw.lstrip().startswith('*')
        tokens = raw.replace('*', ' ', 1).split()
        if len(tokens) < 3 or not tokens[-1].isdigit():
            continue
        state_raw = tokens[-2]
        state = 'running' if _RUNNING_RE.search(state_raw) else 'stopped' if _STOPPED_RE.search(state_raw) else state_raw
        distros.append({'name': ' '.join(tokens[:-2]), 'state': state, 'state_raw': state_raw,
                        'version': int(tokens[-1]), 'is_default': is_default})
    return distros


def read_wslconfig(path: Path) -> Dict[str, str]:
    """Читает ключи секции [wsl2] файла .wslconfig (read-only).

    Args:
        path: Путь к .wslconfig.

    Returns:
        Dict[str, str]: Найденные ключи из набора _WSLCONFIG_KEYS; пустой словарь, если файла нет.
    """
    if not path.is_file():
        return {}
    parser = configparser.ConfigParser(strict=False, allow_no_value=True, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment]
    try:
        parser.read_string(path.read_text(encoding='utf-8-sig', errors='replace'))
    except configparser.Error:
        return {}
    if not parser.has_section('wsl2'):
        return {}
    return {k: str(parser.get('wsl2', k)) for k in _WSLCONFIG_KEYS if parser.has_option('wsl2', k)}


class WslNetworkCollector(BaseCollector):
    """Сборщик сведений о WSL и его сетевых компонентах Windows."""

    name = 'wsl'
    source = 'wsl.exe --status/--list --verbose/--version, .wslconfig, интерфейсы Windows'

    def __init__(self, runner: PowerShellRunner, wslconfig_path: Optional[Path] = None) -> None:
        """Инициализирует сборщик.

        Args:
            runner: Раннер PowerShell/wsl.exe.
            wslconfig_path: Путь к .wslconfig (по умолчанию ~/.wslconfig).
        """
        super().__init__(runner)
        self.wslconfig_path = wslconfig_path or (Path.home() / '.wslconfig')

    def _collect(self, result: CollectorResult, ctx: Dict[str, CollectorResult]) -> None:
        if not self.runner.which_wsl():
            result.status = STATUS_NOT_INSTALLED
            result.notes.append('wsl.exe не найден: WSL не установлен. Зависимые сборщики не запускались.')
            return
        listing = self.runner.run_wsl(('--list', '--verbose'))
        combined = f'{listing.text}\n{listing.stderr}'
        distros: List[Dict[str, Any]] = []
        if listing.timed_out:
            result.status = STATUS_SOURCE_UNAVAILABLE
            result.errors.append(listing.error)
            return
        if listing.ok:
            distros = parse_wsl_list(listing.text)
        elif _NO_DISTROS_RE.search(combined):
            result.notes.append('WSL установлен, дистрибутивы не зарегистрированы.')
        elif _NOT_INSTALLED_RE.search(combined):
            result.status = STATUS_NOT_INSTALLED
            result.notes.append('wsl.exe сообщает, что WSL не установлен.')
            return
        else:
            result.status = STATUS_ERROR
            result.errors.append(f'wsl --list --verbose: {listing.error}; {combined.strip()[:200]}')
            return

        status = self.runner.run_wsl(('--status',))
        version = self.runner.run_wsl(('--version',))
        default_distro = default_version = ''
        if status.ok:
            m = re.search(r'(?:Default Distribution|Дистрибутив по умолчанию)\s*[:：]\s*(.+)', status.text)
            default_distro = m.group(1).strip() if m else ''
            m = re.search(r'(?:Default Version|Версия по умолчанию)\s*[:：]\s*(\d+)', status.text)
            default_version = m.group(1) if m else ''
        else:
            result.notes.append('wsl --status недоступен (возможно, старая версия WSL).')
        wsl_version = ''
        if version.ok:
            m = re.search(r'\d+\.\d+\.\d+(?:\.\d+)?', version.text)
            wsl_version = m.group(0) if m else ''

        config = read_wslconfig(self.wslconfig_path)
        explicit_mode = config.get('networkingMode', '').strip().lower()
        if not explicit_mode:
            result.notes.append('networkingMode не задан в .wslconfig: режим по умолчанию зависит от версии WSL '
                                'и Windows, достоверно не определён.')
        interfaces, switch_names, nat_names, deps_ok = self._windows_side(ctx)
        if not deps_ok:
            result.notes.append('Сведения об интерфейсах Windows, связанных с WSL, получены не полностью '
                                '(адаптеры/IP-конфигурация недоступны).')
        stamp = now_iso()
        env = {'installed': True, 'wsl_version': wsl_version, 'default_distro': default_distro,
               'default_wsl_version': default_version, 'networking_mode': explicit_mode or 'unknown',
               'mode_source': '.wslconfig' if explicit_mode else 'не определён', 'wslconfig': config,
               'interfaces': interfaces, 'switches': switch_names, 'nat': nat_names,
               'distro_count': len(distros), 'running_count': sum(1 for d in distros if d['state'] == 'running')}
        result.items.append(make_item(KIND_WSL, 'wsl:environment', 'WSL', 'wsl.exe', env,
                                      {'list': listing.text, 'status': status.text, 'version': version.text}, stamp))
        for d in distros:
            result.items.append(make_item(KIND_WSL_DISTRO, f"distro:{d['name'].lower()}", d['name'], 'wsl.exe --list',
                                          {k: d[k] for k in ('name', 'state', 'version', 'is_default')}, d, stamp))
        result.status = STATUS_OK if deps_ok else STATUS_PARTIAL

    @staticmethod
    def _windows_side(ctx: Dict[str, CollectorResult]) -> tuple:
        """Определяет интерфейсы, коммутаторы и NAT Windows, связанные с WSL."""
        adapters = ctx.get('adapters')
        ip_cfg = ctx.get('ip_config')
        deps_ok = bool(adapters and ip_cfg and adapters.status in (STATUS_OK, STATUS_PARTIAL)
                       and ip_cfg.status in (STATUS_OK, STATUS_PARTIAL))
        wsl_adapters = [a for a in (adapters.items if adapters else []) if a['props'].get('adapter_class') == 'wsl']
        ip_by_alias = {i['props'].get('alias'): i for i in (ip_cfg.items if ip_cfg else [])}
        interfaces: List[Dict[str, Any]] = []
        for a in wsl_adapters:
            ip = ip_by_alias.get(a['props']['name'], {}).get('props', {})
            interfaces.append({'name': a['props']['name'], 'status': a['props']['status'], 'mac': a['props']['mac'],
                               'ipv4': [x['address'] for x in ip.get('ipv4', [])],
                               'ipv6': [x['address'] for x in ip.get('ipv6', [])]})
        hv = ctx.get('hyperv')
        switch_names = [s['props']['name'] for s in (hv.items if hv else []) if re.search(r'\bwsl\b', s['props']['name'], re.I)]
        nat_names: List[str] = []
        nat = ctx.get('nat')
        wsl_ip_items = [i for a in wsl_adapters for i in [ip_by_alias.get(a['props']['name'])] if i]
        for n in (nat.items if nat else []):
            if link_nat_to_interfaces(n['props']['internal_prefix'], wsl_ip_items):
                nat_names.append(n['props']['name'])
        return interfaces, switch_names, nat_names, deps_ok

