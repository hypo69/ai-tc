# Вкладка `tab_storage_management` — Накопители (консолидированная)

Контейнер с суб-вкладками «Диски и тома» и «Ресурс и SMART»; подгружает `tab_storage_manager` и `tab_storage_wear`.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | — |
| Бэкенд / SDK | `sdk/modules/storage_manager` |
| Загрузка | `/html/tab_storage_management/index.html` и `/html/tab_storage_management/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00