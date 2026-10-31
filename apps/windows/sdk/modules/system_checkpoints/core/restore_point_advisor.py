# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules System_Checkpoints Core - Restore Point Advisor
# =============================================================================
# Description:
#   Интеллектуальный советник и контроллер точек восстановления Windows (RestorePointAdvisor).
#   Выполняет предварительную оценку состояния системы по 8 категориям, отвечает на
#   три ключевых вопроса (целесообразность, дублирование, условия восстановления)
#   и управляет созданием точек на основе детерминированных правил и отпечатков (fingerprints).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.system_checkpoints.core.restore_point_advisor import RestorePointAdvisor
#
#     advisor = RestorePointAdvisor()
#     eval_result = advisor.evaluate(trigger_event="USER_REQUEST")
#     print(eval_result.decision, eval_result.summary)
#
# File: restore_point_advisor.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.system_checkpoints.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 22:52:00
# =============================================================================

from __future__ import annotations
"""Интеллектуальный советник и контроллер точек восстановления Windows."""

import hashlib
import json
import os
import sqlite3
import subprocess
import winreg
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from logger import logger
from apps.windows.system_checkpoints.models import (
    AdvisorDecision,
    AdvisorEvaluationResult,
    AdvisorTrigger,
    CategoryDelta,
    CategoryFingerprint,
    CategoryImportance,
    CheckpointType,
)


def get_default_state_journal_db_path() -> Path:
    """Возвращает стандартный путь к файлу базы данных state_journal.sqlite в %ProgramData%.

    Returns:
        Path: Путь к файлу state_journal.sqlite в каталоге телеметрии Windows.
    """
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE")
    if programdata and os.path.exists(programdata):
        base_dir = Path(programdata)
    else:
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if appdata and os.path.exists(appdata):
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / ".config"
    return base_dir / "AI-Windows-Admin" / "apps" / "windows" / "telemetry" / "logs" / "state_journal.sqlite"


class RestorePointStateJournal:
    """Хранилище снимков состояний и журнала дельт в SQLite."""

    DDL_STATEMENTS = (
        """
        CREATE TABLE IF NOT EXISTS smart_restore_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            trigger_event TEXT NOT NULL,
            composite_fingerprint TEXT NOT NULL,
            category_fingerprints TEXT NOT NULL,
            category_data_json TEXT NOT NULL DEFAULT '{}',
            decision TEXT NOT NULL,
            summary TEXT NOT NULL,
            questions_json TEXT NOT NULL DEFAULT '{}',
            is_restore_point INTEGER NOT NULL DEFAULT 0,
            restore_point_seq INTEGER,
            restore_point_desc TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS smart_restore_deltas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            category TEXT NOT NULL,
            change_type TEXT NOT NULL,
            item_key TEXT NOT NULL,
            details TEXT,
            importance TEXT NOT NULL DEFAULT 'HIGH',
            FOREIGN KEY (snapshot_id) REFERENCES smart_restore_snapshots(id) ON DELETE CASCADE
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_restore_snapshots_ts ON smart_restore_snapshots(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_restore_snapshots_hash ON smart_restore_snapshots(composite_fingerprint);",
        "CREATE INDEX IF NOT EXISTS idx_restore_deltas_snap ON smart_restore_deltas(snapshot_id);",
    )

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        """Инициализация журнала состояний.

        Args:
            db_path: Путь к файлу SQLite базы данных (по умолчанию
                     %ProgramData%\\AI-Windows-Admin\\apps\\windows\\telemetry\\logs\\state_journal.sqlite).
        """
        self.db_path = Path(db_path) if db_path else get_default_state_journal_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Создание таблиц и индексов при их отсутствии."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.cursor()
            for ddl in self.DDL_STATEMENTS:
                cur.execute(ddl)
            conn.commit()

    def save_snapshot(
        self,
        trigger_event: str,
        composite_fingerprint: str,
        category_fingerprints: Dict[str, Any],
        category_data: Dict[str, Any],
        decision: str,
        summary: str,
        questions: Dict[str, Any],
        is_restore_point: bool = False,
        restore_point_seq: Optional[int] = None,
        restore_point_desc: Optional[str] = None,
        deltas: Optional[List[CategoryDelta]] = None,
    ) -> int:
        """Сохранение снимка состояния и связанных дельт в БД."""
        ts = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO smart_restore_snapshots (
                    timestamp, trigger_event, composite_fingerprint, category_fingerprints,
                    category_data_json, decision, summary, questions_json,
                    is_restore_point, restore_point_seq, restore_point_desc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    trigger_event,
                    composite_fingerprint,
                    json.dumps(category_fingerprints, ensure_ascii=False),
                    json.dumps(category_data, ensure_ascii=False, default=str),
                    decision,
                    summary,
                    json.dumps(questions, ensure_ascii=False),
                    1 if is_restore_point else 0,
                    restore_point_seq,
                    restore_point_desc,
                ),
            )
            snapshot_id = int(cur.lastrowid or 0)
            if deltas:
                cur.executemany(
                    """
                    INSERT INTO smart_restore_deltas (
                        snapshot_id, timestamp, category, change_type, item_key, details, importance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_id,
                            ts,
                            d.category,
                            d.change_type,
                            d.item_key,
                            d.details,
                            d.importance,
                        )
                        for d in deltas
                    ],
                )
            conn.commit()
            return snapshot_id

    def get_last_restore_point_snapshot(self) -> Optional[Dict[str, Any]]:
        """Получение последнего сохраненного снимка, привязанного к точке восстановления."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM smart_restore_snapshots
                WHERE is_restore_point = 1
                ORDER BY id DESC LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT * FROM smart_restore_snapshots ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["category_fingerprints"] = json.loads(res["category_fingerprints"])
            res["category_data"] = json.loads(res["category_data_json"])
            res["questions"] = json.loads(res["questions_json"])
            return res

    def get_recent_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение последних записей журнала."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM smart_restore_snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            snapshots = []
            for r in rows:
                item = dict(r)
                item["category_fingerprints"] = json.loads(item["category_fingerprints"])
                item["questions"] = json.loads(item["questions_json"])
                snapshots.append(item)
            return snapshots


class RestorePointAdvisor:
    """Интеллектуальный советник создания контрольных точек Windows."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        coordinator: Optional[Any] = None,
    ) -> None:
        """Инициализация советника."""
        self.journal = RestorePointStateJournal(db_path=db_path)
        self.coordinator = coordinator

    def _get_restore_manager(self) -> Any:
        """Получение нативного менеджера System Restore."""
        try:
            from apps.windows.sdk.core.system_restore import WindowsSystemRestoreManager
            return WindowsSystemRestoreManager()
        except Exception as ex:
            logger.debug(f"Не удалось инициализировать WindowsSystemRestoreManager: {ex}")
            return None

    def check_readiness(self) -> Dict[str, Any]:
        """Проверка условий готовности ОС к созданию точки восстановления (Вопрос 3)."""
        sr_mgr = self._get_restore_manager()
        protection_ok = False
        vss_ok = False
        usage_pct = 0.0
        free_bytes = 0
        target_drive = "C:"
        error_msg = None

        if sr_mgr:
            try:
                prot = sr_mgr.check_protection_status()
                protection_ok = bool(prot.get("system_protection_enabled", False))
                target_drive = prot.get("target_drive", "C:")
                if prot.get("error"):
                    error_msg = prot.get("error")
            except Exception as e:
                error_msg = str(e)

            try:
                shadow = sr_mgr.get_shadow_storage_info()
                vss_ok = bool(shadow.get("available", False))
                usage_pct = float(shadow.get("usage_percent", 0.0))
            except Exception as e:
                logger.debug(f"Ошибка проверки VSS: {e}")

        # Проверка дискового пространства
        try:
            import shutil
            total, used, free = shutil.disk_usage(f"{target_drive}\\")
            free_bytes = free
            free_gb = round(free / (1024 ** 3), 2)
            has_enough_space = free_gb >= 1.0
        except Exception:
            has_enough_space = True
            free_gb = 10.0

        can_restore = bool(protection_ok and (vss_ok or has_enough_space) and free_gb >= 1.0)
        return {
            "can_restore": can_restore,
            "protection_enabled": protection_ok,
            "vss_available": vss_ok,
            "shadow_usage_percent": usage_pct,
            "free_space_gb": free_gb,
            "target_drive": target_drive,
            "error_message": error_msg,
        }

    def _collect_drivers(self) -> List[Dict[str, str]]:
        """Сбор установленных драйверов через pnputil."""
        drivers = []
        try:
            res = subprocess.run(["pnputil", "/enum-drivers"], capture_output=True, text=True, timeout=12)
            if res.returncode == 0:
                cur: Dict[str, str] = {}
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith(("Published Name:", "Опубликованное имя:")):
                        if cur:
                            drivers.append(cur)
                        cur = {"name": line.split(":", 1)[1].strip()}
                    elif line.startswith(("Provider Name:", "Имя поставщика:")):
                        cur["provider"] = line.split(":", 1)[1].strip()
                    elif line.startswith(("Class Name:", "Имя класса:")):
                        cur["class"] = line.split(":", 1)[1].strip()
                    elif line.startswith(("Driver Version:", "Версия драйвера:")):
                        cur["version"] = line.split(":", 1)[1].strip()
                if cur:
                    drivers.append(cur)
        except Exception as e:
            logger.debug(f"Ошибка pnputil: {e}")
        return sorted(drivers, key=lambda x: x.get("name", ""))

    def _collect_software(self) -> List[Dict[str, str]]:
        """Сбор установленных программ из реестра Windows."""
        apps = []
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root, subkey in roots:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(count):
                        try:
                            sub_name = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, sub_name) as app_k:
                                try:
                                    name, _ = winreg.QueryValueEx(app_k, "DisplayName")
                                    name = str(name).strip()
                                    if not name:
                                        continue
                                    try:
                                        ver, _ = winreg.QueryValueEx(app_k, "DisplayVersion")
                                        ver = str(ver).strip()
                                    except OSError:
                                        ver = ""
                                    try:
                                        pub, _ = winreg.QueryValueEx(app_k, "Publisher")
                                        pub = str(pub).strip()
                                    except OSError:
                                        pub = ""
                                    apps.append({"name": name, "version": ver, "publisher": pub})
                                except OSError:
                                    pass
                        except OSError:
                            pass
            except OSError:
                pass
        unique_apps = {a["name"].lower(): a for a in apps}.values()
        return sorted(list(unique_apps), key=lambda x: x.get("name", "").lower())

    def _collect_services(self) -> List[Dict[str, Any]]:
        """Сбор конфигурации системных служб Windows из реестра."""
        services = []
        reg_path = r"SYSTEM\CurrentControlSet\Services"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as root_key:
                num_subkeys, _, _ = winreg.QueryInfoKey(root_key)
                for i in range(min(num_subkeys, 350)):
                    try:
                        svc_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, svc_name) as svc_key:
                            try:
                                start_type, _ = winreg.QueryValueEx(svc_key, "Start")
                            except OSError:
                                start_type = -1
                            try:
                                image_path, _ = winreg.QueryValueEx(svc_key, "ImagePath")
                                image_path = str(image_path).strip()
                            except OSError:
                                image_path = ""
                            services.append({
                                "name": svc_name,
                                "start_type": int(start_type),
                                "image_path": image_path[:100],
                            })
                    except OSError:
                        pass
        except OSError as e:
            logger.debug(f"Ошибка чтения служб из реестра: {e}")
        return sorted(services, key=lambda x: x.get("name", "").lower())

    def _collect_updates(self) -> List[str]:
        """Сбор установленных пакетов обновлений Windows (KB)."""
        kbs = []
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "Get-HotFix | Select-Object -ExpandProperty HotFixID"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if res.returncode == 0:
                kbs = [line.strip() for line in res.stdout.splitlines() if line.strip().upper().startswith("KB")]
        except Exception as e:
            logger.debug(f"Ошибка сбора HotFix: {e}")
        return sorted(list(set(kbs)))

    def _collect_boot_config(self) -> Dict[str, str]:
        """Сбор параметров конфигурации загрузки и WinRE."""
        boot = {"timeout": "30", "winre_enabled": "Unknown"}
        try:
            res = subprocess.run(["reagentc", "/info"], capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                stdout = res.stdout.lower()
                boot["winre_enabled"] = "Enabled" if ("enabled" in stdout or "включено" in stdout) else "Disabled"
        except Exception:
            pass
        return boot

    def _collect_registry_policies(self) -> Dict[str, str]:
        """Сбор хеша ключевых веток автозапуска и системных политик."""
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"),
        ]
        values = []
        for root, path in paths:
            try:
                with winreg.OpenKey(root, path) as k:
                    _, num_vals, _ = winreg.QueryInfoKey(k)
                    for i in range(num_vals):
                        try:
                            name, val, _ = winreg.EnumValue(k, i)
                            values.append(f"{path}\\{name}={val}")
                        except OSError:
                            pass
            except OSError:
                pass
        content = "\n".join(sorted(values))
        return {"policy_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]}

    def _collect_system_files(self) -> List[Dict[str, Any]]:
        """Сбор версий и метаданных критичных системных файлов ОС."""
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        critical_files = [
            os.path.join(sys_root, "System32", "ntoskrnl.exe"),
            os.path.join(sys_root, "System32", "hal.dll"),
            os.path.join(sys_root, "System32", "win32k.sys"),
        ]
        items = []
        for path in critical_files:
            if os.path.exists(path):
                try:
                    stat = os.stat(path)
                    items.append({
                        "file": os.path.basename(path),
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime),
                    })
                except OSError:
                    pass
        return sorted(items, key=lambda x: x.get("file", ""))

    def collect_current_state(self, trigger_event: str = "USER_REQUEST") -> Dict[str, Any]:
        """Полный сбор текущего состояния системы с нормализацией и вычислением отпечатков."""
        drivers = self._collect_drivers()
        software = self._collect_software()
        services = self._collect_services()
        updates = self._collect_updates()
        boot = self._collect_boot_config()
        reg = self._collect_registry_policies()
        sys_files = self._collect_system_files()

        def _calc_hash(data: Any) -> str:
            raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        cat_hashes = {
            "drivers": _calc_hash(drivers),
            "software": _calc_hash(software),
            "services": _calc_hash(services),
            "updates": _calc_hash(updates),
            "boot_config": _calc_hash(boot),
            "registry": _calc_hash(reg),
            "system_files": _calc_hash(sys_files),
            "user_files": "SKIPPED_USER_SPACE",
        }

        # Композитный отпечаток
        composite_source = ":".join(cat_hashes[k] for k in sorted(cat_hashes.keys()) if k != "user_files")
        composite_hash = hashlib.sha256(composite_source.encode("utf-8")).hexdigest()

        return {
            "trigger_event": trigger_event,
            "composite_fingerprint": composite_hash,
            "category_hashes": cat_hashes,
            "data": {
                "drivers": drivers,
                "software": software,
                "services": services,
                "updates": updates,
                "boot_config": boot,
                "registry": reg,
                "system_files": sys_files,
            },
        }

    def evaluate(
        self,
        trigger_event: str = "USER_REQUEST",
        current_state: Optional[Dict[str, Any]] = None,
    ) -> AdvisorEvaluationResult:
        """Интеллектуальная оценка необходимости создания точки восстановления."""
        readiness = self.check_readiness()
        cur_state = current_state or self.collect_current_state(trigger_event)
        prev_snapshot = self.journal.get_last_restore_point_snapshot()

        cur_hashes = cur_state["category_hashes"]
        cur_data = cur_state["data"]
        deltas: List[CategoryDelta] = []
        categories_dict: Dict[str, CategoryFingerprint] = {}

        prev_hashes = prev_snapshot.get("category_fingerprints", {}) if prev_snapshot else {}
        prev_data = prev_snapshot.get("category_data", {}) if prev_snapshot else {}

        cat_titles = {
            "drivers": "Драйверы и PnP устройства",
            "software": "Установленные программы и компоненты",
            "services": "Системные службы Windows",
            "updates": "Обновления Windows Update (KB)",
            "boot_config": "Конфигурация загрузки и WinRE",
            "registry": "Системный реестр и политики",
            "system_files": "Критические системные файлы ядра",
            "user_files": "Пользовательские файлы (Документы, Загрузки)",
        }

        cat_importance = {
            "drivers": "HIGH",
            "software": "MEDIUM",
            "services": "HIGH",
            "updates": "HIGH",
            "boot_config": "HIGH",
            "registry": "MEDIUM",
            "system_files": "HIGH",
            "user_files": "LOW",
        }

        # Анализ категорий
        for cat, title in cat_titles.items():
            if cat == "user_files":
                categories_dict[cat] = CategoryFingerprint(
                    category=cat,
                    category_title_ru=title,
                    hash="EXCLUDED_BY_POLICY",
                    items_count=0,
                    changed=False,
                    importance="LOW",
                    details="Исключено: пользовательские файлы не защищаются точками восстановления",
                )
                continue

            c_hash = cur_hashes.get(cat, "")
            p_hash = prev_hashes.get(cat, "")
            changed = bool(p_hash and c_hash != p_hash)
            items = cur_data.get(cat, [])
            items_count = len(items) if isinstance(items, (list, dict)) else 0

            # Вычисление дельт при наличии предыдущего состояния
            if prev_snapshot and changed:
                p_items = prev_data.get(cat, [])
                if cat == "updates" and isinstance(items, list) and isinstance(p_items, list):
                    cur_set = set(items)
                    prev_set = set(p_items)
                    for added in (cur_set - prev_set):
                        deltas.append(CategoryDelta(cat, "ADDED", added, f"Установлено обновление {added}", "HIGH"))
                    for removed in (prev_set - cur_set):
                        deltas.append(CategoryDelta(cat, "REMOVED", removed, f"Удалено обновление {removed}", "HIGH"))
                elif cat == "drivers" and isinstance(items, list) and isinstance(p_items, list):
                    cur_map = {d.get("name", ""): d for d in items}
                    prev_map = {d.get("name", ""): d for d in p_items}
                    for name in (set(cur_map) - set(prev_map)):
                        deltas.append(CategoryDelta(cat, "ADDED", name, f"Новый драйвер: {cur_map[name].get('class', '')}", "HIGH"))
                    for name in (set(prev_map) - set(cur_map)):
                        deltas.append(CategoryDelta(cat, "REMOVED", name, f"Удален драйвер {name}", "HIGH"))
                elif cat == "software" and isinstance(items, list) and isinstance(p_items, list):
                    cur_map = {a.get("name", "").lower(): a for a in items}
                    prev_map = {a.get("name", "").lower(): a for a in p_items}
                    for name in (set(cur_map) - set(prev_map)):
                        deltas.append(CategoryDelta(cat, "ADDED", cur_map[name].get("name", name), f"Установлена программа {cur_map[name].get('version', '')}", "MEDIUM"))
                    for name in (set(prev_map) - set(cur_map)):
                        deltas.append(CategoryDelta(cat, "REMOVED", prev_map[name].get("name", name), "Программа удалена", "MEDIUM"))
                else:
                    deltas.append(CategoryDelta(cat, "MODIFIED", cat, f"Изменена конфигурация в категории {title}", cat_importance.get(cat, "HIGH")))

            categories_dict[cat] = CategoryFingerprint(
                category=cat,
                category_title_ru=title,
                hash=c_hash[:16],
                items_count=items_count,
                changed=changed,
                importance=cat_importance.get(cat, "HIGH"),
                details=f"{items_count} элементов, {'изменена' if changed else 'без изменений'}",
            )

        # Ответы на 3 ключевых вопроса
        is_duplicate = False
        if prev_snapshot:
            if cur_state["composite_fingerprint"] == prev_snapshot.get("composite_fingerprint"):
                is_duplicate = True

        high_deltas = [d for d in deltas if d.importance == "HIGH"]
        med_deltas = [d for d in deltas if d.importance == "MEDIUM"]

        # Если снимков не было вовсе — это первая фиксация
        is_initial = prev_snapshot is None
        need_creation = is_initial or bool(high_deltas) or len(med_deltas) >= 2

        # Формирование ответов на 3 вопроса
        q1_answer = {
            "question": "1. Есть ли смысл создавать точку восстановления?",
            "verdict": "Да" if need_creation else "Нет",
            "meaningful_changes": bool(need_creation),
            "explanation": (
                "Первая фиксация эталонного состояния системы." if is_initial else
                f"Обнаружены значимые изменения ({len(high_deltas)} критических, {len(med_deltas)} умеренных)." if need_creation else
                "Существенных изменений в системных файлах, драйверах, службах или ПО не обнаружено."
            ),
        }

        q2_answer = {
            "question": "2. Не дублирует ли она предыдущую точку?",
            "verdict": "Дублирует" if is_duplicate else "Уникальна",
            "is_duplicate": is_duplicate,
            "explanation": (
                f"Конфигурационный отпечаток совпадает с предыдущей точкой от {prev_snapshot.get('timestamp', '')[:19]}." if is_duplicate else
                "Конфигурационный отпечаток уникален, состояние системы отличается от предыдущей точки."
            ),
        }

        q3_answer = {
            "question": "3. Достаточно ли данных и условий для восстановления?",
            "verdict": "Достаточно" if readiness["can_restore"] else "Недостаточно",
            "can_restore": readiness["can_restore"],
            "explanation": (
                f"Защита системы включена на {readiness['target_drive']}, доступно {readiness['free_space_gb']} ГБ свободного места." if readiness["can_restore"] else
                f"Внимание: защита системы выключена или недоступно теневое хранилище ({readiness.get('error_message') or 'Ошибка VSS'})."
            ),
        }

        # Принятие итогового детерминированного решения
        if not readiness["can_restore"]:
            decision = AdvisorDecision.CLARIFY
            summary = "Недостаточно данных или отключена защита системы (System Protection). Требуется включить защиту диска."
            rec = "Включите защиту системы (Enable-ComputerRestore -Drive 'C:') и проверьте службу теневого копирования томов (VSS)."
        elif is_duplicate:
            decision = AdvisorDecision.SKIP
            summary = "Создание точки пропущено: состояние системы полностью идентично предыдущей контрольной точке."
            rec = "Создание дублирующей точки не требуется. Система защищена существующей точкой."
        elif need_creation:
            decision = AdvisorDecision.CREATE
            summary = f"Рекомендуется создать точку: зафиксированы изменения ({len(high_deltas)} важных, {len(med_deltas)} средних)."
            rec = "Создайте контрольную точку восстановления для возможности отката в случае непредвиденных сбоев."
        else:
            decision = AdvisorDecision.MONITOR
            summary = "Небольшие изменения конфигурации. Рекомендуется продолжить наблюдение без создания точки."
            rec = "Изменения зафиксированы в журнале наблюдений. Точка восстановления пока не требуется."

        result = AdvisorEvaluationResult(
            decision=decision,
            trigger=trigger_event,
            questions={"q1": q1_answer, "q2": q2_answer, "q3": q3_answer},
            composite_fingerprint=cur_state["composite_fingerprint"],
            categories=categories_dict,
            deltas=deltas,
            summary=summary,
            readiness=readiness,
            recommended_action=rec,
            previous_snapshot_time=prev_snapshot.get("timestamp") if prev_snapshot else None,
        )
        return result

    def execute_smart_restore_point(
        self,
        title: Optional[str] = None,
        trigger_event: str = "USER_REQUEST",
        force: bool = False,
        checkpoint_type: CheckpointType = CheckpointType.PERIODIC,
    ) -> Dict[str, Any]:
        """Интеллектуальное создание точки восстановления с проверкой и журналированием."""
        current_state = self.collect_current_state(trigger_event)
        eval_res = self.evaluate(trigger_event=trigger_event, current_state=current_state)

        should_create = (eval_res.decision == AdvisorDecision.CREATE) or force

        if not should_create:
            # Сохраняем срез в журнал без создания нативной точки
            self.journal.save_snapshot(
                trigger_event=trigger_event,
                composite_fingerprint=current_state["composite_fingerprint"],
                category_fingerprints={k: v.to_dict() for k, v in eval_res.categories.items()},
                category_data=current_state["data"],
                decision=eval_res.decision.value,
                summary=eval_res.summary,
                questions=eval_res.questions,
                is_restore_point=False,
                deltas=eval_res.deltas,
            )
            return {
                "success": True,
                "created": False,
                "decision": eval_res.decision.value,
                "message": eval_res.summary,
                "evaluation": eval_res.to_dict(),
            }

        # Если создание одобрено — вызываем исполнитель
        sr_mgr = self._get_restore_manager()
        clean_title = title or f"AI-Advisor [{checkpoint_type.value}]: {eval_res.summary[:50]}"
        create_res: Dict[str, Any] = {}

        if sr_mgr:
            create_res = sr_mgr.create_restore_point(
                description=clean_title,
                restore_point_type="MODIFY_SETTINGS",
            )
        else:
            create_res = {"success": False, "error": "Менеджер System Restore недоступен."}

        is_success = bool(create_res.get("success", False))

        # Запись в журнал состояний с пометкой точки восстановления
        self.journal.save_snapshot(
            trigger_event=trigger_event,
            composite_fingerprint=current_state["composite_fingerprint"],
            category_fingerprints={k: v.to_dict() for k, v in eval_res.categories.items()},
            category_data=current_state["data"],
            decision=eval_res.decision.value,
            summary=eval_res.summary,
            questions=eval_res.questions,
            is_restore_point=is_success,
            restore_point_desc=clean_title if is_success else None,
            deltas=eval_res.deltas,
        )

        return {
            "success": is_success,
            "created": is_success,
            "decision": eval_res.decision.value,
            "title": clean_title,
            "message": create_res.get("message", eval_res.summary),
            "error": create_res.get("error"),
            "evaluation": eval_res.to_dict(),
            "restore_point_details": create_res,
        }

    def explain_with_ai(self, eval_res: AdvisorEvaluationResult) -> str:
        """Формирование пояснения на русском языке."""
        return (
            f"Анализ конфигурации системы завершен.\n\n"
            f"1. Целесообразность: {eval_res.questions['q1']['explanation']}\n"
            f"2. Дедупликация: {eval_res.questions['q2']['explanation']}\n"
            f"3. Условия восстановления: {eval_res.questions['q3']['explanation']}\n\n"
            f"Итоговое решение: {eval_res.decision.value} — {eval_res.summary}\n"
            f"Рекомендация: {eval_res.recommended_action}"
        )

