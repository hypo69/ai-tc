# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Data Models
# =============================================================================
# Description:
#   Модели данных для каталога Windows API, WinRT namespaces, Win32 DLL, COM,
#   WMI/CIM, ETW и интеллектуального диспетчера системных интерфейсов.
#
# Usage Examples:
#   from apps.windows.api_registry.models import WindowsApiEntry, PlatformSubsystem
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.api_registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:53:00
# =============================================================================

from __future__ import annotations
"""Модели данных реестра Windows API и интеллектуального диспетчера."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApiFamily(str, Enum):
    """Семейство API операционной системы Windows."""
    WIN32 = "win32"               # Нативные Win32 DLL (Kernel32, Advapi32, User32, Iphlpapi, Psapi...)
    WINRT = "winrt"               # Windows Runtime (Windows.Graphics, Windows.Media, Windows.Devices...)
    COM = "com"                   # Component Object Model (TaskScheduler, VSS, Firewall...)
    WMI_CIM = "wmi_cim"           # WMI / CIM репозиторий классов (root/cimv2, root/standardcimv2)
    ETW = "etw"                   # Event Tracing for Windows (ядро, провайдеры событий)
    DIRECTX = "directx"           # DirectX / DXGI / Direct3D графический стек
    WFP = "wfp"                   # Windows Filtering Platform (сетевая фильтрация)
    APP_SDK = "app_sdk"           # Windows App SDK (Microsoft.Windows.*)


class PlatformSubsystem(str, Enum):
    """Шесть ключевых подсистем платформенного слоя Windows в AI-TC."""
    HARDWARE_DEVICES = "hardware_devices"       # Hardware & Devices (CPU, GPU, RAM, PCI, USB, Sensors)
    SYSTEM_DIAGNOSTICS = "system_diagnostics"   # System Diagnostics (Processes, Services, Events, ETW)
    NETWORK_INTELLIGENCE = "network_intel"      # Network Intelligence (Adapters, TCP/IP, DNS, Routing, Firewall)
    GRAPHICS_VISION = "graphics_vision"         # Graphics & Vision (Screen Capture, Imaging, OCR, GPU)
    SECURITY_INTELLIGENCE = "security_intel"    # Security Intelligence (Tokens, ACL, UAC, Audit, Defender)
    STORAGE_INTELLIGENCE = "storage_intel"      # Storage Intelligence (Disks, Volumes, SMART, VSS)


class PrivilegeLevel(str, Enum):
    """Требуемый уровень привилегий для вызова API."""
    USER = "user"                 # Обычный непривилегированный пользователь
    ADMIN = "admin"               # Администратор (UAC Elevation)
    SYSTEM = "system"             # NT AUTHORITY\SYSTEM / Драйвер ядра


class WindowsApiEntry(BaseModel):
    """Карточка системного API в реестре Windows."""
    id: str = Field(description="Уникальный системный ID (например, 'iphlpapi_adapters')")
    name: str = Field(description="Человекочитаемое имя API или библиотеки")
    family: ApiFamily = Field(description="Семейство интерфейса (Win32, WinRT, COM, etc.)")
    subsystem: PlatformSubsystem = Field(description="Подсистема AI-TC Platform Layer")
    binary_or_namespace: str = Field(description="Имя системной DLL или WinRT namespace (например, 'Iphlpapi.dll')")
    description: str = Field(description="Назначение и сценарии применения в системной диагностике")
    functions: List[str] = Field(default_factory=list, description="Ключевые функции, методы или классы интерфейса")
    min_win_version: str = Field(default="Windows 10", description="Минимальная поддерживаемая версия Windows")
    privileges: PrivilegeLevel = Field(default=PrivilegeLevel.USER, description="Необходимые права")
    python_bindings: List[str] = Field(default_factory=list, description="Доступные Python-привязки (ctypes, pywin32, winsdk, wmi)")
    zero_dependency: bool = Field(default=False, description="Доступно ли через ctypes / стандартную библиотеку без pip-пакетов")
    code_examples: Dict[str, str] = Field(default_factory=dict, description="Примеры кода (python, powershell, csharp)")
    limitations: str = Field(default="", description="Ограничения, подводные камни или изолированные песочницы")
    alternatives: List[str] = Field(default_factory=list, description="Альтернативные интерфейсы для решения схожей задачи")


class ApiRecommendationQuery(BaseModel):
    """Запрос на подбор оптимального системного API под задачу."""
    task_description: str = Field(description="Текстовое описание задачи (например, 'получить список сетевых адаптеров')")
    prefer_zero_dependency: bool = Field(default=True, description="Отдавать приоритет встроенному ctypes без сторонних библиотек")
    require_admin: Optional[bool] = Field(default=None, description="Допускать ли административные привилегии")
    subsystem: Optional[PlatformSubsystem] = Field(default=None, description="Ограничить поиск конкретной подсистемой")


class ApiRecommendationResult(BaseModel):
    """Результат работы интеллектуального диспетчера API."""
    query: str
    recommended_api: WindowsApiEntry
    matched_apis: List[WindowsApiEntry]
    rationale: str = Field(description="Обоснование выбора (скорость, права, доступность)")
    python_snippet: str = Field(description="Готовый к исполнению фрагмент кода на Python")
    powershell_equivalent: str = Field(default="", description="Эквивалентная команда PowerShell")


class RegistryFilterConfig(BaseModel):
    """Пользовательские настройки и фильтры реестра Windows API."""
    prefer_zero_dependency: bool = Field(default=True, description="Приоритет ctypes и встроенных библиотек")
    hide_deprecated: bool = Field(default=True, description="Скрывать устаревшие API")
    max_recommendations: int = Field(default=5, ge=1, le=20, description="Количество кандидатов в ответе")
    preferred_language: str = Field(default="python", description="Основной язык примеров (python, powershell)")
