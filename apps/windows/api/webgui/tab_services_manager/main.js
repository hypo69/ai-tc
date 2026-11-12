/**
 * =============================================================================
 * Process Name: Windows Services Manager Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом диспетчера служб Windows
 *   с поддержкой вызова универсального модального окна ИИ-ассистента (AIModalDialog).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_services_manager/main.js?v=20261112_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initServicesManagerTab, openServiceAiModal } from '/html/tab_services_manager/main.js';
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_services_manager
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 01:56:00
 * =============================================================================
 */

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};

var isInitialized = false;
let servicesList = [];
let currentFilter = 'all';

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
 */
export async function fetchServicesSummary() {
  const refreshBtn = document.getElementById('svc-refresh-btn');
  if (refreshBtn) {
    const icon = refreshBtn.querySelector('i');
    if (icon) icon.classList.add('spin-animation');
  }

  try {
    const res = await fetch('/api/services-manager/summary');
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
 * Отрисовка сводной статистики и применение фильтрации.
 * @param {Object} data - Сводные данные от бэкенда.
 */
function renderServices(data) {
  servicesList = data.services || [];

  const totalEl = document.getElementById('svc-total-count');
  const runningEl = document.getElementById('svc-running-count');
  const stoppedEl = document.getElementById('svc-stopped-count');
  const autoEl = document.getElementById('svc-auto-count');

  const runningCount = servicesList.filter(s => {
    const st = (s.status || s.state || '').toLowerCase();
    return st.includes('running') || s.state === '4';
  }).length;

  const stoppedCount = servicesList.filter(s => {
    const st = (s.status || s.state || '').toLowerCase();
    return st.includes('stopped') || s.state === '1';
  }).length;

  const autoCount = servicesList.filter(s => (s.start_type || s.startup_type || '').toLowerCase().includes('auto')).length;

  if (totalEl) totalEl.textContent = servicesList.length;
  if (runningEl) runningEl.textContent = runningCount;
  if (stoppedEl) stoppedEl.textContent = stoppedCount;
  if (autoEl) autoEl.textContent = autoCount;

  applyServiceFilters();
}

/**
 * Применение фильтров поиска и состояния к таблице служб.
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

    if (query) {
      const matchName = (s.name || '').toLowerCase().includes(query);
      const matchDisp = (s.display_name || '').toLowerCase().includes(query);
      return matchName || matchDisp;
    }
    return true;
  });

  if (badge) badge.textContent = `${filtered.length} из ${servicesList.length} служб`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Службы не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.slice(0, 150).map(s => {
    const st = (s.status || s.state || '').toLowerCase();
    const isRunning = st.includes('running') || s.state === '4';
    const badgeClass = isRunning
      ? 'badge bg-success-subtle text-success border border-success'
      : 'badge bg-secondary-subtle text-secondary border border-secondary';
    const statusText = isRunning ? 'Running' : 'Stopped';

    return `
      <tr class="interactive-service-row" data-service-name="${escapeHtml(s.name)}" style="cursor: pointer;" title="Нажмите для вызова ИИ-досье службы">
        <td class="fw-bold font-monospace" style="color: var(--accent-color, #0ea5e9);">
          <span class="d-inline-flex align-items-center gap-1.5">
            <span>${escapeHtml(s.name)}</span>
          </span>
        </td>
        <td style="color: var(--text-color);">${escapeHtml(s.display_name || s.name)}</td>
        <td>
          <span class="${badgeClass}">
            ${statusText}
          </span>
        </td>
        <td class="small text-muted">${escapeHtml(s.start_type || s.startup_type || 'Manual')}</td>
        <td class="font-monospace small text-muted">${escapeHtml(String(s.pid || '—'))}</td>
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

  // Обработка клика по строкам таблицы для открытия универсального ИИ-досье службы
  tbody.querySelectorAll('.interactive-service-row').forEach(row => {
    row.addEventListener('click', (e) => {
      // Изоляция: не вызывать модальное окно при клике по кнопкам действий или элементам ввода
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

  // Обработка кнопок действий в строках
  tbody.querySelectorAll('.svc-action-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sName = btn.dataset.service;
      const sAct = btn.dataset.action;
      executeServiceCmd(sName, sAct);
    });
  });
}

/**
 * Открытие универсального модального окна ИИ-ассистента для службы Windows.
 * @param {Object} service - Объект с данными службы.
 */
export function openServiceAiModal(service) {
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

  const st = (service.status || service.state || '').toLowerCase();
  const isRunning = st.includes('running') || service.state === '4';
  const startType = service.start_type || service.startup_type || 'Manual';

  const badges = [
    {
      text: isRunning ? 'Running' : 'Stopped',
      class: isRunning ? 'badge bg-success-subtle text-success border border-success' : 'badge bg-secondary-subtle text-secondary border border-secondary'
    },
    {
      text: `Тип: ${startType}`,
      class: 'badge bg-info-subtle text-info border border-info'
    }
  ];

  if (service.pid) {
    badges.push({
      text: `PID: ${service.pid}`,
      class: 'badge bg-primary-subtle text-primary border border-primary font-monospace'
    });
  }

  if (service.is_orphaned) {
    badges.push({
      text: 'Orphaned (битый путь)',
      class: 'badge bg-danger-subtle text-danger border border-danger'
    });
  }

  const metadata = [
    { label: 'Имя службы (Service Name)', value: service.name, isCode: true },
    { label: 'Отображаемое имя (Display Name)', value: service.display_name || service.name },
    { label: 'Состояние (Status)', value: isRunning ? 'RUNNING (Работает)' : 'STOPPED (Остановлена)' },
    { label: 'Тип запуска (Startup Type)', value: startType },
    { label: 'Идентификатор процесса (PID)', value: service.pid ? String(service.pid) : '—', isCode: true },
    { label: 'Учетная запись (Account)', value: service.account || service.user_account || 'LocalSystem' },
    { label: 'Исполняемый файл (Binary Path)', value: service.binary_path || service.binpath || '—', isCode: true, fullWidth: true }
  ];

  modal.show({
    icon: '⚙️',
    title: service.name,
    subtitle: service.display_name ? `${service.display_name} | ${isRunning ? 'Running' : 'Stopped'}` : `Служба Windows | ${isRunning ? 'Running' : 'Stopped'}`,
    panelId: 'panel-windows-services-manager',
    tableType: 'service',
    badges: badges,
    metadata: metadata,
    rawTitle: 'Телеметрия службы Windows (JSON)',
    rawContent: JSON.stringify(service, null, 2),
    requestData: {
      name: service.name,
      display_name: service.display_name || service.name,
      status: isRunning ? 'RUNNING' : 'STOPPED',
      start_type: startType,
      pid: service.pid || null,
      binary_path: service.binary_path || service.binpath || '',
      account: service.account || service.user_account || 'LocalSystem',
      is_orphaned: Boolean(service.is_orphaned)
    },
    autoRun: false,
    actions: [
      {
        label: isRunning ? 'Остановить службу' : 'Запустить службу',
        icon: isRunning ? 'bi-stop-fill' : 'bi-play-fill',
        class: isRunning ? 'btn-outline-danger' : 'btn-outline-success',
        onClick: () => {
          executeServiceCmd(service.name, isRunning ? 'sc_stop' : 'sc_start');
        }
      },
      {
        label: 'Перезапустить',
        icon: 'bi-arrow-repeat',
        class: 'btn-outline-warning',
        onClick: async () => {
          if (isRunning) {
            await executeServiceCmd(service.name, 'sc_stop');
            setTimeout(() => {
              executeServiceCmd(service.name, 'sc_start');
            }, 1200);
          } else {
            executeServiceCmd(service.name, 'sc_start');
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
    const res = await fetch('/api/services-manager/action', {
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
      fetchServicesSummary();
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
  if (refreshBtn) refreshBtn.addEventListener('click', fetchServicesSummary);

  const searchInput = document.getElementById('svc-search-input');
  if (searchInput) searchInput.addEventListener('input', applyServiceFilters);

  const filterAll = document.getElementById('svc-filter-all');
  const filterRunning = document.getElementById('svc-filter-running');
  const filterStopped = document.getElementById('svc-filter-stopped');

  [filterAll, filterRunning, filterStopped].forEach(btn => {
    if (!btn) return;
    btn.addEventListener('click', () => {
      [filterAll, filterRunning, filterStopped].forEach(b => {
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

  registerTabPoller('tab-services-manager', fetchServicesSummary, 10000, { immediate: true });
}

window.initServicesManagerTab = initServicesManagerTab;
window.openServiceAiModal = openServiceAiModal;

// Автозапуск если вкладка уже в DOM
if (document.getElementById('svc-table') || document.getElementById('tab-services-manager')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initServicesManagerTab());
  } else {
    setTimeout(() => initServicesManagerTab(), 10);
  }
}
