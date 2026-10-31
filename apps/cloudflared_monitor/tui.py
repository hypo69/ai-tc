# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Cloudflared Monitor Rich TUI Dashboard
# =============================================================================
# Description:
#   Интерактивный дашборд терминала для мониторинга туннеля Cloudflare,
#   потокового вывода логов, телеметрии процесса и ИИ-диагностики.
#
# Examples:
#   >>> from apps.cloudflared_monitor.tui import run_cloudflared_dashboard
#   >>> await run_cloudflared_dashboard(interval=2.0)
#
# File: tui.py
# Project: ai-windows-admin
# Package: apps.cloudflared_monitor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""Отрисовка Rich TUI интерфейса для Cloudflared Monitor."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from logger import logger
from .src.state import CloudflaredLogEntry, CloudflaredState

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    Console = Any  # type: ignore
    Layout = Any  # type: ignore
    Live = Any  # type: ignore
    Panel = Any  # type: ignore
    Table = Any  # type: ignore
    Text = Any  # type: ignore
    RICH_AVAILABLE = False


def _render_tunnel_info_table(state: CloudflaredState) -> Table:
    """Отрисовывает таблицу телеметрии туннеля и процесса.

    Args:
        state: Экземпляр CloudflaredState.

    Returns:
        Table: Таблица Rich.
    """
    table = Table(expand=True, show_header=False, box=None, padding=(0, 1))
    table.add_column("Параметр", style="bold cyan", width=22)
    table.add_column("Значение", style="white")

    proc = state.process
    status_style = "bold green" if proc.is_running else "bold red"
    status_str = f"[{status_style}]{'АКТИВЕН / РАБОТАЕТ' if proc.is_running else 'ОСТАНОВЛЕН'}[/{status_style}]"

    table.add_row("Статус демона", status_str)
    table.add_row("PID процесса", str(proc.pid) if proc.pid else "[dim]N/A[/dim]")
    table.add_row("Использование CPU", f"{proc.cpu_percent:.1f}%")
    table.add_row("Память RSS", f"{proc.memory_mb:.1f} MB ({proc.memory_percent:.1f}%)")
    table.add_row("Потоков", str(proc.num_threads))
    uptime_h = round(proc.uptime_seconds / 3600, 2)
    table.add_row("Время работы", f"{uptime_h} ч ({int(proc.uptime_seconds)} с)")
    table.add_row("Время старта", proc.start_time or "[dim]N/A[/dim]")

    table.add_row("─" * 20, "─" * 30)

    token_color = "green" if state.has_token else "red"
    table.add_row("Токен туннеля", f"[{token_color}]{state.token_preview}[/{token_color}]")
    table.add_row("Путь к bin", state.exe_path or "[red]Не найден в PATH[/red]")
    table.add_row("Публичный URL", f"[bold underline cyan]{state.public_url}[/bold underline cyan]")

    ep = state.endpoint
    if ep.is_reachable:
        code_color = "green" if (ep.status_code and ep.status_code < 400) else "yellow"
        ep_status = f"[{code_color}]HTTP {ep.status_code}[/{code_color}] ({ep.response_time_ms} мс)"
    else:
        ep_status = f"[red]Недоступен[/red] ({ep.error_message or 'Сбой соединения'})"

    table.add_row("Отклик Ingress", ep_status)
    table.add_row("Активных коннекторов", f"[bold green]{state.active_connections_count}[/bold green]")
    table.add_row("Ошибок / Предупреждений", f"[red]{state.total_errors_in_log}[/red] / [yellow]{state.total_warnings_in_log}[/yellow]")

    return table


def _render_log_table(logs: List[CloudflaredLogEntry]) -> Table:
    """Отрисовывает таблицу последних записей лога.

    Args:
        logs: Список распарсенных строк лога.

    Returns:
        Table: Таблица Rich.
    """
    table = Table(title="Журнал cloudflared.log (Tail)", expand=True, header_style="bold cyan", border_style="bright_black")
    table.add_column("Время", style="dim", width=19)
    table.add_column("Уровень", width=8, justify="center")
    table.add_column("Conn", style="dim magenta", width=6)
    table.add_column("Сообщение", style="white", min_width=30)

    if not logs:
        table.add_row("-", "[dim]INFO[/dim]", "-", "[dim]Журнал пока пуст.[/dim]")
        return table

    for entry in logs[:18]:
        lvl = entry.level.upper()
        if lvl in ("ERR", "ERROR"):
            lvl_fmt = "[bold red]ERR[/bold red]"
            msg_fmt = f"[red]{entry.message}[/red]"
        elif lvl in ("WRN", "WARN", "WARNING"):
            lvl_fmt = "[bold yellow]WRN[/bold yellow]"
            msg_fmt = f"[yellow]{entry.message}[/yellow]"
        elif lvl in ("DBG", "DEBUG"):
            lvl_fmt = "[dim]DBG[/dim]"
            msg_fmt = f"[dim]{entry.message}[/dim]"
        else:
            lvl_fmt = "[green]INF[/green]"
            msg_fmt = entry.message

        table.add_row(
            entry.timestamp[-19:] if len(entry.timestamp) >= 19 else entry.timestamp,
            lvl_fmt,
            entry.connection_id or "-",
            msg_fmt,
        )

    return table


def render_ui(state: CloudflaredState) -> Any:
    """Строит общий композитный макет интерфейса Rich TUI.

    Args:
        state: Экземпляр CloudflaredState.

    Returns:
        Any: Сконфигурированный объект Layout.
    """
    if not RICH_AVAILABLE:
        return None

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )

    layout["main"].split_row(
        Layout(name="left_panel", ratio=2),
        Layout(name="right_panel", ratio=3),
    )

    layout["right_panel"].split_column(
        Layout(name="logs", ratio=3),
        Layout(name="diagnostics", ratio=2),
    )

    proc = state.process
    status_label = "ONLINE" if proc.is_running else "OFFLINE"
    status_style = "bold green" if proc.is_running else "bold red"
    rep = state.report
    score_val = rep.health_score if rep else 0
    score_color = "green" if score_val >= 80 else ("yellow" if score_val >= 50 else "red")

    header_text = Text.assemble(
        ("МОНИТОРИНГ И СУПЕРВИЗИЯ CLOUDFLARE TUNNEL\n", "bold cyan"),
        (f"Хост: {state.public_url} | Демон: ", "dim"),
        (f"[{status_label}] ", status_style),
        (f"| Здоровье: [{score_val}/100] | ", f"bold {score_color}"),
        (f"Ошибок в логе: {state.total_errors_in_log}", "yellow" if state.total_errors_in_log else "dim"),
    )
    layout["header"].update(Panel(header_text, border_style="cyan"))

    info_table = _render_tunnel_info_table(state)
    layout["left_panel"].update(Panel(info_table, title="⚙️ Телеметрия процесса туннеля", border_style="blue"))

    log_table = _render_log_table(state.logs)
    layout["logs"].update(Panel(log_table, border_style="bright_black"))

    diag_content = Text()
    if rep:
        diag_color = "green" if rep.health_score >= 80 else ("yellow" if rep.health_score >= 50 else "red")
        diag_content.append(f"Диагностика: {rep.status} ({rep.health_score}/100)\n", style=f"bold {diag_color}")
        diag_content.append(f"{rep.summary}\n\n", style="white")

        if rep.anomalies:
            diag_content.append("⚠️ Замеченные аномалии:\n", style="bold yellow")
            for a in rep.anomalies:
                diag_content.append(f" • [{a.severity.upper()}] {a.title}: {a.description}\n", style="white")
        else:
            diag_content.append("✅ Сбоев и аномалий в работе не обнаружено.\n", style="green")

        if rep.recommendations:
            diag_content.append("\n💡 Рекомендации:\n", style="bold cyan")
            for r in rep.recommendations:
                diag_content.append(f" • {r}\n", style="dim")
    else:
        diag_content.append("Ожидание первого цикла сбора данных...", style="dim")

    layout["diagnostics"].update(Panel(diag_content, title="🤖 Диагностика и рекомендации", border_style="magenta"))

    footer_text = Text(
        " [Ctrl+C] Выход  |  Опрос состояния каждые 2.0 с  |  Проверка URL: https://kino.davidka.net",
        style="dim white",
    )
    layout["footer"].update(Panel(footer_text, border_style="bright_black"))

    return layout


async def run_cloudflared_dashboard(
    interval: float = 2.0,
    public_url: str = "https://kino.davidka.net",
    max_iterations: Optional[int] = None,
) -> None:
    """Запускает живой интерактивный дашборд в терминале.

    Args:
        interval: Частота обновления экрана в секундах.
        public_url: Публичный хост для мониторинга.
        max_iterations: Ограничение итераций (для тестов).
    """
    if not RICH_AVAILABLE:
        logger.warning("Для интерактивного TUI требуется библиотека rich.")
        return

    console = Console()
    state = CloudflaredState(public_url=public_url)
    state.refresh(probe_network=True)

    iterations = 0
    with Live(render_ui(state), console=console, refresh_per_second=4, screen=True) as live:
        try:
            while True:
                probe_net = (iterations % 5 == 0)
                state.refresh(probe_network=probe_net)
                live.update(render_ui(state))
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                await asyncio.sleep(interval)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
