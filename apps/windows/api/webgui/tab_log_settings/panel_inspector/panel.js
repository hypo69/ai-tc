/**
 * =============================================================================
 * Process Name: Windows Log Settings - Event Inspector Panel
 * =============================================================================
 * Description:
 *   Модуль детального инспектора событий Windows Event Log и telemetry.db:
 *   выборка по Event ID, уровням, процессам, просмотр детальных атрибутов и сырых XML/JSON.
 *
 * File: panel_inspector/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_inspector
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let eventsData = [];
let selectedEvent = null;

/**
 * Загружает события согласно заданным фильтрам инспектора.
 */
export async function fetchInspectorEvents() {
  const channelSelect = document.getElementById('ls-insp-channel-select');
  const levelSelect = document.getElementById('ls-insp-level-select');
  const userInput = document.getElementById('ls-insp-user-input');
  const processInput = document.getElementById('ls-insp-process-input');
  const searchInput = document.getElementById('ls-insp-search-input');

  const channel = channelSelect ? channelSelect.value : 'Security';
  const level = levelSelect ? levelSelect.value : '';
  const user = userInput ? userInput.value.trim() : '';
  const process = processInput ? processInput.value.trim() : '';
  const search = searchInput ? searchInput.value.trim() : '';

  const activeEidBtn = document.querySelector('.ls-quick-eid-btn.active');
  const eventId = activeEidBtn ? parseInt(activeEidBtn.dataset.eid, 10) || 0 : 0;

  const tbody = document.getElementById('ls-events-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Загрузка событий...</td></tr>';
  }

  try {
    const params = new URLSearchParams({
      channel: channel,
      event_id: eventId,
      level: level,
      user: user,
      process: process,
      search: search,
      limit: 100,
    });

    const res = await fetch(`/api/v1/log-settings/events?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    eventsData = data.events || [];
    renderInspectorEvents(eventsData);
  } catch (err) {
    console.warn('[LogSettings] Ошибка чтения событий:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger py-4">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Отрисовывает строки таблицы событий в инспекторе.
 * @param {Array} events - Список событий.
 */
export function renderInspectorEvents(events) {
  const tbody = document.getElementById('ls-events-tbody');
  const countLabel = document.getElementById('ls-events-count-label');
  if (!tbody) return;

  if (countLabel) countLabel.textContent = `Событий: ${events.length}`;

  if (events.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">События по заданным фильтрам не найдены.</td></tr>';
    return;
  }

  tbody.innerHTML = events.map((ev, idx) => {
    const eid = ev.event_id || 0;
    const lvl = ev.level || 'Information';
    const ts = ev.timestamp || '';
    const msg = ev.message || ev.raw_data || '';
    const proc = ev.process_name || ev.provider || '';

    let lvlBadge = 'bg-secondary';
    if (lvl === 'Error' || lvl === 'Critical') lvlBadge = 'bg-danger';
    else if (lvl === 'Warning') lvlBadge = 'bg-warning text-dark';
    else if (lvl === 'Information') lvlBadge = 'bg-info text-dark';

    return `
      <tr class="ls-event-row" data-index="${idx}" style="cursor: pointer;">
        <td class="font-monospace text-secondary text-truncate" style="max-width: 140px;">${escapeHtml(ts)}</td>
        <td>
          <span class="badge bg-dark border border-secondary font-monospace">${eid}</span>
        </td>
        <td>
          <span class="badge ${lvlBadge} small" style="font-size: 0.7rem;">${escapeHtml(lvl)}</span>
        </td>
        <td>
          <div class="text-truncate text-light fw-medium" style="max-width: 320px;" title="${escapeHtml(msg)}">${escapeHtml(msg)}</div>
          ${proc ? `<div class="small text-muted text-truncate font-monospace" style="font-size: 0.72rem;">${escapeHtml(proc)}</div>` : ''}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.ls-event-row').forEach((row) => {
    row.addEventListener('click', () => {
      tbody.querySelectorAll('.ls-event-row').forEach((r) => r.classList.remove('table-active'));
      row.classList.add('table-active');
      const idx = parseInt(row.dataset.index, 10);
      showEventDetail(eventsData[idx]);
    });
  });

  if (events.length > 0) {
    const firstRow = tbody.querySelector('.ls-event-row');
    if (firstRow) firstRow.classList.add('table-active');
    showEventDetail(events[0]);
  }
}

/**
 * Отображает подробные сведения о выбранном событии в боковой карточке.
 * @param {Object} ev - Запись события.
 */
export function showEventDetail(ev) {
  if (!ev) return;
  selectedEvent = ev;

  const emptyEl = document.getElementById('ls-detail-empty');
  const contentEl = document.getElementById('ls-detail-content');
  if (emptyEl) emptyEl.classList.add('d-none');
  if (contentEl) contentEl.classList.remove('d-none');

  document.getElementById('ls-detail-eid-badge').textContent = `ID ${ev.event_id || 0}`;
  document.getElementById('ls-detail-time').textContent = ev.timestamp || '--';
  document.getElementById('ls-detail-user').textContent = ev.subject_user || ev.target_user || (ev.event_data?.SubjectUserName || ev.event_data?.TargetUserName || 'SYSTEM / N/A');

  const procName = ev.process_name || ev.event_data?.NewProcessName || ev.provider || '--';
  const pid = ev.process_id || ev.event_data?.NewProcessId || '';
  document.getElementById('ls-detail-process').textContent = pid ? `${procName} (PID ${pid})` : procName;

  const cmdLine = ev.command_line || ev.event_data?.CommandLine || 'Не зафиксирована или аудит CommandLine выключен';
  document.getElementById('ls-detail-cmdline').textContent = cmdLine;

  const parent = ev.parent_process_name || ev.event_data?.ParentProcessName || (ev.parent_process_id ? `PID ${ev.parent_process_id}` : '--');
  document.getElementById('ls-detail-parent').textContent = parent;

  document.getElementById('ls-detail-msg').textContent = ev.message || '--';
  document.getElementById('ls-detail-raw').textContent = JSON.stringify(ev, null, 2);
}
