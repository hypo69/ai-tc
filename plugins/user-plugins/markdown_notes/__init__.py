# -*- coding: utf-8 -*-
from typing import Any, Optional
from .plugin import MarkdownNotesPlugin


def plugin(ai_model: Any = None, config: Optional[dict] = None) -> MarkdownNotesPlugin:
    """Фабричная функция создания экземпляра плагина."""
    return MarkdownNotesPlugin(ai_model=ai_model, config=config)


__all__ = ["MarkdownNotesPlugin", "plugin"]
