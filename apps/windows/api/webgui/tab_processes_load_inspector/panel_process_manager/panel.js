/**
 * Модуль Диспетчера процессов и приложений (Task Manager Process Manager).
 * Группировка Apps, Background, Windows, фильтрация, раскрытие деревьев и SafeOps.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/panel_process_manager/panel.js
 * Updated: 2026-10-31 18:55:00
 */

import {
  escapeHtml,
  showToast,
  isProcessesTabActive,
  getActiveSubTabId,
  renderAIBadge,
  getProcessTooltipAttributes,
  initTableSmartTooltips
} from '../common/ui_utils.js?v=20261031_v2';
import { openProcessAiModal } from '../panel_ai_audit/panel.js?v=20261031_v2';

let pmReport = null;
let currentCategoryFilter = 'all';
let expandedGroups = new Set();
let allExpanded = false;
let onDrillDownCallback = null;
let onRefreshTopCallback = null;

/**
 * Инициализирует панель диспетчера процессов и привязывает внешние колбэки.
 * @param {Object} options - Настройки и колбэки.
 */
export function initProcessManagerPanel(options = {}) {
  onDrillDownCallback = options.onDrillDown || null;
  onRefreshTopCallback = options.onRefreshTop || null;
  setupProcessManagerControls();
}

/**
 * Привязывает обработчики к элементам управления поиска и переключения категорий.
 */
function setupProcessManagerControls() {
  const searchInput = document.getElementById('pm-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => applyProcessFilters());
  }

  const btnExpandAll = document.getElementById('pm-btn-expand-all');
  if (btnExpandAll) {
    btnExpandAll.onclick = () => toggleAllGroups();
  }

  const catRadios = document.querySelectorAll('input[name="pm-cat-filter"]');
  catRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      setCategoryFilter(radio.value);
    });
  });

  const btnRefresh = document.getElementById('pm-btn-refresh');
  if (btnRefresh) {
    btnRefresh.onclick = () => fetchProcessManagerSummary(true);
  }
}

/**
 * Запрашивает сводные данные процессов с сервера.
 * @param {boolean} [force=false] - Принудительный запрос независимо от активности подвкладки.
 */
export async function fetchProcessManagerSummary(force = false) {
  if (!isProcessesTabActive() || (!force && getActiveSubTabId() !== 'manager')) return;
  try {
    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-process-manager');
    if (!res.ok) {
      const fallbackRes = await fetch('/api/v1/tab-processes-load-inspector/panel-process-manager/summary');
      if (!fallbackRes.ok) throw new Error(`HTTP ${res.status}`);
      pmReport = await fallbackRes.json();
    } else {
      pmReport = await res.json();
    }
    renderProcessManager(pmReport);
  } catch (err) {
    console.warn('[ProcessManager] Ошибка получения процессов:', err);
  }
}

/**
 * Отрисовывает сводку и запускает фильтрацию категорий.
 * @param {Object} report - Отчет диспетчера процессов.
 */
export function renderProcessManager(report) {
  if (!report) return;

  const appsList = report.apps || [];
  const bgList = report.background_processes || [];
  const winList = report.windows_processes || [];

  const appsCountEl = document.getElementById('pm-apps-count');
  const bgCountEl = document.getElementById('pm-bg-count');
  const winCountEl = document.getElementById('pm-win-count');
  const totalCountEl = document.getElementById('pm-total-count');
  const ramUsageEl = document.getElementById('pm-ram-usage');

  const totalProcs = report.total_processes || (appsList.length + bgList.length + winList.length);
  const totalMemMb = report.total_memory_used_mb || 0;

  if (appsCountEl) appsCountEl.textContent = report.apps_count !== undefined ? report.apps_count : appsList.length;
  if (bgCountEl) bgCountEl.textContent = report.background_count !== undefined ? report.background_count : bgList.length;
  if (winCountEl) winCountEl.textContent = report.windows_count !== undefined ? report.windows_count : winList.length;
  if (totalCountEl) totalCountEl.textContent = totalProcs;

  if (ramUsageEl) {
    const memStr = totalMemMb >= 1024 ? `${(totalMemMb / 1024).toFixed(1)} GB` : `${Math.round(totalMemMb)} MB`;
    ramUsageEl.textContent = `Память: ${memStr}`;
  }

  applyProcessFilters();
}

/**
 * Применяет текстовый и категориальный фильтры к таблице процессов.
 */
export function applyProcessFilters() {
  if (!pmReport) return;

  const tbody = document.getElementById('pm-tbody');
  const searchInput = document.getElementById('pm-search-input');
  const badge = document.getElementById('pm-table-badge');
  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

  const apps = pmReport.apps || [];
  const bg = pmReport.background_processes || [];
  const win = pmReport.windows_processes || [];

  function filterGroup(group) {
    if (!query) return true;
    const nameMatch = (group.name || '').toLowerCase().includes(query);
    const friendlyMatch = (group.friendly_name || '').toLowerCase().includes(query);
    const pidMatch = String(group.main_pid || '').includes(query);
    const realParentMatch = (group.real_parent_name || '').toLowerCase().includes(query);
    const launchMatch = (group.launch_summary || '').toLowerCase().includes(query);
    const userMatch = (group.username || '').toLowerCase().includes(query);
    const titlesMatch = (group.window_titles || []).some(t => t.toLowerCase().includes(query));
    const subMatch = (group.subprocesses || []).some(sub => 
      (sub.name || '').toLowerCase().includes(query) ||
      String(sub.pid || '').includes(query) ||
      (sub.username || '').toLowerCase().includes(query) ||
      (sub.launch_summary || '').toLowerCase().includes(query) ||
      (sub.command_line || '').toLowerCase().includes(query) ||
      (sub.parent_name || '').toLowerCase().includes(query) ||
      (sub.real_parent || '').toLowerCase().includes(query)
    );
    return nameMatch || friendlyMatch || pidMatch || titlesMatch || subMatch || realParentMatch || launchMatch || userMatch;
  }

  const filteredApps = (currentCategoryFilter === 'all' || currentCategoryFilter === 'app') ? apps.filter(filterGroup) : [];
  const filteredBg = (currentCategoryFilter === 'all' || currentCategoryFilter === 'background') ? bg.filter(filterGroup) : [];
  const filteredWin = (currentCategoryFilter === 'all' || currentCategoryFilter === 'windows') ? win.filter(filterGroup) : [];

  const totalShown = filteredApps.length + filteredBg.length + filteredWin.length;
  if (badge) {
    badge.textContent = `${totalShown} групп (${pmReport.total_processes || totalShown} процессов)`;
  }

  if (totalShown === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-muted);">Процессы не найдены</td></tr>';
    return;
  }

  let html = '';

  if (filteredApps.length > 0) {
    html += renderCategorySectionHeader('Apps', 'Приложения с окнами (Apps)', filteredApps.length, 'primary', 'bi-window-stack');
    html += filteredApps.map((g, idx) => renderProcessGroupRow(g, `app-${idx}`, 'app')).join('');
  }

  if (filteredBg.length > 0) {
    html += renderCategorySectionHeader('Background', 'Фоновые процессы (Background processes)', filteredBg.length, 'info', 'bi-gear-wide-connected');
    html += filteredBg.map((g, idx) => renderProcessGroupRow(g, `bg-${idx}`, 'background')).join('');
  }

  if (filteredWin.length > 0) {
    html += renderCategorySectionHeader('Windows', 'Процессы Windows (Windows processes)', filteredWin.length, 'warning', 'bi-microsoft');
    html += filteredWin.map((g, idx) => renderProcessGroupRow(g, `win-${idx}`, 'windows')).join('');
  }

  tbody.innerHTML = html;
  bindProcessManagerEvents();
  initTableSmartTooltips(tbody);
}

/**
 * Отрисовывает заголовок категории процессов.
 */
function renderCategorySectionHeader(key, title, count, color, icon) {
  return `
    <tr class="table-active" style="background: var(--surface-2); border-bottom: 2px solid var(--border-color);">
      <td colspan="7" class="py-1 px-3">
        <span class="badge bg-${color}-subtle text-${color} border border-${color} me-2 font-monospace">
          <i class="bi ${icon} me-1"></i>${key}
        </span>
        <span class="fw-bold" style="color: var(--text-color); font-size: 0.85rem;">${title}</span>
        <span class="text-muted small ms-2">(${count})</span>
      </td>
    </tr>
  `;
}

/**
 * Отрисовывает строку группы процессов и ее подпроцессы.
 */
function renderProcessGroupRow(group, groupKey, category) {
  const isExpanded = allExpanded || expandedGroups.has(groupKey);
  const subCount = group.instance_count || (group.subprocesses ? group.subprocesses.length : 1);
  const hasSubs = group.subprocesses && group.subprocesses.length > 1;

  const cpu = group.total_cpu_percent !== undefined ? group.total_cpu_percent : 0;
  const cpuClass = cpu > 10 ? 'badge-cpu-high' : cpu > 2 ? 'badge-cpu-med' : 'text-light';
  const memMb = group.total_memory_mb || 0;
  const memStr = memMb >= 1024 ? `${(memMb / 1024).toFixed(1)} GB` : `${Math.round(memMb)} MB`;

  const title = group.friendly_name || group.name;
  const subLabel = group.friendly_name ? group.name : '';
  const mainPid = group.main_pid || (group.subprocesses && group.subprocesses[0] ? group.subprocesses[0].pid : '-');

  const firstSub = group.subprocesses && group.subprocesses[0] ? group.subprocesses[0] : null;
  const userStr = (group.username || (firstSub && firstSub.username) || 'SYSTEM').replace(/^.*\\/, '');
  const startTimeStr = (firstSub && firstSub.create_time) ? firstSub.create_time : (group.create_time || '--:--:--');

  const tooltipAttrs = getProcessTooltipAttributes(group.name, mainPid, title);
  const aiBadge = renderAIBadge(group.name);

  let row = `
    <tr class="pm-group-header" data-group-key="${groupKey}" ${tooltipAttrs} style="cursor: pointer;">
      <td class="text-center no-modal-trigger" style="width: 36px;" onclick="event.stopPropagation();">
        <button type="button" class="btn btn-xs btn-outline-info pm-btn-drilldown" data-pid="${mainPid}" title="Drill-Down: 🔬 Process Intelligence Deep Dive (7 виджетов)">
          <img src="/html/assets/red_drill.png?v=20261015_v2" alt="Drill-down" style="width: 14px; height: 14px; vertical-align: middle;">
        </button>
      </td>
      <td class="text-truncate" style="max-width: 320px;">
        <div class="d-flex align-items-center">
          <span class="pm-chevron ${isExpanded ? 'expanded' : ''}" style="display: ${hasSubs ? 'inline-block' : 'none'};">
            <i class="bi bi-chevron-right"></i>
          </span>
          <span class="me-2">${category === 'app' ? '🪟' : category === 'windows' ? '⚙️' : '📦'}</span>
          <div class="text-truncate">
            <strong class="text-light">${escapeHtml(title)}</strong>
            ${aiBadge}
            ${subCount > 1 ? `<span class="badge bg-secondary ms-1.5" style="font-size: 0.72rem;">${subCount}</span>` : ''}
            ${subLabel ? `<div class="small text-muted font-monospace text-truncate">${escapeHtml(subLabel)}</div>` : ''}
          </div>
        </div>
      </td>
      <td class="font-monospace text-info">${mainPid}</td>
      <td>
        <div class="small text-light font-monospace text-truncate" style="max-width: 180px;">${escapeHtml(userStr)}</div>
        <div class="small text-muted font-monospace" style="font-size: 0.72rem;">🕒 ${escapeHtml(startTimeStr)}</div>
      </td>
      <td>
        <span class="badge bg-dark border border-secondary text-info">${escapeHtml(category)}</span>
      </td>
      <td class="text-end font-monospace ${cpuClass}">${cpu.toFixed(1)}%</td>
      <td class="text-end font-monospace text-light">${memStr}</td>
      <td class="text-end" onclick="event.stopPropagation();">
        <button type="button" class="btn btn-xs btn-outline-danger pm-btn-kill" data-pid="${mainPid}" data-name="${escapeHtml(title)}" data-is-group="true" title="Завершить дерево процессов">
          <i class="bi bi-x-circle"></i>
        </button>
      </td>
    </tr>
  `;

  if (hasSubs && isExpanded) {
    group.subprocesses.forEach((sub, sIdx) => {
      const subCpu = sub.cpu_percent !== undefined ? sub.cpu_percent : 0;
      const subMem = sub.memory_mb || 0;
      const subMemStr = subMem >= 1024 ? `${(subMem / 1024).toFixed(1)} GB` : `${Math.round(subMem)} MB`;
      const subUser = (sub.username || userStr).replace(/^.*\\/, '');
      const subStart = sub.create_time || startTimeStr;

      const subTooltipAttrs = getProcessTooltipAttributes(sub.name, sub.pid, sub.name);
      const subAiBadge = renderAIBadge(sub.name);

      row += `
        <tr class="pm-sub-row" data-sub-idx="${sIdx}" data-parent-key="${groupKey}" ${subTooltipAttrs} style="cursor: pointer;">
          <td class="text-center no-modal-trigger" style="width: 36px;" onclick="event.stopPropagation();">
            <button type="button" class="btn btn-xs btn-outline-info pm-btn-drilldown" data-pid="${sub.pid}" title="Drill-Down: 🔬 Process Intelligence Deep Dive">
              <img src="/html/assets/red_drill.png?v=20261015_v2" alt="Drill-down" style="width: 14px; height: 14px; vertical-align: middle;">
            </button>
          </td>
          <td class="ps-4 text-truncate" style="max-width: 320px;">
            <div class="d-flex align-items-center">
              <i class="bi bi-arrow-return-right text-muted me-2"></i>
              <div class="text-truncate">
                <span class="text-light">${escapeHtml(sub.name)}</span>
                ${subAiBadge}
                ${sub.window_title ? `<div class="small text-info text-truncate">🪟 ${escapeHtml(sub.window_title)}</div>` : ''}
              </div>
            </div>
          </td>
          <td class="font-monospace text-muted">${sub.pid}</td>
          <td>
            <div class="small text-muted font-monospace text-truncate">${escapeHtml(subUser)}</div>
            <div class="small text-muted font-monospace" style="font-size: 0.70rem;">🕒 ${escapeHtml(subStart)}</div>
          </td>
          <td><span class="badge bg-secondary" style="font-size: 0.70rem;">Подпроцесс</span></td>
          <td class="text-end font-monospace text-muted">${subCpu.toFixed(1)}%</td>
          <td class="text-end font-monospace text-muted">${subMemStr}</td>
          <td class="text-end" onclick="event.stopPropagation();">
            <button type="button" class="btn btn-xs btn-outline-danger pm-btn-kill" data-pid="${sub.pid}" data-name="${escapeHtml(sub.name)}" data-is-group="false" title="Завершить подпроцесс">
              <i class="bi bi-x"></i>
            </button>
          </td>
        </tr>
      `;
    });
  }

  return row;
}

/**
 * Привязывает события кликов к строкам, шевронам, кнопкам Drill-Down и Kill.
 */
function bindProcessManagerEvents() {
  const tbody = document.getElementById('pm-tbody');
  if (!tbody) return;

  tbody.querySelectorAll('.pm-group-header').forEach(tr => {
    tr.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;

      if (e.target.closest('.pm-chevron')) {
        const key = tr.getAttribute('data-group-key');
        if (!key) return;
        if (expandedGroups.has(key)) {
          expandedGroups.delete(key);
        } else {
          expandedGroups.add(key);
        }
        applyProcessFilters();
        return;
      }

      const key = tr.getAttribute('data-group-key');
      const group = findGroupByCompoundKey(key);
      if (group) openProcessAiModal(group, 'group', null, killProcess);
    });
  });

  tbody.querySelectorAll('.pm-sub-row').forEach(tr => {
    tr.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;
      const parentKey = tr.getAttribute('data-parent-key');
      const sIdx = parseInt(tr.getAttribute('data-sub-idx'), 10);
      const group = findGroupByCompoundKey(parentKey);
      if (group && group.subprocesses && group.subprocesses[sIdx]) {
        openProcessAiModal(group.subprocesses[sIdx], 'sub', group, killProcess);
      }
    });
  });

  tbody.querySelectorAll('.pm-btn-drilldown').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetBtn = e.target.closest('.pm-btn-drilldown') || btn;
      const pid = parseInt(targetBtn.getAttribute('data-pid'), 10);
      if (pid && onDrillDownCallback) {
        onDrillDownCallback(pid);
      }
    });
  });

  tbody.querySelectorAll('.pm-btn-kill').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const pid = btn.getAttribute('data-pid');
      const name = btn.getAttribute('data-name');
      const isGroup = btn.getAttribute('data-is-group') === 'true';
      killProcess(pid, name, isGroup);
    });
  });
}

/**
 * Ищет группу по составному ключу (app-0, bg-2, win-1).
 */
function findGroupByCompoundKey(key) {
  if (!pmReport || !key) return null;
  const parts = key.split('-');
  const cat = parts[0];
  const idx = parseInt(parts[1], 10);
  if (cat === 'app') return (pmReport.apps || [])[idx];
  if (cat === 'bg') return (pmReport.background_processes || [])[idx];
  if (cat === 'win') return (pmReport.windows_processes || [])[idx];
  return null;
}

/**
 * Переключает раскрытие/сворачивание всех групп процессов.
 */
export function toggleAllGroups() {
  allExpanded = !allExpanded;
  const btnText = document.getElementById('pm-expand-btn-text');
  if (btnText) {
    btnText.textContent = allExpanded ? 'Свернуть все' : 'Развернуть все';
  }
  expandedGroups.clear();
  applyProcessFilters();
}

/**
 * Устанавливает фильтр категории (all, app, background, windows).
 */
export function setCategoryFilter(cat) {
  currentCategoryFilter = cat;
  const radio = document.querySelector(`input[name="pm-cat-filter"][value="${cat}"]`);
  if (radio) radio.checked = true;
  applyProcessFilters();
}

/**
 * Завершает процесс или дерево процессов с подтверждением пользователя.
 * @param {number|string} pid - Идентификатор процесса.
 * @param {string} name - Имя процесса.
 * @param {boolean} [killTree=false] - Флаг завершения всего дерева.
 */
export async function killProcess(pid, name, killTree = false) {
  const treeMsg = killTree ? ' (и все дочерние процессы)' : '';
  if (!confirm(`Вы действительно хотите завершить ${name} [PID: ${pid}]${treeMsg}?`)) return;

  try {
    const res = await fetch('/api/v1/tab-processes-load-inspector/panel-process-manager/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid: parseInt(pid, 10), kill_tree: killTree, dry_run: false, confirmed_by_user: true })
    });
    const result = await res.json();
    if (res.ok && result.status === 'SUCCESS') {
      showToast(`Процесс ${name} (PID: ${pid}) завершен`, 'success');
      fetchProcessManagerSummary();
      if (onRefreshTopCallback) onRefreshTopCallback();
    } else {
      showToast(result.message || result.detail || 'Отказано в доступе', 'danger');
    }
  } catch (err) {
    showToast(err.message, 'danger');
  }
}
