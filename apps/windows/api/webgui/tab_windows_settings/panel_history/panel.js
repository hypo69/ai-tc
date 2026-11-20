/**
 * =============================================================================
 * Process Name: Windows Settings - Audit History & Rollback Panel
 * =============================================================================
 * Description:
 *   Модуль журнала аудита и отката настроек Windows: загрузка истории
 *   изменений параметров из базы данных телеметрии, мгновенный откат
 *   произвольного изменения или последнего примененного параметра.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_settings/panel_history
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { API_BASE, fetchJson } from '../common/ui_utils.js';
import { loadQuickSettings } from '../panel_quick_settings/panel.js';
import { loadCatalogSettings } from '../panel_catalog/panel.js';

/**
 * Загрузка истории изменений SafeOps из telemetry.db.
 * @returns {Promise<void>}
 */
export async function loadHistory() {
  const histBody = document.getElementById('winset-history-body');
  if (!histBody) return;

  histBody.innerHTML = `
    <tr>
      <td colspan="7" class="text-center py-3 text-muted">
        <div class="spinner-border spinner-border-sm me-2" role="status"></div> Загрузка журнала изменений...
      </td>
    </tr>
  `;

  try {
    const history = await fetchJson(`${API_BASE}/history?limit=100`);
    if (!history || history.length === 0) {
      histBody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-4 text-muted">
            История изменений пока пуста. Примените любой параметр для начала аудита.
          </td>
        </tr>
      `;
      return;
    }

    histBody.innerHTML = history.map((item) => `
      <tr>
        <td class="small font-monospace text-muted">${item.applied_at || item.created_at || '—'}</td>
        <td>
          <div class="fw-semibold">${item.setting_name || item.name_ru || item.setting_id}</div>
          <div class="small text-muted font-monospace" style="font-size: 0.72rem;">${item.setting_id}</div>
        </td>
        <td class="font-monospace small text-danger">${String(item.old_value)}</td>
        <td class="font-monospace small text-success">${String(item.new_value)}</td>
        <td>
          <span class="badge ${item.status === 'SUCCESS' ? 'bg-success-subtle text-success border' : 'bg-danger-subtle text-danger border'}">
            ${item.status || 'OK'}
          </span>
        </td>
        <td class="small text-muted">${item.restore_point_id || '—'}</td>
        <td class="text-end">
          <button class="btn btn-xs btn-outline-danger py-0 px-2" onclick="window.winsetRollbackItem('${item.change_id}')" ${item.rolled_back ? 'disabled' : ''}>
            ${item.rolled_back ? 'Откачен' : 'Откатить'}
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    histBody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-4 text-danger">
          Ошибка чтения журнала аудита: ${err.message}
        </td>
      </tr>
    `;
  }
}

/**
 * Откат выбранного изменения из истории.
 * @param {string} changeId - Идентификатор записи изменения
 */
export async function winsetRollbackItem(changeId) {
  if (!confirm(`Откатить изменение [${changeId}]?`)) return;
  try {
    const res = await fetchJson(`${API_BASE}/rollback/${changeId}`, { method: 'POST' });
    if (res && res.rolled_back) {
      alert('Параметр успешно возвращен к предыдущему значению!');
      await loadHistory();
      await loadQuickSettings();
    } else {
      alert(`Ошибка отката: ${res?.message}`);
    }
  } catch (err) {
    alert(`Сбой вызова API: ${err.message}`);
  }
}

/**
 * Быстрый откат последнего системного изменения.
 * @returns {Promise<void>}
 */
export async function rollbackLastSetting() {
  if (!confirm('Вы действительно хотите откатить последнее системное изменение к исходному значению?')) {
    return;
  }
  try {
    const res = await fetchJson(`${API_BASE}/rollback-last`, { method: 'POST' });
    if (res && res.rolled_back) {
      alert(`Успешно откачен параметр: ${res.setting_id}`);
      await loadQuickSettings();
      await loadCatalogSettings();
    } else {
      alert(`Не удалось выполнить откат: ${res?.message || 'Нет изменений для отката'}`);
    }
  } catch (err) {
    alert(`Ошибка связи при откате: ${err.message}`);
  }
}

window.winsetRollbackItem = winsetRollbackItem;
