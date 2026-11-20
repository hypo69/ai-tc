
# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc UTILS - Html Module
# =============================================================================
# Description:
#   HTML conversion utilities. The module provides HTML escaping, parsing and namespace conversion
#   without requiring external HTML rendering libraries.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.html import html2escape
#
#     res = html2escape()
#     print(res)
# Example:
#    >>> from src.utils.convertors.html import html2escape
#    >>> html2escape('<p>Hello</p>')
#    '&lt;p&gt;Hello&lt;/p&gt;'
#
#
# File: html.py
# Project: ai-tc
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20
# =============================================================================

from __future__ import annotations
"""HTML conversion utilities.1"""

import html
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

from logger import logger


def html2escape(input_str: str) -> str:
    """Convert HTML markup into escaped HTML entities.

    :param input_str: HTML source string.
    :return: HTML string with escaped entities.
    """
    return html.escape(input_str)


def escape2html(input_str: str) -> str:
    """Decode HTML entities into ordinary HTML markup.

    :param input_str: String containing escaped HTML entities.
    :return: Decoded HTML string.
    """
    return html.unescape(input_str)


def html2dict(html_str: str) -> dict[str, str]:
    """Convert HTML elements into a dictionary of tag names and text.

    :param html_str: HTML source string.
    :return: Dictionary containing tag names and their text content.

    .. note::
        When multiple elements use the same tag, the last parsed value
        replaces the previous value.
    """

    class HTMLToDictParser(HTMLParser):
        """Parse HTML elements into a dictionary."""

        def __init__(self) -> None:
            super().__init__()
            self.result: dict[str, str] = {}
            self.current_tag: str | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self.current_tag = tag

        def handle_endtag(self, tag: str) -> None:
            self.current_tag = None

        def handle_data(self, data: str) -> None:
            if self.current_tag:
                value = data.strip()
                if value:
                    self.result[self.current_tag] = value

    parser = HTMLToDictParser()
    parser.feed(html_str)
    parser.close()

    return parser.result


def html2ns(html_str: str) -> SimpleNamespace:
    """Convert HTML elements into a SimpleNamespace object.

    :param html_str: HTML source string.
    :return: Namespace with HTML tag names as attributes.
    """
    html_dict = html2dict(html_str)
    return SimpleNamespace(**html_dict)


def html2pdf(html_str: str, pdf_file: str | Path) -> bool | None:
    """Convert HTML content into a PDF file using an optional backend.

    WeasyPrint is deliberately not imported during module initialization.

    :param html_str: HTML source string.
    :param pdf_file: Destination PDF file path.
    :return: True on success, None when the converter is unavailable
        or PDF generation fails.
    """
    try:
        from weasyprint import HTML

    except (ImportError, OSError) as ex:
        logger.warning(
            f'HTML to PDF conversion is unavailable: {ex}'
        )
        return None

    try:
        HTML(string=html_str).write_pdf(str(pdf_file))

        logger.info(f'PDF generated: {pdf_file}')
        return True

    except Exception as ex:
        logger.error(f'Error during PDF generation: {ex}')
        return None
