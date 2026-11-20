/**
 * =============================================================================
 * Process Name: Windows App Internals - Database Manager Panel
 * =============================================================================
 * Description:
 *   Клиентский модуль панели управления базами данных и хостингом (Database Workbench):
 *   - Быстрый просмотр параметров и структуры баз (SQLite и Hostinger MariaDB);
 *   - Прямая консоль выполнения SQL команд (SELECT, INSERT, UPDATE, DELETE);
 *   - Инструменты сжатия и оптимизации (SQLite VACUUM, MariaDB OPTIMIZE);
 *   - Экспорт баз и таблиц на хостинге в форматы SQL Dump, JSON, CSV;
 *   - Создание резервных копий (бэкапов) с ZIP-сжатием, скачивание и восстановление.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_app_internals/panel_db_manager
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 17:25:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261111_v1';

let isDbManagerInitialized = false;
let cachedOverviewData = null;

/**
 * Инициализирует обработчики событий панели Database Manager.
 * @returns {Promise<void>}
 */
export async function initDbManagerPanel() {
  if (isDbManagerInitialized) {
    await loadDbOverview();
    return;
  }
  isDbManagerInitialized = true;

  bindDbManagerEvents();
  await loadDbOverview();
  await loadDbBackups();
}

/**
 * Переключение активного блока внутри панели управления БД.
 * @param {string} blockId - Идентификатор блока
 */
export function switchDbManagerBlock(blockId) {
  if (blockId === 'block-db-overview') {
    loadDbOverview();
  } else if (blockId === 'block-db-backups') {
    loadDbBackups();
  }
}

/**
 * Привязка событий элементов управления.
 */
function bindDbManagerEvents() {
  // Кнопка обновления обзора
  const refreshBtn = document.getElementById('dbm-refresh-overview-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => loadDbOverview());
  }

  // Кнопка выполнения SQL
  const runSqlBtn = document.getElementById('dbm-run-sql-btn');
  if (runSqlBtn) {
    runSqlBtn.addEventListener('click', () => executeConsoleQuery());
  }

  // Горячая клавиша Ctrl+Enter в поле SQL
  const sqlInput = document.getElementById('dbm-sql-input');
  if (sqlInput) {
    sqlInput.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        executeConsoleQuery();
      }
    });
  }

  // Кнопка очистки SQL
  const clearSqlBtn = document.getElementById('dbm-clear-sql-btn');
  if (clearSqlBtn && sqlInput) {
    clearSqlBtn.addEventListener('click', () => {
      sqlInput.value = '';
      sqlInput.focus();
    });
  }

  // Шаблоны SQL
  document.querySelectorAll('.dbm-sql-snippet-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const template = btn.getAttribute('data-sql-template') || '';
      if (sqlInput && template) {
        sqlInput.value = template;
        sqlInput.focus();
      }
    });
  });

  // Кнопка запуска сжатия
  const compressBtn = document.getElementById('dbm-start-compress-btn');
  if (compressBtn) {
    compressBtn.addEventListener('click', () => executeDatabaseCompression());
  }

  // Кнопка экспорта
  const exportBtn = document.getElementById('dbm-start-export-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => executeDatabaseExport());
  }

  // Кнопка создания бэкапа
  const backupBtn = document.getElementById('dbm-create-backup-btn');
  if (backupBtn) {
    backupBtn.addEventListener('click', () => executeCreateBackup());
  }

  // Кнопка обновления списка бэкапов
  const refreshBkpBtn = document.getElementById('dbm-refresh-backups-btn');
  if (refreshBkpBtn) {
    refreshBkpBtn.addEventListener('click', () => loadDbBackups());
  }

  // Изменение целевой БД в экспорте для обновления списка таблиц
  const exportTargetSel = document.getElementById('dbm-export-target-select');
  if (exportTargetSel) {
    exportTargetSel.addEventListener('change', () => updateExportTableDropdown());
  }
}

/**
 * Загрузка сводки и параметров всех баз данных.
 * @returns {Promise<void>}
 */
export async function loadDbOverview() {
  const container = document.getElementById('dbm-targets-container');
  if (container) {
    container.innerHTML = `
      <div class="p-3 text-center text-secondary">
        <div class="spinner-border spinner-border-sm me-2" role="status"></div>
        <span>Опрос параметров и статусов баз данных...</span>
      </div>`;
  }

  try {
    const res = await fetch('/api/v1/db-manager/overview');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    cachedOverviewData = data;
    renderOverview(data);
    updateTargetDropdowns(data.targets || []);
  } catch (err) {
    console.error('[DBManager] Ошибка загрузки обзора баз:', err);
    if (container) {
      container.innerHTML = `
        <div class="alert alert-danger p-2 m-2">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>Не удалось загрузить параметры: ${err.message}
        </div>`;
    }
  }
}

/**
 * Отрисовка карточек баз данных в блоке обзора.
 * @param {object} data
 */
function renderOverview(data) {
  const container = document.getElementById('dbm-targets-container');
  if (!container) return;

  const targets = data.targets || [];
  if (!targets.length) {
    container.innerHTML = '<div class="alert alert-info">Базы данных не сконфигурированы.</div>';
    return;
  }

  let html = '<div class="row g-3">';
  for (const t of targets) {
    const isOnline = t.status === 'online';
    const statusBadge = isOnline
      ? '<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>Доступна</span>'
      : `<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i>${t.status === 'not_found' ? 'Файл не найден' : 'Недоступна'}</span>`;

    const typeBadge = t.type === 'mariadb'
      ? '<span class="ui-badge ui-badge-info"><i class="bi bi-cloud me-1"></i>Hostinger MariaDB</span>'
      : '<span class="ui-badge ui-badge-neutral"><i class="bi bi-hdd me-1"></i>SQLite (Локально)</span>';

    const params = t.parameters || {};
    const paramEntries = Object.entries(params)
      .map(([k, v]) => `<div><strong class="text-secondary">${k}:</strong> <span class="font-monospace">${v}</span></div>`)
      .join('');

    const tables = t.tables || [];
    let tablesHtml = '<div class="text-muted small">Таблицы отсутствуют</div>';
    if (tables.length) {
      tablesHtml = `
        <div class="table-responsive mt-2" style="max-height: 140px; overflow-y: auto;">
          <table class="table table-sm table-hover mb-0" style="font-size: 0.82rem;">
            <thead>
              <tr class="text-secondary">
                <th>Таблица</th>
                <th>Строк</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              ${tables.map((tbl) => `
                <tr>
                  <td class="fw-semibold font-monospace">${tbl.name}</td>
                  <td>${tbl.rows}</td>
                  <td>
                    <button type="button" class="btn btn-outline-primary btn-sm py-0 px-1.5 dbm-query-table-btn"
                      data-target-id="${t.id}" data-table-name="${tbl.name}" title="Открыть SELECT в консоли">
                      <i class="bi bi-search"></i>
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
    }

    html += `
      <div class="col-md-6 col-lg-4">
        <div class="card h-100 shadow-sm border" style="border-color: var(--border-color) !important;">
          <div class="card-header d-flex justify-content-between align-items-center py-2 flex-wrap gap-1">
            <span class="fw-bold text-truncate" title="${t.name}">
              <i class="bi bi-database me-1 text-primary"></i>${t.name}
            </span>
            <div class="d-flex align-items-center gap-1">
              ${typeBadge}
              ${statusBadge}
            </div>
          </div>
          <div class="card-body p-2.5 d-flex flex-column justify-content-between">
            <div>
              <div class="small text-secondary mb-2">${t.description || ''}</div>
              <div class="p-2 rounded bg-light bg-opacity-10 small mb-2" style="font-size: 0.78rem;">
                <div><strong class="text-secondary">Путь / Хост:</strong> <span class="font-monospace text-truncate d-inline-block mw-100">${t.location || '—'}</span></div>
                <div><strong class="text-secondary">Размер:</strong> <span class="fw-bold">${t.size_human || '—'}</span> (${t.tables_count} табл.)</div>
                ${paramEntries}
              </div>
              <label class="form-label form-label-sm fw-semibold mb-1">Таблицы (${t.tables_count}):</label>
              ${tablesHtml}
            </div>
            <div class="mt-2 pt-2 border-top d-flex gap-1 justify-content-end">
              <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-2 dbm-quick-switch-console-btn"
                data-target-id="${t.id}" title="Перейти в SQL консоль этой базы">
                <i class="bi bi-terminal me-1"></i>Консоль
              </button>
            </div>
          </div>
        </div>
      </div>`;
  }
  html += '</div>';
  container.innerHTML = html;

  // Слушатели кнопок в карточках
  container.querySelectorAll('.dbm-query-table-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target-id');
      const tableName = btn.getAttribute('data-table-name');
      openTableInConsole(targetId, tableName);
    });
  });

  container.querySelectorAll('.dbm-quick-switch-console-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target-id');
      selectConsoleTarget(targetId);
      document.getElementById('btn-block-db-console')?.click();
    });
  });
}

/**
 * Обновление выпадающих списков целевых баз данных во всех блоках.
 * @param {Array} targets
 */
function updateTargetDropdowns(targets) {
  const selects = [
    document.getElementById('dbm-console-target-select'),
    document.getElementById('dbm-compress-target-select'),
    document.getElementById('dbm-export-target-select'),
    document.getElementById('dbm-backup-target-select'),
  ];

  for (const sel of selects) {
    if (!sel) continue;
    const currVal = sel.value;
    sel.innerHTML = targets.map((t) => `
      <option value="${t.id}" ${t.id === currVal || t.is_default ? 'selected' : ''}>
        ${t.name} (${t.type.toUpperCase()})
      </option>
    `).join('');
  }
  updateExportTableDropdown();
}

/**
 * Обновление списка таблиц для выбранной базы в блоке экспорта.
 */
function updateExportTableDropdown() {
  const targetSel = document.getElementById('dbm-export-target-select');
  const tableSel = document.getElementById('dbm-export-table-select');
  if (!targetSel || !tableSel || !cachedOverviewData) return;

  const targetId = targetSel.value;
  const target = (cachedOverviewData.targets || []).find((t) => t.id === targetId);
  const tables = target?.tables || [];

  tableSel.innerHTML = '<option value="all">Все таблицы (All Tables)</option>' +
    tables.map((tbl) => `<option value="${tbl.name}">${tbl.name} (${tbl.rows} строк)</option>`).join('');
}

/**
 * Быстрый переход к таблице в консоли.
 * @param {string} targetId
 * @param {string} tableName
 */
function openTableInConsole(targetId, tableName) {
  selectConsoleTarget(targetId);
  const sqlInput = document.getElementById('dbm-sql-input');
  if (sqlInput) {
    sqlInput.value = `SELECT * FROM ${tableName} LIMIT 20;`;
  }
  document.getElementById('btn-block-db-console')?.click();
  executeConsoleQuery();
}

/**
 * Установка целевой базы в селекторе консоли.
 * @param {string} targetId
 */
function selectConsoleTarget(targetId) {
  const sel = document.getElementById('dbm-console-target-select');
  if (sel && targetId) sel.value = targetId;
}

/**
 * Выполнение произвольного SQL запроса из консоли.
 * @returns {Promise<void>}
 */
export async function executeConsoleQuery() {
  const targetSel = document.getElementById('dbm-console-target-select');
  const sqlInput = document.getElementById('dbm-sql-input');
  const resultContainer = document.getElementById('dbm-query-result-container');
  const statusBadge = document.getElementById('dbm-query-status-badge');

  if (!sqlInput || !resultContainer) return;
  const sql = sqlInput.value.trim();
  if (!sql) {
    notifyUser('Введите текст SQL запроса для выполнения.', 'warning');
    sqlInput.focus();
    return;
  }

  const targetId = targetSel ? targetSel.value : 'sqlite:knowledge';
  if (statusBadge) {
    statusBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выполнение...';
    statusBadge.className = 'ui-badge ui-badge-info';
  }
  resultContainer.innerHTML = '<div class="text-center p-3 text-secondary"><div class="spinner-border spinner-border-sm me-2"></div>Выполнение запроса...</div>';

  try {
    const res = await fetch('/api/v1/db-manager/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, sql, max_rows: 200 }),
    });
    const data = await res.json();

    if (!data.success) {
      if (statusBadge) {
        statusBadge.innerHTML = `<i class="bi bi-x-circle me-1"></i>Ошибка (${data.execution_time_ms || 0} ms)`;
        statusBadge.className = 'ui-badge ui-badge-danger';
      }
      resultContainer.innerHTML = `
        <div class="alert alert-danger m-2">
          <i class="bi bi-exclamation-octagon-fill me-2"></i><strong>Ошибка выполнения SQL:</strong>
          <pre class="mb-0 mt-2 p-2 bg-dark text-white rounded font-monospace" style="font-size: 0.85rem;">${data.error}</pre>
        </div>`;
      return;
    }

    if (statusBadge) {
      statusBadge.innerHTML = `<i class="bi bi-check-circle me-1"></i>Успешно (${data.execution_time_ms} ms)`;
      statusBadge.className = 'ui-badge ui-badge-success';
    }

    // Если запрос возвращает строки (SELECT, SHOW, PRAGMA)
    if (data.is_query) {
      renderQueryResultSet(data, resultContainer);
    } else {
      // DML (INSERT, UPDATE, DELETE)
      resultContainer.innerHTML = `
        <div class="alert alert-success m-2 d-flex align-items-center gap-2">
          <i class="bi bi-check-circle-fill fs-4"></i>
          <div>
            <strong>Команда успешно выполнена!</strong>
            <div>Затронуто строк: <span class="badge bg-success font-monospace">${data.affected_rows}</span> | Время: <span class="font-monospace">${data.execution_time_ms} ms</span></div>
          </div>
        </div>`;
      // Фоновое обновление счетчиков в обзоре
      loadDbOverview();
    }
  } catch (err) {
    if (statusBadge) {
      statusBadge.textContent = 'Ошибка сети';
      statusBadge.className = 'ui-badge ui-badge-danger';
    }
    resultContainer.innerHTML = `<div class="alert alert-danger m-2">Ошибка отправки запроса: ${err.message}</div>`;
  }
}

/**
 * Отрисовка таблицы результатов SELECT запроса.
 * @param {object} data
 * @param {HTMLElement} container
 */
function renderQueryResultSet(data, container) {
  const rows = data.rows || [];
  const columns = data.columns || [];

  if (!rows.length) {
    container.innerHTML = `
      <div class="alert alert-info m-2">
        <i class="bi bi-info-circle me-1"></i>Запрос выполнен успешно, но вернул 0 строк (Пустая выборка).
      </div>`;
    return;
  }

  const tableHeader = columns.map((c) => `<th class="text-nowrap font-monospace">${c}</th>`).join('');
  const tableRows = rows.map((r) => {
    const cells = columns.map((c) => {
      const val = r[c];
      const strVal = val === null ? '<span class="text-muted fst-italic">NULL</span>' : String(val);
      return `<td class="text-truncate" style="max-width: 260px;" title="${val === null ? 'NULL' : String(val).replace(/"/g, '&quot;')}">${strVal}</td>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  container.innerHTML = `
    <div class="d-flex justify-content-between align-items-center px-2 py-1.5 border-bottom bg-light bg-opacity-10 small">
      <span class="text-secondary">Показано <strong class="text-dark">${rows.length}</strong> строк(и) из <span class="font-monospace">${data.target}</span></span>
      <span class="text-secondary font-monospace">${data.execution_time_ms} ms</span>
    </div>
    <div class="table-responsive" style="max-height: 380px; overflow-y: auto;">
      <table class="table table-sm table-striped table-hover mb-0" style="font-size: 0.83rem;">
        <thead class="table-light sticky-top">
          <tr>${tableHeader}</tr>
        </thead>
        <tbody>
          ${tableRows}
        </tbody>
      </table>
    </div>`;
}

/**
 * Выполнение сжатия и оптимизации базы данных.
 * @returns {Promise<void>}
 */
export async function executeDatabaseCompression() {
  const targetSel = document.getElementById('dbm-compress-target-select');
  const actionSel = document.getElementById('dbm-compress-action-select');
  const resultDiv = document.getElementById('dbm-compress-result-box');

  const targetId = targetSel ? targetSel.value : 'sqlite:knowledge';
  const action = actionSel ? actionSel.value : 'vacuum';

  if (resultDiv) {
    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Выполняется сжатие...';
  }

  try {
    const res = await fetch('/api/v1/db-manager/compress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, action }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || 'Ошибка сжатия');
    }

    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="alert alert-success d-flex align-items-center gap-2 mb-0">
          <i class="bi bi-file-earmark-zip-fill fs-3 text-success"></i>
          <div>
            <strong>${data.message}</strong>
            ${data.saved_bytes !== undefined ? `<div>Было: <span class="font-monospace">${data.before_human}</span> -> Стало: <span class="font-monospace">${data.after_human}</span> (Освобождено: <span class="badge bg-success font-monospace">${data.saved_human}</span>)</div>` : ''}
          </div>
        </div>`;
    }
    notifyUser('Сжатие успешно завершено!', 'success');
    loadDbOverview();
  } catch (err) {
    if (resultDiv) {
      resultDiv.innerHTML = `<div class="alert alert-danger mb-0"><i class="bi bi-x-circle me-1"></i>${err.message}</div>`;
    }
    notifyUser(`Ошибка сжатия: ${err.message}`, 'danger');
  }
}

/**
 * Выполнение экспорта из базы данных (Hostinger или SQLite).
 * @returns {Promise<void>}
 */
export async function executeDatabaseExport() {
  const targetSel = document.getElementById('dbm-export-target-select');
  const tableSel = document.getElementById('dbm-export-table-select');
  const formatSel = document.getElementById('dbm-export-format-select');
  const resultDiv = document.getElementById('dbm-export-result-box');

  const targetId = targetSel ? targetSel.value : 'hostinger:tool_chains';
  const tableName = tableSel ? tableSel.value : 'all';
  const exportFormat = formatSel ? formatSel.value : 'sql';

  if (resultDiv) {
    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Формирование файла экспорта...';
  }

  try {
    const res = await fetch('/api/v1/db-manager/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, table_name: tableName, export_format: exportFormat }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || 'Ошибка экспорта');
    }

    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="alert alert-success d-flex justify-content-between align-items-center flex-wrap gap-2 mb-0">
          <div>
            <i class="bi bi-check-circle-fill me-1 text-success"></i>
            <strong>${data.message}</strong>
            <div class="small text-secondary">Таблиц: ${data.tables_count} | Записей: ${data.records_count} | Размер: ${data.size_human}</div>
          </div>
          <a href="${data.download_url}" class="btn btn-sm btn-primary" download>
            <i class="bi bi-download me-1"></i>Скачать файл (${data.filename})
          </a>
        </div>`;
    }
    notifyUser('Экспорт успешно создан!', 'success');
  } catch (err) {
    if (resultDiv) {
      resultDiv.innerHTML = `<div class="alert alert-danger mb-0"><i class="bi bi-x-circle me-1"></i>${err.message}</div>`;
    }
    notifyUser(`Ошибка экспорта: ${err.message}`, 'danger');
  }
}

/**
 * Создание резервной копии базы данных.
 * @returns {Promise<void>}
 */
export async function executeCreateBackup() {
  const targetSel = document.getElementById('dbm-backup-target-select');
  const zipCheck = document.getElementById('dbm-backup-zip-check');
  const resultDiv = document.getElementById('dbm-backup-result-box');

  const targetId = targetSel ? targetSel.value : 'sqlite:knowledge';
  const compressZip = zipCheck ? zipCheck.checked : true;

  if (resultDiv) {
    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>Создание резервной копии...';
  }

  try {
    const res = await fetch('/api/v1/db-manager/backup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, compress_zip: compressZip }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || 'Ошибка создания бэкапа');
    }

    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="alert alert-success mb-0 d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div>
            <i class="bi bi-shield-check me-1 text-success"></i>
            <strong>${data.message}</strong>
          </div>
          <a href="${data.download_url}" class="btn btn-sm btn-outline-success" download>
            <i class="bi bi-download me-1"></i>Скачать
          </a>
        </div>`;
    }
    notifyUser('Резервная копия успешно создана!', 'success');
    await loadDbBackups();
  } catch (err) {
    if (resultDiv) {
      resultDiv.innerHTML = `<div class="alert alert-danger mb-0">${err.message}</div>`;
    }
    notifyUser(`Ошибка создания бэкапа: ${err.message}`, 'danger');
  }
}

/**
 * Загрузка и рендеринг каталога резервных копий.
 * @returns {Promise<void>}
 */
export async function loadDbBackups() {
  const listContainer = document.getElementById('dbm-backups-list-container');
  if (!listContainer) return;

  listContainer.innerHTML = '<div class="text-center p-3 text-secondary"><div class="spinner-border spinner-border-sm me-2"></div>Загрузка списка бэкапов...</div>';

  try {
    const res = await fetch('/api/v1/db-manager/backups');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const backups = data.backups || [];

    if (!backups.length) {
      listContainer.innerHTML = '<div class="alert alert-info m-2">Резервные копии отсутствуют. Нажмите кнопку выше для создания нового бэкапа.</div>';
      return;
    }

    const rows = backups.map((b) => {
      const zipBadge = b.is_compressed
        ? '<span class="ui-badge ui-badge-info"><i class="bi bi-file-earmark-zip me-1"></i>ZIP</span>'
        : '<span class="ui-badge ui-badge-neutral"><i class="bi bi-file-earmark me-1"></i>RAW</span>';

      return `
        <tr>
          <td class="font-monospace fw-semibold">${b.filename}</td>
          <td>${zipBadge}</td>
          <td>${b.size_human}</td>
          <td class="text-secondary small">${b.created_at ? new Date(b.created_at).toLocaleString() : '—'}</td>
          <td class="text-end">
            <a href="${b.download_url}" class="btn btn-sm btn-outline-primary py-0 px-2" download title="Скачать бэкап">
              <i class="bi bi-download"></i>
            </a>
            <button type="button" class="btn btn-sm btn-outline-warning py-0 px-2 dbm-restore-backup-btn ms-1"
              data-backup-name="${b.filename}" title="Восстановить базу из этого бэкапа">
              <i class="bi bi-arrow-counterclockwise"></i>
            </button>
            <button type="button" class="btn btn-sm btn-outline-danger py-0 px-2 dbm-delete-backup-btn ms-1"
              data-backup-name="${b.filename}" title="Удалить бэкап">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>`;
    }).join('');

    listContainer.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm table-hover align-middle mb-0" style="font-size: 0.84rem;">
          <thead class="table-light">
            <tr>
              <th>Имя файла</th>
              <th>Тип</th>
              <th>Размер</th>
              <th>Дата создания</th>
              <th class="text-end">Действия</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>`;

    // Привязка действий к строкам таблицы
    listContainer.querySelectorAll('.dbm-delete-backup-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const fn = btn.getAttribute('data-backup-name');
        if (confirm(`Вы уверены, что хотите удалить бэкап ${fn}?`)) {
          await deleteBackupFile(fn);
        }
      });
    });

    listContainer.querySelectorAll('.dbm-restore-backup-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const fn = btn.getAttribute('data-backup-name');
        if (confirm(`ВНИМАНИЕ: Восстановление перезапишет существующие данные базы из бэкапа ${fn}. Продолжить?`)) {
          await restoreBackupFile(fn);
        }
      });
    });
  } catch (err) {
    listContainer.innerHTML = `<div class="alert alert-danger m-2">Ошибка загрузки бэкапов: ${err.message}</div>`;
  }
}

/**
 * Удаление файла бэкапа.
 * @param {string} filename
 */
async function deleteBackupFile(filename) {
  try {
    const res = await fetch(`/api/v1/db-manager/backups/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.detail || data.error || 'Ошибка удаления');
    notifyUser(`Бэкап ${filename} удален.`, 'info');
    await loadDbBackups();
  } catch (err) {
    notifyUser(`Ошибка удаления бэкапа: ${err.message}`, 'danger');
  }
}

/**
 * Восстановление базы из файла бэкапа.
 * @param {string} filename
 */
async function restoreBackupFile(filename) {
  try {
    const res = await fetch('/api/v1/db-manager/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_name: filename }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.detail || data.error || 'Ошибка восстановления');
    notifyUser(data.message || 'Восстановление успешно завершено!', 'success');
    await loadDbOverview();
  } catch (err) {
    notifyUser(`Ошибка восстановления: ${err.message}`, 'danger');
  }
}

// Экспорт в глобальное пространство window для совместимости с оркестратором
window.initDbManagerPanel = initDbManagerPanel;
window.switchDbManagerBlock = switchDbManagerBlock;
