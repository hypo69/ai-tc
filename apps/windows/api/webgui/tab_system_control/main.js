/**
 * Модуль-оркестратор вкладки System Logs & Activity Center (tab_system_control).
 * 
 * Маршрутизирует и объединяет изолированные модули:
 * - panel_summary: сводный дашборд сбоев (BSOD, Kernel-Power, ошибки драйверов, аномалии)
 * - panel_event_logs: события Windows Event Log, дерево каналов, фильтрация
 * - panel_smart_digest: Smart Digest аудит, кластеризация, каскадные инциденты, таймлайн
 * - panel_rag: локальный семантический RAG-поиск в IndexedDB без затрат токенов LLM
 * - panel_power_lifecycle: непрерывный аптайм, сессии питания, аварийные выключения
 * - panel_defender_logs: статус защиты, антивирусные события Defender, блокировки CFA/ASR
 * - panel_forensics: поведенческая форензика, UserAssist ROT13, активность окон, микрофон/камера
 * - panel_throttling: детекция термального троттлинга (PROCHOT), Power Limit (PL1/PL2), задержки DPC/ISR, шина GPU PCIe, дампы BSOD
 * 
 * Updated: 2026-11-12 02:30:00
 */

import { adjustMainStreamHeight, initTableResizers, t } from './common/ui_utils.js';
import { initSummaryDashboard, loadFailuresSummary } from './panel_summary/panel.js';
import { initEventLogsPanel, scanChannels, loadEvents, getCurrentChannel, getCurrentFilePath, getCachedEvents, getCachedChannels } from './panel_event_logs/panel.js';
import { showEventDetails } from './panel_event_logs/modal.js';
import { initRagPanel, fetchRagStatus, setRagEventDetailsCallback } from './panel_rag/panel.js';
import { initPowerLifecyclePanel, loadPowerData, stopPowerUptimeCounter as stopPowerLifecycleUptimeCounter } from './panel_power_lifecycle/panel.js?v=20261101_v2';
import { initDefenderLogsPanel, loadDefenderData } from './panel_defender_logs/panel.js';
import { initForensicsPanel, loadForensicsData, switchForensicsSubTab } from './panel_forensics/panel.js';
import { initThrottlingPanel, loadThrottlingData, stopThrottlingPolling } from './panel_throttling/panel.js';
import { loadAuditDigest } from './panel_smart_digest/panel.js';
import { loadIncidents, loadTimeline } from './panel_smart_digest/incidents_timeline.js';

let isSCCInitialized = false;
let activeSource = 'summary-dashboard';
let activeMode = 'live';
let currentMode = 'live';
let liveIntervalTimer = null;
let activeSourcePollerTimer = null;

function isSystemControlTabActive() {
  const pane = document.getElementById('tab-system-control') || document.getElementById('tab-system-logs');
  if (pane) {
    return pane.classList.contains('active') || pane.classList.contains('show') || pane.style.display !== 'none';
  }
  return true;
}

function normalizeSystemControlSource(sourceId) {
  const s = String(sourceId).toLowerCase().trim().replace(/^#/, '').replace(/^panel-/, '');
  if (s.includes('summary')) return 'summary-dashboard';
  if (s.includes('event')) return 'event-logs';
  if (s.includes('defender')) return 'defender-logs';
  if (s.includes('power')) return 'power-lifecycle';
  if (s.includes('forensic')) return 'forensics';
  if (s.includes('throttling') || s.includes('throttle')) return 'throttling';
  return 'summary-dashboard';
}

function getSystemControlPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash.includes('tab-system-control')) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const p1 = parts[1];
    const blockPart = parts.find((p) => p.startsWith('block-'));
    let sub = null;
    if (blockPart) {
      sub = blockPart.replace(/^block-/, '');
    } else if (parts[2]) {
      sub = parts[2].replace(/^block-/, '');
    } else if (p1.includes('userassist')) {
      sub = 'userassist';
    } else if (p1.includes('timeline')) {
      sub = 'timeline';
    }
    return { source: normalizeSystemControlSource(p1), subtab: sub };
  }
  return { source: 'summary-dashboard', subtab: null };
}

function updateUrlWithSource(source, subtab = null) {
  const canonical = normalizeSystemControlSource(source);
  const search = location.search || '';
  let blockSuffix = '';
  if (canonical === 'forensics') {
    const rawSub = subtab ? String(subtab).replace(/^block-/, '') : 'userassist';
    blockSuffix = `#block-${rawSub}`;
  }
  const newHash = `#tab-system-control#panel-${canonical}${blockSuffix}`;
  if (location.hash !== newHash) {
    history.replaceState(null, '', `${location.pathname}${search}${newHash}`);
  }
}

function fetchActiveSourceData(force = false) {
  const canonical = normalizeSystemControlSource(activeSource);
  if (!isSystemControlTabActive()) return;

  // Изоляция фонового опроса: отсечение неактивных источников
  if (activeSource !== 'summary-dashboard' && canonical === 'summary-dashboard') return;
  if (activeSource !== 'event-logs' && canonical === 'event-logs') return;
  if (activeSource !== 'power-lifecycle' && canonical === 'power-lifecycle') return;
  if (activeSource !== 'defender-logs' && canonical === 'defender-logs') return;
  if (activeSource !== 'forensics' && canonical === 'forensics') return;
  if (activeSource !== 'throttling' && canonical === 'throttling') return;

  if (canonical === 'summary-dashboard') {
    loadFailuresSummary(null, force, isSystemControlTabActive);
  } else if (canonical === 'event-logs') {
    if (activeMode === 'live' || activeMode === 'errors') {
      loadEvents(force, activeMode);
    }
  } else if (canonical === 'power-lifecycle') {
    loadPowerData(force, isSystemControlTabActive);
  } else if (canonical === 'defender-logs') {
    loadDefenderData(force, isSystemControlTabActive);
  } else if (canonical === 'forensics') {
    loadForensicsData(force, isSystemControlTabActive);
  } else if (canonical === 'throttling') {
    loadThrottlingData(force, isSystemControlTabActive);
  }
}

function stopPowerUptimeCounter() {
  stopPowerLifecycleUptimeCounter();
}

function stopPolling() {
  if (liveIntervalTimer) {
    clearInterval(liveIntervalTimer);
    liveIntervalTimer = null;
  }
  if (activeSourcePollerTimer) {
    clearInterval(activeSourcePollerTimer);
    activeSourcePollerTimer = null;
  }
  stopPowerUptimeCounter();
  stopThrottlingPolling();
}

function startPolling() {
  stopPolling();
  const liveSwitch = document.getElementById('slc-live-switch');
  if (liveSwitch && !liveSwitch.checked) {
    return;
  }
  const intervalMs = 3000;
  liveIntervalTimer = setInterval(() => {
    if (!isSystemControlTabActive()) return;
    if (activeSource === 'event-logs' && (currentMode === 'live' || currentMode === 'errors')) {
      loadEvents(false, currentMode);
    }
  }, intervalMs);

  activeSourcePollerTimer = setInterval(() => {
    if (!isSystemControlTabActive()) return;
    const can = normalizeSystemControlSource(activeSource);
    if (can === 'defender-logs') {
      loadDefenderData(false, isSystemControlTabActive);
    } else if (can === 'forensics') {
      loadForensicsData(false, isSystemControlTabActive);
    } else if (can === 'throttling') {
      loadThrottlingData(false, isSystemControlTabActive);
    } else if (can === 'power-lifecycle') {
      loadPowerData(false, isSystemControlTabActive);
    }
  }, 5000);
}

function setSource(source, updateUrl = true, subtab = null) {
  stopPolling();
  const canonical = normalizeSystemControlSource(source);
  activeSource = canonical;

  const sourceBtns = [
    { id: 'btn-source-summary-dashboard', source: 'summary-dashboard' },
    { id: 'btn-source-event-logs', source: 'event-logs' },
    { id: 'btn-source-defender-logs', source: 'defender-logs' },
    { id: 'btn-source-power-lifecycle', source: 'power-lifecycle' },
    { id: 'btn-source-forensics', source: 'forensics' },
    { id: 'btn-source-throttling', source: 'throttling' },
  ];

  sourceBtns.forEach(b => {
    const el = document.getElementById(b.id);
    if (el) {
      el.classList.toggle('active', b.source === canonical);
    }
  });

  const modeTabs = document.getElementById('slc-mode-tabs');
  const panelControl1 = document.getElementById('panel-system-control-1');
  if (canonical === 'event-logs') {
    if (modeTabs) modeTabs.classList.remove('d-none');
    if (panelControl1) panelControl1.classList.remove('d-none');
    applySourceAndMode(canonical, activeMode, true);
  } else {
    if (modeTabs) modeTabs.classList.add('d-none');
    if (panelControl1) panelControl1.classList.add('d-none');
    applySourceAndMode(canonical, 'live', true);
  }

  if (updateUrl) {
    updateUrlWithSource(canonical, subtab);
  }
  startPolling();
}

function setMode(mode) {
  activeMode = mode;
  currentMode = mode;

  document.querySelectorAll('#slc-mode-tabs button').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-mode') === mode);
  });

  applySourceAndMode(activeSource, mode, true);
}

function applySourceAndMode(source, mode, forceRefresh = false) {
  const summaryContainer = document.getElementById('slc-summary-dashboard-container');
  const panelControl1 = document.getElementById('panel-system-control-1');
  const mainRow = document.getElementById('slc-main-row');
  const tableContainer = document.getElementById('slc-table-container');
  const auditContainer = document.getElementById('slc-audit-container');
  const ragContainer = document.getElementById('slc-rag-container');
  const incidentsContainer = document.getElementById('slc-incidents-container');
  const timelineContainer = document.getElementById('slc-timeline-container');
  const rawContainer = document.getElementById('slc-raw-container');
  const eventLogsContainer = document.getElementById('slc-event-logs-container');
  const powerLifecycleContainer = document.getElementById('slc-power-lifecycle-container');
  const defenderLogsContainer = document.getElementById('slc-defender-logs-container');
  const forensicsContainer = document.getElementById('slc-forensics-container');
  const throttlingContainer = document.getElementById('slc-throttling-container');
  const filterRow = document.getElementById('slc-filter-row');
  const sidebar = document.getElementById('slc-channel-tree-sidebar');
  const mainStreamCol = document.getElementById('slc-main-stream-column');
  const mainStreamHeader = document.querySelector('#slc-main-stream-column .panel-header');

  if (summaryContainer) summaryContainer.classList.add('d-none');

  if (source === 'summary-dashboard') {
    if (summaryContainer) summaryContainer.classList.remove('d-none');
    if (panelControl1) panelControl1.classList.add('d-none');
    if (mainRow) mainRow.classList.add('d-none');
    loadFailuresSummary(null, false, isSystemControlTabActive);
    return;
  }

  if (source === 'event-logs') {
    if (panelControl1) panelControl1.classList.remove('d-none');
    if (mainRow) mainRow.classList.remove('d-none');
  } else {
    if (panelControl1) panelControl1.classList.add('d-none');
    if (mainRow) mainRow.classList.add('d-none');
  }

  [tableContainer, auditContainer, ragContainer, incidentsContainer, timelineContainer, rawContainer, eventLogsContainer, powerLifecycleContainer, defenderLogsContainer, forensicsContainer, throttlingContainer].forEach(el => {
    if (el) el.classList.add('d-none');
  });

  if (filterRow) {
    if (source === 'event-logs') {
      filterRow.classList.remove('d-none');
    } else {
      filterRow.classList.add('d-none');
    }
  }

  if (source === 'event-logs' && (mode === 'live' || mode === 'errors')) {
    if (sidebar) sidebar.classList.remove('d-none');
    if (mainStreamCol) {
      mainStreamCol.classList.remove('col-12');
      mainStreamCol.classList.add('col-lg-9');
    }
    if (mainStreamHeader) mainStreamHeader.classList.remove('d-none');
  } else {
    if (sidebar) sidebar.classList.add('d-none');
    if (mainStreamCol) {
      mainStreamCol.classList.remove('col-lg-9');
      mainStreamCol.classList.add('col-12');
    }
    if (mainStreamHeader) mainStreamHeader.classList.add('d-none');
  }

  // Специализированные панели отображаются независимо от activeMode
  if (source === 'power-lifecycle') {
    if (powerLifecycleContainer) powerLifecycleContainer.classList.remove('d-none');
    initPowerLifecyclePanel();
    loadPowerData(forceRefresh, isSystemControlTabActive);
  } else if (source === 'defender-logs') {
    if (defenderLogsContainer) defenderLogsContainer.classList.remove('d-none');
    initDefenderLogsPanel();
    loadDefenderData(forceRefresh, isSystemControlTabActive);
  } else if (source === 'forensics') {
    if (forensicsContainer) forensicsContainer.classList.remove('d-none');
    initForensicsPanel();
    loadForensicsData(forceRefresh, isSystemControlTabActive);
  } else if (source === 'throttling') {
    if (throttlingContainer) throttlingContainer.classList.remove('d-none');
    initThrottlingPanel();
    loadThrottlingData(forceRefresh, isSystemControlTabActive);
  } else if (source === 'event-logs') {
    if (!getCachedChannels() || getCachedChannels().length === 0) {
      scanChannels(false);
    }
    if (mode === 'live' || mode === 'errors') {
      if (tableContainer) tableContainer.classList.remove('d-none');
      loadEvents(forceRefresh, mode);
    } else if (mode === 'audit') {
      if (auditContainer) auditContainer.classList.remove('d-none');
      loadAuditDigest(getCurrentChannel(), source, getCurrentFilePath());
    } else if (mode === 'rag') {
      if (ragContainer) ragContainer.classList.remove('d-none');
      if (filterRow) filterRow.classList.add('d-none');
      fetchRagStatus();
    } else if (mode === 'incidents') {
      if (incidentsContainer) incidentsContainer.classList.remove('d-none');
      loadIncidents(getCurrentChannel(), getCurrentFilePath());
    } else if (mode === 'timeline') {
      if (timelineContainer) timelineContainer.classList.remove('d-none');
      loadTimeline(getCurrentChannel(), getCurrentFilePath());
    }
  }

  setTimeout(adjustMainStreamHeight, 10);
}

function exportEvents(format = 'json') {
  const cachedEvents = getCachedEvents();
  if (!cachedEvents || cachedEvents.length === 0) {
    if (window.toast) {
      window.toast.warning('Экспорт', 'Нет загруженных событий для экспорта.');
    }
    return;
  }
  let content = '';
  let mime = 'application/json';
  let ext = 'json';

  if (format === 'json') {
    content = JSON.stringify(cachedEvents, null, 2);
  } else {
    mime = 'text/csv';
    ext = 'csv';
    const headers = ['timestamp', 'level', 'event_id', 'provider', 'process_id', 'message'];
    const rows = cachedEvents.map(e => headers.map(h => `"${String(e[h] || '').replace(/"/g, '""')}"`).join(','));
    content = [headers.join(','), ...rows].join('\n');
  }

  const cleanChan = getCurrentChannel().replace(/^evt:/i, '').replace(/[^a-zA-Z0-9_-]/g, '_');
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `system_logs_${cleanChan}_${Date.now()}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

export function initSystemControlTab() {
  if (isSCCInitialized) return;
  isSCCInitialized = true;

  setRagEventDetailsCallback((entry) => showEventDetails(entry, 'panel-system-control-3', getCurrentChannel()));

  initSummaryDashboard();
  initEventLogsPanel();
  initRagPanel();
  initPowerLifecyclePanel();
  initDefenderLogsPanel();
  initForensicsPanel();
  initThrottlingPanel();
  initTableResizers();

  const sourceBtns = [
    { id: 'btn-source-summary-dashboard', source: 'summary-dashboard' },
    { id: 'btn-source-event-logs', source: 'event-logs' },
    { id: 'btn-source-defender-logs', source: 'defender-logs' },
    { id: 'btn-source-power-lifecycle', source: 'power-lifecycle' },
    { id: 'btn-source-forensics', source: 'forensics' },
    { id: 'btn-source-throttling', source: 'throttling' },
  ];

  sourceBtns.forEach(b => {
    const el = document.getElementById(b.id);
    if (el) {
      el.addEventListener('click', () => setSource(b.source, true));
    }
  });

  document.querySelectorAll('#slc-mode-tabs button').forEach(b => {
    b.addEventListener('click', () => {
      const mode = b.getAttribute('data-mode');
      if (mode) setMode(mode);
    });
  });

  const btnExportJson = document.getElementById('btn-slc-export-json');
  if (btnExportJson) btnExportJson.addEventListener('click', () => exportEvents('json'));

  const btnExportCsv = document.getElementById('btn-slc-export-csv');
  if (btnExportCsv) btnExportCsv.addEventListener('click', () => exportEvents('csv'));

  const btnRefresh = document.getElementById('btn-slc-refresh');
  if (btnRefresh && !btnRefresh._bound) {
    btnRefresh._bound = true;
    btnRefresh.addEventListener('click', () => {
      fetchActiveSourceData(true);
    });
  }

  const btnScan = document.getElementById('btn-slc-scan');
  if (btnScan && !btnScan._bound) {
    btnScan._bound = true;
    btnScan.addEventListener('click', () => {
      const canonical = normalizeSystemControlSource(activeSource);
      if (canonical === 'power-lifecycle') {
        const pwrRebuild = document.getElementById('pwr-rebuild-btn');
        if (pwrRebuild) pwrRebuild.click();
      } else if (canonical === 'event-logs') {
        scanChannels(true);
      } else if (canonical === 'throttling') {
        loadThrottlingData(true, isSystemControlTabActive);
      } else {
        fetchActiveSourceData(true);
      }
    });
  }

  const hashData = getSystemControlPanelFromHash();
  const initialSource = (hashData && hashData.source) ? hashData.source : 'summary-dashboard';
  setSource(initialSource, false, hashData ? hashData.subtab : null);

  startPolling();

  if (typeof window !== 'undefined' && window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    window.AISmartTooltip.initAll();
  }
}

window.initSystemControlTab = initSystemControlTab;
window.fetchActiveSourceData = fetchActiveSourceData;
window.switchForensicsSubTab = switchForensicsSubTab;
window.switchSystemControlSource = function(source, subtab) {
  setSource(source, true, subtab);
  if (source === 'forensics' && subtab) {
    switchForensicsSubTab(subtab);
  }
};
window.activateSystemControlTab = function() {
  const hData = getSystemControlPanelFromHash();
  if (hData && hData.source && hData.source !== activeSource) {
    setSource(hData.source, false, hData.subtab);
    if (hData.source === 'forensics' && hData.subtab) {
      switchForensicsSubTab(hData.subtab);
    }
  }
  fetchActiveSourceData(false);
  startPolling();
};
window.deactivateSystemControlTab = function() {
  stopPolling();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSystemControlTab);
} else {
  initSystemControlTab();
}
