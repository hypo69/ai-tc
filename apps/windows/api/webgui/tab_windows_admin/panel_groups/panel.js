/**
 * =============================================================================
 * Название: Панель групп безопасности Windows
 * =============================================================================
 * Описание:
 *   Загрузка локальных групп безопасности, фильтрация по имени и SID,
 *   отображение счетчиков членов и модальное окно управления участниками
 *   (добавление и исключение пользователей из группы безопасности).
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_groups/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let _groupsCache = [];
let _usersCache = [];
let _activeModalGroupName = '';
let _groupsEventsBound = false;

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
    const res = await fetch('/api/v1/windows/identity/groups');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _groupsCache = await res.json();

    if (badge) badge.innerText = `${_groupsCache.length} групп`;
    const filterInput = document.getElementById('filter-groups-input');
    const currentQuery = filterInput ? filterInput.value : '';
    if (currentQuery && currentQuery.trim()) {
      filterGroupsTable(currentQuery);
    } else {
      renderGroupsTable(_groupsCache);
    }
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
    const safeName = escapeHtml(g.name);
    return `
      <tr class="winadmin-group-row" data-group-name="${safeName}" title="Нажмите, чтобы открыть управление участниками группы ${safeName}">
        <td class="fw-bold"><i class="bi bi-shield me-1 text-primary"></i> ${safeName}</td>
        <td><code class="small text-muted">${escapeHtml(g.sid || '—')}</code></td>
        <td class="text-muted small">${escapeHtml(g.description || '—')}</td>
        <td>${typeBadge}</td>
        <td><span class="ui-badge ui-badge-neutral">${membersCount} уч.</span></td>
        <td style="text-align: right;">
          <button class="btn btn-xs btn-outline-info py-0 px-2 btn-group-members-open" type="button" data-group-name="${safeName}" onmouseenter="window._handleGroupRollover(this, this.getAttribute('data-group-name'))" title="Участники и добавление пользователей">
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
    const group = _groupsCache.find(g => g.name.toLowerCase() === groupName.toLowerCase());
    if (group && Array.isArray(group.members)) {
      members = group.members;
    } else {
      const res = await fetch(`/api/v1/windows/identity/groups/${encodeURIComponent(groupName)}`);
      if (res.ok) {
        const data = await res.json();
        members = Array.isArray(data.members) ? data.members : [];
      }
    }
    const memberNames = members.length > 0 ? members.join(', ') : 'Нет участников';
    if (btnElement) {
      btnElement.setAttribute('title', `Участники: ${memberNames}`);
    }
  } catch (e) {
    console.debug('[WinAdminTab] Ошибка получения участников группы:', e);
  }
}

/**
 * Показывает статусный баннер в модальном окне управления участниками группы.
 * @param {string} message - Текст сообщения.
 * @param {'success'|'danger'|'warning'|'info'} [type='info'] - Тип уведомления.
 */
function setGroupModalFeedback(message, type = 'info') {
  const box = document.getElementById('group-members-feedback');
  if (!box) return;
  if (!message) {
    box.style.display = 'none';
    box.innerHTML = '';
    return;
  }
  box.className = `mt-2 small alert alert-${type} py-1.5 px-2.5 mb-0`;
  box.textContent = message;
  box.style.display = 'block';
}

/**
 * Загружает список локальных пользователей Windows для выпадающего списка в модальном окне.
 * @returns {Promise<Array>} Список учетных записей пользователей.
 */
async function loadUsersForGroupModal() {
  try {
    const res = await fetch('/api/v1/windows/identity/users');
    if (res.ok) {
      _usersCache = await res.json();
    }
  } catch (e) {
    console.debug('[WinAdminTab] Не удалось загрузить список пользователей для модального окна групп:', e);
  }
  return _usersCache;
}

/**
 * Заполняет выпадающий список локальных пользователей с отметкой уже состоящих в группе.
 * @param {Array<string>} currentMembers - Текущие участники выбранной группы.
 */
function populateUserSelect(currentMembers = []) {
  const select = document.getElementById('group-add-user-select');
  if (!select) return;

  const normalizedMembers = new Set(
    currentMembers.map(m => String(m || '').toLowerCase().split('\\').pop())
  );

  const options = ['<option value="">— Выберите локального пользователя —</option>'];
  for (const user of _usersCache) {
    const name = user.name || user.username || '';
    if (!name) continue;
    const isMember = normalizedMembers.has(name.toLowerCase());
    const statusNote = isMember ? ' (уже в группе)' : (user.enabled === false ? ' (отключен)' : '');
    options.push(
      `<option value="${escapeHtml(name)}" ${isMember ? 'disabled' : ''}>${escapeHtml(name)}${escapeHtml(statusNote)}</option>`
    );
  }
  select.innerHTML = options.join('');
}

/**
 * Заполняет выпадающий список групп безопасности в модальном окне.
 * @param {string} [selectedGroupName] - Имя группы, которую нужно выбрать.
 */
function populateGroupSelect(selectedGroupName) {
  const select = document.getElementById('group-members-select');
  if (!select) return;

  if (!_groupsCache.length) {
    select.innerHTML = '<option value="">Группы не найдены</option>';
    return;
  }

  select.innerHTML = _groupsCache.map(g => {
    const suffix = g.is_admin ? ' [ADMIN]' : '';
    const count = (g.members || []).length;
    return `<option value="${escapeHtml(g.name)}">${escapeHtml(g.name)}${suffix} (${count} уч.)</option>`;
  }).join('');

  if (selectedGroupName) {
    const match = _groupsCache.find(g => g.name.toLowerCase() === selectedGroupName.toLowerCase());
    if (match) {
      select.value = match.name;
      _activeModalGroupName = match.name;
      return;
    }
  }
  _activeModalGroupName = _groupsCache[0].name;
  select.value = _activeModalGroupName;
}

/**
 * Отрисовывает данные и таблицу участников выбранной группы в модальном окне.
 * @param {string} groupName - Имя группы безопасности.
 * @param {boolean} [fetchFresh=true] - Запрашивать ли свежие данные с сервера.
 */
async function renderGroupModalDetails(groupName, fetchFresh = true) {
  const sidEl = document.getElementById('group-modal-sid');
  const typeEl = document.getElementById('group-modal-type');
  const countEl = document.getElementById('group-modal-members-count');
  const descEl = document.getElementById('group-modal-description');
  const tbody = document.getElementById('group-members-tbody');

  if (!groupName) {
    if (tbody) tbody.innerHTML = '<tr><td class="text-center text-muted py-3" colspan="2">Выберите группу безопасности</td></tr>';
    return;
  }

  _activeModalGroupName = groupName;
  let group = _groupsCache.find(g => g.name.toLowerCase() === groupName.toLowerCase()) || null;

  if (fetchFresh) {
    if (tbody) {
      tbody.innerHTML = '<tr><td class="text-center text-muted py-3" colspan="2"><div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>Загрузка участников...</td></tr>';
    }
    try {
      const res = await fetch(`/api/v1/windows/identity/groups/${encodeURIComponent(groupName)}`);
      if (res.ok) {
        group = await res.json();
        const idx = _groupsCache.findIndex(g => g.name.toLowerCase() === groupName.toLowerCase());
        if (idx >= 0) {
          _groupsCache[idx] = group;
        }
      }
    } catch (e) {
      console.debug('[WinAdminTab] Не удалось обновить данные группы:', e);
    }
  }

  if (!group) {
    if (tbody) tbody.innerHTML = `<tr><td class="text-center text-danger py-3" colspan="2">Группа «${escapeHtml(groupName)}» не найдена</td></tr>`;
    return;
  }

  const members = Array.isArray(group.members) ? group.members : [];
  if (sidEl) {
    sidEl.textContent = group.sid || '—';
    sidEl.title = group.sid || '—';
  }
  if (typeEl) {
    typeEl.innerHTML = group.is_admin
      ? '<span class="ui-badge ui-badge-danger">ADMIN GROUP</span>'
      : '<span class="ui-badge ui-badge-neutral">Локальная</span>';
  }
  if (countEl) {
    countEl.textContent = `${members.length} уч.`;
  }
  if (descEl) {
    descEl.textContent = group.description || 'Описание отсутствует';
  }

  populateUserSelect(members);

  if (!tbody) return;
  if (members.length === 0) {
    tbody.innerHTML = '<tr><td class="text-center text-muted py-3" colspan="2">В группе пока нет участников</td></tr>';
    return;
  }

  tbody.innerHTML = members.map(member => {
    const safeMember = escapeHtml(member);
    return `
      <tr>
        <td class="font-monospace"><i class="bi bi-person me-1 text-info"></i> ${safeMember}</td>
        <td style="text-align: right;">
          <button class="btn btn-xs btn-outline-danger py-0 px-2 btn-group-remove-member" type="button" data-member-name="${safeMember}" title="Исключить из группы">
            <i class="bi bi-person-dash me-1"></i>Удалить
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Открывает модальное окно управления участниками группы безопасности.
 * @param {string|null} [groupName=null] - Имя группы для предвыбора (опционально).
 */
export async function openGroupMembersModal(groupName = null) {
  const modalEl = document.getElementById('groupMembersModal');
  if (!modalEl) return;

  setGroupModalFeedback('');
  const userInput = document.getElementById('group-add-user-input');
  if (userInput) userInput.value = '';

  if (window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  if (!_groupsCache.length) {
    await loadGroups();
  }
  await loadUsersForGroupModal();

  const targetGroup = groupName || _activeModalGroupName || (_groupsCache[0] ? _groupsCache[0].name : '');
  populateGroupSelect(targetGroup);
  await renderGroupModalDetails(_activeModalGroupName, true);
}

/**
 * Обработчик добавления пользователя в выбранную группу безопасности.
 */
async function handleAddGroupMember() {
  const groupSelect = document.getElementById('group-members-select');
  const userSelect = document.getElementById('group-add-user-select');
  const userInput = document.getElementById('group-add-user-input');
  const addBtn = document.getElementById('btn-group-add-member');

  const groupName = (groupSelect ? groupSelect.value : _activeModalGroupName || '').trim();
  const username = ((userInput ? userInput.value : '') || (userSelect ? userSelect.value : '')).trim();

  if (!groupName) {
    setGroupModalFeedback('Выберите целевую группу безопасности.', 'warning');
    return;
  }
  if (!username) {
    setGroupModalFeedback('Выберите пользователя из списка или введите имя учетной записи.', 'warning');
    if (userInput) userInput.focus();
    return;
  }

  const originalHtml = addBtn ? addBtn.innerHTML : '';
  if (addBtn) {
    addBtn.disabled = true;
    addBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
  }
  setGroupModalFeedback('');

  try {
    const res = await fetch(`/api/v1/windows/identity/groups/${encodeURIComponent(groupName)}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    const msg = data.message || `Пользователь «${username}» добавлен в группу «${groupName}»`;
    setGroupModalFeedback(msg, 'success');
    if (window.toast && typeof window.toast.success === 'function') {
      window.toast.success('Группы безопасности', msg);
    }
    if (userInput) userInput.value = '';
    if (userSelect) userSelect.value = '';

    await loadGroups();
    populateGroupSelect(groupName);
    await renderGroupModalDetails(groupName, true);
  } catch (err) {
    const errMsg = `Не удалось добавить пользователя «${username}» в группу «${groupName}»: ${err.message}`;
    setGroupModalFeedback(errMsg, 'danger');
    if (window.toast && typeof window.toast.error === 'function') {
      window.toast.error('Ошибка добавления в группу', err.message);
    }
  } finally {
    if (addBtn) {
      addBtn.disabled = false;
      addBtn.innerHTML = originalHtml;
    }
  }
}

/**
 * Обработчик исключения пользователя из выбранной группы безопасности.
 * @param {string} memberName - Имя участника группы.
 */
async function handleRemoveGroupMember(memberName) {
  const groupSelect = document.getElementById('group-members-select');
  const groupName = (groupSelect ? groupSelect.value : _activeModalGroupName || '').trim();
  if (!groupName || !memberName) return;

  if (!window.confirm(`Исключить участника «${memberName}» из группы «${groupName}»?`)) {
    return;
  }

  setGroupModalFeedback('');
  try {
    const res = await fetch(
      `/api/v1/windows/identity/groups/${encodeURIComponent(groupName)}/members/${encodeURIComponent(memberName)}`,
      { method: 'DELETE' }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    const msg = data.message || `Участник «${memberName}» исключен из группы «${groupName}»`;
    setGroupModalFeedback(msg, 'success');
    if (window.toast && typeof window.toast.success === 'function') {
      window.toast.success('Группы безопасности', msg);
    }

    await loadGroups();
    populateGroupSelect(groupName);
    await renderGroupModalDetails(groupName, true);
  } catch (err) {
    const errMsg = `Не удалось исключить «${memberName}» из группы «${groupName}»: ${err.message}`;
    setGroupModalFeedback(errMsg, 'danger');
    if (window.toast && typeof window.toast.error === 'function') {
      window.toast.error('Ошибка исключения из группы', err.message);
    }
  }
}

/**
 * Просмотр и управление участниками группы в модальном окне.
 * @param {string} groupName - Имя группы.
 */
export function viewGroupMembers(groupName) {
  openGroupMembersModal(groupName);
}

/**
 * Привязка обработчиков кликов по панели групп безопасности и элементам модального окна.
 */
export function bindGroupsEvents() {
  if (_groupsEventsBound) return;
  _groupsEventsBound = true;

  const panel = document.getElementById('panel-winadmin-groups');
  if (panel) {
    panel.addEventListener('click', (e) => {
      // Игнорируем клики по полю поиска, кнопке 100%, ползунку растягивания и ссылкам
      if (e.target.closest('input, select, textarea, .input-group, .sys-table-resizer, .btn-table-expand-100, a')) {
        return;
      }

      const openBtn = e.target.closest('#btn-open-group-members-modal');
      if (openBtn) {
        e.stopPropagation();
        openGroupMembersModal(null);
        return;
      }

      const memberBtn = e.target.closest('.btn-group-members-open');
      if (memberBtn) {
        e.stopPropagation();
        openGroupMembersModal(memberBtn.getAttribute('data-group-name'));
        return;
      }

      const row = e.target.closest('tr[data-group-name]');
      if (row) {
        openGroupMembersModal(row.getAttribute('data-group-name'));
        return;
      }

      // Клик по самой панели (заголовок или пустая область) открывает модальное окно
      openGroupMembersModal(null);
    });
  }

  const groupSelect = document.getElementById('group-members-select');
  if (groupSelect) {
    groupSelect.addEventListener('change', (e) => {
      setGroupModalFeedback('');
      renderGroupModalDetails(e.target.value, true);
    });
  }

  const userSelect = document.getElementById('group-add-user-select');
  const userInput = document.getElementById('group-add-user-input');
  if (userSelect && userInput) {
    userSelect.addEventListener('change', () => {
      if (userSelect.value) {
        userInput.value = userSelect.value;
      }
    });
  }

  if (userInput) {
    userInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddGroupMember();
      }
    });
  }

  const addMemberBtn = document.getElementById('btn-group-add-member');
  if (addMemberBtn) {
    addMemberBtn.addEventListener('click', handleAddGroupMember);
  }

  const refreshBtn = document.getElementById('btn-group-members-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      setGroupModalFeedback('');
      await loadGroups();
      populateGroupSelect(_activeModalGroupName);
      await renderGroupModalDetails(_activeModalGroupName, true);
    });
  }

  const membersTbody = document.getElementById('group-members-tbody');
  if (membersTbody) {
    membersTbody.addEventListener('click', (e) => {
      const removeBtn = e.target.closest('.btn-group-remove-member');
      if (removeBtn) {
        handleRemoveGroupMember(removeBtn.getAttribute('data-member-name'));
      }
    });
  }
}
