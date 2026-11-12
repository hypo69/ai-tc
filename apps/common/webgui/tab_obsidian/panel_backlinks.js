/**
 * =============================================================================
 * Process Name: Common WebGUI - Obsidian Backlinks & Mentions Inspector
 * =============================================================================
 * Description:
 *   Модуль инспектора связей базы знаний Obsidian (apps/common/webgui/tab_obsidian).
 *   Обеспечивает загрузку и отображение:
 *   - Входящих обратных ссылок (Backlinks) с контекстными сниппетами.
 *   - Несвязанных упоминаний (Unlinked Mentions) с кнопкой связывания.
 *   - Исходящих ссылок (Outgoing links) активной заметки.
 *
 * File: panel_backlinks.js
 * Project: ai-assistant
 * Package: apps.common.webgui.tab_obsidian
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 16:45:00
 * =============================================================================
 */

export async function fetchBacklinksData(relPath, onOpenNote, notesList) {
  try {
    const res = await fetch(`/api/v1/obsidian/backlinks?rel_path=${encodeURIComponent(relPath)}`);
    if (!res.ok) return;
    const data = await res.json();

    // 1. Входящие ссылки
    renderBacklinksList(data.backlinks, onOpenNote);

    // 2. Неразмеченные упоминания
    renderUnlinkedMentions(data.unlinked_mentions, onOpenNote, relPath);

    // 3. Исходящие ссылки
    renderOutgoingLinks(data.outgoing_links, onOpenNote, notesList);
  } catch (err) {
    console.warn('[ObsidianBacklinks] Ошибка инспектора связей:', err);
  }
}

function renderBacklinksList(backlinks, onOpenNote) {
  const listEl = document.getElementById('obs-backlinks-list');
  const badgeEl = document.getElementById('obs-backlinks-count-badge');
  if (badgeEl) badgeEl.textContent = backlinks.length;
  if (!listEl) return;

  listEl.innerHTML = '';
  if (backlinks.length === 0) {
    listEl.innerHTML = '<div class="text-muted small">Нет входящих ссылок</div>';
    return;
  }

  backlinks.forEach(b => {
    const card = document.createElement('div');
    card.className = 'obs-backlink-card';
    card.onclick = () => onOpenNote(b.source_path);
    card.innerHTML = `<div class="fw-semibold font-size-80 text-primary">📄 ${b.source_title}</div>` +
      (b.context_snippet ? `<div class="small text-muted font-size-75 text-truncate">${b.context_snippet}</div>` : '');
    listEl.appendChild(card);
  });
}

function renderUnlinkedMentions(unlinked, onOpenNote, activeRelPath) {
  const listEl = document.getElementById('obs-unlinked-list');
  const badgeEl = document.getElementById('obs-unlinked-count-badge');
  if (badgeEl) badgeEl.textContent = unlinked.length;
  if (!listEl) return;

  listEl.innerHTML = '';
  if (unlinked.length === 0) {
    listEl.innerHTML = '<div class="text-muted small">Нет упоминаний</div>';
    return;
  }

  unlinked.forEach(u => {
    const card = document.createElement('div');
    card.className = 'obs-unlinked-card';
    card.innerHTML = `<div class="d-flex justify-content-between align-items-center">` +
      `<span class="fw-semibold font-size-80 text-warning-emphasis">📄 ${u.source_title}</span>` +
      `<button class="btn btn-xs btn-outline-primary py-0 px-1">Связать</button></div>` +
      `<div class="small text-muted font-size-75 text-truncate mt-1">${u.context_snippet}</div>`;

    const btnLink = card.querySelector('button');
    if (btnLink) {
      btnLink.onclick = async (e) => {
        e.stopPropagation();
        await linkMentionInNote(u.source_path, u.matched_text, activeRelPath, onOpenNote);
      };
    }
    card.onclick = () => onOpenNote(u.source_path);
    listEl.appendChild(card);
  });
}

async function linkMentionInNote(sourcePath, matchedText, activeRelPath, onOpenNote) {
  try {
    const res = await fetch(`/api/v1/obsidian/note?rel_path=${encodeURIComponent(sourcePath)}`);
    if (!res.ok) return;
    const note = await res.json();
    const replaced = note.raw_content.replace(matchedText, `[[${matchedText}]]`);
    await fetch('/api/v1/obsidian/note/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: sourcePath,
        content: replaced,
        commit_message: `Связана ссылка [[${matchedText}]]`,
      }),
    });
    await fetchBacklinksData(activeRelPath, onOpenNote, []);
  } catch (err) {
    console.error('[ObsidianBacklinks] Ошибка связывания:', err);
  }
}

function renderOutgoingLinks(outgoing, onOpenNote, notesList) {
  const listEl = document.getElementById('obs-outgoing-list');
  const badgeEl = document.getElementById('obs-outgoing-count-badge');
  if (badgeEl) badgeEl.textContent = outgoing.length;
  if (!listEl) return;

  listEl.innerHTML = '';
  if (outgoing.length === 0) {
    listEl.innerHTML = '<div class="text-muted small">Нет исходящих ссылок</div>';
    return;
  }

  outgoing.forEach(outLink => {
    const item = document.createElement('div');
    item.className = 'badge bg-secondary-subtle text-secondary cursor-pointer text-start p-1.5 border';
    item.textContent = `[[${outLink}]]`;
    item.onclick = () => {
      const found = notesList.find(n => n.title.toLowerCase() === outLink.toLowerCase() || n.rel_path.toLowerCase().includes(outLink.toLowerCase()));
      if (found) onOpenNote(found.rel_path);
    };
    listEl.appendChild(item);
  });
}
