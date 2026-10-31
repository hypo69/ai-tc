# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Audio Module - Sound Manager
# =============================================================================
# Description:
#   Диспетчер управления звуковой подсистемой Windows на базе Core Audio WASAPI
#   и реестра Windows. Позволяет считывать и настраивать мастер-громкость,
#   громкость системных звуков, сессии приложений, устройства и звуковые схемы.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.sound.manager import SoundManager
#     mgr = SoundManager()
#     state = mgr.get_state()
#     mgr.set_system_sounds_volume(75)
#
# File: manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.sound
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

from __future__ import annotations
"""Диспетчер звуковой подсистемы Windows на базе WASAPI Core Audio."""

import ctypes
import os
import subprocess
from ctypes import HRESULT, POINTER, byref, c_bool, c_float, c_int, c_void_p, wintypes
from typing import List, Optional, Tuple

import psutil
from logger import logger
from .models import (
    AudioDeviceDTO,
    SoundSchemeDTO,
    SoundSessionDTO,
    SoundSettingsDTO,
)
from .wasapi import (
    CLSID_MMDEVICE_ENUMERATOR,
    IID_IAUDIO_ENDPOINT_VOLUME,
    IID_IAUDIO_SESSION_CONTROL2,
    IID_IAUDIO_SESSION_MANAGER2,
    IID_IMMDEVICE_ENUMERATOR,
    IID_ISIMPLE_AUDIO_VOLUME,
    GUID,
    parse_guid,
)

try:
    import winreg
except ImportError:
    winreg = None

try:
    import winsound
except ImportError:
    winsound = None


class SoundManager:
    """Менеджер управления звуковой подсистемой Windows."""

    def __init__(self) -> None:
        """Инициализация менеджера и кэша GUID."""
        self._init_com()
        self._clsid_enum = parse_guid(CLSID_MMDEVICE_ENUMERATOR)
        self._iid_enum = parse_guid(IID_IMMDEVICE_ENUMERATOR)
        self._iid_epv = parse_guid(IID_IAUDIO_ENDPOINT_VOLUME)
        self._iid_sm2 = parse_guid(IID_IAUDIO_SESSION_MANAGER2)
        self._iid_ctl2 = parse_guid(IID_IAUDIO_SESSION_CONTROL2)
        self._iid_sav = parse_guid(IID_ISIMPLE_AUDIO_VOLUME)

    def _init_com(self) -> None:
        """Инициализирует COM-подсистему в текущем потоке."""
        ctypes.windll.ole32.CoInitialize(None)

    def _get_default_render_device(self) -> Tuple[Optional[c_void_p], Optional[str]]:
        """Возвращает указатель на устройство вывода по умолчанию и его ID."""
        self._init_com()
        p_enum = c_void_p()
        hr = ctypes.windll.ole32.CoCreateInstance(
            byref(self._clsid_enum), None, 1 | 2 | 4 | 16, byref(self._iid_enum), byref(p_enum)
        )
        if hr != 0 or not p_enum.value:
            return None, None

        vtbl_enum = ctypes.cast(ctypes.cast(p_enum, POINTER(c_void_p)).contents, POINTER(c_void_p))
        get_default = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_int, c_int, POINTER(c_void_p))(vtbl_enum[4])

        p_dev = c_void_p()
        hr = get_default(p_enum, 0, 1, byref(p_dev))
        if hr != 0 or not p_dev.value:
            return None, None

        vtbl_dev = ctypes.cast(ctypes.cast(p_dev, POINTER(c_void_p)).contents, POINTER(c_void_p))
        get_id = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(wintypes.LPWSTR))(vtbl_dev[5])
        dev_id = wintypes.LPWSTR()
        get_id(p_dev, byref(dev_id))

        return p_dev, (dev_id.value if dev_id.value else None)

    def get_state(self) -> SoundSettingsDTO:
        """Возвращает полное состояние звуковой подсистемы Windows."""
        master_vol, master_mute = 50, False
        sys_vol, sys_mute = 100, False
        sessions: List[SoundSessionDTO] = []
        default_dev_id: Optional[str] = None

        try:
            p_dev, default_dev_id = self._get_default_render_device()
            if p_dev and p_dev.value:
                vtbl_dev = ctypes.cast(ctypes.cast(p_dev, POINTER(c_void_p)).contents, POINTER(c_void_p))
                activate = ctypes.WINFUNCTYPE(
                    HRESULT, c_void_p, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
                )(vtbl_dev[3])

                # Мастер-громкость
                p_epv = c_void_p()
                if activate(p_dev, byref(self._iid_epv), 23, None, byref(p_epv)) == 0 and p_epv.value:
                    vtbl_epv = ctypes.cast(ctypes.cast(p_epv, POINTER(c_void_p)).contents, POINTER(c_void_p))
                    get_vol = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_float))(vtbl_epv[9])
                    get_mute = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_bool))(vtbl_epv[14])
                    v, m = c_float(), c_bool()
                    get_vol(p_epv, byref(v))
                    get_mute(p_epv, byref(m))
                    master_vol = int(round(v.value * 100))
                    master_mute = bool(m.value)

                # Сессии и системные звуки
                p_sm2 = c_void_p()
                if activate(p_dev, byref(self._iid_sm2), 23, None, byref(p_sm2)) == 0 and p_sm2.value:
                    sessions, f_vol, f_mute = self._read_audio_sessions(p_sm2)
                    if f_vol is not None:
                        sys_vol, sys_mute = f_vol, bool(f_mute)
        except Exception as exc:
            logger.warning(f"[SoundManager] Ошибка чтения WASAPI состояния звука: {exc}")

        out_devs, in_devs = self._get_devices_from_registry(default_dev_id)
        default_out_name = next((d.name for d in out_devs if d.is_default), out_devs[0].name if out_devs else None)

        return SoundSettingsDTO(
            master_volume=master_vol,
            master_muted=master_mute,
            system_sounds_volume=sys_vol,
            system_sounds_muted=sys_mute,
            startup_sound_enabled=self._get_startup_sound_enabled(),
            current_scheme=self._get_sound_schemes()[0],
            default_output_device=default_out_name,
            output_devices=out_devs,
            input_devices=in_devs,
            active_sessions=sessions,
            available_schemes=self._get_sound_schemes()[1],
        )

    def _read_audio_sessions(self, p_sm2: c_void_p) -> Tuple[List[SoundSessionDTO], Optional[int], Optional[bool]]:
        """Считывает список аудиосессий из IAudioSessionManager2."""
        vtbl_sm2 = ctypes.cast(ctypes.cast(p_sm2, POINTER(c_void_p)).contents, POINTER(c_void_p))
        get_sess_enum = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_void_p))(vtbl_sm2[5])
        p_enum = c_void_p()
        if get_sess_enum(p_sm2, byref(p_enum)) != 0 or not p_enum.value:
            return [], None, None

        vtbl_enum = ctypes.cast(ctypes.cast(p_enum, POINTER(c_void_p)).contents, POINTER(c_void_p))
        get_count = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_int))(vtbl_enum[3])
        get_sess = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_int, POINTER(c_void_p))(vtbl_enum[4])

        cnt = c_int()
        get_count(p_enum, byref(cnt))
        sessions: List[SoundSessionDTO] = []
        found_sys_vol, found_sys_mute = None, None

        for i in range(cnt.value):
            p_ctl = c_void_p()
            if get_sess(p_enum, i, byref(p_ctl)) != 0 or not p_ctl.value:
                continue

            vtbl_ctl = ctypes.cast(ctypes.cast(p_ctl, POINTER(c_void_p)).contents, POINTER(c_void_p))
            query_interface = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(vtbl_ctl[0])

            p_ctl2, p_sav = c_void_p(), c_void_p()
            query_interface(p_ctl, byref(self._iid_ctl2), byref(p_ctl2))
            query_interface(p_ctl, byref(self._iid_sav), byref(p_sav))
            if not p_ctl2.value or not p_sav.value:
                continue

            vtbl_ctl2 = ctypes.cast(ctypes.cast(p_ctl2, POINTER(c_void_p)).contents, POINTER(c_void_p))
            vtbl_sav = ctypes.cast(ctypes.cast(p_sav, POINTER(c_void_p)).contents, POINTER(c_void_p))

            get_pid = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(wintypes.DWORD))(vtbl_ctl2[14])
            is_sys_session = ctypes.WINFUNCTYPE(HRESULT, c_void_p)(vtbl_ctl2[15])
            pid = wintypes.DWORD()
            get_pid(p_ctl2, byref(pid))
            is_sys = (is_sys_session(p_ctl2) == 0)

            get_vol = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_float))(vtbl_sav[4])
            get_mute = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_bool))(vtbl_sav[6])
            svol, smute = c_float(), c_bool()
            get_vol(p_sav, byref(svol))
            get_mute(p_sav, byref(smute))
            vol_pct, is_muted = int(round(svol.value * 100)), bool(smute.value)

            if is_sys:
                found_sys_vol, found_sys_mute = vol_pct, is_muted
                sessions.append(
                    SoundSessionDTO(
                        id="system_sounds",
                        name="Системные звуки Windows",
                        pid=0,
                        volume=vol_pct,
                        is_muted=is_muted,
                        is_system_sounds=True,
                    )
                )
            else:
                proc_name = f"Процесс PID {pid.value}"
                if pid.value > 0:
                    try:
                        proc_name = psutil.Process(pid.value).name()
                    except Exception:
                        pass
                sessions.append(
                    SoundSessionDTO(
                        id=str(pid.value),
                        name=proc_name,
                        pid=pid.value,
                        volume=vol_pct,
                        is_muted=is_muted,
                        is_system_sounds=False,
                    )
                )
        return sessions, found_sys_vol, found_sys_mute

    def set_master_volume(self, volume: int) -> bool:
        """Устанавливает мастер-громкость (0-100%)."""
        try:
            p_dev, _ = self._get_default_render_device()
            if not p_dev or not p_dev.value:
                return False
            vtbl_dev = ctypes.cast(ctypes.cast(p_dev, POINTER(c_void_p)).contents, POINTER(c_void_p))
            activate = ctypes.WINFUNCTYPE(
                HRESULT, c_void_p, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
            )(vtbl_dev[3])
            p_epv = c_void_p()
            if activate(p_dev, byref(self._iid_epv), 23, None, byref(p_epv)) == 0 and p_epv.value:
                vtbl_epv = ctypes.cast(ctypes.cast(p_epv, POINTER(c_void_p)).contents, POINTER(c_void_p))
                set_vol = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_float, POINTER(GUID))(vtbl_epv[7])
                scalar = max(0.0, min(1.0, float(volume) / 100.0))
                return set_vol(p_epv, c_float(scalar), None) == 0
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка установки мастер-громкости: {exc}")
        return False

    def set_master_mute(self, mute: bool) -> bool:
        """Включает или выключает Master Mute."""
        try:
            p_dev, _ = self._get_default_render_device()
            if not p_dev or not p_dev.value:
                return False
            vtbl_dev = ctypes.cast(ctypes.cast(p_dev, POINTER(c_void_p)).contents, POINTER(c_void_p))
            activate = ctypes.WINFUNCTYPE(
                HRESULT, c_void_p, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
            )(vtbl_dev[3])
            p_epv = c_void_p()
            if activate(p_dev, byref(self._iid_epv), 23, None, byref(p_epv)) == 0 and p_epv.value:
                vtbl_epv = ctypes.cast(ctypes.cast(p_epv, POINTER(c_void_p)).contents, POINTER(c_void_p))
                set_mute = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_bool, POINTER(GUID))(vtbl_epv[13])
                return set_mute(p_epv, c_bool(mute), None) == 0
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка переключения Master Mute: {exc}")
        return False

    def set_system_sounds_volume(self, volume: int) -> bool:
        """Устанавливает уровень громкости системных звуков Windows."""
        return self.set_session_volume("system_sounds", volume)

    def set_system_sounds_mute(self, mute: bool) -> bool:
        """Включает или отключает приглушение системных звуков Windows."""
        return self.set_session_mute("system_sounds", mute)

    def _modify_session(self, target: str, is_volume: bool, value: Any) -> bool:
        """Вспомогательный метод изменения громкости или mute аудиосессии."""
        try:
            p_dev, _ = self._get_default_render_device()
            if not p_dev or not p_dev.value:
                return False
            vtbl_dev = ctypes.cast(ctypes.cast(p_dev, POINTER(c_void_p)).contents, POINTER(c_void_p))
            activate = ctypes.WINFUNCTYPE(
                HRESULT, c_void_p, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
            )(vtbl_dev[3])
            p_sm2 = c_void_p()
            if activate(p_dev, byref(self._iid_sm2), 23, None, byref(p_sm2)) != 0 or not p_sm2.value:
                return False

            vtbl_sm2 = ctypes.cast(ctypes.cast(p_sm2, POINTER(c_void_p)).contents, POINTER(c_void_p))
            get_sess_enum = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_void_p))(vtbl_sm2[5])
            p_enum = c_void_p()
            if get_sess_enum(p_sm2, byref(p_enum)) != 0 or not p_enum.value:
                return False

            vtbl_enum = ctypes.cast(ctypes.cast(p_enum, POINTER(c_void_p)).contents, POINTER(c_void_p))
            get_count = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_int))(vtbl_enum[3])
            get_sess = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_int, POINTER(c_void_p))(vtbl_enum[4])
            cnt = c_int()
            get_count(p_enum, byref(cnt))

            matched = False
            for i in range(cnt.value):
                p_ctl = c_void_p()
                if get_sess(p_enum, i, byref(p_ctl)) != 0 or not p_ctl.value:
                    continue
                vtbl_ctl = ctypes.cast(ctypes.cast(p_ctl, POINTER(c_void_p)).contents, POINTER(c_void_p))
                query_interface = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(vtbl_ctl[0])

                p_ctl2, p_sav = c_void_p(), c_void_p()
                query_interface(p_ctl, byref(self._iid_ctl2), byref(p_ctl2))
                query_interface(p_ctl, byref(self._iid_sav), byref(p_sav))
                if not p_ctl2.value or not p_sav.value:
                    continue

                vtbl_ctl2 = ctypes.cast(ctypes.cast(p_ctl2, POINTER(c_void_p)).contents, POINTER(c_void_p))
                vtbl_sav = ctypes.cast(ctypes.cast(p_sav, POINTER(c_void_p)).contents, POINTER(c_void_p))

                get_pid = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(wintypes.DWORD))(vtbl_ctl2[14])
                is_sys_session = ctypes.WINFUNCTYPE(HRESULT, c_void_p)(vtbl_ctl2[15])
                pid = wintypes.DWORD()
                get_pid(p_ctl2, byref(pid))
                is_sys = (is_sys_session(p_ctl2) == 0)

                if (target == "system_sounds" and is_sys) or (str(pid.value) == target):
                    if is_volume:
                        set_vol = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_float, POINTER(GUID))(vtbl_sav[3])
                        scalar = max(0.0, min(1.0, float(value) / 100.0))
                        set_vol(p_sav, c_float(scalar), None)
                    else:
                        set_mute = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_bool, POINTER(GUID))(vtbl_sav[5])
                        set_mute(p_sav, c_bool(value), None)
                    matched = True
            return matched
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка изменения сессии {target}: {exc}")
        return False

    def set_session_volume(self, target: str, volume: int) -> bool:
        """Устанавливает громкость аудиосессии (PID или 'system_sounds')."""
        return self._modify_session(target, is_volume=True, value=volume)

    def set_session_mute(self, target: str, mute: bool) -> bool:
        """Переключает Mute конкретной аудиосессии."""
        return self._modify_session(target, is_volume=False, value=mute)

    def set_startup_sound(self, enabled: bool) -> bool:
        """Включает или отключает звук при загрузке Windows."""
        if not winreg:
            return False
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI\BootAnimation"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
                val = 0 if enabled else 1
                winreg.SetValueEx(key, "DisableStartupSound", 0, winreg.REG_DWORD, val)
                return True
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка настройки звука запуска: {exc}")
        return False

    def play_test_sound(self, sound_type: str = "asterisk") -> bool:
        """Воспроизводит системный звуковой сигнал Windows."""
        try:
            if winsound:
                sound_map = {
                    "asterisk": winsound.MB_ICONASTERISK,
                    "exclamation": winsound.MB_ICONEXCLAMATION,
                    "beep": -1,
                    "question": winsound.MB_ICONQUESTION,
                }
                flag = sound_map.get(sound_type.lower(), winsound.MB_ICONASTERISK)
                winsound.MessageBeep(flag)
                return True
            ctypes.windll.user32.MessageBeep(0)
            return True
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка воспроизведения звука: {exc}")
        return False

    def launch_tool(self, tool: str = "settings") -> bool:
        """Открывает нативное системное окно параметров звука Windows."""
        try:
            tool_l = tool.lower()
            if tool_l == "sndvol":
                subprocess.Popen(["sndvol.exe"], shell=False)
            elif tool_l == "mmsys":
                subprocess.Popen(["control.exe", "mmsys.cpl"], shell=False)
            else:
                os.system("start ms-settings:sound")
            return True
        except Exception as exc:
            logger.error(f"[SoundManager] Ошибка запуска системного инструмента {tool}: {exc}")
        return False

    def _get_startup_sound_enabled(self) -> bool:
        """Считывает состояние звука запуска из реестра."""
        if not winreg:
            return True
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI\BootAnimation"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "DisableStartupSound")
                return val == 0
        except Exception:
            return True

    def _get_sound_schemes(self) -> Tuple[str, List[SoundSchemeDTO]]:
        """Считывает доступные звуковые схемы и текущую схему."""
        cur_scheme = ".Default"
        schemes = [
            SoundSchemeDTO(id=".Default", name="Windows по умолчанию", is_current=True),
            SoundSchemeDTO(id=".None", name="Без звука", is_current=False),
        ]
        if not winreg:
            return cur_scheme, schemes
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"AppEvents\Schemes", 0, winreg.KEY_READ) as key:
                cur, _ = winreg.QueryValueEx(key, "")
                if cur:
                    cur_scheme = str(cur)

            names_path = r"AppEvents\Schemes\Names"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, names_path, 0, winreg.KEY_READ) as key:
                found_schemes = []
                idx = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, idx)
                        idx += 1
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            disp_name, _ = winreg.QueryValueEx(subkey, "")
                            disp_name = disp_name or subkey_name
                            if disp_name.startswith("@mmres.dll"):
                                disp_name = "Без звука"
                            elif subkey_name == ".Default":
                                disp_name = "Windows по умолчанию"
                            found_schemes.append(
                                SoundSchemeDTO(id=subkey_name, name=disp_name, is_current=(subkey_name == cur_scheme))
                            )
                    except OSError:
                        break
                if found_schemes:
                    schemes = found_schemes
        except Exception as exc:
            logger.debug(f"[SoundManager] Чтение схем звуков: {exc}")
        return cur_scheme, schemes

    def _get_devices_from_registry(
        self, default_id: Optional[str] = None
    ) -> Tuple[List[AudioDeviceDTO], List[AudioDeviceDTO]]:
        """Извлекает список устройств вывода и ввода из системного реестра MMDevices."""
        if not winreg:
            return [], []

        def _scan_flow(flow_name: str, flow_type: str) -> List[AudioDeviceDTO]:
            dev_list: List[AudioDeviceDTO] = []
            base_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\{flow_name}"
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path, 0, winreg.KEY_READ) as key:
                    idx = 0
                    while True:
                        try:
                            guid = winreg.EnumKey(key, idx)
                            idx += 1
                        except OSError:
                            break
                        try:
                            dev_path = f"{base_path}\\{guid}\\Properties"
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_path, 0, winreg.KEY_READ) as pkey:
                                friendly_name, _ = winreg.QueryValueEx(pkey, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")
                                if friendly_name:
                                    is_def = bool(default_id and guid.lower() in default_id.lower())
                                    dev_list.append(
                                        AudioDeviceDTO(id=guid, name=friendly_name, flow=flow_type, is_default=is_def, state="active")
                                    )
                        except Exception:
                            continue
            except Exception as exc:
                logger.debug(f"[SoundManager] Опрос устройств {flow_name}: {exc}")
            return dev_list

        return _scan_flow("Render", "render"), _scan_flow("Capture", "capture")

