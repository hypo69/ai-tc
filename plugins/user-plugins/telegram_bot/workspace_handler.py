# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot Workspace Switcher & Media Pipeline Handler
# =============================================================================
# Description:
#   Модуль переключения рабочих областей по команде /workspace (включая
#   «דוד משה» и инлайн-клавиатуру) и сохранения входящих медиафайлов
#   (включая *.mp3 в assets/) с автоматической транскрибацией текста нейросетью
#   и добавлением в базу знаний (Git, KnowledgeStore, RAG FAISS, Obsidian).
#
# File: workspace_handler.py
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:55:00
# =============================================================================

from __future__ import annotations
"""Маршрутизация рабочих пространств и конвейер сохранения медиа в Telegram-боте."""

from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from header import __root__
from logger import logger
from plugins.telegram_bot import user_auth as user_manager

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac"})
_SLUG_SEP_RE = re.compile(r"[\s/\\]+")


def _format_size(size_bytes: int) -> str:
    """Форматирует размер файла в удобочитаемый вид."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


def resolve_workspace(wm: WorkspaceManager, query: str) -> Tuple[str, str]:
    """Находит существующую рабочую область по имени/ID или создаёт новую с учётом иврита.

    Args:
        wm: Экземпляр WorkspaceManager.
        query: Запрошенное имя или идентификатор рабочей области.

    Returns:
        Кортеж (workspace_id, workspace_name).
    """
    clean_query = query.strip()
    if not clean_query:
        return "default", "Default"

    from apps.ai_assistant.core.telegram_workspace_scenario import (
        _normalize_hebrew_token,
        TelegramWorkspaceScenarioService,
    )

    scenario = TelegramWorkspaceScenarioService()
    # 1. Проверяем совпадение со сценарием דוד משה
    if scenario.is_david_moshe_workspace(clean_query):
        canonical_id = scenario.resolve_david_moshe_workspace_id(wm, preferred_id=clean_query)
        ws = wm.get_workspace(canonical_id)
        if not ws:
            ws = wm.create_or_select_workspace(canonical_id, name="דוד משה")
        return canonical_id, str(ws.get("name") or "דוד משה")

    workspaces = wm.list_workspaces()
    norm_query = _normalize_hebrew_token(clean_query)

    # 2. Точное совпадение по ID или имени
    for ws in workspaces:
        ws_id = str(ws.get("workspace_id") or "")
        ws_name = str(ws.get("name") or "")
        if clean_query.lower() in (ws_id.lower(), ws_name.lower()):
            return ws_id, ws_name or ws_id

    # 3. Нормализованное совпадение (без огласовок, единые пробелы)
    if norm_query:
        for ws in workspaces:
            ws_id = str(ws.get("workspace_id") or "")
            ws_name = str(ws.get("name") or "")
            if norm_query in (_normalize_hebrew_token(ws_id), _normalize_hebrew_token(ws_name)):
                return ws_id, ws_name or ws_id

    # 4. Если область не найдена — создаем новую
    safe_slug = _SLUG_SEP_RE.sub("_", clean_query).strip("_")
    if not safe_slug:
        safe_slug = f"ws_{int(time.time())}"
    ws = wm.create_or_select_workspace(safe_slug, name=clean_query)
    logger.console(f"[TelegramBot] Создана новая рабочая область: {safe_slug} ('{clean_query}')")
    return safe_slug, clean_query


def get_effective_user_workspace(wm: WorkspaceManager, tg_id: int) -> Tuple[str, str]:
    """Возвращает текущую рабочую область пользователя (сохранённую или активную по умолчанию).

    Args:
        wm: Экземпляр WorkspaceManager.
        tg_id: Telegram ID пользователя.

    Returns:
        Кортеж (workspace_id, workspace_name).
    """
    saved_ws_id = user_manager.get_user_workspace(tg_id)
    if saved_ws_id:
        ws = wm.get_workspace(saved_ws_id)
        if ws:
            return saved_ws_id, str(ws.get("name") or saved_ws_id)

    # Активная рабочая область в системе
    active_id = wm.get_active_workspace_id()
    if active_id:
        ws = wm.get_workspace(active_id)
        if ws:
            return active_id, str(ws.get("name") or active_id)

    # Первая доступная
    all_ws = wm.list_workspaces()
    if all_ws:
        first = all_ws[0]
        f_id = str(first.get("workspace_id") or "default")
        f_name = str(first.get("name") or f_id)
        return f_id, f_name

    # Создаём дефолтную область при пустом реестре
    ws = wm.create_or_select_workspace("default", name="Главная область")
    return "default", "Главная область"


def _build_workspaces_keyboard(
    wm: WorkspaceManager,
    current_ws_id: str,
) -> InlineKeyboardMarkup:
    """Формирует инлайн-клавиатуру со списком рабочих областей для быстрого переключения."""
    all_ws = wm.list_workspaces()
    keyboard: List[List[InlineKeyboardButton]] = []

    for ws in all_ws:
        w_id = str(ws.get("workspace_id") or "")
        w_name = str(ws.get("name") or w_id)
        is_active = (w_id == current_ws_id)
        prefix = "✅ " if is_active else "📁 "
        btn_text = f"{prefix}{w_name}"
        if len(btn_text) > 30:
            btn_text = btn_text[:28] + "…"
        keyboard.append([
            InlineKeyboardButton(
                btn_text,
                callback_data=f"ws_set:{w_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔄 Обновить список", callback_data="ws_refresh"),
    ])
    return InlineKeyboardMarkup(keyboard)


async def handle_workspace_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    wm: WorkspaceManager,
) -> None:
    """Обрабатывает команду /workspace [имя_или_id]."""
    if not update.message or not update.effective_user:
        return

    tg_id = update.effective_user.id
    args = context.args or []

    if not args:
        # Режим отображения списка и выбора
        cur_id, cur_name = get_effective_user_workspace(wm, tg_id)
        reply_markup = _build_workspaces_keyboard(wm, cur_id)
        text = (
            "📂 <b>Управление рабочими областями</b>\n\n"
            f"Текущая выбранная область: <b>{cur_name}</b> (<code>{cur_id}</code>)\n\n"
            "Нажмите на кнопку ниже для переключения или отправьте команду с именем области:\n"
            "<code>/workspace &lt;имя_или_id&gt;</code> (или <code>/w &lt;имя&gt;</code>)\n"
            "Например: <code>/w דוד משה</code>"
        )
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        return

    # Режим прямого переключения: /workspace דוד משה
    query = " ".join(args).strip()
    ws_id, ws_name = resolve_workspace(wm, query)

    user_manager.set_user_workspace(tg_id, ws_id)
    try:
        wm.set_active_workspace(ws_id)
    except Exception as exc:
        logger.debug(f"[TelegramBot] Синхронизация активной области: {exc}")

    confirm_text = (
        "✅ <b>Рабочая область успешно выбрана!</b>\n\n"
        f"📂 <b>{ws_name}</b> (<code>{ws_id}</code>)\n\n"
        "Отправленные вами аудиофайлы (<code>*.mp3</code>, голосовые сообщения и др.) "
        "будут сохраняться в папку <code>assets/</code> этой рабочей области с автоматической "
        "транскрибацией текста нейросетью и добавлением в базу знаний (Git + RAG + Obsidian)!"
    )
    await update.message.reply_text(confirm_text, parse_mode="HTML")


async def handle_workspace_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    wm: WorkspaceManager,
) -> None:
    """Обрабатывает нажатия кнопок выбора рабочей области."""
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    data = query.data
    tg_id = update.effective_user.id

    if data == "ws_refresh":
        cur_id, cur_name = get_effective_user_workspace(wm, tg_id)
        reply_markup = _build_workspaces_keyboard(wm, cur_id)
        await query.answer("Список обновлён")
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as edit_exc:
            logger.debug(f"[TelegramBot] Обновление клавиатуры рабочих областей: {edit_exc}")
        return

    if data.startswith("ws_set:"):
        target_ws_id = data.split("ws_set:", 1)[1].strip()
        ws = wm.get_workspace(target_ws_id)
        ws_name = str(ws.get("name") or target_ws_id) if ws else target_ws_id

        user_manager.set_user_workspace(tg_id, target_ws_id)
        try:
            wm.set_active_workspace(target_ws_id)
        except Exception:
            pass

        await query.answer(f"Выбрана область: {ws_name}")

        reply_markup = _build_workspaces_keyboard(wm, target_ws_id)
        text = (
            "📂 <b>Управление рабочими областями</b>\n\n"
            f"Текущая выбранная область: <b>{ws_name}</b> (<code>{target_ws_id}</code>)\n\n"
            "✅ Область активирована. Теперь все входящие файлы и аудиозаписи (<code>*.mp3</code>) "
            "сохраняются в <code>assets/</code> этой области с транскрибацией и индексацией!"
        )
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            pass


async def handle_incoming_media(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    wm: WorkspaceManager,
    attachment: Any,
    default_filename: str,
    admin_ids: Optional[List[int]] = None,
    is_audio: bool = False,
) -> None:
    """Загружает файл, помещает оригинал в assets/ рабочей области и транскрибирует контент."""
    if not update.message or not update.effective_user:
        return

    tg_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Пользователь"
    user = user_manager.get_user_by_telegram_id(tg_id, admin_ids=admin_ids)

    if not user:
        await update.message.reply_text(
            "🔒 <b>Доступ ограничен!</b>\n\n"
            "Для отправки и обработки файлов привяжите ваш аккаунт: откройте профиль в веб-интерфейсе "
            "и введите команду <code>/link &lt;КОД&gt;</code>.",
            parse_mode="HTML",
        )
        return

    # Очищаем и нормализуем имя файла
    clean_name = Path(default_filename).name.strip()
    if not clean_name:
        ext = ".mp3" if is_audio else ".dat"
        clean_name = f"file_{int(time.time())}{ext}"

    suffix = Path(clean_name).suffix.lower()
    is_audio_file = is_audio or (suffix in AUDIO_EXTENSIONS)

    # Определяем целевую рабочую область пользователя
    ws_id, ws_name = get_effective_user_workspace(wm, tg_id)

    status_msg = await update.message.reply_text(
        f"📥 <i>Загружаю файл <code>{clean_name}</code> в рабочую область «{ws_name}»...</i>",
        parse_mode="HTML",
    )

    try:
        # 1. Скачиваем байты файла из Telegram
        await update.message.chat.send_action("upload_document")
        tg_file = await context.bot.get_file(attachment.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        raw_bytes = bytes(file_bytes)
        size_str = _format_size(len(raw_bytes))

        # 2. Проверяем триггер текстового сценария דוד משה (для не-аудио файлов)
        scenario = wm.scenario_service
        if not is_audio_file and (scenario.is_trigger_file(clean_name) or (scenario.is_david_moshe_workspace(ws_id) and "שיחה" in clean_name)):
            await status_msg.edit_text(
                f"⚙️ <i>Обнаружен сценарий для «{ws_name}». Запускаю обработку файла «{clean_name}»...</i>",
                parse_mode="HTML",
            )
            scenario_res = await scenario.trigger_scenario(
                wm=wm,
                workspace_id=ws_id,
                trigger_source="telegram_bot",
                trigger_file_name=clean_name,
                delay_seconds=3.0,
                wait_for_completion=True,
            )
            await status_msg.edit_text(
                f"✅ <b>Специальный сценарий «{ws_name}» успешно выполнен!</b>\n\n"
                f"📁 <b>Рабочая область:</b> {ws_name} (<code>{ws_id}</code>)\n"
                f"📄 <b>Файл:</b> <code>{scenario_res.get('target_file_name', clean_name)}</code>\n"
                "Документ зафиксирован в Git, добавлен в SQLite KnowledgeStore и проиндексирован в RAG/Obsidian.",
                parse_mode="HTML",
            )
            return

        # 3. Сохраняем файл в рабочую область через add_uploaded_files (в assets/ с обработкой в Paperless-ngx или транскрибацией)
        from apps.ai_assistant.core.paperless_connector import PaperlessConnector
        is_paperless_doc = PaperlessConnector.is_supported_file(clean_name)
        if is_paperless_doc:
            status_text = (
                f"⚙️ <i>Отправляю <code>{clean_name}</code> в Paperless-ngx для OCR-распознавания "
                f"и индексации в базе знаний «{ws_name}»...</i>"
            )
        else:
            status_text = (
                f"⚙️ <i>Сохраняю оригинал <code>{clean_name}</code> в <code>assets/</code> области «{ws_name}» "
                f"и запускаю транскрибацию контента...</i>"
            )
        await status_msg.edit_text(status_text, parse_mode="HTML")

        commit_msg = f"Telegram ({user_name}): добавлен {clean_name} в assets (Paperless/Git)"
        upload_result = await wm.add_uploaded_files(
            workspace_id=ws_id,
            files_data=[(clean_name, raw_bytes)],
            commit_message=commit_msg,
            audio_mode="model",
        )

        # 4. Извлекаем распознанный текст (из companion .md или tracked_files)
        ws_path = wm.registry.workspace_path(ws_id)
        companion_md = ws_path / "assets" / f"{clean_name}.md"
        transcript_text = ""
        if companion_md.exists():
            try:
                transcript_text = companion_md.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 5. Сохраняем локальную резервную копию в папку пользователя
        try:
            sub = "audio" if is_audio_file else "documents"
            user_dir = user_manager.get_user_directory(user["id"], subfolder=sub, create=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = user_dir / f"{ts}_{clean_name}"
            backup_path.write_bytes(raw_bytes)
        except Exception as b_exc:
            logger.debug(f"[TelegramBot] Резервная копия файла: {b_exc}")

        # 6. Формируем структурированный ответ
        copied_transcript_name = ""
        paperless_id_val = None
        for tf in upload_result.get("tracked_files", []):
            if tf.get("source") == "david_moshe_scenario_transcript":
                copied_transcript_name = Path(tf.get("path") or tf.get("name") or "").name
            if tf.get("paperless_id"):
                paperless_id_val = tf.get("paperless_id")

        lines: List[str] = [
            "🎙 <b>Аудиозапись успешно обработана!</b>" if is_audio_file else "📄 <b>Файл успешно добавлен!</b>",
            "",
            f"📁 <b>Рабочая область:</b> <b>{ws_name}</b> (<code>{ws_id}</code>)",
            f"💾 <b>Оригинал сохранён в:</b> <code>assets/{clean_name}</code> ({size_str})",
        ]
        if paperless_id_val is not None:
            lines.append(f"📑 <b>Paperless-ngx:</b> Документ обработан и распознан (ID: <code>#{paperless_id_val}</code>)")
        if copied_transcript_name:
            lines.append(f"📄 <b>Стенограмма скопирована в:</b> <code>assets/{copied_transcript_name}</code>")
        lines.append("🧠 <b>База знаний:</b> Факты сохранены в SQLite, проиндексированы в RAG FAISS и Obsidian.")

        if transcript_text:
            preview = transcript_text[:2000].strip()
            if len(transcript_text) > 2000:
                preview += "…\n<i>(полный текст сохранён в рабочей области)</i>"
            lines.append("")
            lines.append("📝 <b>Транскрибированный текст:</b>")
            lines.append(f"<blockquote>{preview}</blockquote>")
        elif is_audio_file:
            lines.append("")
            lines.append("ℹ️ <i>Транскрибация выполнена. Полный конспект сохранён в рабочей области.</i>")

        await status_msg.edit_text("\n".join(lines), parse_mode="HTML")
        logger.console(
            f"[TelegramBot] Файл {clean_name} ({size_str}) добавлен в рабочую область '{ws_id}' (assets/)."
        )

    except Exception as exc:
        logger.error(f"[TelegramBot] Ошибка обработки файла {clean_name}: {exc}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Ошибка при сохранении файла:</b>\n<code>{exc}</code>",
            parse_mode="HTML",
        )
