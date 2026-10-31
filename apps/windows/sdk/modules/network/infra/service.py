# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Service
# =============================================================================
# Description:
#   Сервис сетевой диагностики: параллельный запуск независимых сборщиков,
#   нормализация, диагностические правила, кэш последнего сбора, защита от
#   параллельных повторных запусков (одновременные запросы получают результат
#   уже выполняющегося сбора), сохранение снимков и сравнение.
#
# Usage Examples:
#   service = NetworkInfraService(runner, store, settings)
#   collection = service.collect()
#   view = service.resource('adapters')
#
# File: service.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from logger import logger

from .collectors_basic import (BaseCollector, IpConfigurationCollector, NetworkAdapterCollector,
                               RouteTableCollector)
from .collectors_virtual import HyperVSwitchCollector, NatConfigurationCollector, WslNetworkCollector
from .compare import compare_snapshots
from .diagnostics import run_diagnostics
from .models import (CollectorResult, STATUS_ERROR, STATUS_NOT_INSTALLED, STATUS_OK, STATUS_PARTIAL,
                     STATUS_UNKNOWN, now_iso)
from .normalize import adapters_view, finalize_identities, link_nat, refine_classification
from .ps_runner import PowerShellRunner
from .settings import InfraSettings
from .store import NetworkInfraStore

RESOURCES = ('adapters', 'ip_config', 'routes', 'hyperv', 'nat', 'wsl')


def overall_status(sources: Dict[str, Dict[str, Any]]) -> str:
    """Агрегирует статус сбора: ok / partial / error.

    Args:
        sources: Метаданные источников (поле status).

    Returns:
        str: ok, если все источники определены (ok или not_installed); error, если ни один
            источник не дал данных; иначе partial.
    """
    statuses = [s.get('status', STATUS_UNKNOWN) for s in sources.values()]
    if all(s in (STATUS_OK, STATUS_NOT_INSTALLED) for s in statuses):
        return 'ok'
    if not any(s in (STATUS_OK, STATUS_PARTIAL) for s in statuses):
        return 'error'
    return 'partial'


class NetworkInfraService:
    """Оркестратор диагностики сетевой инфраструктуры (read-only)."""

    def __init__(self, runner: PowerShellRunner, store: NetworkInfraStore, settings: InfraSettings,
                 independent: Optional[List[BaseCollector]] = None, wsl: Optional[BaseCollector] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        """Инициализирует сервис.

        Args:
            runner: Раннер PowerShell/wsl.exe.
            store: Хранилище снимков.
            settings: Настройки.
            independent: Независимые сборщики (по умолчанию — штатные пять).
            wsl: Сборщик WSL (зависит от результатов остальных).
            clock: Источник монотонного времени (подменяется в тестах).
        """
        self.runner, self.store, self.settings, self._clock = runner, store, settings, clock
        self.independent = independent if independent is not None else [
            NetworkAdapterCollector(runner), IpConfigurationCollector(runner), RouteTableCollector(runner),
            HyperVSwitchCollector(runner), NatConfigurationCollector(runner)]
        self.wsl = wsl if wsl is not None else WslNetworkCollector(runner)
        self._state_lock = threading.Lock()
        self._inflight: Optional[Future] = None
        self._results: Dict[str, CollectorResult] = {}
        self._collection: Dict[str, Any] = {}
        self._cached_at: float = 0.0

    # ------------------------------------------------------------------ сбор
    def collect(self, force: bool = False) -> Dict[str, Any]:
        """Возвращает результат сбора: из кэша, из уже выполняющегося сбора или новый.

        Args:
            force: Игнорировать кэш.

        Returns:
            Dict[str, Any]: Коллекция (sources, data, findings, summary, status, cached/shared).
        """
        with self._state_lock:
            if not force and self._collection and self._clock() - self._cached_at < self.settings.cache_ttl_sec:
                return {**self._collection, 'cached': True, 'shared': False}
            if self._inflight is not None:
                future, owner = self._inflight, False
            else:
                future, owner = Future(), True
                self._inflight = future
        if not owner:
            logger.info('[NetworkInfra] Сбор уже выполняется — используется его результат')
            return {**future.result(timeout=self.settings.ps_timeout_sec * 4), 'cached': False, 'shared': True}
        try:
            collection = self._collect_now()
            future.set_result(collection)
            return {**collection, 'cached': False, 'shared': False}
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._state_lock:
                self._inflight = None

    def _collect_now(self) -> Dict[str, Any]:
        """Выполняет полный цикл: сборщики → нормализация → диагностика → кэш."""
        started_at, t0 = now_iso(), time.perf_counter()
        logger.info('[NetworkInfra] Начат сбор сетевой конфигурации')
        results: Dict[str, CollectorResult] = {}
        with ThreadPoolExecutor(max_workers=max(1, self.settings.max_workers)) as pool:
            futures = {c.name: pool.submit(c.collect) for c in self.independent}
            for name, fut in futures.items():
                results[name] = fut.result()
        finalize_identities(results)
        refine_classification(results)
        link_nat(results)
        results[self.wsl.name] = self.wsl.collect(results)
        findings = [f.to_dict() for f in run_diagnostics(results)]
        sources = {n: r.to_dict(include_items=False) for n, r in results.items()}
        hv = results.get('hyperv')
        data = {'adapters': results['adapters'].items if 'adapters' in results else [],
                'ip_config': results['ip_config'].items if 'ip_config' in results else [],
                'routes': results['routes'].items if 'routes' in results else [],
                'switches': hv.items if hv else [],
                'virtual_adapters': hv.extra.get('virtual_adapters', []) if hv else [],
                'nat': results['nat'].items if 'nat' in results else [],
                'wsl': results[self.wsl.name].items}
        collection = {'started_at': started_at, 'finished_at': now_iso(), 'status': overall_status(sources),
                      'duration_ms': int((time.perf_counter() - t0) * 1000), 'sources': sources, 'data': data,
                      'findings': findings, 'summary': self._summary(results, findings)}
        with self._state_lock:
            self._results, self._collection, self._cached_at = results, collection, self._clock()
        logger.info(f"[NetworkInfra] Сбор завершён: статус={collection['status']}, {collection['duration_ms']} мс, "
                    f"диагностик={len(findings)}")
        return collection

    @staticmethod
    def _summary(results: Dict[str, CollectorResult], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Формирует сводку для панели «Обзор» строго из результатов сбора."""
        def count(name: str) -> Optional[int]:
            res = results.get(name)
            return len(res.items) if res and res.status in (STATUS_OK, STATUS_PARTIAL) else None
        adapters = results.get('adapters')
        up = down = None
        if adapters and adapters.status in (STATUS_OK, STATUS_PARTIAL):
            up = sum(1 for a in adapters.items if str(a['props']['status']).lower() == 'up')
            down = len(adapters.items) - up
        wsl = results.get('wsl')
        env = wsl.items[0]['props'] if wsl and wsl.items else {}
        sev: Dict[str, int] = {}
        for f in findings:
            sev[f['severity']] = sev.get(f['severity'], 0) + 1
        return {'adapters_total': count('adapters'), 'adapters_up': up, 'adapters_down': down,
                'switches_count': count('hyperv'), 'hyperv_status': results['hyperv'].status if 'hyperv' in results else STATUS_UNKNOWN,
                'nat_count': count('nat'), 'nat_status': results['nat'].status if 'nat' in results else STATUS_UNKNOWN,
                'wsl_status': wsl.status if wsl else STATUS_UNKNOWN, 'wsl_distros': env.get('distro_count'),
                'wsl_running': env.get('running_count'), 'wsl_networking_mode': env.get('networking_mode'),
                'routes_count': count('routes'), 'findings_total': len(findings), 'findings_by_severity': sev,
                'main_interfaces': [{'name': a['props']['name'], 'status': a['props']['status'],
                                     'class': a['props'].get('adapter_class')}
                                    for a in (adapters.items if adapters else [])
                                    if a['props'].get('adapter_class') == 'physical'][:8]}

    # ---------------------------------------------------------------- виды
    def resource(self, name: str, refresh: bool = False) -> Dict[str, Any]:
        """Возвращает данные одного источника с его статусом (отличимым от «пусто»).

        Args:
            name: Один из RESOURCES.
            refresh: Принудительно выполнить новый сбор.

        Returns:
            Dict[str, Any]: Конверт {resource, status, source, collected_at, errors, notes, items, extra, cached}.

        Raises:
            KeyError: Неизвестный ресурс.
        """
        if name not in RESOURCES:
            raise KeyError(name)
        collection = self.collect(force=refresh)
        with self._state_lock:
            res = self._results.get(name)
        meta = collection['sources'].get(name, {})
        items = copy.deepcopy(adapters_view(self._results)) if name == 'adapters' else copy.deepcopy(res.items if res else [])
        extra = copy.deepcopy(res.extra) if res else {}
        return {'resource': name, 'status': meta.get('status', STATUS_UNKNOWN), 'source': meta.get('source', ''),
                'collected_at': meta.get('finished_at', ''), 'duration_ms': meta.get('duration_ms', 0),
                'errors': meta.get('errors', []), 'notes': meta.get('notes', []),
                'needs_elevation': meta.get('needs_elevation', False), 'items': items, 'extra': extra,
                'cached': collection.get('cached', False), 'shared': collection.get('shared', False)}

    def summary(self, refresh: bool = False) -> Dict[str, Any]:
        """Возвращает сводку для «Обзора»."""
        c = self.collect(force=refresh)
        return {'status': c['status'], 'collected_at': c['finished_at'], 'duration_ms': c['duration_ms'],
                'summary': c['summary'], 'sources': c['sources'], 'cached': c.get('cached', False),
                'shared': c.get('shared', False)}

    def diagnostics(self, refresh: bool = False) -> Dict[str, Any]:
        """Возвращает результаты диагностических правил."""
        c = self.collect(force=refresh)
        return {'status': c['status'], 'checked_at': c['finished_at'], 'findings': c['findings'],
                'sources': {n: {'status': s['status'], 'errors': s['errors']} for n, s in c['sources'].items()},
                'cached': c.get('cached', False)}

    # --------------------------------------------------------------- история
    def create_snapshot(self) -> Dict[str, Any]:
        """Выполняет новый сбор и сохраняет его как снимок.

        Returns:
            Dict[str, Any]: Метаданные сохранённого снимка.
        """
        collection = self.collect(force=True)
        sid = self.store.save_snapshot(collection)
        meta = next(s for s in self.store.list_snapshots(limit=5) if s['id'] == sid)
        return meta

    def compare(self, base_id: str, target_id: str) -> Dict[str, Any]:
        """Сравнивает два сохранённых снимка.

        Raises:
            SnapshotNotFound: Один из снимков не найден.
        """
        return compare_snapshots(self.store.get_snapshot(base_id), self.store.get_snapshot(target_id))

