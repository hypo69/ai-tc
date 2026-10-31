<!--
=============================================================================
Process Name: Windows App Internals - Tooltips Editor Panel Documentation
=============================================================================
Description:
  Документация субпанели «Редактор тултипов» (Tooltips Editor)
  вкладки «Внутренняя кухня» (App Internals).
  Описывает архитектуру редактирования подсказок, предпросмотр (Live Preview),
  мультиязычность и синхронизацию с TooltipCache и FastAPI роутером.

# File: README.md
Project: ai-windows-admin
Package: windows/api/webgui/tab_app_internals/panel_tooltips_editor
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 18:06:00
=============================================================================
-->

# 💬 Редактор всплывающих подсказок (Tooltips Editor)

## Описание
Субпанель **«Редактор тултипов»** (`tooltips-editor`) расположена во вкладке «Внутренняя кухня» (`tab-app-internals`) по адресу:
`http://localhost:8001/tc#tab-app-internals#tooltips-editor`

Предназначена для управления справочными подсказками интерфейса (AI Smart Tooltips и i18n hints):
- Просмотр, поиск и фильтрация всех подсказок системы по категориям («Логирование», «Безопасность», «Форензика», «Процессы» и др.);
- Мультиязычность: переключение и редактирование на 4 языках (`ru`, `en`, `uk`, `he`);
- Живой интерактивный предпросмотр (**Live Preview**) карточки всплывающей подсказки в дизайн-системе AI-Windows-Admin;
- Редактирование уникального ключа (`key`), краткого заголовка (`title`), развернутого заголовка (`fullTitle`), эмодзи/иконки (`icon`), категории (`category`) и текста подсказки (`summary`);
- Мгновенная синхронизация с файлами локализаций (`locales/{lang}.json`) через FastAPI роутер `/api/v1/tooltips` и клиентом `window.TooltipCache`.

---

## Архитектура и интеграция
- **FastAPI роутер:** [`apps/windows/api/routers/router_tooltips.py`](file:///C:/Users/onela/AppData/Local/AI-TC/apps/windows/api/routers/router_tooltips.py)
  - `GET /api/v1/tooltips?lang=ru` — список всех зарегистрированных тултипов
  - `GET /api/v1/tooltips/{key}?lang=ru` — получение информации о подсказке
  - `POST /api/v1/tooltips` — сохранение/обновление подсказки
  - `DELETE /api/v1/tooltips/{key}` — удаление подсказки
- **Клиентский модуль:** [`panel.js`](file:///C:/Users/onela/AppData/Local/AI-TC/apps/windows/api/webgui/tab_app_internals/panel_tooltips_editor/panel.js)
  - `initTooltipsEditorPanel()` — инициализация разметки, слушателей событий и загрузка данных
  - `loadTooltipsList()` — получение актуального списка
  - `updateLivePreview()` — обновление интерактивной карточки предпросмотра
