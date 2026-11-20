/**
 * =============================================================================
 * Process Name: Windows Web Interface - Sound Settings Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер панели настройки звука Windows.
 *   Управляет получением параметров звука, регулировкой громкости системных
 *   звуков, мастер-громкости, аудио-микшера сессий и системных звуковых схем.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_sound_settings/main.js?v=20261027_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_sound_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

(function () {
  'use strict';

  let _pollInterval = null;
  let _debounceTimerSys = null;
  let _debounceTimerMaster = null;
  const _debounceTimersSession = {};
  let _lastState = null;

  /**
   * Выводит всплывающее уведомление toast.
   * @param {string} message - Текст сообщения.
   * @param {'info'|'success'|'warning'|'danger'} type - Тип уведомления.
   */
  function showToastNotification(message, type = 'info') {
    if (window.showToast && typeof window.showToast === 'function') {
      window.showToast(message, type);
    } else {
      console.log(`[SoundTab] [${type}] ${message}`);
    }
  }

  /**
   * Загружает текущее состояние звуковой подсистемы с сервера.
   */
  async function loadSoundState() {
    try {
      const resp = await fetch('/api/v1/sound/state');
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      const data = await resp.json();
      _lastState = data;
      renderSoundState(data);
    } catch (err) {
      console.warn('[SoundTab] Ошибка получения состояния звука:', err);
    }
  }

  /**
   * Отрисовывает полученное состояние параметров звука в интерфейсе.
   * @param {Object} state - DTO состояния звука.
   */
  function renderSoundState(state) {
    if (!state) return;

    // 1. Системные звуки
    const sysBadge = document.getElementById('sound-sys-vol-badge');
    const sysRange = document.getElementById('sound-sys-volume-range');
    const sysMuteBtn = document.getElementById('sound-btn-sys-mute');
    const sysMuteIcon = document.getElementById('sound-sys-mute-icon');
    const sysMuteText = document.getElementById('sound-sys-mute-text');

    if (sysBadge) sysBadge.textContent = `${state.system_sounds_volume}%`;
    if (sysRange && document.activeElement !== sysRange) {
      sysRange.value = state.system_sounds_volume;
    }
    if (sysMuteBtn && sysMuteIcon && sysMuteText) {
      if (state.system_sounds_muted) {
        sysMuteBtn.classList.remove('btn-outline-secondary');
        sysMuteBtn.classList.add('btn-outline-danger');
        sysMuteIcon.className = 'bi bi-volume-mute-fill';
        sysMuteText.textContent = 'Звук заглушен';
      } else {
        sysMuteBtn.classList.remove('btn-outline-danger');
        sysMuteBtn.classList.add('btn-outline-secondary');
        sysMuteIcon.className = 'bi bi-volume-up-fill';
        sysMuteText.textContent = 'Звук включен';
      }
    }

    // Звук запуска Windows
    const startupToggle = document.getElementById('sound-startup-toggle');
    if (startupToggle && document.activeElement !== startupToggle) {
      startupToggle.checked = Boolean(state.startup_sound_enabled);
    }

    // 2. Мастер-громкость
    const masterBadge = document.getElementById('sound-master-vol-badge');
    const masterRange = document.getElementById('sound-master-volume-range');
    const masterMuteBtn = document.getElementById('sound-btn-master-mute');
    const masterMuteIcon = document.getElementById('sound-master-mute-icon');
    const masterMuteText = document.getElementById('sound-master-mute-text');
    const devNameEl = document.getElementById('sound-default-device-name');
    const schemeLabel = document.getElementById('sound-current-scheme-label');
    const outDevCount = document.getElementById('sound-output-devices-count');

    if (masterBadge) masterBadge.textContent = `${state.master_volume}%`;
    if (masterRange && document.activeElement !== masterRange) {
      masterRange.value = state.master_volume;
    }
    if (masterMuteBtn && masterMuteIcon && masterMuteText) {
      if (state.master_muted) {
        masterMuteBtn.classList.remove('btn-outline-secondary');
        masterMuteBtn.classList.add('btn-outline-danger');
        masterMuteIcon.className = 'bi bi-volume-mute-fill';
        masterMuteText.textContent = 'Звук заглушен';
      } else {
        masterMuteBtn.classList.remove('btn-outline-danger');
        masterMuteBtn.classList.add('btn-outline-secondary');
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
   * Отрисовывает список активных аудиосессий микшера.
   * @param {Array<Object>} sessions - Список аудиосессий.
   */
  function renderAudioSessions(sessions) {
    const listEl = document.getElementById('sound-sessions-list');
    const badgeEl = document.getElementById('sound-sessions-count-badge');
    if (!listEl) return;

    if (badgeEl) {
      badgeEl.textContent = `${sessions.length} активн.`;
    }

    if (!sessions || sessions.length === 0) {
      listEl.innerHTML = `
        <div class="text-center text-muted py-3">
          <i class="bi bi-music-note-list fs-3 d-block mb-1"></i>
          <div>Нет активных программ, воспроизводящих звук в данный момент.</div>
        </div>
      `;
      return;
    }

    // Сохраняем значения элементов в фокусе
    const focusedInputId = document.activeElement ? document.activeElement.id : null;

    let html = '';
    sessions.forEach((s) => {
      const isSys = s.is_system_sounds;
      const iconClass = isSys ? 'bi-bell text-warning' : 'bi-app-indicator text-primary';
      const rangeId = `sound-sess-range-${s.id}`;
      const muteBtnId = `sound-sess-mute-${s.id}`;

      html += `
        <div class="d-flex flex-wrap align-items-center justify-content-between p-2 rounded bg-body-tertiary border border-secondary-subtle gap-2">
          <div class="d-flex align-items-center gap-2" style="min-width: 200px;">
            <i class="bi ${iconClass} fs-5"></i>
            <div>
              <div class="fw-semibold text-truncate" style="max-width: 250px;">${escapeHtml(s.name)}</div>
              <div class="text-muted small">${isSys ? 'Служба звуковых оповещений' : `PID: ${s.pid}`}</div>
            </div>
          </div>
          <div class="d-flex align-items-center gap-2 flex-grow-1" style="max-width: 450px;">
            <button class="btn btn-sm ${s.is_muted ? 'btn-outline-danger' : 'btn-outline-secondary'} px-2 py-1" id="${muteBtnId}" data-target="${escapeHtml(s.id)}" data-muted="${s.is_muted}" title="Mute/Unmute">
              <i class="bi ${s.is_muted ? 'bi-volume-mute-fill' : 'bi-volume-up-fill'}"></i>
            </button>
            <input type="range" class="form-range flex-grow-1" id="${rangeId}" min="0" max="100" step="1" value="${s.volume}" data-target="${escapeHtml(s.id)}">
            <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle" style="min-width: 45px;" id="sound-sess-val-${s.id}">${s.volume}%</span>
          </div>
        </div>
      `;
    });

    listEl.innerHTML = html;

    // Восстанавливаем фокус, если был
    if (focusedInputId) {
      const el = document.getElementById(focusedInputId);
      if (el) el.focus();
    }

    // Навешиваем обработчики для каждой сессии
    sessions.forEach((s) => {
      const rangeEl = document.getElementById(`sound-sess-range-${s.id}`);
      const muteEl = document.getElementById(`sound-sess-mute-${s.id}`);
      const valEl = document.getElementById(`sound-sess-val-${s.id}`);

      if (rangeEl) {
        rangeEl.addEventListener('input', (e) => {
          const val = parseInt(e.target.value, 10);
          if (valEl) valEl.textContent = `${val}%`;

          clearTimeout(_debounceTimersSession[s.id]);
          _debounceTimersSession[s.id] = setTimeout(() => {
            updateSessionVolume(s.id, val);
          }, 150);
        });
      }

      if (muteEl) {
        muteEl.addEventListener('click', () => {
          const newMuted = !s.is_muted;
          updateSessionMute(s.id, newMuted);
        });
      }
    });
  }

  /**
   * Экранирует HTML строку.
   */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Отправляет запрос на изменение громкости системных звуков.
   * @param {number} vol - Уровень громкости (0-100).
   */
  async function updateSystemSoundsVolume(vol) {
    try {
      const resp = await fetch('/api/v1/sound/system-sounds-volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume: vol }),
      });
      if (!resp.ok) throw new Error('Ошибка сервера');
      const badge = document.getElementById('sound-sys-vol-badge');
      if (badge) badge.textContent = `${vol}%`;
    } catch (err) {
      showToastNotification(`Не удалось изменить громкость системных звуков: ${err.message}`, 'danger');
    }
  }

  /**
   * Отправляет запрос на переключение Mute системных звуков.
   * @param {boolean} muted - Состояние Mute.
   */
  async function updateSystemSoundsMute(muted) {
    try {
      const resp = await fetch('/api/v1/sound/system-sounds-mute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ muted: muted }),
      });
      if (!resp.ok) throw new Error('Ошибка сервера');
      await loadSoundState();
      showToastNotification(muted ? 'Системные звуки отключены' : 'Системные звуки включены', 'info');
    } catch (err) {
      showToastNotification(`Ошибка переключения Mute: ${err.message}`, 'danger');
    }
  }

  /**
   * Отправляет запрос на изменение мастер-громкости.
   * @param {number} vol - Уровень мастер-громкости (0-100).
   */
  async function updateMasterVolume(vol) {
    try {
      const resp = await fetch('/api/v1/sound/master-volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume: vol }),
      });
      if (!resp.ok) throw new Error('Ошибка сервера');
      const badge = document.getElementById('sound-master-vol-badge');
      if (badge) badge.textContent = `${vol}%`;
    } catch (err) {
      showToastNotification(`Не удалось изменить мастер-громкость: ${err.message}`, 'danger');
    }
  }

  /**
   * Отправляет запрос на переключение Master Mute.
   * @param {boolean} muted - Состояние Mute.
   */
  async function updateMasterMute(muted) {
    try {
      const resp = await fetch('/api/v1/sound/master-mute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ muted: muted }),
      });
      if (!resp.ok) throw new Error('Ошибка сервера');
      await loadSoundState();
      showToastNotification(muted ? 'Основной звук заглушен' : 'Основной звук включен', 'info');
    } catch (err) {
      showToastNotification(`Ошибка переключения Master Mute: ${err.message}`, 'danger');
    }
  }

  /**
   * Отправляет запрос на изменение громкости отдельной аудиосессии.
   */
  async function updateSessionVolume(target, vol) {
    try {
      await fetch('/api/v1/sound/session-volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: String(target), volume: vol }),
      });
    } catch (err) {
      console.warn('[SoundTab] Ошибка громкости сессии:', err);
    }
  }

  /**
   * Отправляет запрос на переключение Mute аудиосессии.
   */
  async function updateSessionMute(target, muted) {
    try {
      await fetch('/api/v1/sound/session-mute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: String(target), muted: muted }),
      });
      await loadSoundState();
    } catch (err) {
      console.warn('[SoundTab] Ошибка Mute сессии:', err);
    }
  }

  /**
   * Привязывает события к элементам интерфейса вкладки.
   */
  function bindEvents() {
    // Кнопка обновления
    const refreshBtn = document.getElementById('sound-btn-refresh');
    if (refreshBtn) {
      refreshBtn.onclick = () => {
        loadSoundState();
        showToastNotification('Параметры звука обновлены', 'success');
      };
    }

    // Ползунок системных звуков
    const sysRange = document.getElementById('sound-sys-volume-range');
    if (sysRange) {
      sysRange.oninput = (e) => {
        const val = parseInt(e.target.value, 10);
        const badge = document.getElementById('sound-sys-vol-badge');
        if (badge) badge.textContent = `${val}%`;

        clearTimeout(_debounceTimerSys);
        _debounceTimerSys = setTimeout(() => {
          updateSystemSoundsVolume(val);
        }, 150);
      };
    }

    // Кнопка Mute системных звуков
    const sysMuteBtn = document.getElementById('sound-btn-sys-mute');
    if (sysMuteBtn) {
      sysMuteBtn.onclick = () => {
        const currentMuted = _lastState ? _lastState.system_sounds_muted : false;
        updateSystemSoundsMute(!currentMuted);
      };
    }

    // Ползунок мастер-громкости
    const masterRange = document.getElementById('sound-master-volume-range');
    if (masterRange) {
      masterRange.oninput = (e) => {
        const val = parseInt(e.target.value, 10);
        const badge = document.getElementById('sound-master-vol-badge');
        if (badge) badge.textContent = `${val}%`;

        clearTimeout(_debounceTimerMaster);
        _debounceTimerMaster = setTimeout(() => {
          updateMasterVolume(val);
        }, 150);
      };
    }

    // Кнопка Master Mute
    const masterMuteBtn = document.getElementById('sound-btn-master-mute');
    if (masterMuteBtn) {
      masterMuteBtn.onclick = () => {
        const currentMuted = _lastState ? _lastState.master_muted : false;
        updateMasterMute(!currentMuted);
      };
    }

    // Переключатель звука запуска
    const startupToggle = document.getElementById('sound-startup-toggle');
    if (startupToggle) {
      startupToggle.onchange = async (e) => {
        const enabled = e.target.checked;
        try {
          const resp = await fetch('/api/v1/sound/startup-sound', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ muted: enabled }),
          });
          if (!resp.ok) throw new Error('Требуются права Администратора');
          showToastNotification(enabled ? 'Звук запуска Windows включен' : 'Звук запуска Windows отключен', 'success');
        } catch (err) {
          showToastNotification(`Ошибка настройки звука запуска: ${err.message}`, 'warning');
          await loadSoundState();
        }
      };
    }

    // Кнопка проверки звука
    const testSoundBtn = document.getElementById('sound-btn-test-sound');
    if (testSoundBtn) {
      testSoundBtn.onclick = async () => {
        const select = document.getElementById('sound-test-type');
        const soundType = select ? select.value : 'asterisk';
        try {
          await fetch('/api/v1/sound/test-sound', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sound: soundType }),
          });
        } catch (err) {
          console.warn('[SoundTab] Ошибка проигрывания сигнала:', err);
        }
      };
    }

    // Системные инструменты
    const btnSettings = document.getElementById('sound-btn-open-settings');
    if (btnSettings) {
      btnSettings.onclick = () => launchSoundTool('settings');
    }
    const btnSndvol = document.getElementById('sound-btn-open-sndvol');
    if (btnSndvol) {
      btnSndvol.onclick = () => launchSoundTool('sndvol');
    }
    const btnMmsys = document.getElementById('sound-btn-open-mmsys');
    if (btnMmsys) {
      btnMmsys.onclick = () => launchSoundTool('mmsys');
    }
  }

  /**
   * Запускает системный апплет звука.
   */
  async function launchSoundTool(tool) {
    try {
      await fetch('/api/v1/sound/launch-tool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: tool }),
      });
      showToastNotification(`Запущен инструмент: ${tool}`, 'info');
    } catch (err) {
      showToastNotification(`Ошибка запуска утилиты: ${err.message}`, 'danger');
    }
  }

  /**
   * Инициализация вкладки при активации в интерфейсе.
   */
  window.initSoundSettingsTab = function () {
    bindEvents();
    loadSoundState();

    // Опрос состояния сессий раз в 5 секунд при активной вкладке
    if (_pollInterval) clearInterval(_pollInterval);
    _pollInterval = setInterval(() => {
      loadSoundState();
    }, 5000);
  };

  /**
   * Деактивация вкладки при переходе на другую страницу.
   */
  window.deactivateSoundSettingsTab = function () {
    if (_pollInterval) {
      clearInterval(_pollInterval);
      _pollInterval = null;
    }
  };
})();
