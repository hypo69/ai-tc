# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Audio Transcription Module
# =============================================================================
# Description:
#   Модуль транскрибации аудиофайлов (.wav, .mp3, .ogg, .m4a, .flac) в текст.
#   Использует мультимодальные возможности Google Gemini API (через google.genai)
#   с ротацией ключей из src/secrets/gemini_keys.json и резервным переключением
#   на локальные библиотеки распознавания речи (speech_recognition / tts).
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.audio import audio2text
#
#     text = await audio2text("recordings/meeting.mp3", language="ru")
#     print(text)
#
# File: audio.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 13:17:00
# =============================================================================

from __future__ import annotations
"""Транскрибация аудиофайлов в текст с помощью Google Gemini API и локальных моделей."""

import asyncio
from pathlib import Path
from typing import Optional, Union

from logger import logger

MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".ogg": "audio/ogg",
    ".m4a": "audio/m4a",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}


def _get_gemini_client():
    """Возвращает инициализированный клиент Google GenAI с активным ключом."""
    try:
        from src.ai.gemini.gemini_api_key_state import load_api_keys
        from google.genai import Client

        keys, names, _ = load_api_keys()
        if not keys:
            return None
        return Client(api_key=keys[0])
    except Exception as exc:
        logger.warning(f"[audio2text] Не удалось инициализировать клиент Gemini: {exc}")
        return None


async def audio2text(
    audio_path: Union[str, Path],
    language: str = "ru",
    prompt: Optional[str] = None,
) -> str:
    """Транскрибирует аудиофайл в структурированный текст.

    Args:
        audio_path: Путь к локальному аудиофайлу.
        language: Код целевого языка распознавания (по умолчанию 'ru').
        prompt: Дополнительные инструкции по транскрибации.

    Returns:
        str: Распознанный текст аудиозаписи или информационное сообщение об ошибке.
    """
    path = Path(audio_path)
    if not path.is_file():
        logger.error(f"[audio2text] Аудиофайл не найден: {path}")
        return ""

    suffix = path.suffix.lower()
    mime_type = MIME_TYPES.get(suffix, "audio/wav")

    # 1. Попытка транскрибации через Google Gemini API (высокое качество)
    client = _get_gemini_client()
    if client:
        try:
            from google.genai import types

            audio_data = path.read_bytes()
            instruction = prompt or (
                f"Пожалуйста, выполни максимально точную и полную транскрибацию этой аудиозаписи в текст "
                f"на языке оригинала (предпочтительно {language}). Сохраняй знаки препинания и разделение на смысловые абзацы. "
                f"Выведи только расшифрованный текст без вступительных или заключительных фраз."
            )

            # Вызов генерации контента
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_data, mime_type=mime_type),
                    types.Part.from_text(text=instruction),
                ],
            )

            if response and response.text:
                recognized_text = response.text.strip()
                logger.info(f"[audio2text] Аудио {path.name} успешно транскрибировано через Gemini ({len(recognized_text)} симв.)")
                return recognized_text
        except Exception as gemini_err:
            logger.warning(f"[audio2text] Ошибка транскрибации через Gemini API: {gemini_err}")

    # 2. Резервный вариант через модуль tts / speech_recognizer
    try:
        from src.utils.convertors.tts import speech_recognizer

        lang_code = "ru-RU" if language.lower().startswith("ru") else ("he-IL" if language.lower().startswith("he") else "en-US")
        fallback_text = await asyncio.to_thread(speech_recognizer, audio_file_path=path, language=lang_code)
        if fallback_text and not fallback_text.startswith("Error") and not fallback_text.startswith("Sorry"):
            return fallback_text
    except Exception as tts_err:
        logger.warning(f"[audio2text] Резервная транскрибация через TTS недоступна: {tts_err}")

    # Информативное описание, если распознавание не удалось
    return f"*(Аудиофайл {path.name}: транскрибация недоступна. Настройте API-ключ Gemini в src/secrets/gemini_keys.json)*"

