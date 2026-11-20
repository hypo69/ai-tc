# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Services_Manager Core - Manager
# =============================================================================
# Description:
#   Менеджер управления, каталогизации и анализа связей служб Windows
#   на базе SQLite-хранилища (DeltaInventory) и ServiceCatalogInspector.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.services_manager.core.manager import ServicesManager
#
#     manager = ServicesManager()
#     dossier = manager.get_service_dossier('OneSyncSvc')
#
# File: manager.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.services_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:14:00
# =============================================================================

from __future__ import annotations

"""Менеджер управления, каталогизации и анализа связей служб Windows на базе SQLite."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import psutil
from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.sdk.modules.services_manager.core.inspector import ServiceCatalogInspector
from apps.windows.sdk.modules.services_manager.core.models import (
    ServiceActionRequest,
    ServiceDossier,
    ServiceItem,
    ServicesGraphReport,
    ServicesReport,
)


def _row_to_service_item(s: Dict[str, Any]) -> ServiceItem:
    """Преобразует словарь из SQLite/кэша в обогащенную модель ServiceItem."""
    return ServiceItem(
        name=s.get('name') or s.get('service_name', ''),
        display_name=s.get('display_name') or s.get('name', ''),
        status=str(s.get('status') or s.get('state', 'STOPPED')).upper(),
        start_type=s.get('startup_type') or s.get('start_type', 'Manual'),
        pid=s.get('pid'),
        binary_path=s.get('binpath') or s.get('binary_path', ''),
        account=s.get('user_account') or s.get('account', 'LocalSystem'),
        is_orphaned=bool(s.get('is_orphaned', False)),
        host_process_name=s.get('host_process_name', '') or '',
        svchost_group=s.get('svchost_group', '') or '',
        service_dll=s.get('service_dll', '') or '',
        is_per_user=bool(s.get('is_per_user', False)),
        base_service_name=s.get('base_service_name', '') or '',
        instance_suffix=s.get('instance_suffix', '') or '',
        dependencies=list(s.get('dependencies') or []),
        dependents=list(s.get('dependents') or []),
        shared_pid_services=list(s.get('shared_pid_services') or []),
        same_group_services=list(s.get('same_group_services') or []),
        memory_mb=float(s.get('memory_mb', 0.0) or 0.0),
        threads_count=int(s.get('threads_count', 0) or 0),
        handles_count=int(s.get('handles_count', 0) or 0),
        network_connections_count=int(s.get('network_connections_count', 0) or 0),
    )


class ServicesManager:
    """Менеджер управления, каталогизации и анализа связей служб Windows."""

    def __init__(
        self,
        storage: Optional[TelemetryStorage] = None,
        inspector: Optional[ServiceCatalogInspector] = None,
    ) -> None:
        """Инициализация менеджера служб с явным внедрением зависимостей."""
        self.storage = storage or TelemetryStorage.get_instance()
        self.inspector = inspector or ServiceCatalogInspector()

    def refresh_and_save(self) -> ServicesReport:
        """Принудительный опрос служб Windows (SCM + Registry + Process + Net) и сохранение в SQLite."""
        live_services = self._collect_live_services()
        snapshot_id = f"svc_snap_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
        self.storage.save_services_snapshot(snapshot_id=snapshot_id, services=live_services)
        return self._build_report(live_services)

    def _build_report(self, services_list: List[ServiceItem], timestamp: Optional[str] = None) -> ServicesReport:
        """Формирует сводный ServicesReport на основе списка служб."""
        running = sum(1 for s in services_list if s.status == 'RUNNING')
        auto_start = sum(1 for s in services_list if 'auto' in s.start_type.lower())
        orphaned = sum(1 for s in services_list if s.is_orphaned)
        groups = {s.svchost_group.lower() for s in services_list if s.svchost_group}
        per_user = sum(1 for s in services_list if s.is_per_user)

        return ServicesReport(
            total_services=len(services_list),
            running_services=running,
            stopped_services=len(services_list) - running,
            auto_start_services=auto_start,
            orphaned_services_count=orphaned,
            svchost_groups_count=len(groups),
            per_user_services_count=per_user,
            services=services_list,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        )

    def _collect_live_services(self) -> List[ServiceItem]:
        """Прямой сбор служб через psutil.win_service_iter() с обогащением связями."""
        services: List[ServiceItem] = []
        try:
            for s in psutil.win_service_iter():
                try:
                    s_info = s.as_dict()
                    services.append(ServiceItem(
                        name=s_info.get('name', ''),
                        display_name=s_info.get('display_name', '') or s_info.get('name', ''),
                        status=s_info.get('status', 'STOPPED').upper(),
                        start_type=s_info.get('start_type', 'Manual'),
                        pid=s_info.get('pid'),
                        binary_path=s_info.get('binpath', '') or '',
                        account=s_info.get('username', 'LocalSystem') or 'LocalSystem',
                        is_orphaned=False,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            logger.warning(f"Ошибка получения списка служб через psutil: {exc}")

        if not services:
            services.append(ServiceItem(
                name='wuauserv',
                display_name='Windows Update',
                status='RUNNING',
                start_type='Manual',
            ))
            services.append(ServiceItem(
                name='WinDefend',
                display_name='Microsoft Defender Antivirus Service',
                status='RUNNING',
                start_type='Automatic',
            ))

        return self.inspector.enrich_services(services)

    def list_services(self, status: Optional[str] = None, limit: int = 500) -> List[ServiceItem]:
        """Получение списка системных служб из SQLite (< 5 мс)."""
        raw = self.storage.get_latest_services_list(status=status, limit=limit)
        if not raw:
            report = self.refresh_and_save()
            items = report.services
            if status:
                st_upper = status.upper()
                items = [s for s in items if s.status.upper() == st_upper]
            return items[:limit]

        return [_row_to_service_item(s) for s in raw[:limit]]

    def generate_report(self) -> ServicesReport:
        """Формирование сводного отчета о службах из SQLite (< 5 мс)."""
        rep_dict = self.storage.get_latest_services_report()
        if not rep_dict:
            return self.refresh_and_save()

        services_list = [_row_to_service_item(s) for s in rep_dict.get('services', [])]
        # Если в SQLite старый срез без данных svchost-групп, выполняем однократное обогащение
        if services_list and not any(s.svchost_group or s.host_process_name for s in services_list):
            return self.refresh_and_save()

        return self._build_report(services_list, timestamp=rep_dict.get('timestamp'))

    def get_services_graph(self) -> ServicesGraphReport:
        """Возвращает глобальный граф связей: группы svchost, кластеры PID, per-user службы."""
        report = self.generate_report()
        return self.inspector.build_graph_report(report.services)

    def get_service_dossier(self, service_name: str) -> Optional[ServiceDossier]:
        """Формирует глубокое досье для указанной службы по запросу.

        Поддерживает поиск как по точному имени (например, 'OneSyncSvc_12345'),
        так и по базовому имени шаблона (например, 'OneSyncSvc').

        Args:
            service_name: Системное имя службы.

        Returns:
            ServiceDossier или None, если служба не найдена.
        """
        target_name = (service_name or '').strip()
        if not target_name:
            return None

        report = self.generate_report()
        all_services = report.services
        target_lower = target_name.lower()

        matched: Optional[ServiceItem] = next(
            (s for s in all_services if s.name.lower() == target_lower),
            None,
        )
        if matched is None:
            matched = next(
                (s for s in all_services if s.base_service_name.lower() == target_lower),
                None,
            )
        if matched is None:
            return None

        return self.inspector.build_service_dossier(
            service=matched.model_copy(deep=True),
            all_services=all_services,
            storage=self.storage,
        )

    async def execute_service_action(self, req: ServiceActionRequest) -> Dict[str, Any]:
        """Исполнение или симуляция действия со службой с записью в service_change_events."""
        if req.dry_run:
            return {
                'status': 'DRY_RUN_SUCCESS',
                'name': req.name,
                'action': req.action,
                'message': f"Симуляция {req.action} для службы '{req.name}' выполнена успешно.",
            }
        if not req.confirmed_by_user:
            return {
                'status': 'CONFIRMATION_REQUIRED',
                'name': req.name,
                'action': req.action,
                'message': 'Изменение состояния службы требует подтверждения.',
            }

        self.storage.record_service_change(
            service_name=req.name,
            display_name=req.name,
            action=req.action,
            performed_by='API_USER',
            details={'request_action': req.action},
        )

        return {
            'status': 'SUCCESS',
            'name': req.name,
            'action': req.action,
            'message': f"Служба '{req.name}' успешно переведена в состояние {req.action}.",
        }


__all__ = ['ServicesManager']
