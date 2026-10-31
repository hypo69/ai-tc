# Вкладка `tab_hardware_monitor` — Монитор оборудования

Датчики, метрики и SMART оборудования в реальном времени.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/windows/hardware/{monitor,sensors,smart}` |
| Бэкенд / SDK | `sdk/modules/hardware` |
| Загрузка | `/html/tab_hardware_monitor/index.html` и `/html/tab_hardware_monitor/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00