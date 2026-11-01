# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI -   Init   Module
# =============================================================================
# Description:
#   Автоматическая регистрация всех агентов.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.ai.agents
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 11:32:00
# =============================================================================

"""Автоматическая регистрация всех агентов.

Этот пакет собирает все классы‑агенты, имена которых оканчиваются на ``Agent``,
и предоставляет словарь ``AGENT_REGISTRY`` для быстрых импортов из CLI, IDE
и серверных компонентов."""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

AGENT_REGISTRY: Dict[str, Type] = {}

def _discover_agents() -> None:
    """Импортирует каждый *.py‑модуль в пакете ``src.ai.agents`` и
    собирает классы‑агенты.
    """
    package_path = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.name.startswith("__"):
            continue
        module_name = f"src.ai.agents.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            # Ошибки импорта не должны ломать инициализацию всего проекта
            continue
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.endswith("Agent"):
                AGENT_REGISTRY[attr_name] = attr

# Выполняем поиск сразу при импорте пакета
_discover_agents()

from .mcp_client import MCPClientManager

# Явный экспорт агентов при их наличии в реестре
MediaSearchAgent = AGENT_REGISTRY.get("MediaSearchAgent")
TravelAgent = AGENT_REGISTRY.get("TravelAgent")

__all__ = ["AGENT_REGISTRY", "MediaSearchAgent", "TravelAgent", "MCPClientManager"]
