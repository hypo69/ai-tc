# 🛠️ Руководство по интеграции MCP Серверов

Данное руководство объясняет, как подключить серверы Model Context Protocol (MCP) из каталога `.mcp/` к внешним AI-ассистентам.

---

## ⚙️ Утилита автоматической конфигурации (`config_helper.py`)

В репозитории предусмотрен скрипт `.mcp/config_helper.py`, который автоматически генерирует пути и настройки для различных клиентов.

### Использование

```powershell
# Просмотр доступных серверов
py .mcp/config_helper.py --list

# Вывод конфигурации в формате JSON
py .mcp/config_helper.py --json
```

---

## 🖥️ Подключение к Claude Desktop

Файл конфигурации Claude Desktop находится по пути:
`%APPDATA%\Claude\claude_desktop_config.json`

### Пример конфигурации:

```json
{
  "mcpServers": {
    "aitc-fastapi": {
      "command": "py",
      "args": ["C:/Users/onela/AppData/Local/ai-tc/.mcp/fastapi_mcp_server.py"]
    },
    "aitc-gemini": {
      "command": "py",
      "args": ["C:/Users/onela/AppData/Local/ai-tc/.mcp/gemini_search_mcp_server.py"]
    },
    "aitc-langchain": {
      "command": "py",
      "args": ["C:/Users/onela/AppData/Local/ai-tc/.mcp/langchain_mcp_server.py"]
    }
  }
}
```

---

## 💻 Подключение к Cursor / VS Code

В Cursor или VS Code с поддержкой MCP добавьте конфигурацию в `.cursor/mcp.json` или глобальные настройки расширения:

```json
{
  "mcpServers": {
    "ai-windows-admin-tools": {
      "command": "py",
      "args": [
        "${workspaceFolder}/.mcp/gemini_cli_search_mcp_server.py"
      ]
    }
  }
}
```

---

## 🧪 Тестирование и отладка MCP серверов

Для интерактивной отладки и проверки работы инструментов вы можете использовать официальный инспектор MCP:

```powershell
# Запуск MCP Inspector для проверки сервера
npx @modelcontextprotocol/inspector py .mcp/gemini_search_mcp_server.py
```

---

## 📚 Связанные разделы

- [Каталог MCP серверов](catalog.md) — полный список серверов и инструментов.
- [Обзор MCP](index.md) — архитектура интеграции.
- Руководство разработчика — общая инструкция для разработчиков.