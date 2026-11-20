/**
 * @file apps/windows/api/webgui/tab_defender_firewall/panel_firewall/panel.js
 * @description Панель управления Брандмауэром Windows (профили Domain/Private/Public, netsh advfirewall правила)
 * @author hypo69
 * @version 1.1.0
 * Updated: 2026-11-20 16:45:00
 */

import { escapeHtml } from '../common/ui_utils.js';

let firewallRulesList = [];
let isFirewallInitialized = false;
let inFlightFirewallPromise = null;

/**
 * Проверка, открыта ли сейчас субвкладка Брандмауэра
 * @returns {boolean}
 */
export function isFirewallSubtabActive() {
  const fwPane = document.getElementById('subpane-firewall');
  return fwPane ? fwPane.classList.contains('active') : false;
}

/**
 * Отрисовка профилей и правил Брандмауэра
 * @param {Object} data
 */
export function renderFirewall(data) {
  if (!data) return;
  firewallRulesList = data.rules || [];

  const domEl = document.getElementById('fw-domain-status');
  const privEl = document.getElementById('fw-private-status');
  const pubEl = document.getElementById('fw-public-status');
  const rulesCountEl = document.getElementById('fw-rules-count');

  const getProfileStatus = (pName, fallbackField) => {
    if (data[fallbackField]) return data[fallbackField];
    if (Array.isArray(data.profiles)) {
      const found = data.profiles.find(p => (p.profile_type || '').toLowerCase() === pName.toLowerCase());
      if (found) return found.enabled ? 'ON' : 'OFF';
    }
    return 'ON';
  };

  const domStatus = getProfileStatus('domain', 'domain_profile');
  const privStatus = getProfileStatus('private', 'private_profile');
  const pubStatus = getProfileStatus('public', 'public_profile');

  const isDomOn = domStatus === 'ON' || domStatus === true || domStatus === 'Активен';
  const isPrivOn = privStatus === 'ON' || privStatus === true || privStatus === 'Активен';
  const isPubOn = pubStatus === 'ON' || pubStatus === true || pubStatus === 'Активен';

  if (domEl) {
    domEl.textContent = isDomOn ? 'Активен' : 'Отключен';
    domEl.className = `fs-4 fw-bold mt-1 ${isDomOn ? 'text-success' : 'text-danger'}`;
  }
  if (privEl) {
    privEl.textContent = isPrivOn ? 'Активен' : 'Отключен';
    privEl.className = `fs-4 fw-bold mt-1 ${isPrivOn ? 'text-success' : 'text-danger'}`;
  }
  if (pubEl) {
    pubEl.textContent = isPubOn ? 'Активен' : 'Отключен';
    pubEl.className = `fs-4 fw-bold mt-1 ${isPubOn ? 'text-success' : 'text-danger'}`;
  }
  if (rulesCountEl) {
    rulesCountEl.textContent = `${data.total_rules || firewallRulesList.length} правил`;
  }

  applyFirewallFilters();
}

/**
 * Применение поисковой фильтрации по таблице правил брандмауэра
 */
export function applyFirewallFilters() {
  const tbody = document.getElementById('fw-tbody');
  const searchInput = document.getElementById('fw-search-input');
  const badge = document.getElementById('fw-table-badge');

  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

  const filtered = firewallRulesList.filter(r => {
    if (!query) return true;
    const nameMatch = (r.name || r.rule_name || '').toLowerCase().includes(query);
    const portMatch = String(r.port || r.local_port || '').includes(query);
    const protoMatch = String(r.protocol || '').toLowerCase().includes(query);
    const dirMatch = String(r.direction || '').toLowerCase().includes(query);
    const actionMatch = String(r.action || '').toLowerCase().includes(query);
    return nameMatch || portMatch || protoMatch || dirMatch || actionMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${firewallRulesList.length} правил`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Правила не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.slice(0, 150).map(r => {
    const name = r.name || r.rule_name || 'Firewall Rule';
    const dir = r.direction || 'In';
    const action = r.action || 'Allow';
    const port = r.local_port || r.port || 'Any';
    const proto = r.protocol || 'TCP';
    const profile = r.profile || 'All';
    const enabled = r.enabled ?? true;
    const isAllow = String(action).toLowerCase().includes('allow') || String(action).toLowerCase().includes('разреш');

    return `
      <tr>
        <td class="fw-semibold text-body" style="word-break: break-all;">${escapeHtml(name)}</td>
        <td><span class="badge ${dir === 'In' ? 'bg-primary' : 'bg-info text-dark'}">${escapeHtml(dir)}</span></td>
        <td><span class="badge ${isAllow ? 'bg-success' : 'bg-danger'}">${escapeHtml(action)}</span></td>
        <td class="font-monospace small text-body">${escapeHtml(proto)}:${escapeHtml(port)}</td>
        <td class="small text-body-secondary">${escapeHtml(profile)}</td>
        <td><span class="badge ${enabled ? 'bg-success' : 'bg-secondary'}">${enabled ? 'Включено' : 'Выключено'}</span></td>
        <td class="text-end">
          <button class="btn btn-xs ${enabled ? 'btn-outline-warning' : 'btn-outline-success'} py-0 px-2 fw-toggle-btn" 
                  data-name="${escapeHtml(name)}" data-action="${enabled ? 'disable_rule' : 'enable_rule'}"
                  title="${enabled ? 'Отключить правило' : 'Включить правило'}">
            <i class="bi ${enabled ? 'bi-pause-fill' : 'bi-play-fill'}"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.fw-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const rName = btn.dataset.name;
      const rAct = btn.dataset.action;
      executeFirewallAction(rName, rAct);
    });
  });
}

/**
 * Получение сводки правил брандмауэра
 */
export async function fetchFirewallSummary() {
  if (inFlightFirewallPromise) {
    return inFlightFirewallPromise;
  }
  const tbody = document.getElementById('fw-tbody');
  if (tbody && (!firewallRulesList || firewallRulesList.length === 0)) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm text-primary me-2" role="status"></span>Опрос правил брандмауэра...</td></tr>';
  }
  inFlightFirewallPromise = (async () => {
    try {
      const res = await fetch('/api/v1/firewall-manager/summary');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderFirewall(data);
    } catch (err) {
      console.warn('[FirewallManager] Ошибка получения правил:', err);
      if (tbody && (!firewallRulesList || firewallRulesList.length === 0)) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4"><i class="bi bi-exclamation-triangle me-2"></i>Не удалось загрузить правила брандмауэра</td></tr>';
      }
    } finally {
      inFlightFirewallPromise = null;
    }
  })();
  return inFlightFirewallPromise;
}

/**
 * Принудительное пересканирование правил через netsh
 */
export async function forceRefreshFirewall() {
  const refreshBtn = document.getElementById('fw-refresh-btn');
  if (refreshBtn) refreshBtn.disabled = true;
  const tbody = document.getElementById('fw-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm text-primary me-2" role="status"></span>Пересканирование правил через netsh...</td></tr>';
  }
  try {
    const res = await fetch('/api/v1/firewall-manager/refresh', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderFirewall(data);
    if (window.toast) window.toast.success('Брандмауэр', 'Правила брандмауэра успешно обновлены');
  } catch (err) {
    console.warn('[FirewallManager] Ошибка принудительного обновления:', err);
    await fetchFirewallSummary();
  } finally {
    if (refreshBtn) refreshBtn.disabled = false;
  }
}

/**
 * Выполнение действия над правилом брандмауэра
 * @param {string} ruleName Имя правила
 * @param {string} action Действие ('enable_rule', 'disable_rule', 'reset_defaults')
 */
export async function executeFirewallAction(ruleName, action) {
  try {
    const res = await fetch('/api/v1/firewall-manager/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule_name: ruleName, action: action, dry_run: false, confirmed_by_user: true })
    });
    const result = await res.json();
    if (res.ok) {
      if (window.toast) window.toast.success('Брандмауэр', `${ruleName}: обновлено`);
      await fetchFirewallSummary();
    } else {
      if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой операции');
    }
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка сети', err.message);
  }
}

/**
 * Инициализация обработчиков событий панели брандмауэра
 */
export function bindFirewallControls() {
  if (isFirewallInitialized) return;
  isFirewallInitialized = true;

  const refreshBtn = document.getElementById('fw-refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', forceRefreshFirewall);

  const resetBtn = document.getElementById('fw-reset-defaults-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (confirm('Сбросить правила брандмауэра к значениям по умолчанию?')) {
        executeFirewallAction('all', 'reset_defaults');
      }
    });
  }

  const searchInput = document.getElementById('fw-search-input');
  if (searchInput) searchInput.addEventListener('input', applyFirewallFilters);

  if (window.registerTabPoller) {
    window.registerTabPoller('tab-defender-firewall', () => {
      if (isFirewallSubtabActive()) {
        fetchFirewallSummary();
      }
    }, 20000, { pollerId: 'tab-defender-firewall_fw', immediate: false });
  }
}

/**
 * Инициализация и загрузка данных субвкладки брандмауэра
 */
export function initFirewallSubtab() {
  bindFirewallControls();
  return fetchFirewallSummary();
}
