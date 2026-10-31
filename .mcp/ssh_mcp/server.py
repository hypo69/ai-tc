# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер (Local STDIO и Remote Streamable HTTP + FastAPI)
# =============================================================================
# Description:
#   Реализация компонента `ssh-mcp-server` и `ssh-mcp-agent` на базе
#   Official MCP Python SDK v2 (`mcp.server.MCPServer`).
#   Поддерживает протокол STDIO (для локальной интеграции с ИИ-клиентами) и
#   Streamable HTTP с обязательной проверкой Bearer-токена и заголовка Origin
#   для удалённого режима (Раздел 3, 10, 11 ТЗ).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.server import build_mcp_server, build_remote_http_app
#     mcp_srv, modules = build_mcp_server(runtime)
#
# File: server.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:01:00
# =============================================================================

import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from mcp.server import MCPServer
from pydantic import BaseModel, Field

from .bootstrap import SSHMCPRuntime, create_runtime
from .mcp_tools import register_all_tools
from .security.authentication import AuthenticationError, RemoteMCPAuthenticator


class RemoteCommandRequest(BaseModel):
    """Тело запроса для удалённого выполнения команды через Remote MCP Agent.

    Attributes:
        command (str): Исполняемая команда.
        args (List[str]): Список аргументов.
        env (Dict[str, str]): Переменные окружения.
        shell (str): Оболочка.
        timeout (int): Таймаут в секундах.
        elevate (bool): Флаг повышения привилегий.
    """

    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    shell: str = Field(default="default")
    timeout: int = Field(default=60)
    elevate: bool = Field(default=False)


class ApprovalDecisionRequest(BaseModel):
    """Запрос на одобрение или отклонение опасной операции.

    Attributes:
        approval_id (str): Идентификатор подтверждения.
        decision (str): Решение ('approved' или 'rejected').
        decided_by (str): Имя администратора.
    """

    approval_id: str
    decision: str = Field(default="approved")
    decided_by: str = Field(default="administrator")


def build_mcp_server(
    runtime: Optional[SSHMCPRuntime] = False,  # type: ignore[assignment]
) -> tuple[MCPServer, Dict[str, object], SSHMCPRuntime]:
    """Создание экземпляра MCPServer v2 и регистрация всех 72 инструментов.

    Args:
        runtime (Optional[SSHMCPRuntime]): Существующий контейнер ядра (или создаётся новый).

    Returns:
        tuple[MCPServer, Dict[str, object], SSHMCPRuntime]: Сервер MCP, словарь модулей и рантайм.

    Examples:
        >>> srv, mods, rt = build_mcp_server(create_runtime(db_path=":memory:"))
        >>> srv.name
        'SSH MCP Server'
    """
    rt = runtime if runtime else create_runtime()
    mcp = MCPServer(
        name=rt.settings.application.name,
        version=rt.settings.application.version,
        instructions=(
            "Универсальный SSH MCP Server (Windows + Linux, Full Admin). "
            "Все операции проходят через Command Registry, Approval Manager и Audit Logger."
        ),
    )
    modules = register_all_tools(mcp, rt)
    return mcp, modules, rt


def build_remote_http_app(
    runtime: Optional[SSHMCPRuntime] = False,  # type: ignore[assignment]
    expected_token: str = "",
) -> FastAPI:
    """Создание защищённого HTTP-приложения для Remote MCP Server (Streamable HTTP + Admin API).

    Обеспечивает обязательную проверку заголовков `Authorization: Bearer <token>`
    и `Origin` для защиты от несанкционированных обращений (Раздел 10 и 14 ТЗ).

    Args:
        runtime (Optional[SSHMCPRuntime]): Контейнер сервисов ядра.
        expected_token (str): Ожидаемый секретный токен (если пуст — берётся из окружения).

    Returns:
        FastAPI: Защищённое ASGI-приложение.

    Examples:
        >>> app = build_remote_http_app(create_runtime(db_path=":memory:"), expected_token="tok-1")
    """
    mcp, _modules, rt = build_mcp_server(runtime)
    token = expected_token or os.environ.get(rt.settings.security.api_token_env, "default-dev-token")

    authenticator = RemoteMCPAuthenticator(
        expected_token=token,
        allowed_origins=rt.settings.server.remote.allowed_origins,
    )

    app = FastAPI(
        title=rt.settings.application.name,
        version=rt.settings.application.version,
    )

    @app.middleware("http")
    async def security_auth_middleware(request: Request, call_next: Any) -> Any:
        """Middleware строгой проверки Bearer-токена и Origin для всех обращений к Remote MCP."""
        auth_header = request.headers.get("Authorization", "")
        origin_header = request.headers.get("Origin", "")
        try:
            authenticator.verify_request(auth_header, origin_header)
        except AuthenticationError as exc:
            rt.audit_logger.log_event(
                host_id="remote-mcp",
                operation=f"http:{request.url.path}",
                risk_level="high",
                status="denied",
                details={"error": str(exc), "origin": origin_header},
                actor="unauthenticated",
            )
            return JSONResponse(
                status_code=401,
                content=rt.normalizer.failure(
                    host="remote-mcp",
                    platform="windows",
                    operation="remote_mcp.auth",
                    code="UNAUTHORIZED",
                    message=str(exc),
                ),
            )
        return await call_next(request)

    @app.get("/api/ssh-mcp/health")
    async def health_endpoint() -> Dict[str, Any]:
        """Проверка работоспособности удалённого MCP-сервера."""
        return rt.normalizer.success(
            host="localhost",
            platform="windows",
            operation="remote_mcp.health",
            data={"status": "healthy", "mode": rt.settings.server.mode},
        )

    @app.post("/api/ssh-mcp/execute")
    async def execute_endpoint(req: RemoteCommandRequest) -> Dict[str, Any]:
        """Точка входа для выполнения команд через RemoteMCPTransport в гибридном режиме."""
        tr = await rt.connection_manager.get_transport("localhost")
        raw = await tr.execute_command(
            command=req.command,
            args=req.args,
            env=req.env,
            shell=req.shell,
            timeout=req.timeout,
            elevate=req.elevate,
        )
        return {
            "exit_code": raw.exit_code,
            "stdout": raw.stdout,
            "stderr": raw.stderr,
            "duration_ms": raw.duration_ms,
        }

    @app.post("/api/ssh-mcp/approvals/decide")
    async def decide_approval(req: ApprovalDecisionRequest) -> Dict[str, Any]:
        """Подтверждение или отклонение ожидающей опасной операции администратором."""
        if req.decision == "approved":
            ok = rt.approval_manager.approve(req.approval_id, req.decided_by)
        else:
            ok = rt.approval_manager.reject(req.approval_id, req.decided_by)
        if not ok:
            raise HTTPException(status_code=404, detail="Approval ID not found")
        return rt.normalizer.success(
            host="localhost",
            platform="windows",
            operation="approvals.decide",
            data={"approval_id": req.approval_id, "status": req.decision},
        )

    streamable_subapp = mcp.streamable_http_app(streamable_http_path="/")
    app.mount("/mcp", streamable_subapp)
    return app
