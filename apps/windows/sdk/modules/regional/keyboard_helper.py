# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Regional - Keyboard & Language Helper
# =============================================================================
# Description:
#   Низкоуровневое управление языковыми пакетами (Русский, Иврит, Английский),
#   раскладками клавиатуры (Keyboard Layouts / KLID), порядком ввода
#   и языком интерфейса Windows через реестр и Win32 API.
#
# File: keyboard_helper.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.regional
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:40:00
# =============================================================================

from __future__ import annotations

import ctypes
import os
import platform
import re
from typing import Any, Callable, Dict, List, Tuple

from logger import logger


# ── Целевая тройка языковых пакетов (Русский, Иврит, Английский) ─────────────
TARGET_LANGUAGES: List[Dict[str, Any]] = [
    {
        "tag": "ru-RU",
        "short": "ru",
        "lcid": "0419",
        "lcid_int": 0x0419,
        "alts": ["ru", "ru-ru"],
        "name": "Русский",
        "native_name": "Русский (Россия)",
        "flag": "🇷🇺",
        "default_klid": "00000419",
    },
    {
        "tag": "he-IL",
        "short": "he",
        "lcid": "040d",
        "lcid_int": 0x040D,
        "alts": ["he", "he-il", "iw", "iw-il"],
        "name": "Иврит",
        "native_name": "עברית (ישראל)",
        "flag": "🇮🇱",
        "default_klid": "0002040d",
    },
    {
        "tag": "en-US",
        "short": "en",
        "lcid": "0409",
        "lcid_int": 0x0409,
        "alts": ["en", "en-us", "en-gb"],
        "name": "Английский",
        "native_name": "English (United States)",
        "flag": "🇺🇸",
        "default_klid": "00000409",
    },
]

# Локализованные названия раскладок на русском языке
LAYOUT_DISPLAY_NAMES_RU: Dict[str, str] = {
    "00000419": "Русская (Стандартная ЙЦУКЕН)",
    "00010419": "Русская (Машинопись)",
    "00020419": "Русская (Мнемоническая)",
    "a0000419": "Русская фонетическая (WinRus Student)",
    "0000040d": "Иврит (Традиционная)",
    "0002040d": "Иврит (Стандартная SI-1452)",
    "0003040d": "Иврит (Стандартная, 2018)",
    "00000409": "Английская США (QWERTY)",
    "00010409": "Английская США (Dvorak)",
    "00020409": "Английская США (Международная)",
    "00030409": "Английская США (Dvorak для левой руки)",
    "00040409": "Английская США (Dvorak для правой руки)",
    "00060409": "Английская США (Colemak)",
}


def resolve_target_meta(tag_or_code: str) -> Dict[str, Any] | None:
    """Находит описание целевого языка по тегу ('ru-RU', 'he', '0419' и т.д.)."""
    clean = (tag_or_code or "").strip().lower()
    for t in TARGET_LANGUAGES:
        if clean == t["tag"].lower() or clean in t["alts"] or clean == t["lcid"].lower():
            return t
    return None


def read_all_hklm_keyboard_layouts(is_windows: bool) -> Dict[str, str]:
    """Считывает справочник всех зарегистрированных раскладок клавиатуры из HKLM."""
    layouts: Dict[str, str] = dict(LAYOUT_DISPLAY_NAMES_RU)
    if not is_windows:
        return layouts

    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Keyboard Layouts",
        ) as k_root:
            sub_cnt, _, _ = winreg.QueryInfoKey(k_root)
            for i in range(sub_cnt):
                try:
                    klid = winreg.EnumKey(k_root, i).lower()
                    if klid in LAYOUT_DISPLAY_NAMES_RU:
                        continue
                    with winreg.OpenKey(k_root, klid) as k_sub:
                        txt, _ = winreg.QueryValueEx(k_sub, "Layout Text")
                        if txt:
                            layouts[klid] = str(txt)
                except Exception:
                    continue
    except Exception as exc:
        logger.debug(f"[keyboard_helper] Ошибка чтения HKLM Keyboard Layouts: {exc}")

    return layouts


def read_user_keyboard_state(is_windows: bool) -> Tuple[List[Tuple[str, str]], Dict[str, str]]:
    """Считывает Preload и Substitutes раскладок текущего пользователя из HKCU.

    Returns:
        Tuple[List[Tuple[str, str]], Dict[str, str]]:
            - Упорядоченный список (slot, preload_klid)
            - Словарь подстановок {preload_klid_lower: actual_klid_lower}
    """
    preload_items: List[Tuple[str, str]] = []
    substitutes: Dict[str, str] = {}

    if not is_windows:
        return [("1", "00000419"), ("2", "00000409"), ("3", "0002040d")], {}

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Keyboard Layout\Substitutes") as k_sub:
            _, val_cnt, _ = winreg.QueryInfoKey(k_sub)
            for i in range(val_cnt):
                name, val, _ = winreg.EnumValue(k_sub, i)
                if name and val:
                    substitutes[str(name).lower()] = str(val).lower()
    except Exception:
        pass

    try:
        import winreg
        raw_preload: List[Tuple[int, str, str]] = []
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Keyboard Layout\Preload") as k_pre:
            _, val_cnt, _ = winreg.QueryInfoKey(k_pre)
            for i in range(val_cnt):
                name, val, _ = winreg.EnumValue(k_pre, i)
                if name and val:
                    try:
                        slot_num = int(str(name))
                    except ValueError:
                        slot_num = 999 + i
                    raw_preload.append((slot_num, str(name), str(val).lower()))
        raw_preload.sort(key=lambda x: x[0])
        preload_items = [(slot_str, klid) for _, slot_str, klid in raw_preload]
    except Exception as exc:
        logger.debug(f"[keyboard_helper] Ошибка чтения Preload: {exc}")

    return preload_items, substitutes


def get_system_language_identity(is_windows: bool = True) -> Dict[str, str]:
    """Определяет основной язык установленной ОС (InstallLanguage) и текущий язык интерфейса (Display Language)."""
    install_lcid = "0409"
    ui_lcid_int = 0x0419
    preferred_tag = ""

    if is_windows:
        try:
            ui_lcid_int = int(ctypes.windll.kernel32.GetUserDefaultUILanguage()) & 0xFFFF
        except Exception:
            ui_lcid_int = 0x0419

        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Nls\Language",
            ) as k_nls:
                inst_val, _ = winreg.QueryValueEx(k_nls, "InstallLanguage")
                if inst_val:
                    install_lcid = str(inst_val).strip().lower().zfill(4)[-4:]
        except Exception:
            pass

        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k_desk:
                for val_name in ("PreferredUILanguagesPending", "PreferredUILanguages"):
                    try:
                        val, _ = winreg.QueryValueEx(k_desk, val_name)
                        if isinstance(val, (list, tuple)) and len(val) > 0 and str(val[0]).strip():
                            preferred_tag = str(val[0]).strip()
                            break
                    except Exception:
                        continue
        except Exception:
            pass

    inst_meta = resolve_target_meta(install_lcid)
    if inst_meta:
        install_lang_str = f"{inst_meta['native_name']} [{inst_meta['tag']}]" if inst_meta["name"] in inst_meta["native_name"] else f"{inst_meta['name']} ({inst_meta['native_name']}) [{inst_meta['tag']}]"
        install_tag = inst_meta["tag"]
    else:
        install_lang_str = f"LCID {install_lcid.upper()}"
        install_tag = install_lcid.upper()

    disp_meta = resolve_target_meta(preferred_tag) if preferred_tag else None
    if not disp_meta:
        disp_meta = resolve_target_meta(f"{ui_lcid_int:04x}")

    if disp_meta:
        display_lang_str = f"{disp_meta['native_name']} [{disp_meta['tag']}]" if disp_meta["name"] in disp_meta["native_name"] else f"{disp_meta['name']} ({disp_meta['native_name']}) [{disp_meta['tag']}]"
        display_tag = disp_meta["tag"]
    else:
        display_lang_str = preferred_tag or f"LCID {ui_lcid_int:04X}"
        display_tag = preferred_tag or f"{ui_lcid_int:04X}"

    return {
        "os_install_language": install_lang_str,
        "os_install_language_tag": install_tag,
        "display_language": display_lang_str,
        "display_language_tag": display_tag,
    }


def collect_language_packs_full(is_windows: bool) -> List[Dict[str, Any]]:
    """Собирает полные сведения о языковых пакетах и раскладках клавиатуры (Русский, Иврит, Английский)."""
    installed_mui: set[str] = set()
    user_langs_ordered: List[str] = []
    lang_ident = get_system_language_identity(is_windows)
    active_disp_tag = lang_ident["display_language_tag"].lower()
    active_inst_tag = lang_ident["os_install_language_tag"].lower()

    if is_windows:

        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\MUI\UILanguages",
            ) as key:
                count, _, _ = winreg.QueryInfoKey(key)
                for i in range(count):
                    installed_mui.add(winreg.EnumKey(key, i).lower())
        except Exception as exc:
            logger.debug(f"[keyboard_helper] Ошибка чтения MUI UILanguages: {exc}")

        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\International\User Profile",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Languages")
                if isinstance(val, (list, tuple)):
                    user_langs_ordered = [str(item).strip() for item in val if str(item).strip()]
        except Exception as exc:
            logger.debug(f"[keyboard_helper] Ошибка чтения User Profile Languages: {exc}")
    else:
        installed_mui = {"ru-ru", "en-us", "he-il"}
        user_langs_ordered = ["ru-RU", "en-US", "he-IL"]

    all_layouts_catalog = read_all_hklm_keyboard_layouts(is_windows)
    preload_items, substitutes = read_user_keyboard_state(is_windows)

    # Группируем активные раскладки из Preload по 4-символьному LCID (суффикс)
    active_layouts_by_lcid: Dict[str, List[Dict[str, Any]]] = {}
    seen_klids_by_lcid: Dict[str, set[str]] = {}

    for slot_str, preload_val in preload_items:
        if len(preload_val) < 4:
            continue
        lcid_suffix = preload_val[-4:].lower()
        actual_klid = substitutes.get(preload_val, preload_val).lower()
        layout_name = (
            LAYOUT_DISPLAY_NAMES_RU.get(actual_klid)
            or all_layouts_catalog.get(actual_klid)
            or f"Раскладка {actual_klid.upper()}"
        )
        seen_set = seen_klids_by_lcid.setdefault(lcid_suffix, set())
        if actual_klid not in seen_set:
            seen_set.add(actual_klid)
            active_layouts_by_lcid.setdefault(lcid_suffix, []).append({
                "klid": actual_klid,
                "name": layout_name,
                "preload_slot": slot_str,
                "is_active": True,
            })

    # Дополнительно проверяем подключенные раскладки внутри HKCU\Control Panel\International\User Profile\<lang>
    if is_windows:
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\International\User Profile",
            ) as k_prof:
                sub_cnt, _, _ = winreg.QueryInfoKey(k_prof)
                for idx in range(sub_cnt):
                    sub_name = winreg.EnumKey(k_prof, idx)
                    with winreg.OpenKey(k_prof, sub_name) as k_lang:
                        _, v_cnt, _ = winreg.QueryInfoKey(k_lang)
                        for j in range(v_cnt):
                            v_name, _, _ = winreg.EnumValue(k_lang, j)
                            if ":" in str(v_name):
                                parts = str(v_name).split(":", 1)
                                lcid_p = parts[0].strip().lower()
                                klid_p = parts[1].strip().lower()
                                if len(lcid_p) == 4 and len(klid_p) == 8:
                                    seen_set = seen_klids_by_lcid.setdefault(lcid_p, set())
                                    if klid_p not in seen_set:
                                        seen_set.add(klid_p)
                                        layout_name = (
                                            LAYOUT_DISPLAY_NAMES_RU.get(klid_p)
                                            or all_layouts_catalog.get(klid_p)
                                            or f"Раскладка {klid_p.upper()}"
                                        )
                                        active_layouts_by_lcid.setdefault(lcid_p, []).append({
                                            "klid": klid_p,
                                            "name": layout_name,
                                            "preload_slot": "",
                                            "is_active": True,
                                        })
        except Exception:
            pass

    user_langs_lower = [u.lower() for u in user_langs_ordered]
    result: List[Dict[str, Any]] = []
    seen_tags: set[str] = set()

    for t in TARGET_LANGUAGES:
        tag = t["tag"]
        lcid = t["lcid"].lower()
        alts_lower = [a.lower() for a in [tag] + t["alts"]]
        for a in alts_lower:
            seen_tags.add(a)

        is_inst = any(a in installed_mui for a in alts_lower)
        order_idx = 99
        for pos, u_lang in enumerate(user_langs_lower):
            if u_lang in alts_lower or u_lang.split("-")[0] == t["short"]:
                order_idx = pos + 1
                break

        act_layouts = active_layouts_by_lcid.get(lcid, [])
        is_act = (order_idx < 99) or (len(act_layouts) > 0)
        is_disp = (active_disp_tag in alts_lower)
        is_os_install = (active_inst_tag in alts_lower)

        # Доступные системные раскладки для этого языка
        avail_layouts: List[Dict[str, Any]] = []
        active_klids_set = {x["klid"].lower() for x in act_layouts}
        for k_code, k_title in sorted(all_layouts_catalog.items()):
            if k_code.lower().endswith(lcid):
                avail_layouts.append({
                    "klid": k_code.lower(),
                    "name": LAYOUT_DISPLAY_NAMES_RU.get(k_code.lower(), k_title),
                    "preload_slot": "",
                    "is_active": k_code.lower() in active_klids_set,
                })

        result.append({
            "tag": tag,
            "name": t["name"],
            "native_name": t["native_name"],
            "flag": t["flag"],
            "lcid": lcid.upper(),
            "is_installed": is_inst,
            "is_active": is_act,
            "is_display_language": is_disp,
            "is_os_install_language": is_os_install,
            "is_default_input": (order_idx == 1),
            "order_index": order_idx,
            "is_target": True,
            "keyboard_layouts": act_layouts,
            "available_layouts": avail_layouts,
        })

    # Сортируем целевую тройку: сначала по позиции в списке ввода, затем по базовому порядку
    result.sort(key=lambda item: (item["order_index"], 0 if item["tag"] == "ru-RU" else (1 if item["tag"] == "he-IL" else 2)))

    # Дополнительные языковые пакеты, если установлены в системе
    for mui_tag in sorted(installed_mui):
        if mui_tag not in seen_tags:
            result.append({
                "tag": mui_tag,
                "name": mui_tag.upper(),
                "native_name": mui_tag,
                "flag": "🌐",
                "lcid": "",
                "is_installed": True,
                "is_active": mui_tag in user_langs_lower,
                "is_display_language": False,
                "is_default_input": False,
                "order_index": 99,
                "is_target": False,
                "keyboard_layouts": [],
                "available_layouts": [],
            })

    return result


def manage_language_pack_action(
    is_windows: bool,
    run_ps_fn: Callable[[str, int], Tuple[int, str, str]],
    tag: str,
    action: str,
    klid: str = "",
) -> Dict[str, Any]:
    """Выполняет операцию управления языковым пакетом и раскладками клавиатуры.

    Поддерживаемые действия (action):
        - ``install``: Установка MUI-пакета и подключение языка со стандартной раскладкой.
        - ``activate``: Включение языка и его раскладки в список ввода пользователя.
        - ``deactivate``: Отключение языка из раскладки ввода (без удаления системного пакета).
        - ``set_default_input``: Установка языка первым по умолчанию в списке ввода.
        - ``set_display_language``: Установка языка интерфейса Windows (Display Language).
        - ``add_layout``: Добавление конкретной раскладки клавиатуры (KLID) к языку.
        - ``remove_layout``: Удаление конкретной раскладки клавиатуры (KLID) у языка.
        - ``sync_trio``: Синхронизация и подключение всей тройки (Русский, Иврит, Английский).
    """
    clean_action = (action or "install").strip().lower()
    meta = resolve_target_meta(tag)
    canonical_tag = meta["tag"] if meta else (tag or "ru-RU").strip()
    lang_name = meta["name"] if meta else canonical_tag
    lcid = meta["lcid"].lower() if meta else "0419"
    default_klid = meta["default_klid"].lower() if meta else "00000419"

    if not is_windows:
        return {
            "status": "ok",
            "tag": canonical_tag,
            "name": lang_name,
            "action": clean_action,
            "message": f"Эмуляция действия '{clean_action}' для языка {lang_name} ({canonical_tag})",
            "language_packs": collect_language_packs_full(False),
        }

    import winreg

    try:
        # ── 1. Синхронизация всей тройки RU + HE + EN ────────────────────────
        if clean_action == "sync_trio":
            _ensure_user_profile_languages(["ru-RU", "he-IL", "en-US"])
            for t_item in TARGET_LANGUAGES:
                _add_keyboard_layout_to_registry(t_item["lcid"].lower(), t_item["default_klid"].lower(), t_item["tag"])
            ps_sync = """
            try {
                $list = New-WinUserLanguageList -Language 'ru-RU'
                $list.Add('he-IL')
                $list.Add('en-US')
                Set-WinUserLanguageList $list -Force -Confirm:$false -ErrorAction SilentlyContinue
            } catch {}
            """
            run_ps_fn(ps_sync, 12)
            logger.console("Тройка языковых пакетов (Русский, Иврит, Английский) синхронизирована и подключена")
            return {
                "status": "ok",
                "tag": "ru-RU,he-IL,en-US",
                "name": "Русский, Иврит, Английский",
                "action": clean_action,
                "message": "Вся тройка языковых пакетов (Русский, Иврит, Английский) и их стандартные раскладки активированы.",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 2. Активация или установка языкового пакета ──────────────────────
        if clean_action in ("install", "activate"):
            _add_lang_to_user_profile(canonical_tag, meta["short"] if meta else canonical_tag)
            _add_keyboard_layout_to_registry(lcid, default_klid, canonical_tag)

            ps_cmd = f"""
            $tag = '{canonical_tag}'
            try {{
                $list = Get-WinUserLanguageList
                if ($null -ne $list -and $list.Count -gt 0) {{
                    if ($list.LanguageTag -notcontains $tag -and $list.LanguageTag -notcontains '{meta["short"] if meta else canonical_tag}') {{
                        $list.Add($tag)
                        Set-WinUserLanguageList $list -Force -Confirm:$false -ErrorAction SilentlyContinue
                    }}
                }}
            }} catch {{}}
            """
            if clean_action == "install":
                ps_cmd += f"""
                if (Get-Command Install-Language -ErrorAction SilentlyContinue) {{
                    try {{
                        Install-Language -Language '{canonical_tag}' -Confirm:$false -ErrorAction SilentlyContinue
                    }} catch {{}}
                }}
                """
            run_ps_fn(ps_cmd, 20)
            logger.console(f"Языковой пакет {lang_name} ({canonical_tag}) активирован в раскладках")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Языковой пакет «{lang_name}» ({canonical_tag}) и раскладка клавиатуры подключены.",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 3. Отключение языка из раскладки ввода ───────────────────────────
        if clean_action == "deactivate":
            packs_now = collect_language_packs_full(True)
            active_targets = [p for p in packs_now if p.get("is_active")]
            if len(active_targets) <= 1 and any(p["tag"] == canonical_tag and p["is_active"] for p in packs_now):
                return {
                    "status": "error",
                    "tag": canonical_tag,
                    "name": lang_name,
                    "action": clean_action,
                    "message": "Нельзя отключить единственный активный язык ввода в системе.",
                    "language_packs": packs_now,
                }

            _remove_lang_from_user_profile(canonical_tag, meta["short"] if meta else canonical_tag, lcid)
            logger.console(f"Язык {lang_name} ({canonical_tag}) отключен из раскладки ввода")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Язык «{lang_name}» ({canonical_tag}) убран из активных раскладок ввода.",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 4. Установка языка основным (первым в списке ввода) ──────────────
        if clean_action == "set_default_input":
            _move_lang_to_first(canonical_tag, meta["short"] if meta else canonical_tag, lcid, default_klid)
            logger.console(f"Язык ввода по умолчанию установлен: {lang_name} ({canonical_tag})")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Язык «{lang_name}» ({canonical_tag}) установлен первым языком ввода по умолчанию.",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 5. Установка языка интерфейса Windows (Display Language) ─────────
        if clean_action == "set_display_language":
            ps_disp = f"""
            try {{
                Set-WinUILanguageOverride -Language '{canonical_tag}' -ErrorAction SilentlyContinue
            }} catch {{}}
            """
            run_ps_fn(ps_disp, 10)
            try:
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    r"Control Panel\Desktop",
                    0,
                    winreg.KEY_SET_VALUE,
                ) as k_desk:
                    winreg.SetValueEx(k_desk, "PreferredUILanguages", 0, winreg.REG_MULTI_SZ, [canonical_tag])
                    winreg.SetValueEx(k_desk, "PreferredUILanguagesPending", 0, winreg.REG_MULTI_SZ, [canonical_tag])
            except Exception as reg_err:
                logger.debug(f"[keyboard_helper] Ошибка записи PreferredUILanguages: {reg_err}")

            logger.console(f"Язык интерфейса Windows переключен на {lang_name} ({canonical_tag})")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Язык интерфейса Windows установлен на «{lang_name}» ({canonical_tag}). Изменения вступят в силу после повторного входа в систему.",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 6. Добавление раскладки клавиатуры (KLID) ────────────────────────
        if clean_action == "add_layout":
            clean_klid = (klid or default_klid).strip().lower()
            if not re.match(r"^[0-9a-f]{8}$", clean_klid):
                return {
                    "status": "error",
                    "tag": canonical_tag,
                    "name": lang_name,
                    "action": clean_action,
                    "message": f"Некорректный код раскладки KLID: '{clean_klid}'.",
                    "language_packs": collect_language_packs_full(True),
                }
            _add_lang_to_user_profile(canonical_tag, meta["short"] if meta else canonical_tag)
            _add_keyboard_layout_to_registry(lcid, clean_klid, canonical_tag)
            layout_title = LAYOUT_DISPLAY_NAMES_RU.get(clean_klid, clean_klid.upper())
            logger.console(f"Добавлена раскладка клавиатуры {layout_title} ({clean_klid}) для {canonical_tag}")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Раскладка «{layout_title}» [{clean_klid.upper()}] добавлена для языка «{lang_name}».",
                "language_packs": collect_language_packs_full(True),
            }

        # ── 7. Удаление раскладки клавиатуры (KLID) ──────────────────────────
        if clean_action == "remove_layout":
            clean_klid = (klid or "").strip().lower()
            if not re.match(r"^[0-9a-f]{8}$", clean_klid):
                return {
                    "status": "error",
                    "tag": canonical_tag,
                    "name": lang_name,
                    "action": clean_action,
                    "message": f"Некорректный код раскладки KLID: '{clean_klid}'.",
                    "language_packs": collect_language_packs_full(True),
                }
            _remove_keyboard_layout_from_registry(lcid, clean_klid)
            layout_title = LAYOUT_DISPLAY_NAMES_RU.get(clean_klid, clean_klid.upper())
            logger.console(f"Удалена раскладка клавиатуры {layout_title} ({clean_klid}) для {canonical_tag}")
            return {
                "status": "ok",
                "tag": canonical_tag,
                "name": lang_name,
                "action": clean_action,
                "message": f"Раскладка «{layout_title}» [{clean_klid.upper()}] удалена.",
                "language_packs": collect_language_packs_full(True),
            }

        return {
            "status": "error",
            "tag": canonical_tag,
            "name": lang_name,
            "action": clean_action,
            "message": f"Неизвестное действие: '{clean_action}'.",
            "language_packs": collect_language_packs_full(True),
        }

    except Exception as exc:
        logger.error(f"[keyboard_helper] Ошибка выполнения {clean_action} для {canonical_tag}: {exc}")
        return {
            "status": "error",
            "tag": canonical_tag,
            "name": lang_name,
            "action": clean_action,
            "message": f"Ошибка выполнения операции: {exc}",
            "language_packs": collect_language_packs_full(is_windows),
        }


# ── Внутренние функции синхронизации реестра HKCU и Win32 API ────────────────

def _ensure_user_profile_languages(tags: List[str]) -> None:
    """Гарантирует наличие указанных языков в HKCU\\Control Panel\\International\\User Profile\\Languages."""
    import winreg
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\International\User Profile",
        0,
        winreg.KEY_ALL_ACCESS,
    ) as k_prof:
        try:
            cur_langs, _ = winreg.QueryValueEx(k_prof, "Languages")
            cur_list = [str(x) for x in cur_langs] if isinstance(cur_langs, (list, tuple)) else []
        except Exception:
            cur_list = []

        for t in tags:
            short = t.split("-")[0].lower()
            if not any(x.lower() == t.lower() or x.lower().split("-")[0] == short for x in cur_list):
                cur_list.append(t)

        winreg.SetValueEx(k_prof, "Languages", 0, winreg.REG_MULTI_SZ, cur_list)


def _add_lang_to_user_profile(canonical_tag: str, short_tag: str) -> None:
    """Добавляет язык в список Languages профиля пользователя."""
    _ensure_user_profile_languages([canonical_tag])


def _remove_lang_from_user_profile(canonical_tag: str, short_tag: str, lcid: str) -> None:
    """Удаляет язык из списка Languages и его раскладки из Preload."""
    import winreg
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\International\User Profile",
        0,
        winreg.KEY_ALL_ACCESS,
    ) as k_prof:
        try:
            cur_langs, _ = winreg.QueryValueEx(k_prof, "Languages")
            cur_list = [str(x) for x in cur_langs] if isinstance(cur_langs, (list, tuple)) else []
        except Exception:
            cur_list = []

        new_list = [
            x for x in cur_list
            if x.lower() != canonical_tag.lower() and x.lower().split("-")[0] != short_tag.lower()
        ]
        if new_list:
            winreg.SetValueEx(k_prof, "Languages", 0, winreg.REG_MULTI_SZ, new_list)

    # Удаляем все слоты этого LCID из Preload
    preload_items, substitutes = read_user_keyboard_state(True)
    remaining: List[Tuple[str, str]] = []
    for _, pre_val in preload_items:
        actual = substitutes.get(pre_val, pre_val)
        if not pre_val.endswith(lcid.lower()):
            remaining.append((pre_val, actual))
        else:
            # Выгружаем HKL из активной сессии, если возможно
            try:
                hkl = int(pre_val, 16)
                ctypes.windll.user32.UnloadKeyboardLayout(hkl)
            except Exception:
                pass

    _write_preload_and_substitutes(remaining)


def _move_lang_to_first(canonical_tag: str, short_tag: str, lcid: str, default_klid: str) -> None:
    """Перемещает выбранный язык и его раскладку на 1-е место в списке ввода."""
    import winreg
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\International\User Profile",
        0,
        winreg.KEY_ALL_ACCESS,
    ) as k_prof:
        try:
            cur_langs, _ = winreg.QueryValueEx(k_prof, "Languages")
            cur_list = [str(x) for x in cur_langs] if isinstance(cur_langs, (list, tuple)) else []
        except Exception:
            cur_list = []

        matched = [
            x for x in cur_list
            if x.lower() == canonical_tag.lower() or x.lower().split("-")[0] == short_tag.lower()
        ]
        others = [
            x for x in cur_list
            if x.lower() != canonical_tag.lower() and x.lower().split("-")[0] != short_tag.lower()
        ]
        first_entry = matched[0] if matched else canonical_tag
        winreg.SetValueEx(k_prof, "Languages", 0, winreg.REG_MULTI_SZ, [first_entry] + others)

    preload_items, substitutes = read_user_keyboard_state(True)
    target_pairs: List[Tuple[str, str]] = []
    other_pairs: List[Tuple[str, str]] = []
    for _, pre_val in preload_items:
        actual = substitutes.get(pre_val, pre_val)
        if pre_val.endswith(lcid.lower()):
            target_pairs.append((pre_val, actual))
        else:
            other_pairs.append((pre_val, actual))

    if not target_pairs:
        target_pairs.append((f"0000{lcid.lower()}", default_klid.lower()))

    _write_preload_and_substitutes(target_pairs + other_pairs)


def _add_keyboard_layout_to_registry(lcid: str, klid: str, canonical_tag: str) -> None:
    """Добавляет раскладку клавиатуры (KLID) в Preload, Substitutes и User Profile, а также загружает её."""
    import winreg
    lcid_clean = lcid.lower()
    klid_clean = klid.lower()

    preload_items, substitutes = read_user_keyboard_state(True)
    pairs: List[Tuple[str, str]] = []
    already_exists = False

    for _, pre_val in preload_items:
        actual = substitutes.get(pre_val, pre_val).lower()
        if actual == klid_clean and pre_val.endswith(lcid_clean):
            already_exists = True
        pairs.append((pre_val, actual))

    if not already_exists:
        base_preload = f"0000{lcid_clean}"
        used_preloads = {p[0].lower() for p in pairs}
        if klid_clean == base_preload and base_preload not in used_preloads:
            new_preload = base_preload
        elif base_preload not in used_preloads:
            new_preload = base_preload
        else:
            # Выделяем слот d001<LCID>, d002<LCID>...
            idx = 1
            while f"d{idx:03x}{lcid_clean}" in used_preloads:
                idx += 1
            new_preload = f"d{idx:03x}{lcid_clean}"

        pairs.append((new_preload, klid_clean))
        _write_preload_and_substitutes(pairs)

    # Обновляем подключ языка в HKCU\Control Panel\International\User Profile\<subkey>
    try:
        short = canonical_tag.split("-")[0].lower()
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\International\User Profile",
            0,
            winreg.KEY_ALL_ACCESS,
        ) as k_prof:
            sub_cnt, _, _ = winreg.QueryInfoKey(k_prof)
            existing_subs = [winreg.EnumKey(k_prof, i) for i in range(sub_cnt)]
            target_sub = canonical_tag
            for s in existing_subs:
                if s.lower() == canonical_tag.lower() or s.lower() == short:
                    target_sub = s
                    break
            with winreg.CreateKeyEx(k_prof, target_sub, 0, winreg.KEY_ALL_ACCESS) as k_lang:
                val_name = f"{lcid_clean.upper()}:{klid_clean.upper()}"
                winreg.SetValueEx(k_lang, val_name, 0, winreg.REG_DWORD, 1)
    except Exception as exc:
        logger.debug(f"[keyboard_helper] Ошибка записи раскладки в User Profile: {exc}")

    # Динамически подгружаем раскладку через Win32 LoadKeyboardLayoutW (KLF_ACTIVATE=1)
    try:
        ctypes.windll.user32.LoadKeyboardLayoutW(klid_clean, 1)
    except Exception:
        pass


def _remove_keyboard_layout_from_registry(lcid: str, klid: str) -> None:
    """Удаляет конкретную раскладку клавиатуры (KLID) из Preload, Substitutes и User Profile."""
    import winreg
    lcid_clean = lcid.lower()
    klid_clean = klid.lower()

    preload_items, substitutes = read_user_keyboard_state(True)
    new_pairs: List[Tuple[str, str]] = []
    removed_preloads: List[str] = []

    for _, pre_val in preload_items:
        actual = substitutes.get(pre_val, pre_val).lower()
        if actual == klid_clean and pre_val.endswith(lcid_clean):
            removed_preloads.append(pre_val)
        else:
            new_pairs.append((pre_val, actual))

    if new_pairs:
        _write_preload_and_substitutes(new_pairs)

    # Удаляем запись <LCID>:<KLID> из подразделов User Profile
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\International\User Profile",
            0,
            winreg.KEY_ALL_ACCESS,
        ) as k_prof:
            sub_cnt, _, _ = winreg.QueryInfoKey(k_prof)
            for idx in range(sub_cnt):
                sub_name = winreg.EnumKey(k_prof, idx)
                try:
                    with winreg.OpenKey(k_prof, sub_name, 0, winreg.KEY_ALL_ACCESS) as k_lang:
                        _, v_cnt, _ = winreg.QueryInfoKey(k_lang)
                        to_del = []
                        for j in range(v_cnt):
                            v_name, _, _ = winreg.EnumValue(k_lang, j)
                            if str(v_name).lower() == f"{lcid_clean}:{klid_clean}":
                                to_del.append(v_name)
                        for d_name in to_del:
                            winreg.DeleteValue(k_lang, d_name)
                except Exception:
                    continue
    except Exception:
        pass


def _write_preload_and_substitutes(pairs: List[Tuple[str, str]]) -> None:
    """Перезаписывает упорядоченный список Preload и таблицу Substitutes в HKCU."""
    import winreg
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Keyboard Layout\Preload",
        0,
        winreg.KEY_ALL_ACCESS,
    ) as k_pre:
        _, v_cnt, _ = winreg.QueryInfoKey(k_pre)
        old_names = [winreg.EnumValue(k_pre, i)[0] for i in range(v_cnt)]
        for name in old_names:
            try:
                winreg.DeleteValue(k_pre, name)
            except Exception:
                pass
        for idx, (pre_val, _) in enumerate(pairs, start=1):
            winreg.SetValueEx(k_pre, str(idx), 0, winreg.REG_SZ, pre_val.lower())

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Keyboard Layout\Substitutes",
        0,
        winreg.KEY_ALL_ACCESS,
    ) as k_sub:
        _, v_cnt, _ = winreg.QueryInfoKey(k_sub)
        old_subs = [winreg.EnumValue(k_sub, i)[0] for i in range(v_cnt)]
        for name in old_subs:
            try:
                winreg.DeleteValue(k_sub, name)
            except Exception:
                pass
        for pre_val, actual_val in pairs:
            if pre_val.lower() != actual_val.lower():
                winreg.SetValueEx(k_sub, pre_val.lower(), 0, winreg.REG_SZ, actual_val.lower())


def get_detailed_language_packs() -> List[Dict[str, Any]]:
    """Возвращает детальный список языковых пакетов и раскладок клавиатуры текущей ОС."""
    is_win = (os.name == "nt" or platform.system().lower() == "windows")
    return collect_language_packs_full(is_win)


