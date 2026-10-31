# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Network Activity Collector
# =============================================================================
# Description:
#   Сборщик сетевой активности: слушающие порты и соединения процессов с классификацией трафика.
#   Вынесено из collector.py при декомпозиции SystemCollector (этап 4 ТЗ оптимизации).
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.network_activity import NetworkActivityCollector
#
#     component = NetworkActivityCollector()
#
# File: network_activity.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 05:00:00
# =============================================================================

from __future__ import annotations
"""Сборщик сетевой активности: слушающие порты и соединения процессов с классификацией трафика."""

import socket
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from logger import logger
from .models import NetworkPortMetrics, ProcessNetworkActivity


class NetworkActivityCollector:
    """Сборщик сетевой активности: слушающие порты и соединения процессов с классификацией трафика."""

    def __init__(self) -> None:
        """Инициализирует состояние дельт ввода-вывода процессов."""
        self._last_proc_net_io: Dict[int, Tuple[float, float, float]] = {}

    def get_listening_ports(self, limit: int=15) -> List[NetworkPortMetrics]:
        """Collect active listening TCP/UDP sockets with process attribution.

        Args:
            limit: Maximum listening ports to return.

        Returns:
            List[NetworkPortMetrics]: Active listening ports.
        """
        ports: List[NetworkPortMetrics] = []
        if PSUTIL_AVAILABLE:
            try:
                conns = psutil.net_connections(kind='inet')
                seen = set()
                for c in conns:
                    if c.status == 'LISTEN' or c.type == socket.SOCK_DGRAM:
                        p_num = c.laddr.port
                        if p_num in seen:
                            continue
                        seen.add(p_num)
                        p_name = None
                        if c.pid:
                            try:
                                p_name = psutil.Process(c.pid).name()
                            except Exception:
                                pass
                        ports.append(NetworkPortMetrics(port=p_num, protocol='TCP' if c.type == socket.SOCK_STREAM else 'UDP', address=c.laddr.ip or '0.0.0.0', pid=c.pid, process_name=p_name))
                        if len(ports) >= limit:
                            break
            except Exception as ex:
                logger.debug(f'Failed to query listening ports: {ex}')
        return ports

    def get_process_network_activity(self, limit: int=50, only_internet: bool=False) -> List[ProcessNetworkActivity]:
        """Collect active network connections and traffic attribution for processes.

        Args:
            limit: Maximum connections to return.
            only_internet: Whether to restrict only to external internet addresses.

        Returns:
            List[ProcessNetworkActivity]: Active network connections with process and traffic description.
        """
        activities: List[ProcessNetworkActivity] = []
        if not PSUTIL_AVAILABLE:
            return activities
        try:
            raw_conns = psutil.net_connections(kind='inet')
        except Exception as ex:
            logger.debug(f'Failed to query network connections: {ex}')
            return activities
        proc_cache: Dict[int, Dict[str, Any]] = {}
        now_ts = time.time()

        def _get_proc_info(pid: Optional[int]) -> Dict[str, Any]:
            if not pid or pid == 0:
                return {'name': 'System Idle', 'user': 'SYSTEM', 'read_kb': 0.0, 'write_kb': 0.0, 'delta_read_kb': 0.0, 'delta_write_kb': 0.0, 'read_speed_kbs': 0.0, 'write_speed_kbs': 0.0}
            if pid == 4:
                return {'name': 'System', 'user': 'NT AUTHORITY\\SYSTEM', 'read_kb': 0.0, 'write_kb': 0.0, 'delta_read_kb': 0.0, 'delta_write_kb': 0.0, 'read_speed_kbs': 0.0, 'write_speed_kbs': 0.0}
            if pid in proc_cache:
                return proc_cache[pid]
            try:
                p = psutil.Process(pid)
                pname = p.name()
                puser = ''
                try:
                    puser = p.username()
                except Exception:
                    puser = ''
                read_kb = 0.0
                write_kb = 0.0
                delta_read_kb = 0.0
                delta_write_kb = 0.0
                read_speed_kbs = 0.0
                write_speed_kbs = 0.0
                try:
                    io = p.io_counters()
                    read_kb = round(io.read_bytes / 1024, 1)
                    write_kb = round(io.write_bytes / 1024, 1)
                    if hasattr(self, '_last_proc_net_io') and pid in self._last_proc_net_io:
                        prev_t, prev_r, prev_w = self._last_proc_net_io[pid]
                        dt = max(now_ts - prev_t, 0.1)
                        if io.read_bytes >= prev_r:
                            delta_read_kb = round((io.read_bytes - prev_r) / 1024, 1)
                            read_speed_kbs = round(delta_read_kb / dt, 1)
                        if io.write_bytes >= prev_w:
                            delta_write_kb = round((io.write_bytes - prev_w) / 1024, 1)
                            write_speed_kbs = round(delta_write_kb / dt, 1)
                    if hasattr(self, '_last_proc_net_io'):
                        self._last_proc_net_io[pid] = (now_ts, io.read_bytes, io.write_bytes)
                except Exception:
                    pass
                info = {'name': pname, 'user': puser, 'read_kb': read_kb, 'write_kb': write_kb, 'delta_read_kb': delta_read_kb, 'delta_write_kb': delta_write_kb, 'read_speed_kbs': read_speed_kbs, 'write_speed_kbs': write_speed_kbs}
                proc_cache[pid] = info
                return info
            except Exception:
                info = {'name': f'PID {pid}', 'user': '', 'read_kb': 0.0, 'write_kb': 0.0, 'delta_read_kb': 0.0, 'delta_write_kb': 0.0, 'read_speed_kbs': 0.0, 'write_speed_kbs': 0.0}
                proc_cache[pid] = info
                return info

        def _is_ext_internet(ip: str) -> bool:
            if not ip:
                return False
            if ip in ('127.0.0.1', '::1', '0.0.0.0', '::') or ip.startswith('127.') or ip.startswith('fe80:'):
                return False
            return True
        for c in raw_conns:
            laddr_str = f'{c.laddr.ip}:{c.laddr.port}' if c.laddr else '-'
            raddr_str = f'{c.raddr.ip}:{c.raddr.port}' if c.raddr else '-'
            rip = c.raddr.ip if c.raddr else ''
            rport = c.raddr.port if c.raddr else 0
            lport = c.laddr.port if c.laddr else 0
            is_ext = _is_ext_internet(rip)
            if only_internet and (not is_ext):
                continue
            proto = 'TCP' if c.type == socket.SOCK_STREAM else 'UDP'
            status = c.status or ('LISTEN' if not c.raddr else 'ESTABLISHED')
            p_info = _get_proc_info(c.pid)
            p_name = p_info['name']
            p_user = p_info['user']
            service_type, sent_desc, recv_desc = self._classify_traffic(p_name, rport or lport, proto, status, is_ext)
            activities.append(ProcessNetworkActivity(pid=c.pid or 0, name=p_name, user=p_user, local_address=laddr_str, remote_address=raddr_str, remote_host=None, protocol=proto, status=status, is_internet=is_ext, service_type=service_type, sent_kb=p_info.get('write_kb', 0.0), recv_kb=p_info.get('read_kb', 0.0), delta_sent_kb=p_info.get('delta_write_kb', 0.0), delta_recv_kb=p_info.get('delta_read_kb', 0.0), sent_rate_kbs=p_info.get('write_speed_kbs', 0.0), recv_rate_kbs=p_info.get('read_speed_kbs', 0.0), sent_summary=sent_desc, recv_summary=recv_desc))
            if len(activities) >= limit:
                break
        return activities

    @staticmethod
    def _classify_traffic(proc_name: str, port: int, proto: str, status: str, is_internet: bool) -> tuple[str, str, str]:
        """Classify network traffic service type and generate human-readable summaries."""
        p_lower = proc_name.lower()
        if status == 'LISTEN' or not is_internet:
            if 'python' in p_lower or 'uvicorn' in p_lower or 'node' in p_lower:
                return ('Локальный Web API / Сервер', 'HTTP ответы локальным клиентам / WebSockets', 'Входящие HTTP запросы от фронтенда / браузера')
            return ('Локальная служба / Socket', 'Служебные ответы локальной подсистемы', 'Ожидание входящих подключений (Listen)')
        if port in (443, 8443):
            if any((b in p_lower for b in ('edge', 'chrome', 'firefox', 'brave', 'opera', 'browser'))):
                return ('HTTPS / Веб-навигация', 'Исходящие HTTPS запросы, URL заголовки, формы, cookies', 'HTML страницы, скрипты, видео, изображения, медиа')
            if any((m in p_lower for m in ('telegram', 'discord', 'slack', 'whatsapp', 'skype'))):
                return ('Мессенджер / Зашифрованный чат', 'Текстовые сообщения, медиа-файлы, голосовые пакеты, пинги', 'Входящие сообщения, аудио/видеопоток, обновления чатов')
            if any((s in p_lower for s in ('onedrive', 'googledrivefs', 'dropbox', 'cloud'))):
                return ('Облачная синхронизация / Хранилище', 'Выгрузка локальных файлов, метаданные изменений', 'Синхронизация файлов из облака, снимки папок')
            if any((d in p_lower for d in ('code', 'devenv', 'language_server', 'python', 'pycharm', 'git'))):
                return ('Разработка / LLM API & Git', 'AI промпты к LLM моделям, API вызовы, git push, пакеты', 'Сгенерированный AI код, ответы API, пакеты библиотек')
            if any((w in p_lower for w in ('svchost', 'system', 'msmpeng', 'searchindexer', 'spoolsv'))):
                return ('Системные службы Windows / Облако MS', 'Телеметрия Defender, проверка сертификатов, запросы ОС', 'Сигнатуры безопасности, метаданные обновлений Windows')
            return ('HTTPS / Зашифрованный веб-трафик', 'Зашифрованные HTTPS/TLS запросы и полезная нагрузка', 'Ответы удаленного веб-сервера, зашифрованные данные')
        if port in (80, 8080):
            return ('HTTP / Открытый веб-трафик', 'HTTP GET/POST запросы, клиентские заголовки', 'HTML веб-страницы, незашифрованный контент, ответы')
        if port == 53:
            return ('DNS / Разрешение имен', 'Запросы на получение IP-адресов доменов (DNS Queries)', 'DNS-ответы с IP-адресами серверов (DNS Answers)')
        if port in (5222, 5223, 5228):
            return ('Push-нотификации / XMPP', 'Heartbeat пинги, исходящие push-запросы', 'Входящие фоновые push-уведомления и события')
        if port == 22:
            return ('SSH / Защищенный терминал', 'Команды консоли, зашифрованные SSH сессии', 'Вывод удаленного терминала, файловые потоки SFTP')
        if port == 7680:
            return ('WUDO / P2P обновления Windows', 'P2P раздача фрагментов обновлений ОС', 'P2P получение компонентов обновлений ОС')
        if port in (465, 587):
            return ('SMTP / Почтовая отправка', 'Исходящие электронные письма (MIME/SMTP)', 'Квитанции доставки, подтверждения почтового сервера')
        if port in (993, 995):
            return ('IMAP/POP3 / Почтовый прием', 'Команды проверки новых писем и папок', 'Входящие электронные письма, заголовки, вложения')
        return (f'{proto}/{port}', f'Исходящие пакеты данных ({proto}) на порт {port}', f'Входящие пакеты и ответы сервера с порта {port}')

