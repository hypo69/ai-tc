# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Package Init
# =============================================================================
# Description:
#   Экспорт моделей, каталога и сервиса единого реестра Windows API.
#
# Usage Examples:
#   from apps.windows.api_registry import get_api_registry_service, WindowsApiEntry
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.api_registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:57:00
# =============================================================================

from __future__ import annotations
"""Единый реестр и диспетчер Windows API для AI-TC."""

from apps.windows.api_registry.models import (
    ApiFamily,
    ApiRecommendationQuery,
    ApiRecommendationResult,
    PlatformSubsystem,
    PrivilegeLevel,
    RegistryFilterConfig,
    WindowsApiEntry,
)
from apps.windows.api_registry.service import (
    WindowsApiRegistryService,
    get_api_registry_service,
)

__all__ = [
    "ApiFamily",
    "ApiRecommendationQuery",
    "ApiRecommendationResult",
    "PlatformSubsystem",
    "PrivilegeLevel",
    "RegistryFilterConfig",
    "WindowsApiEntry",
    "WindowsApiRegistryService",
    "get_api_registry_service",
]
