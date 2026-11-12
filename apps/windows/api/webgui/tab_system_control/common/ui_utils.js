/**
 * Модуль общих графических и вспомогательных утилит для вкладки System Logs & Control.
 * 
 * Включает экранирование HTML, форматирование времени, определение классов важности событий,
 * настройку ресайзеров таблиц и динамический расчет высоты контейнеров.
 * 
 * Updated: 2026-11-11 23:20:00
 */

/**
 * Локализация ключа через i18next с fallback значением.
 *
 * @param {string} key - Ключ локализации.
 * @param {string} fallback - Значение по умолчанию.
 * @returns {string} Локализованный текст.
 */
export function t(key, fallback) {
  if (window.i18next && typeof window.i18next.t === 'function' && window.i18next.isInitialized) {
    const res = window.i18next.t(key);
    if (res && res !== key) return res;
  }
  return fallback !== undefined ? fallback : key;
}

/**
 * Экранирование специальных символов HTML для предотвращения XSS атак.
 *
 * @param {string} str - Исходный текст.
 * @returns {string} Безопасный HTML текст.
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
 * Форматирование ISO метки времени в локальное время (HH:MM:SS).
 *
 * @param {string} isoStr - Строка ISO timestamp.
 * @returns {string} Отформатированное время.
 */
export function formatTime(isoStr) {
  if (!isoStr) return '-';
  try {
    return new Date(isoStr).toLocaleTimeString();
  } catch {
    return isoStr.slice(11, 19);
  }
}

/**
 * Получение CSS-класса бейджа в зависимости от уровня важности события Windows.
 *
 * @param {string} level - Уровень события (Critical, Error, Warning, Verbose, Info).
 * @returns {string} Имя CSS-класса.
 */
export function getSeverityClass(level) {
  const lvl = (level || '').toLowerCase();
  if (lvl.includes('crit')) return 'badge-crit';
  if (lvl.includes('err')) return 'badge-err';
  if (lvl.includes('warn')) return 'badge-warn';
  if (lvl.includes('verb')) return 'badge-verb';
  return 'badge-inf';
}

/**
 * Инициализация интерактивных ресайзеров для табличных контейнеров вкладки.
 */
export function initTableResizers() {
  function setupResizer(resizerId, containerId, defaultMaxHeight = 520, minH = 140, maxH = 1500) {
    const resizer = document.getElementById(resizerId);
    const container = document.getElementById(containerId);
    if (!resizer || !container || resizer._resizerBound) return;
    resizer._resizerBound = true;

    let startY = 0, startHeight = 0;
    const onMouseMove = (e) => {
      const delta = e.clientY - startY;
      const newH = Math.max(minH, Math.min(maxH, startHeight + delta));
      container.style.maxHeight = 'none';
      container.style.height = `${newH}px`;
    };
    const onMouseUp = () => {
      resizer.classList.remove('resizing');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    resizer.onmousedown = (e) => {
      e.preventDefault();
      startY = e.clientY;
      startHeight = container.getBoundingClientRect().height || parseInt(window.getComputedStyle(container).height, 10) || defaultMaxHeight;
      resizer.classList.add('resizing');
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    };
    resizer.ondblclick = () => {
      container.style.height = '';
      container.style.maxHeight = '';
      adjustMainStreamHeight();
    };
  }

  setupResizer('el-table-resizer', 'el-table-container', 520, 140, 1500);
  setupResizer('slc-table-resizer', 'slc-table-container', 560, 140, 1500);
  setupResizer('pwr-sessions-table-resizer', 'pwr-sessions-table-container', 520, 140, 1500);
  setupResizer('pwr-events-table-resizer', 'pwr-events-table-container', 520, 140, 1500);
  setupResizer('def-events-table-resizer', 'def-events-table-container', 520, 140, 1500);
}

/**
 * Автоматическая адаптация максимальной высоты видимых контейнеров под высоту экрана браузера.
 */
export function adjustMainStreamHeight() {
  const bottomOffset = 20;
  const containerIds = [
    'slc-table-container',
    'slc-channel-tree-container',
    'slc-audit-container',
    'slc-rag-container',
    'slc-incidents-container',
    'slc-timeline-container',
    'slc-raw-container',
    'pwr-sessions-table-container',
    'pwr-events-table-container',
    'def-events-table-container'
  ];

  containerIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el || el.classList.contains('d-none')) return;
    if (el.style.height && el.style.height !== '') return;
    const rect = el.getBoundingClientRect();
    if (rect.top > 0) {
      const availH = Math.max(300, Math.floor(window.innerHeight - rect.top - bottomOffset));
      el.style.maxHeight = `${availH}px`;
    }
  });
}
