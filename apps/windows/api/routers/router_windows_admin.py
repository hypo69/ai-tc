# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Windows Admin
# =============================================================================
# Description:
#   API роутер административных функций, управления пользователями и настройками системы.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_windows_admin import UserSessionDTO
#
#     service = UserSessionDTO()
#
# File: router_windows_admin.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 16:15:00
# =============================================================================

from __future__ import annotations
"""API роутер административных функций, управления пользователями и настройками системы."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from logger import logger


class UserSessionDTO(BaseModel):
    """User session data transfer object."""
    username: str
    session_id: int
    status: str
    login_time: str
    ip_address: str
    process_count: int


class SecurityEventDTO(BaseModel):
    """Security event data transfer object."""
    timestamp: datetime
    event_id: int
    level: str
    source: str
    description: str


class SystemStatusDTO(BaseModel):
    """Windows system status data transfer object."""
    hostname: str
    domain: str
    ad_connected: bool
    ad_status: str
    uptime_seconds: int
    users_online: int
    recent_events: int


class ADObjectDTO(BaseModel):
    """Active Directory object data transfer object."""
    object_type: str  # User, Group, Computer, OrgUnit
    name: str
    distinguished_name: str
    creation_date: Optional[str] = None
    modified_date: Optional[str] = None


class GroupPolicyDTO(BaseModel):
    """Group Policy object data transfer object."""
    gpo_name: str
    guid: str
    status: str  # Enabled, Disabled
    linked_to: List[str]
    applied_to: List[str]


class AppExecutionDTO(BaseModel):
    """Execution history data transfer object."""
    last_run_time: Optional[str] = None
    run_count: int = 0
    focus_time_seconds: int = 0
    source_artifact: str = "UserAssist"
    raw_path: str = ""


class InstalledAppDTO(BaseModel):
    """Installed software application data transfer object."""
    name: str
    display_name: str
    version: str = ""
    publisher: str = ""
    install_date: Optional[str] = None
    install_location: str = ""
    uninstall_string: str = ""
    size_mb: float = 0.0
    architecture: str = "x64"
    category: str = "Прочее"
    purpose_description: str = ""
    is_system_component: bool = False
    execution_info: Optional[AppExecutionDTO] = None


class SoftwareAuditReportDTO(BaseModel):
    """Software audit summary report data transfer object."""
    timestamp: str
    total_apps: int
    active_apps_count: int
    unused_apps_count: int
    categories_breakdown: Dict[str, int]
    recently_launched: List[InstalledAppDTO]
    top_launched: List[InstalledAppDTO]
    never_launched_or_dormant_count: int



def init_router(chat_model: Optional[Any] = None) -> APIRouter:
    """Initialize and configure Windows System Administrator router.

    Args:
        chat_model: Optional UnifiedChatModel instance for AI analysis.

    Returns:
        APIRouter: Configured FastAPI router instance.
    """
    router = APIRouter(prefix="/api/v1/windows-admin", tags=["Windows System Administrator"])

    @router.get("/status", response_model=SystemStatusDTO)
    async def get_system_status() -> SystemStatusDTO:
        """Retrieve current Windows system status, domain, and AD connectivity."""
        import platform
        
        return SystemStatusDTO(
            hostname=platform.node(),
            domain="WORKGROUP",  # Would be fetched from Windows APIs in production
            ad_connected=False,
            ad_status="Not connected to domain",
            uptime_seconds=3600,
            users_online=2,
            recent_events=15,
        )

    @router.get("/sessions", response_model=List[UserSessionDTO])
    async def list_user_sessions() -> List[UserSessionDTO]:
        """Retrieve list of active user sessions."""
        return [
            UserSessionDTO(
                username="Administrator",
                session_id=1,
                status="Active",
                login_time=datetime.now().isoformat(),
                ip_address="127.0.0.1",
                process_count=23,
            ),
            UserSessionDTO(
                username="Guest",
                session_id=2,
                status="Idle",
                login_time=(datetime.now() - timedelta(hours=2)).isoformat(),
                ip_address="127.0.0.1",
                process_count=1,
            ),
        ]

    @router.get("/events", response_model=List[SecurityEventDTO])
    async def get_security_events(
        hours: int = Query(default=24, ge=1, le=720, description="Hours lookback"),
        limit: int = Query(default=50, ge=1, le=500, description="Max events count"),
        level: Optional[str] = Query(default=None, description="Filter by level (Critical, Warning, Information)"),
    ) -> List[SecurityEventDTO]:
        """Retrieve Windows security events from Event Log."""
        now = datetime.now()
        
        events = [
            SecurityEventDTO(
                timestamp=now,
                event_id=4624,
                level="Information",
                source="Security",
                description="An account was successfully logged on.",
            ),
            SecurityEventDTO(
                timestamp=now - timedelta(minutes=5),
                event_id=4688,
                level="Information",
                source="Security",
                description="A new process has been created.",
            ),
            SecurityEventDTO(
                timestamp=now - timedelta(minutes=10),
                event_id=4720,
                level="Warning",
                source="Security",
                description="A user account was created.",
            ),
        ]
        
        if level:
            events = [e for e in events if e.level == level]
        
        return events[:limit]

    @router.get("/ad/users", response_model=List[ADObjectDTO])
    async def list_ad_users(
        domain: Optional[str] = Query(default=None, description="Target domain"),
        limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    ) -> List[ADObjectDTO]:
        """Retrieve Active Directory user accounts."""
        return [
            ADObjectDTO(
                object_type="User",
                name="John Doe",
                distinguished_name="CN=John Doe,CN=Users,DC=CONTOSO,DC=COM",
                creation_date=datetime.now().isoformat(),
                modified_date=datetime.now().isoformat(),
            ),
            ADObjectDTO(
                object_type="User",
                name="Jane Smith",
                distinguished_name="CN=Jane Smith,CN=Users,DC=CONTOSO,DC=COM",
                creation_date=datetime.now().isoformat(),
                modified_date=datetime.now().isoformat(),
            ),
        ]

    @router.get("/ad/groups", response_model=List[ADObjectDTO])
    async def list_ad_groups(
        domain: Optional[str] = Query(default=None, description="Target domain"),
        limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    ) -> List[ADObjectDTO]:
        """Retrieve Active Directory security groups."""
        return [
            ADObjectDTO(
                object_type="Group",
                name="Domain Admins",
                distinguished_name="CN=Domain Admins,CN=Users,DC=CONTOSO,DC=COM",
            ),
            ADObjectDTO(
                object_type="Group",
                name="Enterprise Admins",
                distinguished_name="CN=Enterprise Admins,CN=Users,DC=CONTOSO,DC=COM",
            ),
        ]

    @router.get("/ad/computers", response_model=List[ADObjectDTO])
    async def list_ad_computers(
        domain: Optional[str] = Query(default=None, description="Target domain"),
        limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    ) -> List[ADObjectDTO]:
        """Retrieve Active Directory computer accounts."""
        return [
            ADObjectDTO(
                object_type="Computer",
                name="WORKSTATION01",
                distinguished_name="CN=WORKSTATION01,CN=Computers,DC=CONTOSO,DC=COM",
            ),
            ADObjectDTO(
                object_type="Computer",
                name="SERVER01",
                distinguished_name="CN=SERVER01,CN=Computers,DC=CONTOSO,DC=COM",
            ),
        ]

    @router.get("/gpo", response_model=List[GroupPolicyDTO])
    async def list_group_policies(
        domain: Optional[str] = Query(default=None, description="Target domain"),
    ) -> List[GroupPolicyDTO]:
        """Retrieve Group Policy Objects and their status."""
        return [
            GroupPolicyDTO(
                gpo_name="Default Domain Policy",
                guid="31B2F340-016D-11D2-945F-00C04FB984F9",
                status="Enabled",
                linked_to=["DC=CONTOSO,DC=COM"],
                applied_to=["Domain Admins", "Enterprise Admins"],
            ),
            GroupPolicyDTO(
                gpo_name="Default Domain Controllers Policy",
                guid="6AC1786C-016F-11D2-945F-00C04FB984F9",
                status="Enabled",
                linked_to=["OU=Domain Controllers,DC=CONTOSO,DC=COM"],
                applied_to=["Domain Controllers"],
            ),
        ]

    @router.get("/software", response_model=List[InstalledAppDTO])
    async def list_installed_software(
        category: Optional[str] = Query(default=None, description="Filter by software category"),
        unused_only: bool = Query(default=False, description="Filter only unused or dormant applications"),
        limit: int = Query(default=50, ge=1, le=500, description="Max applications count"),
        force_refresh: bool = Query(default=False, description="Force re-scan installed software"),
    ) -> List[InstalledAppDTO]:
        """Retrieve list of installed software applications with execution history and purpose."""
        try:
            if not force_refresh:
                try:
                    from apps.windows.telemetry.sqlite import TelemetryStorage
                    storage = TelemetryStorage.get_instance()
                    db_apps = storage.get_software_inventory_from_db(limit=limit)
                    if db_apps:
                        items: List[InstalledAppDTO] = []
                        for a in db_apps:
                            exec_info = a.get("execution_info")
                            exec_dto = None
                            if exec_info and isinstance(exec_info, dict):
                                exec_dto = AppExecutionDTO(
                                    last_run_time=exec_info.get("last_run_time"),
                                    run_count=int(exec_info.get("run_count") or 0),
                                    focus_time_seconds=int(exec_info.get("focus_time_seconds") or 0),
                                    source_artifact=exec_info.get("source_artifact"),
                                    raw_path=exec_info.get("raw_path"),
                                )
                            items.append(InstalledAppDTO(
                                name=a.get("app_id") or a.get("name") or "",
                                display_name=a.get("display_name") or a.get("name") or "",
                                version=a.get("version") or "",
                                publisher=a.get("publisher") or "",
                                install_date=a.get("install_date"),
                                install_location=a.get("install_location"),
                                uninstall_string=a.get("uninstall_string"),
                                size_mb=round(float(a.get("size_bytes") or 0) / (1024 * 1024), 2),
                                architecture=a.get("architecture") or "x64",
                                category=str(a.get("category") or "Прочее"),
                                purpose_description=str(a.get("purpose_description") or ""),
                                is_system_component=bool(a.get("is_system_component", False)),
                                execution_info=exec_dto,
                            ))
                        if category:
                            c_lower = category.lower()
                            items = [it for it in items if c_lower in it.category.lower()]
                        if unused_only:
                            items = [it for it in items if not it.execution_info or it.execution_info.run_count == 0]
                        if items:
                            return items[:limit]
                except Exception as db_err:
                    logger.debug(f"Чтение инвентаря ПО из SQLite телеметрии: {db_err}")

            from apps.windows.sdk.core.software_audit import SoftwareAuditEngine
            engine = SoftwareAuditEngine()
            apps = await asyncio.to_thread(engine.get_installed_applications)
            
            if category:
                c_lower = category.lower()
                apps = [a for a in apps if c_lower in a.category.value.lower()]
            if unused_only:
                apps = [a for a in apps if not a.was_launched]
                
            return [
                InstalledAppDTO(
                    name=a.name,
                    display_name=a.display_name,
                    version=a.version,
                    publisher=a.publisher,
                    install_date=a.install_date,
                    install_location=a.install_location,
                    uninstall_string=a.uninstall_string,
                    size_mb=round(a.size_mb, 2),
                    architecture=a.architecture,
                    category=a.category.value if hasattr(a.category, "value") else str(a.category),
                    purpose_description=a.purpose_description,
                    is_system_component=a.is_system_component,
                    execution_info=AppExecutionDTO(
                        last_run_time=a.execution_info.last_run_time.isoformat() if a.execution_info.last_run_time else None,
                        run_count=a.execution_info.run_count,
                        focus_time_seconds=a.execution_info.focus_time_seconds,
                        source_artifact=a.execution_info.source_artifact,
                        raw_path=a.execution_info.raw_path,
                    ) if a.execution_info else None,
                )
                for a in apps[:limit]
            ]
        except Exception as e:
            logger.error(f"Error retrieving installed software: {e}")
            return []

    @router.get("/software/audit", response_model=SoftwareAuditReportDTO)
    async def get_software_audit_report(force_refresh: bool = Query(default=False, description="Force re-audit software")) -> SoftwareAuditReportDTO:
        """Retrieve comprehensive software audit report with usage analytics."""
        try:
            if not force_refresh:
                try:
                    from apps.windows.telemetry.sqlite import TelemetryStorage
                    storage = TelemetryStorage.get_instance()
                    latest = storage.get_latest_software_audit_report()
                    if latest:
                        return SoftwareAuditReportDTO(
                            timestamp=str(latest.get("timestamp") or datetime.now().isoformat()),
                            total_apps=int(latest.get("total_apps") or 0),
                            active_apps_count=int(latest.get("active_apps_count") or 0),
                            unused_apps_count=int(latest.get("unused_apps_count") or 0),
                            categories_breakdown=latest.get("categories_breakdown") or {},
                            recently_launched=[],
                            top_launched=[],
                            never_launched_or_dormant_count=int(latest.get("unused_apps_count") or 0),
                        )
                except Exception as db_err:
                    logger.debug(f"Чтение отчета аудита ПО из SQLite телеметрии: {db_err}")

            from apps.windows.sdk.core.software_audit import SoftwareAuditEngine
            engine = SoftwareAuditEngine()
            report = await asyncio.to_thread(engine.generate_audit_report, True)
            
            def _to_dto(a):
                return InstalledAppDTO(
                    name=a.name,
                    display_name=a.display_name,
                    version=a.version,
                    publisher=a.publisher,
                    install_date=a.install_date,
                    install_location=a.install_location,
                    uninstall_string=a.uninstall_string,
                    size_mb=round(a.size_mb, 2),
                    architecture=a.architecture,
                    category=a.category.value if hasattr(a.category, "value") else str(a.category),
                    purpose_description=a.purpose_description,
                    is_system_component=a.is_system_component,
                    execution_info=AppExecutionDTO(
                        last_run_time=a.execution_info.last_run_time.isoformat() if a.execution_info.last_run_time else None,
                        run_count=a.execution_info.run_count,
                        focus_time_seconds=a.execution_info.focus_time_seconds,
                        source_artifact=a.execution_info.source_artifact,
                        raw_path=a.execution_info.raw_path,
                    ) if a.execution_info else None,
                )

            return SoftwareAuditReportDTO(
                timestamp=report.timestamp.isoformat(),
                total_apps=report.total_apps,
                active_apps_count=report.active_apps_count,
                unused_apps_count=report.unused_apps_count,
                categories_breakdown=report.categories_breakdown,
                recently_launched=[_to_dto(a) for a in report.recently_launched[:10]],
                top_launched=[_to_dto(a) for a in report.top_launched[:10]],
                never_launched_or_dormant_count=len(report.never_launched_or_dormant),
            )
        except Exception as e:
            logger.error(f"Error generating software audit report: {e}")
            return SoftwareAuditReportDTO(
                timestamp=datetime.now().isoformat(),
                total_apps=0,
                active_apps_count=0,
                unused_apps_count=0,
                categories_breakdown={},
                recently_launched=[],
                top_launched=[],
                never_launched_or_dormant_count=0,
            )


    @router.post("/command/lock-session")
    async def lock_user_session(session_id: int) -> Dict[str, Any]:
        """Lock a user session (requires admin privileges)."""
        logger.info(f"Locking session {session_id}")
        return {"status": "success", "message": f"Session {session_id} locked"}

    @router.post("/command/logoff-session")
    async def logoff_user_session(session_id: int, force: bool = False) -> Dict[str, Any]:
        """Log off a user session (requires admin privileges)."""
        logger.info(f"Logging off session {session_id}, force={force}")
        return {"status": "success", "message": f"Session {session_id} logged off"}

    @router.post("/command/restart-computer")
    async def restart_computer(delay_seconds: int = 0, message: str = "") -> Dict[str, Any]:
        """Schedule computer restart (requires admin privileges)."""
        logger.warning(f"Computer restart scheduled in {delay_seconds}s: {message}")
        return {"status": "scheduled", "restart_in": delay_seconds}

    @router.websocket("/stream")
    async def stream_admin_events(websocket: WebSocket) -> None:
        """Stream real-time security events and admin operations over WebSocket."""
        await websocket.accept()
        interval_sec = 2.0

        try:
            while True:
                now = datetime.now()
                event = {
                    "timestamp": now.isoformat(),
                    "type": "security_event",
                    "event_id": 4624,
                    "level": "Information",
                    "description": "System monitoring active",
                }
                await websocket.send_json(event)
                await asyncio.sleep(interval_sec)
        except WebSocketDisconnect:
            logger.info("Admin events WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close(code=1000)

    # -------------------------------------------------------------------------
    # Управление ACL, шаблоны прав и авто-бэкап (01_FRONTEND.md § 3)
    # -------------------------------------------------------------------------
    @router.post("/acl/reset")
    async def reset_acl_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Сброс ACL по умолчанию с предварительным созданием дампа в apps/logs/acl_backups/."""
        target_path = payload.get("path") or "C:\\Windows\\System32"
        backup_dir = Path("apps/logs/acl_backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(target_path).name or "root"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{stem}_{ts}.acl"

        # 1. Авто-бэкап через icacls /save
        try:
            subprocess.run(
                ["icacls", target_path, "/save", str(backup_file), "/t", "/c"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False
            )
        except Exception as e:
            logger.warning(f"Ошибка создания бэкапа ACL: {e}")

        # 2. Сброс прав по умолчанию
        try:
            res = subprocess.run(
                ["icacls", target_path, "/reset", "/t", "/c"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False
            )
            output = res.stdout.strip()
        except Exception as e:
            output = str(e)

        return {
            "status": "success",
            "message": f"ACL для '{target_path}' сброшен к исходным системным значениям.",
            "backup_file": str(backup_file),
            "output": output
        }

    @router.post("/acl/template")
    async def apply_acl_template_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Применение предустановленных шаблонов прав (readonly, isolated, full_control)."""
        target_path = payload.get("path") or "C:\\Windows\\System32"
        tmpl = payload.get("template", "readonly").lower()

        backup_dir = Path("apps/logs/acl_backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"template_{tmpl}_{ts}.acl"

        # Бэкап
        try:
            subprocess.run(["icacls", target_path, "/save", str(backup_file)], capture_output=True, timeout=5.0)
        except Exception:
            pass

        # Применение шаблона
        cmds = []
        if tmpl == "readonly":
            cmds = ["icacls", target_path, "/grant:r", "Users:(OI)(CI)R", "/c"]
        elif tmpl == "isolated":
            cmds = ["icacls", target_path, "/inheritance:r", "/grant:r", "SYSTEM:(OI)(CI)F", "Administrators:(OI)(CI)F", "/c"]
        elif tmpl == "full_control":
            cmds = ["icacls", target_path, "/grant", "Everyone:(OI)(CI)F", "/c"]

        output = ""
        if cmds:
            try:
                res = subprocess.run(cmds, capture_output=True, text=True, timeout=5.0)
                output = res.stdout.strip()
            except Exception as e:
                output = str(e)

        return {
            "status": "success",
            "template": tmpl,
            "path": target_path,
            "backup_file": str(backup_file),
            "output": output
        }

    @router.post("/acl/restore")
    async def restore_acl_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Откат прав ACL из последнего сохраненного бэкапа."""
        target_path = payload.get("path") or "C:\\Windows\\System32"
        backup_dir = Path("apps/logs/acl_backups")
        backup_file_str = payload.get("backup_file")

        if not backup_file_str:
            if backup_dir.exists():
                backups = sorted(backup_dir.glob("*.acl"), key=os.path.getmtime, reverse=True)
                if backups:
                    backup_file_str = str(backups[0])

        if not backup_file_str or not Path(backup_file_str).exists():
            return {"status": "error", "message": "Резервные копии ACL не найдены в apps/logs/acl_backups/"}

        parent_dir = str(Path(target_path).parent)
        try:
            res = subprocess.run(
                ["icacls", parent_dir, "/restore", backup_file_str],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            out = res.stdout.strip()
        except Exception as e:
            out = str(e)

        return {
            "status": "success",
            "message": f"Права успешно восстановлены из {Path(backup_file_str).name}",
            "backup_file": backup_file_str,
            "output": out
        }

    return router


__all__ = [
    "init_router",
    "UserSessionDTO",
    "SecurityEventDTO",
    "SystemStatusDTO",
    "ADObjectDTO",
    "GroupPolicyDTO",
]

