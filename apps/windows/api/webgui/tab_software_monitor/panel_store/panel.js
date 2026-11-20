/**
 * =============================================================================
 * Process Name: Windows Software Monitor - Microsoft Store Packages Panel
 * =============================================================================
 * Description:
 *   Клиентская панель мониторинга и управления приложениями,
 *   установленными через Microsoft Store (AppX/MSIX/msstore).
 *
 * File: panel_store/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_monitor/panel_store
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let storePackages = [];
let isStoreInitialized = false;

/**
 * Инициализирует панель программ Microsoft Store.
 */
export async function initStorePackagesPanel() {
  const container = document.getElementById('sw-store-embed-container');
  if (!container) return;

  if (!isStoreInitialized) {
    renderStoreLayout(container);
    bindStoreEvents();
    isStoreInitialized = true;
  }

  await fetchStorePackages();
}

/**
 * Создает разметку субпанели Microsoft Store.
 * @param {HTMLElement} container - Родительский контейнер.
 */
function renderStoreLayout(container) {
  container.innerHTML = `
    <div class="row g-2 mb-3">
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Приложений Microsoft Store 🛍️</div>
          <div class="fs-4 fw-bold mt-1 text-info" id="store-pkg-count">--</div>
          <div class="small text-muted mt-1">Источник msstore / AppX / MSIX</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Доступно обновлений ⬆️</div>
          <div class="fs-4 fw-bold mt-1 text-warning" id="store-pkg-updates">--</div>
          <div class="small text-muted mt-1">По данным каталога Store</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3 d-flex flex-column justify-content-between">
          <div>
            <div class="text-muted small text-uppercase fw-semibold">Быстрые действия 🚀</div>
            <div class="small text-muted mt-1">Запуск системного клиента магазина</div>
          </div>
          <div class="mt-2">
            <a href="ms-windows-store://home" class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5" target="_blank">
              <i class="bi bi-shop"></i>
              <span>Открыть Microsoft Store</span>
            </a>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex align-items-center justify-content-between mb-3 p-2 bg-dark rounded border border-secondary flex-wrap gap-2">
      <div class="d-flex align-items-center gap-2">
        <button class="btn btn-sm btn-primary d-flex align-items-center gap-1.5" id="store-refresh-btn">
          <i class="bi bi-arrow-clockwise"></i>
          <span>Обновить каталог Store</span>
        </button>
        <span class="badge rounded-pill bg-info-subtle text-info border border-info px-3 py-2" id="store-status-badge">
          ● Готов
        </span>
      </div>
      <div class="d-flex align-items-center gap-2">
        <input class="form-control form-control-sm bg-dark text-white border-secondary" id="store-search-input" placeholder="Поиск в Store по названию или ID..." style="width: 280px;" type="text"/>
      </div>
    </div>

    <div class="card bg-dark text-white border-secondary shadow-sm">
      <div class="card-header border-secondary d-flex align-items-center justify-content-between py-2 px-3">
        <span class="fw-semibold"><i class="bi bi-shop text-info me-2"></i>Установленные приложения Microsoft Store</span>
        <span class="badge bg-secondary" id="store-table-badge">0 приложений</span>
      </div>
      <div class="card-body p-0 table-responsive" style="max-height: 520px; overflow-y: auto;">
        <table class="table table-dark table-hover table-striped align-middle mb-0 small" id="store-table">
          <thead class="sticky-top bg-dark">
            <tr class="text-secondary">
              <th>Приложение / Издатель</th>
              <th>Идентификатор Store (ID)</th>
              <th>Версия</th>
              <th>Доступно</th>
              <th class="text-end">Действия</th>
            </tr>
          </thead>
          <tbody id="store-tbody">
            <tr><td class="text-center text-muted py-4" colspan="5">Загрузка приложений Microsoft Store...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * Привязывает обработчики событий к элементам субпанели Store.
 */
function bindStoreEvents() {
  const refreshBtn = document.getElementById('store-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchStorePackages(true));
  }

  const searchInput = document.getElementById('store-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', applyStoreFilter);
  }
}

/**
 * Загружает список приложений Microsoft Store с бэкенда.
 * @param {boolean} forceRefresh - Принудительное обновление.
 */
export async function fetchStorePackages(forceRefresh = false) {
  const tbody = document.getElementById('store-tbody');
  const statusBadge = document.getElementById('store-status-badge');

  if (statusBadge) {
    statusBadge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-2';
    statusBadge.textContent = '● Опрос Store...';
  }

  try {
    const url = forceRefresh ? '/api/v1/software-manager/store?refresh=true' : '/api/v1/software-manager/store';
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    storePackages = Array.isArray(data) ? data : [];

    const countEl = document.getElementById('store-pkg-count');
    const updatesEl = document.getElementById('store-pkg-updates');
    if (countEl) countEl.textContent = storePackages.length;
    if (updatesEl) {
      const updCount = storePackages.filter(p => p.available_version && p.available_version !== p.version).length;
      updatesEl.textContent = updCount;
    }

    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
      statusBadge.textContent = '● Актуально';
    }

    applyStoreFilter();
  } catch (err) {
    console.warn('[StorePanel] Ошибка загрузки пакетов Store:', err);
    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-2';
      statusBadge.textContent = '● Ошибка связи';
    }
    if (tbody && storePackages.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Не удалось получить данные Microsoft Store: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Фильтрация и рендеринг таблицы программ Microsoft Store.
 */
function applyStoreFilter() {
  const tbody = document.getElementById('store-tbody');
  const searchInput = document.getElementById('store-search-input');
  const badge = document.getElementById('store-table-badge');
  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const filtered = storePackages.filter(p => {
    if (!query) return true;
    const nameMatch = (p.name || '').toLowerCase().includes(query);
    const idMatch = (p.package_id || p.store_id || '').toLowerCase().includes(query);
    const pubMatch = (p.publisher || '').toLowerCase().includes(query);
    return nameMatch || idMatch || pubMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${storePackages.length} приложений`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Приложения Microsoft Store не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(p => {
    const name = escapeHtml(p.name || 'Store Application');
    const id = escapeHtml(p.package_id || p.store_id || '-');
    const ver = escapeHtml(p.version || '-');
    const avail = escapeHtml(p.available_version || '-');
    const hasUpgrade = avail && avail !== '-' && avail !== ver;

    return `
      <tr>
        <td class="fw-semibold text-light">
          <div><i class="bi bi-shop text-info me-1.5"></i>${name}</div>
          ${p.publisher ? `<div class="text-secondary small font-monospace" style="font-size: 0.75rem;">${escapeHtml(p.publisher)}</div>` : ''}
        </td>
        <td class="font-monospace text-info small">${id}</td>
        <td class="text-muted small">${ver}</td>
        <td>
          <span class="badge ${hasUpgrade ? 'bg-warning text-dark' : 'bg-secondary'}">
            ${avail}
          </span>
        </td>
        <td class="text-end text-nowrap">
          <a href="ms-windows-store://pdp/?productid=${encodeURIComponent(p.store_id || id)}" class="btn btn-xs btn-outline-info py-0 px-2 me-1" title="Открыть карточку в Microsoft Store" target="_blank">
            <i class="bi bi-box-arrow-up-right me-1"></i>В магазин
          </a>
          ${hasUpgrade ? `
            <button class="btn btn-xs btn-outline-warning py-0 px-2 store-action-btn" data-id="${id}" data-action="upgrade" title="Обновить приложение">
              <i class="bi bi-arrow-up-circle"></i> Обновить
            </button>
          ` : `
            <button class="btn btn-xs btn-outline-danger py-0 px-2 store-action-btn" data-id="${id}" data-action="uninstall" title="Удалить приложение">
              <i class="bi bi-trash"></i>
            </button>
          `}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.store-action-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pkgId = btn.dataset.id;
      const act = btn.dataset.action;
      if (window.toast) window.toast.info('Microsoft Store', `${act}: ${pkgId}`);
      try {
        const res = await fetch('/api/v1/software-manager/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ package_id: pkgId, action: act, dry_run: false, confirmed_by_user: true })
        });
        const result = await res.json();
        if (res.ok) {
          if (window.toast) window.toast.success('Успех', `${pkgId}: операция выполнена`);
          fetchStorePackages(true);
        } else {
          if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой операции');
        }
      } catch (err) {
        if (window.toast) window.toast.error('Ошибка сети', err.message);
      }
    });
  });
}
