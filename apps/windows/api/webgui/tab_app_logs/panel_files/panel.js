/**
 * =============================================================================
 * Process Name: Windows App Logs - Files Panel
 * =============================================================================
 * Description:
 *   Модуль управления файлами внутренних журналов (%APPDATA%\ai-tc\logs):
 *   загрузка списка файлов, отрисовка бейджей с индикаторами ошибок и очистка логов.
 *
 * File: panel_files/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_files
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, showAppLogsToast } from '../common/ui_utils.js';

/**
 * Загружает сводную информацию и список доступных файлов журналов.
 * @param {Function} [onChanged=null] - Колбэк при обновлении данных.
 */
export async function loadOverviewAndFiles(onChanged = null) {
  try {
    const [ovRes, filesRes] = await Promise.all([
      fetch('/api/v1/app_logs/overview').catch(() => null),
      fetch('/api/v1/app_logs/files').catch(() => null),
    ]);

    if (ovRes && ovRes.ok) {
      state.overview = await ovRes.json();
    }
    if (filesRes && filesRes.ok) {
      const data = await filesRes.json();
      state.files = data.files || [];
      const pathLabel = document.getElementById('apl-full-path-label');
      if (pathLabel && data.logs_dir) {
        pathLabel.textContent = data.logs_dir;
        pathLabel.title = data.logs_dir;
      }
    }

    renderFilesBadges(onChanged);
  } catch (err) {
    console.error('[AppLogs] Ошибка загрузки файлов и сводки:', err);
  }
}

/**
 * Очищает один выбранный файл логов.
 * @param {string} fileName - Имя файла.
 * @param {Function} [onCleared=null] - Колбэк после завершения очистки.
 */
export async function clearSingleLog(fileName, onCleared = null) {
  if (!fileName) return;
  if (!confirm(`Вы действительно хотите очистить файл "${fileName}"? Содержимое журнала будет безвозвратно удалено.`)) {
    return;
  }
  try {
    const res = await fetch('/api/v1/app_logs/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: fileName })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showAppLogsToast('Очищено', data.message || `Файл ${fileName} успешно очищен`, 'success');
      await loadOverviewAndFiles(onCleared);
      if (typeof onCleared === 'function') await onCleared();
    } else {
      showAppLogsToast('Ошибка', data.detail || 'Не удалось очистить файл', 'error');
    }
  } catch (err) {
    showAppLogsToast('Ошибка', err.message, 'error');
  }
}

/**
 * Очищает все файлы журналов приложения.
 * @param {Function} [onCleared=null] - Колбэк после завершения очистки.
 */
export async function clearAllLogs(onCleared = null) {
  if (!confirm('Вы действительно хотите очистить ВСЕ файлы логов программы (%APPDATA%\\ai-tc\\logs)? Все журналы будут обнулены.')) {
    return;
  }
  try {
    const res = await fetch('/api/v1/app_logs/clear_all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showAppLogsToast('Все логи очищены', data.message || 'Все файлы логов успешно очищены', 'success');
      await loadOverviewAndFiles(onCleared);
      if (typeof onCleared === 'function') await onCleared();
    } else {
      const errMsg = data.detail || (data.failed_files?.length ? `Некоторые файлы заблокированы процессами: ${data.failed_files.map((f) => f.name).join(', ')}` : 'Не удалось очистить все логи');
      showAppLogsToast('Внимание', errMsg, 'warning');
      await loadOverviewAndFiles(onCleared);
      if (typeof onCleared === 'function') await onCleared();
    }
  } catch (err) {
    showAppLogsToast('Ошибка', err.message, 'error');
  }
}

/**
 * Отрисовывает интерактивные бейджи файлов с индикаторами ошибок и кнопками очистки.
 * @param {Function} [onSelect=null] - Колбэк при выборе файла.
 */
export function renderFilesBadges(onSelect = null) {
  const container = document.getElementById('apl-files-badges-container');
  if (!container) return;

  container.innerHTML = '';
  if (state.files.length === 0) {
    container.innerHTML = '<span class="text-muted small">Файлы журналов не обнаружены.</span>';
    return;
  }

  // Карта ошибок по файлам из overview
  const errorMap = {};
  if (state.overview && state.overview.files) {
    state.overview.files.forEach((f) => {
      errorMap[f.name] = f.recent_errors || 0;
    });
  }

  state.files.forEach((f) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    const isActive = f.name === state.currentFile;
    const errorsCount = errorMap[f.name] || 0;
    const hasError = errorsCount > 0;

    btn.className = `btn btn-sm rounded-pill px-2.5 py-0.5 small apl-file-badge ${isActive ? 'active' : ''} ${hasError ? 'has-error' : ''}`;
    btn.style.fontSize = '0.76rem';

    const icon = f.is_json ? 'bi-filetype-json text-info' : 'bi-file-text text-warning';
    const errIndicator = hasError ? `<span class="badge bg-danger ms-1" style="font-size:0.65rem;" title="Ошибок: ${errorsCount}">${errorsCount}</span>` : '';

    btn.innerHTML = `<i class="bi ${icon} me-1"></i><strong>${f.name}</strong> <span class="badge apl-card border border-secondary-subtle ms-1">${f.size_formatted}</span>${errIndicator}`;

    // Кнопка очистки конкретно этого файла лога
    const clearBtn = document.createElement('span');
    clearBtn.className = 'apl-badge-clear-btn';
    clearBtn.title = `Очистить лог-файл ${f.name}`;
    clearBtn.innerHTML = '<i class="bi bi-trash3" style="font-size: 0.72rem;"></i>';
    clearBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await clearSingleLog(f.name, onSelect);
    });
    btn.appendChild(clearBtn);

    btn.addEventListener('click', async () => {
      state.currentFile = f.name;
      renderFilesBadges(onSelect);
      if (typeof onSelect === 'function') {
        await onSelect();
      }
    });

    container.appendChild(btn);
  });
}
