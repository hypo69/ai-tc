# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - Supported File Catalog
# =============================================================================
# Description:
#   Полный каталог поддерживаемых типов файлов в стиле Visual Studio Code.
#   Обеспечивает классификацию более 85 расширений по языкам синтаксиса,
#   режимам редактирования (Code, Markdown, Tabular, Notebook, Vector SVG,
#   Image, PDF, Media, Hex) и возможность редактирования любого файла.
#
# File: catalog.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:00
# =============================================================================

from __future__ import annotations
"""Каталог всех типов файлов и режимов редактирования VS Code."""

from pathlib import Path
from typing import Dict, List
from apps.common.file_editor.models import EditorMode, FileTypeDescriptor


def _code_desc(
    ext: str,
    lang: str,
    name: str,
    icon: str = "bi-file-earmark-code",
    fmt: bool = True,
) -> FileTypeDescriptor:
    """Создает дескриптор для файла исходного кода или конфигурации."""
    return FileTypeDescriptor(
        extension=ext,
        language_id=lang,
        display_name=name,
        default_mode=EditorMode.CODE,
        supported_modes=[EditorMode.CODE, EditorMode.HEX],
        mime_type="text/plain",
        icon_class=icon,
        is_binary_default=False,
        supports_formatting=fmt,
    )


# Единый справочник расширений, поддерживаемых в VS Code
_RAW_DESCRIPTORS: List[FileTypeDescriptor] = [
    # 1. Языки программирования
    _code_desc("py", "python", "Python", "bi-filetype-py"),
    _code_desc("pyi", "python", "Python Stub", "bi-filetype-py"),
    _code_desc("pyw", "python", "Python Windows", "bi-filetype-py"),
    _code_desc("rs", "rust", "Rust", "bi-gear-wide-connected"),
    _code_desc("js", "javascript", "JavaScript", "bi-filetype-js"),
    _code_desc("mjs", "javascript", "JavaScript ES Module", "bi-filetype-js"),
    _code_desc("cjs", "javascript", "JavaScript CommonJS", "bi-filetype-js"),
    _code_desc("jsx", "javascriptreact", "React JSX", "bi-filetype-jsx"),
    _code_desc("ts", "typescript", "TypeScript", "bi-filetype-tsx"),
    _code_desc("tsx", "typescriptreact", "React TSX", "bi-filetype-tsx"),
    _code_desc("c", "c", "C Source", "bi-file-earmark-code"),
    _code_desc("h", "c", "C/C++ Header", "bi-file-earmark-code"),
    _code_desc("cpp", "cpp", "C++ Source", "bi-file-earmark-code"),
    _code_desc("hpp", "cpp", "C++ Header", "bi-file-earmark-code"),
    _code_desc("cc", "cpp", "C++ Source", "bi-file-earmark-code"),
    _code_desc("cs", "csharp", "C#", "bi-filetype-cs"),
    _code_desc("go", "go", "Go", "bi-file-earmark-code"),
    _code_desc("java", "java", "Java", "bi-filetype-java"),
    _code_desc("kt", "kotlin", "Kotlin", "bi-file-earmark-code"),
    _code_desc("swift", "swift", "Swift", "bi-file-earmark-code"),
    _code_desc("php", "php", "PHP", "bi-filetype-php"),
    _code_desc("rb", "ruby", "Ruby", "bi-filetype-rb"),
    _code_desc("lua", "lua", "Lua", "bi-file-earmark-code"),
    _code_desc("r", "r", "R Script", "bi-file-earmark-code"),
    _code_desc("dart", "dart", "Dart", "bi-file-earmark-code"),
    _code_desc("scala", "scala", "Scala", "bi-file-earmark-code"),
    _code_desc("zig", "zig", "Zig", "bi-file-earmark-code"),
    _code_desc("wat", "wat", "WebAssembly Text (WAT)", "bi-cpu"),
    # 2. Веб-разметка и таблицы стилей
    _code_desc("html", "html", "HTML", "bi-filetype-html"),
    _code_desc("htm", "html", "HTML", "bi-filetype-html"),
    _code_desc("css", "css", "CSS", "bi-filetype-css"),
    _code_desc("scss", "scss", "SCSS", "bi-filetype-scss"),
    _code_desc("sass", "sass", "Sass", "bi-filetype-sass"),
    _code_desc("less", "less", "Less", "bi-file-earmark-code"),
    _code_desc("vue", "vue", "Vue Component", "bi-file-earmark-code"),
    _code_desc("svelte", "svelte", "Svelte Component", "bi-file-earmark-code"),
    # 3. Конфигурации, схемы и структурированные данные
    _code_desc("json", "json", "JSON", "bi-braces"),
    _code_desc("jsonc", "jsonc", "JSON with Comments", "bi-braces"),
    _code_desc("json5", "json", "JSON5", "bi-braces"),
    _code_desc("jsonl", "json", "JSON Lines", "bi-braces"),
    _code_desc("yaml", "yaml", "YAML", "bi-filetype-yml"),
    _code_desc("yml", "yaml", "YAML", "bi-filetype-yml"),
    _code_desc("toml", "toml", "TOML", "bi-gear"),
    _code_desc("xml", "xml", "XML", "bi-filetype-xml"),
    _code_desc("xsd", "xml", "XML Schema", "bi-filetype-xml"),
    _code_desc("xsl", "xml", "XSLT", "bi-filetype-xml"),
    _code_desc("ini", "ini", "INI Configuration", "bi-sliders", False),
    _code_desc("cfg", "ini", "Config File", "bi-sliders", False),
    _code_desc("conf", "ini", "Configuration", "bi-sliders", False),
    _code_desc("env", "dotenv", "Environment (.env)", "bi-key", False),
    _code_desc("properties", "ini", "Java Properties", "bi-sliders", False),
    _code_desc("graphql", "graphql", "GraphQL", "bi-diagram-2"),
    _code_desc("proto", "protobuf", "Protocol Buffers", "bi-diagram-3"),
    # 4. Скрипты оболочки, базы данных и DevOps
    _code_desc("sql", "sql", "SQL Query", "bi-filetype-sql"),
    _code_desc("ps1", "powershell", "PowerShell", "bi-terminal"),
    _code_desc("psm1", "powershell", "PowerShell Module", "bi-terminal"),
    _code_desc("psd1", "powershell", "PowerShell Data", "bi-terminal"),
    _code_desc("sh", "shell", "Bash / Shell", "bi-terminal"),
    _code_desc("bash", "shell", "Bash Script", "bi-terminal"),
    _code_desc("zsh", "shell", "Zsh Script", "bi-terminal"),
    _code_desc("bat", "bat", "Windows Batch", "bi-terminal", False),
    _code_desc("cmd", "bat", "Windows Command", "bi-terminal", False),
    _code_desc("dockerfile", "dockerfile", "Dockerfile", "bi-box-seam", False),
    _code_desc("makefile", "makefile", "Makefile", "bi-hammer", False),
    _code_desc("gitignore", "ignore", "Git Ignore", "bi-git", False),
    _code_desc("gitattributes", "ignore", "Git Attributes", "bi-git", False),
    _code_desc("txt", "plaintext", "Plain Text", "bi-file-text", False),
    _code_desc("log", "log", "Log File", "bi-journal-text", False),
    # 5. Документация Markdown (Split-View: Код + Живой предпросмотр)
    FileTypeDescriptor(
        extension="md",
        language_id="markdown",
        display_name="Markdown",
        default_mode=EditorMode.MARKDOWN,
        supported_modes=[EditorMode.MARKDOWN, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/markdown",
        icon_class="bi-markdown-fill",
        is_binary_default=False,
        supports_formatting=True,
    ),
    FileTypeDescriptor(
        extension="markdown",
        language_id="markdown",
        display_name="Markdown",
        default_mode=EditorMode.MARKDOWN,
        supported_modes=[EditorMode.MARKDOWN, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/markdown",
        icon_class="bi-markdown-fill",
        is_binary_default=False,
        supports_formatting=True,
    ),
    FileTypeDescriptor(
        extension="mdx",
        language_id="markdown",
        display_name="MDX Document",
        default_mode=EditorMode.MARKDOWN,
        supported_modes=[EditorMode.MARKDOWN, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/markdown",
        icon_class="bi-markdown-fill",
        is_binary_default=False,
        supports_formatting=True,
    ),
    FileTypeDescriptor(
        extension="rst",
        language_id="restructuredtext",
        display_name="reStructuredText",
        default_mode=EditorMode.MARKDOWN,
        supported_modes=[EditorMode.MARKDOWN, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/x-rst",
        icon_class="bi-file-earmark-richtext",
        is_binary_default=False,
        supports_formatting=False,
    ),
    # 6. Табличные файлы (Grid View + Raw Text)
    FileTypeDescriptor(
        extension="csv",
        language_id="csv",
        display_name="CSV Table",
        default_mode=EditorMode.TABULAR,
        supported_modes=[EditorMode.TABULAR, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/csv",
        icon_class="bi-filetype-csv",
        is_binary_default=False,
        supports_formatting=True,
    ),
    FileTypeDescriptor(
        extension="tsv",
        language_id="tsv",
        display_name="TSV Table",
        default_mode=EditorMode.TABULAR,
        supported_modes=[EditorMode.TABULAR, EditorMode.CODE, EditorMode.HEX],
        mime_type="text/tab-separated-values",
        icon_class="bi-table",
        is_binary_default=False,
        supports_formatting=True,
    ),
    # 7. Интерактивные блокноты Jupyter (.ipynb)
    FileTypeDescriptor(
        extension="ipynb",
        language_id="json",
        display_name="Jupyter Notebook",
        default_mode=EditorMode.NOTEBOOK,
        supported_modes=[EditorMode.NOTEBOOK, EditorMode.CODE, EditorMode.HEX],
        mime_type="application/x-ipynb+json",
        icon_class="bi-journal-code",
        is_binary_default=False,
        supports_formatting=True,
    ),
    # 8. Векторная графика SVG (XML-код + интерактивный холст)
    FileTypeDescriptor(
        extension="svg",
        language_id="xml",
        display_name="Scalable Vector Graphics (SVG)",
        default_mode=EditorMode.VECTOR_SVG,
        supported_modes=[EditorMode.VECTOR_SVG, EditorMode.CODE, EditorMode.IMAGE, EditorMode.HEX],
        mime_type="image/svg+xml",
        icon_class="bi-filetype-svg",
        is_binary_default=False,
        supports_formatting=True,
    ),
    # 9. Растровые изображения (Canvas Studio + Hex)
    *[
        FileTypeDescriptor(
            extension=ext,
            language_id="binary",
            display_name=f"Image ({ext.upper()})",
            default_mode=EditorMode.IMAGE,
            supported_modes=[EditorMode.IMAGE, EditorMode.HEX],
            mime_type=mime,
            icon_class="bi-file-earmark-image",
            is_binary_default=True,
            supports_formatting=False,
        )
        for ext, mime in [
            ("png", "image/png"),
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("gif", "image/gif"),
            ("webp", "image/webp"),
            ("bmp", "image/bmp"),
            ("ico", "image/x-icon"),
        ]
    ],
    # 10. Документы PDF (Wasm PDF Viewer & Markdown Extractor + Hex)
    FileTypeDescriptor(
        extension="pdf",
        language_id="pdf",
        display_name="PDF Document (Wasm Engine)",
        default_mode=EditorMode.PDF,
        supported_modes=[EditorMode.PDF, EditorMode.HEX],
        mime_type="application/pdf",
        icon_class="bi-file-earmark-pdf",
        is_binary_default=True,
        supports_formatting=False,
    ),
    # 11. Аудио и видео (Media Inspector + Hex)
    *[
        FileTypeDescriptor(
            extension=ext,
            language_id="binary",
            display_name=f"Media ({ext.upper()})",
            default_mode=EditorMode.MEDIA,
            supported_modes=[EditorMode.MEDIA, EditorMode.HEX],
            mime_type=mime,
            icon_class="bi-file-earmark-play",
            is_binary_default=True,
            supports_formatting=False,
        )
        for ext, mime in [
            ("mp3", "audio/mpeg"),
            ("wav", "audio/wav"),
            ("ogg", "audio/ogg"),
            ("mp4", "video/mp4"),
            ("webm", "video/webm"),
        ]
    ],
    # 12. Специальные бинарные файлы и WebAssembly (Hex Editor + Data Inspector)
    *[
        FileTypeDescriptor(
            extension=ext,
            language_id="binary",
            display_name=label,
            default_mode=EditorMode.HEX,
            supported_modes=[EditorMode.HEX, EditorMode.CODE],
            mime_type="application/octet-stream",
            icon_class="bi-file-earmark-binary",
            is_binary_default=True,
            supports_formatting=False,
        )
        for ext, label in [
            ("wasm", "WebAssembly Binary (.wasm)"),
            ("bin", "Binary Data (.bin)"),
            ("dat", "Data File (.dat)"),
            ("exe", "PE Executable (.exe)"),
            ("dll", "Dynamic Link Library (.dll)"),
            ("sqlite", "SQLite Database (.sqlite)"),
            ("db", "Database File (.db)"),
            ("zip", "ZIP Archive (.zip)"),
        ]
    ],
]


class SupportedFileCatalog:
    """Реестр типов файлов и определения оптимального режима редактирования."""

    _BY_EXT: Dict[str, FileTypeDescriptor] = {d.extension: d for d in _RAW_DESCRIPTORS}
    _SPECIAL_NAMES: frozenset[str] = frozenset(
        {"dockerfile", "makefile", ".gitignore", ".gitattributes", ".env"}
    )

    @classmethod
    def get_descriptor(cls, file_path_or_name: str, is_binary_detected: bool = False) -> FileTypeDescriptor:
        """Определяет дескриптор типа файла по его имени, расширению и признаку бинарности.

        Args:
            file_path_or_name: Имя файла или относительный путь.
            is_binary_detected: Обнаружены ли бинарные нулевые байты при чтении файла.

        Returns:
            Дескриптор `FileTypeDescriptor` с режимами редактирования VS Code.
        """
        name = Path(file_path_or_name).name.lower()
        if name in cls._SPECIAL_NAMES:
            special_key = name.lstrip(".")
            if special_key in cls._BY_EXT:
                return cls._BY_EXT[special_key]

        ext = Path(name).suffix.lstrip(".").lower()
        if ext in cls._BY_EXT:
            desc = cls._BY_EXT[ext]
            if is_binary_detected and not desc.is_binary_default and desc.default_mode == EditorMode.CODE:
                return desc.model_copy(update={"default_mode": EditorMode.HEX})
            return desc

        # Универсальный fallback: любой неизвестный файл редактируется как текст или в Hex-редакторе
        if is_binary_detected:
            return FileTypeDescriptor(
                extension=ext or "bin",
                language_id="binary",
                display_name=f"Binary ({ext.upper() if ext else 'RAW'})",
                default_mode=EditorMode.HEX,
                supported_modes=[EditorMode.HEX, EditorMode.CODE],
                mime_type="application/octet-stream",
                icon_class="bi-file-earmark-binary",
                is_binary_default=True,
                supports_formatting=False,
            )

        return FileTypeDescriptor(
            extension=ext or "txt",
            language_id="plaintext",
            display_name=f"Text ({ext.upper() if ext else 'Plain'})",
            default_mode=EditorMode.CODE,
            supported_modes=[EditorMode.CODE, EditorMode.HEX],
            mime_type="text/plain",
            icon_class="bi-file-earmark-text",
            is_binary_default=False,
            supports_formatting=False,
        )

    @classmethod
    def list_all(cls) -> List[Dict[str, object]]:
        """Возвращает сериализованный список всех поддерживаемых форматов."""
        return [d.model_dump() for d in _RAW_DESCRIPTORS]
