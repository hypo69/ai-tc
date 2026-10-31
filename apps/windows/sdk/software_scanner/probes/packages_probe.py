# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Packages Probe
# =============================================================================
# Description:
#   Зонд пакетных менеджеров Windows: опрос AppX / MSIX / Microsoft Store,
#   WinGet, Scoop, Chocolatey и виртуальных сред.
#
# File: packages_probe.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд сканирования пакетов AppX, Store, WinGet, Scoop и Chocolatey."""

import json
import os
import subprocess
import sys
from typing import List
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class PackagesProbe:
    """Зонд сбора установленных пакетов из современных пакетных менеджеров."""

    def scan_appx_packages(self) -> List[EvidenceItem]:
        """Сбор установленных AppX/MSIX пакетов через PowerShell."""
        items: List[EvidenceItem] = []
        if not sys.platform.startswith("win"):
            return items

        ps_script = (
            "Get-AppxPackage | Select-Object Name, PackageFullName, InstallLocation, Publisher, Version | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=12,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]

                for pkg in data:
                    name = pkg.get("Name")
                    if not name:
                        continue
                    # Фильтруем внутренние системные библиотеки Windows
                    if name.startswith("Microsoft.NET.") or name.startswith("Microsoft.VCLibs."):
                        continue

                    install_loc = pkg.get("InstallLocation") or ""
                    items.append(EvidenceItem(
                        evidence_type=EvidenceType.PACKAGE,
                        source="AppX_Store",
                        path=install_loc,
                        product_name=name,
                        publisher=pkg.get("Publisher"),
                        version=pkg.get("Version"),
                        confidence=ConfidenceLevel.HIGH,
                        raw_details={"package_full_name": pkg.get("PackageFullName")},
                    ))
        except Exception as ex:
            logger.debug(f"[PackagesProbe] Ошибка сбора AppX пакетов: {ex}")

        return items

    def scan_scoop_packages(self) -> List[EvidenceItem]:
        """Сбор пакетов менеджера Scoop."""
        items: List[EvidenceItem] = []
        user_profile = os.environ.get("USERPROFILE", "")
        scoop_apps = os.path.join(user_profile, "scoop", "apps")
        if not os.path.isdir(scoop_apps):
            return items

        try:
            for entry in os.scandir(scoop_apps):
                if entry.is_dir() and entry.name != "scoop":
                    current_link = os.path.join(entry.path, "current")
                    manifest = os.path.join(current_link, "manifest.json")
                    version = None
                    if os.path.isfile(manifest):
                        try:
                            with open(manifest, "r", encoding="utf-8") as f:
                                mdata = json.load(f)
                                version = mdata.get("version")
                        except Exception:
                            pass

                    items.append(EvidenceItem(
                        evidence_type=EvidenceType.PACKAGE,
                        source="Scoop",
                        path=entry.path,
                        product_name=entry.name,
                        version=version,
                        confidence=ConfidenceLevel.HIGH,
                        raw_details={"scoop_dir": entry.path},
                    ))
        except Exception as ex:
            logger.debug(f"[PackagesProbe] Ошибка сбора Scoop: {ex}")

        return items

    def scan_chocolatey_packages(self) -> List[EvidenceItem]:
        """Сбор пакетов менеджера Chocolatey."""
        items: List[EvidenceItem] = []
        choco_dir = os.environ.get("ChocolateyInstall", r"C:\ProgramData\chocolatey")
        lib_dir = os.path.join(choco_dir, "lib")
        if not os.path.isdir(lib_dir):
            return items

        try:
            for entry in os.scandir(lib_dir):
                if entry.is_dir() and entry.name.lower() != "chocolatey":
                    items.append(EvidenceItem(
                        evidence_type=EvidenceType.PACKAGE,
                        source="Chocolatey",
                        path=entry.path,
                        product_name=entry.name,
                        confidence=ConfidenceLevel.HIGH,
                        raw_details={"choco_lib_dir": entry.path},
                    ))
        except Exception as ex:
            logger.debug(f"[PackagesProbe] Ошибка сбора Chocolatey: {ex}")

        return items

    def scan_all(self) -> List[EvidenceItem]:
        """Полный запуск зонда пакетов."""
        results: List[EvidenceItem] = []
        results.extend(self.scan_appx_packages())
        results.extend(self.scan_scoop_packages())
        results.extend(self.scan_chocolatey_packages())
        return results


__all__ = ["PackagesProbe"]

