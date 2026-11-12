# Code Helper — Автономная система RAG исходного кода и диагностики

## 📋 Описание проекта

**Code Helper** (`apps/code_helper`) — полностью автономное микроприложение для AST-индексации, семантического поиска по исходному коду Python и документации Markdown, а также автоматической диагностики ошибок и сбоев (Root Cause Analysis & Remediation).

База знаний системы централизованно хранится в реляционной базе данных **MariaDB на сервере Hostinger**, с автоматическим переключением на локальный кэш **SQLite** при отсутствии интернет-соединения или сетевых ограничений.

**Updated:** 2026-11-01 17:10:00  
**Автор:** hypo69  
**Лицензия:** © 2026 hypo69

---

## ⚙️ Параметры подключения к Hostinger

Система настроена на взаимодействие со следующими реквизитами базы знаний:

| Параметр | Значение |
|---|---|
| **Хост (Host)** | `srv1502.hstgr.io` |
| **Резервный IP (Fallback IP)** | `77.37.35.16` |
| **Порт (Port)** | `3306` |
| **База данных (Database)** | `u177424397_code_helper` |
| **Пользователь (User)** | `u177424397_code_help_adm` |
| **Пароль (Password)** | `@Davidka#1969` |
| **Кодировка** | `utf8mb4` |
| **Локальный кэш (Fallback SQLite)** | `data/code_helper/code_helper.db` |

> [!TIP]
> **Настройка удаленного доступа в Hostinger (Remote MySQL):**  
> Если при прямом подключении возвращается ошибка `Access denied for user...`:
> 1. Войдите в панель управления **Hostinger hPanel**.
> 2. Перейдите в раздел **Базы данных** -> **Удаленный MySQL** (Remote MySQL).
> 3. Выберите базу данных `u177424397_code_helper`.
> 4. В поле **IP (IPv4 или IPv6)** укажите `%` (для доступа с любого IP) или ваш текущий публичный IP-адрес.
> 5. Нажмите кнопку **Создать**. После этого прямое подключение MariaDB активируется автоматически.

---

## 🏗 Архитектура приложения

```
apps/code_helper/
├── __init__.py           # Экспорт компонентов и интерфейсов
├── __main__.py           # Автономный CLI-диспетчер
├── config.json           # Конфигурация приложения и реквизиты Hostinger
├── manifest.json         # Манифест микроприложения для AppRegistry
├── models.py             # Pydantic модели (CodeChunk, CodeSymbol, DiagnosticConclusion)
├── parser.py             # AST-парсер Python и секционный парсер Markdown
├── storage.py            # Менеджер хранения MariaDB (Hostinger) и SQLite
├── rag.py                # Движок гибридного поиска и диагностики сбоев
├── router.py             # FastAPI REST API эндпоинты (/api/code-helper)
├── server.py             # Запуск автономного ASGI веб-сервера Uvicorn
└── tests/                # Модульные TDD тесты
    ├── test_parser.py    # Тестирование AST-парсинга
    ├── test_storage.py   # Тестирование MariaDB/SQLite хранилища
    └── test_rag.py       # Тестирование поиска и генерации заключений
```

---

## 💻 Использование через командную строку (CLI)

Запуск осуществляется как модуль Python из любого каталога:

### 1. Проверка статуса базы знаний и соединения
```powershell
py -m apps.code_helper status
```

### 2. Тестирование соединения с Hostinger MariaDB
```powershell
py -m apps.code_helper db-test
```

### 3. Сборка / обновление индекса кодовой базы
```powershell
# Индексация текущего проекта в индекс 'codebase'
py -m apps.code_helper build --root . --name codebase

# Индексация только конкретной поддиректории
py -m apps.code_helper build --root apps/code_helper --name code_helper_self
```

### 4. Поиск фрагментов кода и документации
```powershell
py -m apps.code_helper search "def build_index" --name codebase --top-k 5
```

### 5. Поиск функций, классов и методов AST
```powershell
py -m apps.code_helper symbols "CodeHelperStorage" --name codebase
```

### 6. Диагностика ошибок и формирование заключения (Root Cause Analysis)
```powershell
py -m apps.code_helper diagnose --error "ZeroDivisionError in calculate_ratio at math_utils.py:42"
```

### 7. Запуск автономного веб-сервера
```powershell
py -m apps.code_helper serve --port 8105
```

---

## 🌐 REST API Эндпоинты (`/api/code-helper`)

- `GET /api/code-helper/status` — статус подключения к Hostinger MariaDB, активный движок и список индексов.
- `POST /api/code-helper/db/test` — прямое тестирование сетевой задержки и доступности Hostinger MariaDB.
- `GET /api/code-helper/indexes` — список всех собранных индексов кодовой базы.
- `POST /api/code-helper/build` — асинхронный запуск индексации проекта.
- `POST /api/code-helper/search` — гибридный поиск по чанкам кода.
- `POST /api/code-helper/symbols` — поиск по таблице AST-символов.
- `POST /api/code-helper/diagnose` — формирование структурированного заключения `DiagnosticConclusion`.

---

## 🧪 Запуск тестов

```powershell
pytest apps/code_helper/tests/ -v
```
