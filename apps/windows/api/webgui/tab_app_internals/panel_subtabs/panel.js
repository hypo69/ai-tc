/**
 * =============================================================================
 * Process Name: Windows App Internals - Subtabs Navigation Panel
 * =============================================================================
 * Description:
 *   Модуль динамической загрузки, ленивой подгрузки и переключения
 *   встраиваемых суб-панелей вкладки «Внутренняя кухня» и подменю блоков
 *   согласно канону «Меню — всегда меню» (см. conversation 37efa6e9-9633-42ba-9751-7f4bced2022c):
 *   Уровень 1: Меню субвкладок (телеметрия, модели, логи, ETW, параметры, подсказки, инструменты)
 *   Уровень 2: Подменю блоков внутри баз знаний:
 *     - Подсказки по системе: Хранилище SQLite, Параметры WikiLLM, Статьи
 *     - База инструментов: Сервер Hostinger, Цепочка размышлений, Каталог
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_subtabs
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-11 23:20:00
 * =============================================================================
 */

import {
  loadScript,
  normalizeSubTabId,
  normalizeBlockId,
  getBlockFromHash,
  getActiveBlockId,
  updateUrlWithPanel,
  getActiveSubTabId,
} from '../common/ui_utils.js?v=20261111_v1';

/**
 * Загрузка разметки и скрипта конкретной суб-панели с вызовом хуков инициализации.
 * @param {string} containerId - ID DOM-контейнера суб-панели
 * @param {string} htmlUrl - URL разметки HTML
 * @param {string} jsUrl - URL управляющего JS скрипта
 * @param {string} [initFnName] - Глобальное имя функции инициализации
 * @param {string} [activateFnName] - Глобальное имя функции активации/обновления
 * @returns {Promise<void>}
 */
export async function loadSubPane(containerId, htmlUrl, jsUrl, initFnName, activateFnName) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!container.children.length || !container.innerHTML.trim()) {
    try {
      const res = await fetch(`${htmlUrl}?v=${Date.now()}`);
      if (!res.ok) {
        container.innerHTML = `
          <div class="alert alert-warning m-3">
            <i class="bi bi-exclamation-triangle me-2"></i>Не удалось загрузить компонент (${res.status}).
          </div>`;
        return;
      }
      container.innerHTML = await res.text();
    } catch (err) {
      console.warn(`[AppInternals] Ошибка загрузки HTML для ${containerId}:`, err);
      container.innerHTML = `
        <div class="alert alert-danger m-3">
          <i class="bi bi-x-circle me-2"></i>Ошибка загрузки разметки: ${err.message}
        </div>`;
      return;
    }
  }

  if (jsUrl) {
    try {
      await loadScript(`${jsUrl}?v=${Date.now()}`);
      if (initFnName && typeof window[initFnName] === 'function') {
        try {
          const maybePromise = window[initFnName]();
          if (maybePromise && typeof maybePromise.catch === 'function') {
            await maybePromise;
          }
        } catch (err) {
          console.debug(`[AppInternals] ${initFnName} error:`, err);
        }
      }
      if (activateFnName && typeof window[activateFnName] === 'function') {
        try {
          const maybePromise = window[activateFnName]();
          if (maybePromise && typeof maybePromise.catch === 'function') {
            await maybePromise;
          }
        } catch (err) {
          console.debug(`[AppInternals] ${activateFnName} error:`, err);
        }
      }
    } catch (err) {
      console.warn(`[AppInternals] Ошибка инициализации скрипта для ${containerId}:`, err);
    }
  }
}

/**
 * Конвейерная загрузка внешних суб-панелей:
 * Первая (активная) загружается немедленно, остальные подгружаются параллельно.
 * @returns {Promise<void>}
 */
export async function loadSubPanes() {
  await loadSubPane(
    'internals-telemetry-embed-container',
    '/html/tab_telemetry_control/index.html',
    '/html/tab_telemetry_control/main.js',
    'initTelemetryControlTab'
  );

  await Promise.allSettled([
    loadSubPane(
      'internals-models-embed-container',
      '/html/tab_models/index.html',
      '/html/tab_models/main.js',
      'initModelsTab'
    ),
    loadSubPane(
      'internals-logs-embed-container',
      '/html/tab_app_logs/index.html',
      '/html/tab_app_logs/main.js',
      'initAppLogsTab',
      'activateAppLogsTab'
    ),
    loadSubPane(
      'internals-etw-embed-container',
      '/html/tab_performance_tracing/index.html',
      '/html/tab_performance_tracing/main.js',
      'initPerformanceTracingTab',
      'fetchPerformanceSummary'
    ),
    loadSubPane(
      'internals-settings-embed-container',
      '/html/tab_log_settings/index.html',
      '/html/tab_log_settings/main.js',
      'initLogSettingsTab',
      'fetchDomainsSummary'
    ),
  ]);
}

/**
 * Вызов обновления данных и хуков для конкретной суб-панели и блока.
 * @param {string} subtabName - Имя субпанели
 * @param {string|null} [blockId=null] - Идентификатор блока
 * @returns {Promise<void>}
 */
export async function triggerSubTabInit(subtabName, blockId = null) {
  const canonical = normalizeSubTabId(subtabName);
  if (canonical === 'telemetry') {
    await loadSubPane(
      'internals-telemetry-embed-container',
      '/html/tab_telemetry_control/index.html',
      '/html/tab_telemetry_control/main.js',
      'initTelemetryControlTab'
    );
    if (typeof window.initTelemetryControlTab === 'function') window.initTelemetryControlTab();
  } else if (canonical === 'models') {
    await loadSubPane(
      'internals-models-embed-container',
      '/html/tab_models/index.html',
      '/html/tab_models/main.js',
      'initModelsTab'
    );
    if (typeof window.initModelsTab === 'function') window.initModelsTab();
  } else if (canonical === 'logs') {
    await loadSubPane(
      'internals-logs-embed-container',
      '/html/tab_app_logs/index.html',
      '/html/tab_app_logs/main.js',
      'initAppLogsTab',
      'activateAppLogsTab'
    );
    if (typeof window.initAppLogsTab === 'function') window.initAppLogsTab();
    if (typeof window.activateAppLogsTab === 'function') window.activateAppLogsTab();
    window.APP_LOG_URL = '/api/v1/internals/logs/app.log';
  } else if (canonical === 'activity') {
    if (typeof window.initAppInternalsActivityPanel === 'function') {
      await window.initAppInternalsActivityPanel();
    } else {
      const mod = await import('../panel_activity/panel.js?v=20261111_v1');
      if (mod && typeof mod.initAppInternalsActivityPanel === 'function') {
        await mod.initAppInternalsActivityPanel();
      }
    }
  } else if (canonical === 'etw') {
    await loadSubPane(
      'internals-etw-embed-container',
      '/html/tab_performance_tracing/index.html',
      '/html/tab_performance_tracing/main.js',
      'initPerformanceTracingTab',
      'fetchPerformanceSummary'
    );
    if (typeof window.initPerformanceTracingTab === 'function') window.initPerformanceTracingTab();
    if (typeof window.fetchPerformanceSummary === 'function') window.fetchPerformanceSummary();
  } else if (canonical === 'settings') {
    await loadSubPane(
      'internals-settings-embed-container',
      '/html/tab_log_settings/index.html',
      '/html/tab_log_settings/main.js',
      'initLogSettingsTab',
      'fetchDomainsSummary'
    );
    if (typeof window.initLogSettingsTab === 'function') window.initLogSettingsTab();
    if (typeof window.fetchDomainsSummary === 'function') window.fetchDomainsSummary();
  } else if (canonical === 'wikillm-system') {
    const targetBlock = blockId || getBlockFromHash('wikillm-system') || 'block-sys-storage';
    switchAppInternalsBlock('wikillm-system', targetBlock, false);
  } else if (canonical === 'tooltips-editor') {
    if (typeof window.initTooltipsEditorPanel === 'function') {
      await window.initTooltipsEditorPanel();
    } else {
      const mod = await import('../panel_tooltips_editor/panel.js?v=20261031_v3');
      if (mod && typeof mod.initTooltipsEditorPanel === 'function') {
        await mod.initTooltipsEditorPanel();
      }
    }
  } else if (canonical === 'helppages-editor') {
    await loadSubPane(
      'internals-helppages-editor-embed-container',
      '/html/tab_app_internals/panel_helppages_editor/panel.html',
      '/html/tab_app_internals/panel_helppages_editor/panel.js',
      'initHelpPagesEditor'
    );
    if (typeof window.initHelpPagesEditor === 'function') window.initHelpPagesEditor();
  } else if (canonical === 'instruments') {
    const targetBlock = blockId || getBlockFromHash('instruments') || 'block-inst-hostinger';
    switchAppInternalsBlock('instruments', targetBlock, false);
  } else if (canonical === 'codebase-rag') {
    const targetBlock = blockId || getBlockFromHash('codebase-rag') || 'block-code-diagnose';
    switchAppInternalsBlock('codebase-rag', targetBlock, false);
  }
}

/**
 * Переключение активного блока подменю внутри составной панели.
 * @param {'wikillm-system' | 'instruments'} panelId
 * @param {string} rawBlockId
 * @param {boolean} [updateUrl=true]
 */
export function switchAppInternalsBlock(panelId, rawBlockId, updateUrl = true) {
  const canonicalBlock = normalizeBlockId(rawBlockId, panelId);
  let navId = 'wikillm-sys-blocks-nav';
  if (panelId === 'instruments') navId = 'instruments-blocks-nav';
  else if (panelId === 'codebase-rag') navId = 'codebase-blocks-nav';
  const nav = document.getElementById(navId);

  if (nav) {
    const btns = nav.querySelectorAll('button[data-block-id]');
    btns.forEach((btn) => {
      const bId = normalizeBlockId(btn.getAttribute('data-block-id'), panelId);
      if (bId === canonicalBlock) {
        btn.classList.add('active');
        const targetPaneSelector = btn.getAttribute('data-bs-target');
        if (targetPaneSelector) {
          const targetPane = document.querySelector(targetPaneSelector);
          if (targetPane) {
            targetPane.parentElement?.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('show', 'active'));
            targetPane.classList.add('show', 'active');
          }
        }
      } else {
        btn.classList.remove('active');
      }
    });
  }

  // Ленивый вызов инициализации данных только активного блока
  if (panelId === 'wikillm-system') {
    if (canonicalBlock === 'block-sys-storage') {
      if (typeof window.bindWikiLLMDbButtons === 'function') window.bindWikiLLMDbButtons();
      if (typeof window.loadWikiLLMDbConfig === 'function') window.loadWikiLLMDbConfig();
    } else if (canonicalBlock === 'block-sys-params') {
      if (typeof window.bindWikiLLMButtons === 'function') window.bindWikiLLMButtons();
      if (typeof window.loadWikiLLMSettings === 'function') window.loadWikiLLMSettings();
    } else if (canonicalBlock === 'block-sys-articles') {
      if (typeof window.initWikiLLMEditor === 'function') window.initWikiLLMEditor();
    }
  } else if (panelId === 'instruments') {
    if (canonicalBlock === 'block-inst-hostinger') {
      if (typeof window.bindInstrumentsDbButtons === 'function') window.bindInstrumentsDbButtons();
      if (typeof window.loadInstrumentsDbConfig === 'function') window.loadInstrumentsDbConfig();
    } else if (canonicalBlock === 'block-inst-runtime') {
      if (typeof window.bindInstrumentsRuntimeButtons === 'function') window.bindInstrumentsRuntimeButtons();
      if (typeof window.loadInstrumentsRuntimeConfig === 'function') window.loadInstrumentsRuntimeConfig();
    } else if (canonicalBlock === 'block-inst-catalog') {
      if (typeof window.bindInstrumentsCatalogButtons === 'function') window.bindInstrumentsCatalogButtons();
      if (typeof window.loadInstrumentsCatalog === 'function') window.loadInstrumentsCatalog();
    }
  } else if (panelId === 'codebase-rag') {
    if (typeof window.bindCodebaseRagButtons === 'function') window.bindCodebaseRagButtons();
    if (typeof window.loadCodebaseIndexes === 'function') window.loadCodebaseIndexes();
  }

  if (updateUrl) {
    updateUrlWithPanel(panelId, canonicalBlock);
  }
}

/**
 * Программное переключение на нужную суб-панель с обновлением URL hash (#tab-app-internals#<panel_id>[#block-<block_id>]).
 * @param {string} subtabName - Имя субпанели
 * @param {string|null} [blockId=null] - Блок подменю
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash
 */
export function switchAppInternalsSubTab(subtabName, blockId = null, updateUrl = true) {
  const canonical = normalizeSubTabId(subtabName);
  let btnId = 'subtab-internals-telemetry-btn';
  if (canonical === 'models') btnId = 'subtab-internals-models-btn';
  else if (canonical === 'logs') btnId = 'subtab-internals-logs-btn';
  else if (canonical === 'activity') btnId = 'subtab-internals-activity-btn';
  else if (canonical === 'etw') btnId = 'subtab-internals-etw-btn';
  else if (canonical === 'settings') btnId = 'subtab-internals-settings-btn';
  else if (canonical === 'wikillm-system') btnId = 'subtab-internals-wikillm-system-btn';
  else if (canonical === 'codebase-rag') btnId = 'subtab-internals-codebase-rag-btn';
  else if (canonical === 'instruments') btnId = 'subtab-internals-instruments-btn';
  else if (canonical === 'tooltips-editor') btnId = 'subtab-internals-tooltips-editor-btn';
  else if (canonical === 'helppages-editor') btnId = 'subtab-internals-helppages-editor-btn';

  const btn = document.getElementById(btnId);
  if (btn) {
    const nav = document.getElementById('app-internals-subtabs-nav');
    if (nav) {
      nav.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
    }
    btn.classList.add('active');

    const targetPaneId = `subpane-internals-${canonical}`;
    const targetPane = document.getElementById(targetPaneId);
    if (targetPane) {
      targetPane.parentElement?.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('show', 'active'));
      targetPane.classList.add('show', 'active');
    }

    if (window.bootstrap && window.bootstrap.Tab) {
      try {
        window.bootstrap.Tooltip?.getInstance?.(btn)?.dispose();
      } catch (_) {}
      try {
        const tabInst = window.bootstrap.Tab.getOrCreateInstance
          ? window.bootstrap.Tab.getOrCreateInstance(btn)
          : (window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn));
        tabInst?.show?.();
      } catch (err) {
        console.debug('[AppInternals] Bootstrap tab switch ignored:', err);
      }
    }
  }

  triggerSubTabInit(canonical, blockId);

  if (updateUrl) {
    const effectiveBlock = blockId || getActiveBlockId(canonical);
    updateUrlWithPanel(canonical, effectiveBlock);
  }
}

/**
 * Подключение слушателей навигации по кнопкам суб-вкладок (Уровень 1) и блоков (Уровень 2).
 */
export function setupSubTabNavigation() {
  // Навигация Уровня 1: Меню панелей
  const navContainer = document.getElementById('app-internals-subtabs-nav');
  if (navContainer && !navContainer.dataset.subnavBound) {
    navContainer.dataset.subnavBound = 'true';
    navContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-bs-toggle="pill"]');
      if (!btn) return;
      const pId = btn.getAttribute('data-panel-id');
      const target = btn.getAttribute('data-bs-target') || '';
      const canonical = normalizeSubTabId(pId || target);
      switchAppInternalsSubTab(canonical, null, true);
    });
  }

  // Навигация Уровня 2: Блоки подсказок по системе
  const sysBlocksNav = document.getElementById('wikillm-sys-blocks-nav');
  if (sysBlocksNav && !sysBlocksNav.dataset.blocknavBound) {
    sysBlocksNav.dataset.blocknavBound = 'true';
    sysBlocksNav.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-block-id]');
      if (!btn) return;
      const bId = btn.getAttribute('data-block-id');
      switchAppInternalsBlock('wikillm-system', bId, true);
    });
  }

  // Навигация Уровня 2: Блоки базы инструментов
  const instBlocksNav = document.getElementById('instruments-blocks-nav');
  if (instBlocksNav && !instBlocksNav.dataset.blocknavBound) {
    instBlocksNav.dataset.blocknavBound = 'true';
    instBlocksNav.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-block-id]');
      if (!btn) return;
      const bId = btn.getAttribute('data-block-id');
      switchAppInternalsBlock('instruments', bId, true);
    });
  }

  // Навигация Уровня 2: Блоки Codebase RAG
  const codeBlocksNav = document.getElementById('codebase-blocks-nav');
  if (codeBlocksNav && !codeBlocksNav.dataset.blocknavBound) {
    codeBlocksNav.dataset.blocknavBound = 'true';
    codeBlocksNav.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-block-id]');
      if (!btn) return;
      const bId = btn.getAttribute('data-block-id');
      switchAppInternalsBlock('codebase-rag', bId, true);
    });
  }
}

/**
 * Инициализация модуля навигации по суб-вкладкам.
 * @returns {Promise<void>}
 */
export async function initSubtabsPanel() {
  setupSubTabNavigation();
  window.switchAppInternalsSubTab = switchAppInternalsSubTab;
  window.switchAppInternalsBlock = switchAppInternalsBlock;
}
