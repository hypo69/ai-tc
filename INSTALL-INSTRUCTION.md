# 📦 Инструкция по установке AI-Windows-Admin (ai-tc)
# Updated: 2026-10-31 19:10:00
# Author: hypo69

Данный документ определяет полный регламент установки, предварительные проверки, настройку окружения и проверку целостности проекта **AI Windows Admin (ai-tc)** на платформах Windows, Linux и macOS.

> [!NOTE]
> Настоящая инструкция является единым стандартом как для ручного развертывания администратором, так и для автономного агента установки (`.agents/skills/project-installer`).

---

## 🎯 Архитектурные принципы установки

1. **Изолированное окружение:** Работа выполняется в выделенном виртуальном окружении Python (`venv`).
2. **Первоочередной старт телеметрии:** Перед проверками и установкой запускается служба телеметрии (`tlm.ps1`), фиксирующая состояние системы.
3. **Конфигурация превыше хардкода:** Все системные параметры считываются из `config.json`, секреты и API-ключи — строго из `.env`.
4. **Отказоустойчивость и самодиагностика:** Автоматическая валидация портов, путей и модулей через утилиту `verify_installation.py`.

---

## 🚀 Этап 0: Первоочередной запуск телеметрии

Перед выполнением любых дальнейших шагов развертывания обязательно запускается системная телеметрия:

- **Windows (PowerShell):**
  ```powershell
  Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File .\tlm.ps1"
  ```
- **Linux / macOS (Bash):**
  ```bash
  python3 apps/windows/telemetry/main.py &
  ```

Убедитесь, что процесс телеметрии успешно стартовал и создает метрики в `telemetry.db`.

---

## 🏗️ Этап 1: Предварительные проверки (Pre-Flight Checks)

### 1.1 Требования к операционной системе
- **Windows:** Windows 10/11 x64, PowerShell 5.1+ или PowerShell 7+ (`$PSVersionTable`).
- **Linux / macOS:** Ubuntu 22.04+, Debian 12+, Fedora 38+, macOS 13+ (x86_64 или arm64).

### 1.2 Проверка интерпретатора Python
- Требуется Python версии **3.10 – 3.14** (рекомендуется **3.12** / **3.14**).
- На Windows: избегайте нулевых псевдонимов Microsoft Store (`WindowsApps\python.exe`). Используйте лаунчер `py` или полный путь к установленному Python.

### 1.3 Разблокировка файлов скриптов (Windows)
При загрузке архива скрипты PowerShell могут быть заблокированы атрибутом Zone.Identifier:
```powershell
Get-ChildItem -Path . -Recurse -File -Include "*.ps1","*.cmd" | Unblock-File -ErrorAction SilentlyContinue
```

---

## ⚙️ Этап 2: Пошаговый процесс установки

### Шаг 1: Создание виртуального окружения (`venv`)
```powershell
# Windows
py -3.14 -m venv venv
# или: python -m venv venv

# Linux / macOS
python3 -m venv venv
```

### Шаг 2: Обновление базовых инструментов упаковки
```powershell
# Windows
.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel

# Linux / macOS
./venv/bin/python -m pip install --upgrade pip setuptools wheel
```

### Шаг 3: Установка зависимостей проекта
Выберите необходимый профиль зависимостей:

1. **Полная установка (Рекомендуется):**
   ```powershell
   .\venv\Scripts\pip.exe install -r requirements.txt
   ```
2. **Базовый профиль ядра (Core):**
   ```powershell
   .\venv\Scripts\pip.exe install -r install/req/requirements-core.txt
   ```
3. **ИИ-модули (Google GenAI, Antigravity SDK):**
   ```powershell
   .\venv\Scripts\pip.exe install -r install/req/requirements-ai.txt
   ```
4. **Тесты и документация:**
   ```powershell
   .\venv\Scripts\pip.exe install -r install/req/requirements-test.txt -r install/req/requirements-docs.txt
   ```

### Шаг 4: Настройка файла секретов (`.env`)
1. Скопируйте шаблон секретов:
   ```powershell
   copy .env.example .env
   ```
2. Откройте `.env` и укажите необходимые ключи:
   - `GEMINI_API_KEY` — ключ Google Gemini API
   - `JWT_SECRET` — секрет для сессий (генерация: `py -c "import secrets; print(secrets.token_urlsafe(64))"`)
   - `ADMIN_PASSWORD` — пароль доступа к панели управления

### Шаг 5: Настройка SSL-сертификатов (HTTPS)
Для работы веб-интерфейса и защищенных WebSockets:
- Сертификаты по умолчанию располагаются в `%USERPROFILE%\.certs\`:
  - `localhost+2.pem` (сертификат)
  - `localhost+2-key.pem` (приватный ключ)
- Генерация через утилиту обслуживания:
  ```powershell
  .\venv\Scripts\python.exe scripts/maintenance/generate_ssl_certs.py
  ```
  *(Или через mkcert: `mkcert -key-file ~/.certs/localhost+2-key.pem -cert-file ~/.certs/localhost+2.pem localhost 127.0.0.1 ::1`)*

### Шаг 6: Интеграция глобального CLI (`assist`)
Зарегистрируйте глобальные команды вызова:
```powershell
.\assist.ps1 --help
```
Переменная `AIWINDOWSADMIN_DIR` и `AITC_DIR` указывает на корневую директорию проекта.

---

## 🔍 Этап 3: Проверка целостности установки

Запустите автоматическую проверку всех путей, директорий, конфигураций и импортов модулей:
```powershell
# Текстовый отчет
.\venv\Scripts\python.exe .agents/skills/project-installer/scripts/verify_installation.py

# Или вывод в формате JSON:
.\venv\Scripts\python.exe .agents/skills/project-installer/scripts/verify_installation.py --json
```

Чек-лист проверки:
- [x] Каталоги: `apps`, `src`, `scripts`, `launchers`, `docs`, `tests`, `install`, `data`, `logger`, `.agents`, `venv`
- [x] Файлы: `header.py`, `config.json`, `requirements.txt`, `.env` / `.env.example`
- [x] Модули Python: `fastapi`, `uvicorn`, `pydantic`, `dotenv`, `cryptography`, `aiohttp`, `platformdirs`, `psutil`
- [x] Код возврата: `0`

---

## 🚦 Этап 4: Запуск приложения

```powershell
# Стандартный запуск WebGUI сервера
.\venv\Scripts\python.exe main.py

# Либо через лаунчер TC:
.\tc.ps1

# Либо через командный менеджер:
py manage_tools.py --help
```
Веб-интерфейс доступен по адресу: `http://127.0.0.1:8001/tc` (или `https://127.0.0.1:8001/tc` при включенном SSL).

---

## 🛠️ Матрица решения типовых проблем (Self-Healing)

| Симптом / Ошибка | Причина | Автоматическое исправление |
|---|---|---|
| `running scripts is disabled` | Политика выполнения PowerShell | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` |
| `Порт 8001 / 8000 занят` | Зависший процесс сервера | Автоматически завершается `free_port_if_occupied()` в `main.py` или `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess -Force` |
| `SSL certificate not found` | Отсутствует `.certs` | Запустить `py scripts/maintenance/generate_ssl_certs.py` либо переключить `"use_ssl": false` в `config.json` |
| `No module named 'logger'` | Корневой путь не в `sys.path` | Всегда импортировать `header` первым в начале скрипта: `import header; from logger import logger` |
