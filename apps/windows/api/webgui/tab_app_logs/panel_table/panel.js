/**
 * =============================================================================
 * Process Name: Windows App Logs - Records Table Panel
 * =============================================================================
 * Description:
 *   Модуль рендеринга таблицы записей логов, обновления метрик шапки,
 *   выпадающего списка компонентов и открытия модального окна AIModalDialog.
 *
 * File: panel_table/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_table
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, escapeHtml, showAppLogsToast } from '../common/ui_utils.js';

/**
 * Обновляет счетчики и метрики в шапке вкладки.
 * @param {Object} data - Ответ бэкенда с метаданными.
 */
export function updateHeaderStats(data) {
  const sizeEl = document.getElementById('apl-stat-size');
  if (sizeEl && data.file_info) {
    sizeEl.textContent = data.file_info.size_formatted || '0 KB';
  }

  const loadedEl = document.getElementById('apl-stat-loaded');
  if (loadedEl) {
    loadedEl.textContent = `${data.records.length} / ${data.total_matches}`;
  }

  const errEl = document.getElementById('apl-stat-errors');
  if (errEl && data.stats) {
    errEl.textContent = data.stats.errors_count || 0;
  }

  const warnEl = document.getElementById('apl-stat-warnings');
  if (warnEl && data.stats) {
    warnEl.textContent = data.stats.warnings_count || 0;
  }
}

/**
 * Актуализирует список компонентов в селекте фильтра.
 * @param {Array} components - Список компонентов с количеством записей.
 */
export function updateComponentsDropdown(components) {
  const select = document.getElementById('apl-component-select');
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = '<option value="">Все модули/компоненты</option>';

  components.forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c.name;
    opt.textContent = `${c.name} (${c.count})`;
    if (c.name === currentVal) opt.selected = true;
    select.appendChild(opt);
  });
}

/**
 * Открывает универсальное модальное окно AIModalDialog для анализа записи лога.
 * @param {Object} entry - Запись лога.
 */
export function openItemAiModal(entry) {
  state.selectedEntry = entry;
  const modal = window.AIModalDialog || window.AITableModal;

  let badgeClass = 'badge bg-info';
  const lvl = (entry.level || '').toUpperCase();
  if (lvl === 'CRITICAL' || lvl === 'FATAL' || lvl === 'ERROR') badgeClass = 'badge bg-danger';
  else if (lvl === 'WARNING' || lvl === 'WARN') badgeClass = 'badge bg-warning text-dark';
  else if (lvl === 'DEBUG') badgeClass = 'badge bg-secondary';

  const icon = (lvl === 'CRITICAL' || lvl === 'ERROR') ? '🚨' : ((lvl === 'WARNING' || lvl === 'WARN') ? '⚠️' : '📑');

  if (modal && typeof modal.show === 'function') {
    modal.show({
      title: `[${entry.level}] ${entry.component || 'Log Entry'}`,
      subtitle: `Время: ${entry.timestamp || 'N/A'} | Файл: ${state.currentFile} | Повторов: ${entry.repeat_count || 1}`,
      icon: icon,
      panelId: 'panel-app-logs',
      tableType: 'app_log',
      badges: [
        { text: entry.level || 'INFO', class: badgeClass },
        { text: entry.component || 'System', class: 'badge apl-comp-badge' },
        { text: `${entry.repeat_count || 1}x`, class: 'badge border text-secondary' }
      ],
      metadata: [
        { label: 'Временная метка', value: entry.timestamp || 'N/A' },
        { label: 'Компонент / Модуль', value: entry.component || 'N/A' },
        { label: 'Уровень события', value: entry.level || 'INFO' },
        { label: 'Файл журнала', value: state.currentFile },
        { label: 'Повторений инцидента', value: `${entry.repeat_count || 1}` },
        { label: 'Сообщение лога', value: entry.message || '', fullWidth: true, isCode: true },
      ],
      rawTitle: 'Стек вызовов (Traceback) / Сырая запись',
      rawContent: entry.exc_info ? (typeof entry.exc_info === 'string' ? entry.exc_info : JSON.stringify(entry.exc_info, null, 2)) : entry.raw || entry.message,
      autoRun: false,
      actions: [
        {
          label: 'Копировать запись',
          icon: 'bi-clipboard',
          class: 'btn-outline-info',
          onClick: () => {
            navigator.clipboard.writeText(JSON.stringify(entry, null, 2)).then(() => {
              showAppLogsToast('Скопировано', 'Лог-запись скопирована в буфер обмена', 'success');
            });
          }
        }
      ]
    });
  } else {
    console.log('[AppLogs] Запись лога:', entry);
    alert(`[${entry.level}] ${entry.component}\n\n${entry.message}`);
  }
}

/**
 * Отрисовывает строки таблицы записей журналов.
 * @param {Array} records - Список записей.
 */
export function renderRecordsTable(records) {
  const tbody = document.getElementById('apl-table-body');
  if (!tbody) return;

  if (!records || records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Нет записей, удовлетворяющих условиям фильтрации.</td></tr>';
    return;
  }

  tbody.innerHTML = records.map((entry) => {
    let badgeClass = 'badge-apl-inf';
    const lvl = (entry.level || '').toUpperCase();
    if (lvl === 'CRITICAL' || lvl === 'FATAL') badgeClass = 'badge-apl-crit';
    else if (lvl === 'ERROR') badgeClass = 'badge-apl-err';
    else if (lvl === 'WARNING' || lvl === 'WARN') badgeClass = 'badge-apl-warn';
    else if (lvl === 'DEBUG') badgeClass = 'badge-apl-deb';

    const repeatBadge = entry.repeat_count > 1 ? `<span class="badge apl-card border border-secondary-subtle text-warning ms-1" title="Повторений">${entry.repeat_count}x</span>` : '';
    const hasExc = !!entry.exc_info;
    const excBadge = hasExc ? `<span class="badge bg-danger ms-1" title="Содержит Stacktrace"><i class="bi bi-bug"></i> Trace</span>` : '';

    return `
      <tr class="interactive-log-row" data-id="${entry.id}" style="cursor: pointer;" title="Кликните для запуска AI-анализа">
        <td class="font-monospace small text-muted text-nowrap">${escapeHtml(entry.timestamp || '--:--:--')}</td>
        <td><span class="badge ${badgeClass} small">${escapeHtml(entry.level || 'INFO')}</span>${repeatBadge}</td>
        <td><span class="badge apl-comp-badge font-monospace text-truncate" style="max-width: 120px;" title="${escapeHtml(entry.component)}">${escapeHtml(entry.component)}</span></td>
        <td class="font-monospace small text-break text-body">${escapeHtml(entry.message || '')}${excBadge}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.interactive-log-row').forEach((row) => {
    row.addEventListener('click', (event) => {
      if (event.target.closest('button, a, input, select, .no-modal-trigger')) return;
      const entryId = row.getAttribute('data-id');
      const entry = records.find((x) => String(x.id) === String(entryId));
      if (!entry) return;

      openItemAiModal(entry);
    });
  });
}

/**
 * Загружает записи лога с бэкенда согласно текущим фильтрам и обновляет таблицу.
 * @param {Function} [onViewUpdated=null] - Колбэк после обновления данных.
 */
export async function refreshCurrentView(onViewUpdated = null) {
  const search = document.getElementById('apl-search-input')?.value || '';
  const level = document.getElementById('apl-level-select')?.value || '';
  const component = document.getElementById('apl-component-select')?.value || '';
  const timePreset = document.getElementById('apl-time-preset-select')?.value || '';
  const limit = document.getElementById('apl-limit-select')?.value || '200';

  const fnStat = document.getElementById('apl-stat-filename');
  if (fnStat) fnStat.textContent = state.currentFile;

  try {
    const queryParams = new URLSearchParams({
      file_name: state.currentFile,
      limit: limit,
      search: search,
      level: level,
      component: component,
      time_preset: timePreset,
    });

    const res = await fetch(`/api/v1/app_logs/records?${queryParams.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.records = data.records || [];
    state.stats = data.stats || null;

    updateHeaderStats(data);
    updateComponentsDropdown(data.stats?.components || []);

    if (state.currentMode === 'table') {
      renderRecordsTable(state.records);
    } else if (typeof onViewUpdated === 'function') {
      await onViewUpdated();
    }
  } catch (err) {
    console.error('[AppLogs] Ошибка обновления логов:', err);
    const tbody = document.getElementById('apl-table-body');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Ошибка загрузки: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}
