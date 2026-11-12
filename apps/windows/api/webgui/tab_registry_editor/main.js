/**
 * =============================================================================
 * Process Name: Windows Registry Editor Tab - Main Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский контроллер-оркестратор проводника и редактора реестра Windows.
 *   Координирует навигацию по ульям, чтение подразделов/параметров,
 *   редактирование, удаление, резервные копии и AI-инспекцию AITableModal.
 *
 * File: main.js
 * Package: apps/windows/api/webgui/tab_registry_editor
 * Updated: 2026-11-01 14:32:00
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

let _isLoadingUcpd = false;

/**
 * Всплывающее уведомление Toast.
 * @param {string} msg - Сообщение.
 * @param {'info'|'success'|'warning'|'danger'} type - Тип.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[RegistryEditor] [${type}] ${msg}`);
  }
}

/**
 * Загрузка статуса драйвера UCPD.
 */
export async function loadUcpdStatus() {
  const switchEl = document.getElementById('reg-switch-ucpd');
  const badgeEl = document.getElementById('reg-badge-ucpd');
  const alertEl = document.getElementById('reg-alert-ucpd-reboot');
  if (!switchEl || !badgeEl) return;

  _isLoadingUcpd = true;
  try {
    const res = await fetch('/api/v1/taskbar/ucpd');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.supported) {
      switchEl.disabled = true;
      switchEl.checked = false;
      badgeEl.className = 'badge bg-secondary-subtle text-secondary border border-secondary-subtle';
      badgeEl.textContent = 'Не поддерживается';
      if (alertEl) alertEl.classList.add('d-none');
      return;
    }

    switchEl.disabled = false;
    switchEl.checked = Boolean(data.enabled);

    if (data.enabled) {
      badgeEl.className = 'badge bg-primary-subtle text-primary border border-primary-subtle';
      badgeEl.textContent = 'Защита включена';
    } else {
      badgeEl.className = 'badge bg-warning-subtle text-warning border border-warning-subtle';
      badgeEl.textContent = 'Отключен (Разблокирован)';
    }

    if (alertEl) {
      if (data.reboot_pending) {
        alertEl.classList.remove('d-none');
        alertEl.classList.add('d-flex');
      } else {
        alertEl.classList.add('d-none');
        alertEl.classList.remove('d-flex');
      }
    }
  } catch (err) {
    console.warn('[RegistryEditor] Ошибка проверки UCPD:', err);
    badgeEl.className = 'badge bg-danger-subtle text-danger border border-danger-subtle';
    badgeEl.textContent = 'Ошибка статуса';
  } finally {
    _isLoadingUcpd = false;
  }
}

/**
 * Переключение состояния драйвера защиты UCPD.
 * @param {boolean} enabled - Флаг включения/отключения.
 */
export async function toggleUcpd(enabled) {
  if (_isLoadingUcpd) return;
  const switchEl = document.getElementById('reg-switch-ucpd');
  const badgeEl = document.getElementById('reg-badge-ucpd');
  if (switchEl) switchEl.disabled = true;
  if (badgeEl) {
    badgeEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1" style="width: 0.7rem; height: 0.7rem;"></span>Применение...';
  }

  try {
    const res = await fetch('/api/v1/taskbar/ucpd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
    const result = await res.json();
    if (!res.ok || result.status !== 'SUCCESS') {
      throw new Error(result.detail || result.message || `HTTP ${res.status}`);
    }

    showToast(
      enabled
        ? 'Драйвер UCPD включен.'
        : 'Драйвер UCPD отключен! Для применения в ядре требуется перезагрузка Windows.',
      enabled ? 'success' : 'warning'
    );
  } catch (err) {
    showToast(`Ошибка переключения UCPD: ${err.message}`, 'danger');
  } finally {
    await loadUcpdStatus();
  }
}

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

  const ucpdSwitch = document.getElementById('reg-switch-ucpd');
  if (ucpdSwitch) {
    ucpdSwitch.onchange = (e) => toggleUcpd(e.target.checked);
  }

  await Promise.allSettled([
    loadBookmarks((h, p) => navigateTo(h, p, loadKey)),
    navigateTo(getCurrentHive(), getCurrentPath(), loadKey),
    loadUcpdStatus()
  ]);
  isInitialized = true;
}

window.initRegistryViewerTab = initRegistryViewerTab;
window.initRegistryEditorTab = initRegistryViewerTab;

if (document.getElementById('tab-registry-editor') || document.getElementById('tab-registry-viewer') || document.getElementById('reg-subkeys-list')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initRegistryViewerTab());
  } else {
    setTimeout(() => initRegistryViewerTab(), 10);
  }
}
