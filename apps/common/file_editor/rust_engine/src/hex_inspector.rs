//! =============================================================================
//! Process Name: AI-Windows-Admin Common File Editor - Rust Hex & Data Inspector
//! =============================================================================
//! Description:
//!   Модуль побайтового представления и инспекции типов данных (Data Inspector)
//!   для режима VS Code Hex Editor: декодирование Int8, UInt8, Int16, UInt16,
//!   Int32, UInt32, Float32, Float64 в порядках байтов Little/Big Endian.
//!
//! File: hex_inspector.rs
//! Project: ai-windows-admin
//! Package: apps.common.file_editor.rust_engine
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-10-28 17:01:00
//! =============================================================================

use serde::{Deserialize, Serialize};
use wasm_bindgen::prelude::*;

/// Снимок значений Data Inspector для выбранного смещения в бинарном буфере.
#[derive(Serialize, Deserialize)]
pub struct DataInspectorSnapshot {
    pub offset: usize,
    pub binary_bits: String,
    pub uint8: u8,
    pub int8: i8,
    pub uint16_le: Option<u16>,
    pub int16_le: Option<i16>,
    pub uint32_le: Option<u32>,
    pub int32_le: Option<i32>,
    pub float32_le: Option<f32>,
    pub float64_le: Option<f64>,
    pub ascii_char: String,
}

/// Инспектирует байты начиная с указанного смещения и возвращает все числовые представления.
#[wasm_bindgen]
pub fn inspect_bytes_at(buffer: &[u8], offset: usize) -> Result<JsValue, JsValue> {
    if offset >= buffer.len() {
        return Err(JsValue::from_str("Смещение выходит за границы буфера"));
    }

    let b0 = buffer[offset];
    let rem = &buffer[offset..];

    let uint16_le = if rem.len() >= 2 {
        Some(u16::from_le_bytes([rem[0], rem[1]]))
    } else {
        None
    };
    let int16_le = if rem.len() >= 2 {
        Some(i16::from_le_bytes([rem[0], rem[1]]))
    } else {
        None
    };
    let uint32_le = if rem.len() >= 4 {
        Some(u32::from_le_bytes([rem[0], rem[1], rem[2], rem[3]]))
    } else {
        None
    };
    let int32_le = if rem.len() >= 4 {
        Some(i32::from_le_bytes([rem[0], rem[1], rem[2], rem[3]]))
    } else {
        None
    };
    let float32_le = if rem.len() >= 4 {
        Some(f32::from_le_bytes([rem[0], rem[1], rem[2], rem[3]]))
    } else {
        None
    };
    let float64_le = if rem.len() >= 8 {
        Some(f64::from_le_bytes([
            rem[0], rem[1], rem[2], rem[3], rem[4], rem[5], rem[6], rem[7],
        ]))
    } else {
        None
    };

    let ascii_char = if (32..=126).contains(&b0) {
        (b0 as char).to_string()
    } else {
        ".".to_string()
    };

    let snap = DataInspectorSnapshot {
        offset,
        binary_bits: format!("{:08b}", b0),
        uint8: b0,
        int8: b0 as i8,
        uint16_le,
        int16_le,
        uint32_le,
        int32_le,
        float32_le,
        float64_le,
        ascii_char,
    };

    serde_wasm_bindgen::to_value(&snap).map_err(|e| JsValue::from_str(&e.to_string()))
}
