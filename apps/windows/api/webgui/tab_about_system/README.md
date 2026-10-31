# ℹ️ Вкладка «О Системе» (About System Tab)

Интерактивная панель подробной спецификации оборудования, системной телеметрии и AI-диагностики хоста Windows с поддержкой сквозной наблюдаемости (Observability).

---

## 🏛️ Архитектура и блок-схема потока данных

```mermaid
flowchart TD
    subgraph Host_OS["💻 Хост Windows (Низкоуровневый слой)"]
        REG["Реестр Windows (winreg)<br/>• HKLM/CurrentVersion (InstallDate, Build)<br/>• HKLM/System/BIOS (Материнская плата)"]
        WIN32["Native Win32 API (ctypes)<br/>• Locale & Codepages (Kernel32)<br/>• Keyboard Layouts (User32)<br/>• WinAPI Capability Detector"]
        PSUTIL["Системные вызовы & psutil<br/>• CPU, RAM, Uptime, Диски, Сеть"]
        WMI_SENS["Аппаратные зонды & WMI/CIM<br/>• Нативные сенсоры Windows (Температуры, Нагрузка)"]
    end

    subgraph Windows_Subsystem["⚙️ Подсистема apps/windows (Единое ядро)"]
        COLLECTOR["apps.windows.telemetry.collector<br/><b>SystemCollector</b>"]
        
        subgraph Collector_Methods["Методы сбора фактов"]
            M_IDENT["get_system_identity()<br/>(Хост, Юзер, Локали, <b>InstallDate</b>)"]
            M_TREE["get_hardware_tree()<br/>(Иерархическое дерево узлов оборудования)"]
            M_METRICS["get_cpu_metrics() / get_disk_metrics()<br/>(Метрики производительности и дисков)"]
            M_SENS["get_hardware_sensors()<br/>(Сенсоры и температуры WMI/CIM)"]
        end

        subgraph Core_Managers["Менеджеры apps/windows/sdk/core"]
            SPM["system_param_manager<br/>(Безопасное управление + Restore Points)"]
            SWA["software_audit<br/>(Аудит ПО, Prefetch, UserAssist)"]
            DEF["defender_manager<br/>(Защитник Windows и Firewall)"]
        end

        MODELS["apps.windows.telemetry.models<br/><b>SystemSnapshot</b> & <b>HardwareNode</b>"]
    end

    subgraph AI_Observability["🧠 Слой AI-диагностики & Observability"]
        AI_ENGINE["src.ai.observability.engine<br/><b>ObservabilityDiagnosticsEngine</b>"]
        DIAG_ENGINE["src.ai.observability.system_engine<br/><b>SystemDiagnosticEngine</b>"]
        STAGES["Multi-stage Pipeline<br/>(Telemetry Analysis → Heuristic Evaluation → LLM Diagnosis)"]
        OBS_MODELS["src.ai.observability.models<br/><b>SystemDiagnosticReport</b><br/>• health_score, anomalies, recommendations<br/>• system_instruction, generated_prompt, raw_llm_response, error"]
    end

    subgraph API_Layer["🌐 Слой API (FastAPI)"]
        ROUTER["src.api.router_system.py<br/><b>/api/v1/system/*</b>"]
        EP_SUM["GET /api/v1/system/summary<br/>(Единый снимок SystemSnapshot)"]
        EP_HW["GET /api/v1/system/hardware<br/>(Дерево узлов HardwareNode)"]
        EP_SENS["GET /api/v1/system/sensors<br/>(Сенсоры WMI/CIM)"]
        EP_DIAG["POST /api/v1/system/diagnose<br/>(AI-диагностика и аудит телеметрии)"]
    end

    subgraph Frontend["🖥️ Веб-интерфейс (about_system_tab)"]
        GUI_MAIN["main.js<br/>(fetchSystemSummary, fetchHardwareSpec, fetchAIDiagnostics)"]
        
        subgraph UI_Components["Компоненты index.html"]
            UI_ID["<b>Карточка идентификации хоста</b><br/>• Имя ПК / Юзер / Локали / Часовой пояс<br/>• 📅 <b>Дата установки ОС</b><br/>• 🛡️ Резервное копирование / Сборка Windows / Обновления"]
            UI_KPI["<b>KPI Телеметрии</b><br/>• CPU, RAM, GPU, Диск (C:) I/O"]
            UI_SPEC["<b>Сводные таблицы</b><br/>• System Specification<br/>• Security & Firewall Profiles<br/>• Storage Volumes & Partitions"]
            UI_TREE["<b>Спецификация оборудования</b><br/>• Адаптивный CSS Grid (ключ-значение рядом)<br/>• Многоколоночный макет на широких экранах"]
            UI_AI["<b>AI Copilot & Observability Panel</b><br/>• Health Score & Индикаторы этапов сканирования<br/>• Аномалии и Рекомендации<br/>• Инспектор системной инструкции и промпта<br/>• Инспектор сырого ответа LLM и блок ошибок"]
        end
    end

    %% Связи Host -> Windows Subsystem
    REG --> M_IDENT
    REG --> M_TREE
    WIN32 --> M_IDENT
    PSUTIL --> M_METRICS
    WMI_SENS --> M_SENS

    %% Связи внутри Windows Subsystem
    COLLECTOR --> Collector_Methods
    Collector_Methods --> MODELS
    Core_Managers -.-> COLLECTOR

    %% Связи Windows Subsystem -> API
    MODELS --> ROUTER
    ROUTER --> EP_SUM
    ROUTER --> EP_HW
    ROUTER --> EP_SENS

    %% Связи AI Observability -> API
    MODELS --> DIAG_ENGINE
    DIAG_ENGINE --> AI_ENGINE
    AI_ENGINE --> STAGES
    STAGES --> OBS_MODELS
    OBS_MODELS --> EP_DIAG
    ROUTER --> EP_DIAG

    %% Связи API -> Frontend
    EP_SUM --> GUI_MAIN
    EP_HW --> GUI_MAIN
    EP_SENS --> GUI_MAIN
    EP_DIAG --> GUI_MAIN

    %% Связи Frontend -> UI
    GUI_MAIN --> UI_ID
    GUI_MAIN --> UI_KPI
    GUI_MAIN --> UI_SPEC
    GUI_MAIN --> UI_TREE
    GUI_MAIN --> UI_AI
```

---

## 📋 Возможности и компоненты интерфейса

1. **Окружение пользователя, сеть, региональные параметры и безопасность (User Environment, Network, Regional & Security)**:
   - Полная идентификация пользователя: имя и фамилия (`fullname`), системный логин (`@username`), уровень привилегий (`is_admin`), должность/описание, путь к каталогу профиля (`user_profile`), идентификатор безопасности SID (`user_sid`) и группы безопасности (`user_groups`).
   - Сетевая конфигурация: активный сетевой адаптер, категория профиля сети (Частная / Общедоступная с быстрым переключением), статус сетевого обнаружения Windows (Вкл / Выкл).
   - Модальное окно расширенных параметров (`#aboutRegionalSettingsModal`) с вкладками «Часовой пояс», «Язык и локали», «Учетная запись» и «Сеть и имя ПК» (с возможностью переименования компьютера и смены рабочей группы).
   - Язык интерфейса, локали пользователя и системы (`user_locale`, `system_locale`), кодовые страницы (ACP / OEM), раскладки клавиатуры.
   - 📅 **Дата чистой установки ОС** — прямое чтение времени установки Windows из системного реестра (`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\InstallDate`).
   - Номер сборки Windows, статус OneDrive, MS Office, брандмауэра Defender (Domain/Private/Public) и UAC.

2. **Сводные KPI-карточки и живая телеметрия**:
   - Мониторинг загрузки CPU (физические ядра, логические потоки, частота).
   - Оперативная память (RAM занято / свободно, процент использования).
   - Графический ускоритель (GPU модель, объем VRAM, нагрузка, поддержка CUDA / DirectML).
   - Активность накопителя C: (скорость чтения и записи в реальном времени).

3. **Спецификация оборудования (Hardware Tree)**:
   - Иерархическое дерево устройств (System, Processor, Motherboard, Memory, Display, Storage, Network).
   - **Верстка CSS Grid**: свойства отображаются в виде компактной адаптивной двухколоночной сетки (`minmax(140px, 200px) 1fr`), где ключ и значение находятся рядом друг с другом.
   - На широких мониторах список свойств автоматически распределяется по нескольким параллельным колонкам (`repeat(auto-fill, minmax(360px, 1fr))`).
   - Быстрый поиск компонентов и фильтрация на лету.

4. **Износ накопителей (Disks Health & Wear Panel)**:
   - Мониторинг износа и остаточного ресурса SSD / NVMe (SMART-статус, Health %).
   - Детальная таблица разделов с полосами износа, наработкой POH и счетчиками ввода/вывода (I/O).
   - Независимый опрос через `GET /api/v1/system/diagnostics/storage-wear`.

5. **Деградация и состояние батареи (Battery Deep Telemetry)**:
   - Самостоятельная полноразмерная панель в отдельной строке (`panel-about-battery`).
   - Телеметрия источника питания (AC Mains 220V / Battery).
   - Мониторинг уровня заряда, заводской емкости (Design Capacity) и текущей (Full Charge Capacity).
   - Расчет процента износа (Battery Wear Level %) и расчетного времени автономной работы.
   - Независимый опрос через `GET /api/v1/system/diagnostics/battery`.

6. **Интеллектуальная AI-диагностика и Observability**:
   - Многоэтапный конвейер аудита (*Multi-stage Diagnostic Pipeline*) со статусами выполнения в реальном времени.
   - Расчет индекса здоровья системы (*Health Score 0-100*).
   - Кластеризация и отображение аномалий по уровням важности (Warning, Critical, Info).
   - **Сквозная наблюдаемость (Observability)**:
     - 🛡️ Инспектор системной инструкции модели (*System Instruction Inspector*).
     - 📝 Инспектор сгенерированного промпта (*Sent Prompt Inspector*).
     - 🔬 Инспектор сырого ответа нейросети (*Raw LLM Response Inspector*).
     - ⚠️ Информативный блок ошибок с точной локализацией сбоев провайдеров.

---

## 🔌 API эндпоинты

- `GET /api/v1/system/summary` — получение сводного снимка телеметрии хоста (`SystemSnapshot`).
- `GET /api/v1/system/hardware` — получение иерархического дерева компонентов (`List[HardwareNode]`).
- `GET /api/v1/system/sensors` — сбор показателей нативных сенсоров оборудования (`List[HardwareSensor]`).
- `GET /api/v1/about-system/bundle` — единый одноразовый пакет всех данных вкладки (сводка, оборудование, разделы, износ дисков `disks_wear` и телеметрия батареи `battery_wear`).
- `GET /api/v1/system/diagnostics/storage-wear` — независимая телеметрия износа накопителей SSD/NVMe и SMART.
- `GET /api/v1/system/diagnostics/battery` — независимая глубокая телеметрия аккумулятора и питания.
- `GET /api/v1/system/diagnostics/storage-battery` — комбинированная телеметрия накопителей и батареи (обратная совместимость).
- `GET /api/v1/system/processes` — получение списка активных процессов хоста с метриками CPU/RAM.
- `POST /api/v1/system/diagnose` — запуск эвристического и AI-анализа телеметрии (`SystemDiagnosticReport`).

---

## 📂 Модульная структура Frontend (ES6)

Все скрипты вкладки декомпозированы на изолированные модули в директориях `panel_*` в строгом соответствии с лимитом <= 500 строк кода:

```text
tab_about_system/
├── index.html                           # Разметка вкладки и модальных окон
├── main.js                              # Корневой оркестратор (153 строки)
├── common/
│   └── ui_utils.js                      # Кеширующий fetch, экранирование HTML, бейджи (171 строка)
├── panel_kpi/
│   └── panel.js                         # KPI-карточки CPU, RAM, GPU, диска (59 строк)
├── panel_identity/
│   └── panel.js                         # Идентификация хоста, InstallDate, безопасность, износ дисков (418 строк)
├── panel_battery/
│   └── panel.js                         # Самостоятельная глубокая телеметрия батареи и питания (148 строк)
├── panel_hardware/
│   ├── panel.js                         # Дерево оборудования, сортировка, таблицы (280 строк)
│   └── enrichment.js                    # Спецификации вендоров, модальная история деталей (379 строк)
├── panel_ai_diagnostics/
│   ├── panel.js                         # Конвейер AI-диагностики, запуск групп, инспекторы (481 строка)
│   └── renderers.js                     # Отрисовка этапов, карточек доменов и аномалий (118 строк)
├── panel_regional_network/
│   ├── network.js                       # Профиль Public/Private и сетевое обнаружение (211 строк)
│   ├── regional.js                      # Имя ПК, рабочая группа, локали, часовой пояс (481 строка)
│   └── localization.js                  # Языковые пакеты Windows, таймзоны (155 строк)
└── panel_history/
    └── panel.js                         # Выборка срезов телеметрии из telemetry.db (179 строк)
```

