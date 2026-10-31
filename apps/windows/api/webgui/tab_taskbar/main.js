/**
 * =============================================================================
 * Process Name: Windows Taskbar Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский контроллер-оркестратор интерактивного управления панелью задач,
 *   окнами, запуском приложений, прогресс-барами ITaskbarList3 и историей Rollback.
 *
 * File: main.js
 * Package: apps/windows/api/webgui/tab_taskbar
 * Updated: 2026-10-31 15:55:00
 * =============================================================================
 */

import { loadSummary } from './panel_summary/panel.js';
import {
  loadWindows,
  renderWindowsTable,
  openTaskbarWindowCopilotModal,
  executeBatchWindowAction
} from './panel_windows/panel.js';
import {
  loadSettings,
  saveTaskbarSettings,
  restartExplorer,
  bindTaskbarSettingsEvents
} from './panel_settings/panel.js';
import { loadPinnedApps, handleLaunchApp } from './panel_pinned_apps/panel.js';
import { handleApplyUxProgress } from './panel_ux_progress/panel.js';
import {
  loadHistory,
  renderHistoryTable,
  rollbackAction,
  rollbackLast,
  loadCommandCatalog,
  renderCommandsTable,
  executeCommandDirect
} from './panel_history_catalog/panel.js';

/**
 * Полное обновление всех панелей вкладки.
 */
export async function refreshAll() {
  await Promise.all([
    loadSummary(),
    loadWindows(),
    loadSettings(),
    loadPinnedApps(),
    loadHistory(),
    loadCommandCatalog(),
  ]);
}

/**
 * Привязка обработчиков событий к элементам интерфейса.
 */
function bindEvents() {
  document.getElementById('btn-refresh-taskbar-data')?.addEventListener('click', () => refreshAll());
  document.getElementById('btn-restart-explorer-quick')?.addEventListener('click', () => restartExplorer());
  document.getElementById('btn-rollback-last-quick')?.addEventListener('click', () => rollbackLast(refreshAll));
  document.getElementById('btn-refresh-history')?.addEventListener('click', () => loadHistory());
  document.getElementById('input-search-windows')?.addEventListener('input', () => renderWindowsTable());
  document.getElementById('btn-batch-minimize-all')?.addEventListener('click', () => executeBatchWindowAction('minimize_all', refreshAll));
  document.getElementById('btn-batch-restore-all')?.addEventListener('click', () => executeBatchWindowAction('restore_all', refreshAll));
  document.getElementById('form-taskbar-settings')?.addEventListener('submit', (e) => saveTaskbarSettings(e, refreshAll));
  bindTaskbarSettingsEvents(refreshAll);
  document.getElementById('form-launch-app')?.addEventListener('submit', (e) => handleLaunchApp(e, refreshAll));
  document.getElementById('btn-refresh-pinned')?.addEventListener('click', () => loadPinnedApps());

  const range = document.getElementById('range-ux-progress');
  const label = document.getElementById('label-progress-val');
  if (range && label) {
    range.addEventListener('input', () => { label.textContent = `${range.value}%`; });
  }
  document.getElementById('btn-apply-ux-progress')?.addEventListener('click', () => handleApplyUxProgress(loadHistory));

  document.getElementById('filter-cmd-category')?.addEventListener('change', () => renderCommandsTable());
  document.getElementById('filter-cmd-risk')?.addEventListener('change', () => renderCommandsTable());
}

/**
 * Инициализация вкладки Taskbar.
 */
export async function init() {
  bindEvents();
  await refreshAll();
}

// Глобальные действия над окнами для HTML inline onclick
window._taskbarActions = {
  aiCopilot: async (hwnd) => {
    await openTaskbarWindowCopilotModal(hwnd);
  },
  activate: async (hwnd) => {
    await fetch(`/api/v1/taskbar/windows/${hwnd}/activate`, { method: 'POST' });
    await loadWindows();
    await loadHistory();
  },
  minimize: async (hwnd) => {
    await fetch(`/api/v1/taskbar/windows/${hwnd}/minimize`, { method: 'POST' });
    await loadWindows();
    await loadHistory();
  },
  maximize: async (hwnd) => {
    await fetch(`/api/v1/taskbar/windows/${hwnd}/maximize`, { method: 'POST' });
    await loadWindows();
    await loadHistory();
  },
  restore: async (hwnd) => {
    await fetch(`/api/v1/taskbar/windows/${hwnd}/restore`, { method: 'POST' });
    await loadWindows();
    await loadHistory();
  },
  close: async (hwnd) => {
    await fetch(`/api/v1/taskbar/windows/${hwnd}`, { method: 'DELETE' });
    await loadWindows();
    await loadHistory();
  }
};

window._rollbackAction = (historyId) => rollbackAction(historyId, refreshAll);
window._executeCommandDirect = (cmdId) => executeCommandDirect(cmdId, loadHistory);
window.initTaskbarTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => init());
} else {
  init();
}
