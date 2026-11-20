/**
 * =============================================================================
 * Process Name: Windows MCP Servers Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Модульный клиентский оркестратор вкладки управления MCP-серверами (Model Context Protocol).
 *   Координирует реестр серверов, режимы карточек и таблицы, модальный редактор,
 *   пресеты провайдеров, интерактивное тестирование задержки и каталог инструментов.
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_mcp
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, escapeHtml, apiFetch } from './common/ui_utils.js';
import {
  updateStats,
  applyFilters,
  clearSearch,
  setViewMode,
  showLoading,
  render,
  renderServerCard,
  renderServerTableRow,
  renderError,
  refreshServers,
  toggleServer,
  deleteServer,
  bindServersEvents,
} from './panel_servers/panel.js';
import {
  onTransportChange,
  applyPreset,
  openCreateModal,
  openEditModal,
  saveServer,
  testCurrentForm,
} from './panel_modal_server/panel.js';
import {
  testServer,
  openAllToolsModal,
  renderDiscoveredTools,
} from './panel_test_tools/panel.js';

/**
 * Фасадный класс менеджера вкладки MCP для полной совместимости с inline onclick хэндлерами.
 */
export class McpTabManager {
  constructor() {
    this.escapeHtml = escapeHtml;
    this.apiFetch = apiFetch;
  }

  get servers() { return state.servers; }
  set servers(val) { state.servers = val; }

  get filteredServers() { return state.filteredServers; }
  set filteredServers(val) { state.filteredServers = val; }

  get viewMode() { return state.viewMode; }
  set viewMode(val) { state.viewMode = val; }

  get searchQuery() { return state.searchQuery; }
  set searchQuery(val) { state.searchQuery = val; }

  get activeFilter() { return state.activeFilter; }
  set activeFilter(val) { state.activeFilter = val; }

  get isInitialized() { return state.isInitialized; }
  set isInitialized(val) { state.isInitialized = val; }

  async init() {
    if (this.isInitialized) {
      await this.refresh();
      return;
    }
    this.bindEvents();
    this.isInitialized = true;
    await this.refresh();
  }

  bindEvents() {
    bindServersEvents();
  }

  async refresh() {
    await refreshServers();
  }

  updateStats() {
    updateStats();
  }

  applyFilters() {
    applyFilters();
  }

  clearSearch() {
    clearSearch();
  }

  setViewMode(mode) {
    setViewMode(mode);
  }

  showLoading(show) {
    showLoading(show);
  }

  render() {
    render();
  }

  renderServerCard(server) {
    return renderServerCard(server);
  }

  renderServerTableRow(server) {
    return renderServerTableRow(server);
  }

  renderError(msg) {
    renderError(msg);
  }

  onTransportChange() {
    onTransportChange();
  }

  applyPreset(presetKey) {
    applyPreset(presetKey);
  }

  openCreateModal() {
    openCreateModal();
  }

  openEditModal(serverId) {
    openEditModal(serverId);
  }

  async saveServer(event) {
    await saveServer(event);
  }

  async testCurrentForm() {
    await testCurrentForm();
  }

  async toggleServer(serverId) {
    await toggleServer(serverId);
  }

  async deleteServer(serverId) {
    await deleteServer(serverId);
  }

  async testServer(serverId) {
    await testServer(serverId);
  }

  async openAllToolsModal() {
    await openAllToolsModal();
  }

  renderDiscoveredTools(tools, container) {
    renderDiscoveredTools(tools, container);
  }
}

// Экспорт глобальных объектов для совместимости с хостом
window.McpTabManager = McpTabManager;
if (!window.mcpTab) {
  window.mcpTab = new McpTabManager();
}

/**
 * Инициализация вкладки MCP серверов.
 */
export function initMcpTab() {
  if (window.mcpTab) {
    window.mcpTab.init();
  }
}

window.initMcpTab = initMcpTab;

if (document.getElementById('mcp-tab-root')) {
  window.mcpTab.init();
}
