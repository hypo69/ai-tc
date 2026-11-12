/**
 * =============================================================================
 * Process Name: Windows Admin - Lazy-Init-Patch Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля lazy-init-patch.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/admin/lazy-init-patch.js?v=20261001_v1" type="module"></script>
 *
 * File: lazy-init-patch.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/admin
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 14:41:44
 * =============================================================================
 */

/**
 * Lazy Init Patch - Патч для переключения на ленивую загрузку вкладок
 * 
 * Этот скрипт перехватывает инициализацию main.js и использует
 * LazyTabLoader вместо стандартной загрузки всех вкладок сразу
 */

import { 
  initLazyTabLoading, 
  enhanceTabSwitching, 
  restoreLastTab 
} from './optimization-init.js';
import { autoPatchTab } from '../js/tab-debounce-auto-patch.js';
import TabStatePersistence from '../js/tab-state-persistence.js';
import TabSwitchOptimizer from '../js/tab-switch-optimizer.js';

console.log('[LazyInitPatch] Patching admin interface initialization...');

// Глобальный хелпер активности вкладок
if (typeof window.isTabActive !== 'function') {
  window.isTabActive = function(tabId) {
    if (typeof document !== 'undefined' && document.hidden) return false;
    if (!tabId) return false;
    const cleanId = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;
    const rawId = cleanId.replace(/^tab-/, '');
    const pane = document.getElementById(cleanId) || document.getElementById(rawId);
    return pane ? pane.classList.contains('active') : false;
  };
}

// Инициализируем persistence для админки
const tabPersistence = new TabStatePersistence('admin');
window.tabPersistence = tabPersistence;

// Ждем когда main.js загрузится и инициализирует базовые элементы
window.addEventListener('load', async () => {
  console.log('[LazyInitPatch] Window load event, initializing lazy loading...');

  // Ждем немного чтобы main.js выполнил свои скрипты
  await new Promise(resolve => setTimeout(resolve, 100));

  // Если есть оригинальная функция switchTab, оборачиваем ее
  if (window.switchTab && typeof window.switchTab === 'function') {
    const originalSwitchTab = window.switchTab;
    
    // Применяем оптимизацию переключения
    const switchOptimizer = new TabSwitchOptimizer();
    switchOptimizer.enableDOMCaching();
    
    // Оборачиваем в enhanced версию с lazy loading
    let enhancedSwitchTab = enhanceTabSwitching(originalSwitchTab);
    
    // Оборачиваем в optimizer версию для отслеживания производительности
    const optimizedSwitchTab = switchOptimizer.optimizeSwitching(enhancedSwitchTab);
    
    window.switchTab = async function(targetId) {
      // Вызываем оптимизированную функцию
      await optimizedSwitchTab.call(this, targetId);
      
      // Сохраняем активную вкладку
      if (targetId) {
        const cleanId = targetId.startsWith('#') ? targetId.slice(1) : targetId;
        tabPersistence.saveActiveTab(cleanId);
      }
    };
    
    console.log('[LazyInitPatch] Enhanced switchTab with on-demand lazy loading and persistence');
  }

  // Инициализируем ленивую загрузку с определением всех вкладок
  const allTabDefinitions = [
    // Основные вкладки (Диалог и аудио)
    { tabName: 'chat', htmlUrl: `/html/tab_chat/index.html`, jsUrl: `/html/tab_chat/main.js` },
    { tabName: 'voice', htmlUrl: `/html/tab_voice/index.html`, jsUrl: `/html/tab_voice/main.js` },
    { tabName: 'tts', htmlUrl: `/html/tab_tts/index.html`, jsUrl: `/html/tab_tts/main.js` },
    
    // ИИ и Знания
    { tabName: 'rag', htmlUrl: `/html/tab_rag/index.html`, jsUrl: `/html/tab_rag/main.js` },
    { tabName: 'models', htmlUrl: `/html/tab_models/index.html`, jsUrl: `/html/tab_models/main.js` },
    { tabName: 'agents', htmlUrl: `/html/tab_agents/index.html`, jsUrl: `/html/tab_agents/main.js` },
    { tabName: 'skills', htmlUrl: `/html/tab_skills/index.html`, jsUrl: `/html/tab_skills/main.js` },
    { tabName: 'mcp', htmlUrl: `/html/tab_mcp/index.html`, jsUrl: `/html/tab_mcp/main.js` },
    { tabName: 'observability', htmlUrl: `/html/tab_system_inspector/index.html`, jsUrl: `/html/tab_system_inspector/main.js` },
    { tabName: 'telegram-rag', htmlUrl: `/html/tab_telegram_rag/index.html`, jsUrl: `/html/tab_telegram_rag/main.js` },
    { tabName: 'sources', htmlUrl: `/html/tab_sources/index.html`, jsUrl: `/html/tab_sources/main.js` },
    { tabName: 'search', htmlUrl: `/html/tab_search/index.html`, jsUrl: `/html/tab_search/main.js` },
    
    // Система и Администратор
    { tabName: 'admin', htmlUrl: `/html/tab_admin/index.html`, jsUrl: `/html/tab_admin/main.js` },
    { tabName: 'plugins', htmlUrl: `/html/tab_plugins/index.html`, jsUrl: `/html/tab_plugins/main.js` },
    { tabName: 'google-accounts', htmlUrl: `/html/tab_google_accounts/index.html`, jsUrl: `/html/tab_google_accounts/main.js` },
    { tabName: 'instructions', htmlUrl: `/html/tab_instructions/index.html`, jsUrl: `/html/tab_instructions/main.js` },
    { tabName: 'news', htmlUrl: `/html/tab_news/index.html`, jsUrl: `/html/tab_news/main.js` },
    { tabName: 'logs', htmlUrl: `/html/logs/index.html`, jsUrl: `/html/logs/main.js` },
    { tabName: 'help', htmlUrl: `/html/help/index.html`, jsUrl: `/html/help/main.js` },
    { tabName: 'issues', htmlUrl: `/html/tab_issues/index.html`, jsUrl: `/html/tab_issues/main.js` },
    
    // Микроприложения (с привязкой к ID приложения в конфиге профиля)
    { tabName: 'network', appId: 'network_terminal', htmlUrl: `/html/tab_network/index.html`, jsUrl: `/html/tab_network/main.js` },
    { tabName: 'system-inspector', appId: 'system_inspector', htmlUrl: `/html/tab_system_inspector/index.html`, jsUrl: `/html/tab_system_inspector/main.js` },
    { tabName: 'about-system', appId: 'about_system', htmlUrl: `/html/tab_about_system/index.html?v=20261020_v10`, jsUrl: `/html/tab_about_system/main.js?v=20261020_v10` },
    { tabName: 'windows-admin', appId: 'windows_sysadmin', htmlUrl: `/html/tab_windows_admin/index.html`, jsUrl: `/html/tab_windows_admin/main.js` },
    { tabName: 'cloudflared', appId: 'cloudflared_monitor', htmlUrl: `/html/tab_cloudflared/index.html`, jsUrl: `/html/tab_cloudflared/main.js` },
    { tabName: 'user-assistant', appId: 'user_assistant', htmlUrl: `/html/tab_user_assistant/index.html`, jsUrl: `/html/tab_user_assistant/main.js` },
    { tabName: 'gcloud', appId: 'gcloud_monitor', htmlUrl: `/html/tab_gcloud/index.html`, jsUrl: `/html/tab_gcloud/main.js` },
    { tabName: 'website-monitor', appId: 'website_monitor', htmlUrl: `/html/tab_website_monitor/index.html`, jsUrl: `/html/tab_website_monitor/main.js` },
    { tabName: 'system-control', appId: 'system_control_center', htmlUrl: `/html/tab_system_control/index.html?v=20261020_v4`, jsUrl: `/html/tab_system_control/main.js?v=20261020_v4` },
    { tabName: 'system-logs', appId: 'system_log_viewer', htmlUrl: `/html/tab_system_logs/index.html`, jsUrl: `/html/tab_system_logs/main.js` },
    { tabName: 'software-audit', appId: 'software_audit', htmlUrl: `/html/tab_software_audit/index.html`, jsUrl: `/html/tab_software_audit/main.js` },
    { tabName: 'registry-editor', appId: 'registry_editor', htmlUrl: `/html/tab_registry_editor/index.html`, jsUrl: `/html/tab_registry_editor/main.js` },
    { tabName: 'startup-auditor', appId: 'windows_startup_auditor', htmlUrl: `/html/tab_startup_auditor/index.html`, jsUrl: `/html/tab_startup_auditor/main.js` },
    { tabName: 'windows-backup', appId: 'windows_backup_manager', htmlUrl: `/html/tab_windows_backup/index.html?v=20260924_v2`, jsUrl: `/html/tab_windows_backup/main.js?v=20260924_v2` },
    { tabName: 'wikipedia-research', appId: 'wikipedia_research', htmlUrl: `/html/tab_wikipedia_research/index.html`, jsUrl: `/html/tab_wikipedia_research/main.js` },
    { tabName: 'process-leaks', appId: 'process_leaks', htmlUrl: `/html/tab_process_leaks/index.html?v=20260924_v1`, jsUrl: `/html/tab_process_leaks/main.js?v=20260924_v1` },
    { tabName: 'forensics', appId: 'forensics', htmlUrl: `/html/tab_forensics/index.html?v=20260924_v1`, jsUrl: `/html/tab_forensics/main.js?v=20260924_v1` },
    { tabName: 'throttling', appId: 'throttling', htmlUrl: `/html/tab_throttling/index.html?v=20260924_v1`, jsUrl: `/html/tab_throttling/main.js?v=20260924_v1` },
    { tabName: 'storage-wear', appId: 'storage_wear', htmlUrl: `/html/tab_storage_wear/index.html?v=20260924_v1`, jsUrl: `/html/tab_storage_wear/main.js?v=20260924_v1` },
    { tabName: 'peripherals', appId: 'peripherals', htmlUrl: `/html/tab_peripherals/index.html?v=20261016_v2`, jsUrl: `/html/tab_peripherals/main.js?v=20261016_v2` },
  ];

  try {
    // Получаем статус приложений для активного сценария (Run-Dashboard, Run-TC, su)
    let appsStatus = window.appsStatusMap || null;
    if (!appsStatus) {
      try {
        const res = await (window.api ? window.api.fetch('/api/v1/apps/status') : fetch('/api/v1/apps/status').then(r => r.json()));
        appsStatus = res?.apps || null;
      } catch (err) {
        console.warn('[LazyInitPatch] Could not fetch apps status for profile filtering:', err);
      }
    }

    // Фильтруем вкладки: загружаем ТОЛЬКО те, которые разрешены в активном профиле конфига
    const activeTabDefinitions = allTabDefinitions.filter(tab => {
      if (tab.appId && appsStatus) {
        const appInfo = appsStatus[tab.appId] || Object.values(appsStatus).find(a => a.id === tab.appId || a.tab === `tab-${tab.tabName}`);
        if (appInfo && appInfo.enabled === false) {
          return false; // Отключено в активном сценарии/профиле
        }
      }
      return true;
    });

    // Инициализируем систему ленивой загрузки только для разрешенных в профиле вкладок
    await initLazyTabLoading(activeTabDefinitions);
    
    console.log(`[LazyInitPatch] Lazy loading initialized: ${activeTabDefinitions.length} tabs registered on-demand.`);

    // Восстанавливаем и загружаем ТОЛЬКО одну активную вкладку
    const restored = await restoreLastTab('tab-about-system');
    console.log(`[LazyInitPatch] Initial active tab loaded: ${restored}`);

  } catch (error) {
    console.error('[LazyInitPatch] Error during initialization:', error);
  }
});

console.log('[LazyInitPatch] Patch loaded successfully');

export {};

