# Вкладка `tab_performance_tracing` — Трассировка производительности

Счётчики производительности в реальном времени (typeperf/PDH) и управление сборщиками ETW (logman).

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/performance-tracing/{summary,action}` |
| Бэкенд / SDK | `sdk/modules/performance_tracing` |
| Загрузка | `/html/tab_performance_tracing/index.html` и `/html/tab_performance_tracing/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00