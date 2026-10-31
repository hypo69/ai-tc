/**
 * =============================================================================
 * Process Name: Windows App Internals - AI Instruments Catalog & Execution
 * =============================================================================
 * Description:
 *   Модуль каталога инструментов агента: просмотр, полнотекстовый поиск,
 *   фильтрация по типам и сущностям, интерактивное модальное окно редактора
 *   по клику на строку (onclick), тестовое выполнение PowerShell/CMD/SDK команд
 *   и удаление устаревших инструментов из базы на сервере Hostinger и SQLite.
 *
 * File: catalog.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_instruments_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 18:12:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v3';

let catalogSearchTimer = null;
let catalogItemsCache = new Map();
let activeModalInstance = null;

/**
 * Загрузка каталога инструментов с сервера.
 * @param {string} [query=''] - Поисковая строка
 * @param {string} [toolType=''] - Фильтр по типу: powershell, cmd, utility
 * @param {string} [targetEntity=''] - Фильтр по сущности: process, service, network, storage, system
 * @returns {Promise<void>}
 */
export async function loadInstrumentsCatalog(query = '', toolType = '', targetEntity = '') {
  const container = document.getElementById('inst-catalog-list-container');
  const counter = document.getElementById('inst-catalog-counter');
  if (!container) return;

  const q = query.trim();
  let url = '/api/v1/ai-instruments/list?limit=200';
  if (toolType) url += `&tool_type=${encodeURIComponent(toolType)}`;
  if (targetEntity) url += `&target_entity=${encodeURIComponent(targetEntity)}`;
  if (q) {
    url = `/api/v1/ai-instruments/search?q=${encodeURIComponent(q)}&limit=100`;
  }

  try {
    const res = await fetch(url);
    if (!res.ok) {
      container.innerHTML = `
        <div class="alert alert-warning py-2 px-3 small">
          <i class="bi bi-exclamation-triangle me-1"></i>
          Не удалось загрузить каталог инструментов (${res.status}).
        </div>
      `;
      return;
    }
    const data = await res.json();
    const items = data.items || [];
    if (counter) {
      counter.textContent = `${items.length} инструментов`;
    }
    renderInstrumentsCatalog(items);
  } catch (err) {
    console.error('[AI Instruments Catalog] Ошибка загрузки списка:', err);
    container.innerHTML = `
      <div class="alert alert-danger py-2 px-3 small">
        <i class="bi bi-x-circle me-1"></i>
        Ошибка соединения: ${err.message}
      </div>
    `;
  }
}

/**
 * Отрисовка таблицы инструментов агента с открытием модального редактора по onclick строки.
 * @param {Array<object>} items - Список инструментов
 */
export function renderInstrumentsCatalog(items) {
  const container = document.getElementById('inst-catalog-list-container');
  if (!container) return;

  catalogItemsCache.clear();
  items.forEach((it) => {
    const id = it.tool_id || it.id || '';
    if (id) catalogItemsCache.set(id, it);
  });

  if (!items.length) {
    container.innerHTML = `
      <div class="text-center py-4 text-muted">
        <i class="bi bi-inbox fs-3 d-block mb-2"></i>
        <span>Инструменты не найдены. Создайте первый инструмент или проверьте фильтры.</span>
      </div>
    `;
    return;
  }

  const rows = items.map((item) => {
    const toolId = item.tool_id || item.id || '';
    const name = item.name || 'Без названия';
    const type = item.tool_type || 'powershell';
    const entity = item.target_entity || 'system';
    const command = item.command || '';
    const execCount = item.execution_count ?? 0;
    const createdAt = item.created_at ? item.created_at.replace('T', ' ').slice(0, 19) : '—';

    let badgeClass = 'ui-badge ui-badge-info';
    if (type === 'cmd') badgeClass = 'ui-badge ui-badge-neutral';
    if (type === 'utility') badgeClass = 'ui-badge ui-badge-success';

    return `
      <tr class="inst-catalog-row" data-tool-id="${escapeHtml(toolId)}" style="cursor: pointer;" title="Нажмите для редактирования инструмента" onclick="window.openInstrumentEditorModal('${escapeHtml(toolId)}')">
        <td class="align-middle">
          <div class="fw-semibold text-break"><i class="bi bi-pencil-square text-primary me-1 small"></i>${escapeHtml(name)}</div>
          <small class="text-secondary font-monospace">${escapeHtml(toolId)}</small>
        </td>
        <td class="align-middle">
          <span class="${badgeClass}">${escapeHtml(type.toUpperCase())}</span>
          <div class="small text-muted mt-0.5">${escapeHtml(entity)}</div>
        </td>
        <td class="align-middle" style="max-width: 320px;">
          <div class="p-1 rounded font-monospace small text-truncate" style="background: var(--surface-2); border: 1px solid var(--border-color);" title="${escapeHtml(command)}">
            <code>${escapeHtml(command)}</code>
          </div>
        </td>
        <td class="align-middle text-center small text-secondary">
          <div><i class="bi bi-play-circle me-1"></i>${execCount}</div>
          <small class="text-muted">${createdAt}</small>
        </td>
        <td class="align-middle text-end" onclick="event.stopPropagation();">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-primary btn-inst-test" data-tool-id="${escapeHtml(toolId)}" title="Тестовый запуск инструмента">
              <i class="bi bi-play-fill me-0.5"></i>Тест
            </button>
            <button type="button" class="btn btn-outline-danger btn-inst-del" data-tool-id="${escapeHtml(toolId)}" title="Удалить инструмент">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <table class="table table-sm table-hover align-middle mb-0">
      <thead>
        <tr class="text-secondary small">
          <th>Инструмент / ID</th>
          <th>Тип / Сущность</th>
          <th>Команда / Скрипт</th>
          <th class="text-center">Запуски</th>
          <th class="text-end">Действия</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;

  // Подключение кнопок запуска и удаления
  container.querySelectorAll('.btn-inst-test').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const toolId = btn.getAttribute('data-tool-id');
      if (toolId) executeInstrumentTest(toolId);
    });
  });

  container.querySelectorAll('.btn-inst-del').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const toolId = btn.getAttribute('data-tool-id');
      if (toolId && confirm(`Удалить инструмент '${toolId}' из базы?`)) {
        deleteInstrument(toolId);
      }
    });
  });
}

/**
 * Открытие модального окна редактора инструмента (для редактирования или создания нового).
 * @param {string|null} [toolId=null] - ID инструмента или null для создания нового
 */
export async function openInstrumentEditorModal(toolId = null) {
  const modalEl = document.getElementById('inst-editor-modal');
  if (!modalEl) return;

  bindInstrumentEditorModalButtons();

  const titleEl = document.getElementById('inst-editor-modal-title');
  const idInp = document.getElementById('inst-edit-tool-id');
  const nameInp = document.getElementById('inst-edit-name');
  const typeSel = document.getElementById('inst-edit-type');
  const entitySel = document.getElementById('inst-edit-entity');
  const cmdInp = document.getElementById('inst-edit-command');
  const descInp = document.getElementById('inst-edit-description');
  const riskSel = document.getElementById('inst-edit-risk');
  const authorInp = document.getElementById('inst-edit-author');
  const tagsInp = document.getElementById('inst-edit-tags');
  const metaExec = document.getElementById('inst-edit-meta-exec');
  const metaUpdated = document.getElementById('inst-edit-meta-updated');
  const delBtn = document.getElementById('inst-editor-btn-delete');
  const testBtn = document.getElementById('inst-editor-btn-test');
  const execOut = document.getElementById('inst-editor-exec-output');

  if (execOut) {
    execOut.style.display = 'none';
    execOut.innerHTML = '';
  }

  let item = toolId ? catalogItemsCache.get(toolId) : null;
  if (toolId && !item) {
    try {
      const res = await fetch(`/api/v1/ai-instruments/${encodeURIComponent(toolId)}`);
      if (res.ok) {
        const data = await res.json();
        item = data.item || null;
        if (item) catalogItemsCache.set(toolId, item);
      }
    } catch (e) {
      console.warn('[AI Instruments Editor] Не удалось загрузить инструмент по ID:', e);
    }
  }

  if (item) {
    if (titleEl) {
      titleEl.innerHTML = `<i class="bi bi-pencil-square text-primary me-2"></i>Редактирование инструмента: <code class="ms-1">${escapeHtml(item.tool_id)}</code>`;
    }
    if (idInp) {
      idInp.value = item.tool_id || '';
      idInp.readOnly = true;
    }
    if (nameInp) nameInp.value = item.name || '';
    if (typeSel) typeSel.value = (item.tool_type || 'powershell').toLowerCase();
    if (entitySel) {
      const ent = (item.target_entity || 'system').toLowerCase();
      if (![...entitySel.options].some((o) => o.value === ent)) {
        const opt = document.createElement('option');
        opt.value = ent;
        opt.textContent = ent;
        entitySel.appendChild(opt);
      }
      entitySel.value = ent;
    }
    if (cmdInp) cmdInp.value = item.command || '';
    if (descInp) descInp.value = item.description || '';
    if (riskSel) riskSel.value = (item.risk_level || 'safe').toLowerCase();
    if (authorInp) authorInp.value = item.author_agent || 'reasoning_chain';
    if (tagsInp) {
      const tagsArr = Array.isArray(item.tags) ? item.tags : ['#agent_tool'];
      tagsInp.value = tagsArr.join(', ');
    }
    if (metaExec) metaExec.textContent = `Запусков: ${item.execution_count ?? 0}`;
    if (metaUpdated) {
      const upd = item.updated_at ? item.updated_at.replace('T', ' ').slice(0, 19) : '—';
      metaUpdated.textContent = `Обновлено: ${upd}`;
    }
    if (delBtn) delBtn.style.display = '';
    if (testBtn) testBtn.style.display = '';
  } else {
    if (titleEl) {
      titleEl.innerHTML = `<i class="bi bi-plus-circle text-primary me-2"></i>Создание нового инструмента ИИ-агента`;
    }
    if (idInp) {
      idInp.value = `inst_custom_${Math.random().toString(36).slice(2, 8)}`;
      idInp.readOnly = false;
    }
    if (nameInp) nameInp.value = '';
    if (typeSel) typeSel.value = 'powershell';
    if (entitySel) entitySel.value = 'system';
    if (cmdInp) cmdInp.value = '';
    if (descInp) descInp.value = '';
    if (riskSel) riskSel.value = 'safe';
    if (authorInp) authorInp.value = 'admin_editor';
    if (tagsInp) tagsInp.value = '#agent_tool, #powershell';
    if (metaExec) metaExec.textContent = 'Новый инструмент';
    if (metaUpdated) metaUpdated.textContent = '';
    if (delBtn) delBtn.style.display = 'none';
    if (testBtn) testBtn.style.display = '';
  }

  if (window.bootstrap && window.bootstrap.Modal) {
    activeModalInstance = window.bootstrap.Modal.getOrCreateInstance
      ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
      : new window.bootstrap.Modal(modalEl);
    activeModalInstance.show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}

/**
 * Сохранение отредактированного или нового инструмента из модального окна на сервер.
 * @returns {Promise<boolean>}
 */
export async function saveInstrumentFromModal() {
  const toolId = document.getElementById('inst-edit-tool-id')?.value.trim() || '';
  const name = document.getElementById('inst-edit-name')?.value.trim() || '';
  const toolType = document.getElementById('inst-edit-type')?.value || 'powershell';
  const targetEntity = document.getElementById('inst-edit-entity')?.value || 'system';
  const command = document.getElementById('inst-edit-command')?.value.trim() || '';
  const description = document.getElementById('inst-edit-description')?.value.trim() || '';
  const riskLevel = document.getElementById('inst-edit-risk')?.value || 'safe';
  const authorAgent = document.getElementById('inst-edit-author')?.value.trim() || 'admin_editor';
  const tagsRaw = document.getElementById('inst-edit-tags')?.value || '';

  if (!name || !command) {
    notifyUser('Укажите название инструмента и исполняемую команду', 'warning');
    return false;
  }

  const tags = tagsRaw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => (t.startsWith('#') ? t : `#${t}`));

  const payload = {
    tool_id: toolId || undefined,
    name,
    tool_type: toolType,
    command,
    description,
    target_entity: targetEntity,
    risk_level: riskLevel,
    author_agent: authorAgent,
    tags: tags.length ? tags : ['#agent_tool'],
  };

  const saveBtn = document.getElementById('inst-editor-btn-save');
  if (saveBtn) saveBtn.disabled = true;

  try {
    const res = await fetch('/api/v1/ai-instruments/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      notifyUser(`Инструмент '${name}' (${data.tool_id}) успешно сохранен`, 'success');
      if (data.item) {
        catalogItemsCache.set(data.tool_id, data.item);
      }
      await triggerFilteredCatalogLoad();
      return true;
    }
    notifyUser(data.detail || 'Не удалось сохранить инструмент', 'warning');
    return false;
  } catch (err) {
    notifyUser(`Ошибка сохранения: ${err.message}`, 'danger');
    return false;
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * Привязка обработчиков кнопок внутри модального окна редактора инструмента.
 */
function bindInstrumentEditorModalButtons() {
  const saveBtn = document.getElementById('inst-editor-btn-save');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', async () => {
      const ok = await saveInstrumentFromModal();
      if (ok && activeModalInstance) {
        activeModalInstance.hide();
      }
    });
  }

  const testBtn = document.getElementById('inst-editor-btn-test');
  if (testBtn && !testBtn._bound) {
    testBtn._bound = true;
    testBtn.addEventListener('click', async () => {
      const ok = await saveInstrumentFromModal();
      if (!ok) return;
      const toolId = document.getElementById('inst-edit-tool-id')?.value.trim();
      if (toolId) {
        await executeInstrumentTest(toolId, 'inst-editor-exec-output');
      }
    });
  }

  const delBtn = document.getElementById('inst-editor-btn-delete');
  if (delBtn && !delBtn._bound) {
    delBtn._bound = true;
    delBtn.addEventListener('click', async () => {
      const toolId = document.getElementById('inst-edit-tool-id')?.value.trim();
      if (!toolId) return;
      if (confirm(`Удалить инструмент '${toolId}' из базы?`)) {
        await deleteInstrument(toolId);
        if (activeModalInstance) activeModalInstance.hide();
      }
    });
  }
}

/**
 * Тестовое выполнение инструмента агента с выводом результата.
 * @param {string} toolId - ID инструмента
 * @param {string} [outputElementId='inst-catalog-exec-output'] - ID контейнера для вывода
 */
export async function executeInstrumentTest(toolId, outputElementId = 'inst-catalog-exec-output') {
  const outputBox = document.getElementById(outputElementId);
  if (outputBox) {
    outputBox.style.display = 'block';
    outputBox.innerHTML = `
      <div class="alert alert-secondary py-2 px-3 mb-0 small">
        <span class="spinner-border spinner-border-sm text-primary me-2"></span>
        Выполнение инструмента <strong>${escapeHtml(toolId)}</strong>...
      </div>
    `;
  }

  try {
    const res = await fetch('/api/v1/ai-instruments/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool_id: toolId,
        timeout_sec: 20,
        as_admin: true,
      }),
    });
    const data = await res.json();
    if (!outputBox) return;

    const isSuccess = data.success ?? (data.exit_code === 0);
    const alertClass = isSuccess ? 'alert-success' : 'alert-danger';
    const statusText = isSuccess ? 'Успешно выполнено' : `Ошибка выполнения (Exit: ${data.exit_code ?? -1})`;
    const stdout = data.stdout || '(нет стандартного вывода)';
    const stderr = data.stderr ? `<div class="mt-1 text-danger font-monospace small">Ошибки: ${escapeHtml(data.stderr)}</div>` : '';

    outputBox.innerHTML = `
      <div class="alert ${alertClass} py-2 px-3 mb-0">
        <div class="d-flex justify-content-between align-items-center mb-1">
          <strong class="small"><i class="bi bi-terminal me-1"></i>${statusText} [${escapeHtml(toolId)}]</strong>
          <button type="button" class="btn-close btn-sm" onclick="this.closest('#${escapeHtml(outputElementId)}').style.display='none';"></button>
        </div>
        <pre class="mb-0 p-2 rounded small font-monospace" style="background: var(--surface-2); border: 1px solid var(--border-color); max-height: 220px; overflow-y: auto;">${escapeHtml(stdout)}</pre>
        ${stderr}
      </div>
    `;
  } catch (err) {
    if (outputBox) {
      outputBox.innerHTML = `
        <div class="alert alert-danger py-2 px-3 mb-0 small">
          <strong>Ошибка запроса:</strong> ${err.message}
        </div>
      `;
    }
  }
}

/**
 * Удаление инструмента из базы данных.
 * @param {string} toolId - ID инструмента
 */
export async function deleteInstrument(toolId) {
  try {
    const res = await fetch(`/api/v1/ai-instruments/${encodeURIComponent(toolId)}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      catalogItemsCache.delete(toolId);
      notifyUser(`Инструмент '${toolId}' удален`, 'info');
      triggerFilteredCatalogLoad();
    } else {
      notifyUser(`Не удалось удалить инструмент '${toolId}'`, 'warning');
    }
  } catch (err) {
    notifyUser(`Ошибка сети: ${err.message}`, 'danger');
  }
}

/**
 * Запуск загрузки каталога с учетом текущих фильтров.
 */
export function triggerFilteredCatalogLoad() {
  const query = document.getElementById('inst-catalog-search')?.value || '';
  const typeFilter = document.getElementById('inst-catalog-filter-type')?.value || '';
  const entityFilter = document.getElementById('inst-catalog-filter-entity')?.value || '';
  loadInstrumentsCatalog(query, typeFilter, entityFilter);
}

/**
 * Подключение событий элементов каталога инструментов.
 */
export function bindInstrumentsCatalogButtons() {
  window.openInstrumentEditorModal = openInstrumentEditorModal;

  const createBtn = document.getElementById('inst-catalog-btn-create');
  if (createBtn && !createBtn._bound) {
    createBtn._bound = true;
    createBtn.addEventListener('click', () => openInstrumentEditorModal(null));
  }

  const refreshBtn = document.getElementById('inst-catalog-btn-refresh');
  if (refreshBtn && !refreshBtn._bound) {
    refreshBtn._bound = true;
    refreshBtn.addEventListener('click', triggerFilteredCatalogLoad);
  }

  const searchInp = document.getElementById('inst-catalog-search');
  if (searchInp && !searchInp._bound) {
    searchInp._bound = true;
    searchInp.addEventListener('input', () => {
      clearTimeout(catalogSearchTimer);
      catalogSearchTimer = setTimeout(triggerFilteredCatalogLoad, 300);
    });
  }

  const typeSelect = document.getElementById('inst-catalog-filter-type');
  if (typeSelect && !typeSelect._bound) {
    typeSelect._bound = true;
    typeSelect.addEventListener('change', triggerFilteredCatalogLoad);
  }

  const entitySelect = document.getElementById('inst-catalog-filter-entity');
  if (entitySelect && !entitySelect._bound) {
    entitySelect._bound = true;
    entitySelect.addEventListener('change', triggerFilteredCatalogLoad);
  }
}

/**
 * Экранирование HTML спецсимволов.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
