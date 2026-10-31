# Архитектура SSH MCP Server

**Версия:** 1.0  
**Updated:** 2026-10-31 17:05:00

## 1. Трёхуровневое разделение ответственности

| Уровень | Пакеты | Ответственность |
|---|---|---|
| **MCP Layer** | `server.py`, `client.py`, `mcp_tools/*` | Протокол MCP SDK v2 (STDIO и Streamable HTTP), экспозиция 72 инструментов. |
| **Management Layer** | `core/*`, `security/*`, `registry/*`, `storage/*` | `CommandRegistry`, `PermissionManager`, `ApprovalManager`, `TaskManager`, `AuditLogger`. |
| **Transport & Platform Layer** | `transports/*`, `platforms/windows/*`, `platforms/linux/*` | Доставка команд через `AsyncSSH`, `SFTP`, `LocalTransport` и `RemoteMCPTransport`. |

## 2. Три самостоятельных компонента

- `ssh-mcp-core` — используется как внутри MCP, так и напрямую из FastAPI / ai-tc.
- `ssh-mcp-server` — локальный координатор и шлюз MCP.
- `ssh-mcp-agent` — удалённый агент (Streamable HTTP + TLS + Bearer Auth).
