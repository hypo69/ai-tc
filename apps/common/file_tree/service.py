# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Common File Tree - Backend Service
# =============================================================================
# Description:
#   Сервисный уровень древовидного проводника файлов и поддиректорий
#   (apps/common/file_tree).
#   Обеспечивает:
#   - Построение иерархического дерева файлов и папок для выбранной директории.
#   - Навигацию по директориям (вверх, хлебные крошки, переходы).
#   - Краткую аналитическую сводку о содержимом файла (размер, строки, суть).
#   - Создание новых файлов и папок в выбранной директории с фиксацией в Git.
#   - Защиту от Path Traversal и валидацию относительных путей.
#
# File: service.py
# Project: ai-assistant
# Package: apps.common.file_tree
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:40
# =============================================================================

from __future__ import annotations
"""Сервис обзора дерева директорий, краткой сводки и создания файлов."""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.common.workspace_resolver import (
    CommonWorkspaceResolver,
    format_file_size,
    sanitize_relative_path,
)
from apps.common.file_editor.catalog import SupportedFileCatalog
from apps.common.file_tree.models import (
    BreadcrumbItem,
    CreateItemRequest,
    CreateItemResponse,
    DirectoryBrowseResponse,
    FileSummaryResponse,
    FileTreeNode,
)

# Ограничения обхода дерева каталогов для защиты ОЗУ и Event Loop
MAX_TREE_DEPTH: int = 12
MAX_TREE_NODES: int = 5000
MAX_SUMMARY_READ_BYTES: int = 2 * 1024 * 1024
_IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {".git", ".workspace", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
)


def _format_size(size_bytes: int) -> str:
    """Форматирует байты в удобную читаемую строку (B, KB, MB, GB)."""
    return format_file_size(size_bytes)


class FileTreeService:
    """Сервис древовидной структуры файлов с навигацией и генерацией сводок."""

    def __init__(
        self,
        base_root: Optional[Path] = None,
        resolver: Optional[CommonWorkspaceResolver] = None,
        workspace_manager: Any = None,
    ) -> None:
        """Инициализирует сервис дерева файлов.

        Args:
            base_root: Опциональный корневой каталог для автономного режима (тестов).
            resolver: Опциональный резолвер путей рабочего пространства.
            workspace_manager: Опциональный экземпляр WorkspaceManager.
        """
        self._base_root = base_root.resolve() if base_root else None
        if resolver is not None:
            self._resolver = resolver
        else:
            self._resolver = CommonWorkspaceResolver(
                base_root=self._base_root,
                workspace_manager=workspace_manager,
            )

    def _get_workspace_manager(self) -> Any:
        """Лениво возвращает экземпляр WorkspaceManager при наличии."""
        return self._resolver.get_workspace_manager()

    def resolve_workspace_and_dir(
        self,
        dir_path: str = "",
        workspace_id: Optional[str] = None,
    ) -> Tuple[str, Path, str, Path]:
        """Разрешает рабочее пространство и проверяет безопасность относительного пути каталога.

        Args:
            dir_path: Относительный путь к директории (пустая строка для корня).
            workspace_id: Идентификатор рабочего пространства.

        Returns:
            Кортеж (resolved_ws_id, ws_root, clean_dir_rel, target_dir_path).

        Raises:
            ValueError: При выходе за пределы рабочей директории (Path Traversal).
            FileNotFoundError: Если директория не существует на диске.
        """
        return self._resolver.resolve_path(dir_path, workspace_id=workspace_id, must_exist=True, is_dir=True)

    def _get_git_statuses(self, ws_root: Path) -> Dict[str, Tuple[str, str]]:
        """Извлекает коды и статусы Git для отслеживаемых файлов рабочей области."""
        return self._resolver.get_git_statuses(ws_root)

    def browse_directory(
        self,
        dir_path: str = "",
        workspace_id: Optional[str] = None,
        max_depth: int = 8,
    ) -> DirectoryBrowseResponse:
        """Сканирует и строит иерархическое дерево файлов для выбранной директории.

        Args:
            dir_path: Относительный путь к целевой директории.
            workspace_id: Идентификатор рабочей области.
            max_depth: Максимальная глубина рекурсивного сканирования.

        Returns:
            Экземпляр `DirectoryBrowseResponse` с цепочкой навигации и узлами дерева.
        """
        resolved_ws, ws_root, clean_dir_rel, target_dir = self.resolve_workspace_and_dir(
            dir_path=dir_path,
            workspace_id=workspace_id,
        )

        git_statuses = self._get_git_statuses(ws_root)

        # Построение хлебных крошек
        breadcrumbs: List[BreadcrumbItem] = [
            BreadcrumbItem(name="/ (Корень)", path="", is_current=(not clean_dir_rel))
        ]
        if clean_dir_rel:
            parts = clean_dir_rel.split("/")
            accum = ""
            for idx, part in enumerate(parts):
                accum = f"{accum}/{part}" if accum else part
                breadcrumbs.append(
                    BreadcrumbItem(
                        name=part,
                        path=accum,
                        is_current=(idx == len(parts) - 1),
                    )
                )

        parent_dir: Optional[str] = None
        if clean_dir_rel:
            parent_parts = clean_dir_rel.split("/")[:-1]
            parent_dir = "/".join(parent_parts)

        total_files = 0
        total_dirs = 0
        total_size = 0
        effective_max_depth = max(1, min(max_depth, MAX_TREE_DEPTH))

        # Рекурсивная функция обхода каталога с защитой от переполнения узлов
        def _scan_node(
            current_path: Path,
            current_depth: int,
            base_root: Optional[Path] = None,
            prefix_rel: str = "",
        ) -> List[FileTreeNode]:
            nonlocal total_files, total_dirs, total_size

            if (
                current_depth > effective_max_depth
                or (total_files + total_dirs) >= MAX_TREE_NODES
                or not current_path.exists()
            ):
                return []

            nodes: List[FileTreeNode] = []
            try:
                entries = sorted(
                    list(current_path.iterdir()),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except (PermissionError, OSError):
                return []

            root_for_rel = base_root if base_root is not None else ws_root

            for entry in entries:
                if (total_files + total_dirs) >= MAX_TREE_NODES:
                    break
                # Игнорируем внутренние системные каталоги Git и временные файлы
                if entry.name in _IGNORED_DIR_NAMES:
                    continue

                try:
                    rel_sub = entry.relative_to(root_for_rel).as_posix()
                    rel_to_ws = f"{prefix_rel}/{rel_sub}" if prefix_rel else rel_sub
                except ValueError:
                    rel_to_ws = entry.name

                is_directory = entry.is_dir()
                stat_info = entry.stat() if entry.exists() else None
                mtime_str = (
                    datetime.fromtimestamp(stat_info.st_mtime, timezone.utc).isoformat()
                    if stat_info
                    else ""
                )

                if is_directory:
                    total_dirs += 1
                    child_nodes = _scan_node(
                        entry,
                        current_depth + 1,
                        base_root=root_for_rel,
                        prefix_rel=prefix_rel,
                    )
                    node = FileTreeNode(
                        name=entry.name,
                        rel_path=rel_to_ws,
                        is_dir=True,
                        size=0,
                        size_formatted=f"{len(child_nodes)} эл.",
                        extension="dir",
                        modified_at=mtime_str,
                        tracked_by_git=True,
                        children_count=len(child_nodes),
                        children=child_nodes,
                    )
                    nodes.append(node)
                else:
                    total_files += 1
                    file_size = stat_info.st_size if stat_info else 0
                    total_size += file_size
                    ext = entry.suffix.lower()

                    git_info = git_statuses.get(rel_to_ws)
                    tracked = bool(git_info) or (ws_root / ".git").exists()
                    git_code = git_info[0] if git_info else ("L" if base_root else None)
                    git_desc = git_info[1] if git_info else ("Отслеживается (на диске)" if base_root else ("Отслеживается" if tracked else None))

                    descriptor = SupportedFileCatalog.get_descriptor(entry.name)
                    lang_id = descriptor.language_id if descriptor else "plaintext"

                    node = FileTreeNode(
                        name=entry.name,
                        rel_path=rel_to_ws,
                        is_dir=False,
                        size=file_size,
                        size_formatted=_format_size(file_size),
                        extension=ext,
                        modified_at=mtime_str,
                        tracked_by_git=tracked,
                        git_code=git_code,
                        git_status=git_desc,
                        children_count=0,
                        children=[],
                        language_id=lang_id,
                    )
                    nodes.append(node)

            return nodes

        tree_nodes = _scan_node(target_dir, current_depth=0)

        # Если находимся в корне рабочего пространства — включаем отслеживаемые внешние источники
        if not clean_dir_rel:
            wm = self._resolver.get_workspace_manager()
            if wm is not None:
                try:
                    dir_info = wm.get_directory_contents(resolved_ws)
                    ext_items = [i for i in dir_info.get("items", []) if i.get("is_external")]
                    existing_names = {node.name for node in tree_nodes}

                    for item in ext_items:
                        item_rel = str(item.get("rel_path") or item.get("name") or "")
                        # Обрабатываем только элементы верхнего уровня корня
                        if "/" in item_rel:
                            continue
                        i_name = item.get("name") or item_rel
                        if i_name in existing_names:
                            continue

                        is_dir_item = bool(item.get("is_dir"))
                        if is_dir_item:
                            local_p = Path(str(item.get("local_path", "")))
                            sub_children: List[FileTreeNode] = []
                            if local_p.exists() and local_p.is_dir():
                                sub_children = _scan_node(
                                    local_p,
                                    current_depth=1,
                                    base_root=local_p,
                                    prefix_rel=i_name,
                                )
                                total_dirs += 1
                            ext_node = FileTreeNode(
                                name=i_name,
                                rel_path=i_name,
                                is_dir=True,
                                size=0,
                                size_formatted=f"{len(sub_children)} эл.",
                                extension="dir",
                                modified_at=item.get("modified") or "",
                                tracked_by_git=True,
                                git_code=item.get("git_code") or "L",
                                git_status=item.get("git_status") or "Внешняя директория",
                                children_count=len(sub_children),
                                children=sub_children,
                            )
                            tree_nodes.append(ext_node)
                            existing_names.add(i_name)
                        else:
                            f_sz = int(item.get("size_bytes", 0))
                            total_files += 1
                            total_size += f_sz
                            descriptor = SupportedFileCatalog.get_descriptor(i_name)
                            lang_id = descriptor.language_id if descriptor else "plaintext"
                            f_node = FileTreeNode(
                                name=i_name,
                                rel_path=i_name,
                                is_dir=False,
                                size=f_sz,
                                size_formatted=_format_size(f_sz),
                                extension=item.get("extension") or Path(i_name).suffix.lower(),
                                modified_at=item.get("modified") or "",
                                tracked_by_git=True,
                                git_code=item.get("git_code") or "L",
                                git_status=item.get("git_status") or "Отслеживается (на диске)",
                                children_count=0,
                                children=[],
                                language_id=lang_id,
                            )
                            tree_nodes.append(f_node)
                            existing_names.add(i_name)
                except Exception as ext_err:
                    logger.warning(f"[FileTreeService] Ошибка включения внешних источников: {ext_err}")

        return DirectoryBrowseResponse(
            status="ok",
            workspace_id=resolved_ws,
            current_dir=clean_dir_rel,
            parent_dir=parent_dir,
            breadcrumbs=breadcrumbs,
            total_files=total_files,
            total_dirs=total_dirs,
            total_size_bytes=total_size,
            tree=tree_nodes,
        )

    def get_file_summary(
        self,
        rel_path: str,
        workspace_id: Optional[str] = None,
    ) -> FileSummaryResponse:
        """Формирует краткую аналитическую сводку по файлу для контекстного меню.

        Args:
            rel_path: Относительный путь к файлу.
            workspace_id: Идентификатор рабочей области.

        Returns:
            Объект `FileSummaryResponse`.
        """
        clean_rel = (rel_path or "").strip().replace("\\", "/").strip("/")
        if not clean_rel:
            raise ValueError("Путь к файлу не может быть пустым.")

        dir_part = str(Path(clean_rel).parent).replace("\\", "/")
        if dir_part == ".":
            dir_part = ""

        resolved_ws, ws_root, _, _ = self.resolve_workspace_and_dir(
            dir_path=dir_part,
            workspace_id=workspace_id,
        )

        target_file = (ws_root / clean_rel).resolve()
        try:
            target_file.relative_to(ws_root)
        except ValueError:
            raise ValueError(f"Путь '{rel_path}' выходит за пределы рабочей директории.")

        if not target_file.exists():
            raise FileNotFoundError(f"Файл '{clean_rel}' не найден в рабочей области.")
        if target_file.is_dir():
            raise ValueError(f"Указанный путь '{clean_rel}' является директорией, а не файлом.")

        file_stat = target_file.stat()
        file_size = file_stat.st_size
        mtime_str = datetime.fromtimestamp(file_stat.st_mtime, timezone.utc).isoformat()
        ext = target_file.suffix.lower()

        # Проверка на бинарность (чтение только первых 8 КБ без загрузки всего файла в память)
        with open(target_file, "rb") as bf:
            raw_head = bf.read(8192)
        is_binary = b"\x00" in raw_head

        descriptor = SupportedFileCatalog.get_descriptor(target_file.name, is_binary_detected=is_binary)
        language_id = descriptor.language_id if descriptor else "plaintext"

        summary_text = ""
        preview_text = ""
        lines_count: Optional[int] = None
        tags: List[str] = [ext.lstrip(".") or "файл", language_id]

        if is_binary:
            summary_text = f"Бинарный файл ({descriptor.display_name if descriptor else 'данные'}). Размер: {_format_size(file_size)}."
            preview_text = f"[Бинарные данные: {file_size} байт. Доступен в Hex-редакторе Wasm]"
        else:
            try:
                with open(target_file, "rb") as tf:
                    bounded_bytes = tf.read(MAX_SUMMARY_READ_BYTES)
                full_text = bounded_bytes.decode("utf-8", errors="replace")
                lines = full_text.splitlines()
                lines_count = len(lines)

                # Извлечение краткого резюме: ищем docstring, markdown h1, или первые информативные строки
                doc_match = re.search(r'"""(.*?)"""', full_text, re.DOTALL)
                if doc_match:
                    doc_content = doc_match.group(1).strip()
                    summary_text = " ".join(doc_content.splitlines()[:2]).strip()
                elif ext in {".md", ".markdown"}:
                    h1_match = re.search(r"^#\s+(.+)$", full_text, re.MULTILINE)
                    summary_text = h1_match.group(1).strip() if h1_match else "Документ Markdown"
                else:
                    informative_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*"))]
                    summary_text = " ".join(informative_lines[:2]) if informative_lines else f"Текстовый файл {target_file.name}"

                if len(summary_text) > 200:
                    summary_text = summary_text[:197] + "..."

                preview_text = "\n".join(lines[:10])
                if len(lines) > 10:
                    preview_text += f"\n... (всего {len(lines)} строк)"

                if lines_count > 100:
                    tags.append(f"{lines_count} строк")
            except Exception as read_err:
                summary_text = f"Ошибка чтения текстового содержимого: {read_err}"

        return FileSummaryResponse(
            status="ok",
            workspace_id=resolved_ws,
            rel_path=clean_rel,
            name=target_file.name,
            extension=ext,
            size=file_size,
            size_formatted=_format_size(file_size),
            is_binary=is_binary,
            lines_count=lines_count,
            language_id=language_id,
            summary=summary_text,
            preview=preview_text,
            modified_at=mtime_str,
            tags=list(dict.fromkeys(tags)),
        )

    def create_item(
        self,
        req: CreateItemRequest,
    ) -> CreateItemResponse:
        """Создает новый файл или директорию в заданной целевой директории с фиксацией в Git.

        Args:
            req: Запрос создания `CreateItemRequest`.

        Returns:
            Объект `CreateItemResponse`.
        """
        clean_target_dir = (req.target_dir or "").strip().replace("\\", "/").strip("/")
        name_clean = (req.name or "").strip().replace("\\", "/").strip("/")

        if not name_clean:
            raise ValueError("Имя создаваемого объекта не может быть пустым.")

        full_rel_path = f"{clean_target_dir}/{name_clean}" if clean_target_dir else name_clean

        wm = self._get_workspace_manager()
        resolved_ws, ws_root, _, _ = self.resolve_workspace_and_dir(
            dir_path=clean_target_dir,
            workspace_id=req.workspace_id,
        )

        commit_msg = (
            req.commit_message.strip()
            if req.commit_message and req.commit_message.strip()
            else f"Создан {'каталог' if req.is_dir else 'файл'}: {full_rel_path}"
        )

        if self._base_root is None and wm is not None and hasattr(wm, "create_workspace_item"):
            res = wm.create_workspace_item(
                workspace_id=resolved_ws,
                rel_path=full_rel_path,
                is_dir=req.is_dir,
                content=req.content,
            )
            return CreateItemResponse(
                status="ok",
                workspace_id=resolved_ws,
                rel_path=full_rel_path,
                target_dir=clean_target_dir,
                name=name_clean,
                is_dir=req.is_dir,
                size=res.get("size", len(req.content.encode("utf-8"))),
                message=commit_msg,
            )

        # Автономный режим (для тестов или прямого доступа к файловой системе)
        target_path = (ws_root / full_rel_path).resolve()
        try:
            target_path.relative_to(ws_root)
        except ValueError:
            raise ValueError(f"Путь '{full_rel_path}' выходит за пределы рабочей директории.")

        if req.is_dir:
            target_path.mkdir(parents=True, exist_ok=True)
            size = 0
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            encoded_bytes = req.content.encode("utf-8")
            tmp_path = target_path.with_name(f".{target_path.name}.tmp")
            try:
                tmp_path.write_bytes(encoded_bytes)
                os.replace(tmp_path, target_path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
            size = len(encoded_bytes)

        return CreateItemResponse(
            status="ok",
            workspace_id=resolved_ws,
            rel_path=full_rel_path,
            target_dir=clean_target_dir,
            name=name_clean,
            is_dir=req.is_dir,
            size=size,
            message=commit_msg,
        )

    def list_directories(
        self,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Возвращает плоский список всех папок рабочей области для быстрого перехода.

        Args:
            workspace_id: Идентификатор рабочей области.

        Returns:
            Список словарей с полями `path` и `name`.
        """
        resolved_ws, ws_root, _, _ = self.resolve_workspace_and_dir(
            dir_path="",
            workspace_id=workspace_id,
        )

        dirs: List[Dict[str, str]] = [{"path": "", "name": "/ (Корень)"}]
        for p in sorted(ws_root.rglob("*")):
            if len(dirs) >= MAX_TREE_NODES:
                break
            if p.is_dir():
                if any(part in _IGNORED_DIR_NAMES for part in p.parts):
                    continue
                rel_dir = p.relative_to(ws_root).as_posix()
                dirs.append({"path": rel_dir, "name": f"/{rel_dir}"})

        return dirs
