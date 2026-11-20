/**
 * =============================================================================
 * Process Name: Windows AI Agents - AI Prompt Architect Panel
 * =============================================================================
 * Description:
 *   Модуль генерации спецификаций, промптов и рекомендованных инструментов
 *   для новых ИИ-агентов на основе естественного описания задачи с использованием
 *   выбранной LLM-модели (Gemini / Foundry / Ollama).
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_agents/panel_ai_builder
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, fetchJson, showToast } from '../common/ui_utils.js';
import { updateModelDropdown, openEditor } from '../panel_editor/panel.js';

/**
 * Открытие модального окна AI-Архитектора агентов.
 */
export function openAiBuilder() {
  const modalEl = document.getElementById('modal-ai-builder');
  if (!modalEl) return;

  const promptInput = document.getElementById('ai-builder-prompt');
  const resultBox = document.getElementById('ai-builder-result');
  if (promptInput) promptInput.value = '';
  if (resultBox) resultBox.classList.add('d-none');
  state.lastGeneratedSpec = null;

  if (window.bootstrap && window.bootstrap.Modal) {
    new window.bootstrap.Modal(modalEl).show();
  }
}

/**
 * Запуск генерации спецификации агента выбранной LLM-моделью.
 */
export async function handleRunAiGenerate() {
  const taskDesc = document.getElementById('ai-builder-prompt')?.value.trim();
  const provider = document.getElementById('ai-builder-provider')?.value ?? 'gemini';
  const model = document.getElementById('ai-builder-model')?.value ?? 'gemini-3.1-flash';

  if (!taskDesc) {
    showToast('Пожалуйста, опишите задачу агента', 'warning');
    return;
  }

  const runBtn = document.getElementById('btn-run-ai-generate');
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Анализ задачи и генерация...';
  }

  try {
    const res = await fetchJson('/api/v1/agents/generate-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_description: taskDesc, provider, model })
    });

    if (res?.data) {
      state.lastGeneratedSpec = { ...res.data, provider, model };
      const resultBox = document.getElementById('ai-builder-result');
      const previewBox = document.getElementById('ai-builder-preview-box');
      if (resultBox && previewBox) {
        resultBox.classList.remove('d-none');
        previewBox.innerHTML = `
          <div><strong class="text-info">Название:</strong> <span class="text-body fw-bold">${res.data.name}</span></div>
          <div class="mt-1"><strong class="text-muted">Описание:</strong> <span class="text-body">${res.data.description}</span></div>
          <div class="mt-1"><strong class="text-success">Инструменты:</strong> <span class="text-body">${(res.data.recommended_tools ?? []).join(', ') || 'нет'}</span></div>
          <div class="mt-2 p-2 rounded" style="background: var(--surface-1); border: 1px solid var(--border-color); color: var(--text-color); white-space: pre-wrap; font-size: 0.85rem; line-height: 1.45;">${res.data.system_prompt}</div>
        `;
      }
      showToast('Спецификация агента успешно сгенерирована!', 'success');
    }
  } catch (err) {
    console.error('[AgentsTab] AI Generator error:', err);
    showToast(`Ошибка генерации: ${err.message}`, 'danger');
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = '<i class="bi bi-stars me-1"></i> Сгенерировать спецификацию';
    }
  }
}

/**
 * Привязка событий элементов управления модального окна AI-Архитектора.
 */
export function bindAiBuilderEvents() {
  document.getElementById('btn-open-ai-builder')?.addEventListener('click', openAiBuilder);

  document.getElementById('ai-builder-provider')?.addEventListener('change', () => {
    updateModelDropdown('ai-builder-provider', 'ai-builder-model');
  });

  document.getElementById('btn-run-ai-generate')?.addEventListener('click', handleRunAiGenerate);

  document.getElementById('btn-apply-ai-generated')?.addEventListener('click', () => {
    if (!state.lastGeneratedSpec) return;
    const builderModalEl = document.getElementById('modal-ai-builder');
    if (window.bootstrap && window.bootstrap.Modal) {
      window.bootstrap.Modal.getInstance(builderModalEl)?.hide();
    }
    openEditor(null, state.lastGeneratedSpec);
  });
}
