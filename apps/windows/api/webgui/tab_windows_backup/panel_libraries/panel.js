/**
 * =============================================================================
 * Process Name: Windows Backup - Windows Libraries Panel
 * =============================================================================
 * Description:
 *   Модуль управления системными библиотеками Windows (Документы, Музыка,
 *   Видео, Изображения и пользовательские): создание библиотек, аудит доступности
 *   включенных папок, добавление новых папок и папка сохранения по умолчанию.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/panel_libraries
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { sharedState, escapeHtml, showModal, hideModal } from '../common/ui_utils.js';

/**
 * Загрузка списка библиотек Windows и связанных папок.
 * @returns {Promise<void>}
 */
export async function loadLibraries() {
  const tbody = document.getElementById('wb-libraries-body');
  const countBadge = document.getElementById('wb-lib-count');
  const valLibs = document.getElementById('wb-val-libraries');

  try {
    const res = await fetch('/api/v1/windows-backup/libraries');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const libs = await res.json();
    sharedState.librariesData = libs || [];

    if (countBadge) countBadge.textContent = `${libs.length} шт.`;
    if (valLibs) valLibs.textContent = `${libs.length}`;

    if (!tbody) return;
    if (!libs || libs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">Библиотеки не найдены</td></tr>';
      return;
    }

    tbody.innerHTML = libs.map(lib => {
      const foldersHtml = (lib.folders || []).map(f => {
        const path = typeof f === 'string' ? f : f.folder_path;
        const exists = typeof f === 'object' ? f.exists : true;
        return `
          <div class="text-break font-monospace small d-flex align-items-center gap-1 ${exists ? 'text-white' : 'text-danger'}">
            <i class="bi ${exists ? 'bi-folder-check text-info' : 'bi-folder-x text-danger'}"></i>
            <span>${escapeHtml(path)}</span>
            ${!exists ? '<span class="badge bg-danger-subtle text-danger py-0 px-1" style="font-size:0.6rem;">Недоступна</span>' : ''}
          </div>
        `;
      }).join('') || '<span class="text-muted small">Нет папок</span>';

      return `
        <tr>
          <td class="fw-bold text-white">
            <i class="bi bi-collection me-1 text-primary"></i>${escapeHtml(lib.name)}
          </td>
          <td>${foldersHtml}</td>
          <td class="text-break font-monospace small text-info">
            ${lib.default_save_folder ? escapeHtml(lib.default_save_folder) : '<span class="text-muted">—</span>'}
          </td>
          <td>
            <span class="badge ${lib.is_pinned ? 'bg-primary' : 'bg-secondary'}">${lib.is_pinned ? 'Да' : 'Нет'}</span>
          </td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-danger">Ошибка: ${escapeHtml(e.message)}</td></tr>`;
  }
}

/**
 * Создание новой библиотеки Windows.
 */
export async function executeCreateLibrary() {
  const btn = document.getElementById('wb-btn-execute-create-lib');
  const name = document.getElementById('wb-create-lib-name')?.value?.trim();
  const foldersRaw = document.getElementById('wb-create-lib-folders')?.value || '';
  const isPinned = document.getElementById('wb-create-lib-pinned')?.checked ?? true;

  if (!name) {
    alert('Укажите название библиотеки');
    return;
  }

  const folders = foldersRaw
    .split('\n')
    .map(f => f.trim())
    .filter(f => f.length > 0);

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Создание...';
  }

  try {
    const res = await fetch('/api/v1/windows-backup/libraries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, folders, is_pinned: isPinned })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Библиотека "${name}" успешно создана!`);
      hideModal('wb-create-lib-modal');
      await loadLibraries();
    } else {
      alert('Ошибка: ' + (data.detail || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Ошибка сети: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-lg"></i> <span>Создать</span>';
    }
  }
}

/**
 * Добавление папки в существующую библиотеку Windows.
 */
export async function executeAddFolderToLibrary() {
  const btn = document.getElementById('wb-btn-execute-add-folder');
  const libName = document.getElementById('wb-add-folder-lib-select')?.value;
  const folderPath = document.getElementById('wb-add-folder-path')?.value?.trim();
  const isDefault = document.getElementById('wb-add-folder-default-save')?.checked ?? false;

  if (!libName || !folderPath) {
    alert('Выберите библиотеку и укажите путь к папке');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Добавление...';
  }

  try {
    const res = await fetch(`/api/v1/windows-backup/libraries/${encodeURIComponent(libName)}/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath, is_default_save: isDefault })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Папка успешно добавлена в библиотеку "${libName}"!`);
      hideModal('wb-add-folder-modal');
      await loadLibraries();
    } else {
      alert('Ошибка: ' + (data.detail || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Ошибка сети: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-lg"></i> <span>Добавить</span>';
    }
  }
}

/**
 * Привязка событий элементов управления библиотеками.
 */
export function bindLibrariesEvents() {
  // Открытие модалки создания библиотеки
  const btnOpenCreateLib = document.getElementById('wb-btn-open-create-lib');
  if (btnOpenCreateLib && !btnOpenCreateLib._bound) {
    btnOpenCreateLib._bound = true;
    btnOpenCreateLib.onclick = () => showModal('wb-create-lib-modal');
  }

  const btnExecCreateLib = document.getElementById('wb-btn-execute-create-lib');
  if (btnExecCreateLib && !btnExecCreateLib._bound) {
    btnExecCreateLib._bound = true;
    btnExecCreateLib.onclick = executeCreateLibrary;
  }

  // Открытие модалки добавления папки
  const btnQuickAddFolder = document.getElementById('wb-btn-quick-add-folder');
  if (btnQuickAddFolder && !btnQuickAddFolder._bound) {
    btnQuickAddFolder._bound = true;
    btnQuickAddFolder.onclick = () => {
      const select = document.getElementById('wb-add-folder-lib-select');
      if (select) {
        select.innerHTML = sharedState.librariesData.length > 0
          ? sharedState.librariesData.map(l => `<option value="${escapeHtml(l.name)}">${escapeHtml(l.name)} (${l.folder_count || 0} папок)</option>`).join('')
          : '<option value="">Нет доступных библиотек</option>';
      }
      showModal('wb-add-folder-modal');
    };
  }

  const btnExecAddFolder = document.getElementById('wb-btn-execute-add-folder');
  if (btnExecAddFolder && !btnExecAddFolder._bound) {
    btnExecAddFolder._bound = true;
    btnExecAddFolder.onclick = executeAddFolderToLibrary;
  }
}
