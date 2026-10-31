# 📦 Навык установки проекта (Project Installer Skill)
# Updated: 2026-10-31 19:10:00
# Author: hypo69

Интерактивный навык установки и проверки целостности для AI Windows Admin (ai-tc).

## Описание
Данный навык позволяет моделям ИИ, запущенным через Gemini CLI (`gemini --model "gemini-3.1-flash-lite"`) или Antigravity, выполнять полный цикл развертывания проекта, включая первоочередной запуск службы телеметрии (`tlm.ps1`), создание виртуального окружения Python, установку зависимостей из `requirements.txt`, настройку конфигурации `.env`, генерацию SSL-сертификатов и автоматическую верификацию всех директорий и модулей.

## Структура навыка
```
.agents/skills/project-installer/
├── README.md                     # Описание навыка
├── SKILL.md                      # Инструкции и протокол работы агента
├── INSTALL-INSTRUCTION.md        # Полный регламент установки и диагностики
└── scripts/
    ├── verify_installation.py    # Утилита верификации директорий и модулей
    ├── run_installer_gemini.ps1  # Скрипт запуска для Windows PowerShell
    └── run_installer_gemini.sh   # Скрипт запуска для Linux/macOS Bash
```

## Использование
Запуск проверки целостности:
```powershell
python .agents/skills/project-installer/scripts/verify_installation.py
```

Интерактивный запуск установщика через Gemini CLI:
```powershell
.\.agents\skills\project-installer\scripts\run_installer_gemini.ps1
```
