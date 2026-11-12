/**
 * Модуль панели сессий питания, фильтрации и детального анализа.
 * Файл: apps/windows/api/webgui/tab_power_lifecycle/panel_sessions/panel.js
 * Updated: 2026-11-01 17:49:00
 */

import { escapeHtml } from '../common/ui_utils.js';

let allSessions = [];

export function getAllSessions() {
  return allSessions;
}

export function setAllSessions(sessions) {
  allSessions = sessions || [];
}

/**
 * Фильтрует и отрисовывает таблицу сессий питания.
 */
export function filterAndRenderSessions() {
  const tbody = document.getElementById('pwr-sessions-tbody');
  const counter = document.getElementById('pwr-sessions-counter');
  if (!tbody) return;

  const searchVal = (document.getElementById('pwr-sessions-search')?.value || '').toLowerCase().trim();
  const typeFilter = document.getElementById('pwr-filter-type')?.value || '';
  const unexpOnly = document.getElementById('pwr-filter-unexpected-only')?.checked || false;

  const filtered = allSessions.filter(s => {
    if (unexpOnly && !s.unexpected_shutdown) return false;
    if (typeFilter) {
      if (typeFilter === 'Active' && s.shutdown_type !== 'Active') return false;
      if (typeFilter === 'Restart' && s.shutdown_type !== 'Restart') return false;
      if (typeFilter === 'Shutdown' && s.shutdown_type !== 'Shutdown' && s.shutdown_type !== 'PowerOff') return false;
      if (typeFilter === 'Unexpected' && !s.unexpected_shutdown) return false;
      if (typeFilter === 'BSOD' && s.shutdown_type !== 'BSOD' && !s.bugcheck) return false;
    }

    if (searchVal) {
      const init = (s.initiator || '').toLowerCase();
      const proc = (s.process || '').toLowerCase();
      const reason = (s.reason || '').toLowerCase();
      const code = (s.reason_code || '').toLowerCase();
      const sId = (s.session_id || '').toLowerCase();
      if (!init.includes(searchVal) && !proc.includes(searchVal) && !reason.includes(searchVal) && !code.includes(searchVal) && !sId.includes(searchVal)) {
        return false;
      }
    }
    return true;
  });

  if (counter) counter.textContent = `Найдено: ${filtered.length}`;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center py-4 text-muted">
          Сессии питания, удовлетворяющие критериям фильтрации, не найдены.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(s => {
    let statusBadge = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">Неизвестно</span>';
    if (s.shutdown_type === 'Active') {
      statusBadge = '<span class="badge bg-success-subtle text-success border border-success-subtle">🟢 Активная</span>';
    } else if (s.shutdown_type === 'Restart') {
      statusBadge = '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">↻ Перезагрузка</span>';
    } else if (s.shutdown_type === 'Shutdown' || s.shutdown_type === 'PowerOff') {
      statusBadge = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">⏻ Выключение</span>';
    } else if (s.shutdown_type === 'BSOD' || s.bugcheck) {
      statusBadge = `<span class="badge bg-danger text-white">🚨 BSOD ${escapeHtml(s.bugcheck || '')}</span>`;
    } else if (s.unexpected_shutdown) {
      statusBadge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">⚠️ Сбой / 41</span>';
    }

    let initiatorHtml = '<span class="text-muted">--</span>';
    if (s.initiator || s.process) {
      const initName = s.initiator ? `<span class="fw-semibold text-primary">${escapeHtml(s.initiator)}</span>` : '';
      const procName = s.process ? `<span class="badge pwr-proc-badge font-monospace ms-1 text-truncate" style="max-width: 260px;" title="${escapeHtml(s.process)}">${escapeHtml(s.process)}</span>` : '';
      initiatorHtml = `<div class="d-flex align-items-center flex-wrap">${initName} ${procName}</div>`;
      if (s.initiator_chain && s.initiator_chain.length > 1) {
        initiatorHtml += `<div class="small text-muted font-monospace mt-0.5 text-truncate" style="font-size: 0.72rem; max-width: 260px;" title="${escapeHtml(s.initiator_chain.join(' → '))}">🔗 ${escapeHtml(s.initiator_chain.join(' → '))}</div>`;
      }
    }

    let reasonHtml = '<span class="text-muted">--</span>';
    if (s.reason || s.reason_code) {
      const codeBadge = s.reason_code ? `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle font-monospace me-1">${escapeHtml(s.reason_code)}</span>` : '';
      reasonHtml = `<div>${codeBadge}<span>${escapeHtml(s.reason || '')}</span></div>`;
      if (s.comment) {
        reasonHtml += `<div class="small text-muted font-italic mt-0.5">💬 ${escapeHtml(s.comment)}</div>`;
      }
    }

    return `
      <tr>
        <td class="font-monospace text-primary small fw-bold text-nowrap">${escapeHtml(s.session_id)}</td>
        <td class="font-monospace small text-nowrap">${escapeHtml(s.boot_time)}</td>
        <td class="font-monospace small text-muted text-nowrap">${s.shutdown_time ? escapeHtml(s.shutdown_time) : '<span class="text-success fw-bold">Сейчас</span>'}</td>
        <td class="font-monospace fw-semibold text-nowrap">${escapeHtml(s.uptime_human || '--')}</td>
        <td class="text-nowrap">${statusBadge}</td>
        <td style="min-width: 220px; max-width: 280px;">${initiatorHtml}</td>
        <td style="min-width: 320px;">${reasonHtml}</td>
        <td class="text-center">
          <button class="btn btn-xs btn-outline-info p-1 px-2 pwr-detail-btn" data-session-id="${escapeHtml(s.session_id)}" title="Посмотреть подробную хронологию">
            <i class="bi bi-eye"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.pwr-detail-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const sId = btn.dataset.sessionId;
      showSessionDetailModal(sId);
    });
  });
}

/**
 * Открывает модальное окно деталей конкретной сессии питания.
 * @param {string} sessionId
 */
export function showSessionDetailModal(sessionId) {
  const session = allSessions.find(s => s.session_id === sessionId);
  if (!session) return;

  const modalTitle = document.getElementById('pwr-modal-title');
  const modalBody = document.getElementById('pwr-modal-body');
  if (modalTitle) modalTitle.textContent = `Сессия питания: ${session.session_id}`;

  if (modalBody) {
    let eventsListHtml = '<div class="text-muted small">Нет связанных событий</div>';
    if (session.events && session.events.length > 0) {
      eventsListHtml = session.events.map(ev => `
        <div class="pwr-detail-card p-2 mb-2">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="badge bg-primary-subtle text-primary border border-primary-subtle font-monospace">Event ${ev.event_id}</span>
            <span class="font-monospace small text-muted">${escapeHtml(ev.timestamp)}</span>
          </div>
          <div class="small fw-semibold text-primary">${escapeHtml(ev.provider || '')}</div>
          <div class="small mt-1">${escapeHtml(ev.reason || ev.details?.message || '')}</div>
          ${ev.process ? `<div class="small text-muted font-monospace mt-1">Процесс: ${escapeHtml(ev.process)} | Пользователь: ${escapeHtml(ev.user || '--')}</div>` : ''}
        </div>
      `).join('');
    }

    modalBody.innerHTML = `
      <div class="row g-3 mb-3">
        <div class="col-6">
          <div class="pwr-detail-card p-2.5">
            <div class="text-muted small">🚀 Время старта (Boot):</div>
            <div class="font-monospace fw-bold text-info mt-1">${escapeHtml(session.boot_time)}</div>
          </div>
        </div>
        <div class="col-6">
          <div class="pwr-detail-card p-2.5">
            <div class="text-muted small">⏹️ Завершение работы:</div>
            <div class="font-monospace fw-bold ${session.shutdown_time ? '' : 'text-success'} mt-1">
              ${session.shutdown_time ? escapeHtml(session.shutdown_time) : 'Сессия активна'}
            </div>
          </div>
        </div>
      </div>

      <div class="pwr-detail-card p-3 mb-3">
        <h6 class="fw-bold text-warning mb-2"><i class="bi bi-sliders me-1.5"></i>Параметры завершения</h6>
        <div class="row g-2 small">
          <div class="col-4 text-muted">Тип завершения:</div>
          <div class="col-8 fw-semibold">${escapeHtml(session.shutdown_type)}</div>
          
          <div class="col-4 text-muted">Аптайм сессии:</div>
          <div class="col-8 font-monospace fw-bold">${escapeHtml(session.uptime_human || '--')}</div>

          <div class="col-4 text-muted">Инициатор:</div>
          <div class="col-8">${escapeHtml(session.initiator || 'SYSTEM / Hardware')}</div>

          <div class="col-4 text-muted">Процесс:</div>
          <div class="col-8 font-monospace text-info">${escapeHtml(session.process || '--')}</div>

          <div class="col-4 text-muted">Код причины:</div>
          <div class="col-8 font-monospace text-secondary">${escapeHtml(session.reason_code || '--')}</div>

          <div class="col-4 text-muted">Текст причины:</div>
          <div class="col-8">${escapeHtml(session.reason || '--')}</div>

          ${session.comment ? `
            <div class="col-4 text-muted">Комментарий:</div>
            <div class="col-8 font-italic">${escapeHtml(session.comment)}</div>
          ` : ''}

          ${session.bugcheck ? `
            <div class="col-4 text-danger fw-bold">BSOD BugCheck:</div>
            <div class="col-8 text-danger font-monospace fw-bold">${escapeHtml(session.bugcheck)}</div>
          ` : ''}
        </div>
      </div>

      ${session.initiator_chain && session.initiator_chain.length > 0 ? `
        <div class="pwr-detail-card p-3 mb-3">
          <h6 class="fw-bold text-info mb-2"><i class="bi bi-diagram-3 me-1.5"></i>Корреляция цепочки вызова</h6>
          <div class="d-flex align-items-center flex-wrap gap-1 font-monospace small">
            ${session.initiator_chain.map((step, idx) => `
              <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle p-2">${escapeHtml(step)}</span>
              ${idx < session.initiator_chain.length - 1 ? '<i class="bi bi-arrow-right text-muted"></i>' : ''}
            `).join('')}
          </div>
        </div>
      ` : ''}

      <div class="pwr-detail-card p-3">
        <h6 class="fw-bold mb-2"><i class="bi bi-list-nested me-1.5"></i>Хронология событий в рамках сессии</h6>
        <div style="max-height: 250px; overflow-y: auto;">
          ${eventsListHtml}
        </div>
      </div>
    `;

    const modalEl = document.getElementById('pwrSessionDetailModal');
    if (modalEl && window.bootstrap) {
      const modal = new window.bootstrap.Modal(modalEl);
      modal.show();
    }
  }
}
