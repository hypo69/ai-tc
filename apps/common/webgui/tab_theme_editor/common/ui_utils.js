/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные утилиты манипуляции элементами DOM, чтения/записи значений
 *   полей формы и уведомлений toast для Редактора тем оформления.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_theme_editor/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Список пар элементов (колорпикер и текстовое hex-поле).
 */
export const COLOR_PAIRS = [
  { picker: 'picker-bg-base', text: 'color-bg-base' },
  { picker: 'picker-bg-surface', text: 'color-bg-surface' },
  { picker: 'picker-bg-elevated', text: 'color-bg-elevated' },
  { picker: 'picker-bg-nav', text: 'color-bg-nav' },
  { picker: 'picker-text-primary', text: 'color-text-primary' },
  { picker: 'picker-text-muted', text: 'color-text-muted' },
  { picker: 'picker-accent', text: 'color-accent' },
  { picker: 'picker-accent-hover', text: 'color-accent-hover' },
  { picker: 'picker-border', text: 'color-border' },
  { picker: 'picker-border-strong', text: 'color-border-strong' },
  { picker: 'picker-status-success', text: 'color-status-success' },
  { picker: 'picker-status-warning', text: 'color-status-warning' },
  { picker: 'picker-status-danger', text: 'color-status-danger' },
  { picker: 'picker-status-info', text: 'color-status-info' },
  { picker: 'picker-panel-header-text', text: 'color-panel-header-text' },
  { picker: 'picker-panel-header-bg', text: 'color-panel-header-bg' },
  { picker: 'picker-tab-header-text', text: 'color-tab-header-text' },
  { picker: 'picker-tab-header-sub', text: 'color-tab-header-sub' },
];

/**
 * Устанавливает значение инпута по ID.
 * @param {string} id - ID элемента.
 * @param {string|number} val - Значение.
 */
export function setInputValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

/**
 * Устанавливает текстовое содержимое элемента по ID.
 * @param {string} id - ID элемента.
 * @param {string} text - Текст.
 */
export function setTextContent(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/**
 * Устанавливает выбранное значение в select по ID.
 * @param {string} id - ID элемента.
 * @param {string} val - Значение.
 */
export function setSelectValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

/**
 * Устанавливает состояние чекбокса по ID.
 * @param {string} id - ID элемента.
 * @param {boolean} checked - Флаг активности.
 */
export function setCheckboxValue(id, checked) {
  const el = document.getElementById(id);
  if (el) el.checked = !!checked;
}

/**
 * Устанавливает одинаковый hex-код в колорпикер и соответствующее текстовое поле.
 * @param {string} suffix - Суффикс ID элемента.
 * @param {string} hex - Код цвета в формате hex.
 */
export function setColorPair(suffix, hex) {
  const picker = document.getElementById(`picker-${suffix}`);
  const text = document.getElementById(`color-${suffix}`);
  if (picker) picker.value = hex;
  if (text) text.value = hex;
}

/**
 * Возвращает значение цвета из текстового инпута или колорпикера.
 * @param {string} suffix - Суффикс ID элемента.
 * @param {string} [fallback='#000000'] - Значение по умолчанию.
 * @returns {string} Hex-строка цвета.
 */
export function getColorValue(suffix, fallback = '#000000') {
  const text = document.getElementById(`color-${suffix}`);
  const picker = document.getElementById(`picker-${suffix}`);
  return text?.value || picker?.value || fallback;
}

/**
 * Отображает всплывающее системное уведомление.
 * @param {string} title - Заголовок.
 * @param {string} msg - Текст сообщения.
 * @param {string} [type='info'] - Тип уведомления ('info', 'success', 'danger').
 */
export function showToast(title, msg, type = 'info') {
  if (window.toast) {
    if (type === 'success') window.toast.success(title, msg);
    else if (type === 'danger' || type === 'error') window.toast.error(title, msg);
    else window.toast.info(title, msg);
  } else {
    console.log(`[Toast ${type}] ${title}: ${msg}`);
  }
}
