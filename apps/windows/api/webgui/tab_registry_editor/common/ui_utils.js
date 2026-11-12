/**
 * Вспомогательные утилиты интерфейса редактора реестра Windows.
 * Файл: apps/windows/api/webgui/tab_registry_editor/common/ui_utils.js
 * Updated: 2026-11-01 14:38:00
 */

/**
 * Экранирует HTML-спецсимволы.
 * @param {string} text - Исходная строка.
 * @returns {string} Экранированная строка.
 */
export function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
