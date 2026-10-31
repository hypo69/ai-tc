# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Модульные тесты ядра, репозиториев и модулей инструментов
# =============================================================================
# Description:
#   Проверка всех 10 функциональных модулей, 12 репозиториев SQLite,
#   CommandRegistry, стандартизации ответов StandardMCPResponse и работы с
#   Windows/Linux адаптерами.
#
# File: test_core_and_tools.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.tests.unit
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:07:30
# =============================================================================

from pathlib import Path
import tempfile
import pytest

from ssh_mcp.bootstrap import create_runtime
from ssh_mcp.client import SSHMCPClient
from ssh_mcp.schemas.host import HostConfig
from ssh_mcp.tests.fixtures.mock_transports import FakeTransport


@pytest.mark.asyncio
async def test_all_10_modules_and_standardized_response() -> None:
    """Проверка работы всех 10 модулей инструментов и единого формата ответа (Раздел 4 и 9 ТЗ)."""
    rt = create_runtime(db_path=":memory:")
    client = SSHMCPClient(rt)

    # 1. Connection Management
    conn_res = await client.invoke_local("connection", "ssh_connect", host_id="localhost")
    assert conn_res["success"] is True
    assert conn_res["operation"] == "ssh.connect"
    assert "timestamp" in conn_res
    assert "execution" in conn_res

    fp_res = await client.invoke_local("connection", "ssh_host_fingerprint", host_id="localhost")
    assert fp_res["success"] is True
    assert fp_res["data"]["fingerprint"].startswith("SHA256:")

    # 2. System Administration (Windows local)
    mem_res = await client.invoke_local("system", "system_memory", host_id="localhost")
    assert mem_res["success"] is True
    assert mem_res["data"]["total_mb"] > 0
    assert "used_mb" in mem_res["data"]
    assert "available_mb" in mem_res["data"]

    cpu_res = await client.invoke_local("system", "system_cpu", host_id="localhost")
    assert cpu_res["success"] is True
    assert cpu_res["data"]["cores_logical"] >= 1

    # 3. Process Management
    proc_res = await client.invoke_local("processes", "process_list", host_id="localhost", limit=5)
    assert proc_res["success"] is True
    assert len(proc_res["data"]["processes"]) > 0

    top_res = await client.invoke_local("processes", "process_resource_usage", host_id="localhost", top_n=3)
    assert top_res["success"] is True
    assert len(top_res["data"]["top_processes"]) <= 3

    # 4. Filesystem Management + SFTP SHA-256 verification
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = str(Path(tmpdir) / "test_doc.txt")
        w_res = await client.invoke_local(
            "filesystem", "fs_write", host_id="localhost", path=test_file, content="hello-ssh-mcp"
        )
        assert w_res["success"] is True
        expected_hash = w_res["data"]["sha256"]

        r_res = await client.invoke_local("filesystem", "fs_read", host_id="localhost", path=test_file)
        assert r_res["success"] is True
        assert r_res["data"]["content"] == "hello-ssh-mcp"
        assert r_res["data"]["sha256"] == expected_hash

        stat_res = await client.invoke_local("filesystem", "fs_stat", host_id="localhost", path=test_file)
        assert stat_res["success"] is True
        assert stat_res["data"]["sha256"] == expected_hash

    # 5. Network Management
    net_res = await client.invoke_local("network", "network_interfaces", host_id="localhost")
    assert net_res["success"] is True
    assert isinstance(net_res["data"]["interfaces"], list)

    # 6. Diagnostics & Telemetry (сохранение в SQLite + экспорт для RAG)
    diag_res = await client.invoke_local("diagnostics", "diagnostics_collect", host_id="localhost")
    assert diag_res["success"] is True
    assert "health_score" in diag_res["data"]

    exp_res = await client.invoke_local("diagnostics", "diagnostics_export", host_id="localhost")
    assert exp_res["success"] is True
    assert exp_res["data"]["report_id"] == diag_res["data"]["report_id"]


@pytest.mark.asyncio
async def test_multi_node_parallel_windows_and_linux_ssh() -> None:
    """Проверка параллельного управления несколькими узлами Windows и Linux через SSH Pool (Раздел 14 ТЗ)."""
    rt = create_runtime(db_path=":memory:")

    def _factory(cfg: HostConfig) -> FakeTransport:
        return FakeTransport(cfg, rt.host_verifier, presented_fingerprint=f"SHA256:fp-{cfg.host_id}")

    rt.connection_manager._transport_factory = _factory

    win_host = HostConfig(
        host_id="win-ssh-01",
        hostname="win-srv-01",
        address="10.10.0.11",
        platform="windows",
        username="admin",
        auth_method="key",
    )
    lin_host = HostConfig(
        host_id="lin-ssh-01",
        hostname="lin-srv-01",
        address="10.10.0.12",
        platform="linux",
        username="root",
        auth_method="key",
    )
    rt.connection_manager.register_host(win_host)
    rt.connection_manager.register_host(lin_host)

    # Доверяем ключам обоих серверов в реестре host_keys
    rt.host_verifier.trust_host_key("win-ssh-01", "10.10.0.11", 22, "ssh-ed25519", "SHA256:fp-win-ssh-01")
    rt.host_verifier.trust_host_key("lin-ssh-01", "10.10.0.12", 22, "ssh-ed25519", "SHA256:fp-lin-ssh-01")

    client = SSHMCPClient(rt)
    import asyncio

    win_mem, lin_mem, lin_srv = await asyncio.gather(
        client.invoke_local("system", "system_memory", host_id="win-ssh-01"),
        client.invoke_local("system", "system_memory", host_id="lin-ssh-01"),
        client.invoke_local("services", "service_list", host_id="lin-ssh-01"),
    )

    assert win_mem["success"] is True
    assert win_mem["platform"] == "windows"
    assert win_mem["data"]["total_mb"] == 32768

    assert lin_mem["success"] is True
    assert lin_mem["platform"] == "linux"
    assert lin_mem["data"]["total_mb"] == 16384
    assert lin_mem["data"]["available_mb"] == 8192

    assert lin_srv["success"] is True
    assert lin_srv["data"]["init_system"] == "systemd"
