<!--
=============================================================================
Process Name: AI Instruments Module Documentation
=============================================================================
Description:
  Документация базы инструментов ИИ-агента (u177424397_tool_chains на Hostinger).
  Хранит исключительно инструменты (скрипты PowerShell, CLI-утилиты, команды),
  используемые агентом и моделью при решении задач.

File: README.md
Project: ai-tc
Package: apps.windows.ai_instruments
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 05:00:00
=============================================================================
-->

# База инструментов ИИ-агента (`u177424397_tool_chains` на Hostinger MariaDB)

Модуль `apps.windows.ai_instruments` реализует централизованное хранилище инструментов ИИ-агента.

## 🎯 Архитектурное разделение двух баз знаний

В проекте действуют **две совершенно разные базы знаний**:

1. **WikiLLM (`knowledge.db` / MariaDB `wikillm_knowledge`)**:
   - Предназначена **для администратора**: помогает понять суть изучаемого параметра Windows (назначение процесса, службы, драйвера, ошибки, влияние на ресурсы, оценка безопасности, вердикт).
2. **Инструменты агента (`u177424397_tool_chains` / MariaDB Hostinger)**:
   - Предназначена **ТОЛЬКО для модели и агента**: хранит исполняемые инструменты (параметризованные CLI-команды, PowerShell-скрипты, системные утилиты, параметры запуска, OpenAPI схемы для подстановки модели).

## 🚀 Режимы хранения

- **Основная база данных (Active Production)**: MariaDB на сервере Hostinger (`srv1373.hstgr.io:3306`, база: `u177424397_tool_chains`, таблица: `ai_instruments`).
- **Локальный кэш / Резерв (Offline Fallback)**: SQLite файл `data/ai_instruments/ai_instruments.db`.

## 🛠️ Структура инструмента (`AIInstrument`)

| Поле | Тип | Описание |
|---|---|---|
| `tool_id` | `str` | Уникальный ID инструмента (например: `inst_a1b2c3d4`) |
| `name` | `str` | Название инструмента или скрипта |
| `tool_type` | `str` | Тип: `powershell`, `utility`, `cmd`, `python` |
| `command` | `str` | Исполняемая команда или тело скрипта |
| `description` | `str` | Назначение инструмента и рекомендации агенту |
| `target_entity` | `str` | Связанная сущность системы (например: `user`, `service`, `process`) |
| `parameters_schema` | `dict` | JSON-схема аргументов и параметров запуска инструмента (OpenAPI / Function Calling) |
| `risk_level` | `str` | Уровень риска: `safe`, `caution`, `danger` |
| `author_agent` | `str` | Агент-автор (`command_wizard`, `reasoning_chain`, `gemini`, `admin`) |
| `execution_count` | `int` | Количество успешных запусков инструмента |
| `last_executed_at`| `str` | Дата и время последнего запуска |

## 🪄 Мастер создания команд для модели (`command_wizard.py`)

Модуль включает парсер и мастер создания параметризованных команд для языковых моделей:
- **Поддерживаемый синтаксис**:
  - `net user {user_name} /active:{yes|no}`
  - `sc.exe config {service_name} start={auto|demand|disabled}`
  - `taskkill.exe /PID {pid:int} /F`
  - `shutdown.exe /{s|r|a} /t {timeout:int} /f`
- **Автоматический парсинг**:
  - Извлечение имен параметров и вариантов выбора (`enum`, `string`, `integer`, `boolean`, `filepath`).
  - Генерация нормализованного шаблона команды (`net user {user_name} /active:{active}`).
  - Формирование JSON-схемы (`parameters_schema`) для Function Calling модели.
  - Подстановка аргументов (`substitute`) и интерактивный Live Preview в WebGUI.
