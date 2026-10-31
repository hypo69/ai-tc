# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - WikiLLM Editor Router
# =============================================================================
# Description:
#   FastAPI роутер редактора Базы Знаний WikiLLM и параметров RAG-профилей точности.
#
# File: router_wikillm_editor.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:25:00
# =============================================================================

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, Field

try:
    from logger import logger
except ImportError:
    logger = logging.getLogger("wikillm_editor_router")

router = APIRouter(
    prefix="/api/v1/wikillm",
    tags=["WikiLLM Editor & KB Management"]
)

# ------------------------------------------------------------------------------
# Pydantic Schemas
# ------------------------------------------------------------------------------

class MariaDBSettingsSchema(BaseModel):
    """Схема конфигурации подключения к MariaDB."""
    connection_type: str = Field(default="direct", description="Метод подключения: direct или php_api")
    host: str = Field(default="srv1502.hstgr.io", description="Хост сервера MariaDB")
    port: int = Field(default=3306, description="Порт MariaDB")
    user: str = Field(default="u177424397_davidka", description="Имя пользователя")
    password: str = Field(default="@Davidka#1969", description="Пароль пользователя")
    database: str = Field(default="u177424397_comp_knowledge", description="Имя базы данных")
    ip_fallback: Optional[str] = Field(default="77.37.35.16", description="Резервный IP-адрес")
    connect_timeout: int = Field(default=10, description="Таймаут подключения (сек)")
    php_api_url: Optional[str] = Field(default="https://srv1502.hstgr.io/wikillm_hostinger.php", description="URL PHP API скрипта")
    php_api_key: Optional[str] = Field(default="", description="Ключ авторизации PHP API")


class DatabaseConfigSchema(BaseModel):
    """Схема общей конфигурации базы данных WikiLLM."""
    engine: str = Field(default="mariadb", description="Целевой движок: mariadb или sqlite")
    mariadb: MariaDBSettingsSchema = Field(default_factory=MariaDBSettingsSchema)
    sqlite_path: str = Field(default="data/windows_wikillm/knowledge.db", description="Путь к SQLite")


class DatabaseActionRequest(BaseModel):
    """Схема запроса действий с базой данных."""
    engine: Optional[str] = Field(default=None, description="Тип базы данных")
    connection_type: Optional[str] = Field(default=None, description="Метод: direct или php_api")
    host: Optional[str] = Field(default=None, description="Хост сервера MariaDB")
    port: Optional[int] = Field(default=None, description="Порт")
    user: Optional[str] = Field(default=None, description="Пользователь")
    password: Optional[str] = Field(default=None, description="Пароль")
    database: Optional[str] = Field(default=None, description="Имя базы данных")
    ip_fallback: Optional[str] = Field(default=None, description="Резервный IP")
    connect_timeout: Optional[int] = Field(default=None, description="Таймаут")
    sqlite_path: Optional[str] = Field(default=None, description="Путь к файлу SQLite")
    php_api_url: Optional[str] = Field(default=None, description="URL PHP API")
    php_api_key: Optional[str] = Field(default=None, description="Ключ PHP API")


class WikiEntitySchema(BaseModel):
    canonical_key: str = Field(..., description="Unique canonical key (e.g. win_event_4624)")
    title: str = Field(..., description="Display title of the knowledge entry")
    category: str = Field(default="general", description="Category classification")
    description: str = Field(default="", description="Detailed description / markdown content")
    claims: List[str] = Field(default_factory=list, description="Verified claims list")
    remediation: List[str] = Field(default_factory=list, description="Recommended remediation steps")
    is_verified: bool = Field(default=True, description="Verification status flag")

class WikiProfileSchema(BaseModel):
    profile_name: str = Field(..., description="Profile identifier: fast, balanced, precise, custom")
    top_k: int = Field(default=5, ge=1, le=50)
    fetch_k: int = Field(default=20, ge=1, le=200)
    score_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    reranker_enabled: bool = Field(default=True)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_context_tokens: int = Field(default=4096, ge=512, le=32768)
    grounding_required: bool = Field(default=True)

class WikiArticle(BaseModel):
    """Модель статьи базы знаний WikiLLM."""
    id: str = Field(..., description="Уникальный идентификатор статьи")
    process_name: str = Field(..., description="Имя процесса (например, msedge.exe)")
    title: str = Field(..., description="Заголовок инструкции / статьи")
    category: str = Field(
        ...,
        description="Категория процесса (browser, system_service, dev_tool, background_agent, user_app)",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Теги статьи (memory_leak, gpu_acceleration, high_cpu, untrusted_path и др.)",
    )
    content_pattern: str = Field(
        ...,
        description="Паттерн решения, диагностическая рекомендация или горячие клавиши",
    )

class WikiArticlesResponse(BaseModel):
    """Схема ответа со списком статей WikiLLM."""
    status: str = Field(default="success", description="Статус выполнения запроса")
    total: int = Field(..., description="Общее количество отфильтрованных статей")
    articles: List[WikiArticle] = Field(default_factory=list, description="Список статей")


class WikiSettingsSchema(BaseModel):
    """Схема параметров и системных настроек WikiLLM."""
    model_name: str = Field(default="gemini-3.1-flash-lite", description="Модель генерации")
    confidence_threshold: float = Field(default=0.85, description="Порог точности")
    db_path: str = Field(default="data/wikillm.db", description="Расположение базы данных WikiLLM")
    editor_enabled: bool = Field(default=True, description="Флаг активности редактора")
    auto_enrichment: bool = Field(default=True, description="Авто-обогащение неизвестных событий")
    temperature: float = Field(default=0.2, description="Температура генерации")
    max_context_tokens: int = Field(default=4096, description="Размер контекстного окна")
    auto_indexing: bool = Field(default=True, description="Автоматическая индексация статей")


# ------------------------------------------------------------------------------
# Helper for Database Bridge & Fallback Storage
# ------------------------------------------------------------------------------

_ENTITIES_FILE = Path("data/wikillm_entities.json")
_SETTINGS_FILE = Path("data/wikillm_settings.json")


def _load_fallback_entities() -> Dict[str, Dict[str, Any]]:
    if _ENTITIES_FILE.is_file():
        try:
            with open(_ENTITIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "win_event_4624": {
            "canonical_key": "win_event_4624",
            "title": "Успешный вход в систему (Event 4624)",
            "category": "security_audit",
            "description": "Событие успешного входа пользователя в систему. Фиксирует тип входа (Logon Type) и SID.",
            "claims": ["Вход выполнен успешно", "Фиксирует учетные данные субъекта"],
            "remediation": ["Проверить IP-адрес источника при сетевом входе", "Сверить рабочие часы"],
            "is_verified": True,
        }
    }


def _save_fallback_entities(entities: Dict[str, Dict[str, Any]]) -> None:
    _ENTITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_ENTITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)


def _load_settings_dict() -> Dict[str, Any]:
    if _SETTINGS_FILE.is_file():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    from roadmap.patches import WikiLLMSettingsService
    return WikiLLMSettingsService().get_settings()


def _save_settings_dict(data: Dict[str, Any]) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_db_adapter():
    """Import and return the global DatabaseAdapter instance."""
    try:
        from apps.windows.db.db_adapter import db_adapter
        return db_adapter
    except ImportError:
        logger.warning("[WARN] Using local JSON/SQLite fallback for WikiLLM Editor")
        return None


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# API Endpoints: Конфигурация и управление базой данных (MariaDB / SQLite)
# ------------------------------------------------------------------------------

@router.get("/db/config")
async def get_db_configuration() -> Dict[str, Any]:
    """Возвращает текущую конфигурацию базы данных (MariaDB / SQLite) с динамическим разрешением путей."""
    from apps.windows.db.paths import resolve_system_knowledge_db_path, get_dynamic_path_config
    dyn_cfg = get_dynamic_path_config()
    default_sq = dyn_cfg["template"]

    db = get_db_adapter()
    if not db:
        resolved_p = str(resolve_system_knowledge_db_path(default_sq))
        return {
            "engine": "sqlite",
            "mariadb": {
                "connection_type": "direct",
                "host": "srv1502.hstgr.io",
                "port": 3306,
                "database": "u177424397_comp_knowledge",
                "user": "u177424397_davidka",
                "php_api_url": "https://srv1502.hstgr.io/wikillm_hostinger.php",
                "php_api_key": ""
            },
            "sqlite": {"path": default_sq, "resolved_path": resolved_p}
        }

    mariadb_cfg = dict(db.config.get("mariadb", {}))
    mariadb_cfg.setdefault("connection_type", "direct")
    mariadb_cfg.setdefault("php_api_url", "https://srv1502.hstgr.io/wikillm_hostinger.php")
    mariadb_cfg.setdefault("php_api_key", "")

    sqlite_cfg = dict(db.config.get("sqlite", {"path": default_sq}))
    raw_p = sqlite_cfg.get("path") or default_sq
    resolved_p = str(resolve_system_knowledge_db_path(raw_p))
    sqlite_cfg["path"] = raw_p
    sqlite_cfg["resolved_path"] = resolved_p

    return {
        "engine": db.engine,
        "mariadb": mariadb_cfg,
        "sqlite": sqlite_cfg,
        "dynamic_paths": dyn_cfg,
    }


@router.post("/db/config")
async def save_db_configuration(req: DatabaseConfigSchema) -> Dict[str, Any]:
    """Сохраняет конфигурацию подключения к базе данных и переподключает адаптер."""
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=500, detail="Адаптер базы данных недоступен")

    new_cfg = {
        "engine": req.engine,
        "sqlite": {"path": req.sqlite_path},
        "mariadb": req.mariadb.model_dump(),
    }
    db.update_config(new_cfg, save_to_disk=True)

    # Синхронизация с системными файлами config.json
    cfg_paths = [Path("apps/windows/api/config.json"), Path("config.json")]
    for p in cfg_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    c = json.load(f)
                if "paths" not in c or not isinstance(c["paths"], dict):
                    c["paths"] = {}
                c["paths"]["system_knowledge_db"] = req.sqlite_path
                if "database" not in c:
                    c["database"] = {}
                if "sqlite" not in c["database"]:
                    c["database"]["sqlite"] = {}
                c["database"]["sqlite"]["path"] = req.sqlite_path
                if "wikillm" in c and isinstance(c["wikillm"], dict):
                    c["wikillm"]["db_path"] = req.sqlite_path
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False, indent=2)
                    f.write("\n")
            except Exception as ex:
                logger.warning(f"[RouterWikiLLMEditor] Ошибка записи config {p}: {ex}")

    return {"status": "success", "ok": True, "message": "Конфигурация базы данных успешно сохранена", "config": new_cfg}


def _extract_mariadb_cfg(db: Any, req: Optional[DatabaseActionRequest]) -> Optional[Dict[str, Any]]:
    """Извлекает и мерджит кастомные параметры подключения MariaDB/PHP API/SQLite."""
    if not req:
        return None
    base = dict(db.config.get("mariadb", {}))
    if req.engine is not None:
        base["engine"] = req.engine
        if req.engine.lower() == "sqlite" and req.connection_type is None:
            base["connection_type"] = "sqlite"
    if req.sqlite_path is not None:
        base["sqlite_path"] = req.sqlite_path
    if req.connection_type is not None:
        base["connection_type"] = req.connection_type
        if req.connection_type.lower() == "sqlite" and req.engine is None:
            base["engine"] = "sqlite"
        elif req.connection_type.lower() in ("direct", "php_api") and req.engine is None:
            base["engine"] = "mariadb"
    if req.host is not None: base["host"] = req.host
    if req.port is not None: base["port"] = req.port
    if req.user is not None: base["user"] = req.user
    if req.password is not None: base["password"] = req.password
    if req.database is not None: base["database"] = req.database
    if req.ip_fallback is not None: base["ip_fallback"] = req.ip_fallback
    if req.connect_timeout is not None: base["connect_timeout"] = req.connect_timeout
    if req.php_api_url is not None: base["php_api_url"] = req.php_api_url
    if req.php_api_key is not None: base["php_api_key"] = req.php_api_key
    return base


@router.post("/db/check")
async def check_db_connection(req: Optional[DatabaseActionRequest] = None) -> Dict[str, Any]:
    """Проверяет подключение к серверу MariaDB (напрямую или через PHP API), наличие базы данных и таблиц."""
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=500, detail="Адаптер базы данных недоступен")

    custom_cfg = _extract_mariadb_cfg(db, req)
    return db.check_connection(custom_cfg)


@router.post("/db/create-database")
async def create_mariadb_database(req: Optional[DatabaseActionRequest] = None) -> Dict[str, Any]:
    """Создает базу данных на сервере MariaDB (напрямую или через PHP API)."""
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=500, detail="Адаптер базы данных недоступен")

    custom_cfg = _extract_mariadb_cfg(db, req)
    return db.create_database(custom_cfg)


@router.post("/db/init-tables")
async def init_mariadb_tables(req: Optional[DatabaseActionRequest] = None) -> Dict[str, Any]:
    """Создает пустые таблицы WikiLLM в MariaDB (напрямую или через PHP API)."""
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=500, detail="Адаптер базы данных недоступен")

    custom_cfg = _extract_mariadb_cfg(db, req)
    return db.init_empty_tables(custom_cfg)


@router.post("/db/import-sqlite")
async def import_data_from_sqlite(req: Optional[DatabaseActionRequest] = None) -> Dict[str, Any]:
    """Импортирует знания, сущности и инструменты из локальной базы SQLite в MariaDB (напрямую или через PHP API)."""
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=500, detail="Адаптер базы данных недоступен")

    sqlite_path = req.sqlite_path if req and req.sqlite_path else None
    custom_cfg = _extract_mariadb_cfg(db, req)
    return db.import_from_sqlite(sqlite_path=sqlite_path, cfg=custom_cfg)


# ------------------------------------------------------------------------------
# API Endpoints: Параметры WikiLLM
# ------------------------------------------------------------------------------

@router.get("/settings", response_model=WikiSettingsSchema)
async def get_wikillm_settings() -> WikiSettingsSchema:
    """Возвращает текущие параметры генерации и базы данных WikiLLM."""
    return WikiSettingsSchema(**_load_settings_dict())


@router.post("/settings", response_model=WikiSettingsSchema)
async def save_wikillm_settings(payload: WikiSettingsSchema) -> WikiSettingsSchema:
    """Сохраняет параметры генерации и базы данных WikiLLM."""
    d = payload.dict()
    _save_settings_dict(d)
    return payload


@router.get("/entities", response_model=List[WikiEntitySchema])
async def list_wiki_entities(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Search and retrieve WikiLLM knowledge entities from MariaDB/SQLite/JSON.
    """
    q_str = str(q) if isinstance(q, str) else None
    cat_str = str(category) if isinstance(category, str) else None
    limit_num = 50
    if isinstance(limit, int):
        limit_num = limit
    elif hasattr(limit, "default") and isinstance(limit.default, int):
        limit_num = limit.default
    elif limit is not None:
        try:
            limit_num = int(limit)
        except Exception:
            limit_num = 50

    db = get_db_adapter()
    if not db:
        items = list(_load_fallback_entities().values())
        if q_str:
            q_lower = q_str.lower()
            items = [i for i in items if q_lower in i.get("title", "").lower() or q_lower in i.get("canonical_key", "").lower()]
        if cat_str:
            items = [i for i in items if i.get("category") == cat_str]
        return [WikiEntitySchema(**i) for i in items[:limit_num]]

    try:
        sql = "SELECT canonical_key, title, category, description, is_verified, claims_json, remediation_json FROM wikillm_knowledge WHERE 1=1"
        params = {}

        if q_str:
            sql += " AND (title LIKE :q OR canonical_key LIKE :q OR description LIKE :q)"
            params['q'] = f"%{q_str}%"
        if cat_str:
            sql += " AND category = :cat"
            params['cat'] = cat_str

        sql += f" ORDER BY updated_at DESC LIMIT {limit_num}"

        rows = db.fetch_all(sql, params)
        result = []
        for r in rows:
            result.append(WikiEntitySchema(
                canonical_key=r['canonical_key'],
                title=r['title'],
                category=r.get('category', 'general'),
                description=r.get('description', ''),
                claims=json.loads(r['claims_json']) if r.get('claims_json') else [],
                remediation=json.loads(r['remediation_json']) if r.get('remediation_json') else [],
                is_verified=bool(r.get('is_verified', 1))
            ))
        return result
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch WikiLLM entities: {e}")
        items = list(_load_fallback_entities().values())
        return [WikiEntitySchema(**i) for i in items[:limit_num]]


@router.get("/entities/{canonical_key}", response_model=WikiEntitySchema)
async def get_wiki_entity(canonical_key: str):
    """
    Get a single WikiLLM knowledge entity by canonical key.
    """
    db = get_db_adapter()
    if not db:
        entities = _load_fallback_entities()
        if canonical_key not in entities:
            raise HTTPException(status_code=404, detail=f"Entity '{canonical_key}' not found")
        return WikiEntitySchema(**entities[canonical_key])

    try:
        sql = "SELECT canonical_key, title, category, description, is_verified, claims_json, remediation_json FROM wikillm_knowledge WHERE canonical_key = :key LIMIT 1"
        row = db.fetch_one(sql, {'key': canonical_key})

        if not row:
            raise HTTPException(status_code=404, detail=f"Entity '{canonical_key}' not found")

        return WikiEntitySchema(
            canonical_key=row['canonical_key'],
            title=row['title'],
            category=row.get('category', 'general'),
            description=row.get('description', ''),
            claims=json.loads(row['claims_json']) if row.get('claims_json') else [],
            remediation=json.loads(row['remediation_json']) if row.get('remediation_json') else [],
            is_verified=bool(row.get('is_verified', 1))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[WARN] DB query failed, using fallback: {e}")
        entities = _load_fallback_entities()
        if canonical_key not in entities:
            raise HTTPException(status_code=404, detail=f"Entity '{canonical_key}' not found")
        return WikiEntitySchema(**entities[canonical_key])


@router.post("/entities", status_code=status.HTTP_201_CREATED)
async def upsert_wiki_entity(entity: WikiEntitySchema):
    """
    Create or update a WikiLLM knowledge entity record.
    """
    db = get_db_adapter()
    if not db:
        entities = _load_fallback_entities()
        entities[entity.canonical_key] = entity.dict()
        _save_fallback_entities(entities)
        return {"status": "success", "canonical_key": entity.canonical_key, "message": "Entity saved successfully"}

    import time
    sql = """
    INSERT INTO wikillm_knowledge 
        (canonical_key, title, category, description, is_verified, claims_json, remediation_json, updated_at)
    VALUES 
        (:key, :title, :category, :description, :verified, :claims, :remediation, :updated)
    ON DUPLICATE KEY UPDATE 
        title = :title, 
        category = :category, 
        description = :description, 
        is_verified = :verified, 
        claims_json = :claims, 
        remediation_json = :remediation, 
        updated_at = :updated
    """
    params = {
        'key': entity.canonical_key,
        'title': entity.title,
        'category': entity.category,
        'description': entity.description,
        'verified': 1 if entity.is_verified else 0,
        'claims': json.dumps(entity.claims, ensure_ascii=False),
        'remediation': json.dumps(entity.remediation, ensure_ascii=False),
        'updated': time.time()
    }

    try:
        db.execute(sql, params)
        return {"status": "success", "canonical_key": entity.canonical_key, "message": "Entity saved successfully"}
    except Exception as e:
        logger.warning(f"[WARN] Failed to save in DB, saving to fallback: {e}")
        entities = _load_fallback_entities()
        entities[entity.canonical_key] = entity.dict()
        _save_fallback_entities(entities)
        return {"status": "success", "canonical_key": entity.canonical_key, "message": "Entity saved successfully"}


@router.delete("/entities/{canonical_key}")
async def delete_wiki_entity(canonical_key: str):
    """
    Delete a WikiLLM knowledge entity by canonical key.
    """
    db = get_db_adapter()
    if not db:
        entities = _load_fallback_entities()
        if canonical_key not in entities:
            raise HTTPException(status_code=404, detail=f"Entity '{canonical_key}' not found")
        del entities[canonical_key]
        _save_fallback_entities(entities)
        return {"status": "success", "message": f"Entity '{canonical_key}' deleted"}

    sql = "DELETE FROM wikillm_knowledge WHERE canonical_key = :key"
    try:
        rows = db.execute(sql, {'key': canonical_key})
        if rows == 0:
            raise HTTPException(status_code=404, detail=f"Entity '{canonical_key}' not found")
        return {"status": "success", "message": f"Entity '{canonical_key}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[WARN] Failed to delete in DB: {e}")
        entities = _load_fallback_entities()
        if canonical_key in entities:
            del entities[canonical_key]
            _save_fallback_entities(entities)
            return {"status": "success", "message": f"Entity '{canonical_key}' deleted"}
        raise HTTPException(status_code=500, detail=str(e))


DEFAULT_PROFILES = [
    WikiProfileSchema(profile_name="fast", top_k=3, fetch_k=10, score_threshold=0.60, reranker_enabled=False, rerank_top_n=3, temperature=0.1, max_context_tokens=2048, grounding_required=False),
    WikiProfileSchema(profile_name="balanced", top_k=5, fetch_k=20, score_threshold=0.70, reranker_enabled=True, rerank_top_n=5, temperature=0.2, max_context_tokens=4096, grounding_required=True),
    WikiProfileSchema(profile_name="precise", top_k=8, fetch_k=30, score_threshold=0.85, reranker_enabled=True, rerank_top_n=5, temperature=0.0, max_context_tokens=8192, grounding_required=True),
]


@router.get("/profiles", response_model=List[WikiProfileSchema])
async def get_wiki_profiles():
    """
    Get all WikiLLM accuracy tuning profiles (fast, balanced, precise).
    """
    db = get_db_adapter()
    if not db:
        return DEFAULT_PROFILES

    sql = "SELECT * FROM wiki_llm_profiles ORDER BY profile_name"
    try:
        rows = db.fetch_all(sql)
        if rows:
            return [WikiProfileSchema(**r) for r in rows]
        return DEFAULT_PROFILES
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch profiles: {e}")
        return DEFAULT_PROFILES


@router.post("/profiles")
async def save_wiki_profile(profile: WikiProfileSchema):
    """
    Save or update WikiLLM accuracy tuning profile.
    """
    db = get_db_adapter()
    if not db:
        raise HTTPException(status_code=503, detail="Database adapter unavailable")

    import time
    sql = """
    INSERT INTO wiki_llm_profiles 
        (profile_name, top_k, fetch_k, score_threshold, reranker_enabled, rerank_top_n, temperature, max_context_tokens, grounding_required, updated_at)
    VALUES 
        (:profile_name, :top_k, :fetch_k, :score_threshold, :reranker_enabled, :rerank_top_n, :temperature, :max_context_tokens, :grounding_required, :ts)
    ON DUPLICATE KEY UPDATE 
        top_k = :top_k, fetch_k = :fetch_k, score_threshold = :score_threshold,
        reranker_enabled = :reranker_enabled, rerank_top_n = :rerank_top_n,
        temperature = :temperature, max_context_tokens = :max_context_tokens,
        grounding_required = :grounding_required, updated_at = :ts
    """
    params = profile.dict()
    params['reranker_enabled'] = 1 if profile.reranker_enabled else 0
    params['grounding_required'] = 1 if profile.grounding_required else 0
    params['ts'] = time.time()

    try:
        db.execute(sql, params)
        return {"status": "success", "profile": profile.profile_name, "message": "Profile updated successfully"}
    except Exception as e:
        logger.error(f"[ERROR] Failed to save profile {profile.profile_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/articles", response_model=WikiArticlesResponse)
async def get_wikillm_articles(
    category: Optional[str] = Query(None, description="Фильтр по категории процесса"),
    tag: Optional[str] = Query(None, description="Фильтр по тегу"),
    search_query: Optional[str] = Query(None, description="Поисковый запрос"),
) -> WikiArticlesResponse:
    """Возвращает список статей WikiLLM с учётом категорий, тегов и поиска (Задача №33).

    Args:
        category: Категория процесса (browser, system_service, dev_tool, background_agent, user_app).
        tag: Популярный тег (memory_leak, gpu_acceleration, high_cpu, untrusted_path).
        search_query: Подстрока поиска в заголовке, имени процесса или паттерне.

    Returns:
        Объект WikiArticlesResponse со списком статей и общим количеством.
    """
    logger.debug(
        f"[WikiLLM Articles] Запрос статей: category='{category}', tag='{tag}', search_query='{search_query}'"
    )

    from roadmap.code_fixes.patch_31_wikillm_ui_category_filter import (
        DEFAULT_ARTICLES,
        filter_articles,
    )

    filtered = filter_articles(
        DEFAULT_ARTICLES,
        category=category,
        tag=tag,
        search_query=search_query,
    )

    return WikiArticlesResponse(
        status="success",
        total=len(filtered),
        articles=[WikiArticle(**a) for a in filtered],
    )


def init_router() -> APIRouter:
    """Возвращает сконфигурированный экземпляр APIRouter для WikiLLM Editor & Articles."""
    return router


