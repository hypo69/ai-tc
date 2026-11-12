/**
 * =============================================================================
 * Process Name: Windows App Internals - Activity Log Panel
 * =============================================================================
 * Description:
 *   Модуль панели журнала внутренней активности и операций приложения/системы
 *   во вкладке «Внутренняя кухня» (#tab-app-internals#activity).
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_activity
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-11 23:20:00
 * =============================================================================
 */

import {
  escapeHtml,
  getActiveSubTabId,
  isAppInternalsTabActive,
} from '../common/ui_utils.js?v=20261111_v1';

let isPollerRegistered = false;

/**
 * Локализация ключа через i18next с fallback-значением.
 * @param {string} key - Ключ локализации.
 * @param {string} fallback - Текст по умолчанию.
 * @returns {string} Локализованная строка.
 */
function t(key, fallback) {
  if (typeof window !== 'undefined' && window.i18next?.isInitialized && typeof window.i18next.t === 'function') {
    const translated = window.i18next.t(key);
    if (translated && translated !== key) return translated;
  }
  return fallback !== undefined ? fallback : key;
}

/**
 * Рендерит базовую разметку таблицы журнала активности внутри контейнера панели.
 * @param {HTMLElement} container - DOM-контейнер панели.
 */
function renderActivityLayout(container) {
  if (!container || document.getElementById('internals-activity-tbody')) return;

  container.innerHTML = `
    <div class="p-2">
      <div class="card bg-body border-subtle shadow-sm mb-3">
        <div class="panel-header d-flex justify-content-between align-items-center py-2 px-3 flex-wrap gap-2">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-gear-wide-connected text-primary fs-5"></i>
            <span class="panel-title fw-bold" data-i18n="systemControl.activityTitle">${escapeHtml(t('systemControl.activityTitle', 'Журнал активности'))}</span>
            <span class="ui-badge ui-badge-info" id="internals-activity-counter">0</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <button type="button" class="btn btn-xs btn-outline-secondary btn-table-expand-100" data-target-container="internals-activity-table-container" title="Раскрыть таблицу на 100% высоты без скроллера">100%</button>
            <button type="button" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1" id="btn-internals-refresh-activity">
              <i class="bi bi-arrow-clockwise"></i>
              <span data-i18n="systemControl.btnRefresh">${escapeHtml(t('systemControl.btnRefresh', 'Обновить'))}</span>
            </button>
          </div>
        </div>
        <div class="table-responsive" id="internals-activity-table-container" data-resizable-table="true" style="min-height: 200px; max-height: calc(100vh - 340px); overflow-y: auto;">
          <table class="table table-sm table-hover align-middle mb-0">
            <thead>
              <tr>
                <th data-i18n="systemControl.colTime" style="width: 180px;">${escapeHtml(t('systemControl.colTime', 'Время'))}</th>
                <th data-i18n="systemControl.colAction" style="width: 160px;">${escapeHtml(t('systemControl.colAction', 'Действие'))}</th>
                <th data-i18n="systemControl.colTarget">${escapeHtml(t('systemControl.colTarget', 'Объект'))}</th>
                <th data-i18n="systemControl.colStatus" style="width: 120px;">${escapeHtml(t('systemControl.colStatus', 'Статус'))}</th>
                <th data-i18n="systemControl.colDetails" style="width: 30%;">${escapeHtml(t('systemControl.colDetails', 'Подробности'))}</th>
              </tr>
            </thead>
            <tbody id="internals-activity-tbody">
              <tr><td class="text-center text-muted p-3" colspan="5" data-i18n="systemControl.loadingActivity">${escapeHtml(t('systemControl.loadingActivity', 'Загрузка журнала активности...'))}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="sys-table-resizer" id="internals-activity-table-resizer" data-container-id="internals-activity-table-container" title="Потяните для изменения высоты таблицы (двойной клик — сброс)">
          <div class="sys-table-resizer-grip"></div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Загрузка истории активности операций администрирования из API.
 * @param {boolean} [force=false] - Принудительное обновление без проверки активной суб-панели.
 * @returns {Promise<void>}
 */
export async function loadAppInternalsActivityLogs(force = false) {
  if (!force && (!isAppInternalsTabActive() || getActiveSubTabId() !== 'activity')) {
    return;
  }

  const tbody = document.getElementById('internals-activity-tbody');
  const counter = document.getElementById('internals-activity-counter');
  if (!tbody) return;

  try {
    const res = await fetch('/api/v1/system_logs/activity');
    if (!res.ok) return;
    const data = await res.json();
    const logs = data.logs || [];

    if (counter) {
      counter.textContent = String(logs.length);
    }

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted p-3">${escapeHtml(t('systemControl.emptyActivity', 'Журнал активности пуст.'))}</td></tr>`;
    } else {
      tbody.innerHTML = logs.map((l) => {
        const isOk = l.status === 'SUCCESS' || l.status === 'OK';
        const statusBadge = isOk ? 'ui-badge-success' : 'ui-badge-warning';
        return `
          <tr>
            <td class="font-monospace small text-muted">${escapeHtml(l.timestamp)}</td>
            <td><span class="ui-badge ui-badge-neutral font-monospace">${escapeHtml(l.action)}</span></td>
            <td class="text-body">${escapeHtml(l.target)}</td>
            <td><span class="ui-badge ${statusBadge}">${escapeHtml(l.status)}</span></td>
            <td class="small text-muted text-truncate" style="max-width: 280px;" title="${escapeHtml(l.details)}">${escapeHtml(l.details)}</td>
          </tr>
        `;
      }).join('');
    }

    if (typeof window.autoAdjustTableHeight === 'function') {
      window.autoAdjustTableHeight('internals-activity-table-container', logs.length);
    }
  } catch (err) {
    console.warn('[AppInternals:Activity] Ошибка загрузки журнала активности:', err);
  }
}

/**
 * Инициализация панели журнала активности во вкладке «Внутренняя кухня».
 * @returns {Promise<void>}
 */
export async function initAppInternalsActivityPanel() {
  const container = document.getElementById('internals-activity-container');
  if (!container) return;

  renderActivityLayout(container);

  const btnRefresh = document.getElementById('btn-internals-refresh-activity');
  if (btnRefresh && !btnRefresh._bound) {
    btnRefresh._bound = true;
    btnRefresh.addEventListener('click', () => loadAppInternalsActivityLogs(true));
  }

  if (typeof window.setupTableResizer === 'function') {
    window.setupTableResizer({
      containerId: 'internals-activity-table-container',
      resizerId: 'internals-activity-table-resizer',
    });
  }

  if (!isPollerRegistered && typeof window.registerTabPoller === 'function') {
    isPollerRegistered = true;
    window.registerTabPoller(
      'tab-app-internals',
      async () => {
        if (getActiveSubTabId() === 'activity') {
          await loadAppInternalsActivityLogs(false);
        }
      },
      5000,
      { pollerId: 'app-internals-activity', immediate: false }
    );
  }

  await loadAppInternalsActivityLogs(true);
}
