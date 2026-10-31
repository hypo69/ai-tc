# Вкладка `tab_event_logs` — Журналы событий Windows

Просмотр событий Windows Event Log, профиль каналов и интеллектуальный аудит; кеш браузера и фоновая загрузка со спиннером.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/event-logs/events`, `/api/event-logs/intelligence/{audit,profile,search}` |
| Бэкенд / SDK | `sdk/modules/event_logs` |
| Загрузка | `/html/tab_event_logs/index.html` и `/html/tab_event_logs/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00