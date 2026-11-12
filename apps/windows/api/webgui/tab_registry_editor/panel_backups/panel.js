/**
 * Модуль модального окна резервных копий реестра и точек восстановления.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/panel_backups/panel.js
 * Updated: 2026-10-17 01:55:00
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Открывает модальное окно точек восстановления реестра и загружает список.
 * @param {Function} onRestored - Коллбек перезагрузки текущего ключа после отката.
 */
export async function openBackupsModal(onRestored) {
  const modalEl = document.getElementById('regBackupsModal');
  const tbody = document.getElementById('reg-backups-tbody');

  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">Загрузка истории снимков...</td></tr>';

  try {
    const res = await fetch('/api/registry/backups');
    if (!res.ok) throw new Error('Ошибка загрузки бэкапов');
    const data = await res.json();
    const backups = data?.backups || [];

    if (backups.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-muted">Точки восстановления отсутствуют</td></tr>';
      return;
    }

    tbody.innerHTML = backups.map(b => `
      <tr>
        <td><small class="text-light">${new Date(b.timestamp).toLocaleString()}</small></td>
        <td class="text-truncate" style="max-width: 250px;" title="${b.hive}\\${b.path}">
          <span class="text-warning">${b.hive}</span>\\${escapeHtml(b.path)}
        </td>
        <td><span class="badge bg-secondary">${escapeHtml(b.operation)}</span></td>
        <td>
          <button class="btn btn-xs btn-outline-warning py-0 px-2 btn-restore-backup" data-id="${b.backup_id}">
            <i class="bi bi-arrow-counterclockwise me-1"></i> Откатить
          </button>
        </td>
      </tr>
    `).join('');

    tbody.querySelectorAll('.btn-restore-backup').forEach(btn => {
      btn.onclick = async () => {
        const backupId = btn.getAttribute('data-id');
        if (!confirm(`Восстановить реестр из снимка ${backupId}?`)) return;

        try {
          const rRes = await fetch(`/api/registry/restore?backup_id=${encodeURIComponent(backupId)}`, {
            method: 'POST'
          });
          if (!rRes.ok) {
            const err = await rRes.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${rRes.status}`);
          }
          window.showToast?.('Реестр успешно восстановлен из резервной копии!', 'success');
          if (onRestored) await onRestored();
        } catch (err) {
          window.showToast?.(`Ошибка восстановления: ${err.message}`, 'danger') || alert(`Ошибка восстановления: ${err.message}`);
        }
      };
    });
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-danger">${e.message}</td></tr>`;
  }
}
