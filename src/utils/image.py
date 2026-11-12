# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Image Module
# =============================================================================
# Description:
#   Утилиты загрузки, сохранения, конвертации и наложения водяных знаков на изображения.
#
# Usage Examples:
#   CLI:
#     python -m src.utils.image
#   Python API:
#     from src.utils.image import ImageError, save_image
#
# File: image.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:40:00
# =============================================================================

"""Утилиты загрузки, сохранения, конвертации и наложения водяных знаков на изображения."""

from io import BytesIO
from pathlib import Path
import random
from typing import Optional, Tuple, Union

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont

from logger import logger

_IMAGE_DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=30.0, connect=10.0, sock_read=20.0)


class ImageError(Exception):
    """Специализированное исключение для ошибок обработки изображений."""
    pass


async def save_image_from_url(image_url: str, filename: Union[str, Path]) -> Optional[str]:
    """Асинхронно скачивает изображение по URL с явным таймаутом и сохраняет в локальный файл.

    Args:
        image_url (str): URL изображения для скачивания.
        filename (Union[str, Path]): Путь к файлу для сохранения.

    Returns:
        Optional[str]: Путь к сохраненному файлу.

    Raises:
        ImageError: Если не удалось скачать или сохранить изображение.
    """
    try:
        async with aiohttp.ClientSession(timeout=_IMAGE_DOWNLOAD_TIMEOUT) as session:
            async with session.get(image_url) as response:
                response.raise_for_status()
                image_data = await response.read()
    except Exception as ex:
        logger.error(f'Ошибка скачивания изображения с {image_url}', exc_info=True)
        raise ImageError(f'Failed to download image from {image_url}') from ex
    return await save_image(image_data, filename)


async def save_image(image_data: bytes, file_name: Union[str, Path], format: str = 'PNG') -> Optional[str]:
    """Асинхронно сохраняет бинарные данные изображения в указанном формате.

    Args:
        image_data (bytes): Бинарные данные изображения.
        file_name (Union[str, Path]): Путь к целевому файлу.
        format (str): Формат сохранения изображения (по умолчанию PNG).

    Returns:
        Optional[str]: Строковый путь к сохраненному файлу.

    Raises:
        ImageError: Если файл не удалось создать, сохранить или его размер равен 0 байт.
    """
    file_path = Path(file_name)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, 'wb') as file:
            await file.write(image_data)
        if not file_path.exists():
            logger.error(f'Файл {file_path} не был создан.')
            raise ImageError(f'File {file_path} was not created.')
        with Image.open(file_path) as img:
            img.save(file_path, format=format)
        if file_path.stat().st_size == 0:
            logger.error(f'Файл {file_path} сохранен, но имеет нулевой размер.')
            raise ImageError(f'File {file_path} saved, but its size is 0 bytes.')
        return str(file_path)
    except Exception as ex:
        logger.critical(f'Не удалось сохранить изображение {file_path}', exc_info=True)
        raise ImageError(f'Failed to save file {file_path}') from ex


def get_image_bytes(image_path: Path, raw: bool = True) -> Optional[Union[BytesIO, bytes]]:
    """Читает изображение через Pillow и возвращает его байты в формате JPEG.

    Args:
        image_path (Path): Путь к файлу изображения.
        raw (bool): Если True, возвращает объект BytesIO; иначе возвращает bytes.

    Returns:
        Optional[Union[BytesIO, bytes]]: Байты изображения в формате JPEG или None при ошибке.
    """
    try:
        with Image.open(image_path) as img:
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='JPEG')
            return img_byte_arr if raw else img_byte_arr.getvalue()
    except Exception:
        logger.error('Ошибка чтения изображения через Pillow:', exc_info=True)
        return None


def get_raw_image_data(file_name: Union[str, Path]) -> Optional[bytes]:
    """Читает сырые бинарные данные файла изображения, если он существует.

    Args:
        file_name (Union[str, Path]): Путь к файлу изображения.

    Returns:
        Optional[bytes]: Бинарные данные файла или None при отсутствии файла/ошибке.
    """
    file_path = Path(file_name)
    if not file_path.exists():
        logger.error(f'Файл {file_path} не существует.')
        return None
    try:
        return file_path.read_bytes()
    except Exception:
        logger.error(f'Ошибка чтения файла {file_path}', exc_info=True)
        return None


def random_image(root_path: Union[str, Path]) -> Optional[str]:
    """Рекурсивно ищет случайное изображение в указанной директории.

    Args:
        root_path (Union[str, Path]): Директория поиска изображений.

    Returns:
        Optional[str]: Путь к случайному изображению или None, если изображения не найдены.
    """
    root_path = Path(root_path)
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    image_files = [
        file_path
        for file_path in root_path.rglob('*')
        if file_path.is_file() and file_path.suffix.lower() in image_extensions
    ]
    if not image_files:
        logger.warning(f'Изображения не найдены в {root_path}.')
        return None
    return str(random.choice(image_files))


def add_text_watermark(
    image_path: Union[str, Path],
    watermark_text: str,
    output_path: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """Накладывает текстовый водяной знак по центру изображения.

    Args:
        image_path (Union[str, Path]): Путь к исходному изображению.
        watermark_text (str): Текст водяного знака.
        output_path (Optional[Union[str, Path]]): Путь для сохранения результата.

    Returns:
        Optional[str]: Путь к сохраненному изображению или None при ошибке.
    """
    image_path = Path(image_path)
    output_path = image_path if output_path is None else Path(output_path)
    try:
        with Image.open(image_path) as raw_img:
            image = raw_img.convert('RGBA')
        watermark_layer = Image.new('RGBA', image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)
        font_size = max(10, min(image.size) // 10)
        try:
            font = ImageFont.truetype('arial.ttf', size=font_size)
        except IOError:
            font = ImageFont.load_default()
            logger.warning('Шрифт arial.ttf не найден; используется шрифт по умолчанию.')
        if hasattr(draw, 'textsize'):
            text_width, text_height = draw.textsize(watermark_text, font=font)
        else:
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (image.width - text_width) // 2
        y = (image.height - text_height) // 2
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))
        watermarked_image = Image.alpha_composite(image, watermark_layer)
        watermarked_image.save(output_path)
        return str(output_path)
    except Exception:
        logger.error(f'Не удалось добавить текстовый водяной знак на {image_path}', exc_info=True)
        return None


def add_image_watermark(
    input_image_path: Path,
    watermark_image_path: Path,
    output_image_path: Optional[Path] = None,
) -> Optional[Path]:
    """Накладывает графический водяной знак на изображение и сохраняет результат.

    Args:
        input_image_path (Path): Путь к исходному изображению.
        watermark_image_path (Path): Путь к изображению водяного знака.
        output_image_path (Optional[Path]): Путь сохранения результата.

    Returns:
        Optional[Path]: Путь к сохраненному файлу или None при ошибке.
    """
    try:
        with Image.open(input_image_path) as base_image, Image.open(watermark_image_path) as raw_wm:
            watermark = raw_wm.convert('RGBA')
            position = base_image.size
            newsize = (max(1, int(position[0] * 8 / 100)), max(1, int(position[0] * 8 / 100)))
            watermark = watermark.resize(newsize)
            new_position = (position[0] - newsize[0] - 20, position[1] - newsize[1] - 20)
            transparent = Image.new(mode='RGBA', size=position, color=(0, 0, 0, 0))
            transparent.paste(base_image, (0, 0))
            transparent.paste(watermark, new_position, watermark)
            image_mode = base_image.mode
            if image_mode == 'RGB':
                transparent = transparent.convert(image_mode)
            else:
                transparent = transparent.convert('P')
            if output_image_path is None:
                output_image_path = input_image_path.parent / 'output' / input_image_path.name
            output_image_path.parent.mkdir(parents=True, exist_ok=True)
            transparent.save(output_image_path, optimize=True, quality=100)
            logger.info(f'Сохранение {output_image_path}...')
            return output_image_path
    except Exception as ex:
        logger.error(f'Не удалось добавить водяной знак на {input_image_path}: {ex}', exc_info=True)
        return None


def resize_image(
    image_path: Union[str, Path],
    size: Tuple[int, int],
    output_path: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """Изменяет размер изображения до заданных габаритов (ширина, высота).

    Args:
        image_path (Union[str, Path]): Путь к файлу изображения.
        size (Tuple[int, int]): Новые размеры (width, height).
        output_path (Optional[Union[str, Path]]): Путь для сохранения.

    Returns:
        Optional[str]: Путь к сохраненному изображению или None при ошибке.
    """
    image_path = Path(image_path)
    output_path = image_path if output_path is None else Path(output_path)
    try:
        with Image.open(image_path) as img:
            resized_img = img.resize(size)
            resized_img.save(output_path)
        return str(output_path)
    except Exception:
        logger.error(f'Не удалось изменить размер изображения {image_path}', exc_info=True)
        return None


def convert_image(
    image_path: Union[str, Path],
    format: str,
    output_path: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """Конвертирует изображение в указанный графический формат.

    Args:
        image_path (Union[str, Path]): Путь к файлу изображения.
        format (str): Целевой формат (например, 'JPEG', 'PNG').
        output_path (Optional[Union[str, Path]]): Путь сохранения результата.

    Returns:
        Optional[str]: Путь к конвертированному файлу или None при ошибке.
    """
    image_path = Path(image_path)
    output_path = image_path if output_path is None else Path(output_path)
    try:
        with Image.open(image_path) as img:
            img.save(output_path, format=format)
        return str(output_path)
    except Exception:
        logger.error(f'Не удалось конвертировать изображение {image_path}', exc_info=True)
        return None


def process_images_with_watermark(folder_path: Path, watermark_path: Path) -> None:
    """Пакетно накладывает водяной знак на все изображения в указанной папке.

    Args:
        folder_path (Path): Папка с исходными изображениями.
        watermark_path (Path): Путь к файлу водяного знака.
    """
    if not folder_path.is_dir():
        logger.error(f'Директория {folder_path} не существует.')
        return
    output_dir = folder_path / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_path in folder_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
            output_image_path = output_dir / file_path.name
            add_image_watermark(file_path, watermark_path, output_image_path)


if __name__ == '__main__':
    folder = Path(input('Введите путь к папке с изображениями: '))
    watermark = Path(input('Введите путь к водяному знаку: '))
    process_images_with_watermark(folder, watermark)
