/**
 * Вспомогательные утилиты интерфейса просмотрщика реестра Windows.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/common/ui_utils.js
 * Updated: 2026-10-17 01:55:00
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
