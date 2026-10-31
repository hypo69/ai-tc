# Вкладка `tab_software_manager` — Менеджер ПО

Управление пакетами: WinGet, Microsoft Store (AppX/MSIX) и MSI/реестр.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/software-manager/{summary,action}` |
| Бэкенд / SDK | `sdk/modules/software_manager` |
| Загрузка | `/html/tab_software_manager/index.html` и `/html/tab_software_manager/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00