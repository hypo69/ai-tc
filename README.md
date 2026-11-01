<!--
File: README.md
Path: README.md
Description: Главный файл описания проекта AI Windows Admin (AI-TC) для GitHub.
Author: hypo69
Created: 2026-10-10
Updated: 2026-11-01 12:17:00
-->

# 🖥️ AI Windows Admin (AI-TC)

[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://hypo69.github.io/aiwindowsadmin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10–3.14](https://img.shields.io/badge/python-3.10--3.14-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/hypo69/AI-TC)

**AI Windows Admin (`ai-tc`)** — модульная интерактивная платформа администрирования ОС Windows, аппаратной телеметрии, диагностики и бесшовной маршрутизации между облачными и локальными языковыми моделями искусственного интеллекта.

Название отсылает к концепции «макетной платы» и командного центра (`Total Control` / `Telemetry Center`): различные ИИ-провайдеры, системные коллекторы, навыки (`Skills`), плагины (`Plugins`) и MCP-серверы подключаются как сменные компоненты через единую шину без переписывания кода.

> [!IMPORTANT]
> **Философия платформы:**  
> *«Если рабочий процесс начинает состоять из слишком большого количества отдельных инструментов, это рано или поздно начинает раздражать. Все инструменты диагностики, телеметрии и ИИ-агенты должны работать в едином пространстве.»*

---

## 📑 Содержание

- [Ключевые возможности](#-ключевые-возможности)
- [Архитектура](#-архитектура)
- [Требования к системе](#-требования-к-системе)
- [Установка](#-установка)
  - [Опция 1: Полная автоустановка в одну строку PowerShell (скачивание Git + запуск install.ps1)](#опция-1-полная-автоустановка-в-одну-строку-powershell-скачивание-git--запуск-installps1)
  - [Опция 2: Быстрый запуск онлайн-инсталлятора](#опция-2-быстрый-запуск-онлайн-инсталлятора)
  - [Опция 3: Стандартная установка через Git](#опция-3-стандартная-установка-через-git)
  - [Опция 4: Ручная установка в виртуальное окружение](#опция-4-ручная-установка-в-виртуальное-окружение)
- [Настройка (`.env` и `config.json`)](#-настройка-env-и-configjson)
- [Запуск и использование](#-запуск-и-использование)
- [Интерфейсы доступа](#-интерфейсы-доступа)
- [Структура проекта](#-структура-проекта)
- [Тестирование](#-тестирование)
- [Устранение неполадок](#-устранение-неполадок)
- [Документация](#-документация)
- [Лицензия](#-лицензия)

---

## ✨ Ключевые возможности

### 🤖 Единая шина ИИ-провайдеров (`UnifiedChatModel`)
Бесшовное переключение и маршрутизация запросов между облачными и локальными моделями по префиксу:

| Провайдер | Префикс | Тип | Описание |
|---|---|---|---|
| **Google Gemini SDK** | `gemini:<model>` | ☁️ Облако | Прямая работа через `google-genai` с пулингом и авто-ротацией ключей |
| **Gemini CLI** | `gemini_cli:<model>` | 💻 Локальный CLI | Автономный CLI-агент Google Gemini |
| **Antigravity SDK (AGY)** | `agy:<model>` | ☁️ Облако / Агент | Мультиагентная среда Google Antigravity |
| **OpenAI / DeepSeek / Groq** | `openai:` / `deepseek:` / `groq:` | ☁️ Облако | Любые OpenAI-совместимые облачные API |
| **Microsoft Foundry Local** | `foundry:<model>` | 🌐 Локальный сервер | Локальный инференс через Microsoft AI Foundry |
| **Ollama / LM Studio** | `ollama:<model>` | 🌐 Локальный сервер | Локальные LLM-серверы |
| **ONNX Runtime / DirectML** | `onnx:<model>` | 💾 На устройстве | Аппаратное ускорение на GPU/NPU через Windows ML |
| **Hugging Face** | `hf:<model>` | 💾 На устройстве | Локальные модели Transformers |

### 🛠️ Центр диагностики и управления Windows (`apps/windows`)
- **15 доменных коллекторов ОС**: оборудование, датчики температур, SMART и износ накопителей, процессы, службы, планировщик задач, сеть, драйверы, журналы событий (`EventLog`), безопасность и целостность ОС.
- **Фоновая телеметрия (`SQLite`)**: непрерывный сбор метрик производительности и состояния датчиков в `telemetry.db`.
- **Протокол безопасного исполнения `SafeOps`**: классификация команд по уровням риска (`OBSERVE`, `DIAGNOSE`, `CONTROL`, `ADMIN`, `DESTRUCTIVE`), режим симуляции (`Dry-Run`) и автоматические точки восстановления.
- **База знаний `WikiLLM`**: локальная интерактивная энциклопедия процессов, служб, событий Windows и оборудования с ИИ-обогащением.

### 🧩 Расширяемая экосистема
- **Навыки (`Skills`)**: модульные инструменты в `.agents/skills/` для автономного выполнения диагностических и административных сценариев.
- **MCP-серверы (`.mcp/`)**: готовые серверы Model Context Protocol (поиск по RAG, управление FastAPI, SSH, авто-коммиты, Playwright).
- **RAG и база знаний**: векторный и семантический поиск по локальным документам, логам и кодовой базе проекта.

---

## 🏗️ Архитектура

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              ИНТЕРФЕЙСЫ ДОСТУПА                                  │
├──────────────────────────────────────┬───────────────────────────────────────────┤
│     Веб-интерфейс WebGUI (/tc)       │           CLI и Агенты                    │
│   • Панели диагностики и телеметрии  │   • tc.ps1 / main.py                      │
│   • Интерактивный ИИ-ассистент       │   • manage_tools.py                       │
│   • WikiLLM и Редактор сценариев     │   • Gemini CLI / Antigravity Skills       │
└──────────────────┬───────────────────┴─────────────────────┬─────────────────────┘
                   │                                         │
                   └────────────────────┬────────────────────┘
                                        ▼
                        ┌───────────────────────────────┐
                        │     FastAPI + WebSocket Hub   │
                        │   • Маршрутизация API         │
                        │   • Стриминг телеметрии       │
                        └───────────────┬───────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐      ┌────────────────────────┐
│   TELEMETRY & SDK   │      │   AI ОРКЕСТРАТОР    │      │   RAG & БАЗА ЗНАНИЙ    │
│ • SystemCollector   │      │ • UnifiedChatModel  │      │ • WikiLLM (SQLite)     │
│ • 15 Доменов ОС     │      │ • ModelManager      │      │ • FAISS / Embeddings   │
│ • SafeOps Guard     │      │ • Пул API-ключей    │      │ • Локальные документы  │
└─────────────────────┘      └─────────────────────┘      └────────────────────────┘
```

---

## 💻 Требования к системе

| Компонент | Минимальные требования | Рекомендуемые требования |
|---|---|---|
| **ОС** | Windows 10 / 11 (x64), Linux, macOS | Windows 11 Pro / Enterprise (23H2+) |
| **Python** | Python `3.10` – `3.14` | Python `3.12` или `3.14` |
| **ОЗУ (RAM)** | 4 ГБ (для облачных моделей) | 16 ГБ+ (для локальных моделей Ollama / ONNX) |
| **Диск** | 2 ГБ свободного места | 20 ГБ+ (с учетом кэша моделей и БД телеметрии) |
| **Оболочка** | PowerShell 5.1+ / Bash | PowerShell 7+ (`pwsh`) |

---

## 🚀 Установка

### Опция 1: Полная автоустановка в одну строку PowerShell (скачивание Git + запуск `install.ps1`)

Если на чистой системе еще **не установлен Git**, выполните следующую однострочную команду в **PowerShell (от имени Администратора)**. Команда автоматически проверит наличие Git, при необходимости скачает и установит его (через `winget` или прямой установщик Git for Windows), обновит переменные среды `PATH`, склонирует репозиторий и запустит `install.ps1`:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-Host "Установка Git..." -ForegroundColor Cyan; if (Get-Command winget -ErrorAction SilentlyContinue) { winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent } else { $gitUrl = (Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest").assets | Where-Object { $_.name -match "Git-.*-64-bit\.exe$" } | Select-Object -First 1 -ExpandProperty browser_download_url; $gitInstaller = "$env:TEMP\git-installer.exe"; Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller; Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP-" -Wait; Remove-Item $gitInstaller -Force }; $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User") }; $targetDir = "$env:LOCALAPPDATA\AI-TC"; if (-not (Test-Path "$targetDir\.git")) { git clone https://github.com/hypo69/AI-TC.git $targetDir }; Set-Location $targetDir; .\install.ps1
```

### Опция 2: Быстрый запуск онлайн-инсталлятора

Если вы хотите запустить скрипт установки напрямую из репозитория:

```powershell
irm https://raw.githubusercontent.com/hypo69/AI-TC/master/install.ps1 | iex
```

### Опция 3: Стандартная установка через Git

Если Git уже установлен на вашем компьютере:

```powershell
# Windows (PowerShell)
git clone https://github.com/hypo69/AI-TC.git
cd AI-TC
.\install.ps1
```

```bash
# Linux / macOS
git clone https://github.com/hypo69/AI-TC.git
cd AI-TC
bash install.sh
```

### Опция 4: Ручная установка в виртуальное окружение

Полный пошаговый регламент описан в [INSTALL-INSTRUCTION.md](INSTALL-INSTRUCTION.md):

```powershell
# 1. Разблокировка скриптов (Windows)
Get-ChildItem -Path . -Recurse -File -Include "*.ps1","*.cmd" | Unblock-File -ErrorAction SilentlyContinue

# 2. Первоочередной запуск фоновой телеметрии
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File .\tlm.ps1"

# 3. Создание виртуального окружения и установка пакетов
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\venv\Scripts\pip.exe install -r requirements.txt

# 4. Создание файла секретов и генерация SSL-сертификатов
Copy-Item .env.example .env
.\venv\Scripts\python.exe scripts/maintenance/generate_ssl_certs.py

# 5. Верификация целостности установки
.\venv\Scripts\python.exe .agents/skills/project-installer/scripts/verify_installation.py
```

---

## ⚙️ Настройка (`.env` и `config.json`)

В проекте строго разделены секретные ключи (`.env`) и системная конфигурация (`config.json`).

1. Откройте файл `.env` и заполните ключи доступа:
   ```ini
   # Основной ключ Google Gemini API (поддерживается пул GEMINI_API_KEY_1, GEMINI_API_KEY_2...)
   GEMINI_API_KEY=ваш_ключ_gemini

   # Секрет для подписи JWT-токенов сессий
   JWT_SECRET=ваша_случайная_строка_64_символа

   # Пароль администратора веб-интерфейса
   ADMIN_PASSWORD=ваш_надежный_пароль
   ```
2. При необходимости настройте сетевые порты, SSL и параметры моделей в [config.json](config.json).

---

## 🚦 Запуск и использование

### Запуск основного сервера и WebGUI
```powershell
# Через лаунчер PowerShell (рекомендуется)
.\tc.ps1

# Или напрямую через виртуальное окружение Python
.\venv\Scripts\python.exe main.py
```

### Запуск службы телеметрии
```powershell
# Запуск фонового сборщика метрик
.\tlm.ps1

# Просмотр статуса телеметрии в консоли
.\show-tlm.ps1
```

### Универсальный CLI-менеджер инструментов (`manage_tools.py`)
```powershell
py manage_tools.py skills list          # Список доступных навыков ИИ
py manage_tools.py rag build            # Построение индекса базы знаний RAG
py manage_tools.py db check-integrity   # Проверка целостности баз данных SQLite
py manage_tools.py docs generate        # Генерация документации
```

---

## 🌐 Интерфейсы доступа

После запуска сервера доступны следующие веб-интерфейсы:

| Интерфейс | URL по умолчанию | Назначение |
|---|---|---|
| **Панель управления TC (WebGUI)** | `http://127.0.0.1:8001/tc` | Главный центр мониторинга, диагностики Windows, оборудования и WikiLLM |
| **Swagger UI (OpenAPI)** | `http://127.0.0.1:8001/docs` | Интерактивная документация всех REST API эндпоинтов |
| **ReDoc API** | `http://127.0.0.1:8001/redoc` | Спецификация API для разработчиков |

*(При активном SSL в `config.json` используйте протокол `https://`)*

---

## 📂 Структура проекта

```text
AI-TC/
├── .agents/skills/       # Автономные навыки (Skills) для ИИ-агентов и установщика
├── .ai/instructions/     # Инженерные стандарты, правила кода и документация архитектуры
├── .mcp/                 # Серверы Model Context Protocol (MCP)
├── apps/
│   ├── windows/          # Ядро диагностики Windows, SDK, коллекторы, телеметрия и WebGUI
│   ├── cloudflared_monitor/ # Мониторинг туннелей Cloudflared
│   └── tshark/           # Интеграция сетевого анализатора трафика
├── data/                 # Базы знаний WikiLLM, векторные индексы RAG и снапшоты
├── docs/                 # Документация проекта (MkDocs, RU/EN)
├── install/              # Профили зависимостей (requirements-*.txt) и скрипты установки
├── launchers/            # Скрипты запуска сервисов и тестовых прогонов
├── logger/               # Стандартизированная подсистема логирования
├── plugins/              # Системные и пользовательские плагины
├── scripts/              # Утилиты обслуживания, генерации сертификатов и сборки
├── src/                  # ИИ-оркестратор, управление моделями, конфигурация и ядро сервера
├── tests/                # Модульные и интеграционные тесты (Pytest)
├── config.json           # Системная конфигурация платформы
├── INSTALL-INSTRUCTION.md# Полный регламент установки и самодиагностики
├── main.py               # Точка входа веб-сервера приложения
├── manage_tools.py       # CLI-утилита управления инструментами проекта
├── tc.ps1                # Главный скрипт запуска AI-TC
└── tlm.ps1               # Лаунчер фоновой службы телеметрии
```

---

## 🧪 Тестирование

Проект разрабатывается по методологии **TDD (Test-Driven Development)**:

```powershell
# Полный тестовый прогон через лаунчер
.\launchers\run_tests.ps1

# Запуск pytest с отчетом о покрытии кода
.\venv\Scripts\pytest.exe tests/ --cov
```

---

## 🛠️ Устранение неполадок

| Проблема | Причина | Решение |
|---|---|---|
| `Выполнение скриптов отключено в этой системе` | Политика `ExecutionPolicy` в Windows | Выполните: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` |
| `Порт 8001 занят` | Запущен предыдущий экземпляр сервера | `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess -Force` |
| `SSL certificate not found` | Не созданы локальные сертификаты | Запустите: `.\venv\Scripts\python.exe scripts/maintenance/generate_ssl_certs.py` |
| `Python не найден` при создании `venv` | Псевдоним Microsoft Store перехватывает `python.exe` | Используйте лаунчер `py -3.14 -m venv venv` или отключите псевдонимы выполнения в параметрах Windows |

---

## 📚 Документация

- [Инструкция по установке (`INSTALL-INSTRUCTION.md`)](INSTALL-INSTRUCTION.md)
- [Мастер-индекс стандартов разработки (`GEMINI.md`)](GEMINI.md)
- [Документация в каталоге `docs/`](docs/README.md)

Для локального просмотра сайта документации MkDocs:
```powershell
mkdocs serve
```

---

## 📄 Лицензия

Проект распространяется под лицензией **MIT**. Подробности см. в файле лицензии.  
© 2026 **hypo69**
