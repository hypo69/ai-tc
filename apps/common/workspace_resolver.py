# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps Common - Workspace & Path Resolver
# =============================================================================
# Description:
#   Единый сервисный компонент разрешения рабочих пространств, безопасных
#   относительных путей (защита от Path Traversal), форматирования размеров
#   и работы с Git для модулей file_editor, file_tree и obsidian.
#
# File: workspace_resolver.py
# Project: ai-assistant
# Package: apps.common
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:28:30
# =============================================================================

from __future__ import annotations
"""Единый сервис разрешения рабочих пространств и безопасной навигации по путям."""

from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple

from logger import logger


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в байтах в человекочитаемую строку.

    Args:
        size_bytes: Размер в байтах.

    Returns:
        Строка с единицами измерения (B, KB, MB, GB).
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def sanitize_relative_path(rel_path: str = "") -> str:
    """Очищает и нормализует относительный путь, удаляя лишние слэши и нулевые байты.

    Args:
        rel_path: Входной относительный путь.

    Returns:
        Нормализованный относительный путь с прямыми слэшами.
    """
    clean = (rel_path or "").replace("\x00", "").strip().replace("\\", "/").strip("/")
    if clean in {".", "/"}:
        return ""
    return clean


class CommonWorkspaceResolver:
    """Единый резолвер путей и рабочих пространств с защитой от выхода за пределы корня."""

    def __init__(self, base_root: Optional[Path] = None, workspace_manager: Any = None) -> None:
        """Инициализирует резолвер.

        Args:
            base_root: Фиксированный корневой каталог (например, для тестов).
            workspace_manager: Экземпляр WorkspaceManager (Explicit DI).
        """
        self._base_root = base_root.resolve() if base_root else None
        self._wm: Any = workspace_manager

    def get_workspace_manager(self) -> Any:
        """Лениво загружает и возвращает экземпляр WorkspaceManager."""
        if self._wm is None:
            try:
                from apps.ai_assistant.core.workspace_manager import WorkspaceManager
                self._wm = WorkspaceManager()
            except Exception as exc:
                logger.warning(f"[CommonWorkspaceResolver] WorkspaceManager недоступен: {exc}")
        return self._wm

    def resolve_workspace_root(
        self,
        workspace_id: Optional[str] = None,
    ) -> Tuple[str, Path]:
        """Определяет идентификатор и корневой каталог рабочего пространства.

        Args:
            workspace_id: Желаемый идентификатор рабочей области.

        Returns:
            Кортеж (resolved_ws_id, ws_root_path).
        """
        if self._base_root is not None:
            return workspace_id or "custom", self._base_root

        wm = self.get_workspace_manager()
        if wm is not None:
            target_ws = workspace_id or wm.store.get_active_workspace_id()
            if not target_ws:
                all_ws = wm.list_workspaces()
                target_ws = all_ws[0]["workspace_id"] if all_ws else "demo"
            _, ws_root = wm._get_or_create_workspace(target_ws)
            return target_ws, ws_root.resolve()

        try:
            from apps.ai_assistant.core.workspace_registry import resolve_workspaces_dir
            ws_dir = resolve_workspaces_dir().resolve()
        except Exception:
            from header import __root__
            ws_dir = (__root__ / "data" / "workspaces").resolve()
        raw_ws = (workspace_id or "demo").strip()
        safe_ws = re.sub(r'[\\/:*?"<>|\x00]', "_", raw_ws).strip(".") or "demo"
        ws_root = (ws_dir / safe_ws).resolve()
        try:
            ws_root.relative_to(ws_dir)
        except ValueError:
            raise ValueError(f"Недопустимый идентификатор рабочего пространства: '{workspace_id}'")
        ws_root.mkdir(parents=True, exist_ok=True)
        return safe_ws, ws_root

    def resolve_path(
        self,
        rel_path: str = "",
        workspace_id: Optional[str] = None,
        must_exist: bool = False,
        is_dir: Optional[bool] = None,
    ) -> Tuple[str, Path, str, Path]:
        """Разрешает путь внутри рабочего пространства с защитой от Path Traversal.

        Args:
            rel_path: Относительный путь к файлу или папке.
            workspace_id: Идентификатор рабочего пространства.
            must_exist: Требовать ли фактическое существование объекта на диске.
            is_dir: Если задано True/False, проверяет тип объекта (папка/файл).

        Returns:
            Кортеж (resolved_ws, ws_root, clean_rel, target_path).

        Raises:
            ValueError: При попытке выхода за пределы рабочей директории или некорректном типе.
            FileNotFoundError: Если must_exist=True и объект не найден.
        """
        clean_rel = sanitize_relative_path(rel_path)
        if is_dir is False and not clean_rel:
            raise ValueError("Относительный путь к файлу не может быть пустым.")

        resolved_ws, ws_root = self.resolve_workspace_root(workspace_id)

        target = (ws_root / clean_rel).resolve() if clean_rel else ws_root

        # Проверяем, находится ли путь внутри ws_root
        is_inside_root = False
        try:
            target.relative_to(ws_root)
            is_inside_root = True
        except ValueError:
            is_inside_root = False

        # Если путь не внутри корня или не найден локально — проверяем привязанные внешние источники
        if (not is_inside_root or (must_exist and not target.exists())) and clean_rel:
            wm = self.get_workspace_manager()
            if wm is not None:
                try:
                    sources = wm.list_sources(resolved_ws)
                    for s in sources:
                        s_name = s.get("name") or Path(str(s.get("source_path", ""))).name
                        s_path = Path(str(s.get("source_path", "")))
                        s_type = s.get("source_type")
                        if clean_rel == s_name:
                            if s_path.exists():
                                target = s_path.resolve()
                                is_inside_root = True
                                break
                        elif clean_rel.startswith(f"{s_name}/"):
                            sub_rel = clean_rel[len(s_name) + 1:]
                            s_path_resolved = s_path.resolve()
                            cand = (s_path_resolved / sub_rel).resolve()
                            try:
                                cand.relative_to(s_path_resolved)
                            except ValueError:
                                continue
                            if cand.exists() or not must_exist:
                                target = cand
                                is_inside_root = True
                                break
                except Exception:
                    pass

        if not is_inside_root:
            raise ValueError(f"Путь '{rel_path}' выходит за пределы рабочей директории.")

        if must_exist and not target.exists():
            item_type = "Директория" if is_dir else "Файл или директория"
            raise FileNotFoundError(f"{item_type} '{clean_rel or '/'}' не найдена в рабочей области.")

        if target.exists() and is_dir is not None:
            if is_dir and not target.is_dir():
                raise ValueError(f"Путь '{clean_rel}' является файлом, а не директорией.")
            if not is_dir and target.is_dir():
                raise ValueError(f"Путь '{clean_rel}' является директорией, а не файлом.")

        return resolved_ws, ws_root, clean_rel, target

    def get_git_statuses(self, ws_root: Path) -> Dict[str, Tuple[str, str]]:
        """Извлекает коды и описания статусов Git для отслеживаемых файлов.

        Args:
            ws_root: Корневой путь рабочего пространства.

        Returns:
            Словарь {относительный_путь: (status_code, status_label)}.
        """
        status_map: Dict[str, Tuple[str, str]] = {}
        git_dir = ws_root / ".git"
        if not git_dir.exists():
            return status_map

        wm = self.get_workspace_manager()
        raw_status = ""
        if wm is not None and hasattr(wm, "_run_git"):
            try:
                raw_status = wm._run_git(ws_root, ["status", "--porcelain", "-uall"])
            except Exception:
                raw_status = ""

        if not raw_status:
            return status_map

        code_labels = {
            "M": "Модифицирован",
            "A": "Добавлен",
            "D": "Удален",
            "R": "Переименован",
            "C": "Скопирован",
            "?": "Не отслеживается",
            "!": "Игнорируется",
        }

        for line in raw_status.splitlines():
            line_str = line.strip()
            if len(line_str) < 4:
                continue
            index_code = line_str[0]
            work_code = line_str[1]
            filepath = line_str[3:].strip().strip('"').replace("\\", "/")
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[-1].strip()

            effective_code = work_code if work_code != " " else index_code
            if effective_code == "?":
                label = code_labels.get("?", "Новый файл")
            else:
                label = code_labels.get(effective_code, "Изменен")

            status_map[filepath] = (effective_code, label)

        return status_map

    def commit_file(
        self,
        ws_root: Path,
        rel_path: str,
        commit_message: str,
        author_name: str = "ai-assistant",
    ) -> Optional[str]:
        """Выполняет Git commit для измененного или созданного файла.

        Args:
            ws_root: Корневой путь рабочего пространства.
            rel_path: Относительный путь к коммитируемому файлу.
            commit_message: Текст коммита.
            author_name: Имя автора изменений.

        Returns:
            Хеш созданного коммита или None, если репозиторий недоступен.
        """
        if not (ws_root / ".git").exists():
            return None

        clean_rel = sanitize_relative_path(rel_path)
        wm = self.get_workspace_manager()
        if wm is not None and hasattr(wm, "_run_git"):
            try:
                wm._run_git(ws_root, ["add", clean_rel])
                wm._run_git(
                    ws_root,
                    ["commit", "-m", f"[{author_name}] {commit_message}", "--", clean_rel],
                )
                commit_hash = wm._run_git(ws_root, ["rev-parse", "--short", "HEAD"]).strip()
                return commit_hash
            except Exception as exc:
                logger.warning(f"[CommonWorkspaceResolver] Ошибка фиксации коммита в Git: {exc}")
                return None
        return None
