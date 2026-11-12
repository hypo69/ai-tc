/**
 * Модуль сетевой активности программ и мониторинга изменений файлов хоста.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/panel_network_files/panel.js
 * Updated: 2026-11-01 17:45:00
 */

import {
  escapeHtml,
  formatBytes,
  isProcessesTabActive,
  getActiveSubTabId,
  renderAIBadge,
  getProcessTooltipAttributes,
  initTableSmartTooltips
} from '../common/ui_utils.js?v=20261031_v2';

let cachedNetworkActivities = [];
let currentNetFilter = 'internet';
let isNetPaused = false;

let cachedFileEvents = [];
let isWatcherPaused = false;

/**
 * Инициализирует элементы управления для сети и файлового мониторинга.
 */
export function initNetworkFilesPanel() {
  const netSearch = document.getElementById('proc-net-search');
  if (netSearch) {
    netSearch.addEventListener('input', () => renderNetworkActivityTable());
  }

  const netRadios = document.querySelectorAll('input[name="proc-net-filter"]');
  netRadios.forEach(r => {
    r.addEventListener('change', () => {
      currentNetFilter = r.value;
      renderNetworkActivityTable();
    });
  });

  const btnNetPause = document.getElementById('btn-proc-net-pause');
  if (btnNetPause) {
    btnNetPause.addEventListener('click', () => {
      isNetPaused = !isNetPaused;
      btnNetPause.innerHTML = isNetPaused ? '<i class="bi bi-play-fill me-1"></i>Продолжить' : '<i class="bi bi-pause-fill me-1"></i>Пауза';
      btnNetPause.className = isNetPaused ? 'btn btn-xs btn-outline-warning' : 'btn btn-xs btn-outline-secondary';
    });
  }

  const btnWatcherPause = document.getElementById('btn-proc-watcher-pause');
  if (btnWatcherPause) {
    btnWatcherPause.addEventListener('click', () => {
      isWatcherPaused = !isWatcherPaused;
      btnWatcherPause.innerHTML = isWatcherPaused ? '<i class="bi bi-play-fill me-1"></i>Продолжить' : '<i class="bi bi-pause-fill me-1"></i>Пауза';
      btnWatcherPause.className = isWatcherPaused ? 'btn btn-xs btn-outline-warning' : 'btn btn-xs btn-outline-secondary';
    });
  }
}

/**
 * Запрашивает данные о сетевой активности процессов.
 * @param {boolean} [force=false] - Принудительный опрос.
 */
export async function fetchNetworkActivity(force = false) {
  const activeSub = getActiveSubTabId();
  if (!isProcessesTabActive() || (!force && activeSub !== 'network-activity-by-process' && activeSub !== 'net')) return;
  try {
    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-network-activity?limit=100');
    if (res.ok) {
      const data = await res.json();
      renderNetworkActivityTable(data);
    }
  } catch (e) {
    console.warn('[ProcessActivity] Failed to fetch network activity:', e);
  }
}

/**
 * Отрисовывает таблицу сетевой активности программ.
 * @param {Array<Object>} [activities] - Список сетевых активностей.
 */
export function renderNetworkActivityTable(activities) {
  if (activities) cachedNetworkActivities = activities;
  if (isNetPaused) return;

  const tbody = document.getElementById('proc-net-tbody');
  const badgeCount = document.getElementById('proc-netact-count-badge');
  const badgeConns = document.getElementById('proc-netact-conns-badge');
  const searchVal = document.getElementById('proc-net-search')?.value.toLowerCase().trim() || '';
  if (!tbody) return;

  let filtered = cachedNetworkActivities;
  if (currentNetFilter === 'internet') {
    filtered = filtered.filter(a => a.is_internet || (a.remote_address && !a.remote_address.startsWith('127.') && !a.remote_address.startsWith('0.0.0.0')));
  } else if (currentNetFilter === 'listen') {
    filtered = filtered.filter(a => a.status === 'LISTEN' || a.status === 'LISTENING');
  }

  if (searchVal) {
    filtered = filtered.filter(a => 
      (a.process_name || a.name || '').toLowerCase().includes(searchVal) ||
      String(a.pid || '').includes(searchVal) ||
      (a.remote_address || '').toLowerCase().includes(searchVal) ||
      (a.local_address || '').toLowerCase().includes(searchVal)
    );
  }

  if (badgeCount) badgeCount.textContent = `${filtered.length} программ`;
  if (badgeConns) badgeConns.textContent = `${filtered.reduce((acc, curr) => acc + (curr.connections_count || 1), 0)} сокетов`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center p-3" style="color: var(--text-muted);">Активных сетевых соединений не обнаружено</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(a => {
    const procName = a.process_name || a.name || 'System';
    const sentBytes = a.bytes_sent != null ? a.bytes_sent : ((a.sent_kb || 0) * 1024);
    const recvBytes = a.bytes_recv != null ? a.bytes_recv : ((a.recv_kb || 0) * 1024);
    const sendRate = a.send_rate_kb != null ? a.send_rate_kb : (a.sent_rate_kbs || 0);
    const recvRate = a.recv_rate_kb != null ? a.recv_rate_kb : (a.recv_rate_kbs || 0);
    const serviceProto = a.service_type || a.service_name || a.local_port || '-';
    const tooltipAttrs = getProcessTooltipAttributes(procName, a.pid, `${procName} [PID: ${a.pid}]`);
    const aiBadge = renderAIBadge(procName);

    return `
      <tr ${tooltipAttrs} style="cursor: pointer;">
        <td class="font-monospace" style="min-width: 340px;">
          <div class="d-flex align-items-center gap-1.5">
            <strong class="text-light text-truncate" style="max-width: 360px;" title="${escapeHtml(procName)}">${escapeHtml(procName)}</strong>
            ${aiBadge}
            <span class="badge bg-secondary ms-1 flex-shrink-0">PID: ${a.pid}</span>
          </div>
        </td>
        <td class="font-monospace text-warning text-truncate" style="min-width: 240px; max-width: 360px;" title="${escapeHtml(a.remote_address || '0.0.0.0:*')}">${escapeHtml(a.remote_address || '0.0.0.0:*')}</td>
        <td class="font-monospace text-info">${escapeHtml(a.protocol || 'TCP')} / ${escapeHtml(serviceProto)}</td>
        <td class="text-center"><span class="badge bg-success-subtle text-success">${escapeHtml(a.status || 'ESTABLISHED')}</span></td>
        <td class="font-monospace text-light text-nowrap">${formatBytes(sentBytes)} (${sendRate.toFixed(1)} KB/s)</td>
        <td class="font-monospace text-light text-nowrap">${formatBytes(recvBytes)} (${recvRate.toFixed(1)} KB/s)</td>
      </tr>
    `;
  }).join('');

  initTableSmartTooltips(tbody);

  if (window.autoAdjustTableHeight) {
    window.autoAdjustTableHeight('proc-net-table-container', filtered.length);
  }
}

/**
 * Запрашивает события изменений файлов в реальном времени.
 * @param {boolean} [force=false] - Принудительный опрос.
 */
export async function fetchLiveFileEvents(force = false) {
  if (!isProcessesTabActive() || (!force && getActiveSubTabId() !== 'files')) return;
  try {
    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-file-watcher/events?limit=50');
    if (res.ok) {
      const events = await res.json();
      renderFileEventsTable(events);
    }
  } catch (e) {
    console.warn('[ProcessActivity] Failed to fetch file watcher events:', e);
  }
}

/**
 * Отрисовывает таблицу изменений файлов.
 * @param {Array<Object>} [events] - Список событий файлов.
 */
export function renderFileEventsTable(events) {
  if (events) cachedFileEvents = events;
  if (isWatcherPaused) return;

  const tbody = document.getElementById('proc-watcher-tbody');
  if (!tbody) return;

  if (!cachedFileEvents || cachedFileEvents.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center p-3" style="color: var(--text-muted);">Мониторинг файловых событий...</td></tr>';
    return;
  }

  tbody.innerHTML = cachedFileEvents.map(ev => `
    <tr>
      <td class="font-monospace text-muted" style="font-size: 0.74rem;">${ev.time || (ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString('ru-RU') : '--')}</td>
      <td><span class="badge bg-info-subtle text-info">${escapeHtml(ev.action || 'MODIFY')}</span></td>
      <td class="font-monospace text-truncate text-light" style="min-width: 280px; max-width: 360px;" title="${escapeHtml(ev.process_name || 'System')}">${escapeHtml(ev.process_name || 'System')}</td>
      <td class="font-monospace text-truncate text-muted" style="max-width: 480px;" title="${escapeHtml(ev.path || ev.file_path)}">${escapeHtml(ev.path || ev.file_path)}</td>
    </tr>
  `).join('');

  if (window.autoAdjustTableHeight) {
    window.autoAdjustTableHeight('proc-watcher-table-container', cachedFileEvents.length);
  }
}
