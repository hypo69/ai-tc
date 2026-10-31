# Конфигурация подсистемы телеметрии Windows (`config.json`)

Файл `config.json` (по умолчанию располагающийся в `%ProgramData%/AI-Windows-Admin/apps/windows/telemetry/config.json` для всей системы) является центральным конфигурационным файлом для системы сбора, буферизации, аудита и мониторинга телеметрии Windows в проекте AI-Windows-Admin.

Управление загрузкой, валидацией и модификацией параметров осуществляется модулем [`telemetry_config.py`](file:///c:/Users/onela/AppData/Local/ai-tc/apps/windows/telemetry/telemetry_config.py) (класс `TelemetryConfigManager`).

---

## 📑 Содержание

1. [Основные параметры, хранилище и буферизация](#1-основные-параметры-хранилище-и-буферизация)
2. [Режимы сбора и интервалы](#2-режимы-сбора-и-интервалы)
3. [Управление процессами](#3-управление-процессами)
4. [Тяжелые коллекторы и автопереключение](#4-тяжелые-коллекторы-и-автопереключение)
5. [Логгеры приложений (`loggers`)](#5-логгеры-приложений-loggers)
6. [Конфигурация сенсоров (`sensors`)](#6-конфигурация-сенсоров-sensors)
7. [Опции телеметрии (`telemetry_options`)](#7-опции-телеметрии-telemetry_options)
8. [Низкоуровневый сборщик Windows (`w64_collector`)](#8-низкоуровневый-сборщик-windows-w64_collector)

---

## 1. Основные параметры, хранилище и буферизация

Параметры хранилища и буферизации определяют пути к данным общесистемной телеметрии (`%ProgramData%`) и предотвращают избыточную нагрузку на SQLite базу данных путем пакетного сброса данных, а также обеспечивают сохранность телеметрии при нестабильной работе ПК.

| Параметр | Тип | Значение по умолчанию | Описание |
|---|---|---|---|
| `storage.data_path` | `string` | `"%ProgramData%/AI-Windows-Admin/apps/windows/telemetry/logs"` | Путь к каталогу хранения файлов и логов общесистемной телеметрии. |
| `storage.db_path` | `string` | `"%ProgramData%/AI-Windows-Admin/apps/windows/telemetry/logs/telemetry.db"` | Путь к основной базе данных SQLite телеметрии. |
| `mode` | `string` | `"hybrid"` | Общий режим работы: `"minimal"`, `"hybrid"`, `"full"`. |
| `buffer_mode` | `string` | `"memory"` | Режим накопления данных: `"memory"`, `"file"`, `"direct"`. |
| `buffer_size` | `integer` | `50` | Максимальное количество записей в буфере перед автоматическим сбросом в БД. |
| `flush_interval_seconds` | `float` | `30.0` | Интервал таймера автоматического сброса буфера в БД (в секундах). |
| `buffer_file` | `string` | `"telemetry_buffer.jsonl"` | Имя файла для сохранения буфера на диске в аварийном режиме сбоев. |
| `max_db_size_mb` | `float` | `50.0` | Предельный размер базы данных SQLite (включая WAL/SHM). При превышении запускается ступенчатая очистка. |
| `retention_days` | `integer` | `7` | Срок хранения сырых снимков и детальных событий телеметрии (в днях). |
| `db_cleanup_interval_seconds` | `float` | `300.0` | Периодичность автоматической проверки размера и очистки БД (в секундах). |
| `auto_vacuum_enabled` | `boolean` | `true` | Разрешение дефрагментации и сжатия SQLite (`VACUUM`) при усечении переполненной БД. |

### 💡 Режимы буферизации (`buffer_mode`):
- **`"memory"` (накопление в RAM)**: Все события, снимки и показания датчиков накапливаются в оперативной памяти. Сброс в SQLite выполняется пачкой (`executemany` в рамках одной WAL-транзакции) по таймеру или по достижении `buffer_size`.
- **`"file"` (аварийный/отказоустойчивый режим)**: При частых сбоях, перезагрузках или нестабильном питании ПК данные немедленно пишутся на диск в append-only JSONL файл с `os.fsync`. При заполнении буфера или по таймеру данные пачкой переносятся в SQLite, а файл очищается. При перезапуске системы остаточный JSON-буфер автоматически импортируется в БД.
- **`"direct"` (прямая запись)**: Буферизация отключена; каждая запись немедленно фиксируется в SQLite.

---

## 2. Режимы сбора и интервалы

> [!TIP]
> **Динамическая регулировка "на лету"**:
> Все сервисы телеметрии ([`service.py`](file:///c:/Users/onela/AppData/Local/ai-tc/apps/windows/telemetry/service.py), [`main.py`](file:///c:/Users/onela/AppData/Local/ai-tc/apps/windows/telemetry/main.py), [`TelemetryConfigManager`](file:///c:/Users/onela/AppData/Local/ai-tc/apps/windows/telemetry/telemetry_config.py)) отслеживают время изменения `config.json`. При сохранении файла новые интервалы и настройки подхватываются автоматически **без перезапуска сервиса**.
> 
> Поддерживаются как числовые значения в секундах (`5`, `6.0`), так и строковые интервалы (`"5 seconds"`, `"10s"`, `"1 minute"`, `"2 мин"`, `"1 hour"`, `"6 hours"`).

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `interval_seconds` | `float / string` | `6.0` | Базовый интервал опроса легковесных метрик (CPU, RAM, сеть, быстрые датчики). |
| `heavy_interval_seconds` | `float / string` | `90.0` | Интервал опроса тяжелых датчиков (WMI/CIM, SMART накопителей). |
| `fast_interval_seconds` | `float / string` | `30.0` | Интервал быстрого режима при детальной диагностике. |
| `fast_duration_days` | `integer` | `2` | Максимальная длительность быстрого режима (в днях). |
| `aggregation_interval_seconds` | `float / string` | `3600` | Интервал почасовой агрегации показаний сенсоров в БД (1 час). |
| `max_file_size_mb` | `float` | `50` | Максимальный размер лог-файлов до ротации (в МБ). |
| `enable_autolog` | `boolean` | `true` | Флаг автоматической фоновой записи метрик. |
| `default_interval` | `string` | `"1 minute"` | Интервал по умолчанию для логгеров приложений. |

---

## 3. Управление процессами

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `process_mode` | `string` | `"top_n"` | Режим сохранения процессов: `"top_n"` (только наиболее активные) или `"all"` (все процессы). |
| `top_processes` | `integer` | `10` | Количество сохраняемых процессов с наибольшей нагрузкой CPU/RAM. |
| `low_priority` | `boolean` | `true` | Автоматическое понижение приоритета фонового процесса сбора для исключения влияния на систему. |

---

## 4. Тяжелые коллекторы и автопереключение

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `heavy_disk_scan_interval_seconds` | `float` | `43200` | Интервал глубокого сканирования состояния накопителей (12 часов). |
| `heavy_mode_max_duration_days` | `float` | `5` | Предельная длительность непрерывной работы тяжелого режима. |
| `heavy_mode_auto_switch_enabled` | `boolean` | `true` | Автоматический возврат в гибридный/легкий режим по истечении лимита времени. |
| `heavy_collectors.hardware_sensors` | `boolean` | `true` | Опрос аппаратных датчиков напряжений, вентиляторов и температур. |
| `heavy_collectors.storage_smart` | `boolean` | `true` | Опрос SMART-атрибутов и степени износа накопителей. |
| `heavy_collectors.network_ping` | `boolean` | `true` | Проверка задержки и доступности интернет-хостов. |
| `heavy_collectors.inventory_wmi` | `boolean` | `true` | Полный сбор оборудования через WMI. |

---

## 5. Логгеры приложений (`loggers`)

Необязательная секция. Словарь `имя_логгера → {параметры}` читается `TelemetryConfigManager` (`telemetry_config.py`) как есть, без предопределённого списка имён: набор логгеров, их интервалы и флаг активности задаются пользователем (через `config.json` или API `router_telemetry_config`). В поставляемом `config.json` секции `loggers` нет.

## 6. Конфигурация сенсоров (`sensors`)

Каждый блок определяет активность (`enabled`), интервал опроса (`interval_seconds`) и собираемые метрики (`metrics`):

| Сенсор | Интервал | Метрики |
|---|---|---|
| `cpu` | `5.0 с` | `temperature`, `load`, `clocks` |
| `gpu` | `10.0 с` | `temperature`, `load`, `memory`, `power` |
| `ram` | `10.0 с` | `usage`, `swap` |
| `disk` | `30.0 с` | `usage`, `io` |
| `network` | `10.0 с` | `throughput`, `connections` |
| `sensors` | `10.0 с` | `temperature`, `fan`, `voltage` |
| `internet` | `120.0 с` | `ping`, `download`, `upload`, `dns` |
| `storage` | `32000.0 с` | `smart_attributes`, `temperature`, `wear_level` |
| `device_flapping` | `30.0 с` | `connect_events`, `disconnect_events`, `flapping_count` |

---

## 7. Опции телеметрии (`telemetry_options`)

| Параметр | Тип | Значение | Описание |
|---|---|---|---|
| `collect_serial_numbers` | `boolean` | `true` | Сбор серийных номеров оборудования (диски, материнская плата, BIOS). |
| `collect_hardware_inventory`| `boolean` | `true` | Полный аудит инвентаря устройств. |
| `collect_file_events` | `boolean` | `true` | Отслеживание файловых аномалий в наблюдаемых каталогах. |
| `max_file_size_mb` | `integer` | `50` | Лимит размера JSONL-файла журнала измерений. |
| `watch_directories` | `array` | `["C:\\Users\\"]` | Список директорий для отслеживания файловых изменений. |

---

## 8. Низкоуровневый сборщик Windows (`w64_collector`)

Интеграция с нативными подсистемами мониторинга Windows и трассировкой событий ETW (Event Tracing for Windows):

| Параметр | Тип | Описание |
|---|---|---|
| `enabled` | `boolean` | Общая активность модуля W64. |
| `enable_file_monitoring` | `boolean` | Мониторинг изменений в файловой системе через ReadDirectoryChangesW. |
| `enable_process_monitoring` | `boolean` | Отслеживание создания и завершения процессов (WMI/ETW). |
| `enable_registry_monitoring`| `boolean` | Перехват изменений реестра (RegNotifyChangeKeyValue). |
| `enable_network_monitoring` | `boolean` | Мониторинг сетевых соединений и открытых портов. |
| `enable_event_log_monitoring`| `boolean` | Чтение системных журналов Windows Event Log. |
| `enable_process_trace` | `boolean` | Низкоуровневая ETW-трассировка процессов. |
| `enable_disk_trace` | `boolean` | ETW-трассировка операций блочного ввода-вывода дисков. |
| `enable_network_trace` | `boolean` | ETW-трассировка сетевых пакетов TCP/IP. |
| `enable_registry_trace` | `boolean` | ETW-трассировка операций с ключами реестра. |


---

## 9. Многоскоростное ядро (`multi_rate_engine`)

Параметры [`TelemetryEngine`](telemetry_engine.py). Уровни: 3 — realtime, 2 — адаптивные сенсоры, 1 — низкочастотные.

| Параметр | По умолчанию | Описание |
|---|---|---|
| `enabled` | `true` | Включить многоскоростное ядро |
| `level3_realtime_interval_seconds` | `1.0` | Период realtime-тика |
| `level2_adaptive_initial_interval_seconds` / `_min_` / `_max_` | `2.0` / `0.5` / `30.0` | Начальный/минимальный/максимальный интервал адаптивных сенсоров |
| `level2_cooldown_ticks`, `level2_backoff_multiplier` | `10`, `1.5` | Число «спокойных» тиков и множитель замедления |
| `level1_smart_interval_seconds` | `43200` | Опрос SMART |
| `level1_battery_interval_seconds` | `900` | Опрос батареи |
| `level1_security_interval_seconds` | `3600` | Опрос журнала Security |
| `level1_scm_interval_seconds` | `1800` | Опрос служб и задач (SCM) |
| `level1_schedule_check_interval_seconds` | `60` | Проверка расписаний |
| `wal_flush_interval_seconds` | `5.0` | Период сброса буфера в SQLite |
| `ring_buffer_capacity`, `ring_buffer_max_mb` | `600`, `32` | Размер кольцевого буфера |
| `deadband.*` | см. файл | Пороги значимого изменения (`temperature_c`, `cpu_load_pct`, `freq_mhz`, `power_w`, `fan_rpm`, `network_bytes`, `network_packets`, `disk_space_gb`, `default_threshold`), `heartbeat_interval_seconds` (принудительная запись), `ignore_cumulative_network_spikes` |

## 10. TTL кэшей (`cache_ttls`)

Время жизни кэша (сек) для дорогих проб: `acpi_thermal_ttl_sec`, `storage_smart_ttl_sec`, `cloud_storage_ttl_sec`, `internet_speed_ttl_sec`, `network_adapter_stats_ttl_sec`, `physical_disks_health_ttl_sec`, `forensics_consent_store_ttl_sec`, `forensics_userassist_ttl_sec`, `gpu_probe_ttl_sec`, `disk_partitions_ttl_sec`.

## 11. Пороги (`thresholds`)

Используются детектором инцидентов и анализом утечек:

| Группа | Параметры |
|---|---|
| Инциденты | `incident_cpu_pct`, `incident_cpu_critical_pct`, `incident_disk_write_burst_mb_s`, `incident_net_burst_mb_s`, `incident_cooldown_seconds`, `incident_window_before_seconds` |
| Подозрительная температура | `suspicious_temp_cpu_pct`, `suspicious_temp_critical_cpu_pct`, `individual_process_high_cpu_pct` |
| Утечки | `leak_candidate_*`, `leak_warning_*`, `leak_critical_*`, `leak_severe_handles`, `leak_warning_gdi`, `leak_critical_gdi`, `leak_warning_user_objects`, `leak_high_page_faults`, `leak_high_memory_mb`, `leaks_scan_every_n_ticks` |
| DPC / прерывания | `dpc_elevated_pct`, `dpc_severe_pct`, `interrupt_elevated_pct`, `interrupt_severe_pct` |

## 12. Адаптивная частота (`sampling_controller`)

Читается [`SamplingController`](sampling_controller.py):

| Параметр | По умолчанию | Описание |
|---|---|---|
| `forensic_interval_sec` / `forensic_duration_sec` | `0.25` / `300` | Форензик-режим |
| `incident_interval_sec` / `incident_duration_sec` | `1.0` / `1200` | Режим после инцидента |
| `boot_phase{1,2,3}_max_uptime_sec` | `600` / `3600` / `86400` | Границы фаз после загрузки |
| `boot_phase{1,2,3}_interval_sec` | `1` / `5` / `30` | Интервалы по фазам |
| `monitoring_interval_sec`, `normal_interval_sec` | `30`, `60` | Штатные режимы |

## 13. Прочие интервалы

| Параметр | По умолчанию | Описание |
|---|---|---|
| `telemetry_mode` | `audit` | `audit` / `live_stream` / `both` / `tc` (см. раздел 2) |
| `light_poll_interval_seconds` / `heavy_poll_interval_seconds` | `6.0` / `90.0` | Лёгкий и тяжёлый опрос |
| `heavy_polls_intervals.*` | см. файл | Интервалы отдельных тяжёлых проб: `hardware_audit`, `startup_audit`, `extended_audit`, `defender_audit`, `process_activity_sync`, `software_audit`, `wmi`, `smart`, `handles`, `network_ports`, `network_activity`, `disk_scan` (`0` — отключено) |

---

**Updated:** 2026-10-31 16:25:00