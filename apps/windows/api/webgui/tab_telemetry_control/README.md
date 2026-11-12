# Вкладка `tab_telemetry_control` — Управление телеметрией

Режим тщательного сбора (Thorough Mode), интервалы и тумблеры тяжёлых сенсоров, немедленное сжатие (compact-now), а также установка фоновой службы телеметрии в Windows Task Scheduler (запуск при старте ПК); применение через Hot Reload `config.json`.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js` и встраивается во вкладку `tab_app_internals`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/windows/telemetry/config`, `/api/windows/telemetry/config/compact-now`, `/api/windows/telemetry/config/task-scheduler/status`, `/api/windows/telemetry/config/task-scheduler/install`, `/api/windows/telemetry/collect-heavy-sequentially` |
| Бэкенд / SDK | `telemetry` (см. `telemetry/CONFIG.md` и `telemetry/launchers/Install-TelemetryTask.ps1`) |
| Загрузка | `/html/tab_telemetry_control/index.html` и `/html/tab_telemetry_control/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-11-11 20:37:00