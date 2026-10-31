# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Common - App Telemetry Logger
# =============================================================================
# Description:
#   Универсальный логгер телеметрии приложений и SDK модулей Windows.
#   Направляет метрики опроса, события и изменения параметров исключительно в
#   буфер оперативной памяти TelemetryStorage с последующим пакетным сбросом
#   в базу данных SQLite (telemetry.db).
#
# Usage Examples:
#   Python API:
#     from apps.common.telemetry_logger import AppTelemetryLogger
#
#     logger = AppTelemetryLogger('network_terminal')
#     logger.log_event('start_capture', 'SUCCESS', {'interface': 'eth0'})
#
# File: telemetry_logger.py
# Project: ai-windows-admin
# Package: apps.common
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:36:45
# =============================================================================

from __future__ import annotations
"""Универсальный логгер телеметрии модулей и приложений Windows."""

from typing import Any, Dict, Optional, Union
from logger import logger


class AppTelemetryLogger:
    """Логгер телеметрии и событий модулей с накоплением в памяти и сбросом в SQLite."""

    def __init__(self, app_name: str) -> None:
        """Инициализирует логгер телеметрии для указанного приложения.

        Args:
            app_name (str): Имя модуля или подсистемы (например, 'network_terminal').
        """
        self.app_name = app_name

    def _get_storage(self) -> Any:
        """Получить экземпляр TelemetryStorage."""
        try:
            from apps.windows.telemetry.sqlite import TelemetryStorage
            return TelemetryStorage.get_instance()
        except Exception as exc:
            logger.debug(f'Не удалось получить экземпляр TelemetryStorage: {exc}')
            return None

    def log_poll(
        self,
        poll_type: str,
        metric_name: str,
        value: Any,
        unit: str = '',
        status: str = 'OK',
        details: Optional[Union[Dict[str, Any], str]] = None,
    ) -> bool:
        """Логирует замер метрики опроса в буфер памяти TelemetryStorage.

        Args:
            poll_type (str): Категория замера.
            metric_name (str): Название метрики.
            value (Any): Значение метрики.
            unit (str): Единица измерения.
            status (str): Статус ('OK', 'WARN', 'ERR').
            details (Optional[Union[Dict[str, Any], str]]): Дополнительные параметры.

        Returns:
            bool: True в случае успешной буферизации.
        """
        storage = self._get_storage()
        if not storage:
            return False
        try:
            storage.save_app_poll(
                app=self.app_name,
                poll_type=poll_type,
                metric_name=metric_name,
                value=value,
                unit=unit,
                status=status,
                details=details if details is not None else {},
            )
            return True
        except Exception as exc:
            logger.debug(f'Ошибка сохранения poll телеметрии {self.app_name}: {exc}')
            return False

    def log_event(
        self,
        event_type: str,
        status: str = 'SUCCESS',
        details: Optional[Union[Dict[str, Any], str]] = None,
    ) -> bool:
        """Логирует операционное событие подсистемы в буфер памяти TelemetryStorage.

        Args:
            event_type (str): Тип события.
            status (str): Результат выполнения ('SUCCESS', 'FAILED', 'INFO').
            details (Optional[Union[Dict[str, Any], str]]): Описание или данные события.

        Returns:
            bool: True в случае успешной буферизации.
        """
        storage = self._get_storage()
        if not storage:
            return False
        try:
            storage.save_app_event(
                app=self.app_name,
                event_type=event_type,
                status=status,
                details=details if details is not None else {},
            )
            return True
        except Exception as exc:
            logger.debug(f'Ошибка сохранения event телеметрии {self.app_name}: {exc}')
            return False

    def log_param_change(
        self,
        param_name: str,
        old_value: Any,
        new_value: Any,
        status: str = 'SUCCESS',
        details: Optional[Union[Dict[str, Any], str]] = None,
        user: str = 'system',
    ) -> bool:
        """Логирует изменение системного параметра или настройки в буфер памяти TelemetryStorage.

        Args:
            param_name (str): Название параметра.
            old_value (Any): Предыдущее значение.
            new_value (Any): Новое значение.
            status (str): Статус применения.
            details (Optional[Union[Dict[str, Any], str]]): Дополнительные сведения.
            user (str): Пользователь или процесс, инициировавший изменение.

        Returns:
            bool: True в случае успешной буферизации.
        """
        storage = self._get_storage()
        if not storage:
            return False
        try:
            storage.save_app_param_change(
                app=self.app_name,
                param_name=param_name,
                old_value=old_value,
                new_value=new_value,
                status=status,
                user=user,
                details=details if details is not None else {},
            )
            return True
        except Exception as exc:
            logger.debug(f'Ошибка сохранения param_change телеметрии {self.app_name}: {exc}')
            return False

