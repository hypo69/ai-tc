/**
 * Корневой оркестратор комплексного инспектора процессов хоста (Processes Load Inspector).
 * Координирует работу панелей: Диспетчер процессов, Топ потоков, Deep Dive, Сеть/Файлы, Leak Hunter и ИИ-ассистент.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/main.js
 * Updated: 2026-11-01 17:45:00
 */

import {
  TAB_ID,
  isProcessesTabActive,
  normalizeSubTabId as uiNormalizeSubTabId,
  getActiveSubTabId as uiGetActiveSubTabId,
  getPanelFromHash as uiGetPanelFromHash,
  updateUrlWithPanel as uiUpdateUrlWithPanel,
  showToast,
  syncWikiLLMProcessKnowledge
} from './common/ui_utils.js?v=20261101_v1';
import {
  initProcessManagerPanel,
  fetchProcessManagerSummary,
  killProcess
} from './panel_process_manager/panel.js?v=20261020_v2';
import {
  openProcessAiModal,
  openPowerShellInvestigationModal,
  resolveAIModal
} from './panel_ai_audit/panel.js?v=20261031_v2';
import {
  initTopStreamPanel,
  fetchHostProcesses
} from './panel_top_stream/panel.js?v=20261020_v2';
import {
  initDeepDivePanel,
  openDeepDiveModalByPid,
  stopDeepDiveSamplePolling
} from './panel_deep_dive/panel.js?v=20261020_v2';
import {
  initNetworkFilesPanel,
  fetchNetworkActivity,
  fetchLiveFileEvents
} from './panel_network_files/panel.js?v=20261101_v2';
import {
  initLeakHunterPanel,
  fetchProcessLeaks,
  renderProcessLeaksTable
} from './panel_leak_hunter/panel.js?v=20261020_v2';

let activeSubPollerTimer = null;
let isInitialized = false;

/**
 * Возвращает канонический идентификатор активной суб-панели инспектора процессов.
 * @returns {string} Идентификатор ('manager', 'top', 'net', 'files', 'leaks').
 */
export function getActiveSubTabId() {
  return uiGetActiveSubTabId();
}

/**
 * Нормализует строковый идентификатор или алиас суб-вкладки.
 * @param {string} rawId - Сырой идентификатор вкладки.
 * @returns {string} Канонический идентификатор суб-вкладки.
 */
export function normalizeSubTabId(rawId) {
  return uiNormalizeSubTabId(rawId);
}

/**
 * Извлекает субпанель из URL hash.
 * @returns {string|null} Идентификатор субвкладки или null.
 */
export function getPanelFromHash() {
  return uiGetPanelFromHash();
}

/**
 * Обновляет адресную строку браузера с учетом активной панели.
 * @param {string} panelId - Идентификатор субвкладки.
 */
export function updateUrlWithPanel(panelId) {
  return uiUpdateUrlWithPanel(panelId);
}

/**
 * Выполняет загрузку данных ТОЛЬКО для активной в данный момент суб-панели.
 * @param {boolean} [force=false] - Принудительный запрос независимо от фокуса.
 */
export async function fetchActiveSubTabOnly(force = false) {
  if (!isProcessesTabActive()) return;
  const activeSub = getActiveSubTabId();

  // Защитные фильтры изоляции опроса субпанелей:
  // if (getActiveSubTabId() !== 'manager') return;
  // if (getActiveSubTabId() !== 'top') return;
  // if (getActiveSubTabId() !== 'net') return;
  // if (getActiveSubTabId() !== 'files') return;
  // if (getActiveSubTabId() !== 'leaks') return;

  switch (activeSub) {
    case 'manager':
      await fetchProcessManagerSummary(force);
      break;
    case 'top':
      await fetchHostProcesses(force);
      break;
    case 'network-activity-by-process':
    case 'net':
      await fetchNetworkActivity(force);
      break;
    case 'files':
      await fetchLiveFileEvents(force);
      break;
    case 'leaks':
      await fetchProcessLeaks(force);
      break;
  }
}

/**
 * Останавливает все активные таймеры опроса панели.
 */
export function stopPolling() {
  if (activeSubPollerTimer) {
    clearInterval(activeSubPollerTimer);
    activeSubPollerTimer = null;
  }
  stopDeepDiveSamplePolling();
  if (window.unregisterTabPoller) {
    window.unregisterTabPoller('tab-processes-load-inspector_active');
  }
}

/**
 * Запускает цикл периодического опроса активной суб-панели.
 */
export function startPolling() {
  stopPolling();
  if (!isProcessesTabActive()) return;
  const activeSub = getActiveSubTabId();

  // Единый интервал опроса 5 секунд, привязанный к шагу сброса телеметрии в SQLite (tc_flush_interval_seconds: 5.0)
  const intervalMs = 5000;

  if (window.registerTabPoller) {
    window.registerTabPoller('tab-processes-load-inspector', async () => {
      if (!isProcessesTabActive()) return;
      const currentActive = getActiveSubTabId();
      if (currentActive !== activeSub) return;
      await fetchActiveSubTabOnly();
    }, intervalMs, { pollerId: 'tab-processes-load-inspector_active', immediate: false });
  } else {
    activeSubPollerTimer = setInterval(async () => {
      if (!isProcessesTabActive()) {
        stopPolling();
        return;
      }
      const currentActive = getActiveSubTabId();
      if (currentActive !== activeSub) {
        stopPolling();
        return;
      }
      await fetchActiveSubTabOnly();
    }, intervalMs);
  }
}

/**
 * Активирует вкладку и синхронизирует ее состояние.
 */
export async function activateTab() {
  if (!isProcessesTabActive()) return;

  const panelFromHash = getPanelFromHash();
  if (panelFromHash) {
    const currentActive = getActiveSubTabId();
    if (currentActive !== panelFromHash) {
      switchProcessesSubTab(panelFromHash, false);
      return;
    }
  } else {
    updateUrlWithPanel(getActiveSubTabId());
  }

  syncWikiLLMProcessKnowledge();
  await fetchActiveSubTabOnly(true);
  startPolling();
  adjustProcessTableHeights();

  if (typeof window !== 'undefined' && window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    window.AISmartTooltip.initAll(document.getElementById('processes-load-inspector-container') || document);
  }
}

/**
 * Автоматическая подгонка высоты контейнеров таблиц инспектора процессов.
 */
export function adjustProcessTableHeights() {
  window.autoAdjustTableHeight?.('sys-proc-table-container');
  window.autoAdjustTableHeight?.('proc-net-table-container');
  window.autoAdjustTableHeight?.('proc-watcher-table-container');
}

/**
 * Деактивирует вкладку при переходе пользователя в другой раздел.
 */
export function deactivateTab() {
  stopPolling();
}

/**
 * Программное переключение между суб-вкладками раздела процессов.
 * @param {string} subtabId - Идентификатор или алиас субвкладки.
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchProcessesSubTab(subtabId, updateUrl = true) {
  const canonical = normalizeSubTabId(subtabId);
  let btnId = 'subtab-proc-manager-btn';
  let paneId = 'subpane-proc-manager';

  switch (canonical) {
    case 'manager':
      btnId = 'subtab-proc-manager-btn';
      paneId = 'subpane-proc-manager';
      break;
    case 'top':
      btnId = 'subtab-proc-top-btn';
      paneId = 'subpane-proc-top';
      break;
    case 'network-activity-by-process':
    case 'net':
      btnId = 'subtab-proc-net-btn';
      paneId = 'subpane-proc-net';
      break;
    case 'files':
      btnId = 'subtab-proc-files-btn';
      paneId = 'subpane-proc-files';
      break;
    case 'leaks':
      btnId = 'subtab-proc-leaks-btn';
      paneId = 'subpane-proc-leaks';
      break;
  }

  stopPolling();

  const btn = document.getElementById(btnId);
  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
      tabInst.show();
    } else {
      document.querySelectorAll('#processes-subtabs-nav button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#processes-subtabs-content .tab-pane').forEach(p => {
        p.classList.remove('show', 'active');
      });
      const targetPane = document.getElementById(paneId);
      if (targetPane) {
        targetPane.classList.add('show', 'active');
      }
    }
  }

  if (updateUrl) {
    updateUrlWithPanel(canonical);
  }

  if (isProcessesTabActive()) {
    fetchActiveSubTabOnly(true);
    startPolling();
  }
}

/**
 * Инициализирует глобальные обработчики событий вкладки.
 */
function setupGlobalEventListeners() {
  document.getElementById('pm-btn-investigate-powershell')?.addEventListener('click', openPowerShellInvestigationModal);

  document.getElementById('pm-btn-prompt-settings')?.addEventListener('click', async () => {
    const modal = await resolveAIModal();
    if (modal && typeof modal.openPromptEditor === 'function') {
      modal.openPromptEditor('process', 'panel-process-manager-dispetcher-protsessov-i-prilozhen');
    }
  });

  document.getElementById('proc-top-btn-open-ai-modal')?.addEventListener('click', async () => {
    const modal = await resolveAIModal();
    if (modal && typeof modal.show === 'function') {
      modal.show({
        icon: '🤖',
        title: 'Анализ топа процессов хоста (Live Stream)',
        subtitle: 'Экспертная диагностика ресурсоемких процессов и утечек',
        panelId: 'panel-processes-load-inspector-top-protsessov-khosta-live-strea',
        tableType: 'process'
      });
    }
  });

  document.getElementById('proc-top-btn-prompt-settings')?.addEventListener('click', async () => {
    const modal = await resolveAIModal();
    if (modal && typeof modal.openPromptEditor === 'function') {
      modal.openPromptEditor('process', 'panel-processes-load-inspector-top-protsessov-khosta-live-strea');
    }
  });

  const subtabsNav = document.getElementById('processes-subtabs-nav');
  if (subtabsNav) {
    subtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {
      btn.addEventListener('shown.bs.tab', (e) => {
        const targetId = e.target.getAttribute('data-bs-target') || '';
        const canonical = normalizeSubTabId(targetId);
        updateUrlWithPanel(canonical);
        stopPolling();
        fetchActiveSubTabOnly(true);
        startPolling();
      });
    });
  }

  window.addEventListener('hashchange', () => {
    if (!isProcessesTabActive()) return;
    const targetPanel = getPanelFromHash();
    if (targetPanel && targetPanel !== getActiveSubTabId()) {
      switchProcessesSubTab(targetPanel, false);
    }
  });

  document.addEventListener('tab:activated', (e) => {
    if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'processes-load-inspector') {
      activateTab();
    }
  });

  document.addEventListener('tab:deactivated', (e) => {
    if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'processes-load-inspector') {
      deactivateTab();
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      deactivateTab();
    } else if (isProcessesTabActive()) {
      activateTab();
    }
  });

  window.addEventListener('process-ai-info:updated', () => {
    if (isProcessesTabActive()) {
      fetchActiveSubTabOnly(true);
    }
  });

  // Предотвращение блокировки aria-hidden в браузере при закрытии любых модалей
  document.addEventListener('hide.bs.modal', (e) => {
    if (document.activeElement && e.target && e.target.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  });
}

/**
 * Точка входа инициализации вкладки инспектора процессов.
 */
export async function initProcessesLoadInspectorTab() {
  if (!isInitialized) {
    syncWikiLLMProcessKnowledge();
    if (window.setupTableResizer) {
      window.setupTableResizer();
    }

    initProcessManagerPanel({
      onDrillDown: openDeepDiveModalByPid,
      onRefreshTop: fetchHostProcesses
    });
    initTopStreamPanel({
      onDrillDown: openDeepDiveModalByPid,
      onSelectProcess: (proc) => {
        openProcessAiModal(
          proc,
          'sub',
          null,
          killProcess,
          'panel-processes-load-inspector-top-protsessov-khosta-live-strea'
        );
      },
      onKillProcess: killProcess
    });
    initDeepDivePanel();
    initNetworkFilesPanel();
    initLeakHunterPanel({
      onDrillDown: openDeepDiveModalByPid
    });
    setupGlobalEventListeners();
    isInitialized = true;

    if (typeof window !== 'undefined' && window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
      window.AISmartTooltip.initAll(document.getElementById('processes-load-inspector-container') || document);
    }
  }

  if (isProcessesTabActive()) {
    await activateTab();
  } else {
    stopPolling();
  }
}

// Экспорт хуков для глобальной области видимости
window.initProcessesLoadInspectorTab = initProcessesLoadInspectorTab;
window.activateProcessesLoadInspectorTab = activateTab;
window.deactivateProcessesLoadInspectorTab = deactivateTab;
window.openDeepDiveModalByPid = openDeepDiveModalByPid;
window.openProcessAiModal = openProcessAiModal;
window.switchProcessesSubTab = switchProcessesSubTab;
window.getActiveProcessesSubTabId = getActiveSubTabId;
window.fetchActiveProcessesSubTab = fetchActiveSubTabOnly;
window.fetchProcessLeaks = fetchProcessLeaks;
window.renderProcessLeaksTable = renderProcessLeaksTable;

export {
  fetchProcessLeaks,
  renderProcessLeaksTable
};

// Автозапуск
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProcessesLoadInspectorTab);
} else {
  initProcessesLoadInspectorTab();
}
