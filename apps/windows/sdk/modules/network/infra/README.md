# 🌐 Диагностика сетевой инфраструктуры Windows (`network/infra`)

**Статус:** ✅ Активен · **Язык:** Русский · **Автор:** hypo69 · **Обновлено:** 2026-10-28 16:30:00

Модуль встроен в существующее приложение ai-tc (вкладка `tab-network`, `http://127.0.0.1:8001/tc#tab-network`). Отдельного сервера и отдельной навигации нет. Режим — **только чтение**.

## Архитектура

```
UI (tab_network/panel_infra) → /api/network/infra/* (router.py) → NetworkInfraService (service.py)
  → сборщики (collectors_basic.py, collectors_virtual.py) → PowerShellRunner / wsl.exe (ps_runner.py)
  → нормализация (normalize.py, classification.py) → правила (diagnostics.py)
  → SQLite-история (store.py) и сравнение (compare.py)
```

| Файл | Назначение |
|---|---|
| `settings.py` | Настройки из секции `infra` в `../config.json` (тайм-ауты, кэш, retention, путь БД) |
| `models.py` | Статусы данных, `CollectorResult`, `Finding`, `NetworkChange`, `make_item` |
| `ps_runner.py` | Read-only раннер: allowlist глаголов (`Get/Select/Where/ForEach/ConvertTo/Sort/Test/Measure`), allowlist аргументов `wsl.exe`, тайм-аут, UTF-8/UTF-16, нормализация JSON |
| `collectors_basic.py` | `NetworkAdapterCollector`, `IpConfigurationCollector`, `RouteTableCollector` |
| `collectors_virtual.py` | `HyperVSwitchCollector`, `NatConfigurationCollector`, `WslNetworkCollector` |
| `classification.py` | Многопризнаковая классификация адаптеров (physical / hyperv_virtual / wsl / virtual_other) |
| `normalize.py` | Устойчивые ID (InterfaceGuid), связывание NAT↔коммутаторы↔интерфейсы |
| `diagnostics.py` | Правила NET001–NET011, NET090/091 |
| `store.py`, `compare.py` | Хранилище снимков и сравнение с учётом полноты сбора |
| `service.py` | Параллельный запуск, кэш, single-flight, сводка |
| `router.py` | REST API, подключается через `apps/windows/api/config.json` |

## Источники данных и требования

| Область | Источник | Примечание |
|---|---|---|
| Адаптеры | `Get-NetAdapter` | Windows 8+/модуль NetAdapter |
| IP / DNS / шлюзы / метрики | `Get-NetIPAddress`, `Get-DnsClientServerAddress`, `Get-NetIPConfiguration`, `Get-NetIPInterface` | Часть запросов опциональна → статус `partial` |
| Маршруты | `Get-NetRoute` | IPv4+IPv6 |
| Hyper-V | `Get-VMSwitch`, `Get-VMNetworkAdapter -ManagementOS`, `Get-VMNetworkAdapterVlan -ManagementOS` | Наличие командлета проверяется заранее; обычно нужны права *Hyper-V Administrators* |
| NAT | `Get-NetNat`, `Get-NetNatStaticMapping` | Только WinNAT. ICS/Default Switch и NAT WSL2 (HNS) могут не отображаться — пустой результат ≠ «NAT нет» |
| WSL | `wsl.exe --list --verbose / --status / --version`, `~/.wslconfig` | Если `wsl.exe` нет — остальные запросы не выполняются. Вывод локализован — состояния разбираются по маскам |

CIM/WMI на данном этапе не используется: покрытия командлетов достаточно (разрешён ТЗ как дополнительный источник).

## Статусы данных

`ok`, `partial`, `source_unavailable`, `not_installed`, `data_unavailable` (компонент есть, нужны права/нет сведений), `error`, `unknown`. Пустой список всегда сопровождается статусом: UI различает «объектов нет» (`ok`) и «данные не получены».

## API (`/api/network/infra`)

| Метод и путь | Назначение |
|---|---|
| `GET /summary` | Сводка («Обзор») |
| `GET /adapters`, `/ip-config`, `/routes?family=IPv4\|IPv6`, `/switches`, `/nat`, `/wsl` | Данные источников в конверте `{resource,status,source,collected_at,duration_ms,errors,notes,needs_elevation,items,extra,cached,shared}` |
| `GET /diagnostics` / `POST /diagnostics/run` | Результаты правил (кэш / новый сбор) |
| `POST /snapshots` | Создать снимок |
| `GET /snapshots?limit=` | Список снимков |
| `GET /snapshots/{id}` | Детали и исходные данные снимка |
| `GET /snapshots/compare?base=&target=` | Сравнение (`added`/`removed`/`changed`/`status_changed`) |
| `GET /history/findings?severity=&limit=` | История предупреждений |
| `POST /history/prune` | Очистка по политике хранения |

`refresh=true` форсирует новый сбор. Ошибки: `400` (параметры), `404` (снимок), `500` (внутренняя). Сбои источников данных — в теле ответа (`status`), а не HTTP-ошибкой. Кэш 30 с; параллельные запросы получают результат уже идущего сбора (`shared: true`).

## Модель данных и идентификация

Объект: `{id, kind, name, source, status, collected_at, props, raw}`. Стратегия `id`: адаптер — `InterfaceGuid` (иначе MAC, иначе имя); IP — `<id интерфейса>|<адрес>`; маршрут — `<префикс>|<next hop>|<id интерфейса>`; коммутатор — `Id` (иначе имя); NAT — имя; дистрибутив WSL — имя. `InterfaceIndex` как ключ не используется (нестабилен).

## Хранилище

SQLite `%APPDATA%/ai-tc/network_infra/network_infra.db`: `network_snapshots`, `network_snapshot_sources`, `network_snapshot_objects`, `network_snapshot_findings`. Изменения вычисляются при сравнении (отдельно не хранятся). Политика: `retention_max_snapshots` (200), `retention_days` (90); очистка при сохранении и по `POST /history/prune`.

Сравнение: `added/removed` для вида объектов вычисляются только если источник имел статус `ok` в **обоих** снимках; иначе вид попадает в `skipped`, а смена статуса источника фиксируется как `status_changed`.

## Диагностические правила

| Код | Суть | Важность |
|---|---|---|
| NET001 | Адаптер в неожиданном состоянии | warning |
| NET002 | Дубли IP (`Duplicate` — error; один IP на разных интерфейсах — warning) | error/warning |
| NET003 | Дубли маршрутов | warning |
| NET004 | Нет default-маршрута (только при полных данных) / несколько default (штатно) | warning/info |
| NET005 | Одинаковая минимальная метрика одного префикса на разных интерфейсах | warning |
| NET006 | Коммутатор ссылается на отсутствующий / неактивный адаптер | error/warning |
| NET007 | Неполная конфигурация (внешний коммутатор без адаптера, внутренний без vEthernet, NAT без интерфейса) | warning |
| NET008 | Несогласованные связи адаптеров и коммутаторов | warning/info |
| NET011 | WSL запущен, интерфейс Windows не найден | info |
| NET090 | Источник недоступен / компонент не установлен | warning/info |
| NET091 | Частичный сбор / ошибка | warning/error |

`critical` не используется: текущих данных недостаточно для подтверждения критичности. Правила не меняют настройки.

## Безопасность

Только `Get-*` и служебные конвейерные командлеты (проверка `assert_read_only` до запуска), `wsl.exe` — только `--status`, `--list --verbose`, `--version`. Пользовательский ввод в команды не подставляется. Тайм-ауты заданы настройками. Права повышаются **не** автоматически: при отказе в доступе статус `data_unavailable` и предупреждение в UI.

## Тесты

```powershell
py -m pytest tests/test_network_infra.py tests/test_network_infra_api.py -o addopts=""
```

Сборщики тестируются на подменяемых источниках (Hyper-V/WSL не нужны).

## Известные ограничения

- Режим сети WSL2 определяется только по явному `networkingMode` в `.wslconfig`; иначе `unknown`.
- `Get-NetNat` не показывает ICS/HNS-NAT.
- Без прав Hyper-V Administrators `Get-VMSwitch` может вернуть отказ — статус `data_unavailable`.
- Вывод `wsl.exe` локализован: неизвестная локализация фиксируется как ошибка с фрагментом вывода.

## Диагностика ошибок сбора

Смотрите поле `errors`/`notes` ответа и журнал приложения (записи `[NetworkInfra]`: сборщик, статус, число объектов, длительность). Типовые причины: нет модуля (`not_installed`/`source_unavailable`), нет прав (`needs_elevation`), тайм-аут (`source_unavailable`).
