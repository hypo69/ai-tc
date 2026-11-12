<!--
=============================================================================
File: README.md
Project: ai-windows-admin
Package: windows/api/webgui/tab_app_internals/panel_activity
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-11 23:20:00
=============================================================================
-->

# Панель «Журнал активности» (`panel_activity`)

## Назначение
Суб-панель вкладки [`tab_app_internals`](../README.md) (`#tab-app-internals#activity`), отображающая хронологический журнал внутренней активности и операций администрирования.

## Контракт API
- `GET /api/v1/system_logs/activity` — возвращает список последних операций (`timestamp`, `action`, `target`, `status`, `details`).

## Программное API
- `initAppInternalsActivityPanel()` — инициализирует разметку, ресайзер таблицы (`setupTableResizer`), активный поллер (`window.registerTabPoller`) и выполняет первоначальную загрузку.
- `loadAppInternalsActivityLogs(force)` — загружает и отрисовывает записи журнала активности.
