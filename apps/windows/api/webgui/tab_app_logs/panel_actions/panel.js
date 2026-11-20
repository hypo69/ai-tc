/**
 * =============================================================================
 * Process Name: Windows App Logs - Actions and Filtering Panel
 * =============================================================================
 * Description:
 *   Модуль быстрых пресетов фильтрации, переключения режимов отображения
 *   (таблица, аудит, таймлайн, терминал, сырой файл) и экспорта данных (CSV/JSON/MD).
 *
 * File: panel_actions/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_actions
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state } from '../common/ui_utils.js';

/**
 * Применяет быстрый пресет фильтрации журнала.
 * @param {string} preset - Название пресета ('all', 'errors', 'warnings_errors', 'windows', 'ai', 'fastapi', 'hour', 'day').
 * @param {Function} [onRefresh=null] - Колбэк на обновление данных.
 */
export function applyQuickPreset(preset, onRefresh = null) {
  const levelSelect = document.getElementById('apl-level-select');
  const compSelect = document.getElementById('apl-component-select');
  const timeSelect = document.getElementById('apl-time-preset-select');
  const searchInput = document.getElementById('apl-search-input');

  if (preset === 'all') {
    if (levelSelect) levelSelect.value = '';
    if (compSelect) compSelect.value = '';
    if (timeSelect) timeSelect.value = '';
    if (searchInput) searchInput.value = '';
  } else if (preset === 'errors') {
    if (levelSelect) levelSelect.value = 'ERRORS';
  } else if (preset === 'warnings_errors') {
    if (levelSelect) levelSelect.value = 'WARNINGS_ERRORS';
  } else if (preset === 'windows') {
    if (searchInput) searchInput.value = 'Windows';
  } else if (preset === 'ai') {
    if (searchInput) searchInput.value = 'AI';
  } else if (preset === 'fastapi') {
    if (searchInput) searchInput.value = 'FastAPI';
  } else if (preset === 'hour') {
    if (timeSelect) timeSelect.value = '1h';
  } else if (preset === 'day') {
    if (timeSelect) timeSelect.value = '24h';
  }

  if (typeof onRefresh === 'function') {
    onRefresh();
  }
}

/**
 * Сбрасывает все поля фильтров к значениям по умолчанию.
 * @param {Function} [onRefresh=null] - Колбэк на обновление данных.
 */
export function resetAllFilters(onRefresh = null) {
  const searchInput = document.getElementById('apl-search-input');
  const levelSelect = document.getElementById('apl-level-select');
  const compSelect = document.getElementById('apl-component-select');
  const timeSelect = document.getElementById('apl-time-preset-select');
  const limitSelect = document.getElementById('apl-limit-select');

  if (searchInput) searchInput.value = '';
  if (levelSelect) levelSelect.value = '';
  if (compSelect) compSelect.value = '';
  if (timeSelect) timeSelect.value = '';
  if (limitSelect) limitSelect.value = '200';

  document.querySelectorAll('.apl-quick-preset-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.preset === 'all');
  });

  if (typeof onRefresh === 'function') {
    onRefresh();
  }
}

/**
 * Инициирует экспорт текущей выборки записей лога.
 * @param {string} format - Формат экспорта ('csv', 'json', 'markdown').
 */
export function triggerExport(format) {
  const search = document.getElementById('apl-search-input')?.value || '';
  const level = document.getElementById('apl-level-select')?.value || '';
  const url = `/api/v1/app_logs/export?file_name=${encodeURIComponent(state.currentFile)}&export_format=${format}&search=${encodeURIComponent(search)}&level=${encodeURIComponent(level)}`;
  window.open(url, '_blank');
}

/**
 * Переключает видимый контейнер представления.
 * @param {string} mode - Имя режима ('table', 'audit', 'timeline', 'tail', 'raw').
 * @param {Object} [handlers={}] - Обработчики переключения.
 */
export function switchViewMode(mode, handlers = {}) {
  const views = {
    table: document.getElementById('apl-view-table'),
    audit: document.getElementById('apl-view-audit'),
    timeline: document.getElementById('apl-view-timeline'),
    tail: document.getElementById('apl-view-tail'),
    raw: document.getElementById('apl-view-raw'),
  };

  Object.entries(views).forEach(([m, el]) => {
    if (!el) return;
    if (m === mode) {
      el.classList.remove('d-none');
    } else {
      el.classList.add('d-none');
    }
  });

  if (typeof handlers[mode] === 'function') {
    handlers[mode]();
  }
}
