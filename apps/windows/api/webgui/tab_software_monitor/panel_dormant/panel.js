/**
 * =============================================================================
 * Process Name: Windows Software Scanner - Dormant & Orphans Panel
 * =============================================================================
 * Description:
 *   Модуль сканирования спящих программ (>90 дней не запускавшихся) и сирот
 *   (битые ключи реестра, остаточные папки, недействительные службы и задачи).
 *
 * File: panel_dormant/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_software_scanner/panel_dormant
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 15:15:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentInventory = [];
let currentOrphans = [];
let activeFilter = 'all';
let isDormantInitialized = false;
let isSoftwareAuditLoading = false;

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

  // Подключаем стили модала при необходимости
  if (!document.getElementById('link-ai-modal-dialog-style')) {
    const link = document.createElement('link');
    link.id = 'link-ai-modal-dialog-style';
    link.rel = 'stylesheet';
    link.href = '/html/ai_modal_dialog/style.css?v=20261028_v1';
    document.head.appendChild(link);
  }

  // Подключаем управляющий скрипт модала при необходимости
  if (!document.getElementById('script-ai-modal-dialog-lazy')) {
    const s = document.createElement('script');
    s.id = 'script-ai-modal-dialog-lazy';
    s.src = '/html/ai_modal_dialog/main.js?v=20261028_v1';
    document.head.appendChild(s);
  }

  const maxWaitMs = 3000;
  const pollIntervalMs = 50;
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    modal = findExistingAIModal();
    if (modal) return modal;
    await new Promise((r) => setTimeout(r, pollIntervalMs));
  }

  try {
    const mod = await import('/html/ai_modal_dialog/ai_modal_dialog.js?v=20261028_v1');
    if (mod && mod.AIModalDialog && typeof mod.AIModalDialog.show === 'function') {
      return mod.AIModalDialog;
    }
  } catch (_) {}

  return findExistingAIModal();
}

/**
 * Инициализирует модуль сканера спящих программ и сирот.
 */
export function initDormantScanner() {
  if (isDormantInitialized) return;
  isDormantInitialized = true;

  setupDormantEventListeners();
  loadLatestScanResults();
}

/**
 * Настраивает обработчики событий элементов управления сканера.
 */
function setupDormantEventListeners() {
  const btnScan = document.getElementById('sw-btn-trigger-scan');
  if (btnScan) {
    btnScan.addEventListener('click', () => triggerScan());
  }

  const searchInput = document.getElementById('sw-scanner-search-input') || document.getElementById('sw-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderTable());
  }

  const filterButtons = document.querySelectorAll('#sw-status-filter-group button');
  filterButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      filterButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.getAttribute('data-filter') || 'all';
      renderTable();
    });
  });
}

/**
 * Запускает процесс сканирования следов ПО.
 */
export async function triggerScan() {
  if (isSoftwareAuditLoading) return;
  isSoftwareAuditLoading = true;

  const modeSelect = document.getElementById('sw-scan-mode-select');
  const mode = modeSelect ? modeSelect.value : 'deep';

  const statusBadge = document.getElementById('sw-scanner-status-badge');
  const btnScan = document.getElementById('sw-btn-trigger-scan');

  if (statusBadge) {
    statusBadge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-2';
    statusBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сканирование...';
  }
  if (btnScan) {
    btnScan.disabled = true;
  }

  const abortController = new AbortController();
  const timeoutId = setTimeout(() => {
    abortController.abort(new Error('Превышено время ожидания глубокого сканирования ПО (120с)'));
  }, 120000);

  try {
    const res = await fetch('/api/windows/software-scanner/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
      signal: abortController.signal,
    });

    if (!res.ok) {
      throw new Error(`Ошибка сканирования: ${res.statusText}`);
    }

    const report = await res.json();
    processScanReport(report);

    if (window.toast) {
      window.toast.success('Глубокий сканер ПО', `Сканирование завершено: найдено ${report.stats?.total_software_identified || 0} программ`);
    } else if (window.showToast) {
      window.showToast(`Сканирование завершено: найдено ${report.stats?.total_software_identified || 0} программ`, 'success');
    }
  } catch (err) {
    console.error('[SoftwareScannerTab] Ошибка:', err);
    await loadLatestScanResults();

    if (window.toast) {
      window.toast.warning('Глубокий сканер ПО', `Отображен локальный отчет: ${err.message}`);
    } else if (window.showToast) {
      window.showToast(`Отображен локальный отчет: ${err.message}`, 'warning');
    }
  } finally {
    clearTimeout(timeoutId);
    isSoftwareAuditLoading = false;
    if (statusBadge) {
      statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
      statusBadge.textContent = '● Готов к запуску';
    }
    if (btnScan) {
      btnScan.disabled = false;
    }
  }
}

/**
 * Загружает последний сохраненный отчет сканирования из telemetry.db.
 */
export async function loadLatestScanResults() {
  const statusBadge = document.getElementById('sw-scanner-status-badge');
  try {
    const res = await fetch('/api/windows/software-scanner/latest-report');
    if (res.ok) {
      const report = await res.json();
      if (report && report.inventory && report.inventory.length > 0) {
        processScanReport(report);
        if (statusBadge) {
          statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
          statusBadge.innerHTML = `<i class="bi bi-database-check me-1"></i> telemetry.db (${report.inventory.length} ПО)`;
        }
      }
    }
  } catch (err) {
    console.debug('[SoftwareScannerTab] Отчет по умолчанию еще не сформирован в telemetry.db:', err);
  }
}

/**
 * Обрабатывает данные отчета и обновляет метрики со списками.
 * @param {Object} report - Отчет сканирования.
 */
function processScanReport(report) {
  if (!report) return;

  const stats = report.stats || {};
  currentInventory = report.inventory || [];
  currentOrphans = report.orphan_items || [];

  updateMetric('sw-metric-total-evidence', stats.total_evidence_found || (currentInventory.length + currentOrphans.length));
  updateMetric('sw-metric-total-apps', stats.total_software_identified || currentInventory.length);
  updateMetric('sw-metric-active-apps', stats.active_count || currentInventory.filter((c) => c.status === 'active').length);
  updateMetric('sw-metric-dormant-apps', stats.dormant_count || currentInventory.filter((c) => c.status === 'dormant' || c.status === 'never_launched').length);
  updateMetric('sw-metric-orphan-items', stats.orphan_count || currentOrphans.length);
  updateMetric('sw-metric-duration', `${Math.round(stats.duration_ms || 0)} мс`);

  const statusBadge = document.getElementById('sw-scanner-status-badge');
  if (statusBadge && !isSoftwareAuditLoading) {
    statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
    statusBadge.innerHTML = `<i class="bi bi-database-check me-1"></i> telemetry.db (${currentInventory.length} ПО)`;
  }

  renderTable();
  renderOrphans();
}

function updateMetric(elementId, value) {
  const el = document.getElementById(elementId);
  if (el) el.textContent = value;
}

/**
 * Рендерит таблицу программ согласно поисковому запросу и фильтру.
 */
export function renderTable() {
  const tbody = document.getElementById('sw-table-body');
  const countBadge = document.getElementById('sw-table-count-badge');
  const searchInput = document.getElementById('sw-scanner-search-input') || document.getElementById('sw-search-input');
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';

  if (!tbody) return;

  const filtered = currentInventory.filter((card) => {
    if (activeFilter === 'dormant' && card.status !== 'dormant' && card.status !== 'never_launched') return false;
    if (activeFilter === 'active' && card.status !== 'active') return false;
    if (activeFilter === 'orphan' && !card.is_orphan && card.status !== 'orphan') return false;
    if (activeFilter === 'store_app' && card.status !== 'store_app') return false;

    if (query) {
      const matchName = (card.name || '').toLowerCase().includes(query);
      const matchPub = (card.publisher || '').toLowerCase().includes(query);
      const matchLoc = (card.install_location || '').toLowerCase().includes(query);
      const matchExe = (card.main_executable || '').toLowerCase().includes(query);
      return matchName || matchPub || matchLoc || matchExe;
    }

    return true;
  });

  if (countBadge) {
    countBadge.textContent = `${filtered.length} из ${currentInventory.length}`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td class="text-center py-4 text-muted" colspan="6">
          ${currentInventory.length === 0 ? 'Нет данных. Запустите сканирование.' : 'Программы по заданным критериям не найдены.'}
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.slice(0, 150).map((card) => {
    const statusBadge = getStatusBadge(card);
    const lastRunStr = formatLastRun(card);
    const pathStr = card.install_location || card.main_executable || '—';

    return `
      <tr class="sw-scanner-row" data-card-id="${card.id}" style="cursor: pointer;" title="Кликните для вызова ИИ-Ассистента">
        <td>
          <div class="fw-bold text-light">${escapeHtml(card.name)}</div>
          <div class="text-muted small font-monospace text-truncate" style="max-width: 380px;" title="${escapeHtml(pathStr)}">
            ${escapeHtml(pathStr)}
          </div>
        </td>
        <td>
          <div>${escapeHtml(card.publisher || '—')}</div>
          <div class="text-secondary small">${escapeHtml(card.version || '—')}</div>
        </td>
        <td class="sw-badge-cell" data-card-id="${card.id}">${statusBadge}</td>
        <td>
          <div class="fw-medium">${lastRunStr}</div>
          <div class="text-muted" style="font-size: 0.72rem;">${card.last_execution ? card.last_execution.substring(0, 10) : ''}</div>
        </td>
        <td>
          <span class="badge bg-secondary font-monospace">${card.run_count || 0}</span>
        </td>
        <td style="text-align: right;">
          <div class="d-flex align-items-center justify-content-end gap-1">
            <button class="btn btn-sm btn-outline-info btn-evidence-details" data-card-id="${card.id}" title="Просмотреть все найденные следы">
              <i class="bi bi-info-circle"></i> Следы (${(card.evidence || []).length})
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.btn-evidence-details').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const cardId = btn.getAttribute('data-card-id');
      const targetCard = currentInventory.find((c) => c.id === cardId);
      if (targetCard) {
        showEvidenceModal(targetCard);
      }
    });
  });

  tbody.querySelectorAll('.sw-scanner-row').forEach((row) => {
    row.addEventListener('click', async (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) {
        return;
      }
      const cardId = row.getAttribute('data-card-id');
      const targetCard = currentInventory.find((c) => c.id === cardId);
      if (targetCard) {
        const modal = await resolveAIModal();
        if (modal) {
          if (typeof modal.open === 'function') {
            modal.open({ program: targetCard, panelId: 'software-scanner' });
          } else if (typeof modal.show === 'function') {
            modal.show({
              title: targetCard.name,
              subtitle: targetCard.publisher || targetCard.install_location || '',
              icon: '📦',
              panelId: 'software-scanner',
              tableType: 'software',
              rawTitle: 'Телеметрия программы',
              rawContent: JSON.stringify(targetCard, null, 2),
              requestData: targetCard,
              autoRun: true
            });
          }
        }
      }
    });
  });
}

/**
 * Открывает досье сироты / остаточного артефакта в универсальном модальном окне ИИ.
 * @param {Object} item - Объект свидетельства сироты.
 */
export async function openOrphanAiModal(item) {
  if (!item) return;

  const modal = await resolveAIModal();
  if (!modal || typeof modal.show !== 'function') {
    console.warn('[SoftwareScannerTab] AIModalDialog не найден в глобальной области видимости');
    if (window.showToast) {
      window.showToast('Модуль ИИ-помощника загружается, повторите попытку через секунду', 'info');
    }
    return;
  }

  const sourceStr = item.source || 'Остаток ПО';
  const typeStr = item.evidence_type || 'orphan';
  const title = item.product_name ? `Сирота: ${item.product_name}` : `Остаточный компонент: ${item.path || 'Неизвестно'}`;
  const subtitle = `Источник: ${sourceStr} | Тип: ${typeStr}`;

  const badges = [
    { text: `Источник: ${sourceStr}`, class: 'badge bg-danger-subtle text-danger border border-danger' },
    { text: `Тип: ${typeStr}`, class: 'badge bg-warning-subtle text-warning border border-warning' },
    { text: `Достоверность: ${item.confidence || 'HIGH'}`, class: 'badge bg-secondary' }
  ];

  if (item.raw_details && item.raw_details.binary_exists === false) {
    badges.push({ text: 'Файл на диске отсутствует', class: 'badge bg-danger' });
  }

  const metadata = [
    { label: 'Источник обнаружения', value: sourceStr },
    { label: 'Тип свидетельства', value: typeStr },
    { label: 'Причина / Название', value: item.product_name || 'Недействительная запись' },
    { label: 'Путь / Ссылка в реестре', value: item.path || '—', isCode: true, fullWidth: true }
  ];

  if (item.raw_details) {
    if (item.raw_details.service_name) {
      metadata.push({ label: 'Имя службы Windows', value: item.raw_details.service_name, isCode: true });
    }
    if (item.raw_details.task_name) {
      metadata.push({ label: 'Имя задачи Task Scheduler', value: item.raw_details.task_name, isCode: true });
    }
    if (item.raw_details.raw_image_path) {
      metadata.push({ label: 'Исходный путь BinaryPathName', value: item.raw_details.raw_image_path, isCode: true, fullWidth: true });
    }
    if (item.raw_details.binary_exists !== undefined) {
      metadata.push({ label: 'Наличие файла на диске', value: item.raw_details.binary_exists ? 'Обнаружен' : 'Отсутствует (битая ссылка)' });
    }
    if (item.raw_details.installlocation) {
      metadata.push({ label: 'Каталог установки из реестра', value: item.raw_details.installlocation, isCode: true, fullWidth: true });
    }
  }

  if (item.publisher) metadata.push({ label: 'Издатель', value: item.publisher });
  if (item.version) metadata.push({ label: 'Версия', value: item.version });
  if (item.last_execution) metadata.push({ label: 'Метка последнего запуска', value: item.last_execution });
  if (item.run_count) metadata.push({ label: 'Число запусков', value: String(item.run_count) });

  const actions = [];

  // Генерация безопасной команды очистки PowerShell
  let cleanupCmd = '';
  if (item.evidence_type === 'service' && item.raw_details && item.raw_details.service_name) {
    cleanupCmd = `sc.exe delete "${item.raw_details.service_name}"`;
  } else if (item.evidence_type === 'task' && item.raw_details && item.raw_details.task_name) {
    cleanupCmd = `Unregister-ScheduledTask -TaskName "${item.raw_details.task_name}" -Confirm:$false`;
  } else if (item.path && item.path.includes('\\')) {
    if (item.evidence_type === 'directory') {
      cleanupCmd = `Remove-Item -Path "${item.path}" -Recurse -Force`;
    } else if (item.source && item.source.toLowerCase().includes('registry')) {
      cleanupCmd = `Remove-ItemProperty -Path "${item.path}"`;
    }
  }

  if (cleanupCmd) {
    actions.push({
      label: 'Скопировать команду очистки',
      icon: 'bi-clipboard-check',
      class: 'btn-outline-warning',
      onClick: async () => {
        try {
          await navigator.clipboard.writeText(cleanupCmd);
          if (window.showToast) {
            window.showToast(`Команда очистки скопирована в буфер:\n${cleanupCmd}`, 'success');
          } else {
            alert(`Команда скопирована в буфер:\n${cleanupCmd}`);
          }
        } catch (_) {
          prompt('Скопируйте команду очистки вручную:', cleanupCmd);
        }
      }
    });
  }

  modal.show({
    icon: '🗑️',
    title: title,
    subtitle: subtitle,
    panelId: 'panel-software-scanner-orphans',
    tableType: 'orphan',
    badges: badges,
    metadata: metadata,
    rawTitle: 'Телеметрия осиротевшего артефакта Windows (JSON)',
    rawContent: JSON.stringify(item, null, 2),
    requestData: item,
    autoRun: true,
    actions: actions
  });
}

/**
 * Рендерит таблицу сирот и поврежденных записей с вызовом ИИ-помощника по клику.
 */
export function renderOrphans() {
  const container = document.getElementById('panel-software-scanner-orphans');
  const tbody = document.getElementById('sw-orphans-table-body');
  const badge = document.getElementById('sw-orphans-count-badge');
  const navBadge = document.getElementById('sw-orphans-nav-badge');

  if (!container || !tbody) return;

  if (currentOrphans.length === 0) {
    if (badge) badge.textContent = '0';
    if (navBadge) {
      navBadge.style.display = 'none';
      navBadge.textContent = '0';
    }
    tbody.innerHTML = `
      <tr>
        <td class="text-center py-5 text-muted" colspan="3">
          <div class="d-flex flex-column align-items-center gap-2">
            <i class="bi bi-shield-check text-success fs-1"></i>
            <span class="fw-semibold text-light">Сироты и поврежденные компоненты не обнаружены</span>
            <small class="text-secondary">Все проверенные службы, задачи планировщика и записи реестра корректны.</small>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  if (badge) badge.textContent = currentOrphans.length;
  if (navBadge) {
    navBadge.style.display = 'inline-block';
    navBadge.textContent = currentOrphans.length;
  }

  tbody.innerHTML = currentOrphans.map((item, idx) => `
    <tr class="sw-orphan-row" data-orphan-index="${idx}" style="cursor: pointer;" title="Кликните для вызова ИИ-помощника и анализа остатка">
      <td><span class="badge bg-danger-subtle text-danger border border-danger">${escapeHtml(item.source)}</span></td>
      <td class="font-monospace text-break">${escapeHtml(item.path)}</td>
      <td class="text-warning">${escapeHtml(item.product_name || 'Неизвестная причина')}</td>
    </tr>
  `).join('');

  tbody.querySelectorAll('.sw-orphan-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;
      const idx = parseInt(row.getAttribute('data-orphan-index'), 10);
      const item = currentOrphans[idx];
      if (item) {
        openOrphanAiModal(item);
      }
    });
  });
}

function getStatusBadge(card) {
  if (card.status === 'dormant') {
    return '<span class="badge bg-warning-subtle text-warning border border-warning">🟡 Dormant (Спящее)</span>';
  } else if (card.status === 'never_launched') {
    return '<span class="badge bg-secondary-subtle text-secondary border border-secondary">⚪ Без запусков</span>';
  } else if (card.status === 'active') {
    return '<span class="badge bg-success-subtle text-success border border-success">🟢 Active</span>';
  } else if (card.status === 'orphan' || card.is_orphan) {
    return '<span class="badge bg-danger-subtle text-danger border border-danger">🔴 Orphan</span>';
  } else if (card.status === 'store_app') {
    return '<span class="badge bg-info-subtle text-info border border-info">Store App</span>';
  } else if (card.status === 'portable') {
    return '<span class="badge bg-primary-subtle text-primary border border-primary">Portable</span>';
  }
  return '<span class="badge bg-secondary">Неизвестно</span>';
}

function formatLastRun(card) {
  if (card.days_since_last_run !== null && card.days_since_last_run !== undefined) {
    return `${card.days_since_last_run} дн. назад`;
  }
  return 'Не зафиксирован';
}

function showEvidenceModal(card) {
  const modalEl = document.getElementById('sw-evidence-modal');
  const titleEl = document.getElementById('sw-evidence-modal-title');
  const summaryEl = document.getElementById('sw-evidence-modal-summary');
  const listEl = document.getElementById('sw-evidence-modal-list');

  if (!modalEl) return;

  if (titleEl) titleEl.textContent = `Следы: ${card.name}`;

  if (summaryEl) {
    summaryEl.innerHTML = `
      <div class="card bg-secondary bg-opacity-10 border-secondary p-2 mb-2">
        <div><strong>Издатель:</strong> ${escapeHtml(card.publisher || '—')}</div>
        <div><strong>Версия:</strong> ${escapeHtml(card.version || '—')}</div>
        <div><strong>Команда деинсталляции:</strong> <code>${escapeHtml(card.uninstall_string || '—')}</code></div>
      </div>
    `;
  }

  if (listEl) {
    listEl.innerHTML = (card.evidence || []).map((ev) => `
      <div class="list-group-item bg-dark text-light border-secondary">
        <div class="d-flex align-items-center justify-content-between mb-1">
          <span class="badge bg-primary">${escapeHtml(ev.evidence_type)}</span>
          <span class="badge bg-secondary">${escapeHtml(ev.source)}</span>
        </div>
        <div class="small font-monospace text-break text-info">${escapeHtml(ev.path)}</div>
        ${ev.last_execution ? `<div class="small text-muted mt-1">Метка времени: ${escapeHtml(ev.last_execution)}</div>` : ''}
      </div>
    `).join('');
  }

  if (window.bootstrap && window.bootstrap.Modal) {
    const modal = new window.bootstrap.Modal(modalEl);
    modal.show();
  }
}
