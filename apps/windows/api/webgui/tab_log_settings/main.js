/**
 * =============================================================================
 * Process Name: Windows Log Settings - Main Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор вкладки настройки параметров журналов событий
 *   Windows по 7 доменам телеметрии, аудита CommandLine, графа процессов и инспектора.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_log_settings/main.js?v=20261017_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initLogSettingsTab } from '/windows/api/webgui/tab_log_settings/main.js';
 *
 * File: main.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { fetchDomainsSummary, fetchEventCatalog } from './panel_domains/panel.js';
import {
  fetchChannelsList,
  renderChannelsTable,
  saveChannelConfig,
  confirmClearChannel
} from './panel_channels/panel.js';
import {
  fetchAuditStatus,
  toggleCmdlineAudit,
  runCollector,
  resetBookmark
} from './panel_security/panel.js';
import { buildProcessProvenance } from './panel_provenance/panel.js';
import { fetchPowerLifecycle } from './panel_lifecycle/panel.js';
import { fetchInspectorEvents } from './panel_inspector/panel.js';

const registerTabPoller = (typeof window !== 'undefined' && window.registerTabPoller) || function () {};

let isInitialized = false;

/**
 * Инициализирует вкладку параметров и каталога журналов Windows.
 */
export function initLogSettingsTab() {
  if (isInitialized) return;
  isInitialized = true;

  // Кнопка обновления всех параметров
  document.getElementById('ls-refresh-all-btn')?.addEventListener('click', () => {
    fetchDomainsSummary();
    fetchEventCatalog();
    fetchChannelsList();
    fetchAuditStatus();
  });

  document.getElementById('ls-reload-channels-btn')?.addEventListener('click', () => fetchChannelsList());

  // Поиск по списку каналов
  document.getElementById('ls-channel-filter-input')?.addEventListener('input', () => {
    fetchChannelsList();
  });

  // Фильтры каталога провайдеров
  document.getElementById('ls-catalog-domain-select')?.addEventListener('change', fetchEventCatalog);
  document.getElementById('ls-catalog-search-input')?.addEventListener('input', fetchEventCatalog);

  // Provenance граф
  document.getElementById('ls-prov-build-btn')?.addEventListener('click', buildProcessProvenance);

  // Хронология жизненного цикла
  document.getElementById('ls-lifecycle-hours-select')?.addEventListener('change', fetchPowerLifecycle);
  document.getElementById('ls-lifecycle-reload-btn')?.addEventListener('click', fetchPowerLifecycle);

  // Пресеты размеров в модальном окне
  document.querySelectorAll('.ls-preset-size-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mb = btn.dataset.mb;
      const input = document.getElementById('ls-modal-maxsize-input');
      if (input) input.value = mb;
    });
  });

  // Сохранение конфигурации канала
  document.getElementById('ls-modal-save-btn')?.addEventListener('click', saveChannelConfig);

  // Очистка канала
  document.getElementById('ls-confirm-clear-btn')?.addEventListener('click', confirmClearChannel);
  document.getElementById('ls-clear-backup-checkbox')?.addEventListener('change', (e) => {
    const pathGroup = document.getElementById('ls-clear-backup-path-group');
    if (pathGroup) pathGroup.style.display = e.target.checked ? 'flex' : 'none';
  });

  // Управление аудитом CommandLine
  document.getElementById('ls-toggle-cmdline-btn')?.addEventListener('click', async () => {
    const isCurrentlyEnabled = document.getElementById('ls-cmdline-status')?.textContent.includes('Включен');
    await toggleCmdlineAudit(!isCurrentlyEnabled);
  });
  document.getElementById('ls-enable-cmdline-btn')?.addEventListener('click', () => toggleCmdlineAudit(true));
  document.getElementById('ls-disable-cmdline-btn')?.addEventListener('click', () => toggleCmdlineAudit(false));

  // Управление сборщиком
  document.getElementById('ls-collect-btn')?.addEventListener('click', () => runCollector(fetchDomainsSummary));
  document.getElementById('ls-run-collector-btn')?.addEventListener('click', () => runCollector(fetchDomainsSummary));

  // Сброс закладки
  document.getElementById('ls-reset-bm-btn')?.addEventListener('click', () => resetBookmark(null));
  document.getElementById('ls-set-custom-bm-btn')?.addEventListener('click', () => {
    const val = document.getElementById('ls-custom-record-id-input')?.value;
    const num = val ? parseInt(val, 10) : null;
    resetBookmark(num);
  });

  // Быстрые фильтры Event ID
  document.querySelectorAll('.ls-quick-eid-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.ls-quick-eid-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      fetchInspectorEvents();
    });
  });

  // Инспектор событий
  document.getElementById('ls-insp-fetch-btn')?.addEventListener('click', fetchInspectorEvents);
  document.getElementById('ls-insp-channel-select')?.addEventListener('change', fetchInspectorEvents);
  document.getElementById('ls-insp-level-select')?.addEventListener('change', fetchInspectorEvents);

  // Первоначальная загрузка данных всех подразделов
  fetchDomainsSummary();
  fetchEventCatalog();
  fetchChannelsList();
  fetchAuditStatus();
  fetchPowerLifecycle();

  // Регистрация фонового поллера (каждые 20 секунд при активной вкладке)
  registerTabPoller('tab-log-settings', () => {
    fetchDomainsSummary();
    fetchChannelsList();
    fetchAuditStatus();
  }, 20000);
}

// Экспорт методов в глобальную область window
if (typeof window !== 'undefined') {
  window.initLogSettingsTab = initLogSettingsTab;
  window.fetchDomainsSummary = fetchDomainsSummary;
  window.fetchEventCatalog = fetchEventCatalog;
  window.fetchChannelsList = fetchChannelsList;
  window.fetchAuditStatus = fetchAuditStatus;
  window.fetchPowerLifecycle = fetchPowerLifecycle;
  window.buildProcessProvenance = buildProcessProvenance;
  window.fetchInspectorEvents = fetchInspectorEvents;
}

// Автоматическая инициализация при загрузке документа
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLogSettingsTab);
  } else {
    initLogSettingsTab();
  }
}

export {
  fetchDomainsSummary,
  fetchEventCatalog,
  fetchChannelsList,
  fetchAuditStatus,
  fetchPowerLifecycle,
  buildProcessProvenance,
  fetchInspectorEvents
};
