# Вкладка `tab_services_manager` — Диспетчер служб

Список служб Windows, запуск, остановка, смена типа запуска и контекстный анализ служб через универсальное модальное окно ИИ-ассистента (`AIModalDialog`).

## Файлы

- `index.html` — разметка вкладки (`#panel-windows-services-manager`);
- `main.js` — клиентская логика и интеграция с универсальным ИИ-модальным окном `window.AIModalDialog` (подключается через `core/tab-registry.js`).

## Интеграция

| Параметр | Значение |
|---|---|
| REST API | `/api/services-manager/{summary,action}` |
| Бэкенд / SDK | `sdk/modules/services_manager` |
| Загрузка | `/html/tab_services_manager/index.html` и `/html/tab_services_manager/main.js` |
| Модальное окно ИИ | `window.AIModalDialog.show({...})` (`panelId: 'panel-windows-services-manager'`, `tableType: 'service'`) |

Вкладка отражена в интерактивной карте сайта [`tab_sitemap`](../tab_sitemap/README.md).

---

**Updated:** 2026-11-12 01:56:00
