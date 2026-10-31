<!--
=============================================================================
Process Name: Windows Web Interface - App Internals Documentation
=============================================================================
Description:
  Документация вкладки «Внутренняя кухня» (App Internals).
  Описывает архитектуру субпанелей и двухуровневого меню блоков,
  а также разделение двух баз знаний WikiLLM:
  1. Подсказки по системе (локальный файл SQLite на диске)
  2. База инструментов агента в цепочке размышлений (сервер Hostinger).

# File: README.md
Project: ai-windows-admin
Package: windows/api/webgui/tab_app_internals
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 19:50:00
=============================================================================
-->

# Вкладка «Внутренняя кухня» (App Internals)

## Описание
Вкладка **«Внутренняя кухня»** (`tab_app_internals`) представляет собой служебный хаб администрирования веб-интерфейса AI Windows Admin, организующий субпанели и базы знаний:
1. `telemetry`: Телеметрия (Telemetry Control & Config)
2. `models`: Модели и API (Models & Providers)
3. `logs`: Центр логов (Logs Center)
4. `etw`: Трассировка ETW (Performance Tracing)
5. `settings`: Параметры (Log Settings)
6. `wikillm-system`: **Подсказки по системе (WikiLLM System Knowledge)** — общие рекомендации и подсказки по Windows OS, хранящиеся в локальном файле SQLite на диске (`data/windows_wikillm/knowledge.db`).
7. `instruments`: **База инструментов ИИ-агента (WikiLLM AI Instruments)** — инструменты и скрипты PowerShell/CMD, используемые в цепочке размышлений над задачами (см. conversation `8bdc91cc-bd8f-4a2b-b7d9-d13455e82580`), хранящиеся на сервере Hostinger.
8. `tooltips-editor`: **Редактор тултипов (Tooltips Editor)** — интерактивный визуальный редактор всплывающих подсказок (AI Smart Tooltips & i18n hints) с мультиязычностью и предпросмотром.
9. `helppages-editor`: **Редактор подсказок (Help Pages Editor)** — редактор атомарных блоков и композитных страниц справки системы.
10. `codebase-rag`: **RAG Кода и Диагностики (Codebase AST & Diagnostic RAG)** — управление AST-индексами кодовой базы и формирование диагностических заключений по логам и ошибкам.

---

## Архитектура меню: «Меню — всегда меню»
В соответствии со стандартом `SUBTABS_AND_BLOCKS_MENU.md` (см. conversation `37efa6e9-9633-42ba-9751-7f4bced2022c`), навигация разделена на 2 строгих уровня:

### Уровень 1: Панели субвкладок (`panelId`)
- Располагается строго слева под заголовком вкладки;
- Каждая кнопка снабжена статическим тултипом (`title="..."`, `data-i18n-title="..."`) без обращения к модели и меткой (`data-i18n="..."`).

### Уровень 2: Подменю блоков внутри панелей (`blockId`)
- **В панели «Подсказки по системе» (`wikillm-system`)**:
  - `block-sys-storage`: Хранилище SQLite (путь к `.db`, проверка целостности, создание таблиц);
  - `block-sys-params`: Параметры WikiLLM (модель, порог уверенности, контекстное окно, автообогащение);
  - `block-sys-articles`: Статьи подсказок (встроенный редактор базы знаний WikiLLM).
- **В панели «База инструментов» (`instruments`)**:
  - `block-inst-hostinger`: Сервер Hostinger (REST PHP API шлюз `wikillm_hostinger.php`, токен, БД `u177424397_comp_knowledge`, таблица `ai_instruments`, проверка связи);
  - `block-inst-runtime`: Цепочка размышлений (таймауты, запуск от администратора, SafeOps, автоизвлечение инструментов из рассуждений модели);
  - `block-inst-catalog`: Каталог инструментов (поиск, фильтрация по сущностям, тестовый запуск скрипта и удаление).

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
- `http://localhost:8001/tc#tab-app-internals#telemetry` — мониторинг телеметрии
- `http://localhost:8001/tc#tab-app-internals#models` — управление моделями и провайдерами
- `http://localhost:8001/tc#tab-app-internals#logs` — центр внутренних логов
- `http://localhost:8001/tc#tab-app-internals#etw` — трассировка ETW
- `http://localhost:8001/tc#tab-app-internals#settings` — параметры и ротация логов
- `http://localhost:8001/tc#tab-app-internals#wikillm-system#block-sys-storage` — локальное хранилище подсказок SQLite
- `http://localhost:8001/tc#tab-app-internals#wikillm-system#block-sys-params` — параметры модели генерации подсказок
- `http://localhost:8001/tc#tab-app-internals#wikillm-system#block-sys-articles` — редактор статей подсказок
- `http://localhost:8001/tc#tab-app-internals#instruments#block-inst-hostinger` — настройки подключения к серверу Hostinger
- `http://localhost:8001/tc#tab-app-internals#instruments#block-inst-runtime` — параметры инструментов в цепочке размышлений
- `http://localhost:8001/tc#tab-app-internals#instruments#block-inst-catalog` — библиотека инструментов агента
- `http://localhost:8001/tc#tab-app-internals#tooltips-editor` — редактор всплывающих подсказок и базы знаний тултипов
- `http://localhost:8001/tc#tab-app-internals#helppages-editor` — редактор страниц и блоков контекстной справки
- `http://localhost:8001/tc#tab-app-internals#codebase-rag#block-code-diagnose` — диагностика ошибок и логов по AST кодовой базы

---

## Программное API
- `window.initAppInternalsTab()` — главная инициализация вкладки
- `window.switchAppInternalsSubTab(panelId, blockId, updateUrl)` — переключение субпанели и блока
- `window.switchAppInternalsBlock(panelId, blockId, updateUrl)` — переключение блока внутри панели
- `window.getAppInternalsPanelFromHash()` — извлечение панели из хэша
- `window.getAppInternalsBlockFromHash(panelId)` — извлечение блока из хэша
- `window.updateAppInternalsUrlWithPanel(panelId, blockId)` — обновление адресной строки
