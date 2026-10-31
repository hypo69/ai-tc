# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Classification & Normalization Helpers
# =============================================================================
# Description:
#   Многопризнаковая классификация адаптеров (физический / Hyper-V / WSL2 /
#   прочий виртуальный), нормализация перечислений PowerShell, преобразование
#   префиксов в маски, связывание NAT с коммутаторами.
#   Совпадения только по имени адаптера недостаточно для вывода о назначении.
#
# File: classification.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, List, Optional, Tuple

HYPERV_MAC_OUI = '00-15-5D'
_VIRTUAL_VENDOR_RE = re.compile(r'vmware|virtualbox|vbox|tap-windows|wintun|wireguard|npcap|loopback|'
                                r'tunnel|teredo|isatap|6to4|vpn|zerotier|tailscale|miniport', re.IGNORECASE)
_WSL_NAME_RE = re.compile(r'\bwsl\b', re.IGNORECASE)
_VETH_RE = re.compile(r'^vEthernet \((.+)\)$', re.IGNORECASE)

_SWITCH_TYPES = {'0': 'Private', '1': 'Internal', '2': 'External',
                 'private': 'Private', 'internal': 'Internal', 'external': 'External'}


def normalize_switch_type(value: Any) -> str:
    """Приводит SwitchType (число или строка) к Private / Internal / External / Unknown."""
    return _SWITCH_TYPES.get(str(value).strip().lower(), 'Unknown')


def family_of_prefix(prefix: str) -> str:
    """Определяет семейство адресов по тексту префикса/адреса."""
    return 'IPv6' if ':' in str(prefix) else 'IPv4'


def prefix_to_mask(prefix_length: Any, family: str = 'IPv4') -> str:
    """Преобразует длину префикса в маску подсети (для IPv4) или возвращает пустую строку.

    Args:
        prefix_length: Длина префикса.
        family: 'IPv4' или 'IPv6'.

    Returns:
        str: Маска вида 255.255.255.0; для IPv6 и некорректных значений — ''.
    """
    try:
        length = int(prefix_length)
    except (TypeError, ValueError):
        return ''
    if family != 'IPv4' or not 0 <= length <= 32:
        return ''
    return str(ipaddress.IPv4Network(f'0.0.0.0/{length}').netmask)


def normalize_mac(value: Any) -> str:
    """Нормализует MAC-адрес к виду AA-BB-CC-DD-EE-FF (пустая строка, если не задан)."""
    text = re.sub(r'[^0-9A-Fa-f]', '', str(value or ''))
    if len(text) != 12:
        return ''
    return '-'.join(text[i:i + 2] for i in range(0, 12, 2)).upper()


def as_list(value: Any) -> List[Any]:
    """Приводит скаляр/None/список к списку (PowerShell возвращает одиночное значение без массива)."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def classify_adapter(raw: Dict[str, Any], switch_names: Optional[List[str]] = None) -> Tuple[str, List[str], str]:
    """Классифицирует адаптер по совокупности признаков.

    Args:
        raw: Сырые свойства Get-NetAdapter.
        switch_names: Имена виртуальных коммутаторов Hyper-V (если известны).

    Returns:
        Tuple[str, List[str], str]: (класс, список признаков, уверенность).
            Классы: physical, hyperv_virtual, wsl, virtual_other, unknown.
            Уверенность: high / medium / low.
    """
    name = str(raw.get('Name') or '')
    desc = str(raw.get('InterfaceDescription') or '')
    component = str(raw.get('ComponentID') or '').lower()
    mac = normalize_mac(raw.get('MacAddress'))
    hardware = raw.get('HardwareInterface')
    virtual_flag = raw.get('Virtual')

    hyperv_signals: List[str] = []
    if component == 'vms_pp':
        hyperv_signals.append('ComponentID=vms_pp')
    if 'hyper-v virtual ethernet' in desc.lower():
        hyperv_signals.append('описание: Hyper-V Virtual Ethernet Adapter')
    if mac.startswith(HYPERV_MAC_OUI):
        hyperv_signals.append('MAC OUI 00-15-5D (Microsoft Hyper-V)')

    name_signals: List[str] = []
    match = _VETH_RE.match(name)
    if match:
        name_signals.append('имя vEthernet (<коммутатор>)')
        if _WSL_NAME_RE.search(match.group(1)):
            name_signals.append('имя содержит WSL')
        if switch_names and match.group(1).lower() in {s.lower() for s in switch_names}:
            hyperv_signals.append(f'совпадение с коммутатором Hyper-V «{match.group(1)}»')
    if _WSL_NAME_RE.search(name) or _WSL_NAME_RE.search(desc):
        name_signals.append('WSL в имени/описании')

    other_signals: List[str] = []
    if virtual_flag is True:
        other_signals.append('Virtual=True')
    if _VIRTUAL_VENDOR_RE.search(desc) or _VIRTUAL_VENDOR_RE.search(name):
        other_signals.append('виртуальный драйвер/поставщик в описании')
    if hardware is False:
        other_signals.append('HardwareInterface=False')

    wsl_named = any('WSL' in s for s in name_signals)
    if wsl_named and hyperv_signals:
        return 'wsl', name_signals + hyperv_signals, 'high' if len(hyperv_signals) > 1 else 'medium'
    if hyperv_signals:
        return 'hyperv_virtual', name_signals + hyperv_signals, 'high' if len(hyperv_signals) > 1 else 'medium'
    if other_signals or name_signals:
        # Только имя (без независимых признаков) — низкая уверенность.
        conf = 'medium' if len(other_signals) > 1 else 'low'
        return 'virtual_other', name_signals + other_signals, conf
    if hardware is True:
        return 'physical', ['HardwareInterface=True'], 'high'
    return 'unknown', [], 'low'


def switch_name_of_alias(alias: str) -> str:
    """Извлекает имя коммутатора из alias вида 'vEthernet (Name)' (пустая строка, если не подходит)."""
    match = _VETH_RE.match(alias or '')
    return match.group(1) if match else ''


def is_link_local_or_loopback(address: str) -> bool:
    """True для link-local, loopback и APIPA адресов."""
    try:
        ip = ipaddress.ip_address(str(address).split('%')[0])
    except ValueError:
        return False
    return ip.is_link_local or ip.is_loopback


def link_nat_to_interfaces(nat_prefix: str, ip_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Находит интерфейсы, адрес которых входит во внутренний префикс NAT.

    Args:
        nat_prefix: InternalIPInterfaceAddressPrefix (например, 172.20.0.0/20).
        ip_items: Нормализованные записи IP-конфигурации интерфейсов.

    Returns:
        List[Dict[str, Any]]: [{'interface_id', 'alias', 'switch', 'address'}].
    """
    try:
        network = ipaddress.ip_network(nat_prefix, strict=False)
    except ValueError:
        return []
    found: List[Dict[str, Any]] = []
    for item in ip_items:
        props = item.get('props', {})
        for addr in props.get('ipv4', []) + props.get('ipv6', []):
            try:
                if ipaddress.ip_address(addr['address'].split('%')[0]) in network:
                    found.append({'interface_id': item['id'], 'alias': props.get('alias', ''),
                                  'switch': switch_name_of_alias(props.get('alias', '')),
                                  'address': addr['address']})
            except (ValueError, KeyError):
                continue
    return found

