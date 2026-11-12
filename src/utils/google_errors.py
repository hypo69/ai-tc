# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Utils - Google API Errors Diagnostic Engine
# =============================================================================
# Description:
#   Централизованный модуль парсинга, диагностики и обработки ошибок сервисов
#   и API Google (Google Calendar, Gmail, Google Drive, Google Contacts, Sheets, Gemini).
#   Распознает причины сбоев (accessNotConfigured, insufficientPermissions,
#   invalid_grant, quotaExceeded), извлекает ID проекта, формирует прямые ссылки
#   в Google Cloud Console и генерирует пошаговые рекомендации по устранению.
#
# Usage Examples:
#   Python API:
#     from src.utils.google_errors import parse_google_error, log_google_error, handle_google_errors
#
#     try:
#         client.list_events()
#     except Exception as exc:
#         parsed = log_google_error(exc, context="Calendar Sync")
#
# File: google_errors.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:45:00
# =============================================================================

from __future__ import annotations

"""Модуль диагностики, парсинга и генерации решений для ошибок Google API."""

import ast
import functools
import inspect
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from logger import logger

F = TypeVar("F", bound=Callable[..., Any])

_SERVICE_MAP = {
    "calendar": ("Google Calendar API", "calendar-json.googleapis.com"),
    "gmail": ("Gmail API", "gmail.googleapis.com"),
    "drive": ("Google Drive API", "drive.googleapis.com"),
    "people": ("Google People API (Contacts)", "people.googleapis.com"),
    "contacts": ("Google Contacts API", "people.googleapis.com"),
    "sheets": ("Google Sheets API", "sheets.googleapis.com"),
    "docs": ("Google Docs API", "docs.googleapis.com"),
    "generativelanguage": ("Google Gemini API", "generativelanguage.googleapis.com"),
}


@dataclass
class ParsedGoogleError:
    """Структурированное описание распознанной ошибки Google API."""

    status_code: int = 500
    reason: str = "unknown"
    service_name: str = "Google API"
    service_id: str = ""
    project_id: Optional[str] = None
    console_url: Optional[str] = None
    title: str = "Ошибка сервиса Google API"
    human_reason: str = ""
    remediation_steps: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Возвращает сериализуемый словарь для ответов REST API."""
        return {
            "status": "error",
            "error_code": self.status_code,
            "reason": self.reason,
            "service_name": self.service_name,
            "service_id": self.service_id,
            "project_id": self.project_id,
            "console_url": self.console_url,
            "title": self.title,
            "human_reason": self.human_reason,
            "remediation_steps": self.remediation_steps,
            "notes": self.notes,
            "raw_message": self.raw_message,
        }


def _extract_dict_payload(error_source: Any) -> Dict[str, Any]:
    """Извлекает структурированный словарь из исключения или строки."""
    if isinstance(error_source, dict):
        return error_source

    # Проверка атрибута content у HttpError
    content = getattr(error_source, "content", None)
    if content:
        if isinstance(content, (bytes, bytearray)):
            content = content.decode("utf-8", errors="ignore")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # Проверка деталей у исключений
    details = getattr(error_source, "details", None)
    if isinstance(details, dict):
        return details
    if isinstance(details, list) and details and isinstance(details[0], dict):
        return details[0]

    # Поиск JSON-блоков в строковом представлении
    raw_str = str(error_source)
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = raw_str.find(start_char)
        end = raw_str.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            snippet = raw_str[start : end + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    return parsed[0]
            except Exception:
                try:
                    parsed = ast.literal_eval(snippet)
                    if isinstance(parsed, dict):
                        return parsed
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        return parsed[0]
                except Exception:
                    pass

    return {}


def _detect_service(text: str, uri: str = "") -> tuple[str, str]:
    """Определяет понятное название сервиса и его API ID по URL или тексту ошибки."""
    combined = f"{text} {uri}".lower()
    for key, (name, s_id) in _SERVICE_MAP.items():
        if key in combined:
            return name, s_id
    return "Google API", "googleapis.com"


def _extract_project_id(text: str) -> Optional[str]:
    """Извлекает цифровой или строковый Project ID из сообщения об ошибке."""
    patterns = [
        r"project[=\s/]+([0-9]{6,20})",
        r"project[:\s]+([0-9a-z\-_]{6,40})",
        r"project=([0-9a-z\-_]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_console_url(text: str) -> Optional[str]:
    """Находит прямую ссылку на включение API в консоли Google Cloud."""
    pattern = r"(https?://console\.(?:developers|cloud)\.google\.com/[^\s\"'>\)]+)"
    match = re.search(pattern, text)
    if match:
        url = match.group(1).rstrip(".,;")
        return url
    return None


def parse_google_error(error: Any) -> ParsedGoogleError:
    """Парсит ошибку Google API и генерирует структурированные рекомендации.

    Args:
        error: Объект исключения, строка или словарь с ошибкой.

    Returns:
        Объект ParsedGoogleError с пошаговыми инструкциями.
    """
    raw_str = str(error)
    payload = _extract_dict_payload(error)
    uri = getattr(error, "uri", "")

    # Определение HTTP статуса
    status_code = 500
    resp = getattr(error, "resp", None)
    if resp and hasattr(resp, "status"):
        try:
            status_code = int(resp.status)
        except Exception:
            pass
    elif "status_code" in payload:
        try:
            status_code = int(payload["status_code"])
        except Exception:
            pass
    elif "error" in payload and isinstance(payload["error"], dict) and "code" in payload["error"]:
        try:
            status_code = int(payload["error"]["code"])
        except Exception:
            pass
    else:
        status_match = re.search(r"HttpError\s+([0-9]{3})", raw_str, re.IGNORECASE)
        if status_match:
            status_code = int(status_match.group(1))

    # Определение сервиса Google
    service_name, service_id = _detect_service(raw_str, uri)

    # Извлечение Project ID и ссылки
    project_id = _extract_project_id(raw_str)
    console_url = _extract_console_url(raw_str)

    # Определение причины (reason)
    reason = "unknown"
    message = raw_str

    if "error" in payload and isinstance(payload["error"], dict):
        err_obj = payload["error"]
        message = err_obj.get("message", message)
        errors_list = err_obj.get("errors", [])
        if errors_list and isinstance(errors_list, list) and isinstance(errors_list[0], dict):
            reason = errors_list[0].get("reason", reason)
        details = err_obj.get("details", [])
        if details and isinstance(details, list) and isinstance(details[0], dict):
            reason = details[0].get("reason", reason)
    elif "reason" in payload:
        reason = payload["reason"]
    elif "error" in payload and isinstance(payload["error"], str):
        reason = payload["error"]

    # Эвристика по тексту, если reason не найден
    if reason in ("unknown", ""):
        if "accessnotconfigured" in raw_str.lower() or "has not been used in project" in raw_str.lower():
            reason = "accessNotConfigured"
        elif "insufficient" in raw_str.lower() or "scope" in raw_str.lower():
            reason = "insufficientPermissions"
        elif "invalid_grant" in raw_str.lower():
            reason = "invalid_grant"
        elif "ratelimitexceeded" in raw_str.lower() or "quota" in raw_str.lower():
            reason = "rateLimitExceeded"
        elif "notfound" in raw_str.lower() or status_code == 404:
            reason = "notFound"

    # Формирование URL консоли при его отсутствии
    if not console_url and project_id and service_id:
        console_url = f"https://console.developers.google.com/apis/api/{service_id}/overview?project={project_id}"

    # Формирование решений и рекомендаций
    remediation_steps: List[str] = []
    notes: List[str] = []

    if reason == "accessNotConfigured" or status_code == 403 and "has not been used" in raw_str:
        reason = "accessNotConfigured"
        status_code = 403
        title = f"API сервиса {service_name} не включён в проекте Google Cloud"
        human_reason = (
            f"Приложение обращается к {service_name}, но этот API ещё не активирован "
            f"в Google Cloud Project {project_id or ''} либо отключён администратором."
        )
        if console_url:
            remediation_steps.append(f"Откройте страницу активации в Google Cloud Console: {console_url}")
        else:
            remediation_steps.append(f"Откройте консоль Google Cloud и перейдите в раздел '{service_name}'")
        remediation_steps.append("Нажмите кнопку 'Включить' (Enable). Если отображается 'Управление' (Manage) — API уже включён.")
        remediation_steps.append("Подождите 2-5 минут для распространения изменений на серверах Google и повторите операцию.")
        notes.append(f"Проверьте, что в настройках проекта используется ID {project_id or 'активного проекта'}, а не другого тестового.")
        notes.append("Параметры запроса (фильтры дат, лимиты, пагинация) не являются причиной данной ошибки.")

    elif reason in ("ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficientPermissions"):
        status_code = 403
        title = f"Недостаточно прав доступа (OAuth Scopes) для {service_name}"
        human_reason = "Текущий токен авторизации не содержит необходимых разрешений для выполнения этой операции."
        remediation_steps.append("Проверьте набор разрешений (OAuth Scopes) в конфигурации аккаунтов Google.")
        remediation_steps.append("Выполните повторную авторизацию аккаунта Google для выдачи расширенных прав.")
        remediation_steps.append("Убедитесь, что пользователь подтвердил все запрашиваемые доступы на экране согласия Google.")

    elif reason == "invalid_grant" or "token has been expired" in raw_str.lower():
        status_code = 401
        title = "Срок действия токена авторизации Google истек или отозван"
        human_reason = "OAuth refresh token недействителен, был отозван пользователем или истек срок его жизни."
        remediation_steps.append("Удалите устаревший токен аккаунта в каталоге src/secrets/google_oauth_tokens/.")
        remediation_steps.append("Пройдите повторную авторизацию аккаунта через WebGUI или CLI.")

    elif reason in ("rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded") or status_code == 429:
        status_code = 429
        title = f"Превышен лимит запросов или квота для {service_name}"
        human_reason = "Серверы Google временно ограничили запросы из-за превышения квоты вызовов в минуту или сутки."
        remediation_steps.append("Сделайте паузу на 1-2 минуты перед следующим запросом.")
        remediation_steps.append("Убедитесь, что не запущены параллельные интенсивные циклы синхронизации.")
        remediation_steps.append("При регулярном возникновении увеличьте квоту в Google Cloud Console (Quotas & System Limits).")

    elif reason == "notFound" or status_code == 404:
        status_code = 404
        title = f"Запрашиваемый ресурс {service_name} не найден"
        human_reason = "Календарь, письмо, файл или контакт с указанным идентификатором не существует или удален."
        remediation_steps.append("Проверьте корректность переданного ID ресурса.")
        remediation_steps.append("Убедитесь, что у учетной записи есть доступ к этому ресурсу.")

    else:
        title = f"Ошибка выполнения запроса к {service_name}"
        human_reason = message or "Произошла непредвиденная ошибка при обращении к сервисам Google."
        remediation_steps.append("Проверьте сетевое соединение и доступность сервисов Google.")
        remediation_steps.append("Проверьте актуальность учетных данных и конфигурации аккаунта.")

    return ParsedGoogleError(
        status_code=status_code,
        reason=reason,
        service_name=service_name,
        service_id=service_id,
        project_id=project_id,
        console_url=console_url,
        title=title,
        human_reason=human_reason,
        remediation_steps=remediation_steps,
        notes=notes,
        raw_message=raw_str,
    )


def log_google_error(error: Any, context: str = "") -> ParsedGoogleError:
    """Логирует ошибку в файл и выводит понятную инструкцию по устранению в консоль.

    Args:
        error: Объект исключения или строка с ошибкой.
        context: Контекст вызова (например, 'Google Calendar Sync', 'Gmail Router').

    Returns:
        Экземпляр ParsedGoogleError.
    """
    parsed = parse_google_error(error)
    prefix = f"[{context}] " if context else ""

    # Запись технического события в файл лога
    logger.error(
        f"{prefix}Google API Error ({parsed.service_name}): {parsed.reason} "
        f"[HTTP {parsed.status_code}] Project: {parsed.project_id or 'N/A'}"
    )

    # Вывод красиво оформленного диагностического отчета в консоль
    logger.console("\n" + "=" * 76, text_color="yellow")
    logger.console(f"⚠️  {parsed.title.upper()}", text_color="light_red")
    logger.console("=" * 76, text_color="yellow")
    logger.console(f"Сервис:   {parsed.service_name} ({parsed.service_id or 'Google APIs'})")
    if parsed.project_id:
        logger.console(f"Проект:   Google Cloud Project ID: {parsed.project_id}")
    logger.console(f"Причина:  {parsed.human_reason}\n")

    if parsed.console_url:
        logger.console(f"🔗 ССЫЛКА НА ВКЛЮЧЕНИЕ API В GOOGLE CONSOLE:\n   {parsed.console_url}\n", text_color="cyan")

    if parsed.remediation_steps:
        logger.console("КАК ИСПРАВИТЬ (ПОШАГОВАЯ ИНСТРУКЦИЯ):", text_color="light_green")
        for idx, step in enumerate(parsed.remediation_steps, 1):
            logger.console(f"  {idx}. {step}")

    if parsed.notes:
        logger.console("\nДОПОЛНИТЕЛЬНО:", text_color="light_yellow")
        for note in parsed.notes:
            logger.console(f"  • {note}")

    logger.console("=" * 76 + "\n", text_color="yellow")
    return parsed


def handle_google_errors(context: str = "", reraise: bool = True) -> Callable[[F], F]:
    """Декоратор для безопасного перехвата и диагностики ошибок Google API.

    Args:
        context: Описание выполняемой операции.
        reraise: Вызывать ли исключение RuntimeError с понятным текстом после логирования.

    Returns:
        Обернутая функция или корутина.
    """
    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    ctx = context or func.__name__
                    parsed = log_google_error(exc, context=ctx)
                    if reraise:
                        url_hint = f" Ссылка для активации: {parsed.console_url}" if parsed.console_url else ""
                        raise RuntimeError(
                            f"[{parsed.service_name}] {parsed.human_reason} (Код: {parsed.status_code}, "
                            f"Причина: {parsed.reason}).{url_hint}"
                        ) from exc
                    return None
            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ctx = context or func.__name__
                parsed = log_google_error(exc, context=ctx)
                if reraise:
                    url_hint = f" Ссылка для активации: {parsed.console_url}" if parsed.console_url else ""
                    raise RuntimeError(
                        f"[{parsed.service_name}] {parsed.human_reason} (Код: {parsed.status_code}, "
                        f"Причина: {parsed.reason}).{url_hint}"
                    ) from exc
                return None
        return sync_wrapper  # type: ignore[return-value]

    return decorator
