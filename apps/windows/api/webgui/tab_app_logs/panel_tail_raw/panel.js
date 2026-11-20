/**
 * =============================================================================
 * Process Name: Windows App Logs - Live Tail and Raw View Panel
 * =============================================================================
 * Description:
 *   Модуль потокового терминала реального времени (Live Tail), фонового опроса
 *   (Live Polling) и инспекции сырых текстовых файлов журналов.
 *
 * File: panel_tail_raw/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_tail_raw
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, escapeHtml } from '../common/ui_utils.js';

/**
 * Проверяет, активна ли в данный момент вкладка App Logs.
 * @returns {boolean} Флаг активности.
 */
export function isAppLogsTabActive() {
  if (typeof document !== 'undefined' && document.hidden) return false;
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive('tab-app-logs') || window.isTabActive('app-logs'));
  }
  const pane = document.getElementById('tab-app-logs') || document.getElementById('app-logs');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Загружает и отображает последние строки в терминале Live Tail.
 */
export async function loadTailTerminal() {
  const term = document.getElementById('apl-tail-terminal');
  if (!term) return;

  const filterText = (document.getElementById('apl-tail-filter')?.value || '').toLowerCase();

  try {
    const res = await fetch(`/api/v1/app_logs/tail?file_name=${encodeURIComponent(state.currentFile)}&lines=150`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    let lines = data.lines || [];
    if (filterText) {
      lines = lines.filter((l) => l.toLowerCase().includes(filterText));
    }

    term.textContent = lines.join('\n') || '[Файл логов пуст или нет совпадений по фильтру]';

    const autoscroll = document.getElementById('apl-tail-autoscroll')?.checked;
    if (autoscroll) {
      term.scrollTop = term.scrollHeight;
    }
  } catch (err) {
    term.textContent = `[Ошибка чтения tail: ${escapeHtml(err.message)}]`;
  }
}

/**
 * Загружает сырое содержимое активного лог-файла.
 */
export async function loadRawContent() {
  const pre = document.getElementById('apl-raw-content');
  if (!pre) return;

  pre.textContent = 'Загрузка содержимого файла...';
  try {
    const res = await fetch(`/api/v1/app_logs/tail?file_name=${encodeURIComponent(state.currentFile)}&lines=500`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    pre.textContent = (data.lines || []).join('\n') || '[Файл логов пуст]';
  } catch (err) {
    pre.textContent = `[Ошибка чтения: ${escapeHtml(err.message)}]`;
  }
}

/**
 * Запускает фоновый опрос для потокового обновления.
 * @param {Function} onPollTick - Обработчик тика опроса.
 */
export function startLivePolling(onPollTick) {
  stopLivePolling();
  if (!isAppLogsTabActive()) return;

  if (window.registerTabPoller) {
    window.registerTabPoller('tab-app-logs', async () => {
      if (!isAppLogsTabActive()) return;
      if (typeof onPollTick === 'function') {
        await onPollTick();
      }
    }, 3000, { pollerId: 'tab-app-logs_live', immediate: false });
  } else {
    state.liveTimer = setInterval(async () => {
      if (!isAppLogsTabActive()) {
        stopLivePolling();
        return;
      }
      if (typeof onPollTick === 'function') {
        await onPollTick();
      }
    }, 3000);
  }
}

/**
 * Останавливает фоновый опрос.
 */
export function stopLivePolling() {
  if (state.liveTimer) {
    clearInterval(state.liveTimer);
    state.liveTimer = null;
  }
  if (window.unregisterTabPoller) {
    window.unregisterTabPoller('tab-app-logs_live');
  }
}
