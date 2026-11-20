<!--
=============================================================================
Process Name: Windows Web Interface - App Internals Documentation
=============================================================================
Description:
  Документация вкладки «Внутренняя кухня» (App Internals).
  Описывает архитектуру субпанелей и двухуровневого меню блоков,
  а также разделение двух баз знаний WikiLLM и единого центра управления
  базами данных (Database Workbench).

# File: README.md
Project: ai-tc
Package: windows/api/webgui/tab_app_internals
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-19 17:25:00
=============================================================================
-->

# Вкладка «Внутренняя кухня» (App Internals)

## Описание
Вкладка **«Внутренняя кухня»** (`tab_app_internals`) представляет собой служебный хаб администрирования веб-интерфейса ai-tc, организующий субпанели и базы знаний:
1. `telemetry`: Телеметрия (Telemetry Control & Config)
2. `models`: Модели и API (Models & Providers)
3. `logs`: Центр логов (Logs Center)
4. `activity`: Журнал активности (Activity Log — история операций администрирования и системы)
5. `etw`: Трассировка ETW (Performance Tracing)
6. `settings`: Параметры (Log Settings)
7. `wikillm-system`: **Подсказки по системе (WikiLLM System Knowledge)** — общие рекомендации и подсказки по Windows OS, хранящиеся в локальном файле SQLite на диске (`data/windows_wikillm/knowledge.db`).
8. `instruments`: **База инструментов ИИ-агента (u177424397_tool_chains)** — инструменты и команды, хранящиеся в MariaDB на сервере Hostinger (`srv1373.hstgr.io`, БД `u177424397_tool_chains`).
9. `tooltips-editor`: **Редактор тултипов (Tooltips Editor)** — интерактивный визуальный редактор всплывающих подсказок (AI Smart Tooltips & i18n hints) с мультиязычностью и предпросмотром.
10. `helppages-editor`: **Редактор подсказок (Help Pages Editor)** — редактор атомарных блоков и композитных страниц справки системы.
11. `codebase-rag`: **RAG Кода и Диагностики (Codebase AST & Diagnostic RAG)** — управление AST-индексами кодовой базы и формирование диагностических заключений по логам и ошибкам.
12. `db-manager`: **Управление БД и хостингом (Database Workbench)** — быстрый просмотр параметров, структуры таблиц, прямая SQL-консоль (SELECT, INSERT, DELETE), инструменты сжатия (VACUUM, OPTIMIZE), экспорт данных с серверов Hostinger и SQLite, создание и восстановление бэкапов с ZIP-сжатием.

---

## Архитектура меню: «Меню — всегда меню»
В соответствии со стандартом `SUBTABS_AND_BLOCKS_MENU.md` (см. conversation `37efa6e9-9633-42ba-9751-7f4bced2022c`), навигация разделена на 2 строгих уровня:

### Уровень 1: Панели субвкладок (`panelId`)
- Располагается строго слева под заголовком вкладки;
- Каждая кнопка снабжена статическим тултипом (`title="..."`, `data-i18n-title="..."`) без обращения к модели и меткой (`data-i18n="..."`).

### Уровень 2: Подменю блоков внутри панелей (`blockId`)
- **В панели «Управление БД» (`db-manager`)**:
  - `block-db-overview`: Параметры и структура (сводные метрики, статус подключений, размеры на диске, схема таблиц SQLite и Hostinger MariaDB);
  - `block-db-console`: SQL Консоль (прямой ввод и исполнение команд `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `SHOW TABLES`, `PRAGMA` с табличным просмотром результатов и статистикой времени);
  - `block-db-compress`: Сжатие и оптимизация (полная дефрагментация хранилища SQLite `VACUUM`, сброс WAL-журнала, `OPTIMIZE TABLE` для таблиц MariaDB на сервере Hostinger);
  - `block-db-export`: Экспорт с хостинга (выгрузка любых таблиц или всей базы данных Hostinger/SQLite в форматы SQL Dump, JSON или CSV со скачиванием);
  - `block-db-backups`: Бэкапы (создание атомарных снимков баз в один клик с ZIP-сжатием, хранение в `data/backups/`, скачивание, безопасное восстановление и удаление).

- **В панели «Подсказки по системе» (`wikillm-system`)**:
  - `block-sys-storage`: Хранилище SQLite (путь к `.db`, проверка целостности, создание таблиц);
  - `block-sys-params`: Параметры WikiLLM (модель, порог уверенности, контекстное окно, автообогащение);
  - `block-sys-articles`: Статьи подсказок (встроенный редактор базы знаний WikiLLM).

- **В панели «База инструментов» (`instruments`)**:
  - `block-inst-hostinger`: Сервер Hostinger (MariaDB direct TCP `srv1373.hstgr.io`, БД `u177424397_tool_chains`, таблица `ai_instruments`, проверка связи);
  - `block-inst-runtime`: Цепочка размышлений (таймауты, запуск от администратора, SafeOps, автоизвлечение инструментов из рассуждений модели);
  - `block-inst-catalog`: Каталог инструментов и **Мастер создания команд для модели**.

- **В панели «RAG Кода и Диагностики» (`codebase-rag`)**:
  - `block-code-diagnose`: Интеллектуальная диагностика ошибок, логов и архитектуры кода;
  - `block-code-index`: Построение и переиндексация AST-индексов кодовой базы;
  - `block-code-search`: Интерактивный поиск по AST-символам (классы, функции) и фрагментам кода.

---

## Маршрутизация и навигация по URL
URL автоматически синхронизируется при каждом переключении без перезагрузки страницы:

```text
# Субпанель верхнего уровня:
http://localhost:8001/tc#tab-app-internals#<panel_id>

# Субпанель с активным блоком:
http://localhost:8001/tc#tab-app-internals#<panel_id>#block-<block_id>
```

### Примеры маршрутов:
- `http://localhost:8001/tc#tab-app-internals#db-manager` — единая панель управления БД и хостингом
- `http://localhost:8001/tc#tab-app-internals#db-manager#block-db-overview` — сводка параметров и схемы баз
- `http://localhost:8001/tc#tab-app-internals#db-manager#block-db-console` — прямая консоль выполнения SQL
- `http://localhost:8001/tc#tab-app-internals#db-manager#block-db-compress` — инструменты сжатия хранилища (VACUUM / OPTIMIZE)
- `http://localhost:8001/tc#tab-app-internals#db-manager#block-db-export` — мастер экспорта с хостинга (SQL, JSON, CSV)
- `http://localhost:8001/tc#tab-app-internals#db-manager#block-db-backups` — каталог резервных копий и восстановление
- `http://localhost:8001/tc#tab-app-internals#telemetry` — мониторинг телеметрии
- `http://localhost:8001/tc#tab-app-internals#models` — управление моделями и провайдерами
- `http://localhost:8001/tc#tab-app-internals#logs` — центр внутренних логов
- `http://localhost:8001/tc#tab-app-internals#activity` — журнал внутренней активности и операций системы/приложения
- `http://localhost:8001/tc#tab-app-internals#etw` — трассировка ETW
- `http://localhost:8001/tc#tab-app-internals#settings` — параметры и ротация логов
- `http://localhost:8001/tc#tab-app-internals#wikillm-system#block-sys-storage` — локальное хранилище подсказок SQLite
- `http://localhost:8001/tc#tab-app-internals#instruments#block-inst-hostinger` — настройки подключения к серверу Hostinger
- `http://localhost:8001/tc#tab-app-internals#codebase-rag#block-code-diagnose` — диагностика ошибок и логов по AST кодовой базы

---

## Программное API
- `window.initAppInternalsTab()` — главная инициализация вкладки
- `window.initDbManagerPanel()` — инициализация панели Database Manager
- `window.switchDbManagerBlock(blockId)` — переключение блока внутри Database Manager
- `window.executeConsoleQuery()` — отправка прямого SQL запроса
- `window.executeDatabaseCompression()` — выполнение операции сжатия
- `window.executeDatabaseExport()` — создание файла экспорта
- `window.executeCreateBackup()` — создание новой резервной копии
- `window.loadDbBackups()` — загрузка каталога бэкапов
- `window.switchAppInternalsSubTab(panelId, blockId, updateUrl)` — переключение субпанели и блока
- `window.switchAppInternalsBlock(panelId, blockId, updateUrl)` — переключение блока внутри панели
- `window.getAppInternalsPanelFromHash()` — извлечение панели из хэша
- `window.getAppInternalsBlockFromHash(panelId)` — извлечение блока из хэша
- `window.updateAppInternalsUrlWithPanel(panelId, blockId)` — обновление адресной строки
