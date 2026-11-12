//! =============================================================================
//! Process Name: AI-Windows-Admin Common File Editor - Rust Wasm Core Entry
//! =============================================================================
//! Description:
//!   Корневой модуль Rust + WebAssembly для универсального редактора файлов.
//!   Экспортирует высокоскоростные функции индексации строк, расчёта FNV-1a хеша,
//!   детектирования бинарных потоков, генерации Hex-дампа с Data Inspector
//!   и лексического анализа файлов всех типов VS Code.
//!
//! File: lib.rs
//! Project: ai-windows-admin
//! Package: apps.common.file_editor.rust_engine
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-10-28 17:01:00
//! =============================================================================

pub mod hex_inspector;
pub mod syntax_analyzer;

use wasm_bindgen::prelude::*;

/// Вычисляет 32-битный хеш FNV-1a для переданного среза байтов.
#[no_mangle]
#[wasm_bindgen]
pub fn fnv1a_hash(data: &[u8]) -> u32 {
    let mut hash: u32 = 2166136261;
    for &byte in data {
        hash ^= byte as u32;
        hash = hash.wrapping_mul(16777619);
    }
    hash
}

/// Подсчитывает количество строк в буфере по символу перевода строки `0x0A`.
#[no_mangle]
#[wasm_bindgen]
pub fn count_lines(data: &[u8]) -> u32 {
    let mut lines: u32 = 1;
    for &byte in data {
        if byte == b'\n' {
            lines += 1;
        }
    }
    lines
}

/// Проверяет, содержит ли буфер нулевые байты (`0x00`), характерные для бинарных файлов.
#[no_mangle]
#[wasm_bindgen]
pub fn is_binary_buffer(data: &[u8]) -> u32 {
    let limit = data.len().min(8192);
    for &byte in &data[..limit] {
        if byte == 0 {
            return 1;
        }
    }
    0
}
