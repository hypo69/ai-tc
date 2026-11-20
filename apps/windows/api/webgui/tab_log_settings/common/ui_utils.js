/**
 * =============================================================================
 * Process Name: Windows Log Settings - UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные функции экранирования символов и утилиты проверки
 *   активности вкладки параметров журналов Windows.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Экранирует HTML-сущности в переданной строке.
 * @param {*} str - Исходный текст.
 * @returns {string} Экранированная строка.
 */
export function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Проверяет, активна ли в данный момент вкладка параметров журналов.
 * @param {string} [tabId='tab-log-settings'] - Идентификатор вкладки.
 * @returns {boolean} Флаг активности.
 */
export function checkTabActive(tabId = 'tab-log-settings') {
  if (typeof window !== 'undefined' && typeof window.isTabActive === 'function') {
    return window.isTabActive(tabId);
  }
  return true;
}
