/**
 * =============================================================================
 * Process Name: Common WebGUI - Studio Code Central File Editor Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор центрального окна редактора файлов Studio Code
 *   (apps/common/webgui/tab_file_editor).
 *   Управляет открытыми вкладками файлов в центральной области (#fe-open-tabs-bar),
 *   переключением активного файла, встроенным видеоплеером (HTML5 Video),
 *   аудиоплеером, просмотром изображений, подсчётом строк и символов,
 *   предпросмотром Markdown, автосохранением/сохранением с коммитом в Git (Ctrl+S)
 *   и синхронизацией с навигатором файлов (#ide-file-navigator).
 *
 * File: main.js
 * Project: ai-assistant
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-10 18:15:00
 * =============================================================================
 */

let isInitialized = false;
const openDocuments = new Map(); // key: `${wsId}:${relPath}` -> docState
let activeDocKey = null;

const VIDEO_EXTENSIONS = new Set(['mp4', 'webm', 'ogg', 'ogv', 'mov', 'mkv', 'avi', 'm4v']);
const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'flac', 'aac', 'm4a', 'wma']);
const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'bmp']);

function notifyToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else if (typeof window.showNotificationToast === 'function') {
    window.showNotificationToast(msg, type);
  }
}

function getActiveWorkspaceId() {
  if (typeof window.getActiveWorkspaceId === 'function') {
    const ws = window.getActiveWorkspaceId();
    if (ws) return ws;
  }
  const sel = document.getElementById('top-workspace-select') || document.getElementById('drawer-workspace-select');
  if (sel && sel.value) return sel.value;
  return 'default';
}

function makeDocKey(wsId, relPath) {
  return `${wsId || 'default'}:${(relPath || '').trim()}`;
}

function getFileIconClass(fileName, isMedia, mediaType) {
  if (isMedia) {
    if (mediaType === 'video') return 'bi-file-earmark-play-fill text-danger';
    if (mediaType === 'audio') return 'bi-file-earmark-music-fill text-info';
    if (mediaType === 'image') return 'bi-file-earmark-image-fill text-success';
  }
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  switch (ext) {
    case 'py': return 'bi-filetype-py text-primary';
    case 'js':
    case 'mjs': return 'bi-filetype-js text-warning';
    case 'json': return 'bi-filetype-json text-info';
    case 'html': return 'bi-filetype-html text-danger';
    case 'css': return 'bi-filetype-css text-info';
    case 'md': return 'bi-markdown-fill text-primary';
    case 'svg': return 'bi-filetype-svg text-warning';
    case 'csv': return 'bi-filetype-csv text-success';
    case 'sh':
    case 'ps1': return 'bi-terminal text-success';
    default: return 'bi-file-earmark-text text-secondary';
  }
}

/**
 * Инициализирует модуль редактора при первом монтировании вкладки.
 */
function initFileEditorTab() {
  bindToolbarEvents();
  bindEditorEvents();
  renderTabsBar();
  renderActiveDocument();
}

/**
 * Привязывает обработчики кнопок верхней и нижней панелей.
 */
function bindToolbarEvents() {
  const root = document.getElementById('wasm-file-editor-root');
  if (root && root.dataset.toolbarBound === 'true') return;
  if (root) root.dataset.toolbarBound = 'true';
  // Кнопка сохранения Ctrl+S
  document.getElementById('fe-btn-save')?.addEventListener('click', () => {
    saveActiveDocument();
  });

  // Кнопка Сохранить как...
  document.getElementById('fe-btn-save-as')?.addEventListener('click', () => {
    saveActiveDocumentAs();
  });

  // Кнопка Сохранить все
  document.getElementById('fe-btn-save-all')?.addEventListener('click', () => {
    saveAllDocuments();
  });

  // Кнопка нового файла (+)
  document.getElementById('fe-btn-new-file')?.addEventListener('click', () => {
    handleCreateNewFilePrompt();
  });

  // Кнопка закрытия всех вкладок
  document.getElementById('fe-btn-close-all')?.addEventListener('click', () => {
    closeAllDocuments();
  });

  // Кнопка открытия в системном приложении
  document.getElementById('fe-btn-system-open')?.addEventListener('click', () => {
    handleOpenSystem();
  });
  document.getElementById('fe-btn-binary-open')?.addEventListener('click', () => {
    handleOpenSystem();
  });

  // Переключение режимов Редактор / Вид/Редактор (Split) / Вид
  document.getElementById('fe-tab-mode-code')?.addEventListener('click', () => {
    switchActiveViewMode('code');
  });
  document.getElementById('fe-tab-mode-split')?.addEventListener('click', () => {
    switchActiveViewMode('split');
  });
  document.getElementById('fe-tab-mode-preview')?.addEventListener('click', () => {
    switchActiveViewMode('preview');
  });
}

/**
 * Привязывает обработчики к textarea (счетчики строк, Tab, скролл gutter, Ctrl+S).
 */
function bindEditorEvents() {
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  if (!textarea || textarea.dataset.editorBound === 'true') return;
  textarea.dataset.editorBound = 'true';

  textarea.addEventListener('input', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    doc.content = textarea.value;
    doc.isDirty = (doc.content !== doc.initialContent);
    updateGutter();
    updateCursorAndStats();
    updateActiveTabDirtyIndicator();
    if (doc.viewMode === 'split' || doc.viewMode === 'preview') {
      renderMarkdownPreview();
    }
  });

  textarea.addEventListener('scroll', () => {
    if (gutter) gutter.scrollTop = textarea.scrollTop;
  });

  textarea.addEventListener('keyup', updateCursorAndStats);
  textarea.addEventListener('click', updateCursorAndStats);

  textarea.addEventListener('keydown', (e) => {
    // Поддержка сохранения по Ctrl+S / Cmd+S
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      saveActiveDocument();
      return;
    }

    // Поддержка отступа Tab (2 пробела)
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;
      textarea.value = val.substring(0, start) + '  ' + val.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
      textarea.dispatchEvent(new Event('input'));
    }
  });
}

/**
 * Открывает файл в центральном окне Studio Code в виде вкладки.
 * @param {string} relPath - Относительный путь к файлу
 * @param {string} [wsId] - ID рабочей области
 * @param {boolean} [switchSubtab=true] - Переключить ли субвкладку на panel-file-editor
 */
async function openDocumentInTab(relPath, wsId, switchSubtab = true) {
  if (!relPath) return;
  const currentWs = wsId || getActiveWorkspaceId();
  const docKey = makeDocKey(currentWs, relPath);

  // Переключаем интерфейс на суб-панель редактора
  if (switchSubtab) {
    switchToEditorSubtab();
  }

  // Если файл уже открыт во вкладках — просто активируем её
  if (openDocuments.has(docKey)) {
    activeDocKey = docKey;
    renderTabsBar();
    renderActiveDocument();
    return;
  }

  const fileName = relPath.split('/').pop().split('\\').pop();
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  const isVideo = VIDEO_EXTENSIONS.has(ext);
  const isAudio = AUDIO_EXTENSIONS.has(ext);
  const isImage = IMAGE_EXTENSIONS.has(ext);
  const isMedia = isVideo || isAudio || isImage;
  const mediaType = isVideo ? 'video' : (isAudio ? 'audio' : (isImage ? 'image' : null));
  const rawUrl = `/api/v1/workspaces/${encodeURIComponent(currentWs)}/file-raw?rel_path=${encodeURIComponent(relPath)}`;

  let isBinary = isMedia;
  let initialContent = '';

  // Для не-медиа файлов загружаем текстовое содержимое через API
  if (!isMedia) {
    try {
      const url = `/api/v1/workspaces/${encodeURIComponent(currentWs)}/file-content?rel_path=${encodeURIComponent(relPath)}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        isBinary = Boolean(data.is_binary);
        initialContent = isBinary ? '' : (data.content ?? '');
      } else if (res.status === 404) {
        // Новый файл, ещё не сохранённый на диске
        isBinary = false;
        initialContent = '';
      } else {
        throw new Error(`Ошибка HTTP ${res.status}`);
      }
    } catch (err) {
      console.warn(`[FileEditor] Не удалось загрузить содержимое ${relPath}:`, err);
      notifyToast(`Не удалось прочитать файл: ${err.message}`, 'danger');
      return;
    }
  }

  const docState = {
    wsId: currentWs,
    relPath,
    fileName,
    ext,
    isMedia,
    mediaType,
    rawUrl,
    isBinary,
    content: initialContent,
    initialContent,
    isDirty: false,
    viewMode: 'code',
    cursorLine: 1,
    cursorCol: 1,
  };

  openDocuments.set(docKey, docState);
  activeDocKey = docKey;

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Переключает навигацию рабочей области на суб-панель редактора.
 */
function switchToEditorSubtab() {
  if (typeof window.switchTab === 'function' && typeof window.isTabActive === 'function' && !window.isTabActive('tab-workspace')) {
    window.switchTab('tab-workspace');
  }
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab('panel-file-editor', true);
    return;
  }
  const btn = document.getElementById('subtab-ws-file-editor-btn');
  if (btn) btn.click();
}

/**
 * Возвращает состояние активного документа.
 */
function getActiveDoc() {
  if (!activeDocKey) return null;
  return openDocuments.get(activeDocKey) || null;
}

/**
 * Отрисовывает полосу открытых вкладок.
 */
function renderTabsBar() {
  const bar = document.getElementById('fe-open-tabs-bar');
  if (!bar) return;

  bar.innerHTML = '';
  if (openDocuments.size === 0) {
    return;
  }

  for (const [key, doc] of openDocuments.entries()) {
    const isActive = (key === activeDocKey);
    const tabEl = document.createElement('div');
    tabEl.className = `wasm-tab-item d-flex align-items-center gap-1.5 px-2.5 py-1 rounded-top small border-end border-subtle ${isActive ? 'active' : ''}`;
    tabEl.style.cursor = 'pointer';

    const iconClass = getFileIconClass(doc.fileName, doc.isMedia, doc.mediaType);
    tabEl.innerHTML = `
      <i class="bi ${iconClass}"></i>
      <span class="wasm-tab-title text-truncate" style="max-width: 140px;" title="${doc.relPath}">${doc.fileName}</span>
      <span class="wasm-tab-dirty text-warning ${doc.isDirty ? '' : 'd-none'}">●</span>
      <button type="button" class="btn-close btn-close-white wasm-tab-close p-0 ms-1" style="font-size: 0.65rem;" title="Закрыть вкладку"></button>
    `;

    // Клик по вкладке — активация
    tabEl.addEventListener('click', (e) => {
      if (e.target.closest('.wasm-tab-close')) return;
      activeDocKey = key;
      renderTabsBar();
      renderActiveDocument();
    });

    // Правый клик (ПКМ) по вкладке — вызов контекстного меню вкладки (VS Code Style)
    tabEl.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      e.stopPropagation();
      showTabContextMenu(e.clientX, e.clientY, key);
    });

    // Клик по крестику — закрытие вкладки
    tabEl.querySelector('.wasm-tab-close')?.addEventListener('click', (e) => {
      e.stopPropagation();
      closeDocument(key);
    });

    bar.appendChild(tabEl);
  }
}

/**
 * Закрывает указанную вкладку документа.
 */
function closeDocument(key) {
  const doc = openDocuments.get(key);
  if (!doc) return;

  if (doc.isDirty) {
    const ok = confirm(`Файл "${doc.fileName}" имеет несохранённые изменения. Закрыть без сохранения?`);
    if (!ok) return;
  }

  // Если закрывается активный медиафайл — останавливаем воспроизведение
  if (doc.isMedia && key === activeDocKey) {
    stopMediaPlayback();
  }

  openDocuments.delete(key);

  if (activeDocKey === key) {
    const remaining = Array.from(openDocuments.keys());
    activeDocKey = remaining.length > 0 ? remaining[remaining.length - 1] : null;
  }

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Закрывает все открытые вкладки.
 */
function closeAllDocuments() {
  let hasDirty = false;
  for (const doc of openDocuments.values()) {
    if (doc.isDirty) {
      hasDirty = true;
      break;
    }
  }
  if (hasDirty) {
    const ok = confirm('Есть несохранённые файлы. Закрыть все вкладки без сохранения?');
    if (!ok) return;
  }

  stopMediaPlayback();
  openDocuments.clear();
  activeDocKey = null;

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Останавливает воспроизведение встроенных плееров.
 */
function stopMediaPlayback() {
  const video = document.getElementById('fe-media-video');
  const audio = document.getElementById('fe-media-audio');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
  if (audio) {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
  }
}

/**
 * Отрисовывает содержимое активного документа на центральной сцене.
 */
function renderActiveDocument() {
  const emptyState = document.getElementById('fe-empty-state');
  const binaryNotice = document.getElementById('fe-binary-notice');
  const textStage = document.getElementById('fe-text-stage');
  const mediaStage = document.getElementById('fe-media-stage');

  const fileNameEl = document.getElementById('fe-active-file-name');
  const filePathEl = document.getElementById('fe-active-file-path');
  const fileIconEl = document.getElementById('fe-active-file-icon');
  const viewModeGroup = document.getElementById('fe-view-mode-group');
  const btnSave = document.getElementById('fe-btn-save');
  const textarea = document.getElementById('fe-code-textarea');

  const video = document.getElementById('fe-media-video');
  const audioContainer = document.getElementById('fe-media-audio-container');
  const audio = document.getElementById('fe-media-audio');
  const image = document.getElementById('fe-media-image');

  // Всегда сначала приостанавливаем текущий поток медиа при смене документа
  stopMediaPlayback();

  const doc = getActiveDoc();

  // Если нет открытых вкладок
  if (!doc) {
    if (emptyState) emptyState.classList.remove('d-none');
    if (binaryNotice) binaryNotice.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (mediaStage) mediaStage.classList.add('d-none');

    if (fileNameEl) fileNameEl.textContent = 'Файл не выбран';
    if (filePathEl) filePathEl.textContent = '---';
    if (fileIconEl) fileIconEl.className = 'bi bi-file-earmark-code text-primary fs-5';
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;

    updateCursorAndStats();
    return;
  }

  // Скрываем заглушку "нет файлов"
  if (emptyState) emptyState.classList.add('d-none');

  // Обновляем шапку активного файла
  if (fileNameEl) fileNameEl.textContent = doc.fileName;
  if (filePathEl) filePathEl.textContent = doc.relPath;
  if (fileIconEl) {
    const iconClass = getFileIconClass(doc.fileName, doc.isMedia, doc.mediaType);
    fileIconEl.className = `bi ${iconClass} fs-5`;
  }

  // 1. СЛУЧАЙ: ВСТРОЕННЫЙ МЕДИАПЛЕЕР (Видео, Аудио, Картинки)
  if (doc.isMedia) {
    if (binaryNotice) binaryNotice.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;

    if (mediaStage) mediaStage.classList.remove('d-none');

    if (doc.mediaType === 'video') {
      if (video) {
        video.classList.remove('d-none');
        video.src = doc.rawUrl;
      }
      if (audioContainer) audioContainer.classList.add('d-none');
      if (image) image.classList.add('d-none');
      setStatsText('Видеофайл • Встроенный видеоплеер');
    } else if (doc.mediaType === 'audio') {
      if (video) video.classList.add('d-none');
      if (audioContainer) {
        audioContainer.classList.remove('d-none');
        const titleEl = document.getElementById('fe-media-audio-title');
        if (titleEl) titleEl.textContent = doc.fileName;
      }
      if (audio) {
        audio.src = doc.rawUrl;
      }
      if (image) image.classList.add('d-none');
      setStatsText('Аудиозапись • Встроенный аудиоплеер');
    } else if (doc.mediaType === 'image') {
      if (video) video.classList.add('d-none');
      if (audioContainer) audioContainer.classList.add('d-none');
      if (image) {
        image.classList.remove('d-none');
        image.src = doc.rawUrl;
      }
      setStatsText('Изображение • Предпросмотр');
    }
    return;
  }

  // 2. СЛУЧАЙ: НЕИЗВЕСТНЫЙ БИНАРНЫЙ ФАЙЛ
  if (doc.isBinary) {
    if (mediaStage) mediaStage.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (binaryNotice) binaryNotice.classList.remove('d-none');
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;
    setStatsText('Бинарный файл');
    return;
  }

  // 3. СЛУЧАЙ: ТЕКСТОВЫЙ / CODE / MARKDOWN ФАЙЛ
  if (mediaStage) mediaStage.classList.add('d-none');
  if (binaryNotice) binaryNotice.classList.add('d-none');
  if (textStage) textStage.classList.remove('d-none');
  if (btnSave) btnSave.disabled = false;

  // Показываем переключатель "Редактор / Вид/Редактор / Вид" для всех текстовых файлов
  if (viewModeGroup) {
    viewModeGroup.classList.remove('d-none');
  }

  if (textarea) {
    textarea.value = doc.content ?? '';
  }

  updateGutter();
  updateCursorAndStats();
  applyViewMode(doc.viewMode || 'code');
}

function setStatsText(txt) {
  const statsEl = document.getElementById('fe-editor-stats');
  if (statsEl) statsEl.textContent = txt;
}

/**
 * Переключает режим отображения Редактор / Вид/Редактор / Вид.
 * @param {'code'|'split'|'preview'} mode
 */
function switchActiveViewMode(mode) {
  const doc = getActiveDoc();
  if (!doc) return;
  doc.viewMode = mode;
  applyViewMode(mode);
}

function applyViewMode(mode) {
  const btnCode = document.getElementById('fe-tab-mode-code');
  const btnSplit = document.getElementById('fe-tab-mode-split');
  const btnPrev = document.getElementById('fe-tab-mode-preview');
  const textStage = document.getElementById('fe-text-stage');
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  const preview = document.getElementById('fe-markdown-preview');

  if (!textStage) return;

  btnCode?.classList.toggle('active', mode === 'code');
  btnSplit?.classList.toggle('active', mode === 'split');
  btnPrev?.classList.toggle('active', mode === 'preview');

  textStage.classList.remove('wasm-split-mode', 'wasm-preview-mode');

  if (mode === 'split') {
    textStage.classList.add('wasm-split-mode');
    if (gutter) gutter.classList.remove('d-none');
    if (textarea) textarea.classList.remove('d-none');
    if (preview) {
      preview.classList.remove('d-none');
      renderMarkdownPreview();
    }
  } else if (mode === 'preview') {
    textStage.classList.add('wasm-preview-mode');
    if (gutter) gutter.classList.add('d-none');
    if (textarea) textarea.classList.add('d-none');
    if (preview) {
      preview.classList.remove('d-none');
      renderMarkdownPreview();
    }
  } else {
    // Режим 'code' (Только редактор)
    if (gutter) gutter.classList.remove('d-none');
    if (textarea) textarea.classList.remove('d-none');
    if (preview) preview.classList.add('d-none');
  }
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeAttr(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Рендерит предпросмотр документа в зависимости от его формата (Markdown, HTML, SVG, CSV, JSON и др.).
 */
function renderMarkdownPreview() {
  const doc = getActiveDoc();
  const preview = document.getElementById('fe-markdown-preview');
  if (!doc || !preview) return;

  const raw = doc.content || '';
  const ext = (doc.ext || '').toLowerCase();

  // 1. Markdown
  if (ext === 'md' || ext === 'markdown') {
    if (typeof window.marked === 'function') {
      preview.innerHTML = window.marked(raw);
    } else if (typeof window.marked?.parse === 'function') {
      preview.innerHTML = window.marked.parse(raw);
    } else {
      preview.innerHTML = `<pre class="m-0 font-monospace small" style="white-space: pre-wrap; line-height: 1.5;">${escapeHtml(raw)}</pre>`;
    }
    return;
  }

  // 2. HTML
  if (ext === 'html' || ext === 'htm') {
    preview.innerHTML = `
      <iframe class="w-100 h-100 border-0 bg-body rounded shadow-xs"
              sandbox="allow-scripts allow-same-origin"
              style="min-height: 420px;"
              srcdoc="${escapeAttr(raw)}"></iframe>
    `;
    return;
  }

  // 3. SVG
  if (ext === 'svg') {
    preview.innerHTML = `
      <div class="d-flex align-items-center justify-content-center p-3 h-100 bg-body-tertiary rounded border border-subtle">
        ${raw}
      </div>
    `;
    return;
  }

  // 4. CSV / TSV
  if (ext === 'csv' || ext === 'tsv') {
    const delimiter = ext === 'tsv' ? '\t' : ',';
    const lines = raw.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length > 0) {
      const rows = lines.map(line => line.split(delimiter).map(c => c.replace(/^"|"$/g, '')));
      const thead = rows[0].map(h => `<th class="px-2 py-1 bg-body-tertiary">${escapeHtml(h)}</th>`).join('');
      const tbody = rows.slice(1).map(r => `<tr>${r.map(c => `<td class="px-2 py-1 font-monospace small">${escapeHtml(c)}</td>`).join('')}</tr>`).join('');
      preview.innerHTML = `
        <div class="table-responsive h-100">
          <table class="table table-sm table-bordered table-hover mb-0">
            <thead><tr>${thead}</tr></thead>
            <tbody>${tbody}</tbody>
          </table>
        </div>
      `;
      return;
    }
  }

  // 5. JSON
  if (ext === 'json') {
    try {
      const parsed = JSON.parse(raw);
      const pretty = JSON.stringify(parsed, null, 2);
      preview.innerHTML = `<pre class="m-0 font-monospace small" style="white-space: pre-wrap; line-height: 1.5;">${escapeHtml(pretty)}</pre>`;
      return;
    } catch (_) {
      // Игнорируем синтаксическую ошибку в процессе набора
    }
  }

  // 6. Общий просмотр для исходного кода и текста
  preview.innerHTML = `<pre class="m-0 font-monospace small" style="white-space: pre-wrap; line-height: 1.5;">${escapeHtml(raw)}</pre>`;
}

/**
 * Обновляет нумерацию строк слева от редактора.
 */
function updateGutter() {
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  if (!textarea || !gutter) return;

  const lines = (textarea.value || '').split('\n').length;
  let numbers = '';
  for (let i = 1; i <= lines; i++) {
    numbers += i + '\n';
  }
  gutter.textContent = numbers;
}

/**
 * Обновляет позицию курсора и статистику символов/строк.
 */
function updateCursorAndStats() {
  const doc = getActiveDoc();
  const textarea = document.getElementById('fe-code-textarea');
  const cursorEl = document.getElementById('fe-editor-cursor');
  const statsEl = document.getElementById('fe-editor-stats');

  if (!doc) {
    if (cursorEl) cursorEl.textContent = 'Ln 1, Col 1';
    if (statsEl) statsEl.textContent = 'Строк: 0 | Символов: 0';
    return;
  }

  if (doc.isMedia || doc.isBinary) {
    if (cursorEl) cursorEl.textContent = '---';
    return;
  }

  if (!textarea) return;

  const val = textarea.value || '';
  const selStart = textarea.selectionStart || 0;
  const upToCursor = val.substring(0, selStart);
  const lines = upToCursor.split('\n');
  const curLine = lines.length;
  const curCol = lines[lines.length - 1].length + 1;

  if (cursorEl) cursorEl.textContent = `Ln ${curLine}, Col ${curCol}`;
  const totalLines = val.split('\n').length;
  const totalChars = val.length;
  if (statsEl) statsEl.textContent = `Строк: ${totalLines} | Символов: ${totalChars}`;
}

/**
 * Обновляет индикатор несохранённых правок (желтая точка) на активной вкладке.
 */
function updateActiveTabDirtyIndicator() {
  const doc = getActiveDoc();
  if (!doc) return;
  const bar = document.getElementById('fe-open-tabs-bar');
  if (!bar) return;
  const activeTab = bar.querySelector('.wasm-tab-item.active .wasm-tab-dirty');
  if (activeTab) {
    if (doc.isDirty) {
      activeTab.classList.remove('d-none');
    } else {
      activeTab.classList.add('d-none');
    }
  }
}

/**
 * Сохраняет активный документ через POST /api/v1/workspaces/{workspace_id}/file-content.
 */

/**
 * Закрывает все открытые вкладки, кроме указанной.
 * @param {string} keepKey
 */
function closeOtherDocuments(keepKey) {
  for (const key of Array.from(openDocuments.keys())) {
    if (key !== keepKey) {
      closeDocument(key);
    }
  }
}

/**
 * Сохраняет активный документ под новым именем/путем (Save As, Ctrl+Shift+S).
 */
async function saveActiveDocumentAs() {
  const doc = getActiveDoc();
  if (!doc) return;
  const currentWs = doc.wsId || getActiveWorkspaceId();
  const defaultName = doc.relPath;
  const newPath = prompt('Сохранить файл как (укажите путь/имя файла):', defaultName);
  if (!newPath || !newPath.trim()) return;

  const cleanPath = newPath.trim().replace(/^[\\/]+/, '');
  if (cleanPath === doc.relPath) {
    await saveActiveDocument();
    return;
  }

  try {
    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(currentWs)}/file-content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: cleanPath,
        content: doc.content,
        commit_message: `Сохранить как ${cleanPath}`,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    notifyToast(`Файл сохранён как "${cleanPath}"`, 'success');
    await openDocumentInTab(cleanPath, currentWs, true);
    if (typeof window.refreshFileTree === 'function') {
      await window.refreshFileTree(currentWs);
    }
  } catch (err) {
    console.error('[FileEditor] Ошибка Save As:', err);
    notifyToast(`Не удалось сохранить как: ${err.message}`, 'danger');
  }
}

/**
 * Сохраняет все измененные документы рабочей области (Save All, Ctrl+Alt+S / Ctrl+K S).
 */
async function saveAllDocuments() {
  const dirtyDocs = [];
  for (const doc of openDocuments.values()) {
    if (doc.isDirty && !doc.isBinary && !doc.isMedia) {
      dirtyDocs.push(doc);
    }
  }

  if (dirtyDocs.length === 0) {
    notifyToast('Все файлы уже сохранены', 'info');
    return;
  }

  let savedCount = 0;
  for (const doc of dirtyDocs) {
    try {
      const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(doc.wsId)}/file-content`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rel_path: doc.relPath,
          content: doc.content,
          commit_message: `Сохранить все: ${doc.fileName}`,
        }),
      });
      if (res.ok) {
        doc.initialContent = doc.content;
        doc.isDirty = false;
        savedCount++;
      }
    } catch (err) {
      console.warn(`[FileEditor] Не удалось сохранить ${doc.fileName}:`, err);
    }
  }

  renderTabsBar();
  renderActiveDocument();
  notifyToast(`Успешно сохранено файлов: ${savedCount} из ${dirtyDocs.length}`, 'success');

  const cur = getActiveDoc();
  if (cur && typeof window.refreshFileTree === 'function') {
    await window.refreshFileTree(cur.wsId);
  }
}

/**
 * Отображает всплывающее контекстное меню по ПКМ для вкладки редактора.
 */
function showTabContextMenu(clientX, clientY, docKey) {
  let menu = document.getElementById('fe-tab-context-menu');
  if (!menu) {
    menu = document.createElement('div');
    menu.id = 'fe-tab-context-menu';
    menu.className = 'custom-context-menu shadow-lg';
    document.body.appendChild(menu);
  }

  const doc = openDocuments.get(docKey);
  if (!doc) return;

  menu.innerHTML = `
    <div class="custom-context-menu-header">${doc.fileName}</div>
    <div class="custom-context-menu-item" data-tab-action="close">
      <span class="custom-context-menu-icon"><i class="bi bi-x-lg"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.closeTab">Закрыть</span>
      <span class="custom-context-menu-shortcut font-monospace text-muted font-size-75">Ctrl+W</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="close-others">
      <span class="custom-context-menu-icon"><i class="bi bi-x-square"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.closeOtherTabs">Закрыть другие</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="close-all">
      <span class="custom-context-menu-icon"><i class="bi bi-trash"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.closeAllTabs">Закрыть все</span>
    </div>
    <div class="custom-context-menu-divider"></div>
    <div class="custom-context-menu-item" data-tab-action="save">
      <span class="custom-context-menu-icon"><i class="bi bi-floppy text-primary"></i></span>
      <span class="custom-context-menu-label" data-i18n="fileEditor.saveBtn">Сохранить</span>
      <span class="custom-context-menu-shortcut font-monospace text-muted font-size-75">Ctrl+S</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="save-as">
      <span class="custom-context-menu-icon"><i class="bi bi-save2 text-info"></i></span>
      <span class="custom-context-menu-label" data-i18n="fileEditor.saveAsBtn">Сохранить как...</span>
      <span class="custom-context-menu-shortcut font-monospace text-muted font-size-75">Ctrl+Shift+S</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="save-all">
      <span class="custom-context-menu-icon"><i class="bi bi-collection text-success"></i></span>
      <span class="custom-context-menu-label" data-i18n="fileEditor.saveAllBtn">Сохранить все</span>
      <span class="custom-context-menu-shortcut font-monospace text-muted font-size-75">Ctrl+Alt+S</span>
    </div>
    <div class="custom-context-menu-divider"></div>
    <div class="custom-context-menu-item" data-tab-action="copy-path">
      <span class="custom-context-menu-icon"><i class="bi bi-clipboard"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.copyPath">Копировать путь</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="copy-rel-path">
      <span class="custom-context-menu-icon"><i class="bi bi-clipboard-check"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.copyRelPath">Копировать относительный путь</span>
    </div>
    <div class="custom-context-menu-item" data-tab-action="reveal">
      <span class="custom-context-menu-icon"><i class="bi bi-box-arrow-up-right"></i></span>
      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.reveal">Показать в проводнике</span>
    </div>
  `;

  menu.style.position = 'fixed';
  menu.style.left = `${Math.min(clientX, window.innerWidth - 240)}px`;
  menu.style.top = `${Math.min(clientY, window.innerHeight - 340)}px`;
  menu.style.zIndex = '10500';
  menu.classList.remove('d-none');

  const closeMenu = () => {
    menu.classList.add('d-none');
    document.removeEventListener('click', closeMenu);
    document.removeEventListener('keydown', onEsc);
  };
  const onEsc = (e) => { if (e.key === 'Escape') closeMenu(); };
  setTimeout(() => {
    document.addEventListener('click', closeMenu);
    document.addEventListener('keydown', onEsc);
  }, 10);

  menu.onclick = async (e) => {
    const item = e.target.closest('.custom-context-menu-item');
    if (!item) return;
    const action = item.dataset.tabAction;
    closeMenu();
    activeDocKey = docKey;
    renderTabsBar();
    renderActiveDocument();

    switch (action) {
      case 'close':
        closeDocument(docKey);
        break;
      case 'close-others':
        closeOtherDocuments(docKey);
        break;
      case 'close-all':
        closeAllDocuments();
        break;
      case 'save':
        await saveActiveDocument();
        break;
      case 'save-as':
        await saveActiveDocumentAs();
        break;
      case 'save-all':
        await saveAllDocuments();
        break;
      case 'copy-path':
        await navigator.clipboard.writeText(doc.relPath);
        notifyToast(`Путь скопирован: ${doc.relPath}`, 'info');
        break;
      case 'copy-rel-path':
        await navigator.clipboard.writeText(doc.relPath);
        notifyToast(`Относительный путь скопирован: ${doc.relPath}`, 'info');
        break;
      case 'reveal':
        handleOpenSystem();
        break;
    }
  };
}

// Глобальные клавиатурные сокращения Studio Code
let chordPending = false;
let chordTimeout = null;

if (typeof document !== 'undefined') {
  document.addEventListener('keydown', (e) => {
    const editorRoot = document.getElementById('wasm-file-editor-root');
    if (!editorRoot || editorRoot.offsetParent === null) return;

    // Аккорд Ctrl+K S (Save All)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      chordPending = true;
      clearTimeout(chordTimeout);
      chordTimeout = setTimeout(() => { chordPending = false; }, 1500);
      return;
    }

    if (chordPending && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      chordPending = false;
      saveAllDocuments();
      return;
    }

    // Сохранить (Ctrl+S), Сохранить как (Ctrl+Shift+S), Сохранить все (Ctrl+Alt+S)
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      if (e.shiftKey) {
        saveActiveDocumentAs();
      } else if (e.altKey) {
        saveAllDocuments();
      } else {
        saveActiveDocument();
      }
      return;
    }

    // Закрыть активную вкладку (Ctrl+W)
    if ((e.ctrlKey || e.metaKey) && (e.key === 'w' || e.key === 'W')) {
      e.preventDefault();
      const active = getActiveDoc();
      if (active) {
        closeDocument(activeDocKey);
      }
      return;
    }
  });
}

async function saveActiveDocument() {
  const doc = getActiveDoc();
  if (!doc || doc.isBinary || doc.isMedia) return;

  const btnSave = document.getElementById('fe-btn-save');
  const commitInput = document.getElementById('fe-commit-msg-input');
  const statusBadge = document.getElementById('fe-save-status');

  const commitMsg = commitInput?.value?.trim() || `Правка файла ${doc.fileName}`;

  try {
    if (btnSave) btnSave.disabled = true;
    if (statusBadge) {
      statusBadge.textContent = 'Сохранение...';
      statusBadge.className = 'badge bg-warning-subtle text-warning';
    }

    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(doc.wsId)}/file-content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: doc.relPath,
        content: doc.content,
        commit_message: commitMsg,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Ошибка ${res.status}`);
    }

    doc.initialContent = doc.content;
    doc.isDirty = false;
    updateActiveTabDirtyIndicator();

    if (commitInput) commitInput.value = '';
    if (statusBadge) {
      statusBadge.textContent = 'Сохранено в Git';
      statusBadge.className = 'badge bg-success-subtle text-success';
      setTimeout(() => {
        statusBadge.textContent = '';
      }, 3000);
    }
    notifyToast(`Файл "${doc.fileName}" успешно сохранён`, 'success');
  } catch (err) {
    console.error('[FileEditor] Ошибка сохранения файла:', err);
    notifyToast(`Ошибка сохранения: ${err.message}`, 'danger');
    if (statusBadge) {
      statusBadge.textContent = 'Ошибка сохранения';
      statusBadge.className = 'badge bg-danger-subtle text-danger';
    }
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
}

/**
 * Открывает диалог создания нового файла.
 */
function handleCreateNewFilePrompt() {
  const name = prompt('Введите имя нового файла (например, app.py или notes.md):');
  if (!name || !name.trim()) return;
  const relPath = name.trim();
  const currentWs = getActiveWorkspaceId();
  openDocumentInTab(relPath, currentWs, true);
}

/**
 * Открывает текущий файл в ассоциированном системном приложении Windows.
 */
async function handleOpenSystem() {
  const doc = getActiveDoc();
  if (!doc) return;

  try {
    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(doc.wsId)}/open-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: doc.relPath }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    notifyToast(`Файл ${doc.fileName} открывается в системе`, 'info');
  } catch (err) {
    notifyToast(`Не удалось открыть файл в системе: ${err.message}`, 'warning');
  }
}

// Экспорт для глобального использования из дерева файлов и контекстного меню
if (typeof window !== 'undefined') {
  window.initFileEditorTab = initFileEditorTab;
  window.openFileInCentralEditor = openDocumentInTab;
  window.openFileInWasmEditor = openDocumentInTab;
  window.switchActiveViewMode = switchActiveViewMode;
}

export {
  initFileEditorTab,
  openDocumentInTab,
  saveActiveDocument,
  saveActiveDocumentAs,
  saveAllDocuments,
  closeOtherDocuments,
  switchActiveViewMode,
  applyViewMode,
  openDocumentInTab as openFileInWasmEditor,
  openDocumentInTab as openFileInCentralEditor,
};

export default {
  initFileEditorTab,
  openDocumentInTab,
  saveActiveDocument,
  saveActiveDocumentAs,
  saveAllDocuments,
  closeOtherDocuments,
  switchActiveViewMode,
  applyViewMode,
  openFileInWasmEditor: openDocumentInTab,
  openFileInCentralEditor: openDocumentInTab,
};
