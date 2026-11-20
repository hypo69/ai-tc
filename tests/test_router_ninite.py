# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-TC Tests - Router Ninite
# =============================================================================
# Description:
#   Юнит-тесты для FastAPI-роутера Ninite Auto-Updater (`router_ninite.py`):
#   проверка загрузки, переименования в `ninite.exe`, атомарной замены
#   существующего файла (в том числе с атрибутом Read-Only) и валидации входа.
#
# Usage Examples:
#   CLI:
#     pytest tests/test_router_ninite.py
#
# File: test_router_ninite.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 17:10:00
# =============================================================================

from __future__ import annotations

import os
import stat
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers import router_ninite


def _create_client() -> TestClient:
    """Создаёт тестовый FastAPI-клиент с подключённым роутером Ninite."""
    app = FastAPI()
    app.include_router(router_ninite.router)
    return TestClient(app)


def test_upload_renames_to_ninite_exe_and_replaces_existing(tmp_path: Path, monkeypatch) -> None:
    """
    Проверяет сохранение установщика под именем `ninite.exe` и замену
    существующего файла при повторной загрузке другого `.exe`.
    """
    pf_dir = tmp_path / "ProgramFiles" / "Ninite"
    pd_dir = tmp_path / "ProgramData" / "ai-tc" / "ninite"
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_FILES", pf_dir)
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_DATA", pd_dir)

    client = _create_client()

    # Первичная загрузка: файл с произвольным именем Ninite переименовывается в ninite.exe
    first_payload = b"MZ_FIRST_NINITE_BINARY_V1"
    resp1 = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("Ninite Chrome 7Zip Installer.exe", first_payload, "application/octet-stream")},
    )
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["success"] is True
    assert body1["replaced"] is False
    assert body1["saved_filename"] == "ninite.exe"
    assert body1["original_filename"] == "Ninite Chrome 7Zip Installer.exe"

    dest_file = pf_dir / "ninite.exe"
    assert dest_file.exists()
    assert dest_file.read_bytes() == first_payload

    # Повторная загрузка: существующий ninite.exe заменяется новым файлом и остаётся ninite.exe
    second_payload = b"MZ_SECOND_NINITE_BINARY_V2_LONGER"
    resp2 = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("Ninite Firefox VLC Installer.exe", second_payload, "application/octet-stream")},
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["success"] is True
    assert body2["replaced"] is True
    assert body2["saved_filename"] == "ninite.exe"
    assert body2["original_filename"] == "Ninite Firefox VLC Installer.exe"
    assert body2["size_bytes"] == len(second_payload)

    assert dest_file.read_bytes() == second_payload
    # Временных файлов после атомарной замены оставаться не должно
    assert [p.name for p in pf_dir.iterdir()] == ["ninite.exe"]


def test_upload_replaces_readonly_existing_ninite_exe(tmp_path: Path, monkeypatch) -> None:
    """Проверяет замену существующего `ninite.exe` с установленным атрибутом Read-Only."""
    pf_dir = tmp_path / "ProgramFiles" / "Ninite"
    pd_dir = tmp_path / "ProgramData" / "ai-tc" / "ninite"
    pf_dir.mkdir(parents=True, exist_ok=True)
    existing = pf_dir / "ninite.exe"
    existing.write_bytes(b"OLD_READONLY_BINARY")
    os.chmod(existing, stat.S_IREAD)

    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_FILES", pf_dir)
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_DATA", pd_dir)

    client = _create_client()
    new_payload = b"NEW_REPLACED_BINARY"
    resp = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("Ninite Updated.exe", new_payload, "application/octet-stream")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["replaced"] is True
    assert existing.read_bytes() == new_payload


def test_upload_rejects_non_exe_and_empty_file(tmp_path: Path, monkeypatch) -> None:
    """Проверяет валидацию расширения `.exe` и непустого содержимого загружаемого файла."""
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_FILES", tmp_path / "Ninite")
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_DATA", tmp_path / "ProgramData")

    client = _create_client()

    resp_bad_ext = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("readme.txt", b"not an exe", "text/plain")},
    )
    assert resp_bad_ext.status_code == 400

    resp_empty = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("Ninite.exe", b"", "application/octet-stream")},
    )
    assert resp_empty.status_code == 400


def test_upload_returns_403_when_existing_primary_cannot_be_overwritten(tmp_path: Path, monkeypatch) -> None:
    """
    Проверяет, что при невозможности перезаписать уже существующий
    `Program Files\\Ninite\\ninite.exe` возвращается 403 без тихого fallback в ProgramData.
    """
    pf_dir = tmp_path / "ProgramFiles" / "Ninite"
    pd_dir = tmp_path / "ProgramData" / "ai-tc" / "ninite"
    pf_dir.mkdir(parents=True, exist_ok=True)
    (pf_dir / "ninite.exe").write_bytes(b"EXISTING_PRIMARY")

    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_FILES", pf_dir)
    monkeypatch.setattr(router_ninite, "NINITE_PROGRAM_DATA", pd_dir)

    def _deny_write(target_dir: Path, content: bytes):
        raise PermissionError("Access is denied")

    monkeypatch.setattr(router_ninite, "_write_and_replace_ninite", _deny_write)

    client = _create_client()
    resp = client.post(
        "/api/v1/ninite/upload",
        files={"file": ("Ninite New.exe", b"NEW_DATA", "application/octet-stream")},
    )
    assert resp.status_code == 403
    assert not (pd_dir / "ninite.exe").exists()
