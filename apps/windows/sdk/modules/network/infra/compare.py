# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Snapshot Comparison
# =============================================================================
# Description:
#   Приведение снимка к плоскому списку объектов и сравнение двух снимков с учётом
#   идентичности объектов и полноты сбора. Если источник в любом из снимков
#   не дал полных данных (статус != ok), для его объектов НЕ фиксируются
#   added/removed (отсутствие данных не равно удалению); изменения свойств
#   объектов, присутствующих в обоих снимках, фиксируются всегда.
#   Дополнительно фиксируется смена статуса самого источника (status_changed).
#
# Usage Examples:
#   diff = compare_snapshots(snapshot_a, snapshot_b)
#
# File: compare.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import (COMPLETE_STATUSES, KIND_ADAPTER, KIND_IP, KIND_IP_IFACE, KIND_NAT, KIND_ROUTE,
                     KIND_SOURCE, KIND_SWITCH, KIND_VNIC, KIND_WSL, KIND_WSL_DISTRO, NetworkChange)

# Ключ набора данных снимка -> тип объекта (для наборов, не требующих разворачивания).
_DATA_KINDS = {'adapters': KIND_ADAPTER, 'routes': KIND_ROUTE, 'switches': KIND_SWITCH,
               'virtual_adapters': KIND_VNIC, 'nat': KIND_NAT}


def snapshot_objects(snapshot: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Преобразует снимок в словарь объектов {(kind, id): {name, props}}.

    IP-конфигурация разворачивается в объекты по адресам (ip_address) и объекты
    интерфейсов с DNS/шлюзами/метриками (ip_interface).

    Args:
        snapshot: Снимок (поле data с наборами объектов).

    Returns:
        Dict[Tuple[str, str], Dict[str, Any]]: Объекты снимка.
    """
    data = snapshot.get('data', {})
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for key, kind in _DATA_KINDS.items():
        for item in data.get(key, []):
            out[(kind, item['id'])] = {'name': item['name'], 'props': item['props']}
    for item in data.get('ip_config', []):
        p = item['props']
        for fam in ('ipv4', 'ipv6'):
            for rec in p.get(fam, []):
                out[(KIND_IP, f"{item['id']}|{rec['address']}")] = {
                    'name': f"{rec['address']} ({item['name']})",
                    'props': {'address': rec['address'], 'prefix_length': rec['prefix_length'], 'interface': item['name'],
                              'state': rec.get('state')}}
        out[(KIND_IP_IFACE, item['id'])] = {
            'name': item['name'], 'props': {k: p.get(k) for k in ('dns', 'gateways', 'metric_v4', 'metric_v6', 'dhcp_v4')}}
    for item in data.get('wsl', []):
        kind = KIND_WSL if item['kind'] == KIND_WSL else KIND_WSL_DISTRO
        out[(kind, item['id'])] = {'name': item['name'], 'props': item['props']}
    return out


def _diff_props(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Возвращает изменившиеся ключи {key: {'old', 'new'}}."""
    return {k: {'old': old.get(k), 'new': new.get(k)} for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}


def _finding_keys(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Ключ диагностического результата: код правила + затронутые объекты."""
    return {f"{f['rule_code']}|{'/'.join(sorted(f.get('affected', [])))}|{f.get('title', '')}": f
            for f in snapshot.get('findings', [])}


def compare_snapshots(base: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    """Сравнивает два снимка.

    Args:
        base: Более ранний (базовый) снимок.
        target: Сравниваемый снимок.

    Returns:
        Dict[str, Any]: {'base_id', 'target_id', 'changes', 'summary', 'skipped', 'findings'}.
            skipped — виды объектов, для которых added/removed не вычислялись из-за неполноты данных.
    """
    sources_a, sources_b = base.get('sources', {}), target.get('sources', {})
    objs_a, objs_b = snapshot_objects(base), snapshot_objects(target)
    changes: List[NetworkChange] = []
    skipped: Dict[str, str] = {}

    for source in sorted(set(sources_a) | set(sources_b)):
        sa, sb = sources_a.get(source, {}).get('status'), sources_b.get(source, {}).get('status')
        if sa != sb:
            changes.append(NetworkChange('status_changed', 'source', source, source, {'old': sa, 'new': sb}))

    def complete(kind: str) -> bool:
        src = KIND_SOURCE[kind]
        ok = (sources_a.get(src, {}).get('status') in COMPLETE_STATUSES
              and sources_b.get(src, {}).get('status') in COMPLETE_STATUSES)
        if not ok and kind not in skipped:
            skipped[kind] = (f"источник «{src}»: статус {sources_a.get(src, {}).get('status')} → "
                             f"{sources_b.get(src, {}).get('status')}; added/removed не вычислялись")
        return ok

    for key in sorted(set(objs_a) | set(objs_b)):
        kind, oid = key
        a, b = objs_a.get(key), objs_b.get(key)
        if a and b:
            delta = _diff_props(a['props'], b['props'])
            if delta:
                changes.append(NetworkChange('changed', kind, oid, b['name'], delta))
        elif b and complete(kind):
            changes.append(NetworkChange('added', kind, oid, b['name']))
        elif a and complete(kind):
            changes.append(NetworkChange('removed', kind, oid, a['name']))

    fa, fb = _finding_keys(base), _finding_keys(target)
    summary: Dict[str, int] = {}
    for c in changes:
        summary[c.change_type] = summary.get(c.change_type, 0) + 1
    return {'base_id': base.get('id'), 'target_id': target.get('id'), 'changes': [c.to_dict() for c in changes],
            'summary': summary, 'skipped': skipped,
            'findings': {'new': [fb[k] for k in sorted(set(fb) - set(fa))],
                         'resolved': [fa[k] for k in sorted(set(fa) - set(fb))]}}

