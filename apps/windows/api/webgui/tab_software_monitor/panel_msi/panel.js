/**
 * =============================================================================
 * Process Name: Windows Software Monitor - MSI Packages Panel
 * =============================================================================
 * Description:
 *   Клиентская панель мониторинга и управления пакетами,
 *   установленными через Windows Installer (MSI / msiexec) и системный реестр.
 *
 * File: panel_msi/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_monitor/panel_msi
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let msiPackages = [];
let isMsiInitialized = false;

/**
 * Инициализирует панель пакетов MSI.
 */
export async function initMsiPackagesPanel() {
  const container = document.getElementById('sw-msi-embed-container');
  if (!container) return;

  if (!isMsiInitialized) {
    renderMsiLayout(container);
    bindMsiEvents();
    isMsiInitialized = true;
  }

  await fetchMsiPackages();
}

/**
 * Создает разметку субпанели пакетов MSI.
 * @param {HTMLElement} container - Родительский контейнер.
 */
function renderMsiLayout(container) {
  container.innerHTML = `
    <div class="row g-2 mb-3">
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Пакетов MSI / Реестр ⚙️</div>
          <div class="fs-4 fw-bold mt-1 text-success" id="msi-pkg-count">--</div>
          <div class="small text-muted mt-1">Windows Installer &amp; Registry</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Формат пакетов 🛡️</div>
          <div class="fs-4 fw-bold mt-1 text-info">MSI (.msi)</div>
          <div class="small text-muted mt-1">Транзакционная установка и откат</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3 d-flex flex-column justify-content-between">
          <div>
            <div class="text-muted small text-uppercase fw-semibold">Диспетчер службы 🧰</div>
            <div class="small text-muted mt-1">Служба msiexec.exe / Windows Installer</div>
          </div>
          <div class="mt-2">
            <span class="badge bg-success-subtle text-success border border-success px-2 py-1">
              <i class="bi bi-gear-wide-connected me-1"></i> Windows Installer
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex align-items-center justify-content-between mb-3 p-2 bg-dark rounded border border-secondary flex-wrap gap-2">
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <button class="btn btn-sm btn-primary d-flex align-items-center gap-1.5" id="msi-refresh-btn">
          <i class="bi bi-arrow-clockwise"></i>
          <span>Обновить каталог MSI</span>
        </button>
        <span class="badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2" id="msi-status-badge">
          ● Готов
        </span>
      </div>
      <div class="d-flex align-items-center gap-2">
        <input class="form-control form-control-sm bg-dark text-white border-secondary" id="msi-search-input" placeholder="Поиск MSI по названию, коду или издателю..." style="width: 280px;" type="text"/>
      </div>
    </div>

    <div class="card bg-dark text-white border-secondary shadow-sm">
      <div class="card-header border-secondary d-flex align-items-center justify-content-between py-2 px-3">
        <span class="fw-semibold"><i class="bi bi-gear-wide-connected text-success me-2"></i>Установленные пакеты MSI и компоненты установщика</span>
        <span class="badge bg-secondary" id="msi-table-badge">0 пакетов</span>
      </div>
      <div class="card-body p-0 table-responsive" style="max-height: 520px; overflow-y: auto;">
        <table class="table table-dark table-hover table-striped align-middle mb-0 small" id="msi-table">
          <thead class="sticky-top bg-dark">
            <tr class="text-secondary">
              <th>Программа / Издатель</th>
              <th>Код продукта / Идентификатор (ID)</th>
              <th>Версия</th>
              <th>Источник</th>
              <th class="text-end">Действия</th>
            </tr>
          </thead>
          <tbody id="msi-tbody">
            <tr><td class="text-center text-muted py-4" colspan="5">Загрузка пакетов MSI...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * Привязывает обработчики событий панели MSI.
 */
function bindMsiEvents() {
  const refreshBtn = document.getElementById('msi-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchMsiPackages(true));
  }

  const searchInput = document.getElementById('msi-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', applyMsiFilter);
  }
}

/**
 * Загружает список пакетов MSI с сервера.
 * @param {boolean} forceRefresh - Флаг принудительного обновления.
 */
export async function fetchMsiPackages(forceRefresh = false) {
  const tbody = document.getElementById('msi-tbody');
  const statusBadge = document.getElementById('msi-status-badge');

  if (statusBadge) {
    statusBadge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-2';
    statusBadge.textContent = '● Опрос MSI...';
  }

  try {
    const url = forceRefresh ? '/api/v1/software-manager/packages?source=msi&refresh=true' : '/api/v1/software-manager/packages?source=msi';
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    msiPackages = Array.isArray(data) ? data.filter(p => {
      const src = (p.source || '').toLowerCase();
      return src === 'msi' || src === 'registry';
    }) : [];

    const countEl = document.getElementById('msi-pkg-count');
    if (countEl) countEl.textContent = msiPackages.length;

    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
      statusBadge.textContent = '● Актуально';
    }

    applyMsiFilter();
  } catch (err) {
    console.warn('[MsiPanel] Ошибка загрузки пакетов MSI:', err);
    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-2';
      statusBadge.textContent = '● Ошибка связи';
    }
    if (tbody && msiPackages.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Не удалось получить данные MSI: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Фильтрация и вывод таблицы пакетов MSI.
 */
function applyMsiFilter() {
  const tbody = document.getElementById('msi-tbody');
  const searchInput = document.getElementById('msi-search-input');
  const badge = document.getElementById('msi-table-badge');
  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const filtered = msiPackages.filter(p => {
    if (!query) return true;
    const nameMatch = (p.name || '').toLowerCase().includes(query);
    const idMatch = (p.package_id || p.id || '').toLowerCase().includes(query);
    const pubMatch = (p.publisher || '').toLowerCase().includes(query);
    return nameMatch || idMatch || pubMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${msiPackages.length} пакетов`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Пакеты MSI не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(p => {
    const name = escapeHtml(p.name || 'MSI Application');
    const id = escapeHtml(p.package_id || p.id || '-');
    const ver = escapeHtml(p.version || '-');

    return `
      <tr>
        <td class="fw-semibold text-light">
          <div><i class="bi bi-gear-wide-connected text-success me-1.5"></i>${name}</div>
          ${p.publisher ? `<div class="text-secondary small font-monospace" style="font-size: 0.75rem;">${escapeHtml(p.publisher)}</div>` : ''}
        </td>
        <td class="font-monospace text-info small">${id}</td>
        <td class="text-muted small">${ver}</td>
        <td>
          <span class="badge bg-success-subtle text-success border border-success">
            MSI
          </span>
        </td>
        <td class="text-end text-nowrap">
          <button class="btn btn-xs btn-outline-danger py-0 px-2 msi-action-btn" data-id="${id}" data-action="uninstall" title="Удалить пакет MSI">
            <i class="bi bi-trash"></i> Удалить
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.msi-action-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pkgId = btn.dataset.id;
      const act = btn.dataset.action;
      if (window.toast) window.toast.info('Пакеты MSI', `${act}: ${pkgId}`);
      try {
        const res = await fetch('/api/v1/software-manager/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ package_id: pkgId, action: act, dry_run: false, confirmed_by_user: true })
        });
        const result = await res.json();
        if (res.ok) {
          if (window.toast) window.toast.success('Успех', `${pkgId}: операция выполнена`);
          fetchMsiPackages(true);
        } else {
          if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой операции');
        }
      } catch (err) {
        if (window.toast) window.toast.error('Ошибка сети', err.message);
      }
    });
  });
}
