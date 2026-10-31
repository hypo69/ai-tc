# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_system
# =============================================================================
# Description:
#   Эндпойнты изменения параметров системы.
#   Вынесено из router_about_system.py (этап 4 оптимизации).
#
# File: endpoints_system.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-28 14:43:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import subprocess
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.sdk import windows_sdk
from .models import ChangeWorkgroupRequest
from .models import ChangeWorkgroupResponse
from .models import LocaleOption
from .models import RegionalOptionsResponse
from .models import LanguagePackInfo
from .models import InstallLanguagePackRequest
from .models import InstallLanguagePackResponse
from .models import ManageLanguagePackRequest
from .models import ManageLanguagePackResponse
from .models import RenameComputerRequest
from .models import RenameComputerResponse
from .models import SetLocaleRequest
from .models import SetLocaleResponse
from .models import SetTimezoneRequest
from .models import SetTimezoneResponse
from .models import TimezoneOption
from .models import UpdateUserProfileRequest
from .models import UpdateUserProfileResponse
from .models import SetNetworkCategoryRequest
from .models import SetNetworkCategoryResponse
from .models import ToggleNetworkDiscoveryRequest
from .models import ToggleNetworkDiscoveryResponse
from .models import NetworkProfileStatusResponse


def register_system_action_endpoints(router: APIRouter, storage: TelemetryStorage) -> None:
    """Регистрирует эндпойнты изменения имени, рабочей группы, региона и профиля."""
    # =========================================================================
    # 9. Переименование компьютера: POST /api/v1/system/rename-computer
    # =========================================================================
    @router.post("/api/v1/system/rename-computer", response_model=RenameComputerResponse)
    async def rename_computer_endpoint(req: RenameComputerRequest) -> RenameComputerResponse:
        """Переименование компьютера в Windows через Windows SDK."""
        old_name = platform.node() or "Host"
        clean_name = req.new_name.strip()

        res = await asyncio.to_thread(windows_sdk.modules.regional.rename_computer, clean_name)
        msg = res.get("message", "")
        restart_sched = False

        if res.get("status") == "ok" and req.restart:
            await asyncio.create_subprocess_exec("shutdown.exe", "/r", "/t", "5", "/c", "AI-Windows-Admin: Перезагрузка для применения нового имени хоста.")
            msg += " Перезагрузка системы запланирована через 5 секунд."
            restart_sched = True

        return RenameComputerResponse(
            status=res.get("status", "ok"),
            old_name=res.get("old_name", old_name),
            new_name=clean_name,
            message=msg,
            restart_scheduled=restart_sched,
        )

    # =========================================================================
    # 10. Изменение рабочей группы: POST /api/v1/system/change-workgroup
    # =========================================================================
    @router.post("/api/v1/system/change-workgroup", response_model=ChangeWorkgroupResponse)
    async def change_workgroup_endpoint(req: ChangeWorkgroupRequest) -> ChangeWorkgroupResponse:
        """Изменение рабочей группы в Windows через Windows SDK."""
        old_wg = windows_sdk.modules.regional.get_workgroup()
        clean_wg = req.new_workgroup.strip().upper()

        res = await asyncio.to_thread(windows_sdk.modules.regional.change_workgroup, clean_wg)
        msg = res.get("message", "")
        restart_sched = False

        if res.get("status") == "ok" and req.restart:
            await asyncio.create_subprocess_exec("shutdown.exe", "/r", "/t", "5", "/c", "AI-Windows-Admin: Перезагрузка для применения новой рабочей группы.")
            msg += " Перезагрузка системы запланирована через 5 секунд."
            restart_sched = True

        return ChangeWorkgroupResponse(
            status=res.get("status", "ok"),
            old_workgroup=res.get("old_workgroup", old_wg),
            new_workgroup=clean_wg,
            message=msg,
            restart_scheduled=restart_sched,
        )

    # =========================================================================
    # 11. Получение региональных настроек: GET /api/v1/system/regional-options
    # =========================================================================
    @router.get("/api/v1/system/regional-options", response_model=RegionalOptionsResponse)
    async def get_regional_options_endpoint() -> RegionalOptionsResponse:
        """Получение текущих региональных параметров, списка часовых поясов и локалей."""
        def _fetch_options() -> RegionalOptionsResponse:
            rm = windows_sdk.modules.regional

            # Текущая таймзона и список часовых поясов
            current_tz_id = rm.get_current_timezone()
            tz_raw = rm.get_timezones()
            tz_list: List[TimezoneOption] = [
                TimezoneOption(
                    id=t["id"],
                    display_name=t["display_name"],
                    offset_minutes=t.get("offset_minutes", 0),
                )
                for t in tz_raw
            ]

            current_tz_name = current_tz_id
            if current_tz_id:
                for t in tz_list:
                    if t.id.lower() == current_tz_id.lower():
                        current_tz_name = t.display_name
                        break

            # Системная и пользовательская локали
            loc_dict = rm.get_current_locales()
            current_sys_loc = loc_dict.get("system_locale", "ru-RU")
            current_usr_loc = loc_dict.get("user_locale", "ru-RU")

            # Пользователь ОС
            user_info = rm.get_user_account_info()
            username = user_info.get("username") or os.environ.get("USERNAME", "User")
            user_fullname = user_info.get("full_name") or ""
            user_first_name = user_info.get("first_name") or ""
            user_last_name = user_info.get("last_name") or ""
            user_desc = user_info.get("description") or ""
            user_sid = user_info.get("sid") or ""
            user_profile = user_info.get("profile_dir") or ""
            user_domain = user_info.get("domain") or ""
            user_groups = user_info.get("groups") or []
            user_account_type = user_info.get("account_type") or "Локальная учетная запись"
            user_last_logon = user_info.get("last_logon") or ""
            codepage = "UTF-8 (65001)"

            curated_locales = [
                LocaleOption(code="ru-RU", name="Русский (Россия) [ru-RU]"),
                LocaleOption(code="en-US", name="English (United States) [en-US]"),
                LocaleOption(code="en-GB", name="English (United Kingdom) [en-GB]"),
                LocaleOption(code="he-IL", name="עברית (ישראל) [he-IL]"),
                LocaleOption(code="de-DE", name="Deutsch (Deutschland) [de-DE]"),
                LocaleOption(code="fr-FR", name="Français (France) [fr-FR]"),
                LocaleOption(code="es-ES", name="Español (España) [es-ES]"),
                LocaleOption(code="it-IT", name="Italiano (Italia) [it-IT]"),
                LocaleOption(code="zh-CN", name="中文 (简体, 中国) [zh-CN]"),
                LocaleOption(code="ja-JP", name="日本語 (日本) [ja-JP]"),
                LocaleOption(code="tr-TR", name="Türkçe (Türkiye) [tr-TR]"),
                LocaleOption(code="uk-UA", name="Українська (Україна) [uk-UA]"),
                LocaleOption(code="pl-PL", name="Polski (Polska) [pl-PL]"),
                LocaleOption(code="pt-BR", name="Português (Brasil) [pt-BR]"),
            ]

            # Сетевой профиль и обнаружение сети
            net_cat = "Public"
            net_idx = None
            is_disc_en = False
            try:
                disc_info = windows_sdk.modules.network_discovery.inspect()
                net_cat = disc_info.get("current_category", "Public")
                net_idx = disc_info.get("primary_interface_index")
                is_disc_en = disc_info.get("is_discovery_enabled", False)
            except Exception as e:
                logger.debug(f"[router_about_system] Ошибка сбора сетевого профиля: {e}")

            # Языковые пакеты Windows (Русский, Иврит, Английский)
            lang_packs: List[LanguagePackInfo] = []
            os_inst_lang = ""
            disp_lang = ""
            try:
                from apps.windows.sdk.modules.regional.keyboard_helper import get_system_language_identity
                ident = get_system_language_identity(os.name == "nt")
                os_inst_lang = ident.get("os_install_language", "")
                disp_lang = ident.get("display_language", "")
                lang_packs = [LanguagePackInfo(**p) for p in rm.get_language_packs()]
            except Exception as e:
                logger.debug(f"[router_about_system] Ошибка сбора языковых пакетов: {e}")

            return RegionalOptionsResponse(
                status="ok",
                current_timezone=current_tz_id,
                current_timezone_name=current_tz_name,
                current_system_locale=current_sys_loc,
                current_user_locale=current_usr_loc,
                current_username=username,
                current_user_fullname=user_fullname,
                current_user_first_name=user_first_name,
                current_user_last_name=user_last_name,
                current_user_description=user_desc,
                current_user_sid=user_sid,
                current_user_profile=user_profile,
                current_user_domain=user_domain,
                current_user_groups=user_groups,
                current_user_account_type=user_account_type,
                current_user_last_logon=user_last_logon,
                current_codepage=codepage,
                network_category=net_cat,
                network_interface_index=net_idx,
                is_discovery_enabled=is_disc_en,
                timezones=tz_list,
                locales=curated_locales,
                language_packs=lang_packs,
                os_install_language=os_inst_lang,
                display_language=disp_lang,
            )

        return await asyncio.to_thread(_fetch_options)

    # =========================================================================
    # 12. Установка часового пояса: POST /api/v1/system/set-timezone
    # =========================================================================
    @router.post("/api/v1/system/set-timezone", response_model=SetTimezoneResponse)
    async def set_timezone_endpoint(req: SetTimezoneRequest) -> SetTimezoneResponse:
        """Изменение часового пояса Windows через Windows SDK."""
        res = await asyncio.to_thread(windows_sdk.modules.regional.set_timezone, req.timezone_id)
        return SetTimezoneResponse(
            status=res.get("status", "ok"),
            old_timezone=res.get("old_timezone", ""),
            new_timezone=res.get("new_timezone", req.timezone_id),
            message=res.get("message", ""),
        )

    # =========================================================================
    # 13. Установка системной локали: POST /api/v1/system/set-locale
    # =========================================================================
    @router.post("/api/v1/system/set-locale", response_model=SetLocaleResponse)
    async def set_locale_endpoint(req: SetLocaleRequest) -> SetLocaleResponse:
        """Изменение системной локали Windows через Windows SDK."""
        res = await asyncio.to_thread(windows_sdk.modules.regional.set_locale, req.system_locale, req.user_locale)
        return SetLocaleResponse(
            status=res.get("status", "ok"),
            system_locale=res.get("locale", req.system_locale),
            message=res.get("message", ""),
            restart_required=res.get("reboot_required", True),
        )

    # =========================================================================
    # 14. Обновление профиля пользователя: POST /api/v1/system/update-user-profile
    # =========================================================================
    @router.post("/api/v1/system/update-user-profile", response_model=UpdateUserProfileResponse)
    async def update_user_profile_endpoint(req: UpdateUserProfileRequest) -> UpdateUserProfileResponse:
        """Обновление описания и полного имени локального пользователя через Set-LocalUser."""
        target_user = req.username.strip() or os.environ.get("USERNAME", "User")
        if not re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", target_user):
            return UpdateUserProfileResponse(
                status="error",
                username=target_user,
                message="Недопустимое имя пользователя.",
            )

        ps_args = []
        if req.full_name is not None:
            clean_fn = req.full_name.replace("'", "''")
            ps_args.append(f"-FullName '{clean_fn}'")
        if req.description is not None:
            clean_desc = req.description.replace("'", "''")
            ps_args.append(f"-Description '{clean_desc}'")

        if not ps_args:
            return UpdateUserProfileResponse(
                status="ok",
                username=target_user,
                message="Параметры для изменения не указаны.",
            )

        try:
            cmd = f"Set-LocalUser -Name '{target_user}' " + " ".join(ps_args)
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip()
                logger.warning(f"[router_about_system] Ошибка Set-LocalUser: {err_text}")
                return UpdateUserProfileResponse(
                    status="error",
                    username=target_user,
                    message=f"Не удалось обновить профиль пользователя: {err_text}. Требуются права администратора.",
                )

            return UpdateUserProfileResponse(
                status="ok",
                username=target_user,
                message=f"Профиль пользователя '{target_user}' успешно обновлен.",
            )
        except Exception as exc:
            logger.error(f"[router_about_system] Ошибка при обновлении профиля пользователя: {exc}", exc_info=True)
            return UpdateUserProfileResponse(
                status="error",
                username=target_user,
                message=f"Внутренняя ошибка: {exc}",
            )

    # =========================================================================
    # 15. Проверка сетевого профиля и обнаружения: GET /api/v1/system/network-profile
    # =========================================================================
    @router.get("/api/v1/system/network-profile", response_model=NetworkProfileStatusResponse)
    async def get_network_profile_endpoint() -> NetworkProfileStatusResponse:
        """Инспекция сетевых профилей, состояния служб и брандмауэра для сетевого обнаружения."""
        def _inspect():
            return windows_sdk.modules.network_discovery.inspect()

        res = await asyncio.to_thread(_inspect)
        return NetworkProfileStatusResponse(
            status=res.get("status", "ok"),
            is_discovery_enabled=res.get("is_discovery_enabled", False),
            current_category=res.get("current_category", "Public"),
            primary_interface_index=res.get("primary_interface_index"),
            primary_profile=res.get("primary_profile"),
            profiles=res.get("profiles", []),
            services=res.get("services", {}),
            firewall=res.get("firewall", {}),
        )

    # =========================================================================
    # 16. Переключение категории профиля (Public/Private): POST /api/v1/system/network-profile/category
    # =========================================================================
    @router.post("/api/v1/system/network-profile/category", response_model=SetNetworkCategoryResponse)
    async def set_network_category_endpoint(req: SetNetworkCategoryRequest) -> SetNetworkCategoryResponse:
        """Изменение категории профиля сети (Public или Private)."""
        def _set_category():
            return windows_sdk.modules.network_discovery.set_network_category(
                category=req.category,
                interface_index=req.interface_index,
            )

        res = await asyncio.to_thread(_set_category)
        return SetNetworkCategoryResponse(
            status=res.get("status", "ok"),
            interface_index=res.get("interface_index"),
            category=res.get("category", req.category),
            message=res.get("message", ""),
        )

    # =========================================================================
    # 17. Включение/отключение сетевого обнаружения: POST /api/v1/system/network-discovery/toggle
    # =========================================================================
    @router.post("/api/v1/system/network-discovery/toggle", response_model=ToggleNetworkDiscoveryResponse)
    async def toggle_network_discovery_endpoint(req: ToggleNetworkDiscoveryRequest) -> ToggleNetworkDiscoveryResponse:
        """Включение или безопасное отключение сетевого обнаружения хоста."""
        def _toggle():
            if req.enabled:
                set_private = (req.set_category == "Private")
                return windows_sdk.modules.network_discovery.enable(
                    interface_index=req.interface_index,
                    set_private=set_private,
                )
            else:
                set_public = (req.set_category == "Public")
                return windows_sdk.modules.network_discovery.disable(
                    interface_index=req.interface_index,
                    set_public=set_public,
                )

        res = await asyncio.to_thread(_toggle)
        state = res.get("state", {})
        return ToggleNetworkDiscoveryResponse(
            status=res.get("status", "ok"),
            message=res.get("message", ""),
            actions=res.get("actions", []),
            is_discovery_enabled=state.get("is_discovery_enabled", req.enabled),
            current_category=state.get("current_category", "Public"),
        )

    # =========================================================================
    # 18. Установка/активация языкового пакета: POST /api/v1/system/install-language-pack
    # =========================================================================
    @router.post("/api/v1/system/install-language-pack", response_model=InstallLanguagePackResponse)
    async def install_language_pack_endpoint(req: InstallLanguagePackRequest) -> InstallLanguagePackResponse:
        """Установка или активация языкового пакета Windows через Windows SDK."""
        res = await asyncio.to_thread(windows_sdk.modules.regional.install_language_pack, req.tag)
        packs = [LanguagePackInfo(**p) for p in res.get("language_packs", [])]
        return InstallLanguagePackResponse(
            status=res.get("status", "ok"),
            tag=res.get("tag", req.tag),
            name=res.get("name", req.tag),
            message=res.get("message", ""),
            installed=res.get("is_installed", False),
            is_installed=res.get("is_installed", False),
            is_active=res.get("is_active", False),
            language_packs=packs,
        )

    # =========================================================================
    # 19. Полное управление языковыми пакетами и раскладками: POST /api/v1/system/manage-language-pack
    # =========================================================================
    @router.post("/api/v1/system/manage-language-pack", response_model=ManageLanguagePackResponse)
    async def manage_language_pack_endpoint(req: ManageLanguagePackRequest) -> ManageLanguagePackResponse:
        """Полное управление тройкой языковых пакетов (Русский, Иврит, Английский) и их раскладками клавиатуры."""
        res = await asyncio.to_thread(
            windows_sdk.modules.regional.manage_language_pack,
            req.tag,
            req.action,
            req.klid,
        )
        packs = [LanguagePackInfo(**p) for p in res.get("language_packs", [])]
        return ManageLanguagePackResponse(
            status=res.get("status", "ok"),
            tag=res.get("tag", req.tag),
            name=res.get("name", req.tag),
            action=res.get("action", req.action),
            message=res.get("message", ""),
            language_packs=packs,
        )



