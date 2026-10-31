# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows DB
# =============================================================================
# Description:
#   Пакет управления базами данных (MariaDB, SQLite) для AI-Windows-Admin.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:39:00
# =============================================================================

"""Пакет управления базами данных (MariaDB, SQLite)."""

from .db_adapter import DatabaseAdapter, db_adapter

__all__ = ["DatabaseAdapter", "db_adapter"]

