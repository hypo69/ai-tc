# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Конфигурационный помощник MCP-серверов (config_helper.py)
# =============================================================================
# Description:
#   Кроссплатформенный модуль управления конфигурацией, сетевыми адресами,
#   путями сертификатов и генерацией клиентских настроек для серверов MCP.
#
#   Зачем нужен этот модуль:
#     1. Единая точка доступа к `config.json` и переменным окружения `.env`
#        для всех серверов в `.mcp/` без дублирования кода чтения файлов.
#     2. Исключение жесткого кодирования (No Hardcode): динамическое извлечение
#        хоста, порта и протокола сервера из корневого `config.json`.
#     3. Генерация готовых JSON-конфигураций для подключения MCP-серверов
#        в Claude Desktop, Cursor, VS Code и Google Antigravity (`--list`, `--json`, `--generate`).
#
# Usage Examples:
#   Python API:
#     from config_helper import get_server_url, get_config_value, is_port_open
#     url = get_server_url()
#     port = get_config_value("server.port", 0)
#
# File: config_helper.py
# Project: AI Windows Admin (ai-tc)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:05:00
# =============================================================================

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from header import __root__
from logger import logger
from src.utils.jjson import j_loads


def get_project_root() -> Path:
    """Определение корневой директории проекта AI Windows Admin.

    Поиск выполняется через глобальный маркер `__root__` из `header.py`,
    переменную окружения `AIWINDOWSADMIN_DIR` или проверку наличия `config.json`.

    Returns:
        Path: Абсолютный путь к корневой директории проекта.

    Examples:
        >>> root = get_project_root()
        >>> (root / "config.json").exists()
        True
    """
    if "AIWINDOWSADMIN_DIR" in os.environ and os.environ["AIWINDOWSADMIN_DIR"].strip():
        env_path = Path(os.environ["AIWINDOWSADMIN_DIR"]).resolve()
        if env_path.exists():
            return env_path
    if (__root__ / "config.json").exists():
        return __root__
    if (_PROJECT_ROOT / "config.json").exists():
        return _PROJECT_ROOT
    return Path.cwd()


def load_config(config_path: Optional[Path] = False) -> Dict[str, Any]:  # type: ignore[assignment]
    """Загрузка публичной конфигурации проекта из файла `config.json`.

    Args:
        config_path (Optional[Path]): Пользовательский путь к файлу конфигурации.
                                      Значение по умолчанию: False (используется корневой `config.json`).

    Returns:
        Dict[str, Any]: Словарь параметров конфигурации или пустой словарь `{}` при ошибке.

    Examples:
        >>> cfg = load_config()
        >>> isinstance(cfg, dict)
        True
    """
    target_path = config_path if isinstance(config_path, Path) else (get_project_root() / "config.json")
    if not target_path.exists():
        logger.warning(f"[config_helper] Файл конфигурации не найден: {target_path}")
        return {}
    try:
        loaded = j_loads(target_path, ordered=False)
        return dict(loaded) if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.error(f"[config_helper] Ошибка чтения конфигурации {target_path}: {exc}")
        return {}


def get_config_value(key_path: str, default: Any = "") -> Any:
    """Извлечение значения из конфигурации по иерархическому пути через точку.

    Args:
        key_path (str): Путь к ключу в точечной нотации (например, `'server.port'`).
        default (Any): Значение по умолчанию, если ключ не найден.
                       Значение по умолчанию: ''.

    Returns:
        Any: Найденное значение параметра или `default`.

    Examples:
        >>> port = get_config_value("server.port", 0)
        >>> isinstance(port, int)
        True
    """
    if not key_path or not key_path.strip():
        return default
    config = load_config()
    if not config:
        return default
    current: Any = config
    for key in key_path.strip().split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def get_server_url() -> str:
    """Формирование базового URL сервера FastAPI на основе параметров `config.json`.

    Returns:
        str: Полный URL сервера (например, `'http://127.0.0.1:8001'`) или `''` при отсутствии настроек.

    Examples:
        >>> url = get_server_url()
        >>> url.startswith("http")
        True
    """
    host = str(get_config_value("server.host", "")).strip()
    port = get_config_value("server.port", 0)
    if not host or not port:
        logger.error("[config_helper] В config.json отсутствуют обязательные параметры server.host или server.port")
        return ""
    if host == "0.0.0.0":
        host = "127.0.0.1"
    use_ssl = bool(get_config_value("server.use_ssl", False))
    configured_proto = str(get_config_value("server.protocol", "")).strip().lower()
    protocol = "https" if use_ssl else (configured_proto if configured_proto in ("http", "https") else "http")
    return f"{protocol}://{host}:{port}"


def get_env_var(key: str, default: str = "") -> str:
    """Безопасное получение переменной окружения из системы или файла `.env`.

    Приоритет разрешения: системное окружение `os.environ` -> файл `.env` -> `default`.

    Args:
        key (str): Имя переменной окружения.
        default (str): Значение по умолчанию при отсутствии переменной.
                       Значение по умолчанию: ''.

    Returns:
        str: Значение переменной окружения или `default`.

    Examples:
        >>> val = get_env_var("APP_NAME", "ai-tc")
        >>> len(val) > 0
        True
    """
    if not key or not key.strip():
        return default
    clean_key = key.strip()
    if clean_key in os.environ and os.environ[clean_key]:
        return os.environ[clean_key]
    env_file = get_project_root() / ".env"
    if not env_file.exists():
        return default
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            env_key, env_value = line.split("=", 1)
            if env_key.strip() == clean_key:
                return env_value.strip().strip('"').strip("'")
    except Exception as exc:
        logger.warning(f"[config_helper] Не удалось прочитать .env файл: {exc}")
    return default


def get_certs_dir() -> Path:
    """Получение кроссплатформенного пути к директории локальных SSL-сертификатов.

    Returns:
        Path: Путь к директории сертификатов текущей ОС.

    Examples:
        >>> certs = get_certs_dir()
        >>> isinstance(certs, Path)
        True
    """
    if sys.platform == "win32":
        return Path.home() / ".certs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Certs"
    return Path.home() / ".local" / "share" / "ca-certificates"


def get_data_dir() -> Path:
    """Получение кроссплатформенного пути к директории данных приложения.

    Returns:
        Path: Абсолютный путь к директории `data` приложения.

    Examples:
        >>> data_path = get_data_dir()
        >>> data_path.name == "data"
        True
    """
    app_name = str(get_config_value("app_name", get_env_var("APP_NAME", "ai-tc"))).strip() or "ai-tc"
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(localappdata) / app_name / "data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name / "data"
    return Path.home() / ".local" / "share" / app_name / "data"


def is_port_open(host: str = "", port: int = 0, timeout: float = 1.0) -> bool:
    """Проверка доступности TCP-порта на указанном сетевом узле.

    Если `host` или `port` не переданы, значения автоматически считываются из `config.json`.

    Args:
        host (str): IP-адрес или доменное имя узла.
                    Значение по умолчанию: '' (считывается `server.host` из конфига).
        port (int): Номер проверяемого TCP-порта.
                    Значение по умолчанию: 0 (считывается `server.port` из конфига).
        timeout (float): Максимальное время ожидания отклика сокета в секундах.
                         Значение по умолчанию: 1.0.

    Returns:
        bool: `True`, если соединение установлено успешно; иначе `False`.

    Examples:
        >>> isinstance(is_port_open("127.0.0.1", 65530, timeout=0.1), bool)
        True
    """
    target_host = host.strip() if host else str(get_config_value("server.host", "127.0.0.1")).strip()
    if target_host == "0.0.0.0":
        target_host = "127.0.0.1"
    target_port = port if port > 0 else int(get_config_value("server.port", 0) or 0)
    if not target_host or target_port <= 0:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((target_host, target_port)) == 0
    except Exception:
        return False


def get_registered_mcp_servers() -> List[Dict[str, str]]:
    """Получение списка локальных Python MCP-серверов в директории `.mcp/`.

    Returns:
        List[Dict[str, str]]: Список словарей с метаданными серверов (`id`, `script`, `path`).

    Examples:
        >>> servers = get_registered_mcp_servers()
        >>> len(servers) > 0
        True
    """
    mcp_dir = get_project_root() / ".mcp"
    servers: List[Dict[str, str]] = []
    for file_path in sorted(mcp_dir.glob("*_mcp_server.py")):
        server_id = f"aitc-{file_path.stem.replace('_mcp_server', '').replace('_', '-')}"
        servers.append(
            {
                "id": server_id,
                "script": file_path.name,
                "path": str(file_path.resolve()).replace("\\", "/"),
            }
        )
    return servers


def build_client_mcp_config() -> Dict[str, Any]:
    """Генерация JSON-структуры `mcpServers` для подключения в Claude Desktop / Cursor.

    Returns:
        Dict[str, Any]: Готовый словарь с секцией `mcpServers`.

    Examples:
        >>> cfg = build_client_mcp_config()
        >>> "mcpServers" in cfg
        True
    """
    root_str = str(get_project_root().resolve()).replace("\\", "/")
    python_cmd = "py" if sys.platform == "win32" else "python3"
    mcp_servers: Dict[str, Any] = {}
    for srv in get_registered_mcp_servers():
        mcp_servers[srv["id"]] = {
            "command": python_cmd,
            "args": [srv["path"]],
            "cwd": root_str,
        }
    return {"mcpServers": mcp_servers}


def main(argv: Optional[List[str]] = []) -> int:
    """Точка входа CLI для инспекции и генерации конфигурации MCP-серверов.

    Args:
        argv (Optional[List[str]]): Аргументы командной строки.
                                    Значение по умолчанию: [].

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> main(["--list"])
        0
    """
    parser = argparse.ArgumentParser(description="Утилита конфигурации MCP-серверов AI Windows Admin")
    parser.add_argument("--list", action="store_true", help="Вывести список доступных MCP-серверов")
    parser.add_argument("--json", action="store_true", help="Вывести JSON-конфигурацию для клиентов MCP")
    parser.add_argument("--generate", action="store_true", help="Сгенерировать и вывести полную конфигурацию")
    args = parser.parse_args(argv if argv else [])

    if args.list:
        for srv in get_registered_mcp_servers():
            logger.console(f"{srv['id']}: {srv['path']}")
        return 0

    if args.json or args.generate:
        logger.console(json.dumps(build_client_mcp_config(), ensure_ascii=False, indent=2))
        return 0

    logger.console(json.dumps(build_client_mcp_config(), ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "build_client_mcp_config",
    "get_certs_dir",
    "get_config_value",
    "get_data_dir",
    "get_env_var",
    "get_project_root",
    "get_registered_mcp_servers",
    "get_server_url",
    "is_port_open",
    "load_config",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
