# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Registry Probe
# =============================================================================
# Description:
#   Зонд реестра Windows: сканирование ключей Uninstall (32/64-бит, системные
#   и пользовательские), App Paths, Run/RunOnce и регистраций приложений.
#
# File: registry_probe.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд сканирования реестра Windows на наличие установленных и зарегистрированных программ."""

import sys
from typing import Any, Dict, List, Optional
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class RegistryProbe:
    """Зонд глубокого обследования реестра Windows."""

    def __init__(self) -> None:
        self._winreg = self._get_winreg()

    @staticmethod
    def _get_winreg() -> Any:
        if sys.platform.startswith("win"):
            import winreg
            return winreg
        return None

    def scan_uninstall_keys(self) -> List[EvidenceItem]:
        """Сбор зарегистрированных установленных программ из Uninstall-ветвей."""
        items: List[EvidenceItem] = []
        if not self._winreg:
            return items

        locations = [
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM_64"),
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM_WOW64"),
            (self._winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
        ]

        for hive, root_path, hive_tag in locations:
            try:
                with self._winreg.OpenKey(hive, root_path, 0, self._winreg.KEY_READ) as root_key:
                    num_subkeys, _, _ = self._winreg.QueryInfoKey(root_key)
                    for i in range(num_subkeys):
                        try:
                            subkey_name = self._winreg.EnumKey(root_key, i)
                            sub_path = f"{root_path}\\{subkey_name}"
                            with self._winreg.OpenKey(hive, sub_path, 0, self._winreg.KEY_READ) as app_key:
                                item = self._parse_uninstall_key(app_key, sub_path, hive_tag)
                                if item:
                                    items.append(item)
                        except OSError:
                            continue
            except OSError as ex:
                logger.debug(f"[RegistryProbe] Ветка недоступна {root_path}: {ex}")

        return items

    def _parse_uninstall_key(self, key: Any, sub_path: str, hive_tag: str) -> Optional[EvidenceItem]:
        """Извлечение полей из конкретного ключа Uninstall."""
        fields: Dict[str, Any] = {}
        for prop in [
            "DisplayName", "DisplayVersion", "Publisher", "InstallLocation",
            "UninstallString", "QuietUninstallString", "InstallDate", "DisplayIcon"
        ]:
            try:
                val, _ = self._winreg.QueryValueEx(key, prop)
                if val:
                    fields[prop.lower()] = str(val).strip()
            except OSError:
                continue

        name = fields.get("displayname")
        if not name:
            return None

        # Игнорируем обновления Windows (KB-пакеты)
        if name.startswith("Security Update") or name.startswith("Update for Windows"):
            return None

        install_loc = fields.get("installlocation") or fields.get("displayicon") or sub_path
        if install_loc and install_loc.startswith('"') and install_loc.endswith('"'):
            install_loc = install_loc[1:-1]
        if install_loc and "," in install_loc:
            install_loc = install_loc.split(",")[0]

        return EvidenceItem(
            evidence_type=EvidenceType.REGISTRY,
            source=f"Registry_{hive_tag}",
            path=install_loc,
            product_name=name,
            publisher=fields.get("publisher"),
            version=fields.get("displayversion"),
            confidence=ConfidenceLevel.HIGH,
            raw_details=fields,
        )

    def scan_app_paths(self) -> List[EvidenceItem]:
        """Сбор путей к исполняемым файлам из HKLM/HKCU App Paths."""
        items: List[EvidenceItem] = []
        if not self._winreg:
            return items

        app_paths = [
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (self._winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hive, base_path in app_paths:
            try:
                with self._winreg.OpenKey(hive, base_path, 0, self._winreg.KEY_READ) as root_key:
                    num_subkeys, _, _ = self._winreg.QueryInfoKey(root_key)
                    for i in range(num_subkeys):
                        try:
                            exe_name = self._winreg.EnumKey(root_key, i)
                            sub_path = f"{base_path}\\{exe_name}"
                            with self._winreg.OpenKey(hive, sub_path, 0, self._winreg.KEY_READ) as key:
                                target_path, _ = self._winreg.QueryValueEx(key, "")
                                if target_path:
                                    clean_path = str(target_path).strip(' "\'')
                                    items.append(EvidenceItem(
                                        evidence_type=EvidenceType.REGISTRY,
                                        source="Registry_AppPaths",
                                        path=clean_path,
                                        product_name=exe_name,
                                        confidence=ConfidenceLevel.MEDIUM,
                                        raw_details={"registry_path": sub_path, "target_path": clean_path},
                                    ))
                        except OSError:
                            continue
            except OSError as ex:
                logger.debug(f"[RegistryProbe] Ошибка чтения App Paths {base_path}: {ex}")

        return items

    def scan_run_keys(self) -> List[EvidenceItem]:
        """Сбор записей автозагрузки из Run и RunOnce."""
        items: List[EvidenceItem] = []
        if not self._winreg:
            return items

        run_locations = [
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM_Run"),
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM_RunOnce"),
            (self._winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU_Run"),
            (self._winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU_RunOnce"),
        ]

        for hive, path, tag in run_locations:
            try:
                with self._winreg.OpenKey(hive, path, 0, self._winreg.KEY_READ) as key:
                    _, num_values, _ = self._winreg.QueryInfoKey(key)
                    for i in range(num_values):
                        try:
                            val_name, val_data, _ = self._winreg.EnumValue(key, i)
                            if val_data:
                                target = str(val_data).strip(' "\'')
                                items.append(EvidenceItem(
                                    evidence_type=EvidenceType.REGISTRY,
                                    source=f"Registry_{tag}",
                                    path=target,
                                    product_name=val_name,
                                    confidence=ConfidenceLevel.HIGH,
                                    raw_details={"key_name": val_name, "command": val_data},
                                ))
                        except OSError:
                            continue
            except OSError as ex:
                logger.debug(f"[RegistryProbe] Ошибка чтения {path}: {ex}")

        return items

    def scan_all(self) -> List[EvidenceItem]:
        """Полный запуск зонда реестра."""
        results: List[EvidenceItem] = []
        results.extend(self.scan_uninstall_keys())
        results.extend(self.scan_app_paths())
        results.extend(self.scan_run_keys())
        return results


__all__ = ["RegistryProbe"]

