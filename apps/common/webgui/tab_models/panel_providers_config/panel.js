/**
 * Модуль конфигурации локальных и облачных провайдеров (Foundry, Ollama, AGY, ONNX)
 * и управления системной инструкцией ИИ.
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_providers_config/panel.js
 * Updated: 2026-11-01 17:37:00
 */

import { showModelsNotification } from '../common/ui_utils.js';

/**
 * Загружает конфигурацию Microsoft Foundry Local.
 */
export async function loadFoundryConfig() {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/foundry/config');
    const config = typeof res.json === 'function' ? await res.json() : res;

    const enabledInput = document.getElementById('foundry-enabled');
    const urlInput = document.getElementById('foundry-url');
    const keyInput = document.getElementById('foundry-key');
    const modelInput = document.getElementById('foundry-model');
    
    if (enabledInput) enabledInput.checked = config.enabled || false;
    if (urlInput) urlInput.value = config.url || '';
    if (keyInput) keyInput.value = config.key || '';
    if (modelInput) modelInput.value = config.model || '';
  } catch (err) {
    console.error('Ошибка загрузки настроек Foundry:', err);
  }
}

/**
 * Загружает конфигурацию Ollama Local Server.
 */
export async function loadOllamaConfig() {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/ollama/config');
    const config = typeof res.json === 'function' ? await res.json() : res;

    const enabledInput = document.getElementById('ollama-enabled');
    const urlInput = document.getElementById('ollama-url');
    const modelInput = document.getElementById('ollama-model');
    
    if (enabledInput) enabledInput.checked = config.enabled || false;
    if (urlInput) urlInput.value = config.url || '';
    if (modelInput) modelInput.value = config.model || '';
  } catch (err) {
    console.error('Ошибка загрузки настроек Ollama:', err);
  }
}

/**
 * Загружает конфигурацию Antigravity (AGY).
 */
export async function loadAgyConfig() {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const modelSelect = document.getElementById('agy-model');
    if (modelSelect) {
      try {
        const modelsRes = await fetchFn('/api/v1/chat/models');
        const modelsData = typeof modelsRes.json === 'function' ? await modelsRes.json() : modelsRes;
        const agyList = modelsData.models?.agy || [];
        if (agyList.length > 0) {
          const curVal = modelSelect.value;
          modelSelect.innerHTML = '';
          agyList.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            modelSelect.appendChild(opt);
          });
          if (curVal && agyList.includes(curVal)) {
            modelSelect.value = curVal;
          }
        }
      } catch (e) {
        console.error('Ошибка загрузки моделей AGY:', e);
      }
    }

    const res = await fetchFn('/api/agy/config');
    const config = typeof res.json === 'function' ? await res.json() : res;

    const enabledInput = document.getElementById('agy-enabled');
    const keyInput = document.getElementById('agy-key');
    
    if (enabledInput) enabledInput.checked = config.enabled ?? true;
    if (modelSelect && config.model) modelSelect.value = config.model;
    if (keyInput) keyInput.value = config.key || '';
  } catch (err) {
    console.error('Ошибка загрузки настроек Antigravity (AGY):', err);
  }
}

/**
 * Загружает конфигурацию ONNX Runtime / Olive.
 */
export async function loadOnnxConfig() {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/onnx/config');
    const config = typeof res.json === 'function' ? await res.json() : res;

    const enabledInput = document.getElementById('onnx-enabled');
    const epSelect = document.getElementById('onnx-execution-provider');
    const dirInput = document.getElementById('onnx-models-dir');
    const modelInput = document.getElementById('onnx-default-model');
    const precSelect = document.getElementById('onnx-olive-precision');

    if (enabledInput) enabledInput.checked = config.enabled ?? true;
    if (epSelect && config.execution_provider) epSelect.value = config.execution_provider;
    if (dirInput && config.models_dir) dirInput.value = config.models_dir;
    if (modelInput && config.default_model) modelInput.value = config.default_model;
    if (precSelect && config.olive_precision) precSelect.value = config.olive_precision;
  } catch (err) {
    console.error('Ошибка загрузки настроек ONNX / Olive:', err);
  }
}

/**
 * Загружает текущую системную инструкцию из доступных эндпоинтов.
 */
export async function loadSystemInstruction() {
  const editor = document.getElementById('system-instruction-editor');
  const statusBadge = document.getElementById('system-instruction-status');
  if (!editor) return;
  
  editor.disabled = true;
  if (statusBadge) {
    statusBadge.className = 'badge bg-warning text-dark';
    statusBadge.textContent = 'Загрузка...';
    statusBadge.style.removeProperty('display');
  }
  
  try {
    let instructionText = '';
    const endpoints = [
      '/api/v1/tc/model-instruction',
      '/api/v1/chat/model-instruction',
      '/api/admin/system_instruction',
      '/api/v1/admin/system_instruction'
    ];

    const fetchFn = (window.api && window.api.fetch) || fetch;
    for (const ep of endpoints) {
      try {
        const res = await fetchFn(ep);
        const data = typeof res.json === 'function' ? await res.json() : res;
        if (data && (data.instruction || data.system_instruction || data.content)) {
          instructionText = data.instruction || data.system_instruction || data.content;
          break;
        }
      } catch (_) {}
    }

    editor.value = instructionText || '';
    if (statusBadge) {
      statusBadge.className = 'badge bg-success';
      statusBadge.textContent = 'Загружено';
      setTimeout(() => {
        if (statusBadge) statusBadge.style.display = 'none';
      }, 2500);
    }
  } catch (err) {
    console.error('Ошибка загрузки системной инструкции:', err);
    if (statusBadge) {
      statusBadge.className = 'badge bg-danger';
      statusBadge.textContent = 'Ошибка';
      statusBadge.style.removeProperty('display');
    }
    showModelsNotification('Ошибка загрузки системной инструкции: ' + err.message, 'danger');
  } finally {
    editor.disabled = false;
  }
}

/**
 * Сохраняет отредактированную системную инструкцию.
 */
export async function saveSystemInstruction() {
  const editor = document.getElementById('system-instruction-editor');
  const saveBtn = document.getElementById('btn-save-instruction');
  const statusBadge = document.getElementById('system-instruction-status');
  if (!editor || !saveBtn) return;

  const originalHtml = saveBtn.innerHTML;
  saveBtn.disabled = true;
  saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Сохранение...';

  try {
    const textVal = editor.value;
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await Promise.allSettled([
      fetchFn('/api/v1/tc/model-instruction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction: textVal, content: textVal, system_instruction: textVal, save_to_disk: true })
      }),
      fetchFn('/api/v1/chat/model-instruction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction: textVal, content: textVal, system_instruction: textVal, save_to_disk: true })
      }),
      fetchFn('/api/admin/system_instruction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: textVal })
      })
    ]);

    showModelsNotification('✅ Системная инструкция успешно сохранена', 'success');
    if (statusBadge) {
      statusBadge.className = 'badge bg-success';
      statusBadge.textContent = 'Сохранено';
      statusBadge.style.removeProperty('display');
      setTimeout(() => {
        if (statusBadge) statusBadge.style.display = 'none';
      }, 3000);
    }
  } catch (err) {
    console.error('Ошибка сохранения системной инструкции:', err);
    if (statusBadge) {
      statusBadge.className = 'badge bg-danger';
      statusBadge.textContent = 'Ошибка сохранения';
      statusBadge.style.removeProperty('display');
    }
    showModelsNotification('Ошибка сохранения: ' + err.message, 'danger');
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = originalHtml;
  }
}
