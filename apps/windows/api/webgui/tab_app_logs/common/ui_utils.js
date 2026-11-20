/**
 * =============================================================================
 * Process Name: Windows App Logs - UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные утилиты экранирования HTML, системных уведомлений и
 *   централизованного управления состоянием вкладки внутренних логов.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Глобальный объект реактивного состояния вкладки.
 */
export const state = {
  currentFile: 'log.json',
  currentMode: 'table',
  liveActive: false,
  liveTimer: null,
  records: [],
  files: [],
  overview: null,
  stats: null,
  selectedEntry: null,
  activePreset: 'all',
};

/**
 * Экранирует спецсимволы в безопасные HTML-сущности.
 * @param {*} text - Исходная строка или значение.
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

/**
 * Отображает всплывающее уведомление пользователю.
 * @param {string} title - Заголовок уведомления.
 * @param {string} msg - Текст сообщения.
 * @param {string} [type='info'] - Тип уведомления ('info', 'success', 'warning', 'error').
 */
export function showAppLogsToast(title, msg, type = 'info') {
  if (window.toast) {
    if (type === 'success') window.toast.success(title, msg);
    else if (type === 'warning') window.toast.warning(title, msg);
    else if (type === 'error' || type === 'danger') window.toast.error(title, msg);
    else window.toast.info(title, msg);
  } else {
    console.log(`[AppLogs ${type}] ${title}: ${msg}`);
  }
}
