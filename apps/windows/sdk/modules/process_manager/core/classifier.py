# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Process_Manager Core - Classifier
# =============================================================================
# Description:
#   Движок классификации и группировки процессов Windows на категории:
#   1. Apps (Интерактивные оконные приложения и их подпроцессы)
#   2. Background processes (Фоновые службы и вспомогательные процессы)
#   3. Windows processes (Критические системные процессы ОС)
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.process_manager.core.classifier import ProcessClassifier
#
#     classifier = ProcessClassifier()
#     report = classifier.classify_processes()
#
# File: classifier.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.process_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 16:16:00
# =============================================================================

from __future__ import annotations
"""Движок классификации процессов Windows (Apps, Background processes, Windows processes)."""

import ctypes
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import psutil
from logger import logger
from apps.windows.sdk.modules.process_manager.core.models import (
    CategorizedProcessReport,
    ProcessGroupItem,
    ProcessItem,
)

# Системные процессы Windows (Windows processes)
WINDOWS_SYSTEM_PROCESS_NAMES = {
    'system',
    'system idle process',
    'registry',
    'smss.exe',
    'csrss.exe',
    'wininit.exe',
    'services.exe',
    'lsass.exe',
    'svchost.exe',
    'dwm.exe',
    'fontdrvhost.exe',
    'winlogon.exe',
    'sihost.exe',
    'taskhostw.exe',
    'taskhost.exe',
    'runtimebroker.exe',
    'ctfmon.exe',
    'spoolsv.exe',
    'werfault.exe',
    'lsiso.exe',
    'secure-system',
    'vssvc.exe',
    'conhost.exe',
    'searchindexer.exe',
    'searchhost.exe',
    'startmenuexperiencehost.exe',
    'shellexperiencehost.exe',
    'smartscreen.exe',
    'securityhealthservice.exe',
    'securityhealthsystray.exe',
    'audiodg.exe',
    'wlanext.exe',
    'dashost.exe',
}

# Известные соответствия бинарников читаемым именам приложений (Friendly Names)
KNOWN_APP_FRIENDLY_NAMES = {
    'chrome.exe': 'Google Chrome',
    'msedge.exe': 'Microsoft Edge',
    'code.exe': 'Visual Studio Code',
    'antigravity.exe': 'Antigravity',
    'chatgpt.exe': 'ChatGPT',
    'telegram.exe': 'Telegram Desktop',
    'whatsapp.exe': 'WhatsApp',
    'keepass.exe': 'KeePass',
    'keepassxc.exe': 'KeePassXC',
    'taskmgr.exe': 'Task Manager',
    'windowsterminal.exe': 'Терминал',
    'wt.exe': 'Терминал',
    'explorer.exe': 'Windows Explorer',
    'notepad.exe': 'Блокнот',
    'devenv.exe': 'Microsoft Visual Studio',
    'slack.exe': 'Slack',
    'discord.exe': 'Discord',
    'spotify.exe': 'Spotify',
    'obs64.exe': 'OBS Studio',
    'vlc.exe': 'VLC Media Player',
    'postman.exe': 'Postman',
    'docker desktop.exe': 'Docker Desktop',
    'pycharm64.exe': 'PyCharm',
    'idea64.exe': 'IntelliJ IDEA',
    'rider64.exe': 'JetBrains Rider',
    'cursor.exe': 'Cursor IDE',
    'windsurf.exe': 'Windsurf IDE',
}


class ProcessClassifier:
    """Классификатор процессов Windows на Apps, Background и Windows процессы."""

    def __init__(self) -> None:
        """Инициализация классификатора процессов."""
        self._user32 = getattr(ctypes.windll, 'user32', None) if os.name == 'nt' else None

    def get_windowed_pids_and_titles(self) -> Tuple[Set[int], Dict[int, List[str]]]:
        """Определяет PID процессов, имеющих открытые видимые окна на рабочем столе.

        Returns:
            Tuple[Set[int], Dict[int, List[str]]]: Множество PID с окнами и словарь {pid: [список заголовков окон]}.
        """
        windowed_pids: Set[int] = set()
        titles_map: Dict[int, List[str]] = {}

        if not self._user32:
            return windowed_pids, titles_map

        try:
            enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def _enum_window_callback(hwnd: Any, extra: Any) -> bool:
                try:
                    if self._user32.IsWindowVisible(hwnd):
                        length = self._user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            self._user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value.strip()
                            if title and title != 'Default IME' and title != 'MSCTFIME UI':
                                pid = ctypes.c_ulong()
                                self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                if pid.value:
                                    windowed_pids.add(pid.value)
                                    titles_map.setdefault(pid.value, []).append(title)
                except Exception:
                    pass
                return True

            cb = enum_windows_proc(_enum_window_callback)
            self._user32.EnumWindows(cb, 0)
        except Exception as ex:
            logger.debug(f'Ошибка EnumWindows при классификации процессов: {ex}')

        return windowed_pids, titles_map

    def _get_friendly_name(self, binary_name: str, window_titles: Optional[List[str]] = None) -> str:
        """Возвращает дружелюбное человекочитаемое имя приложения.

        Args:
            binary_name: Имя исполняемого файла (например, chrome.exe).
            window_titles: Список заголовков окон (опционально).

        Returns:
            str: Отображаемое имя (например, Google Chrome).
        """
        low = binary_name.lower()
        if low in KNOWN_APP_FRIENDLY_NAMES:
            return KNOWN_APP_FRIENDLY_NAMES[low]

        # Если есть понятный заголовок окна и бинарник неизвестен
        if window_titles and window_titles[0]:
            primary_title = window_titles[0]
            # Убираем дефисы и суффиксы окон
            if ' - ' in primary_title:
                parts = primary_title.split(' - ')
                # Часто в конце идет имя программы: "Документ - Microsoft Word"
                if len(parts) > 1 and len(parts[-1].strip()) > 2:
                    return parts[-1].strip()
            if len(primary_title) <= 30:
                return primary_title

        # Очистка имени исполняемого файла от расширения
        clean_name = binary_name
        if clean_name.lower().endswith('.exe'):
            clean_name = clean_name[:-4]
        # Превращаем camelCase / snake_case в красивый заголовок
        return clean_name.replace('_', ' ').replace('-', ' ').title()

    @staticmethod
    def _format_uptime(create_ts: float) -> str:
        """Форматирует время работы процесса в человекочитаемый вид."""
        if not create_ts or create_ts <= 0:
            return ''
        import time
        diff_sec = max(0, int(time.time() - create_ts))
        if diff_sec < 60:
            return f'{diff_sec} с'
        mins = diff_sec // 60
        if mins < 60:
            return f'{mins} мин'
        hours = mins // 60
        rem_mins = mins % 60
        if hours < 24:
            return f'{hours} ч {rem_mins} мин'
        days = hours // 24
        rem_hours = hours % 24
        return f'{days} д {rem_hours} ч'

    @staticmethod
    def _extract_launch_summary(binary_name: str, cmdline_str: Optional[str]) -> Optional[str]:
        """Извлекает ключевую суть запуска из командной строки (модуль, скрипт, PWA).

        Args:
            binary_name: Имя исполняемого файла.
            cmdline_str: Полная командная строка процесса.

        Returns:
            Optional[str]: Краткая суть запуска (например, 'apps.windows.api' или 'ChatGPT PWA').
        """
        if not cmdline_str:
            return None

        cmd = cmdline_str.strip()
        low_bin = binary_name.lower()

        # 1. Интерпретаторы Python
        if 'python' in low_bin or low_bin in ('py.exe', 'pythonw.exe'):
            parts = cmd.split()
            for idx, part in enumerate(parts):
                if part == '-m' and idx + 1 < len(parts):
                    return f'{parts[idx + 1]}'
                if part.lower().endswith('.py'):
                    # Извлекаем красивое имя скрипта или пару каталогов
                    normalized = part.replace('\\', '/').rstrip('"\'')
                    sub_parts = normalized.split('/')
                    if len(sub_parts) >= 2:
                        return f'{sub_parts[-2]}/{sub_parts[-1]}'
                    return sub_parts[-1]
                if part == '-c' and idx + 1 < len(parts):
                    code_snippet = ' '.join(parts[idx + 1:])[:35].replace('"', '')
                    return f'-c: {code_snippet}...'
            return 'python: script'

        # 2. Node.js
        if low_bin in ('node.exe', 'deno.exe', 'bun.exe'):
            parts = cmd.split()
            for part in parts[1:]:
                clean_p = part.replace('\\', '/').rstrip('"\'')
                if any(clean_p.lower().endswith(ext) for ext in ('.js', '.ts', '.mjs', '.cjs')):
                    return clean_p.split('/')[-1]
                if clean_p in ('vite', 'next', 'nest', 'webpack', 'tsc', 'npm', 'pnpm', 'yarn'):
                    return clean_p
            return 'node: app'

        # 3. PowerShell / CMD
        if low_bin in ('powershell.exe', 'pwsh.exe'):
            if '-file' in cmd.lower():
                parts = cmd.split()
                for idx, p in enumerate(parts):
                    if p.lower() == '-file' and idx + 1 < len(parts):
                        return parts[idx + 1].replace('\\', '/').split('/')[-1].rstrip('"\'')
            if '-command' in cmd.lower():
                return 'ps: command'
            return 'PowerShell'

        # 4. Chromium / PWA / Edge
        if low_bin in ('chrome.exe', 'msedge.exe', 'brave.exe'):
            low_cmd = cmd.lower()
            if 'chatgpt' in low_cmd or 'openai' in low_cmd:
                return 'ChatGPT (PWA App)'
            if '--app=' in low_cmd:
                idx = low_cmd.find('--app=') + 6
                target = cmd[idx:].split()[0].rstrip('"\'')
                return f'PWA: {target}'
            if '--app-id=' in low_cmd:
                idx = low_cmd.find('--app-id=') + 9
                app_id = cmd[idx:].split()[0].rstrip('"\'')[:12]
                return f'App: {app_id}'
            if '--type=renderer' in low_cmd:
                return 'Chromium Renderer'
            if '--type=gpu-process' in low_cmd:
                return 'GPU Process'
            if '--type=utility' in low_cmd:
                return 'Utility Service'
            if '--type=crashpad-handler' in low_cmd:
                return 'Crashpad Handler'

        # 5. Svchost Windows
        if low_bin == 'svchost.exe':
            if '-k ' in cmd:
                parts = cmd.split('-k ')
                if len(parts) > 1:
                    group = parts[1].split()[0]
                    return f'Служба: {group}'

        return None

    def classify_processes(self) -> CategorizedProcessReport:
        """Собирает и классифицирует все активные процессы Windows на Apps, Background и Windows.

        С поддержкой распознавания истинных родителей (ChatGPT.exe, PWA, Electron)
        и ключей запуска интерпретаторов (Python -m / script, Node, PowerShell).

        Returns:
            CategorizedProcessReport: Структурированный сводный отчет по категориям.
        """
        windowed_pids, titles_map = self.get_windowed_pids_and_titles()

        # 1. Первичный быстрый опрос процессов через psutil
        raw_proc_map: Dict[int, Dict[str, Any]] = {}
        for p in psutil.process_iter(['pid', 'ppid', 'name', 'username', 'cpu_percent', 'memory_info', 'num_threads', 'create_time', 'exe']):
            try:
                raw_proc_map[p.info['pid']] = p.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Быстрый индекс: PID -> Имя процесса
        pid_to_name: Dict[int, str] = {pid: info.get('name') or '' for pid, info in raw_proc_map.items()}

        raw_proc_items: List[ProcessItem] = []
        name_to_windowed: Dict[str, bool] = {}

        for pid, p_info in raw_proc_map.items():
            name = p_info.get('name') or 'unknown'
            low_name = name.lower()
            ppid = p_info.get('ppid')
            parent_name = pid_to_name.get(ppid) if ppid else None

            # Извлечение командной строки
            cmdline_str: Optional[str] = None
            try:
                proc_obj = psutil.Process(pid)
                raw_cmd = proc_obj.cmdline()
                if raw_cmd:
                    cmdline_str = ' '.join(raw_cmd)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

            mem_rss = (p_info.get('memory_info').rss if p_info.get('memory_info') else 0)
            mem_mb = round(mem_rss / (1024 * 1024), 1)
            cpu_p = float(p_info.get('cpu_percent') or 0.0)
            num_t = int(p_info.get('num_threads') or 1)
            create_ts = float(p_info.get('create_time') or 0.0)
            c_time = datetime.fromtimestamp(create_ts).strftime('%Y-%m-%d %H:%M:%S') if create_ts else ''
            uptime_str = self._format_uptime(create_ts)

            # Извлечение краткой сути команды/запуска
            launch_summary = self._extract_launch_summary(name, cmdline_str)

            # Вычисление истинного родителя и идентификатора хост-приложения
            real_parent: Optional[str] = parent_name
            is_pwa_or_electron = False

            # Анализ дерева ChatGPT и Chromium PWA / Electron
            parent_low = (parent_name or '').lower()
            cmd_low = (cmdline_str or '').lower()
            titles = titles_map.get(pid, [])
            titles_text = ' '.join(titles).lower()

            if low_name == 'chatgpt.exe' or 'chatgpt' in low_name:
                real_parent = 'ChatGPT.exe (OpenAI Desktop)'
                is_pwa_or_electron = True
                if not launch_summary:
                    launch_summary = 'ChatGPT Desktop (OpenAI)'
            elif low_name in ('chrome.exe', 'msedge.exe'):
                if 'chatgpt' in parent_low or 'chatgpt' in cmd_low or 'chatgpt' in titles_text:
                    real_parent = 'ChatGPT.exe (OpenAI Desktop / Chromium PWA)'
                    is_pwa_or_electron = True
                elif parent_low in ('code.exe', 'slack.exe', 'teams.exe', 'discord.exe', 'antigravity.exe'):
                    real_parent = f'{parent_name} (Electron Host)'
                    is_pwa_or_electron = True
                elif '--app=' in cmd_low or '--app-id=' in cmd_low:
                    is_pwa_or_electron = True
            elif 'python' in low_name:
                if parent_name:
                    real_parent = f'{parent_name} [PID: {ppid}]'

            item = ProcessItem(
                pid=pid,
                ppid=ppid,
                name=name,
                username=p_info.get('username'),
                cpu_percent=cpu_p,
                memory_mb=mem_mb,
                num_threads=num_t,
                create_time=c_time,
                uptime_str=uptime_str,
                exe_path=p_info.get('exe'),
                command_line=cmdline_str,
                launch_summary=launch_summary,
                parent_name=parent_name,
                real_parent=real_parent,
                has_window=(pid in windowed_pids),
                window_title=titles[0] if titles else None
            )
            raw_proc_items.append(item)

            if pid in windowed_pids:
                name_to_windowed[low_name] = True

        # Группировка процессов
        groups_by_category: Dict[str, Dict[str, List[ProcessItem]]] = {
            'app': {},
            'background': {},
            'windows': {},
        }

        for item in raw_proc_items:
            low_name = item.name.lower()
            exe_low = (item.exe_path or '').lower()
            cmd_low = (item.command_line or '').lower()
            parent_low = (item.parent_name or '').lower()

            # Логический ключ группировки:
            # Если процесс chrome.exe/msedge.exe порожден ChatGPT или является PWA ChatGPT,
            # мы группируем его под логическим приложением ChatGPT!
            group_key = item.name
            if 'chatgpt' in low_name or 'chatgpt' in parent_low or ('chatgpt' in cmd_low and low_name in ('chrome.exe', 'msedge.exe')):
                group_key = 'ChatGPT.exe'
                category = 'app'
            else:
                # Определение категории:
                is_app = (
                    (item.pid in windowed_pids) or
                    (low_name in name_to_windowed and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES) or
                    (low_name in KNOWN_APP_FRIENDLY_NAMES and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES)
                )

                if is_app:
                    category = 'app'
                elif low_name in WINDOWS_SYSTEM_PROCESS_NAMES or ('c:\\windows\\system32' in exe_low and not name_to_windowed.get(low_name)):
                    category = 'windows'
                else:
                    category = 'background'

            groups_by_category[category].setdefault(group_key, []).append(item)

        # Формирование ProcessGroupItem для каждой категории
        def _build_groups(cat_key: str, cat_name: str) -> List[ProcessGroupItem]:
            result_groups: List[ProcessGroupItem] = []
            for bin_name, items in groups_by_category[cat_key].items():
                total_cpu = round(sum(it.cpu_percent for it in items), 1)
                total_mem = round(sum(it.memory_mb for it in items), 1)
                total_thr = sum(it.num_threads for it in items)

                # Поиск PID главного/оконного процесса
                main_pid = items[0].pid
                for it in items:
                    if it.pid in windowed_pids:
                        main_pid = it.pid
                        break

                # Сбор всех заголовков окон группы
                all_titles: List[str] = []
                for it in items:
                    if it.pid in titles_map:
                        all_titles.extend(titles_map[it.pid])

                friendly = self._get_friendly_name(bin_name, all_titles)
                if bin_name.lower() == 'chatgpt.exe':
                    friendly = 'ChatGPT (OpenAI Desktop / Electron PWA)'

                has_win = len(all_titles) > 0 or any(it.pid in windowed_pids for it in items)

                # Определение общего пользователя и старейшего времени создания
                first_user = next((it.username for it in items if it.username), None)
                first_create = next((it.create_time for it in items if it.create_time), None)
                real_par = next((it.real_parent for it in items if it.real_parent and it.real_parent != it.name), None)
                grp_launch = next((it.launch_summary for it in items if it.launch_summary), None)
                is_pwa = any('chatgpt' in it.name.lower() or 'pwa' in (it.real_parent or '').lower() or 'pwa' in (it.launch_summary or '').lower() for it in items)

                # Сортировка подпроцессов: главный с окном или максимальный по RAM первым
                sorted_subprocs = sorted(items, key=lambda x: (1 if x.pid in windowed_pids else 0, x.memory_mb), reverse=True)

                result_groups.append(
                    ProcessGroupItem(
                        category=cat_key,
                        name=bin_name,
                        friendly_name=friendly,
                        instance_count=len(items),
                        total_cpu_percent=total_cpu,
                        total_memory_mb=total_mem,
                        total_threads=total_thr,
                        main_pid=main_pid,
                        has_visible_window=has_win,
                        window_titles=all_titles,
                        subprocesses=sorted_subprocs,
                        real_parent_name=real_par,
                        launch_summary=grp_launch,
                        username=first_user,
                        create_time=first_create,
                        is_pwa_or_electron=is_pwa,
                    )
                )

            # Сортировка групп: по суммарной памяти / CPU
            result_groups.sort(key=lambda g: (g.total_cpu_percent, g.total_memory_mb), reverse=True)
            return result_groups

        app_groups = _build_groups('app', 'Apps')
        bg_groups = _build_groups('background', 'Background processes')
        win_groups = _build_groups('windows', 'Windows processes')

        total_procs = len(raw_proc_items)
        total_mem_all = round(sum(it.memory_mb for it in raw_proc_items), 1)

        return CategorizedProcessReport(
            total_processes=total_procs,
            apps_count=len(app_groups),
            background_count=len(bg_groups),
            windows_count=len(win_groups),
            total_memory_used_mb=total_mem_all,
            apps=app_groups,
            background_processes=bg_groups,
            windows_processes=win_groups,
            timestamp=datetime.now().isoformat()
        )


__all__ = [
    'ProcessClassifier',
    'WINDOWS_SYSTEM_PROCESS_NAMES',
    'KNOWN_APP_FRIENDLY_NAMES',
]

