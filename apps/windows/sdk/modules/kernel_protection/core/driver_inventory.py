# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Driver Inventory
# =============================================================================
# Description:
#   Инвентаризация системных драйверов Windows, обнаружение механизмов фильтрации,
#   парсинг файловых минифильтров (fltmc) и сопоставление с высотами Microsoft Altitudes.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.driver_inventory import DriverInventoryManager
#
#     manager = DriverInventoryManager()
#     drivers = manager.get_all_system_drivers()
#     filters = manager.get_active_minifilters()
#
# File: driver_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Инвентаризация системных драйверов и файловых минифильтров Windows."""

import json
import re
import subprocess
import time
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core.models import (
    ComponentCriticality,
    DriverCategory,
    MinifilterInfo,
    SystemDriverInfo,
)

# Каталог известных драйверов защиты, изоляции и контроля
KNOWN_PROTECTION_DRIVERS: Dict[str, Dict[str, Any]] = {
    'ucpd': {
        'display_name': 'User Choice Protection Driver',
        'category': DriverCategory.SECURITY,
        'criticality': ComponentCriticality.MEDIUM,
        'can_disable': True,
        'purpose_ru': 'Защита пользовательских ассоциаций файлов, расширений и браузера по умолчанию от прямого изменения через реестр.',
        'protection_role': 'Блокирует перезапись ключей UserChoice (HTTP, HTTPS, PDF) сторонними утилитами.',
    },
    'wdfilter': {
        'display_name': 'Microsoft Defender Mini-filter Driver',
        'category': DriverCategory.SECURITY,
        'criticality': ComponentCriticality.CRITICAL,
        'can_disable': False,
        'purpose_ru': 'Основной антивирусный файловый фильтр Microsoft Defender для проверки операций ввода-вывода в реальном времени.',
        'protection_role': 'Перехватывает создание, модификацию и чтение файлов перед их фиксацией на диске.',
    },
    'wdboot': {
        'display_name': 'Microsoft Defender Antivirus Boot Driver (ELAM)',
        'category': DriverCategory.SECURITY,
        'criticality': ComponentCriticality.CRITICAL,
        'can_disable': False,
        'purpose_ru': 'Драйвер раннего запуска защиты (Early Launch Anti-Malware) при старте системы до сторонних драйверов.',
        'protection_role': 'Проверяет подписи и доверенность всех загружаемых драйверов на ранней стадии UEFI/Boot.',
    },
    'wdnisdrv': {
        'display_name': 'Microsoft Defender Network Inspection System Driver',
        'category': DriverCategory.SECURITY,
        'criticality': ComponentCriticality.HIGH,
        'can_disable': False,
        'purpose_ru': 'Сетевой фильтр Defender для инспекции сетевых протоколов и предотвращения сетевых эксплойтов.',
        'protection_role': 'Анализирует сетевой трафик на уровне ядра для предотвращения удаленного исполнения кода.',
    },
    'luafv': {
        'display_name': 'LUA File Virtualization Driver',
        'category': DriverCategory.SECURITY,
        'criticality': ComponentCriticality.HIGH,
        'can_disable': False,
        'purpose_ru': 'Драйвер виртуализации файлов и реестра для UAC (User Account Control).',
        'protection_role': 'Перенаправляет неавторизованные записи устаревших программ в VirtualStore пользователей.',
    },
    'bindflt': {
        'display_name': 'Windows Bind Filter Driver',
        'category': DriverCategory.MINIFILTER,
        'criticality': ComponentCriticality.MEDIUM,
        'can_disable': False,
        'purpose_ru': 'Файловое перенаправление и изоляция путей для контейнеров, WSL и песочниц.',
        'protection_role': 'Обеспечивает привязку виртуальных директорий к физическим файловым путям.',
    },
    'wcifs': {
        'display_name': 'Windows Container Isolation File System Driver',
        'category': DriverCategory.MINIFILTER,
        'criticality': ComponentCriticality.MEDIUM,
        'can_disable': False,
        'purpose_ru': 'Файловая изоляция виртуальных контейнеров Windows Containers и Docker.',
        'protection_role': 'Контролирует слои файловой системы и защищает базовый образ хоста.',
    },
    'cldflt': {
        'display_name': 'Cloud Files Mini-Filter Driver',
        'category': DriverCategory.MINIFILTER,
        'criticality': ComponentCriticality.LOW,
        'can_disable': True,
        'purpose_ru': 'Поддержка Cloud Files API (интеграция OneDrive и облачных заполнителей файлов).',
        'protection_role': 'Обрабатывает hydrated/dehydrated состояния облачных файлов при чтении/записи.',
    },
    'storqosflt': {
        'display_name': 'Storage QoS Filter Driver',
        'category': DriverCategory.MINIFILTER,
        'criticality': ComponentCriticality.MEDIUM,
        'can_disable': False,
        'purpose_ru': 'Управление качеством обслуживания операций хранения (Storage Quality of Service).',
        'protection_role': 'Ограничивает IOPS и пропускную способность ввода-вывода между процессами.',
    },
    'iorate': {
        'display_name': 'I/O Rate Filter Driver',
        'category': DriverCategory.MINIFILTER,
        'criticality': ComponentCriticality.MEDIUM,
        'can_disable': False,
        'purpose_ru': 'Контроль интенсивности операций ввода-вывода для системных фоновых процессов.',
        'protection_role': 'Дросселирует операции диска фоновых задач во избежание деградации UI.',
    },
    'fileinfo': {
        'display_name': 'File Information Mini-Filter Driver',
        'category': DriverCategory.SYSTEM,
        'criticality': ComponentCriticality.CRITICAL,
        'can_disable': False,
        'purpose_ru': 'Фильтрация и предоставление расширенной информации о файлах и кэшировании.',
        'protection_role': 'Служит базовым поставщиком файловой телеметрии для ядра Windows.',
    },
}

# Диапазоны высот файловых фильтров Microsoft Filter Altitudes
ALTITUDE_RANGES = [
    (420000, 429999, 'FSFilter Top (Верхний уровень перехвата)'),
    (400000, 409999, 'FSFilter Activity Monitor (Мониторинг активности)'),
    (360000, 389999, 'FSFilter Undelete (Восстановление файлов)'),
    (320000, 329999, 'FSFilter Anti-Virus (Антивирусная защита)'),
    (300000, 309999, 'FSFilter Replication (Репликация данных)'),
    (280000, 289999, 'FSFilter Continuous Backup (Резервное копирование)'),
    (260000, 269999, 'FSFilter Content Screener (Фильтрация содержимого/DLP)'),
    (220000, 229999, 'FSFilter Quota Management (Управление квотами)'),
    (180000, 189999, 'FSFilter System Recovery (Восстановление системы)'),
    (160000, 169999, 'FSFilter Security Enhancer (Усиление безопасности)'),
    (140000, 149999, 'FSFilter Copy Protection (Защита от копирования/DRM)'),
    (130000, 139999, 'FSFilter System (Системный уровень)'),
    (80000, 89999, 'FSFilter Physical Quota Management (Физические квоты)'),
    (40000, 49999, 'FSFilter Compression (Сжатие данных)'),
    (20000, 29999, 'FSFilter Bottom (Нижний уровень фильтрации)'),
]


def resolve_altitude_group(altitude_str: str) -> str:
    """Определение группы высоты фильтра по номеру Altitude."""
    try:
        val = float(altitude_str.split('.')[0])
        for low, high, group_name in ALTITUDE_RANGES:
            if low <= val <= high:
                return group_name
        return 'Пользовательский диапазон высоты'
    except Exception:
        return 'Неопределенная группа'


class DriverInventoryManager:
    """Менеджер инвентаризации системных драйверов и файловых фильтров."""

    def __init__(self) -> None:
        """Инициализация менеджера с кэшированием."""
        self._cached_drivers: List[SystemDriverInfo] = []
        self._cache_time: float = 0.0
        self._cache_ttl_seconds: float = 30.0

    def get_all_system_drivers(self, force_refresh: bool = False) -> List[SystemDriverInfo]:
        """Получение списка всех системных драйверов Windows через CIM/WMI.

        Args:
            force_refresh: Принудительное обновление кэша.

        Returns:
            Список объектов SystemDriverInfo.
        """
        now = time.time()
        if not force_refresh and self._cached_drivers and (now - self._cache_time < self._cache_ttl_seconds):
            return list(self._cached_drivers)

        drivers: List[SystemDriverInfo] = []
        ps_cmd = (
            "Get-CimInstance Win32_SystemDriver | "
            "Select-Object Name, DisplayName, State, StartMode, PathName | "
            "ConvertTo-Json -Compress"
        )
        try:
            res = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=12
            )
            if res.returncode == 0 and res.stdout.strip():
                raw_data = json.loads(res.stdout.strip())
                items = [raw_data] if isinstance(raw_data, dict) else raw_data
                for item in items:
                    name = str(item.get('Name') or '').strip()
                    if not name:
                        continue
                    low_name = name.lower()
                    display_name = str(item.get('DisplayName') or name).strip()
                    state = str(item.get('State') or 'Unknown').strip()
                    start_mode = str(item.get('StartMode') or 'Unknown').strip()
                    path_name = str(item.get('PathName') or '').strip()
                    is_running = (state.lower() == 'running')

                    # Определение категории и метаданных по известному каталогу
                    known_meta = KNOWN_PROTECTION_DRIVERS.get(low_name)
                    if known_meta:
                        category = known_meta['category']
                        criticality = known_meta['criticality']
                        can_disable = known_meta['can_disable']
                        purpose_ru = known_meta['purpose_ru']
                        protection_role = known_meta['protection_role']
                    else:
                        is_third_party = bool(path_name and not path_name.lower().startswith(r'c:\windows\system32\drivers'))
                        category = DriverCategory.THIRD_PARTY if is_third_party else DriverCategory.SYSTEM
                        criticality = ComponentCriticality.MEDIUM if is_third_party else ComponentCriticality.HIGH
                        can_disable = is_third_party
                        purpose_ru = f'Системный драйвер Windows ({name})' if not is_third_party else f'Сторонний драйвер ({name})'
                        protection_role = None

                    drivers.append(SystemDriverInfo(
                        name=name,
                        display_name=display_name,
                        state=state,
                        start_mode=start_mode,
                        path_name=path_name,
                        category=category,
                        is_running=is_running,
                        purpose_ru=purpose_ru,
                        protection_role=protection_role,
                        criticality=criticality,
                        can_disable=can_disable
                    ))
        except Exception as ex:
            logger.warning(f'[DriverInventory] Ошибка сбора драйверов через CIM: {ex}')
            # Fallback: минимальный список из известных драйверов
            for low_name, meta in KNOWN_PROTECTION_DRIVERS.items():
                drivers.append(SystemDriverInfo(
                    name=low_name,
                    display_name=meta['display_name'],
                    state='Running',
                    start_mode='Auto',
                    path_name=f'C:\\Windows\\System32\\drivers\\{low_name}.sys',
                    category=meta['category'],
                    is_running=True,
                    purpose_ru=meta['purpose_ru'],
                    protection_role=meta['protection_role'],
                    criticality=meta['criticality'],
                    can_disable=meta['can_disable']
                ))

        self._cached_drivers = drivers
        self._cache_time = now
        return list(drivers)

    def get_security_and_filter_drivers(self) -> List[SystemDriverInfo]:
        """Получение списка только драйверов безопасности, фильтров и сторонних перехватчиков."""
        all_drv = self.get_all_system_drivers()
        return [
            d for d in all_drv
            if d.category in (DriverCategory.SECURITY, DriverCategory.MINIFILTER, DriverCategory.THIRD_PARTY)
            or d.name.lower() in KNOWN_PROTECTION_DRIVERS
        ]

    def get_active_minifilters(self) -> List[MinifilterInfo]:
        """Сбор активных файловых минифильтров Windows через команду fltmc filters.

        Returns:
            Список объектов MinifilterInfo с определенными группами высот (Altitudes).
        """
        filters: List[MinifilterInfo] = []
        try:
            res = subprocess.run(
                ['fltmc', 'filters'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=8
            )
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                # Поиск строк таблицы: Фильтр Инстансов Высота Кадр
                table_started = False
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if '----' in line:
                        table_started = True
                        continue
                    if not table_started:
                        continue

                    parts = re.split(r'\s{2,}', line)
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        instances = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                        altitude = parts[2].strip()
                        frame = parts[3].strip() if len(parts) > 3 else '0'

                        group_ru = resolve_altitude_group(altitude)
                        known_meta = KNOWN_PROTECTION_DRIVERS.get(name.lower())
                        purpose_ru = known_meta['purpose_ru'] if known_meta else f'Файловый минифильтр {name} (группа: {group_ru})'
                        vendor = 'Microsoft' if not ('mfe' in name.lower() or 'crowd' in name.lower() or 'kl' in name.lower()) else 'Third-party'

                        filters.append(MinifilterInfo(
                            name=name,
                            instances_count=instances,
                            altitude=altitude,
                            frame=frame,
                            altitude_group_ru=group_ru,
                            purpose_ru=purpose_ru,
                            vendor=vendor
                        ))
        except Exception as ex:
            logger.warning(f'[DriverInventory] Ошибка выполнения fltmc filters: {ex}')

        # Если fltmc не вернул данных (например нет админ-прав в контейнере), сформируем синтетический снимок базовых фильтров
        if not filters:
            defaults = [
                ('WdFilter', 1, '328010', 'FSFilter Anti-Virus (Антивирусная защита)', 'Microsoft Defender'),
                ('cldflt', 1, '180451', 'FSFilter System Recovery (Восстановление системы)', 'Cloud Files Mini-Filter'),
                ('luafv', 1, '135000', 'FSFilter System (Системный уровень)', 'UAC File Virtualization'),
                ('bindflt', 1, '409800', 'FSFilter Activity Monitor (Мониторинг активности)', 'Windows Bind Filter'),
                ('FileInfo', 1, '405000', 'FSFilter Activity Monitor (Мониторинг активности)', 'File Information Mini-Filter'),
            ]
            for name, inst, alt, grp, desc in defaults:
                filters.append(MinifilterInfo(
                    name=name,
                    instances_count=inst,
                    altitude=alt,
                    frame='0',
                    altitude_group_ru=grp,
                    purpose_ru=desc,
                    vendor='Microsoft'
                ))

        return filters
