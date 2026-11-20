/**
 * =============================================================================
 * Process Name: System Inspector - Intervals & Autolog Config Panel
 * =============================================================================
 * Description:
 *   Модуль настройки интервалов обновления веб-интерфейса и фонового логирования
 *   сенсоров в config.json (AutoLog intervals editor).
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_intervals
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

const INTERVAL_PRESETS = [
  { value: '1 second', label: '1 сек' },
  { value: '2 seconds', label: '2 сек' },
  { value: '3 seconds', label: '3 сек' },
  { value: '5 seconds', label: '5 сек' },
  { value: '10 seconds', label: '10 сек' },
  { value: '15 seconds', label: '15 сек' },
  { value: '30 seconds', label: '30 сек' },
  { value: '1 minute', label: '1 мин' },
  { value: '2 minutes', label: '2 мин' },
  { value: '5 minutes', label: '5 мин' },
  { value: '10 minutes', label: '10 мин' },
  { value: '15 minutes', label: '15 мин' },
  { value: '30 minutes', label: '30 мин' },
  { value: '1 hour', label: '1 час' },
];

const CORE_RESOURCE_LOGGERS = [
  'system_inspector',
  'hardware_monitor',
  'hardware_inspector',
  'network_monitor',
  'network_terminal',
  'storage_manager',
  'process_leaks',
  'processes_load_inspector'
];

let _sysIntervalsConfigData = null;

/**
 * Инициализация панели интервалов.
 */
export function initIntervalsPanel() {
  const btnSave = document.getElementById('btn-modal-intervals-save');
  if (btnSave) {
    btnSave.onclick = () => saveSysIntervalsConfig();
  }
  const btnRefresh = document.getElementById('btn-modal-intervals-refresh');
  if (btnRefresh) {
    btnRefresh.onclick = () => loadSysIntervalsConfig(true);
  }
  window.openSysIntervalsModal = openSysIntervalsModal;
}

/**
 * Открытие модального окна настройки интервалов.
 */
export function openSysIntervalsModal(currentUiSeconds = 5) {
  const modalEl = document.getElementById('sysIntervalsModal');
  if (!modalEl) return;

  const selUi = document.getElementById('modal-ui-refresh-select');
  if (selUi) selUi.value = String(currentUiSeconds);
  const uiBadge = document.getElementById('modal-ui-refresh-badge');
  if (uiBadge) uiBadge.textContent = `${currentUiSeconds} сек`;

  loadSysIntervalsConfig(false);

  if (window.bootstrap && window.bootstrap.Modal) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}

/**
 * Загрузка конфигурации интервалов из API.
 */
export async function loadSysIntervalsConfig(notify = false) {
  try {
    let res = await fetch('/api/autolog/config');
    if (!res.ok) res = await fetch('/sysautologging/config');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    _sysIntervalsConfigData = await res.json();
    renderSysIntervalsForm(_sysIntervalsConfigData);
  } catch (e) {
    console.warn('[IntervalsPanel] Ошибка загрузки интервалов:', e);
  }
}

/**
 * Сохранение конфигурации интервалов.
 */
export async function saveSysIntervalsConfig() {
  const btnSave = document.getElementById('btn-modal-intervals-save');
  if (btnSave) btnSave.disabled = true;

  try {
    const loggers = {};
    document.querySelectorAll('.sys-int-select').forEach(sel => {
      const logger = sel.getAttribute('data-logger');
      const interval = sel.value;
      const chk = document.querySelector(`.sys-int-enable[data-logger="${logger}"]`);
      const enabled = chk ? chk.checked : true;
      loggers[logger] = { interval, enabled };
    });

    const globalEnable = document.getElementById('modal-intervals-global-enable');
    const defSelect = document.getElementById('modal-intervals-default-select');

    const payload = {
      enable_autolog: globalEnable ? globalEnable.checked : true,
      default_interval: defSelect ? defSelect.value : '1 minute',
      loggers
    };

    const res = await fetch('/api/autolog/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const modalEl = document.getElementById('sysIntervalsModal');
    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
  } catch (e) {
    console.warn('[IntervalsPanel] Ошибка сохранения:', e);
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
}

function buildIntervalSelectHtml(loggerName, currentInterval) {
  const val = currentInterval || '1 minute';
  let html = `<select class="form-select form-select-sm sys-int-select" data-logger="${loggerName}" style="min-width: 120px;">`;
  INTERVAL_PRESETS.forEach(p => {
    const sel = p.value === val ? 'selected' : '';
    html += `<option value="${p.value}" ${sel}>${p.label} (${p.value})</option>`;
  });
  html += `</select>`;
  return html;
}

function renderSysIntervalsForm(data) {
  if (!data) return;
  const coreContainer = document.getElementById('modal-core-loggers-container');
  if (!coreContainer) return;

  const loggers = data.loggers || {};
  let coreHtml = '';

  CORE_RESOURCE_LOGGERS.forEach(name => {
    const cfg = loggers[name] || { interval: '5 seconds', enabled: true };
    const isEnabled = cfg.enabled !== false;
    const intervalVal = cfg.interval || '5 seconds';

    coreHtml += `
      <div class="p-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2 mb-1.5" style="background: var(--bg-color); border: 1px solid var(--border-color);">
        <div class="fw-bold small">${escapeHtml(name)}</div>
        <div class="d-flex align-items-center gap-2">
          <input class="form-check-input sys-int-enable" type="checkbox" data-logger="${name}" ${isEnabled ? 'checked' : ''}>
          ${buildIntervalSelectHtml(name, intervalVal)}
        </div>
      </div>
    `;
  });
  coreContainer.innerHTML = coreHtml;
}
