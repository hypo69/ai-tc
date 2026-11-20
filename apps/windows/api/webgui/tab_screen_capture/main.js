/**
 * =============================================================================
 * Process Name: AI-Windows-Admin UI - Screen Capture Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер вкладки Windows.Graphics.Capture & Screen Capture Engine.
 *   Обеспечивает захват мониторов и окон, потоковый опрос, управление настройками,
 *   отображение Screen Diff и корреляцию с ETW-телеметрией.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_screen_capture
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:56:00
 * =============================================================================
 */

(function () {
  'use strict';

  // Состояние контроллера
  let state = {
    isStreaming: false,
    pollTimer: null,
    displays: [],
    windows: [],
    historyFrames: [],
    activeTargetType: 'display', // 'display' | 'window'
  };

  /**
   * Инициализирует вкладку при её активации в DOM.
   */
  window.initScreenCaptureTab = function () {
    bindEvents();
    loadDisplays();
    loadWindows();
    loadConfig();
    loadCapabilities();
    loadEtwEvents();
    checkStreamStatus();
  };

  /**
   * Деактивирует вкладку и останавливает фоновые таймеры.
   */
  window.deactivateScreenCaptureTab = function () {
    stopPollingTimer();
  };

  /**
   * Привязка событий интерфейса.
   */
  function bindEvents() {
    // Переключение типа цели (дисплей / окно)
    const typeDisplay = document.getElementById('sc-type-display');
    const typeWindow = document.getElementById('sc-type-window');
    if (typeDisplay && typeWindow) {
      typeDisplay.addEventListener('change', () => switchTargetType('display'));
      typeWindow.addEventListener('change', () => switchTargetType('window'));
    }

    // Фильтр окон
    const winFilter = document.getElementById('sc-input-win-filter');
    if (winFilter) {
      winFilter.addEventListener('input', () => filterWindowsList(winFilter.value));
    }

    // Кнопка снимка
    const btnSnap = document.getElementById('sc-btn-snap');
    if (btnSnap) {
      btnSnap.addEventListener('click', captureCurrentTarget);
    }

    // Кнопка старт/стоп потока
    const btnStream = document.getElementById('sc-btn-stream-toggle');
    if (btnStream) {
      btnStream.addEventListener('click', toggleStream);
    }

    // Кнопка общего обновления
    const btnRefresh = document.getElementById('sc-btn-refresh');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        loadDisplays();
        loadWindows();
        loadEtwEvents();
        checkStreamStatus();
      });
    }

    // Слайдеры настроек (обновление бейджей значений)
    setupRangeBadge('sc-cfg-fps', 'sc-cfg-fps-val', ' FPS');
    setupRangeBadge('sc-cfg-quality', 'sc-cfg-quality-val', '%');
    setupRangeBadge('sc-cfg-diff-threshold', 'sc-cfg-diff-threshold-val', '%', (v) => (parseFloat(v) * 100).toFixed(1));

    // Сохранение настроек
    const btnSaveCfg = document.getElementById('sc-btn-save-settings');
    if (btnSaveCfg) {
      btnSaveCfg.addEventListener('click', saveConfig);
    }

    // Обновление таблицы ETW
    const btnRefreshEtw = document.getElementById('sc-btn-refresh-etw');
    if (btnRefreshEtw) {
      btnRefreshEtw.addEventListener('click', loadEtwEvents);
    }
  }

  function setupRangeBadge(sliderId, badgeId, suffix, transform) {
    const slider = document.getElementById(sliderId);
    const badge = document.getElementById(badgeId);
    if (!slider || !badge) return;
    slider.addEventListener('input', () => {
      const val = transform ? transform(slider.value) : slider.value;
      badge.textContent = `${val}${suffix}`;
    });
  }

  function switchTargetType(type) {
    state.activeTargetType = type;
    const dispBlock = document.getElementById('sc-display-select-block');
    const winBlock = document.getElementById('sc-window-select-block');
    const kindBadge = document.getElementById('sc-target-kind-badge');

    if (type === 'display') {
      if (dispBlock) dispBlock.classList.remove('d-none');
      if (winBlock) winBlock.classList.add('d-none');
      if (kindBadge) kindBadge.textContent = 'Дисплей';
    } else {
      if (dispBlock) dispBlock.classList.add('d-none');
      if (winBlock) winBlock.classList.remove('d-none');
      if (kindBadge) kindBadge.textContent = 'Окно';
    }
  }

  /**
   * Загрузка списка мониторов.
   */
  async function loadDisplays() {
    try {
      const res = await fetch('/api/v1/vision/capture/displays');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.displays = data;

      const select = document.getElementById('sc-select-display');
      if (!select) return;
      select.innerHTML = '';

      data.forEach((d) => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = `${d.name} (${d.width}x${d.height})${d.is_primary ? ' [Основной]' : ''}`;
        select.appendChild(opt);
      });
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка загрузки дисплеев:', err);
    }
  }

  /**
   * Загрузка списка открытых окон.
   */
  async function loadWindows() {
    try {
      const res = await fetch('/api/v1/vision/capture/windows?limit=100');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.windows = data;
      renderWindowsSelect(data);
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка загрузки окон:', err);
    }
  }

  function renderWindowsSelect(items) {
    const select = document.getElementById('sc-select-window');
    if (!select) return;
    select.innerHTML = '';

    if (items.length === 0) {
      select.innerHTML = '<option value="">Нет подходящих окон</option>';
      return;
    }

    items.forEach((w) => {
      const opt = document.createElement('option');
      opt.value = w.id;
      const proc = w.process_name ? ` [${w.process_name}]` : '';
      const hung = w.is_hung ? ' ⚠️(Зависло)' : '';
      opt.textContent = `${w.title}${proc} (${w.width}x${w.height})${hung}`;
      select.appendChild(opt);
    });

    if (items.length > 0 && !select.value) {
      select.selectedIndex = 0;
    }
  }

  function filterWindowsList(query) {
    if (!query) {
      renderWindowsSelect(state.windows);
      return;
    }
    const q = query.toLowerCase();
    const filtered = state.windows.filter(
      (w) => w.title.toLowerCase().includes(q) || (w.process_name && w.process_name.toLowerCase().includes(q))
    );
    renderWindowsSelect(filtered);
  }

  /**
   * Выполнение моментального снимка.
   */
  async function captureCurrentTarget() {
    const isDisplay = state.activeTargetType === 'display';
    let url = '/api/v1/vision/capture/display';
    let body = {};

    if (isDisplay) {
      const dispSel = document.getElementById('sc-select-display');
      const dispId = dispSel ? parseInt(dispSel.value || '0', 10) : 0;
      body = { display_id: dispId };
    } else {
      url = '/api/v1/vision/capture/window';
      const winSel = document.getElementById('sc-select-window');
      const winId = winSel ? parseInt(winSel.value || '0', 10) : 0;
      if (!winId) {
        alert('Пожалуйста, выберите окно для захвата');
        return;
      }
      body = { window_id: winId };
    }

    setSpinner(true);
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const frame = await res.json();
      displayFrame(frame);
      addFrameToHistory(frame);
      loadEtwEvents();
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка захвата кадра:', err);
      alert('Ошибка захвата кадра: ' + err.message);
    } finally {
      setSpinner(false);
    }
  }

  /**
   * Отображение кадра в видоискателе.
   */
  function displayFrame(frame) {
    if (!frame) return;

    const img = document.getElementById('sc-preview-image');
    const emptyState = document.getElementById('sc-preview-empty-state');
    const tsLabel = document.getElementById('sc-preview-ts');

    if (img && frame.data_base64) {
      img.src = frame.data_base64;
      img.classList.remove('d-none');
      if (emptyState) emptyState.classList.add('d-none');
    }

    if (tsLabel) {
      const d = new Date(frame.timestamp_utc);
      tsLabel.textContent = `${frame.target_title || ''} (${d.toLocaleTimeString()})`;
    }

    // Метаданные
    const resElem = document.getElementById('sc-meta-resolution');
    if (resElem) resElem.textContent = `${frame.width} × ${frame.height}`;

    const sizeElem = document.getElementById('sc-meta-size');
    if (sizeElem) sizeElem.textContent = `${(frame.size_bytes / 1024).toFixed(1)} КБ`;

    const diffElem = document.getElementById('sc-meta-diff');
    if (diffElem) {
      const diffPct = (frame.diff_ratio * 100).toFixed(1);
      diffElem.textContent = `${diffPct}%`;
      diffElem.className = frame.diff_ratio > 0.05 ? 'fw-medium text-warning font-monospace' : 'fw-medium font-monospace';
    }

    const beElem = document.getElementById('sc-meta-backend');
    if (beElem) beElem.textContent = frame.backend_used ? frame.backend_used.toUpperCase() : 'GDI';
  }

  function addFrameToHistory(frame) {
    state.historyFrames.unshift(frame);
    if (state.historyFrames.length > 20) state.historyFrames.pop();

    const container = document.getElementById('sc-history-container');
    const emptyMsg = document.getElementById('sc-history-empty');
    if (!container) return;
    if (emptyMsg) emptyMsg.remove();

    const item = document.createElement('div');
    item.className = 'd-flex align-items-center gap-2 p-1 border-bottom border-subtle small cursor-pointer';
    item.style.cursor = 'pointer';

    const timeStr = new Date(frame.timestamp_utc).toLocaleTimeString();
    item.innerHTML = `
      <img src="${frame.data_base64}" style="width: 50px; height: 32px; object-fit: cover;" class="rounded border border-subtle">
      <div class="flex-grow-1 text-truncate">
        <div class="fw-medium text-truncate">${frame.target_title || frame.target_id}</div>
        <small class="text-secondary">${timeStr} | diff: ${(frame.diff_ratio * 100).toFixed(0)}%</small>
      </div>
    `;

    item.addEventListener('click', () => displayFrame(frame));
    container.prepend(item);
  }

  /**
   * Запуск / остановка видеопотока.
   */
  async function toggleStream() {
    if (state.isStreaming) {
      await stopStream();
    } else {
      await startStream();
    }
  }

  async function startStream() {
    const isDisplay = state.activeTargetType === 'display';
    let targetId = 0;
    if (isDisplay) {
      const dispSel = document.getElementById('sc-select-display');
      targetId = dispSel ? parseInt(dispSel.value || '0', 10) : 0;
    } else {
      const winSel = document.getElementById('sc-select-window');
      targetId = winSel ? parseInt(winSel.value || '0', 10) : 0;
    }

    try {
      const res = await fetch('/api/v1/vision/capture/stream/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_type: state.activeTargetType,
          target_id: targetId,
        }),
      });
      const data = await res.json();
      updateStreamUI(true);
      startPollingTimer();
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка старта стрима:', err);
    }
  }

  async function stopStream() {
    try {
      await fetch('/api/v1/vision/capture/stream/stop', { method: 'POST' });
      updateStreamUI(false);
      stopPollingTimer();
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка остановки стрима:', err);
    }
  }

  async function checkStreamStatus() {
    try {
      const res = await fetch('/api/v1/vision/capture/stream/status');
      if (!res.ok) return;
      const status = await res.json();
      updateStreamUI(status.is_streaming, status.fps_actual);
      if (status.is_streaming && !state.pollTimer) {
        startPollingTimer();
      }
    } catch (err) {
      // Игнорируем сетевые ошибки статуса
    }
  }

  function updateStreamUI(isStreaming, fps = 0.0) {
    state.isStreaming = isStreaming;
    const btn = document.getElementById('sc-btn-stream-toggle');
    const icon = document.getElementById('sc-stream-icon');
    const label = document.getElementById('sc-stream-label');
    const fpsBadge = document.getElementById('sc-screen-capture-fps-badge');
    const statusBadge = document.getElementById('sc-screen-capture-status-badge');

    if (btn && icon && label) {
      if (isStreaming) {
        btn.className = 'btn btn-sm btn-danger d-flex align-items-center gap-2';
        icon.className = 'bi bi-stop-circle';
        label.textContent = 'Стоп потока';
      } else {
        btn.className = 'btn btn-sm btn-success d-flex align-items-center gap-2';
        icon.className = 'bi bi-play-circle';
        label.textContent = 'Старт потока';
      }
    }

    if (fpsBadge) {
      fpsBadge.textContent = `${fps.toFixed(1)} FPS`;
      fpsBadge.className = isStreaming
        ? 'badge bg-success-subtle text-success border border-success-subtle px-2 py-0.5 small'
        : 'badge bg-secondary-subtle text-secondary border border-subtle px-2 py-0.5 small';
    }

    if (statusBadge) {
      statusBadge.textContent = isStreaming ? 'Поток активен' : 'Готов к захвату';
      statusBadge.className = isStreaming
        ? 'badge bg-success-subtle text-success border border-success-subtle px-2 py-0.5 small'
        : 'badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-0.5 small';
    }
  }

  function startPollingTimer() {
    stopPollingTimer();
    state.pollTimer = setInterval(pollLatestFrame, 500);
  }

  function stopPollingTimer() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function pollLatestFrame() {
    try {
      const res = await fetch('/api/v1/vision/capture/stream/latest');
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'ok' && data.frame) {
        displayFrame(data.frame);
      }
      // Периодическое обновление FPS
      const statusRes = await fetch('/api/v1/vision/capture/stream/status');
      if (statusRes.ok) {
        const s = await statusRes.json();
        updateStreamUI(s.is_streaming, s.fps_actual);
      }
    } catch (err) {
      // Молчаливый пропуск ошибок поллинга
    }
  }

  /**
   * Загрузка и сохранение настроек захвата.
   */
  async function loadConfig() {
    try {
      const res = await fetch('/api/v1/vision/capture/config');
      if (!res.ok) return;
      const cfg = await res.json();

      setVal('sc-cfg-backend', cfg.backend);
      setVal('sc-cfg-fps', cfg.fps_limit);
      setVal('sc-cfg-format', cfg.image_format);
      setVal('sc-cfg-quality', cfg.image_quality);
      setVal('sc-cfg-diff-threshold', cfg.diff_threshold);
      setVal('sc-cfg-history-size', cfg.history_buffer_size);

      const etwToggle = document.getElementById('sc-cfg-etw-toggle');
      if (etwToggle) etwToggle.checked = Boolean(cfg.enable_etw_correlation);

      // Обновляем бейджи
      setElemText('sc-cfg-fps-val', `${cfg.fps_limit} FPS`);
      setElemText('sc-cfg-quality-val', `${cfg.image_quality}%`);
      setElemText('sc-cfg-diff-threshold-val', `${(cfg.diff_threshold * 100).toFixed(1)}%`);
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка чтения конфигурации:', err);
    }
  }

  async function saveConfig() {
    const payload = {
      backend: getVal('sc-cfg-backend'),
      fps_limit: parseInt(getVal('sc-cfg-fps'), 10),
      image_format: getVal('sc-cfg-format'),
      image_quality: parseInt(getVal('sc-cfg-quality'), 10),
      diff_threshold: parseFloat(getVal('sc-cfg-diff-threshold')),
      history_buffer_size: parseInt(getVal('sc-cfg-history-size'), 10),
      enable_etw_correlation: document.getElementById('sc-cfg-etw-toggle')?.checked ?? true,
    };

    try {
      const res = await fetch('/api/v1/vision/capture/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      alert('Настройки захвата успешно сохранены!');
    } catch (err) {
      alert('Ошибка сохранения настроек: ' + err.message);
    }
  }

  /**
   * Загрузка журнала событий корреляции с ETW.
   */
  async function loadEtwEvents() {
    try {
      const res = await fetch('/api/v1/vision/capture/telemetry-events?limit=25');
      if (!res.ok) return;
      const events = await res.json();

      const tbody = document.getElementById('sc-tbody-etw');
      if (!tbody) return;

      if (!events || events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-secondary py-4">Событий пока не зафиксировано. Включите стрим или сделайте снимок.</td></tr>';
        return;
      }

      tbody.innerHTML = events.map((ev) => {
        const timeStr = new Date(ev.timestamp_utc).toLocaleTimeString();
        const hungBadge = ev.is_app_hung
          ? '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">Зависло</span>'
          : '<span class="badge bg-success-subtle text-success border border-success-subtle">OK</span>';
        const diffBadge = `<span class="font-monospace">${(ev.diff_ratio * 100).toFixed(1)}%</span>`;

        return `
          <tr>
            <td class="font-monospace small">${timeStr}</td>
            <td class="text-truncate" style="max-width: 220px;" title="${ev.target_name}">${ev.target_name}</td>
            <td><span class="badge ${ev.cpu_percent > 80 ? 'bg-danger-subtle text-danger' : 'bg-body-secondary text-body'}">${ev.cpu_percent}%</span></td>
            <td>${ev.memory_mb} MB</td>
            <td>${ev.disk_active_percent}%</td>
            <td>${diffBadge}</td>
            <td>${hungBadge}</td>
            <td class="small text-secondary text-truncate" style="max-width: 320px;" title="${ev.analysis_notes}">${ev.analysis_notes}</td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка загрузки ETW событий:', err);
    }
  }

  /**
   * Загрузка возможностей Windows.Graphics.
   */
  async function loadCapabilities() {
    try {
      const res = await fetch('/api/v1/vision/capture/capabilities');
      if (!res.ok) return;
      const data = await res.json();

      const display = document.getElementById('sc-caps-json-display');
      if (display) {
        display.innerHTML = `<pre class="mb-0 text-body font-monospace" style="white-space: pre-wrap;">${JSON.stringify(data.capabilities, null, 2)}</pre>`;
      }
    } catch (err) {
      console.error('[ScreenCaptureTab] Ошибка загрузки возможностей:', err);
    }
  }

  // Вспомогательные функции
  function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }

  function setElemText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function setSpinner(show) {
    const sp = document.getElementById('sc-stream-spinner');
    if (sp) {
      if (show) sp.classList.remove('d-none');
      else sp.classList.add('d-none');
    }
  }
})();
