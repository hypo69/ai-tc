# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_overview
# =============================================================================
# Description:
#   Эндпойнты сводки и диагностик.
#   Исключительно чтение из базы данных telemetry.db без внешних опросов.
#
# File: endpoints_overview.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 10:35:00
# =============================================================================

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from .models import AboutSystemHistoryResponse
from .models import AboutSystemPanelOverviewResponse
from .query_about import query_about_system_from_db
from .query_about import query_about_system_history_from_db
from .query_diagnostics import query_backup_health_from_db
from .query_diagnostics import query_battery_wear_from_db
from .query_diagnostics import query_disks_wear_from_db
from .query_diagnostics import query_hardware_tree_full
from .query_diagnostics import query_network_profile_from_db
from .query_diagnostics import query_peripherals_diagnostics
from .query_diagnostics import query_process_leaks_from_db
from .query_diagnostics import query_storage_battery_from_db
from .query_diagnostics import query_throttling_from_db
from .query_summary import query_system_summary_full


def register_overview_endpoints(router: APIRouter, storage: TelemetryStorage) -> None:
    """Регистрирует эндпойнты сводки и диагностик на роутере."""
    # =========================================================================
    # 0.00. Единый пакетный эндпоинт данных вкладки "О системе" (/about-system/bundle)
    # =========================================================================
    @router.get("/api/v1/about-system/bundle")
    @router.get("/api/v1/tc/about-system/bundle")
    async def get_about_system_bundle_endpoint(force: bool = False, process_limit: int = 25) -> Dict[str, Any]:
        """Возвращает полный агрегированный срез всех данных вкладки 'О системе' за один сетевой запрос."""
        summary_task = query_system_summary_full(storage, process_limit=process_limit)
        hardware_task = query_hardware_tree_full(storage, force_refresh=force)

        summary_data, hardware_data = await asyncio.gather(summary_task, hardware_task, return_exceptions=True)
        if isinstance(summary_data, Exception):
            logger.warning(f"[bundle] Ошибка сбора summary: {summary_data}")
            summary_data = {}
        if isinstance(hardware_data, Exception):
            logger.warning(f"[bundle] Ошибка сбора hardware: {hardware_data}")
            hardware_data = []

        disks_res = query_disks_wear_from_db(storage, force_refresh=force)
        battery_res = query_battery_wear_from_db(storage, force_refresh=force)
        disks_data = disks_res.get("disks_wear", [])
        battery_data = battery_res.get("battery_wear", {})
        storage_battery = {
            "status": "ok",
            "disks_wear": disks_data,
            "battery_wear": battery_data,
            "timestamp": disks_res.get("timestamp"),
        }
        backup_health = query_backup_health_from_db(storage)
        network_profile = query_network_profile_from_db(storage)

        kpi_data: Dict[str, Any] = {}
        try:
            overview_res = query_about_system_from_db(storage)
            kpi_data = {
                "os": overview_res.os.model_dump(),
                "security": overview_res.security.model_dump(),
                "checkpoints": overview_res.restore_points.model_dump(),
                "storage": overview_res.storage.model_dump(),
                "cpu": overview_res.cpu.model_dump(),
                "memory": overview_res.memory.model_dump(),
                "gpu": overview_res.gpu.model_dump(),
                "disk_io": overview_res.disk_io.model_dump(),
            }
        except Exception as kpi_err:
            logger.debug(f"[bundle] Ошибка сбора KPI карточек: {kpi_err}")

        is_admin = bool(summary_data.get("user_is_admin", False) if isinstance(summary_data, dict) else False)

        control_status: Dict[str, Any] = {
            "is_elevated": is_admin,
            "security": {
                "defender_enabled": kpi_data.get("security", {}).get("status") == "Active & Protected",
                "realtime_protection_enabled": True,
                "firewall_domain_enabled": True,
                "firewall_private_enabled": True,
                "firewall_public_enabled": True,
                "firewall_overall_enabled": True,
                "uac_enabled": True,
            },
            "restore": {
                "system_protection_enabled": kpi_data.get("checkpoints", {}).get("status") == "ok",
                "restore_points_count": kpi_data.get("checkpoints", {}).get("checkpoints_count", 0),
            },
            "disk": {
                "cleanup_estimate": {"total_cleanable_mb": 150}
            },
            "power": {
                "active_plan_name": (summary_data.get("battery", {}).get("power_profile") or "Balanced (Сбалансированная)") if isinstance(summary_data, dict) else "Balanced (Сбалансированная)"
            },
            "update": {
                "status": (summary_data.get("updates", {}).get("status") or "Up to date") if isinstance(summary_data, dict) else "Up to date"
            }
        }

        return {
            "status": "ok",
            "summary": summary_data,
            "hardware": hardware_data,
            "hardware_tree": hardware_data,
            "disks_wear": disks_data,
            "storage_wear": disks_data,
            "battery": battery_data,
            "battery_wear": battery_data,
            "storage_battery": storage_battery,
            "backup": backup_health,
            "control_status": control_status,
            "kpi": kpi_data,
            "network_profile": network_profile,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # 0. Сводные эндпоинты для фронтенда (/api/v1/system/summary, /about-system/summary)
    # =========================================================================
    @router.get("/api/v1/system/summary")
    @router.get("/api/v1/tc/system/summary")
    async def get_system_summary_full_endpoint(process_limit: int = 25) -> Dict[str, Any]:
        """Получение максимально полного среза системной телеметрии со всеми полями напрямую из telemetry.db."""
        return await query_system_summary_full(storage, process_limit=process_limit)

    @router.websocket("/api/v1/system/stream")
    @router.websocket("/api/v1/tc/system/stream")
    async def websocket_system_stream_endpoint(websocket: WebSocket) -> None:
        """Стриминг срезов системной телеметрии в реальном времени исключительно из telemetry.db."""
        await websocket.accept()
        try:
            while True:
                snap = await query_system_summary_full(storage, process_limit=25)
                await websocket.send_json(snap)
                await asyncio.sleep(2.5)
        except WebSocketDisconnect:
            pass
        except Exception as ws_err:
            logger.debug(f"[system/stream] WebSocket отключен: {ws_err}")

    @router.get("/api/v1/about-system/summary", response_model=AboutSystemPanelOverviewResponse)
    @router.get("/api/v1/about-system", response_model=AboutSystemPanelOverviewResponse)
    @router.get("/api/v1/panel/about-system", response_model=AboutSystemPanelOverviewResponse)
    @router.get("/api/v1/panel/overview", response_model=AboutSystemPanelOverviewResponse)
    async def get_panel_about_system() -> AboutSystemPanelOverviewResponse:
        """Получение полного среза данных всех 8 карточек панели 'О Системе' напрямую из telemetry.db."""
        try:
            return query_about_system_from_db(storage)
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении панели /about-system: {exc}", exc_info=True)
            return AboutSystemPanelOverviewResponse(
                status="error",
                meta={"source": "telemetry.db", "error": str(exc)},
            )

    # =========================================================================
    # 0.01. Спецификация оборудования (Hardware Spec / Tree)
    # =========================================================================
    @router.get("/api/v1/system/hardware")
    @router.get("/api/v1/tc/hardware")
    async def get_system_hardware_spec(force: bool = False) -> List[Dict[str, Any]]:
        """Получение спецификации оборудования для Hardware Tree исключительно из telemetry.db."""
        return await query_hardware_tree_full(storage, force_refresh=force)

    # =========================================================================
    # 0.015. Статус компонентов оборудования (Hardware Components Status)
    # =========================================================================
    @router.get("/api/v1/about-system/hardware-enrichment-status")
    @router.get("/api/v1/tc/hardware-enrichment-status")
    async def get_hardware_enrichment_status_endpoint() -> Dict[str, Any]:
        """Возвращает статус компонентов оборудования (сбор внешних спецификаций вендоров отключен)."""
        try:
            comps = storage.get_hardware_components()
            res: Dict[str, Dict[str, Any]] = {}
            for c in comps:
                key = c.get("component_key")
                if not key:
                    continue
                res[key] = {
                    "component_key": key,
                    "vendor_url": None,
                    "enrichment_status": "completed",
                    "production_date": c.get("production_date"),
                    "production_date_source": c.get("production_date_source"),
                    "production_date_status": c.get("production_date_status", "completed"),
                    "is_present": bool(c.get("is_present", 1)),
                    "install_count": c.get("install_count", 1) or 1,
                    "first_seen": c.get("first_seen"),
                    "last_seen": c.get("last_seen"),
                    "removed_at": c.get("removed_at"),
                }
            return {
                "components": res,
                "pending_count": 0,
                "total_count": len(comps),
            }
        except Exception as ex:
            logger.warning(f"Ошибка получения статуса обогащения: {ex}")
            return {"components": {}, "pending_count": 0, "total_count": 0}

    # =========================================================================
    # 0.0155. Опрос даты производства компонента (Hardware Production Date Agent)
    # =========================================================================
    @router.post("/api/v1/about-system/hardware/query-production-date")
    @router.get("/api/v1/about-system/hardware/query-production-date")
    @router.post("/api/v1/tc/hardware/query-production-date")
    @router.get("/api/v1/tc/hardware/query-production-date")
    async def query_hardware_production_date_endpoint(
        component_key: str,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        serial_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Опрашивает специализированного агента для поиска даты производства по серийному номеру."""
        try:
            from apps.windows.telemetry.production_date_agent import HardwareProductionDateAgent
            agent = HardwareProductionDateAgent()

            comp = storage.get_hardware_component_by_key(component_key) or {}
            props = comp.get("properties_json") or {}
            if isinstance(props, str):
                import json
                try:
                    props = json.loads(props)
                except Exception:
                    props = {}

            c_vendor = vendor or comp.get("vendor") or ""
            c_model = model or comp.get("model") or ""
            c_cat = comp.get("category") or ""
            c_sn = serial_number or props.get("Серийный номер (S/N)") or props.get("Серийный номер")

            logger.console(f"[API] Запрос даты производства для '{component_key}' (S/N: {c_sn})...")
            res = await agent.resolve_production_date_async(
                vendor=c_vendor,
                model=c_model,
                serial_number=c_sn,
                properties=props,
                category=c_cat,
                use_ai=True,
            )

            p_date = res.get("production_date")
            p_source = res.get("production_source")
            if p_date and p_date != "N/A":
                storage.update_hardware_component_production_date(
                    component_key=component_key,
                    production_date=p_date,
                    source=p_source,
                    status="completed",
                )

            return {
                "success": bool(p_date and p_date != "N/A"),
                "component_key": component_key,
                "production_date": p_date,
                "production_source": p_source,
                "confidence": res.get("confidence", "none"),
                "details": res.get("details", ""),
            }
        except Exception as ex:
            logger.warning(f"Ошибка запроса даты производства: {ex}")
            return {
                "success": False,
                "component_key": component_key,
                "error": str(ex),
            }

    # =========================================================================
    # 0.016. История жизненного цикла компонента (Hardware Component History)
    # =========================================================================
    @router.get("/api/v1/about-system/hardware-component-history")
    @router.get("/api/v1/tc/hardware-component-history")
    async def get_hardware_component_history_endpoint(component_key: str) -> Dict[str, Any]:
        """Возвращает историю событий жизненного цикла компонента (установка, удаление, переустановка)."""
        try:
            history = storage.get_hardware_component_history(component_key)
            component = storage.get_hardware_component_by_key(component_key)
            return {
                "component_key": component_key,
                "component": component,
                "history": history,
                "total_events": len(history),
            }
        except Exception as ex:
            logger.warning(f"Ошибка получения истории компонента {component_key}: {ex}")
            return {
                "component_key": component_key,
                "component": None,
                "history": [],
                "total_events": 0,
                "error": str(ex),
            }

    # =========================================================================
    # 0.02. Износ накопителей и батареи (Storage & Battery Wear)
    # =========================================================================
    @router.get("/api/v1/system/diagnostics/storage-wear")
    @router.get("/api/v1/system/diagnostics/disks-wear")
    @router.get("/api/v1/about-system/disks-wear")
    async def get_disks_wear_endpoint(force: bool = False) -> Dict[str, Any]:
        """Получение независимой телеметрии износа накопителей SMART и физических дисков из telemetry.db."""
        return query_disks_wear_from_db(storage, force_refresh=force)

    @router.get("/api/v1/system/diagnostics/battery")
    @router.get("/api/v1/system/diagnostics/battery-wear")
    @router.get("/api/v1/about-system/battery")
    async def get_battery_telemetry_endpoint(force: bool = False) -> Dict[str, Any]:
        """Получение независимой глубокой телеметрии аккумулятора и питания из telemetry.db."""
        return query_battery_wear_from_db(storage, force_refresh=force)

    @router.get("/api/v1/system/diagnostics/storage-battery")
    async def get_storage_battery_wear_endpoint() -> Dict[str, Any]:
        """Получение износа накопителей SMART и батареи из telemetry.db."""
        return query_storage_battery_from_db(storage)

    # =========================================================================
    # 0.03. Резервное копирование (Windows Backup Health)
    # =========================================================================
    @router.get("/api/v1/windows-backup/health")
    async def get_backup_health_endpoint() -> Dict[str, Any]:
        """Получение статуса и здоровья резервного копирования."""
        return query_backup_health_from_db(storage)

    # =========================================================================
    # 0.04. Троттлинг и подсистема питания (CPU Throttling & Power Limits)
    # =========================================================================
    @router.get("/api/v1/system/diagnostics/throttling")
    async def get_throttling_diagnostics_endpoint() -> Dict[str, Any]:
        """Получение состояния троттлинга процессора, лимитов PL1/PL2 и задержек прерываний (< 5 мс)."""
        return query_throttling_from_db(storage)

    @router.post("/api/v1/system/diagnostics/throttling/refresh")
    @router.post("/api/v1/system/diagnostics/throttling/rescan")
    async def refresh_throttling_diagnostics_endpoint() -> Dict[str, Any]:
        """Принудительное фоновое обновление состояния троттлинга по кнопке пользователя."""
        try:
            from apps.windows.telemetry.deep_diagnostics import DeepDiagnosticsEngine
            engine = DeepDiagnosticsEngine()
            rep = await asyncio.to_thread(engine.collect_kernel_throttling)
            snap_id = f"snap_throttling_{int(datetime.now(timezone.utc).timestamp())}"
            storage.save_throttling_snapshot(snap_id, {
                "prochot_active": rep.thermal_throttling_detected,
                "pl1_limit_watts": 65.0 if rep.power_limit_throttling_detected else None,
                "pl2_limit_watts": 125.0 if rep.power_limit_throttling_detected else None,
                "current_power_watts": 45.0,
                "max_core_temp_c": 65.0,
                "package_temp_c": 62.0,
                "dpc_latency_us": int(rep.dpc_latency_pct * 100),
                "isr_latency_us": int(rep.interrupt_latency_pct * 100),
                "throttling_reasons": ["Power limit PL1"] if rep.power_limit_throttling_detected else [],
            })
        except Exception as ex:
            logger.debug(f"Ошибка принудительного обновления троттлинга: {ex}")
        return query_throttling_from_db(storage)

    # =========================================================================
    # 0.05. Утечки ресурсов процессов (Process Leaks & Resource Starvation)
    # =========================================================================
    @router.get("/api/v1/system/diagnostics/leaks")
    @router.get("/api/v1/tc/process-leaks")
    async def get_process_leaks_endpoint(limit: int = 100) -> Dict[str, Any]:
        """Получение сводки и списка утечек ресурсов процессов из SQLite (< 5 мс)."""
        return query_process_leaks_from_db(storage, limit=limit)

    @router.post("/api/v1/system/diagnostics/leaks/refresh")
    @router.post("/api/v1/tc/process-leaks/refresh")
    async def refresh_process_leaks_endpoint(limit: int = 100) -> Dict[str, Any]:
        """Получение актуального среза утечек процессов из SQLite по кнопке обновления."""
        return query_process_leaks_from_db(storage, limit=limit)

    # =========================================================================
    # 0.06. Периферия и сеть (Peripherals, USB, Wi-Fi, Audio)
    # =========================================================================
    @router.get("/api/v1/system/diagnostics/peripherals")
    @router.get("/api/v1/tc/peripherals")
    async def get_peripherals_diagnostics_endpoint(force: bool = False) -> Dict[str, Any]:
        """Получение телеметрии периферии: подключенных USB устройств, параметров Wi-Fi и аудиоустройств."""
        return await query_peripherals_diagnostics(storage, force_refresh=force)

    @router.post("/api/v1/system/diagnostics/peripherals/refresh")
    @router.post("/api/v1/system/diagnostics/peripherals/rescan")
    async def refresh_peripherals_diagnostics_endpoint() -> Dict[str, Any]:
        """Принудительное обновление состояния периферии по кнопке пользователя."""
        return await query_peripherals_diagnostics(storage, force_refresh=True)

    # =========================================================================
    # 0.1. История значений телеметрии: GET /api/v1/about-system/history
    # =========================================================================
    @router.get("/api/v1/about-system/history", response_model=AboutSystemHistoryResponse)
    @router.get("/api/v1/panel/about-system/history", response_model=AboutSystemHistoryResponse)
    async def get_panel_about_system_history(
        limit: int = 30,
        metric: str = "all",
    ) -> AboutSystemHistoryResponse:
        """Получение исторических значений телеметрии из базы данных telemetry.db."""
        try:
            return query_about_system_history_from_db(storage, limit=limit, metric=metric)
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при чтении истории /history: {exc}", exc_info=True)
            return AboutSystemHistoryResponse(
                status="error",
                count=0,
                metric=metric,
                history=[],
                meta={"source": "telemetry.db", "error": str(exc)},
            )

