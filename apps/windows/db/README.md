# 🗄️ Модуль Адаптера Базы Данных (Database Adapter)

## Описание
Модуль `apps.windows.db` предоставляет унифицированный интерфейс взаимодействия с базами данных проекта ai-tc. Модуль реализует поддержку двух режимов хранения данных в соответствии с техническим заданием:
1. **Централизованное удалённое хранилище (MariaDB/MySQL)** — для совместного использования базы знаний, синхронизации телеметрии и централизованного аудита на удалённом сервере.
2. **Локальное хранилище (SQLite)** — для автономной работы на рабочем месте оператора при отсутствии сетевой связности или локальном режиме.

## Возможности
- **Автоматический выбор бэкенда**: считывание секции `database` из `apps/windows/api/config.json` и `config.json`.
- **Автоматический отказоустойчивый режим (Graceful Fallback)**: при сбое подключения к MariaDB или недоступности удалённого сервера адаптер прозрачно переключается на локальную базу SQLite.
- **Универсальная адаптация SQL**: преобразование параметров формата `:param` в `%(:param)s` (для MariaDB) и поддержка нативных параметров SQLite, а также адаптация команд `ON DUPLICATE KEY UPDATE` к синтаксису SQLite.
- **Поддержка пула и переподключения**: валидация живости соединения (`ping(reconnect=True)`) перед выполнением запросов.

## Конфигурация
Параметры подключения задаются в `config.json`:
```json
{
  "database": {
    "engine": "mariadb",
    "sqlite": {
      "path": "data/wikillm.db"
    },
    "mariadb": {
      "host": "srv1502.hstgr.io",
      "port": 3306,
      "user": "...",
      "password": "...",
      "database": "...",
      "connect_timeout": 5
    }
  }
}
```

## Использование
```python
from apps.windows.db.db_adapter import db_adapter

# Выборка данных
rows = db_adapter.fetch_all("SELECT * FROM wikillm_knowledge WHERE category = :cat", {"cat": "system"})

# Выполнение операций записи
db_adapter.execute("DELETE FROM wikillm_knowledge WHERE canonical_key = :key", {"key": "win_event_1001"})
```
