/**
 * =============================================================================
 * Process Name: Windows Backup - VSS Snapshots & File Deletions Audit Panel
 * =============================================================================
 * Description:
 *   Модуль мониторинга теневых копий томов (Volume Shadow Copies - VSS),
 *   аудита удаления файлов (Security Event ID 4663/4660), включения системных
 *   политик аудита и настройки списков системного контроля доступа SACL.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/panel_vss_audit
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Загрузка списка теневых копий томов (VSS Snapshots).
 * @returns {Promise<void>}
 */
export async function loadVssSnapshots() {
  const tbody = document.getElementById('wb-vss-body');
  const countBadge = document.getElementById('wb-vss-count');

  try {
    const res = await fetch('/api/v1/windows-backup/vss/snapshots');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const snapshots = await res.json();

    if (countBadge) countBadge.textContent = `${snapshots.length} шт.`;

    if (!tbody) return;
    if (!snapshots || snapshots.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">Теневые копии (VSS) не найдены</td></tr>';
      return;
    }

    tbody.innerHTML = snapshots.map(s => `
      <tr>
        <td class="font-monospace small text-truncate" style="max-width: 150px;" title="${escapeHtml(s.snapshot_id || '')}">
          ${escapeHtml(s.snapshot_id || '—')}
        </td>
        <td class="fw-semibold text-info">${escapeHtml(s.original_volume || '—')}</td>
        <td class="small text-muted">${escapeHtml(s.creation_time || '—')}</td>
        <td><span class="badge bg-success">${escapeHtml(s.status || 'OK')}</span></td>
      </tr>
    `).join('');
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-danger">Ошибка: ${escapeHtml(e.message)}</td></tr>`;
  }
}

/**
 * Загрузка событий аудита удаления файлов из Security Event Log.
 * @returns {Promise<void>}
 */
export async function loadFileDeletions() {
  try {
    const res = await fetch('/api/v1/system/file-audit/deletions?hours=24&limit=100&deletions_only=true');
    if (!res.ok) return;
    const data = await res.json();
    const events = data.events || [];

    const tbody = document.getElementById('wb-deletions-tbody');
    const badge = document.getElementById('wb-deletions-badge');
    const valDeletions = document.getElementById('wb-val-deletions');

    if (badge) badge.innerText = `${events.length} удалений`;
    if (valDeletions) valDeletions.innerText = events.length;

    if (tbody) {
      if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-3">События удаления (4663/4660) не зафиксированы или аудит не включен</td></tr>';
        return;
      }
      tbody.innerHTML = events.slice(0, 30).map((e, idx) => `
        <tr class="wb-deletion-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для детального анализа удаления">
          <td class="font-monospace text-muted small">${e.timestamp?.slice(11, 19) || ''}</td>
          <td class="font-monospace fw-semibold ${e.event_id === 4660 ? 'text-danger' : 'text-warning'}">${e.event_id}</td>
          <td class="font-monospace text-truncate text-white" style="max-width: 260px;" title="${escapeHtml(e.object_name)}">${escapeHtml(e.object_name.split('\\').pop() || e.object_name)}</td>
          <td class="small text-info text-truncate" style="max-width: 140px;" title="${escapeHtml(e.process_name)}">${escapeHtml(e.process_name ? e.process_name.split('\\').pop() : 'N/A')}</td>
          <td class="small text-muted">${escapeHtml(e.subject_user_name || 'SYSTEM')}</td>
        </tr>
      `).join('');

      tbody.querySelectorAll('.wb-deletion-row').forEach(row => {
        row.onclick = () => {
          const idx = parseInt(row.getAttribute('data-idx'), 10);
          const e = events[idx];
          if (!e) return;

          if (window.AITableModal) {
            window.AITableModal.show({
              icon: '🗑️',
              title: `Удаление: ${e.object_name.split('\\').pop() || e.object_name}`,
              subtitle: `Event ID: ${e.event_id} | ${e.timestamp}`,
              panelId: 'panel-windows-backup-deletions',
              tableType: 'security_event',
              badges: [
                { text: `Event ${e.event_id}`, class: e.event_id === 4660 ? 'badge bg-danger' : 'badge bg-warning text-dark' },
                { text: e.status || 'Success', class: 'badge bg-success' }
              ],
              metadata: [
                { label: 'Целевой объект', value: e.object_name },
                { label: 'Тип объекта', value: e.object_type || 'File' },
                { label: 'Процесс-инициатор', value: e.process_name || 'Не указан' },
                { label: 'PID процесса', value: e.process_id ? String(e.process_id) : 'N/A' },
                { label: 'Пользователь', value: `${e.subject_domain_name}\\${e.subject_user_name}` },
                { label: 'Дескриптор HandleId', value: e.handle_id || 'N/A' },
                { label: 'Маска доступа', value: e.access_mask || 'DELETE (0x10000)' }
              ],
              rawTitle: 'Полное сообщение Security Log',
              rawContent: e.raw_message || JSON.stringify(e, null, 2),
              requestData: e
            });
          }
        };
      });
    }
  } catch (e) {
    console.error('[WindowsBackup] Failed to fetch deletion events:', e);
  }
}

/**
 * Включение системного аудита файловой системы через auditpol.
 */
export async function enableFileSystemAudit() {
  if (confirm('Включить системный аудит файловой системы (auditpol /set /subcategory:File System)?')) {
    try {
      const res = await fetch('/api/v1/system/file-audit/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable_success: true, enable_failure: true })
      });
      const data = await res.json();
      alert(data.success ? 'Аудит файловой системы успешно активирован!' : `Ошибка: ${data.error || 'Сбой'}`);
      if (typeof window.loadBackupData === 'function') {
        await window.loadBackupData();
      }
    } catch (err) {
      alert(`Ошибка выполнения: ${err.message}`);
    }
  }
}

/**
 * Настройка системного контроля доступа SACL для папки.
 */
export async function configureFolderSacl() {
  const targetPath = prompt('Укажите путь к папке для настройки SACL аудита удаления:', 'c:\\Users\\onela\\AppData\\Local\\ai-tc');
  if (targetPath) {
    try {
      const res = await fetch('/api/v1/system/file-audit/folder-sacl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, principal: 'Everyone', enable: true })
      });
      const data = await res.json();
      alert(data.Success ? `SACL успешно настроен для ${targetPath}!` : `Ошибка: ${data.Error || 'Сбой'}`);
      await loadFileDeletions();
    } catch (err) {
      alert(`Ошибка: ${err.message}`);
    }
  }
}

/**
 * Привязка событий элементов аудита и VSS.
 */
export function bindVssAuditEvents() {
  const btnEnableAudit = document.getElementById('wb-btn-enable-auditpol');
  if (btnEnableAudit && !btnEnableAudit._bound) {
    btnEnableAudit._bound = true;
    btnEnableAudit.onclick = enableFileSystemAudit;
  }

  const btnConfigureSacl = document.getElementById('wb-btn-configure-sacl');
  if (btnConfigureSacl && !btnConfigureSacl._bound) {
    btnConfigureSacl._bound = true;
    btnConfigureSacl.onclick = configureFolderSacl;
  }
}
