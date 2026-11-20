/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - History Panel
 * =============================================================================
 * Description:
 *   Модуль управления и отображения истории замеров скорости дисков.
 *
 * File: panel_history/panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed/panel_history
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Загрузка истории тестирования.
 */
export async function loadHistory() {
  try {
    const res = await fetch('/api/v1/storage/benchmark/history?limit=20');
    if (!res.ok) return;
    const list = await res.json();

    const countBadge = document.getElementById('bench-history-count');
    if (countBadge) countBadge.textContent = `${list.length} записей`;

    const tbody = document.getElementById('bench-history-tbody');
    if (!tbody) return;

    if (!list || list.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">История пуста</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    list.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="text-white">${item.created_at}</td>
        <td><span class="badge bg-secondary">${item.target}</span></td>
        <td class="text-info fw-bold">${item.seq1m_read_mb_s.toFixed(0)} <span class="text-muted">/</span> <span class="text-warning">${item.seq1m_write_mb_s.toFixed(0)} MB/s</span></td>
        <td class="text-success">${Math.round(item.rnd4k_read_iops)} <span class="text-muted">/</span> ${Math.round(item.rnd4k_write_iops)}</td>
        <td class="text-end">
          <button class="btn btn-outline-danger btn-sm py-0 px-1 bench-delete-btn" data-id="${item.id}" title="Удалить">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll('.bench-delete-btn').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        if (confirm('Удалить эту запись из истории?')) {
          await deleteHistoryItem(id);
        }
      });
    });
  } catch (err) {
    console.debug('[DiskSpeed] Ошибка загрузки истории:', err);
  }
}

/**
 * Удаление записи из истории.
 * @param {string|number} id
 */
export async function deleteHistoryItem(id) {
  try {
    await fetch(`/api/v1/storage/benchmark/history/${id}`, { method: 'DELETE' });
    await loadHistory();
    if (window.toast) window.toast.info('Удалено', 'Запись удалена из базы данных');
  } catch (err) {
    console.error('[DiskSpeed] Ошибка удаления:', err);
  }
}
