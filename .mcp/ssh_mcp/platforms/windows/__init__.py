# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета адаптеров платформы Windows
# =============================================================================
# Description:
#   Экспорт всех доменных адаптеров ОС Windows.
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:54:15
# =============================================================================

from .events import WindowsEventsAdapter
from .executor import WindowsExecutor
from .filesystem import WindowsFilesystemAdapter
from .network import WindowsNetworkAdapter
from .processes import WindowsProcessAdapter
from .services import WindowsServiceAdapter
from .system import WindowsSystemAdapter
from .users import WindowsUserAdapter

__all__ = [
    "WindowsEventsAdapter",
    "WindowsExecutor",
    "WindowsFilesystemAdapter",
    "WindowsNetworkAdapter",
    "WindowsProcessAdapter",
    "WindowsServiceAdapter",
    "WindowsSystemAdapter",
    "WindowsUserAdapter",
]
