/**
 * =============================================================================
 * Process Name: Windows WebGUI - Universal Panel Loader
 * =============================================================================
 * Description:
 *   Клиентский модуль автоматической загрузки данных для панелей интерфейса.
 *   Каждая панель с div id="panel-{panel_id}" или data-panel-id="{panel_id}"
 *   при инициализации/активации страницы и вкладок вызывает эндпоинт:
 *   GET /api/v1/panel/{panel_id} -> выполнение SQL-запроса в SQLite (telemetry.db).
 *
 * Usage Examples:
 *   HTML:
 *     <div id="panel-cpu-load" class="ui-panel" data-panel-id="panel-cpu-load">...</div>
 *     <script src="/html/js/panel-loader.js?v=20261010_v2"></script>
 *
 *   JavaScript:
 *     import { loadPanelData, initPanels } from '/html/js/panel-loader.js';
 *     await loadPanelData('panel-cpu-load');
 *
 * File: panel-loader.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 17:30:00
 * =============================================================================
 */

const panelRenderers = new Map();
const panelDataCache = new Map();
const pendingRequests = new Map();

/**
 * Загружает данные для панели через GET /api/v1/panel/{panel_id}.
 * @param {string} panelId - Идентификатор панели
 * @param {Object} [options] - Дополнительные параметры запроса (limit, force)
 * @returns {Promise<Object>} Данные ответа SQL-запроса
 */
export async function loadPanelData(panelId, options = {}) {
  if (!panelId) return null;
  const cleanId = panelId.trim();

  // Вкладка «О системе» обслуживается исключительно единым эндпоинтом /api/v1/about-system/bundle.
  // Разрозненные запросы отдельных панелей строго запрещены.
  if (cleanId.startsWith('panel-about-') || cleanId.startsWith('about_system-')) {
    return null;
  }

  // Если уже выполняется запрос для этого panelId, возвращаем существующий промис
  if (pendingRequests.has(cleanId) && !options.force) {
    return pendingRequests.get(cleanId);
  }

  const limit = options.limit || 60;
  const url = `/api/v1/panel/${encodeURIComponent(cleanId)}?limit=${limit}&t=${Date.now()}`;

  const el = document.getElementById(cleanId) || document.querySelector(`[data-panel-id="${cleanId}"]`);
  if (el) {
    el.setAttribute('data-panel-status', 'loading');
  }

  const fetchPromise = (async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const result = await res.json();
      panelDataCache.set(cleanId, result);

      if (el) {
        el.setAttribute('data-panel-status', 'loaded');
        if (result.sql) {
          el.setAttribute('data-panel-sql', result.sql);
        }
        el._panelData = result;
      }

      // Вызов зарегистрированного рендерера
      const renderer = panelRenderers.get(cleanId);
      if (typeof renderer === 'function') {
        try {
          renderer(result, el);
        } catch (rErr) {
          console.warn(`[PanelLoader] Ошибка рендера панели ${cleanId}:`, rErr);
        }
      }

      // Диспетчеризация кастомных событий
      const eventDetail = { panelId: cleanId, result, data: result.data || [], sql: result.sql };
      document.dispatchEvent(new CustomEvent('panel:data', { detail: eventDetail }));
      document.dispatchEvent(new CustomEvent(`panel:${cleanId}:loaded`, { detail: eventDetail }));

      return result;
    } catch (err) {
      console.warn(`[PanelLoader] Ошибка загрузки данных панели ${cleanId}:`, err);
      if (el) {
        el.setAttribute('data-panel-status', 'error');
      }
      return { status: 'error', panel_id: cleanId, error: err.message, data: [] };
    } finally {
      pendingRequests.delete(cleanId);
    }
  })();

  pendingRequests.set(cleanId, fetchPromise);
  return fetchPromise;
}

/**
 * Регистрирует пользовательскую функцию отрисовки для панели.
 * @param {string} panelId 
 * @param {Function} renderFn 
 */
export function registerPanelRenderer(panelId, renderFn) {
  if (panelId && typeof renderFn === 'function') {
    panelRenderers.set(panelId, renderFn);
  }
}

/**
 * Инициализирует и опрашивает все панели внутри контейнера.
 * @param {HTMLElement|Document} [container=document] 
 */
export function initPanels(container = document) {
  if (!container || typeof container.querySelectorAll !== 'function') return;

  // Если весь переданный контейнер обслуживается собственным специализированным API, пропускаем его целиком
  if (container.id === 'tab-about-system' || (container.classList && container.classList.contains('about-sys-wrapper')) ||
      container.id === 'tab-processes-load-inspector' || (container.classList && container.classList.contains('sys-container')) ||
      container.id === 'tab-system-control' || (container.classList && (container.classList.contains('slc-container') || container.classList.contains('scc-container'))) ||
      container.id === 'tab-user-environment' || container.id === 'tab-user-enviroment' || (container.classList && container.classList.contains('user-environment-tab-wrapper')) ||
      container.id === 'tab-windows-admin' || (container.classList && container.classList.contains('windows-admin-tab-wrapper')) || container.id === 'windows-admin-root' ||
      container.id === 'tab-taskbar' || container.id === 'tab-taskbar-controller' || (container.classList && container.classList.contains('taskbar-tab-wrapper')) ||
      container.querySelector?.('#processes-subtabs-nav') || container.querySelector?.('#slc-source-tabs') || container.querySelector?.('#userEnvSubTabs') || container.querySelector?.('#winadmin-subtabs')) {
    return;
  }

  const elements = container.querySelectorAll('[id^="panel-"], [data-panel-id]');
  const processedIds = new Set();

  elements.forEach((el) => {
    // Панели вкладок со своим специализированным контроллером не опрашивают универсальный SQL API
    if (el.closest('#tab-about-system') || el.closest('.about-sys-wrapper') ||
        el.closest('#tab-processes-load-inspector') || el.closest('#processes-load-inspector-container') ||
        el.closest('#tab-system-control') || el.closest('.slc-container') || el.closest('.scc-container') ||
        el.closest('#tab-user-environment') || el.closest('#tab-user-enviroment') || el.closest('.user-environment-tab-wrapper') ||
        el.closest('#tab-windows-admin') || el.closest('#windows-admin-root') || el.closest('.winadmin-panel') ||
        el.closest('#tab-taskbar') || el.closest('#tab-taskbar-controller') || el.closest('.taskbar-tab-wrapper')) {
      return;
    }

    // Если элемент находится в неактивной вкладке, не запрашиваем его
    const tabPane = el.closest('.tab-pane');
    if (tabPane) {
      if (typeof window.isTabActive === 'function' && !window.isTabActive(tabPane.id)) {
        return;
      }
      if (!tabPane.classList.contains('active')) {
        return;
      }
    }

    const panelId = el.getAttribute('data-panel-id') || el.id;
    if (panelId && (
      panelId.startsWith('panel-about-') ||
      panelId.startsWith('about_system-') ||
      panelId.startsWith('panel-system-') ||
      panelId.startsWith('panel-slc-') ||
      panelId.startsWith('panel-throttling-') ||
      panelId.startsWith('panel-winadmin-') ||
      panelId.startsWith('panel-taskbar-') ||
      panelId.startsWith('panel-ue-')
    )) {
      return;
    }

    // Проверка активности суб-панели по URL (#tab-xxx#panel-yyy)
    if (tabPane && typeof window.isPanelActive === 'function') {
      if (!window.isPanelActive(tabPane.id, panelId)) {
        return;
      }
    }

    if (panelId && !processedIds.has(panelId)) {
      processedIds.add(panelId);
      loadPanelData(panelId);
    }
  });
}

// Экспорт в глобальный контекст window
if (typeof window !== 'undefined') {
  window.loadPanelData = loadPanelData;
  window.registerPanelRenderer = registerPanelRenderer;
  window.initPanels = initPanels;

  // Автоматический опрос панелей при активации вкладки (кроме tab-about-system)
  document.addEventListener('tab:activated', (e) => {
    const tabId = e.detail?.tabId;
    if (tabId && tabId !== 'tab-about-system') {
      const tabPane = document.getElementById(tabId);
      if (tabPane) {
        initPanels(tabPane);
      }
    }
  });

  // Первичная инициализация при готовности DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initPanels(document));
  } else {
    setTimeout(() => initPanels(document), 100);
  }
}
