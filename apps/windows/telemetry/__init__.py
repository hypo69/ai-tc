# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Package Root
# =============================================================================
# Description:
#   Слой 3: Сбор, хранение, каталогизация и аналитика телеметрии Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry import SystemCollector, DiagnosticEngine
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 08:00:00
# =============================================================================

from __future__ import annotations
"""Единый слой телеметрии Windows (Слой 3) платформы AI-Windows-Admin."""

# Регистрация алиасов обратной совместимости для win32_ffi и analytics
try:
    from roadmap.patches.package_structure_refactoring import setup_package_aliases
    setup_package_aliases()
except Exception:
    pass

# Импорт перечислений из слоя apps.windows.contracts
from apps.windows.contracts import (
    RiskLevel,
    TelemetryTier,
    ProcessState,
    ThreadState,
)

# Модели телеметрии
from apps.windows.telemetry.models import (
    AnomalyItem,
    BatteryMetrics,
    CloudStorageInfo,
    CpuMetrics,
    DiskIoMetrics,
    DiskPartitionMetrics,
    DriverInfo,
    ForensicsActivityReport,
    GpuMetrics,
    HardwareArchiveEntry,
    HardwareAuditReport,
    HardwareChangeItem,
    HardwareDeviceAudit,
    HardwareNode,
    HardwareSensor,
    KernelThrottlingReport,
    MemoryMetrics,
    MonitorInfo,
    NetworkInterfaceMetrics,
    NetworkPortMetrics,
    NpuMetrics,
    OfficeSuiteInfo,
    PeripheralsNetworkReport,
    PhysicalDiskHealth,
    ProcessLeakDiagnosticsReport,
    ProcessLeakItem,
    ProcessLifecycleEvent,
    ProcessMetrics,
    ProcessNetworkActivity,
    ProcessProvenanceInfo,
    ProcessProvenanceReport,
    ProcessTokenInfo,
    RamStickInfo,
    StartupArchiveEntry,
    StartupChangeItem,
    StorageBatteryWearReport,
    SystemCoreMetrics,
    SystemDiagnosticReport,
    SystemHardwareQuick,
    SystemHealthAlerts,
    SystemSnapshot,
    TelemetryIncident,
    W64CollectorStatus,
    W64SystemEvent,
    WindowsUpdateInfo,
    ETWTraceEvent,
    SecurityAuditStatus,
    SecurityBookmarkState,
    SecurityCollectorReport,
    SecurityCorrelationItem,
    SecurityEventItem,
    SecurityEventRaw,
)

# Хранилище и база данных
from apps.windows.telemetry.sqlite import (
    AggregationLevel,
    TelemetryBuffer,
    TelemetryConnectionManager,
    TelemetryMaintenance,
    TelemetryReader,
    TelemetrySqlAggregator,
    TelemetryStorage,
    TelemetryWriter,
    sensors_aggregate,
)
from apps.windows.telemetry.ring_buffer import TelemetryRingBuffer
from apps.windows.telemetry.init_db import (
    init_telemetry_database,
    init_telemetry_database as init_telemetry_db,
    get_default_telemetry_db_path,
)

# Коллекторы и датчики
from apps.windows.telemetry.sensors import get_hardware_sensors
from apps.windows.telemetry.collector import SystemCollector
from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.telemetry_engine import TelemetryEngine, DeadbandTracker
from apps.windows.telemetry.telemetry_buffer_manager import TelemetryBufferManager
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager, get_default_telemetry_config_path
from apps.windows.telemetry.json_logger import TelemetryJsonLogger
from apps.windows.telemetry.file_collector import FileCollector
from apps.windows.telemetry.sensor_collector import SensorCollector
from apps.windows.telemetry.device_flapping_sensor import DeviceFlappingSensor, DeviceTransitionEvent
from apps.windows.telemetry.storage_usage import WindowsStorageUsageCollector
from apps.windows.telemetry.w64_collector import (
    AIW64Collector,
    get_w64_collector,
    start_w64_collector,
    stop_w64_collector,
)
from apps.windows.telemetry.w64_etw_collector import AIW64ETWCollector
from apps.windows.telemetry.security_collector import WindowsSecurityCollector
from apps.windows.telemetry.security_normalizer import SecurityEventNormalizer
from apps.windows.telemetry.hardware_collector import HardwareCollector

# Аналитический контур (прямой импорт без lazy __getattr__)
from apps.windows.analytics.aggregator import TelemetryAggregator
from apps.windows.analytics.analyzer import TelemetryAnalyzer
from apps.windows.analytics.compactor import TelemetryCompactor
from apps.windows.analytics.diagnostic_engine import DiagnosticEngine, SystemDiagnosticEngine
from apps.windows.analytics.grouped_telemetry import GroupedTelemetryBuilder
from apps.windows.analytics.incident_detector import IncidentDetector
from apps.windows.analytics.reboot_analyzer import WindowsRebootAnalyzer, RebootAnalyzer
from apps.windows.analytics.hardware_auditor import HardwareAuditor
from apps.windows.analytics.deep_diagnostics import DeepDiagnosticsEngine
from apps.windows.analytics.hardware_history_manager import HardwareHistoryManager

# Каталог событий
from apps.windows.telemetry.catalog.event_catalog import WindowsEventCatalog

__all__ = [
    # Контракты и модели
    "RiskLevel",
    "TelemetryTier",
    "ProcessState",
    "ThreadState",
    "CpuMetrics",
    "MemoryMetrics",
    "GpuMetrics",
    "HardwareSensor",
    "HardwareNode",
    "SystemSnapshot",
    "ProcessMetrics",
    "ProcessTokenInfo",
    "TelemetryIncident",
    "AnomalyItem",
    "BatteryMetrics",
    "DiskIoMetrics",
    "DiskPartitionMetrics",
    "DriverInfo",
    "ForensicsActivityReport",
    "HardwareArchiveEntry",
    "HardwareAuditReport",
    "HardwareChangeItem",
    "HardwareDeviceAudit",
    "KernelThrottlingReport",
    "NetworkInterfaceMetrics",
    "NetworkPortMetrics",
    "PeripheralsNetworkReport",
    "PhysicalDiskHealth",
    "ProcessLeakDiagnosticsReport",
    "ProcessLeakItem",
    "ProcessLifecycleEvent",
    "ProcessNetworkActivity",
    "ProcessProvenanceInfo",
    "ProcessProvenanceReport",
    "RamStickInfo",
    "StorageBatteryWearReport",
    "SystemDiagnosticReport",
    "SystemHealthAlerts",
    "W64CollectorStatus",
    "W64SystemEvent",
    "ETWTraceEvent",
    "SecurityAuditStatus",
    "SecurityBookmarkState",
    "SecurityCollectorReport",
    "SecurityCorrelationItem",
    "SecurityEventItem",
    "SecurityEventRaw",
    # Коллекторы
    "SystemCollector",
    "HardwareCollector",
    "SensorCollector",
    "FileCollector",
    "WindowsSecurityCollector",
    "SecurityEventNormalizer",
    "WindowsStorageUsageCollector",
    "AIW64Collector",
    "AIW64ETWCollector",
    "get_w64_collector",
    "start_w64_collector",
    "stop_w64_collector",
    "get_hardware_sensors",
    "DeviceFlappingSensor",
    "DeviceTransitionEvent",
    # Хранилище
    "TelemetryRingBuffer",
    "TelemetryBufferManager",
    "init_telemetry_db",
    "init_telemetry_database",
    "get_default_telemetry_db_path",
    "TelemetryStorage",
    "TelemetrySqlAggregator",
    "AggregationLevel",
    "sensors_aggregate",
    "TelemetryLoggerService",
    "TelemetryEngine",
    "DeadbandTracker",
    "TelemetryConfigManager",
    "TelemetryJsonLogger",
    "get_default_telemetry_config_path",
    # Аналитика
    "DiagnosticEngine",
    "SystemDiagnosticEngine",
    "GroupedTelemetryBuilder",
    "IncidentDetector",
    "WindowsRebootAnalyzer",
    "RebootAnalyzer",
    "TelemetryAggregator",
    "TelemetryAnalyzer",
    "TelemetryCompactor",
    "HardwareAuditor",
    "DeepDiagnosticsEngine",
    "HardwareHistoryManager",
    # Каталог
    "WindowsEventCatalog",
]
