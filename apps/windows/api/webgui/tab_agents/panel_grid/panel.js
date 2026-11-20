/**
 * =============================================================================
 * Process Name: Windows AI Agents - Grid & Filtering Panel
 * =============================================================================
 * Description:
 *   Модуль рендеринга адаптивной сетки карточек ИИ-агентов, фильтрации
 *   (все, активные, системные, пользовательские), тулбара счетчиков,
 *   быстрого переключения активности и удаления агентов.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_agents/panel_grid
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, fetchJson, getProviderDisplayName, showToast } from '../common/ui_utils.js';

/**
 * Обновление счетчиков на кнопках панели фильтрации.
 */
export function renderCounters() {
  const allCount = state.agents.length;
  const activeCount = state.agents.filter((a) => a.enabled).length;
  const systemCount = state.agents.filter((a) => a.is_system).length;
  const customCount = state.agents.filter((a) => !a.is_system).length;

  document.getElementById('count-all')?.replaceChildren(document.createTextNode(String(allCount)));
  document.getElementById('count-active')?.replaceChildren(document.createTextNode(String(activeCount)));
  document.getElementById('count-system')?.replaceChildren(document.createTextNode(String(systemCount)));
  document.getElementById('count-custom')?.replaceChildren(document.createTextNode(String(customCount)));
}

/**
 * Отрисовка карточек агентов в сетке согласно текущему фильтру.
 */
export function renderGrid() {
  const grid = document.getElementById('agents-grid');
  if (!grid) return;

  const filter = state.currentFilter;
  let items = state.agents;

  if (filter === 'active') items = items.filter((a) => a.enabled);
  else if (filter === 'system') items = items.filter((a) => a.is_system);
  else if (filter === 'custom') items = items.filter((a) => !a.is_system);

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="col-12 text-center py-5 text-muted">
        <i class="bi bi-robot fs-1 d-block mb-2 text-info"></i>
        <h5 class="text-body">Агенты не найдены</h5>
        <p class="small text-muted">Создайте нового агента с помощью AI или вручную</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = items
    .map((agent) => {
      const isSystem = Boolean(agent.is_system);
      const isEnabled = Boolean(agent.enabled);
      const providerName = getProviderDisplayName(agent.provider);

      const toolsBadges = (agent.tools ?? [])
        .map((toolId) => {
          const tool = state.tools.find((t) => t.id === toolId);
          const icon = tool?.icon ?? '🔧';
          const name = tool?.name ?? toolId;
          return `<span class="badge tool-badge me-1 mb-1 font-monospace">${icon} <span>${name}</span></span>`;
        })
        .join('');

      return `
        <div class="col-xl-4 col-lg-6">
          <div class="card h-100 agent-card shadow-sm" style="${!isEnabled ? 'opacity: 0.65;' : ''}">
            <div class="card-header d-flex justify-content-between align-items-center py-2 px-3">
              <div class="d-flex align-items-center gap-2">
                <span class="fs-5">${isSystem ? '⚙️' : '🧩'}</span>
                <strong class="text-body fs-6 fw-bold">${agent.name}</strong>
                ${
                  isSystem
                    ? '<span class="badge bg-primary fw-bold" style="font-size: 0.7rem;">SYSTEM</span>'
                    : '<span class="badge bg-warning text-dark fw-bold" style="font-size: 0.7rem;">CUSTOM</span>'
                }
              </div>
              <div class="form-check form-switch m-0" title="Включить / Выключить">
                <input class="form-check-input agent-toggle-switch" type="checkbox" data-agent-id="${agent.id}" ${isEnabled ? 'checked' : ''}>
              </div>
            </div>
            <div class="card-body p-3 d-flex flex-column">
              <p class="small mb-3 flex-grow-1 agent-desc text-muted" style="min-height: 40px; line-height: 1.45;">${agent.description || 'Описание отсутствует'}</p>
              
              <div class="agent-spec-box mb-3 small">
                <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom border-secondary-subtle">
                  <span class="spec-label">Провайдер &amp; Модель:</span>
                  <span class="badge spec-value-badge text-truncate" style="max-width: 190px;">${providerName}: ${agent.model}</span>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                  <span class="spec-label">Температура / Шаги:</span>
                  <span class="spec-tech-val font-monospace">T: ${agent.temperature} <span class="text-muted">|</span> Max: ${agent.max_steps}</span>
                </div>
              </div>

              <div class="mb-3">
                <div class="small fw-semibold mb-2 text-body">Инструменты (${(agent.tools ?? []).length}):</div>
                <div class="d-flex flex-wrap">${toolsBadges || '<span class="small text-muted">Без внешних инструментов</span>'}</div>
              </div>

              <div class="mt-auto d-flex justify-content-between gap-2 pt-2 border-top border-secondary-subtle">
                <button class="btn btn-sm rounded-pill px-3 btn-test-sandbox" data-agent-id="${agent.id}">
                  <i class="bi bi-play-fill"></i> Тест в Sandbox
                </button>
                <div class="d-flex gap-1">
                  <button class="btn btn-sm rounded-pill px-2 btn-edit-agent" data-agent-id="${agent.id}" title="Редактировать">
                    <i class="bi bi-pencil-fill"></i>
                  </button>
                  ${
                    !isSystem
                      ? `
                    <button class="btn btn-sm rounded-pill px-2 btn-delete-agent" data-agent-id="${agent.id}" title="Удалить">
                      <i class="bi bi-trash-fill"></i>
                    </button>
                  `
                      : ''
                  }
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    })
    .join('');

  // Привязка событий элементов карточек
  grid.querySelectorAll('.agent-toggle-switch').forEach((sw) => {
    sw.onchange = async () => {
      const agentId = sw.getAttribute('data-agent-id');
      if (agentId) await toggleAgentState(agentId, sw.checked);
    };
  });

  grid.querySelectorAll('.btn-test-sandbox').forEach((btn) => {
    btn.onclick = () => {
      const agentId = btn.getAttribute('data-agent-id');
      if (agentId && typeof window.openAgentSandbox === 'function') {
        window.openAgentSandbox(agentId);
      }
    };
  });

  grid.querySelectorAll('.btn-edit-agent').forEach((btn) => {
    btn.onclick = () => {
      const agentId = btn.getAttribute('data-agent-id');
      if (agentId && typeof window.openAgentEditor === 'function') {
        window.openAgentEditor(agentId);
      }
    };
  });

  grid.querySelectorAll('.btn-delete-agent').forEach((btn) => {
    btn.onclick = () => {
      const agentId = btn.getAttribute('data-agent-id');
      if (agentId) deleteAgent(agentId);
    };
  });
}

/**
 * Переключение состояния активности агента.
 * @param {string} agentId - Идентификатор агента
 * @param {boolean} enabled - Новое состояние активности
 */
export async function toggleAgentState(agentId, enabled) {
  const agent = state.agents.find((a) => a.id === agentId);
  if (!agent) return;

  agent.enabled = enabled;
  try {
    await fetchJson(`/api/v1/agents/${agentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agent)
    });
    renderCounters();
    renderGrid();
    showToast(`Агент "${agent.name}" ${enabled ? 'включен' : 'отключен'}`, 'success');
  } catch (err) {
    console.error('[AgentsTab] Error toggling agent:', err);
    showToast(`Ошибка: ${err.message}`, 'danger');
    if (typeof window.loadAllAgentsData === 'function') {
      await window.loadAllAgentsData();
    }
  }
}

/**
 * Удаление пользовательского агента после подтверждения.
 * @param {string} agentId - Идентификатор агента
 */
export async function deleteAgent(agentId) {
  const agent = state.agents.find((a) => a.id === agentId);
  if (!agent) return;

  if (!confirm(`Вы действительно хотите удалить агента "${agent.name}" (${agent.id})?`)) {
    return;
  }

  try {
    await fetchJson(`/api/v1/agents/${agentId}`, { method: 'DELETE' });
    showToast(`Агент "${agent.name}" удален`, 'success');
    if (typeof window.loadAllAgentsData === 'function') {
      await window.loadAllAgentsData();
    }
  } catch (err) {
    console.error('[AgentsTab] Error deleting agent:', err);
    showToast(`Ошибка удаления: ${err.message}`, 'danger');
  }
}

/**
 * Привязка обработчиков панели фильтрации и обновления списка агентов.
 */
export function bindGridToolbar() {
  const refreshBtn = document.getElementById('btn-refresh-agents');
  if (refreshBtn && !refreshBtn._bound) {
    refreshBtn._bound = true;
    refreshBtn.onclick = async () => {
      refreshBtn.disabled = true;
      if (typeof window.loadAllAgentsData === 'function') {
        await window.loadAllAgentsData();
      }
      refreshBtn.disabled = false;
      showToast('Список агентов обновлен', 'success');
    };
  }

  const filterGroup = document.getElementById('agents-filter-group');
  if (filterGroup && !filterGroup._bound) {
    filterGroup._bound = true;
    filterGroup.querySelectorAll('button').forEach((btn) => {
      btn.onclick = () => {
        filterGroup.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentFilter = btn.getAttribute('data-filter') ?? 'all';
        renderGrid();
      };
    });
  }
}
