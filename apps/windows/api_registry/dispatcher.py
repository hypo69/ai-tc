# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Dispatcher & Resolver
# =============================================================================
# Description:
#   Интеллектуальный диспетчер системных интерфейсов (Smart API Dispatcher).
#   Подбирает наилучший интерфейс (Win32, WMI/CIM, PowerShell, WinRT) под задачу,
#   проверяет доступность Python-библиотек и генерирует исполняемый код.
#
# Usage Examples:
#   from apps.windows.api_registry.dispatcher import WindowsApiDispatcher
#   dispatcher = WindowsApiDispatcher()
#   res = dispatcher.recommend("получить список сетевых адаптеров")
#
# File: dispatcher.py
# Project: ai-windows-admin
# Package: apps.windows.api_registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:55:00
# =============================================================================

from __future__ import annotations
"""Умный диспетчер системных интерфейсов Windows API под диагностические задачи."""

import ctypes
import importlib
import sys
from typing import Any, Dict, List, Optional
from logger import logger
from apps.windows.api_registry.catalog import get_all_api_entries, get_api_by_id
from apps.windows.api_registry.models import (
    ApiRecommendationQuery,
    ApiRecommendationResult,
    PlatformSubsystem,
    PrivilegeLevel,
    WindowsApiEntry,
)


class WindowsApiDispatcher:
    """Интеллектуальный диспетчер и подборщик системных интерфейсов Windows."""

    def __init__(self) -> None:
        """Инициализация кэша установленных библиотек и привязок."""
        self._bindings_cache: Optional[Dict[str, bool]] = None

    def check_bindings_availability(self, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Проверяет доступность Python-привязок в текущем окружении.

        Returns:
            Dict: Статус наличия ctypes, pywin32, comtypes, winsdk/winrt, psutil, wmi, etc.
        """
        modules_to_test = {
            "ctypes": {"role": "Нативный вызов Win32 DLL без зависимостей (Zero-Dependency)", "required": True},
            "psutil": {"role": "Кросс-платформенная телеметрия процессов и системных ресурсов", "required": True},
            "win32api": {"role": "Пакет pywin32: Win32 API функции и константы", "required": False},
            "win32com.client": {"role": "Пакет pywin32: COM-интерфейсы (VSS, TaskScheduler, Firewall)", "required": False},
            "comtypes": {"role": "Низкоуровневые COM vtable и DirectX interop", "required": False},
            "winsdk": {"role": "Windows Runtime (WinRT) официальные проекции", "required": False},
            "winrt": {"role": "Windows Runtime (WinRT) альтернативные привязки", "required": False},
            "wmi": {"role": "WMI обертка для запросов к Windows Management Instrumentation", "required": False},
        }

        results: Dict[str, Dict[str, Any]] = {}
        for mod_name, meta in modules_to_test.items():
            installed = False
            version = None
            try:
                mod = importlib.import_module(mod_name)
                installed = True
                version = getattr(mod, "__version__", "Встроенный / Доступен")
            except ImportError:
                installed = False
            except Exception as ex:
                installed = False
                version = f"Ошибка инициализации: {ex}"

            results[mod_name] = {
                "name": mod_name,
                "installed": installed,
                "version": str(version) if version else None,
                "role": meta["role"],
                "required": meta["required"],
            }

        return results

    def recommend(self, query: ApiRecommendationQuery) -> ApiRecommendationResult:
        """
        Интеллектуально подбирает оптимальный системный API под задачу пользователя.

        Args:
            query: Запрос с описанием задачи и предпочтениями.

        Returns:
            ApiRecommendationResult: Рекомендованный интерфейс, кандидаты и готовый код.
        """
        text = query.task_description.lower()
        all_apis = get_all_api_entries()

        # 1. Фильтрация по подсистеме при наличии
        candidates = all_apis
        if query.subsystem:
            candidates = [a for a in candidates if a.subsystem == query.subsystem]

        # 2. Ранжирование по релевантности ключевых слов
        scored_candidates: List[tuple[int, WindowsApiEntry]] = []
        for api in candidates:
            score = 0
            # Совпадение в названии и описании
            if any(k in text for k in ("сеть", "адаптер", "ip", "порт", "network", "adapter")) and api.subsystem == PlatformSubsystem.NETWORK_INTELLIGENCE:
                score += 10
            if any(k in text for k in ("процесс", "память", "служба", "лог", "журнал", "event", "etw", "process")) and api.subsystem == PlatformSubsystem.SYSTEM_DIAGNOSTICS:
                score += 10
            if any(k in text for k in ("экран", "снимок", "видео", "ocr", "текст", "screen", "capture", "gpu")) and api.subsystem == PlatformSubsystem.GRAPHICS_VISION:
                score += 10
            if any(k in text for k in ("диск", "smart", "том", "файл", "поиск", "vss", "disk", "storage")) and api.subsystem == PlatformSubsystem.STORAGE_INTELLIGENCE:
                score += 10
            if any(k in text for k in ("токен", "права", "безопасность", "uac", "acl", "security", "defender")) and api.subsystem == PlatformSubsystem.SECURITY_INTELLIGENCE:
                score += 10
            if any(k in text for k in ("устройство", "датчик", "usb", "bluetooth", "pnp", "сенсор", "device")) and api.subsystem == PlatformSubsystem.HARDWARE_DEVICES:
                score += 10

            # Поиск точных подстрок в ключевых функциях
            for fn in api.functions:
                if any(part in fn.lower() for part in text.split()):
                    score += 5

            # Учет предпочтения Zero-Dependency
            if query.prefer_zero_dependency and api.zero_dependency:
                score += 4

            scored_candidates.append((score, api))

        # Сортировка по убыванию релевантности
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        matched_apis = [entry for _, entry in scored_candidates[:5]]

        best_api = matched_apis[0] if matched_apis else all_apis[0]

        # Формирование аргументации и сниппета
        rationale_parts = []
        if best_api.zero_dependency:
            rationale_parts.append(
                f"Выбран нативный интерфейс {best_api.binary_or_namespace} (Zero-Dependency), "
                "так как он гарантированно доступен через встроенный ctypes без установки сторонних пакетов."
            )
        else:
            rationale_parts.append(
                f"Выбран специализированный интерфейс {best_api.name}, обеспечивающий прямой доступ к возможностям Windows Runtime."
            )

        if best_api.alternatives:
            rationale_parts.append(f"Альтернативные подходы: {', '.join(best_api.alternatives)}.")

        py_code = best_api.code_examples.get("python", "# Python snippet not available")
        ps_code = best_api.code_examples.get("powershell", "")

        return ApiRecommendationResult(
            query=query.task_description,
            recommended_api=best_api,
            matched_apis=matched_apis,
            rationale=" ".join(rationale_parts),
            python_snippet=py_code,
            powershell_equivalent=ps_code,
        )

    def execute_api_probe(self, api_id: str) -> Dict[str, Any]:
        """
        Выполняет безопасный диагностический зонд выбранного API через ctypes.

        Args:
            api_id: Системный идентификатор API из каталога.

        Returns:
            Dict: Результат тестового вызова (успех, код ошибки, время отклика).
        """
        entry = get_api_by_id(api_id)
        if not entry:
            return {"status": "error", "message": f"API с ID '{api_id}' не найден в каталоге"}

        if sys.platform != "win32":
            return {"status": "skipped", "message": "Зонд доступен только на платформе Windows"}

        try:
            # Демонстрационные безопасные зонды ключевых DLL
            if "Iphlpapi" in entry.binary_or_namespace:
                # Проверка GetNumberOfInterfaces
                iphlp = ctypes.windll.iphlpapi
                num = ctypes.c_ulong()
                ret = iphlp.GetNumberOfInterfaces(ctypes.byref(num))
                return {
                    "status": "ok",
                    "probe_target": entry.name,
                    "native_function": "GetNumberOfInterfaces",
                    "result": f"Найдено сетевых интерфейсов: {num.value} (Win32 Return Code: {ret})",
                }

            elif "Kernel32" in entry.binary_or_namespace:
                k32 = ctypes.windll.kernel32
                tick = k32.GetTickCount64()
                uptime_hours = round(tick / (1000 * 3600), 2)
                return {
                    "status": "ok",
                    "probe_target": entry.name,
                    "native_function": "GetTickCount64",
                    "result": f"Аптайм системы Windows: {uptime_hours} ч (TickCount64: {tick})",
                }

            elif "Advapi32" in entry.binary_or_namespace:
                adv = ctypes.windll.advapi32
                # Проверка открытия SCM
                hscm = adv.OpenSCManagerW(None, None, 0x0004)  # SC_MANAGER_ENUMERATE_SERVICE
                if hscm:
                    adv.CloseServiceHandle(hscm)
                    return {
                        "status": "ok",
                        "probe_target": entry.name,
                        "native_function": "OpenSCManagerW",
                        "result": "Успешное подключение к Service Control Manager (SCM)",
                    }
                return {
                    "status": "warning",
                    "probe_target": entry.name,
                    "result": "Не удалось открыть SCM с текущими правами",
                }

            else:
                return {
                    "status": "ok",
                    "probe_target": entry.name,
                    "result": f"Интерфейс {entry.binary_or_namespace} зарегистрирован в каталоге и готов к вызову.",
                }

        except Exception as exc:
            logger.error(f"[WindowsApiDispatcher] Ошибка выполнения зонда {api_id}: {exc}")
            return {"status": "error", "message": str(exc)}
