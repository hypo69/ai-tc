# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin GitHub - Package Init
# =============================================================================
# Description:
#   Пакет управления задачами GitHub Issues, вехами Milestones, досками Projects
#   и сквозной интеграции задач с циклом автономной разработки AI-TC.
#
# Usage Examples:
#   from src.github import GitHubService, Issue, IssueType, Priority
#
#   service = GitHubService()
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.github
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Пакет управления жизненным циклом GitHub Issues & Projects для AI-TC."""

from src.github.models import (
    Issue,
    IssueState,
    IssueType,
    Priority,
    Component,
    Milestone,
    ProjectColumn,
    AITaskPlan,
    BranchInfo
)
from src.github.client import GitHubClient
from src.github.task_parser import TaskParser
from src.github.service import GitHubService

__all__ = [
    'Issue',
    'IssueState',
    'IssueType',
    'Priority',
    'Component',
    'Milestone',
    'ProjectColumn',
    'AITaskPlan',
    'BranchInfo',
    'GitHubClient',
    'TaskParser',
    'GitHubService',
]
