# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Hardware - PawnIO Client
# =============================================================================
# Description:
#   Изолированный клиент драйвера PawnIO (через PawnIOLib.dll). Только чтение:
#   разрешены исключительно ioctl из белого списка. Запись в MSR/SMU/EC и
#   выполнение произвольного Pawn-кода не поддерживаются.
#
# Usage Examples:
#   Python API:
#     from apps.windows.hardware.pawnio_client import PawnIOClient
#
#     with PawnIOClient(dll_path, modules_dir) as client:
#         client.load_module('IntelMSR')
#         value = client.execute('ioctl_read_msr', [0x611])[0]
#
# File: pawnio_client.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.hardware
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:55:00
# =============================================================================

from __future__ import annotations
"""Изолированный read-only клиент драйвера PawnIO на базе PawnIOLib.dll."""

import contextlib
import ctypes
from pathlib import Path
from typing import List, Optional
from logger import logger

class PawnIOError(RuntimeError):
    """Ошибка взаимодействия с драйвером PawnIO."""

class PawnIOClient:
    """Read-only обёртка над PawnIOLib (open / load / execute / close)."""
    ALLOWED_IOCTLS = frozenset({'ioctl_read_msr', 'ioctl_read_smn', 'ioctl_read_miscctl', 'ioctl_get_thermtrip'})
    PCI_IOCTLS = frozenset({'ioctl_read_smn', 'ioctl_read_miscctl', 'ioctl_get_thermtrip'})
    PCI_MUTEX_NAME = 'Global\\Access_PCI'
    PCI_MUTEX_TIMEOUT_MS = 5000
    MAX_OUT_QWORDS = 8

    def __init__(self, dll_path: str, modules_dir: str) -> None:
        """Инициализация клиента.

        Args:
            dll_path: Путь к PawnIOLib.dll (из официальной подписанной поставки).
            modules_dir: Каталог подписанных бинарных модулей `*.bin`.
        """
        self._dll_path = dll_path
        self._modules_dir = Path(modules_dir)
        self._lib: Optional[ctypes.WinDLL] = None
        self._handle = ctypes.c_void_p()

    def open(self) -> None:
        """Открыть дескриптор драйвера.

        Raises:
            PawnIOError: Драйвер или библиотека недоступны.
        """
        try:
            lib = ctypes.WinDLL(self._dll_path)
        except OSError as e:
            raise PawnIOError(f'Не удалось загрузить PawnIOLib: {e}') from e
        lib.pawnio_open.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.pawnio_load.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        lib.pawnio_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        lib.pawnio_close.argtypes = [ctypes.c_void_p]
        self._check(lib.pawnio_open(ctypes.byref(self._handle)), 'pawnio_open')
        self._lib = lib

    def load_module(self, module_name: str) -> None:
        """Загрузить бинарный модуль из каталога модулей.

        Args:
            module_name: Имя модуля без расширения (например, `IntelMSR`).

        Raises:
            PawnIOError: Клиент не открыт, имя некорректно или файла нет.
        """
        if self._lib is None:
            raise PawnIOError('Клиент PawnIO не открыт')
        path = (self._modules_dir / f'{Path(module_name).name}.bin')
        if not path.is_file():
            raise PawnIOError(f'Модуль не найден: {path}')
        blob = path.read_bytes()
        logger.debug(f'PawnIO: загрузка модуля {path.name}')
        self._check(self._lib.pawnio_load(self._handle, blob, len(blob)), 'pawnio_load')

    def execute(self, ioctl: str, args: List[int], out_qwords: int=1) -> List[int]:
        """Выполнить разрешённый read-only ioctl загруженного модуля.

        Args:
            ioctl: Имя ioctl (только из ALLOWED_IOCTLS).
            args: Входные 64-битные аргументы.
            out_qwords: Количество 64-битных слов результата.

        Returns:
            Список 64-битных значений результата.

        Raises:
            PawnIOError: ioctl вне белого списка или ошибка драйвера.
        """
        if self._lib is None:
            raise PawnIOError('Клиент PawnIO не открыт')
        if ioctl not in self.ALLOWED_IOCTLS:
            raise PawnIOError(f'ioctl запрещён политикой read-only: {ioctl}')
        if not 0 < out_qwords <= self.MAX_OUT_QWORDS:
            raise PawnIOError(f'Недопустимый размер вывода: {out_qwords}')
        in_buf = (ctypes.c_uint64 * len(args))(*args)
        out_buf = (ctypes.c_uint64 * out_qwords)()
        returned = ctypes.c_size_t()
        logger.debug(f'PawnIO: {ioctl} args={[hex(a) for a in args]}')
        with self._pci_lock() if ioctl in self.PCI_IOCTLS else contextlib.nullcontext():
            self._check(self._lib.pawnio_execute(self._handle, ioctl.encode('ascii'), in_buf, len(args), out_buf, out_qwords, ctypes.byref(returned)), 'pawnio_execute')
        return list(out_buf)[:returned.value]

    @contextlib.contextmanager
    def _pci_lock(self):
        """Захватить общий мьютекс шины PCI (требование модулей SMN/MISCCTL/THERMTRIP)."""
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = k32.CreateMutexW(None, 0, self.PCI_MUTEX_NAME)
        if not mutex:
            raise PawnIOError('Не удалось открыть мьютекс Access_PCI')
        try:
            if k32.WaitForSingleObject(mutex, self.PCI_MUTEX_TIMEOUT_MS) not in (0, 0x80):
                raise PawnIOError('Таймаут ожидания мьютекса Access_PCI')
            try:
                yield
            finally:
                k32.ReleaseMutex(mutex)
        finally:
            k32.CloseHandle(mutex)

    def close(self) -> None:
        """Закрыть дескриптор драйвера (идемпотентно)."""
        if self._lib is not None:
            self._lib.pawnio_close(self._handle)
            self._lib = None

    def __enter__(self) -> 'PawnIOClient':
        """Открыть клиент в контекстном менеджере."""
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Гарантированно закрыть клиент."""
        self.close()

    @staticmethod
    def _check(hresult: int, func: str) -> None:
        """Проверить HRESULT вызова PawnIOLib."""
        if hresult < 0:
            raise PawnIOError(f'{func} завершился с ошибкой HRESULT=0x{hresult & 0xFFFFFFFF:08X}')
