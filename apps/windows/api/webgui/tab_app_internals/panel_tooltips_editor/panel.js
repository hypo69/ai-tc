/**
 * =============================================================================
 * Process Name: Windows App Internals - Tooltips Editor Panel
 * =============================================================================
 * Description:
 *   Интерактивный визуальный редактор всплывающих подсказок (AI Smart Tooltips & i18n hints).
 *   Позволяет искать, просматривать, создавать, редактировать подсказки базы знаний
 *   с мгновенным живым предпросмотром (Live Preview) и сохранением в локали и кэш.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_tooltips_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 18:06:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v3';

let currentTooltips = [];
let activeKey = null;
let currentLang = 'ru';

/**
 * Рендерит базовый каркас панели редактора подсказок.
 * @param {HTMLElement} container - DOM-контейнер
 */
function renderLayout(container) {
  container.innerHTML = `
    <div class="card shadow-sm border-secondary-subtle mb-4">
      <div class="card-header d-flex justify-content-between align-items-center py-2 flex-wrap gap-2" style="background: var(--surface-2); border-bottom: 1px solid var(--border-color); color: var(--text-color);">
        <div class="d-flex align-items-center gap-2">
          <i class="bi bi-chat-square-quote text-primary fs-5"></i>
          <h6 class="m-0 fw-bold">Редактор всплывающих подсказок (AI Smart Tooltips)</h6>
          <span class="ui-badge ui-badge-info" id="tooltips-counter">0 подсказок</span>
        </div>
        <div class="d-flex align-items-center gap-2">
          <div class="input-group input-group-sm" style="width: 140px;">
            <span class="input-group-text"><i class="bi bi-translate"></i></span>
            <select class="form-select form-select-sm" id="tooltips-lang-select">
              <option value="ru" selected>Русский (ru)</option>
              <option value="en">English (en)</option>
              <option value="uk">Українська (uk)</option>
              <option value="he">עברית (he)</option>
            </select>
          </div>
          <button type="button" class="btn btn-sm btn-primary d-flex align-items-center gap-1" id="tooltips-btn-create">
            <i class="bi bi-plus-lg"></i>
            <span>Новая подсказка</span>
          </button>
          <button type="button" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1" id="tooltips-btn-refresh">
            <i class="bi bi-arrow-clockwise"></i>
            <span>Обновить</span>
          </button>
        </div>
      </div>
      <div class="card-body p-3">
        <div class="row g-3">
          <!-- Левая колонка: Поиск, фильтры и список -->
          <div class="col-lg-4 col-md-5 border-end" style="border-color: var(--border-color) !important;">
            <div class="mb-2">
              <input type="text" id="tooltips-search-input" class="form-control form-control-sm" placeholder="Поиск по ключу, заголовку или тексту..."/>
            </div>
            <div class="mb-2">
              <select id="tooltips-filter-category" class="form-select form-select-sm">
                <option value="">Все категории</option>
                <option value="Логирование">Логирование</option>
                <option value="Справка">Справка</option>
                <option value="База знаний">База знаний</option>
                <option value="Рабочая область">Рабочая область</option>
                <option value="Безопасность">Безопасность</option>
                <option value="Форензика">Форензика</option>
                <option value="Обучение">Обучение</option>
                <option value="Процессы">Процессы</option>
              </select>
            </div>
            <div id="tooltips-items-list" class="list-group list-group-flush overflow-auto" style="max-height: 520px;">
              <div class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка подсказок...</div>
            </div>
          </div>

          <!-- Правая колонка: Форма редактирования и Live Preview -->
          <div class="col-lg-8 col-md-7">
            <form id="tooltips-editor-form" onsubmit="return false;">
              <div class="d-flex justify-content-between align-items-center mb-2 pb-1 border-bottom" style="border-color: var(--border-color) !important;">
                <h6 class="fw-bold mb-0" id="tooltips-form-title">Редактирование подсказки</h6>
                <div class="d-flex align-items-center gap-2">
                  <button type="button" class="btn btn-outline-danger btn-sm" id="tooltips-btn-delete" style="display:none;">
                    <i class="bi bi-trash me-1"></i>Удалить
                  </button>
                  <button type="button" class="btn btn-primary btn-sm fw-bold" id="tooltips-btn-save">
                    <i class="bi bi-check-circle me-1"></i>Сохранить подсказку
                  </button>
                </div>
              </div>

              <div class="row g-2 mb-2">
                <div class="col-md-6">
                  <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-key">Ключевой идентификатор (key)</label>
                  <input type="text" id="tooltip-edit-key" class="form-control form-control-sm font-monospace" placeholder="internals-logs" required/>
                  <div class="form-text small text-secondary">Уникальный ключ для data-term, id или data-i18n-title</div>
                </div>
                <div class="col-md-3">
                  <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-icon">Иконка / Эмодзи</label>
                  <input type="text" id="tooltip-edit-icon" class="form-control form-control-sm" placeholder="📜" value="💡" required/>
                </div>
                <div class="col-md-3">
                  <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-category">Категория</label>
                  <input type="text" id="tooltip-edit-category" class="form-control form-control-sm" placeholder="Логирование" required/>
                </div>
              </div>

              <div class="row g-2 mb-2">
                <div class="col-md-6">
                  <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-title">Краткий заголовок (title)</label>
                  <input type="text" id="tooltip-edit-title" class="form-control form-control-sm" placeholder="Центр логов" required/>
                </div>
                <div class="col-md-6">
                  <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-fulltitle">Развернутый заголовок (fullTitle)</label>
                  <input type="text" id="tooltip-edit-fulltitle" class="form-control form-control-sm" placeholder="Центр внутренних логов ai-tc"/>
                </div>
              </div>

              <div class="mb-3">
                <label class="form-label form-label-sm fw-semibold mb-1" for="tooltip-edit-summary">Текст подсказки (summary)</label>
                <textarea id="tooltip-edit-summary" class="form-control form-control-sm" rows="4" placeholder="Просмотр внутренних логов программы ai-tc" required></textarea>
              </div>

              <!-- Интерактивный Live Preview карточки подсказки -->
              <div class="mb-2">
                <label class="form-label form-label-sm fw-semibold mb-1 text-secondary"><i class="bi bi-eye me-1"></i>Живой предпросмотр карточки (Live Preview)</label>
                <div class="p-3 rounded border" style="background: var(--surface-1); border-color: var(--border-color) !important; max-width: 480px;">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <div class="d-flex align-items-center gap-1.5 fw-bold" style="color: var(--text-color);">
                      <span id="preview-tooltip-icon" style="font-size: 1.15rem;">📜</span>
                      <span id="preview-tooltip-title">Центр логов</span>
                    </div>
                    <span class="ui-badge ui-badge-info" id="preview-tooltip-badge">Логирование</span>
                  </div>
                  <div class="small" id="preview-tooltip-body" style="color: var(--text-color); opacity: 0.9; line-height: 1.45;">
                    Просмотр внутренних логов программы ai-tc
                  </div>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Загружает список подсказок с сервера для выбранного языка.
 */
export async function loadTooltipsList() {
  const listEl = document.getElementById('tooltips-items-list');
  const counterEl = document.getElementById('tooltips-counter');
  if (!listEl) return;

  try {
    const res = await fetch(`/api/v1/tooltips?lang=${encodeURIComponent(currentLang)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentTooltips = Array.isArray(data.items) ? data.items : [];
    if (counterEl) {
      counterEl.textContent = `${currentTooltips.length} подсказок`;
    }
    renderTooltipsList();
    if (activeKey) {
      selectTooltip(activeKey);
    } else if (currentTooltips.length > 0) {
      // По умолчанию выбираем первую или internals-logs
      const defaultItem = currentTooltips.find(i => i.key === 'internals-logs') || currentTooltips[0];
      selectTooltip(defaultItem.key);
    }
  } catch (err) {
    listEl.innerHTML = `<div class="alert alert-warning p-2 small"><i class="bi bi-exclamation-triangle me-1"></i>Ошибка загрузки подсказок: ${err.message}</div>`;
  }
}

/**
 * Рендерит элементы списка подсказок с фильтрацией.
 */
function renderTooltipsList() {
  const listEl = document.getElementById('tooltips-items-list');
  if (!listEl) return;

  const searchVal = (document.getElementById('tooltips-search-input')?.value || '').toLowerCase().trim();
  const catVal = (document.getElementById('tooltips-filter-category')?.value || '').toLowerCase().trim();

  const filtered = currentTooltips.filter(item => {
    const matchSearch = !searchVal ||
      item.key.toLowerCase().includes(searchVal) ||
      (item.title && item.title.toLowerCase().includes(searchVal)) ||
      (item.summary && item.summary.toLowerCase().includes(searchVal));
    const matchCat = !catVal || (item.category && item.category.toLowerCase() === catVal);
    return matchSearch && matchCat;
  });

  if (filtered.length === 0) {
    listEl.innerHTML = '<div class="text-center text-muted py-3 small">Подсказки не найдены</div>';
    return;
  }

  listEl.innerHTML = filtered.map(item => `
    <a href="javascript:void(0)" class="list-group-item list-group-item-action py-2 px-2 border-bottom ${item.key === activeKey ? 'active' : ''}" data-key="${item.key}" id="tooltip-item-${item.key}">
      <div class="d-flex w-100 justify-content-between align-items-center mb-1">
        <div class="d-flex align-items-center gap-1.5 text-truncate" style="max-width: 200px;">
          <span>${item.icon || '💡'}</span>
          <strong class="small text-truncate">${escapeHtml(item.title || item.key)}</strong>
        </div>
        <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle" style="font-size: 0.68rem;">${escapeHtml(item.category || 'Справка')}</span>
      </div>
      <div class="small text-muted font-monospace text-truncate" style="font-size: 0.72rem;">${escapeHtml(item.key)}</div>
    </a>
  `).join('');

  listEl.querySelectorAll('[data-key]').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.getAttribute('data-key');
      if (k) selectTooltip(k);
    });
  });
}

/**
 * Выбирает подсказку для редактирования и заполняет форму.
 * @param {string} key - Ключ подсказки
 */
function selectTooltip(key) {
  activeKey = key;
  const item = currentTooltips.find(i => i.key === key);
  if (!item) return;

  document.querySelectorAll('#tooltips-items-list .list-group-item').forEach(el => el.classList.remove('active'));
  const activeItemEl = document.getElementById(`tooltip-item-${key}`);
  if (activeItemEl) activeItemEl.classList.add('active');

  const keyInput = document.getElementById('tooltip-edit-key');
  const titleInput = document.getElementById('tooltip-edit-title');
  const fullTitleInput = document.getElementById('tooltip-edit-fulltitle');
  const iconInput = document.getElementById('tooltip-edit-icon');
  const catInput = document.getElementById('tooltip-edit-category');
  const summaryInput = document.getElementById('tooltip-edit-summary');
  const formTitle = document.getElementById('tooltips-form-title');
  const delBtn = document.getElementById('tooltips-btn-delete');

  if (keyInput) {
    keyInput.value = item.key;
    keyInput.readOnly = true;
  }
  if (titleInput) titleInput.value = item.title || '';
  if (fullTitleInput) fullTitleInput.value = item.fullTitle || item.title || '';
  if (iconInput) iconInput.value = item.icon || '💡';
  if (catInput) catInput.value = item.category || 'Справка';
  if (summaryInput) summaryInput.value = item.summary || '';
  if (formTitle) formTitle.innerText = `Редактирование: ${item.key}`;
  if (delBtn) delBtn.style.display = 'inline-block';

  updateLivePreview();
}

/**
 * Переводит форму в режим создания новой подсказки.
 */
function createNewTooltip() {
  activeKey = null;
  document.querySelectorAll('#tooltips-items-list .list-group-item').forEach(el => el.classList.remove('active'));

  const keyInput = document.getElementById('tooltip-edit-key');
  const titleInput = document.getElementById('tooltip-edit-title');
  const fullTitleInput = document.getElementById('tooltip-edit-fulltitle');
  const iconInput = document.getElementById('tooltip-edit-icon');
  const catInput = document.getElementById('tooltip-edit-category');
  const summaryInput = document.getElementById('tooltip-edit-summary');
  const formTitle = document.getElementById('tooltips-form-title');
  const delBtn = document.getElementById('tooltips-btn-delete');

  if (keyInput) {
    keyInput.value = '';
    keyInput.readOnly = false;
    keyInput.focus();
  }
  if (titleInput) titleInput.value = '';
  if (fullTitleInput) fullTitleInput.value = '';
  if (iconInput) iconInput.value = '💡';
  if (catInput) catInput.value = 'Справка';
  if (summaryInput) summaryInput.value = '';
  if (formTitle) formTitle.innerText = 'Новая подсказка';
  if (delBtn) delBtn.style.display = 'none';

  updateLivePreview();
}

/**
 * Обновляет блок живого предпросмотра на основе полей формы.
 */
function updateLivePreview() {
  const iconVal = document.getElementById('tooltip-edit-icon')?.value || '💡';
  const titleVal = document.getElementById('tooltip-edit-title')?.value || 'Заголовок подсказки';
  const catVal = document.getElementById('tooltip-edit-category')?.value || 'Справка';
  const summaryVal = document.getElementById('tooltip-edit-summary')?.value || 'Текст пояснения подсказки...';

  const pIcon = document.getElementById('preview-tooltip-icon');
  const pTitle = document.getElementById('preview-tooltip-title');
  const pBadge = document.getElementById('preview-tooltip-badge');
  const pBody = document.getElementById('preview-tooltip-body');

  if (pIcon) pIcon.textContent = iconVal;
  if (pTitle) pTitle.textContent = titleVal;
  if (pBadge) pBadge.textContent = catVal;
  if (pBody) pBody.textContent = summaryVal;
}

/**
 * Сохраняет текущую подсказку на сервере и обновляет локальный кэш.
 */
async function saveTooltip() {
  const key = document.getElementById('tooltip-edit-key')?.value.trim();
  const title = document.getElementById('tooltip-edit-title')?.value.trim();
  const fullTitle = document.getElementById('tooltip-edit-fulltitle')?.value.trim() || title;
  const icon = document.getElementById('tooltip-edit-icon')?.value.trim() || '💡';
  const category = document.getElementById('tooltip-edit-category')?.value.trim() || 'Справка';
  const summary = document.getElementById('tooltip-edit-summary')?.value.trim();

  if (!key) {
    notifyUser('Укажите ключ подсказки', 'warning');
    return;
  }
  if (!title) {
    notifyUser('Укажите заголовок подсказки', 'warning');
    return;
  }
  if (!summary) {
    notifyUser('Заполните текст подсказки', 'warning');
    return;
  }

  const payload = {
    key: key,
    title: title,
    fullTitle: fullTitle,
    icon: icon,
    category: category,
    summary: summary,
    lang: currentLang,
    source: 'custom'
  };

  try {
    const res = await fetch('/api/v1/tooltips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }

    // Мгновенное обновление клиентского TooltipCache и DOM
    if (window.TooltipCache && typeof window.TooltipCache.set === 'function') {
      window.TooltipCache.set(key, payload);
      window.TooltipCache.set(`internals-${key}`, payload);
    }

    // Если это центр логов, обновляем подсказку на кнопке в DOM
    if (key === 'internals-logs' || key === 'logs') {
      const logBtn = document.getElementById('subtab-internals-logs-btn');
      if (logBtn) {
        logBtn.setAttribute('title', summary);
        logBtn.setAttribute('data-bs-original-title', summary);
        logBtn.setAttribute('data-bs-title', summary);
      }
    }

    notifyUser(`Подсказка «${key}» успешно сохранена!`, 'success');
    activeKey = key;
    await loadTooltipsList();
  } catch (err) {
    notifyUser(`Ошибка сохранения: ${err.message}`, 'danger');
  }
}

/**
 * Удаляет выбранную подсказку.
 */
async function deleteTooltip() {
  if (!activeKey) return;
  if (!confirm(`Вы действительно хотите удалить подсказку «${activeKey}»?`)) return;

  try {
    const res = await fetch(`/api/v1/tooltips/${encodeURIComponent(activeKey)}?lang=${encodeURIComponent(currentLang)}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }
    notifyUser(`Подсказка «${activeKey}» удалена`, 'info');
    activeKey = null;
    await loadTooltipsList();
    createNewTooltip();
  } catch (err) {
    notifyUser(`Ошибка удаления: ${err.message}`, 'danger');
  }
}

/**
 * Экранирует HTML строку.
 */
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Инициализирует панель редактора тултипов.
 * @returns {Promise<void>}
 */
export async function initTooltipsEditorPanel() {
  const container = document.getElementById('internals-tooltips-editor-container');
  if (!container) return;

  if (!container.dataset.initialized) {
    container.dataset.initialized = 'true';
    renderLayout(container);

    // События
    document.getElementById('tooltips-search-input')?.addEventListener('input', () => renderTooltipsList());
    document.getElementById('tooltips-filter-category')?.addEventListener('change', () => renderTooltipsList());
    document.getElementById('tooltips-btn-create')?.addEventListener('click', () => createNewTooltip());
    document.getElementById('tooltips-btn-refresh')?.addEventListener('click', () => loadTooltipsList());
    document.getElementById('tooltips-btn-save')?.addEventListener('click', () => saveTooltip());
    document.getElementById('tooltips-btn-delete')?.addEventListener('click', () => deleteTooltip());

    // Переключение языка
    document.getElementById('tooltips-lang-select')?.addEventListener('change', (e) => {
      currentLang = e.target.value;
      activeKey = null;
      loadTooltipsList();
    });

    // Живой предпросмотр при вводе
    ['tooltip-edit-icon', 'tooltip-edit-title', 'tooltip-edit-category', 'tooltip-edit-summary'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => updateLivePreview());
    });
  }

  await loadTooltipsList();
}

window.initTooltipsEditorPanel = initTooltipsEditorPanel;
