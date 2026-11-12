/**
 * =============================================================================
 * Process Name: Common WebGUI - AI Instruments Tab Controller
 * =============================================================================
 * Description:
 *   Модуль контроллера вкладки управления базой инструментов цепочек размышлений.
 *   Обеспечивает загрузку каталога, фильтрацию, модальное редактирование,
 *   интерактивный запуск инструментов с параметрами, принудительную синхронизацию
 *   с toolchain_tools.md, экспорт в CSV и автоизвлечение из CoT.
 *
 * File: main.js
 * Package: apps/common/webgui/tab_instruments
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 16:43:00
 * =============================================================================
 */

let instrumentsCache = new Map();
let currentRunningTool = null;
let searchDebounceTimer = null;

/**
 * Инициализация вкладки инструментов.
 */
export async function initInstrumentsTab() {
  bindEvents();
  await loadInstrumentsList();
  await loadStorageStatus();
}

/**
 * Привязка обработчиков событий элементов вкладки.
 */
function bindEvents() {
  // Поиск с debounce
  const searchInput = document.getElementById('inst-search-input');
  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    searchInput.addEventListener('input', () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        loadInstrumentsList();
      }, 250);
    });
  }

  // Фильтры
  const filterType = document.getElementById('inst-filter-type');
  if (filterType && !filterType.dataset.bound) {
    filterType.dataset.bound = 'true';
    filterType.addEventListener('change', () => loadInstrumentsList());
  }

  const filterEntity = document.getElementById('inst-filter-entity');
  if (filterEntity && !filterEntity.dataset.bound) {
    filterEntity.dataset.bound = 'true';
    filterEntity.addEventListener('change', () => loadInstrumentsList());
  }

  // Кнопка обновления каталога
  const btnRefresh = document.getElementById('inst-btn-refresh');
  if (btnRefresh && !btnRefresh.dataset.bound) {
    btnRefresh.dataset.bound = 'true';
    btnRefresh.addEventListener('click', () => loadInstrumentsList());
  }

  // Кнопка создания инструмента
  const btnCreate = document.getElementById('inst-btn-create');
  if (btnCreate && !btnCreate.dataset.bound) {
    btnCreate.dataset.bound = 'true';
    btnCreate.addEventListener('click', () => openEditorModal(null));
  }

  // Кнопка синхронизации
  const btnSync = document.getElementById('inst-btn-sync');
  if (btnSync && !btnSync.dataset.bound) {
    btnSync.dataset.bound = 'true';
    btnSync.addEventListener('click', handleSyncInstruments);
  }

  // Кнопка экспорта CSV
  const btnExport = document.getElementById('inst-btn-export-csv');
  if (btnExport && !btnExport.dataset.bound) {
    btnExport.dataset.bound = 'true';
    btnExport.addEventListener('click', () => {
      window.location.href = '/api/v1/ai-instruments/export-csv';
    });
  }

  // Сохранение в редакторе
  const btnSaveEditor = document.getElementById('editor-inst-btn-save');
  if (btnSaveEditor && !btnSaveEditor.dataset.bound) {
    btnSaveEditor.dataset.bound = 'true';
    btnSaveEditor.addEventListener('click', handleSaveInstrument);
  }

  // Удаление в редакторе
  const btnDeleteEditor = document.getElementById('editor-inst-btn-delete');
  if (btnDeleteEditor && !btnDeleteEditor.dataset.bound) {
    btnDeleteEditor.dataset.bound = 'true';
    btnDeleteEditor.addEventListener('click', handleDeleteInstrument);
  }

  // Выполнение в окне раннера
  const btnExecute = document.getElementById('runner-btn-execute');
  if (btnExecute && !btnExecute.dataset.bound) {
    btnExecute.dataset.bound = 'true';
    btnExecute.addEventListener('click', handleExecuteInstrument);
  }

  // Проверка соединений на вкладке Хранилище
  const btnTestConn = document.getElementById('inst-btn-test-connections');
  if (btnTestConn && !btnTestConn.dataset.bound) {
    btnTestConn.dataset.bound = 'true';
    btnTestConn.addEventListener('click', handleTestConnections);
  }

  // Сохранение параметров рантайма
  const btnSaveRuntime = document.getElementById('inst-btn-save-runtime');
  if (btnSaveRuntime && !btnSaveRuntime.dataset.bound) {
    btnSaveRuntime.dataset.bound = 'true';
    btnSaveRuntime.addEventListener('click', handleSaveRuntimeConfig);
  }

  // Извлечение из ответа LLM
  const btnExtract = document.getElementById('inst-btn-do-extract');
  if (btnExtract && !btnExtract.dataset.bound) {
    btnExtract.dataset.bound = 'true';
    btnExtract.addEventListener('click', handleExtractFromReasoning);
  }
}

/**
 * Загрузка списка инструментов по фильтрам.
 */
async function loadInstrumentsList() {
  const tbody = document.getElementById('inst-table-body');
  const countBadge = document.getElementById('inst-badge-count');
  const q = document.getElementById('inst-search-input')?.value.trim() || '';
  const toolType = document.getElementById('inst-filter-type')?.value || '';
  const targetEntity = document.getElementById('inst-filter-entity')?.value || '';

  let url = `/api/v1/ai-instruments/list?limit=200`;
  if (q) url += `&query=${encodeURIComponent(q)}`;
  if (toolType) url += `&tool_type=${encodeURIComponent(toolType)}`;
  if (targetEntity) url += `&target_entity=${encodeURIComponent(targetEntity)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Ошибка HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];

    instrumentsCache.clear();
    items.forEach(it => instrumentsCache.set(it.tool_id, it));

    if (countBadge) {
      countBadge.textContent = String(data.total || items.length);
    }

    renderTableRows(items);
  } catch (err) {
    console.error('[AI Instruments] Ошибка загрузки каталога:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle me-1"></i>
            Не удалось загрузить список инструментов: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
  }
}

/**
 * Отрисовка строк таблицы инструментов.
 * @param {Array<object>} items 
 */
function renderTableRows(items) {
  const tbody = document.getElementById('inst-table-body');
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-4 text-secondary">
          <i class="bi bi-inbox fs-4 d-block mb-1"></i>
          Инструменты не найдены
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = items.map(it => {
    const riskBadgeClass = it.risk_level === 'high' ? 'bg-danger-subtle text-danger' :
      it.risk_level === 'medium' ? 'bg-warning-subtle text-warning' : 'bg-success-subtle text-success';

    const tagsHtml = (it.tags || []).map(t => `<span class="inst-tag-pill">${escapeHtml(t)}</span>`).join(' ');

    return `
      <tr data-tool-id="${escapeHtml(it.tool_id)}">
        <td>
          <div class="fw-bold text-body text-break">${escapeHtml(it.name || it.tool_id)}</div>
          <small class="text-secondary font-monospace">${escapeHtml(it.tool_id)}</small>
        </td>
        <td>
          <span class="badge bg-body-tertiary border text-body me-1">${escapeHtml(it.tool_type || 'python')}</span>
          <span class="badge ${riskBadgeClass}">${escapeHtml(it.risk_level || 'safe')}</span>
        </td>
        <td>
          <div class="small fw-semibold text-secondary mb-1">${escapeHtml(it.target_entity || 'system')}</div>
          <div class="d-flex flex-wrap gap-1">${tagsHtml}</div>
        </td>
        <td>
          <span class="badge bg-secondary-subtle text-secondary font-monospace">${it.execution_count || 0}</span>
        </td>
        <td style="text-align: right;">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-primary btn-inst-run" data-id="${escapeHtml(it.tool_id)}" title="Запустить инструмент">
              <i class="bi bi-play-fill"></i>
            </button>
            <button type="button" class="btn btn-outline-secondary btn-inst-edit" data-id="${escapeHtml(it.tool_id)}" title="Редактировать">
              <i class="bi bi-pencil"></i>
            </button>
            <button type="button" class="btn btn-outline-danger btn-inst-delete" data-id="${escapeHtml(it.tool_id)}" title="Удалить">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Привязка кликов к кнопкам строк
  tbody.querySelectorAll('.btn-inst-run').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = btn.getAttribute('data-id');
      const item = instrumentsCache.get(id);
      if (item) openRunnerModal(item);
    });
  });

  tbody.querySelectorAll('.btn-inst-edit').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = btn.getAttribute('data-id');
      const item = instrumentsCache.get(id);
      if (item) openEditorModal(item);
    });
  });

  tbody.querySelectorAll('.btn-inst-delete').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.getAttribute('data-id');
      if (confirm(`Удалить инструмент "${id}"?`)) {
        await deleteInstrument(id);
      }
    });
  });
}

/**
 * Открытие модального окна редактирования / создания.
 * @param {object|null} item 
 */
function openEditorModal(item) {
  const modalEl = document.getElementById('modal-inst-editor');
  if (!modalEl) return;

  const titleEl = document.getElementById('modal-inst-editor-title');
  const idInput = document.getElementById('editor-inst-id');
  const nameInput = document.getElementById('editor-inst-name');
  const typeSelect = document.getElementById('editor-inst-type');
  const targetInput = document.getElementById('editor-inst-target');
  const riskSelect = document.getElementById('editor-inst-risk');
  const tagsInput = document.getElementById('editor-inst-tags');
  const descInput = document.getElementById('editor-inst-desc');
  const paramsArea = document.getElementById('editor-inst-params');
  const codeArea = document.getElementById('editor-inst-code');
  const deleteBtn = document.getElementById('editor-inst-btn-delete');

  if (item) {
    if (titleEl) titleEl.innerHTML = `<i class="bi bi-pencil-square text-primary"></i> Редактирование: ${escapeHtml(item.tool_id)}`;
    if (idInput) { idInput.value = item.tool_id; idInput.readOnly = true; }
    if (nameInput) nameInput.value = item.name || '';
    if (typeSelect) typeSelect.value = item.tool_type || 'python';
    if (targetInput) targetInput.value = item.target_entity || 'system';
    if (riskSelect) riskSelect.value = item.risk_level || 'safe';
    if (tagsInput) tagsInput.value = (item.tags || []).join(', ');
    if (descInput) descInput.value = item.description || '';
    if (paramsArea) paramsArea.value = JSON.stringify(item.parameters_schema || {}, null, 2);
    if (codeArea) codeArea.value = item.command || '';
    if (deleteBtn) deleteBtn.style.display = 'block';
  } else {
    if (titleEl) titleEl.innerHTML = `<i class="bi bi-plus-circle text-primary"></i> Создание нового инструмента CoT`;
    if (idInput) { idInput.value = ''; idInput.readOnly = false; }
    if (nameInput) nameInput.value = '';
    if (typeSelect) typeSelect.value = 'python';
    if (targetInput) targetInput.value = 'system';
    if (riskSelect) riskSelect.value = 'safe';
    if (tagsInput) tagsInput.value = '#agent_tool';
    if (descInput) descInput.value = '';
    if (paramsArea) paramsArea.value = '{\n  "type": "object",\n  "properties": {}\n}';
    if (codeArea) codeArea.value = '# python code\n';
    if (deleteBtn) deleteBtn.style.display = 'none';
  }

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

/**
 * Сохранение инструмента из формы модального окна.
 */
async function handleSaveInstrument() {
  const id = document.getElementById('editor-inst-id')?.value.trim();
  const name = document.getElementById('editor-inst-name')?.value.trim();
  const toolType = document.getElementById('editor-inst-type')?.value;
  const targetEntity = document.getElementById('editor-inst-target')?.value.trim() || 'system';
  const riskLevel = document.getElementById('editor-inst-risk')?.value || 'safe';
  const tagsRaw = document.getElementById('editor-inst-tags')?.value || '';
  const desc = document.getElementById('editor-inst-desc')?.value.trim() || '';
  const paramsRaw = document.getElementById('editor-inst-params')?.value || '{}';
  const command = document.getElementById('editor-inst-code')?.value || '';

  if (!id || !name || !command) {
    alert('Поля Tool ID, Название и Код обязательны для заполнения!');
    return;
  }

  let parametersSchema = {};
  try {
    parametersSchema = JSON.parse(paramsRaw);
  } catch (err) {
    alert('Ошибка в JSON схемы параметров: ' + err.message);
    return;
  }

  const tags = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);

  const payload = {
    tool_id: id,
    name,
    tool_type: toolType,
    command,
    description: desc,
    target_entity: targetEntity,
    parameters_schema: parametersSchema,
    risk_level: riskLevel,
    author_agent: 'cot_planner',
    tags,
  };

  try {
    const res = await fetch('/api/v1/ai-instruments/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Ошибка HTTP ${res.status}`);
    
    const modalEl = document.getElementById('modal-inst-editor');
    if (modalEl) {
      bootstrap.Modal.getInstance(modalEl)?.hide();
    }
    await loadInstrumentsList();
    showToast(`Инструмент ${id} сохранен и синхронизирован`);
  } catch (err) {
    alert('Не удалось сохранить инструмент: ' + err.message);
  }
}

/**
 * Удаление инструмента.
 * @param {string} toolId 
 */
async function deleteInstrument(toolId) {
  try {
    const res = await fetch(`/api/v1/ai-instruments/item/${encodeURIComponent(toolId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`Ошибка HTTP ${res.status}`);
    await loadInstrumentsList();
    showToast(`Инструмент ${toolId} удален`);
  } catch (err) {
    alert('Ошибка удаления: ' + err.message);
  }
}

/**
 * Открытие модального окна запуска инструмента.
 * @param {object} item 
 */
function openRunnerModal(item) {
  currentRunningTool = item;
  const modalEl = document.getElementById('modal-inst-runner');
  if (!modalEl) return;

  const titleEl = document.getElementById('modal-inst-runner-title');
  const descEl = document.getElementById('runner-inst-desc');
  const paramsContainer = document.getElementById('runner-params-fields');
  const outputBox = document.getElementById('runner-output-box');
  const latencyBadge = document.getElementById('runner-latency-badge');

  if (titleEl) {
    titleEl.innerHTML = `<i class="bi bi-play-circle text-primary"></i> Запуск: <code>${escapeHtml(item.tool_id)}</code> (${escapeHtml(item.name)})`;
  }
  if (descEl) {
    descEl.textContent = item.description || 'Описание отсутствует';
  }
  if (outputBox) {
    outputBox.textContent = 'Нажмите «Выполнить инструмент» для запуска...';
  }
  if (latencyBadge) {
    latencyBadge.textContent = '';
  }

  // Генерация динамических полей параметров
  if (paramsContainer) {
    const schema = item.parameters_schema || {};
    const props = schema.properties || {};
    const keys = Object.keys(props);

    if (!keys.length) {
      paramsContainer.innerHTML = '<div class="col-12 text-secondary small fst-italic">Инструмент не требует параметров</div>';
    } else {
      paramsContainer.innerHTML = keys.map(k => {
        const p = props[k] || {};
        const def = p.default !== undefined ? String(p.default) : '';
        const desc = p.description || '';
        return `
          <div class="col-md-6">
            <label class="form-label small fw-semibold font-monospace mb-1">${escapeHtml(k)}:</label>
            <input type="text" class="form-control form-control-sm runner-param-input" data-param-name="${escapeHtml(k)}" value="${escapeHtml(def)}" placeholder="${escapeHtml(desc)}">
            ${desc ? `<small class="text-secondary d-block mt-0.5">${escapeHtml(desc)}</small>` : ''}
          </div>
        `;
      }).join('');
    }
  }

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

/**
 * Выполнение инструмента через POST /api/v1/ai-instruments/execute.
 */
async function handleExecuteInstrument() {
  if (!currentRunningTool) return;

  const btn = document.getElementById('runner-btn-execute');
  const outputBox = document.getElementById('runner-output-box');
  const latencyBadge = document.getElementById('runner-latency-badge');
  const asAdmin = document.getElementById('runner-inst-as-admin')?.checked || false;

  // Сбор параметров
  const params = {};
  document.querySelectorAll('.runner-param-input').forEach(inp => {
    const k = inp.getAttribute('data-param-name');
    if (k) params[k] = inp.value;
  });

  if (btn) btn.disabled = true;
  if (outputBox) outputBox.textContent = 'Выполнение скрипта... Пожалуйста, подождите.';

  const t0 = performance.now();

  try {
    const res = await fetch('/api/v1/ai-instruments/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool_id: currentRunningTool.tool_id,
        parameters: params,
        as_admin: asAdmin,
        timeout_sec: 25,
      }),
    });

    const lat = Math.round(performance.now() - t0);
    if (latencyBadge) latencyBadge.textContent = `${lat} мс`;

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    let out = '';
    if (data.stdout) out += data.stdout;
    if (data.stderr) out += (out ? '\n[STDERR]\n' : '') + data.stderr;
    if (!out) out = `[Завершено с кодом ${data.exit_code}]`;

    if (outputBox) outputBox.textContent = out;
  } catch (err) {
    if (outputBox) outputBox.textContent = `Ошибка выполнения: ${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Принудительная синхронизация инструментов с Markdown.
 */
async function handleSyncInstruments() {
  const btn = document.getElementById('inst-btn-sync');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/v1/ai-instruments/sync', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(`Синхронизировано ${data.synced_count} инструментов в ${data.markdown_file}`);
    await loadInstrumentsList();
    await loadStorageStatus();
  } catch (err) {
    alert('Ошибка синхронизации: ' + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Загрузка статуса хранилища.
 */
async function loadStorageStatus() {
  try {
    const res = await fetch('/api/v1/ai-instruments/status');
    if (!res.ok) return;
    const data = await res.json();

    const mdCount = document.getElementById('inst-storage-md-count');
    if (mdCount) mdCount.textContent = String(data.tools_count || 0);

    const activeEngine = document.getElementById('inst-storage-active-engine');
    if (activeEngine) activeEngine.textContent = data.active_engine || 'SQLite';

    const cloudBadge = document.getElementById('inst-storage-cloud-badge');
    if (cloudBadge && data.is_remote) {
      cloudBadge.textContent = 'Connected';
      cloudBadge.className = 'badge bg-success-subtle text-success';
    }
  } catch (err) {
    console.debug('[AI Instruments] Статус хранилища:', err);
  }
}

/**
 * Проверка соединений на вкладке Хранилище.
 */
async function handleTestConnections() {
  const resultBox = document.getElementById('inst-storage-test-result');
  const btn = document.getElementById('inst-btn-test-connections');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/v1/ai-instruments/test-connection', { method: 'POST' });
    const data = await res.json();

    if (resultBox) {
      resultBox.style.display = 'block';
      resultBox.innerHTML = `
        <h6 class="fw-bold mb-2">Результаты тестирования соединений:</h6>
        <div class="row g-2 font-monospace small">
          <div class="col-md-4">
            <div class="p-2 rounded bg-body border">
              <strong>Markdown:</strong> ${data.markdown_ok ? '<span class="text-success">OK</span>' : '<span class="text-danger">FAIL</span>'}
            </div>
          </div>
          <div class="col-md-4">
            <div class="p-2 rounded bg-body border">
              <strong>SQLite:</strong> ${data.sqlite_ok ? '<span class="text-success">OK</span>' : '<span class="text-danger">FAIL</span>'}
            </div>
          </div>
          <div class="col-md-4">
            <div class="p-2 rounded bg-body border">
              <strong>Hostinger:</strong> ${data.remote_ok ? '<span class="text-success">OK</span>' : '<span class="text-secondary">Disabled</span>'}
            </div>
          </div>
        </div>
      `;
    }
  } catch (err) {
    alert('Ошибка тестирования соединений: ' + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Сохранение параметров рантайма.
 */
async function handleSaveRuntimeConfig() {
  const timeout = parseInt(document.getElementById('inst-runtime-timeout')?.value || '20', 10);
  const prefix = document.getElementById('inst-runtime-prefix')?.value || 'Инструмент рассуждения';
  const safeops = document.getElementById('inst-runtime-safeops')?.checked ?? true;
  const autoextract = document.getElementById('inst-runtime-autoextract')?.checked ?? true;

  try {
    const res = await fetch('/api/v1/ai-instruments/runtime/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        execution_timeout: timeout,
        title_prefix: prefix,
        safe_ops_enabled: safeops,
        auto_extract_from_reasoning: autoextract,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Параметры рантайма успешно сохранены');
  } catch (err) {
    alert('Ошибка сохранения рантайма: ' + err.message);
  }
}

/**
 * Извлечение инструментов из цепочки рассуждений.
 */
async function handleExtractFromReasoning() {
  const text = document.getElementById('inst-extract-textarea')?.value.trim();
  const statusEl = document.getElementById('inst-extract-status');
  if (!text) {
    alert('Вставьте текст с блоками кода для извлечения инструментов');
    return;
  }

  if (statusEl) statusEl.textContent = 'Извлечение инструментов...';

  try {
    const res = await fetch('/api/v1/ai-instruments/extract-from-reasoning', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const count = data.extracted_count || 0;
    if (statusEl) statusEl.textContent = `Успешно извлечено и сохранено: ${count} инструментов`;
    await loadInstrumentsList();
    showToast(`Извлечено ${count} инструментов`);
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Ошибка извлечения: ' + err.message;
  }
}

/**
 * Вспомогательное уведомление toast.
 * @param {string} msg 
 */
function showToast(msg) {
  if (window.showToast) {
    window.showToast(msg, 'success');
  } else {
    console.log('[AI Instruments Toast]', msg);
  }
}

/**
 * Экранирование HTML.
 * @param {string} str 
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Экспорт для глобального вызова
window.initInstrumentsTab = initInstrumentsTab;
