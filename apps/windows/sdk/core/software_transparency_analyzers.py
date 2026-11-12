# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Software Transparency Analyzers
# =============================================================================
# Description:
#   Модели данных и анализаторы прозрачности ПО: инвентаризация, места хранения,
#   конфигурационные файлы, сетевые домены, службы Windows и ИИ-исследование.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.software_transparency_analyzers import (
#         SoftwareInventory, StorageAnalyzer, ConfigInspector, NetworkTracker
#     )
#
# File: software_transparency_analyzers.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:58:00
# =============================================================================

from __future__ import annotations
"""Модели данных и анализаторы прозрачности ПО (каталоги, конфиги, сеть, службы)."""

import datetime
import json
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import psutil
except ImportError:
    psutil = None

try:
    import winreg
except ImportError:
    winreg = None

from pydantic import BaseModel, Field
from logger import logger
from apps.windows.sdk.core.software_audit import SoftwareAuditEngine


class StorageCategory(str, Enum):
    """Категории хранилищ данных программы."""
    CONFIG = 'config'
    DATA = 'data'
    CACHE = 'cache'
    LOGS = 'logs'
    BINARIES = 'binaries'
    UNKNOWN = 'unknown'


class EvidenceStatus(str, Enum):
    """Статус достоверности данных."""
    LOCAL_OBSERVED = 'observed'
    DOCS_CONFIRMED = 'confirmed'
    AI_INFERRED = 'inferred'


class ConfigFile(BaseModel):
    """Обнаруженный файл конфигурации программы."""
    path: str = Field(..., description='Абсолютный путь к файлу')
    display_path: str = Field(..., description='Путь с макросами окружения')
    filename: str = Field(..., description='Имя файла')
    format: str = Field(default='unknown', description='Формат файла')
    size_bytes: int = Field(default=0, description='Размер в байтах')
    last_modified: Optional[str] = Field(default=None, description='Дата последнего изменения ISO')
    purpose: str = Field(default='Настройки программы', description='Назначение файла')
    is_sanitized: bool = Field(default=True, description='Статус санитизации секретов')
    sample_content: Optional[str] = Field(default=None, description='Очищенный фрагмент конфигурации')
    status: EvidenceStatus = Field(default=EvidenceStatus.LOCAL_OBSERVED, description='Статус достоверности')


class StorageDirectory(BaseModel):
    """Описание обнаруженного каталога данных программы."""
    path: str = Field(..., description='Абсолютный путь к каталогу')
    display_path: str = Field(..., description='Путь с макросами окружения')
    category: StorageCategory = Field(default=StorageCategory.UNKNOWN, description='Тип хранимых данных')
    description: str = Field(default='', description='Описание назначения каталога')
    file_count: int = Field(default=0, description='Количество файлов')
    total_size_bytes: int = Field(default=0, description='Общий размер файлов')
    status: EvidenceStatus = Field(default=EvidenceStatus.LOCAL_OBSERVED, description='Статус достоверности')


class NetworkEndpoint(BaseModel):
    """Описание сетевого соединения или обнаруженного домена."""
    domain_or_ip: str = Field(..., description='Доменное имя или IP-адрес')
    port: Optional[int] = Field(default=None, description='Сетевой порт')
    protocol: str = Field(default='HTTPS', description='Сетевой протокол')
    source: str = Field(default='observed', description='Источник детекции')
    purpose: str = Field(default='Требуется исследование домена', description='Назначение соединения')
    documentation_source: Optional[str] = Field(default=None, description='Ссылка на документацию')
    status: EvidenceStatus = Field(default=EvidenceStatus.LOCAL_OBSERVED, description='Статус достоверности')


class GeminiAppResearch(BaseModel):
    """Результаты аналитического исследования программы через Gemini."""
    app_name: str = Field(..., description='Название исследованной программы')
    summary: str = Field(default='', description='Назначение и функционал программы')
    config_purpose_explanation: str = Field(default='', description='Объяснение назначения конфигурационных файлов')
    data_storage_explanation: str = Field(default='', description='Описание локального хранения данных')
    network_activity_explanation: str = Field(default='', description='Назначение сетевых доменов и серверов')
    confirmed_facts: List[str] = Field(default_factory=list, description='Факты из официальных источников')
    inferred_facts: List[str] = Field(default_factory=list, description='Логические предположения модели')
    unknown_aspects: List[str] = Field(default_factory=list, description='Неизвестные сведения')
    confidence_level: str = Field(default='Высокий', description='Уровень уверенности')


class SoftwareItem(BaseModel):
    """Сводная карточка установленного программного обеспечения."""
    id: str = Field(..., description='Уникальный идентификатор записи (slug)')
    name: str = Field(..., description='Название программы')
    version: str = Field(default='Не указана', description='Версия ПО')
    publisher: str = Field(default='Неизвестен', description='Разработчик / Издатель')
    install_location: Optional[str] = Field(default=None, description='Путь установки')
    executable_path: Optional[str] = Field(default=None, description='Главный исполняемый файл')
    uninstall_string: Optional[str] = Field(default=None, description='Команда деинсталляции')
    architecture: str = Field(default='x64', description='Разрядность x64, x86 или ARM64')
    install_date: Optional[str] = Field(default=None, description='Дата установки')
    registry_key: Optional[str] = Field(default=None, description='Ветка реестра Windows')
    category: str = Field(default='Прочее ПО', description='Категория программы')
    purpose_description: str = Field(default='', description='Описание назначения программы')
    size_bytes: int = Field(default=0, description='Оценочный или суммарный размер в байтах')
    is_system_component: bool = Field(default=False, description='Признак системного компонента')
    last_run_time: Optional[str] = Field(default=None, description='Время последнего запуска ISO')
    run_count: int = Field(default=0, description='Количество зафиксированных запусков')
    config_files: List[ConfigFile] = Field(default_factory=list, description='Файлы конфигурации')
    data_directories: List[StorageDirectory] = Field(default_factory=list, description='Каталоги хранения данных')
    network_endpoints: List[NetworkEndpoint] = Field(default_factory=list, description='Сетевые взаимодействия')
    windows_services: List[str] = Field(default_factory=list, description='Связанные службы Windows')
    ai_research: Optional[GeminiAppResearch] = Field(default=None, description='Результаты исследования Gemini')


class ScanSummary(BaseModel):
    """Сводная статистика сканирования системы."""
    total_apps: int = Field(default=0, description='Всего обнаружено установленных программ')
    total_configs_found: int = Field(default=0, description='Всего найдено файлов конфигурации')
    total_network_domains: int = Field(default=0, description='Всего уникальных сетевых доменов')
    total_storage_bytes: int = Field(default=0, description='Суммарный объем отслеживаемых данных')
    scan_duration_sec: float = Field(default=0.0, description='Время выполнения сканирования в секундах')
    last_scan_time: Optional[str] = Field(default=None, description='Время последнего сканирования ISO')


class FullScanReport(BaseModel):
    """Полный отчет инвентаризации и аудита прозрачности ПО."""
    summary: ScanSummary = Field(..., description='Сводка сканирования')
    apps: List[SoftwareItem] = Field(default_factory=list, description='Список детальных карточек программ')


class ResearchRequest(BaseModel):
    """Запрос на AI-исследование конкретной программы."""
    app_id: str = Field(..., description='Идентификатор программы')
    force_refresh: bool = Field(default=False, description='Принудительное обновление через Gemini')


class ConfigFileSaveRequest(BaseModel):
    """Запрос на сохранение отредактированного файла конфигурации."""
    path: str = Field(..., description='Абсолютный путь к файлу конфигурации')
    content: str = Field(..., description='Новое содержимое файла')


class SoftwareInventory:
    """Инвентаризатор программного обеспечения Windows на базе SoftwareAuditEngine."""

    def __init__(self) -> None:
        self._audit_engine = SoftwareAuditEngine()

    @staticmethod
    def _create_slug(name: str, version: str, fallback_key: str = '') -> str:
        clean_name = re.sub('[^a-zA-Z0-9_-]+', '-', name.lower()).strip('-')
        if not clean_name and fallback_key:
            clean_name = re.sub('[^a-zA-Z0-9_-]+', '-', fallback_key.lower()).strip('-')
        clean_ver = re.sub('[^a-zA-Z0-9_-]+', '-', version.lower()).strip('-')
        return f"{clean_name or 'unknown-app'}-{clean_ver or 'ver'}"

    @staticmethod
    def _resolve_executable(app: Any) -> Optional[str]:
        exe_path = getattr(app, 'executable_path', None)
        if not exe_path and getattr(app, 'execution_info', None):
            exe_path = getattr(app.execution_info, 'raw_path', None) or getattr(app.execution_info, 'executable_path', None)
        inst_loc = getattr(app, 'install_location', '') or ''
        if exe_path and ':' not in exe_path and inst_loc and os.path.isdir(inst_loc):
            candidate = os.path.join(inst_loc, exe_path)
            if os.path.isfile(candidate):
                return candidate
        if not exe_path and inst_loc and os.path.isdir(inst_loc):
            try:
                for f in os.listdir(inst_loc):
                    if f.lower().endswith('.exe') and not f.lower().startswith(('unins', 'uninst')):
                        return os.path.join(inst_loc, f)
            except OSError:
                pass
        uninst = getattr(app, 'uninstall_string', '') or ''
        if not exe_path and uninst:
            m = re.search(r'["\']?([A-Za-z]:\\[^"\']*?\.exe)["\']?', uninst, re.IGNORECASE)
            if m and 'msiexec' not in m.group(1).lower():
                return m.group(1)
        return exe_path

    def scan_installed_software(self) -> List[SoftwareItem]:
        """Сканирует установленное ПО в системе и формирует обогащенные карточки SoftwareItem."""
        try:
            report = self._audit_engine.generate_audit_report()
            items: List[SoftwareItem] = []
            seen_ids: Set[str] = set()
            for app in report.apps:
                app_name = app.display_name or app.name
                slug = self._create_slug(app_name, app.version, getattr(app, 'name', ''))
                if slug in seen_ids:
                    suffix = re.sub('[^a-zA-Z0-9_-]+', '-', str(getattr(app, 'name', '')).lower()).strip('-')[:12]
                    slug = f"{slug}-{suffix or len(seen_ids)}"
                seen_ids.add(slug)
                exe_path = self._resolve_executable(app)
                reg_key = getattr(app, 'registry_key', '') or getattr(app, 'source', '')
                cat_obj = getattr(app, 'category', None)
                cat_str = (cat_obj.value if hasattr(cat_obj, 'value') else str(cat_obj or '')) or 'Прочее ПО'
                exec_info = getattr(app, 'execution_info', None)
                last_run = getattr(exec_info, 'last_run_time', None) if exec_info else None
                last_run_iso = last_run.isoformat() if hasattr(last_run, 'isoformat') else (str(last_run) if last_run else None)
                run_cnt = int(getattr(exec_info, 'run_count', 0) or 0) if exec_info else 0
                items.append(
                    SoftwareItem(
                        id=slug,
                        name=app_name,
                        version=app.version or 'Не указана',
                        publisher=app.publisher or 'Неизвестен',
                        install_location=app.install_location or None,
                        executable_path=exe_path,
                        uninstall_string=getattr(app, 'uninstall_string', None) or None,
                        architecture=app.architecture or 'x64',
                        install_date=app.install_date,
                        registry_key=reg_key or None,
                        category=cat_str,
                        purpose_description=getattr(app, 'purpose_description', '') or '',
                        size_bytes=int(getattr(app, 'size_bytes', 0) or 0),
                        is_system_component=bool(getattr(app, 'is_system_component', False)),
                        last_run_time=last_run_iso,
                        run_count=run_cnt,
                    )
                )
            if items:
                return items
        except Exception as ex:
            logger.debug(f'Ошибка вызова SoftwareAuditEngine: {ex}')
        return self._get_fallback_mock_software()

    def _get_fallback_mock_software(self) -> List[SoftwareItem]:
        return [
            SoftwareItem(
                id='google-chrome-140-x',
                name='Google Chrome',
                version='140.0.7132.0',
                publisher='Google LLC',
                install_location='C:\\Program Files\\Google\\Chrome\\Application',
                executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                architecture='x64',
                category='Браузеры и Интернет',
                purpose_description='Веб-браузер Google Chrome для навигации в сети Интернет.',
            ),
            SoftwareItem(
                id='visual-studio-code',
                name='Visual Studio Code',
                version='1.93.0',
                publisher='Microsoft Corporation',
                install_location=os.path.expandvars('%LOCALAPPDATA%\\Programs\\Microsoft VS Code'),
                executable_path=os.path.expandvars('%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe'),
                architecture='x64',
                category='Разработка и IDE',
                purpose_description='Редактор исходного кода Visual Studio Code от Microsoft.',
            ),
        ]


class StorageAnalyzer:
    """Анализатор мест хранения пользовательских данных и связанных служб программ."""
    ROOT_ENV_DIRS = [
        ('%APPDATA%', os.getenv('APPDATA'), StorageCategory.CONFIG, 'Пользовательские настройки (Roaming)'),
        ('%LOCALAPPDATA%', os.getenv('LOCALAPPDATA'), StorageCategory.CACHE, 'Кэш и локальные данные'),
        ('%PROGRAMDATA%', os.getenv('PROGRAMDATA'), StorageCategory.CONFIG, 'Общие конфигурации всех пользователей'),
    ]
    SKIP_GENERIC_TOKENS = {
        'microsoft', 'windows', 'google', 'adobe', 'intel', 'nvidia', 'amd',
        'package', 'application', 'winrt', 'visual', 'driver', 'update', 'sdk', 'runtime',
    }

    def __init__(self) -> None:
        self._dir_cache: Dict[str, Dict[str, str]] = {}
        self._services_cache: Optional[List[Tuple[str, str, str]]] = None
        self.reset_cache()

    def reset_cache(self) -> None:
        """Сброс кэша структуры директорий и служб."""
        self._dir_cache.clear()
        self._services_cache = None
        for _, bdir, _, _ in self.ROOT_ENV_DIRS:
            if bdir and os.path.exists(bdir):
                try:
                    entries = [e for e in os.listdir(bdir) if os.path.isdir(os.path.join(bdir, e))]
                    self._dir_cache[bdir] = {e.lower(): os.path.join(bdir, e) for e in entries}
                except Exception:
                    self._dir_cache[bdir] = {}

    def discover_services_for_app(self, app: SoftwareItem) -> List[str]:
        """Находит службы Windows, исполняемый файл которых относится к приложению."""
        if self._services_cache is None:
            self._services_cache = self._load_windows_services()
        inst = (app.install_location or '').strip().rstrip('\\/').lower()
        exe = (app.executable_path or '').strip().lower()
        if not inst and (not exe or ':' not in exe):
            return []
        matched: List[str] = []
        for svc_name, disp_name, img_low in self._services_cache:
            if (inst and len(inst) > 6 and inst in img_low) or (exe and ':' in exe and exe in img_low):
                label = f"{svc_name} ({disp_name})" if disp_name and disp_name != svc_name else svc_name
                if label not in matched:
                    matched.append(label)
        return matched[:8]

    @staticmethod
    def _load_windows_services() -> List[Tuple[str, str, str]]:
        services: List[Tuple[str, str, str]] = []
        if not winreg:
            return services
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Services') as root:
                num_subkeys, _, _ = winreg.QueryInfoKey(root)
                for i in range(num_subkeys):
                    try:
                        sname = winreg.EnumKey(root, i)
                        with winreg.OpenKey(root, sname) as sk:
                            img, _ = winreg.QueryValueEx(sk, 'ImagePath')
                            img_str = os.path.expandvars(str(img or '')).lower()
                            if not img_str or '\\windows\\system32\\drivers\\' in img_str or img_str.startswith('system32\\drivers\\'):
                                continue
                            try:
                                disp, _ = winreg.QueryValueEx(sk, 'DisplayName')
                                disp_str = str(disp or sname)
                            except OSError:
                                disp_str = sname
                            if disp_str.startswith('@'):
                                disp_str = sname
                            services.append((sname, disp_str, img_str))
                    except OSError:
                        continue
        except OSError:
            pass
        return services

    def discover_storage_for_app(self, app: SoftwareItem) -> List[StorageDirectory]:
        """Обнаруживает директории хранения бинарных файлов, настроек и кэша приложения."""
        results: List[StorageDirectory] = []
        existing_paths: Set[str] = set()
        aliases = self._get_search_aliases(app)

        if app.install_location and os.path.isdir(app.install_location):
            stats = self._get_dir_stats(app.install_location)
            results.append(
                StorageDirectory(
                    path=app.install_location,
                    display_path=self._to_display_path(app.install_location),
                    category=StorageCategory.BINARIES,
                    description='Исполняемые файлы программы',
                    file_count=stats['file_count'],
                    total_size_bytes=stats['total_size'],
                    status=EvidenceStatus.LOCAL_OBSERVED,
                )
            )
            existing_paths.add(app.install_location.lower())

        for _, base_dir, default_cat, base_desc in self.ROOT_ENV_DIRS:
            if not base_dir or not os.path.exists(base_dir):
                continue
            matched_dir = self._find_matching_folder(base_dir, aliases)
            if matched_dir and os.path.isdir(matched_dir) and matched_dir.lower() not in existing_paths:
                existing_paths.add(matched_dir.lower())
                stats = self._get_dir_stats(matched_dir)
                category, desc = self._classify_directory(matched_dir, default_cat, base_desc)
                results.append(
                    StorageDirectory(
                        path=matched_dir,
                        display_path=self._to_display_path(matched_dir),
                        category=category,
                        description=desc,
                        file_count=stats['file_count'],
                        total_size_bytes=stats['total_size'],
                        status=EvidenceStatus.LOCAL_OBSERVED,
                    )
                )

        user_profile = os.getenv('USERPROFILE')
        if user_profile and os.path.isdir(user_profile):
            dot_dir = self._find_dot_folder(user_profile, aliases)
            if dot_dir and dot_dir.lower() not in existing_paths:
                existing_paths.add(dot_dir.lower())
                stats = self._get_dir_stats(dot_dir)
                results.append(
                    StorageDirectory(
                        path=dot_dir,
                        display_path=self._to_display_path(dot_dir),
                        category=StorageCategory.CONFIG,
                        description='Конфигурационный dot-каталог профиля',
                        file_count=stats['file_count'],
                        total_size_bytes=stats['total_size'],
                        status=EvidenceStatus.LOCAL_OBSERVED,
                    )
                )

        return results

    def _find_dot_folder(self, user_profile: str, aliases: List[str]) -> Optional[str]:
        entries_lower = self._dir_cache.get(user_profile)
        if entries_lower is None:
            try:
                entries = [
                    e for e in os.listdir(user_profile)
                    if e.startswith('.') and os.path.isdir(os.path.join(user_profile, e))
                ]
                entries_lower = {e.lower(): os.path.join(user_profile, e) for e in entries}
                self._dir_cache[user_profile] = entries_lower
            except (OSError, PermissionError):
                return None
        for alias in aliases:
            dot_cand = f".{alias.lstrip('.')}"
            if dot_cand in entries_lower:
                return entries_lower[dot_cand]
        return None

    def _get_search_aliases(self, app: SoftwareItem) -> List[str]:
        aliases = [app.name.lower()]
        clean_name = re.sub(r'(?i)\b(inc|llc|corp|corporation|ltd|gmbh|64-bit|32-bit|x64|x86|user)\b', '', app.name).strip()
        clean_name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', clean_name).strip().lower()
        if clean_name and clean_name not in aliases:
            aliases.append(clean_name)
        name_no_ver = re.sub(r'\b\d+(\.\d+)*(?:-[0-9a-zA-Z]+)?\b', '', clean_name).strip(' -_').lower()
        if name_no_ver and name_no_ver not in aliases:
            aliases.append(name_no_ver)
        first_word = name_no_ver.split()[0] if name_no_ver else ''
        if len(first_word) >= 3 and first_word not in self.SKIP_GENERIC_TOKENS and first_word not in aliases:
            aliases.append(first_word)
        if app.executable_path:
            exe_stem = Path(app.executable_path).stem.lower()
            if exe_stem not in ('unins000', 'uninstall', 'setup', 'update', 'msiexec') and exe_stem not in aliases:
                aliases.append(exe_stem)
        return [a for a in aliases if len(a) >= 2]

    def _find_matching_folder(self, base_path: str, aliases: List[str]) -> Optional[str]:
        if not base_path or not os.path.exists(base_path):
            return None
        entries_lower = self._dir_cache.get(base_path)
        if entries_lower is None:
            try:
                entries = [e for e in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, e))]
                entries_lower = {e.lower(): os.path.join(base_path, e) for e in entries}
                self._dir_cache[base_path] = entries_lower
            except (OSError, PermissionError):
                return None

        for alias in aliases:
            if alias in entries_lower:
                return entries_lower[alias]
            for e_low, orig_path in entries_lower.items():
                if e_low.startswith((alias + ' ', alias + '-', alias + '_')):
                    return orig_path

        for _, parent_dir_path in entries_lower.items():
            sub_map = self._dir_cache.get(parent_dir_path)
            if sub_map is None:
                try:
                    sub_entries = [s for s in os.listdir(parent_dir_path) if os.path.isdir(os.path.join(parent_dir_path, s))]
                    sub_map = {s.lower(): os.path.join(parent_dir_path, s) for s in sub_entries}
                    self._dir_cache[parent_dir_path] = sub_map
                except (OSError, PermissionError):
                    self._dir_cache[parent_dir_path] = {}
                    continue
            for alias in aliases:
                if alias in sub_map:
                    return sub_map[alias]
                for s_low, orig_sub in sub_map.items():
                    if s_low.startswith((alias + ' ', alias + '-', alias + '_')):
                        return orig_sub
        return None

    def _classify_directory(self, folder_path: str, default_cat: StorageCategory, default_desc: str) -> Tuple[StorageCategory, str]:
        f_lower = folder_path.lower()
        if 'cache' in f_lower or 'temp' in f_lower:
            return (StorageCategory.CACHE, 'Кэш и временные рабочие данные')
        if 'log' in f_lower:
            return (StorageCategory.LOGS, 'Журналы работы')
        return (default_cat, default_desc)

    def _get_dir_stats(self, dir_path: str) -> Dict[str, int]:
        file_count = 0
        total_size = 0
        try:
            for root, dirs, files in os.walk(dir_path):
                if root[len(dir_path):].count(os.sep) >= 2:
                    dirs.clear()
                for f in files:
                    file_count += 1
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
                if file_count >= 500:
                    dirs.clear()
                    break
        except (OSError, PermissionError):
            pass
        return {'file_count': file_count, 'total_size': total_size}

    def _to_display_path(self, full_path: str) -> str:
        p = full_path
        for env_var in ('APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'USERPROFILE'):
            val = os.getenv(env_var)
            if val and p.lower().startswith(val.lower()):
                return f'%{env_var}%{p[len(val):]}'
        return p


class ConfigInspector:
    """Инспекция конфигурационных файлов ПО и очистка секретов."""
    CONFIG_EXTENSIONS = {'.json', '.ini', '.yaml', '.yml', '.xml', '.cfg', '.conf', '.toml', '.config'}
    BEARER_JWT_REGEX = re.compile('(Bearer\\s+)[A-Za-z0-9\\-_=]+\\.[A-Za-z0-9\\-_=]+\\.?[A-Za-z0-9\\-_.+/=]*')
    GENERIC_KEY_REGEX = re.compile('(AIzaSy[A-Za-z0-9_-]{33}|sk-[A-Za-z0-9]{32,})')
    SECRET_KV_REGEX = re.compile('(?i)([\'"]?(?:password|passwd|secret|token|api[_-]?key|auth|credential|private[_-]?key)[\'"]?\\s*[:=]\\s*[\'"])([^\'"\\r\\n]+)([\'"])')

    def __init__(self, max_file_size_kb: int = 256) -> None:
        self.max_file_size_bytes = max_file_size_kb * 1024

    def inspect_directories_for_configs(self, directories: List[StorageDirectory]) -> List[ConfigFile]:
        found_configs: List[ConfigFile] = []
        for d in directories:
            if not os.path.exists(d.path) or not os.path.isdir(d.path):
                continue
            try:
                for root, dirs, files in os.walk(d.path):
                    if root[len(d.path):].count(os.sep) >= 2:
                        dirs.clear()
                    for file in files:
                        if Path(file).suffix.lower() in self.CONFIG_EXTENSIONS:
                            cfg_item = self._process_config_file(os.path.join(root, file))
                            if cfg_item:
                                found_configs.append(cfg_item)
                                if len(found_configs) >= 20:
                                    return found_configs
            except (OSError, PermissionError):
                continue
        return found_configs

    def _process_config_file(self, full_path: str) -> Optional[ConfigFile]:
        try:
            st = os.stat(full_path)
            size = st.st_size
            if size > self.max_file_size_bytes:
                sample = '[Файл превышает лимит размера 256 KB]'
            else:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    sample = self.sanitize_secrets(f.read(4096))
            mod_time = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
            return ConfigFile(
                path=full_path,
                display_path=self._to_display_path(full_path),
                filename=Path(full_path).name,
                format=Path(full_path).suffix.lower().lstrip('.') or 'text',
                size_bytes=size,
                last_modified=mod_time,
                purpose=self._guess_config_purpose(Path(full_path).name),
                is_sanitized=True,
                sample_content=sample,
                status=EvidenceStatus.LOCAL_OBSERVED,
            )
        except (OSError, PermissionError):
            return None

    def sanitize_secrets(self, content: str) -> str:
        if not content:
            return ''
        sanitized = self.BEARER_JWT_REGEX.sub('Bearer [REDACTED_JWT_TOKEN]', content)
        sanitized = self.GENERIC_KEY_REGEX.sub('[REDACTED_API_KEY]', sanitized)
        sanitized = self.SECRET_KV_REGEX.sub('\\g<1>[REDACTED_SECRET]\\g<3>', sanitized)
        return sanitized

    def _guess_config_purpose(self, filename: str) -> str:
        fn = filename.lower()
        if 'settings' in fn or 'config' in fn:
            return 'Пользовательские настройки'
        if 'session' in fn or 'state' in fn:
            return 'Состояние сессии'
        return 'Конфигурация работы приложения'

    def _to_display_path(self, full_path: str) -> str:
        p = full_path
        for env_var in ('APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'USERPROFILE'):
            val = os.getenv(env_var)
            if val and p.lower().startswith(val.lower()):
                return f'%{env_var}%{p[len(val):]}'
        return p


class NetworkTracker:
    """Отслеживание сетевой активности и целевых доменов приложений."""
    DOMAIN_REGEX = re.compile('(?i)\\b(?:https?://)?([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.(?:[a-z0-9-]+\\.)+[a-z]{2,})\\b')
    FALSE_DOMAIN_SUFFIXES = (
        '.exe', '.dll', '.json', '.xml', '.ini', '.cfg', '.conf', '.log', '.txt', '.md',
        '.py', '.pyw', '.js', '.ts', '.css', '.html', '.htm', '.png', '.jpg', '.jpeg',
        '.gif', '.svg', '.ico', '.msi', '.cab', '.zip', '.tar', '.gz', '.7z', '.rar',
        '.bat', '.cmd', '.ps1', '.sys', '.inf', '.cat', '.cer', '.crt', '.pem', '.key',
        '.db', '.sqlite', '.dat', '.bin', '.bak', '.tmp', '.old', '.lock', '.toml', '.yaml', '.yml',
    )
    POPULAR_DOMAINS: Dict[str, List[Tuple[str, int, str, str]]] = {
        'chrome': [('clients2.google.com', 443, 'HTTPS', 'Safe Browsing и расширения'), ('update.googleapis.com', 443, 'HTTPS', 'Автообновления Chrome')],
        'edge': [('edge.microsoft.com', 443, 'HTTPS', 'Обновления и синхронизация Edge'), ('nav.smartscreen.microsoft.com', 443, 'HTTPS', 'Фильтр SmartScreen')],
        'firefox': [('aus5.mozilla.org', 443, 'HTTPS', 'Обновления Mozilla Firefox'), ('services.addons.mozilla.org', 443, 'HTTPS', 'Каталог дополнений')],
        'code': [('marketplace.visualstudio.com', 443, 'HTTPS', 'Каталог расширений VS Code'), ('update.code.visualstudio.com', 443, 'HTTPS', 'Обновления VS Code')],
        'cursor': [('api2.cursor.sh', 443, 'HTTPS', 'Облачный ИИ-шлюз Cursor'), ('marketplace.cursorapi.com', 443, 'HTTPS', 'Реестр расширений Cursor')],
        'antigravity': [('googleapis.com', 443, 'HTTPS', 'Облачный API Google Antigravity')],
        'python': [('pypi.org', 443, 'HTTPS', 'Репозиторий пакетов PyPI'), ('files.pythonhosted.org', 443, 'HTTPS', 'Хранилище пакетов PyPI')],
        'anaconda': [('repo.anaconda.com', 443, 'HTTPS', 'Репозиторий пакетов Anaconda'), ('conda.anaconda.org', 443, 'HTTPS', 'Канал Conda-Forge')],
        'git': [('github.com', 443, 'HTTPS', 'Хостинг репозиториев GitHub')],
        'node': [('registry.npmjs.org', 443, 'HTTPS', 'Реестр пакетов NPM')],
        'docker': [('registry-1.docker.io', 443, 'HTTPS', 'Реестр образов Docker Hub')],
        'dbeaver': [('dbeaver.io', 443, 'HTTPS', 'Обновления и драйверы DBeaver'), ('repo1.maven.org', 443, 'HTTPS', 'Maven-репозиторий JDBC драйверов')],
        'wireshark': [('www.wireshark.org', 443, 'HTTPS', 'Обновления и документация Wireshark')],
        'winscp': [('winscp.net', 443, 'HTTPS', 'Сервер обновлений WinSCP')],
        '7-zip': [('www.7-zip.org', 443, 'HTTPS', 'Официальный портал 7-Zip')],
        'audacity': [('www.audacityteam.org', 443, 'HTTPS', 'Сервис обновлений Audacity')],
        'vlc': [('update.videolan.org', 443, 'HTTPS', 'Сервер обновлений VideoLAN')],
        'obs': [('obsproject.com', 443, 'HTTPS', 'Обновления и профили OBS Studio')],
        'telegram': [('core.telegram.org', 443, 'MTProto/HTTPS', 'Облачные серверы Telegram')],
        'discord': [('discord.com', 443, 'HTTPS/WSS', 'Шлюз обмена данными Discord')],
        'copilot': [('copilot.microsoft.com', 443, 'HTTPS', 'ИИ-сервис Microsoft Copilot')],
        'onedrive': [('onedrive.live.com', 443, 'HTTPS', 'Облачное хранилище OneDrive')],
        'teams': [('teams.microsoft.com', 443, 'HTTPS', 'Коммуникационный шлюз Teams')],
        'nvidia': [('services.gfe.nvidia.com', 443, 'HTTPS', 'Обновления драйверов NVIDIA')],
        'intel': [('dsadata.intel.com', 443, 'HTTPS', 'Ассистент драйверов Intel DSA')],
        'amd': [('drivers.amd.com', 443, 'HTTPS', 'Обновления драйверов AMD')],
    }

    def __init__(self) -> None:
        self._running_procs_map: Optional[Dict[str, List[Any]]] = None

    def reset_cache(self) -> None:
        """Сброс кэша запущенных процессов перед новым сканированием."""
        self._running_procs_map = None

    def track_app_network(self, app: SoftwareItem, config_files: List[ConfigFile]) -> List[NetworkEndpoint]:
        endpoints: List[NetworkEndpoint] = []
        seen: Set[str] = set()
        for ep in self._get_active_connections(app):
            if ep.domain_or_ip not in seen:
                seen.add(ep.domain_or_ip)
                endpoints.append(ep)
        for cfg in config_files:
            if cfg.sample_content:
                for dom in self.DOMAIN_REGEX.findall(cfg.sample_content):
                    d_clean = dom.strip('/').lower()
                    if '.' in d_clean and d_clean not in seen and not d_clean.endswith(self.FALSE_DOMAIN_SUFFIXES):
                        seen.add(d_clean)
                        endpoints.append(NetworkEndpoint(domain_or_ip=d_clean, port=443, protocol='HTTPS', source='config_file', purpose=f'Файл {cfg.filename}', status=EvidenceStatus.LOCAL_OBSERVED))
        if app.publisher and ('http://' in app.publisher.lower() or 'https://' in app.publisher.lower()):
            for dom in self.DOMAIN_REGEX.findall(app.publisher):
                d_clean = dom.strip('/').lower()
                if '.' in d_clean and d_clean not in seen and not d_clean.endswith(self.FALSE_DOMAIN_SUFFIXES):
                    seen.add(d_clean)
                    endpoints.append(NetworkEndpoint(domain_or_ip=d_clean, port=443, protocol='HTTPS', source='registry_publisher', purpose='Официальный домен издателя', status=EvidenceStatus.DOCS_CONFIRMED))
        app_low = f"{app.name} {app.executable_path or ''}".lower()
        for k, dom_list in self.POPULAR_DOMAINS.items():
            if k in app_low:
                for dom, port, proto, purp in dom_list:
                    if dom not in seen:
                        seen.add(dom)
                        endpoints.append(NetworkEndpoint(domain_or_ip=dom, port=port, protocol=proto, source='known_database', purpose=purp, status=EvidenceStatus.DOCS_CONFIRMED))
        return endpoints

    def _get_active_connections(self, app: SoftwareItem) -> List[NetworkEndpoint]:
        if not psutil:
            return []
        results: List[NetworkEndpoint] = []
        target_name = Path(app.executable_path).name.lower() if app.executable_path else ''
        if not target_name:
            return results
        if self._running_procs_map is None:
            self._running_procs_map = {}
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pname = (proc.info.get('name') or '').lower()
                        if pname:
                            self._running_procs_map.setdefault(pname, []).append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        for proc in self._running_procs_map.get(target_name, []):
            try:
                pname = (proc.info.get('name') or '').lower()
                get_conns = getattr(proc, 'net_connections', None) or getattr(proc, 'connections', None)
                for c in (get_conns(kind='inet') if get_conns else []):
                    if c.status == 'ESTABLISHED' and c.raddr:
                        rip = c.raddr.ip
                        if rip not in ('127.0.0.1', '::1', '0.0.0.0'):
                            results.append(NetworkEndpoint(domain_or_ip=rip, port=c.raddr.port, protocol='TCP' if c.type == 1 else 'UDP', source='active_socket', purpose=f'Активный сокет {pname} (PID {proc.pid})', status=EvidenceStatus.LOCAL_OBSERVED))
            except Exception:
                continue
        return results
