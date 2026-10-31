# 🌐 Сетевой терминал Windows (`apps/windows/network`)

**Статус:** ✅ Активен  
**Язык:** Русский  
**Автор:** hypo69  
**Обновлено:** 2026-10-28 16:30:00

---

## 📋 Описание

Модуль `tab_network` интегрирует **Сетевой терминал Windows** (`/apps/windows/network`) в веб-панель управления AI-Windows-Admin.
Интерфейс спроектирован по стандарту **Subtabs Nav-Pills Hub** (как в `tab_software_scanner` и `tab_processes_load_inspector`), объединяя панели мониторинга под верхним меню суб-вкладок:
- **Тест скорости интернета (Speedtest)**: Замер скорости скачивания (Download, Mbps), отдачи (Upload, Mbps), задержки (Ping, ms), джиттера (Jitter) и определение внешнего IP/провайдера.
- **Обнаружение компьютеров в локальной сети (LAN Device Discovery)**: Автоматическое обнаружение компьютеров, рабочих станций, шлюзов и смарт-устройств в локальной сети через ARP-кеш ядра, параллельный ARP-свип по подсетям, SSDP/UPnP, NetBIOS/DNS разрешение имён, экспресс-сканирование открытых сетевых служб (SMB, RDP, HTTP, SSH) и AI-диагностику через `AIModalDialog`.
- **Инспекция сетевых адаптеров Windows**: Мониторинг адаптеров (IPv4, IPv6, MAC, скорость, статус соединения, отправлено/принято байт).
- **Таблица соединений и портов**: Активные TCP/UDP соединения и слушающие сокеты с сопоставлением с процессами Windows и PID.
- **Захват пакетов в реальном времени (DPI)**: Инспекция сетевых заголовков и полезной нагрузки.
- **PCAP-анализ и AI-диагностика**: Загрузка дампов трафика и автоматический эвристический аудит аномалий.

---

## 🏗 Архитектура модулей

```
tab_network/
├── index.html                  # Разметка вкладки, карточек KPI, таблиц и суб-вкладок
├── main.js                     # Корневой скрипт-оркестратор (инициализация, навигация)
├── common/
│   └── ui_utils.js             # Форматирование сетевых байтов (B, KB, MB, GB, TB)
├── panel_kpi_status/
│   └── panel.js                # Панель верхних KPI (адаптеры, сокеты, статус TShark DPI)
├── panel_speedtest/
│   └── panel.js                # Замер скорости интернета, пинга, джиттера и опрос DNS
├── panel_discovery/
│   └── panel.js                # Автоматическое обнаружение компьютеров в LAN, проверка портов, AI-анализ
├── panel_adapters/
│   └── panel.js                # Мониторинг сетевых адаптеров Windows и их метрик
├── panel_connections/
│   └── panel.js                # Таблица активных TCP/UDP соединений и портов, AITableModal
└── panel_capture_pcap/
    └── panel.js                # Живой перехват пакетов через SSE, анализ и загрузка PCAP дампов
```

---

### 🔬 Диагностика сетевой инфраструктуры (панели panel-network-*)

В тот же блок меню #network-subtabs-nav добавлены панели с DOM-идентификаторами panel-network-overview, panel-network-adapters (бывший 	ab-net-adapters, дополнен инвентаризацией), panel-network-switches, panel-network-ip-config, panel-network-nat, panel-network-wsl, panel-network-diagnostics, panel-network-history. Переключение — штатный Bootstrap-механизм + существующий обработчик shown.bs.tab в main.js. Код: panel_infra/{api,render,panel}.js. Backend и документация: [sdk/modules/network/infra](../../../sdk/modules/network/infra/README.md), API /api/network/infra/*.

## 🚀 Основные эндпоинты API

- `GET /api/network/devices` — Список обнаруженных компьютеров и хостов в LAN (кеш соседей ядра или активный опрос)
- `POST /api/network/devices/scan` — Запуск активного параллельного ARP-свипа и SSDP поиска по подсети
- `GET /api/network/devices/probe` — Экспресс-проверка доступности стандартных портов хоста (SMB, RDP, HTTP, SSH, WinRM)
- `GET /api/network/subnets` — Список активных подсетей хоста и шлюзов по умолчанию
- `GET /api/v1/system/network-profile` — Диагностика сетевого обнаружения Windows, брандмауэра и служб
- `POST /api/v1/system/network-discovery/toggle` — Включение сетевого обнаружения Windows и служб публикации
- `POST /api/network/speedtest/run` — Полный замер скорости интернета, пинга и качества соединения
- `GET /api/network/speedtest/ping` — Экспресс-пинг к опорным DNS и CDN серверам
- `GET /api/network/speedtest/latest` — Получение последнего отчета теста скорости
- `GET /api/network/status` — Общий статус сетевой подсистемы
- `GET /api/network/interfaces` — Список всех сетевых адаптеров хоста
- `GET /api/network/connections` — Активные сетевые соединения и открытые порты
- `GET /api/network/telemetry` — Метрики скорости передачи в реальном времени
- `GET /api/network/packets` — Буфер захваченных пакетов
- `POST /api/network/start-capture` / `POST /api/network/stop-capture` — Управление захватом пакетов
- `POST /api/network/analyze/pcap` — Анализ загруженного файла дампа PCAP
