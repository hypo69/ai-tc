/**
 * =============================================================================
 * Process Name: Windows Firewall Manager Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_firewall_manager/main.js?v=20261001_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initFirewallManagerTab } from '/windows/api/webgui/tab_firewall_manager/main.js';
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_firewall_manager
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

/**
 * firewall_manager_tab/main.js — Управление брандмауэром Windows (netsh advfirewall)
 * Updated: 2026-10-16 17:05:00
 */

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};

var isInitialized = false;
let rulesList = [];
let inFlightSummaryPromise = null;

export async function fetchFirewallSummary() {
  if (inFlightSummaryPromise) {
    return inFlightSummaryPromise;
  }
  const tbody = document.getElementById('fw-tbody');
  if (tbody && (!rulesList || rulesList.length === 0)) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm text-primary me-2" role="status"></span>Опрос правил брандмауэра...</td></tr>';
  }
  inFlightSummaryPromise = (async () => {
    try {
      const res = await fetch('/api/v1/firewall-manager/summary');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderFirewall(data);
    } catch (err) {
      console.warn('[FirewallManager] Ошибка получения правил:', err);
      if (tbody && (!rulesList || rulesList.length === 0)) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4"><i class="bi bi-exclamation-triangle me-2"></i>Не удалось загрузить правила брандмауэра</td></tr>';
      }
    } finally {
      inFlightSummaryPromise = null;
    }
  })();
  return inFlightSummaryPromise;
}

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

function renderFirewall(data) {
  if (!data) return;
  rulesList = data.rules || [];

  const domEl = document.getElementById('fw-domain-status');
  const privEl = document.getElementById('fw-private-status');
  const pubEl = document.getElementById('fw-public-status');
  const rulesCountEl = document.getElementById('fw-rules-count');

  const getProfileVal = (pName, fallbackField) => {
    if (data[fallbackField]) return data[fallbackField];
    if (Array.isArray(data.profiles)) {
      const found = data.profiles.find(p => (p.profile_type || '').toLowerCase() === pName.toLowerCase());
      if (found) return found.enabled ? 'ON' : 'OFF';
    }
    return 'ON';
  };

  const domStatus = getProfileVal('domain', 'domain_profile');
  const privStatus = getProfileVal('private', 'private_profile');
  const pubStatus = getProfileVal('public', 'public_profile');

  if (domEl) {
    domEl.textContent = domStatus;
    domEl.className = `fs-4 fw-bold mt-1 ${domStatus === 'ON' ? 'text-success' : 'text-danger'}`;
  }
  if (privEl) {
    privEl.textContent = privStatus;
    privEl.className = `fs-4 fw-bold mt-1 ${privStatus === 'ON' ? 'text-success' : 'text-danger'}`;
  }
  if (pubEl) {
    pubEl.textContent = pubStatus;
    pubEl.className = `fs-4 fw-bold mt-1 ${pubStatus === 'ON' ? 'text-success' : 'text-danger'}`;
  }
  if (rulesCountEl) {
    rulesCountEl.textContent = data.total_rules || rulesList.length;
  }

  applyFirewallFilters();
}

function applyFirewallFilters() {
  const tbody = document.getElementById('fw-tbody');
  const searchInput = document.getElementById('fw-search-input');
  const badge = document.getElementById('fw-table-badge');

  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

  const filtered = rulesList.filter(r => {
    if (!query) return true;
    const nameMatch = (r.name || r.rule_name || '').toLowerCase().includes(query);
    const portMatch = String(r.port || r.local_port || '').includes(query);
    const protoMatch = String(r.protocol || '').toLowerCase().includes(query);
    return nameMatch || portMatch || protoMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${rulesList.length} правил`;

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

    const isAllow = action.toLowerCase().includes('allow') || action.toLowerCase().includes('разреш');

    return `
      <tr>
        <td class="fw-semibold text-body">${name}</td>
        <td><span class="badge ${dir === 'In' ? 'bg-primary' : 'bg-info'}">${dir}</span></td>
        <td><span class="badge ${isAllow ? 'bg-success' : 'bg-danger'}">${action}</span></td>
        <td class="font-monospace small text-body-secondary">${proto}:${port}</td>
        <td class="small text-body-secondary">${profile}</td>
        <td><span class="badge ${enabled ? 'bg-success' : 'bg-danger-subtle text-danger border border-danger fw-bold'}">${enabled ? 'Включено' : 'Выключено'}</span></td>
        <td class="text-end">
          <button class="btn btn-xs ${enabled ? 'btn-outline-warning' : 'btn-outline-success'} py-0 px-2 fw-toggle-btn" 
                  data-name="${name}" data-action="${enabled ? 'disable_rule' : 'enable_rule'}"
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

async function executeFirewallAction(ruleName, action) {
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

export function initFirewallManagerTab() {
  if (isInitialized) {
    fetchFirewallSummary();
    return;
  }
  isInitialized = true;

  const refreshBtn = document.getElementById('fw-refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', forceRefreshFirewall);

  const resetBtn = document.getElementById('fw-reset-defaults-btn');
  if (resetBtn) resetBtn.addEventListener('click', () => {
    if (confirm('Сбросить правила брандмауэра к значениям по умолчанию?')) {
      executeFirewallAction('all', 'reset_defaults');
    }
  });

  const searchInput = document.getElementById('fw-search-input');
  if (searchInput) searchInput.addEventListener('input', applyFirewallFilters);

  registerTabPoller('tab-defender-firewall', fetchFirewallSummary, 20000, { pollerId: 'fw_legacy_poller', immediate: false });
}

window.initFirewallManagerTab = initFirewallManagerTab;
window.fetchFirewallSummary = fetchFirewallSummary;
window.forceRefreshFirewall = forceRefreshFirewall;
window.renderFirewall = renderFirewall;

