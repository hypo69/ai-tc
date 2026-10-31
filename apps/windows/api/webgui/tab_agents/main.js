/**
 * =============================================================================
 * Process Name: Windows AI Agents Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Модульный клиентский оркестратор панели управления ИИ-агентами:
 *   координирует сетку агентов, фильтрацию, редактор спецификаций,
 *   матрицу инструментов, AI-генератор и интерактивную песочницу Sandbox.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_agents
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 11:15:00
 * =============================================================================
 */

import { state, fetchJson, showToast } from './common/ui_utils.js';
import { renderCounters, renderGrid, bindGridToolbar } from './panel_grid/panel.js';
import {
  populateToolsMatrix,
  updateModelDropdown,
  openEditor,
  bindEditorEvents,
} from './panel_editor/panel.js';
import { bindAiBuilderEvents } from './panel_ai_builder/panel.js';
import { openSandbox, bindSandboxEvents } from './panel_sandbox/panel.js';

/**
 * Загрузка всех данных: агенты, каталог инструментов, провайдеры и модели.
 * @returns {Promise<void>}
 */
export async function loadAllAgentsData() {
  try {
    const [agentsRes, toolsRes, providersRes] = await Promise.all([
      fetchJson('/api/agents'),
      fetchJson('/api/agents/tools'),
      fetchJson('/api/agents/providers')
    ]);

    state.agents = Array.isArray(agentsRes) ? agentsRes : (agentsRes?.agents || []);
    state.tools = Array.isArray(toolsRes) ? toolsRes : (toolsRes?.tools || []);
    state.providers = providersRes?.providers || (typeof providersRes === 'object' ? providersRes : {});

    renderCounters();
    renderGrid();
    populateToolsMatrix();
    updateModelDropdown('agent-provider', 'agent-model');
    updateModelDropdown('ai-builder-provider', 'ai-builder-model');
  } catch (err) {
    console.error('[AgentsTab] Failed to load data:', err);
    showToast(`Failed to load data: ${err.message}`, 'danger');
    const grid = document.getElementById('agents-grid');
    if (grid) {
      grid.innerHTML = `
        <div class="col-12 text-center py-5 text-danger">
          <i class="bi bi-exclamation-triangle fs-1 d-block mb-2"></i>
          <h5>Не удалось загрузить данные агентов</h5>
          <p class="small text-secondary">${err.message}</p>
          <button class="btn btn-sm btn-outline-primary rounded-pill px-3" onclick="window.initAgentsTab()">Повторить попытку</button>
        </div>
      `;
    }
  }
}

/**
 * Привязка статических событий пользовательского интерфейса.
 */
function bindStaticEvents() {
  if (state.isEventsBound) return;
  state.isEventsBound = true;

  bindGridToolbar();
  bindEditorEvents();
  bindAiBuilderEvents();
  bindSandboxEvents();
}

/**
 * Инициализация вкладки ИИ-агентов.
 * @returns {Promise<void>}
 */
export async function initAgentsTab() {
  bindStaticEvents();
  await loadAllAgentsData();
}

// Экспорт глобальных методов для внешней совместимости
window.initAgentsTab = initAgentsTab;
window.loadAllAgentsData = loadAllAgentsData;
window.openAgentEditor = openEditor;
window.openAgentSandbox = openSandbox;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAgentsTab);
} else {
  initAgentsTab();
}
