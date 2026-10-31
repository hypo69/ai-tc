/**
 * Модуль аудита утечек ресурсов и дескрипторов процессов (Leak Hunter).
 * Анализ дескрипторов (Handles), GDI/USER объектов, Page Faults и рисков утечек.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/panel_leak_hunter/panel.js
 * Updated: 2026-10-18 22:53:00
 */

import {
  escapeHtml,
  isProcessesTabActive,
  getActiveSubTabId,
  renderAIBadge,
  getProcessTooltipAttributes,
  initTableSmartTooltips
} from '../common/ui_utils.js?v=20261031_v2';

let rawLeakProcesses = [];
let leakFilter = 'all';
let isFetchingLeaks = false;
let onDrillDownCallback = null;

/**
 * Инициализирует модуль Leak Hunter и элементы управления.
 * @param {Object} options - Колбэки и настройки.
 */
export function initLeakHunterPanel(options = {}) {
  onDrillDownCallback = options.onDrillDown || null;

  const searchInput = document.getElementById('diag-leaks-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderProcessLeaksTable(rawLeakProcesses));
  }

  const filterRadios = document.querySelectorAll('input[name="diag-leaks-filter"]');
  filterRadios.forEach(r => {
    r.addEventListener('change', () => {
      leakFilter = r.value;
      renderProcessLeaksTable(rawLeakProcesses);
    });
  });

  const btnRefresh = document.getElementById('btn-diag-leaks-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => fetchProcessLeaks(true));
  }
}

/**
 * Запрашивает данные телеметрии утечек ресурсов с сервера.
 * @param {boolean} [force=false] - Принудительный запрос.
 */
export async function fetchProcessLeaks(force = false) {
  if (!isProcessesTabActive() || (!force && getActiveSubTabId() !== 'leaks')) return;
  if (isFetchingLeaks) return;
  const tbody = document.getElementById('diag-leaks-tbody');
  const refreshBtn = document.getElementById('btn-diag-leaks-refresh');
  const refreshIcon = refreshBtn?.querySelector('i');

  if (refreshBtn) refreshBtn.disabled = true;
  if (refreshIcon) refreshIcon.classList.add('spin-animation');
  isFetchingLeaks = true;

  if (tbody && (!rawLeakProcesses || rawLeakProcesses.length === 0)) {
    tbody.innerHTML = `
      <tr>
        <td colspan="11" class="text-center py-4 text-secondary">
          <div class="spinner-border spinner-border-sm text-info me-2" role="status"></div>
          Загрузка данных глубокой диагностики процессов...
        </td>
      </tr>
    `;
  }

  try {
    if (force) {
      try {
        await fetch('/api/v1/tab-processes-load-inspector/panel-leak-hunter/refresh?limit=100', { method: 'POST' });
      } catch (_) {}
    }

    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-leak-hunter?limit=100');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data) return;

    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val !== null && val !== undefined ? String(val) : '--';
    };

    setText('diag-leaks-total-proc', data.total_processes ?? 0);
    setText('diag-leaks-suspicious-count', data.suspicious_count ?? 0);

    if (data.top_handle_hogs && data.top_handle_hogs.length > 0) {
      const topH = data.top_handle_hogs[0];
      setText('diag-leaks-peak-handles', `${(topH.handles_count || 0).toLocaleString()} шт.`);
      setText('diag-leaks-peak-handles-proc', `Процесс: ${topH.name || 'неизвестно'} (PID ${topH.pid})`);
    } else {
      setText('diag-leaks-peak-handles', '0 шт.');
      setText('diag-leaks-peak-handles-proc', 'Аномалий не обнаружено');
    }

    if (data.top_gdi_hogs && data.top_gdi_hogs.length > 0) {
      const topG = data.top_gdi_hogs[0];
      setText('diag-leaks-peak-gdi', `${(topG.gdi_objects || 0).toLocaleString()} шт.`);
      setText('diag-leaks-peak-gdi-proc', `Процесс: ${topG.name || 'неизвестно'} (PID ${topG.pid})`);
    } else {
      setText('diag-leaks-peak-gdi', '0 шт.');
      setText('diag-leaks-peak-gdi-proc', 'Лимит OS: 10 000');
    }

    rawLeakProcesses = data.all_processes || [];
    renderProcessLeaksTable(rawLeakProcesses);
  } catch (err) {
    console.warn('[ProcessesLoadInspector] fetchProcessLeaks error:', err);
    if (tbody && rawLeakProcesses.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="11" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            Не удалось загрузить данные телеметрии утечек: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
  } finally {
    isFetchingLeaks = false;
    if (refreshBtn) refreshBtn.disabled = false;
    if (refreshIcon) refreshIcon.classList.remove('spin-animation');
  }
}

/**
 * Отрисовывает таблицу процессов и рисков утечек.
 * @param {Array<Object>} [processes] - Список процессов.
 */
export function renderProcessLeaksTable(processes) {
  const tbody = document.getElementById('diag-leaks-tbody');
  if (!tbody) return;

  const query = (document.getElementById('diag-leaks-search')?.value || '').trim().toLowerCase();
  const list = Array.isArray(processes) ? processes : [];

  let filtered = list.filter(p => {
    if (!p) return false;
    const name = String(p.name || '').toLowerCase();
    const pidStr = String(p.pid || '');
    if (query && !name.includes(query) && !pidStr.includes(query)) {
      return false;
    }
    if (leakFilter === 'suspicious') return p.leak_risk_score !== 'normal';
    if (leakFilter === 'gdi') return (p.gdi_objects || 0) > 500;
    if (leakFilter === 'handles') return (p.handles_count || 0) > 1500;
    return true;
  });

  const countBadge = document.getElementById('proc-leaks-count-badge');
  if (countBadge) {
    countBadge.textContent = `${filtered.length} процессов`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="text-center py-4 text-secondary">Процессов по заданным критериям не найдено</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(p => {
    let riskBadge = '<span class="badge bg-success-subtle text-success border border-success">Норма</span>';
    if (p.leak_risk_score === 'critical') {
      riskBadge = '<span class="badge bg-danger-subtle text-danger border border-danger">Критический</span>';
    } else if (p.leak_risk_score === 'warning') {
      riskBadge = '<span class="badge bg-warning-subtle text-warning border border-warning">Внимание</span>';
    }

    const reasons = (p.leak_risk_reasons && p.leak_risk_reasons.length > 0)
      ? p.leak_risk_reasons.map(r => `<span class="badge bg-dark border border-secondary text-warning me-1">${escapeHtml(r)}</span>`).join('')
      : '<span class="text-secondary small">Штатное поведение</span>';

    const handles = Number(p.handles_count || 0);
    const gdi = Number(p.gdi_objects || 0);
    const userObj = Number(p.user_objects || 0);
    const pageFaults = Number(p.page_faults_total || 0);
    const memMb = Number(p.memory_mb || 0);
    const threads = Number(p.threads_count || 0);

    const tooltipAttrs = getProcessTooltipAttributes(p.name, p.pid, `${p.name} [PID: ${p.pid}]`);
    const aiBadge = renderAIBadge(p.name);

    return `
      <tr class="proc-leak-row" data-pid="${p.pid}" ${tooltipAttrs} style="cursor: pointer;">
        <td class="text-center no-modal-trigger" style="width: 36px;" onclick="event.stopPropagation();">
          <button type="button" class="btn btn-xs btn-outline-info btn-drilldown-proc proc-drilldown-btn" data-pid="${p.pid}" title="Drill-down: 🔬 Process Intelligence Deep Dive (7 виджетов)">
            <img src="/html/assets/red_drill.png?v=20261015_v2" alt="Drill-down" style="width: 14px; height: 14px; vertical-align: middle;">
          </button>
        </td>
        <td><span class="text-info font-monospace">${p.pid}</span></td>
        <td class="fw-bold text-truncate" style="max-width: 180px;" title="${escapeHtml(p.name)}">
          ${escapeHtml(p.name)} ${aiBadge}
        </td>
        <td style="text-align: right;" class="${handles > 1500 ? 'text-danger fw-bold' : ''}">${handles.toLocaleString()}</td>
        <td style="text-align: right;" class="${gdi > 800 ? 'text-danger fw-bold' : ''}">${gdi.toLocaleString()}</td>
        <td style="text-align: right;" class="${userObj > 400 ? 'text-warning' : ''}">${userObj.toLocaleString()}</td>
        <td style="text-align: right;" class="text-secondary font-monospace">${pageFaults.toLocaleString()}</td>
        <td style="text-align: right;" class="text-warning">${memMb.toFixed(1)} MB</td>
        <td style="text-align: right;" class="text-secondary">${threads}</td>
        <td>${riskBadge}</td>
        <td>${reasons}</td>
      </tr>
    `;
  }).join('');

  initTableSmartTooltips(tbody);

  tbody.querySelectorAll('.proc-drilldown-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetBtn = e.target.closest('.proc-drilldown-btn') || btn;
      const pid = parseInt(targetBtn.getAttribute('data-pid'), 10);
      if (pid && onDrillDownCallback) {
        onDrillDownCallback(pid);
      }
    });
  });

  tbody.querySelectorAll('.proc-leak-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      const pid = parseInt(row.getAttribute('data-pid'), 10);
      if (pid && onDrillDownCallback) {
        onDrillDownCallback(pid);
      }
    });
  });

  if (window.autoAdjustTableHeight) {
    window.autoAdjustTableHeight('proc-leaks-table-container', filtered.length);
  }
}
