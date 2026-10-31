/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: Personalization Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер персонализации и дисплеев Windows.
 *   Управляет списком мониторов, поворотом экрана с безопасным 15-секундным
 *   таймером подтверждения, расположением панели задач и системной темой.
 *
 * File: panel_personalization.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 18:05:00
 * =============================================================================
 */

let _activeDisplays = [];
let _currentDisplayId = '';
let _countdownTimer = null;
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
    console.log(`[UEPersonalization] [${type}] ${msg}`);
  }
}

/**
 * Загрузка состояния дисплеев и параметров рабочего стола.
 */
export async function loadPersonalizationState() {
  try {
    const resp = await fetch('/api/v1/settings/displays');
    if (resp.ok) {
      _activeDisplays = await resp.json();
      populateDisplaysSelect(_activeDisplays);
    }
  } catch (err) {
    console.warn('[UEPersonalization] Ошибка загрузки дисплеев:', err);
  }
}

/**
 * Заполнение селектора дисплеев.
 * @param {Array<Object>} displays Список мониторов.
 */
function populateDisplaysSelect(displays) {
  const select = document.getElementById('ue-select-display');
  if (!select) return;

  if (!displays || displays.length === 0) {
    select.innerHTML = '<option value="">Дисплеи не обнаружены</option>';
    return;
  }

  select.innerHTML = displays.map((d) => {
    const isPrimaryStr = d.is_primary ? ' [Основной]' : '';
    const nameStr = d.adapter_string ? `${d.id} (${d.adapter_string})${isPrimaryStr}` : `${d.id}${isPrimaryStr}`;
    return `<option value="${d.id}">${nameStr}</option>`;
  }).join('');

  if (!_currentDisplayId || !displays.some((d) => d.id === _currentDisplayId)) {
    const primary = displays.find((d) => d.is_primary) || displays[0];
    _currentDisplayId = primary.id;
  }

  select.value = _currentDisplayId;
  updateActiveDisplayUi();
}

/**
 * Обновление информации о выбранном дисплее.
 */
function updateActiveDisplayUi() {
  const disp = _activeDisplays.find((d) => d.id === _currentDisplayId);
  const badge = document.getElementById('ue-active-display-badge');
  const orientLabel = document.getElementById('ue-cur-orientation-label');

  if (disp) {
    if (badge) {
      badge.textContent = `${disp.width} × ${disp.height} @ ${disp.frequency_hz}Hz`;
    }
    if (orientLabel) {
      const titles = {
        landscape: 'Альбомная (0°)',
        portrait: 'Портретная (90°)',
        landscape_flipped: 'Альбомная перевёрнутая (180°)',
        portrait_flipped: 'Портретная перевёрнутая (270°)',
      };
      orientLabel.textContent = titles[disp.current_orientation] || disp.current_orientation;
    }
    highlightOrientationButton(disp.current_orientation);
  }
}

/**
 * Подсветка кнопки активной ориентации.
 * @param {string} orientation Ориентация.
 */
function highlightOrientationButton(orientation) {
  document.querySelectorAll('button[data-ue-orientation]').forEach((btn) => {
    if (btn.getAttribute('data-ue-orientation') === orientation) {
      btn.className = 'btn btn-primary';
    } else {
      btn.className = 'btn btn-outline-primary';
    }
  });
}

/**
 * Поворот экрана с запуском 15-секундного таймера подтверждения.
 * @param {string} orientation Целевая ориентация (landscape, portrait, etc.).
 */
export async function executeOrientationRotate(orientation) {
  if (!_currentDisplayId) {
    showToast('Выберите целевой монитор', 'warning');
    return;
  }

  try {
    const resp = await fetch('/api/v1/settings/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        command_id: 'MONITOR.ROTATE',
        params: {
          display_id: _currentDisplayId,
          orientation
        }
      })
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const resData = await resp.json();

    if (resData.success) {
      showToast('Ориентация дисплея изменена', 'success');
      startRotationCountdown();
      await loadPersonalizationState();
    } else {
      showToast(`Ошибка: ${resData.message}`, 'danger');
    }
  } catch (err) {
    showToast(`Сбой при повороте экрана: ${err.message}`, 'danger');
  }
}

/**
 * Запуск обратного отсчета подтверждения поворота (15 секунд).
 */
function startRotationCountdown() {
  const alertEl = document.getElementById('ue-rotate-countdown-alert');
  const timerBadge = document.getElementById('ue-rotate-timer-badge');
  if (!alertEl || !timerBadge) return;

  _remainingSeconds = 15;
  timerBadge.textContent = `${_remainingSeconds}s`;
  alertEl.classList.remove('d-none');
  alertEl.classList.add('d-flex');

  if (_countdownTimer) clearInterval(_countdownTimer);

  _countdownTimer = setInterval(async () => {
    _remainingSeconds -= 1;
    timerBadge.textContent = `${_remainingSeconds}s`;

    if (_remainingSeconds <= 0) {
      clearInterval(_countdownTimer);
      _countdownTimer = null;
      await cancelRotation();
    }
  }, 1000);
}

/**
 * Подтверждение сохранения нового режима экрана.
 */
export function confirmRotation() {
  if (_countdownTimer) {
    clearInterval(_countdownTimer);
    _countdownTimer = null;
  }
  const alertEl = document.getElementById('ue-rotate-countdown-alert');
  if (alertEl) {
    alertEl.classList.add('d-none');
    alertEl.classList.remove('d-flex');
  }
  showToast('Новый режим экрана успешно сохранён', 'success');
}

/**
 * Откат поворота экрана к предыдущему режиму.
 */
export async function cancelRotation() {
  if (_countdownTimer) {
    clearInterval(_countdownTimer);
    _countdownTimer = null;
  }
  const alertEl = document.getElementById('ue-rotate-countdown-alert');
  if (alertEl) {
    alertEl.classList.add('d-none');
    alertEl.classList.remove('d-flex');
  }

  try {
    await fetch('/api/v1/settings/rollback-last', { method: 'POST' });
    showToast('Ориентация экрана возвращена в исходное состояние', 'info');
    await loadPersonalizationState();
  } catch (err) {
    showToast(`Ошибка отката ориентации: ${err.message}`, 'danger');
  }
}

/**
 * Привязка событий панели персонализации.
 */
export function bindPersonalizationEvents() {
  const selectDisp = document.getElementById('ue-select-display');
  if (selectDisp) {
    selectDisp.addEventListener('change', () => {
      _currentDisplayId = selectDisp.value;
      updateActiveDisplayUi();
    });
  }

  document.querySelectorAll('button[data-ue-orientation]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const orientation = btn.getAttribute('data-ue-orientation');
      await executeOrientationRotate(orientation);
    });
  });

  document.getElementById('ue-btn-confirm-rotation')?.addEventListener('click', confirmRotation);
  document.getElementById('ue-btn-cancel-rotation')?.addEventListener('click', cancelRotation);
  document.getElementById('ue-btn-refresh-personalization')?.addEventListener('click', loadPersonalizationState);
}
