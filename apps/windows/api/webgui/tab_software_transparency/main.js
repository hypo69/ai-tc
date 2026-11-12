/**
 * =============================================================================
 * Process Name: Windows Software Transparency Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля аудита прозрачности ПО
 *   (Software Transparency Scanner). Отображает полные параметры приложений,
 *   метаданные установки, каталоги хранения, ветки реестра, файлы конфигураций,
 *   сетевые домены, активные сокеты и связанные службы Windows.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_software_transparency/main.js?v=20261101_v2" type="module"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_software_transparency
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 01:15:00
 * =============================================================================
 */

(function () {
  let allApps = [];
  let isScanning = false;

  async function initSoftwareTransparencyTab() {
    bindEvents();
    const tbody = document.getElementById('st-table-body');
    const hasRenderedRows = tbody && tbody.querySelector('.st-app-row');
    if (allApps.length > 0 && !hasRenderedRows) {
      renderTable();
      return;
    }
    if (allApps.length === 0) {
      await loadScannerData(false);
    }
  }

  let isRowsExpanded = false;

  function toggleRowHeightMode() {
    const table = document.getElementById('st-main-table');
    const label = document.getElementById('st-row-height-label');
    const icon = document.getElementById('st-row-height-icon');
    if (!table) return;

    isRowsExpanded = !isRowsExpanded;
    if (isRowsExpanded) {
      table.classList.add('st-unfolded');
      if (label) label.textContent = 'Развёрнуто';
      if (icon) icon.className = 'bi bi-arrows-collapse';
    } else {
      table.classList.remove('st-unfolded');
      if (label) label.textContent = 'Одинаковая высота строк';
      if (icon) icon.className = 'bi bi-distribute-vertical';
    }
  }

  function bindEvents() {
    const btnRefresh = document.getElementById('st-btn-refresh');
    if (btnRefresh) {
      btnRefresh.onclick = () => loadScannerData(true);
    }

    const searchInput = document.getElementById('st-search-input');
    if (searchInput) {
      searchInput.oninput = () => renderTable();
    }

    const btnToggleHeight = document.getElementById('st-btn-toggle-row-height');
    if (btnToggleHeight) {
      btnToggleHeight.onclick = toggleRowHeightMode;
    }
  }

  function isCacheEnriched(cached) {
    if (!cached || !Array.isArray(cached.apps) || cached.apps.length === 0) return false;
    const summary = cached.summary || {};
    if (!summary.total_configs_found && !summary.total_network_domains) return false;
    const sampleWithReg = cached.apps.some(a => a.registry_key || a.category);
    return sampleWithReg;
  }

  function updateSummaryMetrics(summary, appsList, isCached = false) {
    const elApps = document.getElementById('st-metric-total-apps');
    const elCfgs = document.getElementById('st-metric-total-configs');
    const elDoms = document.getElementById('st-metric-total-domains');
    const elDur = document.getElementById('st-metric-scan-duration');
    if (elApps) elApps.innerText = summary.total_apps || appsList.length;
    if (elCfgs) elCfgs.innerText = summary.total_configs_found || 0;
    if (elDoms) elDoms.innerText = summary.total_network_domains || 0;
    if (elDur) elDur.innerText = (summary.scan_duration_sec || 0) + (isCached ? ' с. (кэш)' : ' с.');
  }

  async function loadScannerData(forceRefresh = false) {
    if (isScanning) return;

    const badge = document.getElementById('st-status-badge');
    const tbody = document.getElementById('st-table-body');
    let usedValidCache = false;

    // 1. Офлайн-первый доступ: чтение из кэша IndexedDB браузера (только если кэш обогащён всеми параметрами)
    if (!forceRefresh && window.IndexedDBCache) {
      try {
        const cached = await window.IndexedDBCache.get('software_inventory', 'transparency_full_scan');
        if (isCacheEnriched(cached)) {
          allApps = cached.apps;
          usedValidCache = true;
          updateSummaryMetrics(cached.summary || {}, allApps, true);
          if (badge) {
            badge.className = 'badge rounded-pill bg-info-subtle text-info border border-info px-3 py-2';
            badge.innerText = '● Кэш браузера: ' + allApps.length + ' программ';
          }
          renderTable();
        }
      } catch (err) {
        console.debug('[TransparencyScanner] Ошибка чтения из кэша IndexedDB:', err);
      }
    }

    isScanning = true;

    if (badge && (!allApps || allApps.length === 0)) {
      badge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-2';
      badge.innerText = '● Идет сбор сведений о ПО и сети...';
    }

    if (tbody && (!allApps || allApps.length === 0)) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted"><div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>Выполняется инвентаризация установленных программ, конфигураций и сетевых сокетов...</td></tr>';
    }

    try {
      const needForce = forceRefresh || !usedValidCache;
      const q = '?force_refresh=' + (needForce ? 'true' : 'false');
      const fetchOpts = { signal: AbortSignal.timeout ? AbortSignal.timeout(25000) : undefined };
      let res = await fetch('/api/v1/software-scanner/scan' + q, fetchOpts);
      if (!res.ok) {
        res = await fetch('/api/windows/software-transparency/scan' + q, fetchOpts);
      }
      if (!res.ok) {
        res = await fetch('/api/windows/api/v1/software-scanner/scan' + q, fetchOpts);
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);

      const data = await res.json();
      allApps = data.apps || [];
      const summary = data.summary || {};

      if (window.IndexedDBCache && allApps.length > 0) {
        window.IndexedDBCache.set('software_inventory', 'transparency_full_scan', {
          summary: summary,
          apps: allApps,
          timestamp: Date.now()
        }).catch(e => console.debug('[TransparencyScanner] Ошибка сохранения в IndexedDB:', e));
      }

      updateSummaryMetrics(summary, allApps, false);

      if (badge) {
        badge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
        badge.innerText = '● Обнаружено: ' + allApps.length + ' программ';
      }

      renderTable();
    } catch (err) {
      console.error('[TransparencyScanner] Scan error:', err);
      if (badge && (!allApps || allApps.length === 0)) {
        badge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-2';
        badge.innerText = '● Ошибка сканирования';
      }
      if (tbody && (!allApps || allApps.length === 0)) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Ошибка: ' + escapeHtml(err.message) + '</td></tr>';
      }
    } finally {
      isScanning = false;
    }
  }

  function formatBytes(bytes) {
    const val = Number(bytes || 0);
    if (!val || val <= 0) return '0 Б';
    if (val < 1024) return val + ' Б';
    if (val < 1024 * 1024) return (val / 1024).toFixed(1) + ' КБ';
    if (val < 1024 * 1024 * 1024) return (val / (1024 * 1024)).toFixed(1) + ' МБ';
    return (val / (1024 * 1024 * 1024)).toFixed(2) + ' ГБ';
  }

  function statusDot(status) {
    if (status === 'observed') return '<span title="Достоверность: Локально обнаружено">🟢</span>';
    if (status === 'confirmed') return '<span title="Достоверность: Подтверждено документацией">🔵</span>';
    if (status === 'inferred') return '<span title="Достоверность: Предположение ИИ">🟡</span>';
    return '<span title="Достоверность: Неизвестно">⚪</span>';
  }

  function categoryLabel(cat) {
    const map = {
      binaries: 'Бинарные файлы',
      config: 'Настройки',
      cache: 'Кэш',
      data: 'Данные',
      logs: 'Логи',
      unknown: 'Хранилище'
    };
    return map[String(cat || '').toLowerCase()] || cat || 'Хранилище';
  }

  function sourceLabel(src) {
    const map = {
      active_socket: 'Активный сокет',
      config_file: 'Конфиг',
      known_database: 'База знаний',
      registry_publisher: 'Реестр издателя',
      observed: 'Локально'
    };
    return map[String(src || '').toLowerCase()] || src || 'Локально';
  }

  function renderTable() {
    const tbody = document.getElementById('st-table-body');
    const searchInput = document.getElementById('st-search-input');
    const searchVal = (searchInput ? searchInput.value : '').toLowerCase().trim();

    if (!tbody) return;

    const filtered = allApps.filter((a) => {
      if (!searchVal) return true;
      const netStr = (a.network_endpoints || []).map(n => n.domain_or_ip || n.domain || n.endpoint || '').join(' ').toLowerCase();
      const cfgStr = (a.config_files || []).map(c => c.filename || c.path || '').join(' ').toLowerCase();
      const dirStr = (a.data_directories || []).map(d => d.display_path || d.path || '').join(' ').toLowerCase();
      return (
        (a.name && a.name.toLowerCase().includes(searchVal)) ||
        (a.publisher && a.publisher.toLowerCase().includes(searchVal)) ||
        (a.version && a.version.toLowerCase().includes(searchVal)) ||
        (a.category && a.category.toLowerCase().includes(searchVal)) ||
        (a.purpose_description && a.purpose_description.toLowerCase().includes(searchVal)) ||
        (a.install_location && a.install_location.toLowerCase().includes(searchVal)) ||
        (a.executable_path && a.executable_path.toLowerCase().includes(searchVal)) ||
        (a.registry_key && a.registry_key.toLowerCase().includes(searchVal)) ||
        netStr.includes(searchVal) ||
        cfgStr.includes(searchVal) ||
        dirStr.includes(searchVal)
      );
    });

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Ничего не найдено по фильтру «' + escapeHtml(searchVal) + '»</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map((app) => renderAppRow(app)).join('');
    bindRowActions();
  }

  function renderAppRow(app) {
    // 1. Программа, категория, назначение, пути запуска
    const catBadge = app.category
      ? `<span class="badge bg-info-subtle text-info border border-info me-1">${escapeHtml(app.category)}</span>`
      : '';
    const sysBadge = app.is_system_component
      ? '<span class="badge bg-secondary-subtle text-secondary border border-secondary">Системный</span>'
      : '';
    const purposeHtml = app.purpose_description
      ? `<div class="small text-secondary mt-1">${escapeHtml(app.purpose_description)}</div>`
      : '';
    const instHtml = app.install_location
      ? `<div class="small text-muted text-truncate mt-1" title="Каталог установки: ${escapeHtml(app.install_location)}">📂 ${escapeHtml(app.install_location)}</div>`
      : '';
    const exeHtml = app.executable_path
      ? `<div class="small text-info text-truncate" title="Исполняемый файл: ${escapeHtml(app.executable_path)}">⚡ ${escapeHtml(app.executable_path)}</div>`
      : '';

    // 2. Издатель, версия, архитектура, дата установки, размер, запуски
    const archBadge = `<span class="badge bg-secondary-subtle text-light border border-secondary ms-1">${escapeHtml(app.architecture || 'x64')}</span>`;
    const dateHtml = `<div class="small text-muted mt-1">📅 Дата: ${escapeHtml(app.install_date || 'Не указана')}</div>`;
    const calcDirBytes = (app.data_directories || []).reduce((acc, d) => acc + Number(d.total_size_bytes || 0), 0);
    const totalBytes = Number(app.size_bytes || 0) || calcDirBytes;
    const sizeHtml = totalBytes > 0
      ? `<div class="small text-muted">💾 Размер: ${formatBytes(totalBytes)}</div>`
      : '';
    const runHtml = app.run_count > 0
      ? `<div class="small text-success" title="Последний запуск: ${escapeHtml(app.last_run_time || '')}">🚀 Запусков: ${app.run_count}${app.last_run_time ? ' (' + escapeHtml(String(app.last_run_time).slice(0, 10)) + ')' : ''}</div>`
      : '';

    // 3. Каталоги хранения, реестр и деинсталлятор
    const dirItems = (app.data_directories || []).map(d => {
      const disp = d.display_path || d.path;
      const meta = `${categoryLabel(d.category)} • ${formatBytes(d.total_size_bytes)} • ${d.file_count || 0} файл.`;
      const desc = d.description ? ` (${escapeHtml(d.description)})` : '';
      return `
        <div class="mb-1">
          <div class="text-truncate small text-light" title="${escapeHtml(d.path)}">${statusDot(d.status)} 📁 ${escapeHtml(disp)}</div>
          <div class="text-muted small ps-3">${escapeHtml(meta)}${desc}</div>
        </div>
      `;
    });
    if (app.registry_key) {
      dirItems.push(`<div class="text-truncate small text-secondary" title="Ветка реестра: ${escapeHtml(app.registry_key)}">🔑 Реестр: ${escapeHtml(app.registry_key)}</div>`);
    }
    if (app.uninstall_string) {
      dirItems.push(`<div class="text-truncate small text-muted" title="Команда удаления: ${escapeHtml(app.uninstall_string)}">🗑️ Деинсталлятор: ${escapeHtml(app.uninstall_string)}</div>`);
    }
    const dirsHtml = dirItems.length > 0 ? dirItems.join('') : '<span class="text-muted small">—</span>';

    // 4. Конфигурационные файлы и статус секретов
    const cfgItems = (app.config_files || []).map(c => {
      const fmt = (c.format || 'cfg').toUpperCase();
      const sz = formatBytes(c.size_bytes);
      const purp = c.purpose || 'Настройки';
      const sanBadge = c.is_sanitized ? '🔒 Секреты скрыты' : '⚠️ Открытый текст';
      return `
        <div class="mb-1">
          <button class="btn btn-link btn-sm p-0 text-warning text-decoration-none text-truncate d-block view-config-btn no-modal-trigger" data-app-id="${escapeHtml(app.id)}" data-cfg-path="${escapeHtml(c.path)}" title="${escapeHtml(c.display_path || c.path)}">
            ${statusDot(c.status)} ⚙️ ${escapeHtml(c.filename)}
          </button>
          <div class="text-muted small ps-3">${escapeHtml(fmt)} • ${sz} • ${escapeHtml(purp)} (${sanBadge})</div>
        </div>
      `;
    });
    const cfgsHtml = cfgItems.length > 0
      ? cfgItems.join('')
      : '<span class="text-muted small">Локальных конфигов не обнаружено</span>';

    // 5. Сетевые домены, активные сокеты и службы Windows
    const netItems = (app.network_endpoints || []).map(n => {
      const host = n.domain_or_ip || n.domain || n.endpoint || 'неизвестно';
      const protoPort = (n.protocol || 'HTTPS') + (n.port ? ':' + n.port : '');
      const purp = n.purpose || 'Сетевой узел';
      const src = sourceLabel(n.source);
      return `
        <div class="mb-1">
          <div class="small">
            ${statusDot(n.status)}
            <span class="badge bg-secondary-subtle text-light border border-secondary me-1" title="${escapeHtml(purp)}">${escapeHtml(host)}</span>
            <span class="text-info small">${escapeHtml(protoPort)}</span>
          </div>
          <div class="text-muted small ps-3">${escapeHtml(purp)} (${escapeHtml(src)})</div>
        </div>
      `;
    });
    const svcItems = (app.windows_services || []).map(s =>
      `<div class="small text-warning text-truncate" title="Служба Windows: ${escapeHtml(s)}">⚙️ Служба: ${escapeHtml(s)}</div>`
    );
    const netsHtml = (netItems.length > 0 || svcItems.length > 0)
      ? netItems.concat(svcItems).join('')
      : '<span class="text-muted small">Сетевая активность не зафиксирована</span>';

    return `
      <tr class="st-app-row" data-app-id="${escapeHtml(app.id)}" role="button" title="Кликните для запуска ИИ-Ассистента">
        <td>
          <div class="st-cell-box">
            <div class="fw-bold text-light text-truncate" title="${escapeHtml(app.name)}">${escapeHtml(app.name)}</div>
            <div class="mt-1">${catBadge}${sysBadge}</div>
            ${purposeHtml}
            ${instHtml}
            ${exeHtml}
          </div>
        </td>
        <td>
          <div class="st-cell-box">
            <div class="fw-semibold text-light text-truncate" title="${escapeHtml(app.publisher || 'Неизвестен')}">${escapeHtml(app.publisher || 'Неизвестен')}</div>
            <div class="small text-info mt-1 text-truncate">Версия: ${escapeHtml(app.version || 'Не указана')} ${archBadge}</div>
            ${dateHtml}
            ${sizeHtml}
            ${runHtml}
          </div>
        </td>
        <td><div class="st-cell-box">${dirsHtml}</div></td>
        <td><div class="st-cell-box">${cfgsHtml}</div></td>
        <td><div class="st-cell-box">${netsHtml}</div></td>
      </tr>
    `;
  }

  function bindRowActions() {
    document.querySelectorAll('.view-config-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const appId = btn.getAttribute('data-app-id');
        const cfgPath = btn.getAttribute('data-cfg-path');
        openConfigModal(appId, cfgPath);
      };
    });

    document.querySelectorAll('.st-app-row').forEach(row => {
      row.onclick = (e) => {
        if (e.target.closest('button, a, input, select, .no-modal-trigger')) {
          return;
        }
        if (window.getSelection && window.getSelection().toString().trim().length > 0) {
          return;
        }
        const appId = row.getAttribute('data-app-id');
        const app = allApps.find(a => a.id === appId);
        if (app && window.AIModalDialog && window.AIModalDialog.open) {
          window.AIModalDialog.open({ program: app, panelId: 'sw-transparency' });
        } else if (app) {
          openResearchModal(appId);
        }
      };
    });
  }

  const CONFIG_API_BASES = ['/api/v1/software-scanner', '/api/windows/api/v1/software-scanner'];

  async function configApiFetch(suffix, opts) {
    let res = null;
    for (const base of CONFIG_API_BASES) {
      res = await fetch(base + suffix, opts);
      if (res.status !== 404 || base === CONFIG_API_BASES[CONFIG_API_BASES.length - 1]) break;
      const detail = await res.clone().json().catch(() => null);
      if (detail && detail.detail) break;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ('HTTP ' + res.status));
    }
    return res.json();
  }

  async function openConfigModal(appId, cfgPath) {
    const pathEl = document.getElementById('st-config-modal-path');
    const textEl = document.getElementById('st-config-modal-content');
    const statusEl = document.getElementById('st-config-modal-status');
    const saveBtn = document.getElementById('st-config-modal-save');
    const modalEl = document.getElementById('st-config-modal');

    pathEl.innerText = cfgPath;
    textEl.value = '';
    textEl.disabled = true;
    saveBtn.disabled = true;
    statusEl.className = 'small mt-2 text-muted';
    statusEl.innerText = 'Загрузка файла...';

    if (modalEl && window.bootstrap) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    try {
      const data = await configApiFetch('/config-file?path=' + encodeURIComponent(cfgPath));
      textEl.value = data.content;
      textEl.disabled = false;
      saveBtn.disabled = false;
      statusEl.innerText = '';
      saveBtn.onclick = async () => {
        saveBtn.disabled = true;
        try {
          await configApiFetch('/config-file', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: cfgPath, content: textEl.value })
          });
          statusEl.className = 'small mt-2 text-success';
          statusEl.innerText = 'Файл сохранён';
        } catch (e) {
          statusEl.className = 'small mt-2 text-danger';
          statusEl.innerText = 'Ошибка сохранения: ' + e.message;
        } finally {
          saveBtn.disabled = false;
        }
      };
    } catch (e) {
      statusEl.className = 'small mt-2 text-danger';
      statusEl.innerText = 'Ошибка загрузки: ' + e.message;
    }
  }

  function openResearchModal(appId) {
    const app = allApps.find(a => a.id === appId);
    const titleEl = document.getElementById('st-research-modal-title');
    const bodyEl = document.getElementById('st-research-modal-body');

    if (titleEl) titleEl.innerText = 'AI Исследование: ' + (app ? app.name : appId);
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="p-3 bg-secondary bg-opacity-10 rounded border border-secondary mb-3">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div>
              <h6 class="fw-bold text-info mb-1">${escapeHtml(app ? app.name : appId)}</h6>
              <div class="text-muted small">Издатель: ${escapeHtml(app?.publisher || 'Неизвестен')} | Версия: ${escapeHtml(app?.version || 'N/A')}</div>
            </div>
            <button class="btn btn-primary btn-sm d-flex align-items-center gap-1.5" id="btn-st-start-research">
              <i class="bi bi-robot"></i> Запросить AI-исследование
            </button>
          </div>
        </div>
        <div id="st-research-result-container">
          <div class="text-secondary small">
            <i class="bi bi-info-circle me-1"></i>Нажмите кнопку «Запросить AI-исследование», чтобы отправить запрос к модели ИИ для анализа рисков, безопасности и назначений конфигураций приложения.
          </div>
        </div>
      `;

      const startBtn = document.getElementById('btn-st-start-research');
      if (startBtn) {
        startBtn.onclick = () => executeAppResearch(appId);
      }
    }

    const modalEl = document.getElementById('st-research-modal');
    if (modalEl && window.bootstrap) {
      const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
      bsModal.show();
    }
  }

  async function executeAppResearch(appId) {
    const container = document.getElementById('st-research-result-container');
    const startBtn = document.getElementById('btn-st-start-research');

    if (startBtn) startBtn.disabled = true;
    if (container) {
      container.innerHTML = `
        <div class="text-center py-4 text-info">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>
          <span>Выполняется аналитическое исследование программы через языковую модель...</span>
        </div>
      `;
    }

    try {
      const payload = JSON.stringify({ app_id: appId });
      let res = await fetch('/api/v1/software-scanner/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload
      });
      if (!res.ok) {
        res = await fetch('/api/windows/software-transparency/research', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload
        });
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();

      if (container) {
        container.innerHTML = `
          <div class="card bg-black border-secondary p-3 mb-2">
            <h6 class="text-info fw-bold mb-2">📋 Описание программы:</h6>
            <p class="mb-2 text-light small">${escapeHtml(data.summary || data.description || 'Нет данных')}</p>
            ${data.config_purpose_explanation ? `<div class="mb-2 small"><strong class="text-warning">Конфигурации:</strong> ${escapeHtml(data.config_purpose_explanation)}</div>` : ''}
            ${data.data_storage_explanation ? `<div class="mb-2 small"><strong class="text-info">Хранение данных:</strong> ${escapeHtml(data.data_storage_explanation)}</div>` : ''}
            ${data.network_activity_explanation ? `<div class="mb-2 small"><strong class="text-success">Сетевая активность:</strong> ${escapeHtml(data.network_activity_explanation)}</div>` : ''}
            ${data.confidence_level ? `<div class="small text-muted">Уровень достоверности: ${escapeHtml(data.confidence_level)}</div>` : ''}
          </div>
        `;
      }
    } catch (err) {
      if (container) {
        container.innerHTML = `
          <div class="alert alert-danger py-2 d-flex align-items-center justify-content-between flex-wrap gap-2 small">
            <div><i class="bi bi-exclamation-triangle me-1"></i>Ошибка анализа: ${escapeHtml(err.message)}</div>
            <button type="button" class="btn btn-sm btn-outline-danger" id="btn-st-retry-research">Повторить</button>
          </div>
        `;
        const retryBtn = document.getElementById('btn-st-retry-research');
        if (retryBtn) {
          retryBtn.onclick = () => executeAppResearch(appId);
        }
      }
    } finally {
      if (startBtn) startBtn.disabled = false;
    }
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.innerText = String(text);
    return div.innerHTML;
  }

  window.initSoftwareTransparencyTab = initSoftwareTransparencyTab;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSoftwareTransparencyTab);
  } else {
    initSoftwareTransparencyTab();
  }
})();
