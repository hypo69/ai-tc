/**
 * =============================================================================
 * Process Name: Windows AI Agents - Interactive Sandbox Panel
 * =============================================================================
 * Description:
 *   Модуль изолированной интерактивной песочницы (Sandbox) для тестирования
 *   рассуждений и вызова инструментов выбранного ИИ-агента в режиме реального времени
 *   с отображением трассировки шагов ReAct (Thought -> Action -> Observation).
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_agents/panel_sandbox
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, fetchJson, getProviderDisplayName } from '../common/ui_utils.js';

/**
 * Подбор релевантного тестового запроса для поля ввода песочницы на основе профиля агента.
 * @param {object} agent - Объект конфигурации агента
 * @returns {string} Релевантный тестовый запрос
 */
export function getRelevantSandboxQuery(agent) {
  if (!agent || typeof agent !== 'object') {
    return 'Выполни диагностический тест агента';
  }

  const explicit = typeof agent.sandbox_default_query === 'string'
    ? agent.sandbox_default_query.trim()
    : '';
  if (explicit) return explicit;

  const agentId = String(agent.id ?? '').toLowerCase();
  const tools = (agent.tools ?? []).map((t) => String(t).toLowerCase());
  const description = String(agent.description ?? '').trim();
  const name = String(agent.name ?? agent.id ?? 'агент').trim();

  if (agentId.includes('github') || tools.some((t) => t.includes('github'))) {
    return 'Покажи список открытых GitHub Issues в репозитории и предложи приоритетный план их выполнения';
  }
  if (agentId.includes('log') || tools.some((t) => t.includes('event_log'))) {
    return 'Проанализируй критические ошибки и предупреждения в журналах событий Windows (System и Application) за последние 24 часа';
  }
  if (
    agentId.includes('windows') ||
    tools.some((t) => t.startsWith('windows_') || t === 'system_diagnostics' || t === 'services_manager')
  ) {
    return 'Проверь текущую загрузку CPU, оперативной памяти и статус критических служб Windows';
  }
  if (
    agentId.includes('chat') ||
    tools.some((t) => t === 'wikillm_search' || t === 'rag_search' || t === 'search_web')
  ) {
    return 'Найди в базе знаний WikiLLM краткую справку по диагностике и настройке системы';
  }
  if (tools.some((t) => t === 'python_eval' || t === 'run_command')) {
    return 'Выполни быструю диагностическую проверку окружения и выведи краткий отчёт';
  }
  if (description) {
    return `Выполни тестовую задачу по профилю агента «${name}»: ${description}`;
  }
  return `Выполни диагностический тест возможностей агента «${name}»`;
}

/**
 * Открытие модального окна интерактивной песочницы для указанного агента.
 * @param {string} agentId - Идентификатор агента
 */
export function openSandbox(agentId) {
  const agent = state.agents.find((a) => a.id === agentId);
  if (!agent) return;

  state.activeSandboxAgent = agent;
  const modalEl = document.getElementById('modal-agent-sandbox');
  if (!modalEl) return;

  document.getElementById('sandbox-agent-name')?.replaceChildren(document.createTextNode(agent.name));
  const modelBadge = document.getElementById('sandbox-agent-model');
  if (modelBadge) modelBadge.textContent = `${getProviderDisplayName(agent.provider)}: ${agent.model}`;

  const toolsSummary = document.getElementById('sandbox-agent-tools-summary');
  if (toolsSummary) toolsSummary.textContent = `Инструментов: ${(agent.tools ?? []).length}`;

  const msgsList = document.getElementById('sandbox-messages-list');
  const placeholder = document.getElementById('sandbox-placeholder');
  if (msgsList) msgsList.innerHTML = '';
  if (placeholder) placeholder.style.display = 'block';

  // Предзаполнение поля ввода релевантным запросом для выбранного агента
  const input = document.getElementById('sandbox-input-msg');
  if (input) {
    const relevantQuery = getRelevantSandboxQuery(agent);
    input.value = relevantQuery;
    input.placeholder = relevantQuery;
  }

  if (window.bootstrap && window.bootstrap.Modal) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    if (input) {
      modalEl.addEventListener(
        'shown.bs.modal',
        () => {
          input.focus();
        },
        { once: true }
      );
    }
    modal.show();
  }
}

/**
 * Выполнение тестового запроса к активному агенту песочницы и рендеринг трассировки.
 */
export async function handleRunSandboxTest() {
  const agent = state.activeSandboxAgent;
  const input = document.getElementById('sandbox-input-msg');
  const sendBtn = document.getElementById('btn-sandbox-send');
  const msgsList = document.getElementById('sandbox-messages-list');
  const placeholder = document.getElementById('sandbox-placeholder');

  if (!agent || !input || !msgsList) return;
  const query = input.value.trim();
  if (!query) return;

  if (placeholder) placeholder.style.display = 'none';

  // Сообщение пользователя
  const userMsgEl = document.createElement('div');
  userMsgEl.className = 'd-flex justify-content-end mb-3';
  userMsgEl.innerHTML = `
    <div class="p-2 px-3 rounded shadow-sm text-white small" style="background-color: var(--nav-active, #2563eb); max-width: 80%; font-weight: 500;">
      <strong>Вы:</strong> ${query}
    </div>
  `;
  msgsList.appendChild(userMsgEl);

  input.value = '';
  if (sendBtn) sendBtn.disabled = true;

  // Плейсхолдер ответа со спиннером
  const botMsgEl = document.createElement('div');
  botMsgEl.className = 'd-flex flex-column mb-3';
  botMsgEl.innerHTML = `
    <div class="p-3 rounded small" style="background: var(--surface-1); border: 1px solid var(--border-color); color: var(--text-color);">
      <div class="d-flex align-items-center gap-2 mb-2 text-warning fw-semibold">
        <span class="spinner-border spinner-border-sm"></span>
        <span>Агент выполняет рассуждение и вызовы инструментов...</span>
      </div>
      <div class="steps-trace small font-monospace text-muted"></div>
    </div>
  `;
  msgsList.appendChild(botMsgEl);
  msgsList.scrollTop = msgsList.scrollHeight;

  try {
    const res = await fetchJson('/api/v1/agents/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agent.id, test_message: query })
    });

    const stepsHtml = (res.steps ?? [])
      .map((s) => {
        let icon = '🔹';
        if (s.type === 'tool_init') icon = '🛠️';
        else if (s.type === 'action') icon = '⚡';
        else if (s.type === 'finish') icon = '✅';
        else if (s.type === 'error') icon = '❌';

        return `<div class="mb-1">${icon} <span class="text-info fw-bold">[Шаг ${s.step}]</span> <span class="text-body">${s.content}</span></div>`;
      })
      .join('');

    botMsgEl.innerHTML = `
      <div class="p-3 rounded small" style="background: var(--surface-1); border: 1px solid var(--border-color); color: var(--text-color);">
        <div class="d-flex justify-content-between align-items-center mb-2 pb-1 border-bottom border-secondary-subtle">
          <strong class="text-info" style="font-size: 0.95rem;">🤖 ${agent.name}</strong>
          <span class="badge bg-secondary" style="font-weight: 600;">${res.duration_ms ?? 0} мс</span>
        </div>
        
        <div class="mb-2 text-body" style="white-space: pre-wrap; line-height: 1.5;">${res.response || 'Пустой ответ'}</div>
        
        <div class="p-2 rounded mt-2 small font-monospace" style="background: var(--surface-2); border: 1px solid var(--border-color); font-size: 0.8rem; line-height: 1.45;">
          <div class="fw-bold mb-1 text-muted">Трассировка выполнения (ReAct Trace):</div>
          ${stepsHtml}
        </div>
      </div>
    `;
  } catch (err) {
    botMsgEl.innerHTML = `
      <div class="p-3 rounded small bg-danger-subtle border border-danger text-danger">
        <strong class="text-danger">Ошибка выполнения:</strong> ${err.message}
      </div>
    `;
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    const chatWin = document.getElementById('sandbox-chat-window');
    if (chatWin) chatWin.scrollTop = chatWin.scrollHeight;
  }
}

/**
 * Привязка событий элементов управления модального окна Sandbox.
 */
export function bindSandboxEvents() {
  const sandboxSendBtn = document.getElementById('btn-sandbox-send');
  const sandboxInput = document.getElementById('sandbox-input-msg');
  if (sandboxSendBtn && sandboxInput && !sandboxSendBtn._bound) {
    sandboxSendBtn._bound = true;
    sandboxSendBtn.onclick = handleRunSandboxTest;
    sandboxInput.onkeypress = (e) => {
      if (e.key === 'Enter') handleRunSandboxTest();
    };
  }
}
