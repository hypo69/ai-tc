/**
 * @file apps/windows/api/webgui/tab_skills/common/ui_utils.js
 * @description Вспомогательные утилиты для интерфейса управления навыками (экранирование, байты, API fetch)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-20 16:45:00
 */

/**
 * Безопасное экранирование специальных символов HTML
 * @param {string} str Исходная строка
 * @returns {string} Экранированная строка
 */
export function escapeHtml(str) {
  return String(str || '').replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}

/**
 * Форматирование байт в человекочитаемый вид
 * @param {number} bytes Количество байт
 * @returns {string} Строка с размерностью
 */
export function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Выполнение безопасных HTTP-запросов к API навыков с fallback на admin маршрут
 * @param {string} endpoint URL конечной точки
 * @param {Object} options Параметры fetch
 * @returns {Promise<Response>}
 */
export async function apiFetch(endpoint, options = {}) {
  let url = endpoint;
  let res = await fetch(url, options);
  if (!res.ok && url.startsWith('/api/v1/skills')) {
    const fallbackUrl = url.replace('/api/v1/skills', '/api/v1/admin/skills');
    const fallbackRes = await fetch(fallbackUrl, options);
    if (fallbackRes.ok) {
      return fallbackRes;
    }
  }
  return res;
}
