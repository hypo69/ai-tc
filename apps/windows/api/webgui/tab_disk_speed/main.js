/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский координатор интерфейса бенчмарка дисковой подсистемы (DiskSpd).
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { copyResultsAsMarkdown } from './common/ui_utils.js';
import { checkEngineStatus, loadTargets, updateDriveDetails } from './panel_engine_targets/panel.js';
import { initChart } from './panel_results_chart/panel.js';
import { startBenchmark, cancelBenchmark } from './panel_runner_progress/panel.js';
import { loadHistory } from './panel_history/panel.js';

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};
var isTabActive = (typeof window !== 'undefined' && window.isTabActive) || function() { return true; };

let isInitialized = false;

/**
 * Инициализация вкладки бенчмарка дисков.
 */
export async function initDiskSpeedTab() {
  if (isInitialized) return;
  isInitialized = true;
  initChart();
  setupEventListeners();
  if (window.isTabActive ? window.isTabActive('tab-disk-speed') : false) {
    await checkEngineStatus();
    await loadTargets();
    await loadHistory();
  }
}

/**
 * Активация вкладки при переключении.
 */
export async function activateDiskSpeedTab() {
  await checkEngineStatus();
  await loadTargets();
  await loadHistory();
}

/**
 * Настройка событий элементов управления вкладки.
 */
function setupEventListeners() {
  const driveSelect = document.getElementById('bench-drive-select');
  if (driveSelect) {
    driveSelect.addEventListener('change', updateDriveDetails);
  }

  const refreshBtn = document.getElementById('bench-refresh-targets-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      await loadTargets();
      if (window.toast) window.toast.info('Обновлено', 'Список накопителей обновлен');
    });
  }

  const runAllBtn = document.getElementById('bench-run-all-btn');
  if (runAllBtn) {
    runAllBtn.addEventListener('click', () => {
      startBenchmark(['seq1m_q8t1', 'seq1m_q1t1', 'rnd4k_q32t16', 'rnd4k_q1t1']);
    });
  }

  const cancelBtn = document.getElementById('bench-cancel-btn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', cancelBenchmark);
  }

  // Одиночные кнопки профилей
  const pMap = {
    'bench-run-seq1m-q8': ['seq1m_q8t1'],
    'bench-run-seq1m-q1': ['seq1m_q1t1'],
    'bench-run-rnd4k-q32': ['rnd4k_q32t16'],
    'bench-run-rnd4k-q1': ['rnd4k_q1t1'],
  };

  Object.entries(pMap).forEach(([btnId, profiles]) => {
    const btn = document.getElementById(btnId);
    if (btn) {
      btn.addEventListener('click', () => startBenchmark(profiles));
    }
  });

  const copyMdBtn = document.getElementById('bench-copy-md-btn');
  if (copyMdBtn) {
    copyMdBtn.addEventListener('click', copyResultsAsMarkdown);
  }
}

// Экспорт для контейнера вкладок
window.activateDiskSpeedTab = activateDiskSpeedTab;
window.initDiskSpeedTab = initDiskSpeedTab;

// Регистрация поллера при активной вкладке tab-disk-speed
registerTabPoller('tab-disk-speed', checkEngineStatus, 15000, { immediate: false });

// Автоматический запуск при загрузке
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDiskSpeedTab);
} else {
  initDiskSpeedTab();
}
