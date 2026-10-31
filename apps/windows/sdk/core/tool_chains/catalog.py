# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Catalog
# =============================================================================
# Description:
#   Каталог типовых шаблонов диагностических и административных цепочек инструментов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.catalog import get_builtin_chains
#     chains = get_builtin_chains()
#
# File: catalog.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""Каталог готовых и протестированных шаблонов диагностических цепочек Windows."""

from typing import Dict
from apps.windows.contracts.enums import CapabilityCategory, ExecutionMethod, PrivilegeLevel, RiskLevel
from apps.windows.sdk.core.tool_chains.models import (
    BranchCondition,
    ChainDefinition,
    ChainStepDefinition,
    CompensationAction,
    ConditionOperator,
)


def get_builtin_chains() -> Dict[str, ChainDefinition]:
    """Формирует и возвращает словарь встроенных типовых цепочек инструментов."""
    chains: Dict[str, ChainDefinition] = {}

    # 1. Диагностика недоступности порта и локального сервиса
    port_diag = ChainDefinition(
        chain_id="diag.network.port_availability",
        title_ru="Диагностика недоступности порта и сетевого сервиса",
        description="Пошаговая проверка доступности локального порта, владельца PID, службы Windows и сетевых ошибок в журналах.",
        category=CapabilityCategory.NETWORK,
        initial_step_id="check_tcp_listener",
        requires_restore_point=False,
        steps={
            "check_tcp_listener": ChainStepDefinition(
                step_id="check_tcp_listener",
                tool_id="netstat.connections",
                name_ru="Проверка слушающего TCP сокета",
                description="Проверяет наличие слушающего сокета на указанном порту через Get-NetTCPConnection или netstat.",
                arguments={"port": 8001},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                branch_conditions=[
                    BranchCondition(
                        operator=ConditionOperator.IS_NOT_EMPTY,
                        field_path="stdout",
                        target_step_id="get_owning_process",
                    ),
                    BranchCondition(
                        operator=ConditionOperator.IS_EMPTY,
                        field_path="stdout",
                        target_step_id="check_service_status",
                    ),
                ],
                next_step_id="get_owning_process",
            ),
            "get_owning_process": ChainStepDefinition(
                step_id="get_owning_process",
                tool_id="process.inspect_pid",
                name_ru="Определение процесса-владельца PID",
                description="Получает детальную информацию о процессе, удерживающем порт.",
                arguments={},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="test_local_connectivity",
            ),
            "check_service_status": ChainStepDefinition(
                step_id="check_service_status",
                tool_id="service.query",
                name_ru="Проверка состояния связанных служб",
                description="Поиск службы Windows, которая должна была открыть указанный порт.",
                arguments={},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="inspect_event_logs",
            ),
            "test_local_connectivity": ChainStepDefinition(
                step_id="test_local_connectivity",
                tool_id="test.net_connection",
                name_ru="Тест локального сетевого подключения",
                description="Проверка ответа TCP стека на выбранном IP-адресе и порту.",
                arguments={"port": 8001},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="inspect_event_logs",
            ),
            "inspect_event_logs": ChainStepDefinition(
                step_id="inspect_event_logs",
                tool_id="wevtutil.query",
                name_ru="Анализ ошибок в системных журналах",
                description="Поиск недавних событий сбоев, таймаутов или блокировок брандмауэра.",
                arguments={"log_name": "System", "level": "Error"},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id=None,
            ),
        },
    )
    chains[port_diag.chain_id] = port_diag

    # 2. Расследование скачков записи на накопитель (SSD I/O Investigation)
    ssd_diag = ChainDefinition(
        chain_id="diag.storage.ssd_write_spikes",
        title_ru="Расследование скачков дисковой активности на SSD",
        description="Анализ процессов с интенсивной записью, проверка очереди диска, файловой системы и SMART-статуса.",
        category=CapabilityCategory.STORAGE_FS,
        initial_step_id="query_disk_telemetry",
        requires_restore_point=False,
        steps={
            "query_disk_telemetry": ChainStepDefinition(
                step_id="query_disk_telemetry",
                tool_id="storage.telemetry.metrics",
                name_ru="Сбор метрик очереди и задержки диска",
                description="Опрос текущей длины очереди диска, скорости записи и времени отклика.",
                arguments={},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="find_heavy_io_processes",
            ),
            "find_heavy_io_processes": ChainStepDefinition(
                step_id="find_heavy_io_processes",
                tool_id="process.heavy_io",
                name_ru="Поиск процессов с высоким Write Bytes/sec",
                description="Сортировка запущенных процессов по скорости записи в байтах.",
                arguments={"top": 5},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="check_filesystem_state",
            ),
            "check_filesystem_state": ChainStepDefinition(
                step_id="check_filesystem_state",
                tool_id="fsutil.dirty.query",
                name_ru="Проверка флага целостности тома (Dirty bit)",
                description="Проверка, помечен ли том как поврежденный или требующий проверки chkdsk.",
                arguments={"volume": "C:"},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="query_disk_events",
            ),
            "query_disk_events": ChainStepDefinition(
                step_id="query_disk_events",
                tool_id="wevtutil.disk_events",
                name_ru="Поиск аппаратных дисковых ошибок (disk/stornvme/ntfs)",
                description="Выборка предупреждений и ошибок контроллера диска в System Event Log.",
                arguments={"log_name": "System"},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id=None,
            ),
        },
    )
    chains[ssd_diag.chain_id] = ssd_diag

    # 3. Безопасный перезапуск службы с замкнутым контуром (Service Restart Loop)
    service_restart = ChainDefinition(
        chain_id="admin.service.safe_restart",
        title_ru="Контролируемый безопасный перезапуск службы",
        description="Проверка зависимостей службы, остановка, запуск, верификация статуса и компенсация при сбое.",
        category=CapabilityCategory.SERVICES,
        initial_step_id="check_dependencies",
        requires_restore_point=False,
        steps={
            "check_dependencies": ChainStepDefinition(
                step_id="check_dependencies",
                tool_id="sc.enum_depend",
                name_ru="Проверка зависимостей службы",
                description="Инвентаризация зависимых служб перед остановкой.",
                arguments={"service_name": "wuauserv"},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id="stop_service_step",
            ),
            "stop_service_step": ChainStepDefinition(
                step_id="stop_service_step",
                tool_id="sc.stop",
                name_ru="Остановка целевой службы",
                description="Посылка сигнала остановки в Service Control Manager.",
                arguments={"service_name": "wuauserv"},
                risk_level=RiskLevel.MEDIUM,
                required_privilege=PrivilegeLevel.ADMINISTRATOR,
                execution_method=ExecutionMethod.CLI,
                timeout_seconds=30,
                compensation=CompensationAction(
                    action_id="compensate_start",
                    tool_id="sc.start",
                    arguments={"service_name": "wuauserv"},
                    description="Экстренный запуск службы при нарушении цепочки",
                ),
                next_step_id="start_service_step",
            ),
            "start_service_step": ChainStepDefinition(
                step_id="start_service_step",
                tool_id="sc.start",
                name_ru="Запуск целевой службы",
                description="Инициализация старта службы в SCM.",
                arguments={"service_name": "wuauserv"},
                risk_level=RiskLevel.MEDIUM,
                required_privilege=PrivilegeLevel.ADMINISTRATOR,
                execution_method=ExecutionMethod.CLI,
                timeout_seconds=30,
                next_step_id="verify_service_running",
            ),
            "verify_service_running": ChainStepDefinition(
                step_id="verify_service_running",
                tool_id="sc.query",
                name_ru="Верификация статуса RUNNING",
                description="Подтверждение того, что служба успешно перешла в рабочее состояние.",
                arguments={"service_name": "wuauserv"},
                risk_level=RiskLevel.READ_ONLY,
                required_privilege=PrivilegeLevel.STANDARD,
                execution_method=ExecutionMethod.CLI,
                next_step_id=None,
            ),
        },
    )
    chains[service_restart.chain_id] = service_restart

    return chains

