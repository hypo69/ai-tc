/**
 * =============================================================================
 * Process Name: Windows Backup Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Модульный клиентский оркестратор вкладки резервного копирования и данных:
 *   координирует индекс готовности, библиотеки Windows, семантический поиск
 *   File History RAG, мастер перемещения пользовательских папок, VSS и аудит удалений.
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import {
  loadHealthReport,
  loadFileHistoryStatus,
  bindOverviewEvents,
} from './panel_overview/panel.js';
import { loadLibraries, bindLibrariesEvents } from './panel_libraries/panel.js';
import { bindRagEvents } from './panel_rag/panel.js';
import {
  loadUserFoldersOverview,
  bindUserFoldersEvents,
} from './panel_user_folders/panel.js';
import {
  loadVssSnapshots,
  loadFileDeletions,
  bindVssAuditEvents,
} from './panel_vss_audit/panel.js';

/**
 * Загрузка всех данных вкладки резервного копирования.
 * @returns {Promise<void>}
 */
export async function loadBackupData() {
  await Promise.allSettled([
    loadHealthReport(),
    loadLibraries(),
    loadFileHistoryStatus(),
    loadUserFoldersOverview(),
    loadVssSnapshots(),
    loadFileDeletions()
  ]);
}

/**
 * Привязка переключения подвкладок и общих обработчиков событий.
 */
function bindEvents() {
  const subTabButtons = document.querySelectorAll('#wbSubTabs button[data-bs-toggle="tab"]');
  subTabButtons.forEach(btn => {
    btn.onclick = (e) => {
      e.preventDefault();
      const targetSelector = btn.getAttribute('data-bs-target');
      if (!targetSelector) return;

      subTabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const panes = document.querySelectorAll('#wbTabContent .tab-pane');
      panes.forEach(p => p.classList.remove('show', 'active'));

      const targetPane = document.querySelector(targetSelector);
      if (targetPane) {
        targetPane.classList.add('show', 'active');
      }
    };
  });

  const btnRefresh = document.getElementById('wb-btn-refresh');
  if (btnRefresh && !btnRefresh._bound) {
    btnRefresh._bound = true;
    btnRefresh.onclick = () => loadBackupData();
  }

  bindOverviewEvents();
  bindLibrariesEvents();
  bindRagEvents();
  bindUserFoldersEvents();
  bindVssAuditEvents();
}

/**
 * Инициализация вкладки резервного копирования и управления хранилищем Windows.
 * @returns {Promise<void>}
 */
export async function initWindowsBackupTab() {
  console.log('[WindowsBackup] Initializing tab...');
  bindEvents();
  await loadBackupData();
}

// Экспорт глобальных методов для внешней навигации и совместимости
window.initWindowsBackupTab = initWindowsBackupTab;
window.loadBackupData = loadBackupData;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWindowsBackupTab);
} else {
  initWindowsBackupTab();
}
