import {
  initCodebaseRagPanel,
  loadCodebaseIndexes,
  bindCodebaseRagButtons,
  executeDiagnose,
  executeBuildIndex,
  executeSymbolSearch,
  executeCodeSearch,
} from './panel_codebase_rag/panel.js?v=20261031_v6';
import {
  initHelpPagesEditor,
  bindEditorButtons,
  loadHelpCatalog,
  openFile,
  saveCurrentFile,
  previewCurrentFile,
} from './panel_helppages_editor/panel.js?v=20261031_v1';
import {
  initTooltipsEditorPanel,
} from './panel_tooltips_editor/panel.js?v=20261031_v1';
/**
 * =============================================================================
 * Process Name: Windows App Internals Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Модульный клиентский оркестратор консолидированной панели «Внутренняя кухня».
 *   Координирует суб-панели телеметрии, моделей, логов, ETW-трассировки,
 *   системных настроек, базы знаний подсказок по системе (локальный SQLite)
 *   и базы инструментов агента (сервер Hostinger) с поддержкой двухуровневой
 *   URL-маршрутизации (#tab-app-internals#<panel_id>#block-<block_id>).
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 19:45:00
 * =============================================================================
 */

import {
  initSubtabsPanel,
  switchAppInternalsSubTab,
  switchAppInternalsBlock,
  triggerSubTabInit,
} from './panel_subtabs/panel.js?v=20261031_v5';
import {
  TAB_ID,
  isAppInternalsTabActive,
  normalizeSubTabId,
  normalizeBlockId,
  getActiveSubTabId,
  getActiveBlockId,
  getPanelFromHash,
  getBlockFromHash,
  updateUrlWithPanel,
} from './common/ui_utils.js?v=20261031_v5';
import {
  initWikiLLMSettingsPanel,
  bindWikiLLMButtons,
  loadWikiLLMSettings,
  initWikiLLMEditor,
} from './panel_wikillm_settings/panel.js?v=20261031_v4';
import {
  initWikiLLMDbPanel,
  bindWikiLLMDbButtons,
  loadWikiLLMDbConfig,
} from './panel_wikillm_db/panel.js?v=20261031_v4';
import {
  initInstrumentsDbPanel,
  bindInstrumentsDbButtons,
  loadInstrumentsDbConfig,
  bindInstrumentsRuntimeButtons,
  loadInstrumentsRuntimeConfig,
  bindInstrumentsCatalogButtons,
  loadInstrumentsCatalog,
  openInstrumentEditorModal,
  saveInstrumentFromModal,
} from './panel_instruments_db/panel.js?v=20261031_v5';

let isAppInternalsInitialized = false;

/**
 * Обновление данных и компонентов суб-вкладок баз данных и WikiLLM.
 * @returns {Promise<void>}
 */
export async function refreshWikiLLMSubtab() {
  bindWikiLLMDbButtons();
  await loadWikiLLMDbConfig();
  bindInstrumentsDbButtons();
  await loadInstrumentsDbConfig();
  bindInstrumentsRuntimeButtons();
  await loadInstrumentsRuntimeConfig();
  bindInstrumentsCatalogButtons();
  await loadInstrumentsCatalog();
  bindWikiLLMButtons();
  await loadWikiLLMSettings();
  await initWikiLLMEditor();
}

/**
 * Главная инициализация вкладки «Внутренняя кухня».
 * @returns {Promise<void>}
 */
export async function initAppInternalsTab() {
  if (isAppInternalsInitialized) return;
  isAppInternalsInitialized = true;

  await initSubtabsPanel();

  // Опрашиваем API ТОЛЬКО для активной панели и блока
  const activePanel = getPanelFromHash() || getActiveSubTabId() || 'telemetry';
  const activeBlock = getBlockFromHash(activePanel);
  switchAppInternalsSubTab(activePanel, activeBlock, false);
  if (!getPanelFromHash()) {
    updateUrlWithPanel(activePanel, activeBlock);
  }

  // Реакция на изменение hash в URL при активной вкладке
  window.addEventListener('hashchange', () => {
    if (!isAppInternalsTabActive()) return;
    const targetPanel = getPanelFromHash();
    const targetBlock = getBlockFromHash(targetPanel || '');
    if (targetPanel) {
      switchAppInternalsSubTab(targetPanel, targetBlock, false);
    }
  });

  // Событие активации вкладки в общем интерфейсе
  document.addEventListener('tab:activated', (e) => {
    if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'app-internals') {
      const targetPanel = getPanelFromHash() || getActiveSubTabId();
      const targetBlock = getBlockFromHash(targetPanel);
      if (targetPanel) {
        switchAppInternalsSubTab(targetPanel, targetBlock, false);
      } else {
        updateUrlWithPanel(getActiveSubTabId(), getActiveBlockId(getActiveSubTabId()));
      }
    }
  });
}

// Экспорт глобальных методов для внешней навигации и суб-вкладок
export function activateAppInternalsTab() {
  const targetPanel = getPanelFromHash() || getActiveSubTabId() || 'telemetry';
  const targetBlock = getBlockFromHash(targetPanel);
  switchAppInternalsSubTab(targetPanel, targetBlock, false);
}

window.activateAppInternalsTab = activateAppInternalsTab;
window.initAppInternalsTab = initAppInternalsTab;
window.switchAppInternalsSubTab = switchAppInternalsSubTab;
window.switchAppInternalsBlock = switchAppInternalsBlock;
window.getActiveAppInternalsSubTabId = getActiveSubTabId;
window.getActiveAppInternalsBlockId = getActiveBlockId;
window.getAppInternalsPanelFromHash = getPanelFromHash;
window.getAppInternalsBlockFromHash = getBlockFromHash;
window.updateAppInternalsUrlWithPanel = updateUrlWithPanel;
window.normalizeAppInternalsSubTabId = normalizeSubTabId;
window.normalizeAppInternalsBlockId = normalizeBlockId;
window.refreshWikiLLMSubtab = refreshWikiLLMSubtab;
window.bindWikiLLMDbButtons = bindWikiLLMDbButtons;
window.loadWikiLLMDbConfig = loadWikiLLMDbConfig;
window.bindInstrumentsDbButtons = bindInstrumentsDbButtons;
window.loadInstrumentsDbConfig = loadInstrumentsDbConfig;
window.bindInstrumentsRuntimeButtons = bindInstrumentsRuntimeButtons;
window.loadInstrumentsRuntimeConfig = loadInstrumentsRuntimeConfig;
window.bindInstrumentsCatalogButtons = bindInstrumentsCatalogButtons;
window.loadInstrumentsCatalog = loadInstrumentsCatalog;
window.openInstrumentEditorModal = openInstrumentEditorModal;
window.saveInstrumentFromModal = saveInstrumentFromModal;
window.bindWikiLLMButtons = bindWikiLLMButtons;
window.loadWikiLLMSettings = loadWikiLLMSettings;
window.initWikiLLMEditor = initWikiLLMEditor;
window.initHelpPagesEditor = initHelpPagesEditor;
window.bindHelpEditorButtons = bindEditorButtons;
window.loadHelpCatalog = loadHelpCatalog;
window.openHelpFile = openFile;
window.saveCurrentHelpFile = saveCurrentFile;
window.previewCurrentHelpFile = previewCurrentFile;
window.initTooltipsEditorPanel = initTooltipsEditorPanel;
window.initCodebaseRagPanel = initCodebaseRagPanel;
window.loadCodebaseIndexes = loadCodebaseIndexes;
window.bindCodebaseRagButtons = bindCodebaseRagButtons;
window.executeDiagnose = executeDiagnose;
window.executeBuildIndex = executeBuildIndex;
window.executeSymbolSearch = executeSymbolSearch;
window.executeCodeSearch = executeCodeSearch;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAppInternalsTab);
} else {
  initAppInternalsTab();
}
