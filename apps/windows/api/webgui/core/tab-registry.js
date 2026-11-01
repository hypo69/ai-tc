/**
 * =============================================================================
 * Process Name: AI-Windows-Admin UI - Tab-Registry Script
 * =============================================================================
 * Description:
 *   Клиентский веб-скрипт модуля tab-registry.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/src/api/webgui/core/tab-registry.js?v=20261006_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { TAB_DEFINITIONS, TabRegistry } from '/src/api/webgui/core/tab-registry.js';
 *
 * File: tab-registry.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/core
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:02:30
 * =============================================================================
 */

/**
 * TabRegistry – единый источник правды (SSOT) для всех вкладок WebGUI.
 * Экспортирует методы getAll(), getById(id), getFiltered(appsStatusMap, role).
 */
export const TAB_DEFINITIONS = [
  { id: 'smart_restore', label: 'Умное восстановление', icon: 'bi-shield-check', tab: 'smart-restore', tabId: 'tab-smart-restore', html: '/html/tab_smart_restore/index.html?v=20261016_v1', js: '/html/tab_smart_restore/main.js?v=20261016_v1' },
  { id: 'interactive_agent', label: 'Интерактивный Агент', icon: 'bi-robot', tab: 'interactive-agent', tabId: 'tab-interactive-agent', html: '/html/tab_interactive_agent/index.html?v=20261013_v1', js: '/html/tab_interactive_agent/main.js?v=20261013_v1' },
  { id: 'windows_user_settings', label: 'Настройки Windows', icon: 'bi-sliders2', tab: 'windows-settings', tabId: 'tab-windows-settings', html: '/html/tab_windows_settings/index.html?v=20261015_v1', js: '/html/tab_windows_settings/main.js?v=20261015_v1' },
  { id: 'about_system', label: 'О системе', i18nKey: 'auto___d32ca0', icon: 'ℹ️', tab: 'about-system', tabId: 'tab-about-system', html: '/html/tab_about_system/index.html?v=20261020_v10', js: '/html/tab_about_system/main.js?v=20261020_v10' },
  { id: 'scenarios', label: 'Сценарии', i18nKey: 'auto___ddaf0e', icon: '💬', tab: 'scenarios', tabId: 'tab-scenarios', html: '/html/tab_scenarios/index.html?v=20261006_v8', js: '/html/tab_scenarios/main.js?v=20261006_v8' },
  { id: 'chat', label: 'Чат', i18nKey: 'auto___8c77e4', icon: '💬', tab: 'chat', tabId: 'tab-chat', html: '/html/tab_chat/index.html?v=20260923_v5', js: '/html/tab_chat/main.js?v=20260923_v5' },
  { id: 'network_terminal', label: 'Сеть', i18nKey: 'auto___f6df40', icon: '🌐', tab: 'network', tabId: 'tab-network', html: '/html/tab_network/index.html?v=20261028_v1', js: '/html/tab_network/main.js?v=20261028_v1' },
  { id: 'system_inspector', label: 'Инспектор системы', i18nKey: 'auto___4324be', icon: 'bi-graph-up-arrow', tab: 'hardware-load-inspector', tabId: 'tab-hardware-load-inspector', html: '/html/tab_system_inspector/index.html?v=20261030_v1', js: '/html/tab_system_inspector/main.js?v=20261030_v1' },
  { id: 'processes_load_inspector', label: 'Активность процессов', icon: 'bi-activity', tab: 'processes-load-inspector', tabId: 'tab-processes-load-inspector', html: '/html/tab_processes_load_inspector/index.html?v=20261028_v1', js: '/html/tab_processes_load_inspector/main.js?v=20261028_v1' },
  { id: 'windows_sysadmin', label: 'Windows Sysadmin', icon: 'bi-server', tab: 'windows-admin', tabId: 'tab-windows-admin', html: '/html/tab_windows_admin/index.html?v=20261015_v2', js: '/html/tab_windows_admin/main.js?v=20261015_v2' },
  { id: 'focus_settings', label: 'Фокусировка (Focus)', icon: 'bi-circle-half', tab: 'focus-settings', tabId: 'tab-focus-settings', html: '/html/tab_focus_settings/index.html?v=20261006_v1', js: '/html/tab_focus_settings/main.js?v=20261006_v1' },
  { id: 'system32_commands', label: 'Команды System32', icon: '🛠️', tab: 'system32-commands', tabId: 'tab-system32-commands', html: '/html/tab_system32_commands/index.html?v=20261006_v1', js: '/html/tab_system32_commands/main.js?v=20261006_v1' },
  { id: 'system_control_center', label: 'Сводка сбоев и журналы', i18nKey: 'tabs.systemControl', icon: 'bi-shield-exclamation', tab: 'system-control', tabId: 'tab-system-control', html: '/html/tab_system_control/index.html?v=20261020_v4', js: '/html/tab_system_control/main.js?v=20261020_v4' },
  { id: 'post_install_wizard', label: 'Post-Install Wizard', icon: '⚡', tab: 'post-install-wizard', tabId: 'tab-post-install-wizard', html: '/html/tab_post_install_wizard/index.html?v=20261006_v1', js: '/html/tab_post_install_wizard/main.js?v=20261006_v1' },
  { id: 'maintenance_recovery', label: 'Maintenance & Recovery', icon: '🛠️', tab: 'maintenance-recovery', tabId: 'tab-maintenance-recovery', html: '/html/tab_maintenance_recovery/index.html?v=20261006_v1', js: '/html/tab_maintenance_recovery/main.js?v=20261006_v1' },
  { id: 'system_log_viewer', label: 'Логи системы', i18nKey: 'auto___6e28ee', icon: '📋', tab: 'system-logs', tabId: 'tab-system-logs', html: '/html/tab_system_logs/index.html', js: '/html/tab_system_logs/main.js' },
  { id: 'software_audit', label: 'Аудит ПО', i18nKey: 'auto___128e2e', icon: '📦', tab: 'software-audit', tabId: 'tab-software-audit', html: '/html/tab_software_audit/index.html?v=20261016_v3', js: '/html/tab_software_audit/main.js?v=20261016_v3' },
  { id: 'registry_viewer', label: 'Registry Viewer', icon: '🗝️', tab: 'registry-viewer', tabId: 'tab-registry-viewer', html: '/html/tab_registry_viewer/index.html', js: '/html/tab_registry_viewer/main.js' },
  { id: 'windows_defender', label: 'Defender Security', icon: 'bi-shield-lock', tab: 'defender-firewall', tabId: 'tab-defender-firewall', html: '/html/tab_defender_firewall/index.html?v=20261016_v2', js: '/html/tab_defender_firewall/main.js?v=20261016_v2' },
  { id: 'windows_startup_auditor', label: 'Автозагрузка', i18nKey: 'auto___007983', icon: '🚀', tab: 'startup-auditor', tabId: 'tab-startup-auditor', html: '/html/tab_startup_auditor/index.html', js: '/html/tab_startup_auditor/main.js' },
  { id: 'windows_backup_manager', label: 'Windows Backup', icon: '💾', tab: 'windows-backup', tabId: 'tab-windows-backup', html: '/html/tab_windows_backup/index.html?v=20261004_v1', js: '/html/tab_windows_backup/main.js?v=20261004_v1' },
  { id: 'hardware_monitor', label: 'Мониторинг оборудования', i18nKey: 'auto___8a1c35', icon: 'bi-cpu', tab: 'hardware-monitor', tabId: 'tab-hardware-monitor', html: '/html/tab_hardware_monitor/index.html', js: '/html/tab_hardware_monitor/main.js' },
  { id: 'cloudflared_monitor', label: 'Cloudflared', icon: '☁️', tab: 'cloudflared', tabId: 'tab-cloudflared', html: '/html/tab_cloudflared/index.html', js: '/html/tab_cloudflared/main.js' },
  { id: 'google_user_desktop', label: 'Google User Desktop', icon: '🌐', tab: 'google-desktop', tabId: 'tab-google-desktop', html: '/html/tab_google_desktop/index.html?v=20260928_v2', js: '/html/tab_google_desktop/main.js?v=20260928_v2' },
  { id: 'gcloud_monitor', label: 'Google Cloud', icon: '☁️', tab: 'gcloud', tabId: 'tab-gcloud', html: '/html/tab_gcloud/index.html', js: '/html/tab_gcloud/main.js' },
  { id: 'website_monitor', label: 'Website Intelligence', icon: '📊', tab: 'website-monitor', tabId: 'tab-website-monitor', html: '/html/tab_website_monitor/index.html', js: '/html/tab_website_monitor/main.js' },
  { id: 'user_assistant', label: 'User Assistant', icon: '🗓️', tab: 'user-assistant', tabId: 'tab-user-assistant', html: '/html/tab_user_assistant/index.html', js: '/html/tab_user_assistant/main.js' },
  { id: 'helpdesk', label: 'Helpdesk', icon: '🎫', tab: 'helpdesk', tabId: 'tab-helpdesk', html: '/html/tab_helpdesk/index.html', js: '/html/tab_helpdesk/main.js' },
  { id: 'wikipedia_research', label: 'Wikipedia Research', icon: '📖', tab: 'wikipedia-research', tabId: 'tab-wikipedia-research', html: '/html/tab_wikipedia_research/index.html', js: '/html/tab_wikipedia_research/main.js' },
  { id: 'autolog_manager', label: 'Автологи', i18nKey: 'auto___17b9d1', icon: '📝', tab: 'autolog', tabId: 'tab-autolog', html: '/html/tab_telemetry_config/index.html?v=20261010_v2', js: '/html/tab_telemetry_config/main.js?v=20261010_v2' },
  { id: 'software_transparency_scanner', label: 'Transparency Scanner', icon: '🔍', tab: 'software-transparency', tabId: 'tab-software-transparency', html: '/html/tab_software_transparency/index.html?v=20261028_v1', js: '/html/tab_software_transparency/main.js?v=20261028_v1' },
  { id: 'ninite_updater', label: 'Ninite Updater', icon: '🔄', tab: 'ninite-updater', tabId: 'tab-ninite-updater', html: '/html/tab_ninite_updater/index.html?v=20260924_v2', js: '/html/tab_ninite_updater/main.js?v=20260924_v2' },
  { id: 'file_recovery', label: 'Восстановление файлов', i18nKey: 'auto___8f9984', icon: '🩹', tab: 'file-recovery', tabId: 'tab-file-recovery', html: '/html/tab_file_recovery/index.html', js: '/html/tab_file_recovery/main.js' },
  { id: 'file_history_ai_search', label: 'Поиск файлов AI', i18nKey: 'auto__ai_2d3bf7', icon: '🔍', tab: 'file-history-search', tabId: 'tab-file-history-search', html: '/html/tab_file_history_ai_search/index.html?v=20260928_v1', js: '/html/tab_file_history_ai_search/main.js?v=20260928_v1' },
  { id: 'telemetry_research', label: 'Исследование телеметрии', i18nKey: 'auto___025fa1', icon: '🔬', tab: 'telemetry-research', tabId: 'tab-telemetry-research', html: '/html/tab_telemetry_research/index.html?v=20260924_v1', js: '/html/tab_telemetry_research/main.js?v=20260924_v1' },
  { id: 'process_leaks', label: 'Утечки процессов', i18nKey: 'auto___6e10ab', icon: '⚠️', tab: 'process-leaks', tabId: 'tab-process-leaks', html: '/html/tab_process_leaks/index.html?v=20261013_v1', js: '/html/tab_process_leaks/main.js?v=20261013_v1' },
  { id: 'forensics', label: 'Форензика', i18nKey: 'auto___82e8f9', icon: '🛡️', tab: 'forensics', tabId: 'tab-forensics', html: '/html/tab_forensics/index.html?v=20261010_v2', js: '/html/tab_forensics/main.js?v=20261010_v2' },
  { id: 'throttling', label: 'Троттлинг', i18nKey: 'auto___23403a', icon: '🌡️', tab: 'throttling', tabId: 'tab-throttling', html: '/html/tab_throttling/index.html?v=20260924_v1', js: '/html/tab_throttling/main.js?v=20260924_v1' },
  { id: 'storage_wear', label: 'Износ дисков', i18nKey: 'auto___5c3dfb', icon: '💽', tab: 'storage-wear', tabId: 'tab-storage-wear', html: '/html/tab_storage_wear/index.html?v=20261015_v1', js: '/html/tab_storage_wear/main.js?v=20261015_v1' },
  { id: 'peripherals', label: 'Периферия', i18nKey: 'auto___b62c2e', icon: '🔌', tab: 'peripherals', tabId: 'tab-peripherals', html: '/html/tab_peripherals/index.html?v=20261016_v2', js: '/html/tab_peripherals/main.js?v=20261016_v2' },
  { id: 'rag', label: 'RAG База знаний', i18nKey: 'auto_rag__829445', icon: '🧠', tab: 'rag', tabId: 'tab-rag', html: '/html/tab_rag/index.html', js: '/html/tab_rag/main.js' },
  { id: 'pixelrag', label: 'PixelRAG', icon: '🖼️', tab: 'pixelrag', tabId: 'tab-pixelrag', html: '/html/tab_pixelrag/index.html', js: '/html/tab_pixelrag/main.js' },
  { id: 'models', label: 'Модели', i18nKey: 'auto___44bfc5', icon: '🤖', tab: 'models', tabId: 'tab-models', html: '/html/tab_models/index.html?v=20261015_v2', js: '/html/tab_models/main.js?v=20261015_v2' },
  { id: 'agents', label: 'Агенты', i18nKey: 'auto___af1850', icon: '🧩', tab: 'agents', tabId: 'tab-agents', html: '/html/tab_agents/index.html', js: '/html/tab_agents/main.js' },
  { id: 'skills', label: 'Навыки', i18nKey: 'auto___56221b', icon: '⚡', tab: 'skills', tabId: 'tab-skills', html: '/html/tab_skills/index.html', js: '/html/tab_skills/main.js' },
  { id: 'ai_benchmark', label: 'AI Benchmark', icon: '⏱️', tab: 'ai-benchmark', tabId: 'tab-ai-benchmark', html: '/html/tab_ai_benchmark/index.html?v=20260926_v1', js: '/html/tab_ai_benchmark/main.js?v=20260926_v1' },
  { id: 'storage_manager', label: 'Управление дисками', icon: '💽', tab: 'storage-manager', tabId: 'tab-storage-manager', html: '/html/tab_storage_manager/index.html?v=20261001_v1', js: '/html/tab_storage_manager/main.js?v=20261001_v1' },
  { id: 'disk_speed', label: 'Скорость накопителей', icon: '⚡', tab: 'disk-speed', tabId: 'tab-disk-speed', html: '/html/tab_disk_speed/index.html?v=20261004_v1', js: '/html/tab_disk_speed/main.js?v=20261004_v1' },
  { id: 'boot_recovery', label: 'Загрузка и восстановление', icon: '🔄', tab: 'boot-recovery', tabId: 'tab-boot-recovery', html: '/html/tab_boot_recovery/index.html?v=20261001_v1', js: '/html/tab_boot_recovery/main.js?v=20261001_v1' },
  { id: 'servicing_integrity', label: 'Целостность системы (SFC/DISM)', icon: '🛡️', tab: 'servicing-integrity', tabId: 'tab-servicing-integrity', html: '/html/tab_servicing_integrity/index.html?v=20261001_v1', js: '/html/tab_servicing_integrity/main.js?v=20261001_v1' },
  { id: 'services_manager', label: 'Службы Windows', icon: '⚙️', tab: 'services-manager', tabId: 'tab-services-manager', html: '/html/tab_services_manager/index.html?v=20261006_v1', js: '/html/tab_services_manager/main.js?v=20261006_v1' },
  { id: 'task_scheduler', label: 'Планировщик задач', icon: '⏱️', tab: 'task-scheduler', tabId: 'tab-task-scheduler', html: '/html/tab_task_scheduler/index.html?v=20261015_v1', js: '/html/tab_task_scheduler/main.js?v=20261015_v1' },
  { id: 'process_manager', label: 'Диспетчер процессов', icon: '📊', tab: 'process-manager', tabId: 'tab-process-manager', html: '/html/tab_process_manager/index.html?v=20261015_v5', js: '/html/tab_process_manager/main.js?v=20261015_v5' },
  { id: 'firewall_manager', label: 'Брандмауэр Windows', icon: '🔥', tab: 'firewall-manager', tabId: 'tab-firewall-manager', html: '/html/tab_firewall_manager/index.html?v=20261001_v1', js: '/html/tab_firewall_manager/main.js?v=20261001_v1' },
  { id: 'performance_tracing', label: 'Трассировка ETW', icon: '📈', tab: 'performance-tracing', tabId: 'tab-performance-tracing', html: '/html/tab_performance_tracing/index.html?v=20261001_v1', js: '/html/tab_performance_tracing/main.js?v=20261001_v1' },
  { id: 'log_settings', label: 'Параметры журналов', icon: 'bi-sliders', tab: 'log-settings', tabId: 'tab-log-settings', html: '/html/tab_log_settings/index.html?v=20261008_v1', js: '/html/tab_log_settings/main.js?v=20261008_v1' },
  { id: 'software_manager', label: 'Пакетный менеджер', icon: '📦', tab: 'software-manager', tabId: 'tab-software-manager', html: '/html/tab_software_manager/index.html?v=20261004_v2', js: '/html/tab_software_manager/main.js?v=20261004_v2' },
  { id: 'taskbar_controller', label: 'Панель задач и Окна', icon: '📌', tab: 'taskbar', tabId: 'tab-taskbar', html: '/html/tab_taskbar/index.html?v=20261020_v3', js: '/html/tab_taskbar/main.js?v=20261020_v3' },
  { id: 'power_lifecycle', label: 'Электропитание и сессии', icon: '⚡', tab: 'power-lifecycle', tabId: 'tab-power-lifecycle', html: '/html/tab_power_lifecycle/index.html?v=20261008_v2', js: '/html/tab_power_lifecycle/main.js?v=20261008_v2' },
  { id: 'app_logs', label: 'Логи приложений', icon: '📋', tab: 'app-logs', tabId: 'tab-app-logs', html: '/html/tab_app_logs/index.html?v=20261010_v4', js: '/html/tab_app_logs/main.js?v=20261010_v4' },
  { id: 'software_monitor', label: 'Установленные программы', icon: 'bi-box-seam', tab: 'software-monitor', tabId: 'tab-software-monitor', html: '/html/tab_software_monitor/index.html?v=20261028_v1', js: '/html/tab_software_monitor/main.js?v=20261028_v1' },
  { id: 'software_scanner', label: 'Установленные программы (Legacy)', icon: 'bi-box-seam', tab: 'software-scanner', tabId: 'tab-software-scanner', html: '/html/tab_software_monitor/index.html?v=20261028_v1', js: '/html/tab_software_monitor/main.js?v=20261028_v1' },
  { id: 'mcp', label: 'MCP Серверы', icon: '🔌', tab: 'mcp', tabId: 'tab-mcp', html: '/html/tab_mcp/index.html', js: '/html/tab_mcp/main.js' },
  { id: 'wikillm', label: 'WikiLLM База знаний', icon: '📚', tab: 'wikillm', tabId: 'tab-wikillm', html: '/html/templates/tabs/tab_wikillm.html?v=20261013_v1', js: '/static/js/wikillm_controller.js?v=20261013_v1' },
  { id: 'theme_editor', label: 'Редактор тем оформления', icon: 'bi-palette2', tab: 'theme-editor', tabId: 'tab-theme-editor', html: '/html/tab_theme_editor/index.html?v=20261020_v2', js: '/html/tab_theme_editor/main.js?v=20261020_v2' },
  { id: 'app_internals', label: 'Внутренняя кухня', icon: '🛠️', tab: 'app-internals', tabId: 'tab-app-internals', html: '/html/tab_app_internals/index.html?v=20261031_v7', js: '/html/tab_app_internals/main.js?v=20261031_v7' },
  { id: 'sound_settings', label: 'Настройка звука', icon: 'bi-volume-up', tab: 'sound-settings', tabId: 'tab-sound-settings', html: '/html/tab_sound_settings/index.html?v=20261027_v1', js: '/html/tab_sound_settings/main.js?v=20261027_v1' },
  { id: 'user_environment', label: 'Окружение пользователя', icon: 'bi-person-workspace', tab: 'user-environment', tabId: 'tab-user-environment', html: '/html/tab_user_environment/index.html?v=20261101_v1', js: '/html/tab_user_environment/main.js?v=20261101_v1' },
  { id: 'user_enviroment', label: 'Окружение пользователя', icon: 'bi-person-workspace', tab: 'user-enviroment', tabId: 'tab-user-enviroment', html: '/html/tab_user_environment/index.html?v=20261101_v1', js: '/html/tab_user_environment/main.js?v=20261101_v1' },
  { id: 'sitemap', label: 'Карта сайта (Sitemap)', icon: 'bi-diagram-3-fill', tab: 'sitemap', tabId: 'tab-sitemap', html: '/html/tab_sitemap/index.html?v=20261015_v1', js: '/html/tab_sitemap/main.js?v=20261015_v1' }
];

export class TabRegistry {
  static getAll() { return TAB_DEFINITIONS; }
  static getById(tabId) {
    if (!tabId) return null;
    const clean = tabId.replace(/^tab-/, '');
    return TAB_DEFINITIONS.find(t =>
      t.id === clean ||
      t.tab === clean ||
      t.tabId === tabId ||
      t.tabId === `tab-${clean}` ||
      t.appId === clean
    ) || null;
  }
  static getLabel(tab) {
    if (!tab) return '';
    if (tab.i18nKey && typeof window !== 'undefined' && window.i18next?.t) {
      const translated = window.i18next.t(tab.i18nKey);
      if (translated && translated !== tab.i18nKey) return translated;
    }
    return tab.label || '';
  }
  static getFiltered(appsStatusMap = null, targetRole = 'admin') {
    return TAB_DEFINITIONS.filter(tab => {
      if (tab.roles && !tab.roles.includes(targetRole)) return false;
      if (tab.appId && appsStatusMap && appsStatusMap[tab.appId]) {
        return appsStatusMap[tab.appId].enabled !== false;
      }
      return true;
    });
  }
}

