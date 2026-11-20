/**
 * =============================================================================
 * Process Name: Windows Web Interface - IndexedDB Offline-First Cache
 * =============================================================================
 * Description:
 *   Клиентский кэш Offline-First на базе IndexedDB (ТЗ v2.2 / 01_FRONTEND.md).
 *   Обеспечивает мгновенный отклик (< 10 мс), хранение реестра ПО,
 *   тяжелых системных журналов и отмену сетевых запросов при смене вкладок.
 *
 * File: indexeddb-cache.js
 * Project: ai-tc
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

const DB_NAME = 'AIWindowsAdminDB';
const DB_VERSION = 2;
const STORES = ['software_inventory', 'software_heavy', 'software_sockets', 'system_logs', 'app_metadata'];

let dbPromise = null;

function openDatabase() {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      console.warn('[IndexedDBCache] IndexedDB не поддерживается браузером');
      resolve(null);
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      STORES.forEach((storeName) => {
        if (!db.objectStoreNames.contains(storeName)) {
          db.createObjectStore(storeName, { keyPath: 'key' });
        }
      });
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = (err) => {
      console.error('[IndexedDBCache] Ошибка открытия БД:', err);
      resolve(null);
    };
  });

  return dbPromise;
}

// Глобальный AbortController для отмены сетевых запросов при переключении вкладок
window.activeTabAbortController = null;

/**
 * Отменяет предыдущие летящие запросы и создает свежий AbortController.
 * @returns {AbortSignal}
 */
function getFreshAbortSignal() {
  if (window.activeTabAbortController) {
    try {
      window.activeTabAbortController.abort();
    } catch (_) {}
  }
  window.activeTabAbortController = new AbortController();
  return window.activeTabAbortController.signal;
}

const IndexedDBCache = {
  /**
   * Сохранить данные в хранилище IndexedDB.
   * @param {string} storeName - Имя хранилища.
   * @param {string} key - Ключ записи.
   * @param {any} data - Данные для кэширования.
   */
  async set(storeName, key, data) {
    const db = await openDatabase();
    if (!db) return false;

    return new Promise((resolve) => {
      try {
        const tx = db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        store.put({ key, data, timestamp: Date.now() });
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => resolve(false);
      } catch (e) {
        console.warn(`[IndexedDBCache] Ошибка записи в ${storeName}:`, e);
        resolve(false);
      }
    });
  },

  /**
   * Алиас для set (совместимость с кодом программных вкладок).
   * @param {string} storeName - Имя хранилища.
   * @param {string} key - Ключ записи.
   * @param {any} data - Данные для кэширования.
   */
  async put(storeName, key, data) {
    return this.set(storeName, key, data);
  },

  /**
   * Получить данные из хранилища IndexedDB (время отклика < 10 мс).
   * @param {string} storeName - Имя хранилища.
   * @param {string} key - Ключ записи.
   * @returns {Promise<any|null>}
   */
  async get(storeName, key) {
    const db = await openDatabase();
    if (!db) return null;

    return new Promise((resolve) => {
      try {
        const tx = db.transaction(storeName, 'readonly');
        const store = tx.objectStore(storeName);
        const request = store.get(key);
        request.onsuccess = () => {
          if (request.result && request.result.data !== undefined) {
            resolve(request.result.data);
          } else {
            resolve(null);
          }
        };
        request.onerror = () => resolve(null);
      } catch (e) {
        console.warn(`[IndexedDBCache] Ошибка чтения из ${storeName}:`, e);
        resolve(null);
      }
    });
  },

  /**
   * Очистить хранилище или удалить устаревшие записи.
   * @param {string} storeName - Имя хранилища.
   */
  async clear(storeName) {
    const db = await openDatabase();
    if (!db) return;

    try {
      const tx = db.transaction(storeName, 'readwrite');
      tx.objectStore(storeName).clear();
    } catch (e) {
      console.warn(`[IndexedDBCache] Ошибка очистки ${storeName}:`, e);
    }
  },

  /**
   * Получить свежий AbortSignal для отмены фоновых запросов вкладки.
   * @returns {AbortSignal}
   */
  getFreshAbortSignal() {
    return getFreshAbortSignal();
  },
};

window.IndexedDBCache = IndexedDBCache;
window.getFreshAbortSignal = getFreshAbortSignal;

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { IndexedDBCache, getFreshAbortSignal };
}

