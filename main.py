# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin - Main WebGUI & API Entrypoint
# =============================================================================
# Description:
#   Главная точка входа в систему AI-Windows-Admin (WebGUI и FastAPI сервер).
#   Управляет конфигурацией, освобождением портов, запуском выделенных служб
#   и стартом веб-интерфейса через Uvicorn.
#
# Usage Examples:
#   CLI:
#     python main.py
#     python main.py --host 127.0.0.1 --port 8000
#     python main.py --no-browser
#
# File: main.py
# Project: ai-windows-admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:20:00
# =============================================================================

from __future__ import annotations
"""Главная точка входа для WebGUI и FastAPI сервера AI-Windows-Admin."""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import webbrowser
import logging
import os
import shutil
import subprocess
import sys
import webbrowser
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def launch_gui(
    url: str,
    engine: str,
    profile_path: Path,
    cache_path: Path,
    server_thread: Optional[threading.Thread] = None,
) -> None:
    """Запускает графическую оболочку (Electron, WebView2 или системный браузер).

    Args:
        url: URL веб-приложения для отображения.
        engine: Идентификатор движка оболочки ("electron", "webview2", "browser", "headless").
        profile_path: Путь к пользовательскому профилю Chromium / WebView2.
        cache_path: Путь к дисковому кэшу.
        server_thread: Поток фонового сервера (если запущен локально).
    """
    if engine == "headless":
        logger.console(f"[INFO] Headless mode, UI available at {url}")
        if server_thread:
            try:
                while server_thread.is_alive():
                    server_thread.join(timeout=1.0)
            except (KeyboardInterrupt, SystemExit):
                pass
        return

    if engine == "electron":
        # import of AI Assistant removed – not applicable in this project
        el_adapter = ElectronEngineAdapter()
        if el_adapter._find_electron_binary():
            launch_info = el_adapter.launch_shell(
                url=url,
                force_fresh=bool(server_thread),
                profile_path=profile_path,
                cache_path=cache_path,
            )
            if launch_info.get("status") == "launched":
                proc = launch_info.get("process")
                time.sleep(0.5)
                if proc and proc.poll() is not None and proc.returncode != 0:
                    logger.warning(
                        f"[ElectronEngineAdapter] Process exited with code {proc.returncode}, falling back to browser"
                    )
                else:
                    logger.console(f"[INFO] Electron launched (PID {launch_info.get('pid')})")
                    if server_thread:
                        try:
                            while server_thread.is_alive():
                                if proc and proc.poll() is not None:
                                    break
                                server_thread.join(timeout=1.0)
                        except (KeyboardInterrupt, SystemExit):
                            pass
                        finally:
                            el_adapter.terminate_running_instances()
                        return
    # Attempt to launch WebView2 (pywebview)
    try:
        import webview
        # Setup system tray for WebView2
        def _setup_webview_tray(window: Any, is_force_exit: list[bool]) -> None:
            """Инициализирует и запускает системный трей для окна WebView2."""
            try:
                import pystray
                from PIL import Image
                icon_path = Path(__file__).parent / "assets" / "icon256.png"
                if not icon_path.exists():
                    icon_path = Path(__file__).parent / "assets" / "favicon.ico"
                img = Image.open(icon_path) if icon_path.exists() else Image.new("RGBA", (64, 64), (37, 99, 235, 255))
                tray_state: Dict[str, Any] = {"tray": None}
                def _on_show(icon: Any, item: Any = None) -> None:
                    window.show()
                    window.restore()
                def _on_quit(icon: Any, item: Any = None) -> None:
                    is_force_exit[0] = True
                    if tray_state["tray"]:
                        tray_state["tray"].stop()
                    window.destroy()
                menu = pystray.Menu(
                    pystray.MenuItem("Показать AI Assistant", _on_show, default=True),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Выход", _on_quit),
                )
                tray = pystray.Icon("AIAssistant", img, "AI Assistant", menu)
                tray_state["tray"] = tray
                tray.run()
            except Exception as exc:
                logger.warning(f"[WARN] Не удалось инициализировать системный трей pywebview: {exc}")
        # Окно открывается развёрнутым на весь экран (100%)
        window = webview.create_window("AI Assistant", url, width=1200, height=800, maximized=True)
        is_force_exit = [False]
        def _on_closing() -> bool:
            if not is_force_exit[0]:
                window.hide()
                return False
            return True
        window.events.closing += _on_closing
        threading.Thread(target=_setup_webview_tray, args=(window, is_force_exit), daemon=True).start()
        webview.start(storage_path=str(profile_path), private_mode=False)
        return
    except Exception as exc:
        logger.warning(f"[WARN] Окно WebView недоступно ({exc}). Запуск в браузере: {url}")

    # Fallback to system browser
    import webbrowser
    webbrowser.open(url)
    if server_thread:
        try:
            while server_thread.is_alive():
                server_thread.join(timeout=1.0)
        except (KeyboardInterrupt, SystemExit):
            pass
# 1. Настройка кодировки UTF-8 для Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 2. Определение базовой директории приложения (с поддержкой PyInstaller _MEIPASS)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
    PROJECT_ROOT = EXE_DIR
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    BASE_DIR = PROJECT_ROOT
    EXE_DIR = PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["AIBREADBOARD_DIR"] = str(EXE_DIR)
os.environ["ASSIST_DIR"] = str(EXE_DIR)
os.environ["ENABLE_OAUTH"] = "false"
os.environ["DISABLE_AUTH"] = "true"

try:
    from logger import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("main_server")


def free_port_if_occupied(port: int) -> None:
    """Освобождает указанный TCP порт, завершая конфликтные процессы.

    Args:
        port: Номер TCP порта для освобождения.
    """
    try:
        import psutil
        occupied_pids = set()
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                if conn.pid != os.getpid() and conn.pid != 0:
                    occupied_pids.add(conn.pid)

        for pid in occupied_pids:
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()
                proc.kill()
                logger.info(f"[OK] Освобожден порт {port} (завершен процесс {proc_name}, PID {pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"[WARN] Не удалось завершить процесс PID {pid} на порту {port}: {e}")
    except Exception as e:
        logger.warning(f"[WARN] Проверка порта {port} через psutil не удалась: {e}")


def ensure_external_config(exe_dir: Path, base_dir: Path) -> Path:
    """Проверяет наличие внешнего config.json в директории с .exe и копирует при отсутствии.

    Args:
        exe_dir: Путь к исполняемой директории.
        base_dir: Базовая директория проекта.

    Returns:
        Path: Путь к целевому файлу конфигурации.
    """
    target_config = exe_dir / "config.json"
    if not target_config.is_file():
        source_candidates = [
            base_dir / "config.json",
            base_dir / "apps" / "windows" / "api" / "config.json",
            base_dir / "start_scenarios_config" / "tc.json",
        ]
        for src in source_candidates:
            if src.is_file():
                try:
                    shutil.copy2(src, target_config)
                    logger.info(f"[OK] Внешний файл конфигурации скопирован: {target_config} (из {src.name})")
                    return target_config
                except Exception as exc:
                    logger.warning(f"[WARN] Не удалось скопировать {src} -> {target_config}: {exc}")
    return target_config


def load_config(config_arg: Optional[str] = None) -> Tuple[Dict[str, Any], Path]:
    """Загружает конфигурационный файл config.json / tc.json.

    Args:
        config_arg: Пользовательский путь к файлу конфигурации.

    Returns:
        Tuple[Dict[str, Any], Path]: Словарь конфигурации и путь к файлу.
    """
    ensure_external_config(EXE_DIR, BASE_DIR)

    possible_paths = []
    if config_arg:
        possible_paths.append(Path(config_arg))
        possible_paths.append(EXE_DIR / config_arg)
        possible_paths.append(BASE_DIR / config_arg)

    possible_paths.extend([
        EXE_DIR / "config.json",
        EXE_DIR / "start_scenarios_config" / "tc.json",
        BASE_DIR / "config.json",
        BASE_DIR / "apps" / "windows" / "api" / "config.json",
        BASE_DIR / "start_scenarios_config" / "tc.json",
    ])

    config_file = None
    for p in possible_paths:
        if p.is_file():
            config_file = p
            break

    cfg: Dict[str, Any] = {}
    if config_file:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            logger.info(f"[OK] Конфигурация загружена: {config_file}")
        except Exception as e:
            logger.error(f"[ERROR] Ошибка чтения конфигурации {config_file}: {e}")
    else:
        logger.warning("[WARN] Файл конфигурации config.json/tc.json не найден, используются значения по умолчанию")

    return cfg, (config_file or (EXE_DIR / "config.json"))


def setup_ai_environment(cfg: Dict[str, Any]) -> None:
    """Экспортирует AI-переменные окружения для Gemini и AGY из ai_providers_and_models_configuration.

    Args:
        cfg: Словарь системной конфигурации.
    """
    ai_cfg = cfg.get("ai_providers_and_models_configuration") or cfg.get("ai", {})
    provider = ai_cfg.get("default_provider") or ai_cfg.get("provider")
    if provider:
        os.environ["AI_PROVIDER"] = str(provider)

    providers = ai_cfg.get("providers", {})
    if isinstance(providers, dict):
        gemini_cfg = providers.get("gemini", {})
        if isinstance(gemini_cfg, dict) and gemini_cfg.get("model"):
            os.environ["AI_GEMINI_MODEL"] = str(gemini_cfg["model"])

        gemini_cli_cfg = providers.get("gemini_cli", {})
        if isinstance(gemini_cli_cfg, dict) and (gemini_cli_cfg.get("model") or gemini_cli_cfg.get("default_model")):
            os.environ["AI_GEMINI_CLI_MODEL"] = str(gemini_cli_cfg.get("model") or gemini_cli_cfg.get("default_model"))

        agy_cfg = providers.get("agy", {})
        if isinstance(agy_cfg, dict):
            if agy_cfg.get("model"):
                os.environ["AI_AGY_MODEL"] = str(agy_cfg["model"])
            if agy_cfg.get("effort"):
                os.environ["AI_AGY_EFFORT"] = str(agy_cfg["effort"])
    elif isinstance(ai_cfg, dict):
        if ai_cfg.get("gemini", {}).get("model"):
            os.environ["AI_GEMINI_MODEL"] = str(ai_cfg["gemini"]["model"])
        if ai_cfg.get("gemini_cli", {}).get("model"):
            os.environ["AI_GEMINI_CLI_MODEL"] = str(ai_cfg["gemini_cli"]["model"])
        if ai_cfg.get("agy", {}).get("model"):
            os.environ["AI_AGY_MODEL"] = str(ai_cfg["agy"]["model"])
        if ai_cfg.get("agy", {}).get("effort"):
            os.environ["AI_AGY_EFFORT"] = str(ai_cfg["agy"]["effort"])


def launch_dedicated_apps(cfg: Dict[str, Any]) -> None:
    """Запускает выделенные подприложения из списка apps.enabled.

    Args:
        cfg: Словарь системной конфигурации.
    """
    apps_cfg = cfg.get("apps", {})
    enabled_apps = apps_cfg.get("enabled", [])
    disabled_apps = set(apps_cfg.get("disabled", []))
    launchers_dir = EXE_DIR / "launchers"

    for app_name in enabled_apps:
        if app_name in disabled_apps:
            continue

        app_cfg_paths = [
            EXE_DIR / "apps" / app_name / "config.json",
            EXE_DIR / "apps" / "windows" / app_name / "config.json",
            BASE_DIR / "apps" / app_name / "config.json",
            BASE_DIR / "apps" / "windows" / app_name / "config.json",
        ]
        app_cfg_file = next((p for p in app_cfg_paths if p.is_file()), None)
        if not app_cfg_file:
            continue

        try:
            with open(app_cfg_file, 'r', encoding='utf-8') as f:
                app_cfg = json.load(f)

            is_dedicated = (
                app_cfg.get("server", {}).get("dedicated") is True
                or app_cfg.get("server", {}).get("mode", "").lower() == "dedicated"
            )
            launcher = app_cfg.get("launcher")

            if is_dedicated and launcher:
                logger.info(f"Запуск dedicated-приложения: {app_name} ({launcher})...")
                launcher_path = launchers_dir / launcher
                if launcher_path.is_file():
                    if launcher_path.suffix.lower() == ".ps1":
                        cmd = [
                            "powershell.exe",
                            "-NoProfile",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            str(launcher_path),
                            "-Action",
                            "start",
                        ]
                    else:
                        cmd = [sys.executable, str(launcher_path), "--action", "start"]
                    subprocess.Popen(
                        cmd,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
                    )
        except Exception as e:
            logger.warning(f"[WARN] Ошибка запуска приложения {app_name}: {e}")


def parse_arguments() -> argparse.Namespace:
    """Парсит аргументы командной строки веб-сервера.

    Returns:
        argparse.Namespace: Распарсенные аргументы запуска.
    """
    parser = argparse.ArgumentParser(
        description="AI-Windows-Admin WebGUI & API Server Entrypoint",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-H', '--host', '--address', dest='host', type=str, default=None, help='Хост веб-сервера (по умолчанию 127.0.0.1)')
    parser.add_argument('-P', '--port', dest='port', type=int, default=None, help='Порт веб-сервера (по умолчанию 8000)')
    parser.add_argument('-C', '--config', type=str, default=None, help='Путь к конфигурационному файлу config.json')
    parser.add_argument('--no-browser', dest='no_browser', action='store_true', help='Отключить автоматическое открытие браузера')
    parser.add_argument('--engine', type=str, default='browser', choices=['electron', 'webview2', 'browser', 'headless'], help='Движок GUI')
    parser.add_argument('--ssl', dest='ssl', action='store_true', default=None, help='Принудительно включить HTTPS (SSL)')
    parser.add_argument('--no-ssl', dest='ssl', action='store_false', help='Принудительно отключить HTTPS (SSL)')
    parser.add_argument('--ssl-cert', dest='ssl_cert', type=str, default=None, help='Путь к сертификату SSL (.pem)')
    parser.add_argument('--ssl-key', dest='ssl_key', type=str, default=None, help='Путь к приватному ключу SSL (.pem)')
    return parser.parse_args()


def main() -> int:
    """Точка входа запуска WebGUI сервера AI-Windows-Admin.

    Returns:
        int: Код возврата процесса.
    """
    args = parse_arguments()
    cfg, config_path = load_config(args.config)

    server_cfg = cfg.get("server", {})
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or int(server_cfg.get("port", 8000))
    if args.ssl is not None:
        use_ssl = bool(args.ssl)
    else:
        use_ssl = (
            server_cfg.get("protocol", "").lower() == "https"
            or server_cfg.get("use_ssl") is True
        )

    ssl_certfile: Optional[str] = args.ssl_cert or server_cfg.get("ssl_certfile")
    ssl_keyfile: Optional[str] = args.ssl_key or server_cfg.get("ssl_keyfile")

    if use_ssl:
        if not ssl_certfile or not Path(os.path.expanduser(ssl_certfile)).is_file():
            default_cert = Path.home() / ".certs" / "localhost+2.pem"
            if default_cert.is_file():
                ssl_certfile = str(default_cert)
        else:
            ssl_certfile = str(Path(os.path.expanduser(ssl_certfile)).resolve())

        if not ssl_keyfile or not Path(os.path.expanduser(ssl_keyfile)).is_file():
            default_key = Path.home() / ".certs" / "localhost+2-key.pem"
            if default_key.is_file():
                ssl_keyfile = str(default_key)
        else:
            ssl_keyfile = str(Path(os.path.expanduser(ssl_keyfile)).resolve())

        if ssl_certfile and ssl_keyfile and Path(ssl_certfile).is_file() and Path(ssl_keyfile).is_file():
            logger.info(f"  [🔒 SSL Active]: Cert={ssl_certfile}, Key={ssl_keyfile}")
        else:
            logger.warning("  [WARN] SSL включен, но файлы сертификатов не найдены. Запуск без SSL.")
            use_ssl = False

    try:
        rel_config_path = str(config_path.relative_to(EXE_DIR))
    except Exception:
        rel_config_path = str(config_path)

    os.environ["CONFIG_FILE"] = rel_config_path
    os.environ["AIBREADBOARD_CONFIG"] = rel_config_path

    setup_ai_environment(cfg)
    free_port_if_occupied(port)
    launch_dedicated_apps(cfg)

    proto = "https" if use_ssl else "http"
    browser_host = "localhost" if host == "0.0.0.0" else host
    tc_url = f"{proto}://{browser_host}:{port}/tc"

    logger.info("=" * 60)
    logger.info(" AI-Windows-Admin (WebGUI Server Mode)")
    logger.info(f"  Хост: {host}")
    logger.info(f"  Порт: {port}")
    logger.info(f"  URL:  {tc_url}")
    logger.info("  Cloudflare Ingress: https://kino.davidka.net")
    logger.info("=" * 60)

    # Browser launch handled by launch_gui; no direct opening here.
    pass
    import uvicorn
    from apps.windows.api.server import get_app

    app = get_app()
    def _run_server():
        uvicorn_kwargs: dict[str, Any] = {
            "host": host,
            "port": port,
            "log_level": "info",
            "access_log": True,
        }
        if use_ssl and ssl_certfile and ssl_keyfile:
            uvicorn_kwargs["ssl_certfile"] = ssl_certfile
            uvicorn_kwargs["ssl_keyfile"] = ssl_keyfile
        uvicorn.run(app, **uvicorn_kwargs)

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    time.sleep(1.0)  # allow server to start

    launch_gui(tc_url, args.engine, Path('.'), Path('.'), server_thread=server_thread)
    return 0


if __name__ == "__main__":
    sys.exit(main())

