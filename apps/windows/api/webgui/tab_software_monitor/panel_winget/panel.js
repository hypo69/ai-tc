/**
 * =============================================================================
 * Process Name: Windows Software Monitor - WinGet Packages Panel
 * =============================================================================
 * Description:
 *   Клиентская панель мониторинга и управления пакетами,
 *   установленными через Windows Package Manager (winget-cli).
 *
 * File: panel_winget/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_monitor/panel_winget
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let wingetPackages = [];
let isWingetInitialized = false;

/**
 * Ищет существующий инстанс AIModalDialog в текущем фрейме или родительских окнах.
 * @returns {Object|null} Инстанс AIModalDialog
 */
function findExistingAIModal() {
  if (typeof window !== 'undefined') {
    if (window.AIModalDialog && typeof window.AIModalDialog.show === 'function') {
      return window.AIModalDialog;
    }
    if (window.AITableModal && typeof window.AITableModal.show === 'function') {
      return window.AITableModal;
    }
    try {
      if (window.parent && window.parent !== window) {
        if (window.parent.AIModalDialog && typeof window.parent.AIModalDialog.show === 'function') {
          return window.parent.AIModalDialog;
        }
        if (window.parent.AITableModal && typeof window.parent.AITableModal.show === 'function') {
          return window.parent.AITableModal;
        }
      }
    } catch (_) {}
    try {
      if (window.top && window.top !== window) {
        if (window.top.AIModalDialog && typeof window.top.AIModalDialog.show === 'function') {
          return window.top.AIModalDialog;
        }
        if (window.top.AITableModal && typeof window.top.AITableModal.show === 'function') {
          return window.top.AITableModal;
        }
      }
    } catch (_) {}
  }
  return null;
}

/**
 * Гарантирует наличие и готовность инстанса AIModalDialog с автоподгрузкой.
 * @returns {Promise<Object|null>} Объект модального окна ИИ.
 */
export async function resolveAIModal() {
  let modal = findExistingAIModal();
  if (modal) return modal;

  if (!document.getElementById('link-ai-modal-dialog-style')) {
    const link = document.createElement('link');
    link.id = 'link-ai-modal-dialog-style';
    link.rel = 'stylesheet';
    link.href = '/html/ai_modal_dialog/style.css?v=20261115_v1';
    document.head.appendChild(link);
  }

  try {
    const mod = await import('/html/ai_modal_dialog/main.js?v=20261115_v1');
    if (mod && mod.AIModalDialog && typeof mod.AIModalDialog.show === 'function') {
      return mod.AIModalDialog;
    }
  } catch (err) {
    console.warn('[WinGetPanel] Ошибка импорта AIModalDialog:', err);
  }

  return findExistingAIModal();
}

/**
 * Открывает экспертное досье пакета WinGet в универсальном модальном окне ИИ.
 * @param {Object} pkg - Объект пакета WinGet.
 */
export async function openWingetAiModal(pkg) {
  if (!pkg) return;

  const modal = await resolveAIModal();
  if (!modal || typeof modal.show !== 'function') {
    console.warn('[WinGetPanel] AIModalDialog не найден в глобальной области видимости');
    if (window.showToast) {
      window.showToast('Модуль ИИ-помощника загружается, повторите попытку через секунду', 'info');
    }
    return;
  }

  const pkgId = pkg.package_id || pkg.id || 'Unknown.Package';
  const name = pkg.name || pkgId;
  const ver = pkg.version || 'Unknown';
  const avail = pkg.available_version || '-';
  const hasUpgrade = avail && avail !== '-' && avail !== ver;

  const badges = [
    { text: 'WinGet CLI', class: 'bg-primary-subtle text-primary border border-primary' },
    { text: `v${ver}`, class: 'bg-secondary' }
  ];

  if (hasUpgrade) {
    badges.push({ text: `Доступно: v${avail}`, class: 'bg-warning text-dark' });
  } else {
    badges.push({ text: 'Актуальная версия', class: 'bg-success-subtle text-success border border-success' });
  }

  const metadata = [
    { key: 'Имя приложения', value: name },
    { key: 'WinGet ID', value: pkgId },
    { key: 'Установленная версия', value: ver },
    { key: 'Доступная версия', value: avail },
    { key: 'Издатель', value: pkg.publisher || 'Не указан' },
    { key: 'Источник', value: 'Windows Package Manager (winget-cli)' }
  ];

  const actions = [
    {
      label: 'Команда winget show',
      icon: 'bi-terminal',
      class: 'btn-outline-info',
      onClick: async () => {
        const cmd = `winget show --id "${pkgId}" --exact`;
        try {
          await navigator.clipboard.writeText(cmd);
          if (window.showToast) {
            window.showToast(`Команда скопирована в буфер:\n${cmd}`, 'success');
          } else if (window.toast) {
            window.toast.success('Скопировано', cmd);
          } else {
            alert(`Команда скопирована в буфер:\n${cmd}`);
          }
        } catch (_) {
          prompt('Скопируйте команду winget show вручную:', cmd);
        }
      }
    }
  ];

  if (hasUpgrade) {
    actions.unshift({
      label: 'Обновить пакет',
      icon: 'bi-arrow-up-circle',
      class: 'btn-outline-warning',
      onClick: async () => {
        if (window.toast) window.toast.info('WinGet', `Обновление ${pkgId}...`);
        try {
          const res = await fetch('/api/v1/software-manager/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package_id: pkgId, action: 'upgrade', dry_run: false, confirmed_by_user: true })
          });
          const result = await res.json();
          if (res.ok) {
            if (window.toast) window.toast.success('Успех', `${pkgId}: пакет обновлен`);
            fetchWingetPackages(true);
          } else {
            if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой обновления');
          }
        } catch (err) {
          if (window.toast) window.toast.error('Ошибка сети', err.message);
        }
      }
    });
  }

  modal.show({
    icon: '📦',
    title: name,
    subtitle: `${pkgId}${pkg.publisher ? ` • ${pkg.publisher}` : ''}`,
    panelId: 'panel-software-monitor-winget',
    tableType: 'software',
    badges: badges,
    metadata: metadata,
    rawTitle: 'Телеметрия пакета WinGet (JSON)',
    rawContent: JSON.stringify(pkg, null, 2),
    requestData: pkg,
    autoRun: true,
    actions: actions
  });
}

/**
 * Инициализирует панель пакетов WinGet.
 */
export async function initWingetPackagesPanel() {
  const container = document.getElementById('sw-winget-embed-container') ||
                    document.getElementById('sw-packages-embed-container');
  if (!container) return;

  if (!isWingetInitialized) {
    renderWingetLayout(container);
    bindWingetEvents();
    isWingetInitialized = true;
  }

  await fetchWingetPackages();
}

/**
 * Создает разметку субпанели WinGet пакетов.
 * @param {HTMLElement} container - Родительский контейнер.
 */
function renderWingetLayout(container) {
  container.innerHTML = `
    <div class="row g-2 mb-3">
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Пакетов WinGet 📦</div>
          <div class="fs-4 fw-bold mt-1 text-primary" id="winget-pkg-count">--</div>
          <div class="small text-muted mt-1">Репозиторий winget-cli</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3">
          <div class="text-muted small text-uppercase fw-semibold">Доступно обновлений ⬆️</div>
          <div class="fs-4 fw-bold mt-1 text-warning" id="winget-pkg-updates">--</div>
          <div class="small text-muted mt-1">По данным манифестов WinGet</div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="card bg-dark text-white border-secondary h-100 shadow-sm p-3 d-flex flex-column justify-content-between">
          <div>
            <div class="text-muted small text-uppercase fw-semibold">Источник данных 🌐</div>
            <div class="small text-muted mt-1">Windows Package Manager (CLI)</div>
          </div>
          <div class="mt-2">
            <span class="badge bg-primary-subtle text-primary border border-primary px-2 py-1">
              <i class="bi bi-box-seam me-1"></i> winget.exe
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex align-items-center justify-content-between mb-3 p-2 bg-dark rounded border border-secondary flex-wrap gap-2">
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <button class="btn btn-sm btn-primary d-flex align-items-center gap-1.5" id="winget-refresh-btn">
          <i class="bi bi-arrow-clockwise"></i>
          <span>Обновить WinGet</span>
        </button>
        <span class="badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2" id="winget-status-badge">
          ● Готов
        </span>
      </div>
      <div class="d-flex align-items-center gap-2">
        <input class="form-control form-control-sm bg-dark text-white border-secondary" id="winget-search-input" placeholder="Поиск пакета WinGet по названию или ID..." style="width: 280px;" type="text"/>
      </div>
    </div>

    <div class="card bg-dark text-white border-secondary shadow-sm">
      <div class="card-header border-secondary d-flex align-items-center justify-content-between py-2 px-3">
        <span class="fw-semibold"><i class="bi bi-box-seam text-primary me-2"></i>Установленные пакеты WinGet</span>
        <span class="badge bg-secondary" id="winget-table-badge">0 пакетов</span>
      </div>
      <div class="card-body p-0 table-responsive" style="max-height: 520px; overflow-y: auto;">
        <table class="table table-dark table-hover table-striped align-middle mb-0 small" id="winget-table">
          <thead class="sticky-top bg-dark">
            <tr class="text-secondary">
              <th>Приложение / Издатель</th>
              <th>Идентификатор WinGet (ID)</th>
              <th>Версия</th>
              <th>Доступно</th>
              <th class="text-end">Действия</th>
            </tr>
          </thead>
          <tbody id="winget-tbody">
            <tr><td class="text-center text-muted py-4" colspan="5">Загрузка пакетов WinGet...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * Привязывает обработчики событий панели WinGet.
 */
function bindWingetEvents() {
  const refreshBtn = document.getElementById('winget-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchWingetPackages(true));
  }

  const searchInput = document.getElementById('winget-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', applyWingetFilter);
  }
}

/**
 * Загружает список пакетов WinGet с сервера.
 * @param {boolean} forceRefresh - Флаг принудительного обновления.
 */
export async function fetchWingetPackages(forceRefresh = false) {
  const tbody = document.getElementById('winget-tbody');
  const statusBadge = document.getElementById('winget-status-badge');

  if (statusBadge) {
    statusBadge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-2';
    statusBadge.textContent = '● Опрос WinGet...';
  }

  try {
    const url = forceRefresh ? '/api/v1/software-manager/packages?source=winget&refresh=true' : '/api/v1/software-manager/packages?source=winget';
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    wingetPackages = Array.isArray(data) ? data.filter(p => (p.source || '').toLowerCase() === 'winget') : [];

    const countEl = document.getElementById('winget-pkg-count');
    const updatesEl = document.getElementById('winget-pkg-updates');
    if (countEl) countEl.textContent = wingetPackages.length;
    if (updatesEl) {
      const updCount = wingetPackages.filter(p => p.available_version && p.available_version !== p.version).length;
      updatesEl.textContent = updCount;
    }

    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
      statusBadge.textContent = '● Актуально';
    }

    applyWingetFilter();
  } catch (err) {
    console.warn('[WinGetPanel] Ошибка загрузки пакетов WinGet:', err);
    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-2';
      statusBadge.textContent = '● Ошибка связи';
    }
    if (tbody && wingetPackages.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Не удалось получить данные WinGet: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Фильтрация и вывод таблицы пакетов WinGet.
 */
function applyWingetFilter() {
  const tbody = document.getElementById('winget-tbody');
  const searchInput = document.getElementById('winget-search-input');
  const badge = document.getElementById('winget-table-badge');
  if (!tbody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const filtered = wingetPackages.filter(p => {
    if (!query) return true;
    const nameMatch = (p.name || '').toLowerCase().includes(query);
    const idMatch = (p.package_id || p.id || '').toLowerCase().includes(query);
    const pubMatch = (p.publisher || '').toLowerCase().includes(query);
    return nameMatch || idMatch || pubMatch;
  });

  if (badge) badge.textContent = `${filtered.length} из ${wingetPackages.length} пакетов`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Пакеты WinGet не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map((p, idx) => {
    const name = escapeHtml(p.name || 'WinGet Application');
    const id = escapeHtml(p.package_id || p.id || '-');
    const ver = escapeHtml(p.version || '-');
    const avail = escapeHtml(p.available_version || '-');
    const hasUpgrade = avail && avail !== '-' && avail !== ver;

    return `
      <tr class="winget-table-row" data-index="${idx}" style="cursor: pointer;" title="Нажмите для ИИ-анализа пакета WinGet">
        <td class="fw-semibold text-light">
          <div><i class="bi bi-box-seam text-primary me-1.5"></i>${name}</div>
          ${p.publisher ? `<div class="text-secondary small font-monospace" style="font-size: 0.75rem;">${escapeHtml(p.publisher)}</div>` : ''}
        </td>
        <td class="font-monospace text-info small">${id}</td>
        <td class="text-muted small">${ver}</td>
        <td>
          <span class="badge ${hasUpgrade ? 'bg-warning text-dark' : 'bg-secondary'}">
            ${avail}
          </span>
        </td>
        <td class="text-end text-nowrap no-modal-trigger" onclick="event.stopPropagation();">
          ${hasUpgrade ? `
            <button class="btn btn-xs btn-outline-warning py-0 px-2 winget-action-btn me-1" data-id="${id}" data-action="upgrade" title="Обновить пакет WinGet">
              <i class="bi bi-arrow-up-circle"></i> Обновить
            </button>
          ` : ''}
          <button class="btn btn-xs btn-outline-danger py-0 px-2 winget-action-btn" data-id="${id}" data-action="uninstall" title="Удалить пакет WinGet">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.winget-table-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) {
        return;
      }
      const idx = parseInt(row.getAttribute('data-index'), 10);
      const pkg = filtered[idx];
      if (pkg) {
        openWingetAiModal(pkg);
      }
    });
  });

  tbody.querySelectorAll('.winget-action-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const pkgId = btn.dataset.id;
      const act = btn.dataset.action;
      if (window.toast) window.toast.info('WinGet', `${act}: ${pkgId}`);
      try {
        const res = await fetch('/api/v1/software-manager/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ package_id: pkgId, action: act, dry_run: false, confirmed_by_user: true })
        });
        const result = await res.json();
        if (res.ok) {
          if (window.toast) window.toast.success('Успех', `${pkgId}: операция выполнена`);
          fetchWingetPackages(true);
        } else {
          if (window.toast) window.toast.error('Ошибка', result.detail || result.message || 'Сбой операции');
        }
      } catch (err) {
        if (window.toast) window.toast.error('Ошибка сети', err.message);
      }
    });
  });
}
