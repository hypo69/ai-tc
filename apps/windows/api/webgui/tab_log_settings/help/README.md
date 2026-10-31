<!--
=============================================================================
Process Name: Windows Log Settings - Architecture Documentation for Help Subsystem
=============================================================================
Description:
  Документация по архитектуре, атомарному разделению и композиции
  контекстной справки для модуля «Параметры и ротация журналов».

File: README.md
Project: ai-windows-admin
Package: windows/api/webgui/tab_log_settings/help
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 17:45:30
=============================================================================
-->

# Подсистема контекстной справки модуля Log Settings

Данная директория содержит атомарные HTML-фрагменты и композитный шаблон интерактивной справки для подраздела **«Параметры и ротация журналов»** (`#tab-app-internals#settings` / `tab_log_settings`).

## Архитектура: Атомарные блоки и Композиция

Подсистема реализована по иерархическому принципу:
1. **Атомарные блоки (`help/blocks/`)**:
   - `block_kpi_cards.html`: Сводные карточки состояния (Security EVTX, CommandLine Event 4688, Сборщик Telemetry.db, Sysmon & 7 доменов).
   - `block_domains_catalog.html`: 7 логических доменов телеметрии ОС и иерархический каталог провайдеров.
   - `block_channels_config.html`: Настройка квот (Max Size), ротации (Retention, AutoBackup) и очистки каналов с автобэкапом.
   - `block_security_telemetry.html`: Включение CommandLine в политику аудита, привилегия `SeSecurityPrivilege` и управление закладкой (Bookmark) сборщика в SQLite.
   - `block_provenance_lifecycle.html`: Граф процессов (Process Provenance) и таймлайн жизненного цикла ОС (Boot, Sleep, Crash).
   - `block_event_inspector.html`: Двухпанельный инспектор событий (Master-Detail) с фильтрами по Event ID и просмотром исходных данных.

2. **Композитный уровень (`help/index.html`)**:
   - Объединяет атомарные блоки с помощью директивы `<div data-help-include="/html/tab_log_settings/help/blocks/block_*.html"></div>`.
   - Содержит панель быстрой навигации (`[data-help-jump]`) для мгновенного скролла к нужному разделу внутри модального окна.

3. **Универсальный контроллер (`js/help-modal.js`)**:
   - Отвечает за открытие любого блока или композитной страницы в едином окне `80vw × 80vh`.
   - Рекурсивно разрешает зависимости `data-help-include` с параллельной загрузкой и кешированием.
   - Автоматически применяет интернационализацию через `window.i18n.applyTranslations()`.
   - Поддерживает подсветку и автопрокрутку к конкретному целевому блоку при переходе из контекстных кнопок интерфейса.
