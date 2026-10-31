# Вкладка `tab_interactive_agent` — Интерактивный агент

Пошаговый диалоговый агент со стейт-машиной сессий: постановка цели, степпер, ввод ответов.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/v1/interactive-agent/start`, `/api/v1/interactive-agent/sessions/` |
| Бэкенд / SDK | — |
| Загрузка | `/html/tab_interactive_agent/index.html` и `/html/tab_interactive_agent/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00