/**
 * =============================================================================
 * Process Name: Windows Interactive Scenario Agent Tab - Controller Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер пошагового диалогового агента со стейт-машиной сессий.
 *   Управляет отправкой целей, отображением степпера и вводом ответов.
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_interactive_agent
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

let currentAgentSessionId = null;

export async function initInteractiveAgentTab() {
  console.log('[InteractiveAgentTab] Инициализация вкладки диалогового агента сценариев');
}

window._startInteractiveAgent = async function () {
  const inputEl = document.getElementById('agent-user-prompt');
  const prompt = inputEl ? inputEl.value.trim() : '';
  if (!prompt) return;

  try {
    const res = await fetch('/api/v1/interactive-agent/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_prompt: prompt }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const session = await res.json();
    currentAgentSessionId = session.session_id;
    window._renderAgentSession(session);
  } catch (err) {
    console.error('[InteractiveAgentTab] Ошибка запуска агента:', err);
    if (window.toast) window.toast.error('Ошибка агента', err.message);
  }
};

window._submitAgentReply = async function () {
  const replyInput = document.getElementById('agent-reply-input');
  const replyText = replyInput ? replyInput.value.trim() : '';
  if (!replyText || !currentAgentSessionId) return;

  try {
    const res = await fetch(`/api/v1/interactive-agent/sessions/${currentAgentSessionId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_input: replyText }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const session = await res.json();
    if (replyInput) replyInput.value = '';
    window._renderAgentSession(session);
  } catch (err) {
    console.error('[InteractiveAgentTab] Ошибка отправки ответа агенту:', err);
    if (window.toast) window.toast.error('Ошибка агента', err.message);
  }
};

window._renderAgentSession = function (session) {
  const stepperContainer = document.getElementById('agent-stepper-container');
  const sessionBadge = document.getElementById('agent-session-badge');
  if (stepperContainer) stepperContainer.classList.remove('d-none');
  if (sessionBadge) sessionBadge.textContent = session.status;

  const stepsList = document.getElementById('agent-steps-list');
  if (stepsList) {
    stepsList.innerHTML = session.steps.map((st, idx) => {
      let badgeClass = st.status === 'COMPLETED' ? 'bg-success' : (st.status === 'WAITING_INPUT' ? 'bg-warning text-dark' : 'bg-secondary');
      return `
        <div class="list-group-item d-flex justify-content-between align-items-start">
          <div class="ms-2 me-auto">
            <div class="fw-bold">Шаг ${idx + 1}: ${st.title}</div>
            <small class="text-muted">${st.description}</small>
            ${st.result_summary ? `<div class="mt-1 small text-primary"><b>Результат:</b> ${st.result_summary}</div>` : ''}
          </div>
          <span class="badge ${badgeClass}">${st.status}</span>
        </div>
      `;
    }).join('');
  }

  const widget = document.getElementById('agent-interactive-widget');
  if (widget) {
    if (session.status === 'AWAITING_USER_INPUT') {
      const activeStep = session.steps[session.current_step_index];
      const promptTextEl = document.getElementById('agent-prompt-text');
      if (promptTextEl) {
        promptTextEl.textContent = activeStep ? (activeStep.prompt_for_user || 'Требуется ввод данных.') : 'Требуется ввод данных.';
      }
      widget.classList.remove('d-none');
    } else {
      widget.classList.add('d-none');
    }
  }
};

