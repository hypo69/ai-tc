/**
 * =============================================================================
 * Process Name: Windows Web Interface - Desktop & Displays Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер интерактивного раздела «Рабочий стол и дисплеи»:
 *   - Перечисление мониторов, выбор активного дисплея
 *   - Поворот экрана (MONITOR.ROTATE) с таймером подтверждения и авто-откатом
 *   - Расположение панели задач (TASKBAR.SET_POSITION) с учетом Windows 10/11
 *   - Выравнивание значков панели задач (TASKBAR.SET_ALIGNMENT)
 *   - Автоматическое скрытие панели задач (TASKBAR.SET_AUTOHIDE)
 *   - Логирование контракта Command Registry
 *
 * Usage Examples:
 *   JavaScript:
 *     import { initDesktopDisplays } from './desktop_displays.js';
 *     await initDesktopDisplays();
 *
 * File: desktop_displays.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

let activeDisplays = [];
let currentDisplayId = '';
let countdownTimer = null;
let remainingSeconds = 0;

const SETTINGS_API = '/api/v1/settings';

/**
 * Инициализация элементов управления раздела «Рабочий стол и дисплеи».
 */
export async function initDesktopDisplays() {
  bindDisplayEvents();
  await refreshDesktopState();
}

/**
 * Привязка событий к кнопкам и элементам формы.
 */
function bindDisplayEvents() {
  // Селектор дисплеев
  const selectDisp = document.getElementById('winset-select-display');
  if (selectDisp) {
    selectDisp.onchange = () => {
      currentDisplayId = selectDisp.value;
      updateActiveDisplayUi();
    };
  }

  // Кнопки ориентации экрана
  document.querySelectorAll('button[data-orientation]').forEach((btn) => {
    btn.onclick = async () => {
      const orientation = btn.getAttribute('data-orientation');
      await executeOrientationRotate(orientation);
    };
  });

  // Кнопки баннера обратного отсчета при повороте экрана
  const btnConfirm = document.getElementById('winset-btn-confirm-rotation');
  if (btnConfirm) {
    btnConfirm.onclick = confirmRotation;
  }

  const btnCancel = document.getElementById('winset-btn-cancel-rotation');
  if (btnCancel) {
    btnCancel.onclick = cancelRotation;
  }

  // Кнопки расположения панели задач (bottom, top, left, right)
  document.querySelectorAll('button[data-position]').forEach((btn) => {
    btn.onclick = async () => {
      const position = btn.getAttribute('data-position');
      await executeTaskbarCommand('TASKBAR.SET_POSITION', { position });
    };
  });

  // Кнопки выравнивания значков панели задач (left, center)
  document.querySelectorAll('button[data-align]').forEach((btn) => {
    btn.onclick = async () => {
      const alignment = btn.getAttribute('data-align');
      await executeTaskbarCommand('TASKBAR.SET_ALIGNMENT', { alignment });
    };
  });

  // Переключатель автоскрытия панели задач
  const switchAutoHide = document.getElementById('winset-switch-autohide');
  if (switchAutoHide) {
    switchAutoHide.onchange = async () => {
      await executeTaskbarCommand('TASKBAR.SET_AUTOHIDE', { enabled: switchAutoHide.checked });
    };
  }
}

/**
 * Обновляет состояние дисплеев и панели задач с бэкенда.
 */
export async function refreshDesktopState() {
  try {
    // 1. Загрузка дисплеев
    const respDisplays = await fetch(`${SETTINGS_API}/displays`);
    if (respDisplays.ok) {
      activeDisplays = await respDisplays.json();
      populateDisplaysSelect(activeDisplays);
    }

    // 2. Загрузка состояния панели задач
    const respTb = await fetch(`${SETTINGS_API}/taskbar`);
    if (respTb.ok) {
      const data = await respTb.json();
      updateTaskbarUi(data.state);
    }

    // 3. Каталог и совместимость
    const respCat = await fetch(`${SETTINGS_API}/catalog`);
    if (respCat.ok) {
      const catData = await respCat.json();
      updateCompatibilityBadges(catData);
    }
  } catch (err) {
    console.warn('[DesktopDisplays] Ошибка загрузки состояния рабочего стола:', err);
  }
}

/**
 * Наполняет выпадающий список дисплеев.
 */
function populateDisplaysSelect(displays) {
  const select = document.getElementById('winset-select-display');
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

  if (!currentDisplayId || !displays.some((d) => d.id === currentDisplayId)) {
    const primary = displays.find((d) => d.is_primary) || displays[0];
    currentDisplayId = primary.id;
  }

  select.value = currentDisplayId;
  updateActiveDisplayUi();
}

/**
 * Обновляет отображение текущей ориентации для выбранного дисплея.
 */
function updateActiveDisplayUi() {
  const disp = activeDisplays.find((d) => d.id === currentDisplayId);
  const badge = document.getElementById('winset-active-display-badge');
  const orientLabel = document.getElementById('winset-cur-orientation-label');

  if (disp) {
    if (badge) {
      badge.textContent = `${disp.width}x${disp.height} @ ${disp.frequency_hz}Hz`;
      badge.className = 'badge bg-primary-subtle text-primary border';
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
 * Подсветка активной кнопки ориентации.
 */
function highlightOrientationButton(orientation) {
  document.querySelectorAll('button[data-orientation]').forEach((btn) => {
    if (btn.getAttribute('data-orientation') === orientation) {
      btn.classList.remove('btn-outline-primary');
      btn.classList.add('btn-primary');
    } else {
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-outline-primary');
    }
  });
}

/**
 * Обновление UI панели задач.
 */
function updateTaskbarUi(state) {
  if (!state) return;

  // Расположение панели (bottom, top, left, right)
  const pos = state.position || 'bottom';
  const posStatus = document.getElementById('winset-position-status');
  if (posStatus) {
    const posTitles = { bottom: 'Снизу', top: 'Сверху', left: 'Слева', right: 'Справа' };
    posStatus.textContent = posTitles[pos] || pos;
  }
  document.querySelectorAll('button[data-position]').forEach((btn) => {
    if (btn.getAttribute('data-position') === pos) {
      btn.classList.remove('btn-outline-secondary');
      btn.classList.add('btn-secondary');
    } else {
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-outline-secondary');
    }
  });

  // Выравнивание значков (left, center)
  const align = state.alignment_label || (state.alignment === 1 ? 'center' : 'left');
  document.querySelectorAll('button[data-align]').forEach((btn) => {
    if (btn.getAttribute('data-align') === align) {
      btn.classList.remove('btn-outline-primary');
      btn.classList.add('btn-primary');
    } else {
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-outline-primary');
    }
  });

  // Автоскрытие
  const switchAuto = document.getElementById('winset-switch-autohide');
  if (switchAuto) {
    switchAuto.checked = Boolean(state.auto_hide);
  }
}

/**
 * Обновление бейджей совместимости версий.
 */
function updateCompatibilityBadges(catData) {
  const badge = document.getElementById('winset-taskbar-compat-badge');
  const posHint = document.getElementById('winset-position-hint');
  if (badge) {
    badge.textContent = catData.is_win11 ? 'Windows 11 Shell' : 'Windows 10 Shell';
  }
  if (posHint && catData.is_win11) {
    posHint.innerHTML = '<span class="text-warning"><i class="bi bi-info-circle me-1"></i>В Windows 11 панель зафиксирована снизу. Верхняя и боковые позиции ограничены проводником.</span>';
  }
}

/**
 * Выполнение поворота дисплея через API с запуском обратного отсчета.
 */
async function executeOrientationRotate(orientation) {
  if (!currentDisplayId) {
    alert('Пожалуйста, выберите целевой дисплей');
    return;
  }

  logContractExecution('MONITOR.ROTATE', { display_id: currentDisplayId, orientation });

  try {
    const resp = await fetch(`${SETTINGS_API}/display/rotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_id: currentDisplayId,
        orientation: orientation,
        timeout_seconds: 15,
        auto_rollback: true,
      }),
    });

    const result = await resp.json();
    logContractResult('MONITOR.ROTATE', result);

    if (result.success) {
      highlightOrientationButton(result.actual_orientation);
      if (result.pending_rollback) {
        startCountdown(result.timeout_seconds || 15);
      }
      await refreshDesktopState();
    } else {
      alert(`Ошибка поворота экрана: ${result.error}`);
    }
  } catch (err) {
    alert(`Сбой вызова API поворота: ${err.message}`);
  }
}

/**
 * Запуск обратного отсчета подтверждения режима.
 */
function startCountdown(seconds) {
  stopCountdown();
  remainingSeconds = seconds;
  const alertEl = document.getElementById('winset-rotate-countdown-alert');
  const badgeEl = document.getElementById('winset-rotate-timer-badge');

  if (alertEl) alertEl.classList.remove('d-none');
  if (badgeEl) badgeEl.textContent = `${remainingSeconds}s`;

  countdownTimer = setInterval(() => {
    remainingSeconds -= 1;
    if (badgeEl) badgeEl.textContent = `${remainingSeconds}s`;
    if (remainingSeconds <= 0) {
      stopCountdown();
      refreshDesktopState();
    }
  }, 1000);
}

/**
 * Остановка таймера отката.
 */
function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  const alertEl = document.getElementById('winset-rotate-countdown-alert');
  if (alertEl) alertEl.classList.add('d-none');
}

/**
 * Подтверждение сохранения режима экрана.
 */
async function confirmRotation() {
  stopCountdown();
  try {
    const resp = await fetch(`${SETTINGS_API}/display/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_id: currentDisplayId }),
    });
    const res = await resp.json();
    logContractResult('MONITOR.CONFIRM', res);
    await refreshDesktopState();
  } catch (err) {
    console.error('Ошибка подтверждения ориентации:', err);
  }
}

/**
 * Немедленный откат поворота экрана.
 */
async function cancelRotation() {
  stopCountdown();
  try {
    const resp = await fetch(`${SETTINGS_API}/display/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_id: currentDisplayId }),
    });
    const res = await resp.json();
    logContractResult('MONITOR.ROLLBACK', res);
    await refreshDesktopState();
  } catch (err) {
    console.error('Ошибка отката ориентации:', err);
  }
}

/**
 * Универсальное выполнение команд панели задач через Command Registry.
 */
async function executeTaskbarCommand(command, params) {
  logContractExecution(command, params);
  try {
    const resp = await fetch(`${SETTINGS_API}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, params }),
    });

    const res = await resp.json();
    logContractResult(command, res);

    if (res.success) {
      await refreshDesktopState();
    } else {
      alert(`Ошибка выполнения команды ${command}: ${res.error}`);
    }
  } catch (err) {
    alert(`Сбой отправки команды: ${err.message}`);
  }
}

/**
 * Логирование начала выполнения контракта в интерактивной мини-консоли.
 */
function logContractExecution(command, params) {
  const cmdEl = document.getElementById('winset-contract-cmd');
  const resEl = document.getElementById('winset-contract-result');
  if (cmdEl) cmdEl.textContent = `${command} (${JSON.stringify(params)})`;
  if (resEl) resEl.textContent = 'Выполнение...';
}

/**
 * Логирование результата контракта в мини-консоли.
 */
function logContractResult(command, result) {
  const resEl = document.getElementById('winset-contract-result');
  if (resEl) {
    const isOk = result.success !== false;
    const colorClass = isOk ? 'text-success' : 'text-danger';
    const statusText = isOk ? 'OK' : 'ERROR';
    const actualStr = result.actual ? JSON.stringify(result.actual) : (result.message || '');
    resEl.innerHTML = `<span class="${colorClass}">[${statusText}]</span> ${actualStr}`;
  }
}

