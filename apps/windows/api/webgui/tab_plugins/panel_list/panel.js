/**
 * Модуль панели списка плагинов и фильтрации каталога.
 * Файл: apps/windows/api/webgui/tab_plugins/panel_list/panel.js
 * Updated: 2026-11-20 16:45:00
 */

import { isRunningInUserInterface } from '../common/ui_utils.js';
import { syncPluginTabsVisibility } from '../panel_console_nav/panel.js';

let loadedPlugins = [];
let selectedPluginName = '';

/**
 * Возвращает текущий список загруженных плагинов.
 * @returns {Array<Object>}
 */
export function getLoadedPlugins() {
  return loadedPlugins;
}

/**
 * Устанавливает текущий список плагинов.
 * @param {Array<Object>} plugins
 */
export function setLoadedPlugins(plugins) {
  loadedPlugins = plugins || [];
}

/**
 * Возвращает имя выбранного плагина.
 * @returns {string}
 */
export function getSelectedPluginName() {
  return selectedPluginName;
}

/**
 * Устанавливает имя выбранного плагина.
 * @param {string} name
 */
export function setSelectedPluginName(name) {
  selectedPluginName = name;
}

/**
 * Загружает список плагинов с бэкенда.
 * @param {Function} onSelectPlugin - Коллбек выбора плагина.
 * @param {Function} onShowPlaceholder - Коллбек скрытия деталей.
 */
export async function loadPluginsList(onSelectPlugin, onShowPlaceholder) {
  const container = document.getElementById('plugins-list-container');
  if (!container) return;

  try {
    const isUserUI = isRunningInUserInterface();
    const endpoint = isUserUI ? '/api/v1/plugins?scope=user' : '/api/v1/admin/plugins';

    let data;
    if (window.api && typeof window.api.fetch === 'function') {
      try {
        data = await window.api.fetch(endpoint);
      } catch {
        data = await window.api.fetch('/api/v1/admin/plugins');
      }
    } else {
      let resp = await fetch(endpoint);
      if (!resp.ok && isUserUI) {
        resp = await fetch('/api/v1/admin/plugins?scope=user');
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    }

    let plugins = data?.plugins || [];
    if (isUserUI) {
      plugins = plugins.filter(p => !p.is_system && p.scope !== 'system');
    }
    loadedPlugins = plugins;

    const countEl = document.getElementById('plugins-count');
    if (countEl) countEl.textContent = loadedPlugins.length;
    const activeCount = loadedPlugins.filter(p => p.enabled).length;
    const badgeEl = document.getElementById('active-plugins-badge');
    if (badgeEl) badgeEl.textContent = `${activeCount} активных`;

    renderPluginsList(loadedPlugins);
    syncPluginTabsVisibility(loadedPlugins);

    if (loadedPlugins.length > 0) {
      const toSelect = loadedPlugins.find(p => p.name === selectedPluginName) || loadedPlugins[0];
      if (onSelectPlugin) onSelectPlugin(toSelect.name);
    } else {
      if (onShowPlaceholder) onShowPlaceholder();
    }
  } catch (ex) {
    console.error('[PluginsTab] Ошибка загрузки плагинов:', ex);
    container.innerHTML = `<div class="alert alert-danger m-2 small">Ошибка загрузки плагинов: ${ex.message}</div>`;
  }
}

/**
 * Отрисовывает список плагинов в сайдбаре.
 * @param {Array<Object>} plugins - Список плагинов.
 */
export function renderPluginsList(plugins) {
  const container = document.getElementById('plugins-list-container');
  if (!container) return;

  if (plugins.length === 0) {
    const isUserUI = isRunningInUserInterface();
    const emptyMsg = isUserUI ? 'Пользовательские плагины не найдены' : 'Плагины не найдены';
    container.innerHTML = `<div class="text-center text-muted p-3 small">${emptyMsg}</div>`;
    return;
  }

  let html = '<div class="list-group list-group-flush">';
  plugins.forEach(p => {
    const isSelected = p.name === selectedPluginName;
    const statusBadge = p.enabled 
      ? '<span class="badge bg-success-subtle text-success border border-success-subtle small">Вкл</span>'
      : '<span class="badge bg-secondary-subtle text-muted border small">Выкл</span>';
    const typeBadge = p.is_system
      ? '<span class="badge bg-secondary-subtle text-body-secondary border small">Системный</span>'
      : '<span class="badge bg-info-subtle text-info-emphasis border small">Пользовательский</span>';

    html += `
      <a href="javascript:void(0)" 
         class="list-group-item list-group-item-action p-2 rounded mb-1 border-0 ${isSelected ? 'active text-white' : ''}" 
         onclick="window.selectPlugin('${p.name}')"
         style="cursor: pointer;">
        <div class="d-flex w-100 justify-content-between align-items-center mb-1">
          <div class="d-flex align-items-center gap-2 text-truncate">
            <span class="fs-5">${p.icon || '🧩'}</span>
            <strong class="text-truncate">${p.title || p.name}</strong>
          </div>
          <div class="d-flex align-items-center gap-1">${typeBadge}${statusBadge}</div>
        </div>
        <div class="small text-truncate ${isSelected ? 'text-white-50' : 'text-muted'}">
          ${p.description || p.name}
        </div>
      </a>
    `;
  });
  html += '</div>';
  container.innerHTML = html;
}

/**
 * Фильтрует список плагинов по значению строки поиска.
 */
export function filterPluginsList() {
  const query = (document.getElementById('plugin-search-input')?.value || '').toLowerCase().trim();
  if (!query) {
    renderPluginsList(loadedPlugins);
    return;
  }
  const filtered = loadedPlugins.filter(p => 
    (p.name || '').toLowerCase().includes(query) || 
    (p.title && p.title.toLowerCase().includes(query)) ||
    (p.description && p.description.toLowerCase().includes(query))
  );
  renderPluginsList(filtered);
}
