# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Defender Core - WMI Client
# =============================================================================
# Description:
#   Высокоскоростной WMI-клиент для прямого опроса подсистемы Microsoft Defender
#   (пространство ROOT\Microsoft\Windows\Defender) без порождения процессов PowerShell.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.defender.core.wmi_client import DefenderWmiClient
#
#     status_data = DefenderWmiClient.query_computer_status()
#     pref_data = DefenderWmiClient.query_preference()
#
# File: wmi_client.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.defender.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 14:06:00
# =============================================================================

from __future__ import annotations
"""Высокоскоростной WMI-клиент для Microsoft Defender."""

import platform
from typing import Any, Dict, List, Optional
from logger import logger

WMI_DEFENDER_NAMESPACE = r'winmgmts:\\.\root\Microsoft\Windows\Defender'


class DefenderWmiClient:
    """Прямой WMI-коннектор к классам безопасности Microsoft Defender."""

    @staticmethod
    def query_computer_status() -> Optional[Dict[str, Any]]:
        """Запрашивает состояние защиты через WMI класс MSFT_MpComputerStatus (< 100 мс).

        Returns:
            Optional[Dict[str, Any]]: Словарь свойств статуса или None при ошибке.
        """
        if platform.system() != 'Windows':
            return None
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                wmi = win32com.client.GetObject(WMI_DEFENDER_NAMESPACE)
                items = list(wmi.ExecQuery('SELECT * FROM MSFT_MpComputerStatus'))
                if not items:
                    del items, wmi
                    return None
                obj = items[0]
                result = {
                    p.Name: list(p.Value) if isinstance(p.Value, tuple) else p.Value
                    for p in obj.Properties_
                }
                del obj, items, wmi
                return result
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug(f'WMI MSFT_MpComputerStatus fallback: {e}')
            return None

    @staticmethod
    def query_preference() -> Optional[Dict[str, Any]]:
        """Запрашивает конфигурацию и исключения через WMI класс MSFT_MpPreference (< 100 мс).

        Returns:
            Optional[Dict[str, Any]]: Словарь параметров предпочтений или None при ошибке.
        """
        if platform.system() != 'Windows':
            return None
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                wmi = win32com.client.GetObject(WMI_DEFENDER_NAMESPACE)
                items = list(wmi.ExecQuery('SELECT * FROM MSFT_MpPreference'))
                if not items:
                    del items, wmi
                    return None
                obj = items[0]
                result = {
                    p.Name: list(p.Value) if isinstance(p.Value, tuple) else p.Value
                    for p in obj.Properties_
                }
                del obj, items, wmi
                return result
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug(f'WMI MSFT_MpPreference fallback: {e}')
            return None

    @staticmethod
    def query_threats(limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Запрашивает журнал обнаруженных угроз через WMI класс MSFT_MpThreatDetection.

        Args:
            limit: Максимальное число возвращаемых записей.

        Returns:
            Optional[List[Dict[str, Any]]]: Список записей угроз или None при ошибке.
        """
        if platform.system() != 'Windows':
            return None
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                wmi = win32com.client.GetObject(WMI_DEFENDER_NAMESPACE)
                col = wmi.ExecQuery('SELECT * FROM MSFT_MpThreatDetection')
                records: List[Dict[str, Any]] = []
                for obj in col:
                    rec = {
                        p.Name: list(p.Value) if isinstance(p.Value, tuple) else p.Value
                        for p in obj.Properties_
                    }
                    records.append(rec)
                    if len(records) >= limit:
                        break
                del col, wmi
                return records
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug(f'WMI MSFT_MpThreatDetection fallback: {e}')
            return None

