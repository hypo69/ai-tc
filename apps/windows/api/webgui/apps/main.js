/**
 * =============================================================================
 * Process Name: Windows Apps - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/apps/main.js?v=20261001_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/apps
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:03:00
 * =============================================================================
 */

/**
 * apps/main.js — оркестратор страницы /tc (tc.ps1)
 * Архитектура: UI_ARCHITECTURE.md
 */

import { setupGlobalApi, setupThemeAndLang } from './modules/init-interface.js';
import { fetchAppsStatus, updateModelBadge } from './modules/status-manager.js';
import { initModelTester, sendModelPing } from './modules/model-tester.js';
import { APP_TAB_DEFS } from './modules/tabs-config.js?v=20261101_v1';
import { applyTranslations } from '../js/i18n.js';
import { switchTab, loadTab, setupTabClicks } from '../js/tab-core.js?v=20261031_v4';
import { loadPanelData, initPanels } from '../js/panel-loader.js';

// Глобальный экспорт
window.switchTab = switchTab;
window.switchToTab = switchTab;
window.sendModelPing = sendModelPing;
window.initModelTester = initModelTester;
window.loadPanelData = loadPanelData;
window.initPanels = initPanels;

// Карта: tabId → пути (из tabs-config, не генерируем)
const TAB_PATHS = Object.fromEntries(
  APP_TAB_DEFS.map(d => [d.tabId, { html: d.html, js: d.js }])
);

// Lazy-загрузка: вкладка грузится только при первом открытии
const loadedTabs = new Set();

async function lazyLoad(tabId) {
  const normId = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;
  if (loadedTabs.has(normId)) return;
  const paths = TAB_PATHS[normId];
  if (!paths) return;
  const v = Date.now();
  const name = normId.replace(/^tab-/, '');
  const cleanHtml = paths.html ? (paths.html.includes('?') ? paths.html.split('?')[0] : paths.html) : '';
  const cleanJs = paths.js ? (paths.js.includes('?') ? paths.js.split('?')[0] : paths.js) : '';
  try {
    await loadTab(name, `${cleanHtml}?v=${v}`, cleanJs ? `${cleanJs}?v=${v}` : '');
    loadedTabs.add(normId);
    applyTranslations();
    const pane = document.getElementById(normId);
    if (pane && normId !== 'tab-about-system') {
      initPanels(pane);
    }
  } catch (err) {
    console.error(`[apps/main.js] Ошибка загрузки вкладки ${normId}:`, err);
    loadedTabs.delete(normId);
    if (window.toast) {
      window.toast.error('Ошибка загрузки', `Не удалось загрузить раздел ${name}: ${err.message}`);
    }
  }
}

const _switchTab = switchTab;
export async function switchAppTab(tabId) {
  if (!tabId) return;

  const rawClean = String(tabId).replace(/^#/, '');
  const parts = rawClean.split('#');
  const baseTab = parts[0];
  let subPanel = parts[1] || null;
  const blockId = parts.find(p => p.startsWith('block-')) || null;
  const extraParts = parts.slice(2).filter(Boolean);
  tabId = baseTab;

  // Редирект Брандмауэр -> Defender (суб-панель Firewall)
  if (tabId === 'tab-firewall-manager' || tabId === 'firewall-manager') {
    tabId = 'tab-defender-firewall';
    subPanel = subPanel || 'firewall';
    setTimeout(() => {
      if (typeof window.switchDefenderSubTab === 'function') {
        window.switchDefenderSubTab('firewall');
      } else {
        const btn = document.getElementById('subtab-firewall-btn');
        if (btn && window.bootstrap?.Tab) {
          try {
            new window.bootstrap.Tab(btn).show();
          } catch (_) {}
        }
      }
    }, 70);
  } else if (tabId === 'tab-defender' || tabId === 'defender') {
    tabId = 'tab-defender-firewall';
  } else if (tabId === 'tab-windows-backup' || tabId === 'windows-backup' || tabId === 'tab-accounts-identity' || tabId === 'accounts-identity') {
    tabId = 'tab-windows-admin';
  } else if (tabId === 'tab-security-acl' || tabId === 'security-acl') {
    tabId = 'tab-windows-admin';
    setTimeout(() => {
      if (typeof window.switchWindowsAdminSubTab === 'function') {
        window.switchWindowsAdminSubTab('acl');
      } else {
        const btn = document.getElementById('subtab-winadmin-acl-btn');
        if (btn && window.bootstrap?.Tab) {
          try {
            new window.bootstrap.Tab(btn).show();
          } catch (_) {}
        }
      }
    }, 70);
  } else if (tabId === 'tab-software-monitor' || tabId === 'software-monitor' || tabId === 'tab-software-scanner' || tabId === 'software-scanner') {
    tabId = 'tab-software-monitor';
  } else if (tabId === 'tab-software-audit' || tabId === 'software-audit') {
    tabId = 'tab-software-monitor';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('inventory');
      }
    }, 70);
  } else if (tabId === 'tab-software-manager' || tabId === 'software-manager') {
    tabId = 'tab-software-monitor';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('packages');
      }
    }, 70);
  } else if (tabId === 'tab-ninite-updater' || tabId === 'ninite-updater') {
    tabId = 'tab-software-monitor';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('ninite');
      }
    }, 70);
  } else if (tabId === 'tab-startup-auditor' || tabId === 'startup-auditor' || tabId === 'windows_startup_auditor') {
    tabId = 'tab-software-monitor';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('startup');
      }
    }, 70);
  } else if (tabId === 'tab-software-transparency' || tabId === 'software-transparency' || tabId === 'tab-software-transparency-scanner' || tabId === 'software_transparency_scanner') {
    tabId = 'tab-software-monitor';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('transparency');
      }
    }, 70);
  } else if (tabId === 'tab-storage-wear' || tabId === 'storage-wear') {
    tabId = 'tab-storage-management';
    setTimeout(() => {
      if (typeof window.switchStorageSubTab === 'function') {
        window.switchStorageSubTab('wear');
      }
    }, 70);
  } else if (tabId === 'tab-storage-manager' || tabId === 'storage-manager') {
    tabId = 'tab-storage-management';
    setTimeout(() => {
      if (typeof window.switchStorageSubTab === 'function') {
        window.switchStorageSubTab('volumes');
      }
    }, 70);
  } else if (tabId === 'tab-agents' || tabId === 'agents') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('agents');
      }
    }, 70);
  } else if (tabId === 'tab-skills' || tabId === 'skills') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('skills');
      }
    }, 70);
  } else if (tabId === 'tab-mcp' || tabId === 'mcp') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('mcp');
      }
    }, 70);
  } else if (tabId === 'tab-models' || tabId === 'models') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'models';
  } else if (tabId === 'tab-telemetry-config' || tabId === 'telemetry-config' || tabId === 'tab-telemetry-control' || tabId === 'telemetry-control') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'telemetry';
  } else if (tabId === 'tab-system-logs' || tabId === 'system-logs' || tabId === 'tab-app-logs' || tabId === 'app-logs') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'logs';
  } else if (tabId === 'tab-performance-tracing' || tabId === 'performance-tracing') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'etw';
  } else if (tabId === 'tab-log-settings' || tabId === 'log-settings') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'settings';
  } else if (tabId === 'tab-wikillm' || tabId === 'wikillm' || tabId === 'tab-wikillm-settings' || tabId === 'wikillm-settings') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'wikillm-db';
  } else if (tabId === 'tab-instruments' || tabId === 'instruments' || tabId === 'tab-instruments-db' || tabId === 'instruments-db') {
    tabId = 'tab-app-internals';
    subPanel = subPanel || 'instruments';
  } else if (tabId === 'tab-process-leaks' || tabId === 'process-leaks') {
    tabId = 'tab-processes-load-inspector';
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab('leaks');
      }
    }, 70);
  } else if (tabId === 'tab-process-manager' || tabId === 'process-manager') {
    tabId = 'tab-processes-load-inspector';
    subPanel = subPanel || 'manager';
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab('manager');
      }
    }, 70);
  } else if (tabId === 'tab-user-enviroment' || tabId === 'user-enviroment') {
    tabId = 'tab-user-environment';
  }

  // Мгновенная отмена висящих сетевых запросов предыдущей вкладки (01_FRONTEND.md)
  if (window.IndexedDBCache && typeof window.IndexedDBCache.getFreshAbortSignal === 'function') {
    try {
      window.IndexedDBCache.getFreshAbortSignal();
    } catch (_) {}
  }

  const normId = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;
  await lazyLoad(normId);
  const fullSubHash = [subPanel, ...extraParts].filter(Boolean).join('#');
  _switchTab(fullSubHash ? `${normId}#${fullSubHash}` : normId);

  if (subPanel && (normId === 'tab-user-environment' || normId === 'tab-user-enviroment')) {
    setTimeout(() => {
      if (typeof window.switchUserEnvSubTab === 'function') {
        window.switchUserEnvSubTab(subPanel);
      }
    }, 70);
  } else if (subPanel && normId === 'tab-processes-load-inspector') {
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab(subPanel, false);
      }
    }, 70);
  } else if (subPanel && normId === 'tab-system-control') {
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource(subPanel);
      }
    }, 70);
  } else if (subPanel && (normId === 'tab-software-monitor' || normId === 'software-monitor' || normId === 'tab-software-scanner' || normId === 'software-scanner')) {
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab(subPanel);
      }
    }, 70);
  } else if (subPanel && (normId === 'tab-app-internals' || normId === 'app-internals')) {
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab(subPanel, blockId, false);
      }
    }, 70);
  } else if (subPanel && (normId === 'tab-defender-firewall' || normId === 'defender-firewall' || normId === 'tab-defender' || normId === 'defender')) {
    setTimeout(() => {
      if (typeof window.switchDefenderSubTab === 'function') {
        window.switchDefenderSubTab(subPanel, false);
      }
    }, 70);
  }
}
window.switchTab = switchAppTab;
window.switchToTab = switchAppTab;

// ── МЕНЮ ─────────────────────────────────────────────────────────────────────

/**
 * Словарь сопоставления эмодзи с классами Bootstrap Icons
 */
const EMOJI_TO_BI = {
  'ℹ️': 'bi-info-circle',
  'ℹ': 'bi-info-circle',
  '💬': 'bi-chat-dots',
  '🎙️': 'bi-mic',
  '🎙': 'bi-mic',
  '📋': 'bi-clipboard-check',
  '🔍': 'bi-search',
  '⏱️': 'bi-stopwatch',
  '⏱': 'bi-stopwatch',
  '⚡': 'bi-lightning-charge',
  '🗝️': 'bi-key',
  '🗝': 'bi-key',
  '🔌': 'bi-plug',
  '🌐': 'bi-globe2',
  '🚀': 'bi-rocket-takeoff',
  '📁': 'bi-folder2',
  '🧠': 'bi-cpu',
  '🖼️': 'bi-image',
  '🖼': 'bi-image',
  '💽': 'bi-hdd',
  '🤖': 'bi-robot',
  '📦': 'bi-box-seam',
  '🛠️': 'bi-tools',
  '🛠': 'bi-tools',
  '🔬': 'bi-binoculars',
  '⚙️': 'bi-gear',
  '⚙': 'bi-gear',
  '📅': 'bi-calendar3',
  '📌': 'bi-pin-angle',
  '🗂️': 'bi-archive',
  '🗂': 'bi-archive',
  '🍳': 'bi-code-square',
  '🗺️': 'bi-diagram-3',
  '🗺': 'bi-diagram-3',
  '📄': 'bi-file-earmark-text',
  '📜': 'bi-journal-text',
  '🖥️': 'bi-display',
  '🖥': 'bi-display',
  '🛡️': 'bi-shield-lock',
  '🛡': 'bi-shield-lock',
  '📰': 'bi-newspaper',
  '📚': 'bi-book',
  '🧩': 'bi-puzzle',
  '⏳': 'bi-hourglass-split'
};

/**
 * Создает DOM-элемент HTML-иконки из фреймворка Bootstrap Icons
 * @param {string} iconStr
 * @param {string} defaultIcon
 * @returns {HTMLElement}
 */
function createIconElement(iconStr, defaultIcon = 'bi-app') {
  let icon = (iconStr || defaultIcon).trim();
  if (EMOJI_TO_BI[icon]) {
    icon = EMOJI_TO_BI[icon];
  }
  if (/^bi-[a-z0-9-]+$/.test(icon) || icon.startsWith('bi-')) {
    const i = document.createElement('i');
    i.className = `bi ${icon}`;
    return i;
  }
  const i = document.createElement('i');
  i.className = 'bi bi-app';
  return i;
}

/**
 * Обработчик прямого запуска программ (например R-Studio)
 * @param {Object} item
 * @param {HTMLElement} [iconEl]
 */
async function executeLaunchItem(item, iconEl = null) {
  const origContent = iconEl ? iconEl.innerHTML : '';
  if (iconEl) iconEl.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
  try {
    const res = await fetch('/api/recovery/launch', { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.success) {
      if (window.toast) {
        window.toast.success('R-Studio запущена', data.message || 'Программа восстановления файлов запущена');
      }
    } else {
      if (window.toast) {
        window.toast.error('Ошибка запуска', data.detail || 'Не удалось запустить программу');
      }
    }
  } catch (err) {
    if (window.toast) {
      window.toast.error('Ошибка связи', err.message);
    }
  } finally {
    if (iconEl) iconEl.innerHTML = origContent;
  }
}

function getMenuTarget() {
  const p = location.pathname.toLowerCase();
  if (p.startsWith('/su') || location.search.includes('target=su')) {
    return 'su';
  }
  return 'tc';
}

async function buildMenu(appsMap = {}, customCfg = null) {
  let cfg = customCfg;
  const target = getMenuTarget();
  if (!cfg) {
    try {
      const r = await fetch(`/api/v1/menu/config?target=${target}&t=${Date.now()}`);
      if (r.ok) {
        cfg = await r.json();
      }
    } catch (e) {
      console.warn(`Не удалось загрузить /api/v1/menu/config?target=${target}, пробуем статический файл`, e);
    }
  }

  if (!cfg) {
    try {
      const staticFile = target === 'su' ? 'su_menu_config.json' : 'tc_menu_config.json';
      const r = await fetch(`/html/config_menues/${staticFile}?t=${Date.now()}`);
      if (r.ok) {
        cfg = await r.json();
      }
    } catch (e) {
      console.error('Ошибка загрузки статического файла конфигурации меню', e);
    }
  }

  if (!cfg || !cfg.menu) return null;

  const isAppEnabled = item => {
    if (!appsMap || Object.keys(appsMap).length === 0) return true;
    if (appsMap[item.id] && appsMap[item.id].enabled === false) return false;
    const tabKey = (item.tab || '').replace(/^tab-/, '').replace(/-/g, '_');
    if (appsMap[tabKey] && appsMap[tabKey].enabled === false) return false;
    return true;
  };
  const sorted = arr => [...arr]
    .filter(x => x.visible !== false && isAppEnabled(x))
    .sort((a, b) => (a.order || 0) - (b.order || 0));

  // Верхнее меню
  const topEl = document.querySelector('.main-nav-container .d-flex.gap-1.flex-wrap');
  if (topEl) {
    topEl.innerHTML = '';
    sorted(cfg.menu.topButtons || []).forEach(item => {
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-outline-primary d-flex align-items-center gap-1.5 py-1 px-2 rounded';
      btn.type = 'button';
      btn.title = item.label;

      const iconEl = createIconElement(item.icon, 'bi-app');
      const labelSpan = document.createElement('span');
      labelSpan.className = 'd-none d-sm-inline';
      labelSpan.textContent = item.label;
      if (item.i18n) labelSpan.dataset.i18n = item.i18n;

      btn.append(iconEl, labelSpan);

      if (item.id === 'file_recovery' || item.action === 'launch') {
        btn.dataset.action = 'launch';
        btn.onclick = async (e) => {
          e.preventDefault();
          e.stopPropagation();
          await executeLaunchItem(item, iconEl);
        };
      } else {
        btn.dataset.tab = item.tab;
      }

      topEl.appendChild(btn);
    });
  }

  // Боковое меню
  const navEl = document.getElementById('appsNavTabs');
  if (navEl) {
    navEl.innerHTML = '';
    sorted(cfg.menu.sidebarItems || []).forEach(item => {
      const btn = document.createElement('button');
      btn.className = 'list-group-item list-group-item-action d-flex align-items-center gap-2 py-2 px-3';
      btn.type = 'button';

      const iconEl = createIconElement(item.icon, 'bi-file-earmark-text');
      iconEl.classList.add('fs-6');
      const label = document.createElement('span');
      label.className = 'fw-medium';
      label.textContent = item.label;
      if (item.i18n) label.dataset.i18n = item.i18n;

      btn.append(iconEl, label);

      if (item.id === 'file_recovery' || item.action === 'launch') {
        btn.dataset.action = 'launch';
        btn.title = 'Запуск программы восстановления файлов (R-Studio)';
        btn.onclick = async (e) => {
          e.preventDefault();
          e.stopPropagation();
          await executeLaunchItem(item, iconEl);
        };
      } else {
        btn.dataset.tab = item.tab;
      }

      navEl.appendChild(btn);
    });
  }

  // Обновление активного состояния кнопок вкладок
  const activePane = document.querySelector('#mainTabContent > .tab-pane.active') || document.querySelector('.tab-pane.active');
  const activeTabId = activePane ? activePane.id : null;
  if (activeTabId) {
    document.querySelectorAll('[data-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === activeTabId);
    });
  }

  applyTranslations();
  return cfg;
}

export async function loadRequiredTabs(tabs = []) {
  for (const tab of tabs) {
    await lazyLoad(tab);
  }
}

// ── РЕДАКТОР МЕНЮ ─────────────────────────────────────────────────────────────

function initMenuEditor(cfg, appsMap = {}) {
  const editorBtn = document.getElementById('menu-editor-btn');
  const modal = document.getElementById('menuEditorModal');
  const list = document.getElementById('allMenuEditor');
  const saveBtn = document.getElementById('saveMenuConfig');
  if (!editorBtn || !modal || !list || !cfg) return;

  let currentItems = [];
  let draggedGlobalIdx = null;

  function collectInitialItems() {
    const seen = new Set();
    const result = [];
    const all = [
      ...(cfg.menu.topButtons || []).map(x => ({ ...x, position: x.position || (x.visible === false ? 'hidden' : 'top') })),
      ...(cfg.menu.sidebarItems || []).map(x => ({ ...x, position: x.position || (x.visible === false ? 'hidden' : 'bottom') })),
    ];
    for (const item of all) {
      const key = item.id || item.tab;
      if (key && !seen.has(key)) {
        seen.add(key);
        result.push(item);
      }
    }
    return result;
  }

  function renderList() {
    list.innerHTML = '';

    const GROUPS = [
      {
        key: 'top',
        title: 'Сверху (Верхняя панель)',
        icon: 'bi-layout-text-window-reverse',
        badgeCls: 'bg-primary text-white',
        borderCls: 'border-primary-subtle'
      },
      {
        key: 'bottom',
        title: 'Сбоку (Боковое меню)',
        icon: 'bi-layout-sidebar-inset',
        badgeCls: 'bg-info text-dark',
        borderCls: 'border-info-subtle'
      },
      {
        key: 'hidden',
        title: 'Скрыто (Не отображаются)',
        icon: 'bi-eye-slash',
        badgeCls: 'bg-secondary text-white',
        borderCls: 'border-secondary-subtle'
      }
    ];

    GROUPS.forEach(grp => {
      const groupItems = currentItems.filter(x => x.position === grp.key);
      const grpTotal = groupItems.length;

      const section = document.createElement('div');
      section.className = `menu-group-section mb-3 p-2 rounded border ${grp.borderCls}`;
      section.style.background = 'var(--surface-1, rgba(255,255,255,0.03))';

      // Заголовок группы
      const header = document.createElement('div');
      header.className = 'd-flex align-items-center justify-content-between mb-2 px-1 pb-1 border-bottom border-secondary-subtle';
      header.innerHTML = `
        <span class="fw-bold d-flex align-items-center gap-2 small">
          <i class="bi ${grp.icon}"></i> ${grp.title}
        </span>
        <span class="badge ${grp.badgeCls} rounded-pill px-2 py-1">${grpTotal}</span>
      `;
      section.appendChild(header);

      const itemsContainer = document.createElement('div');
      itemsContainer.className = 'menu-group-items d-flex flex-column gap-2';
      itemsContainer.dataset.group = grp.key;

      if (grpTotal === 0) {
        const empty = document.createElement('div');
        empty.className = 'text-muted small text-center py-2 fst-italic';
        empty.textContent = 'Нет элементов в этой группе';
        itemsContainer.appendChild(empty);
      } else {
        groupItems.forEach((item, grpIdx) => {
          const globalIdx = currentItems.indexOf(item);
          const safeId = (item.id || `item_${globalIdx}`).replace(/[^a-zA-Z0-9_-]/g, '');

          const div = document.createElement('div');
          div.className = 'menu-editor-item d-flex align-items-center gap-2 p-2 rounded border border-secondary-subtle';
          div.dataset.id = item.id || `item_${globalIdx}`;
          div.dataset.globalIndex = globalIdx;
          div.dataset.groupIndex = grpIdx;
          div.draggable = true;

          // 1. Ручка перетаскивания (Drag Handle)
          const dragHandle = document.createElement('div');
          dragHandle.className = 'drag-handle-container text-muted px-1';
          dragHandle.title = 'Перетащите для изменения порядка';
          dragHandle.style.cursor = 'grab';
          dragHandle.innerHTML = '<i class="bi bi-grip-vertical fs-5"></i>';

          // 2. Порядковый номер в группе
          const orderBadge = document.createElement('span');
          orderBadge.className = 'badge bg-secondary-subtle text-light border px-2 py-1';
          orderBadge.textContent = `#${grpIdx + 1}`;
          orderBadge.style.minWidth = '38px';
          orderBadge.style.textAlign = 'center';

          // 3. Иконка элемента
          const iconContainer = document.createElement('div');
          iconContainer.className = 'item-icon d-flex align-items-center justify-content-center px-1 text-center';
          iconContainer.style.minWidth = '28px';
          const iconEl = createIconElement(item.icon, 'bi-file-earmark-text');
          iconContainer.appendChild(iconEl);

          // 4. Информация об элементе
          const info = document.createElement('div');
          info.className = 'item-info flex-grow-1 min-w-0 px-1';
          const labelDiv = document.createElement('div');
          labelDiv.className = 'fw-semibold text-truncate small';
          labelDiv.textContent = item.label;
          const tabDiv = document.createElement('div');
          tabDiv.className = 'text-muted text-truncate font-monospace';
          tabDiv.style.fontSize = '0.75rem';
          tabDiv.textContent = item.tab;
          info.append(labelDiv, tabDiv);

          // 5. Управление порядком внутри группы
          const orderCtrl = document.createElement('div');
          orderCtrl.className = 'd-flex align-items-center gap-1 me-2';
          orderCtrl.style.width = '160px';
          orderCtrl.style.flexShrink = '0';

          const btnUp = document.createElement('button');
          btnUp.type = 'button';
          btnUp.className = 'btn btn-sm btn-outline-secondary p-0 px-1';
          btnUp.title = 'Переместить выше в группе';
          btnUp.disabled = grpIdx === 0;
          btnUp.innerHTML = '<i class="bi bi-chevron-up"></i>';
          btnUp.addEventListener('click', () => {
            if (grpIdx > 0) {
              const prevItem = groupItems[grpIdx - 1];
              const curIdx = currentItems.indexOf(item);
              const targetIdx = currentItems.indexOf(prevItem);
              currentItems.splice(curIdx, 1);
              currentItems.splice(targetIdx, 0, item);
              renderList();
            }
          });

          const slider = document.createElement('input');
          slider.type = 'range';
          slider.className = 'form-range order-slider flex-grow-1 m-0';
          slider.min = '1';
          slider.max = String(grpTotal);
          slider.value = String(grpIdx + 1);
          slider.title = `Позиция в группе: ${grpIdx + 1} из ${grpTotal}`;

          slider.addEventListener('input', (e) => {
            const targetGrpIdx = parseInt(e.target.value, 10) - 1;
            if (targetGrpIdx !== grpIdx && targetGrpIdx >= 0 && targetGrpIdx < grpTotal) {
              const targetItem = groupItems[targetGrpIdx];
              const curIdx = currentItems.indexOf(item);
              const targetIdx = currentItems.indexOf(targetItem);
              currentItems.splice(curIdx, 1);
              currentItems.splice(targetIdx, 0, item);
              renderList();
            }
          });

          const btnDown = document.createElement('button');
          btnDown.type = 'button';
          btnDown.className = 'btn btn-sm btn-outline-secondary p-0 px-1';
          btnDown.title = 'Переместить ниже в группе';
          btnDown.disabled = grpIdx === grpTotal - 1;
          btnDown.innerHTML = '<i class="bi bi-chevron-down"></i>';
          btnDown.addEventListener('click', () => {
            if (grpIdx < grpTotal - 1) {
              const nextItem = groupItems[grpIdx + 1];
              const curIdx = currentItems.indexOf(item);
              const targetIdx = currentItems.indexOf(nextItem);
              currentItems.splice(curIdx, 1);
              currentItems.splice(targetIdx, 0, item);
              renderList();
            }
          });

          orderCtrl.append(btnUp, slider, btnDown);

          // 6. Переключатели позиции (Сверху / Сбоку / Скрыть)
          const group = document.createElement('div');
          group.className = 'btn-group btn-group-sm flex-shrink-0';
          group.setAttribute('role', 'group');

          const radioName = `pos_grp_${globalIdx}_${safeId}`;
          [
            ['top', 'Сверху', 'btn-outline-primary'],
            ['bottom', 'Сбоку', 'btn-outline-info'],
            ['hidden', 'Скрыть', 'btn-outline-danger']
          ].forEach(([val, text, cls]) => {
            const inp = document.createElement('input');
            inp.type = 'radio';
            inp.className = 'btn-check';
            inp.autocomplete = 'off';
            inp.name = radioName;
            inp.id = `pos_${val}_${globalIdx}_${safeId}`;
            inp.value = val;
            inp.checked = (item.position === val);
            inp.addEventListener('change', () => {
              if (inp.checked && item.position !== val) {
                item.position = val;
                item.visible = (val !== 'hidden');
                // Перемещаем элемент в конец новой группы в currentItems
                const curIdx = currentItems.indexOf(item);
                currentItems.splice(curIdx, 1);
                const lastOfGroup = currentItems.filter(x => x.position === val).pop();
                if (lastOfGroup) {
                  const lastIdx = currentItems.indexOf(lastOfGroup);
                  currentItems.splice(lastIdx + 1, 0, item);
                } else {
                  currentItems.push(item);
                }
                renderList();
              }
            });

            const lbl = document.createElement('label');
            lbl.className = `btn ${cls}`;
            lbl.setAttribute('for', inp.id);
            lbl.textContent = text;
            group.append(inp, lbl);
          });

          // Drag & Drop события
          div.addEventListener('dragstart', (e) => {
            draggedGlobalIdx = globalIdx;
            div.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', String(globalIdx));
          });

          div.addEventListener('dragend', () => {
            div.classList.remove('dragging');
            document.querySelectorAll('.menu-editor-item').forEach(el => el.classList.remove('drag-over'));
          });

          div.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            div.classList.add('drag-over');
          });

          div.addEventListener('dragleave', () => {
            div.classList.remove('drag-over');
          });

          div.addEventListener('drop', (e) => {
            e.preventDefault();
            div.classList.remove('drag-over');
            const fromGlobalIdx = parseInt(e.dataTransfer.getData('text/plain'), 10);
            if (!isNaN(fromGlobalIdx) && fromGlobalIdx !== globalIdx) {
              const [moved] = currentItems.splice(fromGlobalIdx, 1);
              moved.position = grp.key;
              moved.visible = (grp.key !== 'hidden');
              currentItems.splice(globalIdx, 0, moved);
              renderList();
            }
          });

          div.append(dragHandle, orderBadge, iconContainer, info, orderCtrl, group);
          itemsContainer.appendChild(div);
        });
      }

      section.appendChild(itemsContainer);
      list.appendChild(section);
    });

    return currentItems;
  }

  editorBtn.addEventListener('click', () => {
    currentItems = collectInitialItems();
    renderList();
    new bootstrap.Modal(modal).show();
  });

  saveBtn.addEventListener('click', async () => {
    cfg.menu.topButtons = currentItems
      .filter(x => x.position === 'top')
      .map(({ position, ...x }, idx) => ({ ...x, visible: true, order: idx + 1 }));

    cfg.menu.sidebarItems = currentItems
      .filter(x => x.position !== 'top')
      .map(({ position, ...x }, idx) => ({ ...x, visible: position === 'bottom', order: idx + 1 }));

    try {
      const target = getMenuTarget();
      const r = await fetch(`/api/v1/menu/config?target=${target}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg)
      });

      if (!r.ok) {
        throw new Error(r.statusText || `HTTP ${r.status}`);
      }

      // Немедленно переопределяем меню и структуру вкладок в интерфейсе
      await buildMenu(appsMap, cfg);

      const modalInstance = bootstrap.Modal.getInstance(modal);
      if (modalInstance) {
        modalInstance.hide();
      }

      // Проверяем, активна ли ещё текущая вкладка, если нет — переключаемся на первую доступную
      const currentTabEl = document.querySelector('#mainTabContent > .tab-pane.active') || document.querySelector('.tab-pane.active');
      const activeTabId = currentTabEl ? currentTabEl.id : '';
      const isStillInMenu = document.querySelector(`[data-tab="${activeTabId}"]`);
      if (!isStillInMenu) {
        const firstVisible = document.querySelector('[data-tab]');
        if (firstVisible?.dataset.tab) {
          await switchAppTab(firstVisible.dataset.tab);
        }
      }
    } catch (e) {
      window.showToast?.('Ошибка при сохранении меню: ' + e.message, 'danger') || alert('Ошибка при сохранении меню: ' + e.message);
    }
  });
}

// ── INIT ─────────────────────────────────────────────────────────────────────

async function init() {
  setupGlobalApi();
  await setupThemeAndLang();

  if (location.pathname.startsWith('/tc'))
    document.title = 'AI Windows Admin — Test Computer (/tc)';

  // Единый обработчик кликов
  setupTabClicks();

  // Статус + бейдж модели
  const statusData = await fetchAppsStatus();
  await updateModelBadge(statusData);
  const appsMap = statusData?.apps || {};

  // Инициализация быстрой проверки доступности модели
  initModelTester();

  // Меню из конфига
  const cfg = await buildMenu(appsMap).catch(() => null);
  initMenuEditor(cfg, appsMap);

  applyTranslations();

  // Вкладка tab-about-system загружается первой, если хэш не задан
  const hash = location.hash.replace(/^#/, '');
  if (!hash) {
    await switchAppTab('tab-about-system');
    location.hash = 'tab-about-system';
  } else {
    await switchAppTab(hash);
  }

  window.addEventListener('hashchange', async () => {
    const h = location.hash.replace(/^#/, '');
    if (h) {
      await switchAppTab(h);
    }
  });
}

document.readyState === 'loading'
  ? document.addEventListener('DOMContentLoaded', init)
  : init();
