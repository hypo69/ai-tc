/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: History & Rollback Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер журнала изменений окружения пользователя (SafeOps Audit).
 *   Обеспечивает просмотр истории примененных параметров из telemetry.db
 *   и гранулярный или мгновенный откат (Rollback) параметров таскбара и окон.
 *
 * File: panel_history.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 18:05:00
 * =============================================================================
 */

let _historyCache = [];

/**
 * Вызов всплывающего уведомления Toast.
 * @param {string} msg Текст сообщения.
 * @param {'info'|'success'|'warning'|'danger'} type Тип уведомления.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[UEHistory] [${type}] ${msg}`);
  }
}

/**
 * Экранирование HTML.
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
 * Загрузка журнала действий из telemetry.db.
 * @param {Function} [onUpdated] Коллбек после отката.
 */
export async function loadHistory(onUpdated) {
  const tbody = document.getElementById('ue-tbody-history-list');
  try {
    const res = await fetch('/api/v1/taskbar/history?limit=30');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _historyCache = await res.json();
    renderHistoryTable(onUpdated);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-danger p-3 text-center">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Отрисовка таблицы истории SafeOps.
 * @param {Function} [onUpdated] Коллбек.
 */
export function renderHistoryTable(onUpdated) {
  const tbody = document.getElementById('ue-tbody-history-list');
  const countBadge = document.getElementById('ue-badge-history-count');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${_historyCache.length} записей`;

  if (!_historyCache || _historyCache.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted p-4 text-center">История изменений пуста</td></tr>';
    return;
  }

  tbody.innerHTML = _historyCache.map((h) => {
    const isSuccess = h.success !== false;
    const isRolledBack = Boolean(h.is_rolled_back);

    let statusBadge = isSuccess
      ? '<span class="badge bg-success-subtle text-success border border-success-subtle">Успешно</span>'
      : '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">Ошибка</span>';

    if (isRolledBack) {
      statusBadge += ' <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle ms-1">Откачено</span>';
    }

    const rollbackBtn = (!isRolledBack && h.rollback_payload)
      ? `<button class="btn btn-sm btn-outline-warning ue-btn-rollback-item" data-id="${h.id}" title="Откатить это изменение">
           <i class="bi bi-arrow-counterclockwise me-1"></i>Откат
         </button>`
      : '<span class="text-muted small">—</span>';

    return `
      <tr>
        <td><code>#${h.id}</code></td>
        <td><small class="text-muted">${escapeHtml(h.timestamp || '—')}</small></td>
        <td><strong class="user-select-all">${escapeHtml(h.command_id || h.action_type || '—')}</strong></td>
        <td>
          <span class="text-truncate d-inline-block" style="max-width: 250px;" title="${escapeHtml(JSON.stringify(h.payload || {}))}">
            <code>${escapeHtml(JSON.stringify(h.payload || {}))}</code>
          </span>
        </td>
        <td>${statusBadge}</td>
        <td class="text-end">${rollbackBtn}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.ue-btn-rollback-item').forEach((btn) => {
    const id = parseInt(btn.getAttribute('data-id'), 10);
    btn.addEventListener('click', () => rollbackAction(id, onUpdated));
  });
}

/**
 * Откат конкретного действия по ID.
 * @param {number} historyId ID записи.
 * @param {Function} [onUpdated] Коллбек.
 */
export async function rollbackAction(historyId, onUpdated) {
  try {
    const res = await fetch(`/api/v1/taskbar/history/${historyId}/rollback`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Действие #${historyId} успешно откачено`, 'warning');
    await loadHistory(onUpdated);
    if (typeof onUpdated === 'function') await onUpdated();
  } catch (err) {
    showToast(`Ошибка отката #${historyId}: ${err.message}`, 'danger');
  }
}

/**
 * Откат последнего действия.
 * @param {Function} [onUpdated] Коллбек.
 */
export async function rollbackLast(onUpdated) {
  try {
    const res = await fetch('/api/v1/taskbar/history/rollback-last', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Последнее действие успешно откачено', 'warning');
    await loadHistory(onUpdated);
    if (typeof onUpdated === 'function') await onUpdated();
  } catch (err) {
    showToast(`Ошибка отката: ${err.message}`, 'danger');
  }
}

/**
 * Привязка событий панели истории.
 * @param {Function} [onUpdated] Коллбек.
 */
export function bindHistoryEvents(onUpdated) {
  document.getElementById('ue-btn-refresh-history')?.addEventListener('click', () => loadHistory(onUpdated));
  document.getElementById('ue-btn-rollback-last')?.addEventListener('click', () => rollbackLast(onUpdated));
}
