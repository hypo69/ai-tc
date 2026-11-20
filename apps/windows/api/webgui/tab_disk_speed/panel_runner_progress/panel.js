/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - Runner & Progress Panel
 * =============================================================================
 * Description:
 *   Модуль запуска бенчмарка, опроса прогресса выполнения и отмены задач.
 *
 * File: panel_runner_progress/panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed/panel_runner_progress
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { loadLatestHistoryResult } from '../panel_results_chart/panel.js';
import { loadHistory } from '../panel_history/panel.js';

let currentTaskId = null;
let pollTimer = null;

/**
 * Управление состоянием элементов UI во время теста.
 * @param {boolean} isRunning - Флаг активности теста.
 */
export function setUiRunning(isRunning) {
  const runAllBtn = document.getElementById('bench-run-all-btn');
  const cancelBtn = document.getElementById('bench-cancel-btn');
  const progressWrapper = document.getElementById('bench-progress-wrapper');
  const statusBadge = document.getElementById('bench-status-badge');

  if (runAllBtn) runAllBtn.disabled = isRunning;
  if (cancelBtn) {
    if (isRunning) {
      cancelBtn.classList.remove('d-none');
    } else {
      cancelBtn.classList.add('d-none');
    }
  }

  if (progressWrapper) {
    if (isRunning) {
      progressWrapper.classList.remove('d-none');
    } else {
      progressWrapper.classList.add('d-none');
    }
  }

  if (statusBadge) {
    if (isRunning) {
      statusBadge.className = 'badge bg-warning text-dark font-monospace';
      statusBadge.textContent = 'Идет тестирование...';
    } else {
      statusBadge.className = 'badge bg-secondary font-monospace';
      statusBadge.textContent = 'Готов к тесту';
    }
  }
}

/**
 * Обновление полосы прогресса.
 * @param {number} pct - Процент выполнения.
 * @param {string} msg - Сообщение фазы.
 */
export function updateProgress(pct, msg) {
  const bar = document.getElementById('bench-progress-bar');
  const pctEl = document.getElementById('bench-progress-pct');
  const msgEl = document.getElementById('bench-progress-msg');

  const val = Math.max(0, Math.min(100, pct || 0));
  if (bar) bar.style.width = `${val}%`;
  if (pctEl) pctEl.textContent = `${val}%`;
  if (msgEl && msg) msgEl.textContent = msg;
}

/**
 * Запуск тестирования производительности.
 * @param {Array<string>} profiles - Список профилей для выполнения.
 */
export async function startBenchmark(profiles) {
  const driveSelect = document.getElementById('bench-drive-select');
  const sizeSelect = document.getElementById('bench-size-select');
  const durSelect = document.getElementById('bench-duration-select');
  const typeRadio = document.querySelector('input[name="bench-type-radio"]:checked');

  const payload = {
    target_drive: driveSelect ? driveSelect.value : 'C:',
    file_size_mb: sizeSelect ? parseInt(sizeSelect.value, 10) : 256,
    duration_sec: durSelect ? parseInt(durSelect.value, 10) : 3,
    test_type: typeRadio ? typeRadio.value : 'both',
    profiles: profiles,
    disable_cache: true,
    delete_test_file: true,
  };

  setUiRunning(true);

  const summarySize = document.getElementById('bench-summary-size');
  if (summarySize) summarySize.textContent = `${payload.file_size_mb} MB`;

  try {
    const res = await fetch('/api/v1/storage/benchmark/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Не удалось запустить бенчмарк');
    }

    const task = await res.json();
    currentTaskId = task.task_id;
    pollBenchmarkTask();
  } catch (err) {
    setUiRunning(false);
    if (window.toast) {
      window.toast.error('Ошибка старта', err.message);
    } else {
      alert(`Ошибка: ${err.message}`);
    }
  }
}

/**
 * Опрос состояния запущенной фоновой задачи бенчмарка.
 */
export function pollBenchmarkTask() {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    if (!currentTaskId) {
      clearInterval(pollTimer);
      return;
    }
    if (window.isTabActive && !window.isTabActive('tab-disk-speed')) return;

    try {
      const res = await fetch(`/api/v1/storage/benchmark/status/${currentTaskId}`);
      if (!res.ok) return;

      const task = await res.json();
      updateProgress(task.progress_percent, task.destination);

      if (task.status === 'completed') {
        clearInterval(pollTimer);
        setUiRunning(false);
        if (window.toast) window.toast.success('Тест завершен', 'Результаты бенчмарка готовы');
        await loadLatestHistoryResult();
        await loadHistory();
      } else if (task.status === 'failed') {
        clearInterval(pollTimer);
        setUiRunning(false);
        if (window.toast) window.toast.error('Ошибка теста', task.error_message || 'Тестирование завершилось с ошибкой');
      } else if (task.status === 'cancelled') {
        clearInterval(pollTimer);
        setUiRunning(false);
        if (window.toast) window.toast.warning('Отменено', 'Тест был отменен');
      }
    } catch (e) {
      console.debug('[DiskSpeed] Ошибка опроса задачи:', e);
    }
  }, 1000);
}

/**
 * Отмена запущенного бенчмарка.
 */
export async function cancelBenchmark() {
  if (!currentTaskId) return;
  try {
    await fetch(`/api/v1/storage/benchmark/cancel/${currentTaskId}`, { method: 'POST' });
    if (window.toast) window.toast.info('Отмена', 'Запрос на остановку отправлен...');
  } catch (err) {
    console.error('[DiskSpeed] Ошибка отмены:', err);
  }
}
