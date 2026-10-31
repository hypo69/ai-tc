# Инструменты ИИ-агентов (`apps.windows.sdk.core.tools`)

Реестр и фабрика инструментов с вызовом через Function Calling.

| Файл | Содержимое |
|---|---|
| `base.py` | `BaseTool`, `ToolExecutionResult`, `RiskLevel` — базовые интерфейсы |
| `registry.py` | `ToolRegistry` — динамическая регистрация/удаление, `to_function_definition()` |
| `system_tools.py` | `WindowsCollectorTool`, `SafePowerShellProbeTool` (SafeOps-фильтр деструктивных команд) |
| `net_user_tool.py` | Управление локальными учётными записями через `net user` |
| `dynamic_factory.py` | `DynamicToolFactory` и мета-инструмент `create_custom_tool` |

Динамический код проходит проверку [`security_ast.py`](../../security_ast.py) и исполняется через [`dynamic_runner.py`](../../dynamic_runner.py).

**Updated:** 2026-10-31 16:40:00