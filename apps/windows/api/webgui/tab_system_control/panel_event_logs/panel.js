/**
 * Модуль панели журналов событий Windows (Event Logs & Channels).
 * 
 * Отвечает за:
 * - Сканирование и построение дерева системных каналов и EVTX-файлов
 * - Кэширование журнала в localStorage для мгновенного отображения (Zero-Latency)
 * - Фильтрацию по уровню важности, Event ID и поисковой строке
 * - Интеллектуальный профиль канала (Log Intelligence)
 * 
 * Updated: 2026-10-31 18:31:00
 */

import { escapeHtml, formatTime, getSeverityClass, adjustMainStreamHeight, initTableResizers, t } from '../common/ui_utils.js';
import { showEventDetails } from './modal.js';
import { createGlobalChannelTooltip, showChannelTooltip, hideChannelTooltip, loadLogFromBrowserCache, saveLogToBrowserCache, updateCacheDateUI } from './channel_tree.js';

let currentChannel = 'System';
let currentFilePath = '';
let cachedChannels = [];
let cachedEvents = [];
let elEventsList = [];
let isElInitialized = false;
let isLogRequestInProgress = false;

export function getCurrentChannel() {
  return currentChannel;
}

export function getCurrentFilePath() {
  return currentFilePath;
}

export function getCachedChannels() {
  return cachedChannels;
}

export function getCachedEvents() {
  return cachedEvents;
}

/**
 * Фильтрация каналов по строке ввода.
 */
export function filterChannels() {
  const filterInput = document.getElementById('slc-channel-filter-input');
  const filterText = filterInput ? filterInput.value.trim().toLowerCase() : '';
  if (!cachedChannels || cachedChannels.length === 0) return;
  if (!filterText) {
    renderChannelTree(cachedChannels);
    return;
  }
  const filtered = cachedChannels.filter(c => {
    const sysName = (c.channel_name || c.name || c.source_id || '').toLowerCase();
    const dispName = (c.display_name || '').toLowerCase();
    const desc = (c.description || '').toLowerCase();
    return sysName.includes(filterText) || dispName.includes(filterText) || desc.includes(filterText);
  });
  renderChannelTree(filtered);
}

/**
 * Сканирование доступных каналов журналов Windows.
 * @param {boolean} force
 */
export async function scanChannels(force = false) {
  const treeEl = document.getElementById('slc-channel-tree-container');
  const countBadge = document.getElementById('slc-channel-count-badge');
  const sourcesStat = document.getElementById('slc-stat-sources');

  if (treeEl && (!cachedChannels || cachedChannels.length === 0)) {
    treeEl.innerHTML = `<div class="text-muted p-2 small"><div class="spinner-border spinner-border-sm text-info me-1"></div>${t('systemControl.searchingChannels', 'Поиск каналов...')}</div>`;
  }

  try {
    const response = await fetch(`/api/v1/system_logs/scan?force=${force}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const rawChannels = data.channels || [];
    const priorityKeywords = ['system', 'application', 'security', 'setup', 'powershell', 'defender'];
    cachedChannels = rawChannels.filter(c => {
      const records = Number(c.record_count) || 0;
      const sizeBytes = Number(c.size_bytes) || 0;
      const sizeMb = Number(c.file_size_mb) || 0;
      const name = (c.channel_name || c.name || '').toLowerCase();
      const isPriority = priorityKeywords.some(k => name.includes(k));
      return records > 0 || sizeBytes > 0 || sizeMb > 0 || isPriority;
    });

    if (countBadge) countBadge.textContent = cachedChannels.length;
    if (sourcesStat) sourcesStat.textContent = cachedChannels.length.toLocaleString();

    filterChannels();
  } catch (err) {
    if (treeEl) treeEl.innerHTML = `<div class="text-danger p-2 small">${t('systemControl.errorScanning', 'Ошибка сканирования каналов:')} ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Рендеринг дерева каналов логов в боковой панели.
 * @param {Array} channels
 */
export function renderChannelTree(channels) {
  const treeEl = document.getElementById('slc-channel-tree-container');
  const countBadge = document.getElementById('slc-channel-count-badge');
  if (!treeEl) return;

  if (countBadge && channels) {
    countBadge.textContent = channels.length;
  }

  if (!channels || channels.length === 0) {
    treeEl.innerHTML = `<div class="text-muted p-2 small">${t('systemControl.noChannels', 'Каналы не найдены.')}</div>`;
    return;
  }

  createGlobalChannelTooltip();

  treeEl.innerHTML = channels.map(ch => {
    const isFile = !!(ch.file_path || (ch.source_type && ch.source_type !== 'channel'));
    const sysName = (ch.channel_name || ch.name || ch.source_id || 'System').replace(/^evt:/, '');
    const dispName = (ch.display_name || ch.channel_name || ch.name || 'Channel').replace(/^evt:/, '');
    const chPath = ch.location || ch.file_path || '';
    const isActive = isFile ? (currentFilePath === chPath) : (currentChannel === sysName && !currentFilePath);
    const icon = isFile ? 'bi-file-earmark-text text-secondary' : 'bi-folder-fill text-warning';
    
    let sizeBadge = '';
    if (ch.record_count !== undefined && ch.record_count > 0) {
      const countText = ch.record_count >= 1000 ? `${(ch.record_count / 1000).toFixed(1)}k` : String(ch.record_count);
      sizeBadge = `<span class="badge bg-secondary font-monospace" style="font-size: 0.68rem;">${countText}</span>`;
    } else if (ch.file_size_mb) {
      sizeBadge = `<span class="badge bg-secondary font-monospace" style="font-size: 0.68rem;">${ch.file_size_mb} MB</span>`;
    }

    return `
      <div class="slc-tree-item ${isActive ? 'active' : ''}" data-channel="${escapeHtml(sysName)}" data-display-name="${escapeHtml(dispName)}" data-path="${escapeHtml(chPath)}">
        <div class="d-flex align-items-center gap-2 text-truncate me-2" style="min-width: 0; flex: 1 1 auto;">
          <i class="bi ${icon} flex-shrink-0"></i>
          <span class="text-truncate fw-medium" title="${escapeHtml(dispName)}">${escapeHtml(dispName)}</span>
        </div>
        <div class="d-flex align-items-center flex-shrink-0">
          ${sizeBadge}
        </div>
      </div>
    `;
  }).join('');

  treeEl.querySelectorAll('.slc-tree-item').forEach((el, index) => {
    const chData = channels[index];
    el.addEventListener('mouseenter', (e) => {
      if (chData) showChannelTooltip(chData, e);
    });
    el.addEventListener('mousemove', (e) => {
      if (chData) showChannelTooltip(chData, e);
    });
    el.addEventListener('mouseleave', () => {
      hideChannelTooltip();
    });

    el.addEventListener('click', () => {
      hideChannelTooltip();
      treeEl.querySelectorAll('.slc-tree-item').forEach(i => i.classList.remove('active'));
      el.classList.add('active');

      currentChannel = (el.getAttribute('data-channel') || el.getAttribute('data-name') || 'System').replace(/^evt:/, '').split(' (')[0].trim();
      currentFilePath = el.getAttribute('data-path') || '';
      const dispName = el.getAttribute('data-display-name') || currentChannel;

      const statChan = document.getElementById('slc-stat-channel');
      if (statChan) statChan.textContent = dispName;

      const mainTitle = document.getElementById('slc-main-view-title');
      if (mainTitle) mainTitle.innerHTML = `<i class="bi bi-list-columns-reverse me-2 text-primary"></i>${t('systemControl.channelEventsTitle', 'События канала:')} <span class="text-info">${escapeHtml(dispName)}</span>`;

      loadEvents(true);
    });
  });
}

/**
 * Загрузка событий выбранного журнала с мгновенным показом из кеша браузера.
 * @param {boolean} forceRefresh
 * @param {string} mode
 */
export async function loadEvents(forceRefresh = false, mode = 'live') {
  const tbody = document.getElementById('slc-table-body');
  const statEvents = document.getElementById('slc-stat-events');
  const statIncidents = document.getElementById('slc-stat-incidents');
  const streamBadge = document.getElementById('slc-stream-count-badge');
  const panelRefreshBtn = document.getElementById('btn-slc-panel-refresh');
  const topRefreshBtn = document.getElementById('btn-slc-refresh');

  const cleanChan = currentChannel.replace(/^evt:/, '').split(' (')[0].trim();

  const searchInput = document.getElementById('slc-search-input');
  const levelSelect = document.getElementById('slc-level-select');
  const hoursSelect = document.getElementById('slc-hours-select');
  const limitSelect = document.getElementById('slc-limit-select');
  const eventIdInput = document.getElementById('slc-eventid-input');

  const query = searchInput ? searchInput.value.trim() : '';
  const level = levelSelect ? levelSelect.value : '';
  const hours = hoursSelect ? hoursSelect.value : '24';
  const limit = limitSelect ? limitSelect.value : '100';
  const eventId = eventIdInput ? eventIdInput.value.trim() : '';

  const isDefaultFilter = !query && !level && hours === '24' && !eventId;

  // 1. Быстрая загрузка из кеша браузера при стандартных фильтрах
  if (!forceRefresh && isDefaultFilter && !currentFilePath) {
    const cached = loadLogFromBrowserCache(cleanChan, currentFilePath);
    if (cached && cached.events && cached.events.length > 0) {
      cachedEvents = cached.events;
      updateCacheDateUI(cached.cachedAtFormatted);

      if (statEvents) statEvents.textContent = cachedEvents.length.toLocaleString();
      if (streamBadge) streamBadge.textContent = `${cachedEvents.length} записей`;

      const faults = cachedEvents.filter(e => {
        const l = (e.level || '').toLowerCase();
        return l.includes('err') || l.includes('crit');
      }).length;
      if (statIncidents) statIncidents.textContent = faults;

      renderEventsTable(cachedEvents, mode);
      return;
    }
  }

  // 2. Фоновый запрос к ОС
  if (isLogRequestInProgress) return;
  isLogRequestInProgress = true;

  if (panelRefreshBtn) {
    const icon = panelRefreshBtn.querySelector('i');
    if (icon) icon.classList.add('spinner-border', 'spinner-border-sm');
  }
  if (topRefreshBtn) {
    const icon = topRefreshBtn.querySelector('i');
    if (icon) icon.classList.add('spinner-border', 'spinner-border-sm');
  }

  const cacheText = document.getElementById('slc-cache-date-text');
  if (cacheText) cacheText.textContent = 'Кеш: запрос к ОС...';

  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-5 text-muted">
          <div class="spinner-border text-primary mb-2" role="status" style="width: 2rem; height: 2rem;"></div>
          <div class="small fw-semibold text-light">Чтение журнала "${escapeHtml(cleanChan)}" у операционной системы...</div>
        </td>
      </tr>
    `;
  }

  const params = new URLSearchParams({
    channel: cleanChan,
    limit: limit,
    hours: hours,
  });

  if (query) {
    params.append('search', query);
    params.append('query', query);
  }
  if (level) params.append('level', level);
  if (eventId) params.append('event_id', eventId);
  if (currentFilePath) params.append('file_path', currentFilePath);

  try {
    const res = await fetch(`/api/v1/system_logs/events?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const freshEvents = data.events || data.entries || [];

    if (isDefaultFilter && !currentFilePath) {
      saveLogToBrowserCache(cleanChan, currentFilePath, freshEvents);
    }
    cachedEvents = freshEvents;

    if (statEvents) statEvents.textContent = cachedEvents.length.toLocaleString();
    if (streamBadge) streamBadge.textContent = `${cachedEvents.length} записей`;

    const faults = cachedEvents.filter(e => {
      const l = (e.level || '').toLowerCase();
      return l.includes('err') || l.includes('crit');
    }).length;
    if (statIncidents) statIncidents.textContent = faults;

    renderEventsTable(cachedEvents, mode);
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-4">Ошибка загрузки событий: ${escapeHtml(err.message)}</td></tr>`;
  } finally {
    isLogRequestInProgress = false;
    if (panelRefreshBtn) {
      const icon = panelRefreshBtn.querySelector('i');
      if (icon) icon.classList.remove('spinner-border', 'spinner-border-sm');
    }
    if (topRefreshBtn) {
      const icon = topRefreshBtn.querySelector('i');
      if (icon) icon.classList.remove('spinner-border', 'spinner-border-sm');
    }
  }
}

/**
 * Рендеринг таблицы событий Windows.
 * @param {Array} events
 * @param {string} mode
 */
export function renderEventsTable(events, mode = 'live') {
  const tbody = document.getElementById('slc-table-body');
  if (!tbody) return;

  let displayEvents = events || [];
  if (mode === 'errors') {
    displayEvents = displayEvents.filter(e => {
      const l = (e.level || '').toLowerCase();
      return l.includes('err') || l.includes('crit') || l.includes('warn');
    });
  }

  if (!displayEvents || displayEvents.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Нет записей, удовлетворяющих заданным фильтрам.</td></tr>`;
    return;
  }

  tbody.innerHTML = displayEvents.map((e, idx) => {
    const timeFormatted = formatTime(e.timestamp);
    const isErr = (e.level || '').toLowerCase().includes('err') || (e.level || '').toLowerCase().includes('crit');
    const provName = e.provider || e.source || '-';
    const msgText = e.message || e.raw_data || '-';

    return `
      <tr data-index="${idx}" class="${isErr ? 'table-danger-subtle' : ''}">
        <td class="font-monospace small" style="color: var(--text-muted);">${escapeHtml(timeFormatted)}</td>
        <td><span class="badge ${getSeverityClass(e.level)} text-uppercase" style="font-size: 0.68rem;">${escapeHtml(e.level || 'Info')}</span></td>
        <td class="font-monospace small fw-bold" style="color: #0284c7;">${e.event_id > 0 ? e.event_id : '-'}</td>
        <td class="text-truncate small" style="max-width: 160px; color: var(--text-color);" title="${escapeHtml(provName)}">${escapeHtml(provName)}</td>
        <td class="font-monospace small" style="color: var(--text-muted);">${e.process_id || '-'}</td>
        <td class="text-truncate" style="max-width: 420px; color: var(--text-color);" title="${escapeHtml(msgText)}">${escapeHtml(msgText)}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('tr').forEach(row => {
    row.onclick = () => {
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('table-active'));
      row.classList.add('table-active');
      const idx = parseInt(row.getAttribute('data-index'), 10);
      const ev = displayEvents[idx];
      if (ev) showEventDetails(ev, 'panel-system-control-3', currentChannel);
    };
  });

  adjustMainStreamHeight();
}

/**
 * Загрузка сводки событий в компактном представлении Event Logs.
 */
export async function fetchEventLogsSummary() {
  const channelSelect = document.getElementById('el-channel-select');
  const channel = channelSelect ? channelSelect.value : 'System';

  try {
    const res = await fetch(`/api/v1/system_logs/events?channel=${encodeURIComponent(channel)}&limit=150`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const entries = data.events || data.entries || [];
    renderElEvents(entries);
  } catch (err) {
    console.warn('[EventLogs] Ошибка загрузки событий:', err);
  }
}

function renderElEvents(entries) {
  elEventsList = entries || [];
  const critEl = document.getElementById('el-critical-count');
  const errEl = document.getElementById('el-error-count');

  let crits = 0;
  let errs = 0;
  elEventsList.forEach(e => {
    const l = (e.level || '').toLowerCase();
    if (l.includes('crit')) crits++;
    else if (l.includes('err')) errs++;
  });

  if (critEl) critEl.textContent = crits;
  if (errEl) errEl.textContent = errs;

  applyElFilters();
}

function applyElFilters() {
  const tbody = document.getElementById('el-tbody');
  const searchInput = document.getElementById('el-search-input');
  const badge = document.getElementById('el-table-badge');
  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const filtered = elEventsList.filter(e => {
    if (!query) return true;
    const msgMatch = (e.message || '').toLowerCase().includes(query);
    const provMatch = (e.provider_name || e.provider || '').toLowerCase().includes(query);
    const idMatch = String(e.event_id || e.id || '').includes(query);
    return msgMatch || provMatch || idMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${elEventsList.length} событий`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">События не найдены</td></tr>`;
    return;
  }

  const itemsToRender = filtered.slice(0, 150);
  tbody.innerHTML = itemsToRender.map((e, idx) => {
    const level = (e.level || 'Information').toLowerCase();
    let badgeClass = 'bg-secondary';
    if (level.includes('crit') || level.includes('err')) badgeClass = 'bg-danger text-white';
    else if (level.includes('warn')) badgeClass = 'bg-warning text-dark';
    else if (level.includes('info')) badgeClass = 'bg-info text-dark';

    return `
      <tr class="slc-el-table-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для просмотра подробностей события">
        <td><span class="badge ${badgeClass}">${escapeHtml(e.level || 'Info')}</span></td>
        <td class="text-muted small font-monospace">${escapeHtml(e.time_created || e.timestamp || '-')}</td>
        <td class="fw-semibold small" style="color: var(--text-color);">${escapeHtml(e.provider_name || e.provider || 'Windows')}</td>
        <td class="font-monospace text-warning small">${escapeHtml(String(e.event_id || e.id || '-'))}</td>
        <td class="small text-truncate" style="max-width: 500px; color: var(--text-color);">${escapeHtml(e.message || '-')}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.slc-el-table-row').forEach(row => {
    row.onclick = () => {
      const idx = parseInt(row.getAttribute('data-idx'), 10);
      const item = itemsToRender[idx];
      if (item) {
        showEventDetails({
          timestamp: item.time_created || item.timestamp,
          level: item.level,
          event_id: item.event_id || item.id,
          provider: item.provider_name || item.provider,
          computer: item.computer || item.machine_name || '',
          process_id: item.process_id || item.pid,
          channel: item.channel || (document.getElementById('el-channel-select')?.value || 'System'),
          message: item.message,
        }, 'panel-system-control-1', currentChannel);
      }
    };
  });
}

/**
 * Инициализация элементов панели Event Logs.
 */
export function initEventLogsPanel() {
  if (isElInitialized) return;
  isElInitialized = true;

  const refreshBtn = document.getElementById('el-refresh-btn');
  if (refreshBtn && !refreshBtn._bound) {
    refreshBtn._bound = true;
    refreshBtn.addEventListener('click', fetchEventLogsSummary);
  }

  const channelSelect = document.getElementById('el-channel-select');
  if (channelSelect && !channelSelect._bound) {
    channelSelect._bound = true;
    channelSelect.addEventListener('change', fetchEventLogsSummary);
  }

  const elSearchInput = document.getElementById('el-search-input');
  if (elSearchInput && !elSearchInput._bound) {
    elSearchInput._bound = true;
    elSearchInput.addEventListener('input', applyElFilters);
  }

  const bannerCloseBtn = document.getElementById('el-intel-close-btn');
  if (bannerCloseBtn && !bannerCloseBtn._bound) {
    bannerCloseBtn._bound = true;
    bannerCloseBtn.addEventListener('click', () => {
      const banner = document.getElementById('el-intel-banner');
      if (banner) banner.classList.add('d-none');
    });
  }

  // Привязка интерактивных элементов сайдбара и потока событий
  const channelFilterInput = document.getElementById('slc-channel-filter-input');
  if (channelFilterInput && !channelFilterInput._bound) {
    channelFilterInput._bound = true;
    channelFilterInput.addEventListener('input', filterChannels);
  }

  const levelSelect = document.getElementById('slc-level-select');
  if (levelSelect && !levelSelect._bound) {
    levelSelect._bound = true;
    levelSelect.addEventListener('change', () => loadEvents(true));
  }

  const hoursSelect = document.getElementById('slc-hours-select');
  if (hoursSelect && !hoursSelect._bound) {
    hoursSelect._bound = true;
    hoursSelect.addEventListener('change', () => loadEvents(true));
  }

  const limitSelect = document.getElementById('slc-limit-select');
  if (limitSelect && !limitSelect._bound) {
    limitSelect._bound = true;
    limitSelect.addEventListener('change', () => loadEvents(true));
  }

  let searchTimer = null;
  const searchInput = document.getElementById('slc-search-input');
  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadEvents(true), 350);
    });
  }

  let eventIdTimer = null;
  const eventIdInput = document.getElementById('slc-eventid-input');
  if (eventIdInput && !eventIdInput._bound) {
    eventIdInput._bound = true;
    eventIdInput.addEventListener('input', () => {
      clearTimeout(eventIdTimer);
      eventIdTimer = setTimeout(() => loadEvents(true), 350);
    });
  }

  const panelRefreshBtn = document.getElementById('btn-slc-panel-refresh');
  if (panelRefreshBtn && !panelRefreshBtn._bound) {
    panelRefreshBtn._bound = true;
    panelRefreshBtn.addEventListener('click', () => loadEvents(true));
  }

  const auditBtn = document.getElementById('btn-slc-audit');
  if (auditBtn && !auditBtn._bound) {
    auditBtn._bound = true;
    auditBtn.addEventListener('click', () => {
      const modeBtn = document.querySelector('#slc-mode-tabs button[data-mode="audit"]');
      if (modeBtn) modeBtn.click();
    });
  }

  initTableResizers();

  // Запуск фонового сканирования каналов при инициализации
  if (!cachedChannels || cachedChannels.length === 0) {
    scanChannels(false);
  }
}
