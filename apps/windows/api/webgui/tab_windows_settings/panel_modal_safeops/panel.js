/**
 * =============================================================================
 * Process Name: Windows Settings - SafeOps Modal Panel
 * =============================================================================
 * Description:
 *   Модуль модального окна предварительного просмотра SafeOps (Dry-Run) и безопасного
 *   применения изменений системных параметров Windows с созданием контрольных точек отката.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings/panel_modal_safeops
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, API_BASE, fetchJson, getRiskBadgeHtml } from '../common/ui_utils.js';
import { loadQuickSettings } from '../panel_quick_settings/panel.js';

/**
 * Создание элемента ввода в зависимости от типа параметра.
 * @param {object} setting - Описание параметра
 * @param {any} curVal - Текущее значение
 * @returns {string} HTML контрола ввода
 */
export function buildInputControl(setting, curVal) {
  if (setting.value_type === 'bool') {
    return `
      <div class="form-check form-switch fs-5">
        <input class="form-check-input" type="checkbox" id="winset-modal-input-val" ${curVal ? 'checked' : ''}>
        <label class="form-check-label fs-6 text-muted" for="winset-modal-input-val">Включить этот параметр</label>
      </div>
    `;
  }
  if (setting.value_type === 'int' || setting.value_type === 'duration_ms') {
    const min = setting.min_val !== null ? setting.min_val : 0;
    const max = setting.max_val !== null ? setting.max_val : 100000;
    return `
      <div class="input-group">
        <input type="number" class="form-control" id="winset-modal-input-val" min="${min}" max="${max}" value="${curVal}">
        <span class="input-group-text">${setting.unit || ''}</span>
      </div>
    `;
  }
  return `
    <input type="text" class="form-control" id="winset-modal-input-val" value="${curVal}">
  `;
}

/**
 * Открытие модального окна предпросмотра / изменения параметра.
 * @param {object} setting - Описание параметра
 * @param {boolean} [isEditMode=false] - Флаг режима редактирования
 */
export async function openPreviewModal(setting, isEditMode = false) {
  state.pendingSetting = setting;
  const modalTitle = document.getElementById('winset-modal-title');
  const modalBody = document.getElementById('winset-modal-body');

  if (modalTitle) {
    modalTitle.innerHTML = `
      <i class="bi bi-sliders text-primary"></i>
      <span>${isEditMode ? 'Изменение параметра' : 'Предпросмотр SafeOps (Dry-Run)'}</span>
    `;
  }

  // Получаем текущее живое значение
  let curVal = state.liveValuesCache[setting.id] || setting.default_value;
  try {
    const live = await fetchJson(`${API_BASE}/settings/${setting.id}?read_live=true`);
    if (live && live.live_state) {
      curVal = live.live_state.value !== undefined ? live.live_state.value : live.live_state.current_value;
      state.liveValuesCache[setting.id] = curVal;
    }
  } catch (ex) {
    console.debug('Не удалось обновить значение для модалки', ex);
  }

  const inputControlHtml = buildInputControl(setting, curVal);

  if (modalBody) {
    modalBody.innerHTML = `
      <div class="d-flex flex-column gap-3">
        <div>
          <h6 class="fw-bold mb-1">${setting.name_ru || setting.name}</h6>
          <div class="small text-muted font-monospace">${setting.id}</div>
          <div class="small text-secondary mt-1">${setting.description_ru || setting.description}</div>
        </div>

        <div class="row g-2 p-2 bg-body-tertiary rounded border">
          <div class="col-6">
            <span class="small text-muted d-block">Уровень риска:</span>
            ${getRiskBadgeHtml(setting.risk)}
          </div>
          <div class="col-6">
            <span class="small text-muted d-block">Область:</span>
            <span class="badge bg-secondary-subtle text-secondary border">${setting.scope}</span>
          </div>
          <div class="col-6">
            <span class="small text-muted d-block">Права администратора:</span>
            <span class="badge ${setting.requires_elevation ? 'bg-danger' : 'bg-success-subtle text-success border'}">
              ${setting.requires_elevation ? 'Требуются (UAC)' : 'Не требуются'}
            </span>
          </div>
          <div class="col-6">
            <span class="small text-muted d-block">Перезапуск оболочки:</span>
            <span class="badge ${setting.requires_restart ? 'bg-warning text-dark' : 'bg-success-subtle text-success border'}">
              ${setting.requires_restart ? 'Требуется Explorer' : 'Мгновенно'}
            </span>
          </div>
        </div>

        <div>
          <label class="form-label fw-semibold">Новое целевое значение:</label>
          ${inputControlHtml}
        </div>

        <div id="winset-preview-feedback" class="small"></div>
      </div>
    `;
  }

  const modalEl = document.getElementById('winset-modal-preview');
  if (modalEl && window.bootstrap) {
    const modal = new window.bootstrap.Modal(modalEl);
    modal.show();
  }
}

/**
 * Подтверждение применения значения из модального окна.
 */
export async function confirmModalApply() {
  if (!state.pendingSetting) return;

  const inputEl = document.getElementById('winset-modal-input-val');
  if (!inputEl) return;

  let newVal = inputEl.type === 'checkbox' ? inputEl.checked : inputEl.value;
  if (state.pendingSetting.value_type === 'int' || state.pendingSetting.value_type === 'duration_ms') {
    newVal = parseInt(newVal, 10);
  }

  const feedback = document.getElementById('winset-preview-feedback');
  if (feedback) {
    feedback.innerHTML = `
      <div class="alert alert-info py-2 d-flex align-items-center gap-2 mb-0">
        <div class="spinner-border spinner-border-sm" role="status"></div>
        <span>Применение параметра и создание контрольной точки...</span>
      </div>
    `;
  }

  try {
    const applyRes = await fetchJson(`${API_BASE}/settings/${state.pendingSetting.id}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: newVal, custom_comment: 'User Settings Tab Change' }),
    });

    if (applyRes && applyRes.success) {
      state.liveValuesCache[state.pendingSetting.id] = newVal;
      const badge = document.getElementById(`live-val-${state.pendingSetting.id}`);
      if (badge) badge.textContent = String(newVal);

      const modalEl = document.getElementById('winset-modal-preview');
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      await loadQuickSettings();
    } else {
      if (feedback) {
        feedback.innerHTML = `
          <div class="alert alert-danger py-2 mb-0">
            <i class="bi bi-x-circle me-1"></i> Ошибка применения: ${applyRes?.message || 'Неизвестная ошибка'}
          </div>
        `;
      }
    }
  } catch (err) {
    if (feedback) {
      feedback.innerHTML = `
        <div class="alert alert-danger py-2 mb-0">
          <i class="bi bi-x-circle me-1"></i> Ошибка соединения: ${err.message}
        </div>
      `;
    }
  }
}
