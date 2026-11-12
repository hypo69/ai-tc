# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Logger - Log Analyzer
# =============================================================================
# Description:
#   Интеллектуальный анализатор логов с интеграцией ИИ (Gemini / UnifiedChatModel).
#
# Usage Examples:
#   Python API:
#     from logger.log_analyzer import get_max_size_bytes
#
#     res = get_max_size_bytes()
#
# File: log_analyzer.py
# Project: ai-windows-admin
# Package: logger
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:15:00
# =============================================================================

"""Интеллектуальный анализатор логов с интеграцией ИИ.

Обеспечивает анализ журналов приложения с помощью языковой модели,
автоматическую генерацию отчётов и ведение сводного журнала состояния системы (Master Journal).
"""

import os
import asyncio
import datetime
import logging
import tempfile
from pathlib import Path
from typing import Optional, List
from src.ai import UnifiedChatModel
from logger import logger
from header import __root__


def _get_app_name() -> str:
    """Возвращает название приложения из окружения или конфигурации."""
    if os.environ.get('APP_NAME'):
        return os.environ['APP_NAME']
    try:
        from logger.logger import _resolve_app_name
        return _resolve_app_name()
    except Exception:
        return __root__.name if __root__.exists() else 'AI-Assistant'


def get_default_log_dir() -> Path:
    """Возвращает целевую директорию логов."""
    env_dir = (
        os.environ.get('AITC_LOGS_DIR')
        or os.environ.get('AI_TC_LOGS_DIR')
        or os.environ.get('AI_WINDOWS_ADMIN_LOGS_DIR')
        or os.environ.get('LOG_DIR')
    )
    if env_dir:
        return Path(env_dir)
    appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
    base_dir = Path(appdata) if appdata and os.path.exists(appdata) else Path.home() / '.config'
    return base_dir / _get_app_name() / 'logs'


def get_default_reports_dir() -> Path:
    """Возвращает целевую директорию отчетов."""
    env_dir = (
        os.environ.get('AITC_REPORTS_DIR')
        or os.environ.get('AI_TC_REPORTS_DIR')
        or os.environ.get('AI_WINDOWS_ADMIN_REPORTS_DIR')
        or os.environ.get('REPORTS_DIR')
    )
    if env_dir:
        return Path(env_dir)
    appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
    base_dir = Path(appdata) if appdata and os.path.exists(appdata) else Path.home() / '.config'
    return base_dir / _get_app_name() / 'reports'

LOG_DIR: Path = get_default_log_dir()
REPORTS_DIR: Path = get_default_reports_dir()
LOCK_FILE: Path = LOG_DIR / 'log_analyzer.lock'
DEFAULT_MAX_SIZE_MB: float = 10.0
MAX_CHARS_FOR_ANALYSIS: int = 500 * 1024
CHECK_INTERVAL_SECONDS: int = 60
MAX_REPORTS_FOR_JOURNAL: int = 10

def get_max_size_bytes() -> float:
    """Получает максимальный размер лог-файла из конфигурации.

    Returns:
        float: Максимальный размер в байтах (по умолчанию 10 МБ).
    """
    try:
        from src.config import logging_cfg
        mb = float(getattr(logging_cfg, 'max_size_mb', DEFAULT_MAX_SIZE_MB)) if logging_cfg else DEFAULT_MAX_SIZE_MB
        return mb * 1024 * 1024
    except Exception as ex:
        logger.debug(f'Не удалось прочитать конфиг размера лога: {ex}')
        return DEFAULT_MAX_SIZE_MB * 1024 * 1024


def _read_log_tail_bounded(file_path: Path, max_chars: int = MAX_CHARS_FOR_ANALYSIS) -> str:
    """Безопасно читает хвост лог-файла без загрузки гигабайтных файлов целиком в ОЗУ.

    Args:
        file_path: Путь к файлу лога.
        max_chars: Максимальное количество символов для анализа.

    Returns:
        Строка с последними символами лога.
    """
    file_size = file_path.stat().st_size
    max_bytes_to_read = max_chars * 4
    with open(file_path, 'rb') as bf:
        if file_size > max_bytes_to_read:
            bf.seek(file_size - max_bytes_to_read)
        raw_bytes = bf.read(max_bytes_to_read)
    text = raw_bytes.decode('utf-8', errors='ignore')
    return text[-max_chars:] if len(text) > max_chars else text


def _write_text_atomic(target_path: Path, text: str) -> None:
    """Атомарно записывает текстовый файл через временный файл в той же директории."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f'.{target_path.name}.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


async def analyze_log_file(file_path: Path, ai_model: UnifiedChatModel) -> bool:
    """Анализирует лог-файл с помощью ИИ и создаёт отчёт.

    Процесс:
    1. Считывает хвост лог-файла с защитой памяти (максимум 500 КБ символов).
    2. Отправляет на анализ ИИ-модели.
    3. Атомарно сохраняет результат в виде Markdown-отчёта.
    4. Очищает исходный лог-файл.

    Args:
        file_path: Путь к лог-файлу для анализа.
        ai_model: Инициализированный экземпляр UnifiedChatModel.

    Returns:
        bool: True, если анализ прошёл успешно, иначе False.
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            logger.warning(f'Лог-файл не найден: {file_path}')
            return False
        try:
            content = await asyncio.to_thread(_read_log_tail_bounded, file_path, MAX_CHARS_FOR_ANALYSIS)
        except Exception as ex:
            logger.error(f'Ошибка при чтении лог-файла {file_path.name}: {ex}')
            return False
        if not content.strip():
            logger.debug(f'Лог-файл {file_path.name} пуст, пропуск анализа')
            return True
        logger.info(f'Начало умного анализа лога {file_path.name} (размер выборки: {len(content)} символов)...')
        prompt = f'\nПроанализируй следующий лог-файл ({file_path.name}).\nВыяви ошибки, предупреждения, критические проблемы, а также общие тренды и дай рекомендации по исправлению.\nОтвет предоставь на русском языке в чистом формате Markdown.\n\nСодержимое лога:\n{content}\n'
        try:
            report_text = await ai_model.ask(prompt)
        except Exception as ex:
            logger.error(f'Ошибка при запросе к Gemini AI: {ex}')
            report_text = f'# Отчет об анализе лога {file_path.name}\n\nОшибка при запросе к ИИ: {ex}'
        if not report_text:
            report_text = f'# Отчет об анализе лога {file_path.name}\n\nНе удалось получить анализ от модели Gemini.'
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
        report_name = f'report_{file_path.stem}_{timestamp}.md'
        report_path = REPORTS_DIR / report_name
        try:
            await asyncio.to_thread(_write_text_atomic, report_path, report_text)
        except Exception as ex:
            logger.error(f'Ошибка при сохранении отчёта {report_name}: {ex}')
            return False
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.truncate(0)
        except Exception as ex:
            logger.error(f'Ошибка при очистке лог-файла {file_path.name}: {ex}')
        logger.info(f'Лог {file_path.name} успешно проанализирован. Отчет сохранен в {report_name}')
        return True
    except Exception as ex:
        logger.error(f'Критическая ошибка при анализе лог-файла {file_path.name}: {ex}')
        return False

async def update_master_journal(ai_model: UnifiedChatModel) -> bool:
    """Создаёт сводный главный журнал (Master Journal) из последних отчётов анализа.

    Args:
        ai_model: Инициализированный экземпляр UnifiedChatModel.

    Returns:
        bool: True, если журнал успешно обновлён, иначе False.
    """
    try:
        if not REPORTS_DIR.exists():
            logger.debug('Директория отчётов не существует, пропуск обновления журнала')
            return False
        report_files = [p for p in REPORTS_DIR.glob('report_*.md') if p.name != 'master_journal.md']
        if not report_files:
            logger.debug('Нет отчётов для создания главного журнала')
            return False
        report_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        reports_content: List[str] = []
        for p in report_files[:MAX_REPORTS_FOR_JOURNAL]:
            try:
                content = await asyncio.to_thread(_read_log_tail_bounded, p, MAX_CHARS_FOR_ANALYSIS)
                reports_content.append(f'### Файл: {p.name}\n{content}\n')
            except Exception as ex:
                logger.warning(f'Ошибка при чтении отчёта {p.name}: {ex}')
                continue
        if not reports_content:
            logger.warning('Не удалось прочитать ни один отчёт для главного журнала')
            return False
        logger.info(f'Создание главного журнала из {len(reports_content)} отчётов...')
        prompt = f"\nНа основе следующих индивидуальных отчетов об анализе логов составь общий единый журнал (Master Journal) состояния системы.\nВыдели:\n1. Повторяющиеся и постоянные ошибки.\n2. Новые обнаруженные тенденции.\n3. Актуальные проблемы, требующие внимания разработчика на текущий момент.\n4. Устаревшие или неактуальные проблемы, которые перестали появляться.\n5. Рекомендации по приоритизации исправлений.\n\nОтвет выведи строго на русском языке в формате Markdown с чётким структурированием информации.\n\nИндивидуальные отчеты:\n{''.join(reports_content)}\n"
        try:
            master_text = await ai_model.ask(prompt)
        except Exception as ex:
            logger.error(f'Ошибка при запросе к Gemini AI для главного журнала: {ex}')
            master_text = f'# Общий журнал анализа логов\n\nОшибка при создании синтеза: {ex}'
        if not master_text:
            master_text = '# Общий журнал анализа логов\n\nНе удалось получить общий анализ от модели Gemini.'
        master_path = REPORTS_DIR / 'master_journal.md'
        try:
            await asyncio.to_thread(_write_text_atomic, master_path, master_text)
        except Exception as ex:
            logger.error(f'Ошибка при сохранении главного журнала: {ex}')
            return False
        logger.info('Общий журнал (master_journal.md) успешно обновлен')
        return True
    except Exception as ex:
        logger.error(f'Критическая ошибка при обновлении общего журнала логов: {ex}')
        return False

async def log_analyzer_loop() -> None:
    """
    Главный цикл анализатора логов, выполняемый в фоновом потоке.
    
    Функциональность:
    1. Checks конфигурацию включения анализатора
    2. Инициализирует AI модель
    3. Периодически (каждые N секунд) checks размер лог-файлов
    4. Запускает анализ файлов превысивших лимит размера
    5. Обновляет главный журнал после каждого анализа
    
    Runs indefinitely until application shutdown.
    """
    logger.info('Запуск фоновой службы интеллектуального анализа логов...')
    try:
        from src.config import logging_cfg
        if not logging_cfg or not getattr(logging_cfg, 'enable_log_analyzer', False):
            logger.warning('Анализ логов отключён в config.json')
            return
    except Exception as ex:
        logger.warning(f'Не удалось прочитать конфиг анализатора: {ex}')
        return
    try:
        api_key_names = [n.strip() for n in os.getenv('GEMINI_API_KEY_NAMES', '').split(',') if n.strip()]
        if not api_key_names:
            logger.warning('Переменная окружения GEMINI_API_KEY_NAMES не установлена, анализ логов отключен')
            return
        system_instruction = 'Вы — профессиональный аналитик системных логов. Ваша задача — исследовать логи, выявлять ошибки, проблемы, тренды и давать рекомендации по устранению.'
        ai_model = UnifiedChatModel(system_instruction=system_instruction)
    except Exception as ex:
        logger.error(f'Error при инициализации AI модели: {ex}')
        return
    logger.info('Анализатор логов успешно инициализирован')
    while True:
        try:
            if not LOG_DIR.exists():
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue
            max_bytes = get_max_size_bytes()
            for log_file in LOG_DIR.glob('*.log'):
                if log_file.is_file() and log_file.stat().st_size >= max_bytes:
                    success = await analyze_log_file(log_file, ai_model)
                    if success:
                        await update_master_journal(ai_model)
                    await asyncio.sleep(1)
            json_log = LOG_DIR / 'log.json'
            if json_log.exists() and json_log.is_file() and (json_log.stat().st_size >= max_bytes):
                success = await analyze_log_file(json_log, ai_model)
                if success:
                    await update_master_journal(ai_model)
        except Exception as ex:
            logger.error(f'Error в цикле анализатора логов: {ex}')
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

def start_log_analyzer() -> None:
    """
    Запускает анализатор логов в фоновом режиме.
    
    Особенности:
    - Гарантирует, что анализатор запускается только в одном процессе
    - Использует lock-файл для синхронизации между процессами
    - Checks живость процесса перед запуском нового
    - Безопасно processes ошибки инициализации
    
    Raises:
        Не выбрасывает исключений, все ошибки логируются.
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            try:
                with open(LOCK_FILE, 'r', encoding='utf-8') as f:
                    pid = int(f.read().strip())
                try:
                    import psutil
                    if psutil.pid_exists(pid):
                        logger.warning(f'Анализатор логов уже запущен (PID: {pid})')
                        return
                except ImportError:
                    logger.debug('psutil не установлен, пропуск проверки процесса')
                    return
                except Exception as ex:
                    logger.debug(f'Не удалось проверить процесс {pid}: {ex}')
            except (ValueError, OSError) as ex:
                logger.debug(f'Error при чтении lock-файла: {ex}')
            try:
                LOCK_FILE.unlink(missing_ok=True)
            except Exception as ex:
                logger.warning(f'Не удалось удалить старый lock-файл: {ex}')
        try:
            import subprocess
            pid = subprocess.os.getpid()
            LOCK_FILE.write_text(str(pid), encoding='utf-8')
        except Exception as ex:
            logger.error(f'Error при создании lock-файла: {ex}')
            return
        try:
            task = asyncio.create_task(log_analyzer_loop())
            logger.debug('Асинхронная задача анализатора логов создана')
        except RuntimeError as ex:
            logger.debug(f'Event loop не активен ({ex}), пропуск запуска анализатора')
    except Exception as ex:
        logger.error(f'Error при запуске анализатора логов: {ex}')