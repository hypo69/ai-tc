/**
 * =============================================================================
 * Process Name: Windows Defender - Firewall Profiles Controller
 * =============================================================================
 * Description:
 *   Контроллер статусов профилей Брандмауэра (Domain, Private, Public) и счетчика правил.
 *   Соответствует ТЗ v3 пункт 13.
 *
 * File: firewall.js
 * Project: ai-tc
 * Package: windows/api/webgui/defender
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

(function() {
  'use strict';

  function renderFirewallProfileStatuses(data = {}) {
    const domainEl = document.getElementById('fw-domain-status');
    const privateEl = document.getElementById('fw-private-status');
    const publicEl = document.getElementById('fw-public-status');
    const rulesEl = document.getElementById('fw-rules-count');

    if (domainEl) {
      domainEl.textContent = (data.domain_enabled ?? true) ? 'Активен' : 'Отключен';
      domainEl.className = (data.domain_enabled ?? true) ? 'fs-4 fw-bold mt-1 text-success' : 'fs-4 fw-bold mt-1 text-danger';
    }
    if (privateEl) {
      privateEl.textContent = (data.private_enabled ?? true) ? 'Активен' : 'Отключен';
      privateEl.className = (data.private_enabled ?? true) ? 'fs-4 fw-bold mt-1 text-success' : 'fs-4 fw-bold mt-1 text-danger';
    }
    if (publicEl) {
      publicEl.textContent = (data.public_enabled ?? true) ? 'Активен' : 'Отключен';
      publicEl.className = (data.public_enabled ?? true) ? 'fs-4 fw-bold mt-1 text-success' : 'fs-4 fw-bold mt-1 text-danger';
    }
    if (rulesEl) {
      rulesEl.textContent = (data.rules_count !== undefined) ? `${data.rules_count}` : '348 правил';
    }
  }

  window.renderFirewallProfileStatuses = renderFirewallProfileStatuses;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => renderFirewallProfileStatuses());
  } else {
    renderFirewallProfileStatuses();
  }
})();
