/**
 * =============================================================================
 * Process Name: Windows App Logs - Main Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки анализатора внутренних журналов ai-tc.
 *   Координирует работу панелей файлов, таблицы записей, AI-аудита, таймлайна,
 *   терминала реального времени и действий экспорта/очистки.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script type="module" src="/html/tab_app_logs/main.js?v=20261017_v1"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, showAppLogsToast } from './common/ui_utils.js';
import { loadOverviewAndFiles, clearSingleLog, clearAllLogs } from './panel_files/panel.js';
import { refreshCurrentView } from './panel_table/panel.js';
import { runAiDiagnostics } from './panel_audit/panel.js';
import { renderTimelineChart } from './panel_timeline/panel.js';
import {
  loadTailTerminal,
  loadRawContent,
  startLivePolling,
  stopLivePolling,
  isAppLogsTabActive
} from './panel_tail_raw/panel.js';
import {
  applyQuickPreset,
  resetAllFilters,
  triggerExport,
  switchViewMode
} from './panel_actions/panel.js';

/**
 * Выполняет обновление активного представления в зависимости от режима.
 */
async function refreshActiveMode() {
  if (state.currentMode === 'table') {
    // В режиме таблицы refreshCurrentView сам рендерит таблицу
  } else if (state.currentMode === 'timeline') {
    renderTimelineChart(
      (timeSlot) => {
        const searchInput = document.getElementById('apl-search-input');
        if (searchInput && timeSlot) {
          searchInput.value = timeSlot.slice(0, 13);
          const tableTab = document.querySelector('#apl-mode-tabs [data-mode="table"]');
          if (tableTab) tableTab.click();
          refreshCurrentView(refreshActiveMode);
        }
      },
      (componentName) => {
        const compSelect = document.getElementById('apl-component-select');
        if (compSelect && componentName) {
          compSelect.value = componentName;
          const tableTab = document.querySelector('#apl-mode-tabs [data-mode="table"]');
          if (tableTab) tableTab.click();
          refreshCurrentView(refreshActiveMode);
        }
      }
    );
  } else if (state.currentMode === 'tail') {
    await loadTailTerminal();
  } else if (state.currentMode === 'raw') {
    await loadRawContent();
  } else if (state.currentMode === 'audit') {
    await runAiDiagnostics();
  }
}

/**
 * Централизованное обновление данных и вида.
 */
async function refreshAll() {
  await refreshCurrentView(refreshActiveMode);
}

/**
 * Привязка обработчиков событий элементов интерфейса.
 */
function bindEvents() {
  // Переключение режимов отображения
  document.querySelectorAll('#apl-mode-tabs .nav-link').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#apl-mode-tabs .nav-link').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentMode = btn.dataset.mode;
      switchViewMode(state.currentMode, {
        audit: runAiDiagnostics,
        tail: loadTailTerminal,
        raw: loadRawContent,
        timeline: refreshActiveMode,
      });
    });
  });

  // Быстрые пресеты фильтрации
  document.querySelectorAll('.apl-quick-preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.apl-quick-preset-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.activePreset = btn.dataset.preset;
      applyQuickPreset(state.activePreset, refreshAll);
    });
  });

  // Кнопка обновления
  const btnRefresh = document.getElementById('btn-apl-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      await loadOverviewAndFiles(refreshAll);
      await refreshAll();
      showAppLogsToast('Обновлено', 'Данные журналов успешно обновлены', 'info');
    });
  }

  // Кнопка AI диагностики
  const btnDiagnose = document.getElementById('btn-apl-diagnose');
  if (btnDiagnose) {
    btnDiagnose.addEventListener('click', async () => {
      const auditBtn = document.querySelector('#apl-mode-tabs [data-mode="audit"]');
      if (auditBtn) auditBtn.click();
      await runAiDiagnostics();
    });
  }

  // Переключатель Live Stream
  const liveSwitch = document.getElementById('apl-live-switch');
  if (liveSwitch) {
    liveSwitch.addEventListener('change', (e) => {
      state.liveActive = e.target.checked;
      if (state.liveActive) {
        startLivePolling(async () => {
          if (state.currentMode === 'tail') {
            await loadTailTerminal();
          } else {
            await refreshAll();
          }
        });
        showAppLogsToast('Live Stream', 'Потоковое обновление активировано (3 сек)', 'success');
      } else {
        stopLivePolling();
        showAppLogsToast('Live Stream', 'Потоковое обновление приостановлено', 'info');
      }
    });
  }

  // Фильтры с debounce
  let searchTimeout = null;
  const searchInput = document.getElementById('apl-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => refreshAll(), 300);
    });
  }

  ['apl-level-select', 'apl-component-select', 'apl-time-preset-select', 'apl-limit-select'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => refreshAll());
  });

  // Сброс фильтров
  const btnReset = document.getElementById('btn-apl-reset-filters');
  if (btnReset) {
    btnReset.addEventListener('click', () => resetAllFilters(refreshAll));
  }

  // Экспорт
  const bindExport = (id, format) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', (e) => { e.preventDefault(); triggerExport(format); });
  };
  bindExport('btn-apl-export-csv', 'csv');
  bindExport('btn-apl-export-json', 'json');
  bindExport('btn-apl-export-md', 'markdown');

  // Скачивание сырого файла
  const btnDownloadRaw = document.getElementById('btn-apl-download-raw');
  if (btnDownloadRaw) {
    btnDownloadRaw.addEventListener('click', (e) => {
      e.preventDefault();
      window.open(`/api/v1/app_logs/download?file_name=${encodeURIComponent(state.currentFile)}`, '_blank');
    });
  }

  // Очистка активного лога
  ['btn-apl-clear', 'btn-apl-clear-raw'].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', async (e) => { e.preventDefault(); await clearSingleLog(state.currentFile, refreshAll); });
  });

  // Очистка ВСЕХ логов
  ['btn-apl-clear-all', 'btn-apl-clear-all-inline', 'btn-apl-menu-clear-all'].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', async (e) => { e.preventDefault(); await clearAllLogs(refreshAll); });
  });

  // Терминал: очистить экран и фильтр
  const btnClearTerm = document.getElementById('btn-apl-clear-terminal');
  if (btnClearTerm) {
    btnClearTerm.addEventListener('click', () => {
      const term = document.getElementById('apl-tail-terminal');
      if (term) term.textContent = '';
    });
  }

  const tailFilterInput = document.getElementById('apl-tail-filter');
  if (tailFilterInput) {
    tailFilterInput.addEventListener('input', () => loadTailTerminal());
  }

  // Копирование сырого содержимого
  const btnCopyRaw = document.getElementById('btn-apl-copy-raw');
  if (btnCopyRaw) {
    btnCopyRaw.addEventListener('click', () => {
      const content = document.getElementById('apl-raw-content')?.textContent || '';
      navigator.clipboard.writeText(content).then(() => {
        showAppLogsToast('Скопировано', 'Содержимое файла скопировано', 'success');
      });
    });
  }
}

/**
 * Инициализирует вкладку анализатора внутренних логов.
 */
export async function initAppLogsTab() {
  bindEvents();
  await loadOverviewAndFiles(refreshAll);
  await refreshAll();
}

// Экспорт методов в window и хуки жизненного цикла
if (typeof window !== 'undefined') {
  window.initAppLogsTab = initAppLogsTab;
  window.activateAppLogsTab = () => {
    if (isAppLogsTabActive() && state.liveActive) {
      startLivePolling(async () => {
        if (state.currentMode === 'tail') await loadTailTerminal();
        else await refreshAll();
      });
    }
  };
  window.deactivateAppLogsTab = () => {
    stopLivePolling();
  };

  document.addEventListener('tab:deactivated', (e) => {
    if (e.detail?.tabId === 'tab-app-logs' || e.detail?.tabId === 'app-logs') {
      stopLivePolling();
    }
  });
}

// Автоинициализация при загрузке документа
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAppLogsTab);
  } else {
    initAppLogsTab();
  }
}
