# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Network - Router
# =============================================================================
# Description:
#   FastAPI router integration for Network Terminal.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.router import get_state
#
#     res = get_state()
#
# File: router.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:56:00
# =============================================================================

from __future__ import annotations
"""FastAPI router integration for Network Terminal."""

import asyncio
import os
import socket
import tempfile
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
import httpx
import psutil
from logger import logger
from apps.windows.api.auth import require_admin_user
from apps.common.telemetry_logger import AppTelemetryLogger
try:
    from apps.tshark import AIDetector, TSharkWrapper, TrafficAnalyzer
except ImportError:
    AIDetector, TSharkWrapper, TrafficAnalyzer = None, None, None
from .lan_scanner import WindowsLanScanner
from .lan_visibility_diagnostics import LanVisibilityDiagnostics
from .remote_access_settings import RemoteAccessApplyRequest, WindowsRemoteAccessManager
from .remote_auth import RemoteLoginRequest, WindowsRemoteAuthenticator
from .sensors import NetworkTerminalSensor
from .smb_sharing import SmbCreateShareRequest, SmbToggleRequest, WindowsSmbSharingManager
from .speedtest import NetworkSpeedTester
from .tui import NetworkTerminalState
router = APIRouter(prefix='/api/v1/network', tags=['network'])
_telemetry_logger = AppTelemetryLogger('network_terminal')
_sensor = NetworkTerminalSensor()
_speedtester = NetworkSpeedTester()
_lan_scanner = WindowsLanScanner()
_remote_auth = WindowsRemoteAuthenticator()
_remote_access = WindowsRemoteAccessManager()
_smb_sharing = WindowsSmbSharingManager()
_visibility_diag = LanVisibilityDiagnostics(smb_manager=_smb_sharing)
_state: NetworkTerminalState | None = None
_latest_speedtest: Dict[str, Any] | None = None

def get_state() -> NetworkTerminalState:
    """Get or create the network terminal state instance."""
    global _state
    if _state is None:
        _state = NetworkTerminalState()
    return _state

def _get_process_name(pid: Optional[int]) -> str:
    """Safely resolve process name by PID."""
    if not pid or pid <= 4:
        return 'System' if pid == 4 else 'Idle'
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return f'PID {pid}'

@router.get('/status')
async def get_status(request: Request) -> dict:
    """Get current network terminal status and summary."""
    state = get_state()
    state.evaluate_security()
    stats = state.compute_stats()
    tshark_avail = TSharkWrapper().is_available() if TSharkWrapper is not None else False
    conn_count = 0
    listen_count = 0
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.status == psutil.CONN_LISTEN:
                listen_count += 1
            elif c.status == psutil.CONN_ESTABLISHED:
                conn_count += 1
    except Exception:
        pass
    adapter_count = len(psutil.net_if_addrs())
    _telemetry_logger.log_poll(poll_type='network_status', metric_name='total_packets', value=state.total_packets_captured, unit='packets', status='OK', details={'interface': state.interface, 'bytes': state.total_bytes_captured, 'adapters': adapter_count, 'established': conn_count, 'listening': listen_count})
    return {'available': True, 'tshark_available': tshark_avail, 'interface': state.interface, 'filter': state.display_filter, 'total_packets': state.total_packets_captured, 'total_bytes': state.total_bytes_captured, 'protocol_counts': state.protocol_counts, 'latest_ai_report': state.latest_ai_report.model_dump() if state.latest_ai_report else None, 'latest_heuristics': state.latest_heuristics, 'total_adapters': adapter_count, 'active_connections_count': conn_count, 'listening_ports_count': listen_count}

@router.get('/interfaces')
async def get_interfaces(request: Request) -> List[dict]:
    """Get detailed list of host network interfaces and adapters."""
    interfaces: List[dict] = []
    native_adapters = _sensor.get_network_adapters_native()
    native_map = {a.get('name', '').lower(): a for a in native_adapters if a.get('name')}
    if_addrs = psutil.net_if_addrs()
    if_stats = psutil.net_if_stats()
    net_io = psutil.net_io_counters(pernic=True)
    idx = 1
    for iface_name, addrs in if_addrs.items():
        ipv4_list = []
        ipv6_list = []
        mac_addr = ''
        for addr in addrs:
            if addr.family == psutil.AF_LINK or str(addr.family).endswith('AF_LINK'):
                mac_addr = addr.address
            elif str(addr.family) in ('AddressFamily.AF_INET', '2'):
                ipv4_list.append(addr.address)
            elif str(addr.family) in ('AddressFamily.AF_INET6', '23'):
                ipv6_list.append(addr.address)
        stat = if_stats.get(iface_name)
        io = net_io.get(iface_name)
        native_item = native_map.get(iface_name.lower(), {})
        is_up = stat.isup if stat else True
        speed_mbps = stat.speed if stat and stat.speed > 0 else native_item.get('speed_mbps', 0)
        description = native_item.get('description') or iface_name
        interfaces.append({'id': str(idx), 'name': iface_name, 'description': description, 'status': 'Up' if is_up else 'Down', 'is_up': is_up, 'speed_mbps': speed_mbps, 'mac': mac_addr or native_item.get('mac', ''), 'ipv4': ipv4_list, 'ipv6': ipv6_list, 'bytes_sent': io.bytes_sent if io else 0, 'bytes_recv': io.bytes_recv if io else 0, 'packets_sent': io.packets_sent if io else 0, 'packets_recv': io.packets_recv if io else 0})
        idx += 1
    return interfaces

@router.get('/connections')
async def get_connections(request: Request, limit: int=150) -> dict:
    """Get active network connections and listening ports with process info."""
    connections: List[dict] = []
    listening_ports: List[dict] = []
    try:
        raw_conns = psutil.net_connections(kind='inet')
        for c in raw_conns:
            laddr_str = f'{c.laddr.ip}:{c.laddr.port}' if c.laddr else '-'
            raddr_str = f'{c.raddr.ip}:{c.raddr.port}' if c.raddr else '-'
            proto = 'TCP' if c.type == 1 else 'UDP' if c.type == 2 else 'RAW'
            proc_name = _get_process_name(c.pid)
            item = {'fd': c.fd, 'protocol': proto, 'local_address': laddr_str, 'remote_address': raddr_str, 'status': c.status, 'pid': c.pid, 'process_name': proc_name}
            if c.status == psutil.CONN_LISTEN:
                listening_ports.append(item)
            else:
                connections.append(item)
    except Exception as ex:
        logger.debug(f'psutil net_connections error: {ex}')
        native_listening = _sensor.get_listening_ports_native()
        for p in native_listening:
            listening_ports.append({'protocol': 'TCP', 'local_address': f"{p.get('ip', '0.0.0.0')}:{p.get('port', 0)}", 'remote_address': '-', 'status': 'LISTEN', 'pid': p.get('pid'), 'process_name': p.get('process') or _get_process_name(p.get('pid'))})
    return {'connections': connections[:limit], 'listening_ports': listening_ports[:limit], 'total_connections': len(connections), 'total_listening': len(listening_ports)}

@router.get('/telemetry')
async def get_telemetry(request: Request) -> dict:
    """Get real-time network throughput and sensor rates."""
    sensors = _sensor.get_network_sensors()
    return {'sensors': [{'sensor_id': s.sensor_id, 'name': s.name, 'category': s.category, 'value': s.value, 'unit': s.unit} for s in sensors]}

@router.get('/packets')
async def get_packets(request: Request, limit: int=50) -> dict:
    """Get last captured packets from the buffer."""
    state = get_state()
    packets = list(state.packet_buffer)[-limit:]
    return {'packets': [{'packet_number': p.packet_number, 'timestamp': p.timestamp, 'source': p.source, 'destination': p.destination, 'protocol': p.protocol, 'length': p.length, 'source_port': p.source_port, 'destination_port': p.destination_port, 'info': p.info} for p in packets]}

@router.get('/packets/stream')
async def stream_packets(request: Request):
    """Stream packets in real-time via SSE."""
    state = get_state()

    async def event_generator():
        while True:
            packets = list(state.packet_buffer)[-10:]
            if packets:
                yield f'data: {len(packets)} new packets\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type='text/event-stream')

@router.get('/stats')
async def get_stats(request: Request) -> dict:
    """Get traffic statistics."""
    state = get_state()
    stats = state.compute_stats()
    avg_packet_size = round(stats.total_bytes / stats.total_packets, 2) if stats.total_packets > 0 else 0.0
    return {'total_packets': stats.total_packets, 'total_bytes': stats.total_bytes, 'avg_packet_size': avg_packet_size, 'avg_bps': 0.0, 'avg_pps': 0.0, 'top_protocols': stats.protocol_distribution, 'top_sources': stats.top_sources, 'top_destinations': stats.top_destinations}

@router.get('/security')
async def get_security(request: Request) -> dict:
    """Get security analysis results."""
    state = get_state()
    state.evaluate_security()
    return {'heuristics': state.latest_heuristics, 'ai_report': state.latest_ai_report.model_dump() if state.latest_ai_report else None}

@router.post('/speedtest/run')
@router.get('/speedtest/run')
async def run_speedtest(request: Request) -> dict:
    """Run full internet speed, ping, jitter, download, and upload benchmark."""
    global _latest_speedtest
    report = await _speedtester.run_full_speedtest()
    _latest_speedtest = report
    return report

@router.get('/speedtest/latest')
async def get_latest_speedtest(request: Request) -> dict:
    """Get latest cached speedtest report."""
    global _latest_speedtest
    if _latest_speedtest is None:
        return {'status': 'NO_DATA', 'message': 'Тест скорости еще не запускался.'}
    return _latest_speedtest

@router.get('/speedtest/ping')
async def ping_servers(request: Request) -> dict:
    """Quick ping latency probe to global DNS and CDN edge servers."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        servers = await _speedtester.measure_ping_servers(client)
        meta = await _speedtester.get_meta_info(client)
        return {'timestamp': time.time(), 'meta': meta, 'servers': servers}

@router.post('/start-capture')
async def start_capture(request: Request, interface: str='1', display_filter: str='') -> dict:
    """Start network capture (admin only)."""
    require_admin_user(request)
    global _state
    _state = NetworkTerminalState(interface=interface, display_filter=display_filter)
    _telemetry_logger.log_event(event_type='start_capture', status='SUCCESS', details={'interface': interface, 'filter': display_filter})
    return {'success': True, 'message': f'Capture started on interface {interface}'}

@router.post('/stop-capture')
async def stop_capture(request: Request) -> dict:
    """Stop network capture (admin only)."""
    require_admin_user(request)
    global _state
    _state = None
    _telemetry_logger.log_event(event_type='stop_capture', status='SUCCESS', details='Capture stopped')
    return {'success': True, 'message': 'Capture stopped'}

@router.post('/analyze/pcap')
async def analyze_pcap(request: Request, file: UploadFile=File(...), max_packets: int=500) -> dict:
    """Analyze uploaded PCAP file via TSharkWrapper and AIDetector."""
    wrapper = TSharkWrapper() if TSharkWrapper is not None else None
    if wrapper is None or not wrapper.is_available():
        return {'error': 'TShark is not installed on this system', 'stats': {'total_packets': 0, 'total_bytes': 0}, 'heuristics': ['TShark executable not available on host'], 'ai_report': {'health_score': 100, 'anomalies': []}, 'sample_packets': []}
    suffix = os.path.splitext(file.filename or 'sample.pcap')[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        packets = wrapper.read_pcap(tmp_path, max_packets=max_packets)
        analyzer = TrafficAnalyzer()
        stats = analyzer.compute_stats(packets)
        heuristics = analyzer.detect_heuristics(packets)
        detector = AIDetector()
        ai_report = await detector.diagnose_traffic(packets, stats, heuristics)
        return {'stats': {'total_packets': stats.total_packets, 'total_bytes': stats.total_bytes, 'protocol_distribution': stats.protocol_distribution, 'top_sources': stats.top_sources, 'top_destinations': stats.top_destinations}, 'heuristics': heuristics, 'ai_report': ai_report.model_dump() if ai_report else None, 'sample_packets': [{'number': p.number, 'timestamp': p.timestamp, 'source': p.source_ip, 'destination': p.destination_ip, 'protocol': p.protocol, 'length': p.length, 'info': p.info} for p in packets[:100]]}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.get('/subnets')
async def get_subnets(request: Request) -> dict:
    """Get active IPv4 local subnets and default gateways."""
    ifaces = _lan_scanner.get_local_interfaces_info()
    gateways = list(_lan_scanner.get_default_gateways())
    subnets = [{'name': iface['name'], 'ip': iface['ip'], 'cidr': iface['cidr']} for iface in ifaces]
    return {'subnets': subnets, 'gateways': gateways}

@router.get('/devices')
async def get_lan_devices(request: Request, scan: bool = False, subnet: Optional[str] = None) -> dict:
    """Get discovered devices on the local network (ARP/Neighbor Cache or Active Scan)."""
    if scan:
        devices = await asyncio.to_thread(_lan_scanner.discover_devices, full_scan=True, subnet_cidr=subnet)
    else:
        devices = await asyncio.to_thread(_lan_scanner.discover_devices, full_scan=False, subnet_cidr=subnet)
    return {
        'devices': [d.model_dump() for d in devices],
        'total': len(devices),
        'scan_timestamp': time.time(),
        'scan_type': 'active' if scan else 'cache',
    }

@router.post('/devices/scan')
async def trigger_lan_scan(request: Request, subnet: Optional[str] = None) -> dict:
    """Trigger active ARP sweep and SSDP scan of the local subnet."""
    devices = await asyncio.to_thread(_lan_scanner.discover_devices, full_scan=True, subnet_cidr=subnet)
    _telemetry_logger.log_event(
        event_type='lan_scan',
        status='SUCCESS',
        details={'devices_found': len(devices), 'subnet': subnet or 'all'},
    )
    return {
        'devices': [d.model_dump() for d in devices],
        'total': len(devices),
        'scan_timestamp': time.time(),
        'status': 'SUCCESS',
    }

@router.get('/devices/probe')
async def probe_device(request: Request, ip: str) -> dict:
    """Быстрая проверка доступности и стандартных портов хоста (SMB, RDP, HTTP, HTTPS, SSH, WinRM)."""
    common_ports = [
        {'port': 445, 'name': 'SMB', 'desc': 'Общие папки Windows'},
        {'port': 3389, 'name': 'RDP', 'desc': 'Удалённый рабочий стол'},
        {'port': 80, 'name': 'HTTP', 'desc': 'Веб-сервер'},
        {'port': 443, 'name': 'HTTPS', 'desc': 'Защищенный веб'},
        {'port': 22, 'name': 'SSH', 'desc': 'Удаленный терминал'},
        {'port': 5985, 'name': 'WinRM', 'desc': 'Управление Windows'},
        {'port': 5357, 'name': 'WSD', 'desc': 'Службы устройств WSD'},
        {'port': 139, 'name': 'NetBIOS', 'desc': 'Сессия NetBIOS'},
    ]

    def check_ports() -> List[dict]:
        results: List[dict] = []
        for p in common_ports:
            port = p['port']
            is_open = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.35)
                    if s.connect_ex((ip, port)) == 0:
                        is_open = True
            except Exception:
                pass
            results.append({**p, 'is_open': is_open})
        return results

    port_status = await asyncio.to_thread(check_ports)
    open_ports = [p['port'] for p in port_status if p['is_open']]
    return {
        'ip': ip,
        'open_ports': open_ports,
        'details': port_status,
        'timestamp': time.time(),
    }


@router.post('/devices/login')
async def login_remote_device(request: Request, payload: RemoteLoginRequest) -> dict:
    """Выполняет попытку аутентификации на удалённом компьютере в локальной сети (SMB / WinRM)."""
    try:
        result = await asyncio.to_thread(
            _remote_auth.authenticate,
            ip=payload.ip,
            username=payload.username,
            password=payload.password,
            protocol=payload.protocol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _telemetry_logger.log_event(
        event_type='lan_remote_login',
        status='SUCCESS' if result.success else 'FAILED',
        details={
            'ip': result.ip,
            'username': result.username,
            'protocol': result.protocol_used,
            'error_code': result.error_code,
        },
    )
    return result.model_dump()


@router.get('/remote-access/status')
async def get_remote_access_status(request: Request) -> dict:
    """Возвращает состояние настроек входящего удалённого доступа (SMB 445, WinRM 5985, профиль сети, UAC)."""
    status = await asyncio.to_thread(_remote_access.get_status)
    return status.model_dump()


@router.post('/remote-access/apply')
async def apply_remote_access_setting(request: Request, payload: RemoteAccessApplyRequest) -> dict:
    """Применяет выбранную настройку входящего удалённого доступа Windows."""
    result = await asyncio.to_thread(_remote_access.apply_action, payload.action)
    _telemetry_logger.log_event(
        event_type='remote_access_config',
        status='SUCCESS' if result.success else 'FAILED',
        details={
            'action': result.action,
            'requires_admin': result.requires_admin,
            'message': result.message,
        },
    )
    return result.model_dump()


@router.get('/sharing/status')
async def get_smb_sharing_status(request: Request) -> dict:
    """Возвращает состояние SMB1/2/3, служб, правил @FirewallAPI.dll,-28502 и списка шар."""
    status = await asyncio.to_thread(_smb_sharing.get_status)
    return status.model_dump()


@router.get('/sharing/sessions')
async def get_smb_sharing_sessions(request: Request) -> dict:
    """Возвращает список активных входящих SMB-сессий (Get-SmbSession)."""
    sessions = await asyncio.to_thread(_smb_sharing.get_sessions)
    return {'sessions': [s.model_dump() for s in sessions], 'total': len(sessions)}


@router.get('/sharing/shares/{share_name}/access')
async def get_smb_share_access(request: Request, share_name: str) -> dict:
    """Возвращает таблицу прав доступа к указанной общей папке Windows."""
    try:
        entries = await asyncio.to_thread(_smb_sharing.get_share_access, share_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'share_name': share_name, 'access': [e.model_dump() for e in entries]}


@router.post('/sharing/toggle')
async def toggle_smb_file_sharing(request: Request, payload: SmbToggleRequest) -> dict:
    """Включает или отключает File and Printer Sharing с предварительным снимком для отката."""
    snap = await asyncio.to_thread(
        _visibility_diag.create_snapshot,
        f"before_sharing_{'enable' if payload.enable else 'disable'}",
    )
    result = await asyncio.to_thread(
        _smb_sharing.toggle_file_sharing,
        enable=payload.enable,
        profiles=list(payload.profiles),
        start_server_service=payload.start_server_service,
        snapshot_id=snap.snapshot_id,
    )
    return result.model_dump()


@router.post('/sharing/shares')
async def create_smb_share(request: Request, payload: SmbCreateShareRequest) -> dict:
    """Публикует новую общую папку Windows (New-SmbShare)."""
    result = await asyncio.to_thread(_smb_sharing.create_share, payload)
    return result.model_dump()


@router.delete('/sharing/shares/{share_name}')
async def remove_smb_share(request: Request, share_name: str) -> dict:
    """Удаляет пользовательскую общую папку Windows (Remove-SmbShare)."""
    result = await asyncio.to_thread(_smb_sharing.remove_share, share_name)
    return result.model_dump()


@router.get('/visibility/diagnose')
async def diagnose_lan_visibility(request: Request) -> dict:
    """Выполняет 4-уровневую диагностику видимости ПК в локальной сети (L1..L4)."""
    report = await asyncio.to_thread(_visibility_diag.diagnose)
    return report.model_dump()


@router.get('/visibility/snapshots')
async def list_visibility_snapshots(request: Request, limit: int = 20) -> dict:
    """Возвращает историю снимков сетевых настроек для отката."""
    snaps = await asyncio.to_thread(_visibility_diag.list_snapshots, limit)
    return {'snapshots': [s.model_dump() for s in snaps], 'total': len(snaps)}


@router.post('/visibility/snapshots')
async def create_visibility_snapshot(request: Request, reason: str = 'manual') -> dict:
    """Создаёт снимок текущего состояния сетевых настроек."""
    snap = await asyncio.to_thread(_visibility_diag.create_snapshot, reason)
    return snap.model_dump()


@router.post('/visibility/rollback/{snapshot_id}')
async def rollback_visibility_snapshot(request: Request, snapshot_id: str) -> dict:
    """Восстанавливает сетевые профили и правила Discovery/Sharing из снимка."""
    result = await asyncio.to_thread(_visibility_diag.rollback, snapshot_id)
    if not result.success and 'не найден' in result.message:
        raise HTTPException(status_code=404, detail=result.message)
    return result.model_dump()


def init_router() -> APIRouter:
    """Initialize the FastAPI router for Network Terminal."""
    return router
__all__ = ['init_router', 'router']
