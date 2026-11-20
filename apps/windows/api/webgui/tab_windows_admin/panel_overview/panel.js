/**
 * =============================================================================
 * Название: Панель общего статуса, токена, Privacy Radar и Windows Backup
 * =============================================================================
 * Описание:
 *   Мониторинг хоста, Active Directory, токена текущего процесса (SID, Integrity),
 *   контроль камеры и микрофона (Privacy Radar) и состояние архивации File History.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_overview/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';
import { isPanelActive } from '../../js/tab-core.js';

/**
 * Получение контекста текущего пользователя и токена безопасности.
 */
export async function loadCurrentToken() {
  const badgeEl = document.getElementById('ai-current-token-badge');
  try {
    const res = await fetch('/api/v1/windows/identity/current');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const isElevated = data.is_elevated
      ? '<span class="ui-badge ui-badge-danger ms-1">Elevated (Admin)</span>'
      : '<span class="ui-badge ui-badge-neutral ms-1">Standard</span>';
    const integrityBadge = `<span class="ui-badge ui-badge-primary ms-1">${escapeHtml(data.integrity_level || 'Medium')}</span>`;
    if (badgeEl) {
      badgeEl.innerHTML = `Текущий токен: <strong>${escapeHtml(data.domain || '')}\\${escapeHtml(data.user_name || '')}</strong> (SID: <code>${escapeHtml(data.user_sid || '')}</code>) | Целостность: ${integrityBadge} ${isElevated}`;
    }
  } catch (err) {
    if (badgeEl) badgeEl.innerHTML = `<span class="text-warning">Контекст токена: локальная среда (${escapeHtml(err.message)})</span>`;
  }
}

/**
 * Получение общего статуса системного администрирования хоста.
 */
export async function fetchStatus() {
  try {
    const res = await fetch('/api/v1/sysadmin/status');
    if (!res.ok) return;
    const data = await res.json();

    const hostEl = document.getElementById('winadmin-hostname');
    const userCountEl = document.getElementById('winadmin-user-count');
    const userBreakdownEl = document.getElementById('winadmin-user-breakdown');
    const adStatusEl = document.getElementById('winadmin-ad-status');
    const eventsCountEl = document.getElementById('winadmin-events-count');

    if (hostEl) hostEl.innerText = `${data.hostname || 'LOCAL'} / ${data.domain || 'WORKGROUP'}`;
    if (userCountEl) {
      userCountEl.innerText = `${data.total_accounts || data.user_count || 0} (${data.active_users || 0} онлайн)`;
    }
    if (userBreakdownEl) {
      userBreakdownEl.innerText = `${data.hidden_users || 0} скрытых`;
    }
    if (adStatusEl) adStatusEl.innerText = data.ad_connected ? 'Подключен' : 'Локальный хост';
    if (eventsCountEl) eventsCountEl.innerText = data.event_count || 0;
  } catch (e) {
    console.error('[WinAdminTab] Ошибка загрузки статуса хоста:', e);
  }
}

/**
 * Обновление виджета Privacy Radar (контроль камеры и микрофона).
 */
export async function updatePrivacyRadar() {
  if (typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-windows-admin', 'panel-overview', 'panel-overview')) return;
  }
  try {
    let data = null;
    try {
      const res = await fetch('/api/v1/system/diagnostics/forensics');
      if (res.ok) data = await res.json();
    } catch (_) {}

    if (!data) {
      try {
        const res = await fetch('/api/v1/forensics/privacy-status');
        if (res.ok) data = await res.json();
      } catch (_) {}
    }

    if (data) {
      const camEl = document.getElementById('camera-active-apps-text');
      const micEl = document.getElementById('mic-active-apps-text');
      const formatApps = (apps) => {
        if (!apps || !apps.length) return 'Нет активных обращений';
        return apps.map(a => typeof a === 'string' ? a : (a.app_name || a.name || JSON.stringify(a))).join(', ');
      };
      if (camEl) camEl.textContent = formatApps(data.camera_active_apps);
      if (micEl) micEl.textContent = formatApps(data.microphone_active_apps);
    }
  } catch (err) {
    console.warn('[WinAdminTab] Ошибка обновления Privacy Radar:', err);
  }
}

/**
 * Обновление статуса службы архивации Windows Backup (File History).
 */
export async function updateWindowsBackupStatus() {
  if (typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-windows-admin', 'panel-overview', 'panel-overview')) return;
  }
  try {
    const res = await fetch('/api/v1/windows-backup/file-history/status');
    if (!res.ok) return;
    const data = await res.json();

    const badgeEl = document.getElementById('sysadmin-backup-badge');
    const lastTimeEl = document.getElementById('sysadmin-last-backup-time');
    const targetEl = document.getElementById('sysadmin-backup-target');

    const isRunning = Boolean(data.is_service_running);
    if (badgeEl) {
      badgeEl.textContent = isRunning ? 'File History: Active' : 'File History: Inactive';
      badgeEl.className = isRunning
        ? 'ui-badge ui-badge-success font-monospace small'
        : 'ui-badge ui-badge-neutral font-monospace small';
    }

    const cfg = data.config;
    if (cfg) {
      if (lastTimeEl) lastTimeEl.textContent = cfg.last_backup_time || 'Нет записей';
      if (targetEl) targetEl.textContent = cfg.target_path || cfg.target_url || 'Не настроено';
    }
  } catch (e) {
    console.warn('[WinAdminTab] Ошибка обновления статуса бэкапа:', e);
  }
}

/**
 * Инициирует немедленный запуск резервного копирования File History.
 */
export async function triggerWindowsBackup() {
  const btn = document.querySelector('#windows-backup-widget button');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Архивация...';
  }
  try {
    const res = await fetch('/api/v1/windows-backup/file-history/trigger', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      alert('Резервное копирование (File History) успешно запущено: ' + (data.message || 'OK'));
    } else {
      alert('Ошибка запуска: ' + (data.detail || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Сетевая ошибка при запуске архивации: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Архивация';
    }
    await updateWindowsBackupStatus();
  }
}
