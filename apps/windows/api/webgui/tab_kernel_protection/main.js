/**
 * =============================================================================
 * Process Name: Windows Web Interface - Kernel & Protection Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер управления защитой ядра, системными драйверами
 *   и расследования причин блокировок доступа (Kernel & Protection).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script type="module" src="/html/tab_kernel_protection/main.js?v=20261101_v1"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_kernel_protection
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 14:40:00
 * =============================================================================
 */

let isTabActive = false;
let cachedDrivers = [];
let activeCategory = 'all';

/**
 * Инициализация вкладки Kernel & Protection при активации.
 */
export async function initKernelProtectionTab() {
  isTabActive = true;
  setupEventHandlers();
  await loadSummary();
  await loadDrivers();
  await loadMinifilters();
}

/**
 * Деактивация вкладки при переключении.
 */
export function deactivateKernelProtectionTab() {
  isTabActive = false;
}

/**
 * Установка обработчиков событий элементов UI.
 */
function setupEventHandlers() {
  const refreshBtn = document.getElementById('kp-btn-refresh');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      await loadSummary();
      await loadDrivers();
      await loadMinifilters();
      refreshBtn.disabled = false;
    });
  }

  // Фильтры категорий драйверов
  const catFilter = document.getElementById('kp-category-filter');
  if (catFilter && !catFilter.dataset.bound) {
    catFilter.dataset.bound = 'true';
    catFilter.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        catFilter.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCategory = btn.getAttribute('data-category') || 'all';
        renderDriversTable();
      });
    });
  }

  // Поиск драйверов
  const searchInput = document.getElementById('kp-driver-search');
  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    searchInput.addEventListener('input', () => {
      renderDriversTable();
    });
  }

  // Пресеты расследования блокировок
  document.querySelectorAll('.kp-preset-btn').forEach(btn => {
    if (!btn.dataset.bound) {
      btn.dataset.bound = 'true';
      btn.addEventListener('click', () => {
        const type = btn.getAttribute('data-type');
        const path = btn.getAttribute('data-path');
        const typeSelect = document.getElementById('kp-blocker-target-type');
        const pathInput = document.getElementById('kp-blocker-target-path');
        if (typeSelect) typeSelect.value = type;
        if (pathInput) pathInput.value = path;
      });
    }
  });

  // Кнопка запуска расследования
  const startInvestigateBtn = document.getElementById('kp-btn-start-investigation');
  if (startInvestigateBtn && !startInvestigateBtn.dataset.bound) {
    startInvestigateBtn.dataset.bound = 'true';
    startInvestigateBtn.addEventListener('click', runBlockerInvestigation);
  }

  // Кнопки SafeOps UCPD
  const disableUcpdBtn = document.getElementById('kp-btn-disable-ucpd');
  if (disableUcpdBtn && !disableUcpdBtn.dataset.bound) {
    disableUcpdBtn.dataset.bound = 'true';
    disableUcpdBtn.addEventListener('click', () => handleSafeOpsAction('disable_ucpd', 'ucpd', true));
  }

  const enableUcpdBtn = document.getElementById('kp-btn-enable-ucpd');
  if (enableUcpdBtn && !enableUcpdBtn.dataset.bound) {
    enableUcpdBtn.dataset.bound = 'true';
    enableUcpdBtn.addEventListener('click', () => handleSafeOpsAction('enable_ucpd', 'ucpd', false));
  }
}

/**
 * Загрузка сводного отчета и механизмов защиты ядра.
 */
async function loadSummary() {
  try {
    const res = await fetch('/api/kernel-protection/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const counter = document.getElementById('kp-drivers-counter');
    if (counter) {
      counter.textContent = `${data.total_drivers_count || 0} драйверов (${data.security_drivers_count || 0} защиты)`;
    }

    renderMechanismsGrid(data.mechanisms || []);
    updateSafeOpsStatus(data.mechanisms || []);
  } catch (err) {
    console.error('[KernelProtection] Ошибка загрузки сводки:', err);
  }
}

/**
 * Отрисовка карточек механизмов защиты ядра.
 */
function renderMechanismsGrid(mechanisms) {
  const container = document.getElementById('kp-mechanisms-grid');
  if (!container) return;

  if (!mechanisms || mechanisms.length === 0) {
    container.innerHTML = '<div class="col-12 text-center text-secondary py-3">Данные механизмов не получены</div>';
    return;
  }

  container.innerHTML = mechanisms.map(m => {
    let badgeClass = m.enabled ? 'kp-badge-active' : 'kp-badge-disabled';
    if (m.id === 'ucpd' && m.enabled) badgeClass = 'kp-badge-warning';

    return `
      <div class="col-md-6 col-lg-3">
        <div class="kp-card d-flex flex-column justify-content-between">
          <div>
            <div class="d-flex justify-content-between align-items-start mb-2">
              <span class="badge ${badgeClass}">${escapeHtml(m.status_label)}</span>
              <small class="text-secondary font-monospace">${escapeHtml(m.category)}</small>
            </div>
            <h6 class="fw-semibold text-body mb-1">${escapeHtml(m.name)}</h6>
            <p class="small text-secondary mb-2">${escapeHtml(m.description_ru)}</p>
          </div>
          <div class="border-top border-secondary border-opacity-25 pt-2 mt-auto">
            <small class="text-secondary d-block">
              <strong>Влияние:</strong> ${escapeHtml(m.impact_ru)}
            </small>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Загрузка списка всех драйверов с бэкенда.
 */
async function loadDrivers() {
  try {
    const res = await fetch('/api/kernel-protection/drivers');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cachedDrivers = await res.json();
    renderDriversTable();
  } catch (err) {
    console.error('[KernelProtection] Ошибка загрузки драйверов:', err);
    const tbody = document.getElementById('kp-drivers-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Ошибка загрузки: ${escapeHtml(err.message)}</td></tr>`;
  }
}

/**
 * Отрисовка таблицы драйверов с фильтрацией и привязкой к AIModalDialog.
 */
function renderDriversTable() {
  const tbody = document.getElementById('kp-drivers-tbody');
  const searchInput = document.getElementById('kp-driver-search');
  if (!tbody) return;

  const query = (searchInput?.value || '').trim().toLowerCase();
  const filtered = cachedDrivers.filter(d => {
    if (activeCategory !== 'all' && d.category !== activeCategory) return false;
    if (query) {
      return d.name.toLowerCase().includes(query) ||
             d.display_name.toLowerCase().includes(query) ||
             (d.purpose_ru && d.purpose_ru.toLowerCase().includes(query));
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">Драйверы по заданным критериям не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    const stateBadge = d.is_running ? 'kp-badge-active' : 'kp-badge-disabled';
    let critBadge = 'kp-badge-info';
    if (d.criticality === 'critical') critBadge = 'kp-badge-disabled';
    else if (d.criticality === 'high') critBadge = 'kp-badge-warning';

    return `
      <tr class="kp-clickable-row" data-driver-name="${escapeHtml(d.name)}">
        <td>
          <div class="fw-semibold text-body">${escapeHtml(d.display_name || d.name)}</div>
          <div class="small text-secondary font-monospace">${escapeHtml(d.name)}.sys</div>
        </td>
        <td><span class="badge ${stateBadge}">${escapeHtml(d.state)}</span></td>
        <td><span class="badge border border-secondary border-opacity-50 text-secondary">${escapeHtml(d.start_mode)}</span></td>
        <td><span class="badge kp-badge-info">${escapeHtml(d.category)}</span></td>
        <td><span class="badge ${critBadge}">${escapeHtml(d.criticality)}</span></td>
        <td class="small text-secondary">${escapeHtml(d.purpose_ru || 'Системный сервис драйвера')}</td>
      </tr>
    `;
  }).join('');

  // Привязка AIModalDialog при клике на строку таблицы драйверов
  tbody.querySelectorAll('.kp-clickable-row').forEach(row => {
    row.addEventListener('click', () => {
      const name = row.getAttribute('data-driver-name');
      const item = cachedDrivers.find(x => x.name === name);
      if (item) openDriverAiModal(item);
    });
  });
}

/**
 * Открытие карточки драйвера через универсальный AIModalDialog.
 */
function openDriverAiModal(driver) {
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) {
    console.warn('[KernelProtection] AIModalDialog не найден в window');
    return;
  }

  modal.show({
    title: `${driver.display_name || driver.name} (${driver.name}.sys)`,
    subtitle: `Категория: ${driver.category} | Критичность: ${driver.criticality}`,
    icon: '⚙️',
    tableType: 'service',
    badges: [
      { text: driver.state, class: driver.is_running ? 'badge bg-success' : 'badge bg-secondary' },
      { text: `Start: ${driver.start_mode}`, class: 'badge border text-secondary' },
      { text: `Критичность: ${driver.criticality}`, class: driver.criticality === 'critical' ? 'badge bg-danger' : 'badge bg-info' }
    ],
    metadata: [
      { label: 'Имя службы', value: driver.name, isCode: true },
      { label: 'Путь к бинарнику', value: driver.path_name || `C:\\Windows\\System32\\drivers\\${driver.name}.sys`, isCode: true, fullWidth: true },
      { label: 'Назначение', value: driver.purpose_ru, fullWidth: true },
      { label: 'Роль в защите', value: driver.protection_role || 'Стандартные операции ядра Windows', fullWidth: true },
      { label: 'Допустимость отключения', value: driver.can_disable ? 'Разрешено (SafeOps)' : 'Запрещено политикой ядра' }
    ]
  });
}

/**
 * Загрузка файловых минифильтров fltmc.
 */
async function loadMinifilters() {
  const tbody = document.getElementById('kp-minifilters-tbody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/kernel-protection/minifilters');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const filters = await res.json();

    if (!filters || filters.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">Минифильтры не обнаружены</td></tr>';
      return;
    }

    tbody.innerHTML = filters.map(f => `
      <tr class="kp-clickable-row" data-filter-name="${escapeHtml(f.name)}">
        <td>
          <div class="fw-semibold text-body">${escapeHtml(f.name)}</div>
          <div class="small text-secondary">${escapeHtml(f.vendor)}</div>
        </td>
        <td><span class="badge font-monospace kp-badge-info">${escapeHtml(f.altitude)}</span></td>
        <td><span class="badge border border-secondary border-opacity-50 text-secondary">${escapeHtml(f.altitude_group_ru)}</span></td>
        <td><span class="badge kp-badge-active">${f.instances_count}</span></td>
        <td class="font-monospace">${escapeHtml(f.frame)}</td>
        <td class="small text-secondary">${escapeHtml(f.purpose_ru)}</td>
      </tr>
    `).join('');

    tbody.querySelectorAll('.kp-clickable-row').forEach(row => {
      row.addEventListener('click', () => {
        const name = row.getAttribute('data-filter-name');
        const item = filters.find(x => x.name === name);
        if (item) openMinifilterAiModal(item);
      });
    });
  } catch (err) {
    console.error('[KernelProtection] Ошибка загрузки минифильтров:', err);
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

/**
 * Карточка минифильтра через AIModalDialog.
 */
function openMinifilterAiModal(filter) {
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) return;

  modal.show({
    title: `Минифильтр ${filter.name}`,
    subtitle: `Высота: ${filter.altitude} (${filter.altitude_group_ru})`,
    icon: '🗂️',
    tableType: 'generic',
    badges: [
      { text: `Altitude: ${filter.altitude}`, class: 'badge bg-primary' },
      { text: `Экземпляров: ${filter.instances_count}`, class: 'badge bg-success' }
    ],
    metadata: [
      { label: 'Имя фильтра', value: filter.name, isCode: true },
      { label: 'Группа высоты', value: filter.altitude_group_ru },
      { label: 'Вендор', value: filter.vendor },
      { label: 'Назначение', value: filter.purpose_ru, fullWidth: true }
    ]
  });
}

/**
 * Запуск расследования причины блокировки доступа (Blocker Detection).
 */
async function runBlockerInvestigation() {
  const targetType = document.getElementById('kp-blocker-target-type')?.value || 'registry_key';
  const targetPath = document.getElementById('kp-blocker-target-path')?.value.trim();
  const resultBox = document.getElementById('kp-blocker-result-box');
  const btn = document.getElementById('kp-btn-start-investigation');

  if (!targetPath) {
    alert('Пожалуйста, укажите целевой путь для расследования.');
    return;
  }

  if (resultBox) {
    resultBox.innerHTML = `
      <div class="text-center py-5 text-secondary">
        <div class="spinner-border text-primary mb-2" role="status"></div>
        <div>Выполняется диагностическая цепочка расследования блокировки...</div>
        <small class="text-secondary">Проверка UAC, UCPD, Tamper Protection, ACL, GPO, журналов событий...</small>
      </div>
    `;
  }

  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/kernel-protection/investigate-blocker', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: targetType,
        target_path: targetPath,
        operation: 'modify'
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const verdict = await res.json();
    renderBlockerVerdict(verdict);
  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = `<div class="alert alert-danger py-3">Сбой расследования: ${escapeHtml(err.message)}</div>`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Отрисовка вердикта расследования блокировки.
 */
function renderBlockerVerdict(verdict) {
  const resultBox = document.getElementById('kp-blocker-result-box');
  if (!resultBox) return;

  const isBlocked = verdict.is_blocked;
  const headerBadge = isBlocked ? 'kp-badge-disabled' : 'kp-badge-active';
  const icon = isBlocked ? '🛑' : '✅';

  const findingsHtml = (verdict.findings || []).map(f => {
    const stageIcon = f.passed ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger';
    return `
      <li class="list-group-item bg-transparent border-secondary border-opacity-25 d-flex align-items-start gap-2 py-2">
        <i class="bi ${stageIcon} mt-1"></i>
        <div class="small">
          <div class="fw-semibold text-body">${escapeHtml(f.stage)}</div>
          <div class="text-secondary">${escapeHtml(f.details_ru)}</div>
        </div>
      </li>
    `;
  }).join('');

  const remediationHtml = (verdict.remediation_steps_ru || []).map(step => `
    <li class="mb-1">${escapeHtml(step)}</li>
  `).join('');

  resultBox.innerHTML = `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div class="d-flex align-items-center gap-2">
          <span class="fs-4">${icon}</span>
          <div>
            <h6 class="mb-0 fw-bold">${escapeHtml(verdict.culprit_title_ru)}</h6>
            <small class="text-secondary">Уверенность AI-диагноста: <strong>${Math.round(verdict.confidence * 100)}%</strong></small>
          </div>
        </div>
        <span class="badge ${headerBadge}">${isBlocked ? 'БЛОКИРОВКА ОБНАРУЖЕНА' : 'ДОСТУП ОТКРЫТ'}</span>
      </div>

      <div class="alert alert-secondary py-2 small mb-3">
        ${escapeHtml(verdict.summary_ru)}
      </div>

      <h6 class="small fw-bold mb-2">Этапы расследования:</h6>
      <ul class="list-group list-group-flush mb-3 rounded border border-secondary border-opacity-25">
        ${findingsHtml}
      </ul>

      <h6 class="small fw-bold mb-2">Рекомендации SafeOps по разрешению:</h6>
      <ol class="small text-secondary ps-3 mb-0">
        ${remediationHtml}
      </ol>
    </div>
  `;
}

/**
 * Выполнение действия SafeOps над компонентом защиты.
 */
async function handleSafeOpsAction(action, componentName, confirmRisk) {
  const logBox = document.getElementById('kp-safeops-log');
  if (confirmRisk && !confirm(`Вы уверены, что хотите выполнить '${action}' над компонентом '${componentName}'?`)) {
    return;
  }

  appendSafeOpsLog(`[${new Date().toLocaleTimeString()}] Запуск действия ${action}...`);

  try {
    const res = await fetch('/api/kernel-protection/safe-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: action,
        component_name: componentName,
        confirm_risk: confirmRisk
      })
    });

    const data = await res.json();
    if (data.success) {
      appendSafeOpsLog(`[${new Date().toLocaleTimeString()}] УСПЕХ: ${data.message}`);
    } else {
      appendSafeOpsLog(`[${new Date().toLocaleTimeString()}] ОТКЛОНЕНО: ${data.message}`);
    }
    await loadSummary();
  } catch (err) {
    appendSafeOpsLog(`[${new Date().toLocaleTimeString()}] ОШИБКА: ${err.message}`);
  }
}

function updateSafeOpsStatus(mechanisms) {
  const ucpd = mechanisms.find(m => m.id === 'ucpd');
  const ucpdStatusBadge = document.getElementById('kp-safeops-ucpd-status');
  if (ucpdStatusBadge && ucpd) {
    ucpdStatusBadge.textContent = ucpd.status_label;
    ucpdStatusBadge.className = `badge ${ucpd.enabled ? 'kp-badge-warning' : 'kp-badge-active'}`;
  }
}

function appendSafeOpsLog(msg) {
  const logBox = document.getElementById('kp-safeops-log');
  if (!logBox) return;
  const div = document.createElement('div');
  div.textContent = msg;
  logBox.prepend(div);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
