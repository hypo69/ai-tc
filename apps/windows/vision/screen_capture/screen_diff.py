# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Screen Diff Engine
# =============================================================================
# Description:
#   Детектор визуальных изменений между последовательными кадрами экрана,
#   расчет метрик расхождения (diff ratio) и локализация зон активности.
#
# Usage Examples:
#   from apps.windows.vision.screen_capture.screen_diff import ScreenDiffEngine
#   diff_engine = ScreenDiffEngine(threshold=0.02)
#   ratio, bbox = diff_engine.compute_diff(frame1, frame2)
#
# File: screen_diff.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:50:00
# =============================================================================

from __future__ import annotations
"""Движок анализа визуальных различий кадров и детекции изменений."""

import math
from typing import Optional, Tuple
from PIL import Image, ImageChops


class ScreenDiffEngine:
    """Анализатор визуальных изменений кадров (Screen Diff)."""

    def __init__(self, threshold: float = 0.02) -> None:
        """
        Инициализация детектора.

        Args:
            threshold: Порог значимого изменения (по умолчанию 2% площади).
        """
        self.threshold = threshold

    def compute_diff(
        self,
        img1: Optional[Image.Image],
        img2: Optional[Image.Image],
        downsample_size: Tuple[int, int] = (160, 90),
    ) -> Tuple[float, Optional[Tuple[int, int, int, int]]]:
        """
        Вычисляет долю изменившихся пикселей и ограничивающий прямоугольник (bbox) изменений.

        Args:
            img1: Предыдущий снимок.
            img2: Текущий снимок.
            downsample_size: Размерность миниатюры для быстрого сравнения без нагрузки на CPU.

        Returns:
            Tuple[float, Optional[Tuple[int, int, int, int]]]:
                - diff_ratio (0.0 .. 1.0): Доля изменившихся пикселей.
                - bbox (left, top, right, bottom) в исходных координатах img2 или None.
        """
        if img1 is None or img2 is None:
            return 1.0, None

        # Приводим к одному размеру при необходимости
        if img1.size != img2.size:
            return 1.0, (0, 0, img2.width, img2.height)

        # Быстрый расчет доли изменений через downsample
        try:
            thumb1 = img1.resize(downsample_size, Image.Resampling.NEAREST).convert("L")
            thumb2 = img2.resize(downsample_size, Image.Resampling.NEAREST).convert("L")
            diff_thumb = ImageChops.difference(thumb1, thumb2)

            # Подсчет изменившихся пикселей через tobytes() без предупреждений Pillow
            raw_bytes = diff_thumb.tobytes()
            diff_pixels = sum(1 for b in raw_bytes if b > 10)
            total_pixels = len(raw_bytes)
            diff_ratio = round(diff_pixels / total_pixels, 4) if total_pixels > 0 else 0.0

            # Если изменения несущественны, не тратим ресурсы на поиск полного bbox
            if diff_ratio < 0.001:
                return 0.0, None

            # Определение ориентировочного bbox на исходном изображении
            thumb_bbox = diff_thumb.getbbox()
            if not thumb_bbox:
                return diff_ratio, None

            scale_x = img2.width / downsample_size[0]
            scale_y = img2.height / downsample_size[1]

            real_bbox = (
                int(thumb_bbox[0] * scale_x),
                int(thumb_bbox[1] * scale_y),
                min(img2.width, int(thumb_bbox[2] * scale_x)),
                min(img2.height, int(thumb_bbox[3] * scale_y)),
            )

            return diff_ratio, real_bbox

        except Exception:
            return 0.0, None

    def is_significant_change(self, diff_ratio: float) -> bool:
        """Определяет, превышает ли изменение установленный порог чувствительности."""
        return diff_ratio >= self.threshold

    def compute_root_mean_square(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        Вычисляет RMS (среднеквадратичную разность цветов) между двумя изображениями.

        Returns:
            float: Значение ошибки от 0.0 (идентичны) до 255.0.
        """
        try:
            diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
            h = diff.histogram()
            # Сумма квадратов разностей
            sq = (
                value * ((idx % 256) ** 2)
                for idx, value in enumerate(h)
            )
            sum_of_squares = sum(sq)
            rms = math.sqrt(sum_of_squares / float(img1.size[0] * img1.size[1] * 3))
            return round(rms, 2)
        except Exception:
            return 0.0
