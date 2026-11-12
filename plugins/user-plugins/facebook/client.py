# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Facebook Graph API Client Interface
# =============================================================================
# Description:
#   Асинхронный HTTP-клиент для взаимодействия с Facebook Graph API:
#   публикация записей, ссылок, фотографий и инспекция страниц с поддержкой
#   явных таймаутов и Exponential Backoff + Jitter.
#
# File: client.py
# Project: ai-breadboard
# Package: plugins.facebook
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:40:00
# =============================================================================

"""Модуль клиента Facebook Graph API.

Обрабатывает сетевые запросы к эндпоинтам Facebook Graph API, предоставляя
типизированные методы публикации сообщений, медиафайлов, получения информации
о страницах и проверки токенов авторизации.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, Optional
import httpx

from logger import logger

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3


class FacebookGraphClient:
    """Асинхронный клиент для взаимодействия с Facebook Graph API.

    Attributes:
        page_id (str): Идентификатор целевой страницы Facebook по умолчанию.
        access_token (str): Токен доступа страницы или пользователя Facebook.
        api_version (str): Версия Facebook Graph API (например, 'v19.0').
        base_url (str): Базовый URL эндпоинтов Graph API.
    """

    def __init__(
        self,
        page_id: str = "",
        access_token: str = "",
        api_version: str = "v19.0",
    ) -> None:
        """Инициализирует клиент Facebook Graph API.

        Args:
            page_id (str): Идентификатор целевой страницы Facebook.
            access_token (str): Валидный токен доступа страницы или пользователя.
            api_version (str): Тег версии Graph API. По умолчанию 'v19.0'.
        """
        self.page_id: str = str(page_id).strip()
        self.access_token: str = access_token.strip()
        self.api_version: str = api_version.strip() or "v19.0"
        self.base_url: str = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        """Проверяет, задан ли минимально необходимый токен доступа.

        Returns:
            bool: True, если токен доступа настроен, иначе False.
        """
        return bool(self.access_token)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        timeout_sec: float = 30.0,
        **kwargs: Any,
    ) -> httpx.Response:
        """Выполняет HTTP-запрос с раздельными таймаутами и Exponential Backoff + Jitter."""
        timeout = httpx.Timeout(connect=5.0, read=timeout_sec, write=timeout_sec, pool=5.0)
        last_exc: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code not in _RETRYABLE_STATUS_CODES or attempt == _MAX_RETRIES - 1:
                        return response
                except httpx.RequestError as exc:
                    last_exc = exc
                    if attempt == _MAX_RETRIES - 1:
                        raise
                backoff = (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.25)
                await asyncio.sleep(backoff)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Не удалось выполнить запрос к Facebook Graph API")

    async def publish_post(
        self,
        message: str,
        link: Optional[str] = None,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Публикует текстовое сообщение и опциональную ссылку на странице Facebook.

        Args:
            message (str): Текст публикации.
            link (Optional[str]): Опциональный URL для прикрепления превью ссылки.
            page_id (Optional[str]): Целевой ID страницы (по умолчанию self.page_id или 'me').
            access_token (Optional[str]): Переопределяющий токен доступа.

        Returns:
            Dict[str, Any]: Ответ API с 'id' созданного поста или описанием ошибки.
        """
        token = access_token or self.access_token
        if not token:
            return {"success": False, "error": "Access token is missing or not configured."}

        target_id = page_id or self.page_id or "me"
        url = f"{self.base_url}/{target_id}/feed"

        payload: Dict[str, Any] = {
            "message": message,
            "access_token": token,
        }
        if link:
            payload["link"] = link

        try:
            response = await self._request_with_retry("POST", url, timeout_sec=30.0, data=payload)
            data = response.json()

            if response.is_success and "id" in data:
                logger.info(f"Пост Facebook успешно опубликован: ID={data['id']}")
                return {"success": True, "id": data["id"], "data": data}

            error_msg = self._extract_error(data, response.status_code)
            logger.error(f"Ошибка публикации поста в Facebook: {error_msg}")
            return {"success": False, "error": error_msg, "status_code": response.status_code, "raw": data}

        except Exception as exc:
            logger.error(f"Сетевая ошибка при публикации поста в Facebook: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    async def publish_photo(
        self,
        caption: str,
        photo_url: Optional[str] = None,
        photo_bytes: Optional[bytes] = None,
        filename: str = "photo.jpg",
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Публикует фотографию с подписью на странице Facebook.

        Args:
            caption (str): Подпись к фотографии.
            photo_url (Optional[str]): Публичный URL изображения.
            photo_bytes (Optional[bytes]): Бинарное содержимое файла изображения.
            filename (str): Имя файла при загрузке байтов.
            page_id (Optional[str]): Целевой ID страницы.
            access_token (Optional[str]): Переопределяющий токен доступа.

        Returns:
            Dict[str, Any]: Ответ API с 'id' и 'post_id' или деталями ошибки.
        """
        token = access_token or self.access_token
        if not token:
            return {"success": False, "error": "Access token is missing or not configured."}

        target_id = page_id or self.page_id or "me"
        url = f"{self.base_url}/{target_id}/photos"

        data_payload: Dict[str, Any] = {
            "caption": caption,
            "access_token": token,
        }

        try:
            if photo_bytes:
                files = {"source": (filename, photo_bytes, "image/jpeg")}
                response = await self._request_with_retry("POST", url, timeout_sec=45.0, data=data_payload, files=files)
            elif photo_url:
                data_payload["url"] = photo_url
                response = await self._request_with_retry("POST", url, timeout_sec=45.0, data=data_payload)
            else:
                return {"success": False, "error": "Neither photo_url nor photo_bytes was provided."}

            data = response.json()
            if response.is_success and "id" in data:
                logger.info(f"Фотография Facebook успешно опубликована: ID={data['id']}")
                return {"success": True, "id": data["id"], "post_id": data.get("post_id"), "data": data}

            error_msg = self._extract_error(data, response.status_code)
            logger.error(f"Ошибка публикации фотографии в Facebook: {error_msg}")
            return {"success": False, "error": error_msg, "status_code": response.status_code, "raw": data}

        except Exception as exc:
            logger.error(f"Сетевая ошибка при публикации фото в Facebook: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    async def get_page_info(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
        fields: str = "id,name,fan_count,followers_count,link,about,is_published",
    ) -> Dict[str, Any]:
        """Получает метаданные и публичную статистику целевой страницы Facebook."""
        token = access_token or self.access_token
        if not token:
            return {"success": False, "error": "Access token is missing or not configured."}

        target_id = page_id or self.page_id or "me"
        url = f"{self.base_url}/{target_id}"
        params = {"fields": fields, "access_token": token}

        try:
            response = await self._request_with_retry("GET", url, timeout_sec=20.0, params=params)
            data = response.json()

            if response.is_success and "id" in data:
                return {"success": True, "data": data}

            error_msg = self._extract_error(data, response.status_code)
            return {"success": False, "error": error_msg, "status_code": response.status_code}

        except Exception as exc:
            logger.error(f"Ошибка получения информации о странице Facebook: {exc}")
            return {"success": False, "error": str(exc)}

    async def get_accounts(
        self,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получает список страниц Facebook, управляемых текущим пользователем."""
        token = access_token or self.access_token
        if not token:
            return {"success": False, "error": "Access token is missing or not configured."}

        url = f"{self.base_url}/me/accounts"
        params = {"access_token": token}

        try:
            response = await self._request_with_retry("GET", url, timeout_sec=20.0, params=params)
            data = response.json()

            if response.is_success and "data" in data:
                return {"success": True, "accounts": data["data"]}

            error_msg = self._extract_error(data, response.status_code)
            return {"success": False, "error": error_msg, "status_code": response.status_code}

        except Exception as exc:
            logger.error(f"Ошибка получения аккаунтов Facebook: {exc}")
            return {"success": False, "error": str(exc)}

    async def test_connection(self) -> Dict[str, Any]:
        """Проверяет валидность токена API и доступность Graph API."""
        if not self.is_configured():
            return {
                "success": False,
                "configured": False,
                "error": "Facebook Access Token is not set.",
            }

        target_id = self.page_id or "me"
        info = await self.get_page_info(page_id=target_id, fields="id,name,is_published")
        if info.get("success"):
            page_data = info.get("data", {})
            return {
                "success": True,
                "configured": True,
                "target_id": target_id,
                "name": page_data.get("name", "Unknown"),
                "id": page_data.get("id"),
                "message": f"Successfully connected to Facebook target: {page_data.get('name', target_id)}",
            }

        return {
            "success": False,
            "configured": True,
            "error": info.get("error", "Unknown API error during connection test."),
        }

    def _extract_error(self, data: Dict[str, Any], status_code: int) -> str:
        """Извлекает понятное сообщение об ошибке из ответа Graph API."""
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                msg = err.get("message", "Unknown Facebook API error")
                err_type = err.get("type", "")
                code = err.get("code", "")
                fbtrace_id = err.get("fbtrace_id", "")
                details = f"{msg} (code: {code}, type: {err_type})"
                if fbtrace_id:
                    details += f" [trace: {fbtrace_id}]"
                return details
            return str(err)
        return f"HTTP {status_code} request failed"
