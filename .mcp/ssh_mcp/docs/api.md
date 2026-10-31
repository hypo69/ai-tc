# Справочник API и контрактов MCP Tools

**Версия:** 1.0  
**Updated:** 2026-10-31 17:05:45

## Стандартный формат ответа

Успешный ответ:
```json
{
  "success": true,
  "host": "linux-server-01",
  "platform": "linux",
  "operation": "system.memory",
  "timestamp": "2026-10-31T14:00:00Z",
  "execution": {
    "duration_ms": 42,
    "exit_code": 0,
    "stdout": "",
    "stderr": "",
    "truncated": false
  },
  "data": {
    "total_mb": 16384,
    "used_mb": 8192,
    "available_mb": 8192
  },
  "error": {}
}
```

Ответ с ошибкой:
```json
{
  "success": false,
  "host": "windows-server-01",
  "platform": "windows",
  "operation": "service.restart",
  "timestamp": "2026-10-31T14:00:05Z",
  "execution": {
    "duration_ms": 5,
    "exit_code": 1,
    "stdout": "",
    "stderr": "",
    "truncated": false
  },
  "data": {},
  "error": {
    "code": "ACCESS_DENIED",
    "message": "Administrative privileges required"
  }
}
```
