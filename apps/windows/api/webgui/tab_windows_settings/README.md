# 🎛️ Windows User Settings & Control Plane Web Tab

**Status:** ✅ Active  
**Author:** hypo69  
**Updated:** 2026-11-12 05:00:00  

## 📋 Описание

Единая веб-панель управления пользовательскими настройками операционной системы Windows 10/11 для **ai-tc**.
Объединяет управление фокусом, многозадачностью, окнами, специальными возможностями (Accessibility), устройствами ввода (мышь, клавиатура), графической подсистемой DWM и проводником Explorer в едином унифицированном интерфейсе.

## 🏛️ Архитектура модулей
Файлы декомпозированы по панельной схеме (`panel_*`) в соответствии с лимитом `<= 500` строк (`GEMINI.md` § 4.4):

```
tab_windows_settings/
├── index.html                           # Разметка панели и модальных окон
├── main.js                              # Модульный оркестратор вкладки (< 130 строк)
├── desktop_displays.js                  # Модуль отображения мониторов и виртуальных столов
├── README.md                            # Настоящая документация
├── common/
│   └── ui_utils.js                      # Базовый API_BASE, реактивное состояние, fetchJson, бейджи риска
├── panel_quick_settings/
│   └── panel.js                         # Экспресс-управление: X-Mouse, задержка, Foreground Lock, Caret Width
├── panel_catalog/
│   └── panel.js                         # Каталог 295 параметров: фильтрация, поиск, чтение значений
├── panel_modal_safeops/
│   └── panel.js                         # Модальное окно предпросмотра (SafeOps Dry-Run) и применение
└── panel_history/
    └── panel.js                         # Журнал аудита в SQLite telemetry.db и мгновенный откат (Rollback)
```

## 🚀 Ключевые возможности

1. **Экспресс-управление (Quick Actions):**
   - **X-Mouse (Active Window Tracking):** Чтение и переключение передачи фокуса окну под курсором (`SPI_GETACTIVEWINDOWTRACKING` / `SPI_SETACTIVEWINDOWTRACKING`).
   - **Active Window Tracking Delay:** Регулировка задержки передачи фокуса (`ActiveWndTrkTimeout`, 0..2000 мс).
   - **Foreground Lock Timeout:** Настройка таймаута блокировки перехвата фокуса.
   - **Толщина курсора (Caret Width):** Регулировка ширины каретки ввода текста (Accessibility).
   - **Анимации окон:** Включение/выключение визуальных эффектов сворачивания/разворачивания (`SPI_SETANIMATION`).
   - **Snap Assist & Snap Layouts:** Прикрепление и организация окон по сетке.

2. **Каталог 295 параметров по 15 категориям:**
   - Чтение живых значений из Win32 API (`SystemParametersInfoW`), реестра Windows (HKCU/HKLM), DWM API и Group Policy (GPO).
   - Полнотекстовый поиск по ID, русским и английским названиям.
   - Фильтрация по уровням риска (`Safe`, `Low`, `Medium`, `High`, `Critical`) и бэкендам.

3. **Безопасность и SafeOps:**
   - **Сухой прогон (Dry-Run Preview):** Оценка влияния параметра, проверка необходимости повышения прав (UAC) и перезапуска Explorer/DWM.
   - **Интеграция с точками восстановления:** Автоматический вызов `WindowsSystemRestoreManager.create_restore_point()` при изменении параметров с повышенным риском.
   - **Журнал изменений в SQLite (`telemetry.db`):** Фиксация старых и новых значений, оператора и статуса.
   - **Мгновенный откат (Rollback):** Возможность вернуть любое изменение по `change_id` или откатить последнее действие одной кнопкой.

## 🌐 Маршруты интеграции

- **HTML шаблон:** `/html/tab_windows_settings/index.html`
- **Клиентский контроллер:** `/html/tab_windows_settings/main.js`
- **REST API бэкенда:** `/api/v1/window-management/*`
