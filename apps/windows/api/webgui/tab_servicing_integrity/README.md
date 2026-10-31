# Вкладка `tab_servicing_integrity` — Целостность обслуживания

Проверка защищённых файлов (SFC) и обслуживание хранилища компонентов (DISM, WinSxS).

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/servicing-integrity/{summary,action}` |
| Бэкенд / SDK | `sdk/modules/servicing_integrity` |
| Загрузка | `/html/tab_servicing_integrity/index.html` и `/html/tab_servicing_integrity/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00