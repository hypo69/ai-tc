# 🌐 Роутеры внутреннего API Windows (apps/windows/api/routers)

Пакет FastAPI-роутеров. Подключаются двумя путями: явно из `api/config.json` (`routers[]`) и автоматически через `discover_and_register_routers` (см. [`../README.md`](../README.md)).

## Роутеры (`router_*.py`)

| Группа | Файлы |
|---|---|
| Телеметрия и нагрузка | `router_telemetry`, `router_telemetry_config`, `router_cpu_load`, `router_gpu_load`, `router_memory_io`, `router_network_load`, `router_storage_load`, `router_processes_load_inspector`, `router_process_activity`, `router_power_lifecycle` |
| Журналы и форензика | `router_system_logs`, `router_app_logs`, `router_log_settings`, `router_forensics` |
| Администрирование Windows | `router_windows_admin`, `router_storage`, `router_registry_viewer`, `router_system32_catalog`, `router_safe_ops`, `router_settings`, `router_sound`, `router_focus`, `router_ninite`, `router_diagnostics` |
| ИИ и знания | `router_chat`, `router_agents`, `router_interactive_agent`, `router_ai_instruments`, `router_procedural_tools`, `router_wikillm_editor`, `router_keys` |
| Интерфейс | `router_menu`, `router_panel`, `router_scenarios`, `router_control`, `router_tc`, `router_admin`, `router_about_system` |

## Подпакеты

`admin/`, `chat/`, `about_system/`, `scenarios/`, `tc/` — составные роутеры (у каждого свой README); `tab_software_scanner/` — ИИ-диагностика ПО.

**Updated:** 2026-10-31 16:45:00