/**
 * =============================================================================
 * Process Name: Windows Backup - File History RAG Search Panel
 * =============================================================================
 * Description:
 *   Модуль интеллектуального семантического поиска по архиву резервных копий
 *   «Истории файлов» (File History RAG Search) и синхронизации векторного индекса.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/panel_rag
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Выполнение семантического поиска по проиндексированным резервным копиям.
 * @returns {Promise<void>}
 */
export async function performRagSearch() {
  const inputRagQuery = document.getElementById('wb-rag-query');
  const query = inputRagQuery?.value?.trim();
  if (!query) return;

  const resultsContainer = document.getElementById('wb-rag-results');
  if (resultsContainer) {
    resultsContainer.innerHTML = '<div class="text-center text-muted py-2"><span class="spinner-border spinner-border-sm me-1"></span>Поиск в архиве...</div>';
  }

  try {
    const res = await fetch('/api/v1/windows-backup/file-history/rag/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: 5 })
    });
    const items = await res.json();
    if (resultsContainer) {
      if (!items || items.length === 0) {
        resultsContainer.innerHTML = '<div class="text-muted text-center py-2 small">Ничего не найдено по запросу</div>';
        return;
      }
      resultsContainer.innerHTML = items.map(item => `
        <div class="p-1.5 mb-1 rounded bg-dark border border-secondary" style="font-size: 0.75rem;">
          <div class="d-flex justify-content-between align-items-center mb-0.5">
            <span class="fw-bold text-info text-truncate" title="${escapeHtml(item.file_name)}">${escapeHtml(item.file_name)}</span>
            <span class="badge bg-primary-subtle text-primary">${(item.score * 100).toFixed(0)}%</span>
          </div>
          <div class="text-muted font-monospace small text-truncate" title="${escapeHtml(item.original_path)}">${escapeHtml(item.original_path)}</div>
          ${item.snippet ? `<div class="text-white-50 mt-1 small text-truncate">${escapeHtml(item.snippet)}</div>` : ''}
        </div>
      `).join('');
    }
  } catch (e) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `<div class="text-danger small py-1">Ошибка поиска: ${escapeHtml(e.message)}</div>`;
    }
  }
}

/**
 * Синхронизация и переиндексация базы File History RAG.
 * @returns {Promise<void>}
 */
export async function syncRagIndex() {
  const btn = document.getElementById('wb-btn-rag-sync');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Синхр...';
  }

  try {
    const res = await fetch('/api/v1/windows-backup/file-history/rag/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_rebuild: false })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Синхронизация RAG завершена!\nПроиндексировано: ${data.total_indexed || 0} версий файлов.`);
    } else {
      alert('Ошибка синхронизации: ' + (data.detail || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Ошибка сети: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Синхронизация';
    }
  }
}

/**
 * Привязка событий элементов управления поиском RAG.
 */
export function bindRagEvents() {
  const btnRagSync = document.getElementById('wb-btn-rag-sync');
  if (btnRagSync && !btnRagSync._bound) {
    btnRagSync._bound = true;
    btnRagSync.onclick = syncRagIndex;
  }

  const btnRagSearch = document.getElementById('wb-btn-rag-search');
  if (btnRagSearch && !btnRagSearch._bound) {
    btnRagSearch._bound = true;
    btnRagSearch.onclick = performRagSearch;
  }

  const inputRagQuery = document.getElementById('wb-rag-query');
  if (inputRagQuery && !inputRagQuery._bound) {
    inputRagQuery._bound = true;
    inputRagQuery.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        performRagSearch();
      }
    };
  }
}
