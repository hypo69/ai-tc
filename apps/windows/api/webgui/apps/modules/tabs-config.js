/**
 * =============================================================================
 * Process Name: Windows Modules - Tabs-Config Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля tabs-config.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/apps/modules/tabs-config.js?v=20261008_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { APP_TAB_DEFS, TC_EXCLUDES } from '/windows/api/webgui/apps/modules/tabs-config.js';
 *
 * File: tabs-config.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/apps/modules
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:03:00
 * =============================================================================
 */

export const APP_TAB_DEFS = [
  // Консолидированные панели
  { id: 'smart_restore', tab: 'smart-restore', tabId: 'tab-smart-restore', html: '/html/tab_smart_restore/index.html?v=20261016_v1', js: '/html/tab_smart_restore/main.js?v=20261016_v1' },
  { id: 'windows_user_settings', tab: 'windows-settings', tabId: 'tab-windows-settings', html: '/html/tab_windows_settings/index.html?v=20261015_v1', js: '/html/tab_windows_settings/main.js?v=20261015_v1' },
  { id: 'app_internals', tab: 'app-internals', tabId: 'tab-app-internals', html: '/html/tab_app_internals/index.html?v=20261031_v7', js: '/html/tab_app_internals/main.js?v=20261031_v7' },
  { id: 'ai_ecosystem', tab: 'ai-ecosystem', tabId: 'tab-ai-ecosystem', html: '/html/tab_ai_ecosystem/index.html?v=20261030_v1', js: '/html/tab_ai_ecosystem/main.js?v=20261030_v1' },
  { id: 'storage_management', tab: 'storage-management', tabId: 'tab-storage-management', html: '/html/tab_storage_management/index.html?v=20261013_v2', js: '/html/tab_storage_management/main.js?v=20261013_v2' },
  { id: 'telemetry_control', tab: 'telemetry-control', tabId: 'tab-telemetry-control', html: '/html/tab_telemetry_control/index.html?v=20261013_v2', js: '/html/tab_telemetry_control/main.js?v=20261013_v2' },
  { id: 'interactive_agent', tab: 'interactive-agent', tabId: 'tab-interactive-agent', html: '/html/tab_interactive_agent/index.html?v=20261013_v1', js: '/html/tab_interactive_agent/main.js?v=20261013_v1' },
  { id: 'user_environment', tab: 'user-environment', tabId: 'tab-user-environment', html: '/html/tab_user_environment/index.html?v=20261031_v1', js: '/html/tab_user_environment/main.js?v=20261031_v1' },
  { id: 'user_enviroment', tab: 'user-enviroment', tabId: 'tab-user-enviroment', html: '/html/tab_user_environment/index.html?v=20261031_v1', js: '/html/tab_user_environment/main.js?v=20261031_v1' },

  { id: 'about_system', tab: 'about-system', tabId: 'tab-about-system', html: '/html/tab_about_system/index.html?v=20261028_v4', js: '/html/tab_about_system/main.js?v=20261028_v4' },
  { id: 'scenarios', tab: 'scenarios', tabId: 'tab-scenarios', html: '/html/tab_scenarios/index.html?v=20261006_v8', js: '/html/tab_scenarios/main.js?v=20261006_v8' },
  { id: 'chat', tab: 'chat', tabId: 'tab-chat', html: '/html/tab_chat/index.html?v=20260923_v5', js: '/html/tab_chat/main.js?v=20260923_v5' },
  { id: 'network_terminal', tab: 'network', tabId: 'tab-network', html: '/html/tab_network/index.html?v=20261028_v1', js: '/html/tab_network/main.js?v=20261028_v1' },
  { id: 'system_inspector', tab: 'hardware-load-inspector', tabId: 'tab-hardware-load-inspector', html: '/html/tab_system_inspector/index.html?v=20261030_v1', js: '/html/tab_system_inspector/main.js?v=20261030_v1' },
  { id: 'processes_load_inspector', tab: 'processes-load-inspector', tabId: 'tab-processes-load-inspector', html: '/html/tab_processes_load_inspector/index.html?v=20261028_v1', js: '/html/tab_processes_load_inspector/main.js?v=20261028_v1' },
  { id: 'windows_sysadmin', tab: 'windows-admin', tabId: 'tab-windows-admin', html: '/html/tab_windows_admin/index.html?v=20261015_v2', js: '/html/tab_windows_admin/main.js?v=20261015_v2' },
  { id: 'focus_settings', tab: 'focus-settings', tabId: 'tab-focus-settings', html: '/html/tab_focus_settings/index.html?v=20261006_v1', js: '/html/tab_focus_settings/main.js?v=20261006_v1' },
  { id: 'system32_commands', tab: 'system32-commands', tabId: 'tab-system32-commands', html: '/html/tab_system32_commands/index.html?v=20261006_v1', js: '/html/tab_system32_commands/main.js?v=20261006_v1' },
  { id: 'system_control_center', tab: 'system-control', tabId: 'tab-system-control', html: '/html/tab_system_control/index.html?v=20261020_v3', js: '/html/tab_system_control/main.js?v=20261020_v3' },
  { id: 'post_install_wizard', tab: 'post-install-wizard', tabId: 'tab-post-install-wizard', html: '/html/tab_post_install_wizard/index.html?v=20261006_v1', js: '/html/tab_post_install_wizard/main.js?v=20261006_v1' },
  { id: 'maintenance_recovery', tab: 'maintenance-recovery', tabId: 'tab-maintenance-recovery', html: '/html/tab_maintenance_recovery/index.html?v=20261006_v1', js: '/html/tab_maintenance_recovery/main.js?v=20261006_v1' },
  { id: 'system_log_viewer', tab: 'system-logs', tabId: 'tab-system-logs', html: '/html/tab_system_logs/index.html', js: '/html/tab_system_logs/main.js' },
  { id: 'software_audit', tab: 'software-audit', tabId: 'tab-software-audit', html: '/html/tab_software_audit/index.html', js: '/html/tab_software_audit/main.js' },
  { id: 'registry_viewer', tab: 'registry-viewer', tabId: 'tab-registry-viewer', html: '/html/tab_registry_viewer/index.html', js: '/html/tab_registry_viewer/main.js' },
  { id: 'windows_defender', tab: 'defender-firewall', tabId: 'tab-defender-firewall', html: '/html/tab_defender_firewall/index.html?v=20261028_v5', js: '/html/tab_defender_firewall/main.js?v=20261028_v5' },
  { id: 'windows_defender_legacy', tab: 'defender', tabId: 'tab-defender', html: '/html/tab_defender_firewall/index.html?v=20261028_v5', js: '/html/tab_defender_firewall/main.js?v=20261028_v5' },
  { id: 'windows_startup_auditor', tab: 'startup-auditor', tabId: 'tab-startup-auditor', html: '/html/tab_startup_auditor/index.html?v=20261006_v15', js: '/html/tab_startup_auditor/main.js?v=20261006_v15' },
  { id: 'windows_backup_manager', tab: 'windows-backup', tabId: 'tab-windows-backup', html: '/html/tab_windows_backup/index.html?v=20261004_v1', js: '/html/tab_windows_backup/main.js?v=20261004_v1' },
  { id: 'hardware_monitor', tab: 'hardware-monitor', tabId: 'tab-hardware-monitor', html: '/html/tab_hardware_monitor/index.html', js: '/html/tab_hardware_monitor/main.js' },
  { id: 'cloudflared_monitor', tab: 'cloudflared', tabId: 'tab-cloudflared', html: '/html/tab_cloudflared/index.html', js: '/html/tab_cloudflared/main.js' },
  { id: 'google_user_desktop', tab: 'google-desktop', tabId: 'tab-google-desktop', html: '/html/tab_google_desktop/index.html', js: '/html/tab_google_desktop/main.js' },
  { id: 'gcloud_monitor', tab: 'gcloud', tabId: 'tab-gcloud', html: '/html/tab_gcloud/index.html', js: '/html/tab_gcloud/main.js' },
  { id: 'website_monitor', tab: 'website-monitor', tabId: 'tab-website-monitor', html: '/html/tab_website_monitor/index.html', js: '/html/tab_website_monitor/main.js' },
  { id: 'user_assistant', tab: 'user-assistant', tabId: 'tab-user-assistant', html: '/html/tab_user_assistant/index.html', js: '/html/tab_user_assistant/main.js' },
  { id: 'helpdesk', tab: 'helpdesk', tabId: 'tab-helpdesk', html: '/html/tab_helpdesk/index.html', js: '/html/tab_helpdesk/main.js' },
  { id: 'wikipedia_research', tab: 'wikipedia-research', tabId: 'tab-wikipedia-research', html: '/html/tab_wikipedia_research/index.html', js: '/html/tab_wikipedia_research/main.js' },
  { id: 'software_transparency_scanner', tab: 'software-transparency', tabId: 'tab-software-transparency', html: '/html/tab_software_transparency/index.html', js: '/html/tab_software_transparency/main.js' },
  { id: 'software_monitor', tab: 'software-monitor', tabId: 'tab-software-monitor', html: '/html/tab_software_monitor/index.html?v=20261028_v1', js: '/html/tab_software_monitor/main.js?v=20261028_v1' },
  { id: 'software_scanner', tab: 'software-scanner', tabId: 'tab-software-scanner', html: '/html/tab_software_monitor/index.html?v=20261028_v1', js: '/html/tab_software_monitor/main.js?v=20261028_v1' },
  { id: 'ninite_updater', tab: 'ninite-updater', tabId: 'tab-ninite-updater', html: '/html/tab_ninite_updater/index.html?v=20260924_v2', js: '/html/tab_ninite_updater/main.js?v=20260924_v2' },
  { id: 'file_recovery', tab: 'file-recovery', tabId: 'tab-file-recovery', html: '/html/tab_file_recovery/index.html', js: '/html/tab_file_recovery/main.js' },
  { id: 'file_history_ai_search', tab: 'file-history-search', tabId: 'tab-file-history-search', html: '/html/tab_file_history_ai_search/index.html?v=20260928_v1', js: '/html/tab_file_history_ai_search/main.js?v=20260928_v1' },
  { id: 'telemetry_research', tab: 'telemetry-research', tabId: 'tab-telemetry-research', html: '/html/tab_telemetry_research/index.html?v=20260924_v1', js: '/html/tab_telemetry_research/main.js?v=20260924_v1' },
  { id: 'telemetry_config', tab: 'telemetry-config', tabId: 'tab-telemetry-config', html: '/html/tab_telemetry_config/index.html?v=20261010_v2', js: '/html/tab_telemetry_config/main.js?v=20261010_v2' },
  { id: 'autolog_manager', tab: 'autolog', tabId: 'tab-autolog', html: '/html/tab_telemetry_config/index.html?v=20261010_v2', js: '/html/tab_telemetry_config/main.js?v=20261010_v2' },
  { id: 'process_leaks', tab: 'process-leaks', tabId: 'tab-process-leaks', html: '/html/tab_process_leaks/index.html?v=20261013_v1', js: '/html/tab_process_leaks/main.js?v=20261013_v1' },
  { id: 'forensics', tab: 'forensics', tabId: 'tab-forensics', html: '/html/tab_forensics/index.html?v=20261010_v2', js: '/html/tab_forensics/main.js?v=20261010_v2' },

  { id: 'throttling', tab: 'throttling', tabId: 'tab-throttling', html: '/html/tab_throttling/index.html?v=20260924_v1', js: '/html/tab_throttling/main.js?v=20260924_v1' },
  { id: 'storage_wear', tab: 'storage-wear', tabId: 'tab-storage-wear', html: '/html/tab_storage_wear/index.html?v=20261015_v1', js: '/html/tab_storage_wear/main.js?v=20261015_v1' },
  { id: 'peripherals', tab: 'peripherals', tabId: 'tab-peripherals', html: '/html/tab_peripherals/index.html?v=20261016_v2', js: '/html/tab_peripherals/main.js?v=20261016_v2' },
  { id: 'rag', tab: 'rag', tabId: 'tab-rag', html: '/html/tab_rag/index.html', js: '/html/tab_rag/main.js' },
  { id: 'pixelrag', tab: 'pixelrag', tabId: 'tab-pixelrag', html: '/html/tab_pixelrag/index.html', js: '/html/tab_pixelrag/main.js' },
  { id: 'models', tab: 'models', tabId: 'tab-models', html: '/html/tab_models/index.html?v=20261010_v1', js: '/html/tab_models/main.js?v=20261010_v1' },
  { id: 'agents', tab: 'agents', tabId: 'tab-agents', html: '/html/tab_agents/index.html', js: '/html/tab_agents/main.js' },
  { id: 'skills', tab: 'skills', tabId: 'tab-skills', html: '/html/tab_skills/index.html', js: '/html/tab_skills/main.js' },
  { id: 'mcp', tab: 'mcp', tabId: 'tab-mcp', html: '/html/tab_mcp/index.html', js: '/html/tab_mcp/main.js' },
  { id: 'ai_benchmark', tab: 'ai-benchmark', tabId: 'tab-ai-benchmark', html: '/html/tab_ai_benchmark/index.html?v=20260926_v1', js: '/html/tab_ai_benchmark/main.js?v=20260926_v1' },

  // Новые модули управления Windows CLI
  { id: 'storage_manager', tab: 'storage-manager', tabId: 'tab-storage-manager', html: '/html/tab_storage_manager/index.html?v=20261001_v1', js: '/html/tab_storage_manager/main.js?v=20261001_v1' },
  { id: 'disk_speed', tab: 'disk-speed', tabId: 'tab-disk-speed', html: '/html/tab_disk_speed/index.html?v=20261004_v1', js: '/html/tab_disk_speed/main.js?v=20261004_v1' },
  { id: 'boot_recovery', tab: 'boot-recovery', tabId: 'tab-boot-recovery', html: '/html/tab_boot_recovery/index.html?v=20261001_v1', js: '/html/tab_boot_recovery/main.js?v=20261001_v1' },
  { id: 'servicing_integrity', tab: 'servicing-integrity', tabId: 'tab-servicing-integrity', html: '/html/tab_servicing_integrity/index.html?v=20261001_v1', js: '/html/tab_servicing_integrity/main.js?v=20261001_v1' },
  { id: 'services_manager', tab: 'services-manager', tabId: 'tab-services-manager', html: '/html/tab_services_manager/index.html?v=20261006_v1', js: '/html/tab_services_manager/main.js?v=20261006_v1' },
  { id: 'task_scheduler', tab: 'task-scheduler', tabId: 'tab-task-scheduler', html: '/html/tab_task_scheduler/index.html?v=20261015_v1', js: '/html/tab_task_scheduler/main.js?v=20261015_v1' },
  { id: 'process_manager', tab: 'process-manager', tabId: 'tab-process-manager', html: '/html/tab_process_manager/index.html?v=20261015_v4', js: '/html/tab_process_manager/main.js?v=20261015_v4' },
  { id: 'firewall_manager', tab: 'firewall-manager', tabId: 'tab-firewall-manager', html: '/html/tab_firewall_manager/index.html?v=20261001_v1', js: '/html/tab_firewall_manager/main.js?v=20261001_v1' },
  { id: 'performance_tracing', tab: 'performance-tracing', tabId: 'tab-performance-tracing', html: '/html/tab_performance_tracing/index.html?v=20261001_v1', js: '/html/tab_performance_tracing/main.js?v=20261001_v1' },
  { id: 'log_settings', tab: 'log-settings', tabId: 'tab-log-settings', html: '/html/tab_log_settings/index.html?v=20261008_v1', js: '/html/tab_log_settings/main.js?v=20261008_v1' },
  { id: 'software_manager', tab: 'software-manager', tabId: 'tab-software-manager', html: '/html/tab_software_manager/index.html?v=20261004_v2', js: '/html/tab_software_manager/main.js?v=20261004_v2' },
  { id: 'taskbar_controller', tab: 'taskbar-controller', tabId: 'tab-taskbar-controller', html: '/html/tab_taskbar/index.html?v=20261010_v2', js: '/html/tab_taskbar/main.js?v=20261010_v2' },
  { id: 'taskbar', tab: 'taskbar', tabId: 'tab-taskbar', html: '/html/tab_taskbar/index.html?v=20261010_v2', js: '/html/tab_taskbar/main.js?v=20261010_v2' },
  { id: 'power_lifecycle', tab: 'power-lifecycle', tabId: 'tab-power-lifecycle', html: '/html/tab_power_lifecycle/index.html?v=20261008_v2', js: '/html/tab_power_lifecycle/main.js?v=20261008_v2' },
  { id: 'app_logs', tab: 'app-logs', tabId: 'tab-app-logs', html: '/html/tab_app_logs/index.html?v=20261010_v4', js: '/html/tab_app_logs/main.js?v=20261010_v4' },
  { id: 'theme_editor', tab: 'theme-editor', tabId: 'tab-theme-editor', html: '/html/tab_theme_editor/index.html?v=20261020_v2', js: '/html/tab_theme_editor/main.js?v=20261020_v2' },
  { id: 'sound_settings', tab: 'sound-settings', tabId: 'tab-sound-settings', html: '/html/tab_sound_settings/index.html?v=20261027_v1', js: '/html/tab_sound_settings/main.js?v=20261027_v1' },
  { id: 'sitemap', tab: 'sitemap', tabId: 'tab-sitemap', html: '/html/tab_sitemap/index.html?v=20261015_v1', js: '/html/tab_sitemap/main.js?v=20261015_v1' },
];

export const TC_EXCLUDES = new Set([
  'cloudflared_monitor',
  'gcloud_monitor',
  'website_monitor',
  'user_assistant',
  'wikipedia_research',
  'helpdesk'
]);

