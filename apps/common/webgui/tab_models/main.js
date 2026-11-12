/**
 * =============================================================================
 * Название: Вкладка управления моделями ИИ и API-ключами - Главный оркестратор
 * =============================================================================
 * Описание:
 *   Модуль инициализации интерфейса управления моделями, провайдерами,
 *   ключами Google Gemini/AGY и аккаунтами Google.
 *
 * Файл: apps/ai_assistant/api/webgui/tab_models/main.js
 * Пакет: apps/ai_assistant/api/webgui/tab_models
 * Автор: hypo69
 * Updated: 2026-11-03 11:46:00
 * =============================================================================
 */

import { showModelsNotification } from './common/ui_utils.js';
import {
  loadTabModels,
  updateModelFavoriteUI,
  persistSelectedModelAndProvider,
  stripModelPrefix,
  renderFavoriteModelsChips
} from './panel_models_catalog/panel.js';
import {
  executeModelTest,
  cancelModelTest
} from './panel_models_catalog/test.js';
import {
  refreshKeysList,
  activateApiKey,
  openKeyTestModal,
  runKeyTest,
  toggleKeyStatus,
  resetKeyQuota,
  deleteKey
} from './panel_gemini_keys/panel.js';
import {
  refreshAgyKeysList,
  activateAgyKey,
  toggleAgyKeyStatus,
  resetAgyKeyQuota,
  deleteAgyKey
} from './panel_agy_keys/panel.js';
import {
  refreshGoogleAccountsList,
  handleAddGoogleAccount,
  setGoogleAccountDefault,
  resetGoogleAccountStatus,
  testGoogleAccount,
  deleteGoogleAccount
} from './panel_google_accounts/panel.js';
import {
  loadSystemInstruction,
  saveSystemInstruction
} from './panel_providers_config/panel.js';

// Экспорт глобальных функций для вызовов из встроенного HTML / хоста
window.initModelsTab = initModelsTab;
window.loadTabModels = loadTabModels;
window.updateModelFavoriteUI = updateModelFavoriteUI;
window.persistSelectedModelAndProvider = persistSelectedModelAndProvider;
window.executeModelTest = executeModelTest;
window.cancelModelTest = cancelModelTest;
window.refreshKeysList = refreshKeysList;
window.activateApiKey = activateApiKey;
window.openKeyTestModal = openKeyTestModal;
window.runKeyTest = runKeyTest;
window.toggleKeyStatus = toggleKeyStatus;
window.resetKeyQuota = resetKeyQuota;
window.deleteKey = deleteKey;
window.refreshAgyKeysList = refreshAgyKeysList;
window.activateAgyKey = activateAgyKey;
window.toggleAgyKeyStatus = toggleAgyKeyStatus;
window.resetAgyKeyQuota = resetAgyKeyQuota;
window.deleteAgyKey = deleteAgyKey;
window.refreshGoogleAccountsList = refreshGoogleAccountsList;
window.handleAddGoogleAccount = handleAddGoogleAccount;
window.setGoogleAccountDefault = setGoogleAccountDefault;
window.resetGoogleAccountStatus = resetGoogleAccountStatus;
window.testGoogleAccount = testGoogleAccount;
window.deleteGoogleAccount = deleteGoogleAccount;
window.loadSystemInstruction = loadSystemInstruction;
window.saveSystemInstruction = saveSystemInstruction;

/**
 * Инициализирует вкладку управления моделями и привязывает обработчики событий.
 */
export async function initModelsTab() {
  window.api = window.api || {};
  if (!window.api.fetch) {
    window.api.fetch = async function(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        let msg = response.statusText;
        try {
          const data = await response.json();
          if (data && data.detail) {
            msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
          } else if (data && data.message) {
            msg = data.message;
          }
        } catch {}
        throw new Error(`${response.status} ${msg}`);
      }
      return response.json();
    };
  }

  const modelSelect = document.getElementById('models-tab-select');
  const saveBtn = document.getElementById('btn-models-tab-save') || document.getElementById('btn-save-default-model');
  const keysListBody = document.getElementById('keys-list-body');
  const refreshKeysBtn = document.getElementById('btn-refresh-keys');
  const addKeyBtn = document.getElementById('btn-add-key');
  const agyKeysListBody = document.getElementById('agy-keys-list-body');
  const refreshAgyKeysBtn = document.getElementById('btn-agy-refresh-keys');
  const addAgyKeyBtn = document.getElementById('btn-agy-add-key');
  const saveBtnInstr = document.getElementById('btn-save-instruction');
  const reloadBtnInstr = document.getElementById('btn-reload-instruction');

  const gaccountsListBody = document.getElementById('gaccounts-list-body');
  const refreshGAccountsBtn = document.getElementById('btn-refresh-gaccounts');
  const addGAccountBtn = document.getElementById('btn-add-gacc');

  const refreshModelsBtn = document.getElementById('btn-refresh-models-list');
  const testModelBtn = document.getElementById('btn-model-test-send');
  const cancelModelBtn = document.getElementById('btn-model-test-cancel');
  const testModelPrompt = document.getElementById('model-test-prompt');

  // Активация вкладки провайдера по умолчанию
  const activePill = document.querySelector('#provider-pills-tab .nav-link.active') || document.getElementById('pill-gemini-tab');
  if (activePill) {
    const targetSelector = activePill.getAttribute('data-bs-target');
    if (targetSelector) {
      const targetPane = document.querySelector(targetSelector);
      if (targetPane && !targetPane.classList.contains('active')) {
        targetPane.classList.add('show', 'active');
      }
    }
  }

  // Привязка обработчиков системной инструкции
  if (saveBtnInstr) saveBtnInstr.onclick = saveSystemInstruction;
  if (reloadBtnInstr) reloadBtnInstr.onclick = loadSystemInstruction;

  // Кнопка обновления каталога моделей
  if (refreshModelsBtn && modelSelect && saveBtn) {
    refreshModelsBtn.onclick = async () => {
      refreshModelsBtn.disabled = true;
      const originalText = refreshModelsBtn.innerHTML;
      refreshModelsBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Обновление...';
      try {
        await loadTabModels(modelSelect, saveBtn, true);
      } finally {
        refreshModelsBtn.disabled = false;
        refreshModelsBtn.innerHTML = originalText;
      }
    };
  }

  // Чекбокс показа всех моделей
  const showAllModelsCheck = document.getElementById('show-all-models-check');
  if (showAllModelsCheck && modelSelect && saveBtn) {
    showAllModelsCheck.onchange = async () => {
      await loadTabModels(modelSelect, saveBtn, false);
    };
  }

  // Избранное и заметки для моделей
  const favToggleBtn = document.getElementById('btn-model-toggle-favorite');
  const saveNoteBtn = document.getElementById('btn-save-model-note');
  const modelNoteInput = document.getElementById('model-user-note');

  if (favToggleBtn && modelSelect) {
    favToggleBtn.onclick = async () => {
      const curModel = modelSelect.value;
      if (!curModel) {
        showModelsNotification('Сначала выберите модель', 'warning');
        return;
      }
      favToggleBtn.disabled = true;
      try {
        const isFav = window.userFavoriteModels && Boolean(window.userFavoriteModels[curModel]);
        if (isFav) {
          await window.api.fetch(`/auth/favorites/${encodeURIComponent(curModel)}`, { method: 'DELETE' });
          if (window.userFavoriteModels) delete window.userFavoriteModels[curModel];
          showModelsNotification(`Модель "${curModel}" удалена из избранного`, 'info');
        } else {
          const noteText = modelNoteInput ? modelNoteInput.value.trim() : '';
          const res = await window.api.fetch('/auth/favorites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: curModel, note: noteText })
          });
          if (res && res.favorites) window.userFavoriteModels = res.favorites;
          showModelsNotification(`Модель "${curModel}" добавлена в избранное ⭐`, 'success');
        }
        updateModelFavoriteUI(modelSelect);
        renderFavoriteModelsChips();
      } catch (err) {
        console.error('Ошибка переключения избранного:', err);
        showModelsNotification('Ошибка: ' + err.message, 'danger');
      } finally {
        favToggleBtn.disabled = false;
      }
    };
  }

  if (saveNoteBtn && modelSelect && modelNoteInput) {
    saveNoteBtn.onclick = async () => {
      const curModel = modelSelect.value;
      if (!curModel) {
        showModelsNotification('Сначала выберите модель', 'warning');
        return;
      }
      saveNoteBtn.disabled = true;
      const originalText = saveNoteBtn.innerHTML;
      saveNoteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сохранение...';
      try {
        const noteText = modelNoteInput.value.trim();
        const res = await window.api.fetch('/auth/favorites', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: curModel, note: noteText })
        });
        if (res && res.favorites) window.userFavoriteModels = res.favorites;
        showModelsNotification(`Заметка для модели "${curModel}" сохранена!`, 'success');
        updateModelFavoriteUI(modelSelect);
      } catch (err) {
        console.error('Ошибка сохранения заметки:', err);
        showModelsNotification('Ошибка сохранения заметки: ' + err.message, 'danger');
      } finally {
        saveNoteBtn.disabled = false;
        saveNoteBtn.innerHTML = originalText;
      }
    };
  }

  if (modelSelect) {
    modelSelect.addEventListener('change', async () => {
      updateModelFavoriteUI(modelSelect);
      const curProv = document.getElementById('provider-tab-select')?.value || '';
      if (modelSelect.value) {
        await persistSelectedModelAndProvider(modelSelect.value, curProv, true);
      }
    });
  }

  // Кнопки тестирования модели
  if (testModelBtn) testModelBtn.onclick = executeModelTest;
  if (cancelModelBtn) cancelModelBtn.onclick = cancelModelTest;
  if (testModelPrompt) {
    testModelPrompt.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeModelTest();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        cancelModelTest();
      }
    };
  }

  // Кнопка сохранения модели по умолчанию
  if (saveBtn && modelSelect) {
    saveBtn.onclick = async () => {
      const selectedModel = modelSelect.value;
      const providerSelect = document.getElementById('provider-tab-select');
      const selectedProvider = providerSelect ? providerSelect.value : '';

      if (!selectedModel) {
        showModelsNotification('Сначала выберите модель из списка', 'warning');
        return;
      }

      saveBtn.disabled = true;
      const originalText = saveBtn.textContent;
      saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Сохранение...';

      try {
        await persistSelectedModelAndProvider(selectedModel, selectedProvider, true);
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
      }
    };
  }

  // Сброс квот и добавление ключей Gemini
  if (refreshKeysBtn) {
    refreshKeysBtn.onclick = async () => {
      refreshKeysBtn.disabled = true;
      const originalText = refreshKeysBtn.textContent;
      refreshKeysBtn.textContent = '⏳ Сброс...';
      try {
        const res = await window.api.fetch('/api/keys/reset-all', { method: 'POST' });
        showModelsNotification(res.message || 'Квоты всех ключей успешно сброшены', 'success');
      } catch (err) {
        console.error('Ошибка сброса квот:', err);
        showModelsNotification('Ошибка сброса: ' + err.message, 'danger');
      } finally {
        refreshKeysBtn.disabled = false;
        refreshKeysBtn.textContent = originalText;
        if (keysListBody) await refreshKeysList(keysListBody);
      }
    };
  }

  if (addKeyBtn) {
    addKeyBtn.onclick = async () => {
      const nameInput = document.getElementById('new-key-name');
      const valueInput = document.getElementById('new-key-value');
      if (!nameInput || !valueInput) return;

      const name = nameInput.value.trim();
      const apiKey = valueInput.value.trim();

      if (!name || !apiKey) {
        showModelsNotification('Заполните все поля!', 'warning');
        return;
      }

      addKeyBtn.disabled = true;
      try {
        await window.api.fetch('/api/keys', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, api_key: apiKey, status: 'active' })
        });
        showModelsNotification(`Ключ "${name}" успешно добавлен`, 'success');
        nameInput.value = '';
        valueInput.value = '';
        if (keysListBody) await refreshKeysList(keysListBody);
      } catch (err) {
        console.error('Ошибка добавления ключа:', err);
        showModelsNotification('Ошибка добавления: ' + err.message, 'danger');
      } finally {
        addKeyBtn.disabled = false;
      }
    };
  }

  // Управление Google Accounts
  if (refreshGAccountsBtn && gaccountsListBody) {
    refreshGAccountsBtn.onclick = async () => {
      refreshGAccountsBtn.disabled = true;
      const originalText = refreshGAccountsBtn.innerHTML;
      refreshGAccountsBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Обновление...';
      try {
        await refreshGoogleAccountsList(gaccountsListBody);
        showModelsNotification('Список аккаунтов Google обновлен', 'success');
      } finally {
        refreshGAccountsBtn.disabled = false;
        refreshGAccountsBtn.innerHTML = originalText;
      }
    };
  }

  if (addGAccountBtn) {
    addGAccountBtn.onclick = async () => {
      await handleAddGoogleAccount(gaccountsListBody);
    };
  }

  // Управление AGY ключами
  if (refreshAgyKeysBtn) {
    refreshAgyKeysBtn.onclick = async () => {
      refreshAgyKeysBtn.disabled = true;
      const originalText = refreshAgyKeysBtn.textContent;
      refreshAgyKeysBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Сброс...';
      try {
        const fetchFn = (window.api && window.api.fetch) || fetch;
        await fetchFn('/api/keys/agy/reset-all', { method: 'POST' });
        showModelsNotification('Все квоты ключей AGY успешно сброшены!', 'success');
      } catch (err) {
        console.error('Ошибка сброса квот AGY:', err);
        showModelsNotification('Ошибка сброса: ' + err.message, 'danger');
      } finally {
        refreshAgyKeysBtn.disabled = false;
        refreshAgyKeysBtn.textContent = originalText;
        if (agyKeysListBody) await refreshAgyKeysList(agyKeysListBody);
      }
    };
  }

  if (addAgyKeyBtn) {
    addAgyKeyBtn.onclick = async () => {
      const nameInput = document.getElementById('new-agy-key-name');
      const valueInput = document.getElementById('new-agy-key-value');
      if (!nameInput || !valueInput) return;

      const name = nameInput.value.trim();
      const apiKey = valueInput.value.trim();

      if (!name || !apiKey) {
        showModelsNotification('Заполните все поля!', 'warning');
        return;
      }

      addAgyKeyBtn.disabled = true;
      try {
        const fetchFn = (window.api && window.api.fetch) || fetch;
        await fetchFn('/api/keys/agy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, api_key: apiKey, status: 'active' })
        });
        showModelsNotification(`Ключ AGY "${name}" успешно добавлен`, 'success');
        nameInput.value = '';
        valueInput.value = '';
        if (agyKeysListBody) await refreshAgyKeysList(agyKeysListBody);
      } catch (err) {
        console.error('Ошибка добавления ключа AGY:', err);
        showModelsNotification('Ошибка добавления: ' + err.message, 'danger');
      } finally {
        addAgyKeyBtn.disabled = false;
      }
    };
  }

  // Асинхронная параллельная загрузка всех компонентов
  await Promise.allSettled([
    modelSelect && saveBtn ? loadTabModels(modelSelect, saveBtn) : Promise.resolve(),
    keysListBody ? refreshKeysList(keysListBody) : Promise.resolve(),
    agyKeysListBody ? refreshAgyKeysList(agyKeysListBody) : Promise.resolve(),
    gaccountsListBody ? refreshGoogleAccountsList(gaccountsListBody) : Promise.resolve(),
    loadSystemInstruction()
  ]);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initModelsTab);
} else {
  initModelsTab();
}

/**
 * Автоматическая синхронизация активной панели вкладки с URL-хэшем.
 */
export function initTabUrlHashRouting() {
  const canonicalTabId = 'tab-models';
  const syncFromHash = () => {
    const raw = window.location.hash || '';
    if (!raw.includes(canonicalTabId)) return;
    const parts = raw.replace(/^#/, '').split('#');
    const panelPart = parts.find((p) => p.startsWith('panel-'));
    if (panelPart) {
      const btn = document.querySelector(`button[data-panel-id="${panelPart}"]`) ||
                  document.querySelector(`button[data-bs-target="#${panelPart}"]`);
      if (btn && window.bootstrap && window.bootstrap.Tab) {
        (window.bootstrap.Tab.getInstance?.(btn) || window.bootstrap.Tab.getOrCreateInstance?.(btn) || new window.bootstrap.Tab(btn)).show();
      }
    }
  };

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-panel-id], button[data-bs-toggle="pill"]');
    if (btn) {
      const panelId = btn.getAttribute('data-panel-id') || btn.getAttribute('data-bs-target')?.replace('#', '');
      const blockId = btn.getAttribute('data-block-id');
      if (panelId) {
        let hash = `#${canonicalTabId}#${panelId}`;
        if (blockId) hash += `#${blockId}`;
        history.replaceState(null, null, hash);
      }
    }
  });

  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}

if (typeof window !== 'undefined') {
  window.initTabUrlHashRouting = initTabUrlHashRouting;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTabUrlHashRouting);
  } else {
    initTabUrlHashRouting();
  }
}
