# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Filesystem Probe
# =============================================================================
# Description:
#   Зонд файловой системы Windows: безопасный обход каталогов установки,
#   пользовательских профилей, извлечение PE-метаданных и разбор ярлыков.
#
# File: filesystem_probe.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд глубокого обхода файловой системы для обнаружения программ и артефактов."""

from datetime import datetime
import os
from pathlib import Path
from typing import List, Tuple
from logger import logger
from apps.windows.sdk.software_scanner.metadata_extractor import PEMetadataExtractor
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
    ScanErrorItem,
)
from apps.windows.sdk.software_scanner.policies import ScannerPolicy
from apps.windows.sdk.software_scanner.scope import ScannerScope


class FilesystemProbe:
    """Зонд обхода файловой системы с контролем нагрузки и безопасности."""

    def __init__(self, policy: ScannerPolicy | None = None) -> None:
        self.policy = policy or ScannerPolicy()
        self.scope = ScannerScope(self.policy)
        self.extractor = PEMetadataExtractor()

    def scan(self, custom_roots: List[str] | None = None) -> Tuple[List[EvidenceItem], List[ScanErrorItem]]:
        """Выполнить обход файловой системы по заданным или стандартным корням."""
        roots = custom_roots or self.scope.get_all_scan_roots(include_drives=True)
        items: List[EvidenceItem] = []
        errors: List[ScanErrorItem] = []

        for root in roots:
            if not os.path.exists(root):
                continue
            sub_items, sub_errors = self._scan_directory_tree(root)
            items.extend(sub_items)
            errors.extend(sub_errors)

        return items, errors

    def _scan_directory_tree(self, root_dir: str) -> Tuple[List[EvidenceItem], List[ScanErrorItem]]:
        """Рекурсивный обход директории с ограничением глубины и отслеживанием ошибок."""
        items: List[EvidenceItem] = []
        errors: List[ScanErrorItem] = []
        base_depth = len(Path(root_dir).parts)

        try:
            for current_root, dirs, files in os.walk(root_dir, topdown=True):
                current_depth = len(Path(current_root).parts) - base_depth
                if current_depth >= self.policy.max_scan_depth:
                    dirs.clear()  # Не углубляемся дальше
                    continue

                # Исключаем системные и мусорные каталоги
                dirs[:] = [
                    d for d in dirs
                    if not self.scope.is_excluded_dir(d)
                    and not self.scope.is_reparse_point(os.path.join(current_root, d))
                ]

                # Ограничиваем количество анализируемых файлов в одной папке
                files_to_scan = files[:self.policy.max_files_per_directory]

                for file_name in files_to_scan:
                    ext = os.path.splitext(file_name)[1].lower()
                    file_path = os.path.join(current_root, file_name)

                    if ext in self.policy.executable_extensions:
                        item = self._process_executable(file_path, file_name)
                        if item:
                            items.append(item)
                    elif ext == ".lnk":
                        item = self._process_shortcut(file_path, file_name)
                        if item:
                            items.append(item)

        except PermissionError as ex:
            errors.append(ScanErrorItem(path=root_dir, error_type="PermissionError", message=str(ex)))
        except OSError as ex:
            errors.append(ScanErrorItem(path=root_dir, error_type="OSError", message=str(ex)))
        except Exception as ex:
            logger.debug(f"[FilesystemProbe] Непредвиденная ошибка в {root_dir}: {ex}")
            errors.append(ScanErrorItem(path=root_dir, error_type="UnexpectedError", message=str(ex)))

        return items, errors

    def _process_executable(self, file_path: str, file_name: str) -> EvidenceItem | None:
        """Обработка обнаруженного бинарного файла .exe."""
        try:
            stat = os.stat(file_path)
            meta = self.extractor.get_version_info(file_path)
            product_name = meta.get("product_name") or meta.get("file_description") or os.path.splitext(file_name)[0]
            
            sha256_hash = None
            if self.policy.compute_sha256:
                sha256_hash = self.extractor.compute_sha256(file_path, self.policy.max_hash_file_size_bytes)

            mtime_iso = datetime.fromtimestamp(stat.st_mtime).isoformat()

            return EvidenceItem(
                evidence_type=EvidenceType.EXECUTABLE,
                source="Filesystem",
                path=file_path,
                product_name=product_name,
                publisher=meta.get("publisher"),
                version=meta.get("product_version") or meta.get("file_version"),
                sha256=sha256_hash,
                last_observed=mtime_iso,
                confidence=ConfidenceLevel.HIGH if meta.get("product_name") else ConfidenceLevel.MEDIUM,
                raw_details={
                    "size_bytes": stat.st_size,
                    "mtime": mtime_iso,
                    "original_filename": meta.get("original_filename"),
                    "file_description": meta.get("file_description"),
                }
            )
        except (OSError, PermissionError):
            return None

    def _process_shortcut(self, file_path: str, file_name: str) -> EvidenceItem | None:
        """Обработка обнаруженного ярлыка .lnk."""
        target = self.extractor.resolve_lnk_target(file_path)
        return EvidenceItem(
            evidence_type=EvidenceType.SHORTCUT,
            source="Filesystem_LNK",
            path=file_path,
            product_name=os.path.splitext(file_name)[0],
            confidence=ConfidenceLevel.LOW,
            raw_details={"target_path": target},
        )


__all__ = ["FilesystemProbe"]

