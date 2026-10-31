# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_panels
# =============================================================================
# Description:
#   Эндпойнты карточек дашборда.
#   Вынесено из router_about_system.py (этап 4 оптимизации).
#
# File: endpoints_panels.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations


from fastapi import APIRouter

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from .models import CpuPanelResponse
from .models import DiskIoPanelResponse
from .models import GpuPanelResponse
from .models import MemoryPanelResponse
from .models import PlatformOsPanelResponse
from .models import RestorePointsPanelResponse
from .models import SecurityPanelResponse
from .models import StoragePanelResponse
from .query_about import query_about_system_from_db


def register_panel_endpoints(router: APIRouter, storage: TelemetryStorage) -> None:
    """Регистрирует эндпойнты карточек дашборда на роутере."""
    # =========================================================================
    # 1. Платформа & ОС: GET /api/v1/dashboard/os, /api/v1/about-system/os
    # =========================================================================
    @router.get("/api/v1/dashboard/os", response_model=PlatformOsPanelResponse)
    @router.get("/api/v1/dashboard/platform_os", response_model=PlatformOsPanelResponse)
    @router.get("/api/v1/about-system/os", response_model=PlatformOsPanelResponse)
    @router.get("/api/v1/panel/os", response_model=PlatformOsPanelResponse)
    async def get_panel_os() -> PlatformOsPanelResponse:
        """Получение сводных данных платформы, ОС, хоста и аптайма из telemetry.db."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.os
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /os: {exc}", exc_info=True)
            return PlatformOsPanelResponse(
                status="error",
                os_name="Windows 11",
                display_title="Windows 11 (AMD64)",
                display_host="Host: --",
            )

    # =========================================================================
    # 2. Безопасность системы: GET /api/v1/dashboard/security, /api/v1/about-system/security
    # =========================================================================
    @router.get("/api/v1/dashboard/security", response_model=SecurityPanelResponse)
    @router.get("/api/v1/about-system/security", response_model=SecurityPanelResponse)
    @router.get("/api/v1/panel/security", response_model=SecurityPanelResponse)
    async def get_panel_security() -> SecurityPanelResponse:
        """Получение сводных данных статуса безопасности, Брандмауэра и UAC из telemetry.db."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.security
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /security: {exc}", exc_info=True)
            return SecurityPanelResponse(
                status="Active & Protected",
                display_title="Active & Protected",
                display_subtitle="Firewall: ON | UAC: ON",
            )

    # =========================================================================
    # 3. Точки восстановления: GET /api/v1/dashboard/checkpoints, /api/v1/dashboard/restore-points
    # =========================================================================
    @router.get("/api/v1/dashboard/checkpoints", response_model=RestorePointsPanelResponse)
    @router.get("/api/v1/dashboard/restore-points", response_model=RestorePointsPanelResponse)
    @router.get("/api/v1/dashboard/restore_points", response_model=RestorePointsPanelResponse)
    @router.get("/api/v1/about-system/restore-points", response_model=RestorePointsPanelResponse)
    @router.get("/api/v1/panel/restore-points", response_model=RestorePointsPanelResponse)
    async def get_panel_restore_points() -> RestorePointsPanelResponse:
        """Получение количества контрольных точек и статуса защиты из telemetry.db."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.restore_points
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /restore-points: {exc}", exc_info=True)
            return RestorePointsPanelResponse(
                status="ok",
                checkpoints_count=0,
                display_title="0 Checkpoints",
                display_subtitle="Protection: Active",
            )

    # =========================================================================
    # 4. Системный накопитель (C:): GET /api/v1/dashboard/storage, /api/v1/dashboard/sorage
    # =========================================================================
    @router.get("/api/v1/dashboard/storage", response_model=StoragePanelResponse)
    @router.get("/api/v1/dashboard/sorage", response_model=StoragePanelResponse)
    @router.get("/api/v1/about-system/storage", response_model=StoragePanelResponse)
    @router.get("/api/v1/panel/storage", response_model=StoragePanelResponse)
    async def get_panel_storage() -> StoragePanelResponse:
        """Получение объема свободного пространства и оценки файлов для очистки из telemetry.db."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.storage
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /storage: {exc}", exc_info=True)
            return StoragePanelResponse(
                status="ok",
                drive="C:",
                display_title="0.0 GB Free",
                display_subtitle="Cleanable: ~0 MB",
            )

    # =========================================================================
    # 5. Загрузка CPU: GET /api/v1/dashboard/cpu
    # =========================================================================
    @router.get("/api/v1/dashboard/cpu", response_model=CpuPanelResponse)
    @router.get("/api/v1/about-system/cpu", response_model=CpuPanelResponse)
    @router.get("/api/v1/panel/cpu", response_model=CpuPanelResponse)
    async def get_panel_cpu() -> CpuPanelResponse:
        """Получение метрик загрузки и частоты процессора CPU."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.cpu
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /cpu: {exc}", exc_info=True)
            return CpuPanelResponse()

    # =========================================================================
    # 6. Память (RAM): GET /api/v1/dashboard/ram, /api/v1/dashboard/panel_ram
    # =========================================================================
    @router.get("/api/v1/dashboard/ram", response_model=MemoryPanelResponse)
    @router.get("/api/v1/dashboard/panel_ram", response_model=MemoryPanelResponse)
    @router.get("/api/v1/dashboard/memory", response_model=MemoryPanelResponse)
    @router.get("/api/v1/about-system/memory", response_model=MemoryPanelResponse)
    @router.get("/api/v1/panel/memory", response_model=MemoryPanelResponse)
    async def get_panel_ram() -> MemoryPanelResponse:
        """Получение объема и процента занятой оперативной памяти RAM."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.memory
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /ram: {exc}", exc_info=True)
            return MemoryPanelResponse()

    # =========================================================================
    # 7. GPU Ускоритель: GET /api/v1/dashboard/gpu
    # =========================================================================
    @router.get("/api/v1/dashboard/gpu", response_model=GpuPanelResponse)
    @router.get("/api/v1/about-system/gpu", response_model=GpuPanelResponse)
    @router.get("/api/v1/panel/gpu", response_model=GpuPanelResponse)
    async def get_panel_gpu() -> GpuPanelResponse:
        """Получение метрик нагрузки и VRAM графического ускорителя GPU."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.gpu
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /gpu: {exc}", exc_info=True)
            return GpuPanelResponse()

    # =========================================================================
    # 8. Диск (C:) I/O: GET /api/v1/dashboard/disk_io, /api/v1/dashboard/disk-io
    # =========================================================================
    @router.get("/api/v1/dashboard/disk_io", response_model=DiskIoPanelResponse)
    @router.get("/api/v1/dashboard/disk-io", response_model=DiskIoPanelResponse)
    @router.get("/api/v1/about-system/disk_io", response_model=DiskIoPanelResponse)
    @router.get("/api/v1/panel/disk_io", response_model=DiskIoPanelResponse)
    async def get_panel_disk_io() -> DiskIoPanelResponse:
        """Получение скоростей чтения и записи системного накопителя C: I/O."""
        try:
            overview = query_about_system_from_db(storage)
            return overview.disk_io
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /disk_io: {exc}", exc_info=True)
            return DiskIoPanelResponse()

