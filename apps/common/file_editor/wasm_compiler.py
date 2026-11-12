# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - WebAssembly Binary Builder
# =============================================================================
# Description:
#   Генератор и менеджер бинарного модуля WebAssembly (file_editor_core.wasm)
#   для низкоуровневой обработки файловых буферов в линейной памяти браузера:
#   вычисление хеша FNV-1a, подсчёт строк, детектирование бинарных байтов
#   и расчёт контрольной суммы без копирования на сервер.
#
# File: wasm_compiler.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:10
# =============================================================================

from __future__ import annotations
"""Сборщик и загрузчик нативного WebAssembly-модуля редактора файлов."""

import os
import threading
from pathlib import Path
from logger import logger

WASM_DIR: Path = Path(__file__).resolve().parent / "wasm"
WASM_BINARY_PATH: Path = WASM_DIR / "file_editor_core.wasm"
_WASM_BUILD_LOCK = threading.Lock()


def _uleb128(value: int) -> bytes:
    """Кодирует беззнаковое целое число в формат ULEB128 (спецификация WebAssembly)."""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        out.append(byte)
        if value == 0:
            break
    return bytes(out)


def _sleb128(value: int) -> bytes:
    """Кодирует знаковое целое число в формат SLEB128 (спецификация WebAssembly)."""
    out = bytearray()
    more = True
    while more:
        byte = value & 0x7F
        value >>= 7
        if (value == 0 and (byte & 0x40) == 0) or (value == -1 and (byte & 0x40) != 0):
            more = False
        else:
            byte |= 0x80
        out.append(byte)
    return bytes(out)


def _section(section_id: int, payload: bytes) -> bytes:
    """Формирует секцию бинарного модуля WebAssembly."""
    return bytes([section_id]) + _uleb128(len(payload)) + payload


def _encode_str(s: str) -> bytes:
    """Кодирует UTF-8 строку с префиксом длины ULEB128."""
    raw = s.encode("utf-8")
    return _uleb128(len(raw)) + raw


def build_file_editor_wasm_bytes() -> bytes:
    """Формирует валидный бинарный модуль WebAssembly 1.0 для ядра файлового редактора.

    Экспортируемые объекты Wasm:
    - `memory`: линейная память (16 страниц = 1 МБ, максимум 256 страниц = 16 МБ)
    - `fnv1a_hash(ptr: i32, len: i32) -> i32`: хеширование FNV-1a (32-бит)
    - `count_lines(ptr: i32, len: i32) -> i32`: подсчет переводов строк (0x0A)
    - `is_binary_buffer(ptr: i32, len: i32) -> i32`: проверка наличия 0x00 байтов

    Returns:
        Байтовый массив скомпилированного `.wasm` модуля.
    """
    # Заголовок WebAssembly: \0asm + версия 1
    header = b"\x00asm\x01\x00\x00\x00"

    # Секция 1 (Type): 1 сигнатура (i32, i32) -> (i32)
    # 0x60 = func, 2 params (0x7F, 0x7F), 1 result (0x7F)
    type_payload = bytes([
        0x01,                   # 1 тип функции
        0x60, 0x02, 0x7F, 0x7F, # (param i32 i32)
        0x01, 0x7F,             # (result i32)
    ])
    sec_type = _section(1, type_payload)

    # Секция 3 (Function): 3 функции, все используют тип 0
    func_payload = bytes([0x03, 0x00, 0x00, 0x00])
    sec_func = _section(3, func_payload)

    # Секция 5 (Memory): 1 линейная память (min=16 страниц, max=256 страниц)
    mem_payload = bytes([0x01, 0x01]) + _uleb128(16) + _uleb128(256)
    sec_mem = _section(5, mem_payload)

    # Секция 7 (Export): memory + 3 функции
    exports = bytearray([0x04])
    # 1. memory (kind=0x02, index=0)
    exports += _encode_str("memory") + bytes([0x02, 0x00])
    # 2. fnv1a_hash (kind=0x00, index=0)
    exports += _encode_str("fnv1a_hash") + bytes([0x00, 0x00])
    # 3. count_lines (kind=0x00, index=1)
    exports += _encode_str("count_lines") + bytes([0x00, 0x01])
    # 4. is_binary_buffer (kind=0x00, index=2)
    exports += _encode_str("is_binary_buffer") + bytes([0x00, 0x02])
    sec_export = _section(7, bytes(exports))

    # Секция 10 (Code): тела 3 функций
    # Функция 0: fnv1a_hash(ptr: local 0, len: local 1) -> i32
    # Locals: local 2 (hash: i32), local 3 (i: i32)
    fn0_code = bytearray([
        0x01, 0x02, 0x7F,       # 1 группа локальных переменных: 2 x i32 (local 2, local 3)
        # hash = 2166136261 (-2128831035 в i32)
        0x41, *_sleb128(-2128831035),
        0x21, 0x02,             # local.set 2 (hash)
        0x41, 0x00,             # i32.const 0
        0x21, 0x03,             # local.set 3 (i = 0)
        0x02, 0x40,             # block
        0x03, 0x40,             #   loop
        0x20, 0x03,             #     local.get 3 (i)
        0x20, 0x01,             #     local.get 1 (len)
        0x4F,                   #     i32.ge_u
        0x0D, 0x01,             #     br_if 1 (выход из block)
        # hash = (hash ^ mem[ptr + i]) * 16777619
        0x20, 0x02,             #     local.get 2 (hash)
        0x20, 0x00,             #     local.get 0 (ptr)
        0x20, 0x03,             #     local.get 3 (i)
        0x6A,                   #     i32.add
        0x2D, 0x00, 0x00,       #     i32.load8_u offset=0 align=0
        0x73,                   #     i32.xor
        0x41, *_sleb128(16777619),
        0x6C,                   #     i32.mul
        0x21, 0x02,             #     local.set 2 (hash)
        # i = i + 1
        0x20, 0x03,             #     local.get 3
        0x41, 0x01,             #     i32.const 1
        0x6A,                   #     i32.add
        0x21, 0x03,             #     local.set 3
        0x0C, 0x00,             #     br 0 (к началу loop)
        0x0B,                   #   end loop
        0x0B,                   # end block
        0x20, 0x02,             # local.get 2 (return hash)
        0x0B,                   # end func
    ])

    # Функция 1: count_lines(ptr: local 0, len: local 1) -> i32
    # Locals: local 2 (lines: i32), local 3 (i: i32)
    fn1_code = bytearray([
        0x01, 0x02, 0x7F,       # 2 x i32 (local 2 = lines, local 3 = i)
        0x41, 0x01,             # i32.const 1 (минимум 1 строка)
        0x21, 0x02,             # local.set 2
        0x41, 0x00,             # i32.const 0
        0x21, 0x03,             # local.set 3
        0x02, 0x40,             # block
        0x03, 0x40,             #   loop
        0x20, 0x03,             #     local.get 3 (i)
        0x20, 0x01,             #     local.get 1 (len)
        0x4F,                   #     i32.ge_u
        0x0D, 0x01,             #     br_if 1
        # if mem[ptr + i] == 10 ('\n') -> lines += 1
        0x20, 0x00,             #     local.get 0 (ptr)
        0x20, 0x03,             #     local.get 3 (i)
        0x6A,                   #     i32.add
        0x2D, 0x00, 0x00,       #     i32.load8_u
        0x41, 0x0A,             #     i32.const 10
        0x46,                   #     i32.eq
        0x04, 0x40,             #     if
        0x20, 0x02,             #       local.get 2
        0x41, 0x01,             #       i32.const 1
        0x6A,                   #       i32.add
        0x21, 0x02,             #       local.set 2
        0x0B,                   #     end if
        # i += 1
        0x20, 0x03,             #     local.get 3
        0x41, 0x01,             #     i32.const 1
        0x6A,                   #     i32.add
        0x21, 0x03,             #     local.set 3
        0x0C, 0x00,             #     br 0
        0x0B,                   #   end loop
        0x0B,                   # end block
        0x20, 0x02,             # local.get 2
        0x0B,                   # end func
    ])

    # Функция 2: is_binary_buffer(ptr: local 0, len: local 1) -> i32
    # Проверяет наличие нулевого байта (0x00) в буфере
    fn2_code = bytearray([
        0x01, 0x01, 0x7F,       # 1 x i32 (local 2 = i)
        0x41, 0x00,             # i32.const 0
        0x21, 0x02,             # local.set 2
        0x02, 0x40,             # block
        0x03, 0x40,             #   loop
        0x20, 0x02,             #     local.get 2 (i)
        0x20, 0x01,             #     local.get 1 (len)
        0x4F,                   #     i32.ge_u
        0x0D, 0x01,             #     br_if 1
        # if mem[ptr + i] == 0 -> return 1
        0x20, 0x00,             #     local.get 0 (ptr)
        0x20, 0x02,             #     local.get 2 (i)
        0x6A,                   #     i32.add
        0x2D, 0x00, 0x00,       #     i32.load8_u
        0x45,                   #     i32.eqz
        0x04, 0x40,             #     if
        0x41, 0x01,             #       i32.const 1
        0x0F,                   #       return
        0x0B,                   #     end if
        # i += 1
        0x20, 0x02,             #     local.get 2
        0x41, 0x01,             #     i32.const 1
        0x6A,                   #     i32.add
        0x21, 0x02,             #     local.set 2
        0x0C, 0x00,             #     br 0
        0x0B,                   #   end loop
        0x0B,                   # end block
        0x41, 0x00,             # i32.const 0
        0x0B,                   # end func
    ])

    bodies = (
        bytes([0x03])
        + _uleb128(len(fn0_code)) + bytes(fn0_code)
        + _uleb128(len(fn1_code)) + bytes(fn1_code)
        + _uleb128(len(fn2_code)) + bytes(fn2_code)
    )
    sec_code = _section(10, bodies)

    return header + sec_type + sec_func + sec_mem + sec_export + sec_code


def ensure_wasm_binary() -> Path:
    """Гарантирует наличие скомпилированного файла `file_editor_core.wasm` на диске.

    Использует потокобезопасную блокировку и атомарную запись через временный файл.

    Returns:
        Абсолютный путь к бинарному файлу `.wasm`.
    """
    with _WASM_BUILD_LOCK:
        WASM_DIR.mkdir(parents=True, exist_ok=True)
        wasm_bytes = build_file_editor_wasm_bytes()
        if not WASM_BINARY_PATH.exists() or WASM_BINARY_PATH.read_bytes() != wasm_bytes:
            tmp_path = WASM_BINARY_PATH.with_suffix(".wasm.tmp")
            tmp_path.write_bytes(wasm_bytes)
            os.replace(tmp_path, WASM_BINARY_PATH)
            logger.info(
                f"[FileEditorWasm] Сгенерирован бинарный модуль Wasm ({len(wasm_bytes)} байт): {WASM_BINARY_PATH}"
            )
    return WASM_BINARY_PATH
