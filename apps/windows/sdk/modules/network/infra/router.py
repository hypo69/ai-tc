# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - FastAPI Router
# =============================================================================
# Description:
#   REST API диагностики сетевой инфраструктуры Windows (/api/network/infra/*).
#   Только чтение состояния ОС. Записи выполняются исключительно в собственную
#   БД истории (снимки, очистка). Подключается существующим механизмом
#   регистрации роутеров ai-tc (config.json / автообнаружение *.router).
#
#   GET  /summary                     сводка («Обзор»)
#   GET  /adapters | /ip-config | /routes[?family=IPv4|IPv6] | /switches | /nat | /wsl
#   GET  /diagnostics                 результаты правил (кэш)
#   POST /diagnostics/run             новый сбор + правила
#   POST /snapshots                   создать снимок
#   GET  /snapshots[?limit=]          список снимков
#   GET  /snapshots/compare?base=&target=   сравнение
#   GET  /snapshots/{id}              детали снимка (исходные данные)
#   GET  /history/findings[?severity=&limit=]
#   POST /history/prune               очистка истории по политике хранения
#   Параметр refresh=true форсирует новый сбор. Коды ошибок: 400 (параметры),
#   404 (снимок не найден), 500 (внутренняя ошибка). Ошибки источников данных
#   возвращаются в теле ответа (поле status), а не HTTP-ошибкой.
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from logger import logger

from apps.windows.api.auth import require_admin_user

from .ps_runner import ForbiddenCommandError, PowerShellRunner
from .service import NetworkInfraService
from .settings import load_settings
from .store import NetworkInfraStore, SnapshotNotFound

router = APIRouter(prefix='/api/network/infra', tags=['network-infra'])

_service: Optional[NetworkInfraService] = None
_service_lock = threading.Lock()


def get_service() -> NetworkInfraService:
    """Возвращает (лениво создаёт) единственный экземпляр сервиса диагностики."""
    global _service
    with _service_lock:
        if _service is None:
            settings = load_settings()
            runner = PowerShellRunner(settings.ps_timeout_sec, settings.wsl_timeout_sec)
            store = NetworkInfraStore(settings.resolved_db_path(), settings.retention_max_snapshots, settings.retention_days)
            _service = NetworkInfraService(runner, store, settings)
        return _service


def set_service(service: Optional[NetworkInfraService]) -> None:
    """Подменяет сервис (используется в тестах)."""
    global _service
    with _service_lock:
        _service = service


async def _run(func, *args, **kwargs) -> Any:
    """Выполняет блокирующий вызов сервиса в потоке с единообразной обработкой ошибок."""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except SnapshotNotFound as exc:
        raise HTTPException(status_code=404, detail=f'Снимок не найден: {exc}') from exc
    except ForbiddenCommandError as exc:
        logger.error(f'[NetworkInfra] Заблокирована запрещённая команда: {exc}')
        raise HTTPException(status_code=500, detail='Внутренняя ошибка: запрещённая команда') from exc
    except Exception as exc:  # noqa: BLE001
        logger.error(f'[NetworkInfra] Ошибка обработки запроса: {exc}')
        raise HTTPException(status_code=500, detail=f'Внутренняя ошибка диагностики сети: {exc}') from exc


@router.get('/summary')
async def get_summary(refresh: bool = False) -> Dict[str, Any]:
    """Сводка состояния сетевой инфраструктуры."""
    return await _run(get_service().summary, refresh)


@router.get('/adapters')
async def get_adapters(refresh: bool = False) -> Dict[str, Any]:
    """Сетевые адаптеры с классификацией и IP-данными."""
    return await _run(get_service().resource, 'adapters', refresh)


@router.get('/ip-config')
async def get_ip_config(refresh: bool = False) -> Dict[str, Any]:
    """IP-конфигурация интерфейсов (адреса, DNS, шлюзы, метрики)."""
    return await _run(get_service().resource, 'ip_config', refresh)


@router.get('/routes')
async def get_routes(family: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
    """Таблицы маршрутизации IPv4/IPv6."""
    if family is not None and family not in ('IPv4', 'IPv6'):
        raise HTTPException(status_code=400, detail='family должен быть IPv4 или IPv6')
    data = await _run(get_service().resource, 'routes', refresh)
    if family:
        data['items'] = [r for r in data['items'] if r['props']['family'] == family]
    return data


@router.get('/switches')
async def get_switches(refresh: bool = False) -> Dict[str, Any]:
    """Виртуальные коммутаторы Hyper-V и адаптеры хоста."""
    return await _run(get_service().resource, 'hyperv', refresh)


@router.get('/nat')
async def get_nat(refresh: bool = False) -> Dict[str, Any]:
    """Доступные NAT-конфигурации."""
    return await _run(get_service().resource, 'nat', refresh)


@router.get('/wsl')
async def get_wsl(refresh: bool = False) -> Dict[str, Any]:
    """Состояние и сетевые сведения WSL."""
    return await _run(get_service().resource, 'wsl', refresh)


@router.get('/diagnostics')
async def get_diagnostics(refresh: bool = False) -> Dict[str, Any]:
    """Результаты диагностических правил (из кэша или нового сбора)."""
    return await _run(get_service().diagnostics, refresh)


@router.post('/diagnostics/run')
async def run_diagnostics_now() -> Dict[str, Any]:
    """Запускает новый сбор и диагностические правила."""
    return await _run(get_service().diagnostics, True)


@router.post('/snapshots')
async def create_snapshot(request: Request) -> Dict[str, Any]:
    """Создаёт и сохраняет снимок текущей конфигурации."""
    require_admin_user(request)
    return await _run(get_service().create_snapshot)


@router.get('/snapshots')
async def list_snapshots(limit: int = 50) -> Dict[str, Any]:
    """Список сохранённых снимков (новые первыми)."""
    return {'items': await _run(get_service().store.list_snapshots, limit)}


@router.get('/snapshots/compare')
async def compare_snapshots_endpoint(base: str, target: str) -> Dict[str, Any]:
    """Сравнивает два снимка по идентификаторам."""
    return await _run(get_service().compare, base, target)


@router.get('/snapshots/{snapshot_id}')
async def get_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Детали снимка вместе с исходными данными."""
    return await _run(get_service().store.get_snapshot, snapshot_id)


@router.get('/history/findings')
async def get_findings_history(limit: int = 200, severity: Optional[str] = None) -> Dict[str, Any]:
    """История диагностических результатов по снимкам."""
    if severity is not None and severity not in ('info', 'warning', 'error', 'critical'):
        raise HTTPException(status_code=400, detail='Недопустимый уровень важности')
    return {'items': await _run(get_service().store.findings_history, limit, severity)}


@router.post('/history/prune')
async def prune_history(request: Request) -> Dict[str, Any]:
    """Очищает историю снимков по политике хранения."""
    require_admin_user(request)
    return {'removed': await _run(get_service().store.prune)}


def init_router() -> APIRouter:
    """Возвращает роутер диагностики сетевой инфраструктуры."""
    return router


__all__ = ['router', 'init_router', 'get_service', 'set_service']

