# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Hardware Enricher
# =============================================================================
# Description:
#   Сервис интеллектуального AI-обогащения компонентов оборудования:
#   автоматический поиск официальных ссылок вендоров и изображений компонентов
#   через LLM/GoogleGenerativeAI с сохранением в таблицу hardware_components базы telemetry.db.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.hardware_enricher import HardwareEnricher
#
#     enricher = HardwareEnricher(storage)
#     enricher.sync_nodes(nodes)
#     enricher.start_background_enrichment()
#
# File: hardware_enricher.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 09:30:00
# =============================================================================

from __future__ import annotations
"""Сервис синхронизации жизненного цикла аппаратных компонентов (опрос внешних спецификаций вендоров отключен)."""

import asyncio
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from logger import logger
from .models import HardwareNode

if TYPE_CHECKING:
    from apps.windows.telemetry.sqlite import TelemetryStorage


def generate_hardware_component_id(
    category: str,
    name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """Генерирует уникальный аппаратный идентификатор компонента на основе физических признаков.

    Для дисков, памяти, процессора, сетевых адаптеров и мониторов приоритетно
    используются неизменяемые аппаратные признаки (Serial Number, MAC, PNP ID, CPUID/ProcessorId),
    что позволяет безошибочно узнать компонент при его повторном подключении в систему.

    Args:
        category: Категория оборудования (напр. Processor (CPU), Physical Disk, RAM).
        name: Название устройства или компонента.
        properties: Словарь собранных характеристик компонента.

    Returns:
        str: Стабильный уникальный строковый ключ компонента.
    """
    props = properties or {}
    clean_cat = re.sub(r"[^a-zA-Z0-9]+", "_", category or "hw").strip("_").lower()

    # 1. Поиск аппаратного серийного номера (диски, планки памяти, мат. платы, мониторы)
    serial = (
        props.get("Серийный номер")
        or props.get("Serial Number")
        or props.get("Серийный номер платы")
        or props.get("Серийный номер накопителя")
        or props.get("Серийный номер дисплея (EDID)")
    )
    if serial and str(serial).strip().lower() not in {"none", "n/a", "default string", "to be filled by o.e.m.", "0", "00000000", ""}:
        clean_sn = re.sub(r"[^a-zA-Z0-9]+", "_", str(serial)).strip("_").lower()
        if len(clean_sn) >= 4:
            return f"{clean_cat}_sn_{clean_sn}"[:96]

    # 2. Сетевые адаптеры: постоянный физический MAC-адрес
    mac = props.get("MAC-адрес") or props.get("Физический MAC") or props.get("MAC Address")
    if mac and str(mac).strip().lower() not in {"none", "n/a", ""}:
        clean_mac = re.sub(r"[^a-zA-Z0-9]+", "", str(mac)).lower()
        if len(clean_mac) == 12:
            return f"net_mac_{clean_mac}"

    # 3. Процессор: Socket + ProcessorId / CPUID
    if "processor" in clean_cat or "cpu" in clean_cat:
        proc_id = props.get("Кодовый идентификатор (ProcessorId)") or props.get("Идентификатор CPUID")
        socket_name = props.get("Разъем (Socket)") or props.get("Сокет") or ""
        if proc_id:
            clean_pid = re.sub(r"[^a-zA-Z0-9]+", "_", str(proc_id)).strip("_").lower()
            clean_sock = re.sub(r"[^a-zA-Z0-9]+", "_", str(socket_name)).strip("_").lower()
            sock_prefix = f"{clean_sock}_" if clean_sock else ""
            return f"cpu_{sock_prefix}{clean_pid}"[:96]

    # 4. PNP Device ID / Device Instance Path для PCI и USB устройств
    pnp = props.get("PNP Device ID") or props.get("Идентификатор PNP") or props.get("Идентификатор экземпляра (Device Instance Path)")
    if pnp and str(pnp).strip():
        clean_pnp = re.sub(r"[^a-zA-Z0-9]+", "_", str(pnp)).strip("_").lower()
        if len(clean_pnp) >= 6:
            return f"{clean_cat}_{clean_pnp}"[:96]

    # 5. Fallback на нормализованную категорию и имя
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", name or "dev").strip("_").lower()
    return f"{clean_cat}_{clean_name}"[:96]


def generate_component_key(category: str, name: str, properties: Optional[Dict[str, Any]] = None) -> str:
    """Алиас для обратной совместимости."""
    return generate_hardware_component_id(category, name, properties)


def is_valid_http_url(url: Optional[str]) -> bool:
    """Проверяет валидность URL адреса (http:// или https://)."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if u.lower() == "n/a" or len(u) < 10:
        return False
    return bool(re.match(r"^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$", u, re.IGNORECASE))


class HardwareEnricher:
    """Сервис AI-обогащения базы данных оборудования официальными ссылками и медиа."""

    _is_running: bool = False

    def __init__(self, storage: Optional[TelemetryStorage] = None) -> None:
        """Инициализирует сервис обогащения.

        Args:
            storage: Экземпляр TelemetryStorage SQLite.
        """
        self._storage = storage

    def _get_storage(self) -> TelemetryStorage:
        """Ленивое получение экземпляра TelemetryStorage."""
        if self._storage is None:
            from apps.windows.telemetry.sqlite import TelemetryStorage
            self._storage = TelemetryStorage()
        return self._storage

    def sync_nodes(self, nodes: List[HardwareNode]) -> None:
        """Синхронизирует узлы оборудования с таблицей hardware_components в telemetry.db.

        Отслеживает статус присутствия (установлен/удален/переустановлен),
        сохраняет параметры в SQLite без затирания уже найденных ссылок,
        и подставляет существующие ссылки вендора и медиа в объекты узлов.

        Args:
            nodes: Список узлов HardwareNode для синхронизации.
        """
        storage = self._get_storage()
        components_to_sync: List[Dict[str, Any]] = []

        for node in nodes:
            props = node.properties or {}
            c_key = generate_hardware_component_id(node.category, node.name, props)
            node.component_key = c_key

            # Извлечение производителя и модели из свойств
            vendor = (
                props.get("Производитель (Вендор)")
                or props.get("Производитель (Бренд)")
                or props.get("Производитель платы")
                or props.get("Производитель")
                or props.get("OEM Производитель ПК")
                or props.get("Вендор (Vendor ID)")
                or ""
            )
            model = (
                props.get("Модель процессора")
                or props.get("Модель накопителя")
                or props.get("Модель видеокарты")
                or props.get("Модель платы")
                or props.get("Модель компьютера")
                or props.get("Модель адаптера")
                or props.get("Название дисплея (EDID)")
                or node.name
            )

            from .production_date_agent import HardwareProductionDateAgent
            date_agent = HardwareProductionDateAgent()

            # Проверяем, есть ли запись в БД
            existing = storage.get_hardware_component_by_key(c_key)
            node.vendor_url = None
            node.enrichment_status = "completed"

            if existing:
                # Подставляем сохраненную дату производства
                p_date = existing.get("production_date")
                p_source = existing.get("production_date_source")
                if p_date and p_date != "N/A":
                    node.production_date = p_date
                    node.production_date_source = p_source
                    node.properties["Дата производства"] = p_date
                else:
                    # Экспресс-декодирование даты по серийному номеру
                    dec_res = date_agent.decode_serial(vendor, model, properties=props, category=node.category)
                    if dec_res and dec_res.get("production_date"):
                        node.production_date = dec_res["production_date"]
                        node.production_date_source = dec_res.get("production_source")
                        node.properties["Дата производства"] = dec_res["production_date"]
                        storage.update_hardware_component_production_date(
                            component_key=c_key,
                            production_date=dec_res["production_date"],
                            source=dec_res.get("production_source"),
                            status="completed",
                        )

                # Подставляем атрибуты жизненного цикла в узел
                node.is_present = bool(existing.get("is_present", 1))
                node.install_count = existing.get("install_count", 1) or 1
                node.first_seen = existing.get("first_seen")
                node.last_seen = existing.get("last_seen")
                node.removed_at = existing.get("removed_at")

                components_to_sync.append({
                    "component_key": c_key,
                    "category": node.category,
                    "name": node.name,
                    "vendor": vendor,
                    "model": model,
                    "properties_json": props,
                    "vendor_url": None,
                    "enrichment_status": "completed",
                })
            else:
                # Экспресс-декодирование даты для нового компонента
                dec_res = date_agent.decode_serial(vendor, model, properties=props, category=node.category)
                prod_date = dec_res.get("production_date") if dec_res else None
                prod_source = dec_res.get("production_source") if dec_res else None
                if prod_date:
                    node.production_date = prod_date
                    node.production_date_source = prod_source
                    node.properties["Дата производства"] = prod_date

                # Новая запись - сохраняем со статусом completed (опрос спецификаций запрещен)
                components_to_sync.append({
                    "component_key": c_key,
                    "category": node.category,
                    "name": node.name,
                    "vendor": vendor,
                    "model": model,
                    "properties_json": props,
                    "vendor_url": None,
                    "production_date": prod_date,
                    "production_date_source": prod_source,
                    "production_date_status": "completed" if prod_date else "completed",
                    "enrichment_status": "completed",
                })

        # Синхронизация жизненного цикла компонентов в БД (установка, переустановка, удаление)
        if components_to_sync:
            storage.sync_hardware_components_lifecycle(components_to_sync)

    def start_background_enrichment(self) -> None:
        """Опрос и сбор спецификаций от вендора полностью запрещены."""
        return

    async def enrich_pending_components_async(self, max_items: int = 15) -> int:
        """Опрос и сбор спецификаций от вендора полностью запрещены."""
        return 0

