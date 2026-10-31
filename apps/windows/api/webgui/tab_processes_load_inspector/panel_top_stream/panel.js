/**
 * Модуль потока топовых процессов хоста в реальном времени (Live Stream).
 * Интерактивный список процессов с вызовом ИИ-ассистента и Drill-Down кнопками Deep Dive.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/panel_top_stream/panel.js
 * Updated: 2026-10-31 18:55:00
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
import { openProcessAiModal } from '../panel_ai_audit/panel.js?v=20261031_v2';

let cachedTopProcesses = [];
let isProcPaused = false;
let onDrillDownCallback = null;
let onSelectProcessCallback = null;
let onKillProcessCallback = null;

/**
 * Инициализирует панель топа процессов и элементы управления поиском/паузой.
 * @param {Object} options - Колбэки и настройки.
 */
export function initTopStreamPanel(options = {}) {
  onDrillDownCallback = options.onDrillDown || null;
  onSelectProcessCallback = options.onSelectProcess || null;
  onKillProcessCallback = options.onKillProcess || null;

  const searchInput = document.getElementById('sys-proc-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderHostProcessesTable());
  }

  const btnPause = document.getElementById('btn-proc-pause') || document.getElementById('btn-sys-pause-proc');
  if (btnPause) {
    btnPause.addEventListener('click', () => {
      isProcPaused = !isProcPaused;
      btnPause.innerHTML = isProcPaused ? '<i class="bi bi-play-fill me-1"></i>Продолжить' : '<i class="bi bi-pause-fill me-1"></i>Пауза';
      btnPause.className = isProcPaused ? 'btn btn-xs btn-outline-warning' : 'btn btn-xs btn-outline-secondary';
    });
  }

  const btnRefresh = document.getElementById('btn-proc-refresh') || document.getElementById('btn-sys-refresh-proc');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => fetchHostProcesses(true));
  }
}

/**
 * Запрашивает топ процессов хоста с сервера.
 * @param {boolean} [force=false] - Принудительный опрос.
 */
export async function fetchHostProcesses(force = false) {
  if (!isProcessesTabActive() || (!force && getActiveSubTabId() !== 'top')) return;
  try {
    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-top-processes?limit=30');
    if (res.ok) {
      const procs = await res.json();
      renderHostProcessesTable(procs);
    }
  } catch (e) {
    console.warn('[ProcessActivity] Failed to fetch top processes:', e);
  }
}

/**
 * Отрисовывает таблицу топовых процессов с фильтрацией по имени/PID.
 * @param {Array<Object>} [processes] - Список процессов.
 */
export function renderHostProcessesTable(processes) {
  if (processes) cachedTopProcesses = processes;
  if (isProcPaused) return;

  const tbody = document.getElementById('sys-proc-tbody');
  const badge = document.getElementById('proc-top-count-badge');
  const searchVal = document.getElementById('sys-proc-search')?.value.toLowerCase().trim() || '';
  if (!tbody) return;

  let filtered = cachedTopProcesses;
  if (searchVal) {
    filtered = filtered.filter(p => 
      p.name.toLowerCase().includes(searchVal) || 
      String(p.pid).includes(searchVal)
    );
  }

  if (badge) badge.textContent = `${filtered.length} процессов`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-3" style="color: var(--text-muted);">Процессы не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(p => {
    const tooltipAttrs = getProcessTooltipAttributes(p.name, p.pid, `${p.name} [PID: ${p.pid}]`);
    const aiBadge = renderAIBadge(p.name);
    const defaultTitleAttr = tooltipAttrs ? '' : `title="Нажмите для открытия ИИ-помощника и анализа процесса ${escapeHtml(p.name)} [PID: ${p.pid}]"`;

    return `
      <tr class="proc-host-row" data-pid="${p.pid}" ${defaultTitleAttr} ${tooltipAttrs} style="cursor: pointer;">
        <td class="text-center no-modal-trigger" style="width: 36px;">
          <button type="button" class="btn-drilldown-proc" data-pid="${p.pid}" title="Drill-down: 🔬 Process Intelligence Deep Dive (7 виджетов)">
            <img src="/html/assets/red_drill.png?v=20261015_v2" alt="Drill-down">
          </button>
        </td>
        <td class="font-monospace fw-bold text-info">${p.pid}</td>
        <td class="font-monospace text-truncate text-light fw-semibold" style="max-width: 220px;" title="${escapeHtml(p.name)}">
          ${escapeHtml(p.name)} ${aiBadge}
        </td>
        <td><span class="badge bg-success-subtle text-success">${escapeHtml(p.status || 'RUNNING')}</span></td>
        <td class="text-end font-monospace ${(p.cpu_percent || 0) > 10 ? 'badge-cpu-high' : 'text-light'}">${(p.cpu_percent || 0).toFixed(1)}%</td>
        <td class="text-end font-monospace text-light">${p.memory_mb ? p.memory_mb.toFixed(0) + ' MB' : (formatBytes(p.memory_bytes))}</td>
        <td class="text-end font-monospace text-muted">${p.num_threads || p.threads || 1}</td>
        <td class="font-monospace text-truncate text-muted" style="max-width: 140px;">${escapeHtml(p.username || 'SYSTEM')}</td>
      </tr>
    `;
  }).join('');

  initTableSmartTooltips(tbody);

  if (window.autoAdjustTableHeight) {
    window.autoAdjustTableHeight('sys-proc-table-container', filtered.length);
  }

  tbody.querySelectorAll('.btn-drilldown-proc').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetBtn = e.target.closest('.btn-drilldown-proc') || btn;
      const pid = parseInt(targetBtn.getAttribute('data-pid'), 10);
      if (pid && onDrillDownCallback) {
        onDrillDownCallback(pid);
      }
    });
  });

  tbody.querySelectorAll('.proc-host-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('.no-modal-trigger') || e.target.closest('button')) return;
      const pid = parseInt(row.getAttribute('data-pid'), 10);
      const proc = cachedTopProcesses.find(p => p.pid === pid);
      if (proc) {
        if (onSelectProcessCallback) {
          onSelectProcessCallback(proc);
        } else {
          openProcessAiModal(
            proc,
            'sub',
            null,
            onKillProcessCallback,
            'panel-processes-load-inspector-top-protsessov-khosta-live-strea'
          );
        }
      } else if (pid && onDrillDownCallback) {
        onDrillDownCallback(pid);
      }
    });
  });
}
