# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Services_Manager Core - Models
# =============================================================================
# Description:
#   Pydantic-модели каталога служб Windows, графа их связей (svchost-группы,
#   зависимости, общие PID, per-user экземпляры) и глубокого досье службы
#   (реестр, процесс, сеть, журнал событий, телеметрия AI-TC).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.services_manager.core.models import ServiceItem, ServiceDossier
#
#     service = ServiceItem(name='OneSyncSvc_12345')
#
# File: models.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.services_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:11:00
# =============================================================================

from __future__ import annotations

"""Модели данных каталога служб Windows, графа связей и глубокого досье."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ServiceItem(BaseModel):
    """Обогащённая информация о службе Windows и её связях в системе."""

    name: str
    display_name: str = ''
    status: str = 'STOPPED'  # RUNNING, STOPPED, PAUSED
    start_type: str = 'Manual'  # Auto, Manual, Disabled
    pid: Optional[int] = None
    binary_path: str = ''
    account: str = 'LocalSystem'
    is_orphaned: bool = False

    # Инфраструктура хоста и экземпляров (svchost / per-user)
    host_process_name: str = ''
    svchost_group: str = ''
    service_dll: str = ''
    is_per_user: bool = False
    base_service_name: str = ''
    instance_suffix: str = ''

    # Граф связей
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    shared_pid_services: List[str] = Field(default_factory=list)
    same_group_services: List[str] = Field(default_factory=list)

    # Быстрые метрики процесса и сети (O(N) по активным PID)
    memory_mb: float = 0.0
    threads_count: int = 0
    handles_count: int = 0
    network_connections_count: int = 0


class ServicesReport(BaseModel):
    """Сводный отчет о службах Windows."""

    total_services: int = 0
    running_services: int = 0
    stopped_services: int = 0
    auto_start_services: int = 0
    orphaned_services_count: int = 0
    svchost_groups_count: int = 0
    per_user_services_count: int = 0
    services: List[ServiceItem] = Field(default_factory=list)
    timestamp: str = ''


class ServiceActionRequest(BaseModel):
    """Запрос на действие со службой."""

    name: str
    action: str  # start, stop, pause, continue, set_start_type
    start_type: Optional[str] = None
    dry_run: bool = True
    confirmed_by_user: bool = False


class ServiceRegistryInfo(BaseModel):
    """Конфигурация службы из реестра Windows (HKLM\\SYSTEM\\CurrentControlSet\\Services)."""

    service_key: str = ''
    service_dll: str = ''
    image_path: str = ''
    object_name: str = ''
    description: str = ''
    start_code: Optional[int] = None
    service_type_code: Optional[int] = None
    delayed_auto_start: bool = False
    failure_actions_configured: bool = False
    svchost_group: str = ''
    svchost_group_members: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class ServiceProcessMetrics(BaseModel):
    """Метрики хост-процесса службы (CPU, RAM, потоки, дескрипторы, I/O, файлы)."""

    pid: int
    name: str = ''
    exe: str = ''
    cmdline: str = ''
    status: str = ''
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    threads_count: int = 0
    handles_count: int = 0
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    open_files: List[str] = Field(default_factory=list)
    loaded_modules_sample: List[str] = Field(default_factory=list)


class ServiceNetworkConnection(BaseModel):
    """Активное сетевое соединение хост-процесса службы."""

    protocol: str = 'TCP'
    local_address: str = ''
    remote_address: str = ''
    status: str = ''


class ServiceEventLogEntry(BaseModel):
    """Запись журнала событий Windows (WevtAPI), связанная со службой."""

    timestamp: str = ''
    event_id: int = 0
    level: str = ''
    provider: str = ''
    channel: str = 'System'
    message: str = ''


class ServiceRelationNode(BaseModel):
    """Узел графа связей службы."""

    id: str
    node_type: str  # service, template, process, svchost_group, dll, network
    label: str
    status: str = ''
    meta: Dict[str, Any] = Field(default_factory=dict)


class ServiceRelationEdge(BaseModel):
    """Направленная связь в графе службы."""

    source: str
    target: str
    relation_type: str  # hosted_in, member_of_group, depends_on, required_by, shares_pid_with, loads_dll, connects_to, instance_of
    label: str = ''


class ServiceDossier(BaseModel):
    """Глубокое досье службы Windows: SCM, реестр, процесс, сеть, Event Log, телеметрия и граф связей."""

    service: ServiceItem
    registry: ServiceRegistryInfo = Field(default_factory=ServiceRegistryInfo)
    process: Optional[ServiceProcessMetrics] = None
    network_connections: List[ServiceNetworkConnection] = Field(default_factory=list)
    recent_events: List[ServiceEventLogEntry] = Field(default_factory=list)
    telemetry_history: List[Dict[str, Any]] = Field(default_factory=list)
    relations_chain: List[str] = Field(default_factory=list)
    graph_nodes: List[ServiceRelationNode] = Field(default_factory=list)
    graph_edges: List[ServiceRelationEdge] = Field(default_factory=list)
    collected_at: str = ''


class SvchostGroupSummary(BaseModel):
    """Сводка по группе служб svchost (например, UnistackSvcGroup, netsvcs)."""

    group_name: str
    total_services: int = 0
    running_services: int = 0
    pids: List[int] = Field(default_factory=list)
    total_memory_mb: float = 0.0
    total_network_connections: int = 0
    services: List[str] = Field(default_factory=list)


class SharedPidCluster(BaseModel):
    """Кластер служб, разделяющих общий PID хост-процесса (например, svchost.exe)."""

    pid: int
    process_name: str = 'svchost.exe'
    svchost_group: str = ''
    memory_mb: float = 0.0
    network_connections_count: int = 0
    services: List[str] = Field(default_factory=list)


class ServicesGraphReport(BaseModel):
    """Глобальный аналитический граф связей всех служб Windows."""

    total_services: int = 0
    total_groups: int = 0
    total_shared_pid_clusters: int = 0
    total_per_user_instances: int = 0
    svchost_groups: List[SvchostGroupSummary] = Field(default_factory=list)
    shared_pid_clusters: List[SharedPidCluster] = Field(default_factory=list)
    per_user_instances: List[Dict[str, str]] = Field(default_factory=list)
    timestamp: str = ''


__all__ = [
    'ServiceItem',
    'ServicesReport',
    'ServiceActionRequest',
    'ServiceRegistryInfo',
    'ServiceProcessMetrics',
    'ServiceNetworkConnection',
    'ServiceEventLogEntry',
    'ServiceRelationNode',
    'ServiceRelationEdge',
    'ServiceDossier',
    'SvchostGroupSummary',
    'SharedPidCluster',
    'ServicesGraphReport',
]
