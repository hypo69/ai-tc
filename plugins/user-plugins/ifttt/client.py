# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: IFTTT Maker Webhook Connector and Dispatcher
# =============================================================================
# Description:
#   Асинхронный клиент для вызова событий умного дома через сервис IFTTT Webhooks
#   Maker с поддержкой пользовательских параметров, JSON-нагрузки, явных таймаутов
#   и Exponential Backoff + Jitter.
#
# File: client.py
# Project: ai-breadboard
# Package: plugins.ifttt
# Module: plugins.ifttt.client
# Class: IFTTTClient
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:40:00
# =============================================================================

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import random
from typing import Any, Dict, Optional

import aiohttp

from header import __root__
from logger import logger
from src.utils.jjson import j_loads_ns

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3


class IFTTTClient:
    """Асинхронный клиент для взаимодействия с каналом IFTTT Webhook Maker.

    Attributes:
        webhook_key (str): Ключ IFTTT Webhooks Maker по умолчанию.
        base_url (str): Базовый URL IFTTT Maker Webhooks.
        timeout_seconds (int): Таймаут сетевого запроса в секундах.
    """

    def __init__(
        self,
        webhook_key: str = "",
        config_path: Path = Path("config.json"),
        timeout_seconds: int = 10,
    ) -> None:
        """Инициализация IFTTTClient с ключом и параметрами конфигурации."""
        self.timeout_seconds: int = max(1, int(timeout_seconds))
        self.base_url: str = "https://maker.ifttt.com/trigger"

        env_key = os.environ.get("IFTTT_WEBHOOK_KEY", "") or os.environ.get("IFTTT_KEY", "")
        if webhook_key:
            self.webhook_key: str = webhook_key
        elif env_key:
            self.webhook_key = env_key
        else:
            cfg = j_loads_ns(__root__ / config_path)
            ifttt_cfg = getattr(cfg, "ifttt", object())
            self.webhook_key = getattr(ifttt_cfg, "webhook_key", "")

        logger.debug(f"[IFTTTClient] Инициализирован (ключ настроен: {bool(self.webhook_key)})")

    def is_configured(self) -> bool:
        """Возвращает True, если ключ IFTTT webhook задан."""
        return bool(self.webhook_key)

    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус готовности клиента IFTTT."""
        configured: bool = self.is_configured()
        return {
            "configured": configured,
            "masked_key": (
                f"{self.webhook_key[:4]}...{self.webhook_key[-4:]}"
                if len(self.webhook_key) >= 8
                else ("configured" if configured else "not_configured")
            ),
            "base_url": self.base_url,
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Проверяет соединение и валидность ключа отправкой тестового события ping."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "IFTTT_WEBHOOK_KEY is missing or not configured in .env or plugin config.",
            }
        result = await self.trigger_event(event_name="ping", value1="AI-Breadboard Connection Test")
        if result.get("status") == "success":
            return {
                "success": True,
                "message": f"Connection to IFTTT Maker Webhooks verified (HTTP {result.get('http_code')}).",
                "data": result,
            }
        return {
            "success": False,
            "error": result.get("error", "Failed to contact IFTTT Maker Webhooks"),
            "data": result,
        }

    async def trigger_event(
        self,
        event_name: str,
        value1: str = "",
        value2: str = "",
        value3: str = "",
        json_payload: Optional[Dict[str, Any]] = None,
        webhook_key: str = "",
    ) -> Dict[str, Any]:
        """Вызывает событие IFTTT Webhook с параметрами или произвольной JSON-нагрузкой."""
        clean_event = (event_name or "").strip()
        if not clean_event:
            logger.warning("[IFTTTClient] Попытка вызова события с пустым event_name.")
            return {
                "status": "error",
                "error": "event_name cannot be empty",
                "event": "",
            }

        active_key = webhook_key or self.webhook_key
        if not active_key:
            logger.error("[IFTTTClient] Ключ IFTTT Webhook не настроен.")
            return {
                "status": "error",
                "error": "IFTTT_WEBHOOK_KEY is not set. Please set it in .env or config.json.",
                "event": clean_event,
            }

        if json_payload:
            endpoint = f"{self.base_url}/{clean_event}/json/with/key/{active_key}"
            payload_data: Dict[str, Any] = dict(json_payload)
        else:
            endpoint = f"{self.base_url}/{clean_event}/with/key/{active_key}"
            payload_data = {}
            if value1:
                payload_data["value1"] = value1
            if value2:
                payload_data["value2"] = value2
            if value3:
                payload_data["value3"] = value3

        logger.info(f"[IFTTTClient] Отправка события '{clean_event}' в IFTTT Maker Webhooks.")

        timeout = aiohttp.ClientTimeout(
            total=float(self.timeout_seconds),
            connect=min(5.0, float(self.timeout_seconds)),
            sock_read=float(self.timeout_seconds),
        )
        last_err = ""
        for attempt in range(_MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        endpoint,
                        json=payload_data,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        resp_text = await response.text()
                        if response.status == 200:
                            logger.info(f"[IFTTTClient] Событие '{clean_event}' успешно вызвано: {resp_text.strip()}")
                            return {
                                "status": "success",
                                "event": clean_event,
                                "http_code": response.status,
                                "message": resp_text.strip(),
                            }
                        if response.status not in _RETRYABLE_STATUS or attempt == _MAX_RETRIES - 1:
                            logger.error(f"[IFTTTClient] Ошибка события '{clean_event}' ({response.status}): {resp_text}")
                            return {
                                "status": "error",
                                "event": clean_event,
                                "http_code": response.status,
                                "error": resp_text.strip(),
                            }
                        last_err = f"HTTP {response.status}: {resp_text.strip()}"
            except Exception as exc:
                last_err = str(exc)
                if attempt == _MAX_RETRIES - 1:
                    logger.error(f"[IFTTTClient] Исключение при вызове события '{clean_event}': {exc}")
                    return {
                        "status": "error",
                        "event": clean_event,
                        "error": str(exc),
                    }
            await asyncio.sleep((0.4 * (2 ** attempt)) + random.uniform(0.05, 0.2))

        return {
            "status": "error",
            "event": clean_event,
            "error": last_err or "Unknown IFTTT error",
        }


async def send_ifttt_event(
    event_name: str,
    value1: str = "",
    value2: str = "",
    value3: str = "",
    json_payload: Optional[Dict[str, Any]] = None,
    webhook_key: str = "",
) -> Dict[str, Any]:
    """Вспомогательная функция для вызова события IFTTT."""
    client = IFTTTClient(webhook_key=webhook_key)
    return await client.trigger_event(
        event_name=event_name,
        value1=value1,
        value2=value2,
        value3=value3,
        json_payload=json_payload,
    )
