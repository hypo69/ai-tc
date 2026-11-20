/**
 * =============================================================================
 * Название: Вспомогательные утилиты интерфейса Windows Sysadmin & Identity
 * =============================================================================
 * Описание:
 *   Экранирование HTML и безопасный сетевой клиент для вызовов API.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/common/ui_utils.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-12 03:48:00
 * =============================================================================
 */

/**
 * Экранирует специальные символы HTML для защиты от XSS-инъекций.
 * @param {string} str - Исходный текст.
 * @returns {string} Экранированный текст.
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
 * Безопасный вызов fetch с автоматическим разбором JSON и информативной обработкой ошибок.
 * Корректно взаимодействует с платформенным мостом window.api.fetch, который
 * возвращает уже распарсенный JSON и генерирует исключения при статусе !ok,
 * а также со стандартным браузерным Fetch API.
 *
 * @param {string} url - URL запроса.
 * @param {Object} [options={}] - Параметры запроса fetch.
 * @returns {Promise<any>} Разобранные данные ответа.
 */
export async function safeApiFetch(url, options = {}) {
  const opts = { ...options };
  if (opts.body && typeof opts.body === 'string' && (!opts.headers || !opts.headers['Content-Type'])) {
    opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  }

  // Если доступен платформенный мост window.api.fetch (возвращающий разобранный JSON)
  if (window.api && typeof window.api.fetch === 'function') {
    const data = await window.api.fetch(url, opts);
    if (data && typeof data.json === 'function') {
      return await data.json();
    }
    return data;
  }

  // Fallback на стандартный Fetch API браузера
  const res = await fetch(url, opts);
  if (!res.ok) {
    let msg = res.statusText || 'Error';
    try {
      const errData = await res.json();
      if (errData && errData.detail) {
        msg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      } else if (errData && errData.message) {
        msg = errData.message;
      }
    } catch (_) {}
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  return await res.json();
}
