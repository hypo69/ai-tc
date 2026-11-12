/**
 * Вспомогательные утилиты для вкладки управления моделями ИИ.
 * Файл: apps/ai_assistant/api/webgui/tab_models/common/ui_utils.js
 * Updated: 2026-11-01 17:37:00
 */

/**
 * Безопасно экранирует спецсимволы HTML.
 * @param {*} text - Входной текст.
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
 * @param {string} message - Текст уведомления.
 * @param {string} [type='info'] - Тип алерта Bootstrap.
 */
export function showModelsNotification(message, type = 'info') {
  if (window.showToast) {
    window.showToast(message, type);
    return;
  }
  const notification = document.createElement('div');
  notification.className = `alert alert-${type} position-fixed top-0 end-0 m-3 shadow`;
  notification.style.zIndex = '9999';
  notification.style.maxWidth = '400px';
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 5000);
}

/**
 * Унифицированный fetch с обработкой ошибок API.
 * @param {string} url - Адрес запроса.
 * @param {Object} [options={}] - Опции fetch.
 * @returns {Promise<any>} Результат в JSON.
 */
export async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let msg = response.statusText;
    try {
      const data = await response.json();
      if (data && data.detail) {
        if (typeof data.detail === 'string') msg = data.detail;
        else if (Array.isArray(data.detail)) msg = data.detail.map(d => d.msg || JSON.stringify(d)).join(', ');
        else msg = JSON.stringify(data.detail);
      } else if (data && data.message) {
        msg = data.message;
      }
    } catch (_) {}
    throw new Error(`${response.status} ${msg}`);
  }
  return response.json();
}
