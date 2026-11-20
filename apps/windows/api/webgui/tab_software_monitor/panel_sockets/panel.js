/**
 * =============================================================================
 * Process Name: Windows Software Scanner - Sockets & Ports Panel
 * =============================================================================
 * Description:
 *   Модуль инспекции открытых сетевых сокетов, портов (TCP/UDP) и связанных
 *   программных процессов с локальным кэшированием IndexedDB и вызовом ИИ-аудита.
 *
 * File: panel_sockets/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_scanner/panel_sockets
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentSocketsList = [];

/**
 * Инициализирует панель сетевых сокетов и портов.
 * @param {boolean} [forceRefresh=false] - Принудительный сетевой запрос.
 */
export async function initSocketsConfigPanel(forceRefresh = false) {
  const tableBody = document.getElementById('sw-sockets-table-body');
  if (!tableBody) return;

  // 1. Быстрое чтение из кэша IndexedDB (< 10 мс)
  if (!forceRefresh && window.IndexedDBCache) {
    try {
      const cached = await window.IndexedDBCache.get('software_sockets', 'list');
      if (cached && Array.isArray(cached) && cached.length > 0) {
        renderSocketsTable(cached);
      }
    } catch (err) {
      console.debug('[SoftwareHub] Ошибка чтения sockets из кэша:', err);
    }
  }

  // 2. Если данных нет или forceRefresh — сетевой запрос
  if (forceRefresh || tableBody.querySelectorAll('tr').length <= 1) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-4 text-info">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>
          Сбор активных сетевых соединений и сокетов Windows...
        </td>
      </tr>
    `;

    try {
      const signal = window.IndexedDBCache ? window.IndexedDBCache.getFreshAbortSignal() : undefined;
      const res = await fetch('/api/v1/software/sockets', { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = data.sockets || [];

      if (window.IndexedDBCache && list.length > 0) {
        await window.IndexedDBCache.put('software_sockets', 'list', list);
      }
      renderSocketsTable(list);
    } catch (err) {
      if (err.name === 'AbortError') return;
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle me-1"></i>Ошибка загрузки сокетов: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
  }

  const refreshBtn = document.getElementById('sw-btn-refresh-sockets');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.onclick = () => initSocketsConfigPanel(true);
  }
}

/**
 * Отрисовывает строки таблицы сетевых сокетов.
 * @param {Array} sockets - Список сокетов.
 */
export function renderSocketsTable(sockets) {
  const tableBody = document.getElementById('sw-sockets-table-body');
  if (!tableBody) return;

  if (!sockets || sockets.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-4 text-muted">
          Нет активных сетевых сокетов.
        </td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = sockets.map((s, idx) => {
    const protoBadge = s.protocol === 'TCP' ? 'bg-primary' : (s.protocol === 'UDP' ? 'bg-info text-dark' : 'bg-secondary');
    return `
      <tr class="sw-socket-row" style="cursor: pointer;" onclick="window.triggerSocketInspection(${idx})" title="Кликните для ИИ-инспекции сокета">
        <td><span class="badge ${protoBadge} px-2">${escapeHtml(s.protocol)}</span></td>
        <td class="font-monospace text-light">${escapeHtml(s.local_address)}</td>
        <td class="font-monospace text-secondary">${escapeHtml(s.remote_address)}</td>
        <td class="font-monospace text-secondary">${s.pid || '—'}</td>
        <td>
          <div class="fw-semibold text-light">${escapeHtml(s.process || 'N/A')}</div>
          <div class="small text-muted font-monospace text-truncate" style="max-width: 260px;" title="${escapeHtml(s.cmdline || s.path || '')}">${escapeHtml(s.cmdline || s.path || '—')}</div>
        </td>
      </tr>
    `;
  }).join('');

  currentSocketsList = sockets;
  window._currentSocketsList = sockets;
}

/**
 * Запускает ИИ-инспекцию открытого сетевого сокета и связанного процесса.
 * @param {number} idx - Индекс сокета в списке.
 */
export function triggerSocketInspection(idx) {
  const s = (window._currentSocketsList || currentSocketsList || [])[idx];
  if (!s) return;

  if (window.AIModalDialog && typeof window.AIModalDialog.open === 'function') {
    window.AIModalDialog.open({
      program: {
        name: s.process || `PID_${s.pid}`,
        pid: s.pid,
        path: s.path,
        cmdline: s.cmdline,
        protocol: s.protocol,
        local_address: s.local_address,
        remote_address: s.remote_address,
        risk_level: 'Low'
      },
      panelId: 'sockets-config',
      tableType: 'software',
      prompt: 'Оцени безопасность открытого сетевого сокета и связанного процесса'
    });
  } else {
    alert(`Инспекция сокета ${s.protocol} ${s.local_address} процесса ${s.process} (PID ${s.pid})`);
  }
}

// Экспорт для глобального использования в inline onclick
if (typeof window !== 'undefined') {
  window.triggerSocketInspection = triggerSocketInspection;
}
