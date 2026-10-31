/**
 * =============================================================================
 * Process Name: Windows Software Monitor - Subtabs Navigation Panel
 * =============================================================================
 * Description:
 *   Модуль координации и ленивой подгрузки разделов хаба ПО:
 *   инвентарь, пакеты WinGet, пакеты MSI, Microsoft Store, Ninite, спящие программы,
 *   автозапуск, ИИ-аудит, ресурсоемкие процессы и сетевые сокеты
 *   с поддержкой URL-маршрутизации панелей (#tab-software-monitor#<panel_id>).
 *
 * File: panel_subtabs/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_software_monitor/panel_subtabs
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 16:42:00
 * =============================================================================
 */

import { loadSubPane } from '../common/ui_utils.js';
import { initDormantScanner, renderOrphans } from '../panel_dormant/panel.js';
import { initHeavyResourcesPanel } from '../panel_heavy/panel.js';
import { initSocketsConfigPanel } from '../panel_sockets/panel.js';
import { initStorePackagesPanel } from '../panel_store/panel.js';
import { initWingetPackagesPanel } from '../panel_winget/panel.js';
import { initMsiPackagesPanel } from '../panel_msi/panel.js';

export const TAB_ID = 'tab-software-monitor';
let _lastTriggerTab = '';
let _lastTriggerTime = 0;

/**
 * Проверяет, активна ли вкладка Software Monitor.
 * @returns {boolean}
 */
export function isSoftwareMonitorTabActive() {
  if (typeof document !== 'undefined' && document.hidden) return false;
  if (typeof window.isTabActive === 'function') {
    return Boolean(
      window.isTabActive(TAB_ID) ||
      window.isTabActive('software-monitor') ||
      window.isTabActive('tab-software-scanner') ||
      window.isTabActive('software-scanner')
    );
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('tab-software-scanner');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор субвкладки/панели к каноническому виду.
 * @param {string} rawId - Исходный идентификатор.
 * @returns {string} Канонический ID панели.
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'inventory';
  const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^subpane-sw-/, '').replace(/^subtab-sw-/, '').replace(/-btn$/, '');
  if (s.includes('invent') || s.includes('audit')) return 'inventory';
  if (s.includes('pack') || s.includes('winget') || s.includes('msi') || s.includes('store') || s.includes('ninite')) return 'packages';
  if (s.includes('orphan')) return 'orphans';
  if (s.includes('dormant') || s.includes('unused')) return 'dormant';
  if (s.includes('startup') || s.includes('autorun')) return 'startup';
  if (s.includes('transpar')) return 'transparency';
  if (s.includes('heavy') || s.includes('resource')) return 'heavy';
  if (s.includes('socket') || s.includes('port')) return 'sockets';
  return s || 'inventory';
}

/**
 * Считывает суб-панель из URL hash.
 * @returns {string|null} ID субпанели или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'software-monitor' || mainPart === 'tab-software-scanner' || mainPart === 'software-scanner') {
      return normalizeSubTabId(parts[1]);
    }
  }
  return null;
}

/**
 * Обновляет URL hash активной суб-панелью (#tab-software-monitor#<panel_id>) без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели.
 */
export function updateUrlWithPanel(panelId) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';
  const newHash = `#${TAB_ID}#${canonical}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
    } catch (_) {}
  }
}

/**
 * Инициализирует конкретную субпанель по ее названию.
 * @param {string} subtabName - Название субпанели.
 */
export async function triggerSubTabInit(subtabName) {
  const now = Date.now();
  if (_lastTriggerTab === subtabName && (now - _lastTriggerTime) < 300) {
    return;
  }
  _lastTriggerTab = subtabName;
  _lastTriggerTime = now;
  if (subtabName === 'inventory' || subtabName === 'audit') {
    await loadSubPane(
      'sw-inventory-embed-container',
      '/html/tab_software_audit/index.html',
      '/html/tab_software_audit/main.js',
      'initSoftwareAuditTab'
    );
  } else if (subtabName === 'packages' || subtabName === 'winget' || subtabName === 'manager') {
    await initWingetPackagesPanel();
  } else if (subtabName === 'msi') {
    await initMsiPackagesPanel();
  } else if (subtabName === 'store' || subtabName === 'msstore' || subtabName === 'microsoft-store') {
    await initStorePackagesPanel();
  } else if (subtabName === 'ninite') {
    await loadSubPane(
      'sw-ninite-embed-container',
      '/html/tab_ninite_updater/index.html',
      '/html/tab_ninite_updater/main.js',
      'initNiniteUpdaterTab'
    );
  } else if (subtabName === 'orphans' || subtabName === 'orphan' || subtabName === 'panel-software-scanner-orphans') {
    initDormantScanner();
    renderOrphans();
  } else if (subtabName === 'dormant') {
    initDormantScanner();
  } else if (subtabName === 'startup' || subtabName === 'startup-auditor' || subtabName === 'startup_auditor') {
    await loadSubPane(
      'sw-startup-embed-container',
      '/html/tab_startup_auditor/index.html',
      '/html/tab_startup_auditor/main.js',
      'initStartupAuditorTab'
    );
  } else if (subtabName === 'transparency') {
    await loadSubPane(
      'sw-transparency-embed-container',
      '/html/tab_software_transparency/index.html',
      '/html/tab_software_transparency/main.js',
      'initSoftwareTransparencyTab'
    );
  } else if (subtabName === 'heavy' || subtabName === 'resources') {
    initHeavyResourcesPanel();
  } else if (subtabName === 'sockets' || subtabName === 'ports') {
    initSocketsConfigPanel();
  }

  // Реинициализация тултипов при подгрузке содержимого субвкладок
  if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    setTimeout(() => {
      const rootEl = document.getElementById('software-monitor-container') ||
                     document.getElementById('software-scanner-container') ||
                     document;
      window.AISmartTooltip.initAll(rootEl);
    }, 120);
  }
}

/**
 * Программное переключение между субвкладками хаба с обновлением URL.
 * @param {string} subtabName - Имя целевой субпанели.
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchSoftwareSubTab(subtabName, updateUrl = true) {
  const canonical = normalizeSubTabId(subtabName);
  let btnId = 'subtab-sw-inventory-btn';
  if (canonical === 'packages') {
    btnId = 'subtab-sw-packages-btn';
  } else if (canonical === 'orphans') {
    btnId = 'subtab-sw-orphans-btn';
  } else if (canonical === 'dormant') {
    btnId = 'subtab-sw-dormant-btn';
  } else if (canonical === 'startup') {
    btnId = 'subtab-sw-startup-btn';
  } else if (canonical === 'transparency') {
    btnId = 'subtab-sw-transparency-btn';
  } else if (canonical === 'heavy') {
    btnId = 'subtab-sw-heavy-btn';
  } else if (canonical === 'sockets') {
    btnId = 'subtab-sw-sockets-btn';
  }

  const btn = document.getElementById(btnId);
  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      new window.bootstrap.Tab(btn).show();
    } else {
      btn.click();
    }
  }

  if (updateUrl) {
    updateUrlWithPanel(canonical);
  }

  // Обработка внутренних вкладок Ninite / WinGet / MSI / Store
  if (subtabName === 'msi') {
    setTimeout(() => {
      const msiBtn = document.getElementById('sw-subtab-msi-btn');
      if (msiBtn) {
        if (window.bootstrap && window.bootstrap.Tab) {
          new window.bootstrap.Tab(msiBtn).show();
        } else {
          msiBtn.click();
        }
      }
      initMsiPackagesPanel();
    }, 50);
  } else if (subtabName === 'store' || subtabName === 'msstore') {
    setTimeout(() => {
      const storeBtn = document.getElementById('sw-subtab-store-btn');
      if (storeBtn) {
        if (window.bootstrap && window.bootstrap.Tab) {
          new window.bootstrap.Tab(storeBtn).show();
        } else {
          storeBtn.click();
        }
      }
      initStorePackagesPanel();
    }, 50);
  } else if (subtabName === 'ninite') {
    setTimeout(() => {
      const niniteBtn = document.getElementById('sw-subtab-ninite-btn');
      if (niniteBtn) {
        if (window.bootstrap && window.bootstrap.Tab) {
          new window.bootstrap.Tab(niniteBtn).show();
        } else {
          niniteBtn.click();
        }
      }
      triggerSubTabInit('ninite');
    }, 50);
  } else if (subtabName === 'packages' || subtabName === 'winget') {
    setTimeout(() => {
      const wingetBtn = document.getElementById('sw-subtab-winget-btn');
      if (wingetBtn) {
        if (window.bootstrap && window.bootstrap.Tab) {
          new window.bootstrap.Tab(wingetBtn).show();
        } else {
          wingetBtn.click();
        }
      }
      initWingetPackagesPanel();
    }, 50);
  }

  triggerSubTabInit(subtabName);
}

/**
 * Настройка обработчиков переключения субвкладок.
 */
export function setupSubTabNavigation() {
  const bindTabBtn = (btnId, name) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('shown.bs.tab', () => {
      updateUrlWithPanel(name);
      triggerSubTabInit(name);
    });
    btn.addEventListener('click', () => {
      updateUrlWithPanel(name);
      if (!window.bootstrap || !window.bootstrap.Tab) {
        triggerSubTabInit(name);
      }
    });
  };

  bindTabBtn('subtab-sw-inventory-btn', 'inventory');
  bindTabBtn('subtab-sw-packages-btn', 'packages');
  bindTabBtn('subtab-sw-dormant-btn', 'dormant');
  bindTabBtn('subtab-sw-orphans-btn', 'orphans');
  bindTabBtn('subtab-sw-startup-btn', 'startup');
  bindTabBtn('subtab-sw-transparency-btn', 'transparency');
  bindTabBtn('subtab-sw-heavy-btn', 'heavy');
  bindTabBtn('subtab-sw-sockets-btn', 'sockets');

  bindTabBtn('sw-subtab-winget-btn', 'winget');
  bindTabBtn('sw-subtab-msi-btn', 'msi');
  bindTabBtn('sw-subtab-store-btn', 'store');
  bindTabBtn('sw-subtab-ninite-btn', 'ninite');
}
