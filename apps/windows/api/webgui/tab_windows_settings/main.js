/**
 * =============================================================================
 * Process Name: Windows Settings Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Модульный клиентский оркестратор единой панели управления пользовательскими
 *   настройками Windows (295 параметров): X-Mouse, специальные возможности,
 *   каталог параметров, SafeOps предпросмотр, журнал аудита и откат.
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state } from './common/ui_utils.js';
import { initDesktopDisplays, refreshDesktopState } from './desktop_displays.js';
import { loadQuickSettings, bindQuickSettingsEvents } from './panel_quick_settings/panel.js';
import { loadCatalogSettings, renderFilteredSettings } from './panel_catalog/panel.js';
import { confirmModalApply } from './panel_modal_safeops/panel.js';
import {
  loadHistory,
  rollbackLastSetting,
  winsetRollbackItem,
} from './panel_history/panel.js';

/**
 * Подключение обработчиков событий элементов UI.
 */
function bindEventListeners() {
  bindQuickSettingsEvents();

  // Кнопка обновления всех параметров
  const btnRefresh = document.getElementById('winset-btn-refresh-all');
  if (btnRefresh && !btnRefresh._bound) {
    btnRefresh._bound = true;
    btnRefresh.onclick = async () => {
      const spinner = document.getElementById('winset-refresh-spinner');
      if (spinner) spinner.classList.add('spin-animation');
      await refreshDesktopState();
      await loadQuickSettings();
      await loadCatalogSettings();
      if (spinner) spinner.classList.remove('spin-animation');
    };
  }

  // Быстрый откат последнего изменения
  const btnRollbackLast = document.getElementById('winset-btn-rollback-last');
  if (btnRollbackLast && !btnRollbackLast._bound) {
    btnRollbackLast._bound = true;
    btnRollbackLast.onclick = rollbackLastSetting;
  }

  // Навигация по категориям
  const categoryTabs = document.getElementById('winset-category-tabs');
  if (categoryTabs && !categoryTabs._bound) {
    categoryTabs._bound = true;
    categoryTabs.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-category]');
      if (!btn) return;
      categoryTabs.querySelectorAll('.nav-link').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentCategory = btn.getAttribute('data-category');

      const catalogContainer = document.getElementById('winset-catalog-container');
      const historyContainer = document.getElementById('winset-history-container');

      if (state.currentCategory === 'history') {
        if (catalogContainer) catalogContainer.classList.add('d-none');
        if (historyContainer) historyContainer.classList.remove('d-none');
        loadHistory();
      } else {
        if (historyContainer) historyContainer.classList.add('d-none');
        if (catalogContainer) catalogContainer.classList.remove('d-none');
        renderFilteredSettings();
      }
    });
  }

  // Поиск и фильтрация
  const searchInput = document.getElementById('winset-search-input');
  const btnClearSearch = document.getElementById('winset-btn-clear-search');
  const filterRisk = document.getElementById('winset-filter-risk');
  const filterBackend = document.getElementById('winset-filter-backend');

  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.oninput = () => renderFilteredSettings();
  }
  if (btnClearSearch && searchInput && !btnClearSearch._bound) {
    btnClearSearch._bound = true;
    btnClearSearch.onclick = () => {
      searchInput.value = '';
      renderFilteredSettings();
    };
  }
  if (filterRisk && !filterRisk._bound) {
    filterRisk._bound = true;
    filterRisk.onchange = () => renderFilteredSettings();
  }
  if (filterBackend && !filterBackend._bound) {
    filterBackend._bound = true;
    filterBackend.onchange = () => renderFilteredSettings();
  }

  // Модальное окно подтверждения
  const btnModalConfirm = document.getElementById('winset-btn-modal-confirm');
  if (btnModalConfirm && !btnModalConfirm._bound) {
    btnModalConfirm._bound = true;
    btnModalConfirm.onclick = confirmModalApply;
  }
}

/**
 * Инициализация вкладки Windows Settings.
 * @returns {Promise<void>}
 */
export async function initWindowsSettingsTab() {
  console.log('[WindowsSettingsTab] Инициализация вкладки пользовательских настроек...');
  bindEventListeners();
  await initDesktopDisplays();
  await loadQuickSettings();
  await loadCatalogSettings();
}

// Экспорт для глобального доступа в оболочке
window.initWindowsSettingsTab = initWindowsSettingsTab;
window.winsetRollbackItem = winsetRollbackItem;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWindowsSettingsTab);
} else {
  initWindowsSettingsTab();
}
