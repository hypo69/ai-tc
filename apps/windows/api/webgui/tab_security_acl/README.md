# Вкладка `tab_security_acl` — Права доступа (ACL)

Аудит и изменение ACL: шаблоны, сброс и восстановление прав.

## Файлы

- `index.html` — разметка вкладки;
- `main.js` — клиентская логика (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/security-acl/{summary,action}`, `/api/v1/admin/acl/{reset,restore,template}` |
| Бэкенд / SDK | `sdk/modules/security_acl` |
| Загрузка | `/html/tab_security_acl/index.html` и `/html/tab_security_acl/main.js` |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-10-31 16:35:00