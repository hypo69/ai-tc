# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Services Probe
# =============================================================================
# Description:
#   Зонд системных служб Windows: опрос SCM/реестра, извлечение путей запуска,
#   проверка существования бинарных файлов и детекция фоновых компонентов.
#
# File: services_probe.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд сканирования системных служб Windows."""

import os
import sys
from typing import Any, List
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class ServicesProbe:
    """Зонд аудита служб и фоновых сервисов Windows."""

    def __init__(self) -> None:
        self._winreg = self._get_winreg()

    @staticmethod
    def _get_winreg() -> Any:
        if sys.platform.startswith("win"):
            import winreg
            return winreg
        return None

    def scan_services(self) -> List[EvidenceItem]:
        """Сбор зарегистрированных служб из HKLM\\SYSTEM\\CurrentControlSet\\Services."""
        items: List[EvidenceItem] = []
        if not self._winreg:
            return items

        services_path = r"SYSTEM\CurrentControlSet\Services"
        try:
            with self._winreg.OpenKey(self._winreg.HKEY_LOCAL_MACHINE, services_path, 0, self._winreg.KEY_READ) as root_key:
                num_subkeys, _, _ = self._winreg.QueryInfoKey(root_key)
                for i in range(num_subkeys):
                    try:
                        svc_name = self._winreg.EnumKey(root_key, i)
                        svc_sub_path = f"{services_path}\\{svc_name}"
                        with self._winreg.OpenKey(self._winreg.HKEY_LOCAL_MACHINE, svc_sub_path, 0, self._winreg.KEY_READ) as svc_key:
                            item = self._parse_service(svc_key, svc_name)
                            if item:
                                items.append(item)
                    except OSError:
                        continue
        except OSError as ex:
            logger.debug(f"[ServicesProbe] Ошибка доступа к реестру служб: {ex}")

        return items

    def _parse_service(self, key: Any, svc_name: str) -> EvidenceItem | None:
        """Извлечение параметров конкретной службы."""
        try:
            image_path, _ = self._winreg.QueryValueEx(key, "ImagePath")
        except OSError:
            return None

        if not image_path:
            return None

        # Очистка пути (удаление кавычек и аргументов)
        raw_image = str(image_path).strip()
        clean_path = raw_image
        if clean_path.startswith(r"\??\\"):
            clean_path = clean_path[4:]
        if clean_path.lower().startswith(r"\systemroot\\"):
            sys_root = os.environ.get("SystemRoot", r"C:\Windows")
            clean_path = sys_root + clean_path[11:]

        if clean_path.startswith('"'):
            end_quote = clean_path.find('"', 1)
            if end_quote != -1:
                clean_path = clean_path[1:end_quote]
        else:
            import re
            m = re.search(r'^(.*?\.(?:exe|dll|sys|drv|ocx))(?:\s+.*)?$', clean_path, re.IGNORECASE)
            if m:
                clean_path = m.group(1).strip(' "\'')
            else:
                clean_path = clean_path.split(" ")[0]

        # Разворачивание переменных окружения (%SystemRoot%, %ProgramFiles%)
        expanded_path = os.path.expandvars(clean_path)

        # Извлечение DisplayName и Description
        display_name = svc_name
        try:
            disp, _ = self._winreg.QueryValueEx(key, "DisplayName")
            if disp:
                display_name = str(disp).strip()
        except OSError:
            pass

        # Проверка наличия бинарника
        binary_exists = os.path.isfile(expanded_path) if expanded_path else False

        return EvidenceItem(
            evidence_type=EvidenceType.SERVICE,
            source="Services_SCM",
            path=expanded_path,
            product_name=display_name,
            confidence=ConfidenceLevel.HIGH,
            raw_details={
                "service_name": svc_name,
                "raw_image_path": raw_image,
                "binary_exists": binary_exists,
            }
        )


__all__ = ["ServicesProbe"]

