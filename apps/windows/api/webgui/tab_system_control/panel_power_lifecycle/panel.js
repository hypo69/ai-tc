/**
 * Модуль панели жизненного цикла питания и аптайма Windows (Power Lifecycle & Boot History).
 * 
 * Отвечает за мониторинг непрерывного аптайма, историю загрузок (Boot), штатные выключения,
 * перезагрузки, внезапные аварийные сбои питания (Kernel-Power 41 / 6008) и BSOD инциденты.
 * 
 * Updated: 2026-11-01 17:49:00
 */

import { escapeHtml, initTableResizers } from '../common/ui_utils.js';
import { showPowerSessionDetailModal, showPowerXmlModal } from './modals.js';

let allPowerSessions = [];
let allPowerEvents = [];
let powerUptimeSeconds = 0;
let powerUptimeInterval = null;
let isPowerInitialized = false;

/**
 * Получение всех сессий электропитания.
 * @returns {Array}
 */
export function getAllPowerSessions() {
  return allPowerSessions;
}

/**
 * Остановка таймера аптайма хоста.
 */
export function stopPowerUptimeCounter() {
  if (powerUptimeInterval) {
    clearInterval(powerUptimeInterval);
    powerUptimeInterval = null;
  }
}

/**
 * Запуск локального секундного таймера обновления строки аптайма в шапке панели.
 */
export function startPowerUptimeCounter() {
  stopPowerUptimeCounter();
  powerUptimeInterval = setInterval(() => {
    powerUptimeSeconds += 1;
    const curUptimeEl = document.getElementById('pwr-current-uptime');
    if (curUptimeEl && powerUptimeSeconds > 0) {
      const days = Math.floor(powerUptimeSeconds / 86400);
      const hours = Math.floor((powerUptimeSeconds % 86400) / 3600);
      const minutes = Math.floor((powerUptimeSeconds % 3600) / 60);
      const sec = Math.floor(powerUptimeSeconds % 60);
      const parts = [];
      if (days > 0) parts.push(`${days}д`);
      if (hours > 0 || days > 0) parts.push(`${hours}ч`);
      if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}м`);
      parts.push(`${sec}с`);
      curUptimeEl.textContent = parts.join(' ');
    }
  }, 1000);
}

/**
 * Рендеринг сводных метрик питания и текущего аптайма.
 * @param {Object} summary - Объект сводки питания.
 */
export function renderPowerSummary(summary) {
  if (!summary) return;

  const curBootEl = document.getElementById('pwr-current-boot');
  if (curBootEl) curBootEl.textContent = `Загрузка: ${summary.current_boot_time || '--'}`;

  const curUptimeEl = document.getElementById('pwr-current-uptime');
  if (curUptimeEl) {
    curUptimeEl.textContent = summary.current_uptime_human || '--';
    powerUptimeSeconds = summary.current_uptime_seconds || 0;
  }

  const totalSessionsEl = document.getElementById('pwr-total-sessions');
  if (totalSessionsEl) totalSessionsEl.textContent = summary.total_sessions_count;

  const totalBadge = document.getElementById('pwr-total-sessions-badge');
  if (totalBadge) totalBadge.textContent = `${summary.total_sessions_count} Сессий`;

  const cleanCountEl = document.getElementById('pwr-clean-count');
  if (cleanCountEl) cleanCountEl.textContent = summary.clean_shutdowns_count;

  const cleanRatioEl = document.getElementById('pwr-clean-ratio');
  if (cleanRatioEl) {
    const total = summary.total_sessions_count || 1;
    const ratio = Math.round((summary.clean_shutdowns_count / total) * 100);
    cleanRatioEl.textContent = `${ratio} %`;
  }

  const lastInitEl = document.getElementById('pwr-last-initiator');
  if (lastInitEl) {
    lastInitEl.textContent = `Инициатор: ${summary.last_initiator || 'Штатный'}`;
  }

  const unexpCountEl = document.getElementById('pwr-unexpected-count');
  if (unexpCountEl) unexpCountEl.textContent = summary.unexpected_shutdowns_count;

  const unexpBadge = document.getElementById('pwr-unexpected-badge');
  if (unexpBadge) {
    unexpBadge.textContent = `${summary.unexpected_shutdowns_count} Сбоев`;
    if (summary.unexpected_shutdowns_count > 0) {
      unexpBadge.className = 'badge bg-danger font-monospace';
    } else {
      unexpBadge.className = 'badge bg-success font-monospace';
    }
  }

  const bsodEl = document.getElementById('pwr-bsod-count');
  if (bsodEl) bsodEl.textContent = `BSOD (1001): ${summary.bsod_count || 0}`;
}

/**
 * Фильтрация и рендеринг таблицы сессий питания.
 */
export function filterAndRenderPowerSessions() {
  const tbody = document.getElementById('pwr-sessions-tbody');
  const counter = document.getElementById('pwr-sessions-counter');
  if (!tbody) return;

  const searchVal = (document.getElementById('pwr-sessions-search')?.value || '').toLowerCase().trim();
  const typeFilter = document.getElementById('pwr-filter-type')?.value || '';
  const unexpOnly = document.getElementById('pwr-filter-unexpected-only')?.checked || false;

  const filtered = allPowerSessions.filter(s => {
    if (unexpOnly && !s.unexpected_shutdown) return false;
    if (typeFilter) {
      if (typeFilter === 'Active' && s.shutdown_type !== 'Active') return false;
      if (typeFilter === 'Restart' && s.shutdown_type !== 'Restart') return false;
      if (typeFilter === 'Shutdown' && s.shutdown_type !== 'Shutdown' && s.shutdown_type !== 'PowerOff') return false;
      if (typeFilter === 'Unexpected' && !s.unexpected_shutdown) return false;
      if (typeFilter === 'BSOD' && s.shutdown_type !== 'BSOD' && !s.bugcheck) return false;
    }

    if (searchVal) {
      const init = (s.initiator || '').toLowerCase();
      const proc = (s.process || '').toLowerCase();
      const reason = (s.reason || '').toLowerCase();
      const code = (s.reason_code || '').toLowerCase();
      const sId = (s.session_id || '').toLowerCase();
      if (!init.includes(searchVal) && !proc.includes(searchVal) && !reason.includes(searchVal) && !code.includes(searchVal) && !sId.includes(searchVal)) {
        return false;
      }
    }
    return true;
  });

  if (counter) counter.textContent = `Найдено: ${filtered.length}`;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center py-4 text-muted">
          Сессии питания, удовлетворяющие критериям фильтрации, не найдены.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(s => {
    let statusBadge = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">Неизвестно</span>';
    if (s.shutdown_type === 'Active') {
      statusBadge = '<span class="badge bg-success-subtle text-success border border-success-subtle">🟢 Активная</span>';
    } else if (s.shutdown_type === 'Restart') {
      statusBadge = '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">↻ Перезагрузка</span>';
    } else if (s.shutdown_type === 'Shutdown' || s.shutdown_type === 'PowerOff') {
      statusBadge = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">⏻ Выключение</span>';
    } else if (s.shutdown_type === 'BSOD' || s.bugcheck) {
      statusBadge = `<span class="badge bg-danger text-white">🚨 BSOD ${escapeHtml(s.bugcheck || '')}</span>`;
    } else if (s.unexpected_shutdown) {
      statusBadge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">⚠️ Сбой / 41</span>';
    }

    let initiatorHtml = '<span class="text-muted">--</span>';
    if (s.initiator || s.process) {
      const initName = s.initiator ? `<span class="fw-semibold text-primary">${escapeHtml(s.initiator)}</span>` : '';
      const procName = s.process ? `<span class="badge pwr-proc-badge font-monospace ms-1 text-truncate" style="max-width: 260px;" title="${escapeHtml(s.process)}">${escapeHtml(s.process)}</span>` : '';
      initiatorHtml = `<div class="d-flex align-items-center flex-wrap">${initName} ${procName}</div>`;
      if (s.initiator_chain && s.initiator_chain.length > 1) {
        initiatorHtml += `<div class="small text-muted font-monospace mt-0.5 text-truncate" style="font-size: 0.72rem; max-width: 260px;" title="${escapeHtml(s.initiator_chain.join(' → '))}">🔗 ${escapeHtml(s.initiator_chain.join(' → '))}</div>`;
      }
    }

    let reasonHtml = '<span class="text-muted">--</span>';
    if (s.reason || s.reason_code) {
      const codeBadge = s.reason_code ? `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle font-monospace me-1">${escapeHtml(s.reason_code)}</span>` : '';
      reasonHtml = `<div>${codeBadge}<span>${escapeHtml(s.reason || '')}</span></div>`;
      if (s.comment) {
        reasonHtml += `<div class="small text-muted font-italic mt-0.5">💬 ${escapeHtml(s.comment)}</div>`;
      }
    }

    return `
      <tr class="pwr-session-row" data-session-id="${escapeHtml(s.session_id)}" style="cursor: pointer;" title="Нажмите для AI-анализа сессии питания">
        <td class="font-monospace text-primary small fw-bold text-nowrap">${escapeHtml(s.session_id)}</td>
        <td class="font-monospace small text-nowrap">${escapeHtml(s.boot_time)}</td>
        <td class="font-monospace small text-muted text-nowrap">${s.shutdown_time ? escapeHtml(s.shutdown_time) : '<span class="text-success fw-bold">Сейчас</span>'}</td>
        <td class="font-monospace fw-semibold text-nowrap">${escapeHtml(s.uptime_human || '--')}</td>
        <td class="text-nowrap">${statusBadge}</td>
        <td style="min-width: 220px; max-width: 280px;">${initiatorHtml}</td>
        <td style="min-width: 320px;">${reasonHtml}</td>
        <td class="text-center">
          <button class="btn btn-xs btn-outline-info p-1 px-2 pwr-detail-btn" data-session-id="${escapeHtml(s.session_id)}" title="Посмотреть подробную хронологию">
            <i class="bi bi-eye"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.pwr-session-row').forEach(row => {
    row.addEventListener('click', () => {
      const sId = row.dataset.sessionId;
      showPowerSessionDetailModal(sId, allPowerSessions);
    });
  });
}

/**
 * Диагностика события электропитания через модальное окно.
 * @param {Object} e - Объект события.
 */
export function showPowerEventDetail(e) {
  if (!e) return;
  const modal = window.AIModalDialog || window.AITableModal;
  if (modal) {
    const isErr = e.event_id === 41 || e.event_id === 6008 || e.event_id === 1001;
    modal.show({
      icon: isErr ? '🚨' : '⚡',
      title: `Событие питания #${e.event_id} (${e.provider || 'Kernel-Power'})`,
      subtitle: `Тип: ${e.event_type || 'Lifecycle'} | ${e.timestamp || ''}`,
      panelId: 'panel-system-control-5',
      tableType: 'power_event',
      badges: [
        { text: `Event ${e.event_id}`, class: isErr ? 'badge bg-danger' : 'badge bg-info text-dark' },
        { text: e.event_type || 'Power', class: 'badge border text-secondary' }
      ],
      metadata: [
        { label: 'Event ID', value: String(e.event_id) },
        { label: 'Поставщик', value: e.provider || 'Kernel-Power' },
        { label: 'Пользователь', value: e.user || 'SYSTEM' },
        { label: 'Процесс', value: e.process || '-' },
        { label: 'Время события', value: e.timestamp || '-' },
        { label: 'Причина / Сообщение', value: e.reason || e.details?.message || '-', fullWidth: true }
      ],
      rawTitle: 'Сырые XML данные события',
      rawContent: e.raw_xml || JSON.stringify(e, null, 2),
      requestData: {
        event_id: e.event_id,
        provider: e.provider,
        user: e.user,
        process: e.process,
        reason: e.reason
      }
    });
  }
}

/**
 * Фильтрация и рендеринг таблицы событий журнала электропитания.
 */
export function filterAndRenderPowerEvents() {
  const tbody = document.getElementById('pwr-events-tbody');
  const counter = document.getElementById('pwr-events-counter');
  if (!tbody) return;

  const searchVal = (document.getElementById('pwr-events-search')?.value || '').toLowerCase().trim();
  const eidFilter = document.getElementById('pwr-event-id-filter')?.value || '';

  const filtered = allPowerEvents.filter(e => {
    if (eidFilter && String(e.event_id) !== String(eidFilter)) return false;
    if (searchVal) {
      const prov = (e.provider || '').toLowerCase();
      const user = (e.user || '').toLowerCase();
      const proc = (e.process || '').toLowerCase();
      const reason = (e.reason || '').toLowerCase();
      const msg = (e.details?.message || '').toLowerCase();
      if (!prov.includes(searchVal) && !user.includes(searchVal) && !proc.includes(searchVal) && !reason.includes(searchVal) && !msg.includes(searchVal)) {
        return false;
      }
    }
    return true;
  });

  if (counter) counter.textContent = `Событий: ${filtered.length}`;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-4 text-muted">
          События журнала, удовлетворяющие критериям поиска, не найдены.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map((e, idx) => {
    let eidBadge = `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle font-monospace">${e.event_id}</span>`;
    if (e.event_id === 1074) {
      eidBadge = '<span class="badge bg-warning-subtle text-warning-emphasis border border-warning font-monospace fw-bold">1074 User32</span>';
    } else if (e.event_id === 41) {
      eidBadge = '<span class="badge bg-danger-subtle text-danger border border-danger font-monospace fw-bold">41 Kernel-Power</span>';
    } else if (e.event_id === 6008) {
      eidBadge = '<span class="badge bg-danger-subtle text-danger border border-danger font-monospace fw-bold">6008 EventLog</span>';
    } else if (e.event_id === 12 || e.event_id === 6005 || e.event_id === 6009) {
      eidBadge = `<span class="badge bg-success-subtle text-success border border-success font-monospace">${e.event_id} Boot</span>`;
    } else if (e.event_id === 13 || e.event_id === 6006) {
      eidBadge = `<span class="badge bg-info-subtle text-info border border-info font-monospace">${e.event_id} Clean</span>`;
    } else if (e.event_id === 1001) {
      eidBadge = '<span class="badge bg-danger text-white font-monospace fw-bold">1001 BSOD</span>';
    }

    let userProc = '<span class="text-muted">--</span>';
    if (e.user || e.process) {
      userProc = `<div class="fw-semibold text-primary">${escapeHtml(e.user || '')}</div>`;
      if (e.process) userProc += `<div class="font-monospace small text-muted">${escapeHtml(e.process)}</div>`;
    }

    const desc = e.reason || e.details?.message || '--';

    return `
      <tr class="pwr-event-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для AI-диагностики инцидента питания">
        <td class="font-monospace small">${escapeHtml(e.timestamp)}</td>
        <td>${eidBadge}</td>
        <td class="small text-muted font-monospace">${escapeHtml(e.provider)}</td>
        <td><span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">${escapeHtml(e.event_type)}</span></td>
        <td>${userProc}</td>
        <td class="small">${escapeHtml(desc)}</td>
        <td>
          ${e.raw_xml ? `
            <button class="btn btn-xs btn-outline-secondary p-1 px-2 pwr-xml-btn" data-xml="${escapeHtml(e.raw_xml)}" title="Просмотреть XML">
              <i class="bi bi-code-square"></i>
            </button>
          ` : '<span class="text-muted">-</span>'}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.pwr-event-row').forEach(row => {
    row.addEventListener('click', (evt) => {
      if (evt.target.closest('.pwr-xml-btn')) return;
      const idx = parseInt(row.dataset.idx, 10);
      const e = filtered[idx];
      if (e) showPowerEventDetail(e);
    });
  });

  tbody.querySelectorAll('.pwr-xml-btn').forEach(btn => {
    btn.addEventListener('click', (evt) => {
      evt.stopPropagation();
      const xml = btn.dataset.xml;
      showPowerXmlModal(xml);
    });
  });
}

/**
 * Загрузка актуальных данных электропитания из API.
 * 
 * @param {boolean} force - Принудительное обновление.
 * @param {Function} isTabActive - Функция проверки активности вкладки.
 */
export async function loadPowerData(force = false, isTabActive = () => true) {
  if (!isTabActive()) return;
  const sessionsTbody = document.getElementById('pwr-sessions-tbody');
  const eventsTbody = document.getElementById('pwr-events-tbody');

  // Показываем индикатор загрузки, если данных ещё нет
  if (allPowerSessions.length === 0 && sessionsTbody) {
    sessionsTbody.innerHTML = `
      <tr>
        <td class="text-center py-4 text-muted" colspan="8">
          <div class="spinner-border spinner-border-sm text-info me-2" role="status"></div>
          Загрузка истории сессий питания...
        </td>
      </tr>
    `;
  }
  if (allPowerEvents.length === 0 && eventsTbody) {
    eventsTbody.innerHTML = `
      <tr>
        <td class="text-center py-4 text-muted" colspan="7">
          <div class="spinner-border spinner-border-sm text-info me-2" role="status"></div>
          Загрузка журнала событий...
        </td>
      </tr>
    `;
  }

  try {
    const summaryPromise = fetch('/api/v1/power/summary').then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    const sessionsPromise = fetch('/api/v1/power/sessions?limit=100').then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    const eventsPromise = fetch('/api/v1/power/events?limit=200').then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });

    const [summary, sessions, events] = await Promise.all([summaryPromise, sessionsPromise, eventsPromise]);

    if (summary) {
      renderPowerSummary(summary);
      startPowerUptimeCounter();
    }

    allPowerSessions = Array.isArray(sessions) ? sessions : [];
    filterAndRenderPowerSessions();

    allPowerEvents = Array.isArray(events) ? events : [];
    filterAndRenderPowerEvents();
  } catch (err) {
    console.warn('[PowerLifecycle] Ошибка загрузки данных питания:', err);
    if (sessionsTbody && allPowerSessions.length === 0) {
      sessionsTbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <span>Не удалось загрузить данные сессий питания: ${escapeHtml(err.message || 'Ошибка сети')}</span>
            <div class="mt-2">
              <button class="btn btn-xs btn-outline-danger px-3 py-1" onclick="window.fetchActiveSourceData ? window.fetchActiveSourceData(true) : null">
                <i class="bi bi-arrow-clockwise me-1"></i>Повторить попытку
              </button>
            </div>
          </td>
        </tr>
      `;
    }
    if (eventsTbody && allPowerEvents.length === 0) {
      eventsTbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <span>Не удалось загрузить журнал событий питания</span>
          </td>
        </tr>
      `;
    }
  }
}

/**
 * Инициализация обработчиков событий панели жизненного цикла питания.
 */
export function initPowerLifecyclePanel() {
  if (isPowerInitialized) return;
  isPowerInitialized = true;

  // Интерактивное переключение суб-вкладок (Сессии vs События)
  const sessionsSubtabBtn = document.getElementById('pwr-sessions-subtab-btn');
  const eventsSubtabBtn = document.getElementById('pwr-events-subtab-btn');
  const sessionsPane = document.getElementById('pwr-subtab-sessions');
  const eventsPane = document.getElementById('pwr-subtab-events');

  if (sessionsSubtabBtn && !sessionsSubtabBtn._bound) {
    sessionsSubtabBtn._bound = true;
    sessionsSubtabBtn.addEventListener('click', (e) => {
      e.preventDefault();
      sessionsSubtabBtn.classList.add('active');
      if (eventsSubtabBtn) eventsSubtabBtn.classList.remove('active');
      if (sessionsPane) sessionsPane.classList.add('show', 'active');
      if (eventsPane) eventsPane.classList.remove('show', 'active');
    });
  }

  if (eventsSubtabBtn && !eventsSubtabBtn._bound) {
    eventsSubtabBtn._bound = true;
    eventsSubtabBtn.addEventListener('click', (e) => {
      e.preventDefault();
      eventsSubtabBtn.classList.add('active');
      if (sessionsSubtabBtn) sessionsSubtabBtn.classList.remove('active');
      if (eventsPane) eventsPane.classList.add('show', 'active');
      if (sessionsPane) sessionsPane.classList.remove('show', 'active');
    });
  }

  const refreshBtn = document.getElementById('pwr-refresh-btn');
  if (refreshBtn && !refreshBtn._bound) {
    refreshBtn._bound = true;
    refreshBtn.addEventListener('click', () => loadPowerData(true));
  }

  const rebuildBtn = document.getElementById('pwr-rebuild-btn');
  if (rebuildBtn && !rebuildBtn._bound) {
    rebuildBtn._bound = true;
    rebuildBtn.addEventListener('click', async () => {
      rebuildBtn.disabled = true;
      rebuildBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сканирование...';
      try {
        const res = await fetch('/api/v1/power/rebuild', { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await loadPowerData(true);
        if (window.toast) window.toast.success('Сессии перестроены', 'Журналы питания успешно проиндексированы');
      } catch (e) {
        console.warn('[PowerLifecycle] Ошибка перестроения:', e);
        if (window.toast) window.toast.error('Ошибка', 'Не удалось перестроить сессии: ' + e.message);
      } finally {
        rebuildBtn.disabled = false;
        rebuildBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i><span>Пересканировать Event Log</span>';
      }
    });
  }

  const searchSessions = document.getElementById('pwr-sessions-search');
  if (searchSessions && !searchSessions._bound) {
    searchSessions._bound = true;
    searchSessions.addEventListener('input', () => filterAndRenderPowerSessions());
  }

  const filterType = document.getElementById('pwr-filter-type');
  if (filterType && !filterType._bound) {
    filterType._bound = true;
    filterType.addEventListener('change', () => filterAndRenderPowerSessions());
  }

  const unexpCheck = document.getElementById('pwr-filter-unexpected-only');
  if (unexpCheck && !unexpCheck._bound) {
    unexpCheck._bound = true;
    unexpCheck.addEventListener('change', () => filterAndRenderPowerSessions());
  }

  const searchEvents = document.getElementById('pwr-events-search');
  if (searchEvents && !searchEvents._bound) {
    searchEvents._bound = true;
    searchEvents.addEventListener('input', () => filterAndRenderPowerEvents());
  }

  const eidFilter = document.getElementById('pwr-event-id-filter');
  if (eidFilter && !eidFilter._bound) {
    eidFilter._bound = true;
    eidFilter.addEventListener('change', () => filterAndRenderPowerEvents());
  }

  initTableResizers();
}
