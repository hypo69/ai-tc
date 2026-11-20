/**
 * @file apps/windows/api/webgui/tab_process_manager/panel_table/panel.js
 * @description Панель отображения и группировки процессов Task Manager (приложения, фоновые, системные)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Отрисовка таблицы процессов с разделением по категориям (Apps, Background, Windows)
 * @param {Object} report Данные сводки процессов
 * @param {string} categoryFilter Фильтр категории ('all', 'app', 'background', 'windows')
 * @param {string} searchTerm Поисковый запрос
 * @param {boolean} allExpanded Флаг развертывания всех групп
 * @param {Set<string>} expandedGroups Множество ID развернутых групп
 * @param {Function} onAiModal Callback вызова модального окна ИИ
 * @param {Function} onKill Callback завершения процесса
 * @param {Function} onToggleGroup Callback переключения шеврона группы
 */
export function renderProcessTable(report, categoryFilter, searchTerm, allExpanded, expandedGroups, onAiModal, onKill, onToggleGroup) {
  const tbody = document.getElementById('pm-process-tbody');
  if (!tbody) return;

  if (!report) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Данные процессов не загружены</td></tr>';
    return;
  }

  const apps = report.apps || [];
  const bg = report.background_processes || [];
  const win = report.windows_processes || [];

  const filterList = (list) => {
    return list.filter(item => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      const inName = item.name && item.name.toLowerCase().includes(term);
      const inFriendly = item.friendly_name && item.friendly_name.toLowerCase().includes(term);
      const inPid = item.main_pid && String(item.main_pid).includes(term);
      const inUser = item.username && item.username.toLowerCase().includes(term);
      const inSub = item.subprocesses && item.subprocesses.some(s =>
        (s.name && s.name.toLowerCase().includes(term)) ||
        (s.pid && String(s.pid).includes(term)) ||
        (s.command_line && s.command_line.toLowerCase().includes(term)) ||
        (s.window_title && s.window_title.toLowerCase().includes(term)) ||
        (s.launch_summary && s.launch_summary.toLowerCase().includes(term))
      );
      return inName || inFriendly || inPid || inUser || inSub;
    });
  };

  const filteredApps = (categoryFilter === 'all' || categoryFilter === 'app') ? filterList(apps) : [];
  const filteredBg = (categoryFilter === 'all' || categoryFilter === 'background') ? filterList(bg) : [];
  const filteredWin = (categoryFilter === 'all' || categoryFilter === 'windows') ? filterList(win) : [];

  const totalCount = filteredApps.length + filteredBg.length + filteredWin.length;
  if (totalCount === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Нет процессов, соответствующих выбранным критериям поиска</td></tr>';
    return;
  }

  let html = '';

  if (filteredApps.length > 0) {
    html += `
      <tr class="table-active">
        <td colspan="7" class="py-2 px-3 fw-bold text-primary">
          <i class="bi bi-window-stack me-1.5"></i> Apps (${filteredApps.length})
        </td>
      </tr>
    `;
    html += filteredApps.map(g => renderGroupRow(g, 'app', 'App', allExpanded, expandedGroups)).join('');
  }

  if (filteredBg.length > 0) {
    html += `
      <tr class="table-active">
        <td colspan="7" class="py-2 px-3 fw-bold text-info">
          <i class="bi bi-gear-wide-connected me-1.5"></i> Background processes (${filteredBg.length})
        </td>
      </tr>
    `;
    html += filteredBg.map(g => renderGroupRow(g, 'background', 'Background process', allExpanded, expandedGroups)).join('');
  }

  if (filteredWin.length > 0) {
    html += `
      <tr class="table-active">
        <td colspan="7" class="py-2 px-3 fw-bold text-warning">
          <i class="bi bi-microsoft me-1.5"></i> Windows processes (${filteredWin.length})
        </td>
      </tr>
    `;
    html += filteredWin.map(g => renderGroupRow(g, 'windows', 'Windows process', allExpanded, expandedGroups)).join('');
  }

  tbody.innerHTML = html;
  attachEventListeners(tbody, expandedGroups, onToggleGroup, onAiModal, onKill);
}

/**
 * Рендеринг строки группы процессов (Task Manager style)
 */
function renderGroupRow(group, category, typeLabel, allExpanded, expandedGroups) {
  const groupId = `grp-${category}-${group.name.replace(/[^a-zA-Z0-9_-]/g, '_')}-${group.main_pid}`;
  const isExpanded = allExpanded || expandedGroups.has(groupId);
  const count = group.instance_count || (group.subprocesses ? group.subprocesses.length : 1);
  const countBadge = count > 1 ? ` <span class="text-muted small">(${count})</span>` : '';
  const chevron = count > 1 || (group.subprocesses && group.subprocesses.length > 0)
    ? `<i class="bi bi-chevron-right pm-chevron ${isExpanded ? 'expanded' : ''}" data-group-id="${groupId}"></i>`
    : `<span style="display:inline-block; width:20px;"></span>`;

  const memMb = group.total_memory_mb || 0;
  const memStr = memMb >= 1024 ? `${(memMb / 1024).toFixed(1)} GB` : `${Math.round(memMb)} MB`;
  const cpuStr = (group.total_cpu_percent !== undefined) ? `${group.total_cpu_percent.toFixed(1)}%` : '0.0%';

  const iconClass = category === 'app' ? 'bi-app-indicator text-primary' : (category === 'windows' ? 'bi-microsoft text-warning' : 'bi-cpu text-info');

  let groupBadges = '';
  if (group.is_pwa_or_electron) {
    groupBadges += `<span class="badge border border-info text-info small ms-1.5 py-0 px-1.5" title="Официальное настольное приложение / Chromium Electron PWA"><i class="bi bi-box-arrow-up-right me-1"></i>PWA / Electron</span>`;
  }
  if (group.real_parent_name && group.real_parent_name.toLowerCase() !== group.name.toLowerCase()) {
    groupBadges += `<span class="badge border border-secondary text-light small ms-1.5 py-0 px-1.5" title="Истинный родительский процесс"><i class="bi bi-diagram-3 me-1"></i>${escapeHtml(group.real_parent_name)}</span>`;
  }
  if (group.launch_summary && !group.is_pwa_or_electron) {
    groupBadges += `<span class="badge bg-secondary bg-opacity-50 text-info font-monospace small ms-1.5 py-0 px-1.5" title="Ключ/суть запуска"><i class="bi bi-terminal me-1"></i>${escapeHtml(group.launch_summary)}</span>`;
  }

  const cleanUser = group.username ? group.username.split('\\').pop() : '';
  const initiatorHtml = cleanUser || group.create_time ? `
    <div><i class="bi bi-person text-secondary me-1"></i><span class="text-light">${escapeHtml(cleanUser || 'SYSTEM')}</span></div>
    ${group.create_time ? `<div class="text-muted small">${escapeHtml(group.create_time.split(' ').pop())}</div>` : ''}
  ` : `<span class="text-muted">-</span>`;

  let subRowsHtml = '';
  if (isExpanded && group.subprocesses && group.subprocesses.length > 0) {
    subRowsHtml = group.subprocesses.map(sub => {
      const subMem = sub.memory_mb >= 1024 ? `${(sub.memory_mb / 1024).toFixed(1)} GB` : `${Math.round(sub.memory_mb)} MB`;
      const titleInfo = sub.window_title ? `<div class="text-light small mt-0.5 text-truncate" style="max-width: 420px;"><i class="bi bi-window text-secondary me-1"></i>${escapeHtml(sub.window_title)}</div>` : '';

      let launchBadge = '';
      if (sub.launch_summary) {
        launchBadge = `<span class="badge bg-secondary bg-opacity-75 text-info font-monospace ms-1.5 py-0 px-1.5" title="${escapeHtml(sub.command_line || sub.launch_summary)}"><i class="bi bi-terminal me-1"></i>${escapeHtml(sub.launch_summary)}</span>`;
      }

      let realParentBadge = '';
      if (sub.real_parent && sub.real_parent !== sub.name && (!group.is_pwa_or_electron || !sub.real_parent.includes('ChatGPT'))) {
        realParentBadge = `<span class="badge border border-info text-info small ms-1 py-0 px-1" title="Истинный родитель: ${escapeHtml(sub.real_parent)}"><i class="bi bi-diagram-3 me-0.5"></i>${escapeHtml(sub.real_parent)}</span>`;
      }

      const subUser = sub.username ? sub.username.split('\\').pop() : '';
      const ppidBadge = sub.ppid ? `<span class="text-secondary small font-monospace" title="PPID родительского процесса: ${sub.ppid}">[PPID: ${sub.ppid}]</span>` : '';
      const timeStr = sub.create_time ? sub.create_time.split(' ').pop() : '';
      const uptimeStr = sub.uptime_str ? ` <span class="text-secondary small">(${escapeHtml(sub.uptime_str)})</span>` : '';

      return `
        <tr class="pm-sub-row" data-parent-group="${groupId}" data-pid="${sub.pid}" data-name="${escapeHtml(sub.name)}" style="cursor: pointer;" title="Клик для вызова ИИ-помощника">
          <td class="ps-4 py-1.5">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <i class="bi bi-arrow-return-right text-muted small"></i>
              <div>
                <span class="text-light fw-medium">${escapeHtml(sub.name)}</span>
                ${launchBadge}
                ${realParentBadge}
                ${titleInfo}
              </div>
            </div>
          </td>
          <td class="font-monospace text-warning small py-1.5">${sub.pid}</td>
          <td class="py-1.5 small">
            <div><span class="text-light">${escapeHtml(subUser || 'SYSTEM')}</span> ${ppidBadge}</div>
            ${timeStr ? `<div class="text-muted small">${escapeHtml(timeStr)}${uptimeStr}</div>` : ''}
          </td>
          <td class="py-1.5"><span class="pm-type-tag text-muted">${typeLabel}</span></td>
          <td class="font-monospace text-light small py-1.5">${sub.cpu_percent.toFixed(1)}%</td>
          <td class="font-monospace text-info small py-1.5">${subMem}</td>
          <td class="text-end py-1.5" onclick="event.stopPropagation();">
            <button class="btn btn-xs btn-outline-danger py-0 px-1.5 pm-kill-btn" data-pid="${sub.pid}" data-name="${escapeHtml(sub.name)}" title="Завершить процесс PID: ${sub.pid}">
              <i class="bi bi-x"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  return `
    <tr class="pm-group-header" data-group-id="${groupId}" data-name="${escapeHtml(group.name)}" data-pid="${group.main_pid || ''}" style="cursor: pointer;" title="Клик по строке — ИИ-анализ, клик по стрелке — раскрыть группу">
      <td class="py-2">
        <div class="d-flex align-items-center flex-wrap gap-1">
          ${chevron}
          <i class="bi ${iconClass} me-1.5"></i>
          <span class="fw-semibold text-white">${escapeHtml(group.friendly_name || group.name)}</span>
          ${countBadge}
          ${groupBadges}
        </div>
      </td>
      <td class="font-monospace text-muted small py-2">${group.main_pid || '-'}</td>
      <td class="py-2 small">${initiatorHtml}</td>
      <td class="py-2"><span class="pm-type-tag">${typeLabel}</span></td>
      <td class="font-monospace text-light small py-2">${cpuStr}</td>
      <td class="font-monospace text-success small py-2">${memStr}</td>
      <td class="text-end py-2" onclick="event.stopPropagation();">
        <button class="btn btn-xs btn-outline-danger py-0 px-2 pm-kill-btn" data-pid="${group.main_pid}" data-name="${escapeHtml(group.name)}" data-tree="true" title="Завершить дерево процессов (${count})">
          <i class="bi bi-x-circle me-1"></i>Завершить
        </button>
      </td>
    </tr>
    ${subRowsHtml}
  `;
}

/**
 * Навешивание обработчиков событий на таблицу
 */
function attachEventListeners(tbody, expandedGroups, onToggleGroup, onAiModal, onKill) {
  tbody.querySelectorAll('.pm-group-header').forEach(header => {
    header.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;

      if (e.target.closest('.pm-chevron')) {
        const groupId = header.dataset.groupId;
        if (onToggleGroup) onToggleGroup(groupId);
        return;
      }

      const name = header.dataset.name;
      const pid = header.dataset.pid ? parseInt(header.dataset.pid, 10) : null;
      if (onAiModal) onAiModal('group', name, pid);
    });
  });

  tbody.querySelectorAll('.pm-sub-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;
      const name = row.dataset.name;
      const pid = row.dataset.pid ? parseInt(row.dataset.pid, 10) : null;
      if (onAiModal) onAiModal('sub', name, pid);
    });
  });

  tbody.querySelectorAll('.pm-kill-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const pid = btn.dataset.pid;
      const name = btn.dataset.name;
      const killTree = btn.dataset.tree === 'true';
      if (onKill) onKill(pid, name, killTree);
    });
  });
}

/**
 * Завершение процесса или дерева процессов через API
 * @param {number|string} pid PID процесса
 * @param {string} name Имя процесса
 * @param {boolean} killTree Флаг завершения всего дерева
 * @param {Function} onSuccess Callback при успешном завершении
 */
export async function killProcess(pid, name, killTree = false, onSuccess = null) {
  const treeMsg = killTree ? ' (и все дочерние процессы)' : '';
  if (!confirm(`Вы действительно хотите завершить ${name} [PID: ${pid}]${treeMsg}?`)) return;

  try {
    const res = await fetch('/api/v1/process-manager/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid: parseInt(pid, 10), kill_tree: killTree, dry_run: false, confirmed_by_user: true })
    });
    const result = await res.json();
    if (res.ok && result.status === 'SUCCESS') {
      if (window.toast) window.toast.success('Процесс завершен', `${name} (PID: ${pid})`);
      if (onSuccess) onSuccess();
    } else {
      if (window.toast) window.toast.error('Ошибка завершения', result.message || result.detail || 'Отказано в доступе');
    }
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка сети', err.message);
  }
}
