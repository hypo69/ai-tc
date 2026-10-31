# Windows API и веб-интерфейс (`apps.windows.api`)

Один из трёх основных рабочих модулей проекта (вместе с [`sdk`](../sdk/README.md) и [`telemetry`](../telemetry/README.md)). FastAPI-сервер, REST-роутеры и WebGUI (вкладки `tab_*`) — «лицо» системы: читает `telemetry.db` и вызывает инструменты SDK.

---

## 🏛️ Структура

```
apps/windows/api/
├── __main__.py            # Запуск Uvicorn: py -m apps.windows.api --port 8001
├── server.py              # create_app(), load_config(), discover_and_register_routers(), монтирование статики
├── internal_app.py        # Реэкспорт фабрик из server.py (create_internal_app и др.)
├── config.json            # server (127.0.0.1:8001) и список routers (module, factory, enabled)
├── config_helper.py       # Чтение/сохранение настроек моделей и провайдеров
├── auth.py                # JWT: TokenData, get_current_user_optional, require_admin_user
├── chat_sessions_db.py    # SQLite-хранилище сессий чата
├── diagnostics_prompt_manager.py  # Шаблоны промптов для аудита/объяснения таблиц
├── router_about_system.py, router_capabilities.py, router_software.py,
│   router_wikillm_editor.py   # Роутеры верхнего уровня пакета
├── routers/               # Основные роутеры router_*.py (см. routers/README.md)
│   ├── admin/, chat/, about_system/, scenarios/, tc/   # Подпакеты роутеров
│   └── tab_software_scanner/   # router_software_ai.py — ИИ-диагностика ПО
├── services/              # sysmon_inspector.py, wikillm_service.py (фоновое обогащение WikiLLM)
├── data/                  # Рабочие данные API
└── webgui/                # Фронтенд (см. webgui/README.md)
```

## 🔌 Как собирается приложение

1. `create_app()` читает `config.json` и подключает роутеры из списка `routers` (`module` + `factory`, флаг `enabled`).
2. Затем `discover_and_register_routers(app, "apps.windows", ...)` автоматически находит остальные `router_*` модули пакета `apps.windows` (уже зарегистрированные пропускаются).
3. Роутеры подключаются через `safe_include_router` — сбой одного роутера не роняет сервер.
4. Монтируется статика: `/webinterface` и `/html` (`SmartMultiDirStaticFiles`: webgui Windows → общий `apps/common/webgui`), `/apps/static`, `/static`.
5. Служебные эндпоинты: `/health`, статус приложений, пользовательские настройки, активная модель чата, темы, терминал.

## 🧭 Группы роутеров (`routers/`)

| Группа | Файлы |
|---|---|
| Телеметрия и нагрузка | `router_telemetry`, `router_telemetry_config`, `router_cpu_load`, `router_gpu_load`, `router_memory_io`, `router_network_load`, `router_storage_load`, `router_processes_load_inspector`, `router_process_activity`, `router_power_lifecycle` |
| Журналы и форензика | `router_system_logs`, `router_app_logs`, `router_log_settings`, `router_forensics` |
| Администрирование Windows | `router_windows_admin`, `router_storage`, `router_registry_viewer`, `router_system32_catalog`, `router_safe_ops`, `router_settings`, `router_sound`, `router_focus`, `router_ninite`, `router_diagnostics` |
| ИИ и знания | `router_chat`, `router_agents`, `router_interactive_agent`, `router_ai_instruments`, `router_procedural_tools`, `router_wikillm_editor`, `router_keys` |
| Интерфейс | `router_menu`, `router_panel`, `router_scenarios`, `router_control`, `router_tc`, `router_admin` |

Каждая вкладка WebGUI обращается к своему роутеру; соответствие описано в `webgui/tab_*/README.md` и интерактивной карте `tab_sitemap`.

> [!NOTE]
> Низкоуровневые ctypes-вызовы Win32 вынесены в [`apps.windows.sdk.win32_ffi`](../sdk/win32_ffi/README.md); API не обращается к DLL напрямую.

---

**Updated:** 2026-10-31 16:30:00
**Package:** `apps.windows.api`
**Author:** hypo69
