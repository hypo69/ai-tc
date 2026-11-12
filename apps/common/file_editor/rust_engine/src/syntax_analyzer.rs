//! =============================================================================
//! Process Name: AI-Windows-Admin Common File Editor - Rust Syntax & Outline
//! =============================================================================
//! Description:
//!   Модуль быстрого извлечения дерева символов (Outline: функции, классы,
//!   структуры, заголовки Markdown, ключи JSON/YAML) и метрик текста в Wasm.
//!
//! File: syntax_analyzer.rs
//! Project: ai-windows-admin
//! Package: apps.common.file_editor.rust_engine
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-10-28 17:01:00
//! =============================================================================

use serde::{Deserialize, Serialize};
use wasm_bindgen::prelude::*;

/// Элемент структуры документа (Outline Symbol как в боковой панели VS Code).
#[derive(Serialize, Deserialize)]
pub struct OutlineSymbol {
    pub name: String,
    pub kind: String,
    pub line: usize,
}

/// Извлекает оглавление и структурные символы из исходного кода или документа.
#[wasm_bindgen]
pub fn extract_outline_symbols(content: &str, ext: &str) -> Result<JsValue, JsValue> {
    let mut symbols: Vec<OutlineSymbol> = Vec::new();
    let lower_ext = ext.to_lowercase();

    for (idx, raw_line) in content.lines().enumerate() {
        let line_num = idx + 1;
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if lower_ext == "md" || lower_ext == "markdown" {
            if trimmed.starts_with('#') {
                symbols.push(OutlineSymbol {
                    name: trimmed.trim_start_matches('#').trim().to_string(),
                    kind: "heading".to_string(),
                    line: line_num,
                });
            }
        } else if lower_ext == "py" {
            if let Some(rest) = trimmed.strip_prefix("class ") {
                let name = rest.split(['(', ':']).next().unwrap_or("").trim();
                symbols.push(OutlineSymbol {
                    name: name.to_string(),
                    kind: "class".to_string(),
                    line: line_num,
                });
            } else if let Some(rest) = trimmed.strip_prefix("def ").or_else(|| trimmed.strip_prefix("async def ")) {
                let name = rest.split('(').next().unwrap_or("").trim();
                symbols.push(OutlineSymbol {
                    name: name.to_string(),
                    kind: "function".to_string(),
                    line: line_num,
                });
            }
        } else if lower_ext == "rs" {
            if trimmed.starts_with("pub fn ") || trimmed.starts_with("fn ") {
                let name = trimmed
                    .trim_start_matches("pub ")
                    .trim_start_matches("fn ")
                    .split('(')
                    .next()
                    .unwrap_or("")
                    .trim();
                symbols.push(OutlineSymbol {
                    name: name.to_string(),
                    kind: "function".to_string(),
                    line: line_num,
                });
            } else if trimmed.starts_with("pub struct ") || trimmed.starts_with("struct ") {
                let name = trimmed
                    .trim_start_matches("pub ")
                    .trim_start_matches("struct ")
                    .split(['{', '(', ';'])
                    .next()
                    .unwrap_or("")
                    .trim();
                symbols.push(OutlineSymbol {
                    name: name.to_string(),
                    kind: "struct".to_string(),
                    line: line_num,
                });
            }
        }
    }

    serde_wasm_bindgen::to_value(&symbols).map_err(|e| JsValue::from_str(&e.to_string()))
}
