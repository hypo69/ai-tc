/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: Sound & Audio Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер панели звуковой подсистемы и аудиомикшера Windows.
 *   Управляет системными звуками, мастер-громкостью WASAPI, звуком запуска,
 *   индивидуальным микшером активных приложений и запуском звуковых апплетов.
 *
 * File: panel_sound.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 00:26:30
 * =============================================================================
 */

let _debounceSys = null;
let _debounceMaster = null;
const _debounceSessions = {};
let _lastSoundState = null;

/**
 * Вызов всплывающего уведомления Toast.
 * @param {string} msg Текст сообщения.
 * @param {'info'|'success'|'warning'|'danger'} type Тип уведомления.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[UESound] [${type}] ${msg}`);
  }
}

/**
 * Экранирование HTML для безопасного вывода.
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
 * Загрузка актуального состояния звука с сервера.
 */
export async function loadSoundState() {
  try {
    const resp = await fetch('/api/v1/sound/state');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _lastSoundState = data;
    renderSoundState(data);
    updateSoundKpis(data);
  } catch (err) {
    console.warn('[UESound] Ошибка получения состояния звука:', err);
  }
}

/**
 * Обновление сводных KPI звука в шапке вкладки.
 * @param {Object} state Состояние звука.
 */
function updateSoundKpis(state) {
  if (!state) return;
  const masterKpi = document.getElementById('ue-kpi-sound-master');
  const sysKpi = document.getElementById('ue-kpi-sound-sys');
  if (masterKpi) {
    masterKpi.textContent = `${state.master_volume}%${state.master_muted ? ' (Muted)' : ''}`;
  }
  if (sysKpi) {
    sysKpi.textContent = `${state.system_sounds_volume}%${state.system_sounds_muted ? ' (Muted)' : ''}`;
  }
}

/**
 * Отрисовка полученных параметров звука.
 * @param {Object} state DTO состояния звука.
 */
export function renderSoundState(state) {
  if (!state) return;

  // 1. Системные звуки
  const sysBadge = document.getElementById('ue-sound-sys-vol-badge');
  const sysRange = document.getElementById('ue-sound-sys-volume-range');
  const sysMuteBtn = document.getElementById('ue-sound-btn-sys-mute');
  const sysMuteIcon = document.getElementById('ue-sound-sys-mute-icon');
  const sysMuteText = document.getElementById('ue-sound-sys-mute-text');

  if (sysBadge) sysBadge.textContent = `${state.system_sounds_volume}%`;
  if (sysRange && document.activeElement !== sysRange) {
    sysRange.value = state.system_sounds_volume;
  }
  if (sysMuteBtn && sysMuteIcon && sysMuteText) {
    if (state.system_sounds_muted) {
      sysMuteBtn.className = 'btn btn-outline-danger d-flex align-items-center gap-2 px-3 py-2';
      sysMuteIcon.className = 'bi bi-volume-mute-fill';
      sysMuteText.textContent = 'Звук заглушен';
    } else {
      sysMuteBtn.className = 'btn btn-outline-secondary d-flex align-items-center gap-2 px-3 py-2';
      sysMuteIcon.className = 'bi bi-volume-up-fill';
      sysMuteText.textContent = 'Звук включен';
    }
  }

  // Звук запуска
  const startupToggle = document.getElementById('ue-sound-startup-toggle');
  if (startupToggle && document.activeElement !== startupToggle) {
    startupToggle.checked = Boolean(state.startup_sound_enabled);
  }

  // 2. Мастер-громкость
  const masterBadge = document.getElementById('ue-sound-master-vol-badge');
  const masterRange = document.getElementById('ue-sound-master-volume-range');
  const masterMuteBtn = document.getElementById('ue-sound-btn-master-mute');
  const masterMuteIcon = document.getElementById('ue-sound-master-mute-icon');
  const masterMuteText = document.getElementById('ue-sound-master-mute-text');
  const devNameEl = document.getElementById('ue-sound-default-device-name');
  const schemeLabel = document.getElementById('ue-sound-current-scheme-label');
  const outDevCount = document.getElementById('ue-sound-output-devices-count');

  if (masterBadge) masterBadge.textContent = `${state.master_volume}%`;
  if (masterRange && document.activeElement !== masterRange) {
    masterRange.value = state.master_volume;
  }
  if (masterMuteBtn && masterMuteIcon && masterMuteText) {
    if (state.master_muted) {
      masterMuteBtn.className = 'btn btn-outline-danger d-flex align-items-center gap-2 px-3 py-2';
      masterMuteIcon.className = 'bi bi-volume-mute-fill';
      masterMuteText.textContent = 'Звук заглушен';
    } else {
      masterMuteBtn.className = 'btn btn-outline-secondary d-flex align-items-center gap-2 px-3 py-2';
      masterMuteIcon.className = 'bi bi-volume-up-fill';
      masterMuteText.textContent = 'Звук включен';
    }
  }

  if (devNameEl) {
    devNameEl.textContent = state.default_output_device
      ? `Активное устройство: ${state.default_output_device}`
      : 'Устройство вывода по умолчанию';
  }
  if (schemeLabel) {
    schemeLabel.textContent = state.current_scheme === '.Default' ? 'Windows по умолчанию' : state.current_scheme;
  }
  if (outDevCount && Array.isArray(state.output_devices)) {
    outDevCount.textContent = state.output_devices.length;
  }

  // 3. Сессии микшера
  renderAudioSessions(state.active_sessions || []);
}

/**
 * Отрисовка списка аудиосессий приложений.
 * @param {Array<Object>} sessions Список сессий WASAPI.
 */
function renderAudioSessions(sessions) {
  const listEl = document.getElementById('ue-sound-sessions-list');
  const badgeEl = document.getElementById('ue-sound-sessions-count-badge');
  if (!listEl) return;

  if (badgeEl) {
    badgeEl.textContent = `${sessions.length} сессий`;
  }

  if (!sessions || sessions.length === 0) {
    listEl.innerHTML = `
      <div class="text-center text-muted py-4">
        <i class="bi bi-soundwave fs-3 d-block mb-1"></i>
        <span>Нет активных приложений, воспроизводящих звук</span>
      </div>
    `;
    return;
  }

  listEl.innerHTML = sessions.map((sess) => {
    const isMuted = Boolean(sess.is_muted);
    const vol = Math.round(sess.volume ?? 0);
    const isSys = Boolean(sess.is_system_sounds);
    const appName = escapeHtml(sess.name || 'Неизвестный процесс');
    const target = String(sess.id ?? sess.pid ?? '');
    const targetEsc = escapeHtml(target);
    const subLabel = isSys ? 'Служба звуковых оповещений' : `PID: ${sess.pid ?? 0}`;
    const iconClass = isSys ? 'bi-bell text-warning' : 'bi-app-indicator text-primary';

    return `
      <div class="d-flex align-items-center gap-3 p-3 rounded border border-secondary-subtle bg-body-tertiary">
        <div class="rounded p-2 bg-body border border-secondary-subtle d-flex align-items-center justify-content-center" style="width: 40px; height: 40px;">
          <i class="bi ${iconClass} fs-5"></i>
        </div>
        <div class="flex-grow-1" style="min-width: 150px;">
          <div class="fw-semibold text-truncate" title="${appName}">${appName}</div>
          <div class="text-muted small">${subLabel}</div>
        </div>
        <div class="d-flex align-items-center gap-2 flex-grow-1" style="max-width: 320px;">
          <button class="btn btn-sm ${isMuted ? 'btn-outline-danger' : 'btn-outline-secondary'} ue-sound-btn-sess-mute" data-target="${targetEsc}" data-muted="${isMuted ? 'true' : 'false'}" title="${isMuted ? 'Включить звук' : 'Заглушить'}">
            <i class="bi ${isMuted ? 'bi-volume-mute-fill' : 'bi-volume-up-fill'}"></i>
          </button>
          <input type="range" class="form-range ue-sound-sess-range flex-grow-1" data-target="${targetEsc}" min="0" max="100" step="1" value="${vol}">
          <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle" id="ue-sound-sess-val-${targetEsc}" style="min-width: 45px;">${vol}%</span>
        </div>
      </div>
    `;
  }).join('');

  // Привязка обработчиков микшера
  listEl.querySelectorAll('.ue-sound-sess-range').forEach((range) => {
    const target = range.getAttribute('data-target');
    const valBadge = document.getElementById(`ue-sound-sess-val-${target}`);
    range.addEventListener('input', () => {
      if (valBadge) valBadge.textContent = `${range.value}%`;
      clearTimeout(_debounceSessions[target]);
      _debounceSessions[target] = setTimeout(() => {
        setSessionVolume(target, parseInt(range.value, 10));
      }, 150);
    });
  });

  listEl.querySelectorAll('.ue-sound-btn-sess-mute').forEach((btn) => {
    const target = btn.getAttribute('data-target');
    const currentMuted = btn.getAttribute('data-muted') === 'true';
    btn.addEventListener('click', () => toggleSessionMute(target, !currentMuted));
  });
}

/**
 * Установка громкости системных звуков.
 * @param {number} volume Уровень громкости (0-100).
 */
export async function setSystemSoundsVolume(volume) {
  try {
    const resp = await fetch('/api/v1/sound/system-sounds-volume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  } catch (err) {
    showToast(`Ошибка системных звуков: ${err.message}`, 'danger');
  }
}

/**
 * Переключение mute системных звуков.
 */
export async function toggleSystemSoundsMute() {
  if (!_lastSoundState) return;
  const newMuted = !_lastSoundState.system_sounds_muted;
  try {
    const resp = await fetch('/api/v1/sound/system-sounds-mute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ muted: newMuted })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    _lastSoundState.system_sounds_muted = newMuted;
    renderSoundState(_lastSoundState);
    showToast(newMuted ? 'Системные звуки заглушены' : 'Системные звуки включены', 'info');
  } catch (err) {
    showToast(`Ошибка переключения: ${err.message}`, 'danger');
  }
}

/**
 * Переключение звука запуска Windows.
 * @param {boolean} enabled Включен ли звук запуска.
 */
export async function toggleStartupSound(enabled) {
  try {
    const resp = await fetch('/api/v1/sound/startup-sound', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ muted: Boolean(enabled) })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showToast(enabled ? 'Звук запуска Windows включен' : 'Звук запуска Windows выключен', 'success');
  } catch (err) {
    showToast(`Ошибка звука запуска: ${err.message}`, 'danger');
  }
}

/**
 * Воспроизведение тестового системного сигнала.
 * @param {string} soundType Тип звука (asterisk, exclamation, beep, question).
 */
export async function playTestSound(soundType) {
  try {
    const resp = await fetch('/api/v1/sound/test-sound', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sound: soundType })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showToast(`Сигнал воспроизведен (${soundType})`, 'success');
  } catch (err) {
    showToast(`Ошибка воспроизведения: ${err.message}`, 'danger');
  }
}

/**
 * Установка мастер-громкости WASAPI.
 * @param {number} volume Уровень громкости (0-100).
 */
export async function setMasterVolume(volume) {
  try {
    const resp = await fetch('/api/v1/sound/master-volume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  } catch (err) {
    showToast(`Ошибка мастер-громкости: ${err.message}`, 'danger');
  }
}

/**
 * Переключение mute мастер-громкости.
 */
export async function toggleMasterMute() {
  if (!_lastSoundState) return;
  const newMuted = !_lastSoundState.master_muted;
  try {
    const resp = await fetch('/api/v1/sound/master-mute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ muted: newMuted })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    _lastSoundState.master_muted = newMuted;
    renderSoundState(_lastSoundState);
    showToast(newMuted ? 'Мастер-звук заглушен' : 'Мастер-звук включен', 'info');
  } catch (err) {
    showToast(`Ошибка переключения: ${err.message}`, 'danger');
  }
}

/**
 * Установка громкости для сессии приложения.
 * @param {string|number} target Идентификатор сессии (PID или 'system_sounds').
 * @param {number} volume Громкость (0-100).
 */
export async function setSessionVolume(target, volume) {
  try {
    const resp = await fetch('/api/v1/sound/session-volume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: String(target), volume: Number(volume) })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  } catch (err) {
    console.warn(`[UESound] Ошибка громкости сессии ${target}:`, err);
  }
}

/**
 * Переключение mute для аудиосессии процесса.
 * @param {string|number} target Идентификатор сессии (PID или 'system_sounds').
 * @param {boolean} muted Новое состояние приглушения.
 */
export async function toggleSessionMute(target, muted) {
  try {
    const resp = await fetch('/api/v1/sound/session-mute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: String(target), muted: Boolean(muted) })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    await loadSoundState();
  } catch (err) {
    showToast(`Ошибка заглушения сессии ${target}: ${err.message}`, 'danger');
  }
}

/**
 * Запуск системных апплетов звука Windows.
 * @param {'settings'|'sndvol'|'mmsys'} tool Целевой системный инструмент.
 */
export async function launchSoundApplet(tool) {
  try {
    const resp = await fetch('/api/v1/sound/launch-tool', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showToast(`Запущен системный апплет: ${tool}`, 'info');
  } catch (err) {
    showToast(`Ошибка запуска апплета: ${err.message}`, 'danger');
  }
}

/**
 * Привязка событий элементов управления звуком.
 */
export function bindSoundEvents() {
  // Системные звуки
  const sysRange = document.getElementById('ue-sound-sys-volume-range');
  const sysBadge = document.getElementById('ue-sound-sys-vol-badge');
  if (sysRange) {
    sysRange.addEventListener('input', () => {
      if (sysBadge) sysBadge.textContent = `${sysRange.value}%`;
      clearTimeout(_debounceSys);
      _debounceSys = setTimeout(() => {
        setSystemSoundsVolume(parseInt(sysRange.value, 10));
      }, 150);
    });
  }

  document.getElementById('ue-sound-btn-sys-mute')?.addEventListener('click', toggleSystemSoundsMute);

  const startupToggle = document.getElementById('ue-sound-startup-toggle');
  if (startupToggle) {
    startupToggle.addEventListener('change', () => {
      toggleStartupSound(startupToggle.checked);
    });
  }

  document.getElementById('ue-sound-btn-test-sound')?.addEventListener('click', () => {
    const sel = document.getElementById('ue-sound-test-type');
    const val = sel ? sel.value : 'asterisk';
    playTestSound(val);
  });

  // Мастер-громкость
  const masterRange = document.getElementById('ue-sound-master-volume-range');
  const masterBadge = document.getElementById('ue-sound-master-vol-badge');
  if (masterRange) {
    masterRange.addEventListener('input', () => {
      if (masterBadge) masterBadge.textContent = `${masterRange.value}%`;
      clearTimeout(_debounceMaster);
      _debounceMaster = setTimeout(() => {
        setMasterVolume(parseInt(masterRange.value, 10));
      }, 150);
    });
  }

  document.getElementById('ue-sound-btn-master-mute')?.addEventListener('click', toggleMasterMute);

  // Системные апплеты
  document.getElementById('ue-sound-btn-open-settings')?.addEventListener('click', () => launchSoundApplet('settings'));
  document.getElementById('ue-sound-btn-open-sndvol')?.addEventListener('click', () => launchSoundApplet('sndvol'));
  document.getElementById('ue-sound-btn-open-mmsys')?.addEventListener('click', () => launchSoundApplet('mmsys'));
  document.getElementById('ue-sound-btn-refresh')?.addEventListener('click', loadSoundState);
}
