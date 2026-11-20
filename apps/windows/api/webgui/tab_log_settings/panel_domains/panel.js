/**
 * =============================================================================
 * Process Name: Windows Log Settings - Domains & Catalog Panel
 * =============================================================================
 * Description:
 *   Модуль визуализации 7 доменов телеметрии Windows и иерархического
 *   каталога провайдеров Event Log с поиском и классификацией объемов.
 *
 * File: panel_domains/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_domains
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml, checkTabActive } from '../common/ui_utils.js';

let domainsData = [];
let catalogData = [];

/**
 * Загружает сводную информацию по 7 доменам телеметрии.
 */
export async function fetchDomainsSummary() {
  if (!checkTabActive('tab-log-settings')) return;

  try {
    const res = await fetch('/api/v1/log-settings/domains');
    if (!res.ok) return;
    const data = await res.json();
    domainsData = data.domains || [];

    renderDomainsCards(domainsData);

    const sysmonBadge = document.getElementById('ls-sysmon-badge');
    if (sysmonBadge) {
      if (data.sysmon_installed) {
        sysmonBadge.textContent = 'Sysmon: Активен ✅';
        sysmonBadge.className = 'badge bg-success font-monospace';
      } else {
        sysmonBadge.textContent = 'Sysmon: Не установлен';
        sysmonBadge.className = 'badge bg-secondary font-monospace';
      }
    }

    const totalRecords = domainsData.reduce((acc, d) => acc + (d.total_records || 0), 0);
    const totalRecordsStat = document.getElementById('ls-total-records-stat');
    if (totalRecordsStat) {
      totalRecordsStat.textContent = `Всего в журналах: ${totalRecords.toLocaleString()} записей`;
    }
  } catch (err) {
    console.debug('[LogSettings] Ошибка загрузки доменов:', err);
  }
}

/**
 * Отрисовывает карточки 7 доменов телеметрии.
 * @param {Array} domains - Список доменов.
 */
export function renderDomainsCards(domains) {
  const container = document.getElementById('ls-domains-cards-grid');
  if (!container) return;

  if (!domains || domains.length === 0) {
    container.innerHTML = '<div class="col-12 text-center text-muted py-3">Домены не найдены.</div>';
    return;
  }

  container.innerHTML = domains.map((d) => {
    const recordsStr = (d.total_records || 0).toLocaleString();
    const isActive = d.status === 'Active' || d.status === 'Активен';
    const badgeBg = isActive ? 'bg-success' : 'bg-secondary';

    return `
      <div class="col-12 col-sm-6 col-lg-3">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3 ls-domain-card" data-domain-id="${d.id}" style="cursor: pointer; transition: transform 0.15s ease, border-color 0.15s ease;">
          <div class="d-flex justify-content-between align-items-start mb-1">
            <strong class="text-light fs-6 text-truncate">${escapeHtml(d.title)}</strong>
            <span class="badge ${badgeBg} font-monospace" style="font-size: 0.68rem;">${escapeHtml(d.status)}</span>
          </div>
          <div class="small text-muted mb-2 text-truncate" style="font-size: 0.75rem;" title="${escapeHtml(d.description)}">
            ${escapeHtml(d.description)}
          </div>
          <div class="d-flex justify-content-between align-items-center mt-auto pt-2 border-top border-secondary small font-monospace">
            <span class="text-info">${d.channels_count} каналов</span>
            <span class="text-warning">${recordsStr} записей</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.ls-domain-card').forEach((card) => {
    card.addEventListener('click', () => {
      const domId = card.dataset.domainId;
      const select = document.getElementById('ls-catalog-domain-select');
      if (select) {
        select.value = domId;
        fetchEventCatalog();
      }
    });
  });
}

/**
 * Загружает каталог провайдеров событий согласно фильтрам.
 */
export async function fetchEventCatalog() {
  const domainSelect = document.getElementById('ls-catalog-domain-select');
  const searchInput = document.getElementById('ls-catalog-search-input');

  const domain = domainSelect ? domainSelect.value : '';
  const search = searchInput ? searchInput.value.trim() : '';

  try {
    const params = new URLSearchParams();
    if (domain) params.append('domain', domain);
    if (search) params.append('search', search);

    const res = await fetch(`/api/v1/log-settings/catalog?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    catalogData = data.catalog || [];
    renderCatalogTable(catalogData);
  } catch (err) {
    console.warn('[LogSettings] Ошибка каталога:', err);
  }
}

/**
 * Отрисовывает таблицу каталога провайдеров.
 * @param {Array} catalog - Список провайдеров.
 */
export function renderCatalogTable(catalog) {
  const tbody = document.getElementById('ls-catalog-tbody');
  const countLabel = document.getElementById('ls-catalog-count');
  if (!tbody) return;

  if (countLabel) countLabel.textContent = `${catalog.length} провайдеров`;

  if (!catalog || catalog.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Провайдеры по заданным критериям не найдены.</td></tr>';
    return;
  }

  tbody.innerHTML = catalog.map((e) => {
    let volBadge = 'bg-secondary';
    if (e.volume_rating === 'Extreme') volBadge = 'bg-danger';
    else if (e.volume_rating === 'High') volBadge = 'bg-warning text-dark';
    else if (e.volume_rating === 'Medium') volBadge = 'bg-info text-dark';
    else if (e.volume_rating === 'Low') volBadge = 'bg-success';

    const eventsList = Object.entries(e.key_events || {}).map(([id, desc]) => {
      return `<span class="badge bg-black border border-secondary text-warning font-monospace me-1 mb-1" title="${escapeHtml(desc)}">ID ${id}</span>`;
    }).join('');

    const targets = (e.correlation_targets || []).map((t) => {
      return `<span class="badge bg-secondary-subtle text-light font-monospace me-1" style="font-size: 0.68rem;">#${escapeHtml(t)}</span>`;
    }).join('');

    return `
      <tr>
        <td>
          <div class="fw-bold text-light font-monospace" style="font-size: 0.8rem;">${escapeHtml(e.provider)}</div>
          <div class="small text-info font-monospace text-truncate" style="max-width: 260px; font-size: 0.72rem;">${escapeHtml(e.channel)}</div>
          <div class="small text-muted text-truncate" style="max-width: 260px; font-size: 0.7rem;" title="${escapeHtml(e.description)}">${escapeHtml(e.description)}</div>
        </td>
        <td>
          <span class="badge bg-dark border border-secondary text-light">${escapeHtml(e.domain_title || e.domain)}</span>
        </td>
        <td>
          <div class="d-flex flex-wrap" style="max-width: 280px;">${eventsList}</div>
        </td>
        <td>
          <span class="badge ${volBadge}">${escapeHtml(e.volume_rating)}</span>
          <div class="small text-muted font-monospace mt-1" style="font-size: 0.7rem;">${(e.record_count || 0).toLocaleString()} rec</div>
        </td>
        <td>
          <div class="small text-light font-monospace">${escapeHtml(e.recommended_collector)}</div>
          <div class="small text-muted" style="font-size: 0.7rem;">
            ${e.realtime_support ? '<span class="text-success">ETW/Stream</span>' : '<span class="text-secondary">Pull</span>'}
            • <span class="text-warning">${escapeHtml(e.privilege_required)}</span>
          </div>
        </td>
        <td>
          <div class="d-flex flex-wrap">${targets}</div>
        </td>
      </tr>
    `;
  }).join('');
}
