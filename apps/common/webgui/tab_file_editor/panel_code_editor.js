/**
 * =============================================================================
 * Process Name: Common WebGUI - Code, Text & Markdown Split-View Panel
 * =============================================================================
 * Description:
 *   Модуль управления текстовым и кодовым редактором, нумерацией строк,
 *   синхронным скроллингом, деревом символов (Outline), поиском/заменой
 *   и живым Split-View предпросмотром Markdown.
 *
 * File: panel_code_editor.js
 * Project: ai-assistant
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 17:08:00
 * =============================================================================
 */

import { extractOutlineSymbols } from './wasm_bridge.js';

/**
 * Обновляет колонку номеров строк (Line Gutter) в соответствии с числом строк текста.
 * @param {HTMLTextAreaElement} textarea
 * @param {HTMLElement} gutter
 */
export function updateLineGutter(textarea, gutter) {
  if (!textarea || !gutter) return;
  const lineCount = Math.max(1, (textarea.value || '').split('\n').length);
  const nums = [];
  for (let i = 1; i <= lineCount; i++) {
    nums.push(i);
  }
  gutter.textContent = nums.join('\n');
  gutter.scrollTop = textarea.scrollTop;
}

/**
 * Вычисляет текущую строку и столбец курсора в текстовом поле.
 * @param {HTMLTextAreaElement} textarea
 * @returns {{line: number, col: number}}
 */
export function getCursorPosition(textarea) {
  if (!textarea) return { line: 1, col: 1 };
  const pos = textarea.selectionStart || 0;
  const before = (textarea.value || '').slice(0, pos);
  const lines = before.split('\n');
  return {
    line: lines.length,
    col: lines[lines.length - 1].length + 1,
  };
}

/**
 * Прокручивает текстовый редактор к заданному номеру строки и выделяет её.
 * @param {HTMLTextAreaElement} textarea
 * @param {number} targetLine
 */
export function jumpToLine(textarea, targetLine) {
  if (!textarea || targetLine < 1) return;
  const lines = (textarea.value || '').split('\n');
  let charOffset = 0;
  for (let i = 0; i < Math.min(targetLine - 1, lines.length); i++) {
    charOffset += lines[i].length + 1;
  }
  const lineLen = (lines[targetLine - 1] || '').length;
  textarea.focus();
  textarea.setSelectionRange(charOffset, charOffset + lineLen);
  const lineHeight = 20;
  textarea.scrollTop = Math.max(0, (targetLine - 4) * lineHeight);
}

/**
 * Отрисовывает боковое дерево символов (Outline) и привязывает переход по строкам.
 * @param {string} content
 * @param {string} ext
 * @param {HTMLElement} container
 * @param {HTMLTextAreaElement} textarea
 */
export function renderOutlinePanel(content, ext, container, textarea) {
  if (!container) return;
  const symbols = extractOutlineSymbols(content, ext);
  if (symbols.length === 0) {
    container.innerHTML = `<div class="small text-muted">—</div>`;
    return;
  }

  container.innerHTML = symbols
    .map(
      (s) => `
      <div class="wasm-editor-file-item justify-content-between py-1 px-2" data-outline-line="${s.line}">
        <span class="text-truncate d-flex align-items-center gap-1.5">
          <i class="bi ${s.icon} text-primary"></i>
          <span class="text-truncate">${escapeHtml(s.name)}</span>
        </span>
        <span class="badge bg-secondary-subtle text-secondary font-monospace">:${s.line}</span>
      </div>
    `
    )
    .join('');

  container.querySelectorAll('[data-outline-line]').forEach((el) => {
    el.addEventListener('click', () => {
      const ln = parseInt(el.getAttribute('data-outline-line') || '1', 10);
      jumpToLine(textarea, ln);
    });
  });
}

/**
 * Рендерит живой предпросмотр Markdown в панели Split-View.
 * @param {string} markdownText
 * @param {HTMLElement} previewEl
 */
export function renderMarkdownSplitPreview(markdownText, previewEl) {
  if (!previewEl) return;
  const src = markdownText || '';
  if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
    previewEl.innerHTML = window.marked.parse(src);
    return;
  }
  // Безопасный встроенный рендерер Markdown при отсутствии внешнего marked
  const html = escapeHtml(src)
    .replace(/^###\s+(.+)$/gm, '<h5>$1</h5>')
    .replace(/^##\s+(.+)$/gm, '<h4>$1</h4>')
    .replace(/^#\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '<br><br>');
  previewEl.innerHTML = html;
}

/**
 * Выполняет поиск и замену в активном текстовом редакторе.
 * @param {HTMLTextAreaElement} textarea
 * @param {string} query
 * @param {string} replacement
 * @param {'find'|'replace'|'replaceAll'} mode
 * @returns {number} Количество найденных вхождений
 */
export function runSearchReplace(textarea, query, replacement, mode = 'find') {
  if (!textarea || !query) return 0;
  const text = textarea.value || '';
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regexGlobal = new RegExp(escaped, 'gi');
  const matches = [...text.matchAll(regexGlobal)];
  if (matches.length === 0) return 0;

  if (mode === 'replaceAll') {
    textarea.value = text.replace(regexGlobal, replacement);
    textarea.dispatchEvent(new Event('input'));
    return matches.length;
  }

  const startFrom = textarea.selectionEnd || 0;
  let nextMatch = matches.find((m) => m.index >= startFrom) || matches[0];
  if (nextMatch) {
    textarea.focus();
    textarea.setSelectionRange(nextMatch.index, nextMatch.index + query.length);
    if (mode === 'replace') {
      const before = text.slice(0, nextMatch.index);
      const after = text.slice(nextMatch.index + query.length);
      textarea.value = before + replacement + after;
      textarea.setSelectionRange(nextMatch.index, nextMatch.index + replacement.length);
      textarea.dispatchEvent(new Event('input'));
    }
  }
  return matches.length;
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
