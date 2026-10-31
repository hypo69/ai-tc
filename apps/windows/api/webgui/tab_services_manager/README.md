# Вкладка `tab_services_manager` — Диспетчер служб

Список служб Windows, запуск, остановка и смена типа запуска.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/services-manager/{summary,action}` |
| Бэкенд / SDK | `sdk/modules/services_manager` |
| Загрузка | `/html/tab_services_manager/index.html` и `/html/tab_services_manager/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00