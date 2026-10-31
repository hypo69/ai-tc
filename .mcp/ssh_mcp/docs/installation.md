# Установка и развёртывание SSH MCP Server

**Версия:** 1.0  
**Updated:** 2026-10-31 17:05:30

## 1. Локальное развёртывание на ai-tc

```powershell
python -m ssh_mcp --transport stdio
```

## 2. Удалённое развёртывание на Windows (Windows Service)

Каталог: `C:\Program Files\SSH-MCP\` (`bin\`, `config\`, `runtime\`, `logs\`).
Установка выполняется скриптом `scripts/install.ps1`.

## 3. Удалённое развёртывание на Linux (systemd)

Каталоги: `/opt/ssh-mcp/`, `/var/lib/ssh-mcp/`, `/var/log/ssh-mcp/`.
Юнит запускает `python3 -m ssh_mcp --transport streamable-http` под выделенным системным пользователем.
