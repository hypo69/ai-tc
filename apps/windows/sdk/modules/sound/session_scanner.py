# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Audio Module - Realtime Session Scanner
# =============================================================================
# Description:
#   Служба оперативного сканирования звуковых сессий Windows (Core Audio WASAPI).
#   Определяет приложения и процессы, использующие звук в реальном времени:
#   колонки, наушники (вывод / render) и микрофоны (ввод / capture), а также
#   состояние активности, громкость, статус Mute и пиковый уровень сигнала.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.sound.session_scanner import AudioSessionScanner
#     sessions = AudioSessionScanner.scan_sessions()
#     summary = AudioSessionScanner.get_active_audio_summary()
#
# File: session_scanner.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.sound
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:35:00
# =============================================================================

from __future__ import annotations
"""Модуль сканирования аудиосессий Windows в реальном времени."""

import time
from typing import Any, Dict, List, Optional, Set
import psutil

from logger import logger
from .models import SoundSessionDTO

try:
    import winreg
except ImportError:
    winreg = None

_PID_CACHE: Dict[int, tuple[float, str]] = {}
_PID_CACHE_TTL = 5.0


def _get_process_name(pid: int) -> str:
    """Возвращает имя процесса по его PID с кэшированием."""
    if pid <= 0:
        return "Системные звуки Windows"
    now = time.time()
    if pid in _PID_CACHE:
        cached_time, name = _PID_CACHE[pid]
        if now - cached_time < _PID_CACHE_TTL:
            return name
    try:
        p = psutil.Process(pid)
        name = p.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        name = f"Процесс PID {pid}"
    except Exception:
        name = f"PID {pid}"
    _PID_CACHE[pid] = (now, name)
    return name


class AudioSessionScanner:
    """Сканер аудиосессий и активности звуковых устройств Windows."""

    @classmethod
    def scan_sessions(cls, include_consent_store: bool = True) -> List[SoundSessionDTO]:
        """Выполняет полный опрос аудиосессий WASAPI для устройств вывода и ввода.

        Returns:
            List[SoundSessionDTO]: Список обнаруженных звуковых сессий с атрибутами активности.
        """
        sessions: List[SoundSessionDTO] = []
        captured_mic_pids: Set[int] = set()

        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            comtypes = None

        try:
            from pycaw.pycaw import AudioUtilities, IAudioSessionControl2, IAudioMeterInformation
            from pycaw.constants import AudioDeviceState

            devices = AudioUtilities.GetAllDevices()
            for d in devices:
                if d.state != AudioDeviceState.Active:
                    continue

                dev_id = getattr(d, "id", "") or ""
                is_capture = "{0.0.1." in dev_id
                flow = "capture" if is_capture else "render"
                friendly_name = getattr(d, "FriendlyName", None) or ("Микрофон" if is_capture else "Динамики / Наушники")

                mgr = getattr(d, "AudioSessionManager", None)
                if not mgr:
                    continue

                try:
                    s_enum = mgr.GetSessionEnumerator()
                    if not s_enum:
                        continue
                    count = s_enum.GetCount()
                except Exception as enum_err:
                    logger.debug(f"[AudioSessionScanner] Ошибка перечислителя сессий устройства {friendly_name}: {enum_err}")
                    continue

                for i in range(count):
                    try:
                        s = s_enum.GetSession(i)
                        s2 = s.QueryInterface(IAudioSessionControl2)
                        pid = int(s2.GetProcessId() or 0)
                        state_raw = int(s2.GetState() or 0)
                        is_sys_session = (pid == 0 and s2.IsSystemSoundsSession() == 0)

                        # Чтение громкости и Mute
                        vol_pct = 100
                        is_muted = False
                        try:
                            sav = s.SimpleAudioVolume
                            vol_pct = int(round(sav.GetMasterVolume() * 100))
                            is_muted = bool(sav.GetMute())
                        except Exception:
                            pass

                        # Чтение пикового уровня аудиосигнала
                        peak_level = 0.0
                        try:
                            meter = s.QueryInterface(IAudioMeterInformation)
                            peak_level = round(float(meter.GetPeakValue()), 4)
                        except Exception:
                            pass

                        # Имя процесса
                        if is_sys_session or pid == 0:
                            proc_name = "Системные звуки Windows"
                            is_sys = True
                        else:
                            proc_name = _get_process_name(pid)
                            is_sys = False
                            if is_capture:
                                captured_mic_pids.add(pid)

                        # Статус сессии
                        state_str = "active" if state_raw == 1 else ("inactive" if state_raw == 0 else "expired")
                        is_active_now = (state_raw == 1) or (peak_level > 0.001)

                        sess_dto = SoundSessionDTO(
                            id=f"{flow}_{pid}_{friendly_name}_{i}",
                            name=proc_name,
                            pid=pid,
                            volume=vol_pct,
                            is_muted=is_muted,
                            is_system_sounds=is_sys,
                            device_name=friendly_name,
                            device_flow=flow,
                            state=state_str,
                            is_active_now=is_active_now,
                            peak_level=peak_level,
                        )
                        sessions.append(sess_dto)
                    except Exception as s_err:
                        logger.debug(f"[AudioSessionScanner] Пропуск аудиосессии {i}: {s_err}")
                        continue
        except Exception as wasapi_err:
            logger.debug(f"[AudioSessionScanner] WASAPI сканирование завершилось с предупреждением: {wasapi_err}")
        finally:
            if comtypes:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

        # Дополнительная проверка ConsentStore для микрофона (UWP / Win32)
        if include_consent_store and winreg:
            cls._enrich_from_consent_store(sessions, captured_mic_pids)

        return sessions

    @classmethod
    def _enrich_from_consent_store(cls, sessions: List[SoundSessionDTO], existing_pids: Set[int]) -> None:
        """Дополняет список сессий приложениями, использующими микрофон через CapabilityAccessManager."""
        try:
            base_path = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path, 0, winreg.KEY_READ) as key:
                sub_count, _, _ = winreg.QueryInfoKey(key)
                for i in range(sub_count):
                    sub = winreg.EnumKey(key, i)
                    if sub == "NonPackaged":
                        np_path = f"{base_path}\\NonPackaged"
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, np_path, 0, winreg.KEY_READ) as np_key:
                            np_count, _, _ = winreg.QueryInfoKey(np_key)
                            for j in range(np_count):
                                app_sub = winreg.EnumKey(np_key, j)
                                try:
                                    with winreg.OpenKey(np_key, app_sub, 0, winreg.KEY_READ) as ak:
                                        stop, _ = winreg.QueryValueEx(ak, "LastUsedTimeStop")
                                        start, _ = winreg.QueryValueEx(ak, "LastUsedTimeStart")
                                        if stop == 0 and start > 0:
                                            app_name = app_sub.replace("#", "\\").split("\\")[-1]
                                            # Проверяем, нет ли уже этой программы в сессиях захвата
                                            already_present = any(
                                                s.device_flow == "capture" and s.name.lower() == app_name.lower()
                                                for s in sessions
                                            )
                                            if not already_present:
                                                sessions.append(
                                                    SoundSessionDTO(
                                                        id=f"consent_mic_{app_name}",
                                                        name=app_name,
                                                        pid=0,
                                                        volume=100,
                                                        is_muted=False,
                                                        is_system_sounds=False,
                                                        device_name="Микрофон (ConsentStore)",
                                                        device_flow="capture",
                                                        state="active",
                                                        is_active_now=True,
                                                        peak_level=1.0,
                                                    )
                                                )
                                except Exception:
                                    continue
                    else:
                        try:
                            with winreg.OpenKey(key, sub, 0, winreg.KEY_READ) as sk:
                                stop, _ = winreg.QueryValueEx(sk, "LastUsedTimeStop")
                                start, _ = winreg.QueryValueEx(sk, "LastUsedTimeStart")
                                if stop == 0 and start > 0:
                                    already_present = any(
                                        s.device_flow == "capture" and s.name.lower() == sub.lower()
                                        for s in sessions
                                    )
                                    if not already_present:
                                        sessions.append(
                                            SoundSessionDTO(
                                                id=f"consent_mic_{sub}",
                                                name=sub,
                                                pid=0,
                                                volume=100,
                                                is_muted=False,
                                                is_system_sounds=False,
                                                device_name="Микрофон Windows App",
                                                device_flow="capture",
                                                state="active",
                                                is_active_now=True,
                                                peak_level=1.0,
                                            )
                                        )
                        except Exception:
                            continue
        except Exception as reg_err:
            logger.debug(f"[AudioSessionScanner] ConsentStore проверка: {reg_err}")

    @classmethod
    def get_active_audio_summary(cls) -> Dict[str, Any]:
        """Возвращает сводку текущей активности звука в реальном времени.

        Returns:
            Dict[str, Any]: Сводка активных приложений для колонок/наушников и микрофона.
        """
        all_sessions = cls.scan_sessions()
        playback_active: List[SoundSessionDTO] = []
        capture_active: List[SoundSessionDTO] = []

        for s in all_sessions:
            if s.is_active_now:
                if s.device_flow == "capture":
                    capture_active.append(s)
                else:
                    playback_active.append(s)

        return {
            "all_sessions": [s.model_dump() for s in all_sessions],
            "playback_active": [s.model_dump() for s in playback_active],
            "capture_active": [s.model_dump() for s in capture_active],
            "playback_active_apps": list({s.name for s in playback_active}),
            "capture_active_apps": list({s.name for s in capture_active}),
            "total_active_streams": len(playback_active) + len(capture_active),
            "timestamp": time.time(),
        }
