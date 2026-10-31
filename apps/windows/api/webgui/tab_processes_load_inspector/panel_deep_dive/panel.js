/**
 * Модуль модального окна Process Intelligence Deep Dive (7 виджетов).
 * Включает паспорт инстанса, SafeOps действия, телеметрию сенсоров и сэмплы.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/panel_deep_dive/panel.js
 * Updated: 2026-10-31 19:16:00
 */

import {
  formatDuration,
  showToast,
  openGenericModal,
  isProcessesTabActive
} from '../common/ui_utils.js?v=20261031_v2';
import {
  initCharts,
  resizeCharts,
  updateChartSamples,
  getChartInterval,
  setChartInterval
} from './charts.js';
import {
  loadInstanceLineage,
  loadInstanceSockets,
  loadInstanceFileActivity,
  initTableResizers
} from './widgets.js?v=20261017_v2';
import { openProcessAiModal } from '../panel_ai_audit/panel.js?v=20261031_v2';
import { killProcess } from '../panel_process_manager/panel.js';

let selectedInstanceId = null;
let selectedInstanceData = null;
let cachedActiveInstances = [];
let cachedHistoryInstances = [];
let currentInstanceFilter = 'active';
let isDeepDiveModalOpen = false;
let deepDiveSampleTimer = null;

/**
 * Инициализирует модуль Deep Dive модального окна.
 */
export function initDeepDivePanel() {
  initCharts();
  initSafeOps();
  initTableResizers();
  setupDeepDiveControls();
}

/**
 * Настраивает селекторы и фильтры в модальном окне Deep Dive.
 */
function setupDeepDiveControls() {
  const searchInput = document.getElementById('deep-dive-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => loadInstancesList());
  }

  const selectEl = document.getElementById('deep-dive-instance-select');
  if (selectEl) {
    selectEl.addEventListener('change', () => selectInstance(selectEl.value));
  }

  const btnActive = document.getElementById('btn-inst-filter-active') || document.getElementById('btn-filter-inst-active');
  const btnHistory = document.getElementById('btn-inst-filter-history') || document.getElementById('btn-filter-inst-history');
  if (btnActive && btnHistory) {
    btnActive.addEventListener('click', () => {
      currentInstanceFilter = 'active';
      btnActive.className = 'btn btn-xs btn-outline-info active';
      btnHistory.className = 'btn btn-xs btn-outline-secondary';
      loadInstancesList();
    });
    btnHistory.addEventListener('click', () => {
      currentInstanceFilter = 'history';
      btnHistory.className = 'btn btn-xs btn-outline-info active';
      btnActive.className = 'btn btn-xs btn-outline-secondary';
      loadInstancesList();
    });
  }

  const intervalBtns = document.querySelectorAll('.btn-chart-interval');
  intervalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      intervalBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setChartInterval(btn.getAttribute('data-interval') || '1m');
      loadInstanceSamples();
    });
  });

  const modalDeepDive = document.getElementById('modal-process-deep-dive');
  if (modalDeepDive) {
    modalDeepDive.addEventListener('hide.bs.modal', () => {
      if (document.activeElement && modalDeepDive.contains(document.activeElement)) {
        document.activeElement.blur();
      }
      isDeepDiveModalOpen = false;
      stopDeepDiveSamplePolling();
    });
  }

  const btnCloseModal = document.querySelector('#modal-process-deep-dive .btn-close');
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', () => {
      isDeepDiveModalOpen = false;
      stopDeepDiveSamplePolling();
    });
  }

  const btnCloseModalFooter = document.getElementById('modal-deep-dive-close-btn');
  if (btnCloseModalFooter) {
    btnCloseModalFooter.addEventListener('click', () => {
      isDeepDiveModalOpen = false;
      stopDeepDiveSamplePolling();
    });
  }
}

/**
 * Открывает паспорт процесса по его PID.
 * @param {number|string} pid - Идентификатор процесса.
 */
export async function openDeepDiveModalByPid(pid) {
  const cleanPid = parseInt(pid, 10);
  if (!cleanPid) return;

  const modalEl = document.getElementById('modal-process-deep-dive');
  openGenericModal(modalEl);
  isDeepDiveModalOpen = true;

  const pidBadge = document.getElementById('modal-deep-dive-pid-badge');
  if (pidBadge) pidBadge.textContent = `PID: ${cleanPid}`;

  const cardPid = document.getElementById('inst-card-pid');
  if (cardPid) cardPid.textContent = `PID: ${cleanPid}`;

  // Предварительно заполняем виртуальный профиль на время загрузки
  renderVirtualInstanceProfile({ pid: cleanPid, name: `PID ${cleanPid}` });

  // Загружаем список активных инстансов
  await loadInstancesList();

  // Ищем инстанс по PID среди кэшированных активных
  let match = cachedActiveInstances.find(i => Number(i.pid) === cleanPid);
  if (!match) {
    try {
      const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/active?search=${cleanPid}`);
      if (res.ok) {
        const list = await res.json();
        if (Array.isArray(list) && list.length > 0) {
          match = list.find(x => Number(x.pid) === cleanPid) || list[0];
        }
      }
    } catch (_) {}
  }

  const targetId = match ? String(match.instance_id) : String(cleanPid);
  await selectInstance(targetId);

  const select = document.getElementById('deep-dive-instance-select');
  if (select && targetId) {
    select.value = targetId;
  }

  setTimeout(() => {
    resizeCharts();
  }, 150);

  startDeepDiveSamplePolling();
}

/**
 * Запускает опрос свежих сэмплов инстанса.
 */
export function startDeepDiveSamplePolling() {
  stopDeepDiveSamplePolling();
  if (!selectedInstanceId) return;
  deepDiveSampleTimer = setInterval(async () => {
    if (!isDeepDiveModalOpen || !isProcessesTabActive()) {
      stopDeepDiveSamplePolling();
      return;
    }
    if (!selectedInstanceData || selectedInstanceData.status === 'RUNNING') {
      await loadInstanceSamples();
    }
  }, 1000);
}

/**
 * Останавливает таймер опроса сэмплов инстанса.
 */
export function stopDeepDiveSamplePolling() {
  if (deepDiveSampleTimer) {
    clearInterval(deepDiveSampleTimer);
    deepDiveSampleTimer = null;
  }
}

/**
 * Загружает список инстансов процессов для выпадающего списка.
 */
export async function loadInstancesList() {
  try {
    const searchVal = document.getElementById('deep-dive-search')?.value.trim() || '';
    const endpoint = currentInstanceFilter === 'active'
      ? `/api/v1/tab-processes-load-inspector/panel-deep-dive/active?limit=100${searchVal ? '&search=' + encodeURIComponent(searchVal) : ''}`
      : `/api/v1/tab-processes-load-inspector/panel-deep-dive/history?limit=100${searchVal ? '&search=' + encodeURIComponent(searchVal) : ''}`;

    const res = await fetch(endpoint);
    if (!res.ok) return;

    const instances = await res.json();
    if (currentInstanceFilter === 'active') {
      cachedActiveInstances = instances;
      const countBadge = document.getElementById('count-inst-active');
      if (countBadge) countBadge.textContent = instances.length;
    } else {
      cachedHistoryInstances = instances;
    }

    renderInstanceDropdown(instances);
  } catch (e) {
    console.warn('[ProcessActivity] Error loading instances:', e);
  }
}

/**
 * Отрисовывает элементы в выпадающем списке инстансов.
 */
function renderInstanceDropdown(instances) {
  const select = document.getElementById('deep-dive-instance-select');
  if (!select) return;

  const currentVal = selectedInstanceId ? String(selectedInstanceId) : '';
  select.innerHTML = '<option value="">Выберите процесс для анализа...</option>';

  instances.forEach(inst => {
    const opt = document.createElement('option');
    opt.value = String(inst.instance_id);
    const statusIcon = inst.status === 'RUNNING' ? '🟢' : inst.status === 'SUSPENDED' ? '🟡' : '⚪';
    opt.textContent = `${statusIcon} ${inst.name} (PID: ${inst.pid}, #${inst.instance_id}) - CPU: ${(inst.cpu_percent || 0).toFixed(1)}% | ${(inst.memory_mb || 0).toFixed(0)} MB`;
    if (String(inst.instance_id) === currentVal || String(inst.pid) === currentVal) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });
}

/**
 * Выбирает инстанс для отображения в паспорте и графиках.
 * @param {number|string} instanceId - ID инстанса или PID процесса.
 */
export async function selectInstance(instanceId) {
  if (!instanceId) return;
  selectedInstanceId = String(instanceId).trim();

  try {
    const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}`);
    if (res.ok) {
      selectedInstanceData = await res.json();
      renderInstanceProfileCard(selectedInstanceData);
      await Promise.all([
        loadInstanceSamples(),
        loadInstanceLineage(selectedInstanceId, selectInstance),
        loadInstanceSockets(selectedInstanceId),
        loadInstanceFileActivity(selectedInstanceId)
      ]);
    } else {
      const pidNum = parseInt(selectedInstanceId, 10);
      if (pidNum) {
        renderVirtualInstanceProfile({ pid: pidNum, name: `PID ${pidNum}` });
        await loadInstanceSamples();
      }
    }
  } catch (e) {
    console.error('[ProcessActivity] Error fetching instance details:', e);
  }
}

/**
 * Отрисовывает виртуальный паспорт для хост-процесса.
 */
function renderVirtualInstanceProfile(p) {
  const nameEl = document.getElementById('inst-card-name');
  if (nameEl) nameEl.textContent = p.name || 'Unknown';

  const pidEl = document.getElementById('inst-card-pid');
  if (pidEl) pidEl.textContent = `PID: ${p.pid}`;

  const headPidBadge = document.getElementById('modal-deep-dive-pid-badge');
  if (headPidBadge) headPidBadge.textContent = `PID: ${p.pid}`;

  const idEl = document.getElementById('inst-card-id');
  if (idEl) idEl.textContent = 'instance_id: #Host';

  const headInstBadge = document.getElementById('modal-deep-dive-inst-badge');
  if (headInstBadge) headInstBadge.textContent = '#Host';

  const pathEl = document.getElementById('inst-card-path');
  if (pathEl) pathEl.textContent = p.executable_path || p.exe || '-';

  const userEl = document.getElementById('inst-card-user');
  if (userEl) userEl.textContent = p.username || 'SYSTEM';

  const integrityEl = document.getElementById('inst-card-integrity');
  if (integrityEl) integrityEl.textContent = 'Medium';

  const startEl = document.getElementById('inst-card-start');
  if (startEl) startEl.textContent = '--:--:--';

  const uptimeEl = document.getElementById('inst-card-uptime');
  if (uptimeEl) uptimeEl.textContent = '⏱️ Uptime: Live';

  const cmdEl = document.getElementById('inst-card-cmdline');
  if (cmdEl) cmdEl.textContent = p.command_line || p.cmdline || p.name;

  const statusEl = document.getElementById('inst-card-status');
  if (statusEl) statusEl.textContent = 'RUNNING';
}

/**
 * Отрисовывает карточку паспорта инстанса.
 */
function renderInstanceProfileCard(inst) {
  if (!inst) return;

  const nameEl = document.getElementById('inst-card-name');
  if (nameEl) nameEl.textContent = inst.name || 'Unknown';

  const pidEl = document.getElementById('inst-card-pid');
  if (pidEl) pidEl.textContent = `PID: ${inst.pid}`;

  const headPidBadge = document.getElementById('modal-deep-dive-pid-badge');
  if (headPidBadge) headPidBadge.textContent = `PID: ${inst.pid}`;

  const idEl = document.getElementById('inst-card-id');
  if (idEl) idEl.textContent = `instance_id: #${inst.instance_id}`;

  const headInstBadge = document.getElementById('modal-deep-dive-inst-badge');
  if (headInstBadge) headInstBadge.textContent = `#${inst.instance_id}`;

  const pathEl = document.getElementById('inst-card-path');
  if (pathEl) pathEl.textContent = inst.executable_path || '-';

  const userEl = document.getElementById('inst-card-user');
  if (userEl) userEl.textContent = inst.user_name || 'SYSTEM / Local';

  const integrityEl = document.getElementById('inst-card-integrity');
  if (integrityEl) integrityEl.textContent = inst.integrity_level || 'Medium';

  const startEl = document.getElementById('inst-card-start');
  if (startEl) startEl.textContent = inst.start_time ? new Date(inst.start_time).toLocaleString('ru-RU') : '--';

  const uptimeEl = document.getElementById('inst-card-uptime');
  if (uptimeEl) uptimeEl.textContent = `⏱️ Uptime: ${formatDuration(inst.uptime_seconds)}`;

  const cmdEl = document.getElementById('inst-card-cmdline');
  if (cmdEl) cmdEl.textContent = inst.command_line || inst.executable_path || '-';

  const parentLink = document.getElementById('inst-card-parent-link');
  if (parentLink) {
    if (inst.parent_instance_id) {
      parentLink.innerHTML = `<a href="javascript:void(0)" class="text-info text-decoration-none fw-bold" id="link-parent-inst">Родитель #${inst.parent_instance_id}</a>`;
      document.getElementById('link-parent-inst')?.addEventListener('click', () => selectInstance(inst.parent_instance_id));
    } else {
      parentLink.textContent = inst.ppid ? `PPID: ${inst.ppid}` : 'Корневой (Root)';
    }
  }

  const statusBadge = document.getElementById('inst-card-status');
  const suspendBtn = document.getElementById('btn-safeops-suspend');
  const resumeBtn = document.getElementById('btn-safeops-resume');

  if (statusBadge) {
    statusBadge.textContent = inst.status;
    if (inst.status === 'RUNNING') {
      statusBadge.className = 'badge bg-success fs-6 px-3 py-1.5';
      suspendBtn?.classList.remove('d-none');
      resumeBtn?.classList.add('d-none');
    } else if (inst.status === 'SUSPENDED') {
      statusBadge.className = 'badge bg-warning text-dark fs-6 px-3 py-1.5';
      suspendBtn?.classList.add('d-none');
      resumeBtn?.classList.remove('d-none');
    } else {
      statusBadge.className = 'badge bg-secondary fs-6 px-3 py-1.5';
      statusBadge.textContent = `EXITED (${inst.exit_code !== null ? 'code: ' + inst.exit_code : '0'})`;
      suspendBtn?.classList.add('d-none');
      resumeBtn?.classList.add('d-none');
    }
  }
}

/**
 * Загружает сэмплы метрик выбранного инстанса.
 */
async function loadInstanceSamples() {
  if (!selectedInstanceId) return;
  try {
    const limitMap = { '1m': 60, '5m': 150, '1h': 300, '24h': 1000 };
    const limit = limitMap[getChartInterval()] || 100;
    const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}/samples?limit=${limit}`);
    if (!res.ok) return;

    const samples = await res.json();
    if (!Array.isArray(samples)) return;

    updateChartSamples(samples);

    if (samples.length > 0) {
      const last = samples[samples.length - 1];
      document.getElementById('chart-cpu-current').textContent = `${last.cpu_percent.toFixed(1)}% | ${last.thread_count} thr`;
      document.getElementById('chart-ram-current').textContent = `${last.working_set_mb.toFixed(1)} MB`;
      document.getElementById('chart-gpu-current').textContent = `${last.gpu_load_percent.toFixed(1)}% | ${last.gpu_vram_mb.toFixed(0)} MB`;
      document.getElementById('chart-disk-current').textContent = `${(last.disk_read_bytes_sec / 1024).toFixed(0)} R / ${(last.disk_write_bytes_sec / 1024).toFixed(0)} W KB/s`;

      document.getElementById('metric-handles-count').textContent = last.handle_count || 0;
      document.getElementById('metric-gdi-count').textContent = last.gdi_objects || 0;
      document.getElementById('metric-user-count').textContent = last.user_objects || 0;
      document.getElementById('metric-page-faults').textContent = (last.page_faults_sec || 0).toFixed(1);

      const leakBadge = document.getElementById('badge-leak-risk');
      if (leakBadge) {
        if ((last.gdi_objects || 0) > 8000 || (last.user_objects || 0) > 8000 || (last.handle_count || 0) > 50000) {
          leakBadge.className = 'badge bg-danger';
          leakBadge.textContent = 'КРИТИЧЕСКИЙ РИСК УТЕЧКИ';
        } else if ((last.gdi_objects || 0) > 3000 || (last.handle_count || 0) > 10000) {
          leakBadge.className = 'badge bg-warning text-dark';
          leakBadge.textContent = 'Умеренный риск';
        } else {
          leakBadge.className = 'badge bg-success';
          leakBadge.textContent = 'Низкий риск';
        }
      }
    }
  } catch (e) {
    console.warn('[ProcessActivity] Error loading samples:', e);
  }
}

/**
 * Привязывает обработчики SafeOps действий (смена приоритета, suspend, dump, kill).
 */
function initSafeOps() {
  document.getElementById('btn-safeops-set-priority')?.addEventListener('click', async () => {
    if (!selectedInstanceId) return;
    const prio = document.getElementById('select-proc-priority')?.value;
    try {
      const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}/priority`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority: prio })
      });
      if (res.ok) showToast(`Приоритет изменен на ${prio}`, 'success');
      else showToast('Ошибка смены приоритета', 'warning');
    } catch (e) {
      showToast(e.message, 'danger');
    }
  });

  document.getElementById('btn-safeops-suspend')?.addEventListener('click', async () => {
    if (!selectedInstanceId) return;
    try {
      const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}/suspend`, { method: 'POST' });
      if (res.ok) {
        showToast('Потоки процесса приостановлены', 'warning');
        selectInstance(selectedInstanceId);
      }
    } catch (e) { showToast(e.message, 'danger'); }
  });

  document.getElementById('btn-safeops-resume')?.addEventListener('click', async () => {
    if (!selectedInstanceId) return;
    try {
      const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}/resume`, { method: 'POST' });
      if (res.ok) {
        showToast('Потоки процесса возобновлены', 'success');
        selectInstance(selectedInstanceId);
      }
    } catch (e) { showToast(e.message, 'danger'); }
  });

  document.getElementById('btn-safeops-dump')?.addEventListener('click', async () => {
    if (!selectedInstanceId) return;
    showToast('Создание дампа памяти...', 'info');
    try {
      const res = await fetch(`/api/v1/tab-processes-load-inspector/panel-deep-dive/${encodeURIComponent(selectedInstanceId)}/dump`, { method: 'POST' });
      if (res.ok) {
        const r = await res.json();
        showToast(`Дамп памяти сохранен: ${r.dump_path || 'Temp'}`, 'success');
      }
    } catch (e) { showToast(e.message, 'danger'); }
  });

  document.getElementById('btn-safeops-ai-audit')?.addEventListener('click', () => {
    if (selectedInstanceData) {
      openProcessAiModal(selectedInstanceData, 'instance');
    }
  });

  document.getElementById('btn-modal-deep-dive-ai')?.addEventListener('click', () => {
    if (selectedInstanceData) {
      openProcessAiModal(selectedInstanceData, 'instance');
    }
  });

  document.getElementById('btn-safeops-kill')?.addEventListener('click', () => {
    if (!selectedInstanceData) return;
    killProcess(selectedInstanceData.pid, selectedInstanceData.name, false);
  });
}
