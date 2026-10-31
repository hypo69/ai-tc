# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Тесты безопасности и граничных сценариев приёмки (Раздел 14 ТЗ)
# =============================================================================
# Description:
#   Обязательная проверка всех негативных и защитных сценариев Раздела 14 ТЗ:
#   1. Неверные SSH-ключи.
#   2. Подмена SSH-сервера (MITM / неизвестный ключ).
#   3. Истечение времени выполнения (Timeout).
#   4. Потеря соединения во время команды и автоматическое восстановление (Recovery).
#   5. Отмена длительной задачи (ssh_task_cancel).
#   6. Попытка выполнения запрещённой команды и Path Traversal.
#   7. Попытка неавторизованного обращения к Remote MCP.
#   8. Привязка подтверждения (Approval) к хосту, команде и параметрам.
#   9. Очистка секретов (SecretRedactor) в журналах аудита.
#
# File: test_security_acceptance.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.tests.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:08:00
# =============================================================================

import asyncio
from fastapi.testclient import TestClient
import pytest

from ssh_mcp.bootstrap import create_runtime
from ssh_mcp.client import SSHMCPClient
from ssh_mcp.schemas.host import HostConfig
from ssh_mcp.server import build_remote_http_app
from ssh_mcp.tests.fixtures.mock_transports import FakeTransport


@pytest.mark.asyncio
async def test_unknown_and_spoofed_host_key_rejected() -> None:
    """Проверка отклонения неизвестного ключа и обнаружения подмены SSH-сервера (MITM)."""
    rt = create_runtime(db_path=":memory:")
    host = HostConfig(
        host_id="untrusted-srv",
        hostname="srv",
        address="10.0.0.99",
        platform="linux",
        username="admin",
        auth_method="key",
    )
    rt.connection_manager.register_host(host)

    # 1. Ключ ещё не добавлен в доверенные — режим strict обязан отклонить подключение
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg, rt.host_verifier, presented_fingerprint="SHA256:unknown-key-1"
    )
    client = SSHMCPClient(rt)
    res_unknown = await client.invoke_local("connection", "ssh_connect", host_id="untrusted-srv")
    assert res_unknown["success"] is False
    assert res_unknown["error"]["code"] == "HOST_KEY_VERIFICATION_FAILED"

    # 2. Регистрируем эталонный ключ, но сервер предъявляет другой (подмена SSH-сервера)
    rt.host_verifier.trust_host_key("untrusted-srv", "10.0.0.99", 22, "ssh-ed25519", "SHA256:legit-key")
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg, rt.host_verifier, presented_fingerprint="SHA256:attacker-mitm-key"
    )
    res_spoof = await client.invoke_local("connection", "ssh_connect", host_id="untrusted-srv")
    assert res_spoof["success"] is False
    assert res_spoof["error"]["code"] == "HOST_KEY_VERIFICATION_FAILED"


@pytest.mark.asyncio
async def test_invalid_ssh_keys_rejected() -> None:
    """Проверка обработки неверных SSH-ключей при подключении."""
    rt = create_runtime(db_path=":memory:")
    host = HostConfig(
        host_id="bad-key-srv",
        hostname="srv",
        address="10.0.0.55",
        platform="linux",
        username="root",
        auth_method="key",
    )
    rt.connection_manager.register_host(host)
    rt.host_verifier.trust_host_key("bad-key-srv", "10.0.0.55", 22, "ssh-ed25519", "SHA256:ok")
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg, rt.host_verifier, presented_fingerprint="SHA256:ok", auth_valid=False
    )

    client = SSHMCPClient(rt)
    res = await client.invoke_local("connection", "ssh_connect", host_id="bad-key-srv")
    assert res["success"] is False
    assert res["error"]["code"] == "CONNECTION_FAILED"


@pytest.mark.asyncio
async def test_command_timeout_and_connection_recovery() -> None:
    """Проверка истечения времени выполнения и авто-восстановления при обрыве соединения."""
    rt = create_runtime(db_path=":memory:")
    host = HostConfig(
        host_id="flaky-srv",
        hostname="flaky",
        address="10.0.0.77",
        platform="linux",
        username="admin",
        auth_method="key",
    )
    rt.connection_manager.register_host(host)
    rt.host_verifier.trust_host_key("flaky-srv", "10.0.0.77", 22, "ssh-ed25519", "SHA256:flaky-fp")

    # Сценарий 1: Потеря соединения во время команды -> автоматический reconnect и успешный повтор
    state = {"created": 0}

    def _recovery_factory(cfg: HostConfig) -> FakeTransport:
        state["created"] += 1
        drop_first = state["created"] == 1
        return FakeTransport(
            cfg,
            rt.host_verifier,
            presented_fingerprint="SHA256:flaky-fp",
            drop_once_on_execute=drop_first,
        )

    rt.connection_manager._transport_factory = _recovery_factory
    client = SSHMCPClient(rt)
    rec_res = await client.invoke_local("system", "system_memory", host_id="flaky-srv")
    assert rec_res["success"] is True
    assert state["created"] >= 2

    # Сценарий 2: Таймаут команды
    await rt.connection_manager.disconnect("flaky-srv")
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg,
        rt.host_verifier,
        presented_fingerprint="SHA256:flaky-fp",
        simulate_timeout=True,
    )
    timeout_res = await client.invoke_local(
        "execution", "ssh_execute", host_id="flaky-srv", command="long_op", timeout=1
    )
    assert timeout_res["success"] is False
    assert timeout_res["error"]["code"] == "EXECUTION_TIMEOUT"


@pytest.mark.asyncio
async def test_long_running_task_cancellation() -> None:
    """Проверка запуска и принудительной отмены длительной задачи (ssh_execute_async / ssh_task_cancel)."""
    rt = create_runtime(db_path=":memory:")
    host = HostConfig(
        host_id="task-srv",
        hostname="task",
        address="10.0.0.88",
        platform="linux",
        username="admin",
        auth_method="key",
    )
    rt.connection_manager.register_host(host)
    rt.host_verifier.trust_host_key("task-srv", "10.0.0.88", 22, "ssh-ed25519", "SHA256:task-fp")
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg, rt.host_verifier, presented_fingerprint="SHA256:task-fp"
    )

    client = SSHMCPClient(rt)
    started = await client.invoke_local(
        "execution", "ssh_execute_async", host_id="task-srv", command="sleep 30"
    )
    assert started["success"] is True
    task_id = started["data"]["task_id"]

    cancelled = await client.invoke_local("execution", "ssh_task_cancel", task_id=task_id)
    assert cancelled["success"] is True
    assert cancelled["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_approval_workflow_bound_to_host_command_and_params() -> None:
    """Проверка контроля опасных операций (Approval) и привязки к хосту, команде и параметрам."""
    rt = create_runtime(db_path=":memory:")
    host = HostConfig(
        host_id="win-prod-01",
        hostname="win-prod",
        address="10.0.0.21",
        platform="windows",
        username="admin",
        auth_method="key",
    )
    rt.connection_manager.register_host(host)
    rt.host_verifier.trust_host_key("win-prod-01", "10.0.0.21", 22, "ssh-ed25519", "SHA256:win-prod-fp")
    rt.connection_manager._transport_factory = lambda cfg: FakeTransport(
        cfg, rt.host_verifier, presented_fingerprint="SHA256:win-prod-fp"
    )

    client = SSHMCPClient(rt)

    # 1. Вызов high-risk операции без подтверждения возвращает APPROVAL_REQUIRED
    first_try = await client.invoke_local(
        "services", "service_restart", host_id="win-prod-01", service_name="Spooler"
    )
    assert first_try["success"] is False
    assert first_try["error"]["code"] == "APPROVAL_REQUIRED"
    approval_id = first_try["error"]["approval_id"]
    assert approval_id.startswith("apr-")

    # 2. Администратор одобряет запрос
    rt.approval_manager.approve(approval_id, decided_by="sec-admin")

    # 3. Попытка использовать этот же approval_id для ДРУГОЙ службы отклоняется!
    spoof_param_try = await client.invoke_local(
        "services",
        "service_restart",
        host_id="win-prod-01",
        service_name="WinDefend",
        approval_id=approval_id,
    )
    assert spoof_param_try["success"] is False
    assert spoof_param_try["error"]["code"] == "APPROVAL_REQUIRED"

    # 4. Вызов с точными согласованными параметрами выполняется успешно
    approved_try = await client.invoke_local(
        "services",
        "service_restart",
        host_id="win-prod-01",
        service_name="Spooler",
        approval_id=approval_id,
    )
    assert approved_try["success"] is True
    assert approved_try["data"]["status"] == "Running"


@pytest.mark.asyncio
async def test_forbidden_command_and_secret_redaction_in_audit() -> None:
    """Проверка отклонения незарегистрированной команды и очистки секретов в логах."""
    rt = create_runtime(db_path=":memory:")

    # Попытка выполнить команду, которой нет в CommandRegistry
    forbid_res = await rt.engine.dispatch(
        host_id="localhost",
        command_id="forbidden.format_disk",
        parameters={"drive": "C:"},
    )
    assert forbid_res["success"] is False
    assert forbid_res["error"]["code"] == "COMMAND_VALIDATION_ERROR"

    # Проверка, что секреты маскируются в журнале аудита
    rt.audit_logger.log_event(
        host_id="localhost",
        operation="user.create",
        risk_level="high",
        status="success",
        details={"username": "operator", "password": "SuperSecretPassword123!", "notes": "token=abc987"},
    )
    logs = rt.audit_logger.get_recent_logs(host_id="localhost", limit=5)
    assert len(logs) >= 1
    raw_json = str(logs[0]["redacted_details_json"])
    assert "SuperSecretPassword123!" not in raw_json
    assert "abc987" not in raw_json
    assert "***REDACTED***" in raw_json


def test_unauthorized_remote_mcp_access_rejected() -> None:
    """Проверка защиты Remote MCP HTTP-интерфейса от неавторизованных запросов и чужих Origin."""
    rt = create_runtime(db_path=":memory:")
    app = build_remote_http_app(rt, expected_token="valid-admin-token-999")
    http_client = TestClient(app)

    # 1. Запрос без токена -> 401 UNAUTHORIZED
    r1 = http_client.get("/api/ssh-mcp/health")
    assert r1.status_code == 401
    assert r1.json()["error"]["code"] == "UNAUTHORIZED"

    # 2. Запрос с неверным токеном -> 401 UNAUTHORIZED
    r2 = http_client.get(
        "/api/ssh-mcp/health",
        headers={"Authorization": "Bearer wrong-token", "Origin": "https://127.0.0.1"},
    )
    assert r2.status_code == 401

    # 3. Запрос с верным токеном, но запрещённым Origin -> 401 UNAUTHORIZED
    r3 = http_client.get(
        "/api/ssh-mcp/health",
        headers={"Authorization": "Bearer valid-admin-token-999", "Origin": "https://evil.example.com"},
    )
    assert r3.status_code == 401

    # 4. Запрос с верным токеном и доверенным Origin -> 200 OK
    r4 = http_client.get(
        "/api/ssh-mcp/health",
        headers={"Authorization": "Bearer valid-admin-token-999", "Origin": "https://127.0.0.1"},
    )
    assert r4.status_code == 200
    assert r4.json()["success"] is True
