# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Server & Router Auto-Discovery
# =============================================================================
# Description:
#   Слой 7: FastAPI сервер и механизм динамического Auto-Discovery роутеров.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.server import create_app, discover_and_register_routers
#
# File: server.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:28:00
# =============================================================================

from __future__ import annotations
"""FastAPI серверная фабрика и автоматическое обнаружение REST API роутеров."""

import importlib
import json
import os
import pkgutil
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from logger import clear_trace_context, logger, set_trace_context
from apps.common.webgui import SmartMultiDirStaticFiles, COMMON_WEBGUI_DIR
from apps.windows.api.config_helper import save_ai_config, resolve_active_config_path
from src.utils.system_engineering import (
    IdempotencyStore,
    REDMetricsCollector,
    format_traceparent,
    generate_span_id,
    parse_traceparent,
)

# Пути к статике и конфигурации
_MODULE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _MODULE_DIR / "config.json"
_WEBGUI_DIR = _MODULE_DIR / "webgui"
_TC_INDEX = _WEBGUI_DIR / "apps" / "index.html"
_PROJECT_ROOT = _MODULE_DIR.parents[2]
_COMMON_WEBGUI_DIR = COMMON_WEBGUI_DIR


def load_config() -> Dict[str, Any]:
    """Загружает конфигурацию сервиса из config.json."""
    if _CONFIG_PATH.is_file():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"[API Server] Ошибка чтения конфигурации {_CONFIG_PATH}: {exc}")
    return {}


def load_tc_config(profile: Optional[str] = None) -> Dict[str, Any]:
    """Загрузка конфигурации для Test Computer / Windows App.

    Args:
        profile: Имя профиля конфигурации (например tc, su).

    Returns:
        Dict[str, Any]: Словарь с параметрами конфигурации.
    """
    candidates: List[Path] = []

    env_cfg = os.getenv("AIWINDOWSADMIN_CONFIG") or os.getenv("CONFIG_FILE")
    if env_cfg:
        p = Path(env_cfg)
        candidates.append(p if p.is_absolute() else _PROJECT_ROOT / p)

    candidates.extend([
        _PROJECT_ROOT / "config_tc.json",
        _MODULE_DIR.parent / "config.json",
        _CONFIG_PATH,
        _PROJECT_ROOT / "config.json",
    ])

    for cand in candidates:
        if cand.exists() and cand.is_file():
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as exc:
                logger.warning(f"[API Server] Ошибка чтения конфигурации {cand}: {exc}")

    return {}


def safe_include_router(app: FastAPI, router: APIRouter) -> bool:
    """Безопасно регистрирует роутер, предотвращая дублирование одинаковых маршрутов (метод, путь).

    Args:
        app: Экземпляр FastAPI приложения.
        router: APIRouter для подключения.

    Returns:
        bool: True, если роутер был успешно подключен, False если все маршруты уже присутствуют.
    """
    if not hasattr(app.state, "registered_route_keys"):
        app.state.registered_route_keys = set()
    app_registered: set[tuple[str, str]] = app.state.registered_route_keys

    router_keys: list[tuple[str, str]] = []
    has_new_routes = False

    for route in router.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = getattr(route, "methods", None) or {"*"}
        for m in methods:
            key = (m.upper(), path)
            router_keys.append(key)
            if key not in app_registered:
                has_new_routes = True

    # Если роутер пустой или все его маршруты уже зарегистрированы в приложении
    if not has_new_routes and router_keys:
        return False

    app.include_router(router)
    for key in router_keys:
        app_registered.add(key)
    return True


def discover_and_register_routers(
    app: FastAPI,
    package_path: str = "apps.windows",
    exclude_modules: Optional[set[str]] = None,
) -> int:
    """Динамическое сканирование и подсоединение дополнительных REST API роутеров.

    Args:
        app: Экземпляр FastAPI приложения.
        package_path: Базовый пакет для поиска роутеров.
        exclude_modules: Опциональный набор модулей, которые уже зарегистрированы.

    Returns:
        int: Количество успешно обнаруженных и зарегистрированных новых роутеров.
    """
    excluded = set(exclude_modules or ())
    try:
        package = importlib.import_module(package_path)
    except Exception as err:
        logger.error(f"[AutoDiscovery] Не удалось импортировать базовый пакет {package_path}: {err}")
        return 0

    if not hasattr(package, "__path__"):
        return 0

    registered_count = 0
    for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if not (
            module_name.endswith(".router")
            or "routers.router_" in module_name
            or module_name.endswith(".router_capabilities")
            or module_name.endswith(".system_inspector_router")
            or module_name.endswith(".router_process_activity")
        ):
            continue

        # Пропуск, если модуль уже зарегистрирован напрямую или через псевдоним
        if module_name in excluded:
            continue
        alt_module = (
            module_name.replace("apps.windows.sdk.modules.", "apps.windows.")
            if "apps.windows.sdk.modules." in module_name
            else module_name.replace("apps.windows.", "apps.windows.sdk.modules.")
        )
        if alt_module in excluded:
            continue

        try:
            mod = importlib.import_module(module_name)
            router = getattr(mod, "router", None)
            if router is None and hasattr(mod, "init_router"):
                try:
                    router = mod.init_router()
                except Exception:
                    pass
            if isinstance(router, APIRouter):
                if safe_include_router(app, router):
                    excluded.add(module_name)
                    excluded.add(alt_module)
                    registered_count += 1
                    logger.console(f"[AutoDiscovery] Зарегистрирован дополнительный роутер: {module_name}", text_color="gray")
        except Exception as router_err:
            logger.warning(f"[AutoDiscovery] Пропуск роутера {module_name} из-за ошибки: {router_err}")

    return registered_count


def create_app() -> FastAPI:
    """Создаёт и конфигурирует масштабируемый FastAPI-сервис Windows API с Auto-Discovery."""
    config = load_config()
    server_cfg = config.get("server", {})

    app = FastAPI(
        title=server_cfg.get("title", "AI-Windows-Admin Windows Internal API"),
        description=server_cfg.get("description", "Сервис TC/Windows: телеметрия, дашборды, диагностика."),
        version="2.0.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1",
            "https://127.0.0.1",
            "http://localhost",
            "https://localhost",
        ],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SRE Observability (W3C TraceContext, RED p50/p95/p99) и Idempotency-Key Middleware
    red_metrics = REDMetricsCollector(max_samples=2000)
    idempotency_store = IdempotencyStore(max_keys=2048, ttl_seconds=3600.0)
    app.state.red_metrics = red_metrics
    app.state.idempotency_store = idempotency_store

    @app.middleware("http")
    async def sre_observability_and_idempotency_middleware(request: Request, call_next: Any) -> Response:
        """Обеспечивает сквозной TraceID (W3C traceparent), защиту Idempotency-Key и сбор перцентилей RED."""
        raw_tp = request.headers.get("traceparent", "")
        raw_x_trace = request.headers.get("X-Trace-Id", "").strip()
        if raw_tp:
            trace_id, span_id = parse_traceparent(raw_tp)
        elif len(raw_x_trace) == 32:
            trace_id, span_id = raw_x_trace.lower(), generate_span_id()
        else:
            trace_id, span_id = parse_traceparent("")

        traceparent_hdr = format_traceparent(trace_id, span_id)
        set_trace_context(trace_id=trace_id, service_name="windows-internal-api")
        request.state.trace_id = trace_id

        start_t = time.perf_counter()
        idem_key = request.headers.get("Idempotency-Key", "").strip()
        is_mutating = request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")

        if is_mutating and idem_key:
            scoped_key = f"{request.method.upper()}:{request.url.path}:{idem_key}"
            state_flag, record = idempotency_store.begin(scoped_key)
            if state_flag == "IN_PROGRESS":
                red_metrics.record((time.perf_counter() - start_t) * 1000.0, is_error=False)
                clear_trace_context()
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "error",
                        "code": "IDEMPOTENCY_CONFLICT",
                        "message": "Операция с данным Idempotency-Key уже выполняется параллельно.",
                        "trace_id": trace_id,
                    },
                    headers={"X-Trace-Id": trace_id, "traceparent": traceparent_hdr},
                )
            if state_flag == "COMPLETED":
                red_metrics.record((time.perf_counter() - start_t) * 1000.0, is_error=False)
                clear_trace_context()
                return Response(
                    content=record.response_body,
                    status_code=record.status_code,
                    media_type="application/json",
                    headers={
                        "X-Trace-Id": trace_id,
                        "traceparent": traceparent_hdr,
                        "X-Idempotent-Replayed": "true",
                    },
                )

        try:
            response: Response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            red_metrics.record(elapsed_ms, is_error=(response.status_code >= 500))

            if is_mutating and idem_key:
                scoped_key = f"{request.method.upper()}:{request.url.path}:{idem_key}"
                if 200 <= response.status_code < 500:
                    body_chunks = [chunk async for chunk in response.body_iterator]
                    raw_body = b"".join(body_chunks)
                    idempotency_store.complete(
                        scoped_key,
                        status_code=response.status_code,
                        response_body=raw_body.decode("utf-8", errors="replace"),
                    )
                    response = Response(
                        content=raw_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                else:
                    idempotency_store.abort(scoped_key)

            response.headers["X-Trace-Id"] = trace_id
            response.headers["traceparent"] = traceparent_hdr
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            red_metrics.record(elapsed_ms, is_error=True)
            if is_mutating and idem_key:
                idempotency_store.abort(f"{request.method.upper()}:{request.url.path}:{idem_key}")
            raise
        finally:
            clear_trace_context()

    # 1. Сначала регистрируем явно сконфигурированные роутеры из config.json (для кастомных параметров)
    routers_list: List[Dict[str, Any]] = config.get("routers", [])
    registered_modules = set()
    
    # Создаем экземпляры моделей один раз для всех роутеров, которым они нужны
    chat_model: Optional[Any] = None
    narrator_model: Optional[Any] = None
    
    try:
        from src.ai.orchestration.unified_chat import UnifiedChatModel
        tc_cfg = load_tc_config()
        ai_cfg_sec = tc_cfg.get("ai_providers_and_models_configuration") or tc_cfg.get("ai") or {}
        default_provider = ai_cfg_sec.get("default_provider", "")
        default_model = ai_cfg_sec.get("default_model", "")
        if not default_provider:
            default_provider = "gemini"
        if not default_model:
            providers = ai_cfg_sec.get("providers", {})
            if isinstance(providers, dict) and default_provider in providers:
                default_model = providers[default_provider].get("default_model") or providers[default_provider].get("model", "")
        if not default_model:
            default_model = "gemini-3.1-flash-lite"

        chat_model = UnifiedChatModel(provider=default_provider, model=default_model)
        if ai_cfg_sec.get("enable_narrator", False):
            narrator_model = UnifiedChatModel(provider=default_provider, model=default_model)
        else:
            narrator_model = None
    except Exception as model_err:
        logger.warning(f"[API Server] Не удалось инициализировать модели: {model_err}")
    
    for entry in routers_list:
        if not entry.get("enabled", True):
            continue
        module_path = entry.get("module")
        if not module_path:
            continue
        factory_name = entry.get("factory", "init_router")
        kwargs = dict(entry.get("kwargs") or {})
        if entry.get("inject_app"):
            kwargs["app"] = app
            kwargs.setdefault("state", None)
        if entry.get("inject_models"):
            kwargs["chat_model"] = chat_model
            kwargs["narrator_model"] = narrator_model

        try:
            mod = importlib.import_module(module_path)
            factory = getattr(mod, factory_name, None)
            if factory and callable(factory):
                router = factory(**kwargs)
            else:
                router = getattr(mod, "router", None)
            if isinstance(router, APIRouter):
                safe_include_router(app, router)
                legacy_r = getattr(mod, "legacy_router", None)
                if isinstance(legacy_r, APIRouter):
                    safe_include_router(app, legacy_r)
                registered_modules.add(module_path)
                if module_path.startswith("apps.windows.sdk.modules."):
                    registered_modules.add(module_path.replace("apps.windows.sdk.modules.", "apps.windows."))
                elif module_path.startswith("apps.windows.") and ".sdk.modules." not in module_path:
                    sub = module_path[len("apps.windows."):]
                    registered_modules.add(f"apps.windows.sdk.modules.{sub}")
        except Exception as exc:
            logger.warning(f"[API Server] Ошибка регистрации роутера {module_path}: {exc}")

    # 2. Затем выполняем динамическое обнаружение (Auto-Discovery) только для новых модулей, не вошедших в config.json
    discover_and_register_routers(app, "apps.windows", exclude_modules=registered_modules)

    # -------------------------------------------------------------------------
    # Роутеры экосистемы ИИ и администрирования (/api/skills, /api/plugins, /api/mcp, /api/admin, /api/v1/admin)
    # -------------------------------------------------------------------------
    try:
        from apps.windows.api.routers.admin.routers import (
            router as admin_router,
            router_v1 as admin_v1_router,
            skills_router,
            plugins_router,
            router_apps,
        )
        for admin_r in (admin_router, admin_v1_router, skills_router, plugins_router, router_apps):
            safe_include_router(app, admin_r)

        from apps.windows.api.routers.admin.mcp import admin_mcp_router, mcp_router
        safe_include_router(app, admin_mcp_router)
        safe_include_router(app, mcp_router)
        logger.info("[Bridge] Роутеры экосистемы ИИ (skills, plugins, mcp, admin) успешно подключены")
    except Exception as exc:
        logger.warning(f"[Bridge] Ошибка подключения роутеров экосистемы ИИ: {exc}")

    # -------------------------------------------------------------------------
    # Роутер Unified RAG (/api/rag/*)
    # -------------------------------------------------------------------------
    try:
        from src.ai.rag.router import init_router as init_rag_router
        safe_include_router(app, init_rag_router())
        logger.info("[Bridge] Роутер Unified RAG (/api/rag/*) успешно подключен")
    except Exception as exc:
        logger.warning(f"[Bridge] Ошибка подключения роутера Unified RAG: {exc}")

    # -------------------------------------------------------------------------
    # Системные и UI точки входа
    # -------------------------------------------------------------------------
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        """Отдача иконки favicon.ico."""
        fav_candidates = [
            _WEBGUI_DIR / "favicon.ico",
            _WEBGUI_DIR / "assets" / "favicon.ico",
        ]
        for fav in fav_candidates:
            if fav.exists() and fav.is_file():
                return FileResponse(fav)
        return Response(status_code=204)

    # TC UI точка входа
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/tc", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/tc/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/apps", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/apps/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/su", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/su/", response_class=HTMLResponse, include_in_schema=False)
    async def tc_index() -> Response:
        """Возвращает главную HTML-страницу Test Computer интерфейса."""
        if _TC_INDEX.exists():
            return FileResponse(
                _TC_INDEX,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        return HTMLResponse("<h1>TC WebGUI (apps/index.html) not found</h1>", status_code=404)

    @app.get("/api/v1/bridge/status", tags=["bridge"])
    @app.get("/api/bridge/status", tags=["bridge"])
    async def get_bridge_status() -> Dict[str, Any]:
        """Возвращает статус веб-интерфейса Windows API."""
        return {
            "status": "ok",
            "service": "ai-windows-admin-bridge",
            "apps": {
                "windows": {
                    "name": "AI Windows Admin (TC)",
                    "url": "/tc",
                    "webgui_exists": _TC_INDEX.exists(),
                },
            },
        }

    # Health-check и SRE метрики RED (Rate, Errors, Duration p50/p95/p99)
    @app.get("/health", tags=["system"])
    @app.get("/internal/health", tags=["system"], include_in_schema=False)
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "windows-internal-api",
            "webgui_dir": str(_WEBGUI_DIR),
            "webgui_exists": _WEBGUI_DIR.exists(),
            "tc_index_exists": _TC_INDEX.exists(),
            "configured_routers_count": len(routers_list),
            "observability": red_metrics.snapshot(),
        }

    @app.get("/api/v1/observability/metrics", tags=["system"])
    @app.get("/api/observability/metrics", tags=["system"])
    async def get_observability_metrics() -> Dict[str, Any]:
        """Возвращает метрики Google SRE RED (Rate, Errors, Duration по перцентилям p50/p95/p99)."""
        return {
            "status": "ok",
            "service": "windows-internal-api",
            "metrics": red_metrics.snapshot(),
        }

    # -------------------------------------------------------------------------
    # Эндпоинты статусов приложений и настроек ИИ
    # -------------------------------------------------------------------------
    @app.get("/api/v1/apps/status", tags=["apps"])
    @app.get("/api/apps/status", tags=["apps"])
    async def get_apps_status(profile: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает статус доступности приложений для формирования меню."""
        cfg = load_tc_config(profile)
        apps_sec = cfg.get("apps", {})
        enabled_list = apps_sec.get("enabled", []) if isinstance(apps_sec, dict) else []
        disabled_list = apps_sec.get("disabled", []) if isinstance(apps_sec, dict) else []

        apps_map: Dict[str, Dict[str, Any]] = {}
        for item in enabled_list:
            apps_map[item] = {"enabled": True, "name": item}
        for item in disabled_list:
            apps_map[item] = {"enabled": False, "name": item}

        ai_config = cfg.get("ai_providers_and_models_configuration") or cfg.get("ai", {})
        if not ai_config:
            global_cfg = load_tc_config()
            ai_config = global_cfg.get("ai_providers_and_models_configuration") or global_cfg.get("ai", {})

        return {
            "status": "ok",
            "apps": apps_map,
            "ai": ai_config,
        }

    @app.get("/auth/settings", tags=["auth"])
    @app.get("/api/v1/auth/settings", tags=["auth"])
    async def get_user_settings(request: Request) -> Dict[str, Any]:
        """Чтение активных настроек системы и модели."""
        settings: Dict[str, Any] = {}

        if not settings.get("model"):
            cfg = load_tc_config()
            ai_sec = cfg.get("ai_providers_and_models_configuration") or cfg.get("ai", {})
            prov = ai_sec.get("default_provider") or ai_sec.get("provider", "gemini")
            model = ai_sec.get("default_model") or (ai_sec.get(prov, {}).get("model", "") if isinstance(ai_sec.get(prov), dict) else "")
            settings.setdefault("model", f"{prov}:{model}" if model else (model or prov))
            settings.setdefault("provider", prov)

        settings.setdefault("status", "ok")
        settings.setdefault("favorite_models", {})
        return settings

    @app.post("/auth/settings", tags=["auth"])
    @app.post("/api/v1/auth/settings", tags=["auth"])
    async def update_user_settings(request: Request) -> Dict[str, Any]:
        """Сохранение активной конфигурации модели."""
        try:
            body = await request.json()
            if body.get("model") or body.get("provider"):
                save_ai_config(provider=body.get("provider", ""), model_name=body.get("model", ""))

            return {"status": "ok", "saved": body}
        except Exception:
            return {"status": "ok"}

    @app.get("/auth/check", tags=["auth"])
    @app.get("/api/v1/auth/check", tags=["auth"])
    async def check_user_auth(request: Request) -> Dict[str, Any]:
        """Проверка статуса текущей пользовательской сессии."""
        return {
            "authenticated": True,
            "name": "Windows Administrator",
            "email": "admin@localhost",
            "role": "Admin",
            "is_admin": True,
            "has_google": False,
            "oauth_enabled": False,
        }

    @app.post("/auth/logout", tags=["auth"])
    @app.get("/auth/logout", tags=["auth"])
    async def auth_logout() -> Dict[str, Any]:
        """Завершение пользовательской сессии."""
        return {"status": "ok"}

    @app.get("/api/v1/chat/active-model", tags=["chat"])
    @app.get("/api/v1/tc/model", tags=["chat"])
    async def get_chat_active_model(profile: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает активную модель ИИ."""
        cfg = load_tc_config(profile)
        ai_sec = cfg.get("ai_providers_and_models_configuration") or cfg.get("ai", {})
        prov = ai_sec.get("default_provider") or ai_sec.get("provider", "gemini")
        model = ai_sec.get("default_model") or (ai_sec.get(prov, {}).get("model", "") if isinstance(ai_sec.get(prov), dict) else "")
        if not model and isinstance(ai_sec.get("providers"), dict) and prov in ai_sec["providers"]:
            model = ai_sec["providers"][prov].get("model", "")
        return {"status": "ok", "provider": prov, "model": model or "gemini-3.1-flash-lite", "config_file": "tc.json"}

    @app.get("/api/v1/chat/models", tags=["chat"])
    async def get_available_chat_models() -> Dict[str, Any]:
        """Список доступных моделей ИИ для дропдауна."""
        try:
            from src.ai.model_manager import get_available_models, is_provider_enabled
            return {
                "models": {
                    "gemini": get_available_models("gemini") or ["gemini-3.1-flash-lite", "gemini-3.1-flash"],
                    "gemini_cli": get_available_models("gemini_cli") or ["gemini_cli:gemini-3.1-flash-lite"],
                    "agy": get_available_models("agy") or ["agy-gemini-3.6-flash"],
                    "foundry": get_available_models("foundry") if is_provider_enabled("foundry") else [],
                    "ollama": get_available_models("ollama") if is_provider_enabled("ollama") else [],
                }
            }
        except Exception:
            return {
                "models": {
                    "gemini": ["gemini-3.1-flash-lite", "gemini-3.1-flash"],
                    "gemini_cli": ["gemini_cli:gemini-3.1-flash-lite"],
                    "agy": ["agy-gemini-3.6-flash"],
                }
            }

    @app.get("/api/admin/system_instruction", tags=["admin"])
    @app.get("/api/v1/admin/system_instruction", tags=["admin"])
    @app.get("/api/v1/tc/model-instruction", tags=["admin"])
    async def get_system_instruction_fallback() -> Dict[str, Any]:
        """Получение системной инструкции."""
        prompt_file = _PROJECT_ROOT / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
        if not prompt_file.exists():
            prompt_file = _PROJECT_ROOT / "apps" / "windows" / "prompts" / "chat" / "system_instruction.md"
        if prompt_file.exists():
            try:
                return {"status": "success", "content": prompt_file.read_text(encoding="utf-8", errors="replace")}
            except Exception:
                pass
        return {"status": "success", "content": "Вы — интеллектуальный ассистент платформы AI Windows Admin."}

    @app.post("/api/admin/system_instruction", tags=["admin"])
    @app.post("/api/v1/admin/system_instruction", tags=["admin"])
    @app.post("/api/v1/tc/model-instruction", tags=["admin"])
    async def set_system_instruction_fallback(request: Request) -> Dict[str, Any]:
        """Сохранение системной инструкции."""
        try:
            body = await request.json()
            content = body.get("content") or body.get("instruction") or body.get("system_instruction") or ""
            if content:
                prompt_file = _PROJECT_ROOT / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
                prompt_file.parent.mkdir(parents=True, exist_ok=True)
                prompt_file.write_text(content, encoding="utf-8")
            return {"status": "success", "content": content}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/terminal/config.json", tags=["terminal"])
    async def get_terminal_config() -> Dict[str, Any]:
        """Возвращает конфигурацию сетевого веб-терминала."""
        term_cfg_path = _WEBGUI_DIR / "terminal" / "config.json"
        if term_cfg_path.is_file():
            try:
                with open(term_cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as ex:
                logger.debug(f"[API Server] Ошибка чтения config.json терминала: {ex}")
        return {
            "theme": {
                "background": "var(--bs-body-bg, #0c1017)",
                "foreground": "var(--bs-body-color, #e6edf3)",
                "cursor": "#38bdf8",
                "selectionBackground": "rgba(56, 189, 248, 0.3)"
            },
            "fontFamily": "Cascadia Code, Consolas, monospace",
            "fontSize": 14,
            "cursorBlink": True,
            "scrollback": 5000
        }

    @app.get("/api/themes", tags=["themes"])
    @app.get("/api/v1/themes", tags=["themes"])
    async def get_themes_catalog() -> Dict[str, Any]:
        """Возвращает каталог тем оформления, сканируя директории apps/windows/api/webgui/themes."""
        themes_dir = _WEBGUI_DIR / "themes"
        catalog_file = themes_dir / "themes_catalog.json"
        if catalog_file.is_file():
            try:
                with open(catalog_file, "r", encoding="utf-8") as f:
                    return {"status": "ok", "themes": json.load(f)}
            except Exception:
                pass
        try:
            from apps.windows.api.webgui.themes.generate_themes_catalog import scan_themes_directory
            themes = scan_themes_directory(themes_dir)
            return {"status": "ok", "themes": themes}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "themes": []}

    # Статические файлы TC
    if _WEBGUI_DIR.exists():
        app.mount("/webinterface", SmartMultiDirStaticFiles(_WEBGUI_DIR, _COMMON_WEBGUI_DIR), name="tc-webinterface")
        app.mount("/html", SmartMultiDirStaticFiles(_WEBGUI_DIR, _COMMON_WEBGUI_DIR), name="tc-html")

        if (_WEBGUI_DIR / "apps").exists():
            app.mount("/apps/static", StaticFiles(directory=_WEBGUI_DIR / "apps"), name="tc-apps-static")
        if (_WEBGUI_DIR / "static").exists():
            app.mount("/static", StaticFiles(directory=_WEBGUI_DIR / "static"), name="tc-static")

    return app


# Алиас для совместимости
create_internal_app = create_app

# Ленивый синглтон приложения для Uvicorn и точки входа
_app: Optional[FastAPI] = None


def get_app() -> FastAPI:
    """Возвращает singleton экземпляр FastAPI приложения (ленивая инициализация)."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def __getattr__(name: str) -> Any:
    """Ленивое предоставление app для uvicorn без сайд-эффектов при импорте модуля."""
    if name == "app":
        return get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "app",
    "get_app",
    "create_app",
    "create_internal_app",
    "discover_and_register_routers",
    "load_config",
    "load_tc_config",
]


