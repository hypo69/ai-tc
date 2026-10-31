# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Defender Core - Process Tree Watcher
# =============================================================================
# Description:
#   Модуль инспекции дерева процессов и детекции подозрительных цепочек выполнения.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.defender.core.process_tree_watcher import ProcessTreeWatcher
#
#     service = ProcessTreeWatcher()
#
# File: process_tree_watcher.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.defender.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 14:10:00
# =============================================================================

from __future__ import annotations
"""Модуль инспекции дерева процессов и детекции подозрительных цепочек выполнения."""

import re
import threading
import time
from typing import List, Optional, Tuple
import psutil
from logger import logger
from apps.windows.sdk.modules.defender.core.models import SuspiciousProcessChain, ThreatSeverity

class ProcessTreeWatcher:
    """Анализатор дерева процессов и цепочек запуска."""
    SUSPICIOUS_PARENTS = {'winword.exe': 'Microsoft Word', 'excel.exe': 'Microsoft Excel', 'powerpnt.exe': 'Microsoft PowerPoint', 'outlook.exe': 'Microsoft Outlook', 'acrord32.exe': 'Adobe Acrobat Reader', 'acrobat.exe': 'Adobe Acrobat'}
    DANGEROUS_CHILDREN = {'powershell.exe', 'pwsh.exe', 'cmd.exe', 'wscript.exe', 'cscript.exe', 'mshta.exe', 'rundll32.exe', 'regsvr32.exe', 'certutil.exe', 'bitsadmin.exe', 'curl.exe', 'vssadmin.exe', 'schtasks.exe', 'wmic.exe'}
    SUSPICIOUS_CMD_PATTERNS = [(re.compile('-(enc|encodedcommand)\\s+[a-za-z0-9+/=]+', re.I), 'Использование закодированной Base64 команды PowerShell'), (re.compile('bypass\\s+-noprofile', re.I), 'Обход политики выполнения скриптов (ExecutionPolicy Bypass)'), (re.compile('downloadstring|downloaddata|downloadfile', re.I), 'Загрузка удаленного контента через WebClient/Net.Sockets'), (re.compile('\\biex\\b|invoke-expression', re.I), 'Динамическое выполнение кода в памяти (Invoke-Expression / Fileless)'), (re.compile('certutil.*-(decode|urlcache)', re.I), 'Использование Certutil для загрузки/декодирования полезной нагрузки'), (re.compile('bitsadmin.*/transfer', re.I), 'Скрытая загрузка файлов через службу BITS'), (re.compile('vssadmin.*delete\\s+shadows', re.I), 'Попытка удаления теневых копий VSS (типично для Ransomware)')]

    def __init__(self) -> None:
        """Инициализация анализатора процессов с оперативным кэшированием."""
        self._cache: List[SuspiciousProcessChain] = []
        self._cache_time: float = 0.0
        self._cache_lock = threading.Lock()

    def scan_suspicious_chains(self, ttl_sec: float = 30.0) -> List[SuspiciousProcessChain]:
        """Сканирование текущих процессов на предмет аномальных связей родитель-потомок.

        Args:
            ttl_sec: Время жизни кэша обнаруженных цепочек (по умолчанию 30 с).

        Returns:
            List[SuspiciousProcessChain]: Список обнаруженных подозрительных цепочек.
        """
        with self._cache_lock:
            if self._cache and (time.time() - self._cache_time < ttl_sec):
                return list(self._cache)

        results: List[SuspiciousProcessChain] = []
        try:
            procs_by_pid = {}
            for p in psutil.process_iter(['pid', 'name', 'ppid']):
                try:
                    procs_by_pid[p.info['pid']] = (p.info, p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            for pid, (info, proc_obj) in procs_by_pid.items():
                pname = (info.get('name') or '').lower()
                ppid = info.get('ppid')
                parent_info = procs_by_pid.get(ppid, ({}, None))[0] if ppid else {}
                parent_name = (parent_info.get('name') or '').lower()

                # Проверяем только потенциально подозрительные процессы или потомков подозрительных родителей
                is_suspicious_child = pname in self.DANGEROUS_CHILDREN
                is_suspicious_parent = parent_name in self.SUSPICIOUS_PARENTS
                if not (is_suspicious_child or is_suspicious_parent):
                    continue

                cmdline_str = ''
                try:
                    cmdline_list = proc_obj.cmdline() or []
                    cmdline_str = ' '.join(cmdline_list)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                if is_suspicious_parent and is_suspicious_child:
                    results.append(SuspiciousProcessChain(
                        parent_process=parent_name,
                        parent_pid=ppid,
                        child_process=pname,
                        child_pid=pid,
                        command_line=cmdline_str,
                        severity=ThreatSeverity.SEVERE,
                        reason=f"Офисное приложение '{self.SUSPICIOUS_PARENTS[parent_name]}' запустило интерпретатор/утилиту '{pname}' (высокий риск эксплуатации макроса/эксплойта)."
                    ))

                if cmdline_str:
                    for pattern, reason in self.SUSPICIOUS_CMD_PATTERNS:
                        if pattern.search(cmdline_str):
                            if not any((r.child_pid == pid for r in results)):
                                results.append(SuspiciousProcessChain(
                                    parent_process=f'PID:{ppid}',
                                    parent_pid=ppid,
                                    child_process=pname,
                                    child_pid=pid,
                                    command_line=cmdline_str,
                                    severity=ThreatSeverity.HIGH,
                                    reason=f'Обнаружен опасный шаблон выполнения: {reason}'
                                ))
        except Exception as e:
            logger.debug(f'Ошибка анализа дерева процессов: {e}')

        with self._cache_lock:
            self._cache = list(results)
            self._cache_time = time.time()
        return results
