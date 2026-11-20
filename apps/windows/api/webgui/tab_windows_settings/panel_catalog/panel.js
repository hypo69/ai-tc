/**
 * =============================================================================
 * Process Name: Windows Settings - Catalog Panel
 * =============================================================================
 * Description:
 *   Модуль каталога системных настроек Windows: загрузка каталога параметров,
 *   поиск, фильтрация по категориям, рискам и бэкендам (Win32 / Registry / DWM),
 *   чтение живых значений и запуск SafeOps модального окна.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings/panel_catalog
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, API_BASE, fetchJson, getRiskBadgeHtml } from '../common/ui_utils.js';
import { openPreviewModal } from '../panel_modal_safeops/panel.js';

/**
 * Загрузка каталога всех параметров из API.
 * @returns {Promise<void>}
 */
export async function loadCatalogSettings() {
  const tableBody = document.getElementById('winset-table-body');
  if (tableBody) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-4 text-muted">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>
          Загрузка каталога параметров...
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetchJson(`${API_BASE}/catalog?limit=500`);
    if (res && res.settings) {
      state.allSettings = res.settings;
      const totalBadge = document.getElementById('winset-total-badge');
      if (totalBadge) totalBadge.textContent = `${state.allSettings.length} параметров`;
      renderFilteredSettings();
    }
  } catch (err) {
    console.error('[WindowsSettingsTab] Ошибка загрузки каталога:', err);
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle me-2"></i> Ошибка загрузки каталога параметров: ${err.message}
          </td>
        </tr>
      `;
    }
  }
}

/**
 * Отрисовка отфильтрованного списка параметров.
 */
export function renderFilteredSettings() {
  const tableBody = document.getElementById('winset-table-body');
  if (!tableBody) return;

  const search = (document.getElementById('winset-search-input')?.value || '').toLowerCase().trim();
  const riskFilter = document.getElementById('winset-filter-risk')?.value || '';
  const backendFilter = document.getElementById('winset-filter-backend')?.value || '';

  const filtered = state.allSettings.filter((item) => {
    // Фильтр по категории
    if (state.currentCategory !== 'all' && state.currentCategory !== 'history') {
      if (item.category !== state.currentCategory) return false;
    }
    // Фильтр по риску
    if (riskFilter && item.risk !== riskFilter) return false;
    // Фильтр по бэкенду
    if (backendFilter) {
      const b = (item.read_spec?.backend || item.write_spec?.backend || '').toLowerCase();
      if (!b.includes(backendFilter.toLowerCase())) return false;
    }
    // Поисковый запрос
    if (search) {
      const hay = `${item.id} ${item.name} ${item.name_ru} ${item.description_ru} ${item.subcategory}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });

  const countLabel = document.getElementById('winset-count-label');
  if (countLabel) countLabel.textContent = `Показано: ${filtered.length}`;

  if (filtered.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-4 text-muted">
          Параметры не найдены по текущим критериям фильтрации.
        </td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = filtered.map((item) => buildSettingRowHtml(item)).join('');

  // Обработчики действий в строках
  tableBody.querySelectorAll('button[data-action]').forEach((btn) => {
    btn.onclick = handleRowAction;
  });
}

/**
 * Формирование HTML-строки параметра.
 * @param {object} item - Описание параметра
 * @returns {string} HTML строки таблицы
 */
export function buildSettingRowHtml(item) {
  const riskBadge = getRiskBadgeHtml(item.risk);
  const backendName = item.read_spec?.backend || item.write_spec?.backend || 'API';
  const liveVal = state.liveValuesCache[item.id] !== undefined ? state.liveValuesCache[item.id] : '—';

  return `
    <tr data-setting-id="${item.id}">
      <td class="text-muted small">${item.index}</td>
      <td>
        <div class="fw-semibold text-body">${item.name_ru || item.name}</div>
        <div class="small text-muted font-monospace" style="font-size: 0.75rem;">${item.id}</div>
        <div class="small text-secondary mt-1">${item.description_ru || item.description}</div>
      </td>
      <td>
        <span class="badge bg-secondary-subtle text-secondary border font-monospace small">${backendName}</span>
        <div class="small text-muted mt-1"><i class="bi bi-person"></i> ${item.scope}</div>
      </td>
      <td>${riskBadge}</td>
      <td>
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-body-secondary text-body border px-2 py-1 live-val-badge font-monospace" id="live-val-${item.id}">
            ${liveVal}
          </span>
          <button class="btn btn-xs btn-outline-secondary py-0 px-1" data-action="read" data-id="${item.id}" title="Прочитать текущее значение">
            <i class="bi bi-arrow-clockwise"></i>
          </button>
        </div>
      </td>
      <td class="text-end">
        <div class="d-flex align-items-center justify-content-end gap-1">
          <button class="btn btn-sm btn-outline-info d-flex align-items-center gap-1" data-action="preview" data-id="${item.id}">
            <i class="bi bi-eye"></i> Предпросмотр
          </button>
          <button class="btn btn-sm btn-primary d-flex align-items-center gap-1" data-action="edit" data-id="${item.id}">
            <i class="bi bi-pencil"></i> Изменить
          </button>
        </div>
      </td>
    </tr>
  `;
}

/**
 * Обработка действий в строке таблицы (чтение, предпросмотр, редактирование).
 * @param {Event} e
 */
export async function handleRowAction(e) {
  const btn = e.currentTarget;
  const action = btn.getAttribute('data-action');
  const id = btn.getAttribute('data-id');
  const setting = state.allSettings.find((s) => s.id === id);
  if (!setting) return;

  if (action === 'read') {
    btn.disabled = true;
    try {
      const res = await fetchJson(`${API_BASE}/settings/${id}?read_live=true`);
      if (res && res.live_state) {
        const liveVal = res.live_state.value !== undefined ? res.live_state.value : res.live_state.current_value;
        state.liveValuesCache[id] = liveVal;
        const badge = document.getElementById(`live-val-${id}`);
        if (badge) badge.textContent = String(liveVal);
      }
    } finally {
      btn.disabled = false;
    }
  } else if (action === 'preview' || action === 'edit') {
    openPreviewModal(setting, action === 'edit');
  }
}
