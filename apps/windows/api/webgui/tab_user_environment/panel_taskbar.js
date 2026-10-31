/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: Taskbar Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер панели задач Windows (Taskbar).
 *   Управляет параметрами выравнивания, автоскрытия, значками поиска, виджетов
 *   и Copilot, закрепленными приложениями, прогресс-баром ITaskbarList3 и Explorer.
 *
 * File: panel_taskbar.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 15:53:00
 * =============================================================================
 */

let _isLoadingSettings = false;
let _saveDebounceTimer = null;

/**
 * Вызов всплывающего уведомления Toast.
 * @param {string} msg Текст сообщения.
 * @param {'info'|'success'|'warning'|'danger'} type Тип уведомления.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[UETaskbar] [${type}] ${msg}`);
  }
}

/**
 * Экранирование HTML.
 * @param {string} str Входная строка.
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Установка состояния чекбокса.
 * @param {string} id ID элемента.
 * @param {boolean} val Значение.
 */
function setCheck(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = Boolean(val);
}

/**
 * Загрузка сводки и габаритов панели задач.
 */
export async function loadTaskbarSummary() {
  try {
    const res = await fetch('/api/v1/taskbar/summary');
    if (!res.ok) return;
    const data = await res.json();
    const rectKpi = document.getElementById('ue-kpi-taskbar-rect');
    const alignKpi = document.getElementById('ue-kpi-taskbar-align');

    if (rectKpi && data.rect) {
      rectKpi.textContent = `${data.rect.width} × ${data.rect.height} px`;
    }
    if (alignKpi && data.settings) {
      alignKpi.textContent = data.settings.alignment === 1 ? 'По центру' : 'Слева';
    }
  } catch (err) {
    console.warn('[UETaskbar] Ошибка загрузки summary:', err);
  }
}

/**
 * Загрузка настроек панели задач.
 */
export async function loadTaskbarSettings() {
  _isLoadingSettings = true;
  try {
    const res = await fetch('/api/v1/taskbar/settings');
    if (!res.ok) return;
    const s = await res.json();

    const alignVal = s.alignment === 1 ? '1' : '0';
    const alignRadio = document.querySelector(`input[name="ue-tb-alignment"][value="${alignVal}"]`);
    if (alignRadio) alignRadio.checked = true;

    const selSearch = document.getElementById('ue-tb-select-search');
    if (selSearch) selSearch.value = String(s.search_mode ?? 1);

    setCheck('ue-tb-switch-autohide', s.auto_hide);
    setCheck('ue-tb-switch-widgets', s.widgets_visible);
    setCheck('ue-tb-switch-taskview', s.task_view_visible);
    setCheck('ue-tb-switch-copilot', s.copilot_visible);
    setCheck('ue-tb-switch-badges', s.badges_enabled);
  } catch (err) {
    console.warn('[UETaskbar] Ошибка настроек панели задач:', err);
  } finally {
    _isLoadingSettings = false;
  }
}

/**
 * Сохранение параметров панели задач.
 * @param {Event} [e] Событие формы.
 * @param {Function} [onUpdated] Коллбек обновления.
 * @param {boolean} [isLive=false] Флаг мгновенного применения на лету.
 */
export async function saveTaskbarSettings(e, onUpdated, isLive = false) {
  if (e) e.preventDefault();
  if (_isLoadingSettings) return;

  const alignRadio = document.querySelector('input[name="ue-tb-alignment"]:checked');
  const alignment = alignRadio ? parseInt(alignRadio.value, 10) : 1;
  const search_mode = parseInt(document.getElementById('ue-tb-select-search')?.value || '1', 10);
  const auto_hide = document.getElementById('ue-tb-switch-autohide')?.checked || false;
  const widgets_visible = document.getElementById('ue-tb-switch-widgets')?.checked || false;
  const task_view_visible = document.getElementById('ue-tb-switch-taskview')?.checked || false;
  const copilot_visible = document.getElementById('ue-tb-switch-copilot')?.checked || false;
  const badges_enabled = document.getElementById('ue-tb-switch-badges')?.checked || false;
  const restart_explorer = document.getElementById('ue-tb-switch-restart-explorer')?.checked || false;

  try {
    const res = await fetch('/api/v1/taskbar/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        alignment,
        search_mode,
        auto_hide,
        widgets_visible,
        task_view_visible,
        copilot_visible,
        badges_enabled,
        restart_explorer
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(isLive ? 'Параметр панели задач применен на лету' : 'Параметры панели задач успешно сохранены', 'success');
    if (typeof onUpdated === 'function') await onUpdated();
  } catch (err) {
    showToast(`Ошибка сохранения параметров: ${err.message}`, 'danger');
  }
}

/**
 * Мгновенное применение параметров панели задач на лету (debounced).
 * @param {Function} [onUpdated] Коллбек обновления.
 */
export function applyTaskbarSettingsLive(onUpdated) {
  if (_isLoadingSettings) return;
  if (_saveDebounceTimer) {
    clearTimeout(_saveDebounceTimer);
  }
  _saveDebounceTimer = setTimeout(() => {
    saveTaskbarSettings(null, onUpdated, true);
  }, 100);
}

/**
 * Перезапуск проводника (Explorer).
 * @param {Function} [onUpdated] Коллбек обновления.
 */
export async function restartExplorer(onUpdated) {
  try {
    const res = await fetch('/api/v1/taskbar/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command_id: 'TASKBAR.RESTART_EXPLORER' })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Проводник перезапускается...', 'warning');
    if (typeof onUpdated === 'function') {
      setTimeout(onUpdated, 1500);
    }
  } catch (err) {
    showToast(`Ошибка перезапуска Explorer: ${err.message}`, 'danger');
  }
}

/**
 * Загрузка списка закрепленных приложений.
 */
export async function loadPinnedApps() {
  const container = document.getElementById('ue-tb-pinned-apps-list');
  const countBadge = document.getElementById('ue-tb-pinned-count-badge');
  if (!container) return;

  try {
    const res = await fetch('/api/v1/taskbar/apps');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const apps = await res.json();

    if (countBadge) countBadge.textContent = `${apps.length} приложений`;

    if (!apps || apps.length === 0) {
      container.innerHTML = `
        <div class="text-center text-muted py-4">
          <i class="bi bi-pin-angle fs-3 d-block mb-1"></i>
          <span>Закрепленные приложения не обнаружены</span>
        </div>
      `;
      return;
    }

    container.innerHTML = apps.map((app) => {
      const name = escapeHtml(app.name || 'Приложение');
      const target = escapeHtml(app.target_path || '');
      return `
        <div class="d-flex align-items-center justify-content-between p-2 rounded border border-secondary-subtle bg-body-tertiary">
          <div class="d-flex align-items-center gap-2 flex-grow-1 text-truncate">
            <i class="bi bi-pin-angle-fill text-warning"></i>
            <div class="text-truncate">
              <strong class="d-block text-truncate">${name}</strong>
              <small class="text-muted d-block text-truncate user-select-all">${target}</small>
            </div>
          </div>
          <div class="d-flex align-items-center gap-1 ms-2">
            <button class="btn btn-sm btn-outline-primary ue-tb-btn-launch-app" data-target="${target}" title="Запустить">
              <i class="bi bi-play-fill"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger ue-tb-btn-unpin-app" data-target="${target}" title="Открепить">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.ue-tb-btn-launch-app').forEach((btn) => {
      const target = btn.getAttribute('data-target');
      btn.addEventListener('click', () => launchApplication(target));
    });

    container.querySelectorAll('.ue-tb-btn-unpin-app').forEach((btn) => {
      const target = btn.getAttribute('data-target');
      btn.addEventListener('click', () => unpinApplication(target));
    });
  } catch (err) {
    container.innerHTML = `<div class="text-danger p-3 text-center">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Запуск приложения.
 * @param {string} target Путь к исполняемому файлу или имя.
 */
export async function launchApplication(target) {
  try {
    const res = await fetch('/api/v1/taskbar/apps/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Запуск: ${target}`, 'success');
  } catch (err) {
    showToast(`Ошибка запуска: ${err.message}`, 'danger');
  }
}

/**
 * Закрепление приложения.
 * @param {string} target Путь к приложению.
 */
export async function pinApplication(target) {
  try {
    const res = await fetch('/api/v1/taskbar/apps/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Приложение закреплено: ${target}`, 'success');
    await loadPinnedApps();
  } catch (err) {
    showToast(`Ошибка закрепления: ${err.message}`, 'danger');
  }
}

/**
 * Открепление приложения.
 * @param {string} target Путь к приложению.
 */
export async function unpinApplication(target) {
  try {
    const res = await fetch(`/api/v1/taskbar/apps/pin?target=${encodeURIComponent(target)}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Приложение откреплено: ${target}`, 'info');
    await loadPinnedApps();
  } catch (err) {
    showToast(`Ошибка открепления: ${err.message}`, 'danger');
  }
}

/**
 * Применение индикатора прогресса ITaskbarList3.
 */
export async function applyUxProgress() {
  const hwndSel = document.getElementById('ue-tb-select-progress-hwnd');
  const hwnd = hwndSel ? parseInt(hwndSel.value, 10) : 0;
  const state = document.getElementById('ue-tb-select-progress-state')?.value || 'normal';
  const progress = parseInt(document.getElementById('ue-tb-range-progress')?.value || '50', 10);

  if (!hwnd) {
    showToast('Выберите целевое окно для прогресса', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/v1/taskbar/ux/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hwnd, state, progress })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Прогресс применен: ${progress}% (${state})`, 'success');
  } catch (err) {
    showToast(`Ошибка прогресса: ${err.message}`, 'danger');
  }
}

/**
 * Привязка событий панели задач.
 * @param {Function} [onUpdated] Коллбек обновления.
 */
export function bindTaskbarEvents(onUpdated) {
  // Явная отправка формы (кнопка "Сохранить")
  document.getElementById('ue-tb-form-settings')?.addEventListener('submit', (e) => saveTaskbarSettings(e, onUpdated, false));

  // Переключения на лету: радиокнопки выравнивания значков
  document.querySelectorAll('input[name="ue-tb-alignment"]').forEach((radio) => {
    radio.addEventListener('change', () => applyTaskbarSettingsLive(onUpdated));
  });

  // Переключения на лету: режим элемента «Поиск»
  document.getElementById('ue-tb-select-search')?.addEventListener('change', () => applyTaskbarSettingsLive(onUpdated));

  // Переключения на лету: переключатели интерфейса панели задач
  const liveSwitches = [
    'ue-tb-switch-autohide',
    'ue-tb-switch-widgets',
    'ue-tb-switch-taskview',
    'ue-tb-switch-copilot',
    'ue-tb-switch-badges'
  ];
  liveSwitches.forEach((id) => {
    document.getElementById(id)?.addEventListener('change', () => applyTaskbarSettingsLive(onUpdated));
  });

  document.getElementById('ue-tb-btn-restart-explorer')?.addEventListener('click', () => restartExplorer(onUpdated));
  document.getElementById('ue-tb-btn-refresh-pinned')?.addEventListener('click', loadPinnedApps);

  // Форма закрепления приложения
  document.getElementById('ue-tb-form-pin')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('ue-tb-input-pin-path');
    const path = input ? input.value.trim() : '';
    if (path) {
      await pinApplication(path);
      if (input) input.value = '';
    }
  });

  // UX прогресс слайдер
  const range = document.getElementById('ue-tb-range-progress');
  const label = document.getElementById('ue-tb-label-progress-val');
  if (range && label) {
    range.addEventListener('input', () => {
      label.textContent = `${range.value}%`;
    });
  }
  document.getElementById('ue-tb-btn-apply-progress')?.addEventListener('click', applyUxProgress);
}
