/**
 * =============================================================================
 * Process Name: Windows Software Monitor - Subtabs Navigation Panel
 * =============================================================================
 * Description:
 *   Модуль координации и ленивой подгрузки разделов хаба ПО:
 *   инвентарь, менеджер пакетов (WinGet, MSI, Store, Ninite), спящие программы,
 *   автозапуск, ИИ-аудит, ресурсоемкие процессы и сетевые сокеты
 *   с поддержкой двухуровневой URL-маршрутизации:
 *   - Панели Уровня 1: #tab-software-monitor#panel-<panel_id>
 *   - Блоки Уровня 2: #tab-software-monitor#panel-packages#block-<block_id>
 *
 * File: panel_subtabs/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_software_monitor/panel_subtabs
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:25:00
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
 * @returns {string} Канонический ID панели ('inventory', 'packages', 'dormant', etc.).
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'inventory';
  const s = String(rawId)
    .toLowerCase()
    .trim()
    .replace(/^#/, '')
    .replace(/^panel-/, '')
    .replace(/^subpane-sw-/, '')
    .replace(/^subtab-sw-/, '')
    .replace(/-btn$/, '');

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
 * Нормализует идентификатор блока внутри панели пакетов.
 * @param {string} rawBlockId
 * @param {string} [panelId='packages']
 * @returns {string} Канонический ID блока ('block-winget', 'block-msi', 'block-store', 'block-ninite').
 */
export function normalizeBlockId(rawBlockId, panelId = 'packages') {
  if (!rawBlockId) {
    return 'block-winget';
  }
  const s = String(rawBlockId)
    .toLowerCase()
    .trim()
    .replace(/^#/, '')
    .replace(/^block-/, '')
    .replace(/^sw-subtab-/, '')
    .replace(/^sw-subpane-/, '')
    .replace(/-btn$/, '');

  if (s.includes('ninite')) return 'block-ninite';
  if (s.includes('msi')) return 'block-msi';
  if (s.includes('store') || s.includes('appx') || s.includes('msix')) return 'block-store';
  if (s.includes('winget') || s.includes('pack')) return 'block-winget';
  return `block-${s}`;
}

/**
 * Возвращает идентификатор активного блока в панели пакетов.
 * @param {string} [panelId='packages']
 * @returns {string}
 */
export function getActiveBlockId(panelId = 'packages') {
  const activeBtn = document.querySelector('#sw-packages-subtabs button.active');
  if (activeBtn) {
    const bId = activeBtn.getAttribute('data-block-id') || activeBtn.id;
    if (bId) return normalizeBlockId(bId, panelId);
  }
  return 'block-winget';
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
      const p1 = parts[1];
      if (p1.startsWith('block-')) {
        return 'packages';
      }
      return normalizeSubTabId(p1);
    }
  }
  return null;
}

/**
 * Извлекает блок подменю (block-<id>) из URL hash.
 * @param {string} [panelId='packages'] - Канонический ID панели
 * @returns {string|null} ID блока или null
 */
export function getBlockFromHash(panelId = 'packages') {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');

  // 1. Поиск прямого сегмента block-*
  const blockPart = parts.find((p) => p.startsWith('block-'));
  if (blockPart) {
    return normalizeBlockId(blockPart, panelId);
  }

  // 2. Проверка алиасов в URL хеше (например #tab-software-monitor#packages#ninite или #tab-software-monitor#panel-packages#ninite)
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i].toLowerCase().trim().replace(/^panel-/, '');
    if (part === 'ninite' || part === 'msi' || part === 'store' || part === 'winget') {
      return normalizeBlockId(part, panelId);
    }
  }

  return null;
}

/**
 * Обновляет URL hash активной суб-панелью и блоком (#tab-software-monitor#panel-<panel_id>[#block-<block_id>]) без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели.
 * @param {string|null} [blockId=null] - Идентификатор блока подменю.
 */
export function updateUrlWithPanel(panelId, blockId = null) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';

  let blockSuffix = '';
  if (canonical === 'packages') {
    const effectiveBlock = blockId ? normalizeBlockId(blockId, canonical) : getActiveBlockId(canonical);
    if (effectiveBlock) {
      blockSuffix = `#${effectiveBlock}`;
    }
  }

  const newHash = `#${TAB_ID}#panel-${canonical}${blockSuffix}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
    } catch (_) {}
  }
}

/**
 * Инициализирует конкретную субпанель по ее названию.
 * @param {string} subtabName - Название субпанели или блока.
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
  } else if (subtabName === 'packages' || subtabName === 'winget' || subtabName === 'manager' || subtabName === 'block-winget') {
    await initWingetPackagesPanel();
  } else if (subtabName === 'msi' || subtabName === 'block-msi') {
    await initMsiPackagesPanel();
  } else if (subtabName === 'store' || subtabName === 'msstore' || subtabName === 'microsoft-store' || subtabName === 'block-store') {
    await initStorePackagesPanel();
  } else if (subtabName === 'ninite' || subtabName === 'block-ninite') {
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
 * Переключает активный блок внутри панели менеджера пакетов (WinGet, MSI, Store, Ninite).
 * @param {string} panelId - Идентификатор панели ('packages')
 * @param {string} rawBlockId - Идентификатор блока ('block-ninite', 'block-winget', etc.)
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash
 */
export function switchSoftwareBlock(panelId, rawBlockId, updateUrl = true) {
  const canonicalBlock = normalizeBlockId(rawBlockId, panelId);
  let btnId = 'sw-subtab-winget-btn';
  let targetSubtabInit = 'winget';

  if (canonicalBlock === 'block-ninite') {
    btnId = 'sw-subtab-ninite-btn';
    targetSubtabInit = 'ninite';
  } else if (canonicalBlock === 'block-msi') {
    btnId = 'sw-subtab-msi-btn';
    targetSubtabInit = 'msi';
  } else if (canonicalBlock === 'block-store') {
    btnId = 'sw-subtab-store-btn';
    targetSubtabInit = 'store';
  } else {
    btnId = 'sw-subtab-winget-btn';
    targetSubtabInit = 'winget';
  }

  const btn = document.getElementById(btnId);
  if (btn) {
    const nav = document.getElementById('sw-packages-subtabs');
    if (nav) {
      nav.querySelectorAll('.nav-link').forEach((b) => b.classList.remove('active'));
    }
    btn.classList.add('active');

    const targetPaneSelector = btn.getAttribute('data-bs-target');
    if (targetPaneSelector) {
      const targetPane = document.querySelector(targetPaneSelector);
      if (targetPane && targetPane.parentElement) {
        targetPane.parentElement.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('show', 'active'));
        targetPane.classList.add('show', 'active');
      }
    }

    if (window.bootstrap && window.bootstrap.Tab) {
      try {
        const tabInst = window.bootstrap.Tab.getOrCreateInstance
          ? window.bootstrap.Tab.getOrCreateInstance(btn)
          : (window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn));
        tabInst?.show?.();
      } catch (_) {}
    }
  }

  triggerSubTabInit(targetSubtabInit);

  if (updateUrl) {
    updateUrlWithPanel('packages', canonicalBlock);
  }
}

/**
 * Программное переключение между субвкладками хаба с обновлением URL.
 * @param {string} subtabName - Имя целевой субпанели.
 * @param {string|boolean|null} [blockId=null] - Блок подменю или флаг updateUrl.
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchSoftwareSubTab(subtabName, blockId = null, updateUrl = true) {
  if (typeof blockId === 'boolean') {
    updateUrl = blockId;
    blockId = null;
  }
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
    const nav = document.getElementById('software-subtabs-nav');
    if (nav) {
      nav.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
    }
    btn.classList.add('active');

    const targetPaneId = `subpane-sw-${canonical}`;
    const targetPane = document.getElementById(targetPaneId);
    if (targetPane && targetPane.parentElement) {
      targetPane.parentElement.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('show', 'active'));
      targetPane.classList.add('show', 'active');
    }

    if (window.bootstrap && window.bootstrap.Tab) {
      try {
        const tabInst = window.bootstrap.Tab.getOrCreateInstance
          ? window.bootstrap.Tab.getOrCreateInstance(btn)
          : (window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn));
        tabInst?.show?.();
      } catch (_) {}
    }
  }

  // Если это панель пакетов (packages) или указан ninite / msi / store / winget
  if (canonical === 'packages') {
    let targetBlock = blockId;
    if (!targetBlock) {
      const s = String(subtabName).toLowerCase();
      if (s.includes('ninite')) targetBlock = 'block-ninite';
      else if (s.includes('msi')) targetBlock = 'block-msi';
      else if (s.includes('store')) targetBlock = 'block-store';
      else if (s.includes('winget')) targetBlock = 'block-winget';
      else targetBlock = getBlockFromHash('packages');
    }
    targetBlock = normalizeBlockId(targetBlock, 'packages');
    switchSoftwareBlock('packages', targetBlock, updateUrl);
  } else {
    triggerSubTabInit(canonical);
    if (updateUrl) {
      updateUrlWithPanel(canonical, null);
    }
  }
}

/**
 * Настройка обработчиков переключения субвкладок и блоков.
 */
export function setupSubTabNavigation() {
  const bindTabBtn = (btnId, name) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('shown.bs.tab', () => {
      switchSoftwareSubTab(name, null, true);
    });
    btn.addEventListener('click', () => {
      switchSoftwareSubTab(name, null, true);
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

  const bindBlockBtn = (btnId, blockId) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('shown.bs.tab', () => {
      switchSoftwareBlock('packages', blockId, true);
    });
    btn.addEventListener('click', () => {
      switchSoftwareBlock('packages', blockId, true);
    });
  };

  bindBlockBtn('sw-subtab-winget-btn', 'block-winget');
  bindBlockBtn('sw-subtab-msi-btn', 'block-msi');
  bindBlockBtn('sw-subtab-store-btn', 'block-store');
  bindBlockBtn('sw-subtab-ninite-btn', 'block-ninite');
}

// Экспорт методов в глобальную область window
if (typeof window !== 'undefined') {
  window.switchSoftwareSubTab = switchSoftwareSubTab;
  window.switchSoftwareBlock = switchSoftwareBlock;
  window.getSoftwarePanelFromHash = getPanelFromHash;
  window.getSoftwareBlockFromHash = getBlockFromHash;
  window.getActiveSoftwareBlockId = getActiveBlockId;
  window.updateSoftwareUrlWithPanel = updateUrlWithPanel;
  window.normalizeSoftwareSubTabId = normalizeSubTabId;
  window.normalizeSoftwareBlockId = normalizeBlockId;
}
