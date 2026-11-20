/**
 * =============================================================================
 * Process Name: Windows Services Manager Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом каталога служб Windows:
 *   фильтрация по статусу, группам svchost, сетевой активности и per-user
 *   экземплярам, а также вызов глубокого досье (/api/v1/services-manager/dossier)
 *   в универсальном модальном окне ИИ-ассистента (AIModalDialog).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_services_manager/main.js?v=20261120_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initServicesManagerTab, openServiceAiModal } from '/html/tab_services_manager/main.js';
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_services_manager
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};

var isInitialized = false;
let servicesList = [];
let currentFilter = 'all';
let currentGroupFilter = '';

/**
 * Экранирование HTML-символов в строке.
 * @param {string} str - Исходная строка.
 * @returns {string} Безопасная строка.
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Запрос сводки о службах с бэкенда.
 * @param {boolean} forceScan - Если true, запускает принудительный POST /scan.
 */
export async function fetchServicesSummary(forceScan = false) {
  const refreshBtn = document.getElementById('svc-refresh-btn');
  if (refreshBtn) {
    const icon = refreshBtn.querySelector('i');
    if (icon) icon.classList.add('spin-animation');
  }

  try {
    const url = forceScan ? '/api/v1/services-manager/scan' : '/api/v1/services-manager/summary';
    const res = await fetch(url, forceScan ? { method: 'POST' } : undefined);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderServices(data);
  } catch (err) {
    console.warn('[ServicesManager] Ошибка получения списка служб:', err);
  } finally {
    if (refreshBtn) {
      const icon = refreshBtn.querySelector('i');
      if (icon) icon.classList.remove('spin-animation');
    }
  }
}

/**
 * Заполнение выпадающего списка групп svchost с количеством служб.
 */
function populateGroupFilter() {
  const select = document.getElementById('svc-group-filter');
  if (!select) return;

  const prevValue = select.value;
  const counts = new Map();
  servicesList.forEach(s => {
    const grp = (s.svchost_group || '').trim();
    if (grp) counts.set(grp, (counts.get(grp) || 0) + 1);
  });

  const sortedGroups = Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  select.innerHTML = `<option value="">Все группы svchost (${sortedGroups.length})</option>` +
    sortedGroups.map(([grp, cnt]) =>
      `<option value="${escapeHtml(grp)}">${escapeHtml(grp)} (${cnt})</option>`
    ).join('');

  if (prevValue && counts.has(prevValue)) {
    select.value = prevValue;
    currentGroupFilter = prevValue;
  }
}

/**
 * Отрисовка сводной статистики и применение фильтрации.
 * @param {Object} data - Сводные данные от бэкенда.
 */
function renderServices(data) {
  servicesList = data.services || [];

  const totalEl = document.getElementById('svc-total-count');
  const runningEl = document.getElementById('svc-running-count');
  const groupsEl = document.getElementById('svc-groups-count');
  const autoEl = document.getElementById('svc-auto-count');
  const perUserSub = document.getElementById('svc-per-user-sub');

  const runningCount = servicesList.filter(s => {
    const st = (s.status || s.state || '').toLowerCase();
    return st.includes('running') || s.state === '4';
  }).length;

  const autoCount = servicesList.filter(s => (s.start_type || s.startup_type || '').toLowerCase().includes('auto')).length;
  const perUserCount = servicesList.filter(s => Boolean(s.is_per_user)).length;
  const uniqueGroups = new Set(servicesList.map(s => (s.svchost_group || '').toLowerCase()).filter(Boolean));

  if (totalEl) totalEl.textContent = servicesList.length;
  if (runningEl) runningEl.textContent = runningCount;
  if (groupsEl) groupsEl.textContent = data.svchost_groups_count ?? uniqueGroups.size;
  if (autoEl) autoEl.textContent = autoCount;
  if (perUserSub) perUserSub.textContent = `Per-user экземпляры: ${data.per_user_services_count ?? perUserCount}`;

  populateGroupFilter();
  applyServiceFilters();
}

/**
 * Применение фильтров поиска, группы svchost и состояния к таблице служб.
 */
function applyServiceFilters() {
  const tbody = document.getElementById('svc-tbody');
  const searchInput = document.getElementById('svc-search-input');
  const badge = document.getElementById('svc-table-badge');

  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

  const filtered = servicesList.filter(s => {
    const st = (s.status || s.state || '').toLowerCase();
    const isRunning = st.includes('running') || s.state === '4';
    if (currentFilter === 'running' && !isRunning) return false;
    if (currentFilter === 'stopped' && isRunning) return false;
    if (currentFilter === 'network' && !(Number(s.network_connections_count) > 0)) return false;
    if (currentFilter === 'per-user' && !s.is_per_user) return false;

    if (currentGroupFilter && (s.svchost_group || '').toLowerCase() !== currentGroupFilter.toLowerCase()) {
      return false;
    }

    if (query) {
      const haystack = [
        s.name,
        s.display_name,
        s.svchost_group,
        s.service_dll,
        s.base_service_name,
        s.host_process_name,
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(query);
    }
    return true;
  });

  if (badge) badge.textContent = `${filtered.length} из ${servicesList.length} служб`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Службы не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.slice(0, 200).map(s => {
    const st = (s.status || s.state || '').toLowerCase();
    const isRunning = st.includes('running') || s.state === '4';
    const badgeClass = isRunning
      ? 'badge bg-success-subtle text-success border border-success'
      : 'badge bg-secondary-subtle text-secondary border border-secondary';
    const statusText = isRunning ? 'Running' : 'Stopped';

    const perUserTag = s.is_per_user
      ? `<span class="badge bg-info-subtle text-info border border-info ms-1" title="Динамический экземпляр шаблона ${escapeHtml(s.base_service_name || '')}">per-user</span>`
      : '';

    const groupHtml = s.svchost_group
      ? `<span class="badge bg-primary-subtle text-primary border border-primary font-monospace">${escapeHtml(s.svchost_group)}</span>`
      : `<span class="text-muted small font-monospace">${escapeHtml(s.host_process_name || '—')}</span>`;

    const linksCount = (s.dependencies ? s.dependencies.length : 0) +
      (s.dependents ? s.dependents.length : 0) +
      (s.shared_pid_services ? s.shared_pid_services.length : 0);

    const resParts = [];
    if (s.pid) resParts.push(`<span class="font-monospace">PID ${escapeHtml(String(s.pid))}</span>`);
    if (Number(s.memory_mb) > 0) resParts.push(`<span class="text-info">${Number(s.memory_mb).toFixed(1)} MB</span>`);
    if (Number(s.network_connections_count) > 0) {
      resParts.push(`<span class="badge bg-warning-subtle text-warning border border-warning" title="Активные сетевые соединения PID">🌐 ${s.network_connections_count}</span>`);
    }
    if (linksCount > 0) {
      resParts.push(`<span class="badge bg-secondary-subtle text-secondary border border-secondary" title="Связанные службы (зависимости и общий PID)">🔗 ${linksCount}</span>`);
    }
    const resourcesHtml = resParts.length ? resParts.join(' ') : '<span class="text-muted">—</span>';

    return `
      <tr class="interactive-service-row" data-service-name="${escapeHtml(s.name)}" title="Нажмите для открытия глубокого досье и графа связей">
        <td class="fw-bold font-monospace svc-name-cell">
          <span>${escapeHtml(s.name)}</span>${perUserTag}
        </td>
        <td>${escapeHtml(s.display_name || s.name)}</td>
        <td>${groupHtml}</td>
        <td><span class="${badgeClass}">${statusText}</span></td>
        <td class="small text-muted">${escapeHtml(s.start_type || s.startup_type || 'Manual')}</td>
        <td class="small">${resourcesHtml}</td>
        <td class="text-end no-modal-trigger">
          <button class="btn btn-xs ${isRunning ? 'btn-outline-danger' : 'btn-outline-success'} py-0 px-2 svc-action-btn"
                  data-service="${escapeHtml(s.name)}" data-action="${isRunning ? 'sc_stop' : 'sc_start'}"
                  title="${isRunning ? 'Остановить службу' : 'Запустить службу'}">
            <i class="bi ${isRunning ? 'bi-stop-fill' : 'bi-play-fill'}"></i> ${isRunning ? 'Стоп' : 'Старт'}
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.interactive-service-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) {
        return;
      }
      const sName = row.dataset.serviceName;
      const sItem = servicesList.find(x => x.name === sName);
      if (sItem) {
        openServiceAiModal(sItem);
      }
    });
  });

  tbody.querySelectorAll('.svc-action-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeServiceCmd(btn.dataset.service, btn.dataset.action);
    });
  });
}

/**
 * Загрузка глубокого досье службы с бэкенда (/api/v1/services-manager/dossier/{name}).
 * @param {string} serviceName - Системное имя службы.
 * @returns {Promise<Object|null>}
 */
async function fetchServiceDossier(serviceName) {
  try {
    const res = await fetch(`/api/v1/services-manager/dossier/${encodeURIComponent(serviceName)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn('[ServicesManager] Не удалось загрузить глубокое досье:', err);
    return null;
  }
}

/**
 * Открытие универсального модального окна ИИ-ассистента с глубоким досье и графом связей.
 * @param {Object} service - Базовый объект службы из таблицы.
 */
export async function openServiceAiModal(service) {
  if (!service) return;

  const modal = window.AIModalDialog || window.AITableModal || (window.parent && (window.parent.AIModalDialog || window.parent.AITableModal));
  if (!modal || typeof modal.show !== 'function') {
    console.warn('[ServicesManager] Универсальное модальное окно AIModalDialog недоступно, попытка динамической загрузки');
    if (!document.querySelector('link[href*="ai_modal_dialog/style.css"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/html/ai_modal_dialog/style.css?v=20261031_v1';
      document.head.appendChild(link);
    }
    const script = document.createElement('script');
    script.src = '/html/ai_modal_dialog/main.js?v=20261031_v2';
    script.onload = () => openServiceAiModal(service);
    document.head.appendChild(script);
    return;
  }

  const dossier = await fetchServiceDossier(service.name);
  const svc = (dossier && dossier.service) ? dossier.service : service;
  const reg = (dossier && dossier.registry) ? dossier.registry : {};
  const proc = (dossier && dossier.process) ? dossier.process : null;
  const conns = (dossier && dossier.network_connections) ? dossier.network_connections : [];
  const events = (dossier && dossier.recent_events) ? dossier.recent_events : [];
  const chain = (dossier && dossier.relations_chain) ? dossier.relations_chain : [];

  const st = (svc.status || svc.state || '').toLowerCase();
  const isRunning = st.includes('running') || svc.state === '4';
  const startType = svc.start_type || svc.startup_type || 'Manual';

  const badges = [
    {
      text: isRunning ? 'Running' : 'Stopped',
      class: isRunning ? 'badge bg-success-subtle text-success border border-success' : 'badge bg-secondary-subtle text-secondary border border-secondary'
    },
    { text: `Тип: ${startType}`, class: 'badge bg-info-subtle text-info border border-info' }
  ];

  if (svc.pid) {
    badges.push({ text: `PID: ${svc.pid}`, class: 'badge bg-primary-subtle text-primary border border-primary font-monospace' });
  }
  if (svc.svchost_group) {
    badges.push({ text: `Группа: ${svc.svchost_group}`, class: 'badge bg-primary-subtle text-primary border border-primary font-monospace' });
  }
  if (svc.is_per_user) {
    badges.push({ text: `Per-User (${svc.base_service_name})`, class: 'badge bg-info-subtle text-info border border-info' });
  }
  if (conns.length > 0) {
    badges.push({ text: `Сеть: ${conns.length} соед.`, class: 'badge bg-warning-subtle text-warning border border-warning' });
  }
  if (events.length > 0) {
    badges.push({ text: `Event Log: ${events.length}`, class: 'badge bg-danger-subtle text-danger border border-danger' });
  }

  const metadata = [
    { label: 'Имя службы (Service Name)', value: svc.name, isCode: true },
    { label: 'Отображаемое имя (Display Name)', value: svc.display_name || svc.name },
    { label: 'Состояние / Тип запуска', value: `${isRunning ? 'RUNNING' : 'STOPPED'} / ${startType}` },
    { label: 'Учетная запись (Account)', value: svc.account || svc.user_account || 'LocalSystem' },
  ];

  if (chain.length > 0) {
    metadata.push({ label: 'Цепочка связей', value: chain.join(' → '), isCode: true, fullWidth: true });
  }
  if (svc.svchost_group) {
    metadata.push({ label: 'Группа svchost', value: svc.svchost_group, isCode: true });
  }
  if (svc.service_dll || reg.service_dll) {
    metadata.push({ label: 'ServiceDll (Registry)', value: svc.service_dll || reg.service_dll, isCode: true, fullWidth: true });
  }
  if (proc) {
    metadata.push({
      label: 'Хост-процесс (CPU / RAM / Потоки / Handles)',
      value: `${proc.name} (PID ${proc.pid}) — CPU ${proc.cpu_percent}%, RAM ${proc.memory_mb} MB, Потоков: ${proc.threads_count}, Handles: ${proc.handles_count}, I/O R/W: ${proc.io_read_mb}/${proc.io_write_mb} MB`,
      fullWidth: true
    });
  }
  if (svc.dependencies && svc.dependencies.length > 0) {
    metadata.push({ label: 'Зависит от (DependOnService)', value: svc.dependencies.join(', '), isCode: true, fullWidth: true });
  }
  if (svc.dependents && svc.dependents.length > 0) {
    metadata.push({ label: 'Зависимые службы (Dependents)', value: svc.dependents.join(', '), isCode: true, fullWidth: true });
  }
  if (svc.shared_pid_services && svc.shared_pid_services.length > 0) {
    metadata.push({ label: `Соседи в общем PID (${svc.pid})`, value: svc.shared_pid_services.join(', '), isCode: true, fullWidth: true });
  }
  if (svc.same_group_services && svc.same_group_services.length > 0) {
    metadata.push({ label: `Соседи по группе ${svc.svchost_group}`, value: svc.same_group_services.slice(0, 20).join(', '), isCode: true, fullWidth: true });
  }
  if (conns.length > 0) {
    const connPreview = conns.slice(0, 8).map(c => `${c.protocol} ${c.local_address} -> ${c.remote_address || '*'} [${c.status}]`).join(' | ');
    metadata.push({ label: `Сетевые соединения (${conns.length})`, value: connPreview, isCode: true, fullWidth: true });
  }
  if (events.length > 0) {
    const evPreview = events.slice(0, 3).map(e => `[ID ${e.event_id} ${e.level}] ${e.message || e.provider}`).join(' ; ');
    metadata.push({ label: `Event Log System (${events.length} за 72ч)`, value: evPreview, fullWidth: true });
  }
  metadata.push({ label: 'Исполняемый файл (Binary Path)', value: svc.binary_path || svc.binpath || '—', isCode: true, fullWidth: true });

  modal.show({
    icon: '⚙️',
    title: svc.name,
    subtitle: svc.display_name ? `${svc.display_name} | ${isRunning ? 'Running' : 'Stopped'}` : `Служба Windows | ${isRunning ? 'Running' : 'Stopped'}`,
    panelId: 'panel-windows-services-manager',
    tableType: 'service',
    badges: badges,
    metadata: metadata,
    rawTitle: 'Глубокое досье и граф связей службы (JSON)',
    rawContent: JSON.stringify(dossier || svc, null, 2),
    requestData: dossier || svc,
    autoRun: false,
    actions: [
      {
        label: isRunning ? 'Остановить службу' : 'Запустить службу',
        icon: isRunning ? 'bi-stop-fill' : 'bi-play-fill',
        class: isRunning ? 'btn-outline-danger' : 'btn-outline-success',
        onClick: () => executeServiceCmd(svc.name, isRunning ? 'sc_stop' : 'sc_start')
      },
      {
        label: 'Перезапустить',
        icon: 'bi-arrow-repeat',
        class: 'btn-outline-warning',
        onClick: async () => {
          if (isRunning) {
            await executeServiceCmd(svc.name, 'sc_stop');
            setTimeout(() => executeServiceCmd(svc.name, 'sc_start'), 1200);
          } else {
            executeServiceCmd(svc.name, 'sc_start');
          }
        }
      }
    ]
  });
}

/**
 * Отправка команды управления службой на бэкенд.
 * @param {string} serviceName - Имя службы.
 * @param {string} action - Идентификатор действия (sc_start, sc_stop, restart).
 */
async function executeServiceCmd(serviceName, action) {
  if (window.showToast) window.showToast(`Команда отправлена: ${action} ${serviceName}`, 'info');
  else if (window.toast) window.toast.info('Команда отправлена', `${action}: ${serviceName}`);

  try {
    const res = await fetch('/api/v1/services-manager/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: serviceName,
        service_name: serviceName,
        action: action,
        confirmed_by_user: true,
        dry_run: false
      })
    });
    const result = await res.json();
    if (res.ok) {
      if (window.showToast) window.showToast(`✅ ${serviceName}: команда выполнена`, 'success');
      else if (window.toast) window.toast.success('Успех', `${serviceName}: команда выполнена`);
      fetchServicesSummary(true);
    } else {
      const errDetail = result.detail || result.message || 'Сбой операции';
      if (window.showToast) window.showToast(`Ошибка: ${errDetail}`, 'danger');
      else if (window.toast) window.toast.error('Ошибка', errDetail);
    }
  } catch (err) {
    const errMsg = `Ошибка сети: ${err.message}`;
    if (window.showToast) window.showToast(errMsg, 'danger');
    else if (window.toast) window.toast.error('Ошибка сети', err.message);
  }
}

/**
 * Инициализация вкладки диспетчера служб Windows.
 */
export function initServicesManagerTab() {
  if (isInitialized) return;
  isInitialized = true;

  const refreshBtn = document.getElementById('svc-refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', () => fetchServicesSummary(true));

  const searchInput = document.getElementById('svc-search-input');
  if (searchInput) searchInput.addEventListener('input', applyServiceFilters);

  const groupSelect = document.getElementById('svc-group-filter');
  if (groupSelect) {
    groupSelect.addEventListener('change', () => {
      currentGroupFilter = groupSelect.value;
      applyServiceFilters();
    });
  }

  const filterButtons = [
    document.getElementById('svc-filter-all'),
    document.getElementById('svc-filter-running'),
    document.getElementById('svc-filter-stopped'),
    document.getElementById('svc-filter-network'),
    document.getElementById('svc-filter-per-user'),
  ];

  filterButtons.forEach(btn => {
    if (!btn) return;
    btn.addEventListener('click', () => {
      filterButtons.forEach(b => {
        if (!b) return;
        b.classList.remove('active', 'btn-primary');
        b.classList.add('btn-outline-secondary');
      });
      btn.classList.add('active', 'btn-primary');
      btn.classList.remove('btn-outline-secondary');
      currentFilter = btn.id.replace('svc-filter-', '');
      applyServiceFilters();
    });
  });

  registerTabPoller('tab-services-manager', () => fetchServicesSummary(false), 15000, { immediate: true });
}

window.initServicesManagerTab = initServicesManagerTab;
window.openServiceAiModal = openServiceAiModal;

if (document.getElementById('svc-table') || document.getElementById('tab-services-manager')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initServicesManagerTab());
  } else {
    setTimeout(() => initServicesManagerTab(), 10);
  }
}
