/**
 * =============================================================================
 * Process Name: Windows Js - Tab-Core Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля tab-core.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/js/tab-core.js?v=20261001_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { normalizeTabId, isTabActive, registerTabPoller } from '/windows/api/webgui/js/tab-core.js';
 *
 * File: tab-core.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:25:00
 * =============================================================================
 */

/**
 * tab-core.js — Единая система управления вкладками, их жизненным циклом и поллингом.
 * Архитектура: UI_ARCHITECTURE.md
 * 
 * Правило: Только открытая АКТИВНАЯ вкладка и АКТИВНАЯ панель (#tab_id#panel_id)
 * выполняют периодические опросы API. Неактивные вкладки и панели не запрашивают ничего.
 * При неактивности вкладки/панели или скрытии страницы (visibilitychange) все таймеры засыпают.
 * Сценарий опроса запускается немедленно при открытии вкладки/панели.
 * 
 * Приоритет переключения: кнопки навигации имеют самый высокий приоритет.
 * Если что-то запущено внутри вкладки, переключение происходит немедленно без ожидания.
 */

const OFFCANVAS_IDS = ['leftSideNavOffcanvas', 'appsSideNavOffcanvas'];

const TAB_ALIASES = {
  'user-enviroment': 'tab-user-environment',
  'tab-user-enviroment': 'tab-user-environment',
  'user-environment': 'tab-user-environment',
  'accounts-identity': 'tab-windows-admin',
  'tab-accounts-identity': 'tab-windows-admin',
  'windows-admin': 'tab-windows-admin',
  'system-control': 'tab-system-control',
  'tab-system-logs': 'tab-system-control',
  'system-logs': 'tab-system-control',
  'taskbar-controller': 'tab-taskbar',
  'tab-taskbar-controller': 'tab-taskbar',
  'taskbar': 'tab-taskbar'
};

const CONSOLIDATED_PARENTS = {
  'tab-telemetry-control': 'tab-app-internals',
  'tab-telemetry-config': 'tab-app-internals',
  'tab-models': 'tab-app-internals',
  'tab-system-logs': 'tab-app-internals',
  'tab-performance-tracing': 'tab-app-internals',
  'tab-log-settings': 'tab-app-internals',
  'tab-agents': 'tab-ai-ecosystem',
  'tab-skills': 'tab-ai-ecosystem',
  'tab-mcp': 'tab-ai-ecosystem',
  'tab-storage-manager': 'tab-storage-management',
  'tab-storage-wear': 'tab-storage-management',
  'tab-defender': 'tab-defender-firewall',
  'tab-defender-firewall': 'tab-defender-firewall',
  'tab-firewall-manager': 'tab-defender-firewall',
  'tab-software-audit': 'tab-software-monitor',
  'tab-software-manager': 'tab-software-monitor',
  'tab-software-transparency': 'tab-software-monitor',
  'tab-ninite-updater': 'tab-software-monitor',
  'tab-startup-auditor': 'tab-software-monitor',
  'tab-software-scanner': 'tab-software-monitor',
  'tab-software-monitor': 'tab-software-monitor',
  'tab-forensics': 'tab-system-control',
  'tab-forensics-timeline': 'tab-system-control',
  'tab-forensics-userassist': 'tab-system-control',
  'tab-throttling': 'tab-system-control',
};

let currentActiveTabId = null;
const registeredPollers = new Map();
const processingFlags = new Map(); // хранит флаг isProcessing для каждой вкладки

/**
 * Приводит идентификатор вкладки к стандартному виду 'tab-xxx' с учетом алиасов.
 * @param {string} tabId 
 * @returns {string}
 */
export function normalizeTabId(tabId) {
  if (!tabId) return '';
  const base = String(tabId).replace(/^#/, '').split('#')[0].trim().toLowerCase();
  if (TAB_ALIASES[base]) return TAB_ALIASES[base];
  const withTab = base.startsWith('tab-') ? base : `tab-${base}`;
  return TAB_ALIASES[withTab] || withTab;
}

/**
 * Проверяет, активна ли сейчас вкладка (видна пользователю и вкладка браузера в фокусе).
 * Приоритет проверки:
 * 1. Состояние видимости документа браузера (document.hidden)
 * 2. URL hash браузера (наивысшая согласованность роутинга)
 * 3. currentActiveTabId оркестратора
 * 4. DOM класс .tab-pane.active
 * 
 * @param {string} tabId 
 * @returns {boolean}
 */
export function isTabActive(tabId) {
  const normId = normalizeTabId(tabId);
  if (typeof document !== 'undefined' && document.hidden) {
    return false;
  }

  // 1. Проверка по URL hash: строгая согласованность с адресной строкой
  if (typeof location !== 'undefined' && location.hash) {
    const hashBase = location.hash.replace(/^#/, '').split('#')[0].trim();
    if (hashBase) {
      const activeFromHash = normalizeTabId(hashBase);
      if (activeFromHash === normId) {
        return true;
      }
      const consolidatedParent = CONSOLIDATED_PARENTS[normId];
      if (consolidatedParent && consolidatedParent === activeFromHash) {
        return true;
      }
      // Если в хэше явно открыта другая вкладка, целевая вкладка гарантированно не активна
      return false;
    }
  }

  // 2. Проверка по текущему внутреннему идентификатору
  if (currentActiveTabId) {
    if (currentActiveTabId === normId) {
      return true;
    }
    const consolidatedParent = CONSOLIDATED_PARENTS[normId];
    if (consolidatedParent && currentActiveTabId === consolidatedParent) {
      return true;
    }
    return false;
  }

  // 3. Fallback по DOM-классу контейнера
  const pane = document.getElementById(normId);
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Извлекает идентификатор активной панели из URL hash (#tab_id#panel_id).
 * @param {string} [tabId] - Опциональный ID вкладки для верификации
 * @returns {string|null} Идентификатор панели или null
 */
export function getActivePanel(tabId = null) {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  const clean = hash.replace(/^#/, '');
  const parts = clean.split('#');
  if (parts.length < 2) return null;
  const currentTab = normalizeTabId(parts[0]);
  if (tabId && currentTab !== normalizeTabId(tabId)) {
    return null;
  }
  return parts[1] || null;
}

/**
 * Проверяет, активна ли панель на вкладке согласно URL hash (#tab_id#panel_id).
 * Если панель не активна в URL (или вкладка не активна) — возвращает false.
 * @param {string} tabId - Идентификатор вкладки (например, 'tab-system-control' или 'tab-user-environment')
 * @param {string} [panelId] - Идентификатор панели (например, 'event-logs' или 'panel-taskbar')
 * @param {string} [defaultPanel] - Панель по умолчанию, если в хэше указана только вкладка
 * @returns {boolean}
 */
export function isPanelActive(tabId, panelId = null, defaultPanel = null) {
  if (!isTabActive(tabId)) {
    return false;
  }
  if (!panelId) {
    return true;
  }
  const activePanel = getActivePanel(tabId);
  if (!activePanel) {
    if (defaultPanel) {
      const cleanDef = String(defaultPanel).toLowerCase().replace(/[-_]/g, '');
      const cleanTarget = String(panelId).toLowerCase().replace(/[-_]/g, '');
      return cleanDef === cleanTarget;
    }
    return true;
  }
  const cleanActive = activePanel.toLowerCase().replace(/[-_]/g, '');
  const cleanTarget = String(panelId).toLowerCase().replace(/[-_]/g, '');
  return cleanActive === cleanTarget;
}

/**
 * Устанавливает активную панель и опциональный блок в URL hash (#tab_<tab>#panel-<panel>[#block-<block>]).
 * @param {string} tabId 
 * @param {string} panelId 
 * @param {string|null} [blockId=null]
 */
export function setPanelHash(tabId, panelId, blockId = null) {
  if (!tabId || !panelId) return;
  const normTab = normalizeTabId(tabId);
  const cleanPanel = String(panelId).replace(/^#/, '');
  const normPanel = cleanPanel.startsWith('panel-') ? cleanPanel : `panel-${cleanPanel}`;
  let blockSuffix = '';
  if (blockId) {
    const cleanBlock = String(blockId).replace(/^#/, '');
    const normBlock = cleanBlock.startsWith('block-') ? cleanBlock : `block-${cleanBlock}`;
    blockSuffix = `#${normBlock}`;
  }
  const newHash = `#${normTab}#${normPanel}${blockSuffix}`;
  if (typeof location !== 'undefined' && location.hash !== newHash) {
    try {
      history.replaceState(null, null, newHash);
      document.dispatchEvent(new CustomEvent('panel:activated', { detail: { tabId: normTab, panelId: normPanel, blockId } }));
    } catch (_) {}
  }
}

/**
 * Останавливает таймер конкретного опросника.
 * @param {Object} poller 
 */
function stopPoller(poller) {
  if (poller.timerId) {
    clearInterval(poller.timerId);
    poller.timerId = null;
  }
}

/**
 * Запускает таймер опросника, если вкладка активна и опрос разрешён.
 * @param {Object} poller 
 * @param {boolean} immediate - Выполнить ли опрос немедленно перед установкой таймера
 */
function startPoller(poller, immediate = false) {
  stopPoller(poller);
  if (!poller.enabled || !isTabActive(poller.tabId)) return;

  const runTick = async () => {
    if (!poller.enabled || !isTabActive(poller.tabId) || poller.inFlight) {
      if (!isTabActive(poller.tabId)) {
        stopPoller(poller);
      }
      return;
    }
    poller.inFlight = true;
    try {
      await poller.pollFn();
    } catch (err) {
      console.warn(`[TabPoller] Ошибка выполнения pollFn для [${poller.id}]:`, err);
    } finally {
      poller.inFlight = false;
    }
  };

  if (immediate) {
    runTick();
  }

  poller.timerId = setInterval(runTick, poller.intervalMs);
}

/**
 * Регистрирует или обновляет периодический опросник (poller) для вкладки.
 * Опросник будет срабатывать ТОЛЬКО тогда, когда вкладка АКТИВНА
 * и документ находится в фокусе (не свёрнут / не скрыт).
 * 
 * @param {string} tabId - ID вкладки (например 'tab-about-system' или 'about-system')
 * @param {Function} pollFn - Функция опроса API
 * @param {number} intervalMs - Интервал опроса в миллисекундах (мин. 1000мс)
 * @param {Object} [options] - Опции: { pollerId, immediate = true, enabled = true }
 * @returns {string} pollerId
 */
export function registerTabPoller(tabId, pollFn, intervalMs = 3000, options = {}) {
  const normTabId = normalizeTabId(tabId);
  const pollerId = options.pollerId || `${normTabId}_default`;

  unregisterTabPoller(pollerId);

  const poller = {
    id: pollerId,
    tabId: normTabId,
    pollFn,
    intervalMs: Math.max(1000, intervalMs),
    enabled: options.enabled !== false,
    timerId: null,
    inFlight: false,
  };

  registeredPollers.set(pollerId, poller);

  if (isTabActive(normTabId) && poller.enabled) {
    startPoller(poller, options.immediate !== false);
  }

  return pollerId;
}

/**
 * Удаляет зарегистрированный опросник по его ID.
 * @param {string} pollerId 
 */
export function unregisterTabPoller(pollerId) {
  if (registeredPollers.has(pollerId)) {
    const poller = registeredPollers.get(pollerId);
    stopPoller(poller);
    registeredPollers.delete(pollerId);
  }
}

/**
 * Удаляет все зарегистрированные опросники для вкладки.
 * @param {string} tabId 
 */
export function unregisterAllTabPollers(tabId) {
  const normTabId = normalizeTabId(tabId);
  for (const [id, poller] of registeredPollers.entries()) {
    if (poller.tabId === normTabId) {
      stopPoller(poller);
      registeredPollers.delete(id);
    }
  }
}

/**
 * Включает или выключает опросник вкладки (например, переключатель Live-режима).
 * @param {string} pollerId 
 * @param {boolean} enabled 
 */
export function setTabPollerEnabled(pollerId, enabled) {
  const poller = registeredPollers.get(pollerId);
  if (!poller) return;
  poller.enabled = !!enabled;
  if (poller.enabled && isTabActive(poller.tabId)) {
    startPoller(poller, true);
  } else {
    stopPoller(poller);
  }
}

/**
 * Переключает активную вкладку и управляет жизненным циклом (активация/деактивация/поллеры).
 * Приоритет: кнопки навигации имеют самый высокий приоритет.
 * Если что-то запущено внутри вкладки, переключение происходит немедленно без ожидания.
 * @param {string} tabId 
 * @param {string|null} [targetSubPanelId=null] - Опциональный идентификатор суб-панели
 */
export function switchTab(tabId, targetSubPanelId = null) {
  if (!tabId) return;
  const rawClean = String(tabId).replace(/^#/, '');
  const parts = rawClean.split('#');
  const id = normalizeTabId(parts[0]);
  const subPanelId = targetSubPanelId || parts[1] || null;
  const subHash = parts.slice(1).filter(Boolean).join('#') || (targetSubPanelId || null);
  const prevTabId = currentActiveTabId;

  // 1. Остановка фонового аудио / синтеза речи при переходе
  if (prevTabId && prevTabId !== id && window.chatService?.stop) {
    try {
      window.chatService.stop();
    } catch (e) {}
  }

  // 2. Мгновенная деактивация ВСЕХ опросников, не относящихся к целевой вкладке
  for (const poller of registeredPollers.values()) {
    if (poller.tabId !== id) {
      stopPoller(poller);
    }
  }

  currentActiveTabId = id;

  // 3. МГНОВЕННОЕ обновление UI элементов в DOM (Zero-Delay)
  document.querySelectorAll('[data-tab]').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.tab === id)
  );

  document.querySelectorAll('#mainTabContent > .tab-pane').forEach(pane => {
    const isTarget = (pane.id === id);
    pane.classList.toggle('show', isTarget);
    pane.classList.toggle('active', isTarget);
  });

  // 4. Бейдж заголовка
  const badge = document.getElementById('active-tab-title-badge');
  const activeBtn = document.querySelector(`[data-tab="${id}"]`);
  if (badge && activeBtn) badge.innerHTML = activeBtn.innerHTML;

  // 5. Быстро закрыть offcanvas меню
  OFFCANVAS_IDS.forEach(ocId => {
    const el = document.getElementById(ocId);
    if (el) {
      try {
        bootstrap.Offcanvas.getInstance(el)?.hide();
      } catch (_) {}
    }
  });
  setTimeout(() => {
    document.querySelectorAll('.offcanvas-backdrop, .modal-backdrop').forEach(b => b.remove());
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.pointerEvents = '';
  }, 50);

  // 6. Обновить URL hash с сохранением суб-панели и блоков
  try {
    const targetHash = subHash ? `#${id}#${subHash}` : `#${id}`;
    history.replaceState(null, null, targetHash);
  } catch (e) {}

  // 7. Запуск опросников новой активной вкладки
  for (const poller of registeredPollers.values()) {
    if (poller.tabId === id && poller.enabled) {
      startPoller(poller, true);
    }
  }

  // 8. Неблокирующий вызов Lifecycle hooks через requestAnimationFrame / setTimeout
  const name = id.replace(/^tab-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  const prevName = prevTabId ? prevTabId.replace(/^tab-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase()) : null;

  // Деактивация предыдущей вкладки в фоне
  if (prevTabId && prevTabId !== id) {
    const deactivateFn = window[`deactivate${prevName[0].toUpperCase() + prevName.slice(1)}Tab`];
    if (typeof deactivateFn === 'function') {
      setTimeout(() => {
        try { deactivateFn(); } catch (err) { console.debug('deactivate hook error:', err); }
      }, 0);
    }
    document.dispatchEvent(new CustomEvent('tab:deactivated', { detail: { tabId: prevTabId, name: prevName } }));
  }

  // Активация новой вкладки в следующем фрейме анимации
  requestAnimationFrame(() => {
    try {
      window[`init${name[0].toUpperCase() + name.slice(1)}Tab`]?.();
    } catch (err) { console.debug('init tab hook error:', err); }
    
    try {
      window[`activate${name[0].toUpperCase() + name.slice(1)}Tab`]?.();
    } catch (err) { console.debug('activate tab hook error:', err); }

    const effectiveSubPanel = typeof subPanelId !== 'undefined' ? subPanelId : null;

    if (effectiveSubPanel && id === 'tab-processes-load-inspector' && typeof window.switchProcessesSubTab === 'function') {
      try {
        window.switchProcessesSubTab(effectiveSubPanel, false);
      } catch (err) {
        console.debug('switchProcessesSubTab error:', err);
      }
    } else if (effectiveSubPanel && id === 'tab-system-control' && typeof window.switchSystemControlSource === 'function') {
      try {
        window.switchSystemControlSource(effectiveSubPanel);
      } catch (err) {
        console.debug('switchSystemControlSource error:', err);
      }
    } else if (effectiveSubPanel && (id === 'tab-software-monitor' || id === 'tab-software-scanner') && typeof window.switchSoftwareSubTab === 'function') {
      try {
        const blockId = parts.find((p) => p.startsWith('block-')) || null;
        window.switchSoftwareSubTab(effectiveSubPanel, blockId, false);
      } catch (err) {
        console.debug('switchSoftwareSubTab error:', err);
      }
    } else if (effectiveSubPanel && (id === 'tab-defender-firewall' || id === 'tab-defender') && typeof window.switchDefenderSubTab === 'function') {
      try {
        window.switchDefenderSubTab(effectiveSubPanel, false);
      } catch (err) {
        console.debug('switchDefenderSubTab error:', err);
      }
    } else if (effectiveSubPanel && (id === 'tab-user-environment' || id === 'tab-user-enviroment') && typeof window.switchUserEnvSubTab === 'function') {
      try {
        window.switchUserEnvSubTab(effectiveSubPanel, false);
      } catch (err) {
        console.debug('switchUserEnvSubTab error:', err);
      }
    }

    const targetPane = document.getElementById(id);
    if (targetPane && typeof window.initPanels === 'function') {
      window.initPanels(targetPane);
    }
    
    document.dispatchEvent(new CustomEvent('tab:activated', { detail: { tabId: id, name, subPanelId: effectiveSubPanel } }));
  });
}

/**
 * Загружает разметку и скрипт вкладки по требованию (Lazy Load).
 * @param {string} tabName 
 * @param {string} htmlUrl 
 * @param {string} jsUrl 
 */
export async function loadTab(tabName, htmlUrl, jsUrl) {
  let container = document.getElementById(`tab-${tabName}`);
  if (!container) {
    const mainContent = document.getElementById('mainTabContent');
    if (mainContent) {
      container = document.createElement('div');
      container.id = `tab-${tabName}`;
      container.className = 'tab-pane fade';
      mainContent.appendChild(container);
    } else {
      return;
    }
  }
  
  // Показываем мгновенный скелетон/спиннер, если контейнер еще пуст
  if (!container.innerHTML.trim()) {
    container.innerHTML = `
      <div class="d-flex flex-column align-items-center justify-content-center py-5 text-muted" style="min-height: 200px;">
        <div class="spinner-border text-primary mb-2" role="status" style="width: 2rem; height: 2rem;"></div>
        <span class="small fw-medium">Загрузка раздела...</span>
      </div>
    `;
  }

  try {
    let r;
    try {
      r = await fetch(htmlUrl);
    } catch (netErr) {
      // Краткий сетевой сбой (сервер перезапускается или стартует) - даем шанс повторить через 1 с
      await new Promise(resolve => setTimeout(resolve, 1000));
      r = await fetch(htmlUrl);
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    container.innerHTML = await r.text();
    if (jsUrl) {
      await new Promise(resolve => {
        const s = document.createElement('script');
        s.type = 'module';
        s.src = jsUrl;
        s.onload = resolve;
        s.onerror = (err) => {
          console.warn(`[TabCore] Ошибка загрузки скрипта ${jsUrl}:`, err);
          resolve();
        };
        document.body.appendChild(s);
      });
    }
    const name = tabName.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    const initName = `init${name[0].toUpperCase() + name.slice(1)}Tab`;
    if (typeof window[initName] === 'function') {
      try {
        window[initName]();
      } catch (err) {
        console.debug(`[TabCore] Ошибка вызова ${initName}:`, err);
      }
    }
    if (typeof window.initPanels === 'function' && tabName !== 'about-system' && tabName !== 'about_system' && container?.id !== 'tab-about-system') {
      window.initPanels(container);
    }
    if (typeof window.initAllTableResizers === 'function') {
      window.initAllTableResizers(container);
    }
  } catch (e) {
    const safeName = String(tabName).replace(/[^a-zA-Z0-9_-]/g, '');
    container.innerHTML = `
      <div class="alert alert-danger m-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div>
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          <span>Ошибка загрузки <strong>${safeName}</strong>: ${e.message}</span>
        </div>
        <button class="btn btn-sm btn-outline-danger" type="button" onclick="window.switchTab ? window.switchTab('tab-${safeName}') : null">
          <i class="bi bi-arrow-clockwise me-1"></i> Повторить попытку
        </button>
      </div>
    `;
    throw e;
  }
}

/**
 * Устанавливает единый слушатель кликов по элементам с data-tab.
 */
export function setupTabClicks() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('button[data-tab], a[data-tab]');
    if (btn && btn.dataset.tab) {
      // Игнорируем кнопки открытия модальных окон или внутренние суб-панели
      if (
        btn.hasAttribute('data-bs-toggle') ||
        btn.hasAttribute('data-reg-tab') ||
        btn.classList.contains('btn-open-reg-tab') ||
        btn.closest('.modal') ||
        btn.dataset.tab.startsWith('pane-')
      ) {
        return;
      }
      e.preventDefault();
      // Мгновенная очистка оверлеев и снятие блокировок body
      document.querySelectorAll('.offcanvas-backdrop, .modal-backdrop').forEach(b => b.remove());
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.pointerEvents = '';

      if (typeof window.switchAppTab === 'function') {
        window.switchAppTab(btn.dataset.tab);
      } else if (typeof window.switchTab === 'function') {
        window.switchTab(btn.dataset.tab);
      } else {
        switchTab(btn.dataset.tab);
      }
    }
  }, true);
}

// Слушатель изменения видимости вкладки браузера
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      // Страница скрыта: останавливаем все активные опросники
      for (const poller of registeredPollers.values()) {
        stopPoller(poller);
      }
    } else {
      // Страница снова видна: возобновляем опросники ТОЛЬКО для активной вкладки
      if (currentActiveTabId) {
        for (const poller of registeredPollers.values()) {
          if (poller.tabId === currentActiveTabId && poller.enabled) {
            startPoller(poller, true);
          }
        }
      }
    }
  });
}

/**
 * Устанавливает флаг processing для вкладки (используется при длительных операциях).
 * Позволяет переключать вкладки без ожидания завершения операции.
 * @param {string} tabId - ID вкладки
 * @param {boolean} isProcessing - флаг состояния
 */
export function setTabProcessing(tabId, isProcessing) {
  const normId = normalizeTabId(tabId);
  processingFlags.set(normId, !!isProcessing);
}

/**
 * Сбрасывает флаг processing для вкладки.
 * @param {string} tabId - ID вкладки
 */
export function resetTabProcessing(tabId) {
  const normId = normalizeTabId(tabId);
  processingFlags.delete(normId);
}

/**
 * Возвращает ID текущей активной вкладки.
 * @returns {string|null}
 */
export function getCurrentActiveTabId() {
  return currentActiveTabId;
}

/**
 * Экспорт в глобальный контекст window для совместимости с инлайн-скриптами и вкладками
 */
if (typeof window !== 'undefined') {
  window.switchTab = switchTab;
  window.switchToTab = switchTab;
  window.loadTab = loadTab;
  window.setupTabClicks = setupTabClicks;
  window.normalizeTabId = normalizeTabId;
  window.isTabActive = isTabActive;
  window.getActivePanel = getActivePanel;
  window.isPanelActive = isPanelActive;
  window.setPanelHash = setPanelHash;
  window.getCurrentActiveTabId = getCurrentActiveTabId;
  window.registerTabPoller = registerTabPoller;
  window.unregisterTabPoller = unregisterTabPoller;
  window.unregisterAllTabPollers = unregisterAllTabPollers;
  window.setTabPollerEnabled = setTabPollerEnabled;
  window.setTabProcessing = setTabProcessing;
  window.resetTabProcessing = resetTabProcessing;
}
