/**
 * =============================================================================
 * Process Name: Windows MCP Servers - Servers Grid & Table Panel
 * =============================================================================
 * Description:
 *   Модуль отображения реестра серверов Model Context Protocol (MCP):
 *   рендеринг в режимах карточек и таблицы, переключение статуса (активен/отключен),
 *   удаление, фильтрация (stdio / sse / enabled / disabled) и текстовый поиск.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_mcp/panel_servers
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, escapeHtml, apiFetch } from '../common/ui_utils.js';

/**
 * Обновление счетчиков статистики серверов MCP.
 */
export function updateStats() {
  const total = state.servers.length;
  const active = state.servers.filter(s => s.enabled !== false).length;
  const stdio = state.servers.filter(s => (s.transport || 'stdio') === 'stdio').length;
  const network = state.servers.filter(s => ['sse', 'streamable_http', 'http'].includes(s.transport)).length;

  const badge = document.getElementById('mcp-total-badge');
  if (badge) badge.textContent = total;

  const elTotal = document.getElementById('stat-total-mcp');
  if (elTotal) elTotal.textContent = total;

  const elActive = document.getElementById('stat-active-mcp');
  if (elActive) elActive.textContent = active;

  const elStdio = document.getElementById('stat-stdio-mcp');
  if (elStdio) elStdio.textContent = stdio;

  const elNetwork = document.getElementById('stat-network-mcp');
  if (elNetwork) elNetwork.textContent = network;
}

/**
 * Применение фильтров категории и строки поиска к реестру серверов.
 */
export function applyFilters() {
  const filterSelect = document.getElementById('mcp-filter-select');
  state.activeFilter = filterSelect ? filterSelect.value : 'all';

  state.filteredServers = state.servers.filter(s => {
    // Поисковый запрос
    if (state.searchQuery) {
      const idMatch = (s.id || '').toLowerCase().includes(state.searchQuery);
      const nameMatch = (s.name || '').toLowerCase().includes(state.searchQuery);
      const descMatch = (s.description || '').toLowerCase().includes(state.searchQuery);
      const cmdMatch = (s.command || '').toLowerCase().includes(state.searchQuery);
      const urlMatch = (s.url || '').toLowerCase().includes(state.searchQuery);
      if (!idMatch && !nameMatch && !descMatch && !cmdMatch && !urlMatch) {
        return false;
      }
    }

    // Категория фильтра
    if (state.activeFilter === 'enabled') {
      return s.enabled !== false;
    } else if (state.activeFilter === 'disabled') {
      return s.enabled === false;
    } else if (state.activeFilter === 'stdio') {
      return (s.transport || 'stdio') === 'stdio';
    } else if (state.activeFilter === 'sse') {
      return ['sse', 'streamable_http', 'http'].includes(s.transport);
    }

    return true;
  });

  render();
}

/**
 * Очистка строки поискового запроса.
 */
export function clearSearch() {
  const searchInput = document.getElementById('mcp-search-input');
  if (searchInput) searchInput.value = '';
  state.searchQuery = '';
  applyFilters();
}

/**
 * Переключение режима отображения (карточки / таблица).
 * @param {'cards' | 'table'} mode - Режим отображения
 */
export function setViewMode(mode) {
  state.viewMode = mode;
  const btnCards = document.getElementById('btn-mcp-view-cards');
  const btnTable = document.getElementById('btn-mcp-view-table');
  const cardsContainer = document.getElementById('mcp-cards-container');
  const tableContainer = document.getElementById('mcp-table-container');

  if (mode === 'cards') {
    btnCards?.classList.add('active');
    btnTable?.classList.remove('active');
    cardsContainer?.classList.remove('d-none');
    tableContainer?.classList.add('d-none');
  } else {
    btnCards?.classList.remove('active');
    btnTable?.classList.add('active');
    cardsContainer?.classList.add('d-none');
    tableContainer?.classList.remove('d-none');
  }
}

/**
 * Переключение индикатора загрузки.
 * @param {boolean} show - Флаг отображения лоадера
 */
export function showLoading(show) {
  const loadingEl = document.getElementById('mcp-loading');
  const cardsEl = document.getElementById('mcp-cards-container');
  const tableEl = document.getElementById('mcp-table-container');
  const emptyEl = document.getElementById('mcp-empty');

  if (show) {
    loadingEl?.classList.remove('d-none');
    cardsEl?.classList.add('d-none');
    tableEl?.classList.add('d-none');
    emptyEl?.classList.add('d-none');
  } else {
    loadingEl?.classList.add('d-none');
    setViewMode(state.viewMode);
  }
}

/**
 * Отрисовка списка серверов в соответствии с текущим представлением.
 */
export function render() {
  const emptyEl = document.getElementById('mcp-empty');
  const cardsContainer = document.getElementById('mcp-cards-container');
  const tableBody = document.getElementById('mcp-table-body');

  if (state.filteredServers.length === 0) {
    if (emptyEl) emptyEl.classList.remove('d-none');
    if (cardsContainer) cardsContainer.innerHTML = '';
    if (tableBody) tableBody.innerHTML = '';
    return;
  }

  if (emptyEl) emptyEl.classList.add('d-none');

  if (cardsContainer) {
    cardsContainer.innerHTML = state.filteredServers.map(s => renderServerCard(s)).join('');
  }

  if (tableBody) {
    tableBody.innerHTML = state.filteredServers.map(s => renderServerTableRow(s)).join('');
  }
}

/**
 * Формирование HTML-разметки карточки MCP сервера.
 * @param {object} server - Объект описания сервера
 * @returns {string} HTML карточки
 */
export function renderServerCard(server) {
  const isEnabled = server.enabled !== false;
  const isStdio = (server.transport || 'stdio') === 'stdio';
  const statusBadge = isEnabled
    ? '<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle-fill"></i> Активен</span>'
    : '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle"><i class="bi bi-dash-circle"></i> Отключен</span>';

  const transportBadge = isStdio
    ? '<span class="badge bg-info-subtle text-info border border-info-subtle"><i class="bi bi-terminal"></i> stdio</span>'
    : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle"><i class="bi bi-broadcast"></i> ${escapeHtml(server.transport)}</span>`;

  const commandOrUrl = isStdio
    ? `<code>${escapeHtml(server.command || '')} ${(server.args || []).join(' ')}</code>`
    : `<a href="${escapeHtml(server.url || '#')}" target="_blank" class="text-info text-truncate d-inline-block" style="max-width: 250px;">${escapeHtml(server.url || '')}</a>`;

  return `
    <div class="col-12 col-md-6 col-xl-4">
      <div class="card bg-dark border-secondary h-100 shadow-sm d-flex flex-column">
        <div class="card-header border-secondary d-flex align-items-center justify-content-between p-3">
          <div class="d-flex align-items-center gap-2 text-truncate">
            <div class="p-2 bg-black rounded border border-secondary text-primary">
              <i class="bi ${isStdio ? 'bi-cpu' : 'bi-globe2'}"></i>
            </div>
            <div class="text-truncate">
              <h6 class="mb-0 text-white text-truncate fw-bold">${escapeHtml(server.name || server.id)}</h6>
              <small class="text-muted font-monospace">${escapeHtml(server.id)}</small>
            </div>
          </div>
          <div class="d-flex align-items-center gap-1">
            ${transportBadge}
            ${statusBadge}
          </div>
        </div>
        <div class="card-body p-3 flex-grow-1">
          <p class="card-text small text-secondary mb-3" style="min-height: 38px;">
            ${escapeHtml(server.description || 'Описание отсутствует.')}
          </p>
          <div class="p-2 bg-black rounded border border-secondary mb-2 small">
            <div class="text-muted small mb-1">${isStdio ? 'Исполняемая команда:' : 'Сетевой эндпоинт:'}</div>
            <div class="text-truncate">${commandOrUrl}</div>
          </div>
        </div>
        <div class="card-footer border-secondary p-2 d-flex align-items-center justify-content-between gap-1 bg-black bg-opacity-25">
          <button class="btn btn-sm btn-outline-info d-flex align-items-center gap-1" onclick="window.mcpTab?.testServer('${escapeHtml(server.id)}')">
            <i class="bi bi-play-circle"></i> Тест & Tools
          </button>
          <div class="d-flex align-items-center gap-1">
            <button class="btn btn-sm ${isEnabled ? 'btn-outline-warning' : 'btn-outline-success'}" title="${isEnabled ? 'Отключить' : 'Включить'}" onclick="window.mcpTab?.toggleServer('${escapeHtml(server.id)}')">
              <i class="bi ${isEnabled ? 'bi-pause-fill' : 'bi-play-fill'}"></i>
            </button>
            <button class="btn btn-sm btn-outline-primary" title="Редактировать" onclick="window.mcpTab?.openEditModal('${escapeHtml(server.id)}')">
              <i class="bi bi-pencil-fill"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" title="Удалить" onclick="window.mcpTab?.deleteServer('${escapeHtml(server.id)}')">
              <i class="bi bi-trash-fill"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Формирование HTML-разметки строки таблицы MCP сервера.
 * @param {object} server - Объект описания сервера
 * @returns {string} HTML строки таблицы
 */
export function renderServerTableRow(server) {
  const isEnabled = server.enabled !== false;
  const isStdio = (server.transport || 'stdio') === 'stdio';
  const statusDot = isEnabled
    ? '<span class="badge bg-success rounded-pill" title="Активен">ON</span>'
    : '<span class="badge bg-secondary rounded-pill" title="Отключен">OFF</span>';

  const transportBadge = isStdio
    ? '<span class="badge bg-info-subtle text-info border border-info-subtle">stdio</span>'
    : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle">${escapeHtml(server.transport)}</span>`;

  const cmdOrUrl = isStdio
    ? `<code>${escapeHtml(server.command || '')} ${(server.args || []).join(' ')}</code>`
    : `<a href="${escapeHtml(server.url || '#')}" target="_blank" class="text-info">${escapeHtml(server.url || '')}</a>`;

  return `
    <tr>
      <td class="text-center">${statusDot}</td>
      <td>
        <div class="fw-bold text-white">${escapeHtml(server.name || server.id)}</div>
        <div class="small font-monospace text-muted">${escapeHtml(server.id)}</div>
      </td>
      <td>${transportBadge}</td>
      <td class="small text-truncate" style="max-width: 250px;">${cmdOrUrl}</td>
      <td class="small text-muted text-truncate" style="max-width: 200px;">${escapeHtml(server.description || '—')}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-info" title="Тест соединения" onclick="window.mcpTab?.testServer('${escapeHtml(server.id)}')">
            <i class="bi bi-play-circle"></i>
          </button>
          <button class="btn ${isEnabled ? 'btn-outline-warning' : 'btn-outline-success'}" title="${isEnabled ? 'Отключить' : 'Включить'}" onclick="window.mcpTab?.toggleServer('${escapeHtml(server.id)}')">
            <i class="bi ${isEnabled ? 'bi-pause-fill' : 'bi-play-fill'}"></i>
          </button>
          <button class="btn btn-outline-primary" title="Редактировать" onclick="window.mcpTab?.openEditModal('${escapeHtml(server.id)}')">
            <i class="bi bi-pencil-fill"></i>
          </button>
          <button class="btn btn-outline-danger" title="Удалить" onclick="window.mcpTab?.deleteServer('${escapeHtml(server.id)}')">
            <i class="bi bi-trash-fill"></i>
          </button>
        </div>
      </td>
    </tr>
  `;
}

/**
 * Отрисовка сообщения об ошибке загрузки серверов.
 * @param {string} msg - Сообщение об ошибке
 */
export function renderError(msg) {
  const container = document.getElementById('mcp-cards-container');
  if (container) {
    container.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger bg-dark border-danger text-light d-flex align-items-center justify-content-between">
          <div><i class="bi bi-exclamation-triangle-fill text-danger me-2"></i> ${escapeHtml(msg)}</div>
          <button class="btn btn-sm btn-outline-light" onclick="window.mcpTab?.refresh()">Повторить</button>
        </div>
      </div>
    `;
  }
}

/**
 * Загрузка актуального списка MCP серверов с бэкенда.
 * @returns {Promise<void>}
 */
export async function refreshServers() {
  showLoading(true);
  try {
    const res = await apiFetch('/api/v1/admin/mcp/servers');
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    state.servers = data.servers || [];
    updateStats();
    applyFilters();
  } catch (err) {
    console.error('[McpTab] Error fetching MCP servers:', err);
    renderError(err.message);
  } finally {
    showLoading(false);
  }
}

/**
 * Переключение состояния активности сервера.
 * @param {string} serverId - Идентификатор сервера
 */
export async function toggleServer(serverId) {
  try {
    const res = await apiFetch(`/api/v1/admin/mcp/servers/${encodeURIComponent(serverId)}/toggle`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    await refreshServers();
  } catch (err) {
    const msg = `Ошибка переключения статуса сервера: ${err.message}`;
    window.showToast?.(msg, 'danger') || alert(msg);
  }
}

/**
 * Удаление сервера MCP после подтверждения.
 * @param {string} serverId - Идентификатор сервера
 */
export async function deleteServer(serverId) {
  if (!confirm(`Вы уверены, что хотите удалить MCP сервер "${serverId}"?`)) {
    return;
  }

  try {
    const res = await apiFetch(`/api/v1/admin/mcp/servers/${encodeURIComponent(serverId)}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    await refreshServers();
  } catch (err) {
    const msg = `Ошибка удаления сервера: ${err.message}`;
    window.showToast?.(msg, 'danger') || alert(msg);
  }
}

/**
 * Привязка событий поиска и фильтрации.
 */
export function bindServersEvents() {
  const searchInput = document.getElementById('mcp-search-input');
  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.trim().toLowerCase();
      applyFilters();
    });
  }

  const idInput = document.getElementById('mcp-server-id');
  if (idInput && !idInput._bound) {
    idInput._bound = true;
    idInput.addEventListener('input', (e) => {
      const val = e.target.value;
      const normalized = val.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
      if (val !== normalized) {
        e.target.value = normalized;
      }
    });
  }
}
