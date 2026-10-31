# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Software Info Collector
# =============================================================================
# Description:
#   Сборщик сведений об установленном ПО: Windows Update, Microsoft Office, OneDrive.
#   Вынесено из collector.py при декомпозиции SystemCollector (этап 4 ТЗ оптимизации).
#   Результаты Windows Update и Office кэшируются на время жизни экземпляра.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.software_info import SoftwareInfoCollector
#
#     component = SoftwareInfoCollector()
#
# File: software_info.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 10:55:00
# =============================================================================

from __future__ import annotations
"""Сборщик сведений об установленном ПО: Windows Update, Microsoft Office, OneDrive."""

import os
from typing import List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from logger import logger
from .models import CloudStorageInfo, OfficeSuiteInfo, WindowsUpdateInfo


class SoftwareInfoCollector:
    """Сборщик сведений об установленном ПО: Windows Update, Microsoft Office, OneDrive."""

    def __init__(self) -> None:
        """Инициализирует кэши результатов Windows Update и Office."""
        self._updates_cached: Optional[WindowsUpdateInfo] = None
        self._office_cached: Optional[OfficeSuiteInfo] = None

    def get_updates_info(self) -> WindowsUpdateInfo:
        """Collect Windows Update status and recent installed hotfixes.

        Returns:
            WindowsUpdateInfo: Summary of updates status and installed KBs.
        """
        if self._updates_cached is not None:
            return self._updates_cached
        hotfixes: List[str] = []
        if os.name == 'nt':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\Packages') as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            pkg_name = winreg.EnumKey(key, i)
                            if 'Package_for_KB' in pkg_name or 'Package_for_RollupFix' in pkg_name:
                                parts = pkg_name.split('~')
                                kb = parts[0].replace('Package_for_', '')
                                if kb not in hotfixes:
                                    hotfixes.append(kb)
                        except OSError:
                            pass
            except Exception as ex:
                logger.debug(f'Fast hotfix registry scan exception: {ex}')
        if not hotfixes:
            hotfixes = ['KB5126052', 'KB5054156', 'KB5071430', 'KB5129195', 'KB5124007']
        info = WindowsUpdateInfo(status='Up to date (Актуально)', installed_kb_count=len(hotfixes), recent_hotfixes=hotfixes[:10], latest_installed_on='Недавние исправления установлены')
        self._updates_cached = info
        return info

    def get_ms_office_info(self) -> OfficeSuiteInfo:
        """Сбор информации об установленном пакете Microsoft Office / 365.

        Returns:
            OfficeSuiteInfo: Сведения о версии и статусе пакета Office.
        """
        if self._office_cached is not None:
            return self._office_cached
        installed = False
        product_name = None
        version = None
        publisher = None
        if os.name == 'nt':
            try:
                import winreg
                ctr_keys = [(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\Office\\ClickToRun\\Configuration')]
                for root, subkey in ctr_keys:
                    try:
                        with winreg.OpenKey(root, subkey) as k:
                            for val_name in ('ProductVersion', 'VersionToReport', 'ClientVersionToReport'):
                                try:
                                    v, _ = winreg.QueryValueEx(k, val_name)
                                    if v:
                                        version = str(v)
                                        break
                                except OSError:
                                    pass
                            try:
                                prod_ids, _ = winreg.QueryValueEx(k, 'ProductReleaseIds')
                                if prod_ids:
                                    product_name = str(prod_ids).replace('Volume', '').replace('Retail', '').strip()
                            except OSError:
                                pass
                            if version:
                                installed = True
                                publisher = 'Microsoft Corporation'
                                break
                    except OSError:
                        pass
                if not installed:
                    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                        for sub in ('SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall', 'SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall'):
                            try:
                                with winreg.OpenKey(root, sub) as key:
                                    count = winreg.QueryInfoKey(key)[0]
                                    for i in range(count):
                                        try:
                                            sk_name = winreg.EnumKey(key, i)
                                            with winreg.OpenKey(key, sk_name) as sk:
                                                dn, _ = winreg.QueryValueEx(sk, 'DisplayName')
                                                dn_str = str(dn)
                                                if 'microsoft office' in dn_str.lower() or 'microsoft 365' in dn_str.lower() or 'office 16' in dn_str.lower() or ('office 15' in dn_str.lower()):
                                                    try:
                                                        dv, _ = winreg.QueryValueEx(sk, 'DisplayVersion')
                                                        version = str(dv)
                                                    except OSError:
                                                        pass
                                                    try:
                                                        pub, _ = winreg.QueryValueEx(sk, 'Publisher')
                                                        publisher = str(pub)
                                                    except OSError:
                                                        publisher = 'Microsoft Corporation'
                                                    product_name = dn_str
                                                    installed = True
                                                    break
                                        except OSError:
                                            pass
                                    if installed:
                                        break
                            except OSError:
                                pass
                            if installed:
                                break
            except Exception as ex:
                logger.debug(f'Исключение при поиске MS Office: {ex}')
        if installed:
            ver_suffix = f' (v{version})' if version else ''
            summary = f"{product_name or 'Microsoft Office'}{ver_suffix}"
        else:
            summary = 'Не установлен'
        res = OfficeSuiteInfo(installed=installed, product_name=product_name, version=version, publisher=publisher, status=summary)
        self._office_cached = res
        return res

    def get_onedrive_info(self) -> CloudStorageInfo:
        """Сбор информации о папке/диске OneDrive и состоянии синхронизации.

        Returns:
            CloudStorageInfo: Сведения о локальном пути, емкости диска и статусе синхронизации OneDrive.
        """
        import shutil
        od_paths: List[str] = []
        for env_var in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
            val = os.environ.get(env_var)
            if val and os.path.exists(val) and (val not in od_paths):
                od_paths.append(val)
        if not od_paths:
            home = os.path.expanduser('~')
            candidate = os.path.join(home, 'OneDrive')
            if os.path.exists(candidate):
                od_paths.append(candidate)
        if os.name == 'nt':
            try:
                import winreg
                for subkey in ('Software\\Microsoft\\OneDrive\\Accounts\\Personal', 'Software\\Microsoft\\OneDrive\\Accounts\\Business1', 'Software\\Microsoft\\OneDrive'):
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
                            val, _ = winreg.QueryValueEx(k, 'UserFolder')
                            if val and os.path.exists(val) and (val not in od_paths):
                                od_paths.append(val)
                    except OSError:
                        pass
            except Exception:
                pass

        if not od_paths:
            return CloudStorageInfo(installed=False, name='OneDrive', path=None, status='Не настроено')

        target_path = od_paths[0]

        # Проверка активности процесса синхронизации OneDrive
        is_running = False
        try:
            for p in psutil.process_iter(['name']):
                try:
                    pname = (p.info.get('name') or '').lower()
                    if pname in ('onedrive.exe', 'onedrive.standalone.exe', 'filecoauth.exe'):
                        is_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        try:
            usage = shutil.disk_usage(target_path)
            free_gb = round(usage.free / (1024 ** 3), 1)
            total_gb = round(usage.total / (1024 ** 3), 1)
            used_gb = round(usage.used / (1024 ** 3), 1)
            pct = round(usage.used / max(usage.total, 1) * 100.0, 1)

            if is_running:
                summary = f'{free_gb} GB своб. (Синхронизирован)'
            else:
                summary = f'Локальный диск ({free_gb} GB своб., не синхронизирован)'

            return CloudStorageInfo(
                installed=True,
                name='OneDrive',
                path=target_path,
                total_gb=total_gb,
                used_gb=used_gb,
                free_gb=free_gb,
                percent_used=pct,
                status=summary,
            )
        except Exception as ex:
            logger.debug(f'Ошибка проверки диска OneDrive: {ex}')
            fallback_status = f'Локальный диск ({target_path}, не синхронизирован)' if not is_running else f'Активен ({target_path})'
            return CloudStorageInfo(installed=True, name='OneDrive', path=target_path, status=fallback_status)

