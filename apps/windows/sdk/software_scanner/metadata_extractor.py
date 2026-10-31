# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Metadata Extractor
# =============================================================================
# Description:
#   Извлечение низкоуровневых метаданных исполняемых файлов (PE VersionInfo),
#   целей ярлыков .lnk и вычисление хеш-сумм SHA-256.
#
# File: metadata_extractor.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Извлечение метаданных исполняемых файлов и ярлыков Windows."""

import ctypes
from ctypes import wintypes
import hashlib
import os
import struct
import sys
from typing import Any, Dict, Optional
from logger import logger


class PEMetadataExtractor:
    """Извлекатель PE-метаданных и свойств файлов Windows."""

    @staticmethod
    def get_version_info(file_path: str) -> Dict[str, Optional[str]]:
        """Извлечь CompanyName, ProductName, FileDescription, FileVersion из PE-ресурсов."""
        meta: Dict[str, Optional[str]] = {
            "product_name": None,
            "publisher": None,
            "file_description": None,
            "file_version": None,
            "product_version": None,
            "original_filename": None,
        }

        if not sys.platform.startswith("win") or not os.path.isfile(file_path):
            return meta

        try:
            version_dll = ctypes.windll.version
            size = version_dll.GetFileVersionInfoSizeW(file_path, None)
            if size == 0:
                return meta

            res_buffer = ctypes.create_string_buffer(size)
            if not version_dll.GetFileVersionInfoW(file_path, 0, size, res_buffer):
                return meta

            # Извлечение языковой кодовой страницы (Translation table)
            lp_translate = ctypes.c_void_p()
            u_len = wintypes.UINT()
            
            sub_block_trans = "\\VarFileInfo\\Translation"
            if version_dll.VerQueryValueW(
                res_buffer,
                sub_block_trans,
                ctypes.byref(lp_translate),
                ctypes.byref(u_len)
            ) and u_len.value >= 4:
                trans_bytes = ctypes.string_at(lp_translate, 4)
                lang, code_page = struct.unpack("<HH", trans_bytes)
                lang_codepage = f"{lang:04x}{code_page:04x}"
            else:
                lang_codepage = "040904b0"  # Default US English / Unicode

            field_keys = {
                "product_name": "ProductName",
                "publisher": "CompanyName",
                "file_description": "FileDescription",
                "file_version": "FileVersion",
                "product_version": "ProductVersion",
                "original_filename": "OriginalFilename",
            }

            for meta_key, prop_name in field_keys.items():
                query_path = f"\\StringFileInfo\\{lang_codepage}\\{prop_name}"
                lp_buffer = ctypes.c_wchar_p()
                val_len = wintypes.UINT()
                if version_dll.VerQueryValueW(
                    res_buffer,
                    query_path,
                    ctypes.byref(lp_buffer),
                    ctypes.byref(val_len)
                ) and val_len.value > 0 and lp_buffer.value:
                    meta[meta_key] = lp_buffer.value.strip()

        except Exception as ex:
            logger.debug(f"[PEMetadataExtractor] Ошибка чтения PE-инфо {file_path}: {ex}")

        return meta

    @staticmethod
    def resolve_lnk_target(lnk_path: str) -> Optional[str]:
        """Бинарный парсинг цели ярлыка .lnk Windows без внешних зависимостей."""
        if not os.path.isfile(lnk_path):
            return None

        try:
            with open(lnk_path, "rb") as f:
                content = f.read()

            # Проверяем LNK Header GUID
            if len(content) < 76 or content[:4] != b"\x4c\x00\x00\x00":
                return None

            flags = struct.unpack_from("<I", content, 0x14)[0]
            has_link_info = bool(flags & 0x02)

            if not has_link_info:
                return None

            # Позиция LinkInfo
            id_list_size = 0
            offset = 76
            if flags & 0x01:  # HasTargetIDList
                if len(content) >= offset + 2:
                    id_list_size = struct.unpack_from("<H", content, offset)[0]
                    offset += 2 + id_list_size

            if len(content) < offset + 28:
                return None

            link_info_offset = offset
            local_base_path_offset = struct.unpack_from("<I", content, link_info_offset + 0x10)[0]
            
            if local_base_path_offset > 0:
                full_path_offset = link_info_offset + local_base_path_offset
                path_end = content.find(b"\x00", full_path_offset)
                if path_end != -1:
                    raw_path = content[full_path_offset:path_end]
                    try:
                        return raw_path.decode("mbcs", errors="ignore")
                    except Exception:
                        return raw_path.decode("utf-8", errors="ignore")

        except Exception as ex:
            logger.debug(f"[PEMetadataExtractor] Ошибка парсинга LNK {lnk_path}: {ex}")

        return None

    @staticmethod
    def compute_sha256(file_path: str, max_size_bytes: int = 50 * 1024 * 1024) -> Optional[str]:
        """Вычисление SHA-256 хеш-суммы файла с лимитом размера."""
        if not os.path.isfile(file_path):
            return None

        try:
            size = os.path.getsize(file_path)
            if size > max_size_bytes:
                return None

            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except OSError as ex:
            logger.debug(f"[PEMetadataExtractor] Ошибка хеширования {file_path}: {ex}")
            return None


__all__ = ["PEMetadataExtractor"]

