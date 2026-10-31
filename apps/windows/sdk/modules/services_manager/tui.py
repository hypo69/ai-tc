# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Services_Manager - Tui
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.services_manager.tui import ServicesManagerTUI
#
#     service = ServicesManagerTUI()
#
# File: tui.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.services_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:44
# =============================================================================

from __future__ import annotations
from logger import logger
"""# Description:"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from apps.windows.sdk.modules.services_manager.core.manager import ServicesManager


class ServicesManagerTUI:
    """Консольный интерфейс отображения служб Windows."""

    def __init__(self, manager: ServicesManager | None = None) -> None:
        self.manager = manager or ServicesManager()
        self.console = Console()

    def render_dashboard(self, limit: int = 25) -> None:
        """Отображение сводного дашборда служб."""
        report = self.manager.generate_report()

        panel = Panel(
            f"[bold white]Всего служб:[/bold white] {report.total_services} | "
            f"[bold green]Работает (Running):[/bold green] {report.running_services} | "
            f"[bold yellow]Остановлено:[/bold yellow] {report.stopped_services} | "
            f"[bold cyan]Автозапуск:[/bold cyan] {report.auto_start_services}",
            title='Сводка Служб Windows (Service Control Manager)',
            style='blue'
        )

        table = Table(title=f'Системные службы (первые {limit})', header_style='bold cyan')
        table.add_column('Имя службы')
        table.add_column('Отображаемое имя')
        table.add_column('Статус', justify='center')
        table.add_column('Тип запуска', justify='center')
        table.add_column('PID', justify='center')

        for s in report.services[:limit]:
            st_color = 'green' if s.status == 'RUNNING' else 'dim'
            table.add_row(
                s.name,
                s.display_name[:40],
                f"[{st_color}]{s.status}[/{st_color}]",
                s.start_type,
                str(s.pid) if s.pid else '-'
            )

        self.console.logger.console(Panel('[bold white]AI-Windows-Admin: Windows Services Control Center[/bold white]', style='blue'))
        self.console.logger.console(panel)
        self.console.logger.console(table)


__all__ = ['ServicesManagerTUI']

