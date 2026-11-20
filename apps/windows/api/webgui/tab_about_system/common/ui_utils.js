/**
 * Модуль общих вспомогательных утилит и клиентского кеширования для вкладки «О Системе».
 * 
 * Включает IndexedDB/Memory кеширование статической спецификации хоста (Cache-First),
 * безопасное экранирование XSS, вспомогательные функции манипуляции DOM.
 * 
 * Updated: 2026-11-16 05:24:00
 */

export const CACHE_STRATEGY = {
  HARDWARE_SPEC: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  SYSTEM_SUMMARY: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  CONTROL_STATUS: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  BACKUP_STATUS: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  STORAGE_BATTERY: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  PANEL_KPI: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' },
  BUNDLE: { ttl: 24 * 60 * 60 * 1000, strategy: 'cache-first' }
};

export const CACHE_STORE = 'api_cache';
export const CACHE_TAG = 'about-system-tab';

/**
 * Универсальная функция для работы с кешем (cache-first, network-first, stale-while-revalidate).
 * 
 * @param {string} url - URL эндпоинта.
 * @param {string} cacheKey - Ключ кеша.
 * @param {Object} options - Параметры кеширования.
 * @returns {Promise<any>}
 */
export async function cachedFetch(url, cacheKey, options = {}) {
  const { ttl = 60000, strategy = 'stale-while-revalidate', forceNetwork = false, onBackgroundUpdate = null } = options;
  const cache = window.browserCache;
  
  if (!cache) {
    return await apiFetch(url);
  }
  
  if (strategy === 'cache-first' && !forceNetwork) {
    const cached = await cache.get(CACHE_STORE, cacheKey);
    if (cached) {
      return cached;
    }
  }
  
  if (strategy === 'stale-while-revalidate' && !forceNetwork) {
    const cached = await cache.get(CACHE_STORE, cacheKey);
    if (cached) {
      apiFetch(url)
        .then(fresh => {
          if (fresh) {
            cache.set(CACHE_STORE, cacheKey, fresh, { ttl, tags: [CACHE_TAG] });
            if (typeof onBackgroundUpdate === 'function') {
              onBackgroundUpdate(fresh);
            }
          }
        })
        .catch(err => console.warn(`[Cache] Фоновое обновление не удалось для ${cacheKey}:`, err));
      return cached;
    }
  }
  
  try {
    const fresh = await apiFetch(url);
    await cache.set(CACHE_STORE, cacheKey, fresh, { ttl, tags: [CACHE_TAG] });
    return fresh;
  } catch (err) {
    const cached = await cache.get(CACHE_STORE, cacheKey);
    if (cached) {
      console.warn(`[Cache] Ошибка сети, возвращаем устаревший кеш: ${cacheKey}`);
      return cached;
    }
    throw err;
  }
}

/**
 * Очистка кеша вкладки «О Системе».
 */
export async function clearTabCache() {
  const cache = window.browserCache;
  if (cache) {
    await cache.invalidateByTag(CACHE_STORE, CACHE_TAG);
    console.log('[Cache] Кеш вкладки «О Системе» очищен');
  }
}

/**
 * Выполнение HTTP запроса через API мост или fetch.
 * 
 * @param {string} url - URL эндпоинта.
 * @param {Object} options - Параметры fetch.
 * @returns {Promise<any>}
 */
export async function apiFetch(url, options = {}) {
  const opts = { ...options };
  if (opts.body && typeof opts.body === 'string') {
    opts.headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {})
    };
  }
  if (window.api && typeof window.api.fetch === 'function') {
    return await window.api.fetch(url, opts);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errMsg += ` (${typeof errJson.detail === 'object' ? JSON.stringify(errJson.detail) : errJson.detail})`;
      }
    } catch (_) {}
    throw new Error(errMsg);
  }
  return await res.json();
}

const STATUS_DANGER_RE = /(?<![\p{L}\p{N}_])(Не\s+подключен(?:[оаы]|н[а-я]+)?|Отключен(?:[оаы]|н[а-я]+)?|Выключен(?:[оаы]|н[а-я]+)?|Не\s+работает|Остановлен(?:[оаы]|н[а-я]+)?|Не\s*актив(?:ен|н[а-я]+)?|Не\s*исправ(?:ен|н[а-я]+)?|Не\s*защищен(?:[оаы]|н[а-я]+)?|Не\s*доступ(?:ен|н[а-я]+)?|Сбой|Ошибка|Disconnected|Disabled|Inactive|Stopped|Offline|Error|Problem|Failed|Fault|Degraded|Bad|Not\s+Present|Отсутствует|OFF|False|Нет|No)(?![\p{L}\p{N}_])/gui;
const STATUS_SUCCESS_RE = /(?<![\p{L}\p{N}_])(Подключен(?:[оаы]|н[а-я]+)?|Работает|В\s+работе|Актив(?:ен|н[а-я]+)?|Включен(?:[оаы]|н[а-я]+)?|Исправ(?:ен|н[а-я]+)?|Защищен(?:[оаы]|н[а-я]+)?|Доступ(?:ен|н[а-я]+)?|Оптимально|Connected|Active|Enabled|Running|Online|OK|Healthy|Protected|Present|Up\s+to\s+date|ON|True|Да|Yes)(?![\p{L}\p{N}_])/gui;
const STATUS_NEUTRAL_RE = /(?<![\p{L}\p{N}_])(Не\s+установлен(?:[оаы]|н[а-я]+)?|Не\s+настроен(?:[оаы]|н[а-я]+)?|Не\s+определен(?:[оаы]|н[а-я]+)?|Нет\s+записей)(?![\p{L}\p{N}_])/gui;

export function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text !== null && text !== undefined ? String(text) : '--';
}

/**
 * Форматирует значение параметра с подсветкой булевых и статусных состояний (зеленый / красный шрифт).
 * @param {any} val - Значение параметра (boolean, string, number).
 * @returns {string} HTML-строка со стилизованными статусными значениями.
 */
export function formatStatusHtml(val) {
  if (val === null || val === undefined) return '--';
  if (typeof val === 'boolean') {
    return val 
      ? '<span class="text-success fw-bold">Да (Включено)</span>'
      : '<span class="text-danger fw-bold">Нет (Отключено)</span>';
  }
  const sRaw = String(val).trim();
  if (sRaw === '') return '--';
  if (sRaw.toLowerCase() === 'true') {
    return '<span class="text-success fw-bold">Да (Включено)</span>';
  }
  if (sRaw.toLowerCase() === 'false') {
    return '<span class="text-danger fw-bold">Нет (Отключено)</span>';
  }

  let s = escapeHtml(sRaw);
  s = s.replace(STATUS_NEUTRAL_RE, '<span class="text-muted">$1</span>');
  s = s.replace(STATUS_DANGER_RE, (match, p1, offset, full) => {
    const before = full.slice(0, offset);
    if (before.lastIndexOf('<span') > before.lastIndexOf('</span>')) return match;
    return `<span class="text-danger fw-bold">${p1}</span>`;
  });
  s = s.replace(STATUS_SUCCESS_RE, (match, p1, offset, full) => {
    const before = full.slice(0, offset);
    if (before.lastIndexOf('<span') > before.lastIndexOf('</span>')) return match;
    return `<span class="text-success fw-bold">${p1}</span>`;
  });
  return s;
}

export function setStatusText(id, isPositive, activeText = 'Включен', inactiveText = 'Отключен') {
  const el = document.getElementById(id);
  if (!el) return;
  const active = Boolean(isPositive);
  el.textContent = active ? activeText : inactiveText;
  el.className = active ? 'text-success fw-bold' : 'text-danger fw-bold';
}

export function setFormattedStatusHtml(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  if (!text) { el.innerHTML = '--'; return; }
  el.innerHTML = formatStatusHtml(text);
}

export function setHtml(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function formatIsoDate(isoStr) {
  if (!isoStr || typeof isoStr !== 'string') return '--';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (_) {
    return isoStr;
  }
}

export function isValidHttpUrl(str) {
  if (!str || typeof str !== 'string' || str === 'n/a') return false;
  return /^https?:\/\//i.test(str.trim());
}

/**
 * Управление отображением глобального спиннера обновления данных.
 * @param {boolean} show
 */
export function showGlobalSpinner(show = true) {
  const spinner = document.getElementById('about-sys-loading') || document.querySelector('.about-global-spinner');
  if (spinner) {
    if (show) {
      spinner.classList.remove('d-none');
    } else {
      spinner.classList.add('d-none');
    }
  }
}
