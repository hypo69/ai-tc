/**
 * =============================================================================
 * Process Name: Windows Js - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/js/main.js?v=20261001_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { switchMainTab } from '/windows/api/webgui/js/main.js';
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:25:00
 * =============================================================================
 */

/**
 * js/main.js — оркестратор главной страницы (run.ps1, маршрут /)
 * Архитектура: UI_ARCHITECTURE.md
 */

import { initI18n, switchLang, applyTranslations } from './i18n.js';
import { initTheme } from './theme.js';
import { initUserSettings } from './userSettings.js';
import { initActivityTracker } from './activityTracker.js';
import { initCacheUI } from './cache-ui.js';
import { initModelTester, sendModelPing } from './model-tester.js';
import { switchTab, loadTab, setupTabClicks } from './tab-core.js?v=20261031_v4';
import './api-cache.js'; // Подключаем универсальный API-кеш слой
import './test-api-cache.js'; // Подключаем тестовый скрипт

// Глобальный экспорт для вызова из вкладок
window.switchTab = switchTab;
window.switchToTab = switchTab;
window.sendModelPing = sendModelPing;
window.initModelTester = initModelTester;
window.applyTranslations = applyTranslations;

// Карта вкладок: имя → [htmlUrl, jsUrl]
// Пути явные — не генерируются из имени
const TABS = {
  // Базовые ИИ и коммуникации
  'chat':                     ['/html/tab_chat/index.html',                         '/html/tab_chat/main.js'],
  'voice':                    ['/html/tab_voice/index.html',                    '/html/tab_voice/main.js'],
  'scenarios':                ['/html/tab_scenarios/index.html',                '/html/tab_scenarios/main.js'],
  'rag':                      ['/html/tab_rag/index.html',                      '/html/tab_rag/main.js'],
  'telegram-rag':             ['/html/tab_telegram_rag/index.html',             '/html/tab_telegram_rag/main.js'],
  'news':                     ['/html/tab_news/index.html',                     '/html/tab_news/main.js'],
  'plugins':                  ['/html/tab_plugins/index.html',                  '/html/tab_plugins/main.js'],
  'admin':                    ['/html/tab_admin/index.html',                    '/html/tab_admin/main.js'],
  'help':                     ['/html/help/index.html',                         '/html/help/main.js'],

  // Консолидированные панели
  'ai-ecosystem':             ['/html/tab_ai_ecosystem/index.html',             '/html/tab_ai_ecosystem/main.js'],
  'storage-management':       ['/html/tab_storage_management/index.html',       '/html/tab_storage_management/main.js'],
  'app-internals':            ['/html/tab_app_internals/index.html',            '/html/tab_app_internals/main.js'],
  'telemetry-control':        ['/html/tab_telemetry_control/index.html',        '/html/tab_telemetry_control/main.js'],

  // Оборудование, Датчики и Телеметрия
  'about-system':             ['/html/tab_about_system/index.html',             '/html/tab_about_system/main.js'],
  'telemetry-research':       ['/html/tab_telemetry_research/index.html',       '/html/tab_telemetry_research/main.js'],
  'process-leaks':            ['/html/tab_process_leaks/index.html',            '/html/tab_process_leaks/main.js'],
  'forensics':                ['/html/tab_forensics/index.html',                '/html/tab_forensics/main.js'],
  'throttling':               ['/html/tab_throttling/index.html',               '/html/tab_throttling/main.js'],
  'peripherals':              ['/html/tab_peripherals/index.html',              '/html/tab_peripherals/main.js'],
  'software-transparency':    ['/html/tab_software_transparency/index.html',    '/html/tab_software_transparency/main.js'],
  'software-scanner':         ['/html/tab_software_scanner/index.html',         '/html/tab_software_scanner/main.js'],

  // Накопители и Диски
  'disk-speed':               ['/html/tab_disk_speed/index.html',               '/html/tab_disk_speed/main.js'],
  'file-recovery':            ['/html/tab_file_recovery/index.html',            '/html/tab_file_recovery/main.js'],
  'file-history-search':      ['/html/tab_file_history_ai_search/index.html',   '/html/tab_file_history_ai_search/main.js'],

  // Управление Windows и Sysadmin
  'system-control':           ['/html/tab_system_control/index.html',           '/html/tab_system_control/main.js'],
  'post-install-wizard':      ['/html/tab_post_install_wizard/index.html',      '/html/tab_post_install_wizard/main.js'],
  'windows-admin':            ['/html/tab_windows_admin/index.html',            '/html/tab_windows_admin/main.js'],
  'focus-settings':           ['/html/tab_focus_settings/index.html',           '/html/tab_focus_settings/main.js'],
  'sound-settings':           ['/html/tab_sound_settings/index.html',           '/html/tab_sound_settings/main.js'],
  'taskbar-controller':       ['/html/tab_taskbar/index.html',                  '/html/tab_taskbar/main.js'],
  'startup-auditor':          ['/html/tab_startup_auditor/index.html',          '/html/tab_startup_auditor/main.js'],
  'services-manager':         ['/html/tab_services_manager/index.html',         '/html/tab_services_manager/main.js'],
  'task-scheduler':           ['/html/tab_task_scheduler/index.html',           '/html/tab_task_scheduler/main.js'],
  'process-manager':          ['/html/tab_process_manager/index.html',          '/html/tab_process_manager/main.js'],
  'registry-editor':          ['/html/tab_registry_editor/index.html',          '/html/tab_registry_editor/main.js'],
  'registry-viewer':          ['/html/tab_registry_editor/index.html',          '/html/tab_registry_editor/main.js'],
  'software-manager':         ['/html/tab_software_manager/index.html',         '/html/tab_software_manager/main.js'],

  // Безопасность и Целостность
  'defender':                 ['/html/tab_defender_firewall/index.html',        '/html/tab_defender_firewall/main.js'],
  'defender-firewall':        ['/html/tab_defender_firewall/index.html',        '/html/tab_defender_firewall/main.js'],
  'security-acl':             ['/html/tab_security_acl/index.html',             '/html/tab_security_acl/main.js'],
  'servicing-integrity':      ['/html/tab_servicing_integrity/index.html',      '/html/tab_servicing_integrity/main.js'],
  'boot-recovery':            ['/html/tab_boot_recovery/index.html',            '/html/tab_boot_recovery/main.js'],
  'smart-restore':            ['/html/tab_smart_restore/index.html',            '/html/tab_smart_restore/main.js'],

  // Сеть и Системные Логи
  'network':                  ['/html/tab_network/index.html',                  '/html/tab_network/main.js'],
  'power-lifecycle':          ['/html/tab_power_lifecycle/index.html',          '/html/tab_power_lifecycle/main.js'],

  // Кастомизация и Темы оформления
  'theme-editor':             ['/html/tab_theme_editor/index.html',             '/html/tab_theme_editor/main.js'],
  'sitemap':                  ['/html/tab_sitemap/index.html',                  '/html/tab_sitemap/main.js'],
};

// Lazy-загрузка: вкладка грузится при первом открытии
const loaded = new Set();

async function lazyLoad(tabName) {
  if (loaded.has(tabName) || !TABS[tabName]) return;
  loaded.add(tabName);
  const v = Date.now();
  const [html, js] = TABS[tabName];
  await loadTab(tabName, `${html}?v=${v}`, `${js}?v=${v}`);
  applyTranslations();
}

// Переопределяем switchTab с приоритетной мгновенной навигацией
const _switchTab = switchTab;
export function switchMainTab(tabId) {
  if (!tabId) return;

  const rawClean = String(tabId).replace(/^#/, '');
  const parts = rawClean.split('#');
  const baseTab = parts[0];
  let subPanel = parts[1] || null;
  const blockId = parts.find(p => p.startsWith('block-')) || null;
  const extraParts = parts.slice(2).filter(Boolean);
  tabId = baseTab;

  // Редирект Брандмауэр -> Defender (суб-панель Firewall)
  if (tabId === 'tab-firewall-manager' || tabId === 'firewall-manager') {
    tabId = 'tab-defender-firewall';
    setTimeout(() => {
      if (typeof window.switchDefenderSubTab === 'function') {
        window.switchDefenderSubTab('firewall');
      } else {
        const btn = document.getElementById('subtab-firewall-btn');
        if (btn && window.bootstrap) {
          new bootstrap.Tab(btn).show();
        }
      }
    }, 70);
  }

  // Редирект Defender -> Defender & Firewall
  if (tabId === 'tab-defender' || tabId === 'defender') {
    tabId = 'tab-defender-firewall';
  }

  // Редирект Windows Backup -> Windows Sysadmin (виджет Backup)
  if (tabId === 'tab-windows-backup' || tabId === 'windows-backup') {
    tabId = 'tab-windows-admin';
    setTimeout(() => {
      const widget = document.getElementById('windows-backup-widget');
      if (widget) {
        widget.scrollIntoView({ behavior: 'smooth', block: 'center' });
        widget.classList.add('border-info');
        setTimeout(() => widget.classList.remove('border-info'), 2500);
      }
    }, 120);
  }

  // Редирект Учетные записи (accounts-identity) -> Windows Sysadmin
  if (tabId === 'tab-accounts-identity' || tabId === 'accounts-identity') {
    tabId = 'tab-windows-admin';
  }

  // Редирект Права доступа и ACL (security-acl) -> Windows Sysadmin
  if (tabId === 'tab-security-acl' || tabId === 'security-acl') {
    tabId = 'tab-windows-admin';
    setTimeout(() => {
      if (typeof window.switchWindowsAdminSubTab === 'function') {
        window.switchWindowsAdminSubTab('acl');
      } else {
        const btn = document.getElementById('subtab-winadmin-acl-btn');
        if (btn && window.bootstrap) {
          new bootstrap.Tab(btn).show();
        }
      }
    }, 70);
  }

  // Редирект Накопители и Диски -> Storage Management (суб-панели)
  if (tabId === 'tab-storage-wear' || tabId === 'storage-wear') {
    tabId = 'tab-storage-management';
    setTimeout(() => {
      if (typeof window.switchStorageSubTab === 'function') {
        window.switchStorageSubTab('wear');
      }
    }, 70);
  } else if (tabId === 'tab-storage-manager' || tabId === 'storage-manager') {
    tabId = 'tab-storage-management';
    setTimeout(() => {
      if (typeof window.switchStorageSubTab === 'function') {
        window.switchStorageSubTab('volumes');
      }
    }, 70);
  }

  // Редирект ИИ-компоненты -> AI Ecosystem (суб-панели)
  if (tabId === 'tab-agents' || tabId === 'agents') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('agents');
      }
    }, 70);
  } else if (tabId === 'tab-skills' || tabId === 'skills') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('skills');
      }
    }, 70);
  } else if (tabId === 'tab-mcp' || tabId === 'mcp') {
    tabId = 'tab-ai-ecosystem';
    setTimeout(() => {
      if (typeof window.switchAiEcosystemSubTab === 'function') {
        window.switchAiEcosystemSubTab('mcp');
      }
    }, 70);
  }

  // Редирект Служебные утилиты -> App Internals (суб-панели)
  if (tabId === 'tab-models' || tabId === 'models') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('models');
      }
    }, 70);
  } else if (tabId === 'tab-telemetry-config' || tabId === 'telemetry-config' || tabId === 'tab-telemetry-control' || tabId === 'telemetry-control') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('telemetry');
      }
    }, 70);
  } else if (tabId === 'tab-system-logs' || tabId === 'system-logs' || tabId === 'tab-app-logs' || tabId === 'app-logs') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('logs');
      }
    }, 70);
  } else if (tabId === 'tab-performance-tracing' || tabId === 'performance-tracing') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('etw');
      }
    }, 70);
  } else if (tabId === 'tab-log-settings' || tabId === 'log-settings') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('settings');
      }
    }, 70);
  } else if (tabId === 'tab-wikillm' || tabId === 'wikillm' || tabId === 'tab-wikillm-settings' || tabId === 'wikillm-settings') {
    tabId = 'tab-app-internals';
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab('wikillm');
      }
    }, 70);
  } else if (tabId === 'tab-process-leaks' || tabId === 'process-leaks') {
    tabId = 'tab-processes-load-inspector';
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab('leaks');
      }
    }, 70);
  } else if (tabId === 'tab-process-manager' || tabId === 'process-manager') {
    tabId = 'tab-processes-load-inspector';
    subPanel = subPanel || 'manager';
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab('manager');
      }
    }, 70);
  } else if (tabId === 'tab-forensics' || tabId === 'forensics') {
    tabId = 'tab-system-control';
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource('forensics');
      } else {
        const btn = document.getElementById('btn-source-forensics');
        if (btn) btn.click();
      }
    }, 70);
  } else if (tabId === 'tab-forensics-timeline' || tabId === 'forensics-timeline') {
    tabId = 'tab-system-control';
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource('forensics', 'timeline');
      } else {
        const btn = document.getElementById('btn-source-forensics');
        if (btn) btn.click();
      }
    }, 70);
  } else if (tabId === 'tab-forensics-userassist' || tabId === 'forensics-userassist') {
    tabId = 'tab-system-control';
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource('forensics', 'userassist');
      } else {
        const btn = document.getElementById('btn-source-forensics');
        if (btn) btn.click();
      }
    }, 70);
  } else if (tabId === 'tab-throttling' || tabId === 'throttling') {
    tabId = 'tab-system-control';
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource('throttling');
      } else {
        const btn = document.getElementById('btn-source-throttling');
        if (btn) btn.click();
      }
    }, 70);
  } else if (tabId === 'tab-startup-auditor' || tabId === 'startup-auditor') {
    tabId = 'tab-software-scanner';
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab('startup');
      }
    }, 70);
  }

  // 1. Мгновенное переключение UI без задержки
  const fullSubHash = [subPanel, ...extraParts].filter(Boolean).join('#');
  _switchTab(fullSubHash ? `${tabId}#${fullSubHash}` : tabId);

  // 2. Фоновая асинхронная подгрузка разметки и скрипта вкладки (если еще не загружена)
  const name = (tabId.startsWith('tab-') ? tabId.slice(4) : tabId);
  if (!loaded.has(name) && TABS[name]) {
    lazyLoad(name).catch(err => console.warn(`[Main] Ошибка lazyLoad для ${name}:`, err));
  }

  if (subPanel && (tabId === 'tab-processes-load-inspector' || tabId === 'processes-load-inspector')) {
    setTimeout(() => {
      if (typeof window.switchProcessesSubTab === 'function') {
        window.switchProcessesSubTab(subPanel, false);
      }
    }, 70);
  } else if (subPanel && (tabId === 'tab-system-control' || tabId === 'system-control')) {
    setTimeout(() => {
      if (typeof window.switchSystemControlSource === 'function') {
        window.switchSystemControlSource(subPanel);
      }
    }, 70);
  } else if (subPanel && (tabId === 'tab-software-scanner' || tabId === 'software-scanner' || tabId === 'tab-software-monitor' || tabId === 'software-monitor')) {
    setTimeout(() => {
      if (typeof window.switchSoftwareSubTab === 'function') {
        window.switchSoftwareSubTab(subPanel, blockId, false);
      }
    }, 70);
  } else if (subPanel && (tabId === 'tab-app-internals' || tabId === 'app-internals')) {
    setTimeout(() => {
      if (typeof window.switchAppInternalsSubTab === 'function') {
        window.switchAppInternalsSubTab(subPanel, blockId, false);
      }
    }, 70);
  } else if (subPanel && (tabId === 'tab-user-environment' || tabId === 'user-environment' || tabId === 'tab-user-enviroment' || tabId === 'user-enviroment')) {
    setTimeout(() => {
      if (typeof window.switchUserEnvSubTab === 'function') {
        window.switchUserEnvSubTab(subPanel, false);
      }
    }, 70);
  }
}
window.switchTab = switchMainTab;
window.switchToTab = switchMainTab;

// Открыть плагин по имени (вызывается из плагинов)
window.openPluginFromDropdown = function(pluginName) {
  if (!pluginName) return;
  const n = pluginName.toLowerCase().replace(/-/g, '_');
  if (n === 'telegram_channel_rag' || n === 'telegram_rag') {
    window.switchTab('tab-telegram-rag'); return;
  }
  if (n === 'news_feed' || n === 'news' || n === 'smart_news') {
    window.switchTab('tab-news'); return;
  }
  window.switchTab('tab-plugins');
  const sel = () => window.selectPlugin?.(pluginName);
  sel(); setTimeout(sel, 200);
};

async function init() {
  // 1. Тема
  initTheme();

  // 2. i18n (с автоматическим парсингом URL параметров: ?region=ru-ru, ?locale=ru-RU и т.д.)
  await initI18n();

  // 3. Пользователь, активность, кеш, быстрая проверка модели
  await initUserSettings();
  initActivityTracker();
  initCacheUI();
  initModelTester();

  // 4. Единый обработчик кликов
  setupTabClicks();

  // 5. Загрузить первую вкладку (чат)
  await lazyLoad('chat');
  applyTranslations();

  // 6. Синхронизация видимости плагинов
  try {
    const r = await fetch('/api/admin/plugins');
    if (r.ok) {
      const data = await r.json();
      window.syncPluginTabsVisibility?.(data.plugins);
    }
  } catch {}

  // 7. Активировать вкладку по hash или чат
  const hash = location.hash.replace(/^#/, '');
  await switchMainTab(hash || 'tab-chat');

  window.addEventListener('hashchange', async () => {
    const h = location.hash.replace(/^#/, '');
    if (h) {
      await switchMainTab(h);
    }
  });

  // 8. Фоновый WebSocket
  initComputerStream();
}

// Фоновый WebSocket для remote transcript
function initComputerStream() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/api/control/ws?role=computer`);
  ws.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.event === 'transcript') window.handleRemoteTranscript?.(msg.text);
    } catch {}
  };
  ws.onclose = () => setTimeout(initComputerStream, 3000);
}



document.readyState === 'loading'
  ? document.addEventListener('DOMContentLoaded', init)
  : init();

