/**
 * =============================================================================
 * Process Name: Common WebGUI - Specialized VS Code Editors (Hex, CSV, IPYNB, Media)
 * =============================================================================
 * Description:
 *   Специализированные редакторы для нетекстовых и структурированных форматов
 *   в стиле Visual Studio Code:
 *   - Hex Editor с побайтовым редактированием и Data Inspector (8/16/32/64 бит)
 *   - Табличный редактор CSV / TSV (Grid View)
 *   - Редактор ячеек Jupyter Notebook (.ipynb)
 *   - Графическая и документная студия (SVG, Canvas-редактор изображений,
 *     Wasm-экстрактор PDF, инспектор аудио/видео).
 *
 * File: panel_specialized_editors.js
 * Project: ai-assistant
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 17:09:00
 * =============================================================================
 */

import { inspectBytesAt, uint8ArrayToBase64 } from './wasm_bridge.js';

const HEX_PAGE_SIZE = 4096; // 4 КБ на страницу (256 строк по 16 байт)

/**
 * Обновляет боковую панель Data Inspector для выбранного байтового смещения.
 * @param {Uint8Array} bytes
 * @param {number} offset
 */
export function updateDataInspectorUI(bytes, offset) {
  const info = inspectBytesAt(bytes, offset);
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
  };
  setTxt('fe-inspector-offset', info.offsetHex);
  setTxt('fe-insp-bin', info.binary);
  setTxt('fe-insp-u8', info.uint8);
  setTxt('fe-insp-i8', info.int8);
  setTxt('fe-insp-u16', info.uint16);
  setTxt('fe-insp-i16', info.int16);
  setTxt('fe-insp-u32', info.uint32);
  setTxt('fe-insp-i32', info.int32);
  setTxt('fe-insp-f32', info.float32);
  setTxt('fe-insp-char', info.ascii);
}

/**
 * Рендерит страницу побайтового редактора VS Code Hex Editor.
 * @param {Object} docState - Состояние открытого файла
 * @param {HTMLElement} container
 * @param {Function} onByteChanged - Колбэк при изменении байта (offset, newVal)
 */
export function renderHexEditorPage(docState, container, onByteChanged) {
  if (!container || !docState) return;
  const bytes = docState.bytes || new Uint8Array(0);
  const totalPages = Math.max(1, Math.ceil(bytes.length / HEX_PAGE_SIZE));
  docState.hexPage = Math.min(Math.max(0, docState.hexPage || 0), totalPages - 1);

  const pageInd = document.getElementById('fe-hex-page-indicator');
  if (pageInd) pageInd.textContent = `${docState.hexPage + 1} / ${totalPages}`;

  const startOffset = docState.hexPage * HEX_PAGE_SIZE;
  const endOffset = Math.min(bytes.length, startOffset + HEX_PAGE_SIZE);

  if (bytes.length === 0) {
    container.innerHTML = `<div class="p-3 text-muted small">Буфер пуст (0 байт)</div>`;
    updateDataInspectorUI(bytes, 0);
    return;
  }

  const rowsHtml = [];
  for (let rowOff = startOffset; rowOff < endOffset; rowOff += 16) {
    const offsetHex = rowOff.toString(16).toUpperCase().padStart(8, '0');
    const cells = [];
    let asciiStr = '';

    for (let i = 0; i < 16; i++) {
      const cur = rowOff + i;
      if (cur < bytes.length) {
        const val = bytes[cur];
        const hexVal = val.toString(16).toUpperCase().padStart(2, '0');
        const isMod = docState.hexPatches && docState.hexPatches.has(cur);
        const isSel = docState.selectedOffset === cur;
        cells.push(
          `<span class="wasm-hex-cell ${isSel ? 'selected' : ''} ${isMod ? 'modified' : ''}" data-hex-offset="${cur}" title="Offset: 0x${cur.toString(16).toUpperCase()} (Двойной клик для изменения)">${hexVal}</span>`
        );
        asciiStr += val >= 32 && val <= 126 ? escapeHtmlChar(String.fromCharCode(val)) : '·';
      } else {
        cells.push(`<span class="wasm-hex-cell text-muted">  </span>`);
        asciiStr += ' ';
      }
    }

    rowsHtml.push(`
      <div class="wasm-hex-row">
        <span class="wasm-hex-offset">${offsetHex}</span>
        ${cells.join('')}
        <span></span>
        <span class="wasm-hex-ascii">${asciiStr}</span>
      </div>
    `);
  }

  container.innerHTML = rowsHtml.join('');
  updateDataInspectorUI(bytes, docState.selectedOffset || startOffset);

  container.querySelectorAll('[data-hex-offset]').forEach((cell) => {
    cell.addEventListener('click', () => {
      const off = parseInt(cell.getAttribute('data-hex-offset') || '0', 10);
      docState.selectedOffset = off;
      container.querySelectorAll('.wasm-hex-cell.selected').forEach((c) => c.classList.remove('selected'));
      cell.classList.add('selected');
      updateDataInspectorUI(bytes, off);
    });

    cell.addEventListener('dblclick', () => {
      const off = parseInt(cell.getAttribute('data-hex-offset') || '0', 10);
      const curHex = bytes[off].toString(16).toUpperCase().padStart(2, '0');
      const input = prompt(`Введите новое Hex-значение байта (00..FF) по смещению 0x${off.toString(16).toUpperCase()}:`, curHex);
      if (input === null) return;
      const parsed = parseInt(input.trim(), 16);
      if (Number.isNaN(parsed) || parsed < 0 || parsed > 255) return;
      onByteChanged(off, parsed);
    });
  });
}

/**
 * Рендерит интерактивный табличный редактор CSV / TSV.
 * @param {Object} docState
 * @param {Function} onContentUpdated
 */
export function renderTabularGrid(docState, onContentUpdated) {
  const thead = document.getElementById('fe-csv-thead');
  const tbody = document.getElementById('fe-csv-tbody');
  const dimLabel = document.getElementById('fe-csv-dimensions-label');
  if (!thead || !tbody || !docState) return;

  const isTsv = (docState.ext || '').toLowerCase() === 'tsv';
  const delimiter = isTsv ? '\t' : ',';
  const rows = parseDelimitedText(docState.content || '', delimiter);
  if (rows.length === 0) rows.push(['Column 1', 'Column 2']);

  const colCount = Math.max(1, ...rows.map((r) => r.length));
  if (dimLabel) dimLabel.textContent = `${rows.length} × ${colCount}`;

  const syncFromTable = () => {
    const newRows = [];
    const headerInputs = thead.querySelectorAll('input[data-csv-cell]');
    if (headerInputs.length > 0) {
      newRows.push(Array.from(headerInputs).map((inp) => inp.value));
    }
    tbody.querySelectorAll('tr').forEach((tr) => {
      const vals = Array.from(tr.querySelectorAll('input[data-csv-cell]')).map((inp) => inp.value);
      if (vals.length > 0) newRows.push(vals);
    });
    const serialized = newRows
      .map((r) =>
        r
          .map((cell) => {
            if (cell.includes(delimiter) || cell.includes('"') || cell.includes('\n')) {
              return `"${cell.replace(/"/g, '""')}"`;
            }
            return cell;
          })
          .join(delimiter)
      )
      .join('\n');
    onContentUpdated(serialized + '\n');
  };

  // Заголовок таблицы (первая строка)
  const headRow = rows[0] || [];
  let headHtml = '<tr><th class="text-center text-muted small">#</th>';
  for (let c = 0; c < colCount; c++) {
    headHtml += `<th><input type="text" class="form-control form-control-sm fw-bold border-0 bg-transparent" data-csv-cell="0:${c}" value="${escapeAttr(headRow[c] || '')}"></th>`;
  }
  headHtml += '</tr>';
  thead.innerHTML = headHtml;

  // Тело таблицы
  let bodyHtml = '';
  for (let r = 1; r < rows.length; r++) {
    bodyHtml += `<tr><td class="text-center text-muted small font-monospace">${r}</td>`;
    for (let c = 0; c < colCount; c++) {
      bodyHtml += `<td><input type="text" class="form-control form-control-sm border-0 bg-transparent" data-csv-cell="${r}:${c}" value="${escapeAttr(rows[r][c] || '')}"></td>`;
    }
    bodyHtml += '</tr>';
  }
  tbody.innerHTML = bodyHtml;

  thead.querySelectorAll('input[data-csv-cell]').forEach((inp) => inp.addEventListener('input', syncFromTable));
  tbody.querySelectorAll('input[data-csv-cell]').forEach((inp) => inp.addEventListener('input', syncFromTable));
}

/**
 * Рендерит интерактивный редактор блокнотов Jupyter (.ipynb).
 * @param {Object} docState
 * @param {Function} onContentUpdated
 */
export function renderNotebookEditor(docState, onContentUpdated) {
  const container = document.getElementById('fe-nb-cells-container');
  const kernelBadge = document.getElementById('fe-nb-kernel-badge');
  if (!container || !docState) return;

  let nbObj = null;
  try {
    nbObj = JSON.parse(docState.content || '{}');
  } catch (_) {
    nbObj = { cells: [], metadata: {}, nbformat: 4, nbformat_minor: 5 };
  }
  if (!Array.isArray(nbObj.cells)) nbObj.cells = [];
  docState.notebookObj = nbObj;

  const kernelName = nbObj.metadata?.kernelspec?.display_name || 'Python 3 (ipykernel)';
  if (kernelBadge) kernelBadge.textContent = kernelName;

  const serializeNb = () => {
    onContentUpdated(JSON.stringify(nbObj, null, 2) + '\n');
  };

  container.innerHTML = nbObj.cells
    .map((cell, idx) => {
      const isCode = cell.cell_type === 'code';
      const srcText = Array.isArray(cell.source) ? cell.source.join('') : String(cell.source || '');
      return `
        <div class="card border-subtle shadow-sm bg-body" data-nb-cell-idx="${idx}">
          <div class="card-header py-1 px-3 bg-body-tertiary d-flex align-items-center justify-content-between small">
            <span class="fw-semibold font-monospace">
              <i class="bi ${isCode ? 'bi-code-square text-primary' : 'bi-markdown text-info'} me-1"></i>
              ${isCode ? `In [${cell.execution_count || idx + 1}] (Code)` : `Markdown [${idx + 1}]`}
            </span>
            <button type="button" class="btn btn-xs btn-outline-danger py-0 px-1.5" data-nb-del="${idx}">
              <i class="bi bi-trash"></i>
            </button>
          </div>
          <div class="card-body p-2">
            <textarea class="form-control font-monospace small" rows="${Math.min(12, Math.max(3, srcText.split('\n').length))}" data-nb-textarea="${idx}">${escapeAttr(srcText)}</textarea>
          </div>
        </div>
      `;
    })
    .join('');

  container.querySelectorAll('textarea[data-nb-textarea]').forEach((ta) => {
    ta.addEventListener('input', () => {
      const idx = parseInt(ta.getAttribute('data-nb-textarea') || '0', 10);
      if (nbObj.cells[idx]) {
        nbObj.cells[idx].source = ta.value.split('\n').map((line, i, arr) => (i < arr.length - 1 ? line + '\n' : line));
        serializeNb();
      }
    });
  });

  container.querySelectorAll('button[data-nb-del]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.getAttribute('data-nb-del') || '0', 10);
      nbObj.cells.splice(idx, 1);
      serializeNb();
      renderNotebookEditor(docState, onContentUpdated);
    });
  });
}

/**
 * Рендерит медиа-студию (SVG, растровые изображения на Canvas, PDF или аудио/видео).
 * @param {Object} docState
 * @param {Function} onImageBinaryChanged
 */
export function renderMediaStudio(docState, onImageBinaryChanged) {
  const viewport = document.getElementById('fe-media-viewport');
  const metaLabel = document.getElementById('fe-media-meta-label');
  if (!viewport || !docState) return;

  const ext = (docState.ext || '').toLowerCase();
  const mime = docState.descriptor?.mime_type || 'application/octet-stream';

  // 1. Векторная графика SVG
  if (ext === 'svg') {
    if (metaLabel) metaLabel.textContent = `SVG Vector XML • ${(docState.content || '').length} chars`;
    viewport.innerHTML = `<div class="p-3 bg-body rounded border shadow-sm">${docState.content || ''}</div>`;
    return;
  }

  // 2. Растровые изображения (Canvas Studio с поддержкой поворота и отражения)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico'].includes(ext)) {
    viewport.innerHTML = `<canvas id="fe-image-canvas" class="rounded shadow-sm border"></canvas>`;
    const canvas = document.getElementById('fe-image-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    const b64 = docState.base64Content || uint8ArrayToBase64(docState.bytes);
    img.onload = () => {
      const angle = ((docState.rotation || 0) % 360 + 360) % 360;
      const swapDims = angle === 90 || angle === 270;
      canvas.width = swapDims ? img.height : img.width;
      canvas.height = swapDims ? img.width : img.height;
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate((angle * Math.PI) / 180);
      ctx.scale(docState.flipH ? -1 : 1, docState.flipV ? -1 : 1);
      ctx.drawImage(img, -img.width / 2, -img.height / 2);
      ctx.restore();
      if (metaLabel) metaLabel.textContent = `${canvas.width} × ${canvas.height} px • ${mime}`;

      if (docState.rotation || docState.flipH || docState.flipV) {
        const outMime = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : 'image/png';
        const dataUrl = canvas.toDataURL(outMime);
        onImageBinaryChanged(dataUrl.split(',')[1]);
      }
    };
    img.src = `data:${mime};base64,${b64}`;
    return;
  }

  // 3. Документы PDF
  if (ext === 'pdf') {
    const b64 = docState.base64Content || uint8ArrayToBase64(docState.bytes);
    if (metaLabel) metaLabel.textContent = `PDF Document • ${docState.bytes?.length || 0} bytes`;
    viewport.innerHTML = `
      <embed src="data:application/pdf;base64,${b64}" type="application/pdf" width="100%" height="480px" class="rounded border" />
    `;
    return;
  }

  // 4. Аудио и Видео
  const b64 = docState.base64Content || uint8ArrayToBase64(docState.bytes);
  if (['mp4', 'webm'].includes(ext)) {
    viewport.innerHTML = `<video controls class="w-100 rounded" src="data:${mime};base64,${b64}"></video>`;
  } else {
    viewport.innerHTML = `<audio controls class="w-100" src="data:${mime};base64,${b64}"></audio>`;
  }
}

function parseDelimitedText(text, delimiter) {
  const lines = String(text || '').trim().split(/\r?\n/);
  return lines.filter(Boolean).map((line) => line.split(delimiter).map((c) => c.replace(/^"|"$/g, '')));
}

function escapeAttr(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeHtmlChar(ch) {
  if (ch === '<') return '&lt;';
  if (ch === '>') return '&gt;';
  if (ch === '&') return '&amp;';
  return ch;
}
