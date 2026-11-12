/**
 * =============================================================================
 * Process Name: Windows Storage Management Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер консолидированной панели накопителей.
 *   Управляет суб-вкладками «Диски и тома» и «Ресурс и SMART»
 *   с поддержкой URL-маршрутизации панелей (#tab-storage-management#panel-<id>).
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_storage_management
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:30:00
 * =============================================================================
 */

(function () {
  'use strict';

  const TAB_ID = 'tab-storage-management';

  function isStorageManagementTabActive() {
    const pane = document.getElementById(TAB_ID);
    return pane ? pane.classList.contains('active') : false;
  }

  function normalizeSubTabId(rawId) {
    if (!rawId) return 'volumes';
    const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^panel-/, '');
    if (s.includes('wear') || s.includes('smart') || s.includes('health')) return 'wear';
    return 'volumes';
  }

  function getPanelFromHash() {
    const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
    if (!hash) return null;
    const cleanHash = hash.replace(/^#/, '');
    const parts = cleanHash.split('#');
    if (parts.length >= 2) {
      const mainPart = parts[0];
      if (mainPart === TAB_ID || mainPart === 'storage-management' || mainPart === 'storage-manager') {
        return normalizeSubTabId(parts[1]);
      }
    }
    return null;
  }

  function updateUrlWithPanel(panelId) {
    if (typeof history === 'undefined' || typeof location === 'undefined') return;
    const canonical = normalizeSubTabId(panelId);
    const search = location.search || '';
    const newHash = `#${TAB_ID}#panel-${canonical}`;
    if (location.hash !== newHash) {
      try {
        history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
      } catch (_) {}
    }
  }

  function loadScript(src) {
    return new Promise((resolve) => {
      const cleanSrc = src.split('?')[0];
      const existing = document.querySelector(`script[src^="${cleanSrc}"]`);
      if (existing) {
        resolve();
        return;
      }
      const s = document.createElement('script');
      s.type = 'module';
      s.src = src;
      s.onload = () => resolve();
      s.onerror = (err) => {
        console.warn(`[StorageManagement] Не удалось загрузить скрипт ${src}:`, err);
        resolve();
      };
      document.body.appendChild(s);
    });
  }

  async function loadSubPane(containerId, htmlUrl, jsUrl, initFnName) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!container.hasChildNodes()) {
      try {
        const res = await fetch(`${htmlUrl}?v=${Date.now()}`);
        if (!res.ok) return;
        container.innerHTML = await res.text();
      } catch (err) {
        console.warn(`[StorageManagement] Ошибка загрузки HTML для ${containerId}:`, err);
        return;
      }
    }

    if (jsUrl) {
      try {
        await loadScript(`${jsUrl}?v=${Date.now()}`);
        if (initFnName && typeof window[initFnName] === 'function') {
          try { window[initFnName](); } catch (err) { console.debug(`[StorageManagement] ${initFnName} error:`, err); }
        }
      } catch (err) {
        console.warn(`[StorageManagement] Ошибка скрипта для ${containerId}:`, err);
      }
    }
  }

  async function loadSubPanes() {
    // 1. Диски и тома
    await loadSubPane(
      'storage-manager-embed-container',
      '/html/tab_storage_manager/index.html',
      '/html/tab_storage_manager/main.js',
      'initStorageManagerTab'
    );

    // 2. Ресурс и SMART
    await loadSubPane(
      'storage-wear-embed-container',
      '/html/tab_storage_wear/index.html',
      '/html/tab_storage_wear/main.js',
      'initStorageWearTab'
    );
  }

  async function triggerSubTabInit(subtabName) {
    const canonical = normalizeSubTabId(subtabName);
    if (canonical === 'wear') {
      await loadSubPane('storage-wear-embed-container', '/html/tab_storage_wear/index.html', '/html/tab_storage_wear/main.js', 'initStorageWearTab');
      if (typeof window.initStorageWearTab === 'function') window.initStorageWearTab();
    } else {
      await loadSubPane('storage-manager-embed-container', '/html/tab_storage_manager/index.html', '/html/tab_storage_manager/main.js', 'initStorageManagerTab');
      if (typeof window.initStorageManagerTab === 'function') window.initStorageManagerTab();
    }
  }

  window.switchStorageSubTab = function(subtabName, updateUrl = true) {
    const canonical = normalizeSubTabId(subtabName);
    const btnId = canonical === 'wear' ? 'subtab-storage-wear-btn' : 'subtab-storage-volumes-btn';
    const btn = document.getElementById(btnId);
    if (btn) {
      if (window.bootstrap && window.bootstrap.Tab) {
        new window.bootstrap.Tab(btn).show();
      } else {
        btn.click();
      }
      triggerSubTabInit(canonical);
    }
    if (updateUrl) {
      updateUrlWithPanel(canonical);
    }
  };

  async function initStorageManagementTab() {
    await loadSubPanes();

    const bindBtn = (id, panel) => {
      const el = document.getElementById(id);
      if (el && !el.dataset.boundRouting) {
        el.dataset.boundRouting = 'true';
        el.addEventListener('shown.bs.tab', () => updateUrlWithPanel(panel));
        el.addEventListener('click', () => updateUrlWithPanel(panel));
      }
    };
    bindBtn('subtab-storage-volumes-btn', 'volumes');
    bindBtn('subtab-storage-wear-btn', 'wear');

    window.addEventListener('hashchange', () => {
      if (!isStorageManagementTabActive()) return;
      const target = getPanelFromHash();
      if (target) {
        window.switchStorageSubTab(target, false);
      }
    });

    document.addEventListener('tab:activated', (e) => {
      if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'storage-management') {
        const target = getPanelFromHash();
        if (target) {
          window.switchStorageSubTab(target, false);
        } else {
          updateUrlWithPanel('volumes');
        }
      }
    });

    const panelFromHash = getPanelFromHash();
    if (panelFromHash) {
      window.switchStorageSubTab(panelFromHash, false);
    }
  }

  window.initStorageManagementTab = initStorageManagementTab;
  window.getStoragePanelFromHash = getPanelFromHash;
  window.updateStorageUrlWithPanel = updateUrlWithPanel;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStorageManagementTab);
  } else {
    initStorageManagementTab();
  }
})();
