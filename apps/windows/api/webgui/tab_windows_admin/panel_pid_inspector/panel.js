/**
 * =============================================================================
 * Название: Панель инспектора процессов и досье токена (PID-инспектор)
 * =============================================================================
 * Описание:
 *   Исследование контекста безопасности процесса: родительский PID, доменная
 *   учетная запись, уровень целостности (Integrity Level), привилегии и сессия.
 *   Поддерживает поиск по PID, поиск по названию процесса и интерактивный
 *   выпадающий список активных процессов хоста.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_pid_inspector/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-01 15:35:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let cachedProcesses = [];
let isInspectorEventsBound = false;

/**
 * Загружает список активных процессов для выпадающего списка и поиска.
 * @returns {Promise<Array>} Список объектов процессов.
 */
export async function loadProcessesList() {
  const selectEl = document.getElementById('select-explain-process');
  if (selectEl && cachedProcesses.length === 0) {
    selectEl.innerHTML = '<option value="">-- Загрузка активных процессов... --</option>';
  }

  try {
    let list = [];
    try {
      const res = await fetch('/api/process-manager/list?limit=0&sort_by=name');
      if (res.ok) {
        list = await res.json();
      }
    } catch (_) {}

    if (!Array.isArray(list) || list.length === 0) {
      try {
        const fbRes = await fetch('/api/v1/tc/processes?limit=300&sort_by=name');
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          list = fbData.processes || [];
        }
      } catch (_) {}
    }

    if (Array.isArray(list) && list.length > 0) {
      cachedProcesses = list.sort((a, b) => {
        const na = (a.name || '').toLowerCase();
        const nb = (b.name || '').toLowerCase();
        if (na < nb) return -1;
        if (na > nb) return 1;
        return (a.pid || 0) - (b.pid || 0);
      });
    }

    const currentPid = document.getElementById('input-explain-pid')?.value;
    renderProcessOptions(cachedProcesses, currentPid || null);
    return cachedProcesses;
  } catch (err) {
    console.error('[PID-Инспектор] Ошибка загрузки процессов:', err);
    if (selectEl) {
      selectEl.innerHTML = '<option value="">-- Ошибка загрузки списка --</option>';
    }
    return [];
  }
}

/**
 * Отрисовывает элементы option в выпадающем списке процессов.
 * @param {Array} procs - Массив объектов процессов.
 * @param {string|number|null} [selectedPid=null] - Выбранный PID.
 */
export function renderProcessOptions(procs, selectedPid = null) {
  const selectEl = document.getElementById('select-explain-process');
  if (!selectEl) return;

  const currentVal = selectedPid !== null ? String(selectedPid) : (selectEl.value || '');
  if (!procs || procs.length === 0) {
    selectEl.innerHTML = '<option value="">-- Процессы не найдены --</option>';
    return;
  }

  let html = `<option value="">-- Выберите процесс (${procs.length}) --</option>`;
  for (const p of procs) {
    const pid = p.pid;
    const name = p.name || 'unknown';
    const user = p.username ? ` [${p.username}]` : '';
    const mem = p.memory_mb ? ` (${Math.round(p.memory_mb)} МБ)` : '';
    const isSelected = String(pid) === String(currentVal) ? 'selected' : '';
    html += `<option value="${pid}" ${isSelected}>${escapeHtml(name)} (PID: ${pid})${escapeHtml(user)}${escapeHtml(mem)}</option>`;
  }
  selectEl.innerHTML = html;
}

/**
 * Фильтрует список процессов по имени и обновляет выпадающий список.
 * @param {string} query - Подстрока имени процесса для поиска.
 */
export function filterProcessesByName(query) {
  const q = (query || '').trim().toLowerCase();
  const filtered = q
    ? cachedProcesses.filter(p => (p.name || '').toLowerCase().includes(q))
    : cachedProcesses;

  const currentPid = document.getElementById('input-explain-pid')?.value;
  renderProcessOptions(filtered, currentPid);

  if (filtered.length === 1) {
    const single = filtered[0];
    const pidInput = document.getElementById('input-explain-pid');
    if (pidInput && !pidInput.value) {
      pidInput.value = single.pid;
    }
  }
}

/**
 * Обработчик выбора процесса из выпадающего списка.
 * @param {string|number} pid - PID выбранного процесса.
 */
export function onProcessSelected(pid) {
  const pidVal = parseInt(pid, 10);
  if (!pidVal || isNaN(pidVal)) return;

  const pidInput = document.getElementById('input-explain-pid');
  if (pidInput) pidInput.value = String(pidVal);

  const found = cachedProcesses.find(p => p.pid === pidVal);
  if (found) {
    const nameInput = document.getElementById('input-explain-name');
    if (nameInput) nameInput.value = found.name || '';
  }

  handleExplainPid(pidVal);
}

/**
 * Исследует процесс по указанному PID или имени и формирует текстовое дерево токена.
 * @param {number|string|null} [targetPid=null] - PID для исследования.
 */
export async function handleExplainPid(targetPid = null) {
  const pidInput = document.getElementById('input-explain-pid');
  const nameInput = document.getElementById('input-explain-name');
  const outputEl = document.getElementById('pid-dossier-output');

  let pidVal = targetPid !== null ? parseInt(targetPid, 10) : parseInt(pidInput?.value || '0', 10);

  // Если PID не указан, пробуем найти по названию
  if ((!pidVal || isNaN(pidVal)) && nameInput?.value?.trim()) {
    const searchName = nameInput.value.trim().toLowerCase();
    const found = cachedProcesses.find(p => (p.name || '').toLowerCase() === searchName)
      || cachedProcesses.find(p => (p.name || '').toLowerCase().includes(searchName));
    if (found) {
      pidVal = found.pid;
      if (pidInput) pidInput.value = String(pidVal);
    }
  }

  if (!pidVal || isNaN(pidVal)) {
    if (outputEl) {
      outputEl.style.display = 'block';
      outputEl.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>Укажите корректный PID процесса или выберите процесс из списка.</span>';
    }
    return;
  }

  if (outputEl) {
    outputEl.style.display = 'block';
    outputEl.textContent = `Исследование процесса PID ${pidVal}...`;
  }

  try {
    const res = await fetch(`/api/windows/identity/explain-pid/${pidVal}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const acc = data.account || {};
    const privs = data.privileges || [];
    const groups = data.groups || [];

    // Синхронизируем имя процесса в строке поиска, если не было введено
    if (data.process_name && nameInput && !nameInput.value) {
      nameInput.value = data.process_name;
    }

    // Синхронизируем селект
    const selectEl = document.getElementById('select-explain-process');
    if (selectEl) {
      selectEl.value = String(pidVal);
    }

    const lines = [
      `PID ${data.pid}`,
      '│',
      `├── Process: ${data.process_name || 'unknown'}`,
      `├── Parent: ${data.parent_name || 'N/A'} (PID ${data.parent_pid || 'N/A'})`,
      '│',
      '├── Account',
      `│   ├── ${acc.domain || 'LOCAL'}\\${acc.user || 'SYSTEM'}`,
      `│   └── SID: ${acc.sid || 'N/A'}`,
      '│',
      `├── Groups (${groups.length})`,
      ...groups.map(g => `│   ├── ${g}`),
      '│',
      `├── Integrity: ${data.integrity || 'Medium'}`,
      `├── Elevated: ${data.elevated ? 'YES (🟢)' : 'NO'}`,
      '│',
      `├── Privileges (${privs.length})`,
      ...privs.map(p => `│   ├── ${p}`),
      '│',
      '└── Session',
      '    ├── Console',
      `    └── Session ID: ${data.session_id !== undefined ? data.session_id : 1}`,
    ];

    if (outputEl) outputEl.textContent = lines.join('\n');
  } catch (err) {
    if (outputEl) outputEl.textContent = `Ошибка исследования PID ${pidVal}: ${err.message}`;
  }
}

/**
 * Инициализирует обработчики событий и загрузку данных панели PID-инспектора.
 */
export async function initPidInspector() {
  if (!isInspectorEventsBound) {
    const btnExplain = document.getElementById('btn-explain-pid');
    if (btnExplain) {
      btnExplain.onclick = () => handleExplainPid();
    }

    const inputPid = document.getElementById('input-explain-pid');
    if (inputPid) {
      inputPid.onkeydown = (e) => {
        if (e.key === 'Enter') handleExplainPid();
      };
      inputPid.oninput = (e) => {
        const val = parseInt(e.target.value, 10);
        if (val) {
          const found = cachedProcesses.find(p => p.pid === val);
          if (found) {
            const nameInput = document.getElementById('input-explain-name');
            if (nameInput) nameInput.value = found.name || '';
            const selectEl = document.getElementById('select-explain-process');
            if (selectEl) selectEl.value = String(found.pid);
          }
        }
      };
    }

    const inputName = document.getElementById('input-explain-name');
    if (inputName) {
      inputName.oninput = (e) => filterProcessesByName(e.target.value);
      inputName.onkeydown = (e) => {
        if (e.key === 'Enter') handleExplainPid();
      };
    }

    const selectProc = document.getElementById('select-explain-process');
    if (selectProc) {
      selectProc.onchange = (e) => onProcessSelected(e.target.value);
    }

    const btnRefresh = document.getElementById('btn-refresh-processes-list');
    if (btnRefresh) {
      btnRefresh.onclick = async () => {
        btnRefresh.classList.add('disabled');
        await loadProcessesList();
        btnRefresh.classList.remove('disabled');
      };
    }

    isInspectorEventsBound = true;
  }

  await loadProcessesList();
}
