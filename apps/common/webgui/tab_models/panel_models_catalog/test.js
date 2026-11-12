/**
 * Модуль тестирования моделей LLM и отмены текущих запросов.
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_models_catalog/test.js
 * Updated: 2026-11-01 17:37:00
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';

let modelTestAbortController = null;

/**
 * Отменяет активный проверочный запрос к модели.
 */
export function cancelModelTest() {
  if (modelTestAbortController) {
    try {
      modelTestAbortController.abort();
    } catch (e) {
      console.warn('Error aborting model test:', e);
    }
    modelTestAbortController = null;
  }
}

/**
 * Выполняет тестовый запрос к выбранной модели.
 */
export async function executeModelTest() {
  const providerSelect = document.getElementById('provider-tab-select');
  const modelSelect = document.getElementById('models-tab-select');
  const promptInput = document.getElementById('model-test-prompt');
  const testBtn = document.getElementById('btn-model-test-send');
  const cancelBtn = document.getElementById('btn-model-test-cancel');
  const resultContainer = document.getElementById('model-test-result');

  if (!testBtn || !resultContainer) return;

  const provider = providerSelect ? providerSelect.value : '';
  const model = modelSelect ? modelSelect.value : '';
  const message = promptInput ? promptInput.value.trim() : '';

  if (!model) {
    showModelsNotification('Выберите модель для тестирования!', 'warning');
    return;
  }

  if (!message) {
    showModelsNotification('Введите текст проверочного запроса!', 'warning');
    if (promptInput) promptInput.focus();
    return;
  }

  cancelModelTest();
  modelTestAbortController = new AbortController();

  testBtn.disabled = true;
  const originalBtnHtml = testBtn.innerHTML;
  testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Тест...';

  if (cancelBtn) {
    cancelBtn.style.display = 'inline-block';
    cancelBtn.disabled = false;
  }

  resultContainer.style.display = 'block';
  resultContainer.innerHTML = `
    <div class="d-flex justify-content-between align-items-center text-info small">
      <div class="d-flex align-items-center text-truncate">
        <span class="spinner-border spinner-border-sm me-2 flex-shrink-0" role="status"></span>
        <span class="text-truncate">Отправка запроса в <strong>${escapeHtml(model)}</strong> (${escapeHtml(provider)})...</span>
      </div>
      <button class="btn btn-outline-danger btn-sm py-0 px-2 rounded ms-2 flex-shrink-0" id="btn-model-test-cancel-inner" type="button" title="Отменить проверочный запрос">
        <i class="bi bi-stop-circle me-1"></i> Отмена
      </button>
    </div>
  `;

  const cancelInnerBtn = document.getElementById('btn-model-test-cancel-inner');
  if (cancelInnerBtn) {
    cancelInnerBtn.onclick = cancelModelTest;
  }

  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/v1/chat/test-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: modelTestAbortController.signal,
      body: JSON.stringify({
        provider: provider,
        model: model,
        message: message
      })
    });

    const data = typeof res.json === 'function' ? await res.json() : res;

    if (data && data.status === 'success') {
      resultContainer.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <div>
            <span class="badge bg-success me-2"><i class="bi bi-check-circle me-1"></i>200 OK</span>
            <span class="text-secondary small font-monospace">⚡ ${data.duration_ms || 0} ms</span>
          </div>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(data.model || model)}</span>
        </div>
        <div class="small mt-1 font-monospace" style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(data.response || 'Пустой ответ от модели')}</div>
      `;
    } else {
      const errMsg = (data && data.message) ? data.message : 'Неизвестная ошибка при запросе к модели';
      resultContainer.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <div>
            <span class="badge bg-danger me-2"><i class="bi bi-x-circle me-1"></i>Ошибка</span>
            <span class="text-secondary small font-monospace">⚡ ${data?.duration_ms || 0} ms</span>
          </div>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(model)}</span>
        </div>
        <div class="text-danger small mt-1 font-monospace" style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(errMsg)}</div>
      `;
    }
  } catch (err) {
    if (err.name === 'AbortError' || err.message?.toLowerCase().includes('abort')) {
      resultContainer.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <span class="badge bg-warning text-dark"><i class="bi bi-slash-circle me-1"></i>Отменено</span>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(model)}</span>
        </div>
        <div class="text-warning small mt-1 font-monospace"><i class="bi bi-info-circle me-1"></i>Запрос отменен пользователем.</div>
      `;
    } else {
      console.error('Error during model test request:', err);
      resultContainer.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Ошибка сети/API</span>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(model)}</span>
        </div>
        <div class="text-danger small mt-1 font-monospace" style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(err.message || 'Ошибка соединения')}</div>
      `;
    }
  } finally {
    modelTestAbortController = null;
    testBtn.disabled = false;
    testBtn.innerHTML = originalBtnHtml;
    if (cancelBtn) {
      cancelBtn.style.display = 'none';
    }
  }
}
