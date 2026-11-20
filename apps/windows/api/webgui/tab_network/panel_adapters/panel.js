/**
 * Модуль панели сетевых адаптеров и интерфейсов хоста.
 * Файл: apps/windows/api/webgui/tab_network/panel_adapters/panel.js
 * Updated: 2026-11-20 16:45:00
 */

import { formatBytes } from '../common/ui_utils.js';

let allAdapters = [];

/**
 * Возвращает массив обнаруженных сетевых адаптеров.
 * @returns {Array<Object>}
 */
export function getAllAdapters() {
  return allAdapters;
}

/**
 * Запрашивает перечень сетевых адаптеров и обновляет таблицу и селектор.
 */
export async function fetchAdapters() {
  const tbody = document.getElementById('net-adapters-tbody');
  const ifaceSelect = document.getElementById('net-interface-select');
  const kpiActive = document.getElementById('net-kpi-adapters-active');

  try {
    const res = await fetch('/api/v1/network/interfaces');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const adapters = await res.json();
    allAdapters = Array.isArray(adapters) ? adapters : [];

    let activeCount = 0;

    if (ifaceSelect) {
      ifaceSelect.innerHTML = allAdapters.map(a => `
        <option value="${a.name || a.id}">${a.name} (${a.description || 'Ethernet'}) - ${a.status}</option>
      `).join('');
    }

    if (tbody) {
      if (allAdapters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">Сетевые адаптеры не обнаружены.</td></tr>';
        return;
      }

      tbody.innerHTML = allAdapters.map(a => {
        if (a.is_up) activeCount++;
        const statusClass = a.is_up ? 'status-badge-up' : 'status-badge-down';
        const speedDisplay = a.speed_mbps ? `${a.speed_mbps} Mbps` : '--';
        const ipDisplay = a.ipv4 && a.ipv4.length > 0 ? a.ipv4.join(', ') : '--';

        return `
          <tr>
            <td class="fw-bold text-body"><i class="bi bi-hdd-network me-1 text-info"></i>${a.name}</td>
            <td class="text-secondary small text-truncate" style="max-width: 220px;" title="${a.description}">${a.description || '--'}</td>
            <td class="text-info">${ipDisplay}</td>
            <td class="text-muted small">${a.mac || '--'}</td>
            <td><span class="badge bg-body-secondary border text-body">${speedDisplay}</span></td>
            <td><span class="proto-badge ${statusClass}">${a.status || 'Unknown'}</span></td>
            <td style="text-align: right;" class="text-success">${formatBytes(a.bytes_sent)}</td>
            <td style="text-align: right;" class="text-primary">${formatBytes(a.bytes_recv)}</td>
          </tr>
        `;
      }).join('');
    }

    if (kpiActive) kpiActive.innerText = `${activeCount} активных`;
  } catch (e) {
    console.error('[NetworkTab] Failed to fetch adapters:', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-3 text-danger">Ошибка загрузки адаптеров: ${e.message}</td></tr>`;
  }
}
