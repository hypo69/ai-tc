/**
 * =============================================================================
 * Название: Панель групп безопасности Windows
 * =============================================================================
 * Описание:
 *   Загрузка локальных групп безопасности, фильтрация по имени и SID,
 *   отображение счетчиков членов и всплывающий просмотр участников.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_groups/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-01 15:53:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let _groupsCache = [];

export function getGroupsCache() {
  return _groupsCache;
}

/**
 * Загрузка списка групп безопасности Windows.
 */
export async function loadGroups() {
  const tbody = document.getElementById('winadmin-groups-tbody');
  const badge = document.getElementById('winadmin-groups-badge');
  try {
    const res = await fetch('/api/windows/identity/groups');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _groupsCache = await res.json();

    if (badge) badge.innerText = `${_groupsCache.length} групп`;
    renderGroupsTable(_groupsCache);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Ошибка загрузки групп: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Отрисовка таблицы групп безопасности.
 * @param {Array} groups - Список групп.
 */
export function renderGroupsTable(groups) {
  const tbody = document.getElementById('winadmin-groups-tbody');
  if (!tbody) return;

  if (!groups || groups.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Группы безопасности не найдены</td></tr>';
    if (window.autoAdjustTableHeight) {
      window.autoAdjustTableHeight('winadmin-groups-table-container', 0);
    }
    return;
  }

  tbody.innerHTML = groups.map(g => {
    const typeBadge = g.is_admin
      ? '<span class="ui-badge ui-badge-danger">ADMIN GROUP</span>'
      : '<span class="ui-badge ui-badge-neutral">Локальная</span>';
    const membersCount = (g.members || []).length;
    return `
      <tr>
        <td class="fw-bold"><i class="bi bi-shield me-1 text-primary"></i> ${escapeHtml(g.name)}</td>
        <td><code class="small text-muted">${escapeHtml(g.sid || '—')}</code></td>
        <td class="text-muted small">${escapeHtml(g.description || '—')}</td>
        <td>${typeBadge}</td>
        <td><span class="ui-badge ui-badge-neutral">${membersCount} уч.</span></td>
        <td style="text-align: right;">
          <button class="btn btn-xs btn-outline-info py-0 px-2" onmouseenter="window._handleGroupRollover(this, '${escapeHtml(g.name)}')" onclick="window._viewGroupMembers('${escapeHtml(g.name)}')" title="Участники">
            Участники
          </button>
        </td>
      </tr>
    `;
  }).join('');

  if (window.autoAdjustTableHeight) {
    window.autoAdjustTableHeight('winadmin-groups-table-container', groups.length);
  }
}

/**
 * Фильтрация таблицы групп по поисковому запросу.
 * @param {string} query - Поисковая строка.
 */
export function filterGroupsTable(query) {
  const q = (query || '').toLowerCase().trim();
  if (!q) {
    renderGroupsTable(_groupsCache);
    return;
  }
  const filtered = _groupsCache.filter(g =>
    (g.name && g.name.toLowerCase().includes(q)) ||
    (g.sid && g.sid.toLowerCase().includes(q)) ||
    (g.description && g.description.toLowerCase().includes(q))
  );
  renderGroupsTable(filtered);
}

/**
 * Всплывающее уведомление и тултип со списком участников группы при наведении.
 * @param {HTMLElement} btnElement - Кнопка действия.
 * @param {string} groupName - Имя группы.
 */
export async function handleGroupRollover(btnElement, groupName) {
  if (!groupName) return;
  try {
    let members = [];
    const res = await fetch(`/api/v1/windows-users/groups/${encodeURIComponent(groupName)}/members`);
    if (res.ok) {
      const data = await res.json();
      members = Array.isArray(data) ? data : (data.members || []);
    } else {
      const group = _groupsCache.find(g => g.name.toLowerCase() === groupName.toLowerCase());
      members = group ? (group.members || []) : [];
    }
    const memberNames = members.length > 0 ? members.join(', ') : 'Нет участников';
    if (window.toast && typeof window.toast.info === 'function') {
      window.toast.info(`Группа: ${groupName}`, `Участники: ${memberNames}`);
    }
    if (btnElement) {
      btnElement.setAttribute('title', `Участники: ${memberNames}`);
    }
  } catch (e) {
    console.debug('[WinAdminTab] Ошибка получения участников группы:', e);
  }
}

/**
 * Просмотр полного списка участников группы в диалоге.
 * @param {string} groupName - Имя группы.
 */
export function viewGroupMembers(groupName) {
  const group = _groupsCache.find(g => g.name.toLowerCase() === groupName.toLowerCase());
  if (!group) return;
  const members = (group.members || []).join('\n') || 'Нет участников';
  alert(`Участники группы ${groupName}:\n\n${members}`);
}
