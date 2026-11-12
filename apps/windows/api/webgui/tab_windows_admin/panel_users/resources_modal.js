/**
 * =============================================================================
 * Название: Модальное окно потребляемых ресурсов пользователя (User Resources Modal)
 * =============================================================================
 * Описание:
 *   Модальное окно со списком процессов и объемом потребляемых ресурсов
 *   (CPU, RAM, количество потоков, статус) для выбранного пользователя Windows.
 *   Включает быстрый поиск/фильтрацию, сортировку по памяти/нагрузке,
 *   а также быстрый переход в инспектор токена по PID и досье ИИ-ассистента.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_users/resources_modal.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-01 14:54:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let _userProcesses = [];
let _currentUser = '';
let _sortField = 'memory_mb';
let _sortAsc = false;
let _filterQuery = '';
let _isEventsBound = false;

/**
 * Получить кэшированный список процессов текущего пользователя.
 * @returns {Array} Список процессов.
 */
export function getUserProcessesCache() {
  return _userProcesses;
}

/**
 * Открытие модального окна потребляемых ресурсов для выбранного пользователя.
 * @param {string} username - Имя учетной записи Windows.
 * @param {boolean} [forceRefresh=false] - Принудительное обновление данных.
 */
export async function openUserResourcesModal(username, forceRefresh = false) {
  if (!username) return;
  _currentUser = username;

  const modalEl = document.getElementById('userResourcesModal');
  if (!modalEl) {
    console.warn('[UserResourcesModal] Элемент #userResourcesModal не найден в DOM');
    return;
  }

  initUserResourcesModalEvents();

  const titleUser = document.getElementById('user-resources-modal-username');
  if (titleUser) titleUser.innerText = username;

  const loadingEl = document.getElementById('user-resources-modal-loading');
  const contentEl = document.getElementById('user-resources-modal-content');
  const errorEl = document.getElementById('user-resources-modal-error');

  if (loadingEl) loadingEl.style.display = 'block';
  if (contentEl) contentEl.style.display = 'none';
  if (errorEl) errorEl.style.display = 'none';

  if (window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  try {
    const res = await fetch(`/api/sysadmin/accounts/${encodeURIComponent(username)}/metrics`);
    if (!res.ok) {
      throw new Error(`Ошибка ${res.status}: не удалось получить метрики ресурсов`);
    }

    const data = await res.json();
    _userProcesses = data.processes || data.top_processes || [];

    // Заполнение сводных карточек в шапке модального окна
    const countEl = document.getElementById('user-res-procs-count');
    if (countEl) countEl.innerText = String(data.total_processes ?? _userProcesses.length);

    const memEl = document.getElementById('user-res-memory-total');
    if (memEl) {
      const ramMb = data.total_memory_rss_mb ?? 0;
      memEl.innerText = ramMb > 1024 ? `${(ramMb / 1024).toFixed(2)} GB` : `${ramMb} MB`;
    }

    const cpuEl = document.getElementById('user-res-cpu-total');
    if (cpuEl) cpuEl.innerText = `${data.total_cpu_percent ?? 0}%`;

    const profileEl = document.getElementById('user-res-profile-path');
    if (profileEl) {
      const profPath = data.profile_path || 'Локальный профиль';
      profileEl.innerText = profPath;
      profileEl.setAttribute('title', profPath);
    }

    // Сброс поля поиска
    const searchInput = document.getElementById('user-res-search-input');
    if (searchInput && !forceRefresh) {
      searchInput.value = '';
      _filterQuery = '';
    }

    renderUserResourcesTable();

    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'block';
  } catch (err) {
    console.error('[UserResourcesModal] Ошибка загрузки ресурсов:', err);
    if (loadingEl) loadingEl.style.display = 'none';
    if (errorEl) {
      errorEl.style.display = 'block';
      errorEl.innerText = `Не удалось загрузить список ресурсов: ${err.message}`;
    }
  }
}

/**
 * Отрисовка таблицы процессов и ресурсов пользователя с учетом фильтра и сортировки.
 */
export function renderUserResourcesTable() {
  const tbody = document.getElementById('user-resources-tbody');
  if (!tbody) return;

  const q = (_filterQuery || '').toLowerCase().trim();
  let filtered = _userProcesses.filter(p => {
    if (!q) return true;
    const nameMatch = p.name && p.name.toLowerCase().includes(q);
    const pidMatch = String(p.pid).includes(q);
    return nameMatch || pidMatch;
  });

  // Сортировка
  filtered.sort((a, b) => {
    let valA = a[_sortField];
    let valB = b[_sortField];

    if (_sortField === 'name') {
      valA = (valA || '').toLowerCase();
      valB = (valB || '').toLowerCase();
      return _sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }

    valA = Number(valA || 0);
    valB = Number(valB || 0);
    return _sortAsc ? valA - valB : valB - valA;
  });

  // Подсчет сводки отфильтрованных процессов
  let filteredRam = 0;
  for (const p of filtered) {
    filteredRam += (p.memory_mb || 0);
  }

  const filteredCountEl = document.getElementById('user-res-filtered-count');
  if (filteredCountEl) filteredCountEl.innerText = String(filtered.length);

  const totalCountEl = document.getElementById('user-res-total-count');
  if (totalCountEl) totalCountEl.innerText = String(_userProcesses.length);

  const filteredRamEl = document.getElementById('user-res-filtered-ram');
  if (filteredRamEl) {
    filteredRamEl.innerText = filteredRam > 1024
      ? `${(filteredRam / 1024).toFixed(2)} GB`
      : `${filteredRam.toFixed(1)} MB`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-3">Процессы по заданному критерию не найдены</td></tr>';
    return;
  }

  // Максимальная память для процентной полосы
  const maxMem = Math.max(...filtered.map(p => p.memory_mb || 0), 1);

  tbody.innerHTML = filtered.map(p => {
    const memPercent = Math.min(100, Math.round(((p.memory_mb || 0) / maxMem) * 100));
    const cpuVal = Number(p.cpu_percent || 0);

    let cpuBadgeClass = 'text-muted';
    if (cpuVal > 20) cpuBadgeClass = 'text-danger fw-bold';
    else if (cpuVal > 5) cpuBadgeClass = 'text-warning fw-semibold';

    const statusText = p.status || 'running';
    const isRunning = statusText.toLowerCase() === 'running';

    return `
      <tr>
        <td class="font-monospace text-secondary small" style="width: 75px;">
          <span class="ui-badge ui-badge-neutral">${p.pid}</span>
        </td>
        <td>
          <div class="d-flex align-items-center gap-1.5">
            <i class="bi bi-gear text-info small"></i>
            <span class="fw-semibold text-body font-monospace">${escapeHtml(p.name)}</span>
          </div>
        </td>
        <td style="min-width: 150px;">
          <div class="d-flex align-items-center justify-content-between small font-monospace">
            <span class="text-info fw-semibold">${p.memory_mb || 0} MB</span>
            <span class="text-muted" style="font-size: 0.7rem;">${memPercent}%</span>
          </div>
          <div class="progress mt-0.5" style="height: 3px; background-color: var(--surface-2, rgba(255,255,255,0.08));">
            <div class="progress-bar bg-info" role="progressbar" style="width: ${memPercent}%;"></div>
          </div>
        </td>
        <td class="font-monospace small ${cpuBadgeClass}" style="width: 90px;">
          ${cpuVal.toFixed(1)}%
        </td>
        <td class="small" style="width: 130px;">
          <span class="text-muted small">${p.num_threads || 1} пот.</span>
          <span class="ui-badge ${isRunning ? 'ui-badge-success' : 'ui-badge-neutral'} ms-1">${escapeHtml(statusText)}</span>
        </td>
        <td style="text-align: right; width: 150px;">
          <button class="btn btn-xs btn-outline-info py-0 px-1.5 btn-res-explain-pid me-1" data-pid="${p.pid}" title="Инспектор токена PID">
            <i class="bi bi-search"></i> PID
          </button>
          <button class="btn btn-xs btn-outline-primary py-0 px-1.5 btn-res-ai-dossier" data-name="${escapeHtml(p.name)}" data-pid="${p.pid}" title="Досье ИИ-ассистента">
            <i class="bi bi-cpu"></i> ИИ
          </button>
        </td>
      </tr>
    `;
  }).join('');

  // Привязка действий строк таблицы
  tbody.querySelectorAll('.btn-res-explain-pid').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const pid = btn.getAttribute('data-pid');
      if (pid) navigateToPidInspector(pid);
    };
  });

  tbody.querySelectorAll('.btn-res-ai-dossier').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const name = btn.getAttribute('data-name');
      const pid = parseInt(btn.getAttribute('data-pid'), 10);
      if (window.AIModalDialog && typeof window.AIModalDialog.open === 'function') {
        window.AIModalDialog.open(name, name, pid);
      } else {
        alert(`Процесс: ${name} (PID ${pid})`);
      }
    };
  });
}

/**
 * Переход на вкладку инспектора токена PID из модального окна ресурсов.
 * @param {string|number} pid - Идентификатор процесса.
 */
function navigateToPidInspector(pid) {
  const modalEl = document.getElementById('userResourcesModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  }

  // Переключение субтаба на 'pid'
  if (typeof window.switchWindowsAdminSubTab === 'function') {
    window.switchWindowsAdminSubTab('pid', true);
  } else {
    const pidBtn = document.getElementById('subtab-winadmin-pid-btn');
    if (pidBtn) pidBtn.click();
  }

  const pidInput = document.getElementById('input-explain-pid');
  if (pidInput) {
    pidInput.value = String(pid);
  }

  const explainBtn = document.getElementById('btn-explain-pid');
  if (explainBtn) {
    setTimeout(() => explainBtn.click(), 150);
  }
}

/**
 * Инициализация обработчиков событий модального окна потребления ресурсов.
 */
export function initUserResourcesModalEvents() {
  if (_isEventsBound) return;
  const modalEl = document.getElementById('userResourcesModal');
  if (!modalEl) return;

  _isEventsBound = true;

  const searchInput = document.getElementById('user-res-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      _filterQuery = e.target.value;
      renderUserResourcesTable();
    });
  }

  const sortSelect = document.getElementById('user-res-sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === 'mem_desc') { _sortField = 'memory_mb'; _sortAsc = false; }
      else if (val === 'mem_asc') { _sortField = 'memory_mb'; _sortAsc = true; }
      else if (val === 'cpu_desc') { _sortField = 'cpu_percent'; _sortAsc = false; }
      else if (val === 'cpu_asc') { _sortField = 'cpu_percent'; _sortAsc = true; }
      else if (val === 'name_asc') { _sortField = 'name'; _sortAsc = true; }
      else if (val === 'pid_asc') { _sortField = 'pid'; _sortAsc = true; }
      renderUserResourcesTable();
    });
  }

  const refreshBtn = document.getElementById('btn-refresh-user-resources');
  if (refreshBtn) {
    refreshBtn.onclick = () => {
      if (_currentUser) {
        openUserResourcesModal(_currentUser, true);
      }
    };
  }
}
