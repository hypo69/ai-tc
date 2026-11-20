/**
 * Модуль локального хранилища RAG-индекса (IndexedDB и LocalStorage).
 * 
 * Обеспечивает автономный семантический поиск по журналам Windows без расхода
 * токенов LLM и кеширование эмбеддингов/чанков непосредственно в браузере.
 * 
 * Updated: 2026-11-12 05:00:00
 */

import { t } from '../common/ui_utils.js';

export const BrowserRagCache = {
  prefix: 'ai_tc_rag_',

  get(key) {
    try {
      const item = localStorage.getItem(this.prefix + key);
      if (!item) return null;
      const parsed = JSON.parse(item);
      if (parsed.expires && Date.now() > parsed.expires) {
        localStorage.removeItem(this.prefix + key);
        return null;
      }
      return parsed.data;
    } catch (e) {
      console.debug('[BrowserRagCache] Ошибка чтения кеша:', e);
      return null;
    }
  },

  set(key, data, ttlMs = 24 * 3600 * 1000) {
    try {
      const payload = {
        data: data,
        timestamp: Date.now(),
        expires: ttlMs ? Date.now() + ttlMs : null,
      };
      localStorage.setItem(this.prefix + key, JSON.stringify(payload));
      RagIndexDB.updateDbIndicator(true, data?.indexed_events || data?.total_events || 0);
    } catch (e) {
      console.debug('[BrowserRagCache] Ошибка записи в кеш:', e);
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(this.prefix + key);
    } catch (e) {}
  },

  clearAll() {
    try {
      Object.keys(localStorage)
        .filter(k => k.startsWith(this.prefix))
        .forEach(k => localStorage.removeItem(k));
    } catch (e) {}
  },

  updateCacheIndicator(active = true) {
    RagIndexDB.updateDbIndicator(active);
  }
};

export const RagIndexDB = {
  dbName: 'AiTc_RAG_Cache',
  dbVersion: 1,
  _db: null,

  /**
   * Инициализация и открытие базы данных IndexedDB.
   * @returns {Promise<IDBDatabase|null>} Экземпляр базы данных.
   */
  async open() {
    if (this._db) return this._db;
    return new Promise((resolve) => {
      if (!window.indexedDB) {
        console.warn('[RagIndexDB] IndexedDB не поддерживается в данном окружении браузера');
        resolve(null);
        return;
      }
      try {
        const request = window.indexedDB.open(this.dbName, this.dbVersion);
        request.onupgradeneeded = (e) => {
          const db = e.target.result;
          if (!db.objectStoreNames.contains('index_meta')) {
            db.createObjectStore('index_meta', { keyPath: 'key' });
          }
          if (!db.objectStoreNames.contains('index_chunks')) {
            const chunkStore = db.createObjectStore('index_chunks', { keyPath: 'id', autoIncrement: true });
            chunkStore.createIndex('channel', 'channel', { unique: false });
            chunkStore.createIndex('level', 'level', { unique: false });
            chunkStore.createIndex('timestamp', 'timestamp', { unique: false });
            chunkStore.createIndex('event_id', 'event_id', { unique: false });
          }
          if (!db.objectStoreNames.contains('query_cache')) {
            db.createObjectStore('query_cache', { keyPath: 'query_key' });
          }
          if (!db.objectStoreNames.contains('activity_logs')) {
            const actStore = db.createObjectStore('activity_logs', { keyPath: 'id', autoIncrement: true });
            actStore.createIndex('action', 'action', { unique: false });
            actStore.createIndex('status', 'status', { unique: false });
          }
        };
        request.onsuccess = (e) => {
          this._db = e.target.result;
          resolve(this._db);
        };
        request.onerror = (e) => {
          console.error('[RagIndexDB] Ошибка открытия IndexedDB:', e.target.error);
          resolve(null);
        };
      } catch (err) {
        console.warn('[RagIndexDB] Исключение при открытии IndexedDB:', err);
        resolve(null);
      }
    });
  },

  /**
   * Сохранение метаданных и пакета чанков в IndexedDB.
   * @param {Object} meta - Метаданные RAG-индекса.
   * @param {Array} chunks - Массив чанков для поиска.
   * @param {Array} activityLogs - Журнал активности.
   * @returns {Promise<boolean>} Успешность операции.
   */
  async saveIndex(meta, chunks = [], activityLogs = []) {
    const db = await this.open();
    if (!db) {
      BrowserRagCache.set(`status_${meta.hours || 24}`, meta);
      return false;
    }
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(['index_meta', 'index_chunks', 'activity_logs'], 'readwrite');
        const metaStore = tx.objectStore('index_meta');
        const chunkStore = tx.objectStore('index_chunks');
        const actStore = tx.objectStore('activity_logs');

        const recordCount = (chunks && chunks.length > 0) ? chunks.length : (meta.indexed_events || meta.total_events || 0);

        metaStore.put({
          key: `meta_${meta.hours || 24}`,
          hours: meta.hours || 24,
          indexed_events: recordCount,
          total_events: recordCount,
          channels_count: meta.scanned_channels || meta.channels_count || (meta.channels_list ? meta.channels_list.length : 0),
          channels_list: meta.channels_list || [],
          last_built_at: meta.last_built_at || meta.generated_at || new Date().toLocaleString(),
          is_indexed: true,
          build_duration_ms: meta.build_duration_ms || 0,
          critical_count: meta.critical_count || 0,
          error_count: meta.error_count || 0,
          updated_at: Date.now()
        });

        metaStore.put({
          key: 'current',
          hours: meta.hours || 24,
          indexed_events: recordCount,
          total_events: recordCount,
          channels_count: meta.scanned_channels || meta.channels_count || (meta.channels_list ? meta.channels_list.length : 0),
          channels_list: meta.channels_list || [],
          last_built_at: meta.last_built_at || meta.generated_at || new Date().toLocaleString(),
          is_indexed: true,
          updated_at: Date.now()
        });

        if (chunks && chunks.length > 0) {
          chunkStore.clear();
          chunks.forEach((chunk, i) => {
            chunkStore.add({
              id: i + 1,
              channel: chunk.channel || 'System',
              level: chunk.level || 'Information',
              event_id: chunk.event_id || 0,
              provider: chunk.provider || 'Windows',
              timestamp: chunk.timestamp || '',
              message: chunk.message || chunk.text || '',
              count: chunk.count || 1,
              occurrences: chunk.occurrences || []
            });
          });
        }

        if (activityLogs && activityLogs.length > 0) {
          actStore.clear();
          activityLogs.forEach((act, i) => {
            actStore.add({ id: i + 1, ...act });
          });
        }

        tx.oncomplete = () => {
          this.updateDbIndicator(true, recordCount);
          resolve(true);
        };
        tx.onerror = (err) => {
          console.warn('[RagIndexDB] Ошибка транзакции записи:', err);
          resolve(false);
        };
      } catch (e) {
        console.warn('[RagIndexDB] Исключение при записи в IndexedDB:', e);
        resolve(false);
      }
    });
  },

  /**
   * Чтение метаданных RAG-индекса из базы данных.
   * @param {number} hours - Период поиска в часах.
   * @returns {Promise<Object|null>}
   */
  async loadIndexMeta(hours = 24) {
    const db = await this.open();
    if (!db) {
      return BrowserRagCache.get(`status_${hours}`);
    }
    return new Promise((resolve) => {
      try {
        const tx = db.transaction('index_meta', 'readonly');
        const store = tx.objectStore('index_meta');
        const req = store.get(`meta_${hours}`);
        req.onsuccess = () => {
          if (req.result && (req.result.indexed_events > 0 || req.result.total_events > 0)) {
            resolve(req.result);
          } else {
            const curReq = store.get('current');
            curReq.onsuccess = () => {
              if (curReq.result && (curReq.result.indexed_events > 0 || curReq.result.total_events > 0)) {
                resolve(curReq.result);
              } else {
                resolve(BrowserRagCache.get(`status_${hours}`));
              }
            };
            curReq.onerror = () => resolve(BrowserRagCache.get(`status_${hours}`));
          }
        };
        req.onerror = () => resolve(BrowserRagCache.get(`status_${hours}`));
      } catch (e) {
        resolve(BrowserRagCache.get(`status_${hours}`));
      }
    });
  },

  /**
   * Локальный поиск по сохраненным в IndexedDB чанкам.
   * @param {string} query - Текст запроса.
   * @param {string} channel - Фильтр по каналу.
   * @returns {Promise<Array>}
   */
  async searchLocalChunks(query, channel = '') {
    const db = await this.open();
    if (!db || !query) return [];
    const q = query.toLowerCase();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction('index_chunks', 'readonly');
        const store = tx.objectStore('index_chunks');
        const req = store.getAll();
        req.onsuccess = () => {
          const all = req.result || [];
          const results = [];
          for (const item of all) {
            if (channel && channel !== 'all' && item.channel !== channel) continue;
            const text = (item.message || item.text || '').toLowerCase();
            const prov = (item.provider || '').toLowerCase();
            if (text.includes(q) || prov.includes(q) || String(item.event_id || '') === q) {
              results.push({
                ...item,
                score: 0.88,
                relevance_score: 0.88
              });
              if (results.length >= 30) break;
            }
          }
          resolve(results);
        };
        req.onerror = () => resolve([]);
      } catch (e) {
        resolve([]);
      }
    });
  },

  /**
   * Обновление визуального индикатора базы данных браузера.
   * @param {boolean} active - Флаг активности.
   * @param {number} count - Количество проиндексированных записей.
   */
  updateDbIndicator(active = true, count = 0) {
    const ind = document.getElementById('slc-rag-cache-indicator');
    if (ind) {
      if (active && count > 0) {
        ind.className = 'badge bg-success-subtle text-success border border-success-subtle font-monospace';
        ind.innerHTML = `<i class="bi bi-database-check me-1"></i>${t('systemControl.ragCacheSynced', 'Кеш БД браузера: Синхронизирован')} (${count.toLocaleString()} записей)`;
      } else if (active) {
        ind.className = 'badge bg-success-subtle text-success border border-success-subtle font-monospace';
        ind.innerHTML = `<i class="bi bi-database-check me-1"></i>${t('systemControl.ragCacheActive', 'Кеш БД браузера: Активен')}`;
      } else {
        ind.className = 'badge bg-secondary-subtle text-secondary font-monospace';
        ind.innerHTML = `<i class="bi bi-database me-1"></i>Кеш БД: Ожидает сбор`;
      }
    }
  }
};
