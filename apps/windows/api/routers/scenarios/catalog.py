# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - catalog
# =============================================================================
# Description:
#   Каталог доступных сценариев.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: catalog.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


__root__ = Path(__file__).resolve().parents[3]


# -----------------------------------------------------------------------------
# Список доступных сценариев
# -----------------------------------------------------------------------------

AVAILABLE_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "safe_update_guard",
        "title": "Безопасная подготовка к обновлению Windows (Safe Update Guard)",
        "description": "Автоматическая подготовка системы к крупным обновлениям ОС (Windows 11 26H2 / Feature Updates): инспекция дискового пространства, проверка и активация среды WinRE, настройка хранилища теневых копий VSS, создание точки восстановления и регистрация PRE_UPDATE контрольной точки.",
        "category": "security",
        "icon": "🛡️",
        "recommended": True,
        "estimated_duration_sec": 8,
    },
    {
        "id": "quick_check",
        "title": "Быстрая проверка (Smoke Test)",
        "description": "Экспресс-проверка целостности окружения, доступности ядра FastAPI, AI-провайдеров, свободного места и ключевых логов. Рекомендуется запускать сразу после установки или перезапуска.",
        "category": "quick",
        "icon": "⚡",
        "recommended": True,
        "estimated_duration_sec": 2,
    },
    {
        "id": "log_audit",
        "title": "Запустить аудит логов",
        "description": "Комплексный анализ файлов логов (info.log, errors.log, app.log) и журналов событий Windows. Поиск критических ошибок, подсчет аномалий и генерация рекомендаций.",
        "category": "logs",
        "icon": "📜",
        "recommended": False,
        "estimated_duration_sec": 3,
    },
    {
        "id": "system_inspector",
        "title": "Диагностика системы и оборудования",
        "description": "Срез телеметрии: загрузка ядер процессора, температура, оперативная память, свободное место на дисках и ресурсоёмкие фоновые процессы.",
        "category": "diagnostics",
        "icon": "🖥️",
        "recommended": False,
        "estimated_duration_sec": 3,
    },
    {
        "id": "windows_admin",
        "title": "Аудит автозапуска и служб Windows",
        "description": "Проверка записей реестра Run/RunOnce, папки автозагрузки, критических системных служб Windows и прав текущего процесса.",
        "category": "security",
        "icon": "🛡️",
        "recommended": False,
        "estimated_duration_sec": 4,
    },
    {
        "id": "network_test",
        "title": "Проверка сетевой доступности и портов",
        "description": "Тестирование локального шлюза, разрешения DNS, открытых серверных портов (8000 и др.) и доступности внешних API.",
        "category": "network",
        "icon": "🌐",
        "recommended": False,
        "estimated_duration_sec": 4,
    },
    {
        "id": "ai_providers_check",
        "title": "Проверка статуса AI-провайдеров",
        "description": "Опрос сконфигурированных AI-моделей (Google Gemini, Antigravity/AGY, Ollama, Foundry) и замер времени отклика инференса.",
        "category": "ai",
        "icon": "🤖",
        "recommended": False,
        "estimated_duration_sec": 5,
    },
    {
        "id": "disk_benchmark_audit",
        "title": "Экспресс-тест скорости всех накопителей (DiskSpd)",
        "description": "Быстрое измерение скорости последовательного и случайного чтения/записи на всех дисках с фиксацией в телеметрии.",
        "category": "diagnostics",
        "icon": "⚡",
        "recommended": True,
        "estimated_duration_sec": 3,
    },
]

