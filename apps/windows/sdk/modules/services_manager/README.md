# ⚙️ Windows Services Control Center

Модуль управления, каталогизации и анализа связей системных служб Windows (SCM, Registry, Process, Network, Event Log через `WevtAPI` и история телеметрии AI-TC).

---

## 🚀 Возможности
- Инвентаризация всех служб Windows, статусов (`RUNNING`, `STOPPED`, `PAUSED`), типов запуска и учетных записей
- Автоматический разбор инфраструктуры `svchost.exe` (`-k <Group>`, `HKLM\...\Svchost`, `Parameters\ServiceDll`) и динамических per-user экземпляров (`OneSyncSvc_XXXX` → шаблон `OneSyncSvc`)
- Глобальный граф связей для всех служб: прямые зависимости (`DependOnService`), обратные зависимые (`dependents`), соседи по общему PID и группе `svchost`, быстрые метрики процесса (RAM, потоки, дескрипторы) и сети
- Глубокое досье по запросу (`ServiceDossier`): цепочка `Service → Template → svchost.exe → Group → DLL → Network → Event Log → Telemetry`
- Запуск, остановка и смена типа автозапуска служб с валидацией SafeOps и фиксацией в SQLite (`DeltaInventory`)

---

## 📡 REST API Эндпоинты (`/api/services-manager`)
- `GET /api/services-manager/summary` (алиас `/report`) — сводный отчет и обогащённый каталог служб из SQLite
- `POST /api/services-manager/scan` (алиас `/refresh`) — принудительный опрос SCM + Registry + Process + Net и сохранение в SQLite
- `GET /api/services-manager/list` — список всех служб (с фильтром `?status=RUNNING`)
- `GET /api/services-manager/graph` — глобальный граф связей (группы `svchost`, кластеры общих PID, per-user экземпляры)
- `GET /api/services-manager/dossier/{service_name}` — глубокое досье и граф связей конкретной службы (поддерживает поиск по базовому шаблону, например `OneSyncSvc`)
- `POST /api/services-manager/action` (алиас `/actions`) — запуск, остановка или изменение типа автозапуска

---

## 🖥️ Использование через CLI
```powershell
# Запуск TUI дашборда
py -m apps.windows.sdk.modules.services_manager

# Запуск REST сервера
py -m apps.windows.sdk.modules.services_manager --mode server --port 8123
```
