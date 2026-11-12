# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API - GitHub Issues Router
# =============================================================================
# Description:
#   FastAPI роутер для управления GitHub Issues, вехами Milestones, метками
#   и Git-контекстом репозитория для глобальной вкладки WebGUI tab_issues.
#
# Usage Examples:
#   GET  /api/issues/git-info
#   GET  /api/issues?state=open
#   POST /api/issues
#
# File: router_issues.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:41:44
# =============================================================================

from __future__ import annotations
"""FastAPI роутер для взаимодействия с GitHub Issues и Git-контекстом."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from src.github.service import GitHubService
from src.github.models import IssueType, Priority, Component
from src.ai.agents.github_issue_agent import GitHubIssueAgent

router = APIRouter(prefix="/api/issues", tags=["github_issues"])
_service = GitHubService()
_agent = GitHubIssueAgent(service=_service)


class CreateIssueRequest(BaseModel):
    """Схема запроса создания новой задачи."""
    title: str = Field(..., description="Заголовок задачи")
    body: str = Field(default="", description="Описание задачи в Markdown")
    issue_type: str = Field(default="feature", description="Тип задачи")
    priority: str = Field(default="priority:medium", description="Приоритет")
    component: str = Field(default="component:core", description="Компонент системы")
    assignee: Optional[str] = Field(default="@me", description="Исполнитель")
    milestone: Optional[str] = Field(default=None, description="Веха/Релиз")
    extra_labels: List[str] = Field(default_factory=list, description="Дополнительные метки")


class CloseIssueRequest(BaseModel):
    """Схема запроса закрытия задачи."""
    comment: Optional[str] = Field(default=None, description="Итоговый комментарий")
    reason: str = Field(default="completed", description="Причина закрытия")


class CommentIssueRequest(BaseModel):
    """Схема запроса добавления комментария."""
    comment: str = Field(..., description="Текст комментария")


def _get_git_info() -> Dict[str, Any]:
    """Сбор информации о локальном Git-репозитории и привязке к GitHub.

    Returns:
        Словарь с параметрами git-репозитория.
    """
    repo_root = Path(__file__).resolve().parents[4]
    git_dir = repo_root / ".git"
    is_git = git_dir.exists()

    remote_url = ""
    repo_name = ""
    branch = ""
    last_commit = ""
    is_clean = True

    if is_git:
        try:
            # Получение remote URL
            res_url = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo_root), check=False
            )
            remote_url = res_url.stdout.strip()

            # Парсинг owner/repo из URL (https://github.com/owner/repo.git или git@github.com:owner/repo.git)
            match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", remote_url)
            if match:
                repo_name = f"{match.group(1)}/{match.group(2)}"

            # Получение текущей ветки
            res_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo_root), check=False
            )
            branch = res_branch.stdout.strip()

            # Получение последнего коммита
            res_commit = subprocess.run(
                ["git", "log", "-1", "--format=%h - %s (%cr)"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo_root), check=False
            )
            last_commit = res_commit.stdout.strip()

            # Проверка чистоты рабочей директории
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(repo_root), check=False
            )
            is_clean = len(res_status.stdout.strip()) == 0

        except Exception as e:
            logger.warning(f"Ошибка получения Git-информации: {e}")

    gh_ready = _service.client.is_ready()
    web_url = f"https://github.com/{repo_name}" if repo_name else ""

    return {
        "is_git_repository": is_git,
        "remote_url": remote_url,
        "repo_name": repo_name,
        "branch": branch,
        "last_commit": last_commit,
        "is_clean": is_clean,
        "gh_cli_installed": _service.client.is_installed(),
        "gh_cli_authenticated": _service.client.is_authenticated(),
        "gh_ready": gh_ready,
        "web_url": web_url,
        "issues_url": f"{web_url}/issues" if web_url else "",
    }


@router.get("/git-info")
async def get_git_info() -> Dict[str, Any]:
    """Получение информации о текущем Git-репозитории и статусе GitHub CLI."""
    return {"status": "ok", "data": _get_git_info()}


@router.get("")
async def list_issues(
    state: str = Query("open", pattern="^(open|closed|all)$"),
    label: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100)
) -> Dict[str, Any]:
    """Список задач с фильтрацией по статусу и меткам."""
    labels = [label] if label else None
    issues = _service.get_issues(state=state, labels=labels, limit=limit)

    results = []
    for issue in issues:
        results.append({
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state.value,
            "issue_type": issue.issue_type.value,
            "priority": issue.priority.value,
            "component": issue.component.value,
            "labels": issue.labels,
            "assignees": issue.assignees,
            "milestone": {
                "title": issue.milestone.title,
                "progress_pct": issue.milestone.progress_pct
            } if issue.milestone else None,
            "url": issue.url
        })

    return {
        "status": "ok",
        "total": len(results),
        "issues": results
    }


@router.get("/templates")
async def get_issue_templates() -> Dict[str, Any]:
    """Получение списка доступных шаблонов задач из .github/ISSUE_TEMPLATE/."""
    repo_root = Path(__file__).resolve().parents[4]
    tpl_dir = repo_root / ".github" / "ISSUE_TEMPLATE"
    templates = []

    if tpl_dir.is_dir():
        for f in tpl_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8", errors="replace")
            # Извлечение name и title из frontmatter
            name_match = re.search(r"name:\s*['\"]?([^'\"\n]+)", content)
            title_match = re.search(r"title:\s*['\"]?([^'\"\n]+)", content)
            body_content = re.sub(r"^---[\s\S]*?---\s*", "", content).strip()

            templates.append({
                "id": f.stem,
                "filename": f.name,
                "name": name_match.group(1).strip() if name_match else f.stem,
                "default_title": title_match.group(1).strip() if title_match else "",
                "body": body_content
            })

    return {"status": "ok", "templates": templates}


@router.get("/labels")
async def get_standard_labels() -> Dict[str, Any]:
    """Получение стандартной палитры меток AI-TC."""
    return {
        "status": "ok",
        "labels": [
            {"name": k, "color": v["color"], "description": v["description"]}
            for k, v in _service.STANDARD_LABELS.items()
        ]
    }


@router.post("/labels/sync")
async def sync_labels() -> Dict[str, Any]:
    """Синхронизация типовых меток AI-TC в репозиторий GitHub."""
    count = _service.sync_standard_labels()
    return {"status": "ok", "synced_count": count}


@router.get("/{number}")
async def get_issue_details(number: int) -> Dict[str, Any]:
    """Детальная информация о задаче."""
    issue = _service.get_issue(number)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Задача #{number} не найдена")

    return {
        "status": "ok",
        "issue": {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state.value,
            "issue_type": issue.issue_type.value,
            "priority": issue.priority.value,
            "component": issue.component.value,
            "labels": issue.labels,
            "assignees": issue.assignees,
            "milestone": {
                "title": issue.milestone.title,
                "progress_pct": issue.milestone.progress_pct
            } if issue.milestone else None,
            "url": issue.url
        }
    }


@router.post("")
async def create_issue(req: CreateIssueRequest) -> Dict[str, Any]:
    """Создание новой задачи GitHub Issue."""
    issue_type = IssueType.from_str(req.issue_type)
    priority = Priority.from_str(req.priority)
    component = Component.from_str(req.component)

    created = _service.create_issue(
        title=req.title,
        body=req.body,
        issue_type=issue_type,
        priority=priority,
        component=component,
        extra_labels=req.extra_labels,
        assignee=req.assignee,
        milestone=req.milestone
    )
    if not created:
        raise HTTPException(status_code=500, detail="Не удалось создать Issue через GitHub CLI")

    return {"status": "ok", "url": created.url}


@router.post("/{number}/close")
async def close_issue(number: int, req: CloseIssueRequest) -> Dict[str, Any]:
    """Закрытие задачи."""
    success = _service.close_issue(number, comment=req.comment)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось закрыть задачу #{number}")
    return {"status": "ok", "number": number, "closed": True}


@router.post("/{number}/reopen")
async def reopen_issue(number: int) -> Dict[str, Any]:
    """Повторное открытие задачи."""
    success = _service.client.reopen_issue(number)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось открыть задачу #{number}")
    return {"status": "ok", "number": number, "reopened": True}


@router.post("/{number}/comment")
async def add_comment(number: int, req: CommentIssueRequest) -> Dict[str, Any]:
    """Добавление комментария в задачу."""
    success = _service.client.add_comment(number, req.comment)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось добавить комментарий к #{number}")
    return {"status": "ok", "number": number, "commented": True}


@router.post("/{number}/create-branch")
async def create_branch_for_issue(number: int) -> Dict[str, Any]:
    """Создание изолированной Git-ветки под задачу."""
    branch = _agent.setup_workspace_branch(number)
    if not branch:
        raise HTTPException(status_code=500, detail=f"Ошибка создания ветки для задачи #{number}")
    return {"status": "ok", "number": number, "branch": branch}


@router.get("/{number}/ai-plan")
async def get_ai_task_plan(number: int) -> Dict[str, Any]:
    """Построение формализованного плана ТЗ для AI-разработчика."""
    plan = _agent.prepare_task(number)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Не удалось построить ТЗ для задачи #{number}")
    return {
        "status": "ok",
        "plan": {
            "issue_number": plan.issue_number,
            "title": plan.title,
            "issue_type": plan.issue_type.value,
            "component": plan.component.value,
            "priority": plan.priority.value,
            "target_files": plan.target_files,
            "requirements": plan.requirements,
            "test_cases": plan.test_cases,
            "suggested_branch": plan.suggested_branch,
            "closing_keyword": plan.closing_keyword
        }
    }
