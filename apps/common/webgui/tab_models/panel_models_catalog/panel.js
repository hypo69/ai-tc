/**
 * Модуль каталога моделей ИИ, избранных чипов и переключения провайдеров.
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_models_catalog/panel.js
 * Updated: 2026-11-01 17:37:00
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';

window.userFavoriteModels = window.userFavoriteModels || {};

/**
 * Очищает префикс провайдера из имени модели.
 * @param {string} name - Полное имя модели.
 * @returns {string} Очищенное имя модели.
 */
export function stripModelPrefix(name) {
  if (!name) return '';
  return String(name)
    .replace(/^(gemini|gemini_cli|foundry|ollama|openai|hf|onnx):+/i, '')
    .replace(/^agy-+/i, '')
    .trim();
}

/**
 * Сохраняет выбранную модель и провайдер в настройках профиля.
 * @param {string} selectedModel - Имя модели.
 * @param {string} [selectedProvider=''] - Имя провайдера.
 * @param {boolean} [showNotify=true] - Показывать ли тост-уведомление.
 */
export async function persistSelectedModelAndProvider(selectedModel, selectedProvider = '', showNotify = true) {
  if (!selectedModel) return;
  const providerSelect = document.getElementById('provider-tab-select');
  const actualProvider = selectedProvider || (providerSelect ? providerSelect.value : '');

  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await Promise.allSettled([
      fetchFn('/auth/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel, provider: actualProvider })
      }),
      fetchFn('/api/v1/tc/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel, provider: actualProvider, save_to_config: true })
      })
    ]);

    const savedCardBadge = document.getElementById('saved-default-model-badge');
    if (savedCardBadge) {
      savedCardBadge.textContent = selectedModel;
      savedCardBadge.className = 'badge bg-success font-monospace px-2 py-1';
      savedCardBadge.title = `Сохранена модель: ${selectedModel}`;
    }

    if (showNotify) {
      showModelsNotification(`Модель "${selectedModel}" успешно сохранена`, 'success');
    }

    if (typeof window.updateChatBadges === 'function') {
      window.updateChatBadges(selectedModel);
    }
  } catch (err) {
    console.error('Failed to persist model:', err);
    if (showNotify) {
      showModelsNotification('Ошибка сохранения модели: ' + err.message, 'danger');
    }
  }
}

/**
 * Обновляет состояние кнопки избранного, иконки звезды и заметок.
 * @param {HTMLSelectElement} [modelSelect] - Селектор моделей.
 */
export function updateModelFavoriteUI(modelSelect) {
  if (!modelSelect) modelSelect = document.getElementById('models-tab-select');
  const curModel = modelSelect ? modelSelect.value : '';
  const starIcon = document.getElementById('favorite-star-icon');
  const favBtn = document.getElementById('btn-model-toggle-favorite');
  const statusBadge = document.getElementById('model-fav-status-badge');
  const noteInput = document.getElementById('model-user-note');

  const favData = curModel && window.userFavoriteModels ? window.userFavoriteModels[curModel] : null;
  const isFav = Boolean(favData);

  if (starIcon) {
    starIcon.className = isFav ? 'bi bi-star-fill text-warning' : 'bi bi-star';
  }
  if (favBtn) {
    if (isFav) {
      favBtn.classList.remove('btn-outline-warning');
      favBtn.classList.add('btn-warning', 'text-dark');
      favBtn.title = 'Удалить модель из избранного';
    } else {
      favBtn.classList.remove('btn-warning', 'text-dark');
      favBtn.classList.add('btn-outline-warning');
      favBtn.title = 'Добавить модель в избранное';
    }
  }
  if (statusBadge) {
    if (isFav) {
      statusBadge.textContent = 'В избранном ⭐';
      statusBadge.className = 'badge bg-warning text-dark font-monospace';
    } else {
      statusBadge.textContent = 'Не в избранном';
      statusBadge.className = 'badge bg-secondary-subtle text-secondary-emphasis border font-monospace';
    }
  }
  if (noteInput && document.activeElement !== noteInput) {
    noteInput.value = favData ? (favData.note || '') : '';
  }

  renderFavoriteModelsChips(modelSelect);
}

/**
 * Добавляет значок звезды ⭐ к названиям избранных моделей в списке options.
 * @param {HTMLSelectElement} modelSelect - Селектор моделей.
 */
export function updateModelSelectOptions(modelSelect) {
  if (!modelSelect) return;
  const options = modelSelect.querySelectorAll('option');
  options.forEach(opt => {
    const val = opt.value;
    if (!val) return;
    const isFav = window.userFavoriteModels && Boolean(window.userFavoriteModels[val]);
    let text = opt.textContent.replace(/^⭐\s*/, '');
    if (isFav) {
      opt.textContent = `⭐ ${text}`;
    } else {
      opt.textContent = text;
    }
  });
}

/**
 * Отрисовывает интерактивные чипы избранных моделей.
 * @param {HTMLSelectElement} modelSelect - Селектор моделей.
 */
export function renderFavoriteModelsChips(modelSelect) {
  const container = document.getElementById('favorite-models-list');
  const section = document.getElementById('favorite-models-section');
  if (!container || !section) return;

  const favKeys = Object.keys(window.userFavoriteModels || {});
  if (favKeys.length === 0) {
    section.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  section.style.display = 'block';
  container.innerHTML = '';

  favKeys.forEach(modelName => {
    const data = window.userFavoriteModels[modelName] || {};
    const note = data.note ? `\nЗаметка: ${data.note}` : '';
    
    const chip = document.createElement('div');
    chip.className = 'btn-group btn-group-sm mb-1 me-1';
    chip.role = 'group';

    const btnSelect = document.createElement('button');
    btnSelect.type = 'button';
    btnSelect.className = modelSelect && modelSelect.value === modelName 
      ? 'btn btn-sm btn-warning text-dark py-0 px-2 font-monospace'
      : 'btn btn-sm btn-outline-warning py-0 px-2 font-monospace';
    btnSelect.innerHTML = `<i class="bi bi-star-fill me-1 text-warning"></i>${escapeHtml(modelName)}`;
    btnSelect.title = `Выбрать модель: ${modelName}${note}`;
    btnSelect.onclick = async () => {
      if (modelSelect) {
        const providerSelect = document.getElementById('provider-tab-select');
        let matchedProv = providerSelect ? providerSelect.value : '';
        if (providerSelect && window._modelsGrouped) {
          for (const p of Object.keys(window._modelsGrouped)) {
            if (window._modelsGrouped[p]?.includes(modelName)) {
              matchedProv = p;
              if (providerSelect.value !== p) {
                providerSelect.value = p;
                if (typeof window._populateModels === 'function') {
                  window._populateModels(p, window._modelsGrouped[p]);
                }
              }
              break;
            }
          }
        }
        modelSelect.value = modelName;
        updateModelFavoriteUI(modelSelect);
        await persistSelectedModelAndProvider(modelName, matchedProv, true);
      }
    };

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'btn btn-sm btn-outline-danger py-0 px-1';
    btnRemove.innerHTML = '<i class="bi bi-x"></i>';
    btnRemove.title = `Удалить ${modelName} из избранного`;
    btnRemove.onclick = async (e) => {
      e.stopPropagation();
      try {
        const fetchFn = (window.api && window.api.fetch) || fetch;
        await fetchFn(`/auth/favorites/${encodeURIComponent(modelName)}`, { method: 'DELETE' });
        delete window.userFavoriteModels[modelName];
        updateModelFavoriteUI(modelSelect);
        updateModelSelectOptions(modelSelect);
        showModelsNotification(`Модель "${modelName}" удалена из избранного`, 'info');
      } catch (err) {
        showModelsNotification('Ошибка удаления: ' + err.message, 'danger');
      }
    };

    chip.appendChild(btnSelect);
    chip.appendChild(btnRemove);
    container.appendChild(chip);
  });
}

/**
 * Загружает список моделей и провайдеров с бэкенда.
 * @param {HTMLSelectElement} modelSelect - Селектор моделей.
 * @param {HTMLButtonElement} saveBtn - Кнопка сохранения.
 * @param {boolean} [forceRefresh=false] - Флаг принудительного обновления.
 */
export async function loadTabModels(modelSelect, saveBtn, forceRefresh = false) {
  const providerSelect = document.getElementById('provider-tab-select');
  if (providerSelect) providerSelect.innerHTML = '';
  modelSelect.innerHTML = '';
  
  let modelsGrouped = {};
  let unsupportedGrouped = {};
  
  const fetchFn = (window.api && window.api.fetch) || fetch;

  const fetchModels = async (force = false) => {
    try {
      const showAll = document.getElementById('show-all-models-check')?.checked ?? false;
      const params = new URLSearchParams();
      if (force) params.append('refresh', 'true');
      if (showAll) params.append('include_unsupported', 'true');
      const url = '/api/v1/chat/models' + (params.toString() ? '?' + params.toString() : '');
      const modelsData = await fetchFn(url);
      const data = typeof modelsData.json === 'function' ? await modelsData.json() : modelsData;
      let grouped = data.models || {};
      if (Array.isArray(grouped)) {
        grouped = { 'gemini': grouped };
      }
      unsupportedGrouped = data.unsupported_models || {};
      return grouped;
    } catch (err) {
      console.error('Error loading AI models:', err);
      showModelsNotification('Ошибка загрузки моделей AI: ' + err.message, 'danger');
      return {};
    }
  };

  modelsGrouped = await fetchModels(forceRefresh);
  window._modelsGrouped = modelsGrouped;
  if (forceRefresh) {
    showModelsNotification('Список моделей успешно обновлен', 'success');
  }

  try {
    const settingsData = await fetchFn('/auth/settings');
    const sData = typeof settingsData.json === 'function' ? await settingsData.json() : settingsData;
    if (sData && sData.favorite_models) {
      window.userFavoriteModels = sData.favorite_models;
    } else {
      const favRes = await fetchFn('/auth/favorites');
      const fData = typeof favRes.json === 'function' ? await favRes.json() : favRes;
      if (fData && fData.favorites) {
        window.userFavoriteModels = fData.favorites;
      }
    }
  } catch (e) {
    console.warn('Failed to load favorite models:', e);
  }

  const providers = Object.keys(modelsGrouped).filter(p => modelsGrouped[p] && modelsGrouped[p].length > 0);

  if (providers.length === 0) {
    if (providerSelect) {
      providerSelect.innerHTML = '<option value="">Нет доступных провайдеров</option>';
    }
    modelSelect.innerHTML = '<option value="">Нет доступных моделей</option>';
    saveBtn.disabled = true;
    updateModelFavoriteUI(modelSelect);
    return;
  }
  
  if (providerSelect) {
    providerSelect.innerHTML = '';
    providers.forEach(p => {
      const option = document.createElement('option');
      option.value = p;
      option.textContent = p.charAt(0).toUpperCase() + p.slice(1);
      providerSelect.appendChild(option);
    });
  }

  const populateModels = (provider, providerModelsList) => {
    modelSelect.innerHTML = '';
    const providerModels = providerModelsList !== undefined ? providerModelsList : (modelsGrouped[provider] || []);
    const unsupList = unsupportedGrouped[provider] || [];
    if (!providerModels || providerModels.length === 0) {
      modelSelect.innerHTML = '<option value="">Нет моделей</option>';
      saveBtn.disabled = true;
    } else {
      providerModels.forEach(modelName => {
        const option = document.createElement('option');
        option.value = modelName;
        let cleanName = stripModelPrefix(modelName);
        
        const isFav = window.userFavoriteModels && Boolean(window.userFavoriteModels[modelName]);
        const isUnsupported = unsupList.includes(cleanName) || unsupList.includes(modelName);
        
        let label = cleanName || modelName;
        if (isFav) label = `⭐ ${label}`;
        if (isUnsupported) label = `${label} ⚠️ [отфильтрована]`;

        option.textContent = label;
        modelSelect.appendChild(option);
      });
      saveBtn.disabled = false;
    }
    updateModelFavoriteUI(modelSelect);
  };
  window._populateModels = populateModels;

  if (providerSelect) {
    providerSelect.onchange = async () => {
      const chosenProvider = providerSelect.value;
      populateModels(chosenProvider, modelsGrouped[chosenProvider]);
      if (modelSelect.options.length > 0) {
        modelSelect.selectedIndex = 0;
      }
      saveBtn.disabled = !modelSelect.value;
      updateModelFavoriteUI(modelSelect);
      if (modelSelect.value) {
        await persistSelectedModelAndProvider(modelSelect.value, chosenProvider, true);
      }
    };
  }

  let activeProvider = '';
  let activeModel = '';

  try {
    const isTcRoute = window.location.pathname.startsWith('/tc') || window.location.pathname.startsWith('/apps');
    const query = isTcRoute ? '?profile=tc' : '';
    
    try {
      const activeResp = await fetchFn(`/api/v1/chat/active-model${query}`);
      const aData = typeof activeResp.json === 'function' ? await activeResp.json() : activeResp;
      if (aData && aData.model) {
        activeModel = aData.model;
        activeProvider = aData.provider || '';
      }
    } catch (_) {}

    if (!activeModel) {
      const settingsData = await fetchFn('/auth/settings');
      const sData = typeof settingsData.json === 'function' ? await settingsData.json() : settingsData;
      if (sData && sData.model) {
        activeModel = sData.model;
        if (sData.provider) activeProvider = sData.provider;
      }
    }
  } catch (err) {
    console.error('Error loading active model settings:', err);
  }

  let targetProvider = activeProvider ? activeProvider.toLowerCase() : '';
  const cleanActiveModel = stripModelPrefix(activeModel);

  if (!targetProvider && activeModel) {
    if (activeModel.startsWith('foundry:')) targetProvider = 'foundry';
    else if (activeModel.startsWith('ollama:')) targetProvider = 'ollama';
    else if (activeModel.startsWith('agy-')) targetProvider = 'agy';
    else if (activeModel.startsWith('gemini_cli:')) targetProvider = 'gemini_cli';
    else if (activeModel.startsWith('hf:') || activeModel.startsWith('hf::')) targetProvider = 'hf';
    else if (activeModel.startsWith('onnx:') || activeModel.startsWith('onnx::')) targetProvider = 'onnx';
    else if (activeModel.toLowerCase().includes('gemini')) targetProvider = 'gemini';
  }

  let matchedProvider = providers.find(p => p.toLowerCase() === targetProvider);

  if (!matchedProvider && activeModel) {
    for (const p of providers) {
      const list = modelsGrouped[p] || [];
      if (list.some(m => m === activeModel || stripModelPrefix(m) === cleanActiveModel)) {
        matchedProvider = p;
        break;
      }
    }
  }

  if (!matchedProvider) {
    matchedProvider = providers.includes('gemini') ? 'gemini' : providers[0];
  }

  if (providerSelect) {
    providerSelect.value = matchedProvider;
  }
  populateModels(matchedProvider, modelsGrouped[matchedProvider]);

  let matchedModelVal = null;
  const currentOptions = Array.from(modelSelect.options);

  if (activeModel) {
    const exactOpt = currentOptions.find(opt => opt.value === activeModel);
    if (exactOpt) {
      matchedModelVal = exactOpt.value;
    } else {
      const cleanOpt = currentOptions.find(opt => stripModelPrefix(opt.value) === cleanActiveModel);
      if (cleanOpt) {
        matchedModelVal = cleanOpt.value;
      }
    }
  }

  if (matchedModelVal) {
    modelSelect.value = matchedModelVal;
  } else if (currentOptions.length > 0) {
    modelSelect.selectedIndex = 0;
  }

  saveBtn.disabled = !modelSelect.value;
  updateModelFavoriteUI(modelSelect);

  const effectiveModelName = modelSelect.value || activeModel;
  const savedCardBadge = document.getElementById('saved-default-model-badge');
  if (savedCardBadge) {
    if (effectiveModelName) {
      savedCardBadge.textContent = effectiveModelName;
      savedCardBadge.className = 'badge bg-success font-monospace px-2 py-1';
      savedCardBadge.title = `В профиле сохранена модель: ${effectiveModelName}`;
    } else {
      savedCardBadge.textContent = 'Не задана (системный fallback)';
      savedCardBadge.className = 'badge bg-secondary font-monospace px-2 py-1';
    }
  }

  if (typeof window.updateChatBadges === 'function') {
    window.updateChatBadges(effectiveModelName);
  }
}
