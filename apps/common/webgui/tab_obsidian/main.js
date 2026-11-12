/**
 * =============================================================================
 * Process Name: Common WebGUI - Obsidian Knowledge Base Client Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор вкладки базы знаний Obsidian
 *   (apps/common/webgui/tab_obsidian).
 *   Управляет:
 *   - Загрузкой сводки хранилища, фильтрацией заметок по поиску и тегам.
 *   - Редактированием Markdown, Split-предпросмотром, кликабельными вики-ссылками
 *     [[...]] и интерактивными чекбоксами задач.
 *   - Интерактивным 2D-графом связей (Graph View) через panel_graph_view.js.
 *   - Инспектором связей и обратных ссылок через panel_backlinks.js.
 *   - Созданием новых и ежедневных заметок (Daily Notes) с фиксацией в Git.
 *
 * File: main.js
 * Project: ai-assistant
 * Package: apps.common.webgui.tab_obsidian
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 16:45:00
 * =============================================================================
 */

import { fetchAndRenderGraph } from './panel_graph_view.js';
import { fetchBacklinksData } from './panel_backlinks.js';

let isInitialized = false;
let activeNotePath = null;
let activeTagFilter = null;
let currentMode = 'split';
let notesList = [];

function t(key, fallback = '') {
  if (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function') {
    return window.i18n.t(key, fallback);
  }
  return fallback;
}

export async function initObsidianTab() {
  if (isInitialized) return;
  isInitialized = true;

  bindObsidianEvents();
  await loadVaultSummary();
  await loadNotesList();

  if (notesList.length > 0) {
    await openNote(notesList[0].rel_path);
  }
}

function bindObsidianEvents() {
  const modeEdit = document.getElementById('obs-mode-btn-edit');
  const modeSplit = document.getElementById('obs-mode-btn-split');
  const modePrev = document.getElementById('obs-mode-btn-preview');
  const modeGraph = document.getElementById('obs-mode-btn-graph');

  if (modeEdit) modeEdit.onclick = () => setViewMode('edit');
  if (modeSplit) modeSplit.onclick = () => setViewMode('split');
  if (modePrev) modePrev.onclick = () => setViewMode('preview');
  if (modeGraph) modeGraph.onclick = () => setViewMode('graph');

  const graphClose = document.getElementById('obs-graph-close-btn');
  if (graphClose) graphClose.onclick = () => setViewMode('split');

  const btnNew = document.getElementById('obs-btn-new-note');
  if (btnNew) {
    btnNew.onclick = () => {
      const modalEl = document.getElementById('modal-obsidian-create-note');
      if (modalEl && window.bootstrap) new window.bootstrap.Modal(modalEl).show();
    };
  }

  const btnConfirmCreate = document.getElementById('obs-btn-confirm-create-note');
  if (btnConfirmCreate) {
    btnConfirmCreate.onclick = async () => {
      const titleInput = document.getElementById('obs-new-note-title');
      const folderInput = document.getElementById('obs-new-note-folder');
      const title = titleInput ? titleInput.value.trim() : '';
      const folder = folderInput ? folderInput.value.trim() : '';
      if (!title) return;

      await createNote({ title, folder, is_daily: false });
      const modalEl = document.getElementById('modal-obsidian-create-note');
      if (modalEl && window.bootstrap) {
        const inst = window.bootstrap.Modal.getInstance(modalEl);
        if (inst) inst.hide();
      }
      if (titleInput) titleInput.value = '';
    };
  }

  const btnDaily = document.getElementById('obs-btn-daily-note');
  if (btnDaily) btnDaily.onclick = () => createNote({ title: 'Daily', is_daily: true });

  const btnRefresh = document.getElementById('obs-btn-refresh-vault');
  if (btnRefresh) {
    btnRefresh.onclick = async () => {
      await loadVaultSummary();
      await loadNotesList();
      if (activeNotePath) await openNote(activeNotePath);
    };
  }

  const searchInput = document.getElementById('obs-search-notes-input');
  if (searchInput) {
    let debounceTimer = null;
    searchInput.oninput = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => loadNotesList(), 250);
    };
  }

  const btnClearSearch = document.getElementById('obs-btn-clear-search');
  if (btnClearSearch && searchInput) {
    btnClearSearch.onclick = () => { searchInput.value = ''; loadNotesList(); };
  }

  const btnResetTag = document.getElementById('obs-btn-reset-tag-filter');
  if (btnResetTag) {
    btnResetTag.onclick = () => { activeTagFilter = null; loadNotesList(); };
  }

  const btnSave = document.getElementById('obs-btn-save-note');
  if (btnSave) btnSave.onclick = () => saveCurrentNote();

  const textarea = document.getElementById('obs-markdown-textarea');
  if (textarea) {
    let renderTimer = null;
    textarea.oninput = () => {
      clearTimeout(renderTimer);
      renderTimer = setTimeout(() => updateLivePreviewFromEditor(), 300);
    };
    textarea.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveCurrentNote();
      }
    });
  }

  bindMarkdownTools();

  const btnDelete = document.getElementById('obs-btn-delete-note');
  if (btnDelete) {
    btnDelete.onclick = async () => {
      if (!activeNotePath || !confirm(`Удалить заметку "${activeNotePath}"?`)) return;
      await deleteCurrentNote();
    };
  }

  const btnToggleInspector = document.getElementById('obs-btn-toggle-inspector');
  const btnCloseInspector = document.getElementById('obs-btn-close-inspector');
  const rightSidebar = document.getElementById('obs-right-sidebar');
  if (btnToggleInspector && rightSidebar) btnToggleInspector.onclick = () => rightSidebar.classList.toggle('d-none');
  if (btnCloseInspector && rightSidebar) btnCloseInspector.onclick = () => rightSidebar.classList.add('d-none');
}

function bindMarkdownTools() {
  const tools = {
    'obs-tool-h1': '# ',
    'obs-tool-h2': '## ',
    'obs-tool-h3': '### ',
    'obs-tool-bold': ['**', '**'],
    'obs-tool-italic': ['*', '*'],
    'obs-tool-strike': ['~~', '~~'],
    'obs-tool-quote': '> ',
    'obs-tool-wikilink': ['[[', ']]'],
    'obs-tool-tag': '#',
    'obs-tool-task': '- [ ] ',
    'obs-tool-callout': '> [!NOTE] Заголовок\n> Текст callout\n',
    'obs-tool-code': ['```python\n', '\n```'],
    'obs-tool-table': '| Колонка 1 | Колонка 2 |\n|-----------|-----------|\n| Данные 1  | Данные 2  |\n',
    'obs-tool-math': ['$$\n', '\n$$'],
  };

  const textarea = document.getElementById('obs-markdown-textarea');
  if (!textarea) return;

  Object.entries(tools).forEach(([id, insertion]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.onclick = () => {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;

      if (Array.isArray(insertion)) {
        const prefix = insertion[0];
        const suffix = insertion[1];
        const selected = val.substring(start, end) || 'текст';
        textarea.value = val.substring(0, start) + prefix + selected + suffix + val.substring(end);
        textarea.selectionStart = start + prefix.length;
        textarea.selectionEnd = start + prefix.length + selected.length;
      } else {
        textarea.value = val.substring(0, start) + insertion + val.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + insertion.length;
      }
      textarea.focus();
      updateLivePreviewFromEditor();
    };
  });
}

function setViewMode(mode) {
  currentMode = mode;
  ['obs-mode-btn-edit', 'obs-mode-btn-split', 'obs-mode-btn-preview', 'obs-mode-btn-graph'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.classList.remove('active');
  });

  const activeBtn = document.getElementById(`obs-mode-btn-${mode}`);
  if (activeBtn) activeBtn.classList.add('active');

  const editorPane = document.getElementById('obs-editor-pane');
  const resizer = document.getElementById('obs-split-resizer');
  const previewPane = document.getElementById('obs-preview-pane');
  const splitViewport = document.getElementById('obs-split-viewport');
  const graphViewport = document.getElementById('obs-graph-viewport');

  if (mode === 'graph') {
    if (splitViewport) splitViewport.classList.add('d-none');
    if (graphViewport) {
      graphViewport.classList.remove('d-none');
      fetchAndRenderGraph(activeNotePath, (nodeId) => {
        setViewMode('split');
        openNote(nodeId);
      });
    }
    return;
  }

  if (splitViewport) splitViewport.classList.remove('d-none');
  if (graphViewport) graphViewport.classList.add('d-none');

  if (mode === 'edit') {
    if (editorPane) editorPane.classList.remove('d-none');
    if (resizer) resizer.classList.add('d-none');
    if (previewPane) previewPane.classList.add('d-none');
  } else if (mode === 'preview') {
    if (editorPane) editorPane.classList.add('d-none');
    if (resizer) resizer.classList.add('d-none');
    if (previewPane) previewPane.classList.remove('d-none');
  } else {
    if (editorPane) editorPane.classList.remove('d-none');
    if (resizer) resizer.classList.remove('d-none');
    if (previewPane) previewPane.classList.remove('d-none');
  }
}

async function loadVaultSummary() {
  try {
    const res = await fetch('/api/v1/obsidian/vault');
    if (!res.ok) return;
    const data = await res.json();

    const nameBadge = document.getElementById('obs-vault-name-badge');
    if (nameBadge) nameBadge.textContent = data.vault_name || 'Vault';

    const notesVal = document.getElementById('obs-stat-notes-val');
    if (notesVal) notesVal.textContent = data.total_notes;

    const linksVal = document.getElementById('obs-stat-links-val');
    if (linksVal) linksVal.textContent = data.total_links;

    const tagsVal = document.getElementById('obs-stat-tags-val');
    if (tagsVal) tagsVal.textContent = data.total_tags;

    const orphansVal = document.getElementById('obs-stat-orphans-val');
    if (orphansVal) orphansVal.textContent = data.orphan_notes_count;

    renderTagCloud(data.tags_cloud || {});
  } catch (err) {
    console.warn('[Obsidian] Ошибка загрузки сводки:', err);
  }
}

function renderTagCloud(tagsCloud) {
  const container = document.getElementById('obs-tag-pills-list');
  if (!container) return;
  container.innerHTML = '';

  Object.entries(tagsCloud).forEach(([tag, count]) => {
    const pill = document.createElement('span');
    pill.className = `obs-tag-pill badge ${activeTagFilter === tag ? 'bg-primary' : 'bg-body-secondary text-body'} border`;
    pill.textContent = `#${tag} (${count})`;
    pill.onclick = () => {
      activeTagFilter = (activeTagFilter === tag) ? null : tag;
      loadNotesList();
    };
    container.appendChild(pill);
  });
}

async function loadNotesList() {
  const searchInput = document.getElementById('obs-search-notes-input');
  const searchVal = searchInput ? searchInput.value.trim() : '';

  let url = '/api/v1/obsidian/notes?';
  const params = new URLSearchParams();
  if (searchVal) params.append('search', searchVal);
  if (activeTagFilter) params.append('tag', activeTagFilter);

  try {
    const res = await fetch(url + params.toString());
    if (!res.ok) return;
    notesList = await res.json();

    const counter = document.getElementById('obs-filtered-notes-count');
    if (counter) counter.textContent = notesList.length;

    renderNotesItems();
  } catch (err) {
    console.warn('[Obsidian] Ошибка загрузки заметок:', err);
  }
}

function renderNotesItems() {
  const container = document.getElementById('obs-notes-items-list');
  if (!container) return;
  container.innerHTML = '';

  if (notesList.length === 0) {
    container.innerHTML = '<div class="text-muted small text-center p-3">Заметки не найдены</div>';
    return;
  }

  notesList.forEach(note => {
    const item = document.createElement('div');
    item.className = `obs-note-item d-flex flex-column gap-1 mb-1 ${activeNotePath === note.rel_path ? 'active' : ''}`;
    item.onclick = () => openNote(note.rel_path);

    item.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <span class="fw-medium text-truncate font-size-90">${note.title}</span>
        <span class="badge bg-secondary-subtle text-secondary font-size-75" title="Входящих ссылок: ${note.backlinks_count}">🔗 ${note.backlinks_count}</span>
      </div>
      <div class="d-flex align-items-center justify-content-between text-muted small font-size-75">
        <span class="text-truncate font-monospace">${note.folder || '/'}</span>
        <span>${note.word_count} сл.</span>
      </div>
    `;
    container.appendChild(item);
  });
}

export async function openNote(relPath) {
  try {
    const res = await fetch(`/api/v1/obsidian/note?rel_path=${encodeURIComponent(relPath)}`);
    if (!res.ok) return;
    const data = await res.json();
    activeNotePath = data.rel_path;

    const titleEl = document.getElementById('obs-active-note-title');
    if (titleEl) titleEl.textContent = data.title;

    const pathEl = document.getElementById('obs-active-note-path');
    if (pathEl) pathEl.textContent = data.rel_path;

    const textarea = document.getElementById('obs-markdown-textarea');
    if (textarea) textarea.value = data.raw_content;

    renderMarkdownHTML(data.rendered_html);
    await fetchBacklinksData(data.rel_path, (p) => openNote(p), notesList);

    renderNotesItems();
    updateEditorCounters();

    const saveMsg = document.getElementById('obs-save-indicator-msg');
    if (saveMsg) saveMsg.textContent = 'Все изменения сохранены';
  } catch (err) {
    console.error(`[Obsidian] Ошибка открытия заметки ${relPath}:`, err);
  }
}

function renderMarkdownHTML(htmlContent) {
  const container = document.getElementById('obs-rendered-markdown-content');
  if (!container) return;
  container.innerHTML = htmlContent;

  container.querySelectorAll('.obsidian-wikilink').forEach(link => {
    link.addEventListener('click', async (e) => {
      e.preventDefault();
      const target = link.getAttribute('data-target');
      if (!target) return;

      const found = notesList.find(n => n.title.toLowerCase() === target.toLowerCase() || n.rel_path.toLowerCase().includes(target.toLowerCase()));
      if (found) {
        await openNote(found.rel_path);
      } else {
        if (confirm(`Заметка "[[${target}]]" не найдена. Создать?`)) {
          await createNote({ title: target, is_daily: false });
        }
      }
    });
  });

  container.querySelectorAll('.obsidian-tag').forEach(tagEl => {
    tagEl.addEventListener('click', () => {
      const tag = tagEl.getAttribute('data-tag');
      if (tag) {
        activeTagFilter = tag;
        loadNotesList();
      }
    });
  });

  container.querySelectorAll('.obsidian-task-checkbox').forEach((checkbox, idx) => {
    checkbox.addEventListener('change', () => {
      toggleTaskCheckboxInEditor(idx, checkbox.checked);
    });
  });
}

function toggleTaskCheckboxInEditor(taskIndex, isChecked) {
  const textarea = document.getElementById('obs-markdown-textarea');
  if (!textarea) return;

  const lines = textarea.value.split('\n');
  let currentTask = 0;
  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(/^(\s*[-*+]\s+)\[([ xX])\]\s*(.*)$/);
    if (match) {
      if (currentTask === taskIndex) {
        lines[i] = `${match[1]}[${isChecked ? 'x' : ' '}] ${match[3]}`;
        break;
      }
      currentTask++;
    }
  }
  textarea.value = lines.join('\n');
  updateLivePreviewFromEditor();
  saveCurrentNote();
}

function updateLivePreviewFromEditor() {
  const textarea = document.getElementById('obs-markdown-textarea');
  if (!textarea) return;

  updateEditorCounters();

  const saveMsg = document.getElementById('obs-save-indicator-msg');
  if (saveMsg) saveMsg.textContent = 'Есть несохраненные изменения...';

  let raw = textarea.value;
  let parsed = raw
    .replace(/^### (.*$)/gim, '<h3 class="mt-3 mb-2">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="mt-3 mb-2">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="mt-3 mb-2">$1</h1>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/\[\[([^\]|#\n]+)(?:#[^\]|\n]+)?(?:\|([^\]\n]+))?\]\]/gim, (m, p1, p2) => {
      const alias = p2 || p1;
      return `<a href="#" class="obsidian-wikilink badge bg-primary-subtle text-primary border" data-target="${p1}">[[${alias}]]</a>`;
    })
    .replace(/(?:^|[\s(])#([a-zA-Zа-яА-Я0-9_\-/]+)/gim, '<span class="obsidian-tag badge bg-info-subtle text-info">#$1</span>')
    .replace(/\n/gim, '<br>');

  renderMarkdownHTML(parsed);
}

function updateEditorCounters() {
  const textarea = document.getElementById('obs-markdown-textarea');
  const counter = document.getElementById('obs-editor-stats-counter');
  if (!textarea || !counter) return;

  const text = textarea.value;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  counter.textContent = `Слов: ${words} | Символов: ${text.length}`;
}

async function saveCurrentNote() {
  if (!activeNotePath) return;

  const textarea = document.getElementById('obs-markdown-textarea');
  const commitInput = document.getElementById('obs-commit-message-input');
  const saveMsg = document.getElementById('obs-save-indicator-msg');

  if (!textarea) return;
  const content = textarea.value;
  const commitMsg = commitInput ? commitInput.value.trim() : null;

  if (saveMsg) saveMsg.textContent = 'Сохранение...';

  try {
    const res = await fetch('/api/v1/obsidian/note/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: activeNotePath,
        content: content,
        commit_message: commitMsg || null,
      }),
    });

    if (!res.ok) throw new Error('Ошибка сохранения');
    const data = await res.json();

    if (saveMsg) {
      saveMsg.textContent = data.commit_hash
        ? `Сохранено в Git [${data.commit_hash}]`
        : 'Все изменения сохранены';
    }
    if (commitInput) commitInput.value = '';

    await loadVaultSummary();
    await fetchBacklinksData(activeNotePath, (p) => openNote(p), notesList);
  } catch (err) {
    if (saveMsg) saveMsg.textContent = 'Ошибка сохранения!';
    console.error('[Obsidian] Ошибка сохранения:', err);
  }
}

async function createNote({ title, folder, is_daily }) {
  try {
    const res = await fetch('/api/v1/obsidian/note/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        folder: folder || '',
        is_daily: is_daily || false,
      }),
    });

    if (!res.ok) throw new Error('Ошибка создания');
    const data = await res.json();

    await loadVaultSummary();
    await loadNotesList();

    if (data.rel_path) {
      await openNote(data.rel_path);
    }
  } catch (err) {
    console.error('[Obsidian] Ошибка создания:', err);
  }
}

async function deleteCurrentNote() {
  if (!activeNotePath) return;
  try {
    const res = await fetch(`/api/v1/obsidian/note?rel_path=${encodeURIComponent(activeNotePath)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Ошибка удаления');

    activeNotePath = null;
    await loadVaultSummary();
    await loadNotesList();

    if (notesList.length > 0) {
      await openNote(notesList[0].rel_path);
    } else {
      const textarea = document.getElementById('obs-markdown-textarea');
      if (textarea) textarea.value = '';
      const preview = document.getElementById('obs-rendered-markdown-content');
      if (preview) preview.innerHTML = '<div class="text-muted p-4 text-center">Создайте новую заметку</div>';
    }
  } catch (err) {
    console.error('[Obsidian] Ошибка удаления:', err);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initObsidianTab());
} else {
  initObsidianTab();
}
