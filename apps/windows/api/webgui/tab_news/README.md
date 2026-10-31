# Вкладка `tab_news` — Новости

Лента новостей, дайджест, профиль интересов, обратная связь и ИИ-саммари статей.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/news/{feed,digest,profile,feedback,summarize-article}` |
| Бэкенд / SDK | — |
| Загрузка | `/html/tab_news/index.html` и `/html/tab_news/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00