# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Diagnostic Rules
# =============================================================================
# Description:
#   Диагностические правила анализа собранной сетевой конфигурации. Правила
#   только читают данные и никогда не изменяют настройки сети. Каждое правило
#   выдаёт Finding с кодом, фактами, источником и рекомендациями. Правила
#   пропускаются, если нужный источник не дал полных данных (вместо ложных срабатываний
#   фиксируется отдельный результат NET090/NET091).
#
# Usage Examples:
#   findings = run_diagnostics(results)
#
# File: diagnostics.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List

from .classification import is_link_local_or_loopback, switch_name_of_alias
from .models import (CollectorResult, Finding, STATUS_DATA_UNAVAILABLE, STATUS_ERROR, STATUS_NOT_INSTALLED,
                     STATUS_OK, STATUS_PARTIAL, STATUS_SOURCE_UNAVAILABLE, now_iso)

_EXPECTED_ADAPTER_STATES = {'up', 'disconnected', 'disabled', 'dormant', 'not present'}
_SKIP_ROUTE_PREFIXES = ('224.', 'ff00::', '255.255.255.255', 'fe80::')


def _complete(results: Dict[str, CollectorResult], *names: str) -> bool:
    """True, если все перечисленные источники вернули полные данные."""
    return all(n in results and results[n].status == STATUS_OK for n in names)


def _finding(code: str, title: str, desc: str, severity: str, affected: List[str], facts: Dict[str, Any],
             source: str, recs: List[str], stamp: str) -> Finding:
    return Finding(code, title, desc, severity, affected, facts, source, stamp, recs)


def rule_source_status(results: Dict[str, CollectorResult], stamp: str) -> List[Finding]:
    """NET090/NET091: недоступность источников и частичный/ошибочный сбор."""
    out: List[Finding] = []
    for name, res in results.items():
        base = {'status': res.status, 'errors': res.errors, 'notes': res.notes, 'needs_elevation': res.needs_elevation}
        if res.status == STATUS_NOT_INSTALLED:
            out.append(_finding('NET090', f'Компонент не установлен: {name}', 'Источник данных отсутствует в системе; '
                                'это не ошибка конфигурации сети.', 'info', [name], base, res.source,
                                ['Если компонент нужен, установите его штатными средствами Windows.'], stamp))
        elif res.status in (STATUS_SOURCE_UNAVAILABLE, STATUS_DATA_UNAVAILABLE):
            hint = ['Запустите ai-tc с повышенными правами для получения полных данных.'] if res.needs_elevation else \
                   ['Проверьте наличие PowerShell-модуля и повторите сбор.']
            out.append(_finding('NET090', f'Источник недоступен: {name}', 'Данные источника не получены; отсутствие '
                                'объектов в отчёте нельзя трактовать как их отсутствие в системе.', 'warning', [name],
                                base, res.source, hint, stamp))
        elif res.status == STATUS_PARTIAL:
            out.append(_finding('NET091', f'Частичный сбор: {name}', 'Часть запросов источника завершилась ошибкой.',
                                'warning', [name], base, res.source, ['Просмотрите ошибки сбора и повторите.'], stamp))
        elif res.status == STATUS_ERROR:
            out.append(_finding('NET091', f'Сбор завершился ошибкой: {name}', 'Источник вернул ошибку.', 'error',
                                [name], base, res.source, ['Проверьте журнал приложения и доступность PowerShell.'], stamp))
    return out


def rule_adapter_state(results: Dict[str, CollectorResult], stamp: str) -> List[Finding]:
    """NET001: адаптер в неожиданном состоянии."""
    adapters = results.get('adapters')
    if not adapters or adapters.status not in (STATUS_OK, STATUS_PARTIAL):
        return []
    out = []
    for a in adapters.items:
        state = str(a['props'].get('status', '')).lower()
        if state and state not in _EXPECTED_ADAPTER_STATES:
            out.append(_finding('NET001', 'Адаптер в неожиданном состоянии', f"Адаптер «{a['name']}» имеет статус «{a['props']['status']}».",
                                'warning', [a['name']], {'status': a['props']['status'], 'media_state': a['props'].get('media_state')},
                                'Get-NetAdapter', ['Проверьте драйвер и состояние устройства в диспетчере устройств.'], stamp))
    return out


def rule_duplicate_ip(results: Dict[str, CollectorResult], stamp: str) -> List[Finding]:
    """NET002: одинаковые IP-адреса на разных интерфейсах / состояние Duplicate."""
    ip_cfg = results.get('ip_config')
    if not ip_cfg or ip_cfg.status not in (STATUS_OK, STATUS_PARTIAL):
        return []
    owners: Dict[str, List[str]] = defaultdict(list)
    out = []
    for item in ip_cfg.items:
        for rec in item['props']['ipv4'] + item['props']['ipv6']:
            addr = str(rec['address']).split('%')[0]
            if str(rec.get('state', '')).lower() == 'duplicate':
                out.append(_finding('NET002', 'Windows обнаружила дублирующийся IP-адрес', f"Адрес {addr} на «{item['name']}» в состоянии Duplicate.",
                                    'error', [item['name']], {'address': addr, 'state': rec['state']}, 'Get-NetIPAddress',
                                    ['Найдите второе устройство с этим адресом в сети.'], stamp))
            if not is_link_local_or_loopback(addr):
                owners[addr].append(item['name'])
    for addr, names in owners.items():
        if len(set(names)) > 1:
            out.append(_finding('NET002', 'Потенциальный конфликт IP-адресов', f'Адрес {addr} назначен нескольким интерфейсам хоста.',
                                'warning', sorted(set(names)), {'address': addr, 'interfaces': sorted(set(names))},
                                'Get-NetIPAddress', ['Проверьте, не вызвано ли это мостом или общим доступом к подключению.'], stamp))
    return out


def rule_routes(results: Dict[str, CollectorResult], stamp: str) -> List[Finding]:
    """NET003/NET004/NET005: дубли маршрутов, отсутствие default route, конфликт метрик."""
    routes, ip_cfg, adapters = results.get('routes'), results.get('ip_config'), results.get('adapters')
    if not routes or routes.status not in (STATUS_OK, STATUS_PARTIAL):
        return []
    out: List[Finding] = []
    seen: Dict[str, int] = defaultdict(int)
    by_prefix: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    defaults: Dict[str, List[Dict[str, Any]]] = {'IPv4': [], 'IPv6': []}
    for r in routes.items:
        p = r['props']
        seen[r['id']] += 1
        if p['is_default']:
            defaults[p['family']].append(p)
        if not p['destination_prefix'].startswith(_SKIP_ROUTE_PREFIXES) and not p['destination_prefix'].endswith(('/32', '/128')):
            by_prefix[p['destination_prefix']].append(p)
    for rid, count in seen.items():
        if count > 1:
            out.append(_finding('NET003', 'Дублирующийся маршрут', f'Маршрут {rid} встречается {count} раз.', 'warning', [rid],
                                {'route': rid, 'count': count}, 'Get-NetRoute', ['Проверьте постоянные и активные маршруты (route print).'], stamp))
    for prefix, items in by_prefix.items():
        metrics = [i['effective_metric'] for i in items]
        best = [i for i in items if i['effective_metric'] == min(metrics)]
        if len({i['interface_id'] for i in best}) > 1:
            out.append(_finding('NET005', 'Потенциальный конфликт метрик маршрутов',
                                f'Маршрут {prefix} через несколько интерфейсов с одинаковой минимальной метрикой {min(metrics)}.',
                                'warning', sorted({i['interface_alias'] for i in items}),
                                {'prefix': prefix, 'metric': min(metrics), 'interfaces': sorted({i['interface_alias'] for i in items})},
                                'Get-NetRoute', ['Это может быть штатной балансировкой; при проблемах задайте различные метрики интерфейсов.'], stamp))
    if _complete(results, 'routes', 'ip_config', 'adapters'):
        up = {a['id'] for a in adapters.items if str(a['props'].get('status')).lower() == 'up'}  # type: ignore[union-attr]
        has_ip4 = [i for i in ip_cfg.items if i['id'] in up and any(  # type: ignore[union-attr]
            not is_link_local_or_loopback(x['address']) for x in i['props']['ipv4'])]
        if has_ip4 and not defaults['IPv4']:
            out.append(_finding('NET004', 'Отсутствует маршрут по умолчанию IPv4', 'Есть активные интерфейсы с IPv4-адресом, но нет маршрута 0.0.0.0/0.',
                                'warning', [i['name'] for i in has_ip4], {'interfaces': [i['name'] for i in has_ip4]},
                                'Get-NetRoute', ['Если нужен доступ за пределы подсети — проверьте шлюз в настройках адаптера.'], stamp))
    for fam, items in defaults.items():
        if len(items) > 1:
            out.append(_finding('NET004', f'Несколько маршрутов по умолчанию {fam}', 'Несколько default-маршрутов — часто штатно (Wi-Fi + Ethernet); '
                                'важны различия метрик.', 'info', sorted({i['interface_alias'] for i in items}),
                                {'routes': [{'interface': i['interface_alias'], 'metric': i['effective_metric']} for i in items]},
                                'Get-NetRoute', ['Определите предпочитаемый интерфейс по минимальной метрике.'], stamp))
    return out


def rule_virtual(results: Dict[str, CollectorResult], stamp: str) -> List[Finding]:
    """NET006/NET007/NET008/NET011: коммутаторы, NAT, WSL — полнота и согласованность."""
    out: List[Finding] = []
    hv, adapters, nat, wsl, ip_cfg = (results.get(k) for k in ('hyperv', 'adapters', 'nat', 'wsl', 'ip_config'))
    if hv and hv.status in (STATUS_OK, STATUS_PARTIAL) and adapters and adapters.status == STATUS_OK:
        by_guid = {a['props']['interface_guid']: a for a in adapters.items if a['props'].get('interface_guid')}
        by_desc = {a['props']['description'].lower(): a for a in adapters.items}
        aliases = {a['props']['name'].lower() for a in adapters.items}
        switch_names = {s['props']['name'].lower() for s in hv.items}
        for s in hv.items:
            p = s['props']
            if p['switch_type'] == 'External':
                bound = next((by_guid[g] for g in p['bound_adapter_guids'] if g in by_guid), None) or by_desc.get(p['bound_adapter_description'].lower())
                if not p['bound_adapter_description'] and not p['bound_adapter_guids']:
                    out.append(_finding('NET007', 'Внешний коммутатор без физического адаптера', f"Коммутатор «{p['name']}» внешний, привязка не указана.",
                                        'warning', [p['name']], {'switch': p}, 'Get-VMSwitch', ['Проверьте привязку в диспетчере виртуальных коммутаторов.'], stamp))
                elif bound is None:
                    out.append(_finding('NET006', 'Коммутатор ссылается на недоступный адаптер', f"Адаптер «{p['bound_adapter_description']}» коммутатора «{p['name']}» не найден среди адаптеров.",
                                        'error', [p['name']], {'bound': p['bound_adapter_description'], 'guids': p['bound_adapter_guids']},
                                        'Get-VMSwitch + Get-NetAdapter', ['Проверьте, не удалён/отключён ли физический адаптер.'], stamp))
                elif str(bound['props']['status']).lower() in ('disabled', 'not present', 'disconnected'):
                    out.append(_finding('NET006', 'Коммутатор привязан к неактивному адаптеру', f"Адаптер «{bound['name']}» коммутатора «{p['name']}» в состоянии {bound['props']['status']}.",
                                        'warning', [p['name'], bound['name']], {'adapter_status': bound['props']['status']},
                                        'Get-VMSwitch + Get-NetAdapter', ['Включите/подключите адаптер или перепривяжите коммутатор вручную.'], stamp))
            elif p['switch_type'] == 'Internal' and f"vethernet ({p['name'].lower()})" not in aliases:
                out.append(_finding('NET007', 'Неполная конфигурация внутреннего коммутатора', f"Для «{p['name']}» не найден адаптер хоста vEthernet.",
                                    'warning', [p['name']], {'switch': p['name']}, 'Get-VMSwitch + Get-NetAdapter',
                                    ['Проверьте AllowManagementOS и состояние адаптера хоста.'], stamp))
        for v in hv.extra.get('virtual_adapters', []):
            if v['props']['switch_name'] and v['props']['switch_name'].lower() not in switch_names:
                out.append(_finding('NET008', 'Несогласованная связь адаптера хоста и коммутатора', f"Адаптер «{v['name']}» ссылается на неизвестный коммутатор «{v['props']['switch_name']}».",
                                    'warning', [v['name']], {'switch_name': v['props']['switch_name']}, 'Get-VMNetworkAdapter',
                                    ['Повторите сбор; при повторении проверьте Hyper-V Manager.'], stamp))
        for a in adapters.items:
            sw = switch_name_of_alias(a['props']['name'])
            if sw and a['props'].get('adapter_class') in ('hyperv_virtual', 'wsl') and sw.lower() not in switch_names:
                out.append(_finding('NET008', 'Виртуальный адаптер без коммутатора', f"«{a['name']}» похож на адаптер Hyper-V, но коммутатор «{sw}» не найден (возможно, создан HNS/WSL).",
                                    'info', [a['name']], {'signals': a['props'].get('signals')}, 'Get-NetAdapter + Get-VMSwitch',
                                    ['Для WSL/Default Switch такое поведение может быть штатным.'], stamp))
    if nat and nat.status in (STATUS_OK, STATUS_PARTIAL) and ip_cfg and ip_cfg.status == STATUS_OK:
        for n in nat.items:
            if not n['props']['related_interfaces']:
                out.append(_finding('NET007', 'NAT без интерфейса во внутренней подсети', f"Для NAT «{n['name']}» ({n['props']['internal_prefix']}) нет интерфейса с адресом из префикса.",
                                    'warning', [n['name']], {'prefix': n['props']['internal_prefix']}, 'Get-NetNat + Get-NetIPAddress',
                                    ['Проверьте шлюзовой адрес на внутреннем виртуальном интерфейсе.'], stamp))
    if wsl and wsl.status in (STATUS_OK, STATUS_PARTIAL) and wsl.items and adapters and adapters.status == STATUS_OK:
        env = wsl.items[0]['props']
        if env.get('running_count', 0) > 0 and not env.get('interfaces'):
            out.append(_finding('NET011', 'WSL запущен, но интерфейс Windows не найден', 'Есть запущенные дистрибутивы, но среди адаптеров нет интерфейса, определяемого как WSL '
                                '(возможен режим mirrored/bridged или иное имя).', 'info', ['WSL'],
                                {'networking_mode': env.get('networking_mode'), 'running': env.get('running_count')},
                                'wsl.exe + Get-NetAdapter', ['Проверьте networkingMode в .wslconfig.'], stamp))
    return out


_RULES: List[Callable[[Dict[str, CollectorResult], str], List[Finding]]] = [
    rule_source_status, rule_adapter_state, rule_duplicate_ip, rule_routes, rule_virtual]


def run_diagnostics(results: Dict[str, CollectorResult]) -> List[Finding]:
    """Выполняет все диагностические правила (только чтение).

    Args:
        results: Результаты сборщиков (после нормализации).

    Returns:
        List[Finding]: Найденные ситуации, отсортированные по важности.
    """
    stamp = now_iso()
    order = {'critical': 0, 'error': 1, 'warning': 2, 'info': 3}
    findings: List[Finding] = []
    for rule in _RULES:
        findings.extend(rule(results, stamp))
    return sorted(findings, key=lambda f: (order.get(f.severity, 9), f.rule_code))

