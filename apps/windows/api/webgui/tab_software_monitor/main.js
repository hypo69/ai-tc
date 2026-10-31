/**
 * =============================================================================
 * Process Name: Windows Software Monitor - Main Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор консолидированного хаба установленного ПО.
 *   Координирует субпанели реестра, пакетных менеджеров (WinGet, Microsoft Store,
 *   Ninite), спящих программ, автозапуска, ИИ-аудита рисков, ресурсов и сокетов
 *   с поддержкой URL-маршрутизации панелей (#tab-software-monitor#<panel_id>).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script type="module" src="/windows/api/webgui/tab_software_monitor/main.js?v=20261028_v1"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_software_monitor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 16:42:00
 * =============================================================================
 */

import {
  TAB_ID,
  isSoftwareMonitorTabActive,
  getPanelFromHash,
  updateUrlWithPanel,
  normalizeSubTabId,
  setupSubTabNavigation,
  triggerSubTabInit,
  switchSoftwareSubTab
} from './panel_subtabs/panel.js';
import { triggerHeavyAnomalyAnalysis } from './panel_heavy/panel.js';
import { triggerSocketInspection } from './panel_sockets/panel.js';

let isSoftwareMonitorInitialized = false;

/**
 * Инициализирует консолидированную вкладку Установленные программы и Мониторинг ПО.
 */
export async function initSoftwareMonitorTab() {
  if (!isSoftwareMonitorInitialized) {
    setupSubTabNavigation();

    // Слушатель изменения hash в URL при активной вкладке
    window.addEventListener('hashchange', () => {
      if (!isSoftwareMonitorTabActive()) return;
      const target = getPanelFromHash();
      if (target) {
        switchSoftwareSubTab(target, false);
      }
    });

    // Активация вкладки в общем интерфейсе
    document.addEventListener('tab:activated', (e) => {
      const tid = e.detail?.tabId;
      if (tid === TAB_ID || tid === 'software-monitor' || tid === 'tab-software-scanner' || tid === 'software-scanner') {
        const target = getPanelFromHash();
        if (target) {
          switchSoftwareSubTab(target, false);
        } else {
          updateUrlWithPanel('inventory');
        }
      }
    });

    isSoftwareMonitorInitialized = true;
  }

  // Интеллектуальные тултипы ИИ (AI Smart Tooltips)
  if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    const rootEl = document.getElementById('software-monitor-container') ||
                   document.getElementById('software-scanner-container') ||
                   document;
    window.AISmartTooltip.initAll(rootEl);
  }

  // Синхронизация суб-панели с URL hash
  const panelFromHash = getPanelFromHash();
  if (panelFromHash) {
    switchSoftwareSubTab(panelFromHash, false);
  } else {
    await triggerSubTabInit('inventory');
  }
}

export const init = initSoftwareMonitorTab;
export const initSoftwareScannerTab = initSoftwareMonitorTab;

// Экспорт методов в глобальную область window
if (typeof window !== 'undefined') {
  window.initSoftwareMonitorTab = initSoftwareMonitorTab;
  window.initSoftwareScannerTab = initSoftwareMonitorTab;
  window.switchSoftwareSubTab = switchSoftwareSubTab;
  window.getSoftwarePanelFromHash = getPanelFromHash;
  window.updateSoftwareUrlWithPanel = updateUrlWithPanel;
  window.normalizeSoftwareSubTabId = normalizeSubTabId;
  window.triggerHeavyAnomalyAnalysis = triggerHeavyAnomalyAnalysis;
  window.triggerSocketInspection = triggerSocketInspection;

  window.activateSoftwareMonitorTab = function () {
    if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
      const rootEl = document.getElementById('software-monitor-container') ||
                     document.getElementById('software-scanner-container') ||
                     document;
      window.AISmartTooltip.initAll(rootEl);
    }
  };
  window.activateSoftwareScannerTab = window.activateSoftwareMonitorTab;
}

// Реэкспорт навигации субвкладок
export { switchSoftwareSubTab, getPanelFromHash, updateUrlWithPanel, normalizeSubTabId };

// Автоматический запуск при автономной загрузке
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSoftwareMonitorTab);
  } else {
    initSoftwareMonitorTab();
  }
}
