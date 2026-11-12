# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Модульные тесты серверов и утилит каталога .mcp/ (test_mcp_servers.py)
# =============================================================================
# Description:
#   Набор юнит-тестов для проверки соответствия всех серверов и модулей `.mcp/`
#   инженерным стандартам проекта (No None Rule, MCPServer v2 SDK, UnifiedChatModel,
#   Dynamic Config from config.json, Early Return).
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что все серверы в `.mcp/` импортируются и регистрируют
#        инструменты на базе `mcp.server.MCPServer` (SDK v2).
#     2. Проверка корректного чтения `config.json` через `config_helper.py`,
#        работы CLI (`--list`, `--json`), безопасности путей и обработки ошибок.
#
# Usage Examples:
#   Pytest:
#     pytest tests/test_mcp_servers.py -v
#
# File: test_mcp_servers.py
# Project: AI Windows Admin (ai-tc)
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:09:00
# =============================================================================

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mcp.server import MCPServer

from header import __root__

_MCP_DIR: Path = __root__ / ".mcp"


def _load_mcp_module(module_filename: str) -> Any:
    """Динамическая загрузка модуля из директории `.mcp/`.

    Args:
        module_filename (str): Имя файла в каталоге `.mcp/` (например, `'config_helper.py'`).

    Returns:
        Any: Загруженный модуль Python.

    Examples:
        >>> mod = _load_mcp_module("config_helper.py")
        >>> hasattr(mod, "get_project_root")
        True
    """
    file_path = _MCP_DIR / module_filename
    module_name = f"mcp_pkg_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Не удалось создать спецификацию для {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_none_keyword_in_mcp_python_files() -> None:
    """Проверка соблюдения правила 'No None Rule' во всех `.py` файлах каталога `.mcp/`."""
    for py_file in sorted(_MCP_DIR.glob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        assert "None" not in content, f"Обнаружено запрещенное слово None в файле {py_file.name}"
        assert "# Updated:" in content, f"Отсутствует метка времени Updated в шапке {py_file.name}"


def test_config_helper_functions() -> None:
    """Проверка функций чтения конфигурации, путей и генерации конфига в `config_helper.py`."""
    cfg_helper = _load_mcp_module("config_helper.py")

    root = cfg_helper.get_project_root()
    assert isinstance(root, Path)
    assert (root / "config.json").exists()

    cfg = cfg_helper.load_config()
    assert isinstance(cfg, dict)
    assert "server" in cfg

    port = cfg_helper.get_config_value("server.port", 0)
    assert isinstance(port, int) and port > 0

    missing = cfg_helper.get_config_value("non.existent.key", "fallback_val")
    assert missing == "fallback_val"

    server_url = cfg_helper.get_server_url()
    assert server_url.startswith("http")
    assert str(port) in server_url

    certs_dir = cfg_helper.get_certs_dir()
    data_dir = cfg_helper.get_data_dir()
    assert isinstance(certs_dir, Path)
    assert isinstance(data_dir, Path)

    servers = cfg_helper.get_registered_mcp_servers()
    assert len(servers) >= 6

    client_cfg = cfg_helper.build_client_mcp_config()
    assert "mcpServers" in client_cfg
    assert "aitc-fastapi" in client_cfg["mcpServers"]
    assert cfg_helper.main(["--list"]) == 0
    assert cfg_helper.main(["--json"]) == 0


def test_all_mcp_servers_use_sdk_v2() -> None:
    """Проверка того, что все MCP-серверы инициализируют экземпляр `MCPServer` (SDK v2)."""
    server_files = [
        "agy_search_mcp_server.py",
        "example_mcp_server.py",
        "fastapi_mcp_server.py",
        "gemini_cli_search_mcp_server.py",
        "gemini_search_mcp_server.py",
        "langchain_mcp_server.py",
        "unicorn_mcp_server.py",
    ]
    for filename in server_files:
        mod = _load_mcp_module(filename)
        assert hasattr(mod, "mcp"), f"В модуле {filename} отсутствует атрибут mcp"
        assert isinstance(mod.mcp, MCPServer), f"Объект mcp в {filename} не является MCPServer v2"


def test_example_mcp_server_tools() -> None:
    """Проверка диагностических инструментов эталонного сервера `example_mcp_server.py`."""
    ex_mod = _load_mcp_module("example_mcp_server.py")

    proj_info = json.loads(ex_mod.get_project_info())
    assert proj_info["config_exists"] is True

    dirs_info = json.loads(ex_mod.get_directories())
    assert "project_root" in dirs_info
    assert "certs_dir" in dirs_info

    srv_status = json.loads(ex_mod.check_server_status())
    assert "port" in srv_status
    assert "status" in srv_status

    cfg_val = ex_mod.read_config_value("server.port")
    assert "server.port" in cfg_val

    assert "Ошибка" in ex_mod.read_config_value("")
    assert "Ошибка" in ex_mod.read_env_variable("")
    assert isinstance(ex_mod.list_certs(), str)


def test_search_mcp_servers_validation_and_mocked_execution() -> None:
    """Проверка валидации пустых запросов и вызова `UnifiedChatModel` в поисковых MCP-серверах."""
    agy_mod = _load_mcp_module("agy_search_mcp_server.py")
    cli_mod = _load_mcp_module("gemini_cli_search_mcp_server.py")
    gem_mod = _load_mcp_module("gemini_search_mcp_server.py")

    # Проверка Early Return при пустом запросе
    assert json.loads(asyncio.run(agy_mod.agy_web_search("")))["status"] == "error"
    assert json.loads(asyncio.run(cli_mod.gemini_cli_web_search("   ")))["status"] == "error"
    assert json.loads(asyncio.run(gem_mod.gemini_web_search("")))["status"] == "error"

    # Проверка статуса пула ключей Gemini
    pool_status = json.loads(gem_mod.gemini_key_pool_status())
    assert pool_status["status"] in ("ok", "error")

    # Проверка вызова через UnifiedChatModel с моком
    mock_instance = MagicMock()
    mock_instance.ask = AsyncMock(return_value="## Результат поиска")

    with patch.object(agy_mod, "UnifiedChatModel", return_value=mock_instance):
        res_agy = asyncio.run(agy_mod.agy_web_search("тестовый запрос"))
        assert res_agy == "## Результат поиска"

    with patch.object(cli_mod, "UnifiedChatModel", return_value=mock_instance):
        res_cli = asyncio.run(cli_mod.gemini_cli_web_search("тестовый запрос"))
        assert res_cli == "## Результат поиска"

    with patch.object(gem_mod, "UnifiedChatModel", return_value=mock_instance):
        res_gem = asyncio.run(gem_mod.gemini_web_search("тестовый запрос"))
        assert res_gem == "## Результат поиска"


def test_fastapi_and_langchain_and_unicorn_mcp_servers() -> None:
    """Проверка инструментов `fastapi_mcp_server`, `langchain_mcp_server` и `unicorn_mcp_server`."""
    fastapi_mod = _load_mcp_module("fastapi_mcp_server.py")
    lc_mod = _load_mcp_module("langchain_mcp_server.py")
    uni_mod = _load_mcp_module("unicorn_mcp_server.py")

    assert fastapi_mod.get_base_url().startswith("http")
    assert "Пустое сообщение" in asyncio.run(fastapi_mod.fastapi_chat(""))

    assert lc_mod.agent_python_eval("10 + 15") == "25"
    assert "server" in lc_mod.agent_file_read("config.json")
    assert json.loads(asyncio.run(lc_mod.agent_query("")))["action"] == "error"
    assert asyncio.run(lc_mod.agent_rag_search("")) == "[]"

    status_str = asyncio.run(uni_mod.unicorn_status())
    assert "Unicorn" in status_str


def test_auto_commits_file_tracking(tmp_path: Path) -> None:
    """Проверка декомпозированных функций отслеживания файлов в `auto_commits.py`."""
    auto_mod = _load_mcp_module("auto_commits.py")

    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("initial", encoding="utf-8")

    ignored_file = tmp_path / "~temp.txt"
    ignored_file.write_text("ignored", encoding="utf-8")

    state: dict[Path, float] = {}
    # Первый проход фиксирует начальные mtime и возвращает False
    assert auto_mod.scan_modified_files(state, root_dir=tmp_path) is False
    assert sample_file in state
    assert ignored_file not in state

    # Модификация файла со сдвигом mtime
    state[sample_file] -= 10.0
    assert auto_mod.scan_modified_files(state, root_dir=tmp_path) is True
