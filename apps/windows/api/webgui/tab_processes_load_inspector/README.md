# Вкладка инспектора активности процессов (Process Intelligence & Activity Deep Dive)

## 📋 Описание модуля
Модуль веб-интерфейса инспектора активности процессов (`processes_load_inspector_tab`), доступный по адресу `http://127.0.0.1:8001/tc#tab-processes-load-inspector`.

Интерфейс спроектирован по модульной схеме **Subtabs Nav-Pills Hub** (аналогично `tab_software_scanner`), объединяя 5 ключевых панелей мониторинга под аккуратным верхним меню переключения без необходимости длинной вертикальной прокрутки:
1. **Диспетчер процессов и приложений**: Task Manager представление (Apps, Background, Windows) с группировкой окон и подпроцессов.
2. **Топ процессов хоста (Live Stream)**: Стриминговый поток наиболее активных процессов хоста с поиском и кнопкой Drill-down.
3. **Сетевая активность программ**: Мониторинг интернет-соединений, сокетов и слушающих портов.
4. **Изменения файлов (Real-Time)**: Монитор файловых событий на базе `ReadDirectoryChangesW`.
5. **Утечки ресурсов и дескрипторов (Leak Hunter)**: Глубокий Win32 аудит утечек дескрипторов (Handles), объектов GDI/USER, Page Faults и оценка рисков деградации.
6. **Process Intelligence Deep Dive**: Всплывающее модальное окно глубокого анализа инстанса процесса (7 виджетов).

Построен на архитектурном принципе **Process Intelligence** с гарантированным разрешением проблемы **PID Recycling** (переиспользование PID операционной системой Windows) за счет уникальной пары `(pid, start_time)` и уникального ключа `instance_id`.

---

## 7 Функциональных виджетов интерфейса

1. **Панель выбора и профиля инстанса (Instance Header & Selector Bar)**:
   - Быстрый поиск и выбор процессов с переключателем «Активные процессы» / «История завершенных».
   - Карточка профиля: имя, PID, `instance_id`, статус (`RUNNING`, `EXITED`, `SUSPENDED`), время запуска (`start_time`), время работы (`Uptime`), пользователь, уровень целостности UAC (`IntegrityLevel`), полная командная строка.

2. **Метрики ресурсоемкости в реальном времени (Real-Time Metrics Charts)**:
   - 4 синхронизированных интерактивных графика (интервалы: 1 мин, 5 мин, 1 час, 24 часа):
     - **ЦП (CPU Utilization)**: общая нагрузка %, User Mode %, счетчик потоков.
     - **Память (RAM Profile)**: Working Set (МБ), Private Bytes (МБ), Page Faults/сек.
     - **Графический процессор (GPU & VRAM)**: нагрузка GPU % и использование видеопамяти VRAM.
     - **Дисковый I/O**: скорость чтения/записи (КБ/с) и количество операций ввода-вывода (IOPS).

3. **Иерархическое дерево происхождения (Process Lineage & Hierarchy Graph)**:
   - Интерактивный граф предков и потомков на основе `parent_instance_id`. Клик по любому узлу мгновенно переключает весь интерфейс на анализ выбранного процесса.

4. **Таблица сетевых сокетов и соединений (Network Sockets Panel)**:
   - Список открытых сокетов инстанса: протокол (TCP/UDP), локальный адрес $\rightarrow$ удаленный сервер, статус соединения, GeoIP/DNS.

5. **Лента файловых операций (File Events Feed)**:
   - Журнал дисковых операций процесса: время, действие (`CREATE`, `MODIFY`, `DELETE`, `RENAME`), путь к файлу, затронутый объем данных.

6. **Панель дескрипторов ОС и системных ресурсов (Handles & GUI Objects)**:
   - Количество открытых дескрипторов (Handles), объектов GDI (кисти, шрифты, битмапы) и USER (окна, меню), детектор риска утечек ресурсов.

7. **Панель безопасного администрирования (SafeOps Action Panel)**:
   - Завершение процесса (`Kill Process` с подтверждением диалоговым окном).
   - Приостановка и возобновление потоков (`Suspend / Resume`).
   - Снятие дампа памяти (`Create Memory Dump`).
   - Изменение класса приоритета CPU (`Set Priority Class`: Idle, Below Normal, Normal, Above Normal, High, Realtime).

---

## 🛠️ Спецификация REST API Контрактов (/api/v1/tab-processes-load-inspector/*)

- `GET /api/v1/tab-processes-load-inspector/panel-top-processes` — потоковый топ ресурсоемких процессов хоста.
- `GET /api/v1/tab-processes-load-inspector/panel-process-manager` — категоризированный отчет процессов (Apps, Background, Windows).
- `GET /api/v1/tab-processes-load-inspector/panel-process-manager/summary` — сводный отчет и агрегаты процессов.
- `POST /api/v1/tab-processes-load-inspector/panel-process-manager/action` — завершение процесса (PID, kill_tree).
- `GET /api/v1/tab-processes-load-inspector/panel-network-activity` — активные сетевые сокеты и интернет-соединения программ.
- `GET /api/v1/tab-processes-load-inspector/panel-file-watcher/events` — живая лента изменений файлов хоста.
- `GET /api/v1/tab-processes-load-inspector/panel-leak-hunter` — срез утечек ресурсов и дескрипторов (Handles, GDI/USER).
- `POST /api/v1/tab-processes-load-inspector/panel-leak-hunter/refresh` — принудительное обновление аудита утечек.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/active` — список всех активных инстансов процессов.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/history` — история завершенных инстансов.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}` — паспорт и текущий статус инстанса.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}/samples` — временной ряд метрик (CPU, RAM, GPU, IO).
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}/lineage` — дерево предков и потомков инстанса.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}/file-activity` — файловые события инстанса.
- `GET /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}/sockets` — открытые сокеты и соединения инстанса.
- `POST /api/v1/tab-processes-load-inspector/panel-deep-dive/{instance_id}/action` — выполнение безопасных действий SafeOps.
- `GET /api/v1/tab-processes-load-inspector/panel-ai-audit/powershell` — автоматическое расследование источников вызовов PowerShell.

---

## 🧭 Навигация и Маршрутизация

- **URL в сценарии `tc.ps1`**: `http://127.0.0.1:8001/tc#tab-processes-load-inspector`
- **Прямой переход к панели Диспетчера Процессов**: `http://127.0.0.1:8001/tc#tab-processes-load-inspector#manager`
- **Прямой переход к панели Сетевой активности процессов**: `http://127.0.0.1:8001/tc#tab-processes-load-inspector#network-activity-by-process` (поддерживается алиас `#net`)
- **Обратная совместимость**: Вкладка `tab-process-manager` консолидирована в данный инспектор как панель `#subpane-proc-manager`. Любые обращения к `#tab-process-manager` автоматически перенаправляются на `#tab-processes-load-inspector#manager`.

---

## 📂 Модульная структура Frontend (ES6)

Все скрипты вкладки декомпозированы на изолированные модули в директориях `panel_*` в строгом соответствии с лимитом <= 500 строк кода:

```text
tab_processes_load_inspector/
├── index.html                           # Разметка вкладок и модального окна Deep Dive
├── main.js                              # Корневой оркестратор жизненного цикла и поллинга (331 строка)
├── common/
│   └── ui_utils.js                      # Утилиты байт, времени, модалок, хэша URL (214 строк)
├── panel_process_manager/
│   └── panel.js                         # Task Manager Process Manager (Apps, Bg, Win, SafeOps) (429 строк)
├── panel_ai_audit/
│   └── panel.js                         # Интеграция с AIModalDialog, расследование PowerShell (203 строки)
├── panel_top_stream/
│   └── panel.js                         # Топ процессов хоста в реальном времени (126 строк)
├── panel_deep_dive/
│   ├── panel.js                         # Паспорт инстанса, SafeOps, сэмплы (425 строк)
│   ├── charts.js                        # 4 синхронизированных графика Chart.js (173 строки)
│   └── widgets.js                       # Lineage дерево, сокеты, файлы, ресайзеры таблиц (219 строк)
├── panel_network_files/
│   └── panel.js                         # Сетевые соединения и файловый вотчер хоста (176 строк)
└── panel_leak_hunter/
    └── panel.js                         # Аудит дескрипторов (Handles), GDI/USER, Page Faults (230 строк)
```

---

**Updated**: 2026-10-18 08:25:00  
**Package**: windows/api/webgui/tab_processes_load_inspector  
**Author**: hypo69  

