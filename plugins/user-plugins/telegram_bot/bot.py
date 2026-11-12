# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot Service and Command Dispatcher
# =============================================================================
# Description:
#   Диспетчер команд и сервис Telegram-бота на базе python-telegram-bot.
#   Обеспечивает жизненный цикл бота, интеграцию с Mini App, маршрутизацию
#   рабочих пространств (/workspace) и конвейер обработки входящих файлов и диалогов.
#
# File: bot.py
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:45:00
# =============================================================================

"""Модуль сервиса и диспетчера команд Telegram-бота.

Управляет Application python-telegram-bot, обработчиками команд, опросом обновлений,
авторизацией пользователей и маршрутизацией в рабочие области.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from logger import logger
from plugins.telegram_bot import user_auth as user_manager
from plugins.telegram_bot.tts import handle_telegram_voiceover_request

_HEX_TOKEN_8_RE = re.compile(r"^[A-F0-9]{8}$")
_LINK_CODE_RE = re.compile(r"^(?:/?link\s+)?/?([A-F0-9]{8})$", re.IGNORECASE)


class TelegramBotEngine:
    """Управляет жизненным циклом Telegram-бота, командами и маршрутизацией сообщений.

    Attributes:
        token (str): Токен Telegram Bot API от BotFather.
        admin_ids (List[int]): Список идентификаторов администраторов Telegram.
        ai_model (Any): Экземпляр модели ИИ для генерации ответов.
        config (Dict[str, Any]): Словарь конфигурации бота.
        app (Optional[Application]): Экземпляр Application python-telegram-bot.
        is_running (bool): Флаг активного состояния поллинга бота.
    """

    def __init__(
        self,
        token: str,
        admin_ids: Optional[List[int]] = None,
        ai_model: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Инициализирует сервис Telegram-бота."""
        self.token: str = token.strip() if token else ""
        self.admin_ids: List[int] = admin_ids or []
        self.ai_model: Any = ai_model
        self.config: Dict[str, Any] = config or {}
        self.app: Optional[Application] = None
        self.is_running: bool = False
        self._bot_info: Dict[str, Any] = {}
        self._workspace_manager: Any = None

    def is_configured(self) -> bool:
        """Проверяет наличие валидного токена Telegram API."""
        return bool(self.token and len(self.token) > 10 and ":" in self.token)

    def _get_workspace_manager(self) -> Any:
        """Возвращает кэшированный экземпляр WorkspaceManager."""
        if self._workspace_manager is None:
            from apps.ai_assistant.core.workspace_manager import WorkspaceManager
            self._workspace_manager = WorkspaceManager()
        return self._workspace_manager

    async def initialize(self) -> bool:
        """Конфигурирует и инициализирует Application python-telegram-bot."""
        if not self.is_configured():
            logger.warning("TelegramBotEngine: Токен бота не задан или невалиден.")
            return False

        try:
            self.app = (
                ApplicationBuilder()
                .token(self.token)
                .connect_timeout(10.0)
                .read_timeout(20.0)
                .write_timeout(20.0)
                .build()
            )

            # Обработчики команд
            for cmd in ["start", "auth", "login", "register"]:
                self.app.add_handler(CommandHandler(cmd, self._cmd_start))
            self.app.add_handler(CommandHandler("help", self._cmd_help))
            self.app.add_handler(CommandHandler("status", self._cmd_status))
            self.app.add_handler(CommandHandler("dialogs", self._cmd_dialogs))
            self.app.add_handler(CommandHandler("link", self._cmd_link))
            self.app.add_handler(CommandHandler("tts", self._cmd_tts))
            self.app.add_handler(CommandHandler(["workspace", "ws", "w"], self._cmd_workspace))

            # Callback queries и медиа
            self.app.add_handler(CallbackQueryHandler(self._handle_callback_query))
            self.app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
            self.app.add_handler(MessageHandler(filters.AUDIO, self._handle_audio))
            self.app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message))
            self.app.add_error_handler(self._handle_error)

            await self.app.initialize()
            logger.info("TelegramBotEngine: Приложение бота успешно инициализировано.")
            return True
        except Exception as exc:
            logger.error(f"TelegramBotEngine: Ошибка инициализации: {exc}", exc_info=True)
            self.app = None
            return False

    async def start(self) -> None:
        """Запускает процесс получения обновлений (polling) Telegram-бота."""
        if self.is_running:
            logger.info("TelegramBotEngine: Бот уже запущен.")
            return

        if not self.app:
            ok = await self.initialize()
            if not ok or not self.app:
                raise RuntimeError("Не удалось запустить Telegram-бота: инициализация не выполнена.")

        try:
            await self.app.start()
            if self.app.updater:
                await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            self.is_running = True

            bot_user = await self.app.bot.get_me()
            self._bot_info = {
                "id": bot_user.id,
                "username": bot_user.username,
                "first_name": bot_user.first_name,
            }
            logger.info(f"Telegram-бот запущен как @{bot_user.username} (ID: {bot_user.id}).")
        except Exception as exc:
            self.is_running = False
            logger.error(f"Не удалось запустить TelegramBotEngine: {exc}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Корректно останавливает опрос обновлений и завершает работу бота."""
        if not self.is_running or not self.app:
            return

        try:
            logger.info("Остановка Telegram-бота...")
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
            await self.app.shutdown()
            self.is_running = False
            logger.info("Telegram-бот успешно остановлен.")
        except Exception as exc:
            logger.error(f"Ошибка при остановке Telegram-бота: {exc}", exc_info=True)
            self.is_running = False

    def get_info(self) -> Dict[str, Any]:
        """Возвращает информацию о текущем состоянии службы бота."""
        return {
            "configured": self.is_configured(),
            "running": self.is_running,
            "bot_info": self._bot_info,
            "admin_count": len(self.admin_ids),
        }

    # =========================================================================
    # Обработчики команд
    # =========================================================================

    async def _cmd_workspace(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /workspace [имя_или_id] и алиасы /w, /ws."""
        from plugins.telegram_bot.workspace_handler import handle_workspace_command
        await handle_workspace_command(update, context, self._get_workspace_manager())

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /start, включая Deep Linking (/start <TOKEN>)."""
        if not update.effective_chat or not update.effective_user or not update.message:
            return

        tg_id = update.effective_user.id
        tg_username = update.effective_user.username or ""
        user_name = update.effective_user.first_name or "Пользователь"

        args = context.args or []
        if args:
            token = args[0].strip().upper()
            if len(token) == 8 and _HEX_TOKEN_8_RE.match(token):
                if user_manager.link_telegram_account(token, tg_id, tg_username or user_name):
                    await update.message.reply_text(
                        f"🎉 <b>Telegram-аккаунт успешно привязан!</b>\n🆔 ID: <code>{tg_id}</code>",
                        parse_mode="HTML",
                    )
                    return
                await update.message.reply_text(
                    "❌ <b>Ошибка привязки!</b> Код недействителен или истек срок (10 мин).",
                    parse_mode="HTML",
                )
                return

        user = user_manager.get_user_by_telegram_id(tg_id, admin_ids=self.admin_ids)
        api_base = self.config.get("api_base_url", "").rstrip("/")
        rc_url = f"{api_base}/rc" if api_base else ""

        if user:
            name = user.get("name", user_name)
            keyboard: List[List[InlineKeyboardButton]] = []
            if rc_url.lower().startswith("https://"):
                keyboard.append([InlineKeyboardButton("📱 Mini App", web_app=WebAppInfo(url=rc_url))])
            keyboard.append([
                InlineKeyboardButton("📁 Рабочие области", callback_data="ws_refresh"),
                InlineKeyboardButton("📊 Статус", callback_data="btn_status"),
            ])
            keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="btn_help")])
            welcome = (
                f"👋 <b>Здравствуйте, {name}!</b> Добро пожаловать в <b>AI-Assistant</b>.\n\n"
                f"🆔 <b>Telegram ID:</b> <code>{tg_id}</code>\n\n"
                "• <code>/workspace &lt;имя&gt;</code> — переключить область (например <code>/w דוד משה</code>)\n"
                "• <code>/dialogs</code> — список файлов\n• <code>/status</code> — статус системы\n"
                "• <code>/tts &lt;текст&gt;</code> — озвучить текст\n\n"
                "🎙 Отправляйте голосовые или *.mp3 файлы для распознавания речи и индексации в базе знаний."
            )
            await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            keyboard = [[
                InlineKeyboardButton("📊 Статус", callback_data="btn_status"),
                InlineKeyboardButton("❓ Помощь", callback_data="btn_help"),
            ]]
            welcome = (
                f"👋 <b>Здравствуйте, {user_name}!</b>\n\n"
                "🔒 Привяжите аккаунт Telegram: в профиле веб-интерфейса нажмите «Привязать Telegram» "
                "и отправьте код командой <code>/link &lt;КОД&gt;</code>."
            )
            await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    async def _cmd_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /link <код> для привязки аккаунта."""
        if not update.message or not update.effective_user:
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("ℹ️ <b>Использование:</b> <code>/link &lt;КОД&gt;</code>", parse_mode="HTML")
            return
        token = args[0].strip().upper()
        tg_id = update.effective_user.id
        tg_username = update.effective_user.username or ""
        name = update.effective_user.first_name or "Пользователь"
        if user_manager.link_telegram_account(token, tg_id, tg_username or name):
            await update.message.reply_text(
                f"🎉 <b>Telegram-аккаунт успешно привязан!</b> (ID: <code>{tg_id}</code>)",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ <b>Код недействителен или истек.</b>", parse_mode="HTML")

    async def _cmd_dialogs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /dialogs для просмотра аудиофайлов."""
        if not update.message or not update.effective_user:
            return
        user = user_manager.get_user_by_telegram_id(update.effective_user.id, admin_ids=self.admin_ids)
        if not user:
            await update.message.reply_text("🔒 <b>Сначала привяжите аккаунт:</b> <code>/link &lt;КОД&gt;</code>", parse_mode="HTML")
            return
        user_id = user.get("id", 1)
        audio_dir = user_manager.get_user_directory(user_id, "audio", create=True)
        files = sorted([f for f in audio_dir.glob("*") if f.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            await update.message.reply_text("📂 В папке аудиофайлов пока нет записей.", parse_mode="HTML")
            return
        lines = [f"📂 <b>Файлы пользователя ({len(files)} шт.):</b>", ""]
        for f in files[:10]:
            lines.append(f"• <code>{f.name}</code> ({f.stat().st_size / 1024.0:.1f} КБ)")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /help."""
        if update.message:
            await update.message.reply_text(self._get_help_text(), parse_mode="HTML")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /status."""
        if update.message:
            await update.message.reply_text(self._build_status_message(), parse_mode="HTML")

    async def _cmd_tts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду синтеза речи /tts <текст>."""
        if not update.message:
            return
        text = " ".join(context.args or []).strip()
        if not text:
            await update.message.reply_text("ℹ️ <b>Использование:</b> <code>/tts &lt;текст&gt;</code>", parse_mode="HTML")
            return
        api_base = self.config.get("api_base_url", "http://127.0.0.1:8000")
        await handle_telegram_voiceover_request(update, context, text=text, api_base_url=api_base)

    # =========================================================================
    # Обработчики медиафайлов
    # =========================================================================

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает входящее голосовое сообщение."""
        if not update.message or not update.message.voice:
            return
        from plugins.telegram_bot.workspace_handler import handle_incoming_media
        voice = update.message.voice
        name = f"voice_{getattr(voice, 'file_unique_id', 'clip')}.ogg"
        await handle_incoming_media(update, context, self._get_workspace_manager(), voice, name, self.admin_ids, is_audio=True)

    async def _handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает входящие аудиофайлы (*.mp3, *.wav, *.ogg)."""
        if not update.message or not update.message.audio:
            return
        from plugins.telegram_bot.workspace_handler import handle_incoming_media
        audio = update.message.audio
        name = audio.file_name or f"audio_{getattr(audio, 'file_unique_id', 'clip')}.mp3"
        await handle_incoming_media(update, context, self._get_workspace_manager(), audio, name, self.admin_ids, is_audio=True)

    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает входящие документы и прикрепленные файлы."""
        if not update.message or not update.message.document:
            return
        from plugins.telegram_bot.workspace_handler import handle_incoming_media
        doc = update.message.document
        name = doc.file_name or f"doc_{getattr(doc, 'file_unique_id', 'file')}.dat"
        await handle_incoming_media(update, context, self._get_workspace_manager(), doc, name, self.admin_ids, is_audio=False)

    # =========================================================================
    # Интерактивные кнопки и текст
    # =========================================================================

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает нажатия на кнопки инлайн-клавиатуры."""
        query = update.callback_query
        if not query:
            return

        data = query.data or ""
        if data.startswith("ws_") or data.startswith("ws:"):
            from plugins.telegram_bot.workspace_handler import handle_workspace_callback
            await handle_workspace_callback(update, context, self._get_workspace_manager())
            return

        await query.answer()
        if data == "btn_status":
            await query.edit_message_text(self._build_status_message(), parse_mode="HTML")
        elif data == "btn_help":
            await query.edit_message_text(self._get_help_text(), parse_mode="HTML")
        elif data == "btn_dialogs" and update.effective_user:
            user = user_manager.get_user_by_telegram_id(update.effective_user.id, admin_ids=self.admin_ids)
            if user:
                files = list(user_manager.get_user_directory(user.get("id", 1), "audio", create=True).glob("*"))
                await query.edit_message_text(f"📂 <b>Ваши аудиозаписи:</b> {len(files)} шт.", parse_mode="HTML")
            else:
                await query.edit_message_text("🔒 Сначала привяжите аккаунт через <code>/link &lt;КОД&gt;</code>.", parse_mode="HTML")

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает текстовые сообщения пользователей (токен привязки или диалог с ИИ)."""
        if not update.message or not update.message.text or not update.effective_user:
            return

        user_text = update.message.text.strip()
        if not user_text:
            return

        tg_id = update.effective_user.id
        tg_username = update.effective_user.username or ""
        user_name = update.effective_user.first_name or "Пользователь"

        # 1. Проверяем ввод 8-значного кода привязки
        token_match = _LINK_CODE_RE.match(user_text)
        if token_match:
            token = token_match.group(1).upper()
            if user_manager.link_telegram_account(token, tg_id, tg_username or user_name):
                await update.message.reply_text(f"🎉 <b>Telegram-аккаунт успешно привязан!</b> (ID: <code>{tg_id}</code>)", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ <b>Код недействителен или истек.</b>", parse_mode="HTML")
            return

        # 2. Проверяем авторизацию
        user = user_manager.get_user_by_telegram_id(tg_id, admin_ids=self.admin_ids)
        if not user:
            await update.message.reply_text(
                "🔒 <b>Доступ ограничен!</b>\nОтправьте команду <code>/link &lt;КОД&gt;</code> для авторизации.",
                parse_mode="HTML",
            )
            return

        # 3. Проверяем реактивный сценарий рабочей области (דוד משה)
        wm = self._get_workspace_manager()
        scenario = getattr(wm, "scenario_service", None)
        if scenario and hasattr(scenario, "is_trigger_file") and scenario.is_trigger_file(user_text):
            from plugins.telegram_bot.workspace_handler import get_effective_user_workspace
            ws_id, ws_name = get_effective_user_workspace(wm, tg_id)
            await scenario.trigger_scenario(wm=wm, workspace_id=ws_id, trigger_source="telegram_bot", trigger_file_name=user_text)
            await update.message.reply_text(f"⚙️ Событие <b>{user_text}</b> принято для рабочей области «{ws_name}».", parse_mode="HTML")
            return

        # 4. Ответ через модель ИИ
        if not self.ai_model:
            await update.message.reply_text(f"🤖 Сообщение получено: «{user_text}»\nОтправьте аудиофайл для транскрибации.")
            return

        try:
            await update.message.chat.send_action("typing")
            if hasattr(self.ai_model, "chat") and callable(self.ai_model.chat):
                res = self.ai_model.chat(user_text) if asyncio.iscoroutinefunction(self.ai_model.chat) else await asyncio.to_thread(self.ai_model.chat, user_text)
            elif hasattr(self.ai_model, "generate") and callable(self.ai_model.generate):
                res = self.ai_model.generate(user_text) if asyncio.iscoroutinefunction(self.ai_model.generate) else await asyncio.to_thread(self.ai_model.generate, user_text)
            else:
                res = f"Ответ: {user_text}"
            reply = await res if asyncio.iscoroutine(res) else str(res)
            await update.message.reply_text(reply)
        except Exception as exc:
            logger.error(f"[TelegramBotEngine] Ошибка генерации ответа модели: {exc}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка при обращении к ИИ: {exc}")

    # =========================================================================
    # Вспомогательные методы
    # =========================================================================

    def _build_status_message(self) -> str:
        """Формирует текстовое сообщение о статусе бота."""
        model_name = getattr(self.ai_model, "model_name", type(self.ai_model).__name__) if self.ai_model else "Не подключена"
        bot_uname = self._bot_info.get("username", "Неизвестно")
        running_icon = "🟢 Онлайн" if self.is_running else "🔴 Остановлен"
        return (
            "📊 <b>Статус Telegram-бота:</b>\n\n"
            f"• <b>Служба:</b> {running_icon}\n"
            f"• <b>Имя бота:</b> @{bot_uname}\n"
            f"• <b>Активная модель:</b> <code>{model_name}</code>\n"
            f"• <b>Администраторы:</b> {len(self.admin_ids)} чел.\n"
        )

    def _get_help_text(self) -> str:
        """Возвращает справочный текст команд бота."""
        return (
            "📖 <b>Справка по командам:</b>\n\n"
            "• <code>/start</code> — Главное меню\n"
            "• <code>/workspace &lt;имя&gt;</code> (алиасы: <code>/w</code>, <code>/ws</code>) — Переключить область\n"
            "• <code>/link &lt;КОД&gt;</code> — Привязать Telegram к веб-профилю\n"
            "• <code>/dialogs</code> — Список аудиофайлов\n"
            "• <code>/status</code> — Статус бота\n"
            "• <code>/tts &lt;текст&gt;</code> — Озвучить текст\n\n"
            "🎙 Отправляйте аудиофайлы (*.mp3, голосовые) для сохранения в <code>assets/</code> и транскрибации."
        )

    async def _handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает исключения polling-цикла и сетевые сбои Telegram API."""
        err = context.error
        if err is None:
            return
        err_str = str(err)
        err_type = type(err).__name__
        if "getaddrinfo" in err_str or "ConnectError" in err_str or "NetworkError" in err_type:
            logger.warning(f"Telegram-бот: Сбой сети Telegram API ({err_str}). Автоповтор...")
        else:
            logger.error(f"Telegram-бот: Ошибка: {err}", exc_info=err)
