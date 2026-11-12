# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - google_accounts
# =============================================================================
# Description:
#   Эндпойнты управления пулом учетных записей Google Workspace (OAuth2 и Service Account).
#
# File: google_accounts.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 15:46:00
# =============================================================================

from __future__ import annotations

"""Эндпойнты управления учетными записями Google Workspace в пуле ротации."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from src.ai.google_accounts_state import (
    DEFAULT_SCOPES,
    _OAUTH_FILES_DIR,
    _TOKENS_DIR,
    delete_google_account,
    get_account_info,
    list_google_accounts,
    reset_account_status,
    save_google_account,
    set_default_account,
)
from .routers import router, router_v1


class GoogleAccountCreatePayload(BaseModel):
    """Полезная нагрузка для создания/добавления учетной записи Google."""
    name: Optional[str] = Field(None, description="Уникальное имя аккаунта")
    account_name: Optional[str] = Field(None, description="Алиас имени аккаунта")
    type: Optional[str] = Field("oauth2", description="Тип учетной записи: oauth2 или service_account")
    account_type: Optional[str] = Field(None, description="Алиас типа аккаунта")
    email: Optional[str] = Field(None, description="Email адрес")
    client_id: Optional[str] = Field(None, description="OAuth2 Client ID")
    client_secret: Optional[str] = Field(None, description="OAuth2 Client Secret")
    credentials_json: Optional[str] = Field(None, description="Содержимое JSON ключа строкой")
    credentials_dict: Optional[Dict[str, Any]] = Field(None, description="Содержимое JSON ключа словарем")
    set_as_default: Optional[bool] = Field(False, description="Установить по умолчанию")


@router_v1.get('/google-accounts')
@router_v1.get('/google-accounts/')
@router.get('/google-accounts')
@router.get('/google-accounts/')
async def get_google_accounts() -> Dict[str, Any]:
    """Возвращает список всех учетных записей Google в пуле."""
    try:
        raw_accounts = list_google_accounts()
        accounts = []
        for acc in raw_accounts:
            item = dict(acc)
            token_str = item.get('token_file', '')
            if token_str:
                tp = Path(token_str)
                token_path = tp if tp.is_absolute() else __root__ / tp
                item['has_token'] = token_path.exists()
            else:
                item['has_token'] = False
            accounts.append(item)
        return {"status": "success", "accounts": accounts}
    except Exception as exc:
        logger.error(f"Ошибка получения списка Google аккаунтов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.get('/google-accounts/{name}')
@router.get('/google-accounts/{name}')
async def get_single_google_account(name: str) -> Dict[str, Any]:
    """Возвращает информацию о конкретной учетной записи Google."""
    try:
        info = get_account_info(name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
        token_str = info.get('token_file', '')
        if token_str:
            tp = Path(token_str)
            token_path = tp if tp.is_absolute() else __root__ / tp
            info['has_token'] = token_path.exists()
        else:
            info['has_token'] = False
        return {"status": "success", "account": info}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка получения данных аккаунта '{name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.post('/google-accounts')
@router_v1.post('/google-accounts/')
@router.post('/google-accounts')
@router.post('/google-accounts/')
async def create_google_account(payload: GoogleAccountCreatePayload) -> Dict[str, Any]:
    """Создает или обновляет учетную запись Google в пуле."""
    try:
        acc_name = (payload.account_name or payload.name or "").strip()
        if not acc_name:
            raise HTTPException(status_code=400, detail="Имя аккаунта обязательно для заполнения")

        acc_type = (payload.account_type or payload.type or "oauth2").strip().lower()

        creds_data: Any = None
        if payload.credentials_dict:
            creds_data = payload.credentials_dict
        elif payload.credentials_json:
            try:
                creds_data = json.loads(payload.credentials_json)
            except Exception:
                creds_data = payload.credentials_json
        elif payload.client_id and payload.client_secret:
            creds_data = {
                "installed": {
                    "client_id": payload.client_id.strip(),
                    "client_secret": payload.client_secret.strip(),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Необходимо предоставить учетные данные (JSON или Client ID/Secret)")

        res = save_google_account(
            account_name=acc_name,
            credentials_path_or_dict=creds_data,
            account_type=acc_type,
            email=payload.email or "",
            set_as_default=bool(payload.set_as_default)
        )
        if not res:
            raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт в пуле")

        return {"status": "success", "account": get_account_info(acc_name)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка создания Google аккаунта '{payload.name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.post('/google-accounts/upload')
@router.post('/google-accounts/upload')
async def upload_google_account_credentials(
    account_name: Optional[str] = Form(None),
    account_type: Optional[str] = Form("oauth2"),
    email: Optional[str] = Form(""),
    set_as_default: Optional[str] = Form("false"),
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """Загрузка файла учетных данных Google (credentials.json / service_account.json)."""
    try:
        content = await file.read()
        try:
            creds_dict = json.loads(content.decode('utf-8'))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Файл не содержит валидный JSON: {exc}")

        # Определение типа по структуре JSON при необходимости
        detected_type = "service_account" if creds_dict.get("type") == "service_account" else (account_type or "oauth2")

        # Определение имени аккаунта
        acc_name = (account_name or "").strip()
        if not acc_name:
            filename = file.filename or "credentials.json"
            acc_name = Path(filename).stem.removesuffix('_secret').removesuffix('_credentials')
            if not acc_name:
                acc_name = "default"

        is_default = str(set_as_default).lower() in ("true", "1", "yes")

        res = save_google_account(
            account_name=acc_name,
            credentials_path_or_dict=creds_dict,
            account_type=detected_type,
            email=email or "",
            set_as_default=is_default
        )
        if not res:
            raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт из загруженного файла")

        return {"status": "success", "account_name": acc_name, "account": get_account_info(acc_name)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка загрузки файла учетных данных Google: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.post('/google-accounts/{name}/default')
@router_v1.post('/google-accounts/{name}/set-default')
@router.post('/google-accounts/{name}/default')
@router.post('/google-accounts/{name}/set-default')
async def set_default_google_account(name: str) -> Dict[str, Any]:
    """Назначение учетной записи Google аккаунтом по умолчанию."""
    try:
        res = set_default_account(name)
        if not res:
            raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
        return {"status": "success", "default_account": name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка назначения аккаунта по умолчанию '{name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.post('/google-accounts/{name}/reset-status')
@router.post('/google-accounts/{name}/reset-status')
async def reset_google_account_status_endpoint(name: str) -> Dict[str, Any]:
    """Сброс исчерпания квоты и возврат аккаунта Google в активное состояние."""
    try:
        res = reset_account_status(name)
        if not res:
            raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
        return {"status": "success", "name": name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка сброса статуса аккаунта '{name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router_v1.post('/google-accounts/{name}/test')
@router.post('/google-accounts/{name}/test')
async def test_google_account_endpoint(name: str) -> Dict[str, Any]:
    """Проверка аутентификации и валидности учетных данных Google аккаунта."""
    try:
        info = get_account_info(name)
        if not info:
            return {"status": "error", "name": name, "message": f"Аккаунт '{name}' не найден в пуле"}

        acc_type = info.get("type", "oauth2")
        creds_rel = info.get("credentials_file", "")
        token_rel = info.get("token_file", "")

        creds_path = (Path(creds_rel) if Path(creds_rel).is_absolute() else __root__ / creds_rel) if creds_rel else None
        token_path = (Path(token_rel) if Path(token_rel).is_absolute() else __root__ / token_rel) if token_rel else (_TOKENS_DIR / f"{name}_token.json")

        if acc_type == "service_account":
            if not creds_path or not creds_path.exists():
                return {"status": "error", "name": name, "message": f"Файл Service Account не найден: {creds_path}"}
            try:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(str(creds_path), scopes=DEFAULT_SCOPES)
                return {"status": "success", "name": name, "message": "Service Account JSON валиден и готов к работе", "scopes": DEFAULT_SCOPES}
            except Exception as e:
                return {"status": "error", "name": name, "message": f"Ошибка верификации Service Account: {e}"}

        # OAuth 2.0
        if not token_path.exists():
            if creds_path and creds_path.exists():
                return {
                    "status": "warning",
                    "name": name,
                    "message": "Файл client_secrets загружен, но OAuth2 токен ещё не создан (требуется авторизация).",
                    "scopes": DEFAULT_SCOPES
                }
            return {
                "status": "error",
                "name": name,
                "message": f"Учетные данные не найдены ни в токенах, ни в secrets."
            }

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(str(token_path), DEFAULT_SCOPES)
            if creds.valid:
                scopes = list(creds.scopes or DEFAULT_SCOPES)
                return {"status": "success", "name": name, "message": "OAuth2 токен валиден и активен", "scopes": scopes}
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(token_path, "w", encoding="utf-8") as tf:
                        tf.write(creds.to_json())
                    scopes = list(creds.scopes or DEFAULT_SCOPES)
                    return {"status": "success", "name": name, "message": "OAuth2 токен успешно обновлен через Refresh Token", "scopes": scopes}
                except Exception as ref_err:
                    return {"status": "warning", "name": name, "message": f"Срок действия токена истек, ошибка обновления: {ref_err}"}
            return {"status": "warning", "name": name, "message": "Токен невалиден или просрочен"}
        except Exception as e:
            return {"status": "error", "name": name, "message": f"Ошибка чтения токена OAuth2: {e}"}

    except Exception as exc:
        logger.error(f"Ошибка тестирования Google аккаунта '{name}': {exc}")
        return {"status": "error", "name": name, "message": str(exc)}


@router_v1.delete('/google-accounts/{name}')
@router.delete('/google-accounts/{name}')
async def delete_google_account_endpoint(name: str) -> Dict[str, Any]:
    """Удаление учетной записи Google из пула."""
    try:
        res = delete_google_account(name)
        if not res:
            raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
        return {"status": "success", "message": f"Аккаунт '{name}' удален"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка удаления аккаунта '{name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

