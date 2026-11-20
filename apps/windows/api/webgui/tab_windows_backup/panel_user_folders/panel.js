/**
 * =============================================================================
 * Process Name: Windows Backup - User Folders & Relocation Panel
 * =============================================================================
 * Description:
 *   Модуль мониторинга объемов пользовательских папок (Документы, Загрузки,
 *   Рабочий стол, Видео и др.), дискового пространства и безопасного мастера
 *   переноса (Relocate) данных на другой физический диск с перенастройкой путей ОС.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/panel_user_folders
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { sharedState, escapeHtml, showModal, hideModal } from '../common/ui_utils.js';

/**
 * Загрузка сводки пользовательских папок и доступных физических дисков.
 * @returns {Promise<void>}
 */
export async function loadUserFoldersOverview() {
  const tbody = document.getElementById('wb-user-folders-tbody');
  const totalSizeBadge = document.getElementById('wb-total-user-size');
  const drivesList = document.getElementById('wb-drives-list');

  try {
    const res = await fetch('/api/v1/windows-backup/user-folders/overview');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    sharedState.userFoldersData = data;

    if (totalSizeBadge) {
      totalSizeBadge.textContent = `Общий объем: ${data.total_user_size_gb} ГБ (${data.total_user_size_mb} МБ)`;
    }

    if (drivesList) {
      if (!data.drives || data.drives.length === 0) {
        drivesList.innerHTML = '<span class="text-muted">Диски не обнаружены</span>';
      } else {
        drivesList.innerHTML = data.drives.map(d => `
          <div class="px-2 py-1 rounded border ${d.is_system_drive ? 'border-info bg-dark' : 'border-secondary bg-dark'} d-flex align-items-center gap-1.5">
            <i class="bi ${d.is_system_drive ? 'bi-hdd-fill text-info' : 'bi-hdd text-success'}"></i>
            <span class="fw-bold">${escapeHtml(d.drive_letter)}</span>
            <span class="text-muted">(${escapeHtml(d.fstype)})</span>:
            <span class="text-success fw-semibold">${d.free_space_gb} ГБ своб.</span>
            <span class="text-muted small">из ${d.total_space_gb} ГБ</span>
            ${d.is_system_drive ? '<span class="badge bg-info-subtle text-info py-0 px-1" style="font-size: 0.65rem;">System</span>' : ''}
          </div>
        `).join('');
      }
    }

    if (!tbody) return;
    if (!data.folders || data.folders.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Пользовательские папки не найдены</td></tr>';
      return;
    }

    tbody.innerHTML = data.folders.map(f => {
      const suitableDrives = (data.available_target_drives || []).filter(d => {
        const folderDrive = f.drive_letter.replace('\\', '');
        const targetDrive = d.drive_letter.replace('\\', '');
        return folderDrive !== targetDrive && d.free_space_gb >= (f.size_gb + 1.0);
      });

      const canRelocate = suitableDrives.length > 0;

      return `
        <tr>
          <td class="fw-bold text-white">
            <i class="bi bi-folder2-open me-1 text-primary"></i>${escapeHtml(f.name)}
          </td>
          <td class="font-monospace text-muted small text-truncate" style="max-width: 250px;" title="${escapeHtml(f.current_path)}">
            ${escapeHtml(f.current_path)}
          </td>
          <td>
            <span class="badge ${f.drive_letter.startsWith('C') ? 'bg-secondary' : 'bg-primary'}">${escapeHtml(f.drive_letter)}</span>
          </td>
          <td class="fw-semibold font-monospace ${f.size_gb > 1.0 ? 'text-warning' : 'text-info'}">
            ${f.size_gb >= 0.01 ? `${f.size_gb} ГБ` : `${f.size_mb} МБ`}
          </td>
          <td class="small text-muted font-monospace">${f.file_count}</td>
          <td class="text-end">
            <button class="btn btn-xs ${canRelocate ? 'btn-outline-warning' : 'btn-outline-secondary'} py-0 px-2 wb-btn-relocate-modal" 
                    data-folder-id="${escapeHtml(f.folder_id)}"
                    ${!canRelocate ? 'title="Нет подходящих дисков с достаточным местом"' : 'title="Перенести на другой диск"'}
                    style="font-size: 0.72rem;">
              <i class="bi bi-box-arrow-right me-1"></i>Перенести
            </button>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.wb-btn-relocate-modal').forEach(btn => {
      btn.onclick = () => {
        const fid = btn.getAttribute('data-folder-id');
        openRelocateModal(fid);
      };
    });

  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center py-3 text-danger">Ошибка загрузки: ${escapeHtml(e.message)}</td></tr>`;
  }
}

/**
 * Открытие модального окна переноса папки на другой диск.
 * @param {string} folderId - Идентификатор системной папки
 */
export function openRelocateModal(folderId) {
  if (!sharedState.userFoldersData) return;
  const folder = (sharedState.userFoldersData.folders || []).find(f => f.folder_id === folderId);
  if (!folder) return;

  const elId = document.getElementById('wb-relocate-folder-id');
  const elName = document.getElementById('wb-relocate-folder-name');
  const elPath = document.getElementById('wb-relocate-folder-path');
  const elSize = document.getElementById('wb-relocate-folder-size');
  const selectDrive = document.getElementById('wb-relocate-target-drive');
  const elHint = document.getElementById('wb-relocate-drive-hint');

  if (elId) elId.value = folder.folder_id;
  if (elName) elName.textContent = folder.name;
  if (elPath) elPath.textContent = folder.current_path;
  if (elSize) elSize.textContent = `${folder.size_gb >= 0.01 ? `${folder.size_gb} ГБ` : `${folder.size_mb} МБ`} (${folder.file_count} файлов)`;

  const inputPath = document.getElementById('wb-relocate-target-path');
  if (inputPath) inputPath.value = '';

  if (selectDrive) {
    selectDrive.innerHTML = '<option value="">-- Выберите диск --</option>';
    const folderDrive = folder.drive_letter.replace('\\', '').toUpperCase();
    let firstSuitableDrive = null;

    (sharedState.userFoldersData.drives || []).forEach(d => {
      const dLetter = d.drive_letter.replace('\\', '').toUpperCase();
      if (dLetter === folderDrive) return;

      const isEnough = d.free_space_gb >= (folder.size_gb + 1.0);
      const opt = document.createElement('option');
      opt.value = d.drive_letter;
      opt.textContent = `${d.drive_letter} (${d.fstype}) — Свободно: ${d.free_space_gb} ГБ из ${d.total_space_gb} ГБ ${isEnough ? '✅ Достаточно места' : '⚠️ Мало места'}`;
      if (!isEnough) {
        opt.disabled = true;
      } else if (!firstSuitableDrive) {
        firstSuitableDrive = d.drive_letter;
      }
      selectDrive.appendChild(opt);
    });

    if (firstSuitableDrive) {
      selectDrive.value = firstSuitableDrive;
      if (inputPath) {
        const d = firstSuitableDrive.replace('/', '\\').replace(/\\+$/, '');
        const parts = folder.current_path.split('\\');
        const folderSubname = parts[parts.length - 1] || folder.name;
        const userMatch = folder.current_path.match(/Users\\([^\\]+)/i);
        const username = userMatch ? userMatch[1] : 'User';
        inputPath.value = `${d}\\Users\\${username}\\${folderSubname}`;
      }
    }
  }

  if (elHint) {
    elHint.textContent = 'Требуется свободного места: минимум ' + (folder.size_gb + 1.0).toFixed(2) + ' ГБ (размер + 1 ГБ резерва).';
  }

  showModal('wb-relocate-modal');
}

/**
 * Выполнение процесса переноса пользовательской папки на целевой диск.
 */
export async function executeFolderRelocation() {
  const btn = document.getElementById('wb-btn-execute-relocate');
  const folderId = document.getElementById('wb-relocate-folder-id')?.value;
  const targetDrive = document.getElementById('wb-relocate-target-drive')?.value;
  const targetPath = document.getElementById('wb-relocate-target-path')?.value?.trim();
  const deleteSource = document.getElementById('wb-relocate-delete-source')?.checked || false;

  if (!folderId || (!targetDrive && !targetPath)) {
    alert('Пожалуйста, выберите целевой диск или укажите целевую папку для переноса.');
    return;
  }

  const destDisplay = targetPath || targetDrive;
  if (!confirm(`Подтвердите перенос папки в "${destDisplay}".\nВсе файлы будут скопированы, а системные пути и библиотеки перенастроены.`)) {
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Перенос...';
  }

  try {
    const res = await fetch('/api/v1/windows-backup/user-folders/relocate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_id: folderId,
        target_drive_letter: targetDrive || null,
        target_path: targetPath || null,
        delete_source_after: deleteSource
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      alert(data.message || 'Перенос успешно завершен!');
      hideModal('wb-relocate-modal');
      if (typeof window.loadBackupData === 'function') {
        await window.loadBackupData();
      }
    } else {
      alert('Ошибка переноса: ' + (data.detail || data.message || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Сетевая ошибка при переносе: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-circle"></i> <span>Выполнить перенос</span>';
    }
  }
}

/**
 * Открытие системного диалога выбора папки (Browse Folder).
 */
export async function browseRelocateTargetFolder() {
  const btn = document.getElementById('wb-btn-browse-folder');
  const currentPathVal = document.getElementById('wb-relocate-target-path')?.value || '';
  const currentDriveVal = document.getElementById('wb-relocate-target-drive')?.value || '';
  const initialPath = currentPathVal || (currentDriveVal ? currentDriveVal + '\\' : '');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Выбор...';
  }

  try {
    const res = await fetch(`/api/v1/windows-backup/browse-folder?initial_path=${encodeURIComponent(initialPath)}`, {
      method: 'POST'
    });
    const data = await res.json();
    if (res.ok && data.selected_path) {
      const chosenPath = data.selected_path;
      const inputPath = document.getElementById('wb-relocate-target-path');
      if (inputPath) inputPath.value = chosenPath;

      const driveLetter = chosenPath.match(/^[a-zA-Z]:/)?.[0]?.toUpperCase();
      const selectRelocateDrive = document.getElementById('wb-relocate-target-drive');
      if (driveLetter && selectRelocateDrive) {
        for (let opt of selectRelocateDrive.options) {
          if (opt.value && opt.value.toUpperCase().startsWith(driveLetter)) {
            selectRelocateDrive.value = opt.value;
            break;
          }
        }
      }
    }
  } catch (err) {
    console.error('[WindowsBackup] Browse folder error:', err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-folder2-open"></i> <span>Обзор...</span>';
    }
  }
}

/**
 * Привязка событий элементов управления пользовательскими папками.
 */
export function bindUserFoldersEvents() {
  const btnRefreshFolders = document.getElementById('wb-btn-refresh-user-folders');
  if (btnRefreshFolders && !btnRefreshFolders._bound) {
    btnRefreshFolders._bound = true;
    btnRefreshFolders.onclick = () => loadUserFoldersOverview();
  }

  const selectRelocateDrive = document.getElementById('wb-relocate-target-drive');
  if (selectRelocateDrive && !selectRelocateDrive._bound) {
    selectRelocateDrive._bound = true;
    selectRelocateDrive.onchange = () => {
      const driveVal = selectRelocateDrive.value;
      const folderId = document.getElementById('wb-relocate-folder-id')?.value;
      const folder = (sharedState.userFoldersData?.folders || []).find(f => f.folder_id === folderId);
      const inputPath = document.getElementById('wb-relocate-target-path');
      if (driveVal && folder && inputPath) {
        const d = driveVal.replace('/', '\\').replace(/\\+$/, '');
        const parts = folder.current_path.split('\\');
        const folderSubname = parts[parts.length - 1] || folder.name;
        const userMatch = folder.current_path.match(/Users\\([^\\]+)/i);
        const username = userMatch ? userMatch[1] : 'User';
        inputPath.value = `${d}\\Users\\${username}\\${folderSubname}`;
      }
    };
  }

  const btnBrowseFolder = document.getElementById('wb-btn-browse-folder');
  if (btnBrowseFolder && !btnBrowseFolder._bound) {
    btnBrowseFolder._bound = true;
    btnBrowseFolder.onclick = browseRelocateTargetFolder;
  }

  const btnExecRelocate = document.getElementById('wb-btn-execute-relocate');
  if (btnExecRelocate && !btnExecRelocate._bound) {
    btnExecRelocate._bound = true;
    btnExecRelocate.onclick = executeFolderRelocation;
  }
}
