/**
 * =============================================================================
 * Process Name: Windows Network Terminal - Remote Access Settings Panel
 * =============================================================================
 * Description:
 *   Модуль субпанели настройки входящего удалённого доступа Windows:
 *   диагностика и управление сетевым профилем (Private), SMB (TCP 445),
 *   WinRM / PowerShell Remoting (TCP 5985) и UAC Remote Restrictions
 *   (LocalAccountTokenFilterPolicy) для устранения ошибки «Код: 53».
 *
 * File: panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_network/panel_remote_access
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 20:45:00
 * =============================================================================
 */

let isRemoteAccessBusy = false;
let isRemoteAccessBound = false;

/**
 * Экранирует HTML-символы для безопасного рендеринга.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Формирует HTML-бейдж состояния (включено / выключено).
 * @param {boolean} ok
 * @param {string} okText
 * @param {string} failText
 * @returns {string}
 */
function renderStatusBadge(ok, okText, failText) {
  return ok
    ? `<span class="badge status-badge-up"><i class="bi bi-check-circle-fill me-1"></i>${escapeHtml(okText)}</span>`
    : `<span class="badge status-badge-down"><i class="bi bi-x-circle-fill me-1"></i>${escapeHtml(failText)}</span>`;
}

/**
 * Блокирует или разблокирует кнопки действий на время выполнения операции.
 * @param {boolean} busy
 */
function setActionButtonsDisabled(busy) {
  isRemoteAccessBusy = busy;
  const container = document.getElementById('tab-net-remote-access');
  if (!container) return;
  container.querySelectorAll('[data-ra-action], #btn-ra-refresh').forEach((btn) => {
    btn.disabled = busy;
  });
}

/**
 * Отрисовывает сводное состояние входящего удалённого доступа в DOM.
 * @param {Object} status - Объект RemoteAccessStatus от API.
 */
function renderRemoteAccessStatus(status) {
  if (!status) return;

  const adminAlert = document.getElementById('ra-admin-warning');
  if (adminAlert) {
    adminAlert.classList.toggle('d-none', Boolean(status.is_admin));
  }

  const hostEl = document.getElementById('ra-hostname-label');
  if (hostEl) {
    hostEl.textContent = status.hostname || 'localhost';
  }

  const smbReadyEl = document.getElementById('ra-kpi-smb-ready');
  if (smbReadyEl) {
    smbReadyEl.innerHTML = renderStatusBadge(status.ready_for_smb, 'Готов (TCP 445)', 'Недоступен');
  }

  const winrmReadyEl = document.getElementById('ra-kpi-winrm-ready');
  if (winrmReadyEl) {
    winrmReadyEl.innerHTML = renderStatusBadge(status.ready_for_winrm, 'Готов (TCP 5985)', 'Недоступен');
  }

  const profileBadgeEl = document.getElementById('ra-kpi-profile');
  if (profileBadgeEl) {
    const profiles = Array.isArray(status.network_profiles) ? status.network_profiles : [];
    if (profiles.length === 0) {
      profileBadgeEl.innerHTML = '<span class="badge bg-secondary">Не определено</span>';
    } else if (status.has_public_profile) {
      profileBadgeEl.innerHTML = renderStatusBadge(false, 'Private', 'Есть Public');
    } else {
      profileBadgeEl.innerHTML = renderStatusBadge(true, 'Private / Domain', 'Public');
    }
  }

  const uacBadgeEl = document.getElementById('ra-kpi-uac');
  if (uacBadgeEl) {
    uacBadgeEl.innerHTML = renderStatusBadge(status.uac_remote_allowed, 'Разрешён (=1)', 'Ограничен (=0)');
  }

  // Детали сетевых профилей
  const profilesListEl = document.getElementById('ra-profiles-list');
  if (profilesListEl) {
    const profiles = Array.isArray(status.network_profiles) ? status.network_profiles : [];
    if (profiles.length === 0) {
      profilesListEl.innerHTML = '<span class="text-muted small">Активные сетевые профили не обнаружены</span>';
    } else {
      profilesListEl.innerHTML = profiles
        .map((p) => {
          const isPub = (p.category || '').toLowerCase() === 'public';
          const badgeCls = isPub ? 'status-badge-down' : 'status-badge-up';
          return `<span class="badge ${badgeCls} me-1 mb-1">${escapeHtml(p.interface_alias || p.name)}: ${escapeHtml(p.category)}</span>`;
        })
        .join('');
    }
  }

  // Детали SMB (445)
  const smbSvcEl = document.getElementById('ra-smb-service-state');
  if (smbSvcEl) {
    const svc = status.smb_service || {};
    smbSvcEl.innerHTML = renderStatusBadge(Boolean(svc.running), `${svc.status || 'Running'} (${svc.start_type || 'Auto'})`, `${svc.status || 'Stopped'}`);
  }
  const smbPortEl = document.getElementById('ra-smb-port-state');
  if (smbPortEl) {
    smbPortEl.innerHTML = renderStatusBadge(Boolean(status.port_445_listening), 'Слушает :445', 'Закрыт :445');
  }
  const smbFwEl = document.getElementById('ra-smb-fw-state');
  if (smbFwEl) {
    smbFwEl.innerHTML = renderStatusBadge(Boolean(status.smb_firewall_enabled), 'Разрешено', 'Заблокировано');
  }

  // Детали WinRM (5985)
  const winrmSvcEl = document.getElementById('ra-winrm-service-state');
  if (winrmSvcEl) {
    const svc = status.winrm_service || {};
    winrmSvcEl.innerHTML = renderStatusBadge(Boolean(svc.running), `${svc.status || 'Running'} (${svc.start_type || 'Auto'})`, `${svc.status || 'Stopped'}`);
  }
  const winrmPortEl = document.getElementById('ra-winrm-port-state');
  if (winrmPortEl) {
    winrmPortEl.innerHTML = renderStatusBadge(Boolean(status.port_5985_listening), 'Слушает :5985', 'Закрыт :5985');
  }
  const winrmFwEl = document.getElementById('ra-winrm-fw-state');
  if (winrmFwEl) {
    winrmFwEl.innerHTML = renderStatusBadge(Boolean(status.winrm_firewall_enabled), 'Разрешено', 'Заблокировано');
  }

  // Детали UAC Remote Restrictions
  const uacStateEl = document.getElementById('ra-uac-state');
  if (uacStateEl) {
    uacStateEl.innerHTML = renderStatusBadge(
      Boolean(status.uac_remote_allowed),
      'LocalAccountTokenFilterPolicy = 1',
      'LocalAccountTokenFilterPolicy = 0 (ограничено)'
    );
  }
}

/**
 * Отображает результат последней применённой операции.
 * @param {Object} result - Объект RemoteAccessActionResult от API.
 */
function renderActionLog(result) {
  const logBox = document.getElementById('ra-action-log');
  if (!logBox || !result) return;

  logBox.classList.remove('d-none');
  const alertCls = result.success ? 'alert-success' : (result.requires_admin ? 'alert-warning' : 'alert-danger');
  const iconCls = result.success ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill';
  const stepsHtml = Array.isArray(result.steps) && result.steps.length > 0
    ? `<ul class="mb-0 mt-1 ps-3 small">${result.steps
        .map(
          (s) =>
            `<li><strong>${escapeHtml(s.step)}:</strong> <span class="${s.success ? 'text-success' : 'text-danger'}">${escapeHtml(s.message)}</span></li>`
        )
        .join('')}</ul>`
    : '';

  logBox.innerHTML = `
    <div class="alert ${alertCls} py-2 px-3 mb-0 small">
      <div class="fw-semibold"><i class="bi ${iconCls} me-1"></i>${escapeHtml(result.message)}</div>
      ${stepsHtml}
    </div>
  `;
}

/**
 * Запрашивает текущее состояние входящего удалённого доступа с сервера.
 */
export async function fetchRemoteAccessStatus() {
  const statusHint = document.getElementById('ra-status-hint');
  if (statusHint) statusHint.textContent = 'Проверка портов 445 / 5985, служб и брандмауэра...';

  try {
    const res = await fetch('/api/v1/network/remote-access/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderRemoteAccessStatus(data);
    if (statusHint) statusHint.textContent = `Обновлено: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.warn('[RemoteAccessPanel] Ошибка получения статуса:', err);
    if (statusHint) statusHint.textContent = `Ошибка диагностики: ${err.message}`;
  }
}

/**
 * Применяет выбранное действие настройки удалённого доступа.
 * @param {string} action - Идентификатор действия (enable_all, enable_smb, enable_winrm и т.д.).
 */
export async function applyRemoteAccessAction(action) {
  if (isRemoteAccessBusy || !action) return;
  setActionButtonsDisabled(true);

  const statusHint = document.getElementById('ra-status-hint');
  if (statusHint) statusHint.textContent = `Выполнение операции: ${action}...`;

  try {
    const res = await fetch('/api/v1/network/remote-access/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || `HTTP ${res.status}`);
    }
    if (data.status) {
      renderRemoteAccessStatus(data.status);
    }
    renderActionLog(data);

    if (window.toast) {
      if (data.success) {
        window.toast.success('Удалённый доступ', data.message || 'Настройки применены');
      } else {
        window.toast.warning('Удалённый доступ', data.message || 'Не удалось применить все настройки');
      }
    }
    if (statusHint) statusHint.textContent = `Обновлено: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.warn('[RemoteAccessPanel] Ошибка применения настройки:', err);
    renderActionLog({ success: false, message: `Сбой операции: ${err.message}`, steps: [] });
    if (window.toast) window.toast.error('Ошибка', err.message);
  } finally {
    setActionButtonsDisabled(false);
  }
}

/**
 * Инициализирует обработчики событий субпанели удалённого доступа.
 */
export function initRemoteAccessPanel() {
  if (isRemoteAccessBound) return;
  const container = document.getElementById('tab-net-remote-access');
  if (!container) return;

  isRemoteAccessBound = true;

  const refreshBtn = document.getElementById('btn-ra-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchRemoteAccessStatus());
  }

  container.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-ra-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-ra-action');
    if (action) {
      applyRemoteAccessAction(action);
    }
  });
}
