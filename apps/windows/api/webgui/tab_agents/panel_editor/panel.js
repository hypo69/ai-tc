/**
 * =============================================================================
 * Process Name: Windows AI Agents - Editor & Tools Matrix Panel
 * =============================================================================
 * Description:
 *   Модуль модального редактора параметров агента (создание, редактирование),
 *   матрицы внешних инструментов/навыков, синхронизации провайдеров/моделей,
 *   ползунка температуры и вставки типовых шаблонов промптов (ReAct / JSON).
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_agents/panel_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, fetchJson, showToast } from '../common/ui_utils.js';

/**
 * Заполнение матрицы чекбоксов инструментов в модальном окне редактора.
 */
export function populateToolsMatrix() {
  const container = document.getElementById('agent-tools-matrix');
  if (!container) return;

  container.innerHTML = state.tools
    .map(
      (tool) => `
      <div class="col-md-6">
        <div class="p-3 rounded h-100" style="background: var(--surface-2); border: 1px solid var(--border-color);">
          <div class="form-check form-switch m-0">
            <input class="form-check-input tool-checkbox" type="checkbox" value="${tool.id}" id="tool-chk-${tool.id}">
            <label class="form-check-label small text-body fw-bold" for="tool-chk-${tool.id}">
              ${tool.icon} ${tool.name}
            </label>
          </div>
          <div class="small mt-1 text-muted" style="font-size: 0.8rem; line-height: 1.4;">${tool.description}</div>
        </div>
      </div>
    `
    )
    .join('');

  container.querySelectorAll('.tool-checkbox').forEach((chk) => {
    chk.onchange = updateSelectedToolsCounter;
  });
}

/**
 * Обновление счетчика выбранных инструментов в бейдже заголовка.
 */
export function updateSelectedToolsCounter() {
  const count = document.querySelectorAll('#agent-tools-matrix .tool-checkbox:checked').length;
  const badge = document.getElementById('agent-tools-count');
  if (badge) badge.textContent = `${count} выбрано`;
}

/**
 * Обновление списка доступных моделей при смене ИИ-провайдера.
 * @param {string} providerSelectId - ID выпадающего списка провайдеров
 * @param {string} modelSelectId - ID выпадающего списка моделей
 * @param {string} [selectedModel=''] - Модель по умолчанию
 */
export function updateModelDropdown(providerSelectId, modelSelectId, selectedModel = '') {
  const pSel = document.getElementById(providerSelectId);
  const mSel = document.getElementById(modelSelectId);
  if (!pSel || !mSel) return;

  const prov = state.providers[pSel.value];
  const models = prov?.models ?? [];

  mSel.innerHTML = models.map((m) => `<option value="${m.id}">${m.name || m.id}</option>`).join('');

  if (selectedModel && models.some((m) => m.id === selectedModel)) {
    mSel.value = selectedModel;
  } else if (prov?.default_model) {
    mSel.value = prov.default_model;
  }
}

/**
 * Открытие модального окна создания или редактирования агента.
 * @param {string|null} [agentId=null] - ID редактируемого агента (или null для создания)
 * @param {object|null} [prefillData=null] - Предзаполненные данные из AI-генератора
 */
export function openEditor(agentId = null, prefillData = null) {
  const modalEl = document.getElementById('modal-agent-editor');
  if (!modalEl) return;

  const modeInput = document.getElementById('agent-edit-mode');
  const idInput = document.getElementById('agent-id');
  const nameInput = document.getElementById('agent-name');
  const descInput = document.getElementById('agent-desc');
  const enabledChk = document.getElementById('agent-enabled');
  const providerSel = document.getElementById('agent-provider');
  const tempSlider = document.getElementById('agent-temperature');
  const tempVal = document.getElementById('agent-temp-val');
  const maxStepsInput = document.getElementById('agent-max-steps');
  const timeoutInput = document.getElementById('agent-timeout');
  const promptTa = document.getElementById('agent-system-prompt');

  // Сброс чекбоксов инструментов
  document.querySelectorAll('#agent-tools-matrix .tool-checkbox').forEach((chk) => {
    chk.checked = false;
  });

  if (agentId) {
    const agent = state.agents.find((a) => a.id === agentId);
    if (!agent) return;

    if (modeInput) modeInput.value = 'edit';
    if (idInput) {
      idInput.value = agent.id;
      idInput.disabled = true;
    }
    if (nameInput) nameInput.value = agent.name;
    if (descInput) descInput.value = agent.description ?? '';
    if (enabledChk) enabledChk.checked = Boolean(agent.enabled);
    if (providerSel) providerSel.value = agent.provider ?? 'gemini';

    updateModelDropdown('agent-provider', 'agent-model', agent.model);

    if (tempSlider) {
      tempSlider.value = agent.temperature ?? 0.3;
      if (tempVal) tempVal.textContent = tempSlider.value;
    }
    if (maxStepsInput) maxStepsInput.value = agent.max_steps ?? 15;
    if (timeoutInput) timeoutInput.value = agent.timeout_seconds ?? 60;
    if (promptTa) promptTa.value = agent.system_prompt ?? '';

    (agent.tools ?? []).forEach((tId) => {
      const chk = document.getElementById(`tool-chk-${tId}`);
      if (chk) chk.checked = true;
    });
  } else if (prefillData) {
    if (modeInput) modeInput.value = 'create';
    if (idInput) {
      idInput.value = (prefillData.name || 'agent').toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 25);
      idInput.disabled = false;
    }
    if (nameInput) nameInput.value = prefillData.name ?? 'Новый ИИ-Агент';
    if (descInput) descInput.value = prefillData.description ?? '';
    if (enabledChk) enabledChk.checked = true;
    if (providerSel) providerSel.value = prefillData.provider ?? 'gemini';

    updateModelDropdown('agent-provider', 'agent-model', prefillData.model);

    if (tempSlider) {
      tempSlider.value = prefillData.temperature ?? 0.3;
      if (tempVal) tempVal.textContent = tempSlider.value;
    }
    if (maxStepsInput) maxStepsInput.value = prefillData.max_steps ?? 15;
    if (timeoutInput) timeoutInput.value = 60;
    if (promptTa) promptTa.value = prefillData.system_prompt ?? '';

    (prefillData.recommended_tools ?? []).forEach((tId) => {
      const chk = document.getElementById(`tool-chk-${tId}`);
      if (chk) chk.checked = true;
    });
  } else {
    if (modeInput) modeInput.value = 'create';
    if (idInput) {
      idInput.value = '';
      idInput.disabled = false;
    }
    if (nameInput) nameInput.value = '';
    if (descInput) descInput.value = '';
    if (enabledChk) enabledChk.checked = true;
    if (providerSel) providerSel.value = 'gemini';

    updateModelDropdown('agent-provider', 'agent-model');

    if (tempSlider) {
      tempSlider.value = 0.3;
      if (tempVal) tempVal.textContent = '0.3';
    }
    if (maxStepsInput) maxStepsInput.value = 15;
    if (timeoutInput) timeoutInput.value = 60;
    if (promptTa) promptTa.value = '';
  }

  updateSelectedToolsCounter();
  if (window.bootstrap && window.bootstrap.Modal) {
    new window.bootstrap.Modal(modalEl).show();
  }
}

/**
 * Сохранение конфигурации агента (создание или обновление).
 */
export async function handleSaveAgent() {
  const mode = document.getElementById('agent-edit-mode')?.value ?? 'create';
  const id = document.getElementById('agent-id')?.value.trim();
  const name = document.getElementById('agent-name')?.value.trim();
  const desc = document.getElementById('agent-desc')?.value.trim();
  const enabled = document.getElementById('agent-enabled')?.checked ?? true;
  const provider = document.getElementById('agent-provider')?.value ?? 'gemini';
  const model = document.getElementById('agent-model')?.value ?? 'gemini-3.1-flash';
  const temperature = parseFloat(document.getElementById('agent-temperature')?.value ?? '0.3');
  const max_steps = parseInt(document.getElementById('agent-max-steps')?.value ?? '15', 10);
  const timeout_seconds = parseInt(document.getElementById('agent-timeout')?.value ?? '60', 10);
  const system_prompt = document.getElementById('agent-system-prompt')?.value.trim() ?? '';

  if (!id || !name) {
    showToast('ID и Название агента обязательны для заполнения', 'warning');
    return;
  }

  const selectedTools = [];
  document.querySelectorAll('#agent-tools-matrix .tool-checkbox:checked').forEach((chk) => {
    selectedTools.push(chk.value);
  });

  const payload = {
    id,
    name,
    description: desc,
    enabled,
    provider,
    model,
    temperature,
    max_steps,
    timeout_seconds,
    tools: selectedTools,
    system_prompt
  };

  const saveBtn = document.getElementById('btn-save-agent');
  if (saveBtn) saveBtn.disabled = true;

  try {
    if (mode === 'create') {
      await fetchJson('/api/v1/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showToast(`Агент "${name}" успешно создан!`, 'success');
    } else {
      await fetchJson(`/api/v1/agents/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showToast(`Агент "${name}" успешно обновлен!`, 'success');
    }

    const modalEl = document.getElementById('modal-agent-editor');
    if (window.bootstrap && window.bootstrap.Modal) {
      window.bootstrap.Modal.getInstance(modalEl)?.hide();
    }
    if (typeof window.loadAllAgentsData === 'function') {
      await window.loadAllAgentsData();
    }
  } catch (err) {
    console.error('[AgentsTab] Error saving agent:', err);
    showToast(`Ошибка сохранения: ${err.message}`, 'danger');
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * Привязка событий элементов управления модального окна редактора.
 */
export function bindEditorEvents() {
  document.getElementById('btn-open-create-agent')?.addEventListener('click', () => openEditor(null));

  document.getElementById('agent-provider')?.addEventListener('change', () => {
    updateModelDropdown('agent-provider', 'agent-model');
  });

  const tempSlider = document.getElementById('agent-temperature');
  const tempVal = document.getElementById('agent-temp-val');
  if (tempSlider && tempVal && !tempSlider._bound) {
    tempSlider._bound = true;
    tempSlider.oninput = () => {
      tempVal.textContent = tempSlider.value;
    };
  }

  const saveBtn = document.getElementById('btn-save-agent');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', handleSaveAgent);
  }

  // Шаблоны системных промптов
  document.getElementById('btn-insert-react-template')?.addEventListener('click', () => {
    const promptInput = document.getElementById('agent-system-prompt');
    if (promptInput) {
      promptInput.value =
        'Ты автономный ReAct-агент Mediteka.\n\n' +
        'ПРИНЦИП РАБОТЫ (Thought -> Action -> Observation):\n' +
        '1. Тщательно анализируй вопрос пользователя (Thought).\n' +
        '2. Выбирай необходимый инструмент из доступных (Action) с корректными параметрами.\n' +
        '3. Анализируй результат выполнения инструмента (Observation).\n' +
        '4. Сформируй итоговый структурированный ответ пользователю.\n\n' +
        'ФОРМАТ ОТВЕТА:\n' +
        '- Используй Markdown с красивым форматированием (списки, жирный шрифт, эмодзи).\n' +
        '- Не выводи технические ошибки напрямую, объясняй суть решения.';
    }
  });

  document.getElementById('btn-insert-json-template')?.addEventListener('click', () => {
    const promptInput = document.getElementById('agent-system-prompt');
    if (promptInput) {
      promptInput.value =
        'Ты специализированный аналитический агент Mediteka.\n\n' +
        'Твоя задача: структурировать полученные данные и всегда отвечать строго валидным JSON-объектом без лишнего обрамления и markdown-блоков.\n\n' +
        'Пример структуры:\n{\n  "status": "success",\n  "items": [],\n  "summary": "краткое резюме"\n}';
    }
  });
}
