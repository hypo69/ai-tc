# Вкладка `tab_firewall_manager` — Брандмауэр Windows

Сводка профилей и правил брандмауэра, выполнение действий над правилами.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/firewall-manager/{summary,refresh,action}` |
| Бэкенд / SDK | `sdk/modules/firewall_manager` |
| Загрузка | `/html/tab_firewall_manager/index.html` и `/html/tab_firewall_manager/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00