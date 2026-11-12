/**
 * =============================================================================
 * Process Name: Windows Registry Viewer Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский контроллер-оркестратор проводника и редактора реестра Windows.
 *   Координирует навигацию по ульям, чтение подразделов/параметров,
 *   редактирование, удаление, резервные копии и AI-инспекцию AITableModal.
 *
 * File: main.js
 * Package: apps/windows/api/webgui/tab_registry_viewer
 * Updated: 2026-10-17 01:55:00
 * =============================================================================
 */

import { loadBookmarks } from './panel_bookmarks/panel.js';
import {
  navigateTo,
  goUp,
  copyCurrentPath,
  getCurrentHive,
  getCurrentPath
} from './panel_navigation/panel.js';
import {
  renderSubkeys,
  openCreateKeyModal,
  saveModalKey,
  deleteCurrentKey
} from './panel_subkeys/panel.js';
import {
  renderValues,
  openCreateValueModal,
  saveModalValue,
  setCurrentKeyData
} from './panel_values/panel.js';
import { openBackupsModal } from './panel_backups/panel.js';

let isInitialized = false;

/**
 * Загрузка данных ключа реестра (подразделы и значения).
 * @param {string} hive - Улей.
 * @param {string} path - Путь.
 */
export async function loadKey(hive, path) {
  const subkeysList = document.getElementById('reg-subkeys-list');
  const valuesTbody = document.getElementById('reg-values-tbody');
  const badge = document.getElementById('reg-status-badge');

  if (badge) badge.innerText = `● Чтение ${hive}...`;

  try {
    const url = `/api/registry/key?hive=${encodeURIComponent(hive)}&path=${encodeURIComponent(path)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    setCurrentKeyData(data);

    renderSubkeys(data.subkeys || [], hive, path, (h, p) => navigateTo(h, p, loadKey));
    renderValues(hive, path, () => loadKey(getCurrentHive(), getCurrentPath()));

    if (badge) {
      badge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
      badge.innerText = `● Реестр: ${hive}`;
    }
  } catch (err) {
    console.error('[RegistryViewerTab] Error loading key:', err);
    if (valuesTbody) {
      valuesTbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger p-4"><i class="bi bi-exclamation-triangle-fill me-1"></i> Ошибка чтения ветки: ${err.message}</td></tr>`;
    }
    if (subkeysList) {
      subkeysList.innerHTML = `<div class="text-danger text-center py-4 small">${err.message}</div>`;
    }
    if (badge) {
      badge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-2';
      badge.innerText = '● Ошибка доступа';
    }
  }
}

/**
 * Инициализация вкладки реестра Windows.
 */
export async function initRegistryViewerTab() {
  console.log('[RegistryViewerTab] Initializing Registry Viewer & Editor tab...');

  const hiveSelect = document.getElementById('reg-hive-select');
  const pathInput = document.getElementById('reg-path-input');
  const goBtn = document.getElementById('btn-reg-go');
  const upBtn = document.getElementById('btn-reg-up');
  const filterInput = document.getElementById('reg-filter-input');
  const refreshBtn = document.getElementById('btn-reg-refresh');
  const copyBtn = document.getElementById('btn-reg-copy-path');
  const backupsBtn = document.getElementById('btn-reg-backups-modal');
  const addValBtn = document.getElementById('btn-reg-add-value');
  const addKeyBtn = document.getElementById('btn-reg-add-key');
  const delKeyBtn = document.getElementById('btn-reg-delete-current-key');
  const saveValModalBtn = document.getElementById('btn-reg-modal-save');
  const saveKeyModalBtn = document.getElementById('btn-reg-modal-create-key');

  if (hiveSelect) {
    hiveSelect.onchange = () => {
      navigateTo(hiveSelect.value, '', loadKey);
    };
  }
  if (goBtn && pathInput) {
    goBtn.onclick = () => {
      navigateTo(hiveSelect.value, pathInput.value, loadKey);
    };
  }
  if (pathInput) {
    pathInput.onkeydown = (e) => {
      if (e.key === 'Enter') {
        navigateTo(hiveSelect.value, pathInput.value, loadKey);
      }
    };
  }
  if (upBtn) upBtn.onclick = () => goUp((h, p) => navigateTo(h, p, loadKey));
  if (filterInput) {
    filterInput.oninput = () => renderValues(getCurrentHive(), getCurrentPath(), () => loadKey(getCurrentHive(), getCurrentPath()));
  }
  if (refreshBtn) refreshBtn.onclick = () => loadKey(getCurrentHive(), getCurrentPath());
  if (copyBtn) copyBtn.onclick = copyCurrentPath;
  if (backupsBtn) backupsBtn.onclick = () => openBackupsModal(() => loadKey(getCurrentHive(), getCurrentPath()));
  if (addValBtn) addValBtn.onclick = openCreateValueModal;
  if (addKeyBtn) addKeyBtn.onclick = openCreateKeyModal;
  if (delKeyBtn) delKeyBtn.onclick = () => deleteCurrentKey(getCurrentHive(), getCurrentPath(), () => goUp((h, p) => navigateTo(h, p, loadKey)));
  if (saveValModalBtn) saveValModalBtn.onclick = () => saveModalValue(getCurrentHive(), getCurrentPath(), () => loadKey(getCurrentHive(), getCurrentPath()));
  if (saveKeyModalBtn) saveKeyModalBtn.onclick = () => saveModalKey(getCurrentHive(), getCurrentPath(), loadKey);

  await loadBookmarks((h, p) => navigateTo(h, p, loadKey));
  await navigateTo(getCurrentHive(), getCurrentPath(), loadKey);
  isInitialized = true;
}

window.initRegistryViewerTab = initRegistryViewerTab;

if (document.getElementById('tab-registry-viewer') || document.getElementById('reg-subkeys-list')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initRegistryViewerTab());
  } else {
    setTimeout(() => initRegistryViewerTab(), 10);
  }
}
