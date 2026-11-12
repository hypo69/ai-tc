# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Эталонный кроссплатформенный MCP-сервер (example_mcp_server.py)
# =============================================================================
# Description:
#   Демонстрационный и диагностический MCP-сервер (STDIO) на базе
#   MCP Python SDK v2 (`MCPServer`), реализующий стандартные паттерны
#   работы с конфигурацией, переменными окружения и SSL-сертификатами
#   в Windows, Linux и macOS.
#
#   Зачем нужен этот модуль:
#     1. Эталонный шаблон для разработки новых MCP-серверов в соответствии
#        с инженерными стандартами проекта (`ENGINEERING.md`, `DOCUMENTATION.md`).
#     2. Предоставление диагностических MCP-инструментов для проверки путей,
#        доступности порта FastAPI-сервера и установленных SSL-сертификатов.
#
# Usage Examples:
#   Python API:
#     from .example_mcp_server import get_project_info, check_server_status
#     info_json = get_project_info()
#
# File: example_mcp_server.py
# Project: AI Windows Admin (ai-tc)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:06:00
# =============================================================================

from __future__ import annotations

import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp.server import MCPServer

from logger import logger

try:
    from .config_helper import (
        get_certs_dir,
        get_config_value,
        get_data_dir,
        get_env_var,
        get_project_root,
        get_server_url,
        is_port_open,
        load_config,
    )
except ImportError:
    from config_helper import (
        get_certs_dir,
        get_config_value,
        get_data_dir,
        get_env_var,
        get_project_root,
        get_server_url,
        is_port_open,
        load_config,
    )

mcp = MCPServer("Example-Server")


@mcp.tool(
    name="get_project_info",
    description="Получить общую информацию о проекте, платформе и конфигурации (кроссплатформенно)",
)
def get_project_info() -> str:
    """Получение диагностических сведений о проекте и окружении Python.

    Returns:
        str: JSON-строка с метаданными проекта (`project_root`, `platform`, `server_url`).

    Examples:
        >>> data = json.loads(get_project_info())
        >>> "project_root" in data
        True
    """
    try:
        root = get_project_root()
        config = load_config()
        info = {
            "project_root": str(root),
            "app_name": config.get("app_name", "ai-tc"),
            "platform": sys.platform,
            "python_version": sys.version,
            "config_exists": (root / "config.json").exists(),
            "env_exists": (root / ".env").exists(),
            "server_url": get_server_url(),
        }
        return json.dumps(info, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка получения сведений о проекте: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="get_directories",
    description="Получить пути к ключевым директориям проекта, сертификатов и данных",
)
def get_directories() -> str:
    """Получение кроссплатформенных путей к основным директориям приложения.

    Returns:
        str: JSON-строка со словарем путей (`project_root`, `certs_dir`, `data_dir`, `home`).

    Examples:
        >>> dirs = json.loads(get_directories())
        >>> "data_dir" in dirs
        True
    """
    try:
        dirs = {
            "project_root": str(get_project_root()),
            "certs_dir": str(get_certs_dir()),
            "data_dir": str(get_data_dir()),
            "home": str(Path.home()),
        }
        return json.dumps(dirs, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка получения директорий: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="check_server_status",
    description="Проверить сетевой статус и открытость порта основного сервера FastAPI",
)
def check_server_status() -> str:
    """Проверка доступности сетевого порта центрального сервера FastAPI.

    Returns:
        str: JSON-строка со статусом сервера (`server_url`, `port`, `is_open`, `status`).

    Examples:
        >>> status = json.loads(check_server_status())
        >>> "is_open" in status
        True
    """
    try:
        server_url = get_server_url()
        port = int(get_config_value("server.port", 0) or 0)
        host = str(get_config_value("server.host", "127.0.0.1")).strip() or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        is_open = is_port_open(host=host, port=port) if port > 0 else False
        status = {
            "server_url": server_url,
            "host": host,
            "port": port,
            "is_open": is_open,
            "status": "Running" if is_open else "Not responding",
        }
        return json.dumps(status, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка проверки статуса сервера: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="read_config_value",
    description="Прочитать значение параметра из config.json по ключу с точечной нотацией",
)
def read_config_value(key_path: str) -> str:
    """Чтение параметра из файла `config.json` по иерархическому пути.

    Args:
        key_path (str): Путь ключей через точку (например, `'server.port'`).

    Returns:
        str: Строка со значением параметра или сообщение об ошибке.

    Examples:
        >>> "server.port" in read_config_value("server.port")
        True
    """
    if not key_path or not key_path.strip():
        return "Ошибка: Не указан путь ключа (key_path)"
    try:
        value = get_config_value(key_path.strip(), "")
        return f"Значение для '{key_path.strip()}': {value}"
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка чтения конфигурации: {exc}")
        return f"Ошибка: {exc}"


@mcp.tool(
    name="read_env_variable",
    description="Прочитать значение переменной окружения из системы или .env",
)
def read_env_variable(var_name: str) -> str:
    """Чтение переменной окружения по её имени.

    Args:
        var_name (str): Имя переменной окружения.

    Returns:
        str: Значение переменной или сообщение об её отсутствии.

    Examples:
        >>> "APP_NAME" in read_env_variable("APP_NAME")
        True
    """
    if not var_name or not var_name.strip():
        return "Ошибка: Не указано имя переменной окружения"
    try:
        clean_name = var_name.strip()
        value = get_env_var(clean_name, "")
        if value:
            return f"Переменная окружения '{clean_name}': {value}"
        return f"Переменная окружения '{clean_name}' не найдена"
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка чтения переменной окружения: {exc}")
        return f"Ошибка: {exc}"


@mcp.tool(
    name="list_certs",
    description="Получить список установленных SSL-сертификатов в системной директории сертификатов",
)
def list_certs() -> str:
    """Получение списка файлов SSL-сертификатов (`.pem`, `.crt`) в директории сертификатов.

    Returns:
        str: Форматированный список найденных сертификатов или уведомление об их отсутствии.

    Examples:
        >>> isinstance(list_certs(), str)
        True
    """
    try:
        certs_dir = get_certs_dir()
        if not certs_dir.exists():
            return f"Директория сертификатов не существует: {certs_dir}"
        certs = sorted(list(certs_dir.glob("*.pem")) + list(certs_dir.glob("*.crt")))
        if not certs:
            return f"Сертификаты не найдены в {certs_dir}"
        lines = [f"Сертификаты в {certs_dir}:"]
        for cert in certs:
            lines.append(f"  - {cert.name}")
        return "\n".join(lines)
    except Exception as exc:
        logger.error(f"[example_mcp_server] Ошибка получения списка сертификатов: {exc}")
        return f"Ошибка: {exc}"


def main() -> int:
    """Запуск эталонного MCP-сервера в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    logger.info(f"[example_mcp_server] Запуск Example MCPServer (платформа={sys.platform})...")
    try:
        mcp.run(transport="stdio")
        return 0
    except KeyboardInterrupt:
        logger.info("[example_mcp_server] Сервер остановлен пользователем")
        return 0
    except Exception as exc:
        logger.error(f"[example_mcp_server] Критическая ошибка сервера: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
