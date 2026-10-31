/**
 * Модуль панели параметров и внешнего вида панели задач Windows.
 * Файл: apps/windows/api/webgui/tab_taskbar/panel_settings/panel.js
 * Updated: 2026-10-31 15:55:00
 */

let _isLoadingSettings = false;
let _debounceTimer = null;

function setCheck(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = Boolean(val);
}

/**
 * Загружает текущие настройки панели задач из реестра / telemetry.
 */
export async function loadSettings() {
  _isLoadingSettings = true;
  try {
    const res = await fetch('/api/v1/taskbar/settings');
    if (!res.ok) return;
    const s = await res.json();

    const alignVal = s.alignment === 1 ? '1' : '0';
    const alignRadio = document.querySelector(`input[name="tb-alignment"][value="${alignVal}"]`);
    if (alignRadio) alignRadio.checked = true;

    const selSearch = document.getElementById('select-search-mode');
    if (selSearch) selSearch.value = String(s.search_mode);

    setCheck('switch-auto-hide', s.auto_hide);
    setCheck('switch-widgets', s.widgets_visible);
    setCheck('switch-task-view', s.task_view_visible);
    setCheck('switch-copilot', s.copilot_visible);
    setCheck('switch-badges', s.badges_enabled);
  } catch (err) {
    console.error('[TaskbarTab] Ошибка настроек:', err);
  } finally {
    _isLoadingSettings = false;
  }
}

/**
 * Сохраняет параметры панели задач в систему.
 * @param {Event} [e] - Событие формы.
 * @param {Function} [onUpdated] - Коллбек обновления.
 * @param {boolean} [isLive=false] - Флаг применения на лету.
 */
export async function saveTaskbarSettings(e, onUpdated, isLive = false) {
  if (e) e.preventDefault();
  if (_isLoadingSettings) return;

  const alignRadio = document.querySelector('input[name="tb-alignment"]:checked');
  const alignment = alignRadio ? parseInt(alignRadio.value, 10) : 1;
  const search_mode = parseInt(document.getElementById('select-search-mode')?.value || '1', 10);
  const auto_hide = document.getElementById('switch-auto-hide')?.checked || false;
  const widgets_visible = document.getElementById('switch-widgets')?.checked || false;
  const task_view_visible = document.getElementById('switch-task-view')?.checked || false;
  const copilot_visible = document.getElementById('switch-copilot')?.checked || false;
  const badges_enabled = document.getElementById('switch-badges')?.checked || false;
  const restart_explorer = document.getElementById('switch-restart-explorer')?.checked || false;

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
        restart_explorer,
      })
    });
    if (res.ok) {
      if (window.toast) {
        window.toast.success(isLive ? 'Применено на лету' : 'Настройки сохранены', 'Параметры панели задач успешно зафиксированы в telemetry.db');
      }
      if (onUpdated) await onUpdated();
    }
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка сохранения', err.message);
  }
}

/**
 * Мгновенное применение параметров на лету с дебаунсом.
 * @param {Function} [onUpdated] - Коллбек обновления.
 */
export function applyLiveTaskbarSettings(onUpdated) {
  if (_isLoadingSettings) return;
  if (_debounceTimer) clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(() => {
    saveTaskbarSettings(null, onUpdated, true);
  }, 100);
}

/**
 * Привязка слушателей изменений на лету.
 * @param {Function} [onUpdated] - Коллбек обновления.
 */
export function bindTaskbarSettingsEvents(onUpdated) {
  document.querySelectorAll('input[name="tb-alignment"]').forEach((radio) => {
    radio.addEventListener('change', () => applyLiveTaskbarSettings(onUpdated));
  });
  document.getElementById('select-search-mode')?.addEventListener('change', () => applyLiveTaskbarSettings(onUpdated));
  const switches = [
    'switch-auto-hide',
    'switch-widgets',
    'switch-task-view',
    'switch-copilot',
    'switch-badges'
  ];
  switches.forEach((id) => {
    document.getElementById(id)?.addEventListener('change', () => applyLiveTaskbarSettings(onUpdated));
  });
}

/**
 * Перезапускает процесс оболочки Windows Explorer.
 */
export async function restartExplorer() {
  if (!confirm('Перезапустить процесс Explorer? Экран на 1-2 секунды обновится.')) return;
  try {
    const res = await fetch('/api/v1/taskbar/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ restart_explorer: true })
    });
    if (res.ok && window.toast) {
      window.toast.success('Explorer перезапущен', 'Оболочка Windows успешно перезапущена');
    }
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка', err.message);
  }
}
