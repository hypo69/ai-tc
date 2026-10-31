# Вкладка `tab_telemetry_control` — Управление телеметрией

Режим тщательного сбора (Thorough Mode), интервалы и тумблеры тяжёлых сенсоров, немедленное сжатие (compact-now); применение через Hot Reload `config.json`.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/windows/telemetry/config`, `/api/windows/telemetry/config/compact-now`, `/api/windows/telemetry/collect-heavy-sequentially` |
| Бэкенд / SDK | `telemetry` (см. `telemetry/CONFIG.md`) |
| Загрузка | `/html/tab_telemetry_control/index.html` и `/html/tab_telemetry_control/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00