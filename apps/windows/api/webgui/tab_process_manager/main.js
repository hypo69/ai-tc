/**
 * @file apps/windows/api/webgui/tab_process_manager/main.js
 * @description Корневой модуль-оркестратор вкладки Process Manager (Диспетчер процессов и приложений Windows)
 * @author hypo69
 * @version 2.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { renderProcessTable, killProcess } from './panel_table/panel.js';
import {
  findAndShowProcessAiModal,
  openProcessAiModal,
  openFirstAvailableProcessAiModal,
  runProcessDiagnostics,
  sendChat,
  closeModalDialogElement
} from './panel_modal_ai/panel.js';

let currentReport = null;
let currentCategoryFilter = 'all';
let allExpanded = false;
const expandedGroups = new Set();
let isInitialized = false;

/**
 * Получение текущего состояния отчета процессов
 * @returns {Object|null}
 */
export function getCurrentReport() {
  return currentReport;
}

/**
 * Загрузка сводки процессов через Task Manager API
 */
export async function fetchProcessManagerSummary() {
  const refreshBtn = document.getElementById('pm-refresh-btn');
  if (refreshBtn) {
    const icon = refreshBtn.querySelector('i');
    if (icon) icon.classList.add('bi-spin');
  }

  try {
    const res = await fetch('/api/v1/process-manager/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentReport = await res.json();
    updateStatCards(currentReport);
    applyProcessFilters();
  } catch (err) {
    console.error('[ProcessManager] Ошибка загрузки сводки:', err);
    const tbody = document.getElementById('pm-process-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4">Ошибка загрузки процессов: ${err.message}</td></tr>`;
    }
  } finally {
    if (refreshBtn) {
      const icon = refreshBtn.querySelector('i');
      if (icon) icon.classList.remove('bi-spin');
    }
  }
}

/**
 * Обновление карточек статистики панели
 * @param {Object} report
 */
function updateStatCards(report) {
  if (!report) return;

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  const apps = report.apps || [];
  const bg = report.background_processes || [];
  const win = report.windows_processes || [];

  setVal('pm-count-apps', apps.length);
  setVal('pm-count-bg', bg.length);
  setVal('pm-count-win', win.length);
  setVal('pm-count-total', report.total_processes_count || (apps.length + bg.length + win.length));

  if (report.total_cpu_percent !== undefined) {
    setVal('pm-stat-total-cpu', `${report.total_cpu_percent.toFixed(1)}%`);
  }
  if (report.total_memory_mb !== undefined) {
    const memGb = report.total_memory_mb / 1024;
    setVal('pm-stat-total-ram', memGb >= 1 ? `${memGb.toFixed(1)} GB` : `${Math.round(report.total_memory_mb)} MB`);
  }
}

/**
 * Применение фильтров категории и текстового поиска
 */
export function applyProcessFilters() {
  const searchInput = document.getElementById('pm-search-input');
  const searchTerm = searchInput ? searchInput.value.trim() : '';

  renderProcessTable(
    currentReport,
    currentCategoryFilter,
    searchTerm,
    allExpanded,
    expandedGroups,
    (type, name, pid) => findAndShowProcessAiModal(type, name, pid, currentReport, handleKillProcess),
    handleKillProcess,
    (groupId) => {
      if (expandedGroups.has(groupId)) {
        expandedGroups.delete(groupId);
      } else {
        expandedGroups.add(groupId);
      }
      applyProcessFilters();
    }
  );
}

/**
 * Обработка завершения процесса с обновлением данных
 */
function handleKillProcess(pid, name, killTree = false) {
  killProcess(pid, name, killTree, () => {
    closeModalDialogElement();
    fetchProcessManagerSummary();
  });
}

/**
 * Установка фильтра категории через карточки или радиобаттоны
 * @param {string} cat Категория ('all', 'app', 'background', 'windows')
 */
export function setCategoryFilter(cat) {
  currentCategoryFilter = cat;
  const radio = document.querySelector(`input[name="pm-cat-filter"][value="${cat}"]`);
  if (radio) radio.checked = true;
  applyProcessFilters();
}

/**
 * Инициализация вкладки Process Manager
 */
export function initProcessManagerTab() {
  if (isInitialized) return;
  isInitialized = true;

  const refreshBtn = document.getElementById('pm-refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', fetchProcessManagerSummary);

  const searchInput = document.getElementById('pm-search-input');
  if (searchInput) searchInput.addEventListener('input', applyProcessFilters);

  // Фильтры по карточкам
  const cardApps = document.getElementById('pm-filter-card-apps');
  const cardBg = document.getElementById('pm-filter-card-bg');
  const cardWin = document.getElementById('pm-filter-card-win');
  const cardAll = document.getElementById('pm-filter-card-all');

  if (cardApps) cardApps.addEventListener('click', () => setCategoryFilter('app'));
  if (cardBg) cardBg.addEventListener('click', () => setCategoryFilter('background'));
  if (cardWin) cardWin.addEventListener('click', () => setCategoryFilter('windows'));
  if (cardAll) cardAll.addEventListener('click', () => setCategoryFilter('all'));

  // Фильтры по радиокнопкам
  document.querySelectorAll('input[name="pm-cat-filter"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      currentCategoryFilter = e.target.value;
      applyProcessFilters();
    });
  });

  // Кнопка развернуть / свернуть все
  const toggleExpandBtn = document.getElementById('pm-toggle-expand-btn');
  const expandText = document.getElementById('pm-expand-btn-text');
  if (toggleExpandBtn) {
    toggleExpandBtn.addEventListener('click', () => {
      allExpanded = !allExpanded;
      if (expandText) expandText.textContent = allExpanded ? 'Свернуть все' : 'Развернуть все';
      applyProcessFilters();
    });
  }

  // Кнопка прямого открытия модального окна ИИ-помощника в шапке панели
  const openAiBtn = document.getElementById('pm-btn-open-ai-modal');
  if (openAiBtn) {
    openAiBtn.addEventListener('click', () => {
      if (!currentReport) {
        fetchProcessManagerSummary().then(() => openFirstAvailableProcessAiModal(currentReport, handleKillProcess));
      } else {
        openFirstAvailableProcessAiModal(currentReport, handleKillProcess);
      }
    });
  }

  // Кнопка настройки промпта ИИ для панели процессов
  const promptBtn = document.getElementById('pm-btn-prompt-settings');
  if (promptBtn) {
    promptBtn.addEventListener('click', () => {
      const modal = window.AIModalDialog || window.AITableModal || (window.parent && (window.parent.AIModalDialog || window.parent.AITableModal));
      if (modal && typeof modal.openPromptEditor === 'function') {
        modal.openPromptEditor('process', 'panel-process-manager-dispetcher-protsessov-i-prilozhen');
      } else {
        openFirstAvailableProcessAiModal(currentReport, handleKillProcess);
      }
    });
  }

  // Обработчики модального окна локального DOM
  const closeX = document.getElementById('pm-modal-close-x');
  if (closeX) closeX.addEventListener('click', closeModalDialogElement);

  const closeBtn = document.getElementById('pm-modal-close-btn');
  if (closeBtn) closeBtn.addEventListener('click', closeModalDialogElement);

  const diagBtn = document.getElementById('btn-pm-modal-diagnose');
  if (diagBtn) diagBtn.addEventListener('click', runProcessDiagnostics);

  const chatSendBtn = document.getElementById('pm-chat-send-btn');
  if (chatSendBtn) chatSendBtn.addEventListener('click', () => sendChat());

  const chatInput = document.getElementById('pm-chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendChat();
      }
    });
  }

  const quickBtns = document.getElementById('pm-chat-quick-buttons');
  if (quickBtns) {
    quickBtns.querySelectorAll('button[data-question]').forEach(btn => {
      btn.addEventListener('click', () => {
        sendChat(btn.getAttribute('data-question'));
      });
    });
  }

  // Закрытие по Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modalEl = document.getElementById('pm-process-ai-modal');
      if (modalEl && modalEl.classList.contains('show')) {
        closeModalDialogElement();
      }
    }
  });

  if (typeof registerTabPoller === 'function') {
    registerTabPoller('tab-process-manager', fetchProcessManagerSummary, 5000, { immediate: true });
  } else {
    fetchProcessManagerSummary();
  }
}

window.initProcessManagerTab = initProcessManagerTab;
window.fetchProcessManagerSummary = fetchProcessManagerSummary;
