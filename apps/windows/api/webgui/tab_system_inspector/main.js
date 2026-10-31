/**
 * =============================================================================
 * Process Name: Windows System Inspector Tab - Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки мониторинга оборудования (tab_system_inspector).
 *   Координирует жизненный цикл, соединение WebSocket (/api/v1/system/stream)
 *   и делегирует логику изолированным панелям в директориях panel_<panel_id>.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_system_inspector
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 19:05:00
 * =============================================================================
 */

import { fetchAvailableTimeRanges } from './common/ui_utils.js';
import { initCpuPanel, fetchCpuLoadFromApi, updateCpuTelemetry } from './panel_cpu/panel.js';
import { initRamPanel, fetchMemoryIoFromApi, updateRamTelemetry } from './panel_ram/panel.js';
import { initGpuPanel, fetchGpuLoadFromApi, updateGpuTelemetry } from './panel_gpu/panel.js?v=20261031_v1';
import { initNetworkPanel, fetchNetworkLoadFromApi, updateNetworkTelemetry, handleNetworkHashRouting } from './panel_network/panel.js';
import { initStoragePanel, fetchStorageLoadFromApi } from './panel_storage/panel.js';
import { initWatcherPanel, fetchLiveFileEvents } from './panel_watcher/panel.js';
import { initAiCopilotPanel } from './panel_ai_copilot/panel.js';
import { initIntervalsPanel, openSysIntervalsModal } from './panel_intervals/panel.js';

let sysWs = null;
let wsFailCount = 0;
let isSysInitialized = false;
let sysWsReconnectTimer = null;
let currentUiRefreshSeconds = 5;

/**
 * Подключение WebSocket потока телеметрии оборудования.
 */
function connectSystemWebSocket() {
  if (sysWs && (sysWs.readyState === WebSocket.OPEN || sysWs.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/v1/system/stream`;

  try {
    sysWs = new WebSocket(wsUrl);
    const statusBadge = document.getElementById('sys-conn-status');

    sysWs.onopen = () => {
      wsFailCount = 0;
      if (statusBadge) {
        statusBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-3 py-2';
        statusBadge.innerText = '● Телеметрия активна';
      }
    };

    sysWs.onmessage = (evt) => {
      try {
        const snap = JSON.parse(evt.data);
        dispatchTelemetrySnapshot(snap);
      } catch (e) {
        console.error('[SystemInspector] Ошибка разбора пакета телеметрии:', e);
      }
    };

    sysWs.onclose = () => {
      if (statusBadge) {
        statusBadge.className = 'badge rounded-pill bg-secondary-subtle text-secondary border border-secondary px-3 py-2';
        statusBadge.innerText = '○ Режим REST API';
      }
    };
  } catch (err) {
    console.debug('[SystemInspector] WebSocket stream unavailable:', err);
  }
}

/**
 * Отключение WebSocket потока телеметрии при уходе со вкладки.
 */
function disconnectSystemWebSocket() {
  if (sysWsReconnectTimer) {
    clearTimeout(sysWsReconnectTimer);
    sysWsReconnectTimer = null;
  }
  if (sysWs) {
    try {
      sysWs.close();
    } catch {}
    sysWs = null;
  }
}

/**
 * Распределение поступившего снимка телеметрии по панелям.
 * @param {Object} snap - Единый снимок SystemSnapshot
 */
function dispatchTelemetrySnapshot(snap) {
  if (!snap) return;
  if (snap.cpu) updateCpuTelemetry(snap.cpu);
  if (snap.memory) updateRamTelemetry(snap.memory);
  if (snap.gpus || snap.gpu) updateGpuTelemetry(snap.gpus || snap.gpu);
  if (snap.network) updateNetworkTelemetry(snap.network);
}

/**
 * Регистрация фонового опроса панелей при неактивном WebSocket.
 * @param {number} seconds - Интервал в секундах
 */
function setupSysSensorInterval(seconds) {
  currentUiRefreshSeconds = seconds;
  const pollHandler = async () => {
    try {
      await fetchCpuLoadFromApi();
      await fetchMemoryIoFromApi();
      await fetchNetworkLoadFromApi();
      await fetchStorageLoadFromApi();
      await fetchGpuLoadFromApi();
      await fetchLiveFileEvents();
    } catch (e) {
      console.debug('[SystemInspector] REST polling error:', e);
    }
  };

  if (window.registerTabPoller) {
    window.registerTabPoller('tab-hardware-load-inspector', pollHandler, seconds * 1000, { pollerId: 'hw_load_inspector', immediate: false });
  }
}

/**
 * Переключение компактного / развернутого режима для всех панелей вкладки.
 */
export function toggleSysCompactMode() {
  const container = document.querySelector('.sys-container.theme-inspector');
  const btn = document.getElementById('btn-sys-toggle-compact');
  if (!container) return;

  const isCompact = container.classList.contains('sys-compact-mode');
  if (isCompact) {
    // Разворачиваем все панели
    container.classList.remove('sys-compact-mode');
    if (btn) {
      btn.classList.remove('collapsed');
      btn.title = '';
    }
    document.querySelectorAll('.sys-drill-btn').forEach((b) => {
      b.classList.add('active');
    });
    document.querySelectorAll('.sys-card.sys-card-collapsed').forEach((card) => {
      card.classList.remove('sys-card-collapsed');
    });
    document.querySelectorAll('.sys-card-details-collapse').forEach((el) => {
      el.classList.add('show');
      el.style.display = 'block';
    });
    const cpuCollapse = document.getElementById('sys-cpu-details-collapse');
    if (cpuCollapse) {
      cpuCollapse.style.display = 'flex';
      const cpuDrillBtn = document.getElementById('sys-cpu-details-drill-btn');
      if (cpuDrillBtn) cpuDrillBtn.classList.remove('collapsed');
    }
  } else {
    // Сворачиваем все панели в компактный вид
    container.classList.add('sys-compact-mode');
    if (btn) {
      btn.classList.add('collapsed');
      btn.title = '';
    }
    document.querySelectorAll('.sys-card.sys-card-drill-expanded').forEach((card) => {
      card.classList.remove('sys-card-drill-expanded');
    });
    document.querySelectorAll('.sys-card.sys-card-collapsed').forEach((card) => {
      card.classList.remove('sys-card-collapsed');
    });
    document.querySelectorAll('.sys-drill-btn').forEach((b) => {
      b.classList.remove('active');
    });
    document.querySelectorAll('.sys-card-details-collapse').forEach((el) => {
      el.classList.remove('show');
      el.style.display = 'none';
    });
    const cpuCollapse = document.getElementById('sys-cpu-details-collapse');
    if (cpuCollapse) {
      cpuCollapse.style.display = 'none';
      const cpuDrillBtn = document.getElementById('sys-cpu-details-drill-btn');
      if (cpuDrillBtn) cpuDrillBtn.classList.add('collapsed');
    }
  }
}

/**
 * Переключение компактного вида / разворачивание drilldown отдельной карточки.
 * Открывает скрытый блок деталей (sys-card-<type>-details) по его ID при клике
 * на панель верхнего баннера с красной дрелью или непосредственно на значок дрели.
 * @param {string} cardId - Идентификатор карточки (например, 'sys-card-cpu')
 * @param {number|Event} [idxOrEvent] - Индекс GPU или объект события клика
 * @param {Event} [event] - Объект события клика (если передан idx)
 */
export function toggleSysCardDrill(cardId, idxOrEvent, event) {
  const ev = (event || (idxOrEvent instanceof Event ? idxOrEvent : window.event));
  if (ev && ev.target) {
    // Предотвращаем ложное срабатывание при клике по интерактивным элементам (кнопки, ссылки, AI карточки, селекты)
    if (ev.target.closest('#sys-cpu-specs-card, .sys-cpu-specs-card, .sys-gpu-specs-card, button:not(.sys-drill-btn), a, select, input')) {
      return;
    }
  }

  const card = document.getElementById(cardId);
  if (!card) return;
  const container = document.querySelector('.sys-container.theme-inspector');
  const isCompact = container ? container.classList.contains('sys-compact-mode') : false;
  const drillBtn = card.querySelector('.sys-drill-btn') || document.getElementById(`sys-drill-btn-${cardId.replace('sys-card-', '')}`);

  // Находим скрытый div по его уникальному ID
  const detailsDiv = document.getElementById(`${cardId}-details`) || 
                     document.getElementById(cardId.replace('sys-card-gpu-', 'sys-card-gpu-details-')) ||
                     document.getElementById(cardId.replace('sys-card-', 'sys-') + '-details') ||
                     card.querySelector('.sys-card-details-collapse');

  if (isCompact) {
    // В компактном режиме переключаем класс sys-card-drill-expanded
    const isExpanded = card.classList.toggle('sys-card-drill-expanded');
    card.classList.remove('sys-card-collapsed');
    if (drillBtn) {
      drillBtn.classList.toggle('active', isExpanded);
    }
    if (detailsDiv) {
      if (isExpanded) {
        detailsDiv.classList.add('show');
        detailsDiv.style.display = 'block';
      } else {
        detailsDiv.classList.remove('show');
        detailsDiv.style.display = 'none';
      }
    }
    // При развертывании CPU также открываем вложенный скрытый блок ядер sys-cpu-details-collapse
    if (cardId === 'sys-card-cpu' && isExpanded) {
      const cpuCollapse = document.getElementById('sys-cpu-details-collapse');
      const cpuDrillBtn = document.getElementById('sys-cpu-details-drill-btn');
      if (cpuCollapse) {
        cpuCollapse.style.display = 'flex';
        if (cpuDrillBtn) cpuDrillBtn.classList.remove('collapsed');
      }
    }
  } else {
    // В обычном (полном) режиме переключаем класс sys-card-collapsed
    const isCollapsed = card.classList.toggle('sys-card-collapsed');
    card.classList.remove('sys-card-drill-expanded');
    if (drillBtn) {
      drillBtn.classList.toggle('active', !isCollapsed);
    }
    if (detailsDiv) {
      if (isCollapsed) {
        detailsDiv.classList.remove('show');
        detailsDiv.style.display = 'none';
      } else {
        detailsDiv.classList.add('show');
        detailsDiv.style.display = 'block';
      }
    }
  }
}

/**
 * Разворачивание / сворачивание блока деталей CPU (ядра, потоки и системные датчики).
 */
export function toggleSysCpuDetails() {
  const collapse = document.getElementById('sys-cpu-details-collapse');
  const btn = document.getElementById('sys-cpu-details-drill-btn');
  if (!collapse) return;

  const isHidden = collapse.style.display === 'none' || getComputedStyle(collapse).display === 'none';
  if (isHidden) {
    collapse.style.display = 'flex';
    if (btn) btn.classList.remove('collapsed');
  } else {
    collapse.style.display = 'none';
    if (btn) btn.classList.add('collapsed');
  }
}

/**
 * Главная инициализация вкладки System Inspector.
 */
export async function initSystemInspectorTab() {
  if (isSysInitialized) return;
  isSysInitialized = true;

  // Привязка обработчиков переключения режимов свертывания
  const btnCompact = document.getElementById('btn-sys-toggle-compact');
  if (btnCompact && !btnCompact._bound) {
    btnCompact._bound = true;
    btnCompact.onclick = toggleSysCompactMode;
  }

  const btnCpuDetails = document.getElementById('sys-cpu-details-toggle-btn');
  if (btnCpuDetails && !btnCpuDetails._bound) {
    btnCpuDetails._bound = true;
    btnCpuDetails.onclick = toggleSysCpuDetails;
  }

  // Привязка обработчиков клика на панели верхних баннеров с красной дрелью
  document.querySelectorAll('.sys-card-top-banner').forEach((banner) => {
    if (banner && !banner._bound) {
      banner._bound = true;
      const card = banner.closest('.sys-card');
      if (card && card.id) {
        banner.onclick = (e) => toggleSysCardDrill(card.id, e);
      }
    }
  });

  // Инициализация обработчиков модулей панелей
  initCpuPanel();
  initRamPanel();
  initGpuPanel();
  initNetworkPanel();
  initStoragePanel();
  initWatcherPanel();
  initAiCopilotPanel();
  initIntervalsPanel();

  // Загрузка первичных диапазонов и данных панелей
  await fetchAvailableTimeRanges();
  await fetchCpuLoadFromApi();
  await fetchGpuLoadFromApi();
  await fetchMemoryIoFromApi();
  await fetchNetworkLoadFromApi();
  await fetchStorageLoadFromApi();
  await fetchLiveFileEvents();

  // Подключение живого WebSocket потока
  connectSystemWebSocket();

  // Регистрация поллера
  setupSysSensorInterval(currentUiRefreshSeconds);
}

/**
 * Обработчик активации вкладки (пользователь переключился на вкладку).
 */
export function activateSystemInspectorTab() {
  if (window.isTabActive && !window.isTabActive('tab-hardware-load-inspector') && !window.isTabActive('tab-system-load-inspector') && !window.isTabActive('tab-system-inspector')) return;
  connectSystemWebSocket();
  handleNetworkHashRouting();
  fetchCpuLoadFromApi();
  fetchGpuLoadFromApi();
  fetchMemoryIoFromApi();
  fetchStorageLoadFromApi();
  fetchNetworkLoadFromApi();
}

/**
 * Обработчик деактивации вкладки (пользователь ушел с вкладки).
 */
export function deactivateSystemInspectorTab() {
  disconnectSystemWebSocket();
}

// Экспорт глобальных обработчиков для WebGUI хоста
window.initSystemInspectorTab = initSystemInspectorTab;
window.initSystemLoadInspectorTab = initSystemInspectorTab;
window.initHardwareLoadInspectorTab = initSystemInspectorTab;
window.activateSystemInspectorTab = activateSystemInspectorTab;
window.activateSystemLoadInspectorTab = activateSystemInspectorTab;
window.activateHardwareLoadInspectorTab = activateSystemInspectorTab;
window.deactivateSystemInspectorTab = deactivateSystemInspectorTab;
window.deactivateSystemLoadInspectorTab = deactivateSystemInspectorTab;
window.deactivateHardwareLoadInspectorTab = deactivateSystemInspectorTab;
window.toggleSysCompactMode = toggleSysCompactMode;
window.toggleSysCardDrill = toggleSysCardDrill;
window.toggleSysCpuDetails = toggleSysCpuDetails;
window.openSysIntervalsModal = () => openSysIntervalsModal(currentUiRefreshSeconds);

