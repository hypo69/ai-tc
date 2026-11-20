/**
 * =============================================================================
 * Название: Панель журнала событий безопасности Windows (Security Log)
 * =============================================================================
 * Описание:
 *   Мониторинг событий безопасности Windows EventLog (аутентификация 4624/4625,
 *   изменение учетных записей и групп, пароли 4723/4724, блокировки 4740).
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_security_events/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let _eventsCache = [];
let _currentEventFilter = 'all';

export function getEventsCache() {
  return _eventsCache;
}

export function getCurrentEventFilter() {
  return _currentEventFilter;
}

export function setCurrentEventFilter(filter) {
  _currentEventFilter = filter || 'all';
}

/**
 * Загрузка журнала событий аудита безопасности.
 */
export async function loadSecurityEvents() {
  const tbody = document.getElementById('winadmin-events-tbody');
  const badge = document.getElementById('winadmin-events-badge');

  try {
    const res = await fetch('/api/v1/windows/identity/audit?limit=100');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _eventsCache = await res.json();

    if (badge) badge.innerText = `${_eventsCache.length} записей`;
    applyEventsFilter();
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4">Ошибка загрузки журнала безопасности: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Применение фильтров категорий и поискового запроса к событиям.
 */
export function applyEventsFilter() {
  const q = (document.getElementById('filter-events-input')?.value || '').toLowerCase().trim();
  let filtered = _eventsCache;

  if (_currentEventFilter === 'logon') {
    filtered = filtered.filter(e => [4624, 4625].includes(e.event_id));
  } else if (_currentEventFilter === 'accounts') {
    filtered = filtered.filter(e => [4720, 4722, 4725, 4726, 4731, 4732, 4733, 4734, 4735, 4738].includes(e.event_id));
  } else if (_currentEventFilter === 'password') {
    filtered = filtered.filter(e => [4723, 4724].includes(e.event_id));
  } else if (_currentEventFilter === 'lockout') {
    filtered = filtered.filter(e => e.event_id === 4740);
  }

  if (q) {
    filtered = filtered.filter(e =>
      String(e.event_id).includes(q) ||
      (e.event_name && e.event_name.toLowerCase().includes(q)) ||
      (e.target_account && e.target_account.toLowerCase().includes(q)) ||
      (e.caller_account && e.caller_account.toLowerCase().includes(q)) ||
      (e.description && e.description.toLowerCase().includes(q))
    );
  }

  renderEventsTable(filtered);
}

export function filterEventsTable() {
  applyEventsFilter();
}

/**
 * Отрисовка строк таблицы событий безопасности.
 * @param {Array} events - Список событий.
 */
export function renderEventsTable(events) {
  const tbody = document.getElementById('winadmin-events-tbody');
  if (!tbody) return;

  if (!events || events.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">События безопасности по выбранному фильтру не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = events.map((e, idx) => {
    let eidBadge = `<span class="ui-badge ui-badge-neutral font-monospace">${e.event_id}</span>`;
    if (e.event_id === 4624) {
      eidBadge = '<span class="ui-badge ui-badge-success font-monospace">4624</span>';
    } else if (e.event_id === 4625 || e.event_id === 4740 || e.event_id === 4726 || e.event_id === 4734) {
      eidBadge = `<span class="ui-badge ui-badge-danger font-monospace">${e.event_id}</span>`;
    } else if (e.event_id === 4724 || e.event_id === 4738) {
      eidBadge = `<span class="ui-badge ui-badge-warning font-monospace">${e.event_id}</span>`;
    } else if (e.event_id === 4720 || e.event_id === 4731 || e.event_id === 4732) {
      eidBadge = `<span class="ui-badge ui-badge-primary font-monospace">${e.event_id}</span>`;
    }

    const shortTime = e.timestamp ? e.timestamp.replace('T', ' ').slice(0, 19) : '—';
    const descText = e.description ? escapeHtml(e.description) : '—';

    return `
      <tr class="event-log-row" data-idx="${idx}" style="cursor: pointer;" onclick="window._showEventDetail(${idx})" title="Нажмите для просмотра полной информации">
        <td class="font-monospace text-muted small">${escapeHtml(shortTime)}</td>
        <td>${eidBadge}</td>
        <td class="fw-semibold text-primary">${escapeHtml(e.event_name || '')}</td>
        <td class="fw-bold text-body">${escapeHtml(e.target_account || '—')}</td>
        <td class="text-muted small">${escapeHtml(e.caller_account || '—')}</td>
        <td class="small text-truncate" style="max-width: 320px;" title="${descText}">${descText}</td>
        <td style="text-align: right;">
          <button class="btn btn-xs btn-outline-info py-0 px-2" onclick="event.stopPropagation(); window._showEventDetail(${idx})" title="Подробнее">
            Инфо
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Открытие модального окна подробностей события безопасности.
 * @param {number} idx - Индекс события в кеше.
 */
export function showEventDetail(idx) {
  const event = _eventsCache[idx];
  if (!event) return;

  const modal = window.AIModalDialog || window.AITableModal || (window.parent && (window.parent.AIModalDialog || window.parent.AITableModal));
  if (modal) {
    modal.show({
      icon: '🛡️',
      title: `Событие аудита: #${event.event_id} - ${event.event_name}`,
      subtitle: `Время: ${event.timestamp} | Целевой аккаунт: ${event.target_account || 'N/A'}`,
      panelId: 'panel-winadmin-audit',
      tableType: 'security_event',
      badges: [
        { text: `Event ${event.event_id}`, class: 'ui-badge ui-badge-primary font-monospace' },
        { text: event.event_name, class: 'ui-badge ui-badge-info' }
      ],
      metadata: [
        { label: 'Event ID', value: String(event.event_id) },
        { label: 'Событие', value: event.event_name },
        { label: 'Время регистрации', value: event.timestamp },
        { label: 'Целевая учетная запись', value: event.target_account || '—' },
        { label: 'Инициатор (Caller)', value: event.caller_account || '—' },
        { label: 'Статус аудита', value: event.status || 'Success' }
      ],
      rawTitle: 'Полное сообщение журнала безопасности',
      rawContent: event.description || '',
      requestData: {
        event_id: event.event_id,
        event_name: event.event_name,
        target_account: event.target_account,
        caller_account: event.caller_account,
        description: event.description
      }
    });
  } else {
    alert(`Событие #${event.event_id} (${event.event_name})\n\nВремя: ${event.timestamp}\nЦелевой аккаунт: ${event.target_account}\nИнициатор: ${event.caller_account}\n\nОписание:\n${event.description}`);
  }
}
