# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot AI Chat & Knowledge QA Handler
# =============================================================================
# Description:
#   Сервис и обработчики чата с моделью ИИ в Telegram-боте.
#   Обеспечивает гибридный диалог (база знаний рабочей области через
#   KnowledgeQAEngine + прямой чат с активной моделью UnifiedChatModel),
#   управление историей диалога, переключение режимов (/mode, /clear)
#   и безопасную отправку длинных ответов в Telegram.
#
# File: chat_handler.py
# Project: ai-assistant
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 22:15:00
# =============================================================================

from __future__ import annotations

"""Модуль чата с моделью ИИ и базой знаний для Telegram-бота."""

import asyncio
import html
import json
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from header import __root__
from logger import logger
from plugins.telegram_bot.workspace_handler import get_effective_user_workspace

if TYPE_CHECKING:
    from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

VALID_CHAT_MODES = ("auto", "chat", "rag")
MAX_TELEGRAM_MESSAGE_LEN = 4000
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_LLM_TIMEOUT = 60.0

_MODE_LABELS: Dict[str, str] = {
    "auto": "🔀 Гибридный (База знаний + Модель ИИ)",
    "chat": "💬 Прямой чат с моделью ИИ",
    "rag": "📚 Только документы рабочей области",
}

_DEFAULT_SYSTEM_INSTRUCTION = (
    "Ты — полезный интеллектуальный ассистент платформы AI-Assistant в Telegram. "
    "Отвечай чётко, по делу и на том же языке, на котором задан вопрос пользователя."
)


def resolve_active_model_config() -> Tuple[str, str]:
    """Читает актуальные провайдер и модель ИИ из конфигурации проекта.

    Returns:
        Tuple[str, str]: Кортеж ``(provider, model)``.
    """
    provider = ""
    model = ""

    # 1. Единый резолвер конфигурации из apps.common.models
    try:
        from apps.common.models import load_root_config

        root_cfg = load_root_config()
        ai_sec = root_cfg.get("ai_providers_and_models_configuration")
        if isinstance(ai_sec, dict):
            provider = str(ai_sec.get("default_provider") or "").strip()
            model = str(ai_sec.get("default_model") or "").strip()
        if not provider or not model:
            llm_sec = root_cfg.get("llm")
            if isinstance(llm_sec, dict):
                provider = provider or str(llm_sec.get("default_provider") or "").strip()
                model = model or str(llm_sec.get("default_model") or "").strip()
    except Exception as exc:
        logger.debug(f"[TelegramChat] Не удалось прочитать корневой config.json: {exc}")

    # 2. Резервное чтение из apps/ai_assistant/config.json
    if not provider or not model:
        app_cfg_path = __root__ / "apps" / "ai_assistant" / "config.json"
        if app_cfg_path.exists():
            try:
                app_cfg = json.loads(app_cfg_path.read_text(encoding="utf-8"))
                llm_sec = app_cfg.get("llm", {})
                if isinstance(llm_sec, dict):
                    provider = provider or str(llm_sec.get("default_provider") or "").strip()
                    model = model or str(llm_sec.get("default_model") or "").strip()
            except Exception as exc:
                logger.debug(f"[TelegramChat] Ошибка чтения apps/ai_assistant/config.json: {exc}")

    # 3. Fallback на src.config.ai_cfg
    if not provider or not model:
        try:
            from src.config import ai_cfg

            provider = provider or str(getattr(ai_cfg, "default_provider", "") or "").strip()
            model = model or str(getattr(ai_cfg, "default_model", "") or "").strip()
        except Exception:
            pass

    return provider or "gemini", model


def split_telegram_message(text: str, max_len: int = MAX_TELEGRAM_MESSAGE_LEN) -> List[str]:
    """Разбивает длинный текст на фрагменты, не превышающие лимит Telegram API.

    Args:
        text (str): Исходный текст ответа.
        max_len (int): Максимальная длина одного фрагмента (по умолчанию 4000).

    Returns:
        List[str]: Список фрагментов текста для последовательной отправки.
    """
    clean = (text or "").strip()
    if not clean:
        return []
    if len(clean) <= max_len:
        return [clean]

    chunks: List[str] = []
    remaining = clean
    while len(remaining) > max_len:
        window = remaining[:max_len]
        split_at = window.rfind("\n\n")
        if split_at < max_len // 3:
            split_at = window.rfind("\n")
        if split_at < max_len // 3:
            split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def send_chat_reply(
    message: Message,
    text: str,
    parse_mode: Optional[str] = None,
) -> None:
    """Отправляет ответ пользователю в Telegram с авторазбивкой и защитой от ошибок разметки.

    Args:
        message (Message): Входящее сообщение Telegram для ответа.
        text (str): Текст ответа.
        parse_mode (Optional[str]): Режим разметки (например, ``"HTML"``) или ``None``.
    """
    chunks = split_telegram_message(text)
    if not chunks:
        return
    for chunk in chunks:
        try:
            if parse_mode:
                await message.reply_text(chunk, parse_mode=parse_mode)
            else:
                await message.reply_text(chunk)
        except Exception as exc:
            if parse_mode:
                logger.debug(f"[TelegramChat] Ошибка parse_mode={parse_mode}, повтор без разметки: {exc}")
                await message.reply_text(chunk)
            else:
                raise


class TelegramChatService:
    """Управляет диалогом пользователей Telegram с моделью ИИ и базой знаний.

    Attributes:
        wm (Optional[WorkspaceManager]): Менеджер рабочих областей.
        qa_engine (Optional[KnowledgeQAEngine]): Движок QA по документам рабочей области.
        ai_model (Any): Опциональный внешний экземпляр модели ИИ (для DI/тестов).
        chat_model_factory (Optional[Callable[..., Any]]): Фабрика создания UnifiedChatModel.
        max_history_messages (int): Максимальное количество сообщений в памяти на пользователя.
    """

    def __init__(
        self,
        workspace_manager: Optional[WorkspaceManager] = None,
        qa_engine: Optional[KnowledgeQAEngine] = None,
        ai_model: Any = None,
        chat_model_factory: Optional[Callable[..., Any]] = None,
        max_history_messages: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        """Инициализирует сервис чата Telegram."""
        self.wm = workspace_manager
        self.qa_engine = qa_engine
        self.ai_model = ai_model
        self.chat_model_factory = chat_model_factory
        self.max_history_messages = max(2, int(max_history_messages))

        self._histories: Dict[int, List[Dict[str, str]]] = {}
        self._modes: Dict[int, str] = {}
        self._cached_model_key: Tuple[str, str] = ("", "")
        self._cached_chat_model: Any = None

    def get_mode(self, tg_id: int) -> str:
        """Возвращает текущий режим чата для пользователя Telegram."""
        return self._modes.get(tg_id, "auto")

    def set_mode(self, tg_id: int, mode: str) -> str:
        """Устанавливает режим чата для пользователя Telegram."""
        clean = str(mode or "").strip().lower()
        if clean not in VALID_CHAT_MODES:
            raise ValueError(f"Недопустимый режим чата: {mode}. Доступно: {', '.join(VALID_CHAT_MODES)}")
        self._modes[tg_id] = clean
        return clean

    def clear_history(self, tg_id: int) -> int:
        """Очищает историю диалога пользователя и возвращает число удалённых сообщений."""
        prev = self._histories.pop(tg_id, [])
        return len(prev)

    def get_history(self, tg_id: int) -> List[Dict[str, str]]:
        """Возвращает копию текущей истории диалога пользователя."""
        return list(self._histories.get(tg_id, []))

    def _append_history(self, tg_id: int, user_text: str, assistant_text: str) -> None:
        """Добавляет пару реплик в историю пользователя с соблюдением лимита длины."""
        hist = self._histories.setdefault(tg_id, [])
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": assistant_text})
        if len(hist) > self.max_history_messages:
            self._histories[tg_id] = hist[-self.max_history_messages :]

    def get_active_model_label(self) -> str:
        """Возвращает читаемое описание текущей активной модели ИИ."""
        if self.ai_model is not None:
            return str(getattr(self.ai_model, "model_name", type(self.ai_model).__name__))
        provider, model = resolve_active_model_config()
        if provider and model:
            return f"{provider}:{model}"
        return provider or "Не настроена"

    def _get_qa_engine(self) -> Optional[KnowledgeQAEngine]:
        """Лениво возвращает экземпляр KnowledgeQAEngine."""
        if self.qa_engine is not None:
            return self.qa_engine
        if self.wm is None:
            return None
        try:
            from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine

            self.qa_engine = KnowledgeQAEngine(workspace_manager=self.wm)
            return self.qa_engine
        except Exception as exc:
            logger.warning(f"[TelegramChat] Не удалось инициализировать KnowledgeQAEngine: {exc}")
            return None

    def _get_or_create_chat_model(self, provider: str, model: str) -> Any:
        """Возвращает кэшированный или новый экземпляр UnifiedChatModel для пары (provider, model)."""
        key = (provider.strip().lower(), model.strip())
        if self._cached_chat_model is not None and self._cached_model_key == key:
            return self._cached_chat_model

        if self.chat_model_factory is not None:
            instance = self.chat_model_factory(
                system_instruction=_DEFAULT_SYSTEM_INSTRUCTION,
                provider=provider,
                model=model,
            )
        else:
            from src.ai.orchestration.unified_chat import UnifiedChatModel

            instance = UnifiedChatModel(
                system_instruction=_DEFAULT_SYSTEM_INSTRUCTION,
                provider=provider,
                model=model,
            )

        self._cached_chat_model = instance
        self._cached_model_key = key
        return instance

    async def _call_custom_ai_model(self, model_obj: Any, user_text: str, history: List[Dict[str, str]]) -> str:
        """Вызывает внешний экземпляр модели ИИ (переданный через DI или тесты)."""
        if hasattr(model_obj, "chat") and callable(model_obj.chat):
            if asyncio.iscoroutinefunction(model_obj.chat):
                res = await model_obj.chat(user_text)
            else:
                res = await asyncio.to_thread(model_obj.chat, user_text)
        elif hasattr(model_obj, "ask") and callable(model_obj.ask):
            if asyncio.iscoroutinefunction(model_obj.ask):
                res = await model_obj.ask(user_text)
            else:
                res = await asyncio.to_thread(model_obj.ask, user_text)
        elif hasattr(model_obj, "generate") and callable(model_obj.generate):
            if asyncio.iscoroutinefunction(model_obj.generate):
                res = await model_obj.generate(user_text)
            else:
                res = await asyncio.to_thread(model_obj.generate, user_text)
        else:
            raise RuntimeError(f"Модель {type(model_obj).__name__} не поддерживает методы chat/ask/generate")
        return str(res or "").strip()

    async def _ask_llm_direct(self, tg_id: int, user_text: str) -> Dict[str, Any]:
        """Выполняет прямой запрос к активной модели ИИ с сохранением истории диалога."""
        history = self.get_history(tg_id)

        if self.ai_model is not None:
            reply = await self._call_custom_ai_model(self.ai_model, user_text, history)
            if not reply:
                reply = "Модель вернула пустой ответ."
            self._append_history(tg_id, user_text, reply)
            return {
                "text": reply,
                "source": "llm",
                "provider": "custom",
                "model": str(getattr(self.ai_model, "model_name", type(self.ai_model).__name__)),
            }

        provider, model = resolve_active_model_config()
        if not model:
            raise RuntimeError(
                "Активная модель ИИ не настроена в config.json. Выберите модель в веб-интерфейсе (вкладка Модели)."
            )

        chat_model = self._get_or_create_chat_model(provider=provider, model=model)
        raw_reply = await asyncio.wait_for(
            chat_model.chat(
                q=user_text,
                history=history if history else None,
                system_instruction=_DEFAULT_SYSTEM_INSTRUCTION,
                attempts=3,
                temperature=0.3,
            ),
            timeout=DEFAULT_LLM_TIMEOUT,
        )
        reply = str(raw_reply or "").strip()
        if not reply:
            reply = "Модель не вернула текстовый ответ. Попробуйте переформулировать вопрос."

        self._append_history(tg_id, user_text, reply)
        return {
            "text": reply,
            "source": "llm",
            "provider": provider,
            "model": model,
        }

    def _format_qa_answer(self, qa_res: Dict[str, Any], ws_name: str) -> str:
        """Форматирует ответ KnowledgeQAEngine с цитатами источников рабочей области."""
        answer = str(qa_res.get("answer") or "").strip()
        sources = qa_res.get("sources") or []
        quote_lines: List[str] = []
        for src in sources[:3]:
            if not isinstance(src, dict):
                continue
            quote = str(src.get("quote") or "").strip()
            doc_id = str(src.get("document_id") or "").strip()
            if quote:
                short_quote = quote if len(quote) <= 280 else f"{quote[:277]}…"
                src_label = f" ({doc_id})" if doc_id else ""
                quote_lines.append(f"• «{short_quote}»{src_label}")

        if quote_lines:
            return f"{answer}\n\n📎 Источники ({ws_name}):\n" + "\n".join(quote_lines)
        return answer

    async def generate_reply(self, tg_id: int, user_text: str) -> Dict[str, Any]:
        """Генерирует ответ на текстовое сообщение пользователя с учётом выбранного режима.

        Args:
            tg_id (int): Telegram ID пользователя.
            user_text (str): Текст входящего сообщения.

        Returns:
            Dict[str, Any]: Словарь с полями ``text``, ``source``, ``provider``, ``model``.
        """
        mode = self.get_mode(tg_id)
        provider, model = resolve_active_model_config()

        # 1. Прямой чат с моделью ИИ (без поиска по базе знаний)
        if mode == "chat":
            return await self._ask_llm_direct(tg_id, user_text)

        # 2. Поиск по базе знаний активной рабочей области (режимы 'auto' и 'rag')
        qa_engine = self._get_qa_engine()
        if qa_engine is not None and self.wm is not None:
            ws_id, ws_name = get_effective_user_workspace(self.wm, tg_id)
            try:
                qa_res = await qa_engine.ask(
                    question=user_text,
                    workspace_id=ws_id,
                    mode="local_first",
                    provider=provider or None,
                    model=model or None,
                )
                qa_status = str(qa_res.get("status") or "")
                qa_answer = str(qa_res.get("answer") or "").strip()

                if qa_status == "success" and qa_answer:
                    formatted = self._format_qa_answer(qa_res, ws_name)
                    self._append_history(tg_id, user_text, qa_answer)
                    proc = qa_res.get("processing") or {}
                    return {
                        "text": formatted,
                        "source": "rag",
                        "workspace_id": ws_id,
                        "provider": str(proc.get("provider") or provider),
                        "model": str(proc.get("model") or model),
                    }

                if mode == "rag":
                    fallback_text = qa_answer or "В документах выбранной рабочей области недостаточно данных для ответа."
                    return {
                        "text": fallback_text,
                        "source": "rag",
                        "workspace_id": ws_id,
                        "provider": provider,
                        "model": model,
                    }
            except Exception as exc:
                logger.warning(f"[TelegramChat] Ошибка KnowledgeQAEngine для '{ws_id}': {exc}")
                if mode == "rag":
                    raise

        # 3. В гибридном режиме ('auto') при отсутствии ответа в БЗ переключаемся на модель ИИ
        return await self._ask_llm_direct(tg_id, user_text)


def _build_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """Строит инлайн-клавиатуру выбора режима чата."""
    rows: List[List[InlineKeyboardButton]] = []
    for mode_id in VALID_CHAT_MODES:
        prefix = "✅ " if mode_id == current_mode else ""
        rows.append([
            InlineKeyboardButton(
                f"{prefix}{_MODE_LABELS[mode_id]}",
                callback_data=f"chat_mode:{mode_id}",
            )
        ])
    return InlineKeyboardMarkup(rows)


async def handle_mode_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_service: TelegramChatService,
) -> None:
    """Обрабатывает команду /mode [auto|chat|rag] для переключения режима чата."""
    if not update.message or not update.effective_user:
        return

    tg_id = update.effective_user.id
    args = context.args or []

    if args:
        requested = args[0].strip().lower()
        if requested not in VALID_CHAT_MODES:
            await update.message.reply_text(
                "ℹ️ <b>Доступные режимы:</b> <code>auto</code>, <code>chat</code>, <code>rag</code>\n"
                "Пример: <code>/mode chat</code>",
                parse_mode="HTML",
            )
            return
        chat_service.set_mode(tg_id, requested)
        await update.message.reply_text(
            f"✅ <b>Режим чата изменён:</b> {_MODE_LABELS[requested]}",
            parse_mode="HTML",
        )
        return

    current = chat_service.get_mode(tg_id)
    active_model = html.escape(chat_service.get_active_model_label())
    text = (
        "⚙️ <b>Настройка режима чата с моделью</b>\n\n"
        f"• <b>Текущий режим:</b> {_MODE_LABELS[current]}\n"
        f"• <b>Активная модель:</b> <code>{active_model}</code>\n\n"
        "Выберите нужный режим ниже:"
    )
    await update.message.reply_text(text, reply_markup=_build_mode_keyboard(current), parse_mode="HTML")


async def handle_mode_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_service: TelegramChatService,
) -> None:
    """Обрабатывает нажатия кнопок выбора режима чата (chat_mode:*)."""
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    tg_id = update.effective_user.id
    target_mode = query.data.split("chat_mode:", 1)[1].strip().lower()
    if target_mode not in VALID_CHAT_MODES:
        await query.answer("Неизвестный режим")
        return

    chat_service.set_mode(tg_id, target_mode)
    await query.answer(f"Режим: {target_mode}")

    active_model = html.escape(chat_service.get_active_model_label())
    text = (
        "⚙️ <b>Настройка режима чата с моделью</b>\n\n"
        f"• <b>Текущий режим:</b> {_MODE_LABELS[target_mode]}\n"
        f"• <b>Активная модель:</b> <code>{active_model}</code>"
    )
    try:
        await query.edit_message_text(text, reply_markup=_build_mode_keyboard(target_mode), parse_mode="HTML")
    except Exception as exc:
        logger.debug(f"[TelegramChat] Ошибка обновления сообщения режима: {exc}")


async def handle_clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_service: TelegramChatService,
) -> None:
    """Обрабатывает команду /clear (/reset) для очистки контекста диалога."""
    if not update.message or not update.effective_user:
        return
    removed = chat_service.clear_history(update.effective_user.id)
    if removed > 0:
        await update.message.reply_text(
            f"🧹 <b>История диалога очищена</b> (удалено сообщений: {removed}).",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("🧹 История диалога уже пуста.", parse_mode="HTML")
