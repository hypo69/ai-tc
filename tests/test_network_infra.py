# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - Network Infra (collectors, rules, history)
# =============================================================================
# Description:
#   Модульные тесты диагностики сетевой инфраструктуры: раннер PowerShell,
#   нормализация вывода, сборщики с подменяемыми источниками (без Hyper-V/WSL),
#   классификация, диагностические правила, сравнение и хранение снимков, сервис.
#
# File: test_network_infra.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:10:00
# =============================================================================

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.windows.sdk.modules.network.infra import compare as cmp_mod
from apps.windows.sdk.modules.network.infra.classification import (classify_adapter, link_nat_to_interfaces,
                                                                    prefix_to_mask)
from apps.windows.sdk.modules.network.infra.collectors_basic import (IpConfigurationCollector,
                                                                      NetworkAdapterCollector,
                                                                      RouteTableCollector)
from apps.windows.sdk.modules.network.infra.collectors_virtual import (HyperVSwitchCollector,
                                                                        NatConfigurationCollector,
                                                                        WslNetworkCollector, parse_wsl_list,
                                                                        read_wslconfig)
from apps.windows.sdk.modules.network.infra.diagnostics import run_diagnostics
from apps.windows.sdk.modules.network.infra.models import CollectorResult, now_iso
from apps.windows.sdk.modules.network.infra.normalize import (finalize_identities, link_nat,
                                                               refine_classification)
from apps.windows.sdk.modules.network.infra.ps_runner import (ForbiddenCommandError, PowerShellRunner,
                                                               PsResult, assert_read_only, decode_output,
                                                               normalize_json_output)
from apps.windows.sdk.modules.network.infra.service import NetworkInfraService, overall_status
from apps.windows.sdk.modules.network.infra.settings import InfraSettings
from apps.windows.sdk.modules.network.infra.store import NetworkInfraStore, SnapshotNotFound


class FakeRunner:
    """Подменяемый источник данных: ответы по подстроке скрипта."""

    def __init__(self, scripts=None, wsl=None, wsl_path='wsl.exe', delay=0.0):
        self.scripts, self.wsl, self.wsl_path, self.delay, self.calls = scripts or {}, wsl or {}, wsl_path, delay, 0

    def run_json(self, script, timeout=None):
        self.calls += 1
        time.sleep(self.delay)
        for key, val in self.scripts.items():
            if key in script:
                if isinstance(val, PsResult):
                    return val
                return PsResult(ok=True, data=val if isinstance(val, list) else [val])
        return PsResult(ok=False, error='unexpected script', stderr='unexpected')

    def run_wsl(self, args):
        val = self.wsl.get(tuple(args))
        return val if val is not None else PsResult(ok=False, return_code=1, error='n/a')

    def which_wsl(self):
        return self.wsl_path


ADAPTERS = [
    {'Name': 'Ethernet', 'InterfaceDescription': 'Intel(R) I219-V', 'ifIndex': 5, 'InterfaceGuid': '{AAAA-1}',
     'MacAddress': '10-20-30-40-50-60', 'Status': 'Up', 'HardwareInterface': True, 'Virtual': False, 'ComponentID': 'pci'},
    {'Name': 'vEthernet (WSL)', 'InterfaceDescription': 'Hyper-V Virtual Ethernet Adapter #2', 'ifIndex': 21,
     'InterfaceGuid': '{BBBB-2}', 'MacAddress': '00-15-5D-01-02-03', 'Status': 'Up', 'HardwareInterface': False,
     'Virtual': True, 'ComponentID': 'vms_pp'},
]
IP_ADDR = [
    {'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet', 'IPAddress': '10.0.0.4', 'PrefixLength': 24,
     'AddressFamily': 'IPv4', 'AddressState': 'Preferred', 'Type': 'Unicast', 'PrefixOrigin': 'Dhcp'},
    {'InterfaceIndex': 21, 'InterfaceAlias': 'vEthernet (WSL)', 'IPAddress': '172.20.0.1', 'PrefixLength': 20,
     'AddressFamily': 'IPv4', 'AddressState': 'Preferred', 'Type': 'Unicast', 'PrefixOrigin': 'Manual'},
]
ROUTES = [
    {'DestinationPrefix': '0.0.0.0/0', 'NextHop': '10.0.0.1', 'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet',
     'RouteMetric': 0, 'InterfaceMetric': 25},
    {'DestinationPrefix': '10.0.0.0/24', 'NextHop': '0.0.0.0', 'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet',
     'RouteMetric': 256, 'InterfaceMetric': 25},
]


def base_scripts():
    return {
        'Get-NetAdapter': ADAPTERS, 'Get-NetIPAddress': IP_ADDR, 'Get-DnsClientServerAddress': [
            {'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet', 'AddressFamily': 'IPv4', 'ServerAddresses': '8.8.8.8'}],
        'Get-NetIPInterface': [{'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet', 'AddressFamily': 'IPv4',
                                'InterfaceMetric': 25, 'Dhcp': 'Enabled', 'NlMtu': 1500, 'ConnectionState': 'Connected'}],
        'Get-NetIPConfiguration': [{'InterfaceIndex': 5, 'InterfaceAlias': 'Ethernet', 'Gateway4': '10.0.0.1', 'Gateway6': []}],
        'Get-NetRoute': ROUTES,
        'Get-Command Get-VMSwitch': [], 'Get-Command Get-NetNat': [{'Name': 'Get-NetNat'}], 'Get-NetNat |': [],
    }


# ----------------------------------------------------------------- раннер
def test_normalize_json_single_list_empty_invalid():
    assert normalize_json_output('{"a":1}') == [{'a': 1}]
    assert normalize_json_output('[{"a":1},{"a":2}]') == [{'a': 1}, {'a': 2}]
    assert normalize_json_output('  \n') == []
    assert normalize_json_output('null') == []
    with pytest.raises(ValueError):
        normalize_json_output('{broken')


def test_read_only_allowlist_blocks_mutations():
    assert_read_only('Get-NetAdapter | Select-Object Name | ConvertTo-Json')
    for bad in ('Set-NetIPAddress -IPAddress 1.1.1.1', 'Remove-NetRoute', 'New-VMSwitch', 'Disable-NetAdapter',
                'Get-NetAdapter | Restart-Service', 'Invoke-Expression "x"'):
        with pytest.raises(ForbiddenCommandError):
            assert_read_only(bad)


def test_wsl_args_allowlist():
    runner = PowerShellRunner()
    with pytest.raises(ForbiddenCommandError):
        runner.run_wsl(['--shutdown'])
    with pytest.raises(ForbiddenCommandError):
        runner.run_wsl(['--unregister', 'Ubuntu'])


def test_decode_output_utf16_and_utf8():
    assert decode_output('Привет мир'.encode('utf-16-le')) == 'Привет мир'
    assert decode_output('\ufeffOK'.encode('utf-8')) == 'OK'
    assert decode_output(b'') == ''


def _runner():
    return PowerShellRunner(timeout_sec=1, powershell_path='fake-powershell.exe')


def test_run_json_timeout_nonzero_invalid_and_denied():
    def run_with(**kw):
        with patch('subprocess.run', **kw):
            return _runner().run_json('Get-NetAdapter | ConvertTo-Json')

    res = run_with(side_effect=subprocess.TimeoutExpired('x', 1))
    assert not res.ok and res.timed_out
    res = run_with(return_value=subprocess.CompletedProcess([], 1, b'', 'Отказано в доступе'.encode('utf-8')))
    assert not res.ok and res.access_denied and res.return_code == 1
    res = run_with(return_value=subprocess.CompletedProcess([], 0, b'{oops', b''))
    assert not res.ok and 'JSON' in res.error
    res = run_with(return_value=subprocess.CompletedProcess([], 0, b'', b''))
    assert res.ok and res.data == []
    res = run_with(return_value=subprocess.CompletedProcess([], 0, b'{"Name":"x"}', b''))
    assert res.ok and res.data == [{'Name': 'x'}]
    res = run_with(side_effect=OSError('нет файла'))
    assert not res.ok and 'запустить' in res.error


# ---------------------------------------------------------- классификация
def test_classification_requires_multiple_signals():
    # Только имя WSL без независимых признаков — не 'wsl'
    cls, _, conf = classify_adapter({'Name': 'WSL Bridge', 'InterfaceDescription': 'Generic', 'HardwareInterface': True})
    assert cls != 'wsl' and conf == 'low'
    cls, signals, conf = classify_adapter(ADAPTERS[1])
    assert cls == 'wsl' and conf == 'high' and len(signals) >= 3
    cls, _, _ = classify_adapter({'Name': 'vEthernet (Default Switch)', 'InterfaceDescription': 'Hyper-V Virtual Ethernet Adapter',
                                  'ComponentID': 'vms_pp'})
    assert cls == 'hyperv_virtual'
    assert classify_adapter(ADAPTERS[0])[0] == 'physical'
    assert classify_adapter({'Name': 'VMware Network Adapter VMnet1', 'InterfaceDescription': 'VMware Virtual Ethernet Adapter',
                             'Virtual': True})[0] == 'virtual_other'


def test_prefix_mask_and_nat_link():
    assert prefix_to_mask(24) == '255.255.255.0' and prefix_to_mask(64, 'IPv6') == '' and prefix_to_mask('x') == ''
    items = [{'id': 'g', 'props': {'alias': 'vEthernet (WSL)', 'ipv4': [{'address': '172.20.0.1'}], 'ipv6': []}}]
    links = link_nat_to_interfaces('172.20.0.0/20', items)
    assert links and links[0]['switch'] == 'WSL'
    assert link_nat_to_interfaces('192.168.0.0/24', items) == []


# ---------------------------------------------------------------- сборщики
def test_basic_collectors_normalization():
    runner = FakeRunner(base_scripts())
    adapters = NetworkAdapterCollector(runner).collect()
    ip = IpConfigurationCollector(runner).collect()
    routes = RouteTableCollector(runner).collect()
    assert adapters.status == ip.status == routes.status == 'ok'
    assert adapters.items[0]['id'] == 'aaaa-1' and adapters.items[0]['props']['adapter_class'] == 'physical'
    eth = next(i for i in ip.items if i['name'] == 'Ethernet')
    assert eth['props']['dns'] == ['8.8.8.8'] and eth['props']['gateways'] == ['10.0.0.1']
    assert eth['props']['ipv4'][0]['mask'] == '255.255.255.0' and eth['props']['metric_v4'] == 25
    default = next(r for r in routes.items if r['props']['is_default'])
    assert default['props']['effective_metric'] == 25 and default['props']['family'] == 'IPv4'


def test_ip_collector_partial_when_optional_fails():
    scripts = base_scripts()
    scripts['Get-DnsClientServerAddress'] = PsResult(ok=False, error='boom', stderr='boom')
    res = IpConfigurationCollector(FakeRunner(scripts)).collect()
    assert res.status == 'partial' and res.items and any('Get-DnsClientServerAddress' in e for e in res.errors)


def test_collector_failure_isolated_and_statuses():
    scripts = base_scripts()
    scripts['Get-NetAdapter'] = PsResult(ok=False, error='Тайм-аут', timed_out=True)
    assert NetworkAdapterCollector(FakeRunner(scripts)).collect().status == 'source_unavailable'
    scripts['Get-NetAdapter'] = PsResult(ok=False, error='x', stderr='Access is denied', access_denied=True)
    res = NetworkAdapterCollector(FakeRunner(scripts)).collect()
    assert res.status == 'data_unavailable' and res.needs_elevation


def test_hyperv_not_installed_vs_installed_empty_vs_denied():
    res = HyperVSwitchCollector(FakeRunner(base_scripts())).collect()
    assert res.status == 'not_installed' and res.items == []
    scripts = base_scripts()
    scripts['Get-Command Get-VMSwitch'] = [{'Name': 'Get-VMSwitch'}]
    scripts['Get-VMSwitch |'] = []
    scripts['Get-VMNetworkAdapter -ManagementOS'] = []
    scripts['Get-VMNetworkAdapterVlan'] = []
    res = HyperVSwitchCollector(FakeRunner(scripts)).collect()
    assert res.status == 'ok' and res.items == []  # Hyper-V есть, коммутаторов нет
    scripts['Get-VMSwitch |'] = PsResult(ok=False, error='x', stderr='not have the required permission', access_denied=True)
    res = HyperVSwitchCollector(FakeRunner(scripts)).collect()
    assert res.status == 'data_unavailable' and res.needs_elevation


def hv_scripts():
    s = base_scripts()
    s['Get-Command Get-VMSwitch'] = [{'Name': 'Get-VMSwitch'}]
    s['Get-VMSwitch |'] = [
        {'Name': 'External', 'Id': '{CCCC-3}', 'SwitchType': 'External', 'NetAdapterInterfaceDescription': 'Realtek Gone',
         'NetAdapterInterfaceGuid': ['{ZZZZ-9}']},
        {'Name': 'WSL', 'Id': 'DDDD-4', 'SwitchType': 'Internal'}]
    s['Get-VMNetworkAdapter -ManagementOS'] = {'Name': 'vEthernet (WSL)', 'SwitchName': 'WSL', 'MacAddress': '00155D010203',
                                               'Status': 'Ok'}
    s['Get-VMNetworkAdapterVlan'] = []
    return s


def test_hyperv_switch_types_single_object_and_vnics():
    res = HyperVSwitchCollector(FakeRunner(hv_scripts())).collect()
    assert res.status == 'ok' and [s['props']['switch_type'] for s in res.items] == ['External', 'Internal']
    assert res.extra['virtual_adapters'][0]['props']['mac'] == '00-15-5D-01-02-03'
    assert res.items[1]['props']['host_adapters'][0]['status'] == ['Ok']


def test_nat_empty_is_ok_with_limitation_and_missing_module():
    s = base_scripts()
    s['Get-Command Get-NetNat'] = []
    res = NatConfigurationCollector(FakeRunner(s)).collect()
    assert res.status == 'source_unavailable' and res.items == []
    s['Get-Command Get-NetNat'] = [{'Name': 'Get-NetNat'}]
    s['Get-NetNat |'] = []
    res = NatConfigurationCollector(FakeRunner(s)).collect()
    assert res.status == 'ok' and res.items == [] and any('ICS' in n for n in res.notes)
    s['Get-NetNat |'] = {'Name': 'N1', 'InternalIPInterfaceAddressPrefix': '172.20.0.0/20', 'Active': True}
    s['Get-NetNatStaticMapping'] = []
    res = NatConfigurationCollector(FakeRunner(s)).collect()
    assert res.items[0]['props']['internal_prefix'] == '172.20.0.0/20'


WSL_LIST = ('  NAME            STATE           VERSION\n* Ubuntu          Running         2\n'
            '  docker-desktop  Stopped         2\n')


def test_parse_wsl_list_and_localized_state():
    d = parse_wsl_list(WSL_LIST)
    assert [x['name'] for x in d] == ['Ubuntu', 'docker-desktop'] and d[0]['is_default'] and d[0]['state'] == 'running'
    ru = parse_wsl_list('  ИМЯ  СОСТОЯНИЕ  ВЕРСИЯ\n* Debian  Остановлен  2\n')
    assert ru[0]['state'] == 'stopped' and ru[0]['version'] == 2


def test_read_wslconfig(tmp_path: Path):
    cfg = tmp_path / '.wslconfig'
    assert read_wslconfig(cfg) == {}
    cfg.write_text('[wsl2]\nnetworkingMode=mirrored\nmemory=4GB\n', encoding='utf-8')
    assert read_wslconfig(cfg) == {'networkingMode': 'mirrored'}


def test_wsl_not_installed_does_not_query(tmp_path: Path):
    runner = FakeRunner(wsl_path=None)
    res = WslNetworkCollector(runner, tmp_path / 'none').collect({})
    assert res.status == 'not_installed' and res.items == []
    runner = FakeRunner(wsl={('--list', '--verbose'): PsResult(ok=False, return_code=1, text='WSL is not installed. wsl.exe --install')})
    assert WslNetworkCollector(runner, tmp_path / 'none').collect({}).status == 'not_installed'


def test_wsl_collects_and_links_windows_interfaces(tmp_path: Path):
    runner = FakeRunner(base_scripts(), wsl={
        ('--list', '--verbose'): PsResult(ok=True, text=WSL_LIST),
        ('--status',): PsResult(ok=True, text='Default Distribution: Ubuntu\nDefault Version: 2'),
        ('--version',): PsResult(ok=True, text='WSL version: 2.1.5.0')})
    cfg = tmp_path / '.wslconfig'
    cfg.write_text('[wsl2]\nnetworkingMode=NAT\n', encoding='utf-8')
    results = {'adapters': NetworkAdapterCollector(runner).collect(), 'ip_config': IpConfigurationCollector(runner).collect()}
    finalize_identities(results)
    res = WslNetworkCollector(runner, cfg).collect(results)
    env = res.items[0]['props']
    assert res.status == 'ok' and env['wsl_version'] == '2.1.5.0' and env['networking_mode'] == 'nat'
    assert env['interfaces'][0]['ipv4'] == ['172.20.0.1'] and env['running_count'] == 1 and len(res.items) == 3
    # без сведений об адаптерах — частичный результат, а не ложное «интерфейсов нет»
    assert WslNetworkCollector(runner, cfg).collect({}).status == 'partial'


# ------------------------------------------------------------ диагностика
def build_results(tmp_path: Path, scripts=None):
    runner = FakeRunner(scripts or hv_scripts(), wsl={('--list', '--verbose'): PsResult(ok=True, text=WSL_LIST)})
    ind = [NetworkAdapterCollector(runner), IpConfigurationCollector(runner), RouteTableCollector(runner),
           HyperVSwitchCollector(runner), NatConfigurationCollector(runner)]
    results = {c.name: c.collect() for c in ind}
    finalize_identities(results)
    refine_classification(results)
    link_nat(results)
    results['wsl'] = WslNetworkCollector(runner, tmp_path / 'none').collect(results)
    return results


def codes(findings):
    return {(f.rule_code, f.severity) for f in findings}


def test_rules_switch_unavailable_adapter_and_internal_switch(tmp_path):
    findings = run_diagnostics(build_results(tmp_path))
    assert ('NET006', 'error') in codes(findings)  # внешний коммутатор → отсутствующий адаптер
    assert not any(f.rule_code == 'NET007' and 'WSL' in f.affected for f in findings)  # адаптер vEthernet (WSL) есть
    for f in findings:
        assert f.source and f.checked_at and isinstance(f.facts, dict) and f.recommendations


def test_rules_no_default_route_and_duplicate_ip_and_state(tmp_path):
    s = base_scripts()
    s['Get-NetRoute'] = [ROUTES[1]]
    s['Get-NetIPAddress'] = IP_ADDR + [{'InterfaceIndex': 21, 'InterfaceAlias': 'vEthernet (WSL)', 'IPAddress': '10.0.0.4',
                                        'PrefixLength': 24, 'AddressFamily': 'IPv4', 'AddressState': 'Duplicate'}]
    s['Get-NetAdapter'] = ADAPTERS[:1] + [{**ADAPTERS[1], 'Status': 'Degraded'}]
    cs = codes(run_diagnostics(build_results(tmp_path, s)))
    assert ('NET004', 'warning') in cs and ('NET002', 'error') in cs and ('NET002', 'warning') in cs
    assert ('NET001', 'warning') in cs


def test_rules_metric_conflict_and_duplicate_routes(tmp_path):
    s = base_scripts()
    s['Get-NetRoute'] = [ROUTES[0], {**ROUTES[0], 'InterfaceIndex': 21, 'InterfaceAlias': 'vEthernet (WSL)'}, ROUTES[0]]
    cs = codes(run_diagnostics(build_results(tmp_path, s)))
    assert ('NET005', 'warning') in cs and ('NET003', 'warning') in cs


def test_rules_unavailable_source_is_not_false_alarm(tmp_path):
    s = base_scripts()
    s['Get-NetRoute'] = PsResult(ok=False, error='x', stderr='Access is denied', access_denied=True)
    findings = run_diagnostics(build_results(tmp_path, s))
    assert not any(f.rule_code == 'NET004' for f in findings)  # маршруты недоступны — нельзя утверждать «нет default route»
    assert any(f.rule_code == 'NET090' and 'routes' in f.affected for f in findings)


def test_diagnostics_do_not_issue_mutations():
    runner = FakeRunner(base_scripts())
    NetworkAdapterCollector(runner).collect()
    from apps.windows.sdk.modules.network.infra import collectors_basic, collectors_virtual
    for mod in (collectors_basic, collectors_virtual):
        for name in dir(mod):
            val = getattr(mod, name)
            if isinstance(val, type) and hasattr(val, '__dict__'):
                for attr, script in vars(val).items():
                    if attr.startswith('_') and isinstance(script, str) and 'Select-Object' in script:
                        assert_read_only(script)


# ------------------------------------------------- хранилище и сравнение
def make_collection(adapters=(), routes=(), status_adapters='ok', status_hv='ok', switches=(), wsl_status='ok'):
    def item(kind, iid, name, props):
        return {'id': iid, 'kind': kind, 'name': name, 'source': 't', 'props': props, 'raw': {}}
    return {'started_at': now_iso(), 'finished_at': now_iso(), 'status': 'ok',
            'sources': {'adapters': {'status': status_adapters, 'source': 's', 'errors': []},
                        'ip_config': {'status': 'ok', 'source': 's', 'errors': []},
                        'routes': {'status': 'ok', 'source': 's', 'errors': []},
                        'hyperv': {'status': status_hv, 'source': 's', 'errors': []},
                        'nat': {'status': 'ok', 'source': 's', 'errors': []},
                        'wsl': {'status': wsl_status, 'source': 's', 'errors': []}},
            'data': {'adapters': [item('adapter', a, a, {'status': st}) for a, st in adapters],
                     'ip_config': [], 'routes': [item('route', r, r, {'metric': m}) for r, m in routes],
                     'switches': [item('virtual_switch', s, s, {'mode': 'internal'}) for s in switches],
                     'virtual_adapters': [], 'nat': [], 'wsl': []},
            'findings': []}


def test_store_roundtrip_and_prune(tmp_path):
    store = NetworkInfraStore(tmp_path / 'h.db', max_snapshots=2, retention_days=90)
    ids = [store.save_snapshot(make_collection(adapters=[('a', 'Up')])) for _ in range(3)]
    assert len(store.list_snapshots()) == 2 and ids[0] not in {s['id'] for s in store.list_snapshots()}
    snap = store.get_snapshot(ids[-1])
    assert snap['data']['adapters'][0]['props'] == {'status': 'Up'} and snap['sources']['adapters']['status'] == 'ok'
    with pytest.raises(SnapshotNotFound):
        store.get_snapshot('missing')
    old = make_collection()
    old['finished_at'] = '2000-01-01T00:00:00+00:00'
    store2 = NetworkInfraStore(tmp_path / 'h2.db', max_snapshots=10, retention_days=30)
    store2.save_snapshot(old)
    assert store2.list_snapshots() == []  # старый снимок удалён политикой хранения


def test_compare_added_removed_changed():
    a = make_collection(adapters=[('a', 'Up'), ('b', 'Up')], routes=[('r1', 10)])
    b = make_collection(adapters=[('a', 'Down'), ('c', 'Up')], routes=[('r1', 20)], switches=['sw'])
    diff = cmp_mod.compare_snapshots(a, b)
    kinds = {(c['change_type'], c['kind'], c['object_id']) for c in diff['changes']}
    assert ('changed', 'adapter', 'a') in kinds and ('removed', 'adapter', 'b') in kinds
    assert ('added', 'adapter', 'c') in kinds and ('changed', 'route', 'r1') in kinds
    assert ('added', 'virtual_switch', 'sw') in kinds


def test_compare_unavailable_source_is_not_removal():
    a = make_collection(adapters=[('a', 'Up')], switches=['sw'])
    b = make_collection(adapters=[('a', 'Up')], status_hv='not_installed')
    diff = cmp_mod.compare_snapshots(a, b)
    assert not any(c['change_type'] == 'removed' for c in diff['changes'])
    assert 'virtual_switch' in diff['skipped']
    assert any(c['change_type'] == 'status_changed' and c['object_id'] == 'hyperv' for c in diff['changes'])
    # источник стал доступным: объекты не считаются «созданными»
    diff2 = cmp_mod.compare_snapshots(b, make_collection(switches=['sw'], adapters=[('a', 'Up')]))
    assert not any(c['change_type'] == 'added' and c['kind'] == 'virtual_switch' for c in diff2['changes'])


# ------------------------------------------------------------------ сервис
def settings(tmp_path, ttl=30):
    return InfraSettings(cache_ttl_sec=ttl, db_path=str(tmp_path / 's.db'))


def make_service(tmp_path, runner=None, ttl=30):
    runner = runner or FakeRunner(base_scripts(), wsl_path=None)
    st = settings(tmp_path, ttl)
    svc = NetworkInfraService(runner, NetworkInfraStore(st.resolved_db_path()), st)
    svc.wsl = WslNetworkCollector(runner, tmp_path / 'none')
    return svc


def test_service_collect_summary_cache_and_resources(tmp_path):
    svc = make_service(tmp_path)
    c = svc.collect()
    assert c['status'] == 'ok' and c['summary']['adapters_total'] == 2 and c['sources']['wsl']['status'] == 'not_installed'
    calls = svc.runner.calls
    assert svc.collect()['cached'] and svc.runner.calls == calls
    ad = svc.resource('adapters')
    assert ad['items'][0]['props']['ip']['ipv4'][0]['address'] == '10.0.0.4'
    assert svc.resource('hyperv')['status'] == 'not_installed'
    with pytest.raises(KeyError):
        svc.resource('nope')


def test_service_single_flight(tmp_path):
    svc = make_service(tmp_path, FakeRunner(base_scripts(), wsl_path=None, delay=0.05), ttl=0)
    out = []
    ts = [threading.Thread(target=lambda: out.append(svc.collect())) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 4 and any(r['shared'] for r in out)


def test_service_partial_when_collector_fails_others_continue(tmp_path):
    s = base_scripts()
    s['Get-NetRoute'] = PsResult(ok=False, error='fail', stderr='fail')
    svc = make_service(tmp_path, FakeRunner(s, wsl_path=None))
    c = svc.collect()
    assert c['status'] == 'partial' and c['sources']['routes']['status'] == 'source_unavailable'
    assert c['sources']['adapters']['status'] == 'ok'
    snap = svc.create_snapshot()
    assert snap['status'] == 'partial' and snap['sources']['routes'] == 'source_unavailable'


def test_overall_status():
    assert overall_status({'a': {'status': 'ok'}, 'b': {'status': 'not_installed'}}) == 'ok'
    assert overall_status({'a': {'status': 'error'}, 'b': {'status': 'source_unavailable'}}) == 'error'
    assert overall_status({'a': {'status': 'ok'}, 'b': {'status': 'error'}}) == 'partial'

