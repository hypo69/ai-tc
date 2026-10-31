# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Cloudflared Monitor CLI Main Entry Point
# =============================================================================
# Description:
#   Точка входа CLI для запуска интерактивного TUI дашборда монитора
#   Cloudflare Tunnel, микросервиса FastAPI или быстрой инспекции статуса.
#
# Examples:
#   $ py -m apps.cloudflared_monitor --status
#   $ py -m apps.cloudflared_monitor --status --json
#   $ py -m apps.cloudflared_monitor --logs --limit 30
#   $ py -m apps.cloudflared_monitor --mode server --port 8104
#
# File: __main__.py
# Project: ai-windows-admin
# Package: apps.cloudflared_monitor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""CLI точка входа для Cloudflared Tunnel Monitor."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from logger import logger
from .src.state import CloudflaredState
from .tui import run_cloudflared_dashboard


def _load_config() -> SimpleNamespace:
    """Загружает конфигурацию приложения из config.json."""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.loads(json.dumps(data), object_hook=lambda d: SimpleNamespace(**d))
        except Exception:
            pass
    return SimpleNamespace()


def _run_standalone_server(
    host: str = "127.0.0.1",
    port: int = 8104,
    reload: bool = False,
    workers: int = 1,
) -> None:
    """Запускает Cloudflared Monitor в режиме выделенного FastAPI-сервера."""
    try:
        import uvicorn
        from fastapi import FastAPI
        from .router import init_router

        logger.console(f"[Cloudflared Monitor] Запуск автономного FastAPI сервера...")
        logger.console(f"  Адрес: http://{host}:{port}")
        logger.console(f"  Документация API: http://{host}:{port}/docs\n")

        app = FastAPI(
            title="Cloudflared Tunnel Monitor",
            description="Супервизор Cloudflare Tunnel, анализ логов и диагностика здоровья (kino.davidka.net)",
            version="1.0.0",
        )
        app.include_router(init_router())

        uvicorn.run(app, host=host, port=port, reload=reload, workers=workers, log_level="info")
    except ImportError as exc:
        logger.error(f"Не удалось импортировать модули для сервера: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Ошибка сервера: {exc}")
        sys.exit(1)


def main() -> None:
    """Парсит аргументы командной строки и выполняет запрошенное действие."""
    parser = argparse.ArgumentParser(
        description="AI-Windows-Admin Cloudflare Tunnel Monitor & Diagnostics Workspace"
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["dashboard", "server", "status", "logs", "health"],
        default="dashboard",
        help="Режим работы (по умолчанию: dashboard)",
    )
    parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Вывести текущий статус и завершить работу",
    )
    parser.add_argument(
        "--logs",
        "-l",
        action="store_true",
        help="Вывести последние строки журнала и завершить работу",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Количество строк журнала (по умолчанию: 20)",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Выполнить диагностику здоровья туннеля",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Запустить демон cloudflared",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Остановить демон cloudflared",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Перезапустить демон cloudflared",
    )
    parser.add_argument(
        "--public-url",
        type=str,
        default="",
        help="Переопределить публичный URL для проверки",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=2.0,
        help="Интервал обновления дашборда (сек)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывод данных в формате JSON",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Хост сервера (по умолчанию: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=0,
        help="Порт сервера (по умолчанию: 8104)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Автоперезагрузка сервера при изменениях",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Количество воркеров сервера",
    )

    args = parser.parse_args()
    config = _load_config()
    cf_cfg = getattr(config, "cloudflared", SimpleNamespace())
    effective_url = args.public_url or getattr(cf_cfg, "public_url", "https://kino.davidka.net")

    state = CloudflaredState(public_url=effective_url)

    if args.start:
        success, msg = state.start_tunnel()
        logger.console(f"[{'SUCCESS' if success else 'ERROR'}] {msg}")
        return

    if args.stop:
        success, msg = state.stop_tunnel()
        logger.console(f"[{'SUCCESS' if success else 'ERROR'}] {msg}")
        return

    if args.restart:
        success, msg = state.restart_tunnel()
        logger.console(f"[{'SUCCESS' if success else 'ERROR'}] {msg}")
        return

    if args.status or args.mode == "status":
        state.refresh(probe_network=True)
        if args.json:
            data = {
                "is_running": state.process.is_running,
                "pid": state.process.pid,
                "cpu_percent": state.process.cpu_percent,
                "memory_mb": state.process.memory_mb,
                "uptime_seconds": state.process.uptime_seconds,
                "has_token": state.has_token,
                "public_url": state.public_url,
                "endpoint_reachable": state.endpoint.is_reachable,
                "status_code": state.endpoint.status_code,
                "latency_ms": state.endpoint.response_time_ms,
                "health_score": state.report.health_score if state.report else 0,
            }
            logger.console(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            logger.console("========================================")
            logger.console("  Статус Cloudflare Tunnel (kino.davidka.net)")
            logger.console("========================================")
            logger.console(f"  Демон запущен:  {'ДА' if state.process.is_running else 'НЕТ'}")
            logger.console(f"  PID процесса:   {state.process.pid or 'N/A'}")
            logger.console(f"  CPU / Память:   {state.process.cpu_percent}% / {state.process.memory_mb} MB")
            logger.console(f"  Публичный URL:  {state.public_url}")
            logger.console(f"  Отклик хоста:   {'ДОСТУПЕН' if state.endpoint.is_reachable else 'НЕДОСТУПЕН'} ({state.endpoint.response_time_ms} мс)")
            logger.console(f"  Оценка здоровья: {state.report.health_score if state.report else 'N/A'}/100 ({state.report.status if state.report else 'N/A'})")
            logger.console("========================================")
        return

    if args.logs or args.mode == "logs":
        logs = state.tail_logs(limit=args.limit)
        if args.json:
            logger.console(json.dumps([{"time": e.timestamp, "level": e.level, "msg": e.message} for e in logs], indent=2, ensure_ascii=False))
        else:
            logger.console(f"--- Журнал ({len(logs)} строк) из {state.log_file} ---")
            for entry in logs:
                logger.console(f"[{entry.timestamp}] [{entry.level:5s}] {entry.message}")
        return

    if args.health or args.mode == "health":
        state.refresh(probe_network=True)
        report = state.evaluate_diagnostics()
        if args.json:
            logger.console(
                json.dumps(
                    {
                        "health_score": report.health_score,
                        "status": report.status,
                        "summary": report.summary,
                        "anomalies": [{"title": a.title, "description": a.description, "severity": a.severity} for a in report.anomalies],
                        "recommendations": report.recommendations,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            logger.console(f"Диагностика туннеля: {report.status} ({report.health_score}/100)")
            logger.console(f"Сводка: {report.summary}\n")
            if report.anomalies:
                logger.console("Аномалии:")
                for a in report.anomalies:
                    logger.console(f"  - [{a.severity.upper()}] {a.title}: {a.description}")
            if report.recommendations:
                logger.console("\nРекомендации:")
                for r in report.recommendations:
                    logger.console(f"  - {r}")
        return

    if args.mode == "server":
        server_cfg = getattr(config, "server", SimpleNamespace())
        effective_host = args.host if args.host != "127.0.0.1" else getattr(server_cfg, "host", "127.0.0.1")
        effective_port = args.port if args.port > 0 else getattr(server_cfg, "port", 8104)
        _run_standalone_server(
            host=effective_host,
            port=effective_port,
            reload=args.reload,
            workers=args.workers,
        )
        return

    try:
        asyncio.run(
            run_cloudflared_dashboard(
                interval=args.interval,
                public_url=effective_url,
            )
        )
    except KeyboardInterrupt:
        logger.console("\n[Cloudflared Monitor] Работа завершена пользователем.")
        sys.exit(0)


if __name__ == "__main__":
    main()
