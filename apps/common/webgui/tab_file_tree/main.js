/**
 * =============================================================================
 * Process Name: Common WebGUI - File & Directory Tree Explorer Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский оркестратор древовидного проводника файлов и поддиректорий
 *   (apps/common/webgui/tab_file_tree).
 *   Управляет:
 *   - Загрузкой и отображением иерархического дерева выбранной директории.
 *   - Чекбоксами выбора каждого файла и директории (с каскадным выбором потомков).
 *   - Кнопками "Выбрать все", "Снять выбор", "Инвертировать выбор".
 *   - Навигацией по директориям (вверх, хлебные крошки, прямой ввод пути).
 *   - Контекстным подменю при правом клике:
 *     1) Кратко о файле (аналитическая сводка и метаданные).
 *     2) Редактор (открытие в Wasm-редакторе tab_file_editor).
 *     3) Создать новый (создание файла или папки в директории клика).
 *
 * File: main.js
 * Project: ai-assistant
 * Package: apps.common.webgui.tab_file_tree
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 13:30:00
 * =============================================================================
 */

let isInitialized = false;
let currentWorkspaceId = 'default';
let currentDirectory = '';
let currentParentDir = null;
let currentTreeData = null;
const expandedFolderPaths = new Set();
const selectedRelPaths = new Set();
let activeTargetNode = null; // { relPath, name, isDir, parentDir }

function t(key, fallback = '') {
  if (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function') {
    return window.i18n.t(key, fallback);
  }
  return fallback;
}

function showToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else if (typeof window.showNotificationToast === 'function') {
    window.showNotificationToast(msg, type);
  } else {
    console.log(`[Toast ${type}] ${msg}`);
  }
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getActiveWorkspace() {
  if (typeof window.getActiveWorkspaceId === 'function') {
    const ws = window.getActiveWorkspaceId();
    if (ws) return ws;
  }
  try {
    return localStorage.getItem('ai_assistant_active_workspace') || 'demo';
  } catch (_) {
    return 'demo';
  }
}

/**
 * Возвращает подходящую иконку Bootstrap Icons для файла или папки.
 * @param {Object} node 
 * @param {boolean} isExpanded 
 * @returns {string} HTML иконки
 */
function getNodeIconHtml(node, isExpanded = true) {
  if (node.is_dir) {
    return isExpanded
      ? '<i class="bi bi-folder2-open text-warning ft-node-icon"></i>'
      : '<i class="bi bi-folder-fill text-warning ft-node-icon"></i>';
  }

  const ext = (node.extension || '').toLowerCase();
  switch (ext) {
    case '.md':
    case '.markdown':
      return '<i class="bi bi-markdown-fill text-info ft-node-icon"></i>';
    case '.json':
      return '<i class="bi bi-braces text-warning ft-node-icon"></i>';
    case '.py':
      return '<i class="bi bi-filetype-py text-primary ft-node-icon"></i>';
    case '.js':
    case '.ts':
      return '<i class="bi bi-filetype-js text-warning ft-node-icon"></i>';
    case '.html':
    case '.xml':
      return '<i class="bi bi-filetype-html text-danger ft-node-icon"></i>';
    case '.css':
    case '.scss':
      return '<i class="bi bi-filetype-css text-info ft-node-icon"></i>';
    case '.pdf':
      return '<i class="bi bi-file-earmark-pdf text-danger ft-node-icon"></i>';
    case '.png':
    case '.jpg':
    case '.jpeg':
    case '.webp':
    case '.svg':
    case '.gif':
      return '<i class="bi bi-file-earmark-image text-success ft-node-icon"></i>';
    case '.csv':
    case '.xlsx':
    case '.xls':
      return '<i class="bi bi-file-earmark-spreadsheet text-success ft-node-icon"></i>';
    case '.ipynb':
      return '<i class="bi bi-journal-code text-warning ft-node-icon"></i>';
    case '.bin':
    case '.wasm':
    case '.exe':
      return '<i class="bi bi-file-earmark-binary text-secondary ft-node-icon"></i>';
    default:
      return '<i class="bi bi-file-earmark-text text-secondary ft-node-icon"></i>';
  }
}

/**
 * Формирует HTML-бейджик статуса Git.
 * @param {Object} node 
 * @returns {string}
 */
function getGitBadgeHtml(node) {
  if (node.is_dir || !node.git_code) return '';
  const code = node.git_code;
  const status = node.git_status || code;

  if (code.includes('M')) {
    return `<span class="badge bg-warning-subtle text-warning border border-warning-subtle" title="${escapeHtml(status)}">M</span>`;
  }
  if (code.includes('A')) {
    return `<span class="badge bg-success-subtle text-success border border-success-subtle" title="${escapeHtml(status)}">A</span>`;
  }
  if (code.includes('D')) {
    return `<span class="badge bg-danger-subtle text-danger border border-danger-subtle" title="${escapeHtml(status)}">D</span>`;
  }
  if (code.includes('R')) {
    return `<span class="badge bg-info-subtle text-info border border-info-subtle" title="${escapeHtml(status)}">R</span>`;
  }
  if (code === '??') {
    return `<span class="badge bg-secondary-subtle text-secondary border" title="${escapeHtml(status)}">??</span>`;
  }
  return '';
}

/**
 * Отрисовывает навигационную цепочку хлебных крошек.
 * @param {Array<Object>} breadcrumbs 
 */
function renderBreadcrumbs(breadcrumbs) {
  const listEl = document.getElementById('ft-breadcrumbs-list');
  if (!listEl) return;

  if (!breadcrumbs || breadcrumbs.length === 0) {
    listEl.innerHTML = '<li class="breadcrumb-item active">/ (Корень)</li>';
    return;
  }

  listEl.innerHTML = breadcrumbs.map((bc, idx) => {
    if (bc.is_current || idx === breadcrumbs.length - 1) {
      return `<li class="breadcrumb-item active fw-semibold" aria-current="page">${escapeHtml(bc.name)}</li>`;
    }
    return `
      <li class="breadcrumb-item">
        <a href="javascript:void(0)" class="text-decoration-none ft-breadcrumb-link" data-path="${escapeHtml(bc.path)}">
          ${escapeHtml(bc.name)}
        </a>
      </li>
    `;
  }).join('');

  listEl.querySelectorAll('.ft-breadcrumb-link').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const p = link.getAttribute('data-path') || '';
      browseDirectory(p);
    });
  });
}

/**
 * Рекурсивно собирает все пути (файлы и подпапки) узла дерева.
 * @param {Object} node 
 * @param {Array<string>} list 
 */
function collectDescendantPaths(node, list = []) {
  if (!node) return list;
  list.push(node.rel_path);
  if (Array.isArray(node.children)) {
    for (const ch of node.children) {
      collectDescendantPaths(ch, list);
    }
  }
  return list;
}

/**
 * Обновляет счетчик выбранных элементов в шапке.
 */
function updateSelectionBadge() {
  const badge = document.getElementById('ft-selection-badge');
  const count = selectedRelPaths.size;
  if (badge) {
    badge.textContent = `${t('fileTree.selectedCount', 'Выбрано')}: ${count}`;
  }

  const btnSelectAll = document.getElementById('ft-btn-select-all');
  const lblSelectAll = document.getElementById('ft-lbl-select-all');
  if (btnSelectAll && lblSelectAll) {
    if (count > 0) {
      lblSelectAll.textContent = t('fileTree.deselectAll', 'Снять выбор');
      btnSelectAll.classList.replace('btn-outline-primary', 'btn-primary');
    } else {
      lblSelectAll.textContent = t('fileTree.selectAll', 'Выбрать все');
      btnSelectAll.classList.replace('btn-primary', 'btn-outline-primary');
    }
  }
}

/**
 * Рекурсивный рендеринг узлов дерева файлов.
 * @param {Array<Object>} nodes 
 * @param {number} depth 
 * @param {string} filterText 
 * @returns {string} HTML
 */
function renderTreeNodesHtml(nodes, depth = 0, filterText = '') {
  if (!nodes || nodes.length === 0) return '';

  const q = (filterText || '').toLowerCase().trim();

  return nodes.map((node) => {
    const isDir = Boolean(node.is_dir);
    const relPath = node.rel_path;
    const isExpanded = !isDir || expandedFolderPaths.has(relPath) || Boolean(q);
    const isSelected = selectedRelPaths.has(relPath);

    // Фильтрация
    if (q) {
      const allPaths = collectDescendantPaths(node);
      const matches = allPaths.some((p) => p.toLowerCase().includes(q) || p.split('/').pop().toLowerCase().includes(q));
      if (!matches) return '';
    }

    const indentPx = depth * 18;
    const chevronHtml = isDir
      ? `<button class="btn btn-sm p-0 border-0 text-secondary ft-toggle-btn" data-folder-path="${escapeHtml(relPath)}" type="button" title="Развернуть/свернуть">
           <i class="bi ${isExpanded ? 'bi-chevron-down' : 'bi-chevron-right'} small"></i>
         </button>`
      : '<span class="d-inline-block" style="width: 18px;"></span>';

    const iconHtml = getNodeIconHtml(node, isExpanded);
    const gitBadge = getGitBadgeHtml(node);
    const sizeBadge = isDir
      ? `<span class="badge bg-secondary-subtle text-secondary border">${node.children_count || 0} эл.</span>`
      : `<span class="text-secondary small font-monospace">${escapeHtml(node.size_formatted)}</span>`;

    const childrenHtml = (isDir && isExpanded && node.children && node.children.length > 0)
      ? `<div class="ft-tree-children border-start border-secondary-subtle ms-3 ps-1 mt-1">${renderTreeNodesHtml(node.children, depth + 1, filterText)}</div>`
      : '';

    return `
      <div class="ft-tree-node-wrap mb-0.5" data-rel-path="${escapeHtml(relPath)}">
        <div class="ft-tree-row ${isSelected ? 'selected' : ''}"
             data-rel-path="${escapeHtml(relPath)}"
             data-name="${escapeHtml(node.name)}"
             data-is-dir="${isDir ? '1' : '0'}"
             data-parent-dir="${escapeHtml(currentDirectory)}"
             style="padding-inline-start: ${indentPx + 6}px; padding-left: ${indentPx + 6}px;"
             role="button">
          <div class="d-flex align-items-center gap-1.5 text-truncate flex-grow-1">
            ${chevronHtml}
            <input type="checkbox"
                   class="form-check-input ft-item-checkbox my-0"
                   data-rel-path="${escapeHtml(relPath)}"
                   data-is-dir="${isDir ? '1' : '0'}"
                   ${isSelected ? 'checked' : ''}
                   title="Выбрать элемент">
            ${iconHtml}
            <span class="ft-tree-item-title text-truncate" title="${escapeHtml(relPath)}">${escapeHtml(node.name)}</span>
          </div>
          <div class="d-flex align-items-center gap-1.5 flex-shrink-0">
            ${gitBadge}
            ${sizeBadge}
          </div>
        </div>
        ${childrenHtml}
      </div>
    `;
  }).join('');
}

/**
 * Отрисовывает дерево файлов в контейнере.
 */
export function renderFileTree() {
  const container = document.getElementById('ft-tree-container');
  if (!container) return;

  if (!currentTreeData || !currentTreeData.tree || currentTreeData.tree.length === 0) {
    container.innerHTML = `
      <div class="text-center text-muted py-5 small" id="ft-empty-message">
        <i class="bi bi-folder2 text-secondary fs-3 d-block mb-2"></i>
        <span>${t('fileTree.emptyDir', 'Директория пуста или файлы не найдены')}</span>
      </div>
    `;
    return;
  }

  const filterText = document.getElementById('ft-filter-input')?.value || '';
  container.innerHTML = renderTreeNodesHtml(currentTreeData.tree, 0, filterText);

  // Обработчик сворачивания/разворачивания папок
  container.querySelectorAll('.ft-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const fPath = btn.getAttribute('data-folder-path');
      if (!fPath) return;
      if (expandedFolderPaths.has(fPath)) {
        expandedFolderPaths.delete(fPath);
      } else {
        expandedFolderPaths.add(fPath);
      }
      renderFileTree();
    });
  });

  // Обработчик клика по строке (навигация в папку / выделение)
  container.querySelectorAll('.ft-tree-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('.ft-item-checkbox') || e.target.closest('.ft-toggle-btn')) {
        return;
      }
      const isDir = row.getAttribute('data-is-dir') === '1';
      const relPath = row.getAttribute('data-rel-path') || '';

      container.querySelectorAll('.ft-tree-row').forEach((r) => r.classList.remove('active'));
      row.classList.add('active');

      if (isDir) {
        if (expandedFolderPaths.has(relPath)) {
          expandedFolderPaths.delete(relPath);
        } else {
          expandedFolderPaths.add(relPath);
        }
        renderFileTree();
      }
    });

    // Двойной клик: папка -> перейти в нее, файл -> открыть в редакторе
    row.addEventListener('dblclick', async (e) => {
      if (e.target.closest('.ft-item-checkbox')) return;
      const isDir = row.getAttribute('data-is-dir') === '1';
      const relPath = row.getAttribute('data-rel-path') || '';
      if (isDir) {
        await browseDirectory(relPath);
      } else {
        await openFileInEditor(relPath);
      }
    });

    // Правый клик (ПКМ) -> вызов подменю
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isDir = row.getAttribute('data-is-dir') === '1';
      const relPath = row.getAttribute('data-rel-path') || '';
      const name = row.getAttribute('data-name') || relPath.split('/').pop();

      activeTargetNode = {
        isDir,
        relPath,
        name,
        parentDir: isDir ? relPath : (relPath.split('/').slice(0, -1).join('/') || ''),
      };

      showContextMenu(e);
    });
  });

  // Обработчики чекбоксов (с каскадным выбором)
  container.querySelectorAll('.ft-item-checkbox').forEach((cb) => {
    cb.addEventListener('change', (e) => {
      e.stopPropagation();
      const relPath = cb.getAttribute('data-rel-path');
      const isDir = cb.getAttribute('data-is-dir') === '1';
      const isChecked = cb.checked;

      if (!relPath) return;

      if (isChecked) {
        selectedRelPaths.add(relPath);
      } else {
        selectedRelPaths.delete(relPath);
      }

      // Если чекбокс на папке — каскадно переключаем всех её потомков
      if (isDir && currentTreeData) {
        const findNode = (nodes) => {
          for (const n of nodes) {
            if (n.rel_path === relPath) return n;
            if (n.children) {
              const f = findNode(n.children);
              if (f) return f;
            }
          }
          return null;
        };
        const targetNode = findNode(currentTreeData.tree);
        if (targetNode) {
          const descPaths = collectDescendantPaths(targetNode);
          for (const dp of descPaths) {
            if (isChecked) selectedRelPaths.add(dp);
            else selectedRelPaths.delete(dp);
          }
        }
      }

      updateSelectionBadge();
      renderFileTree();
    });
  });
}

/**
 * Загружает и отображает дерево файлов для указанной директории.
 * @param {string} dirPath 
 * @param {string|null} wsId 
 */
export async function browseDirectory(dirPath = '', wsId = null) {
  currentWorkspaceId = wsId || getActiveWorkspace() || 'default';
  currentDirectory = (dirPath || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');

  const wsBadge = document.getElementById('ft-workspace-badge');
  const pathInput = document.getElementById('ft-path-input');
  const container = document.getElementById('ft-tree-container');

  if (wsBadge) wsBadge.textContent = currentWorkspaceId;
  if (pathInput) pathInput.value = currentDirectory;

  if (container) {
    container.innerHTML = `
      <div class="text-center text-muted py-5 small" id="ft-loading-spinner">
        <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
        <div>Загрузка дерева директории...</div>
      </div>
    `;
  }

  try {
    const url = `/api/v1/file-tree/browse?workspace_id=${encodeURIComponent(currentWorkspaceId)}&dir_path=${encodeURIComponent(currentDirectory)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    currentTreeData = data;
    currentParentDir = data.parent_dir;

    const itemsBadge = document.getElementById('ft-total-items-badge');
    if (itemsBadge) {
      itemsBadge.textContent = `${data.total_files} файлов, ${data.total_dirs} папок`;
    }

    renderBreadcrumbs(data.breadcrumbs || []);
    renderFileTree();
    updateSelectionBadge();
  } catch (err) {
    if (container) {
      container.innerHTML = `
        <div class="p-3 text-danger small" id="ft-error-message">
          <i class="bi bi-exclamation-triangle me-1"></i> Ошибка обзора директории: ${escapeHtml(err.message)}
        </div>
      `;
    }
    showToast(`Ошибка: ${err.message}`, 'danger');
  }
}

/**
 * Показывает контекстное меню при правом клике.
 * @param {MouseEvent} e 
 */
function showContextMenu(e) {
  const menu = document.getElementById('ft-context-menu');
  if (!menu || !activeTargetNode) return;

  const header = document.getElementById('ft-cm-header');
  const summaryItem = document.getElementById('ft-cm-item-summary');
  const editorItem = document.getElementById('ft-cm-item-editor');

  if (header) {
    const icon = activeTargetNode.isDir ? '📁' : '📄';
    header.textContent = `${icon} ${activeTargetNode.name}`;
  }

  // Пункты меню активны/неактивны в зависимости от типа узла
  if (summaryItem) {
    if (activeTargetNode.isDir) {
      summaryItem.classList.add('disabled');
      summaryItem.title = 'Сводка доступна только для файлов';
    } else {
      summaryItem.classList.remove('disabled');
      summaryItem.title = 'Кратко о файле';
    }
  }

  if (editorItem) {
    if (activeTargetNode.isDir) {
      editorItem.classList.add('disabled');
      editorItem.title = 'Редактор доступен только для файлов';
    } else {
      editorItem.classList.remove('disabled');
      editorItem.title = 'Открыть в универсальном Wasm-редакторе';
    }
  }

  const menuWidth = 230;
  const menuHeight = 170;
  let x = e.clientX;
  let y = e.clientY;

  if (x + menuWidth > window.innerWidth) x = Math.max(10, window.innerWidth - menuWidth - 10);
  if (y + menuHeight > window.innerHeight) y = Math.max(10, window.innerHeight - menuHeight - 10);

  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
  menu.classList.remove('d-none');
}

/**
 * Скрывает контекстное меню.
 */
function hideContextMenu() {
  const menu = document.getElementById('ft-context-menu');
  if (menu && !menu.classList.contains('d-none')) {
    menu.classList.add('d-none');
  }
}

/**
 * Открывает файл в универсальном Wasm-редакторе.
 * @param {string} relPath 
 */
async function openFileInEditor(relPath) {
  if (!relPath) return;
  hideContextMenu();

  // Если доступна глобальная функция из tab_file_editor
  if (typeof window.openFileInWasmEditor === 'function') {
    await window.openFileInWasmEditor(relPath, currentWorkspaceId, true);
    return;
  }

  // Гарантированно открываем в tab-workspace#panel-file-editor
  if (typeof window.switchTab === 'function' && typeof window.isTabActive === 'function' && !window.isTabActive('tab-workspace')) {
    await window.switchTab('tab-workspace');
  }
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab('panel-file-editor', true);
  }
  if (typeof window.openFileInWasmEditor === 'function') {
    await window.openFileInWasmEditor(relPath, currentWorkspaceId, true);
  } else {
    showToast(`Открытие ${relPath} в редакторе...`, 'info');
  }
}

/**
 * Открывает модальное окно с краткой аналитической сводкой по файлу.
 * @param {string} relPath 
 */
async function openSummaryModal(relPath) {
  hideContextMenu();
  if (!relPath) return;

  const modalEl = document.getElementById('modal-ft-file-summary');
  if (!modalEl || !window.bootstrap) return;

  const nameEl = document.getElementById('ft-summary-file-name');
  const pathEl = document.getElementById('ft-summary-file-relpath');
  const sizeBadge = document.getElementById('ft-summary-size-badge');
  const linesBadge = document.getElementById('ft-summary-lines-badge');
  const langBadge = document.getElementById('ft-summary-lang-badge');
  const essenceText = document.getElementById('ft-summary-essence-text');
  const previewPre = document.getElementById('ft-summary-preview-content');
  const tagsContainer = document.getElementById('ft-summary-tags-container');
  const openEditorBtn = document.getElementById('ft-btn-summary-open-editor');

  if (nameEl) nameEl.textContent = relPath.split('/').pop();
  if (pathEl) pathEl.textContent = relPath;
  if (essenceText) essenceText.innerHTML = '<span class="spinner-border spinner-border-sm text-primary me-1"></span> Загрузка анализа...';
  if (previewPre) previewPre.textContent = '';
  if (tagsContainer) tagsContainer.innerHTML = '';

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  if (openEditorBtn) {
    openEditorBtn.onclick = () => {
      modal.hide();
      openFileInEditor(relPath);
    };
  }

  try {
    const url = `/api/v1/file-tree/summary?workspace_id=${encodeURIComponent(currentWorkspaceId)}&rel_path=${encodeURIComponent(relPath)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (sizeBadge) sizeBadge.textContent = data.size_formatted;
    if (linesBadge) linesBadge.textContent = data.lines_count !== null ? `${data.lines_count} строк` : 'Бинарный';
    if (langBadge) langBadge.textContent = data.language_id;
    if (essenceText) essenceText.textContent = data.summary || 'Краткое описание отсутствует.';
    if (previewPre) previewPre.textContent = data.preview || '';

    if (tagsContainer && Array.isArray(data.tags)) {
      tagsContainer.innerHTML = data.tags.map((t) => `<span class="badge bg-secondary-subtle text-secondary border">${escapeHtml(t)}</span>`).join('');
    }
  } catch (err) {
    if (essenceText) essenceText.textContent = `Ошибка получения сводки: ${err.message}`;
  }
}

/**
 * Открывает диалог создания нового файла или папки в директории клика.
 * @param {string} targetDir 
 */
function openCreateModal(targetDir = '') {
  hideContextMenu();
  const modalEl = document.getElementById('modal-ft-create-item');
  if (!modalEl || !window.bootstrap) return;

  const targetBadge = document.getElementById('ft-create-target-dir-badge');
  const nameInput = document.getElementById('ft-create-name-input');
  const contentInput = document.getElementById('ft-create-content-input');
  const commitInput = document.getElementById('ft-create-commit-input');
  const contentGroup = document.getElementById('ft-create-content-group');
  const radioFile = document.getElementById('ft-create-type-file');
  const radioFolder = document.getElementById('ft-create-type-folder');

  const cleanDir = (targetDir || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  if (targetBadge) targetBadge.textContent = cleanDir ? `/${cleanDir}/` : '/ (Корень)';
  if (nameInput) {
    nameInput.value = '';
    setTimeout(() => nameInput.focus(), 250);
  }
  if (contentInput) contentInput.value = '';
  if (commitInput) commitInput.value = '';
  if (radioFile) radioFile.checked = true;
  if (contentGroup) contentGroup.classList.remove('d-none');

  radioFolder?.addEventListener('change', () => {
    if (radioFolder.checked) contentGroup?.classList.add('d-none');
  });
  radioFile?.addEventListener('change', () => {
    if (radioFile.checked) contentGroup?.classList.remove('d-none');
  });

  const submitBtn = document.getElementById('ft-btn-submit-create');
  if (submitBtn) {
    submitBtn.onclick = async () => {
      const name = (nameInput?.value || '').trim();
      if (!name) {
        showToast('Укажите имя создаваемого объекта', 'warning');
        nameInput?.focus();
        return;
      }

      const isFolder = radioFolder?.checked || false;
      const content = isFolder ? '' : (contentInput?.value || '');
      const commitMsg = commitInput?.value?.trim() || null;

      submitBtn.disabled = true;
      try {
        const res = await fetch('/api/v1/file-tree/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: currentWorkspaceId,
            target_dir: cleanDir,
            name,
            is_dir: isFolder,
            content,
            commit_message: commitMsg,
          }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка создания');

        bootstrap.Modal.getInstance(modalEl)?.hide();
        showToast(`✅ ${isFolder ? 'Папка' : 'Файл'} "${data.rel_path}" успешно создан`, 'success');
        await browseDirectory(currentDirectory);
      } catch (err) {
        showToast(`❌ Ошибка создания: ${err.message}`, 'danger');
      } finally {
        submitBtn.disabled = false;
      }
    };
  }

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

/**
 * Инициализирует вкладку дерева файлов и поддиректорий.
 */
export function initFileTreeTab() {
  if (isInitialized) return;
  isInitialized = true;

  // Кнопка перехода на уровень вверх
  document.getElementById('ft-btn-up-dir')?.addEventListener('click', () => {
    if (currentParentDir !== null) {
      browseDirectory(currentParentDir);
    }
  });

  // Кнопка и поле прямого перехода по пути
  const goBtn = document.getElementById('ft-btn-go-path');
  const pathInput = document.getElementById('ft-path-input');

  goBtn?.addEventListener('click', () => {
    browseDirectory(pathInput?.value || '');
  });
  pathInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      browseDirectory(pathInput.value || '');
    }
  });

  // Кнопка Выбрать все / Снять выбор
  document.getElementById('ft-btn-select-all')?.addEventListener('click', () => {
    if (!currentTreeData || !currentTreeData.tree) return;
    if (selectedRelPaths.size > 0) {
      selectedRelPaths.clear();
    } else {
      const allPaths = [];
      for (const node of currentTreeData.tree) {
        collectDescendantPaths(node, allPaths);
      }
      for (const p of allPaths) selectedRelPaths.add(p);
    }
    updateSelectionBadge();
    renderFileTree();
  });

  // Кнопка Инвертировать выбор
  document.getElementById('ft-btn-invert-selection')?.addEventListener('click', () => {
    if (!currentTreeData || !currentTreeData.tree) return;
    const allPaths = [];
    for (const node of currentTreeData.tree) {
      collectDescendantPaths(node, allPaths);
    }
    for (const p of allPaths) {
      if (selectedRelPaths.has(p)) selectedRelPaths.delete(p);
      else selectedRelPaths.add(p);
    }
    updateSelectionBadge();
    renderFileTree();
  });

  // Развернуть / Свернуть все
  document.getElementById('ft-btn-expand-all')?.addEventListener('click', () => {
    if (!currentTreeData || !currentTreeData.tree) return;
    const collectDirs = (nodes) => {
      for (const n of nodes) {
        if (n.is_dir) {
          expandedFolderPaths.add(n.rel_path);
          if (n.children) collectDirs(n.children);
        }
      }
    };
    collectDirs(currentTreeData.tree);
    renderFileTree();
  });

  document.getElementById('ft-btn-collapse-all')?.addEventListener('click', () => {
    expandedFolderPaths.clear();
    renderFileTree();
  });

  // Фильтр по названию
  document.getElementById('ft-filter-input')?.addEventListener('input', () => {
    renderFileTree();
  });

  // Кнопка Обновить
  document.getElementById('ft-btn-refresh')?.addEventListener('click', () => {
    browseDirectory(currentDirectory);
  });

  // Кнопка Создать в текущей папке
  document.getElementById('ft-btn-new-item')?.addEventListener('click', () => {
    openCreateModal(currentDirectory);
  });

  // Слушатели контекстного меню
  document.getElementById('ft-cm-item-summary')?.addEventListener('click', () => {
    if (activeTargetNode && !activeTargetNode.isDir) {
      openSummaryModal(activeTargetNode.relPath);
    }
  });

  document.getElementById('ft-cm-item-editor')?.addEventListener('click', () => {
    if (activeTargetNode && !activeTargetNode.isDir) {
      openFileInEditor(activeTargetNode.relPath);
    }
  });

  document.getElementById('ft-cm-item-create')?.addEventListener('click', () => {
    if (activeTargetNode) {
      openCreateModal(activeTargetNode.parentDir);
    }
  });

  document.getElementById('ft-cm-item-copy-path')?.addEventListener('click', () => {
    if (activeTargetNode) {
      hideContextMenu();
      navigator.clipboard?.writeText(activeTargetNode.relPath);
      showToast(`Скопировано: ${activeTargetNode.relPath}`, 'info');
    }
  });

  // Скрытие контекстного меню при клике вне или по Escape
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#ft-context-menu')) {
      hideContextMenu();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideContextMenu();
  });

  window.addEventListener('scroll', hideContextMenu, true);

  // Первоначальная загрузка
  browseDirectory('');
}

// Экспорт в глобальную область
if (typeof window !== 'undefined') {
  window.initFileTreeTab = initFileTreeTab;
  window.browseDirectoryInTree = browseDirectory;
}

// Автоинициализация при загрузке DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFileTreeTab);
} else {
  initFileTreeTab();
}
