# core/ — Слой управления (Management Layer / ssh-mcp-core)

**Описание:** Центральное ядро оркестрации подключений, реестра команд, проверки привилегий, подтверждений опасных действий и нормализации ответов без привязки к конкретной ОС.

## Файлы

- `connection_manager.py` — `ConnectionManager`: пул подключений, проверка статуса, авто-реконнект.
- `command_registry.py` — `CommandRegistry`: каталог разрешённых команд и валидация типов параметров.
- `execution_engine.py` — `ExecutionEngine`: полный жизненный цикл выполнения с семафором параллелизма и аудитом.
- `task_manager.py` — `TaskManager`: запуск, опрос и отмена длительных асинхронных задач.
- `permission_manager.py` — `PermissionManager`: контроль политик доступа и уровней привилегий.
- `approval_manager.py` — `ApprovalManager`: привязка подтверждений (Approval) к хосту, команде и хэшу параметров.
- `result_normalizer.py` — `ResultNormalizer`: формирование единого JSON-ответа MCP и усечение вывода.
