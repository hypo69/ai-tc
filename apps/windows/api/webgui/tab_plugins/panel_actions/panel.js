/**
 * Модуль панели действий (Actions) выбранного плагина.
 * Файл: apps/windows/api/webgui/tab_plugins/panel_actions/panel.js
 * Updated: 2026-11-20 16:45:00
 */

import { showPluginNotification } from '../common/ui_utils.js';
import { logToPluginConsole } from '../panel_console_nav/panel.js';

/**
 * Отрисовывает доступные действия (кнопки) для плагина.
 * @param {Object} plugin - Объект плагина.
 */
export function renderPluginActions(plugin) {
  const container = document.getElementById('plugin-actions-container');
  const section = document.getElementById('plugin-actions-section');
  if (!container || !section) return;

  const actions = plugin?.actions || [];
  if (actions.length === 0) {
    section.classList.add('d-none');
    return;
  }

  section.classList.remove('d-none');
  let html = '';
  actions.forEach(act => {
    const btnColor = act.color || 'primary';
    const label = act.label || act.name || act.id;
    const icon = act.icon ? `<span class="me-1">${act.icon}</span>` : '';
    const safeLabel = label.replace(/'/g, "\\'");
    html += `
      <button class="btn btn-sm btn-outline-${btnColor} d-inline-flex align-items-center gap-1 shadow-sm"
              onclick="window.executePluginAction('${plugin.name}', '${act.id}', '${safeLabel}')"
              title="${act.description || ''}">
        ${icon}<span>${label}</span>
      </button>
    `;
  });
  container.innerHTML = html;
}

/**
 * Выполняет действие (Action) плагина через REST API.
 * @param {string} pluginName - Имя плагина.
 * @param {string} actionId - Идентификатор действия.
 * @param {string} actionLabel - Человекочитаемая метка действия.
 * @param {Array<Object>} [loadedPlugins=[]] - Список плагинов для проверки параметров.
 */
export async function executePluginAction(pluginName, actionId, actionLabel, loadedPlugins = []) {
  try {
    logToPluginConsole(`[ACTION] Запуск '${actionLabel}' для плагина '${pluginName}'...`);
    showPluginNotification(`Запуск '${actionLabel}'...`, 'info');

    const form = document.getElementById('plugin-config-form');
    const params = {};
    if (form) {
      const elements = form.querySelectorAll('[data-field-type]');
      elements.forEach(el => {
        const name = el.getAttribute('name');
        if (!name) return;
        const type = el.getAttribute('data-field-type');
        if (type === 'boolean') params[name] = el.checked;
        else if (type === 'number') params[name] = Number(el.value);
        else if (type === 'list_string') params[name] = el.value.split(',').map(s => s.trim()).filter(Boolean);
        else params[name] = el.value;
      });
    }

    const plugin = loadedPlugins.find(p => p.name === pluginName);
    const actDef = plugin?.actions?.find(a => a.id === actionId);
    if (actDef && Array.isArray(actDef.parameters)) {
      for (const param of actDef.parameters) {
        if (param.required && (params[param.name] === undefined || params[param.name] === '')) {
          const userVal = prompt(`${param.description || param.name}:`);
          if (userVal === null) {
            logToPluginConsole('[ACTION] Отменено пользователем.');
            return;
          }
          params[param.name] = userVal;
        }
      }
    }

    const endpoint = `/api/v1/admin/plugins/${pluginName}/action/${actionId}`;
    let res;
    if (window.api && typeof window.api.fetch === 'function') {
      res = await window.api.fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params })
      });
    } else {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params })
      });
      res = await resp.json();
    }

    if (res.success || res.status === 'success') {
      showPluginNotification(res.message || 'Действие успешно выполнено', 'success');
      logToPluginConsole(`✓ ${res.message || 'Успех'}\n${JSON.stringify(res.result || res.results || res, null, 2)}`);
    } else {
      showPluginNotification(res.message || 'Ошибка выполнения действия', 'warning');
      logToPluginConsole(`⚠ ${res.message || 'Завершено с предупреждением'}`);
    }
  } catch (ex) {
    console.error(`Ошибка выполнения действия ${actionId}:`, ex);
    showPluginNotification(`Ошибка: ${ex.message}`, 'danger');
    logToPluginConsole(`✗ Ошибка выполнения: ${ex.message}`);
  }
}
