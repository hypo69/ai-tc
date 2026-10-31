# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin API - Router Keys Module
# =============================================================================
# Description:
#   Router для управления API ключами.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_keys import KeyCreateRequest
#
#     service = KeyCreateRequest()
#
# File: router_keys.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 12:24:00
# =============================================================================

"""Router для управления API ключами."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any, Optional
from types import SimpleNamespace

from header import __root__
from logger import logger
from src.ai.gemini.gemini_api_key_state import reset_all_quotas, reset_quota, mark_exhausted, load_api_keys

router = APIRouter(prefix="/api/keys", tags=["router_keys"])

class KeyCreateRequest(BaseModel):
    """Запрос на создание нового API‑ключа."""
    name: str = Field(..., description="Человекочитаемое название ключа")
    role: Literal["admin", "user"] = Field(..., description="Роль доступа")

class KeyUpdateRequest(BaseModel):
    """Запрос на обновление существующего ключа."""
    name: str | None = None
    role: Literal["admin", "user"] | None = None

def _mask_key(key: str) -> str:
    """Возвращает скрытую версию ключа, показывая только последние 4 символа."""
    return "*" * (len(key) - 4) + key[-4:]

def _load_keys_from_file() -> List[dict]:
    """Загружает ключи из gemini_keys.json: открыл -> прочитал -> закрыл."""
    try:
        from src.ai.gemini.gemini_api_key_state import _load_keys_file
        keys_data = _load_keys_file()
        result = []
        for name, data in keys_data.items():
            if isinstance(data, dict):
                result.append({
                    "id": name,
                    "name": name,
                    "role": "admin",
                    "key": data.get("value", ""),
                    "status": data.get("status", "active"),
                    "exhausted": data.get("status") == "exhausted" or bool(data.get("exhausted_at")),
                    "exhausted_at": data.get("exhausted_at", ""),
                    "last_run": data.get("last_run", ""),
                    "is_active": bool(data.get("is_active", False))
                })
        return result
    except Exception as e:
        logger.error(f"Ошибка загрузки ключей из файла: {e}")
        return []

def _check_exhaustion() -> None:
    """Поднимает ошибку, если достигнут лимит количества ключей."""
    if len(_FAKE_DB) >= _MAX_KEYS:
        raise HTTPException(status_code=400, detail="Достигнут лимит количества API‑ключей")

class KeyEntry(BaseModel):
    """Представление ключа в ответах API."""
    id: str
    name: str
    role: str
    masked_key: str
    status: str = "active"
    exhausted: bool = False
    exhausted_at: str = ""
    last_run: str = ""
    is_active: bool = False

@router.get("/", response_model=List[KeyEntry])
async def list_keys() -> List[KeyEntry]:
    from src.ai.gemini.gemini_api_key_state import get_active_key_name
    keys = _load_keys_from_file()
    active_key = get_active_key_name()
    return [KeyEntry(
        id=rec["id"],
        name=rec["name"],
        role=rec["role"],
        masked_key=_mask_key(rec["key"]),
        status=rec.get("status", "active"),
        exhausted=rec.get("exhausted", False),
        exhausted_at=rec.get("exhausted_at", ""),
        last_run=rec.get("last_run", ""),
        is_active=(rec["name"] == active_key or rec.get("is_active", False))
    ) for rec in keys]

@router.post("/", response_model=KeyEntry)
async def create_key(req: KeyCreateRequest) -> KeyEntry:
    try:
        from src.ai.gemini.gemini_api_key_state import save_api_key
        # Для создания ключа будем генерировать простой токен (в реальном приложении использовать безопасный генератор)
        import uuid
        key_value = f"GEMINI_{uuid.uuid4().hex}"
        success = save_api_key(req.name, key_value)
        if not success:
            raise HTTPException(status_code=400, detail="Не удалось сохранить ключ")
        return KeyEntry(
            id=req.name,
            name=req.name,
            role=req.role,
            masked_key=_mask_key(key_value),
            status="active"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания ключа: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания ключа: {str(e)}")

@router.put("/{key_name}", response_model=KeyEntry)
async def update_key(key_name: str, req: KeyUpdateRequest) -> KeyEntry:
    try:
        from src.ai.gemini.gemini_api_key_state import _load_keys_file, _save_keys_file, _sync_environment
        keys_data = _load_keys_file()
        
        if key_name not in keys_data:
            raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
        
        # Обновляем данные ключа
        keys_data[key_name]["status"] = keys_data[key_name].get("status", "active")
        if req.name is not None and req.name != key_name:
            # Renaming keys is not supported in gemini_api_key_state
            raise HTTPException(status_code=400, detail="Переименование ключей не поддерживается")
        
        # Сохраняем
        _save_keys_file(keys_data)
        _sync_environment(keys_data[key_name].get("value", ""))
        
        return KeyEntry(
            id=key_name,
            name=key_name,
            role="admin",
            masked_key=_mask_key(keys_data[key_name].get("value", "")),
            status=keys_data[key_name].get("status", "active")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления ключа '{key_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления ключа: {str(e)}")

@router.delete("/{key_name}")
async def delete_key(key_name: str) -> dict:
    try:
        from src.ai.gemini.gemini_api_key_state import delete_api_key
        success = delete_api_key(key_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления ключа '{key_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления ключа: {str(e)}")

@router.post("/reset-all", response_model=dict)
async def reset_all_keys_quota() -> dict:
    """Сбросить квоты для всех ключей."""
    try:
        reset_count = reset_all_quotas()
        return {"status": "success", "message": f"Квоты сброшены для {reset_count} ключей", "reset_count": reset_count}
    except Exception as e:
        logger.error(f"Ошибка сброса квот: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сброса квот: {str(e)}")

@router.post("/{key_name}/reset-quota", response_model=dict)
async def reset_key_quota(key_name: str) -> dict:
    """Сбросить квоту для конкретного ключа."""
    try:
        result = reset_quota(key_name)
        if result:
            return {"status": "success", "message": f"Квота для ключа '{key_name}' успешно сброшена"}
        else:
            raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сброса квоты для ключа '{key_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сброса квоты: {str(e)}")

@router.patch("/{key_name}", response_model=dict)
async def toggle_key_status(key_name: str, req: dict) -> dict:
    """Переключить статус ключа (active/disabled)."""
    try:
        from src.ai.gemini.gemini_api_key_state import _load_keys_file, _save_keys_file, _sync_environment
        keys_data = _load_keys_file()
        
        if key_name not in keys_data:
            raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
        
        new_status = req.get("status", "active")
        if new_status not in ["active", "disabled"]:
            raise HTTPException(status_code=400, detail="Недопустимый статус. Допустимые значения: active, disabled")
        
        # Обновляем статус
        keys_data[key_name]["status"] = new_status
        if new_status == "disabled":
            was_active = bool(keys_data[key_name].get("is_active"))
            keys_data[key_name]["is_active"] = False
            if was_active:
                new_active_val = ""
                for name, data in keys_data.items():
                    if data.get("status") == "active" and not data.get("exhausted_at") and (data.get("value") or data.get("api_key")):
                        data["is_active"] = True
                        new_active_val = str(data.get("value") or data.get("api_key"))
                        break
                if new_active_val:
                    _sync_environment(new_active_val)
                else:
                    import os
                    os.environ.pop("GEMINI_API_KEY", None)
        elif new_status == "active":
            if keys_data[key_name].get("exhausted_at"):
                keys_data[key_name]["exhausted_at"] = ""
            has_active = any(d.get("is_active") and d.get("status") == "active" and not d.get("exhausted_at") for d in keys_data.values())
            if not has_active:
                for name, data in keys_data.items():
                    data["is_active"] = (name == key_name)
                _sync_environment(str(keys_data[key_name].get("value") or keys_data[key_name].get("api_key") or ""))

        # Сохраняем
        _save_keys_file(keys_data)
        return {"status": "success", "message": f"Статус ключа '{key_name}' изменен на '{new_status}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка переключения статуса ключа '{key_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка переключения статуса: {str(e)}")

@router.post("/{key_name}/activate", response_model=dict)
@router.post("/{key_name}/set-active", response_model=dict)
async def activate_key(key_name: str) -> dict:
    """Назначить конкретный API-ключ активным по умолчанию."""
    try:
        from src.ai.gemini.gemini_api_key_state import set_active_key
        success = set_active_key(key_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден или пустой")
        return {"status": "success", "message": f"Ключ '{key_name}' назначен активным", "active_key": key_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка активации ключа '{key_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка активации ключа: {str(e)}")

class KeyTestPayload(BaseModel):
    """Параметры проверки валидности ключа."""
    model: str = Field(default="gemini-3.1-flash-lite", description="Имя модели для проверки")
    message: str = Field(default="hello world", description="Тестовое сообщение")


@router.post("/{key_name}/test", response_model=dict)
async def test_api_key(key_name: str, payload: KeyTestPayload = None) -> dict:
    """Проверка валидности конкретного API-ключа Gemini отправкой тестового запроса (hello world)."""
    import time
    from google import genai
    from src.ai.gemini.gemini_api_key_state import update_last_run, mark_exhausted, reset_quota, _load_keys_file

    target_model = payload.model if payload and payload.model else "gemini-3.1-flash-lite"
    test_msg = payload.message if payload and payload.message else "hello world"

    # Загружаем ключи
    all_keys = _load_keys_file()
    if key_name not in all_keys:
        raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")

    raw_key = all_keys[key_name].get("value") or all_keys[key_name].get("api_key") or ""

    if not raw_key:
        raise HTTPException(status_code=400, detail=f"Значение токена для ключа '{key_name}' пустое")

    masked = _mask_key(raw_key)
    start_t = time.perf_counter()

    try:
        client = genai.Client(api_key=raw_key)
        response = client.models.generate_content(
            model=target_model,
            contents=test_msg,
        )
        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)
        resp_text = response.text or ""

        # Успешный ответ — обновляем метки и сбрасываем бан квоты
        try:
            update_last_run(key_name)
            reset_quota(key_name)
        except Exception:
            pass

        return {
            "status": "success",
            "valid": True,
            "key_name": key_name,
            "masked_key": masked,
            "model": target_model,
            "message": test_msg,
            "response": resp_text,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)
        err_str = str(exc)
        logger.warning(f"[RouterKeys] Ошибка валидации ключа '{key_name}': {err_str}")

        if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
            try:
                mark_exhausted(key_name)
            except Exception:
                pass

        return {
            "status": "error",
            "valid": False,
            "key_name": key_name,
            "masked_key": masked,
            "model": target_model,
            "message": test_msg,
            "error": err_str,
            "duration_ms": duration_ms,
        }


# =============================================================================
# Google Antigravity (AGY) Key Pool Endpoints
# =============================================================================

_AGY_KEYS_FILE: Path = __root__ / "src" / "secrets" / "agy_keys.json"


class AGYKeyPoolManager:
    """Менеджер пула API-ключей Google Antigravity (AGY)."""

    def __init__(self, secrets_path: Path = _AGY_KEYS_FILE) -> None:
        self.secrets_path = secrets_path

    def _load(self) -> List[Dict[str, Any]]:
        """Загрузка ключей из файла agy_keys.json."""
        if not self.secrets_path.exists():
            return []
        try:
            with open(self.secrets_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                result = []
                for item in data:
                    if isinstance(item, dict):
                        result.append({
                            "name": item.get("name", ""),
                            "key": item.get("key") or item.get("value") or item.get("api_key") or "",
                            "status": item.get("status", "active"),
                            "is_active": bool(item.get("is_active", False)),
                            "exhausted": bool(item.get("exhausted", False) or item.get("status") == "exhausted" or item.get("exhausted_at")),
                            "exhausted_at": item.get("exhausted_at", ""),
                            "last_run": item.get("last_run", ""),
                        })
                return result
            elif isinstance(data, dict):
                result = []
                for name, d in data.items():
                    if isinstance(d, dict):
                        result.append({
                            "name": name,
                            "key": d.get("value") or d.get("key") or d.get("api_key") or "",
                            "status": d.get("status", "active"),
                            "is_active": bool(d.get("is_active", False)),
                            "exhausted": bool(d.get("exhausted", False) or d.get("status") == "exhausted" or d.get("exhausted_at")),
                            "exhausted_at": d.get("exhausted_at", ""),
                            "last_run": d.get("last_run", ""),
                        })
                    else:
                        result.append({
                            "name": name,
                            "key": str(d),
                            "status": "active",
                            "is_active": False,
                            "exhausted": False,
                            "exhausted_at": "",
                            "last_run": "",
                        })
                return result
        except Exception as e:
            logger.error(f"Ошибка чтения ключей AGY из {self.secrets_path}: {e}")
            return []
        return []

    def _save(self, keys: List[Dict[str, Any]]) -> bool:
        """Сохранение ключей в agy_keys.json в формате словаря, аналогичном gemini_keys.json."""
        try:
            self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Dict[str, Any]] = {}
            for item in keys:
                name = item.get("name", "").strip()
                if not name:
                    continue
                data[name] = {
                    "value": item.get("key") or item.get("value") or "",
                    "last_run": item.get("last_run", ""),
                    "status": "active" if item.get("status") == "OK" else item.get("status", "active"),
                    "exhausted_at": item.get("exhausted_at", ""),
                    "is_active": bool(item.get("is_active", False)),
                }
            with open(self.secrets_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения ключей AGY в {self.secrets_path}: {e}")
            return False

    def list_keys(self) -> List[Dict[str, Any]]:
        """Получить список ключей AGY с гарантией наличия активного ключа."""
        keys = self._load()
        has_active = any(k.get("is_active") and k.get("status") == "active" for k in keys)
        if not has_active and keys:
            for k in keys:
                if k.get("status") == "active":
                    k["is_active"] = True
                    self._save(keys)
                    break
        return keys

    def add_key(self, name: str, key: str, is_active: bool = False) -> Dict[str, Any]:
        """Добавить новый или обновить существующий ключ AGY."""
        keys = self._load()
        for item in keys:
            if item.get("name") == name:
                item["key"] = key
                item["status"] = "active"
                item["exhausted"] = False
                item["exhausted_at"] = ""
                if is_active:
                    for other in keys:
                        other["is_active"] = (other.get("name") == name)
                self._save(keys)
                return item

        new_entry = {
            "name": name,
            "key": key,
            "status": "active",
            "is_active": is_active or (len(keys) == 0),
            "exhausted": False,
            "exhausted_at": "",
            "last_run": "",
        }
        if is_active:
            for other in keys:
                other["is_active"] = False
        keys.append(new_entry)
        self._save(keys)
        return new_entry

    def remove_key(self, name: str) -> bool:
        """Удалить ключ AGY по имени."""
        keys = self._load()
        orig_len = len(keys)
        keys = [k for k in keys if k.get("name") != name]
        if len(keys) == orig_len:
            return False
        if not any(k.get("is_active") for k in keys) and keys:
            keys[0]["is_active"] = True
        self._save(keys)
        return True

    def reset_quotas(self) -> int:
        """Сбросить квоты всех ключей AGY."""
        keys = self._load()
        count = 0
        for k in keys:
            if k.get("exhausted") or k.get("status") == "exhausted" or k.get("exhausted_at"):
                count += 1
            k["status"] = "active"
            k["exhausted"] = False
            k["exhausted_at"] = ""
        self._save(keys)
        return count

    def reset_quota(self, name: str) -> bool:
        """Сбросить квоту для одного ключа AGY."""
        keys = self._load()
        found = False
        for k in keys:
            if k.get("name") == name:
                k["status"] = "active"
                k["exhausted"] = False
                k["exhausted_at"] = ""
                found = True
                break
        if found:
            self._save(keys)
        return found

    def toggle_status(self, name: str, new_status: str) -> bool:
        """Включить/выключить ключ AGY."""
        keys = self._load()
        found = False
        for k in keys:
            if k.get("name") == name:
                k["status"] = new_status
                if new_status == "disabled":
                    k["is_active"] = False
                found = True
                break
        if found:
            if not any(k.get("is_active") for k in keys if k.get("status") == "active"):
                for k in keys:
                    if k.get("status") == "active":
                        k["is_active"] = True
                        break
            self._save(keys)
        return found

    def set_active(self, name: str) -> bool:
        """Сделать ключ AGY активным."""
        keys = self._load()
        found = False
        for k in keys:
            if k.get("name") == name:
                k["is_active"] = True
                k["status"] = "active"
                found = True
            else:
                k["is_active"] = False
        if found:
            self._save(keys)
        return found


_agy_manager = AGYKeyPoolManager(secrets_path=_AGY_KEYS_FILE)


class AGYKeyPayload(BaseModel):
    """Модель полезной нагрузки добавления ключа AGY."""
    name: str = Field(..., description="Название ключа AGY")
    key: Optional[str] = Field(None, description="Значение API-ключа AGY")
    api_key: Optional[str] = Field(None, description="Псевдоним ключа AGY")
    value: Optional[str] = Field(None, description="Значение ключа AGY")
    is_active: Optional[bool] = Field(False, description="Флаг активности")


@router.get("/agy")
@router.get("/agy/")
async def list_agy_keys() -> List[KeyEntry]:
    """Возвращает пул ключей Google Antigravity (AGY)."""
    keys = _agy_manager.list_keys()
    result = []
    for k in keys:
        key_val = k.get("key", "")
        masked = _mask_key(key_val) if len(key_val) >= 4 else ("****" if key_val else "")
        status = k.get("status", "active")
        if status == "OK":
            status = "active"
        result.append(KeyEntry(
            id=k.get("name", "key"),
            name=k.get("name", "key"),
            role="admin",
            masked_key=masked,
            status=status,
            exhausted=bool(k.get("exhausted", False)),
            exhausted_at=k.get("exhausted_at", ""),
            last_run=k.get("last_run", ""),
            is_active=bool(k.get("is_active", False)),
        ))
    return result


@router.post("/agy")
@router.post("/agy/")
async def add_agy_key(payload: AGYKeyPayload) -> Dict[str, Any]:
    """Добавляет или обновляет ключ в пуле Google Antigravity (AGY)."""
    key_val = (payload.key or payload.api_key or payload.value or "").strip()
    if not key_val:
        raise HTTPException(status_code=400, detail="API-ключ AGY не может быть пустым")
    res = _agy_manager.add_key(payload.name.strip(), key_val, is_active=bool(payload.is_active))
    return {"status": "success", "entry": res}


@router.delete("/agy/{key_name}")
async def delete_agy_key(key_name: str) -> Dict[str, Any]:
    """Удаляет ключ из пула Google Antigravity (AGY)."""
    success = _agy_manager.remove_key(key_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
    return {"status": "success", "message": f"Ключ '{key_name}' удален"}


@router.post("/agy/reset")
@router.post("/agy/reset-all")
async def reset_agy_keys() -> Dict[str, Any]:
    """Сбрасывает квоты и статусы всех ключей AGY."""
    count = _agy_manager.reset_quotas()
    return {"status": "success", "message": f"Квоты сброшены для {count} ключей AGY", "reset_count": count}


@router.post("/agy/{key_name}/reset-quota")
async def reset_agy_key_quota(key_name: str) -> Dict[str, Any]:
    """Сбросить квоту для конкретного ключа AGY."""
    success = _agy_manager.reset_quota(key_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
    return {"status": "success", "message": f"Квота для ключа '{key_name}' успешно сброшена"}


@router.patch("/agy/{key_name}")
async def toggle_agy_key_status(key_name: str, req: Dict[str, Any]) -> Dict[str, Any]:
    """Переключить статус ключа AGY (active/disabled)."""
    new_status = req.get("status", "active")
    if new_status not in ["active", "disabled"]:
        raise HTTPException(status_code=400, detail="Недопустимый статус. Допустимые значения: active, disabled")
    success = _agy_manager.toggle_status(key_name, new_status)
    if not success:
        raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
    return {"status": "success", "message": f"Статус ключа AGY '{key_name}' изменен на '{new_status}'"}


@router.post("/agy/{key_name}/activate")
@router.post("/agy/{key_name}/set-active")
async def activate_agy_key(key_name: str) -> Dict[str, Any]:
    """Назначить конкретный API-ключ AGY активным."""
    success = _agy_manager.set_active(key_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Ключ '{key_name}' не найден")
    return {"status": "success", "message": f"Ключ AGY '{key_name}' назначен активным", "active_key": key_name}


@router.post("/agy/{key_name}/test")
async def test_agy_key_endpoint(key_name: str, payload: Optional[KeyTestPayload] = None) -> Dict[str, Any]:
    """Проверка валидности API-ключа AGY отправкой тестового запроса."""
    import time
    keys = _agy_manager.list_keys()
    match = next((k for k in keys if k.get("name") == key_name), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Ключ AGY '{key_name}' не найден")

    raw_key = match.get("key", "").strip()
    masked = _mask_key(raw_key) if len(raw_key) >= 4 else ("****" if raw_key else "")
    if not raw_key:
        raise HTTPException(status_code=400, detail=f"Значение токена для ключа '{key_name}' пустое")

    target_model = payload.model if payload and payload.model else "gemini-3.1-flash-lite"
    test_msg = payload.message if payload and payload.message else "hello world"
    start_t = time.perf_counter()

    try:
        from google import genai
        client = genai.Client(api_key=raw_key)
        response = client.models.generate_content(
            model=target_model,
            contents=test_msg,
        )
        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)
        resp_text = response.text or ""
        _agy_manager.reset_quota(key_name)
        return {
            "status": "success",
            "valid": True,
            "key_name": key_name,
            "masked_key": masked,
            "model": target_model,
            "message": test_msg,
            "response": resp_text,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)
        err_str = str(exc)
        logger.warning(f"[RouterKeys] Ошибка валидации ключа AGY '{key_name}': {err_str}")
        return {
            "status": "error",
            "valid": False,
            "key_name": key_name,
            "masked_key": masked,
            "model": target_model,
            "message": test_msg,
            "error": err_str,
            "duration_ms": duration_ms,
        }


def init_router() -> APIRouter:
    """Инициализация роутера ключей."""
    return router


__all__ = [
    "init_router",
    "router",
    "KeyCreateRequest",
    "KeyEntry",
    "KeyUpdateRequest",
    "KeyTestPayload",
    "AGYKeyPayload",
    "AGYKeyPoolManager",
    "_check_exhaustion",
    "_mask_key",
]
