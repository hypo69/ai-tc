---
name: project-installer
# Updated: 2026-10-31 19:10:00
description: "Интерактивный установщик проекта и конфигуратор окружения для AI Windows Admin (ai-tc). Пошагово выполняет предварительные проверки, запуск телеметрии, создание venv, установку зависимостей из requirements.txt, настройку .env, генерацию SSL-сертификатов и верификацию целостности."
description_i18n:
  ru: "Интерактивный установщик проекта и конфигуратор окружения для AI Windows Admin (ai-tc). Пошагово выполняет предварительные проверки, запуск телеметрии, создание venv, установку зависимостей из requirements.txt, настройку .env, генерацию SSL-сертификатов и верификацию целостности."
  en: "Interactive full-project installer and environment configurator for AI Windows Admin (ai-tc). Step-by-step pre-flight checks, telemetry startup, venv creation, requirements.txt installation, .env setup, SSL certs, and integrity verification."
---

# 🚀 Навык установки проекта AI Windows Admin (ai-tc)

Данный навык предназначен для автономных агентов и Gemini CLI для пошаговой установки, конфигурации, диагностики неполадок и полной верификации проекта **AI Windows Admin (ai-tc)** на Windows, Linux и macOS.

---

## 💻 Запуск через Gemini CLI

Для интерактивного запуска установщика через Gemini CLI:

```powershell
# Windows (PowerShell)
gemini --model "gemini-3.1-flash-lite" --prompt "Активируй навык project-installer. Прочти INSTALL-INSTRUCTION.md и пошагово проведи установку AI Windows Admin с запуском телеметрии, созданием venv, установкой зависимостей и финальной верификацией."

# Либо через готовый скрипт:
.\.agents\skills\project-installer\scripts\run_installer_gemini.ps1
```

```bash
# Linux / macOS (Bash)
bash .agents/skills/project-installer/scripts/run_installer_gemini.sh
```

---

## 📖 Обязательные источники и регламенты

Перед выполнением шагов установки агент **ОБЯЗАН** изучить:
- [INSTALL-INSTRUCTION.md](file:///c:/Users/onela/AppData/Local/ai-tc/INSTALL-INSTRUCTION.md) — регламент установки в корне проекта.
- [requirements.txt](file:///c:/Users/onela/AppData/Local/ai-tc/requirements.txt) — реестр зависимостей проекта.
- [.env.example](file:///c:/Users/onela/AppData/Local/ai-tc/.env.example) — шаблон переменных окружения и секретов.
- [config.json](file:///c:/Users/onela/AppData/Local/ai-tc/config.json) — системная конфигурация сервисов и портов.

---

## 🤖 Протокол работы агента (Интерактивный режим)

При активации навыка модель выполняет шаги последовательно, выводя статус пользователю и решая возникающие ошибки:

### Этап 0: Первоочередной запуск телеметрии (`tlm.ps1`)
1. Перед началом любых других действий запустить службу телеметрии:
   ```powershell
   Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File .\tlm.ps1"
   ```
2. Убедиться, что процесс фонового сбора телеметрии запущен (`telemetry.db`).

### Этап 1: Предварительные проверки (Pre-Flight)
1. Определить операционную систему (`platform.system()`) и архитектуру процессора.
2. Проверить доступные интерпретаторы Python:
   - Требуется Python версии **3.10 – 3.14** (рекомендуется 3.12 или 3.14).
   - На Windows убедиться, что лаунчер `py` указывает на реальный интерпретатор, а не пустой алиас Windows Store.
3. Проверить наличие Git и интернет-соединения для загрузки пакетов.

### Этап 2: Пошаговая установка
1. **Разблокировка файлов скриптов (Windows):**
   ```powershell
   Get-ChildItem -Path . -Recurse -File -Include "*.ps1","*.cmd" | Unblock-File -ErrorAction SilentlyContinue
   ```
2. **Создание и проверка виртуального окружения (`venv`):**
   - Создать окружение: `py -3.14 -m venv venv` (или `python -m venv venv`).
   - Проверить наличие `venv\Scripts\python.exe` (Windows) или `venv/bin/python` (Linux/macOS).
3. **Обновление pip и установка зависимостей:**
   - Обновить: `.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel`.
   - Установить зависимости:
     - Полный профиль: `pip install -r requirements.txt`
     - Базовый профиль ядра: `pip install -r install/req/requirements-core.txt`
     - ИИ-провайдеры: `pip install -r install/req/requirements-ai.txt`
4. **Конфигурация секретов (`.env`):**
   - Создать `.env` из шаблона `.env.example`, если он отсутствует.
   - Проверить обязательные переменные: `GEMINI_API_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD`.
5. **Генерация SSL-сертификатов (HTTPS):**
   - Проверить наличие сертификата `localhost+2.pem` и ключа `localhost+2-key.pem` в `%USERPROFILE%\.certs\`.
   - При отсутствии сгенерировать через `py scripts/maintenance/generate_ssl_certs.py` или `mkcert`.
6. **Глобальный CLI (`assist`):**
   - Убедиться в доступности `assist.ps1`, задать переменную среды `AIWINDOWSADMIN_DIR`.

---

## 🧪 Этап 3: Автоматическая проверка целостности

После установки агент **ОБЯЗАН** запустить утилиту валидации целостности:

```powershell
# Запуск утилиты проверки
python .agents/skills/project-installer/scripts/verify_installation.py

# Или в формате JSON:
python .agents/skills/project-installer/scripts/verify_installation.py --json
```

### Чек-лист валидации:
- [x] Каталоги: `apps`, `src`, `scripts`, `launchers`, `docs`, `tests`, `install`, `data`, `logger`, `.agents`
- [x] Файлы: `header.py`, `config.json`, `requirements.txt`, `INSTALL-INSTRUCTION.md`, `.env` / `.env.example`
- [x] Окружение venv: статус `active`, корректный путь к `python.exe`
- [x] Модули ядра: `fastapi`, `uvicorn`, `pydantic`, `dotenv`, `cryptography`, `aiohttp`, `platformdirs`, `psutil`
- [x] Код завершения скрипта равен `0`

---

## 🛠️ Матрица самовосстановления (Self-Healing Matrix)

| Ошибка | Причина | Автоматическое действие |
|---|---|---|
| `running scripts is disabled` | Политика PowerShell | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` |
| `ensurepip is not available` | Отсутствует venv пакет на Linux | `sudo apt-get install python3-venv python3-pip -y` |
| `Port 8001 / 8000 already in use` | Конфликт портов | Убить процесс по PID через `free_port_if_occupied()` или `Stop-Process -Id ... -Force` |
| `mkcert not found` | Отсутствует утилита mkcert | Вызвать `py scripts/maintenance/generate_ssl_certs.py` (чистый Python generator) |
| `ModuleNotFoundError: No module named 'logger'` | Отсутствует корень в `sys.path` | Импортировать модуль `header` первым в скрипте |
