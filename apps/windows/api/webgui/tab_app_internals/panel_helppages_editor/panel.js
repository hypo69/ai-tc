/**
 * =============================================================================
 * Process Name: Windows App Internals - Help Pages Editor Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер редактора страниц и блоков контекстной справки:
 *   - Загрузка каталога модулей, композитов и блоков (/api/v1/help-pages/catalog)
 *   - Открытие и редактирование файлов справки (.html, .md)
 *   - Проверка стандартов стилизации и тем (Linting: отсутствие inline HEX/RGB)
 *   - Сохранение с автоматическим обновлением метки Updated: YYYY-MM-DD HH:MM:SS
 *   - Интеграция с window.HelpModal для мгновенного предпросмотра в 80vw × 80vh
 *   - Создание новых страниц и блоков справки
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_helppages_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 18:03:00
 * =============================================================================
 */

let currentFilePath = null;
let catalogCache = null;
let isEditorInitialized = false;

/**
 * Инициализация контроллера редактора страниц справки.
 */
export async function initHelpPagesEditor() {
  if (isEditorInitialized) return;
  isEditorInitialized = true;

  bindEditorButtons();
  await loadHelpCatalog();
}

/**
 * Привязка кнопок и обработчиков событий панели.
 */
export function bindEditorButtons() {
  const refreshBtn = document.getElementById('hp-btn-refresh-catalog');
  if (refreshBtn && !refreshBtn._bound) {
    refreshBtn._bound = true;
    refreshBtn.addEventListener('click', () => loadHelpCatalog());
  }

  const saveBtn = document.getElementById('hp-btn-save');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', () => saveCurrentFile());
  }

  const previewBtn = document.getElementById('hp-btn-preview');
  if (previewBtn && !previewBtn._bound) {
    previewBtn._bound = true;
    previewBtn.addEventListener('click', () => previewCurrentFile());
  }

  const searchInput = document.getElementById('hp-search-input');
  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener('input', (e) => filterCatalogTree(e.target.value));
  }

  // Сниппеты шаблонов
  const snippetIncludeBtn = document.getElementById('hp-snippet-include');
  if (snippetIncludeBtn && !snippetIncludeBtn._bound) {
    snippetIncludeBtn._bound = true;
    snippetIncludeBtn.addEventListener('click', () => {
      insertSnippet('<div data-help-include="/html/tab_example/help/blocks/block_name.html"></div>\n');
    });
  }

  const snippetAtomicBtn = document.getElementById('hp-snippet-atomic');
  if (snippetAtomicBtn && !snippetAtomicBtn._bound) {
    snippetAtomicBtn._bound = true;
    snippetAtomicBtn.addEventListener('click', () => {
      const template = `<div class="card bg-body border-subtle shadow-sm mb-3 help-atomic-block" data-help-block="block_id">\n` +
        `  <div class="card-header bg-body-tertiary d-flex align-items-center justify-content-between py-2 px-3">\n` +
        `    <h6 class="mb-0 fw-bold text-body">Заголовок блока</h6>\n` +
        `    <span class="ui-badge ui-badge-info">Атомарный блок</span>\n` +
        `  </div>\n` +
        `  <div class="card-body p-3">\n` +
        `    <p class="small text-muted mb-0">Описание функционала...</p>\n` +
        `  </div>\n` +
        `</div>\n`;
      insertSnippet(template);
    });
  }

  // Создание нового файла справки
  const submitCreateBtn = document.getElementById('hp-btn-submit-create');
  if (submitCreateBtn && !submitCreateBtn._bound) {
    submitCreateBtn._bound = true;
    submitCreateBtn.addEventListener('click', () => submitCreateFile());
  }

  // Переключение видимости поля имени блока при выборе типа
  const kindSelect = document.getElementById('hp-create-kind');
  const nameGroup = document.getElementById('hp-create-name-group');
  if (kindSelect && nameGroup && !kindSelect._bound) {
    kindSelect._bound = true;
    kindSelect.addEventListener('change', () => {
      if (kindSelect.value === 'composite' || kindSelect.value === 'doc') {
        nameGroup.classList.add('d-none');
      } else {
        nameGroup.classList.remove('d-none');
      }
    });
  }
}

/**
 * Загрузка каталога страниц справки с сервера.
 */
export async function loadHelpCatalog() {
  const treeContainer = document.getElementById('hp-catalog-tree');
  const countBadge = document.getElementById('hp-modules-count');
  if (!treeContainer) return;

  treeContainer.innerHTML = `
    <div class="text-center py-4 text-muted">
      <div class="spinner-border text-primary spinner-border-sm me-2" role="status"></div>
      <span>Загрузка каталога...</span>
    </div>
  `;

  try {
    const resp = await fetch('/api/v1/help-pages/catalog');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    catalogCache = data.modules || [];

    if (countBadge) {
      countBadge.textContent = String(catalogCache.length);
    }

    renderCatalogTree(catalogCache);
  } catch (err) {
    console.error('[HelpPagesEditor] Ошибка загрузки каталога:', err);
    treeContainer.innerHTML = `
      <div class="alert alert-danger small p-2 mb-0">
        <i class="bi bi-x-circle me-1"></i>Ошибка загрузки каталога: ${err.message}
      </div>
    `;
  }
}

/**
 * Отрисовка дерева модулей и блоков.
 * @param {Array} modules
 */
function renderCatalogTree(modules) {
  const treeContainer = document.getElementById('hp-catalog-tree');
  if (!treeContainer) return;

  if (!modules || modules.length === 0) {
    treeContainer.innerHTML = `
      <div class="text-center py-4 text-muted small">
        <i class="bi bi-folder-x fs-3 d-block mb-1"></i>
        <span>Нет созданных страниц справки</span>
      </div>
    `;
    return;
  }

  let html = '<div class="list-group list-group-flush gap-1">';
  modules.forEach((mod) => {
    html += `
      <div class="p-1 rounded bg-body-tertiary border border-subtle mb-1">
        <div class="d-flex align-items-center justify-content-between px-2 py-1">
          <strong class="small text-body d-flex align-items-center gap-1.5">
            <i class="bi bi-folder-fill text-warning"></i>
            <span>${mod.module}</span>
          </strong>
          <span class="ui-badge ui-badge-neutral">${mod.blocks_count} бл.</span>
        </div>
        <div class="list-group list-group-flush ps-2 mt-1">
    `;

    // Композитный файл (index.html)
    if (mod.has_composite && mod.composite_path) {
      html += `
        <button type="button" class="list-group-item list-group-item-action py-1 px-2 small d-flex align-items-center justify-content-between border-0 rounded mb-0.5 ${currentFilePath === mod.composite_path ? 'active' : ''}" data-file-path="${mod.composite_path}">
          <span class="d-flex align-items-center gap-1 text-truncate">
            <i class="bi bi-file-earmark-richtext text-primary"></i>
            <span class="text-truncate fw-semibold">index.html (Композит)</span>
          </span>
          <span class="ui-badge ui-badge-info" style="font-size: 0.68rem;">Сводка</span>
        </button>
      `;
    }

    // Атомарные блоки
    if (mod.blocks && mod.blocks.length > 0) {
      mod.blocks.forEach((blk) => {
        html += `
          <button type="button" class="list-group-item list-group-item-action py-1 px-2 small d-flex align-items-center justify-content-between border-0 rounded mb-0.5 ${currentFilePath === blk.path ? 'active' : ''}" data-file-path="${blk.path}">
            <span class="d-flex align-items-center gap-1 text-truncate" title="${blk.title}">
              <i class="bi bi-puzzle text-info"></i>
              <span class="text-truncate">${blk.name}</span>
            </span>
            <span class="ui-badge ui-badge-neutral" style="font-size: 0.65rem;">Атом</span>
          </button>
        `;
      });
    }

    // Документация README.md
    if (mod.has_readme && mod.readme_path) {
      html += `
        <button type="button" class="list-group-item list-group-item-action py-1 px-2 small d-flex align-items-center justify-content-between border-0 rounded mb-0.5 ${currentFilePath === mod.readme_path ? 'active' : ''}" data-file-path="${mod.readme_path}">
          <span class="d-flex align-items-center gap-1 text-truncate">
            <i class="bi bi-markdown text-secondary"></i>
            <span class="text-truncate">README.md</span>
          </span>
          <span class="ui-badge ui-badge-neutral" style="font-size: 0.65rem;">Doc</span>
        </button>
      `;
    }

    html += `</div></div>`;
  });
  html += '</div>';

  treeContainer.innerHTML = html;

  // Привязка кликов по файлам
  treeContainer.querySelectorAll('[data-file-path]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const p = btn.getAttribute('data-file-path');
      if (p) openFile(p);
    });
  });
}

/**
 * Фильтрация элементов каталога по подстроке поиска.
 * @param {string} query
 */
function filterCatalogTree(query) {
  if (!catalogCache) return;
  const q = (query || '').toLowerCase().trim();
  if (!q) {
    renderCatalogTree(catalogCache);
    return;
  }

  const filtered = catalogCache
    .map((mod) => {
      const matchMod = mod.module.toLowerCase().includes(q);
      const filteredBlocks = (mod.blocks || []).filter(
        (b) => b.name.toLowerCase().includes(q) || b.title.toLowerCase().includes(q)
      );
      if (matchMod || filteredBlocks.length > 0) {
        return { ...mod, blocks: filteredBlocks };
      }
      return null;
    })
    .filter(Boolean);

  renderCatalogTree(filtered);
}

/**
 * Открытие файла справки в редакторе.
 * @param {string} path
 */
export async function openFile(path) {
  currentFilePath = path;
  const pathLabel = document.getElementById('hp-current-file-path');
  const mtimeLabel = document.getElementById('hp-file-mtime');
  const editor = document.getElementById('hp-code-editor');
  const saveBtn = document.getElementById('hp-btn-save');
  const previewBtn = document.getElementById('hp-btn-preview');
  const lintBadge = document.getElementById('hp-lint-badge');
  const lintWarning = document.getElementById('hp-lint-warning');

  if (pathLabel) pathLabel.textContent = path;
  if (editor) {
    editor.value = 'Загрузка содержимого...';
    editor.disabled = true;
  }
  if (saveBtn) saveBtn.disabled = true;
  if (previewBtn) previewBtn.disabled = true;

  try {
    const resp = await fetch(`/api/v1/help-pages/file?path=${encodeURIComponent(path)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (editor) {
      editor.value = data.content || '';
      editor.disabled = false;
    }
    if (mtimeLabel) mtimeLabel.textContent = `Обновлен: ${data.updated_at || ''}`;
    if (saveBtn) saveBtn.disabled = false;
    if (previewBtn) previewBtn.disabled = !path.endsWith('.html');

    // Проверка линтера тем
    const isCompliant = data.style_lint?.is_theme_compliant;
    if (lintBadge) {
      lintBadge.classList.remove('d-none', 'ui-badge-success', 'ui-badge-danger');
      lintBadge.classList.add(isCompliant ? 'ui-badge-success' : 'ui-badge-danger');
      lintBadge.innerHTML = isCompliant
        ? '<i class="bi bi-check-circle me-1"></i>Theme OK'
        : '<i class="bi bi-exclamation-triangle me-1"></i>Theme Warning';
    }
    if (lintWarning) {
      lintWarning.classList.toggle('d-none', isCompliant);
    }

    // Подсветка активного файла в дереве
    document.querySelectorAll('#hp-catalog-tree [data-file-path]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-file-path') === path);
    });
  } catch (err) {
    console.error('[HelpPagesEditor] Ошибка открытия файла:', err);
    if (editor) editor.value = `Ошибка загрузки файла: ${err.message}`;
  }
}

/**
 * Сохранение текущего файла справки.
 */
export async function saveCurrentFile() {
  if (!currentFilePath) return;
  const editor = document.getElementById('hp-code-editor');
  const saveBtn = document.getElementById('hp-btn-save');
  const mtimeLabel = document.getElementById('hp-file-mtime');
  const lintBadge = document.getElementById('hp-lint-badge');
  const lintWarning = document.getElementById('hp-lint-warning');

  const content = editor?.value || '';
  if (saveBtn) saveBtn.disabled = true;

  try {
    const resp = await fetch('/api/v1/help-pages/file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: currentFilePath, content }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const result = await resp.json();

    if (mtimeLabel) mtimeLabel.textContent = `Обновлен: ${result.updated_at || ''}`;

    const isCompliant = result.style_lint?.is_theme_compliant;
    if (lintBadge) {
      lintBadge.classList.remove('d-none', 'ui-badge-success', 'ui-badge-danger');
      lintBadge.classList.add(isCompliant ? 'ui-badge-success' : 'ui-badge-danger');
      lintBadge.innerHTML = isCompliant
        ? '<i class="bi bi-check-circle me-1"></i>Theme OK'
        : '<i class="bi bi-exclamation-triangle me-1"></i>Theme Warning';
    }
    if (lintWarning) {
      lintWarning.classList.toggle('d-none', isCompliant);
    }

    if (window.toast) {
      window.toast.showSuccess(`Файл ${currentFilePath} успешно сохранен`);
    }
  } catch (err) {
    console.error('[HelpPagesEditor] Ошибка сохранения файла:', err);
    if (window.toast) {
      window.toast.showError(`Ошибка сохранения: ${err.message}`);
    } else {
      alert(`Ошибка сохранения: ${err.message}`);
    }
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * Предпросмотр текущего HTML файла в окне HelpModal (80vw × 80vh).
 */
export function previewCurrentFile() {
  if (!currentFilePath || !window.HelpModal) return;
  const webUrl = `/html/${currentFilePath}`;
  window.HelpModal.openUrl(webUrl, { title: `Предпросмотр: ${currentFilePath}` });
}

/**
 * Вставка сниппета разметки в текущую позицию курсора редактора.
 * @param {string} snippet
 */
function insertSnippet(snippet) {
  const editor = document.getElementById('hp-code-editor');
  if (!editor || editor.disabled) return;
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const val = editor.value;
  editor.value = val.substring(0, start) + snippet + val.substring(end);
  editor.selectionStart = editor.selectionEnd = start + snippet.length;
  editor.focus();
}

/**
 * Отправка запроса на создание нового файла справки.
 */
async function submitCreateFile() {
  const moduleInput = document.getElementById('hp-create-module');
  const kindSelect = document.getElementById('hp-create-kind');
  const nameInput = document.getElementById('hp-create-name');
  const titleInput = document.getElementById('hp-create-title');
  const descInput = document.getElementById('hp-create-desc');
  const statusEl = document.getElementById('hp-create-status');
  const submitBtn = document.getElementById('hp-btn-submit-create');

  const moduleVal = moduleInput?.value.trim();
  const kindVal = kindSelect?.value;
  const nameVal = nameInput?.value.trim();
  const titleVal = titleInput?.value.trim();
  const descVal = descInput?.value.trim();

  if (!moduleVal) {
    if (statusEl) statusEl.textContent = 'Укажите модуль';
    return;
  }
  if (kindVal === 'block' && !nameVal) {
    if (statusEl) statusEl.textContent = 'Укажите имя блока';
    return;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (statusEl) statusEl.textContent = 'Создание...';

  try {
    const resp = await fetch('/api/v1/help-pages/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        module: moduleVal,
        kind: kindVal,
        name: nameVal || 'block',
        title: titleVal,
        description: descVal,
      }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${resp.status}`);
    }
    const res = await resp.json();

    // Закрываем модальное окно
    const modalEl = document.getElementById('hpCreateModal');
    if (modalEl && window.bootstrap) {
      const modalInstance = bootstrap.Modal.getInstance(modalEl);
      if (modalInstance) modalInstance.hide();
    }

    await loadHelpCatalog();
    if (res.path) {
      await openFile(res.path);
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = `Ошибка: ${err.message}`;
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}
