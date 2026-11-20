# -*- coding: utf-8 -*-
# Updated: 2026-11-20 16:45:00
"""router.py – FastAPI роутер для модуля programms_history_deep_researh.

Точка доступа `/api/v1/windows/program-history/report` возвращает JSON‑отчёт,
сгенерированный `report.generate_report()`.
"""

from fastapi import APIRouter
from .report import generate_report

router = APIRouter(prefix="/program-history", tags=["program-history"])

@router.get('/report')
async def get_program_history_report():
    """Возвращает полный отчёт о программах и их артефактах."""
    return generate_report()

