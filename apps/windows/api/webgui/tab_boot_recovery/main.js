/**
 * =============================================================================
 * Process Name: Windows Boot Recovery & Smart Restore Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский скрипт-координатор управления интерфейсом Boot & Recovery.
 *   Объединяет панели BCD/WinRE и советника точек восстановления RestorePointAdvisor.
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_boot_recovery
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import {
  fetchBootRecoverySummary,
  executeBootAction
} from './panel_bcd_winre/panel.js';

import {
  initSmartRestorePanel,
  loadAdvisorData,
  loadAdvisorJournalData
} from './panel_smart_restore/panel.js';

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};
var isInitialized = false;

/**
 * Общая инициализация вкладки восстановления и загрузки Windows.
 */
export function initBootRecoveryTab() {
  if (isInitialized) return;
  isInitialized = true;

  const refreshBtn = document.getElementById('br-refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', fetchBootRecoverySummary);

  const winreEnableBtn = document.getElementById('br-winre-enable-btn');
  if (winreEnableBtn) winreEnableBtn.addEventListener('click', () => executeBootAction('reagentc_enable'));

  const winreInfoBtn = document.getElementById('br-winre-info-btn');
  if (winreInfoBtn) winreInfoBtn.addEventListener('click', () => executeBootAction('reagentc_info'));

  const execBtn = document.getElementById('br-execute-btn');
  if (execBtn) execBtn.addEventListener('click', () => executeBootAction());

  const clearBtn = document.getElementById('br-clear-log-btn');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    const out = document.getElementById('br-console-output');
    if (out) out.textContent = 'Консоль очищена.';
  });

  // Обработчик переключения на вкладку SFC / DISM
  const servicingSubTabBtn = document.getElementById('subtab-servicing-btn');
  if (servicingSubTabBtn) {
    servicingSubTabBtn.addEventListener('shown.bs.tab', async () => {
      if (typeof window.initServicingIntegrityTab === 'function') {
        window.initServicingIntegrityTab();
      } else {
        try {
          const mod = await import('/windows/api/webgui/tab_servicing_integrity/main.js');
          if (mod.initServicingIntegrityTab) mod.initServicingIntegrityTab();
        } catch (e) {
          console.debug('Динамическая загрузка servicing_integrity_tab:', e);
        }
      }
    });
  }

  // Обработчик переключения на субвкладку Умного восстановления
  const smartRestoreSubTabBtn = document.getElementById('subtab-smart-restore-btn');
  if (smartRestoreSubTabBtn) {
    smartRestoreSubTabBtn.addEventListener('shown.bs.tab', async () => {
      await initSmartRestorePanel();
    });
  }

  registerTabPoller('tab-boot-recovery', fetchBootRecoverySummary, 15000, { immediate: true });
}

// Экспорт для хост-контейнера вкладок
window.initBootRecoveryTab = initBootRecoveryTab;
window.initSmartRestorePanel = initSmartRestorePanel;
window.initSmartRestoreTab = initSmartRestorePanel;

export {
  fetchBootRecoverySummary,
  initSmartRestorePanel,
  loadAdvisorData,
  loadAdvisorJournalData
};
