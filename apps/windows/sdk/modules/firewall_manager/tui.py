# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Firewall_Manager - Tui
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.firewall_manager.tui import FirewallManagerTUI
#
#     service = FirewallManagerTUI()
#
# File: tui.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.firewall_manager
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
from apps.windows.sdk.modules.firewall_manager.core.manager import FirewallManager


class FirewallManagerTUI:
    """Консольный интерфейс отображения брандмауэра."""

    def __init__(self, manager: FirewallManager | None = None) -> None:
        self.manager = manager or FirewallManager()
        self.console = Console()

    def render_dashboard(self) -> None:
        """Отображение сводного дашборда брандмауэра."""
        report = self.manager.generate_report()

        prof_text = "\n".join([
            f"[bold cyan]{p.profile_type} Profile:[/bold cyan] "
            f"[{'green' if p.enabled else 'red'}]{'ВКЛЮЧЕН' if p.enabled else 'ОТКЛЮЧЕН'}[/{'green' if p.enabled else 'red'}] "
            f"(Inbound: {p.default_inbound_action}, Outbound: {p.default_outbound_action})"
            for p in report.profiles
        ])

        panel = Panel(
            prof_text + f"\n\n[bold white]Всего правил:[/bold white] {report.total_rules} (Inbound: {report.active_inbound_rules}, Outbound: {report.active_outbound_rules})",
            title='Состояние профилей Windows Defender Firewall',
            style='blue'
        )

        table = Table(title='Правила фильтрации трафика', header_style='bold cyan')
        table.add_column('Имя правила')
        table.add_column('Направление', justify='center')
        table.add_column('Действие', justify='center')
        table.add_column('Протокол', justify='center')
        table.add_column('Порт', justify='center')

        for r in report.rules:
            act_color = 'green' if r.action.lower() == 'allow' else 'red'
            table.add_row(
                r.name,
                r.direction,
                f"[{act_color}]{r.action}[/{act_color}]",
                r.protocol,
                r.local_port or '*'
            )

        self.console.logger.console(Panel('[bold white]AI-Windows-Admin: Windows Defender Firewall Center[/bold white]', style='blue'))
        self.console.logger.console(panel)
        self.console.logger.console(table)


__all__ = ['FirewallManagerTUI']

