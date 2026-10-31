/**
 * =============================================================================
 * Process Name: Windows Network Terminal Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский скрипт-оркестратор вкладки Windows Network Terminal.
 *   Координирует тестирование скорости (Speedtest), опрос адаптеров,
 *   активных сокетов/портов, перехват трафика DPI (TShark) и анализ PCAP
 *   с поддержкой URL-маршрутизации панелей (#tab-network#<panel_id>).
 *
 * File: main.js
 * Package: apps/windows/api/webgui/tab_network
 * Updated: 2026-10-28 19:04:00
 * =============================================================================
 */

import { fetchNetworkStatus } from './panel_kpi_status/panel.js';
import { fetchLatestSpeedtest, runInternetSpeedtest } from './panel_speedtest/panel.js';
import { fetchAdapters, getAllAdapters } from './panel_adapters/panel.js';
import { fetchConnections, renderConnectionsTable, setActiveConnFilter } from './panel_connections/panel.js';
import {
  initDiscoveryPanel,
  fetchDiscoveredDevices,
  startDiscoveryAutoRefresh,
  stopDiscoveryAutoRefresh
} from './panel_discovery/panel.js';
import { loadInfraPanel, initInfraPanels } from './panel_infra/panel.js';
import {
  startLiveCapture,
  stopLiveCapture,
  clearCapturedPackets,
  analyzePcapFile,
  renderPacketsTable,
  getCapturedPacketsCount
} from './panel_capture_pcap/panel.js';

export const TAB_ID = 'tab-network';
let isNetInitialized = false;

/**
 * Проверяет, активна ли вкладка Network Terminal.
 * @returns {boolean}
 */
export function isNetworkTabActive() {
  if (typeof document !== 'undefined' && document.hidden) return false;
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive(TAB_ID) || window.isTabActive('network'));
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('network');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор суб-вкладки.
 * @param {string} rawId - Сырой идентификатор вкладки.
 * @returns {string} Канонический идентификатор панели.
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'speedtest';
  const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^tab-net-/, '').replace(/^panel-network-/, '').replace(/-btn$/, '');
  if (s.includes('speed')) return 'speedtest';
  if (s.includes('discovery') || s.includes('lan') || s.includes('device') || s.includes('computer')) return 'discovery';
  if (s.includes('adapter') || s.includes('interface')) return 'adapters';
  if (s.includes('conn') || s.includes('socket') || s.includes('port')) return 'connections';
  if (s.includes('capture') || s.includes('sniffer') || s.includes('dpi')) return 'capture';
  if (s.includes('pcap')) return 'pcap';
  if (s.includes('overview')) return 'overview';
  if (s.includes('switch')) return 'switches';
  if (s.includes('ip') || s.includes('route')) return 'ip-config';
  if (s.includes('nat')) return 'nat';
  if (s.includes('wsl')) return 'wsl';
  if (s.includes('diag')) return 'diagnostics';
  if (s.includes('hist')) return 'history';
  return s || 'speedtest';
}

/**
 * Извлекает субпанель из URL hash.
 * @returns {string|null} Идентификатор субвкладки или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'network') {
      return normalizeSubTabId(parts[1]);
    }
  }
  return null;
}

/**
 * Обновляет адресную строку браузера активной суб-панелью (#tab-network#<panel_id>).
 * @param {string} panelId - Идентификатор субвкладки.
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
 * Возвращает канонический идентификатор текущей активной субпанели.
 * @returns {string}
 */
export function getActiveSubTabId() {
  const activeBtn = document.querySelector('#network-subtabs-nav button.active');
  if (activeBtn) {
    const pId = activeBtn.getAttribute('data-panel-id');
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(pId || target);
  }
  return getPanelFromHash() || 'speedtest';
}

/**
 * Запрашивает API строго и исключительно для активной субпанели.
 * Неактивные панели не запрашивают API, а их фоновые поллеры останавливаются.
 * @param {string} [subtabId] - Идентификатор целевой панели.
 */
export function fetchActiveSubTabOnly(subtabId) {
  if (!isNetworkTabActive()) return;
  const canonical = normalizeSubTabId(subtabId || getActiveSubTabId());

  // Останавливаем поллеры других панелей
  if (canonical !== 'discovery') {
    stopDiscoveryAutoRefresh();
  }

  switch (canonical) {
    case 'speedtest':
      fetchLatestSpeedtest();
      break;
    case 'discovery':
      loadDiscoveryData(false);
      break;
    case 'adapters':
      fetchAdapters();
      loadInfraPanel('adapters');
      break;
    case 'connections':
      fetchConnections();
      break;
    case 'capture':
      const adapters = getAllAdapters();
      if (!adapters || adapters.length === 0) fetchAdapters();
      break;
    case 'pcap':
      break;
    case 'overview':
    case 'switches':
    case 'ip-config':
    case 'nat':
    case 'wsl':
    case 'diagnostics':
    case 'history':
      loadInfraPanel(canonical);
      break;
  }
}

/**
 * Программное переключение между суб-вкладками сетевого терминала.
 * @param {string} subtabId - Идентификатор подвкладки.
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchNetworkSubTab(subtabId, updateUrl = true) {
  const canonical = normalizeSubTabId(subtabId);
  let btnId = 'subtab-net-speedtest-btn';
  switch (canonical) {
    case 'speedtest':
      btnId = 'subtab-net-speedtest-btn';
      break;
    case 'discovery':
      btnId = 'subtab-net-discovery-btn';
      break;
    case 'adapters':
      btnId = 'subtab-net-adapters-btn';
      break;
    case 'connections':
      btnId = 'subtab-net-connections-btn';
      break;
    case 'capture':
      btnId = 'subtab-net-capture-btn';
      break;
    case 'pcap':
      btnId = 'subtab-net-pcap-btn';
      break;
    case 'overview':
    case 'switches':
    case 'ip-config':
    case 'nat':
    case 'wsl':
    case 'diagnostics':
    case 'history':
      btnId = `subtab-net-${canonical}-btn`;
      break;
  }
  const btn = document.getElementById(btnId);
  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
      tabInst.show();
    } else {
      btn.click();
    }
  }
  if (updateUrl) {
    updateUrlWithPanel(canonical);
  }
  fetchActiveSubTabOnly(canonical);
}

/**
 * Инициализирует вкладку Network Terminal.
 */
export function initNetworkTab() {
  console.log('[NetworkTab] Initializing Windows Network Terminal tab (/apps/windows/network)...');
  initDiscoveryPanel();

  if (!isNetInitialized) {
    const refreshAllBtn = document.getElementById('btn-refresh-network-all');
    const runSpeedtestBtn = document.getElementById('btn-run-speedtest');
    const refreshAdaptersBtn = document.getElementById('btn-refresh-adapters');
    const refreshConnsBtn = document.getElementById('btn-refresh-conns');
    const startBtn = document.getElementById('btn-start-live-capture');
    const stopBtn = document.getElementById('btn-stop-live-capture');
    const analyzePcapBtn = document.getElementById('btn-analyze-pcap');
    const clearPacketsBtn = document.getElementById('btn-clear-packets');
    const connsFilterInput = document.getElementById('net-conns-filter');
    const tableFilterInput = document.getElementById('net-table-filter');

    if (refreshAllBtn) {
      refreshAllBtn.onclick = () => {
        fetchNetworkStatus(getCapturedPacketsCount());
        fetchLatestSpeedtest();
        fetchAdapters();
        fetchConnections();
        fetchDiscoveredDevices(false);
      };
    }
    if (runSpeedtestBtn) runSpeedtestBtn.onclick = runInternetSpeedtest;
    if (refreshAdaptersBtn) refreshAdaptersBtn.onclick = fetchAdapters;
    if (refreshConnsBtn) refreshConnsBtn.onclick = fetchConnections;
    if (startBtn) startBtn.onclick = startLiveCapture;
    if (stopBtn) stopBtn.onclick = stopLiveCapture;
    if (analyzePcapBtn) analyzePcapBtn.onclick = analyzePcapFile;
    if (clearPacketsBtn) clearPacketsBtn.onclick = clearCapturedPackets;

    if (connsFilterInput) connsFilterInput.oninput = renderConnectionsTable;
    if (tableFilterInput) tableFilterInput.oninput = renderPacketsTable;

    // Фильтры подключений
    document.querySelectorAll('.btn-filter-conns').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.btn-filter-conns').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        setActiveConnFilter(btn.getAttribute('data-filter') || 'all');
        renderConnectionsTable();
      };
    });

    initInfraPanels();

    // Навигация по суб-вкладкам
    const subtabsNav = document.getElementById('network-subtabs-nav');
    if (subtabsNav) {
      subtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {
        btn.addEventListener('shown.bs.tab', (e) => {
          const targetId = e.target.getAttribute('data-bs-target') || '';
          const pId = e.target.getAttribute('data-panel-id') || normalizeSubTabId(targetId);
          updateUrlWithPanel(pId);
          fetchActiveSubTabOnly(pId);
        });
      });
    }

    // Слушатель изменения hash в URL при активной вкладке
    window.addEventListener('hashchange', () => {
      if (!isNetworkTabActive()) return;
      const target = getPanelFromHash();
      if (target) {
        switchNetworkSubTab(target, false);
      }
    });

    // Активация вкладки в общем интерфейсе
    document.addEventListener('tab:activated', (e) => {
      if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'network') {
        const target = getPanelFromHash();
        if (target) {
          switchNetworkSubTab(target, false);
        } else {
          updateUrlWithPanel('speedtest');
        }
      }
    });

    isNetInitialized = true;
  }

  // Опрашиваем API ТОЛЬКО для активной панели
  const activePanel = getPanelFromHash() || getActiveSubTabId() || 'speedtest';
  fetchNetworkStatus(getCapturedPacketsCount());
  if (getPanelFromHash()) {
    switchNetworkSubTab(activePanel, false);
  } else {
    fetchActiveSubTabOnly(activePanel);
  }
}

/**
 * Деактивация вкладки при переходе пользователя на другую вкладку.
 */
export function deactivateNetworkTab() {
  stopDiscoveryAutoRefresh();
}

// Экспорт для глобального доступа и совместимости с хост-контейнером
window.initNetworkTab = initNetworkTab;
window.activateNetworkTab = initNetworkTab;
window.deactivateNetworkTab = deactivateNetworkTab;
window.switchNetworkSubTab = switchNetworkSubTab;
window.getNetworkPanelFromHash = getPanelFromHash;
window.updateNetworkUrlWithPanel = updateUrlWithPanel;

// Автозапуск при обнаружении контейнера в DOM
if (document.getElementById('tab-network') || document.getElementById('net-conns-tbody')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initNetworkTab());
  } else {
    setTimeout(() => initNetworkTab(), 10);
  }
}
