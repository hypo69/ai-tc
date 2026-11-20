/**
 * =============================================================================
 * Process Name: Windows Settings - Common UI Utilities & State
 * =============================================================================
 * Description:
 *   Общие утилиты пользовательского интерфейса вкладки настроек Windows:
 *   базовый URL API, сетевой клиент fetchJson, реактивное состояние каталога
 *   и генерация бейджей уровней риска SafeOps.
 *
 * File: ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

export const API_BASE = '/api/v1/window-management';

/**
 * Реактивное состояние модуля пользовательских настроек Windows.
 */
export const state = {
  allSettings: [],
  currentCategory: 'focus_activation',
  pendingSetting: null,
  liveValuesCache: {},
};

/**
 * Выполнение HTTP JSON запроса к API.
 * @param {string} url - URL эндпоинта
 * @param {RequestInit} [options={}] - Опции fetch
 * @returns {Promise<any>}
 */
export async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  return await resp.json();
}

/**
 * Генерация HTML-разметки бейджа для уровня риска SafeOps.
 * @param {string} risk - Уровень риска ('safe', 'low', 'medium', 'high', 'critical')
 * @returns {string} HTML бейджа
 */
export function getRiskBadgeHtml(risk) {
  const r = (risk || 'safe').toLowerCase();
  switch (r) {
    case 'safe':
      return '<span class="badge bg-success-subtle text-success border">Safe</span>';
    case 'low':
      return '<span class="badge bg-info-subtle text-info border">Low</span>';
    case 'medium':
      return '<span class="badge bg-warning-subtle text-warning border">Medium</span>';
    case 'high':
      return '<span class="badge bg-danger-subtle text-danger border">High</span>';
    case 'critical':
      return '<span class="badge bg-danger text-white">Critical</span>';
    default:
      return `<span class="badge bg-secondary">${r}</span>`;
  }
}
