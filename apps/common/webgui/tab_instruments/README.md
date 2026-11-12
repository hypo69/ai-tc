# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Common WebGUI - Tab Instruments Documentation
# =============================================================================
# Description:
#   Документация общесистемной вкладки управления внутренними инструментами
#   агента рассуждений (CoT / ReAct) для AI-Assistant и AI-TC.
#
# File: README.md
# Project: ai-assistant / ai-tc
# Package: apps.common.webgui.tab_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:44:00
# =============================================================================

# 🛠️ Вкладка управления внутренними инструментами агента CoT (`tab_instruments`)

Вкладка расположена в общем репозитории ассетов `apps/common/webgui/tab_instruments` и используется как в проекте **AI-Assistant**, так и в **AI-TC** для централизованного управления каталогом инструментов цепочек размышлений (Chain of Thought).

---

## 📌 Архитектурные возможности

1. **Единый каталог инструментов (`#pill-inst-catalog`):**
   - Просмотр всех зарегистрированных инструментов (Python, PowerShell, CMD, Bash).
   - Фильтрация по типам рантайма и целевым сущностям (`filesystem:search`, `google:drive`, `google:mail`, `google:contacts`, `google:calendar`, `database:sqlite`, `network:port` и др.).
   - Полнотекстовый поиск по ID, названию, тегам и коду.
   - Сортировка и бейджи рисков (`safe`, `medium`, `high`).

2. **Интерактивный запуск и тестирование (`#modal-inst-runner`):**
   - Динамическая генерация полей параметров на основе `parameters_schema` инструмента.
   - Запуск с замером задержки (мс), отображением stdout, stderr и кода возврата.
   - Возможность повышения привилегий («От имени администратора»).

3. **Синхронизация и отказоустойчивость (`#pill-inst-storage`):**
   - Автоматическая двусторонняя синхронизация между:
     - Человекочитаемым файлом `data/apps/ai_assistent/toolchain_tools.md`.
     - Локальной базой SQLite `data/ai_instruments/ai_instruments.db`.
     - Удалённой MariaDB на сервере Hostinger (`srv1502.hstgr.io`) / PHP REST API.
   - Кнопка принудительной синхронизации и тестирование соединений.

4. **Параметры рантайма и автоизвлечение CoT (`#pill-inst-runtime`):**
   - Настройка таймаута выполнения (сек).
   - SafeOps фильтрация деструктивных операций.
   - Интерактивный CoT-парсер для автоматического извлечения блоков кода из рассуждений LLM в базу инструментов.

---

## 📁 Структура каталога

```
apps/common/webgui/tab_instruments/
├── index.html        # Шаблон разметки вкладки и модальных окон (90vw)
├── main.js           # Контроллер вкладки, API-интеграция и рендеринг
├── style.css         # Темизированные стили через CSS-переменные
├── menu_config.json  # Конфигурация двухуровневого меню субвкладок и блоков
└── README.md         # Настоящая документация
```

---

## 🔌 API эндпоинты

Вкладка взаимодействует с маршрутизатором `/api/v1/ai-instruments`:
- `GET /api/v1/ai-instruments/list` — получение списка инструментов.
- `GET /api/v1/ai-instruments/status` — текущее состояние хранилища.
- `POST /api/v1/ai-instruments/execute` — безопасное выполнение инструмента.
- `POST /api/v1/ai-instruments/save` — создание или обновление инструмента.
- `DELETE /api/v1/ai-instruments/item/{id}` — удаление инструмента.
- `POST /api/v1/ai-instruments/sync` — принудительная синхронизация с Markdown.
- `POST /api/v1/ai-instruments/test-connection` — проверка сетевых соединений.
- `POST /api/v1/ai-instruments/extract-from-reasoning` — автоизвлечение из мыслей LLM.
- `GET /api/v1/ai-instruments/export-csv` — экспорт в CSV.
