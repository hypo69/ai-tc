# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Network - LAN Visibility Diagnostics
# =============================================================================
# Description:
#   Сквозная независимая диагностика видимости компьютера в локальной сети
#   по 4 уровням (L1 Профиль сети, L2 Службы Windows, L3 Брандмауэр,
#   L4 SMB и общие ресурсы), а также механизм снимков состояния «до изменения»
#   и безопасного отката (Rollback).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.lan_visibility_diagnostics import (
#         LanVisibilityDiagnostics,
#     )
#
#     diag = LanVisibilityDiagnostics()
#     report = diag.diagnose()
#     snap = diag.create_snapshot('before_sharing_enable')
#     diag.rollback(snap.snapshot_id)
#
# File: lan_visibility_diagnostics.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:54:00
# =============================================================================

from __future__ import annotations
"""Сквозная диагностика 4 уровней видимости ПК в LAN и откат конфигурации."""

import json
import os
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from apps.common.telemetry_logger import AppTelemetryLogger
from logger import logger
from .discovery import NetworkDiscoveryManager, PsRunnerFn
from .smb_sharing import IsAdminFn, WindowsSmbSharingManager, _default_is_admin, _default_ps_runner


SeverityLevel = Literal['ok', 'info', 'warning', 'error']
LevelCode = Literal['L1', 'L2', 'L3', 'L4']

_MAX_SNAPSHOTS = 50


def _default_snapshot_dir() -> Path:
    """Возвращает каталог хранения снимков конфигурации сети в %APPDATA%."""
    appdata = os.environ.get('APPDATA')
    base = Path(appdata) if appdata else Path.home()
    return base / 'ai-tc' / 'network_visibility_snapshots'


class VisibilityFinding(BaseModel):
    """Конкретная диагностическая находка по видимости ПК в локальной сети."""

    code: str = Field(description='Код правила (VIS001..VIS010)')
    level: LevelCode = Field(description='Уровень диагностики (L1..L4)')
    severity: SeverityLevel = Field(description='Уровень важности')
    title: str = Field(description='Краткое описание проблемы')
    detail: str = Field(description='Техническая расшифровка')
    recommendation: str = Field(default='', description='Рекомендуемое действие')


class VisibilityLevelStatus(BaseModel):
    """Состояние отдельного уровня сетевой видимости."""

    level: LevelCode = Field(description='Код уровня (L1..L4)')
    name: str = Field(description='Название уровня')
    status: Literal['ok', 'warning', 'error'] = Field(description='Агрегированный статус уровня')
    summary: str = Field(description='Краткая сводка состояния')
    details: Dict[str, Any] = Field(default_factory=dict, description='Структурированные метрики уровня')


class LanVisibilityReport(BaseModel):
    """Итоговый 4-уровневый отчёт диагностики видимости ПК в локальной сети."""

    timestamp: str = Field(description='Метка времени UTC ISO 8601')
    hostname: str = Field(description='Имя текущего компьютера')
    overall_status: Literal['ok', 'warning', 'error'] = Field(description='Общий статус диагностики')
    is_discoverable: bool = Field(description='Виден ли компьютер через Network Discovery')
    is_file_sharing_ready: bool = Field(description='Готов ли компьютер к File & Printer Sharing (SMB)')
    levels: List[VisibilityLevelStatus] = Field(default_factory=list, description='Диагностика по уровням L1..L4')
    findings: List[VisibilityFinding] = Field(default_factory=list, description='Обнаруженные проблемы и предупреждения')


class NetworkConfigSnapshot(BaseModel):
    """Снимок исходного состояния сетевых настроек для отката (Rollback)."""

    snapshot_id: str = Field(description='Уникальный идентификатор снимка')
    created_at: str = Field(description='Время создания UTC ISO 8601')
    reason: str = Field(default='manual', description='Причина создания снимка')
    profiles: List[Dict[str, Any]] = Field(default_factory=list, description='Сетевые профили адаптеров')
    discovery_firewall_enabled: bool = Field(default=False, description='Были ли включены правила Network Discovery')
    sharing_firewall_enabled: bool = Field(default=False, description='Были ли включены правила File & Printer Sharing')
    services: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description='Состояния 6 сетевых служб')


class RollbackResult(BaseModel):
    """Результат восстановления конфигурации из снимка."""

    success: bool = Field(description='Успешность восстановления')
    snapshot_id: str = Field(description='Идентификатор использованного снимка')
    message: str = Field(description='Итоговое сообщение')
    requires_admin: bool = Field(default=False, description='Требуются ли права администратора')
    restored_steps: List[str] = Field(default_factory=list, description='Лог выполненных шагов отката')


class LanVisibilityDiagnostics:
    """4-уровневый диагност видимости Windows в локальной сети и менеджер снимков."""

    def __init__(
        self,
        discovery_manager: Optional[NetworkDiscoveryManager] = None,
        smb_manager: Optional[WindowsSmbSharingManager] = None,
        snapshot_dir: Optional[Path] = None,
        ps_runner: Optional[PsRunnerFn] = None,
        is_admin_fn: Optional[IsAdminFn] = None,
    ) -> None:
        """Инициализирует диагност видимости сети.

        Args:
            discovery_manager: Менеджер Network Discovery (DI).
            smb_manager: Менеджер File & Printer Sharing (DI).
            snapshot_dir: Каталог для хранения JSON-снимков отката.
            ps_runner: Функция запуска PowerShell (DI).
            is_admin_fn: Функция проверки прав администратора (DI).
        """
        self._ps_runner: PsRunnerFn = ps_runner or _default_ps_runner
        self._is_admin_fn: IsAdminFn = is_admin_fn or _default_is_admin
        self._discovery = discovery_manager or NetworkDiscoveryManager(ps_runner=self._ps_runner)
        self._smb = smb_manager or WindowsSmbSharingManager(
            ps_runner=self._ps_runner,
            is_admin_fn=self._is_admin_fn,
        )
        self._snapshot_dir: Path = snapshot_dir or _default_snapshot_dir()
        self._telemetry_logger = AppTelemetryLogger('network_visibility')

    @staticmethod
    def _aggregate_status(severities: List[SeverityLevel]) -> Literal['ok', 'warning', 'error']:
        """Вычисляет итоговый статус по списку уровней важности."""
        if 'error' in severities:
            return 'error'
        if 'warning' in severities:
            return 'warning'
        return 'ok'

    def diagnose(self) -> LanVisibilityReport:
        """Выполняет независимую диагностику всех 4 уровней видимости ПК в LAN.

        Returns:
            LanVisibilityReport: Детальный отчёт с причинами проблем по уровням L1..L4.
        """
        disc = self._discovery.inspect()
        smb = self._smb.get_status()
        findings: List[VisibilityFinding] = []

        # --- Уровень 1: Network Profile ---
        profiles = disc.get('profiles') or []
        public_profiles = [p for p in profiles if str(p.get('NetworkCategory', '')).lower() == 'public']
        l1_sev: List[SeverityLevel] = []

        if not profiles:
            l1_sev.append('error')
            findings.append(
                VisibilityFinding(
                    code='VIS002',
                    level='L1',
                    severity='error',
                    title='Не обнаружены активные сетевые профили',
                    detail='Get-NetConnectionProfile не вернул ни одного активного подключения.',
                    recommendation='Проверьте состояние сетевых адаптеров и подключение к локальной сети.',
                )
            )
        elif public_profiles:
            l1_sev.append('warning')
            aliases = ', '.join(str(p.get('InterfaceAlias') or p.get('Name')) for p in public_profiles)
            findings.append(
                VisibilityFinding(
                    code='VIS001',
                    level='L1',
                    severity='warning',
                    title='Активен общедоступный сетевой профиль (Public)',
                    detail=f'Интерфейсы в профиле Public: {aliases}. Windows блокирует обнаружение и SMB в публичных сетях.',
                    recommendation='Переключите профиль на Private только если вы уверены, что это доверенная домашняя/офисная сеть.',
                )
            )

        l1_status = VisibilityLevelStatus(
            level='L1',
            name='Сетевой профиль (Network Profile)',
            status=self._aggregate_status(l1_sev),
            summary=(
                'Все активные интерфейсы в доверенном профиле (Private/Domain)'
                if not l1_sev
                else (f'Найдены Public-интерфейсы ({len(public_profiles)})' if public_profiles else 'Нет активных профилей')
            ),
            details={'current_category': disc.get('current_category', 'Unknown'), 'profiles': profiles},
        )

        # --- Уровень 2: Windows Services ---
        disc_svcs = disc.get('services') or {}
        fdres_ok = bool(disc_svcs.get('fdres_running'))
        fdphost_ok = bool(disc_svcs.get('fdphost_running'))
        ssdp_ok = bool(disc_svcs.get('ssdp_running'))
        upnp_ok = bool(disc_svcs.get('upnp_running'))
        srv_ok = smb.lanman_server.running
        wks_ok = smb.lanman_workstation.running
        l2_sev: List[SeverityLevel] = []

        if not fdres_ok or not fdphost_ok:
            l2_sev.append('error')
            stopped = [n for n, ok in (('FDResPub', fdres_ok), ('fdPHost', fdphost_ok)) if not ok]
            findings.append(
                VisibilityFinding(
                    code='VIS003',
                    level='L2',
                    severity='error',
                    title='Остановлены ключевые службы публикации в сети',
                    detail=f"Не запущены службы: {', '.join(stopped)}. Компьютер не будет отображаться в Проводнике Windows.",
                    recommendation='Включите Network Discovery или запустите службы FDResPub и fdPHost.',
                )
            )
        if not ssdp_ok or not upnp_ok:
            l2_sev.append('info')
            stopped_u = [n for n, ok in (('SSDPSRV', ssdp_ok), ('upnphost', upnp_ok)) if not ok]
            findings.append(
                VisibilityFinding(
                    code='VIS004',
                    level='L2',
                    severity='info',
                    title='Службы SSDP/UPnP остановлены',
                    detail=f"Не запущены: {', '.join(stopped_u)}. Обнаружение UPnP-устройств и маршрутизаторов может быть ограничено.",
                    recommendation='Запускайте только если требуется обнаружение UPnP/DLNA устройств.',
                )
            )
        if not srv_ok or not wks_ok:
            l2_sev.append('warning')
            stopped_smb = [n for n, ok in (('LanmanServer', srv_ok), ('LanmanWorkstation', wks_ok)) if not ok]
            findings.append(
                VisibilityFinding(
                    code='VIS005',
                    level='L2',
                    severity='warning',
                    title='Остановлены службы SMB',
                    detail=f"Не запущены службы SMB: {', '.join(stopped_smb)}.",
                    recommendation='Запустите LanmanServer для публикации папок и LanmanWorkstation для подключения к удалённым шарам.',
                )
            )

        l2_status = VisibilityLevelStatus(
            level='L2',
            name='Системные службы (Windows Services)',
            status=self._aggregate_status(l2_sev),
            summary=(
                'Все ключевые службы обнаружения и SMB запущены'
                if not any(s in ('warning', 'error') for s in l2_sev)
                else 'Часть служб обнаружения или SMB остановлена'
            ),
            details={
                'FDResPub': disc_svcs.get('FDResPub', {}),
                'fdPHost': disc_svcs.get('fdPHost', {}),
                'SSDPSRV': disc_svcs.get('SSDPSRV', {}),
                'upnphost': disc_svcs.get('upnphost', {}),
                'LanmanServer': smb.lanman_server.model_dump(),
                'LanmanWorkstation': smb.lanman_workstation.model_dump(),
            },
        )

        # --- Уровень 3: Windows Firewall ---
        disc_fw = disc.get('firewall') or {}
        disc_fw_ok = bool(disc_fw.get('is_enabled'))
        smb_fw_ok = smb.firewall.is_enabled
        l3_sev: List[SeverityLevel] = []

        if not disc_fw_ok:
            l3_sev.append('error')
            findings.append(
                VisibilityFinding(
                    code='VIS006',
                    level='L3',
                    severity='error',
                    title='Брандмауэр блокирует Network Discovery',
                    detail='Группа правил @FirewallAPI.dll,-32752 отключена в активном хранилище Windows Firewall.',
                    recommendation='Включите правила Network Discovery для доверенного профиля (Private/Domain).',
                )
            )
        if not smb_fw_ok:
            l3_sev.append('warning')
            findings.append(
                VisibilityFinding(
                    code='VIS007',
                    level='L3',
                    severity='warning',
                    title='Брандмауэр блокирует File and Printer Sharing',
                    detail='Входящие правила группы @FirewallAPI.dll,-28502 отключены.',
                    recommendation='Включите File and Printer Sharing для Private/Domain, если нужен доступ к общим папкам.',
                )
            )

        l3_status = VisibilityLevelStatus(
            level='L3',
            name='Брандмауэр Windows (Firewall)',
            status=self._aggregate_status(l3_sev),
            summary=(
                'Правила Discovery и File Sharing активны'
                if not l3_sev
                else 'Правила брандмауэра ограничивают обнаружение или общий доступ'
            ),
            details={
                'network_discovery': disc_fw,
                'file_and_printer_sharing': smb.firewall.model_dump(),
            },
        )

        # --- Уровень 4: SMB & Shares ---
        l4_sev: List[SeverityLevel] = []
        if smb.smb1_warning:
            l4_sev.append('warning')
            findings.append(
                VisibilityFinding(
                    code='VIS008',
                    level='L4',
                    severity='warning',
                    title='Включён устаревший небезопасный протокол SMB 1.0',
                    detail='Get-SmbServerConfiguration показывает EnableSMB1Protocol = True.',
                    recommendation='Отключите SMB 1.0, если нет критической зависимости от устаревшего оборудования.',
                )
            )
        if smb.server_config.available and smb.server_config.smb2_enabled is False:
            l4_sev.append('error')
            findings.append(
                VisibilityFinding(
                    code='VIS009',
                    level='L4',
                    severity='error',
                    title='Отключён протокол SMB 2/3',
                    detail='EnableSMB2Protocol = False — современные клиенты Windows не смогут подключиться к шарам.',
                    recommendation='Включите SMB 2/3 через Set-SmbServerConfiguration -EnableSMB2Protocol $true.',
                )
            )
        if smb.user_shares_count == 0:
            l4_sev.append('info')
            findings.append(
                VisibilityFinding(
                    code='VIS010',
                    level='L4',
                    severity='info',
                    title='Нет опубликованных пользовательских папок',
                    detail='Присутствуют только системные ресурсы (IPC$/ADMIN$/диски$).',
                    recommendation='Опубликуйте нужную папку через New-SmbShare или интерфейс AI-TC.',
                )
            )

        l4_status = VisibilityLevelStatus(
            level='L4',
            name='SMB и общие ресурсы (File & Printer Sharing)',
            status=self._aggregate_status(l4_sev),
            summary=(
                f'SMB 2/3 доступен, пользовательских папок: {smb.user_shares_count}'
                if 'error' not in l4_sev
                else 'Протокол SMB 2/3 отключён'
            ),
            details={
                'server_config': smb.server_config.model_dump(),
                'user_shares_count': smb.user_shares_count,
                'total_shares_count': len(smb.shares),
            },
        )

        levels = [l1_status, l2_status, l3_status, l4_status]
        overall = self._aggregate_status([lvl.status for lvl in levels])
        is_discoverable = bool(disc.get('is_discovery_enabled')) and not public_profiles and bool(profiles)

        return LanVisibilityReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            hostname=socket.gethostname(),
            overall_status=overall,
            is_discoverable=is_discoverable,
            is_file_sharing_ready=smb.ready_for_file_sharing and not public_profiles,
            levels=levels,
            findings=findings,
        )

    def create_snapshot(self, reason: str = 'manual') -> NetworkConfigSnapshot:
        """Сохраняет снимок текущего состояния профилей, служб и правил для отката.

        Args:
            reason: Причина создания снимка (например, 'before_sharing_enable').

        Returns:
            NetworkConfigSnapshot: Созданный и сохранённый на диск снимок.
        """
        disc = self._discovery.inspect()
        smb = self._smb.get_status()
        disc_svcs = disc.get('services') or {}

        snapshot = NetworkConfigSnapshot(
            snapshot_id=f"net_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            profiles=disc.get('profiles') or [],
            discovery_firewall_enabled=bool((disc.get('firewall') or {}).get('is_enabled')),
            sharing_firewall_enabled=smb.firewall.is_enabled,
            services={
                'FDResPub': disc_svcs.get('FDResPub') or {},
                'fdPHost': disc_svcs.get('fdPHost') or {},
                'SSDPSRV': disc_svcs.get('SSDPSRV') or {},
                'upnphost': disc_svcs.get('upnphost') or {},
                'LanmanServer': smb.lanman_server.model_dump(),
                'LanmanWorkstation': smb.lanman_workstation.model_dump(),
            },
        )

        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        snap_path = self._snapshot_dir / f'{snapshot.snapshot_id}.json'
        snap_path.write_text(snapshot.model_dump_json(indent=2), encoding='utf-8')
        self._prune_old_snapshots()
        return snapshot

    def _prune_old_snapshots(self) -> None:
        """Удаляет старые снимки сверх лимита _MAX_SNAPSHOTS."""
        if not self._snapshot_dir.exists():
            return
        files = sorted(self._snapshot_dir.glob('net_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_file in files[_MAX_SNAPSHOTS:]:
            try:
                old_file.unlink()
            except OSError:
                continue

    def list_snapshots(self, limit: int = 20) -> List[NetworkConfigSnapshot]:
        """Возвращает список сохранённых снимков конфигурации (от новых к старым)."""
        if not self._snapshot_dir.exists():
            return []
        files = sorted(self._snapshot_dir.glob('net_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        result: List[NetworkConfigSnapshot] = []
        for path in files[: max(1, min(limit, _MAX_SNAPSHOTS))]:
            try:
                result.append(NetworkConfigSnapshot.model_validate_json(path.read_text(encoding='utf-8')))
            except Exception as exc:
                logger.warning(f'[NetworkVisibility] Повреждённый снимок {path.name}: {exc}')
        return result

    def rollback(self, snapshot_id: str) -> RollbackResult:
        """Восстанавливает сетевые профили и состояние правил Discovery/Sharing из снимка.

        Args:
            snapshot_id: Идентификатор сохранённого снимка.

        Returns:
            RollbackResult: Итог выполнения отката.
        """
        if not self._is_admin_fn():
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                message='Для отката сетевых настроек требуются права администратора Windows.',
                requires_admin=True,
            )

        safe_id = Path(snapshot_id).name
        snap_path = self._snapshot_dir / f'{safe_id}.json'
        if not snap_path.exists():
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                message=f"Снимок '{snapshot_id}' не найден.",
            )

        snapshot = NetworkConfigSnapshot.model_validate_json(snap_path.read_text(encoding='utf-8'))
        restored: List[str] = []
        errors: List[str] = []

        # 1. Восстановление категорий профилей
        for prof in snapshot.profiles:
            idx = prof.get('InterfaceIndex')
            cat = str(prof.get('NetworkCategory', ''))
            if idx is not None and cat in ('Public', 'Private'):
                res = self._discovery.set_network_category(cat, interface_index=int(idx))
                if res.get('status') == 'ok':
                    restored.append(f'Интерфейс {idx} → {cat}')
                else:
                    errors.append(str(res.get('message')))

        # 2. Восстановление правил Network Discovery
        if snapshot.discovery_firewall_enabled:
            self._discovery.enable(set_private=False)
            restored.append('Network Discovery → Включён')
        else:
            self._discovery.disable(set_public=False)
            restored.append('Network Discovery → Отключён')

        # 3. Восстановление правил File & Printer Sharing
        sh_res = self._smb.toggle_file_sharing(
            enable=snapshot.sharing_firewall_enabled,
            start_server_service=False,
            snapshot_id=snapshot.snapshot_id,
        )
        if sh_res.success:
            restored.append(f"File & Printer Sharing → {'Включён' if snapshot.sharing_firewall_enabled else 'Отключён'}")
        else:
            errors.append(sh_res.message)

        success = len(errors) == 0
        message = (
            f"Конфигурация успешно восстановлена из снимка '{snapshot.snapshot_id}'"
            if success
            else f"Откат выполнен с ошибками: {'; '.join(errors)}"
        )
        self._telemetry_logger.log_event(
            event_type='network_visibility_rollback',
            status='SUCCESS' if success else 'FAILED',
            details={'snapshot_id': snapshot.snapshot_id, 'restored': restored, 'errors': errors},
        )
        if success:
            logger.console(f'[NetworkVisibility] {message}')

        return RollbackResult(
            success=success,
            snapshot_id=snapshot.snapshot_id,
            message=message,
            requires_admin=False,
            restored_steps=restored,
        )


__all__ = [
    'LanVisibilityDiagnostics',
    'LanVisibilityReport',
    'NetworkConfigSnapshot',
    'RollbackResult',
    'VisibilityFinding',
    'VisibilityLevelStatus',
]
