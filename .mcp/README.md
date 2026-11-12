# 🔌 Серверы Model Context Protocol (`.mcp/`)

**Описание:** Пакет локальных и гибридных серверов протокола **Model Context Protocol (MCP)** на базе официального SDK `mcp.server.MCPServer` (v2) и Node.js/TypeScript для интеграции инструментов AI Windows Admin (ai-tc) с внешними ИИ-клиентами (Google Antigravity, Claude Desktop, Cursor, VS Code).

**Статус:** ✅ Production Ready  
**Версия:** 2.0  
**Автор:** hypo69  
**Updated:** 2026-10-31 17:08:00

---

## 🏗️ Архитектура

Все Python MCP-серверы в директории `.mcp/` построены по единому инженерному стандарту:
- Используют официальный класс **`MCPServer`** (`from mcp.server import MCPServer`, MCP Python SDK v2).
- Все вызовы к ИИ-моделям маршрутизируются строго через единый фасад **`UnifiedChatModel`** (`src.ai.orchestration.unified_chat`).
- Сетевые порты, хосты и идентификаторы моделей считываются динамически из корневого `config.json` через [`config_helper.py`](config_helper.py) без жесткого кодирования (No Hardcode).
- Логирование выполняется централизованно через `from logger import logger` (вывод в консоль по запросу — через `logger.console()`).

### Зарегистрированные серверы и модули

| Модуль / Сервер | Назначение | Основные инструменты (`@mcp.tool`) |
|---|---|---|
| [`ssh_mcp_server.py`](ssh_mcp_server.py) | Точка запуска универсального SSH MCP Server (`ssh_mcp`) для администрирования Windows и Linux | 72 инструмента (`ssh_connect`, `exec_command`, `service_status`, `fs_read_file` и др.) |
| [`langchain_mcp_server.py`](langchain_mcp_server.py) | Автономный ReAct-агент (`MediaSearchAgent`) и инструменты поиска/RAG | `agent_query`, `agent_web_search`, `agent_rag_search`, `agent_python_eval`, `agent_file_read` |
| [`gemini_search_mcp_server.py`](gemini_search_mcp_server.py) | Поиск через облачный провайдер Google Gemini и аудит пула API-ключей | `gemini_web_search`, `gemini_key_pool_status` |
| [`gemini_cli_search_mcp_server.py`](gemini_cli_search_mcp_server.py) | Поиск через терминальный агент Google Gemini CLI | `gemini_cli_web_search` |
| [`agy_search_mcp_server.py`](agy_search_mcp_server.py) | Агентный поиск и анализ через Google Antigravity SDK (`agy`) | `agy_web_search` |
| [`fastapi_mcp_server.py`](fastapi_mcp_server.py) | Мост к REST API центрального FastAPI-сервера (`/api/chat`, `/api/media`, `/api/torrents`) | `fastapi_chat`, `fastapi_media_list`, `fastapi_qbittorrent_info` |
| [`unicorn_mcp_server.py`](unicorn_mcp_server.py) | Управление жизненным циклом фонового ASGI/Uvicorn сервера (`Run-Unicorn.ps1`) | `unicorn_start`, `unicorn_stop`, `unicorn_status` |
| [`example_mcp_server.py`](example_mcp_server.py) | Эталонный диагностический сервер проверки окружения, портов и SSL-сертификатов | `get_project_info`, `get_directories`, `check_server_status`, `read_config_value`, `read_env_variable`, `list_certs` |
| [`config_helper.py`](config_helper.py) | Вспомогательный модуль чтения `config.json`, `.env` и генератор клиентских конфигураций | CLI: `--list`, `--json`, `--generate` |
| [`auto_commits.py`](auto_commits.py) | Фоновая служба отслеживания модификаций файлов и создания атомарных Git-коммитов | `scan_modified_files`, `commit_if_dirty` |
| [`server.js`](server.js) | Вспомогательный Node.js HTTP-мост для безопасных pre-commit операций и записи файлов | `POST /precommit`, `POST /apply` |
| [`playwright/`](playwright/README.md) | TypeScript-сервер оркестрации Playwright MCP | `GET /health`, `POST /precommit`, `POST /apply` |

---

## 🚀 Использование

### 1. Генерация конфигурации для клиентов MCP

Утилита [`config_helper.py`](config_helper.py) автоматически формирует пути для всех серверов каталога `.mcp/`:

```powershell
# Вывести список всех зарегистрированных MCP-серверов
py .mcp/config_helper.py --list

# Сгенерировать готовую JSON-конфигурацию mcpServers
py .mcp/config_helper.py --json
```

### 2. Запуск отдельного MCP-сервера (STDIO)

```powershell
# Запуск сервера поиска Google Gemini
py .mcp/gemini_search_mcp_server.py

# Запуск SSH MCP Server
py .mcp/ssh_mcp_server.py --transport stdio

# Запуск LangChain ReAct-агента
py .mcp/langchain_mcp_server.py
```

### 3. Программное использование `config_helper`

```python
from .config_helper import (
    get_certs_dir,
    get_config_value,
    get_data_dir,
    get_env_var,
    get_project_root,
    get_server_url,
    is_port_open,
)

# Получение URL центрального FastAPI-сервера из config.json
server_url = get_server_url()

# Проверка доступности порта сервера
port_ready = is_port_open()
```

---

## 📂 Файловая структура

- `__init__.py` — Инициализация пакета `.mcp` и экспорт публичного API `config_helper`
- `agy_search_mcp_server.py` — MCP-сервер поиска через Google Antigravity (`UnifiedChatModel`)
- `auto_commits.py` — Служба мониторинга изменений и автокоммитов Git
- `config_helper.py` — Чтение `config.json`, `.env`, проверка портов и CLI-генератор конфигов
- `example_mcp_server.py` — Эталонный кроссплатформенный диагностический MCP-сервер
- `fastapi_mcp_server.py` — MCP-клиент к REST API основного сервера FastAPI
- `gemini_cli_search_mcp_server.py` — MCP-сервер поиска через Google Gemini CLI
- `gemini_search_mcp_server.py` — MCP-сервер поиска через Google Gemini и статуса пула ключей
- `langchain_mcp_server.py` — MCP-сервер автономного LangChain ReAct-агента
- `ssh_mcp_server.py` — Точка запуска `ssh_mcp` из каталога `.mcp/`
- `unicorn_mcp_server.py` — MCP-сервер управления процессом Uvicorn (`Run-Unicorn.ps1`)
- `server.js` — Node.js Express сервер безопасного применения правок и автокоммитов
- `playwright/` — TypeScript-модуль оркестрации Playwright MCP

---

## 🔗 Связанные модули и документация

- [`../ssh_mcp/README.md`](../ssh_mcp/README.md) — Полная документация ядра SSH MCP Server
- [`../src/ai/agents/mcp_client.py`](../src/ai/agents/mcp_client.py) — Клиентский менеджер подключения MCP-серверов в LangChain
- [`../apps/windows/api/routers/admin/mcp.py`](../apps/windows/api/routers/admin/mcp.py) — REST API управления реестром MCP-серверов в WebGUI
- [`../docs/ru/mcp/index.md`](../docs/ru/mcp/index.md) — Руководство по архитектуре подсистемы MCP
