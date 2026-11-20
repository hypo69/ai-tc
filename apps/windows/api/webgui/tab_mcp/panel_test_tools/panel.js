/**
 * =============================================================================
 * Process Name: Windows MCP Servers - Test & Discovered Tools Panel
 * =============================================================================
 * Description:
 *   Модуль интерактивного тестирования связи с серверами MCP, замера сетевой
 *   задержки (latency ms), обнаружения и визуализации инструментов (Tools)
 *   и исследования JSON-схем параметров вызова.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_mcp/panel_test_tools
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, escapeHtml, apiFetch } from '../common/ui_utils.js';

/**
 * Отрисовка списка обнаруженных инструментов MCP в переданном контейнере.
 * @param {Array<object>} tools - Список инструментов
 * @param {HTMLElement} container - DOM-контейнер
 */
export function renderDiscoveredTools(tools, container) {
  if (!tools || tools.length === 0) {
    container.innerHTML = '<div class="text-muted text-center py-3">Сервер не вернул доступных инструментов.</div>';
    return;
  }

  container.innerHTML = tools.map((t, idx) => `
    <div class="p-3 bg-dark rounded border border-secondary">
      <div class="d-flex align-items-center justify-content-between mb-1">
        <strong class="text-warning font-monospace d-flex align-items-center gap-1">
          <i class="bi bi-wrench-adjustable"></i> ${escapeHtml(t.name)}
        </strong>
        <span class="badge bg-dark border border-secondary text-muted">#${idx + 1}</span>
      </div>
      <div class="small text-muted mb-2">${escapeHtml(t.description || 'Описание не указано')}</div>
      ${t.args_schema ? `
        <details class="small">
          <summary class="text-info cursor-pointer">Параметры и схема вызова</summary>
          <pre class="bg-black text-white p-2 rounded mt-1 mb-0 font-monospace small" style="max-height: 180px; overflow-y: auto;">${escapeHtml(typeof t.args_schema === 'object' ? JSON.stringify(t.args_schema, null, 2) : String(t.args_schema))}</pre>
        </details>
      ` : ''}
    </div>
  `).join('');
}

/**
 * Запуск тестирования соединения с указанным MCP сервером и инспекция его инструментов.
 * @param {string} serverId - Идентификатор сервера
 */
export async function testServer(serverId) {
  const server = state.servers.find(s => s.id === serverId);
  const serverName = server?.name || serverId;

  const nameEl = document.getElementById('mcp-test-server-name');
  if (nameEl) nameEl.textContent = serverName;

  const statusBox = document.getElementById('mcp-test-status-box');
  const statusText = document.getElementById('mcp-test-status-text');
  const spinner = document.getElementById('mcp-test-spinner');
  const latencyBadge = document.getElementById('mcp-test-latency-badge');
  const countBadge = document.getElementById('mcp-test-tools-count');
  const toolsList = document.getElementById('mcp-test-tools-list');

  if (spinner) spinner.classList.remove('d-none');
  if (statusBox) {
    statusBox.className = 'p-3 mb-3 rounded border border-info bg-black text-info d-flex align-items-center justify-content-between';
  }
  if (statusText) statusText.textContent = 'Подключение к процессу / эндпоинту и опрос инструментов...';
  if (latencyBadge) latencyBadge.textContent = '...';
  if (countBadge) countBadge.textContent = '0';
  if (toolsList) toolsList.innerHTML = '<div class="text-muted text-center py-3">Опрос инструментов...</div>';

  const modalEl = document.getElementById('mcpTestModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
    modal.show();
  }

  try {
    const res = await apiFetch(`/api/v1/admin/mcp/servers/${encodeURIComponent(serverId)}/test`, {
      method: 'POST'
    });
    const data = await res.json();

    if (spinner) spinner.classList.add('d-none');
    if (latencyBadge) latencyBadge.textContent = `${data.latency_ms || 0} ms`;

    if (data.status === 'ok') {
      if (statusBox) {
        statusBox.className = 'p-3 mb-3 rounded border border-success bg-black text-success d-flex align-items-center justify-content-between';
      }
      if (statusText) statusText.innerHTML = `✅ <strong>Успешно:</strong> ${escapeHtml(data.message)}`;
      if (countBadge) countBadge.textContent = data.tools_count || (data.tools || []).length;
      renderDiscoveredTools(data.tools || [], toolsList);
    } else {
      if (statusBox) {
        statusBox.className = 'p-3 mb-3 rounded border border-danger bg-black text-danger d-flex align-items-center justify-content-between';
      }
      if (statusText) statusText.innerHTML = `❌ <strong>Ошибка:</strong> ${escapeHtml(data.message || 'Не удалось подключиться к серверу')}`;
      if (toolsList) {
        toolsList.innerHTML = `<div class="alert alert-danger bg-dark border-danger text-light small mb-0">${escapeHtml(data.message || 'Ошибка соединения')}</div>`;
      }
    }
  } catch (err) {
    if (spinner) spinner.classList.add('d-none');
    if (statusBox) {
      statusBox.className = 'p-3 mb-3 rounded border border-danger bg-black text-danger d-flex align-items-center justify-content-between';
    }
    if (statusText) statusText.innerHTML = `❌ <strong>Сетевая ошибка:</strong> ${escapeHtml(err.message)}`;
  }
}

/**
 * Открытие модального окна полного каталога инструментов со всех серверов.
 */
export async function openAllToolsModal() {
  const modalEl = document.getElementById('mcpAllToolsModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
    modal.show();
  }

  const loadingEl = document.getElementById('mcp-all-tools-loading');
  const emptyEl = document.getElementById('mcp-all-tools-empty');
  const container = document.getElementById('mcp-all-tools-container');

  loadingEl?.classList.remove('d-none');
  emptyEl?.classList.add('d-none');
  container?.classList.add('d-none');

  try {
    const res = await apiFetch('/api/v1/admin/mcp/tools');
    const data = await res.json();
    loadingEl?.classList.add('d-none');

    const tools = data.tools || [];
    if (tools.length === 0) {
      emptyEl?.classList.remove('d-none');
      return;
    }

    container?.classList.remove('d-none');
    if (container) {
      container.innerHTML = tools.map(t => `
        <div class="col-12 col-lg-6">
          <div class="p-3 bg-black rounded border border-secondary h-100 d-flex flex-column">
            <div class="d-flex align-items-center justify-content-between mb-2">
              <strong class="text-info font-monospace d-flex align-items-center gap-1">
                <i class="bi bi-wrench"></i> ${escapeHtml(t.name)}
              </strong>
              <span class="badge bg-primary-subtle text-primary border border-primary-subtle small">Tool</span>
            </div>
            <p class="small text-muted mb-2 flex-grow-1">${escapeHtml(t.description || 'Нет описания.')}</p>
            ${t.args_schema ? `
              <div class="mt-auto">
                <details class="small">
                  <summary class="text-secondary cursor-pointer">Схема аргументов</summary>
                  <pre class="bg-dark text-light p-2 rounded mt-1 mb-0 font-monospace small" style="max-height: 150px; overflow-y: auto;">${escapeHtml(typeof t.args_schema === 'object' ? JSON.stringify(t.args_schema, null, 2) : String(t.args_schema))}</pre>
                </details>
              </div>
            ` : ''}
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    loadingEl?.classList.add('d-none');
    if (container) {
      container.classList.remove('d-none');
      container.innerHTML = `<div class="col-12"><div class="alert alert-danger">${escapeHtml(err.message)}</div></div>`;
    }
  }
}
