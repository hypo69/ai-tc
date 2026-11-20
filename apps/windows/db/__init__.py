# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows DB
# =============================================================================
# Description:
#   Пакет управления базами данных (MariaDB, SQLite) для ai-tc.
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Пакет управления базами данных (MariaDB, SQLite)."""

from .db_adapter import DatabaseAdapter, db_adapter

__all__ = ["DatabaseAdapter", "db_adapter"]

