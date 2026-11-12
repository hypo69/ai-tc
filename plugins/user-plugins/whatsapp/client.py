# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: WhatsApp Messenger Client & API Dispatcher
# =============================================================================
# Description:
#   Клиент для взаимодействия с API WhatsApp (Meta Cloud API / Green API / Webhook).
#   Обеспечивает валидацию телефонных номеров, формирование полезной нагрузки,
#   отправку текстовых сообщений и оповещений о входящей почте с поддержкой
#   Exponential Backoff + Jitter и проверкой безопасности URL.
#
# File: client.py
# Package: plugins.user-plugins.whatsapp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:40:00
# =============================================================================
"""Модуль клиента для отправки сообщений в WhatsApp через внешние API."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import random
import re
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.parse
import urllib.request

try:
    from logger.logger import logger
except ImportError:
    logger = logging.getLogger("whatsapp_plugin")

_NON_DIGITS_RE = re.compile(r"\D")
_RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3


def normalize_phone_number(phone: str) -> str:
    """Нормализует номер телефона к формату только цифр (E.164 без знака плюс).

    Args:
        phone (str): Исходный номер телефона (напр. '+7 (999) 123-45-67').

    Returns:
        str: Строка из одних цифр (напр. '79991234567').
    """
    return _NON_DIGITS_RE.sub("", phone or "")


class WhatsAppClient:
    """Клиент для отправки сообщений через API WhatsApp."""

    def __init__(
        self,
        token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: str = "v18.0",
        provider: str = "cloud_api",
        config_path: Optional[Path] = None,
        timeout: int = 15,
    ) -> None:
        """Инициализация клиента WhatsApp."""
        self.timeout = max(1, int(timeout))
        self.api_version = api_version
        self.provider = provider
        self._load_config(token, phone_number_id, config_path)

    def _load_config(
        self,
        token: Optional[str],
        phone_number_id: Optional[str],
        config_path: Optional[Path],
    ) -> None:
        """Загружает токены и параметры из аргументов, secrets.json или окружения."""
        file_data: Dict[str, Any] = {}
        paths_to_check = []
        if config_path:
            paths_to_check.append(Path(config_path))
        else:
            current_dir = Path(__file__).resolve().parent
            paths_to_check.extend([
                current_dir / "secrets.json",
                current_dir / ".secrets.json",
                Path.cwd() / "secrets.json",
            ])

        for p in paths_to_check:
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    break
                except Exception as ex:
                    logger.warning(f"[whatsapp_client] Ошибка чтения {p}: {ex}")

        self.token = (
            token
            or file_data.get("token")
            or file_data.get("access_token")
            or file_data.get("whatsapp_token")
            or os.getenv("WHATSAPP_TOKEN")
            or os.getenv("WHATSAPP_ACCESS_TOKEN")
            or ""
        )
        self.phone_number_id = (
            phone_number_id
            or file_data.get("phone_number_id")
            or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
            or ""
        )
        self.provider = (
            file_data.get("provider")
            or os.getenv("WHATSAPP_PROVIDER")
            or self.provider
        )
        self.webhook_url = (
            file_data.get("webhook_url")
            or os.getenv("WHATSAPP_WEBHOOK_URL")
            or ""
        )
        self.default_recipient = (
            file_data.get("default_recipient")
            or os.getenv("WHATSAPP_RECIPIENT_DEFAULT")
            or ""
        )

    def _urlopen_with_retry(self, req: urllib.request.Request) -> bytes:
        """Выполняет HTTP-запрос с проверкой схемы URL, таймаутом и Exponential Backoff + Jitter."""
        parsed = urllib.parse.urlparse(req.full_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Недопустимая схема URL: {parsed.scheme}")

        for attempt in range(_MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as ex:
                if ex.code not in _RETRYABLE_HTTP_CODES or attempt == _MAX_RETRIES - 1:
                    raise
            except urllib.error.URLError:
                if attempt == _MAX_RETRIES - 1:
                    raise
            time.sleep((0.4 * (2 ** attempt)) + random.uniform(0.05, 0.2))
        raise RuntimeError("Превышено число попыток подключения к API WhatsApp")

    def test_connection(self) -> Dict[str, Any]:
        """Проверяет корректность параметров подключения к API."""
        if self.provider == "webhook":
            if not self.webhook_url:
                return {"success": False, "error": "Не указан WHATSAPP_WEBHOOK_URL"}
            return {"success": True, "provider": "webhook", "url": self.webhook_url}

        if not self.token:
            return {
                "success": False,
                "error": "Не задан WHATSAPP_TOKEN (Access Token). Укажите его в secrets.json или переменных окружения.",
            }

        if self.provider == "cloud_api":
            if not self.phone_number_id:
                return {
                    "success": False,
                    "error": "Не задан WHATSAPP_PHONE_NUMBER_ID для Meta Cloud API.",
                }
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
            try:
                raw_bytes = self._urlopen_with_retry(req)
                res_body = json.loads(raw_bytes.decode("utf-8"))
                return {
                    "success": True,
                    "provider": "cloud_api",
                    "phone_number_id": self.phone_number_id,
                    "details": res_body,
                }
            except urllib.error.HTTPError as ex:
                err_text = ex.read().decode("utf-8", errors="replace")
                logger.error(f"[whatsapp_client] Ошибка Graph API: {err_text}")
                return {"success": False, "error": f"HTTP {ex.code}: {err_text}"}
            except Exception as ex:
                return {"success": False, "error": str(ex)}

        return {"success": True, "provider": self.provider}

    def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """Отправляет текстовое сообщение в WhatsApp."""
        recipient = normalize_phone_number(to or self.default_recipient)
        if not recipient:
            return {"success": False, "error": "Не указан номер получателя (recipient phone number)."}

        if not message or not message.strip():
            return {"success": False, "error": "Текст сообщения не может быть пустым."}

        if self.provider == "cloud_api":
            if not self.token or not self.phone_number_id:
                return {
                    "success": False,
                    "error": "Не сконфигурированы WHATSAPP_TOKEN или WHATSAPP_PHONE_NUMBER_ID.",
                }

            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": True, "body": message},
            }
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

            try:
                raw_bytes = self._urlopen_with_retry(req)
                res_body = json.loads(raw_bytes.decode("utf-8"))
                msg_id = ""
                if "messages" in res_body and res_body["messages"]:
                    msg_id = res_body["messages"][0].get("id", "")
                return {
                    "success": True,
                    "provider": "cloud_api",
                    "recipient": recipient,
                    "whatsapp_message_id": msg_id,
                    "response": res_body,
                }
            except urllib.error.HTTPError as ex:
                err_text = ex.read().decode("utf-8", errors="replace")
                logger.error(f"[whatsapp_client] Ошибка отправки WhatsApp: {err_text}")
                return {"success": False, "error": f"HTTP {ex.code}: {err_text}"}
            except Exception as ex:
                logger.error(f"[whatsapp_client] Сетевая ошибка при отправке в WhatsApp: {ex}")
                return {"success": False, "error": str(ex)}

        if self.provider == "webhook" and self.webhook_url:
            payload = {"to": recipient, "message": message}
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                raw_bytes = self._urlopen_with_retry(req)
                res_text = raw_bytes.decode("utf-8", errors="replace")
                return {"success": True, "provider": "webhook", "response": res_text}
            except Exception as ex:
                return {"success": False, "error": str(ex)}

        return {
            "success": False,
            "error": f"Провайдер '{self.provider}' не поддерживается или не настроен.",
        }

    def send_email_alert(self, to: str, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирует и отправляет сводку о входящем письме в WhatsApp."""
        sender = email_data.get("sender") or email_data.get("from") or "Неизвестный отправитель"
        subject = email_data.get("subject") or "(без темы)"
        date_str = email_data.get("date") or ""
        body_text = email_data.get("body_text") or ""
        preview = (body_text[:300] + "...") if len(body_text) > 300 else body_text
        preview = preview.strip() or "[Содержимое письма пустое или только во вложениях]"

        formatted_msg = (
            f"📬 *Новое письмо от:* {sender}\n"
            f"📌 *Тема:* {subject}\n"
            f"🕒 *Дата:* {date_str}\n\n"
            f"💬 *Содержимое:*\n{preview}"
        )
        return self.send_message(to=to, message=formatted_msg)
