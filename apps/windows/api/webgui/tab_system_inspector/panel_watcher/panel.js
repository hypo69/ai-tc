/**
 * =============================================================================
 * Process Name: System Inspector - File Watcher Panel
 * =============================================================================
 * Description:
 *   Модуль панели отслеживания изменений файлов в реальном времени
 *   (Multi-Directory ReadDirectoryChangesW). Включает модальный проводник папок,
 *   настройку исключений, аудит безопасности и ресайзер таблицы событий.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_watcher
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentWatchDirs = [];
let currentWatchDir = '';
let stagedWatchDirs = [];
let currentBrowserPath = 'C:\\';
let cachedDrives = [];

/**
 * Инициализация панели файлового аудита.
 */
export function initWatcherPanel() {
  const exclusionsBtn = document.getElementById('btn-sys-watch-exclusions');
  if (exclusionsBtn) {
    exclusionsBtn.onclick = () => openWatchFoldersModal('exclusions');
  }
  const watchDirBadge = document.getElementById('sys-watch-dir-badge');
  if (watchDirBadge) {
    watchDirBadge.onclick = () => openWatchFoldersModal('folders');
  }
  const liveHelpBtn = document.getElementById('btn-sys-live-help');
  if (liveHelpBtn) {
    liveHelpBtn.onclick = showLiveWatcherHelpModal;
  }

  initWatcherTableResizer();
}

/**
 * Запрос живых событий и телеметрии файловой системы.
 */
export async function fetchLiveFileEvents() {
  try {
    const [resEvents, resTelem] = await Promise.all([
      fetch('/api/v1/system/file-audit/live-events?limit=30'),
      fetch('/api/v1/system/file-audit/telemetry').catch(() => null)
    ]);

    if (resTelem && resTelem.ok) {
      const telem = await resTelem.json();
      const elRate = document.getElementById('sys-watcher-rate');
      const elCr = document.getElementById('sys-watcher-cr');
      const elMod = document.getElementById('sys-watcher-mod');
      const elDel = document.getElementById('sys-watcher-del');
      const elDrive = document.getElementById('sys-watcher-drive');
      const elDriveModel = document.getElementById('sys-watcher-drive-model');
      const elDriveTemp = document.getElementById('sys-watcher-temp');
      const elStatus = document.getElementById('sys-watcher-sensor-status');

      if (elRate) elRate.textContent = (telem.events_rate_per_sec || 0).toFixed(1);
      if (elCr) elCr.textContent = (telem.created_rate_per_sec || 0).toFixed(1);
      if (elMod) elMod.textContent = (telem.modified_rate_per_sec || 0).toFixed(1);
      if (elDel) elDel.textContent = (telem.deleted_rate_per_sec || 0).toFixed(1);
      if (elDrive) {
        elDrive.textContent = (telem.drive_letters && telem.drive_letters.length)
          ? telem.drive_letters.join(', ')
          : (telem.drive_letter || 'C:');
      }
      if (elDriveModel) elDriveModel.textContent = telem.drive_model || 'Storage';
      if (elDriveTemp) elDriveTemp.textContent = telem.drive_temperature_c != null ? `${telem.drive_temperature_c} °C` : '-- °C';

      if (elStatus) {
        if (telem.burst_deletions_alert) {
          elStatus.className = 'badge bg-danger-subtle text-danger border border-danger px-2 py-1';
          elStatus.textContent = '🚨 Всплеск удалений';
        } else if (telem.high_activity_alert) {
          elStatus.className = 'badge bg-warning-subtle text-warning border border-warning px-2 py-1';
          elStatus.textContent = '⚡ Высокий I/O';
        } else {
          elStatus.className = 'badge bg-success-subtle text-success border border-success px-2 py-1';
          elStatus.textContent = '🟢 Штатный режим';
        }
      }
    }

    if (!resEvents || !resEvents.ok) return;
    const data = await resEvents.json();
    const events = data.events || [];

    currentWatchDirs = data.watch_dirs || (data.watch_dir ? [data.watch_dir] : []);
    currentWatchDir = currentWatchDirs[0] || data.watch_dir || '';

    const dirPathEl = document.getElementById('sys-watch-dir-path');
    if (dirPathEl) {
      if (currentWatchDirs.length === 0) {
        dirPathEl.innerText = 'Папки не выбраны';
      } else if (currentWatchDirs.length === 1) {
        dirPathEl.innerText = currentWatchDirs[0].split('\\').pop() || currentWatchDirs[0];
      } else {
        dirPathEl.innerText = `${currentWatchDirs.length} папок`;
      }
    }

    const tbody = document.getElementById('sys-watcher-tbody');
    if (tbody) {
      if (events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted p-2">Ожидание изменений файлов...</td></tr>`;
        return;
      }
      tbody.innerHTML = events.map((e, idx) => `
        <tr class="sys-live-row" data-idx="${idx}" style="cursor: pointer;">
          <td class="font-monospace text-muted small">${e.timestamp?.slice(11, 19) || ''}</td>
          <td><span class="badge ${e.action === 'created' ? 'bg-success' : e.action === 'deleted' ? 'bg-danger' : 'bg-warning text-dark'}">${escapeHtml(e.action)}</span></td>
          <td class="text-truncate font-monospace small" style="max-width: 320px;" title="${escapeHtml(e.file_path)}">${escapeHtml(e.file_name || e.file_path)}</td>
          <td><span class="badge bg-dark border text-info font-monospace">${escapeHtml(e.process_name || '—')}</span></td>
        </tr>
      `).join('');
    }
  } catch (e) {
    console.warn('[WatcherPanel] Ошибка файлового аудита:', e);
  }
}

/**
 * Инициализация вертикального ресайзера таблицы файлового мониторинга.
 */
export function initWatcherTableResizer() {
  const resizer = document.getElementById('sys-watcher-table-resizer');
  const tableContainer = document.getElementById('sys-watcher-table-container');
  if (!resizer || !tableContainer) return;
  if (resizer._resizerInitialized) return;
  resizer._resizerInitialized = true;

  try {
    const saved = localStorage.getItem('sys_inspector_watcher_height');
    if (saved) {
      const h = parseInt(saved, 10);
      if (!isNaN(h) && h >= 120 && h <= 1000) tableContainer.style.height = `${h}px`;
    }
  } catch {}

  let startY = 0;
  let startH = 0;
  let isDragging = false;

  const onMouseMove = (e) => {
    if (!isDragging) return;
    const clientY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : null);
    if (clientY === null) return;
    let newH = startH + (clientY - startY);
    if (newH < 120) newH = 120;
    if (newH > 1000) newH = 1000;
    tableContainer.style.height = `${newH}px`;
  };

  const onMouseUp = () => {
    if (!isDragging) return;
    isDragging = false;
    resizer.classList.remove('resizing');
    document.body.style.cursor = '';
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    try {
      localStorage.setItem('sys_inspector_watcher_height', String(parseInt(tableContainer.style.height, 10)));
    } catch {}
  };

  resizer.addEventListener('mousedown', (e) => {
    isDragging = true;
    startY = e.clientY ?? 0;
    startH = tableContainer.getBoundingClientRect().height;
    resizer.classList.add('resizing');
    document.body.style.cursor = 'ns-resize';
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    e.preventDefault();
  });
}

/**
 * Открытие модального окна настройки отслеживаемых папок и исключений.
 * @param {'folders'|'exclusions'} initialTab - Стартовая вкладка
 */
export async function openWatchFoldersModal(initialTab = 'folders') {
  const modalEl = document.getElementById('sysWatchFoldersModal');
  if (!modalEl) return;
  if (window.bootstrap && window.bootstrap.Modal) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}

/**
 * Показ модального окна справки по мониторингу файловой системы.
 */
export function showLiveWatcherHelpModal() {
  if (window.AIModalDialog) {
    window.AIModalDialog.show({
      icon: '📁',
      title: 'Мониторинг файловой системы (Multi-Directory)',
      subtitle: 'Техническая справка подсистемы ReadDirectoryChangesW',
      panelId: 'watcher',
      tableType: 'process',
      metadata: [
        { label: 'Движок', value: 'Windows API ReadDirectoryChangesW' },
        { label: 'Режим', value: 'Параллельный опрос директорий' }
      ]
    });
  } else {
    alert('Мониторинг файлов: ReadDirectoryChangesW в реальном времени.');
  }
}
