# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Интеграционные тесты гибридного режима и MCP Server v2
# =============================================================================
# Description:
#   Проверка регистрации инструментов в MCPServer v2, проверки файловых
#   политик (Path Traversal) и сквозного сценария диагностики ai-tc.
#
# File: test_mcp_integration.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.tests.integration
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:08:30
# =============================================================================

import pytest
from ssh_mcp.bootstrap import create_runtime
from ssh_mcp.client import SSHMCPClient
from ssh_mcp.server import build_mcp_server


@pytest.mark.asyncio
async def test_mcp_v2_server_registers_all_tools_and_blocks_path_traversal() -> None:
    """Проверка регистрации всех инструментов в MCPServer v2 и блокировки Path Traversal."""
    rt = create_runtime(db_path=":memory:")
    rt.sftp_manager.allowed_roots = ["C:/AllowedSandbox"]

    mcp_srv, modules, _ = build_mcp_server(rt)
    assert mcp_srv.name == "SSH MCP Server"
    assert len(modules) == 10

    client = SSHMCPClient(rt)

    # Попытка выйти за пределы разрешённого каталога через '..'
    traversal_res = await client.invoke_local(
        "filesystem", "fs_read", host_id="localhost", path="C:/AllowedSandbox/../../Windows/win.ini"
    )
    assert traversal_res["success"] is False
    assert traversal_res["error"]["code"] == "ACCESS_DENIED"

    # Попытка обратиться к каталогу вне белого списка
    outside_res = await client.invoke_local(
        "filesystem", "fs_list", host_id="localhost", path="C:/Users"
    )
    assert outside_res["success"] is False
    assert outside_res["error"]["code"] == "ACCESS_DENIED"
