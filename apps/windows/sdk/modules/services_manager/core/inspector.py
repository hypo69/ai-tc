# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Services_Manager Core - Inspector
# =============================================================================
# Description:
#   Инспектор каталога и графа связей служб Windows.
#   Выполняет быстрое O(N)-обогащение всех служб данными реестра (svchost-группы,
#   ServiceDll, зависимости, per-user суффиксы), хост-процессов и сети, а также
#   формирует глубокое досье по запросу (SCM + Registry + Process + Network +
#   Event Log через WevtAPI + история телеметрии AI-TC).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.services_manager.core.inspector import ServiceCatalogInspector
#
#     inspector = ServiceCatalogInspector()
#     enriched = inspector.enrich_services(services)
#
# File: inspector.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.services_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:13:00
# =============================================================================

from __future__ import annotations

"""Инспектор каталога служб Windows, графа связей и глубокого досье."""

import os
import re
import socket
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psutil

from logger import logger
from apps.windows.sdk.modules.services_manager.core.models import (
    ServiceDossier,
    ServiceEventLogEntry,
    ServiceItem,
    ServiceNetworkConnection,
    ServiceProcessMetrics,
    ServiceRegistryInfo,
    ServiceRelationEdge,
    ServiceRelationNode,
    ServicesGraphReport,
    SharedPidCluster,
    SvchostGroupSummary,
)

try:
    import winreg
except ImportError:  # pragma: no cover - не Windows
    winreg = None  # type: ignore[assignment]

# Регулярные выражения для разбора командной строки svchost и суффиксов per-user служб
_SVCHOST_GROUP_RE = re.compile(r'(?:^|\s)-k\s+"?([^\s"]+)"?', re.IGNORECASE)
_PER_USER_SUFFIX_RE = re.compile(r'^(.+)_([0-9a-fA-F]{4,})$')

_SVCHOST_REG_PATH = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Svchost'
_SERVICES_REG_PREFIX = r'SYSTEM\CurrentControlSet\Services'


def parse_per_user_service_name(service_name: str) -> Tuple[bool, str, str]:
    """Определяет, является ли служба динамическим пользовательским экземпляром.

    Например: 'OneSyncSvc_12345' -> (True, 'OneSyncSvc', '12345').

    Args:
        service_name: Системное имя службы.

    Returns:
        Кортеж (is_per_user, base_service_name, instance_suffix).
    """
    match = _PER_USER_SUFFIX_RE.match(service_name or '')
    if not match:
        return False, service_name or '', ''
    return True, match.group(1), match.group(2)


def extract_svchost_group(binary_path: str) -> str:
    """Извлекает имя группы служб из аргумента '-k <Group>' командной строки svchost.exe.

    Args:
        binary_path: Путь и аргументы запуска службы.

    Returns:
        Имя группы svchost или пустая строка.
    """
    if not binary_path or 'svchost' not in binary_path.lower():
        return ''
    match = _SVCHOST_GROUP_RE.search(binary_path)
    return match.group(1).strip() if match else ''


def _read_reg_value(key: Any, name: str, default: Any = None) -> Any:
    """Безопасное чтение значения из открытого ключа реестра Windows."""
    if winreg is None:
        return default
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return val
    except OSError:
        return default


def _normalize_multi_sz(value: Any) -> List[str]:
    """Нормализация REG_MULTI_SZ или строки зависимостей в чистый список имен."""
    if not value:
        return []
    if isinstance(value, str):
        items = [v.strip() for v in value.replace('\x00', '\n').splitlines() if v.strip()]
    elif isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        return []
    return [item for item in items if not item.startswith('+')]


class ServiceCatalogInspector:
    """Анализатор связей служб Windows (SCM, Registry, Process, Network, Event Log)."""

    def read_svchost_groups_map(self) -> Dict[str, List[str]]:
        """Читает карту всех групп svchost из реестра за один проход.

        Returns:
            Словарь {group_name: [service_names...]}.
        """
        groups: Dict[str, List[str]] = {}
        if winreg is None or os.name != 'nt':
            return groups
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _SVCHOST_REG_PATH) as key:
                idx = 0
                while True:
                    try:
                        val_name, val_data, _ = winreg.EnumValue(key, idx)
                        idx += 1
                        members = _normalize_multi_sz(val_data)
                        if val_name and members:
                            groups[val_name] = members
                    except OSError:
                        break
        except OSError as exc:
            logger.debug(f'[ServiceCatalogInspector] Не удалось прочитать группы svchost: {exc}')
        return groups

    def read_service_registry_info(
        self,
        service_name: str,
        svchost_groups_map: Optional[Dict[str, List[str]]] = None,
    ) -> ServiceRegistryInfo:
        """Читает конфигурацию службы из реестра (ServiceDll, зависимости, группа, описание).

        Для per-user экземпляров (например, OneSyncSvc_12345) автоматически
        подтягивает ServiceDll и зависимости из базового шаблона (OneSyncSvc),
        если они не продублированы в ветке экземпляра.

        Args:
            service_name: Системное имя службы.
            svchost_groups_map: Предзагруженная карта групп svchost.

        Returns:
            Заполненная структура ServiceRegistryInfo.
        """
        is_per_user, base_name, _ = parse_per_user_service_name(service_name)
        key_path = f'{_SERVICES_REG_PREFIX}\\{service_name}'
        info = ServiceRegistryInfo(service_key=f'HKLM\\{key_path}')

        if winreg is None or os.name != 'nt':
            return info

        def _populate_from_key(reg_subpath: str, fill_missing_only: bool = False) -> None:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_subpath) as key:
                    img = _read_reg_value(key, 'ImagePath', '')
                    if img and (not fill_missing_only or not info.image_path):
                        info.image_path = str(img)
                    obj = _read_reg_value(key, 'ObjectName', '')
                    if obj and (not fill_missing_only or not info.object_name):
                        info.object_name = str(obj)
                    desc = _read_reg_value(key, 'Description', '')
                    if desc and (not fill_missing_only or not info.description):
                        info.description = str(desc)
                    start_code = _read_reg_value(key, 'Start')
                    if isinstance(start_code, int) and (not fill_missing_only or info.start_code is None):
                        info.start_code = start_code
                    type_code = _read_reg_value(key, 'Type')
                    if isinstance(type_code, int) and (not fill_missing_only or info.service_type_code is None):
                        info.service_type_code = type_code
                    delayed = _read_reg_value(key, 'DelayedAutostart', 0)
                    if delayed and not info.delayed_auto_start:
                        info.delayed_auto_start = bool(delayed)
                    failure = _read_reg_value(key, 'FailureActions')
                    if failure is not None and not info.failure_actions_configured:
                        info.failure_actions_configured = True
                    deps = _normalize_multi_sz(_read_reg_value(key, 'DependOnService'))
                    if deps and (not fill_missing_only or not info.dependencies):
                        info.dependencies = deps

                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f'{reg_subpath}\\Parameters') as pkey:
                        dll = _read_reg_value(pkey, 'ServiceDll', '')
                        if dll and (not fill_missing_only or not info.service_dll):
                            info.service_dll = str(dll)
                except OSError:
                    pass
            except OSError:
                pass

        _populate_from_key(key_path, fill_missing_only=False)
        if is_per_user and base_name and base_name != service_name:
            _populate_from_key(f'{_SERVICES_REG_PREFIX}\\{base_name}', fill_missing_only=True)

        # Определение группы svchost по ImagePath и карте реестра
        group_name = extract_svchost_group(info.image_path)
        groups_map = svchost_groups_map if svchost_groups_map is not None else self.read_svchost_groups_map()
        if not group_name and groups_map:
            lookup_names = {service_name.lower(), base_name.lower()}
            for g_name, members in groups_map.items():
                if any(m.lower() in lookup_names for m in members):
                    group_name = g_name
                    break

        info.svchost_group = group_name
        if group_name:
            for g_name, members in groups_map.items():
                if g_name.lower() == group_name.lower():
                    info.svchost_group = g_name
                    info.svchost_group_members = list(members)
                    break

        return info

    def _collect_pid_network_counts(self) -> Dict[int, int]:
        """Подсчитывает активные сетевые соединения по PID за один проход O(N)."""
        counts: Dict[int, int] = defaultdict(int)
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.pid:
                    counts[int(conn.pid)] += 1
        except Exception as exc:
            logger.debug(f'[ServiceCatalogInspector] Ошибка подсчета сетевых соединений: {exc}')
        return counts

    def _collect_pid_process_summary(self, pids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Собирает быстрые метрики (имя, RAM, потоки, дескрипторы) для уникальных PID."""
        summary: Dict[int, Dict[str, Any]] = {}
        for pid in set(p for p in pids if p and p > 0):
            try:
                proc = psutil.Process(pid)
                mem_info = proc.memory_info()
                handles = proc.num_handles() if hasattr(proc, 'num_handles') else 0
                summary[pid] = {
                    'name': proc.name(),
                    'memory_mb': round(mem_info.rss / (1024 * 1024), 2),
                    'threads_count': proc.num_threads(),
                    'handles_count': int(handles or 0),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
        return summary

    def enrich_services(self, services: List[ServiceItem]) -> List[ServiceItem]:
        """Обогащает полный список служб связями реестра, групп svchost, PID и сети за O(N).

        Args:
            services: Базовый список служб от SCM/psutil.

        Returns:
            Обогащенный список ServiceItem.
        """
        if not services:
            return []

        svchost_map = self.read_svchost_groups_map()
        reverse_group_lookup: Dict[str, str] = {}
        for g_name, members in svchost_map.items():
            for member in members:
                reverse_group_lookup[member.lower()] = g_name

        # 1. Реестр, svchost-группа и per-user метаданные
        dependents_map: Dict[str, List[str]] = defaultdict(list)
        pid_to_services: Dict[int, List[str]] = defaultdict(list)
        group_to_services: Dict[str, List[str]] = defaultdict(list)

        active_pids: List[int] = []
        for svc in services:
            is_per_user, base_name, suffix = parse_per_user_service_name(svc.name)
            svc.is_per_user = is_per_user
            svc.base_service_name = base_name
            svc.instance_suffix = suffix

            reg_info = self.read_service_registry_info(svc.name, svchost_groups_map=svchost_map)
            svc.service_dll = reg_info.service_dll
            svc.dependencies = reg_info.dependencies

            group = (
                reg_info.svchost_group
                or extract_svchost_group(svc.binary_path)
                or reverse_group_lookup.get(svc.name.lower(), '')
                or reverse_group_lookup.get(base_name.lower(), '')
            )
            svc.svchost_group = group

            if svc.binary_path and not svc.host_process_name:
                exe_part = svc.binary_path.strip().lstrip('"').split('"')[0].split()[0]
                svc.host_process_name = os.path.basename(exe_part)

            for dep in svc.dependencies:
                dependents_map[dep.lower()].append(svc.name)

            if svc.pid and svc.pid > 0:
                pid_to_services[svc.pid].append(svc.name)
                active_pids.append(svc.pid)

            if group:
                group_to_services[group.lower()].append(svc.name)

        # 2. Метрики процессов и сети за один проход по уникальным PID
        pid_summary = self._collect_pid_process_summary(active_pids)
        pid_net_counts = self._collect_pid_network_counts()

        # 3. Заполнение обратных связей и метрик O(N)
        for svc in services:
            svc.dependents = sorted(set(dependents_map.get(svc.name.lower(), [])))

            if svc.pid and svc.pid > 0:
                svc.shared_pid_services = sorted(
                    name for name in pid_to_services.get(svc.pid, []) if name != svc.name
                )
                p_info = pid_summary.get(svc.pid)
                if p_info:
                    svc.host_process_name = p_info['name']
                    svc.memory_mb = p_info['memory_mb']
                    svc.threads_count = p_info['threads_count']
                    svc.handles_count = p_info['handles_count']
                svc.network_connections_count = pid_net_counts.get(svc.pid, 0)

            if svc.svchost_group:
                svc.same_group_services = sorted(
                    name for name in group_to_services.get(svc.svchost_group.lower(), [])
                    if name != svc.name
                )

        return services

    def _collect_process_dossier(self, pid: Optional[int]) -> Optional[ServiceProcessMetrics]:
        """Собирает глубокие метрики хост-процесса службы по его PID."""
        if not pid or pid <= 0:
            return None
        try:
            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            handles = proc.num_handles() if hasattr(proc, 'num_handles') else 0
            try:
                exe_path = proc.exe()
            except Exception:
                exe_path = ''
            try:
                cmdline = ' '.join(proc.cmdline())
            except Exception:
                cmdline = ''
            try:
                io = proc.io_counters()
                io_read_mb = round(io.read_bytes / (1024 * 1024), 2)
                io_write_mb = round(io.write_bytes / (1024 * 1024), 2)
            except Exception:
                io_read_mb = 0.0
                io_write_mb = 0.0
            try:
                open_files = [f.path for f in proc.open_files()[:30]]
            except Exception:
                open_files = []
            try:
                loaded_mods = [
                    os.path.basename(m.path)
                    for m in proc.memory_maps()
                    if getattr(m, 'path', '') and m.path.lower().endswith('.dll')
                ]
                loaded_mods = sorted(set(loaded_mods))[:30]
            except Exception:
                loaded_mods = []

            return ServiceProcessMetrics(
                pid=pid,
                name=proc.name(),
                exe=exe_path,
                cmdline=cmdline,
                status=proc.status(),
                cpu_percent=round(proc.cpu_percent(interval=0.0), 2),
                memory_mb=round(mem_info.rss / (1024 * 1024), 2),
                threads_count=proc.num_threads(),
                handles_count=int(handles or 0),
                io_read_mb=io_read_mb,
                io_write_mb=io_write_mb,
                open_files=open_files,
                loaded_modules_sample=loaded_mods,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        except Exception as exc:
            logger.debug(f'[ServiceCatalogInspector] Ошибка инспекции PID={pid}: {exc}')
            return None

    def _collect_network_dossier(self, pid: Optional[int]) -> List[ServiceNetworkConnection]:
        """Собирает активные TCP/UDP соединения конкретного PID."""
        if not pid or pid <= 0:
            return []
        result: List[ServiceNetworkConnection] = []
        try:
            proc = psutil.Process(pid)
            conns = proc.net_connections(kind='inet')
            for c in conns[:50]:
                proto = 'TCP' if c.type == socket.SOCK_STREAM else 'UDP'
                laddr = f'{c.laddr.ip}:{c.laddr.port}' if c.laddr else ''
                raddr = f'{c.raddr.ip}:{c.raddr.port}' if c.raddr else ''
                result.append(ServiceNetworkConnection(
                    protocol=proto,
                    local_address=laddr,
                    remote_address=raddr,
                    status=str(c.status or ''),
                ))
        except Exception as exc:
            logger.debug(f'[ServiceCatalogInspector] Ошибка получения сетевых соединений PID={pid}: {exc}')
        return result

    def _collect_event_log_dossier(self, service: ServiceItem, limit: int = 15) -> List[ServiceEventLogEntry]:
        """Извлекает недавние события журнала System, связанные со службой (через WevtAPI)."""
        entries: List[ServiceEventLogEntry] = []
        if os.name != 'nt':
            return entries
        try:
            from apps.windows.sdk.win32_ffi.wevtapi import WevtAPI

            wevt = WevtAPI()
            if not wevt.is_available():
                return entries
            try:
                search_term = service.base_service_name or service.name
                raw_events = wevt.read_events(
                    channel='System',
                    limit=limit,
                    search=search_term,
                    hours=72,
                    format_message=True,
                )
                for ev in raw_events:
                    entries.append(ServiceEventLogEntry(
                        timestamp=str(ev.get('timestamp') or ev.get('time_created') or ''),
                        event_id=int(ev.get('event_id', 0) or 0),
                        level=str(ev.get('level') or ''),
                        provider=str(ev.get('provider') or ev.get('source') or ''),
                        channel=str(ev.get('channel') or 'System'),
                        message=str(ev.get('message') or '')[:500],
                    ))
            finally:
                wevt.close()
        except Exception as exc:
            logger.debug(f'[ServiceCatalogInspector] Ошибка выборки Event Log для {service.name}: {exc}')
        return entries

    def _build_relations_graph(
        self,
        service: ServiceItem,
        registry: ServiceRegistryInfo,
        process: Optional[ServiceProcessMetrics],
        connections: List[ServiceNetworkConnection],
    ) -> Tuple[List[str], List[ServiceRelationNode], List[ServiceRelationEdge]]:
        """Строит цепочку связей и структуру узлов/рёбер для визуализации досье."""
        chain: List[str] = [service.name]
        nodes: List[ServiceRelationNode] = [
            ServiceRelationNode(
                id=f'svc:{service.name}',
                node_type='service',
                label=service.name,
                status=service.status,
                meta={'display_name': service.display_name, 'start_type': service.start_type},
            )
        ]
        edges: List[ServiceRelationEdge] = []

        if service.is_per_user and service.base_service_name:
            tpl_id = f'tpl:{service.base_service_name}'
            chain.append(f'шаблон {service.base_service_name}')
            nodes.append(ServiceRelationNode(id=tpl_id, node_type='template', label=service.base_service_name))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=tpl_id,
                relation_type='instance_of', label='экземпляр шаблона',
            ))

        if process:
            proc_id = f'pid:{process.pid}'
            chain.append(f'{process.name} (PID {process.pid})')
            nodes.append(ServiceRelationNode(
                id=proc_id, node_type='process', label=f'{process.name} (PID {process.pid})',
                status=process.status, meta={'memory_mb': process.memory_mb, 'threads': process.threads_count},
            ))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=proc_id,
                relation_type='hosted_in', label='выполняется в процессе',
            ))

        if registry.svchost_group:
            grp_id = f'grp:{registry.svchost_group}'
            chain.append(f'группа {registry.svchost_group}')
            nodes.append(ServiceRelationNode(
                id=grp_id, node_type='svchost_group', label=registry.svchost_group,
                meta={'members_count': len(service.same_group_services) + 1},
            ))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=grp_id,
                relation_type='member_of_group', label='группа svchost',
            ))

        if registry.service_dll:
            dll_name = os.path.basename(registry.service_dll)
            dll_id = f'dll:{dll_name}'
            chain.append(f'DLL {dll_name}')
            nodes.append(ServiceRelationNode(
                id=dll_id, node_type='dll', label=dll_name, meta={'path': registry.service_dll},
            ))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=dll_id,
                relation_type='loads_dll', label='ServiceDll',
            ))

        for dep in service.dependencies[:12]:
            dep_id = f'svc:{dep}'
            nodes.append(ServiceRelationNode(id=dep_id, node_type='service', label=dep))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=dep_id,
                relation_type='depends_on', label='зависит от',
            ))

        for req in service.dependents[:12]:
            req_id = f'svc:{req}'
            nodes.append(ServiceRelationNode(id=req_id, node_type='service', label=req))
            edges.append(ServiceRelationEdge(
                source=req_id, target=f'svc:{service.name}',
                relation_type='required_by', label='требует службу',
            ))

        for peer in service.shared_pid_services[:12]:
            peer_id = f'svc:{peer}'
            nodes.append(ServiceRelationNode(id=peer_id, node_type='service', label=peer))
            edges.append(ServiceRelationEdge(
                source=f'svc:{service.name}', target=peer_id,
                relation_type='shares_pid_with', label='общий PID',
            ))

        if connections:
            chain.append(f'Сеть ({len(connections)} соед.)')
            for conn in connections[:10]:
                endpoint = conn.remote_address or conn.local_address
                if not endpoint:
                    continue
                net_id = f'net:{conn.protocol}:{endpoint}'
                nodes.append(ServiceRelationNode(
                    id=net_id, node_type='network', label=f'{conn.protocol} {endpoint}', status=conn.status,
                ))
                edges.append(ServiceRelationEdge(
                    source=f'svc:{service.name}', target=net_id,
                    relation_type='connects_to', label=conn.status or conn.protocol,
                ))

        # Дедупликация узлов по id
        unique_nodes = list({n.id: n for n in nodes}.values())
        return chain, unique_nodes, edges

    def build_service_dossier(
        self,
        service: ServiceItem,
        all_services: List[ServiceItem],
        storage: Optional[Any] = None,
    ) -> ServiceDossier:
        """Собирает полное глубокое досье и граф связей для одной службы.

        Args:
            service: Целевая служба.
            all_services: Полный каталог служб (для перекрёстных связей).
            storage: Хранилище TelemetryStorage для извлечения истории изменений.

        Returns:
            Объект ServiceDossier.
        """
        svchost_map = self.read_svchost_groups_map()
        registry = self.read_service_registry_info(service.name, svchost_groups_map=svchost_map)

        # Синхронизируем поля службы с актуальным реестром
        if not service.svchost_group and registry.svchost_group:
            service.svchost_group = registry.svchost_group
        if not service.service_dll and registry.service_dll:
            service.service_dll = registry.service_dll
        if not service.dependencies and registry.dependencies:
            service.dependencies = registry.dependencies

        # Перекрёстные связи по каталогу
        if all_services:
            if not service.dependents:
                service.dependents = sorted(
                    s.name for s in all_services
                    if any(d.lower() == service.name.lower() for d in s.dependencies)
                )
            if service.pid and not service.shared_pid_services:
                service.shared_pid_services = sorted(
                    s.name for s in all_services if s.pid == service.pid and s.name != service.name
                )
            if service.svchost_group and not service.same_group_services:
                service.same_group_services = sorted(
                    s.name for s in all_services
                    if s.svchost_group.lower() == service.svchost_group.lower() and s.name != service.name
                )

        process = self._collect_process_dossier(service.pid)
        connections = self._collect_network_dossier(service.pid)
        events = self._collect_event_log_dossier(service)

        telemetry_history: List[Dict[str, Any]] = []
        if storage is not None and hasattr(storage, 'get_service_change_events'):
            try:
                all_changes = storage.get_service_change_events(limit=100)
                telemetry_history = [
                    ev for ev in all_changes
                    if str(ev.get('service_name') or ev.get('entity_key') or '').lower() == service.name.lower()
                ][:20]
            except Exception as exc:
                logger.debug(f'[ServiceCatalogInspector] Ошибка чтения истории телеметрии: {exc}')

        chain, nodes, edges = self._build_relations_graph(service, registry, process, connections)

        return ServiceDossier(
            service=service,
            registry=registry,
            process=process,
            network_connections=connections,
            recent_events=events,
            telemetry_history=telemetry_history,
            relations_chain=chain,
            graph_nodes=nodes,
            graph_edges=edges,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

    def build_graph_report(self, services: List[ServiceItem]) -> ServicesGraphReport:
        """Строит глобальный аналитический отчет по группам svchost, общим PID и per-user службам.

        Args:
            services: Полный список служб каталога.

        Returns:
            ServicesGraphReport.
        """
        groups_acc: Dict[str, List[ServiceItem]] = defaultdict(list)
        pid_acc: Dict[int, List[ServiceItem]] = defaultdict(list)
        per_user_list: List[Dict[str, str]] = []

        for svc in services:
            if svc.svchost_group:
                groups_acc[svc.svchost_group].append(svc)
            if svc.pid and svc.pid > 0:
                pid_acc[svc.pid].append(svc)
            if svc.is_per_user:
                per_user_list.append({
                    'name': svc.name,
                    'base_service_name': svc.base_service_name,
                    'instance_suffix': svc.instance_suffix,
                    'status': svc.status,
                    'svchost_group': svc.svchost_group,
                })

        group_summaries: List[SvchostGroupSummary] = []
        for g_name, members in sorted(groups_acc.items(), key=lambda x: (-len(x[1]), x[0].lower())):
            unique_pids: Dict[int, ServiceItem] = {}
            for m in members:
                if m.pid and m.pid > 0 and m.pid not in unique_pids:
                    unique_pids[m.pid] = m
            group_summaries.append(SvchostGroupSummary(
                group_name=g_name,
                total_services=len(members),
                running_services=sum(1 for m in members if m.status == 'RUNNING'),
                pids=sorted(unique_pids.keys()),
                total_memory_mb=round(sum(m.memory_mb for m in unique_pids.values()), 2),
                total_network_connections=sum(m.network_connections_count for m in unique_pids.values()),
                services=sorted(m.name for m in members),
            ))

        shared_clusters: List[SharedPidCluster] = []
        for pid, members in sorted(pid_acc.items(), key=lambda x: (-len(x[1]), x[0])):
            if len(members) < 2:
                continue
            lead = members[0]
            shared_clusters.append(SharedPidCluster(
                pid=pid,
                process_name=lead.host_process_name or 'svchost.exe',
                svchost_group=lead.svchost_group,
                memory_mb=lead.memory_mb,
                network_connections_count=lead.network_connections_count,
                services=sorted(m.name for m in members),
            ))

        return ServicesGraphReport(
            total_services=len(services),
            total_groups=len(group_summaries),
            total_shared_pid_clusters=len(shared_clusters),
            total_per_user_instances=len(per_user_list),
            svchost_groups=group_summaries,
            shared_pid_clusters=shared_clusters,
            per_user_instances=sorted(per_user_list, key=lambda x: x['name'].lower()),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


__all__ = [
    'ServiceCatalogInspector',
    'parse_per_user_service_name',
    'extract_svchost_group',
]
