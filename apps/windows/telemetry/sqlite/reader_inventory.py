# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryInventoryReaderMixin
# =============================================================================
# Description:
#   Миксин чтения инвентаризации и сэмплов оборудования из консолидированных
#   таблиц: hardware_components, hardware_component_history, sensor_polls,
#   process_file_events, incidents и system_snapshots.
#
# File: reader_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:15:00
# =============================================================================

from __future__ import annotations

"""Миксин чтения инвентаризации и телеметрии оборудования из 12 базовых таблиц SQLite."""

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional


def _read_hw_components(
    cm: Any,
    category: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Вспомогательная функция чтения компонентов из hardware_components с распаковкой specs_json."""
    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM hardware_components WHERE category = ? AND (status IS NULL OR status != 'REMOVED') ORDER BY id ASC"
        params: List[Any] = [category]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        cursor.execute(sql, tuple(params))
        results: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            d = dict(row)
            specs = {}
            if d.get("specs_json"):
                try:
                    specs = json.loads(d["specs_json"])
                except Exception:
                    specs = {}
            merged = {
                **d,
                **specs,
                "id": d["id"],
                "first_seen": d["first_seen"],
                "last_seen": d["last_seen"],
                "updated_at": d["updated_at"],
            }
            if "name" not in merged or not merged["name"]:
                merged["name"] = d.get("name")
            results.append(merged)
        return results


def _read_sensor_samples(
    cm: Any,
    sensor_category: str,
    limit: int = 100,
    since_epoch: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Вспомогательная функция чтения исторических сэмплов из sensor_polls с распаковкой raw_json."""
    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        if since_epoch is not None:
            cursor.execute(
                "SELECT * FROM sensor_polls WHERE sensor_category = ? AND created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (sensor_category, float(since_epoch), int(limit)),
            )
        else:
            cursor.execute(
                "SELECT * FROM sensor_polls WHERE sensor_category = ? ORDER BY created_at DESC LIMIT ?",
                (sensor_category, int(limit)),
            )
        results: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            d = dict(row)
            raw = {}
            if d.get("raw_json"):
                try:
                    raw = json.loads(d["raw_json"])
                except Exception:
                    raw = {}
            merged = {
                "id": d["id"],
                "timestamp": d["timestamp"],
                "created_at": d["created_at"],
                **raw,
            }
            results.append(merged)
        return results


class TelemetryInventoryReaderMixin:
    """Миксин чтения инвентаризации и сэмплов оборудования из консолидированных таблиц."""

    def get_device_events(
        self,
        event_type: Optional[str] = None,
        device_instance_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю событий оборудования из таблицы incidents."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["domain = 'device_event'"]
            params: List[Any] = []
            if device_instance_id:
                conditions.append("device_id = ?")
                params.append(device_instance_id)
            if event_type:
                conditions.append("trigger_type = ?")
                params.append(event_type)
            where_sql = " WHERE " + " AND ".join(conditions)
            cursor.execute(
                f"SELECT * FROM incidents{where_sql} ORDER BY created_at DESC LIMIT ?",
                (*params, int(limit)),
            )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                details = {}
                if d.get("details_json"):
                    try:
                        details = json.loads(d["details_json"])
                    except Exception:
                        details = {}
                dev_id = d.get("device_id") or details.get("device_instance_id") or details.get("device_id")
                results.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "device_id": dev_id,
                    "device_instance_id": dev_id,
                    "event_type": d.get("trigger_type") or details.get("event_type"),
                    "friendly_name": d.get("title") or details.get("friendly_name"),
                    **details,
                })
            return results

    def get_device_install_date(self, device_instance_id: str) -> Optional[str]:
        """Возвращает сохраненную дату установки PnP-устройства из hardware_components."""
        if not device_instance_id:
            return None
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT specs_json, first_seen FROM hardware_components WHERE category = 'pnp_device' AND component_key = ? LIMIT 1;",
                (device_instance_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            if row["specs_json"]:
                try:
                    specs = json.loads(row["specs_json"])
                    if specs.get("install_date"):
                        return str(specs["install_date"])
                except Exception:
                    pass
            return row["first_seen"]

    def get_disk_io_events(
        self,
        pid: Optional[int] = None,
        disk_id: Optional[int] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает события дискового ввода-вывода из таблицы process_file_events."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if pid is not None:
                conditions.append("pid = ?")
                params.append(pid)
            if since_epoch is not None:
                conditions.append("created_at >= ?")
                params.append(float(since_epoch))
            where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            cursor.execute(
                f"SELECT * FROM process_file_events{where_sql} ORDER BY created_at DESC LIMIT ?",
                (*params, int(limit) * 2 if disk_id is not None else int(limit)),
            )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                details = {}
                if d.get("details_json"):
                    try:
                        details = json.loads(d["details_json"])
                    except Exception:
                        details = {}
                if disk_id is not None and details.get("disk_index") != disk_id and details.get("disk_id") != disk_id:
                    continue
                results.append({
                    "id": d["event_id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "pid": d["pid"],
                    "name": d.get("process_name"),
                    "operation": d.get("operation_type"),
                    "file_path": d.get("file_path"),
                    "bytes_count": d.get("bytes_transferred"),
                    "io_rate_bytes_sec": d.get("io_rate_bytes_sec"),
                    **details,
                })
                if len(results) >= limit:
                    break
            return results

    def get_disk_inventory(self, disk_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлекает список физических накопителей из hardware_components."""
        items = _read_hw_components(self._cm, "disk")
        if disk_id is not None:
            items = [i for i in items if i.get("disk_index") == disk_id or i.get("disk_id") == disk_id]
        items.sort(key=lambda x: int(x.get("disk_index") or 0))
        return items

    def get_volume_inventory(self) -> List[Dict[str, Any]]:
        """Извлекает список логических томов из hardware_components."""
        items = _read_hw_components(self._cm, "volume")
        items.sort(key=lambda x: str(x.get("drive_letter") or ""))
        return items

    def get_disk_health_history(
        self,
        disk_id: Optional[int] = None,
        serial_number: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю SMART-показателей и здоровья дисков из sensor_polls."""
        samples = _read_sensor_samples(self._cm, "smart", limit=limit * 2, since_epoch=since_epoch)
        if disk_id is not None:
            samples = [s for s in samples if s.get("disk_index") == disk_id or s.get("disk_id") == disk_id]
        if serial_number:
            samples = [s for s in samples if s.get("serial_number") == serial_number]
        return samples[:limit]

    def get_disk_performance_samples(
        self,
        disk_name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю производительности дисков из sensor_polls."""
        samples = _read_sensor_samples(self._cm, "disk_perf", limit=limit * 2, since_epoch=since_epoch)
        if disk_name:
            samples = [
                s for s in samples
                if disk_name in str(s.get("disk_name") or s.get("volume_letter") or s.get("disk_index") or "")
            ]
        return samples[:limit]

    def _probe_and_persist_cpu_inventory(self, cursor: sqlite3.Cursor) -> Dict[str, Any]:
        """Опрашивает CPU через последний снимок при пустой таблице hardware_components."""
        cursor.execute("SELECT raw_json FROM system_snapshots WHERE raw_json IS NOT NULL ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row and row[0]:
            try:
                snap = json.loads(row[0])
                cpu = snap.get("cpu") or {}
                if isinstance(cpu, dict) and (cpu.get("model") or cpu.get("name")):
                    return {
                        "processor_id": 0,
                        "name": cpu.get("model") or cpu.get("name"),
                        "vendor": cpu.get("vendor") or "",
                        "architecture": cpu.get("architecture") or "",
                        "physical_cores": int(cpu.get("cores_physical") or cpu.get("physical_cores") or 0),
                        "logical_cores": int(cpu.get("cores_logical") or cpu.get("logical_cores") or 0),
                        "base_frequency_mhz": float(cpu.get("frequency_mhz") or 0.0),
                        "max_frequency_mhz": float(cpu.get("frequency_max_mhz") or 0.0),
                    }
            except Exception:
                pass
        return {}

    def get_cpu_inventory(self, processor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлекает спецификацию процессоров из hardware_components."""
        items = _read_hw_components(self._cm, "cpu")
        if processor_id is not None:
            items = [i for i in items if i.get("processor_id") == processor_id]
        items.sort(key=lambda x: int(x.get("processor_id") or 0))
        return items

    def get_cpu_telemetry_samples(
        self,
        processor_id: Optional[int] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю телеметрии процессора из sensor_polls или system_snapshots."""
        samples = _read_sensor_samples(self._cm, "cpu_telemetry", limit=limit * 2, since_epoch=since_epoch)
        if processor_id is not None:
            samples = [s for s in samples if s.get("processor_id", 0) == processor_id]
        if samples:
            return samples[:limit]
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            sql = '''
                SELECT id, timestamp, created_at, 0 AS processor_id,
                       cpu_total_percent AS total_percent,
                       cpu_frequency_mhz AS frequency_current_mhz,
                       cpu_temp_c AS temperature_c,
                       cpu_power_w AS package_power_w
                FROM system_snapshots
            '''
            params: List[Any] = []
            if since_epoch is not None:
                sql += " WHERE created_at >= ?"
                params.append(float(since_epoch))
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            cursor.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def get_ram_module_inventory(self) -> List[Dict[str, Any]]:
        """Извлекает спецификации физических модулей RAM из hardware_components."""
        items = _read_hw_components(self._cm, "ram")
        items.sort(key=lambda x: (str(x.get("bank_label") or ""), str(x.get("device_locator") or "")))
        return items

    def get_ram_telemetry_samples(
        self,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю состояния оперативной памяти из sensor_polls или system_snapshots."""
        samples = _read_sensor_samples(self._cm, "ram_telemetry", limit=limit, since_epoch=since_epoch)
        if samples:
            return samples
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            sql = '''
                SELECT id, timestamp, created_at,
                       memory_total_gb AS total_gb,
                       memory_used_gb AS used_gb,
                       memory_percent AS percent_used,
                       swap_percent
                FROM system_snapshots
            '''
            params: List[Any] = []
            if since_epoch is not None:
                sql += " WHERE created_at >= ?"
                params.append(float(since_epoch))
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            cursor.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def get_gpu_inventory(self, gpu_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлекает спецификации видеокарт (GPU) из hardware_components с дедупликацией."""
        items = _read_hw_components(self._cm, "gpu")
        if not items:
            return []

        # Дедупликация адаптеров: объединяем по нормализованному названию/модели
        seen_keys: Dict[str, Dict[str, Any]] = {}
        stale_ids_to_clean: List[int] = []

        for it in items:
            raw_name = str(it.get("name") or "").strip()
            raw_vendor = str(it.get("vendor") or "").strip().lower()
            pnp = str(it.get("pnp_device_id") or "").strip().lower()

            if pnp:
                key = f"pnp:{pnp}"
            else:
                norm_n = re.sub(r"\((r|tm)\)", "", raw_name, flags=re.IGNORECASE).lower().strip()
                if raw_vendor and raw_vendor not in norm_n:
                    norm_n = f"{raw_vendor} {norm_n}"
                key = re.sub(r"[^a-z0-9]+", "_", norm_n).strip("_")

            # Проверяем также нечеткое совпадение ключа (например, geforce_gt_710 и nvidia_geforce_gt_710)
            existing_match_key = None
            for prev_key in list(seen_keys.keys()):
                if prev_key == key or (len(key) > 6 and (key in prev_key or prev_key in key)):
                    existing_match_key = prev_key
                    break

            if existing_match_key:
                prev_item = seen_keys[existing_match_key]
                cur_updated = float(it.get("updated_at") or 0.0)
                prev_updated = float(prev_item.get("updated_at") or 0.0)
                if cur_updated > prev_updated:
                    if prev_item.get("id"):
                        stale_ids_to_clean.append(int(prev_item["id"]))
                    del seen_keys[existing_match_key]
                    seen_keys[key] = it
                else:
                    if it.get("id"):
                        stale_ids_to_clean.append(int(it["id"]))
            else:
                seen_keys[key] = it

        # Асинхронно или безопасно очищаем найденные устаревшие дубли из БД
        if stale_ids_to_clean:
            try:
                with self._cm.lock, self._cm.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"DELETE FROM hardware_components WHERE category = 'gpu' AND id IN ({','.join(['?']*len(stale_ids_to_clean))})",
                        tuple(stale_ids_to_clean)
                    )
            except Exception:
                pass

        unique_items = list(seen_keys.values())
        if gpu_id is not None:
            unique_items = [i for i in unique_items if i.get("gpu_index") == gpu_id or i.get("gpu_id") == gpu_id]

        # Стабильная сортировка: дискретные видеокарты (NVIDIA/AMD) первыми, встроенные вторыми
        def _sort_key(x: Dict[str, Any]) -> tuple:
            v = str(x.get("vendor") or "").upper()
            n = str(x.get("name") or "").upper()
            is_discrete = 0 if ("NVIDIA" in v or "GEFORCE" in n or "AMD" in v or "RADEON" in n) else 1
            orig_idx = int(x.get("gpu_index") if x.get("gpu_index") is not None else (x.get("gpu_id") or 0))
            return (is_discrete, orig_idx)

        unique_items.sort(key=_sort_key)
        for new_idx, it in enumerate(unique_items):
            it["gpu_index"] = new_idx
            it["gpu_id"] = new_idx

        return unique_items

    def get_gpu_telemetry_samples(
        self,
        gpu_id: Optional[int] = None,
        name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю телеметрии видеокарты из sensor_polls или system_snapshots."""
        samples = _read_sensor_samples(self._cm, "gpu_telemetry", limit=limit * 2, since_epoch=since_epoch)
        if gpu_id is not None:
            samples = [s for s in samples if s.get("gpu_index") == gpu_id or s.get("gpu_id") == gpu_id]
        if name:
            samples = [s for s in samples if name.lower() in str(s.get("name") or "").lower()]
        if samples:
            return samples[:limit]
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            sql = '''
                SELECT id, timestamp, created_at, 0 AS gpu_index,
                       gpu_load_percent AS load_percent,
                       gpu_temp_c AS temperature_gpu_c,
                       gpu_vram_used_mb AS memory_used_mb
                FROM system_snapshots
            '''
            params: List[Any] = []
            if since_epoch is not None:
                sql += " WHERE created_at >= ?"
                params.append(float(since_epoch))
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            cursor.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def get_network_adapter_inventory(self) -> List[Dict[str, Any]]:
        """Извлекает список сетевых адаптеров из hardware_components."""
        items = _read_hw_components(self._cm, "network")
        items.sort(key=lambda x: (not bool(x.get("is_up")), str(x.get("interface_name") or "")))
        return items

    def get_network_adapter_samples(
        self,
        adapter_name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю трафика сетевых адаптеров из sensor_polls или system_snapshots."""
        samples = _read_sensor_samples(self._cm, "net_telemetry", limit=limit * 2, since_epoch=since_epoch)
        if adapter_name:
            samples = [
                s for s in samples
                if adapter_name.lower() in str(s.get("interface_name") or s.get("adapter_name") or "").lower()
            ]
        if samples:
            return samples[:limit]
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            sql = '''
                SELECT id, timestamp, created_at, 'Total' AS interface_name,
                       network_sent_bytes_sec AS bytes_sent_sec,
                       network_recv_bytes_sec AS bytes_recv_sec
                FROM system_snapshots
            '''
            params: List[Any] = []
            if since_epoch is not None:
                sql += " WHERE created_at >= ?"
                params.append(float(since_epoch))
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            cursor.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def get_monitor_inventory(self) -> List[Dict[str, Any]]:
        """Извлекает спецификации подключенных мониторов и дисплеев из hardware_components или system_snapshots."""
        items = _read_hw_components(self._cm, "Monitors & Displays")
        if items:
            monitors: List[Dict[str, Any]] = []
            seen_devices: set = set()
            # Обходим в обратном порядке (от самых свежих id), чтобы брать наиболее актуальные данные по каждому устройству
            for it in reversed(items):
                if it.get("status") == "REMOVED" or it.get("is_present") == 0:
                    continue
                props = it.get("properties_json") or {}
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        props = {}
                dev = props.get("Устройство") or it.get("component_key") or ""
                if dev in seen_devices:
                    continue
                seen_devices.add(dev)
                res = str(props.get("Разрешение экрана", "")).split("x")
                w = int(res[0].strip()) if len(res) == 2 and res[0].strip().isdigit() else 1920
                h = int(res[1].strip()) if len(res) == 2 and res[1].strip().isdigit() else 1080
                freq_str = str(props.get("Частота развертки", "")).replace("Hz", "").strip()
                freq = int(freq_str) if freq_str.isdigit() else 60
                is_prim = "Основной" in str(props.get("Основной монитор", ""))
                monitors.append({
                    "device": dev,
                    "name": props.get("Название дисплея (EDID)") or it.get("model") or it.get("name") or "Display Monitor",
                    "vendor": it.get("vendor") or props.get("Производитель", ""),
                    "adapter": props.get("Подключенный видеоадаптер", ""),
                    "width": w,
                    "height": h,
                    "frequency_hz": freq,
                    "bits_per_pixel": 32,
                    "is_primary": is_prim,
                    "orientation": props.get("Ориентация", "горизонтальная"),
                    "serial_number": props.get("Серийный номер (S/N)", ""),
                    "production_date": it.get("production_date"),
                })
            if monitors:
                monitors.reverse()
                return monitors

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT monitors_json FROM system_snapshots WHERE monitors_json IS NOT NULL ORDER BY id DESC LIMIT 1;"
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass
        return []

    def get_hardware_components(
        self,
        include_removed: bool = True,
        only_present: bool = False,
    ) -> List[Dict[str, Any]]:
        """Извлекает зарегистрированные аппаратные компоненты из таблицы hardware_components."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hardware_components ORDER BY category, name;")
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                specs = json.loads(d["specs_json"]) if d.get("specs_json") else {}
                item = {**specs, **d}
                is_pres = int(specs.get("is_present", 0 if d.get("status") == "REMOVED" else 1))
                item["is_present"] = is_pres
                if (only_present or not include_removed) and not is_pres:
                    continue
                results.append(item)
            return results

    def get_pending_hardware_components(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Извлекает компоненты оборудования, ожидающие AI-обогащения ссылками."""
        all_items = self.get_hardware_components(include_removed=False, only_present=True)
        pending = [
            i for i in all_items
            if i.get("ai_enrichment_status") in (None, "pending")
        ]
        return pending[:int(limit)]

    def get_hardware_component_by_key(self, component_key: str) -> Optional[Dict[str, Any]]:
        """Извлекает аппаратный компонент по ключу."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM hardware_components WHERE component_key = ? ORDER BY id DESC LIMIT 1;",
                (component_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            specs = json.loads(d["specs_json"]) if d.get("specs_json") else {}
            return {**specs, **d}

    def get_hardware_component_history(self, component_key: str) -> List[Dict[str, Any]]:
        """Извлекает историю событий установки/переустановки/удаления компонента."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM hardware_component_history
                WHERE component_name = ? OR old_config_json LIKE ? OR new_config_json LIKE ? OR summary LIKE ?
                ORDER BY created_at DESC, id DESC;
                ''',
                (component_key, f"%{component_key}%", f"%{component_key}%", f"%{component_key}%"),
            )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                raw_cfg = d.get("new_config_json") or d.get("old_config_json")
                if raw_cfg:
                    try:
                        d["details"] = json.loads(raw_cfg)
                    except Exception:
                        d["details"] = {}
                results.append(d)
            return results


