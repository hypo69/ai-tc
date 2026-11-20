# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета безопасности (security)
# =============================================================================
# Description:
#   Экспорт классов безопасности, аутентификации, авторизации, аудита и
#   очистки секретов SSH MCP Server.
#
# File: __init__.py
# Project: ai-tc (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from .audit import AuditLogger
from .authentication import AuthenticationError, RemoteMCPAuthenticator
from .authorization import AuthorizationError, PathPolicyValidator
from .credentials import CredentialManager
from .host_verification import HostKeyVerifier, HostVerificationError
from .secret_redactor import SecretRedactor

__all__ = [
    "AuditLogger",
    "AuthenticationError",
    "AuthorizationError",
    "CredentialManager",
    "HostKeyVerifier",
    "HostVerificationError",
    "PathPolicyValidator",
    "RemoteMCPAuthenticator",
    "SecretRedactor",
]
