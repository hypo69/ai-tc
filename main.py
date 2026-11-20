# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc - Main WebGUI & API Entrypoint
# =============================================================================
# Description:
#   Главная точка входа в систему ai-tc (WebGUI и FastAPI сервер).
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
# Project: ai-tc
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:37:00
# =============================================================================

from __future__ import annotations
"""Главная точка входа для WebGUI и FastAPI сервера ai-tc."""

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple
import webbrowser

from src.utils.asyncio_windows_patch import apply_windows_asyncio_patch

try:
    from apps.windows.core.engine_adapter import ElectronEngineAdapter
except ImportError:
    ElectronEngineAdapter = None


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
        if ElectronEngineAdapter is not None:
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
                            f"[ElectronEngineAdapter] Процесс Electron завершился с кодом {proc.returncode}, переключение на браузер"
                        )
                    else:
                        logger.console(f"[INFO] Запущена оболочка Electron (PID {launch_info.get('pid')})")
                        if server_thread:
                            try:
                                while server_thread.is_alive():
                                    if proc and proc.poll() is not None:
                                        if proc.returncode == 0 and el_adapter.get_running_pids():
                                            server_thread.join(timeout=1.0)
                                            continue
                                        break
                                    server_thread.join(timeout=1.0)
                            except (KeyboardInterrupt, SystemExit):
                                pass
                            finally:
                                el_adapter.terminate_running_instances()
                            return
                else:
                    logger.warning(f"[ElectronEngineAdapter] Не удалось запустить Electron: {launch_info.get('error')}")
            else:
                logger.warning("[ElectronEngineAdapter] Рантайм Electron не найден, переключение на браузер")

    if engine == "webview2":
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

    # По умолчанию ("browser") или fallback: открытие системного браузера без подъема тяжелого WebView2 runtime
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


def is_port_occupied(port: int) -> bool:
    """Проверяет, слушается ли указанный TCP порт другим процессом.

    Args:
        port: Номер TCP порта.

    Returns:
        bool: True, если порт прослушивается.
    """
    try:
        import psutil
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return True
    except Exception:
        pass
    return False


def manage_cloudflare_tunnel(
    enable: bool = False,
    restart: bool = False,
    public_url: str = "https://kino.davidka.net",
) -> None:
    """Управляет жизненным циклом фонового туннеля Cloudflare Tunnel.

    Args:
        enable: Флаг необходимости запуска туннеля.
        restart: Флаг принудительного перезапуска.
        public_url: Публичный адрес доступа.
    """
    if not enable:
        logger.info("  [☁️ Cloudflare] Запуск туннеля отключен")
        return

    running_pids: list[int] = []
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if (proc.info.get('name') or '').lower() == 'cloudflared.exe':
                    running_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as exc:
        logger.debug(f"[Cloudflare] Ошибка проверки psutil: {exc}")

    cf_launcher = EXE_DIR / "launchers" / "Run-Cloudflared.ps1"

    if restart or not running_pids:
        if cf_launcher.is_file():
            logger.info(f"  [☁️ Cloudflare] Запуск туннеля для {public_url}...")
            try:
                cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(cf_launcher)]
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            except Exception as exc:
                logger.warning(f"  [WARN] Ошибка запуска Cloudflare Tunnel: {exc}")
        else:
            logger.warning(f"  [WARN] Скрипт {cf_launcher} не найден")
    else:
        pids_str = ", ".join(map(str, running_pids))
        logger.info(f"  [☁️ Cloudflare] Туннель активен (PID: {pids_str}) -> {public_url}")


def resolve_tab_url(base_url: str, tab: Optional[str] = None, panel: Optional[str] = None) -> str:
    """Формирует канонический URL вкладки и подпанели ai-tc.

    Args:
        base_url: Базовый URL сервера (например, http://127.0.0.1:8000/tc).
        tab: Идентификатор вкладки (например, tab-about-system).
        panel: Идентификатор подпанели.

    Returns:
        str: Полный URL с хеш-маршрутом.
    """
    clean_base = base_url.split('#')[0].rstrip('/')
    t_ = (tab or "tab-about-system").strip().lstrip('#')
    if t_ == "tab-process-manager":
        t_ = "tab-processes-load-inspector"

    if panel:
        clean_panel = panel.strip().lstrip('#')
        return f"{clean_base}#{t_}#{clean_panel}"
    return f"{clean_base}#{t_}"


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
        description="ai-tc WebGUI & API Server Entrypoint",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-H', '--host', '--address', dest='host', type=str, default=None, help='Хост веб-сервера (по умолчанию 127.0.0.1)')
    parser.add_argument('-P', '--port', dest='port', type=int, default=None, help='Порт веб-сервера (по умолчанию 8000)')
    parser.add_argument('-C', '--config', type=str, default=None, help='Путь к конфигурационному файлу config.json')
    parser.add_argument('--engine', type=str, default='electron', choices=['electron', 'webview2', 'browser', 'headless'], help='Движок GUI (по умолчанию electron)')
    parser.add_argument('--browser', action='store_true', help='Запуск в системном браузере (shortcut для --engine browser)')
    parser.add_argument('--electron', action='store_true', help='Запуск в оболочке Electron (по умолчанию)')
    parser.add_argument('--headless', action='store_true', help='Запуск без GUI (shortcut для --engine headless)')
    parser.add_argument('--no-browser', dest='no_browser', action='store_true', help='Отключить автоматическое открытие браузера / GUI')
    parser.add_argument('--tab', type=str, default='tab-about-system', help='Стартовая вкладка веб-интерфейса (по умолчанию tab-about-system)')
    parser.add_argument('--panel', '--subpanel', '--subtab', dest='panel', type=str, default=None, help='Подпанель стартовой вкладки')
    parser.add_argument('-c', '--connect', action='store_true', help='Подключиться к запущенному экземпляру сервера и открыть GUI')
    parser.add_argument('-r', '--restart', action='store_true', help='Перезапустить: принудительно завершить процесс на порту и поднять новый')
    parser.add_argument('--with-cloudflare', '--cloudflare', dest='cloudflare', action='store_true', help='Запуск туннеля Cloudflare')
    parser.add_argument('--no-cloudflare', dest='no_cloudflare', action='store_true', help='Принудительно отключить туннель Cloudflare')
    parser.add_argument('--restart-cloudflare', action='store_true', help='Перезапустить туннель Cloudflare')
    parser.add_argument('--public-url', type=str, default='https://kino.davidka.net', help='Публичный адрес Cloudflare Ingress')
    parser.add_argument('--ssl', dest='ssl', action='store_true', default=None, help='Принудительно включить HTTPS (SSL)')
    parser.add_argument('--no-ssl', dest='ssl', action='store_false', help='Принудительно отключить HTTPS (SSL)')
    parser.add_argument('--ssl-cert', dest='ssl_cert', type=str, default=None, help='Путь к сертификату SSL (.pem)')
    parser.add_argument('--ssl-key', dest='ssl_key', type=str, default=None, help='Путь к приватному ключу SSL (.pem)')
    return parser.parse_args()


def main() -> int:
    """Точка входа запуска WebGUI сервера ai-tc.

    Returns:
        int: Код возврата процесса.
    """
    apply_windows_asyncio_patch()
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

    # Определение эффективного движка графической оболочки
    if args.headless or args.no_browser:
        effective_engine = 'headless'
    elif args.browser:
        effective_engine = 'browser'
    elif args.electron:
        effective_engine = 'electron'
    else:
        effective_engine = args.engine or 'electron'

    proto = "https" if use_ssl else "http"
    browser_host = "localhost" if host == "0.0.0.0" else host
    base_url = f"{proto}://{browser_host}:{port}/tc"
    tc_url = resolve_tab_url(base_url, tab=args.tab, panel=args.panel)

    # Режим подключения к работающему серверу без подъема нового процесса
    if args.connect:
        if is_port_occupied(port):
            logger.console(f"[INFO] Подключение к работающему серверу на порту {port} -> {tc_url}")
            launch_gui(tc_url, effective_engine, Path('.'), Path('.'))
            return 0
        logger.warning(f"[WARN] Сервер на порту {port} не обнаружен, запуск нового экземпляра...")

    # Управление фоновым туннелем Cloudflare
    should_start_cf = (args.cloudflare or args.restart_cloudflare) and not args.no_cloudflare
    manage_cloudflare_tunnel(
        enable=should_start_cf,
        restart=bool(args.restart_cloudflare),
        public_url=args.public_url,
    )

    setup_ai_environment(cfg)
    free_port_if_occupied(port)
    launch_dedicated_apps(cfg)

    logger.info("=" * 60)
    logger.info(" ai-tc (WebGUI Server Mode)")
    logger.info(f"  Хост: {host}")
    logger.info(f"  Порт: {port}")
    logger.info(f"  URL:  {tc_url}")
    logger.info(f"  GUI Engine: {effective_engine}")
    logger.info(f"  Cloudflare Ingress: {args.public_url}")
    logger.info("=" * 60)

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
    time.sleep(1.0)  # Дать серверу подняться

    launch_gui(tc_url, effective_engine, Path('.'), Path('.'), server_thread=server_thread)
    return 0


if __name__ == "__main__":
    sys.exit(main())

