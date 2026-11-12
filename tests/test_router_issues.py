# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Issues Unit Tests
# =============================================================================
# Description:
#   Модульные тесты FastAPI роутера управления GitHub Issues и Git-контекстом.
#
# Usage Examples:
#   pytest tests/test_router_issues.py -v
#
# File: test_router_issues.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:41:44
# =============================================================================

from __future__ import annotations
"""Тестирование FastAPI роутера задач GitHub Issues и Git-контекста."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_issues import router, _service, _agent
from src.github.models import Issue, IssueType, Priority, Component, AITaskPlan


@pytest.fixture
def test_client() -> TestClient:
    """Фикстура тестового клиента FastAPI с подключенным роутером."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRouterIssues:
    """Тестирование эндпоинтов управления GitHub Issues."""

    def test_get_git_info(self, test_client: TestClient) -> None:
        """Проверка эндпоинта информации о Git-репозитории."""
        response = test_client.get("/api/issues/git-info")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        info = data["data"]
        assert "is_git_repository" in info
        assert info["is_git_repository"] is True
        assert "remote_url" in info
        assert "repo_name" in info
        assert "branch" in info
        assert "gh_cli_installed" in info

    def test_list_issues_mocked(self, test_client: TestClient) -> None:
        """Проверка получения списка задач с моком сервиса."""
        sample_issue = Issue(
            number=125,
            title="Ошибка загрузки config.json",
            body="Описание проблемы",
            labels=["bug", "priority:high", "component:core"],
            assignees=["hypo69"],
            url="https://github.com/hypo69/AI-TC/issues/125"
        )

        with patch.object(_service, "get_issues", return_value=[sample_issue]):
            response = test_client.get("/api/issues?state=open")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["total"] == 1
            issue = data["issues"][0]
            assert issue["number"] == 125
            assert issue["issue_type"] == "bug"
            assert issue["priority"] == "priority:high"
            assert issue["component"] == "component:core"

    def test_get_issue_templates(self, test_client: TestClient) -> None:
        """Проверка чтения шаблонов задач из .github/ISSUE_TEMPLATE/."""
        response = test_client.get("/api/issues/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        templates = data["templates"]
        assert len(templates) > 0
        tpl_ids = [t["id"] for t in templates]
        assert "bug_report" in tpl_ids
        assert "feature_request" in tpl_ids

    def test_get_standard_labels(self, test_client: TestClient) -> None:
        """Проверка получения стандартной палитры меток AI-TC."""
        response = test_client.get("/api/issues/labels")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        labels = data["labels"]
        assert len(labels) >= 10
        label_names = [l["name"] for l in labels]
        assert "bug" in label_names
        assert "priority:critical" in label_names
        assert "component:telemetry" in label_names

    def test_create_issue_mocked(self, test_client: TestClient) -> None:
        """Проверка создания новой задачи."""
        sample_created = Issue(
            number=126,
            title="Новая панель мониторинга",
            body="Требуется панель",
            url="https://github.com/hypo69/AI-TC/issues/126"
        )

        with patch.object(_service, "create_issue", return_value=sample_created):
            payload = {
                "title": "Новая панель мониторинга",
                "body": "Требуется панель",
                "issue_type": "feature",
                "priority": "priority:medium",
                "component": "component:network",
                "assignee": "@me"
            }
            response = test_client.post("/api/issues", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["url"] == "https://github.com/hypo69/AI-TC/issues/126"

    def test_create_branch_for_issue_mocked(self, test_client: TestClient) -> None:
        """Проверка создания ветки Git под задачу."""
        with patch.object(_agent, "setup_workspace_branch", return_value="fix/125-config-fix"):
            response = test_client.post("/api/issues/125/create-branch")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["branch"] == "fix/125-config-fix"

    def test_get_ai_task_plan_mocked(self, test_client: TestClient) -> None:
        """Проверка генерации структурированного ТЗ для AI."""
        sample_plan = AITaskPlan(
            issue_number=125,
            title="Исправить загрузку",
            issue_type=IssueType.BUG,
            component=Component.CORE,
            priority=Priority.HIGH,
            target_files=["src/config.py"],
            requirements=["Проверить json"],
            test_cases=["Запустить pytest"],
            suggested_branch="fix/125-config",
            closing_keyword="Fixes"
        )

        with patch.object(_agent, "prepare_task", return_value=sample_plan):
            response = test_client.get("/api/issues/125/ai-plan")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            plan = data["plan"]
            assert plan["issue_number"] == 125
            assert plan["closing_keyword"] == "Fixes"
            assert "src/config.py" in plan["target_files"]
