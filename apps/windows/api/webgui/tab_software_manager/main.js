/**
 * =============================================================================
 * Process Name: Windows Software Manager Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом менеджера пакетов:
 *   WinGet, Microsoft Store (AppX/MSIX) и MSI/Реестр.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_software_manager/main.js?v=20261018_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initSoftwareManagerTab } from '/windows/api/webgui/tab_software_manager/main.js';
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_software_manager
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

var registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function() {};

var isInitialized = false;
let packagesList = [];
let currentSourceFilter = '';

export async function fetchSoftwareSummary() {
  try {
    const res = await fetch('/api/v1/software-manager/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderSoftware(data);
  } catch (err) {
    console.warn('[SoftwareManager] Ошибка получения списка ПО:', err);
    const tbody = document.getElementById('sw-tbody');
    if (tbody && packagesList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-4">Ошибка загрузки данных: ${err.message}</td></tr>`;
    }
  }
}

function renderSoftware(data) {
  packagesList = data.packages || [];

  const installedEl = document.getElementById('sw-installed-count');
  const upgradesEl = document.getElementById('sw-upgrades-count');
  const storeEl = document.getElementById('sw-store-count');
  const sourcesEl = document.getElementById('sw-sources-count');

  if (installedEl) installedEl.textContent = data.total_packages ?? packagesList.length;
  if (upgradesEl) upgradesEl.textContent = data.updates_available_count ?? data.upgrades_count ?? 0;
  if (storeEl) storeEl.textContent = data.store_packages_count ?? packagesList.filter(p => p.source === 'msstore').length;
  if (sourcesEl) sourcesEl.textContent = data.sources_count ?? (data.winget_available ? 'WinGet / MSI' : 'MSI');

  applySoftwareFilters();
}

function applySoftwareFilters() {
  const tbody = document.getElementById('sw-tbody');
  const searchInput = document.getElementById('sw-mgr-search-input') || document.getElementById('sw-search-input');
  const badge = document.getElementById('sw-table-badge');

  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

  const filtered = packagesList.filter(p => {
    // Фильтр по источнику
    if (currentSourceFilter) {
      const src = (p.source || '').toLowerCase();
      if (currentSourceFilter === 'msstore' && src !== 'msstore') return false;
      if (currentSourceFilter === 'winget' && src !== 'winget') return false;
      if (currentSourceFilter === 'msi' && src !== 'msi' && src !== 'registry') return false;
    }

    if (!query) return true;
    const nameMatch = (p.name || '').toLowerCase().includes(query);
    const idMatch = (p.package_id || p.id || '').toLowerCase().includes(query);
    const publisherMatch = (p.publisher || '').toLowerCase().includes(query);
    return nameMatch || idMatch || publisherMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${packagesList.length} пакетов`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Пакеты не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.slice(0, 200).map(p => {
    const name = p.name || 'Application';
    const id = p.package_id || p.id || '-';
    const ver = p.version || '-';
    const avail = p.available_version || p.latest_version || '-';
    const source = (p.source || 'winget').toLowerCase();
    const hasUpgrade = avail && avail !== '-' && avail !== ver;

    let sourceBadge = `<span class="badge bg-secondary">${source}</span>`;
    if (source === 'msstore') {
      sourceBadge = `<span class="badge bg-info-subtle text-info border border-info"><i class="bi bi-shop me-1"></i>MS Store</span>`;
    } else if (source === 'winget') {
      sourceBadge = `<span class="badge bg-primary-subtle text-primary border border-primary">WinGet</span>`;
    } else if (source === 'msi' || source === 'registry') {
      sourceBadge = `<span class="badge bg-success-subtle text-success border border-success">MSI</span>`;
    }

    const storeLinkBtn = (source === 'msstore' && id && id !== '-') ? `
      <a href="ms-windows-store://pdp/?productid=${encodeURIComponent(id)}" class="btn btn-xs btn-outline-info py-0 px-2 me-1" title="Открыть в Microsoft Store" target="_blank">
        <i class="bi bi-box-arrow-up-right"></i>
      </a>
    ` : '';

    return `
      <tr>
        <td class="fw-semibold text-light">
          ${name}
          ${p.publisher ? `<div class="text-secondary small font-monospace" style="font-size: 0.75rem;">${p.publisher}</div>` : ''}
        </td>
        <td class="font-monospace text-info small">${id}</td>
        <td class="text-muted small">${ver}</td>
        <td>
          <span class="badge ${hasUpgrade ? 'bg-warning text-dark' : 'bg-secondary'}">
            ${avail}
          </span>
        </td>
        <td>${sourceBadge}</td>
        <td class="text-end text-nowrap">
          ${storeLinkBtn}
          ${hasUpgrade ? `
            <button class="btn btn-xs btn-outline-warning py-0 px-2 sw-action-btn" data-id="${id}" data-action="upgrade" title="Обновить пакет">
              <i class="bi bi-arrow-up-circle"></i> Обновить
            </button>
          ` : `
            <button class="btn btn-xs btn-outline-danger py-0 px-2 sw-action-btn" data-id="${id}" data-action="uninstall" title="Удалить пакет">
              <i class="bi bi-trash"></i>
            </button>
          `}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.sw-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const pkgId = btn.dataset.id;
      const act = btn.dataset.action;
      executeSoftwareAction(pkgId, act);
    });
  });
}

async function executeSoftwareAction(packageId, action) {
  if (window.toast) window.toast.info('Пакетный менеджер', `${action}: ${packageId}`);
  try {
    const res = await fetch('/api/v1/software-manager/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ package_id: packageId, action: action, dry_run: false, confirmed_by_user: true })
    });
    const result = await res.json();
    if (res.ok) {
      if (window.toast) window.toast.success('Успех', `${packageId}: выполнено`);
      fetchSoftwareSummary();
    } else {
      if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой операции');
    }
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка сети', err.message);
  }
}

export function initSoftwareManagerTab() {
  const refreshBtn = document.getElementById('sw-refresh-btn');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.addEventListener('click', () => fetchSoftwareSummary());
  }

  const checkUpgradesBtn = document.getElementById('sw-check-upgrades-btn');
  if (checkUpgradesBtn && !checkUpgradesBtn.dataset.bound) {
    checkUpgradesBtn.dataset.bound = 'true';
    checkUpgradesBtn.addEventListener('click', () => {
      if (window.toast) window.toast.info('Проверка', 'Поиск доступных обновлений...');
      fetchSoftwareSummary();
    });
  }

  // Фильтры источников
  const filterBtns = document.querySelectorAll('#sw-source-filters .sw-src-btn');
  filterBtns.forEach(btn => {
    if (!btn.dataset.bound) {
      btn.dataset.bound = 'true';
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSourceFilter = btn.dataset.source || '';
        applySoftwareFilters();
      });
    }
  });

  const searchInput = document.getElementById('sw-mgr-search-input') || document.getElementById('sw-search-input');
  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    searchInput.addEventListener('input', applySoftwareFilters);
  }

  if (!isInitialized) {
    registerTabPoller('tab-software-manager', fetchSoftwareSummary, 30000, { immediate: true });
    isInitialized = true;
  }
  fetchSoftwareSummary();
}

window.initSoftwareManagerTab = initSoftwareManagerTab;
window.fetchSoftwareSummary = fetchSoftwareSummary;

if (document.getElementById('tab-software-manager') && document.getElementById('sw-tbody')) {
  initSoftwareManagerTab();
}

