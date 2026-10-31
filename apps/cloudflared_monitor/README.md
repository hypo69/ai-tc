# Монитор Cloudflare Tunnel (`apps/cloudflared_monitor`)

**Статус:** ✅ Активен  
**Язык:** Русский  
**Автор:** hypo69  
**Обновлено:** 2026-10-30 14:00:00  

---

## 📋 Описание

Модуль `apps/cloudflared_monitor` предназначен для контроля и супервизии демона Cloudflare Tunnel (`cloudflared`). Он обеспечивает наблюдение за состоянием процесса в реальном времени, потоковый парсинг журналов (`logs/cloudflared.log`), проверку доступности и задержки публичного эндпоинта (`https://kino.davidka.net`), а также эвристическую и ИИ-диагностику сбоев.

---

## 🏛️ Структура каталога

```
apps/cloudflared_monitor/
├── __init__.py                # Инициализация пакета и публичный экспорт
├── __main__.py                # Точка входа CLI (дашборд, сервер, проверка статуса)
├── config.json                # Конфигурация приложения (порты, эндпоинты)
├── router.py                  # REST эндпоинты FastAPI (/api/cloudflared/*)
├── tui.py                     # Интерактивный терминальный дашборд Rich
├── README.md                  # Документация модуля
└── src/
    ├── __init__.py            # Внутренний экспорт
    └── state.py               # Ядро супервизора, парсер логов, пробер сети и диагностика
```

---

## 🚀 Варианты запуска и CLI команды

### 1. Интерактивный терминальный интерфейс (TUI)
```powershell
py -m apps.cloudflared_monitor
```

### 2. Выделенный микросервис FastAPI (порт 8104)
```powershell
py -m apps.cloudflared_monitor --mode server --port 8104
```

### 3. Быстрые команды CLI
```powershell
# Проверка текущего статуса
py -m apps.cloudflared_monitor --status

# Статус в формате JSON
py -m apps.cloudflared_monitor --status --json

# Комплексная диагностика здоровья
py -m apps.cloudflared_monitor --health

# Просмотр последних строк журнала
py -m apps.cloudflared_monitor --logs --limit 30

# Запуск / Перезапуск / Остановка
py -m apps.cloudflared_monitor --start
py -m apps.cloudflared_monitor --restart
py -m apps.cloudflared_monitor --stop
```

---

## 🌐 REST API Эндпоинты

Базовый путь: `/api/cloudflared`

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/api/cloudflared/status` | Состояние процесса, токена, доступность эндпоинта |
| `GET` | `/api/cloudflared/logs` | Распарсенные записи лога с фильтрацией по уровням |
| `GET` | `/api/cloudflared/metrics` | Телеметрия CPU, RAM, времени работы и сетевой задержки |
| `GET` | `/api/cloudflared/diagnostic` | ИИ/эвристическая диагностика, аномалии и рекомендации |
| `POST` | `/api/cloudflared/test-endpoint` | Немедленная HTTP-проверка публичного URL |
| `POST` | `/api/cloudflared/start` | Запуск демона (требуются права администратора) |
| `POST` | `/api/cloudflared/stop` | Остановка демона (требуются права администратора) |
| `POST` | `/api/cloudflared/restart` | Перезапуск демона (требуются права администратора) |
