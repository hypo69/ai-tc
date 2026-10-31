/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: Focus Assist Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер панели сессий фокусировки (Focus Sessions) и режима
 *   «Не беспокоить» (Do Not Disturb) Windows 11. Управляет таймером концентрации,
 *   подавлением мигания панели задач, скрытием бейджей и системными параметрами.
 *
 * File: panel_focus.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 18:05:00
 * =============================================================================
 */

let _durationMinutes = 30;
let _isFocusActive = false;
let _timerInterval = null;
let _remainingSeconds = 0;

/**
 * Вызов всплывающего уведомления Toast.
 * @param {string} msg Текст сообщения.
 * @param {'info'|'success'|'warning'|'danger'} type Тип уведомления.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[UEFocus] [${type}] ${msg}`);
  }
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
 * Загрузка состояния сессии фокусировки из REST API.
 */
export async function loadFocusState() {
  try {
    const res = await fetch('/api/windows/focus/state');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderFocusState(data);
    updateFocusKpi(data);
  } catch (err) {
    console.warn('[UEFocus] Ошибка загрузки focus state:', err);
  }
}

/**
 * Обновление KPI статуса фокусировки в шапке.
 * @param {Object} state Объект состояния.
 */
function updateFocusKpi(state) {
  const kpiEl = document.getElementById('ue-kpi-focus-status');
  if (kpiEl) {
    kpiEl.textContent = state.is_active ? 'Активен' : 'Не активен';
    kpiEl.className = state.is_active ? 'fw-bold text-success' : 'fw-bold text-muted';
  }
}

/**
 * Отрисовка полученного состояния в интерфейсе.
 * @param {Object} state Объект состояния FocusSessionStateDTO.
 */
export function renderFocusState(state) {
  if (!state) return;
  _isFocusActive = Boolean(state.is_active);
  _durationMinutes = state.session_duration_minutes || _durationMinutes;
  _remainingSeconds = state.remaining_seconds || 0;

  updateDurationLabel();

  // Чекбоксы настроек
  const s = state.settings || {};
  setCheck('ue-chk-clock-timer', s.show_timer_in_clock_app ?? true);
  setCheck('ue-chk-hide-badges', s.hide_badges_on_taskbar ?? true);
  setCheck('ue-chk-hide-flashing', s.hide_flashing_on_taskbar ?? true);
  setCheck('ue-chk-turn-on-dnd', s.turn_on_do_not_disturb ?? true);

  // Бейдж и кнопка переключения
  const badge = document.getElementById('ue-focus-status-badge');
  const btnToggle = document.getElementById('ue-btn-toggle-focus');
  const btnIcon = document.getElementById('ue-btn-focus-icon');
  const btnText = document.getElementById('ue-btn-focus-text');
  const hint = document.getElementById('ue-focus-session-hint');
  const countdownBox = document.getElementById('ue-focus-countdown-box');

  if (_isFocusActive) {
    if (badge) {
      badge.className = 'badge bg-success small fs-6';
      badge.textContent = 'Сессия активна';
    }
    if (btnToggle) {
      btnToggle.className = 'btn btn-danger px-4 py-2 d-flex align-items-center gap-2 shadow-sm';
    }
    if (btnIcon) btnIcon.className = 'bi bi-stop-fill';
    if (btnText) btnText.textContent = 'Остановить фокус';
    if (hint) hint.textContent = 'Сессия активна. Отвлекающие уведомления подавлены.';
    if (countdownBox) countdownBox.classList.remove('d-none');

    startCountdown();
  } else {
    if (badge) {
      badge.className = 'badge bg-secondary-subtle text-secondary border border-secondary-subtle small fs-6';
      badge.textContent = 'Не активна';
    }
    if (btnToggle) {
      btnToggle.className = 'btn btn-primary px-4 py-2 d-flex align-items-center gap-2 shadow-sm';
    }
    if (btnIcon) btnIcon.className = 'bi bi-play-fill';
    if (btnText) btnText.textContent = 'Начать сессию фокуса';
    if (hint) hint.textContent = 'Готов к запуску сессии продуктивной работы';
    if (countdownBox) countdownBox.classList.add('d-none');

    stopCountdown();
  }
}

/**
 * Локальный таймер обратного отсчета.
 */
function startCountdown() {
  stopCountdown();
  updateCountdownDisplay();
  _timerInterval = setInterval(() => {
    if (_remainingSeconds > 0) {
      _remainingSeconds -= 1;
      updateCountdownDisplay();
    } else {
      stopCountdown();
      loadFocusState();
    }
  }, 1000);
}

function stopCountdown() {
  if (_timerInterval) {
    clearInterval(_timerInterval);
    _timerInterval = null;
  }
}

function updateCountdownDisplay() {
  const timerText = document.getElementById('ue-focus-timer-text');
  if (timerText) {
    const mins = Math.floor(_remainingSeconds / 60);
    const secs = _remainingSeconds % 60;
    timerText.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
}

/**
 * Изменение длительности сессии (шаг 5 мин, диапазон 5..240 мин).
 * @param {number} delta Шаг.
 */
export function changeDuration(delta) {
  if (_isFocusActive) return;
  _durationMinutes = Math.max(5, Math.min(240, _durationMinutes + delta));
  updateDurationLabel();
}

function updateDurationLabel() {
  const lbl = document.getElementById('ue-lbl-focus-duration');
  if (lbl) lbl.textContent = `${_durationMinutes} мин`;
}

/**
 * Переключение состояния сессии фокусировки (Start / Stop).
 */
export async function toggleFocusSession() {
  try {
    if (_isFocusActive) {
      const res = await fetch('/api/windows/focus/session/stop', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('Сессия фокусировки остановлена', 'info');
    } else {
      const res = await fetch('/api/windows/focus/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_minutes: _durationMinutes })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast(`Сессия фокусировки запущена на ${_durationMinutes} мин`, 'success');
    }
    await loadFocusState();
  } catch (err) {
    showToast(`Ошибка переключения фокуса: ${err.message}`, 'danger');
  }
}

/**
 * Сохранение параметров фокусировки.
 */
export async function saveFocusSettings() {
  const payload = {
    show_timer_in_clock_app: Boolean(document.getElementById('ue-chk-clock-timer')?.checked),
    hide_badges_on_taskbar: Boolean(document.getElementById('ue-chk-hide-badges')?.checked),
    hide_flashing_on_taskbar: Boolean(document.getElementById('ue-chk-hide-flashing')?.checked),
    turn_on_do_not_disturb: Boolean(document.getElementById('ue-chk-turn-on-dnd')?.checked)
  };

  try {
    const res = await fetch('/api/windows/focus/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Параметры фокуса сохранены', 'success');
    await loadFocusState();
  } catch (err) {
    showToast(`Ошибка сохранения: ${err.message}`, 'danger');
  }
}

/**
 * Привязка событий панели Focus.
 */
export function bindFocusEvents() {
  document.getElementById('ue-btn-focus-minus')?.addEventListener('click', () => changeDuration(-5));
  document.getElementById('ue-btn-focus-plus')?.addEventListener('click', () => changeDuration(5));
  document.getElementById('ue-btn-toggle-focus')?.addEventListener('click', toggleFocusSession);
  document.getElementById('ue-btn-save-focus-settings')?.addEventListener('click', saveFocusSettings);
  document.getElementById('ue-btn-refresh-focus')?.addEventListener('click', loadFocusState);
}
