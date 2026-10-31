# Монитор Cloudflare Tunnel (Cloudflared Monitor)

**Статус:** ✅ Активен  
**Версия:** 1.0  
**Обновлено:** 2026-10-30 14:00:00  
**Автор:** hypo69  

---

## 📋 Назначение

Мониторинг, супервизия и управление процессом Cloudflare Tunnel (`cloudflared`). Обеспечивает наблюдение за процессом демона, потоковую передачу и парсинг логов (`logs/cloudflared.log`), проверку задержки общедоступной конечной точки `https://kino.davidka.net` и эвристическую диагностику состояния.

---

## 🏛️ Структура

```
apps/cloudflared_monitor/
├── __init__.py                # Инициализация и экспорт
├── __main__.py                # CLI (дашборд, сервер, диагностика)
├── config.json                # Конфигурация (порты, эндпоинты)
├── router.py                  # API эндпоинты (/api/cloudflared/*)
├── tui.py                     # Дашборд Rich TUI
├── README.md                  # Документация модуля
└── src/
    ├── __init__.py            # Внутренний экспорт
    └── state.py               # Логика супервизора, парсер логов, пробер сети
```

---

## 🚀 Запуск и команды

### Интерактивный TUI
```powershell
py -m apps.cloudflared_monitor
```

### Автономный API сервер (порт 8104)
```powershell
py -m apps.cloudflared_monitor --mode server --port 8104
```

### CLI инструменты
- `py -m apps.cloudflared_monitor --status` — Проверка статуса
- `py -m apps.cloudflared_monitor --health` — Диагностика состояния
- `py -m apps.cloudflared_monitor --logs` — Просмотр последних логов
- `py -m apps.cloudflared_monitor --restart` — Перезапуск

### Скрипты PowerShell
- `launchers/Run-Cloudflared.ps1` — Запуск и перезапуск процесса cloudflared с токеном из `.env`
- `launchers/Run-CloudflaredMonitor.ps1` — Запуск службы монитора в фоновом режиме или консоли

---

## 🌐 REST API

Базовый префикс: `/api/cloudflared`

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/status` | Статус процесса, токена, эндпоинта |
| `GET` | `/logs` | Парсинг логов с фильтрацией |
| `GET` | `/metrics` | Метрики (CPU, RAM, сеть) |
| `GET` | `/diagnostic` | Диагностика состояния и аномалий |
| `POST` | `/test-endpoint` | HTTP probe для публичной URL (`https://kino.davidka.net`) |
| `POST` | `/start`/`/stop`/`/restart` | Управление демоном |

---

## 🖥️ Веб-интерфейс WebGUI

Интерфейс вкладки расположен в `apps/windows/api/webgui/tab_cloudflared`:
- `index.html` — Оформление карточек телеметрии, терминала логов и блока рекомендаций.
- `main.js` — Контроллер вкладки с автообновлением статуса и функциями `initCloudflaredTab()` / `deactivateCloudflaredTab()`.
