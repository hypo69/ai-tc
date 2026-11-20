/**
 * =============================================================================
 * Process Name: Windows MCP Servers - Common UI Utilities & State
 * =============================================================================
 * Description:
 *   Общие утилиты пользовательского интерфейса вкладки MCP серверов:
 *   экранирование HTML, сетевой клиент apiFetch с отказоустойчивым fallback,
 *   реактивное состояние списка серверов и параметров фильтрации.
 *
 * File: ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_mcp/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

/**
 * Глобальное реактивное состояние вкладки MCP серверов.
 */
export const state = {
  servers: [],
  filteredServers: [],
  viewMode: 'cards', // 'cards' | 'table'
  searchQuery: '',
  activeFilter: 'all', // 'all' | 'enabled' | 'disabled' | 'stdio' | 'sse'
  isInitialized: false
};

/**
 * Безопасное экранирование специальных символов HTML.
 * @param {any} str - Входная строка
 * @returns {string} Экранированная строка
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
 * Выполнение HTTP-запроса к MCP API с автоматическим fallback на альтернативный путь.
 * @param {string} endpoint - Путь к эндпоинту
 * @param {RequestInit} [options={}] - Опции запроса fetch
 * @returns {Promise<Response>} Ответ сервера fetch
 */
export async function apiFetch(endpoint, options = {}) {
  let url = endpoint;
  let res = await fetch(url, options);
  if (!res.ok && url.startsWith('/api/v1/admin/mcp')) {
    const fallbackUrl = url.replace('/api/v1/admin/mcp', '/api/v1/mcp');
    const fallbackRes = await fetch(fallbackUrl, options);
    if (fallbackRes.ok) {
      return fallbackRes;
    }
  }
  return res;
}
