/**
 * Модуль панели подробных сведений, переключения активности и сохранения настроек плагина.
 * Файл: apps/windows/api/webgui/tab_plugins/panel_details/panel.js
 * Updated: 2026-11-20 16:45:00
 */

import { showPluginNotification } from '../common/ui_utils.js';
import { logToPluginConsole, syncPluginTabsVisibility } from '../panel_console_nav/panel.js';
import { renderPluginActions } from '../panel_actions/panel.js';
import { renderPluginFields } from '../panel_config_fields/panel.js';
import {
  getLoadedPlugins,
  getSelectedPluginName,
  setSelectedPluginName,
  renderPluginsList,
  loadPluginsList
} from '../panel_list/panel.js';

/**
 * Скрывает область контента и показывает заглушку отсутствия выбора.
 */
export function showPlaceholder() {
  const placeholder = document.getElementById('plugin-placeholder');
  const contentPane = document.getElementById('plugin-content-pane');
  if (placeholder) placeholder.classList.remove('d-none');
  if (contentPane) contentPane.classList.add('d-none');
}

/**
 * Выбирает плагин по имени и отрисовывает его параметры.
 * @param {string} pluginName - Имя плагина.
 */
export function selectPlugin(pluginName) {
  if (!pluginName) return;
  setSelectedPluginName(pluginName);
  const loadedPlugins = getLoadedPlugins();

  const normalized = pluginName.toLowerCase().replace(/-/g, '_');
  const plugin = loadedPlugins.find(p => {
    const pName = (p.name || '').toLowerCase().replace(/-/g, '_');
    const pId = (p.id || '').toLowerCase().replace(/-/g, '_');
    const pTitle = (p.title || '').toLowerCase();
    return pName === normalized || pId === normalized || pTitle === pluginName.toLowerCase();
  });

  if (!plugin) {
    if (!loadedPlugins || loadedPlugins.length === 0) {
      loadPluginsList(selectPlugin, showPlaceholder).then(() => {
        const currentLoaded = getLoadedPlugins();
        if (currentLoaded && currentLoaded.length > 0) {
          const pFound = currentLoaded.find(p => {
            const pName = (p.name || '').toLowerCase().replace(/-/g, '_');
            const pId = (p.id || '').toLowerCase().replace(/-/g, '_');
            const pTitle = (p.title || '').toLowerCase();
            return pName === normalized || pId === normalized || pTitle === pluginName.toLowerCase();
          });
          if (pFound) selectPlugin(pFound.name);
        }
      });
    }
    return;
  }

  renderPluginsList(loadedPlugins);

  const placeholder = document.getElementById('plugin-placeholder');
  const contentPane = document.getElementById('plugin-content-pane');
  if (placeholder) placeholder.classList.add('d-none');
  if (contentPane) contentPane.classList.remove('d-none');

  // Шапка карточки плагина
  const iconEl = document.getElementById('plugin-icon');
  if (iconEl) iconEl.textContent = plugin.icon || '🧩';
  const titleEl = document.getElementById('plugin-title');
  if (titleEl) titleEl.textContent = plugin.title || plugin.name;
  const verEl = document.getElementById('plugin-version');
  if (verEl) verEl.textContent = `v${plugin.version || '1.0.0'}`;
  const catEl = document.getElementById('plugin-category');
  if (catEl) catEl.textContent = plugin.category || 'tools';
  const idEl = document.getElementById('plugin-id');
  if (idEl) idEl.textContent = `id: ${plugin.name}`;
  const descEl = document.getElementById('plugin-description');
  if (descEl) descEl.textContent = plugin.description || 'Нет описания';

  const scopeBadgeEl = document.getElementById('plugin-scope-badge');
  if (scopeBadgeEl) {
    if (plugin.is_system) {
      scopeBadgeEl.textContent = 'Системный';
      scopeBadgeEl.className = 'badge bg-secondary-subtle text-body-secondary border';
    } else {
      scopeBadgeEl.textContent = 'Пользовательский';
      scopeBadgeEl.className = 'badge bg-info-subtle text-info-emphasis border';
    }
  }

  const isAdmin = (typeof window.isUserAdmin === 'function') ? window.isUserAdmin() : false;
  const isLocked = Boolean(plugin.is_system && !isAdmin);

  const toggleSwitch = document.getElementById('plugin-toggle-switch');
  if (toggleSwitch) {
    toggleSwitch.checked = Boolean(plugin.enabled);
    toggleSwitch.disabled = isLocked;
    toggleSwitch.title = isLocked 
      ? 'Системный плагин управляется администратором' 
      : 'Включить / отключить плагин';
  }

  const saveBtn = document.getElementById('btn-save-plugin-config');
  if (saveBtn) {
    saveBtn.disabled = isLocked;
    saveBtn.title = isLocked ? 'Настройки системного плагина изменяются только администратором' : '';
  }

  renderPluginActions(plugin);
  renderPluginFields(plugin);
}

/**
 * Переключает состояние активности текущего плагина.
 * @param {boolean} enabled - Флаг включения.
 */
export async function toggleCurrentPlugin(enabled) {
  const selectedPluginName = getSelectedPluginName();
  if (!selectedPluginName) return;

  try {
    logToPluginConsole(`Переключение плагина '${selectedPluginName}' -> ${enabled ? 'ВКЛ' : 'ВЫКЛ'}...`);
    const endpoint = `/api/v1/admin/plugins/${selectedPluginName}/toggle`;
    let res;
    if (window.api && typeof window.api.fetch === 'function') {
      res = await window.api.fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
    } else {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      res = await resp.json();
    }

    const loadedPlugins = getLoadedPlugins();
    const plugin = loadedPlugins.find(p => p.name === selectedPluginName);
    if (plugin) {
      plugin.enabled = enabled;
    }

    renderPluginsList(loadedPlugins);
    syncPluginTabsVisibility(loadedPlugins);
    showPluginNotification(res.message || 'Статус плагина обновлен', 'success');
    logToPluginConsole(`✓ ${res.message || 'Статус успешно обновлен'}`);
  } catch (ex) {
    console.error('[PluginsTab] Ошибка переключения плагина:', ex);
    showPluginNotification(`Ошибка: ${ex.message}`, 'danger');
    logToPluginConsole(`✗ Ошибка: ${ex.message}`);
    const toggleSwitch = document.getElementById('plugin-toggle-switch');
    if (toggleSwitch) toggleSwitch.checked = !enabled;
  }
}

/**
 * Сохраняет измененную конфигурацию плагина.
 */
export async function saveCurrentPluginConfig() {
  const selectedPluginName = getSelectedPluginName();
  if (!selectedPluginName) return;

  const form = document.getElementById('plugin-config-form');
  if (!form) return;

  const newConfig = {};
  const elements = form.querySelectorAll('[data-field-type]');

  elements.forEach(el => {
    const name = el.getAttribute('name');
    if (!name) return;
    const type = el.getAttribute('data-field-type');

    if (type === 'boolean') {
      newConfig[name] = el.checked;
    } else if (type === 'number') {
      newConfig[name] = Number(el.value);
    } else if (type === 'list_string') {
      newConfig[name] = el.value.split(',').map(s => s.trim()).filter(Boolean);
    } else {
      newConfig[name] = el.value;
    }
  });

  try {
    logToPluginConsole(`Сохранение параметров плагина '${selectedPluginName}'...`);
    const endpoint = `/api/v1/admin/plugins/${selectedPluginName}/config`;
    let res;
    if (window.api && typeof window.api.fetch === 'function') {
      res = await window.api.fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: newConfig })
      });
    } else {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: newConfig })
      });
      res = await resp.json();
    }

    const loadedPlugins = getLoadedPlugins();
    const plugin = loadedPlugins.find(p => p.name === selectedPluginName);
    if (plugin) {
      plugin.config = res.config || newConfig;
    }

    showPluginNotification('Параметры успешно сохранены', 'success');
    logToPluginConsole(`✓ Конфигурация сохранена: ${JSON.stringify(newConfig, null, 2)}`);
  } catch (ex) {
    console.error('[PluginsTab] Ошибка сохранения конфигурации:', ex);
    showPluginNotification(`Ошибка: ${ex.message}`, 'danger');
    logToPluginConsole(`✗ Ошибка сохранения: ${ex.message}`);
  }
}
