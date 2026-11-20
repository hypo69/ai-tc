/**
 * =============================================================================
 * Process Name: Windows Plugins Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский контроллер-оркестратор управления плагинами ai-tc.
 *   Координирует список плагинов, форму настроек, выполнение действий и консоль.
 *
 * File: main.js
 * Package: apps/windows/api/webgui/tab_plugins
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import {
  loadPluginsList,
  filterPluginsList,
  renderPluginsList,
  getLoadedPlugins
} from './panel_list/panel.js';
import {
  selectPlugin,
  toggleCurrentPlugin,
  saveCurrentPluginConfig,
  showPlaceholder
} from './panel_details/panel.js';
import { executePluginAction } from './panel_actions/panel.js';
import {
  clearPluginConsole,
  syncPluginTabsVisibility,
  openPluginFromDropdown
} from './panel_console_nav/panel.js';

/**
 * Инициализирует вкладку управления плагинами.
 */
export async function initPluginsTab() {
  console.log('[PluginsTab] Инициализация вкладки плагинов...');
  const searchInput = document.getElementById('plugin-search-input');
  if (searchInput) {
    searchInput.oninput = () => filterPluginsList();
  }

  const toggleSwitch = document.getElementById('plugin-toggle-switch');
  if (toggleSwitch) {
    toggleSwitch.onchange = (e) => toggleCurrentPlugin(e.target.checked);
  }

  const saveBtn = document.getElementById('btn-save-plugin-config');
  if (saveBtn) {
    saveBtn.onclick = () => saveCurrentPluginConfig();
  }

  const clearBtn = document.getElementById('btn-clear-plugin-console');
  if (clearBtn) {
    clearBtn.onclick = () => clearPluginConsole();
  }

  await loadPluginsList(selectPlugin, showPlaceholder);
}

// Экспорт методов для inline HTML обработчиков и глобального контекста
window.initPluginsTab = initPluginsTab;
window.loadPluginsList = () => loadPluginsList(selectPlugin, showPlaceholder);
window.filterPluginsList = filterPluginsList;
window.selectPlugin = selectPlugin;
window.toggleCurrentPlugin = toggleCurrentPlugin;
window.saveCurrentPluginConfig = saveCurrentPluginConfig;
window.executePluginAction = (pluginName, actionId, actionLabel) => executePluginAction(pluginName, actionId, actionLabel, getLoadedPlugins());
window.clearPluginConsole = clearPluginConsole;
window.syncPluginTabsVisibility = syncPluginTabsVisibility;
window.openPluginFromDropdown = openPluginFromDropdown;

// Автозапуск при обнаружении вкладки в DOM
if (document.getElementById('tab-plugins') || document.getElementById('plugins-list-container')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initPluginsTab());
  } else {
    setTimeout(() => initPluginsTab(), 10);
  }
}
