/**
 * =============================================================================
 * Process Name: Windows Settings - Quick Settings Panel
 * =============================================================================
 * Description:
 *   Модуль панели быстрых переключателей основных параметров рабочего стола Windows:
 *   активация окон наведением (X-Mouse / Active Window Tracking), задержка активации,
 *   блокировка перехвата фокуса (Foreground Lock Timeout) и толщина текстового курсора.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings/panel_quick_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { API_BASE, fetchJson } from '../common/ui_utils.js';

/**
 * Загрузка живых значений быстрых переключателей рабочего стола.
 * @returns {Promise<void>}
 */
export async function loadQuickSettings() {
  const quickStatus = document.getElementById('winset-quick-status');
  if (quickStatus) quickStatus.textContent = 'Опрос...';

  try {
    // 1. X-Mouse
    const xmouseRes = await fetchJson(`${API_BASE}/settings/window.focus.active_window_tracking?read_live=true`);
    if (xmouseRes && xmouseRes.live_state) {
      const liveVal = xmouseRes.live_state.value !== undefined ? xmouseRes.live_state.value : xmouseRes.live_state.current_value;
      const isEnabled = Boolean(liveVal);
      const sw = document.getElementById('winset-switch-xmouse');
      const st = document.getElementById('winset-status-xmouse');
      if (sw) sw.checked = isEnabled;
      if (st) {
        st.textContent = isEnabled ? 'ВКЛ' : 'ВЫКЛ';
        st.className = `badge ${isEnabled ? 'bg-success' : 'bg-secondary'}`;
      }
    }

    // 2. X-Mouse Delay
    const delayRes = await fetchJson(`${API_BASE}/settings/window.focus.active_window_tracking_delay?read_live=true`);
    if (delayRes && delayRes.live_state) {
      const liveVal = delayRes.live_state.value !== undefined ? delayRes.live_state.value : delayRes.live_state.current_value;
      if (liveVal !== null && liveVal !== undefined) {
        const val = parseInt(liveVal, 10) || 500;
        const rng = document.getElementById('winset-range-xmouse-delay');
        const lbl = document.getElementById('winset-val-xmouse-delay');
        if (rng) rng.value = val;
        if (lbl) lbl.textContent = `${val} ms`;
      }
    }

    // 3. Foreground Lock Timeout
    const fgRes = await fetchJson(`${API_BASE}/settings/window.focus.foreground_lock_timeout?read_live=true`);
    if (fgRes && fgRes.live_state) {
      const liveVal = fgRes.live_state.value !== undefined ? fgRes.live_state.value : fgRes.live_state.current_value;
      if (liveVal !== null && liveVal !== undefined) {
        const val = parseInt(liveVal, 10) || 200000;
        const inp = document.getElementById('winset-input-fglock');
        const lbl = document.getElementById('winset-val-fglock');
        if (inp) inp.value = val;
        if (lbl) lbl.textContent = `${val} ms`;
      }
    }

    // 4. Caret Width
    const caretRes = await fetchJson(`${API_BASE}/settings/window.accessibility.caret_width?read_live=true`);
    if (caretRes && caretRes.live_state) {
      const liveVal = caretRes.live_state.value !== undefined ? caretRes.live_state.value : caretRes.live_state.current_value;
      if (liveVal !== null && liveVal !== undefined) {
        const val = parseInt(liveVal, 10) || 1;
        const rng = document.getElementById('winset-range-caret-width');
        const lbl = document.getElementById('winset-val-caret-width');
        if (rng) rng.value = val;
        if (lbl) lbl.textContent = `${val} px`;
      }
    }

    if (quickStatus) quickStatus.textContent = 'Синхронизировано';
  } catch (err) {
    console.warn('[WindowsSettingsTab] Ошибка опроса экспресс-настроек:', err);
    if (quickStatus) quickStatus.textContent = 'Ошибка связи';
  }
}

/**
 * Применение одиночного параметра без открытия модального окна (для быстрых переключателей).
 * @param {string} settingId - Идентификатор параметра
 * @param {any} value - Новое значение
 * @returns {Promise<any>}
 */
export async function applySingleSetting(settingId, value) {
  try {
    const res = await fetchJson(`${API_BASE}/settings/${settingId}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, custom_comment: 'Quick Settings Toggle' }),
    });
    return res;
  } catch (err) {
    console.error(`Ошибка применения параметра ${settingId}:`, err);
    return null;
  }
}

/**
 * Привязка событий элементов быстрых настроек.
 */
export function bindQuickSettingsEvents() {
  // Быстрый переключатель X-Mouse (Active Window Tracking)
  const switchXMouse = document.getElementById('winset-switch-xmouse');
  if (switchXMouse && !switchXMouse._bound) {
    switchXMouse._bound = true;
    switchXMouse.onchange = async () => {
      await applySingleSetting('window.focus.active_window_tracking', switchXMouse.checked);
      await loadQuickSettings();
    };
  }

  // Задержка X-Mouse
  const rangeDelay = document.getElementById('winset-range-xmouse-delay');
  const valDelayLabel = document.getElementById('winset-val-xmouse-delay');
  const btnApplyDelay = document.getElementById('winset-btn-apply-delay');
  if (rangeDelay && valDelayLabel && !rangeDelay._bound) {
    rangeDelay._bound = true;
    rangeDelay.oninput = () => {
      valDelayLabel.textContent = `${rangeDelay.value} ms`;
    };
  }
  if (btnApplyDelay && rangeDelay && !btnApplyDelay._bound) {
    btnApplyDelay._bound = true;
    btnApplyDelay.onclick = async () => {
      await applySingleSetting('window.focus.active_window_tracking_delay', parseInt(rangeDelay.value, 10));
      await loadQuickSettings();
    };
  }

  // Блокировка перехвата фокуса
  const btnApplyFgLock = document.getElementById('winset-btn-apply-fglock');
  const inputFgLock = document.getElementById('winset-input-fglock');
  if (btnApplyFgLock && inputFgLock && !btnApplyFgLock._bound) {
    btnApplyFgLock._bound = true;
    btnApplyFgLock.onclick = async () => {
      await applySingleSetting('window.focus.foreground_lock_timeout', parseInt(inputFgLock.value, 10));
      await loadQuickSettings();
    };
  }

  // Толщина курсора
  const rangeCaret = document.getElementById('winset-range-caret-width');
  const valCaretLabel = document.getElementById('winset-val-caret-width');
  const btnApplyCaret = document.getElementById('winset-btn-apply-caret');
  if (rangeCaret && valCaretLabel && !rangeCaret._bound) {
    rangeCaret._bound = true;
    rangeCaret.oninput = () => {
      valCaretLabel.textContent = `${rangeCaret.value} px`;
    };
  }
  if (btnApplyCaret && rangeCaret && !btnApplyCaret._bound) {
    btnApplyCaret._bound = true;
    btnApplyCaret.onclick = async () => {
      await applySingleSetting('window.accessibility.caret_width', parseInt(rangeCaret.value, 10));
      await loadQuickSettings();
    };
  }
}
