/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор объединенной вкладки окружения пользователя
 *   (User Environment): Панель задач, Звук и Аудиомикшер, Окна рабочего стола,
 *   Сессии фокусировки (Focus Assist), Персонализация и SafeOps аудит с откатом.
 *   Обеспечивает маршрутизацию блоков в URL стандарта #tab-user-environment#panel-<block>.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_user_environment/main.js?v=20261101_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:02:30
 * =============================================================================
 */

import { loadSoundState, bindSoundEvents } from './panel_sound.js';
import {
  loadTaskbarSummary,
  loadTaskbarSettings,
  loadPinnedApps,
  restartExplorer,
  bindTaskbarEvents
} from './panel_taskbar.js';
import {
  loadWindows,
  bindWindowsEvents,
  openWindowCopilotModal,
  executeWindowAction
} from './panel_windows.js?v=20261101_v1';
import { loadFocusState, bindFocusEvents } from './panel_focus.js';
import { loadPersonalizationState, bindPersonalizationEvents } from './panel_personalization.js';
import { loadHistory, rollbackLast, bindHistoryEvents } from './panel_history.js';

export const TAB_ID = 'tab-user-environment';
export const CANONICAL_PANELS = [
  'panel-taskbar',
  'panel-sound',
  'panel-windows',
  'panel-focus',
  'panel-personalization',
  'panel-history'
];

let _isInitialized = false;
let _currentSubTabId = 'panel-taskbar';

/**
 * Проверяет, активна ли вкладка User Environment.
 * @returns {boolean}
 */
export function isUserEnvironmentTabActive() {
  if (typeof document !== 'undefined' && document.hidden) return false;
  if (typeof window.isTabActive === 'function') {
    return Boolean(
      window.isTabActive(TAB_ID) ||
      window.isTabActive('user-environment') ||
      window.isTabActive('tab-user-enviroment') ||
      window.isTabActive('user-enviroment')
    );
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('tab-user-enviroment');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор или алиас блока к каноническому виду panel-<name>.
 * @param {string} rawId - Сырой идентификатор панели/блока.
 * @returns {string} Канонический идентификатор (например 'panel-sound').
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'panel-taskbar';
  const s = String(rawId).toLowerCase().trim().replace(/^#/, '');

  if (s.includes('sound') || s.includes('audio') || s.includes('volume') || s.includes('wasapi') || s.includes('mixer')) {
    return 'panel-sound';
  }
  if (s.includes('window') || s.includes('desktop') || s.includes('hwnd') || s.includes('dwm')) {
    return 'panel-windows';
  }
  if (s.includes('focus') || s.includes('dnd') || s.includes('assist')) {
    return 'panel-focus';
  }
  if (s.includes('personal') || s.includes('display') || s.includes('screen') || s.includes('orient') || s.includes('theme')) {
    return 'panel-personalization';
  }
  if (s.includes('history') || s.includes('safeops') || s.includes('audit') || s.includes('rollback')) {
    return 'panel-history';
  }
  if (s.includes('taskbar') || s.includes('dock') || s.includes('pin') || s.includes('tray')) {
    return 'panel-taskbar';
  }

  const cleaned = s.replace(/^ue-panel-/, '').replace(/^panel-/, '');
  if (CANONICAL_PANELS.includes(`panel-${cleaned}`)) {
    return `panel-${cleaned}`;
  }
  return 'panel-taskbar';
}

/**
 * Считывает идентификатор активного блока из URL hash.
 * Поддерживает форматы:
 * - #tab-user-environment#panel-sound
 * - #tab-user-environment#sound
 * - #tab-user-enviroment#panel-sound
 * - #panel-sound
 * @returns {string|null} Канонический идентификатор панели или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'tab-user-enviroment' || mainPart === 'user-environment' || mainPart === 'user-enviroment') {
      return normalizeSubTabId(parts[1]);
    }
  } else if (parts.length === 1) {
    const single = parts[0];
    if (single !== TAB_ID && single !== 'tab-user-enviroment' && single !== 'user-environment' && single !== 'user-enviroment') {
      if (single.startsWith('panel-') || single.startsWith('ue-panel-')) {
        return normalizeSubTabId(single);
      }
    }
  }
  return null;
}

/**
 * Возвращает идентификатор текущего активного блока.
 * @returns {string} Канонический ID панели (например, 'panel-sound').
 */
export function getActiveSubTabId() {
  const activeBtn = document.querySelector('#userEnvSubTabs button.active');
  if (activeBtn) {
    const pId = activeBtn.getAttribute('data-panel-id');
    if (pId) return normalizeSubTabId(pId);
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(target);
  }
  return _currentSubTabId || 'panel-taskbar';
}

/**
 * Обновляет адресную строку браузера в соответствии со стандартом (#tab-user-environment#panel-<block>) без перезагрузки страницы.
 * @param {string} panelId - Идентификатор блока/панели.
 */
export function updateUrlWithPanel(panelId) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';
  const newHash = `#${TAB_ID}#${canonical}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
      document.dispatchEvent(new CustomEvent('panel:activated', { detail: { tabId: TAB_ID, panelId: canonical } }));
    } catch (_) {}
  }
}

/**
 * Загрузка данных строго для активированного блока (Active-Only).
 * @param {string} blockId - Канонический ID блока ('panel-sound', 'panel-taskbar', и т.д.).
 */
export async function fetchActiveBlockData(blockId) {
  const canonical = normalizeSubTabId(blockId);
  switch (canonical) {
    case 'panel-taskbar':
      await Promise.allSettled([
        loadTaskbarSummary(),
        loadTaskbarSettings(),
        loadPinnedApps()
      ]);
      break;
    case 'panel-sound':
      await loadSoundState();
      break;
    case 'panel-windows':
      await loadWindows();
      break;
    case 'panel-focus':
      await loadFocusState();
      break;
    case 'panel-personalization':
      await loadPersonalizationState();
      break;
    case 'panel-history':
      await loadHistory(refreshAll);
      break;
  }
}

/**
 * Переключение активного блока интерфейса с синхронизацией URL hash по стандарту.
 * @param {string} panelName - Имя блока/панели (taskbar, sound, windows, focus, personalization, history).
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchSubTab(panelName, updateUrl = true) {
  if (!panelName) return;
  const canonical = normalizeSubTabId(panelName);
  const shortName = canonical.replace(/^panel-/, '');
  _currentSubTabId = canonical;

  const btn = document.getElementById(`ue-tab-btn-${shortName}`);
  const targetPaneId = `ue-panel-${shortName}`;
  const pane = document.getElementById(targetPaneId);

  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      try {
        const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
        tabInst.show();
      } catch (_) {}
    }
    document.querySelectorAll('#userEnvSubTabs button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }

  if (pane) {
    document.querySelectorAll('#userEnvSubTabContent > .tab-pane').forEach(p => p.classList.remove('show', 'active'));
    pane.classList.add('show', 'active');
  }

  // Загрузка данных для выбранного блока
  fetchActiveBlockData(canonical);

  if (updateUrl) {
    updateUrlWithPanel(canonical);
  }
}

/**
 * Полное обновление всех панелей окружения пользователя.
 */
export async function refreshAll() {
  await Promise.allSettled([
    loadSoundState(),
    loadTaskbarSummary(),
    loadTaskbarSettings(),
    loadPinnedApps(),
    loadWindows(),
    loadFocusState(),
    loadPersonalizationState(),
    loadHistory(refreshAll)
  ]);
}

/**
 * Привязка общих событий шапки и субпанелей.
 */
function bindGlobalEvents() {
  // Кнопки верхней панели действий
  document.getElementById('ue-btn-refresh-all')?.addEventListener('click', () => refreshAll());
  document.getElementById('ue-btn-rollback-last-header')?.addEventListener('click', () => rollbackLast(refreshAll));
  document.getElementById('ue-btn-restart-explorer-header')?.addEventListener('click', () => restartExplorer(refreshAll));

  // Клики по кнопкам навигации субпанелей с обновлением URL
  const subTabButtons = document.querySelectorAll('#userEnvSubTabs button');
  subTabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const pId = btn.getAttribute('data-panel-id') || btn.id;
      switchSubTab(pId, true);
    });
  });

  // Отслеживание изменений хэша браузера (Back/Forward и прямые ссылки)
  window.addEventListener('hashchange', () => {
    if (!isUserEnvironmentTabActive()) return;
    const target = getPanelFromHash();
    if (target && target !== getActiveSubTabId()) {
      switchSubTab(target, false);
    }
  });

  // Реакция на глобальную активацию вкладки через tab-core
  document.addEventListener('tab:activated', (e) => {
    const actId = e.detail?.tabId;
    if (actId === TAB_ID || actId === 'tab-user-enviroment' || actId === 'user-environment' || actId === 'user-enviroment') {
      const target = getPanelFromHash() || e.detail?.subPanelId;
      if (target) {
        switchSubTab(target, false);
      } else {
        updateUrlWithPanel(getActiveSubTabId());
      }
    }
  });

  // Привязка событий модулей
  bindSoundEvents();
  bindTaskbarEvents(refreshAll);
  bindWindowsEvents();
  bindFocusEvents();
  bindPersonalizationEvents();
  bindHistoryEvents(refreshAll);
}

/**
 * Настройка периодического опроса активной вкладки и активного блока (Active-Only Polling).
 */
function setupActivePolling() {
  if (typeof window.registerTabPoller === 'function') {
    window.registerTabPoller('tab-user-environment', async () => {
      if (!isUserEnvironmentTabActive()) return;
      const activeBlock = getActiveSubTabId();

      // Опрос данных только активного блока
      if (activeBlock === 'panel-sound') {
        await loadSoundState();
      } else if (activeBlock === 'panel-windows') {
        await loadWindows();
      } else if (activeBlock === 'panel-focus') {
        await loadFocusState();
      } else if (activeBlock === 'panel-taskbar') {
        await loadTaskbarSummary();
      }
    }, 4000, { immediate: false });

    window.registerTabPoller('tab-user-enviroment', async () => {
      if (!isUserEnvironmentTabActive()) return;
      const activeBlock = getActiveSubTabId();
      if (activeBlock === 'panel-sound') {
        await loadSoundState();
      } else if (activeBlock === 'panel-windows') {
        await loadWindows();
      } else if (activeBlock === 'panel-focus') {
        await loadFocusState();
      } else if (activeBlock === 'panel-taskbar') {
        await loadTaskbarSummary();
      }
    }, 4000, { immediate: false });
  }
}

/**
 * Инициализация вкладки User Environment.
 */
export async function init() {
  if (!_isInitialized) {
    bindGlobalEvents();
    setupActivePolling();
    _isInitialized = true;
  }

  // Считываем блок из URL при загрузке
  const panelFromHash = getPanelFromHash();
  if (panelFromHash) {
    switchSubTab(panelFromHash, false);
  } else {
    updateUrlWithPanel('panel-taskbar');
  }

  await refreshAll();
}

/**
 * Хук активации вкладки (вызывается tab-core при переключении).
 */
export function activate() {
  const panelFromHash = getPanelFromHash();
  if (panelFromHash && panelFromHash !== getActiveSubTabId()) {
    switchSubTab(panelFromHash, false);
  }
}

// Регистрация глобальных обработчиков для tab-core и inline событий
window.initUserEnvironmentTab = init;
window.initUserEnviromentTab = init;
window.activateUserEnvironmentTab = activate;
window.activateUserEnviromentTab = activate;
window.switchUserEnvSubTab = switchSubTab;
window.switchUserEnvironmentSubTab = switchSubTab;
window.getUserEnvPanelFromHash = getPanelFromHash;
window.updateUserEnvUrlWithPanel = updateUrlWithPanel;
window.normalizeUserEnvSubTabId = normalizeSubTabId;
window.getActiveUserEnvSubTabId = getActiveSubTabId;

window._ueActions = {
  aiCopilot: (hwnd) => openWindowCopilotModal(hwnd),
  activate: (hwnd) => executeWindowAction(hwnd, 'activate'),
  minimize: (hwnd) => executeWindowAction(hwnd, 'minimize'),
  maximize: (hwnd) => executeWindowAction(hwnd, 'maximize'),
  restore: (hwnd) => executeWindowAction(hwnd, 'restore'),
  close: (hwnd) => executeWindowAction(hwnd, 'close')
};

// Автозапуск при непосредственной загрузке скрипта
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => init());
} else {
  init();
}
