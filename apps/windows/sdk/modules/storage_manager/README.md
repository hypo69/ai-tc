# 💾 Windows Storage Manager & Raw Block Cloner

Модуль управления физическими накопителями, посекторного клонирования (диск-в-диск), создания raw-образов и прямой низкоуровневой диагностики блочных устройств Windows (`\\.\PhysicalDriveX`) через WinAPI (`CreateFileW`, `ReadFile`, `WriteFile`, `DeviceIoControl`).

---

## 🚀 Возможности

1. **Прямой посекторный ввод-вывод (WinAPI Direct Block I/O)**:
   - Обход буферизации файловой системы (`FILE_FLAG_NO_BUFFERING`).
   - Чтение и запись произвольных LBA секторов физического диска.
   - Детальный HEX и ASCII дамп секторов (MBR, GPT, VBR, скрытые сектора).

2. **Посекторное клонирование (Raw & Smart Clone)**:
   - `raw` режим: абсолютная посекторная копия всего диска (ESP, MSR, Recovery, NTFS/ReFS, неразмеченная область).
   - `smart` режим: анализ таблицы разделов GPT/MBR и выборочное копирование только используемых разделов и критических секторов.

3. **Создание и восстановление raw-образов**:
   - `disk.image.create` — создание посекторного образа диска в файл (`.img`/`.raw`).
   - `disk.image.restore` — запись образа обратно на блочное устройство.

4. **Контроль целостности и хеширование**:
   - `disk.hash` — потоковый расчет SHA-256 хеша диапазона секторов.
   - `disk.verify` — посекторная верификация дисков или диска с образом.

5. **Безопасность SafeOps**:
   - Симуляция операций (`dry_run=True`) по умолчанию.
   - Защита системного диска (`PhysicalDrive0` / Windows Boot) от случайной перезаписи без флага `force_system_drive` и явного подтверждения.
   - Асинхронный мониторинг фоновых задач (прогресс, скорость МБ/с, ETA, отмена).

---

## 📡 REST API Эндпоинты (`/api/v1/storage`)

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/v1/storage/disks` | Список всех физических блочных дисков (`disk.list`) |
| `GET` | `/api/v1/storage/disks/{disk_id}` | Детальная геометрия, разметка MBR/GPT и SMART (`disk.info`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/read` | Прямое чтение секторов и HEX дамп (`disk.read`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/write` | Прямая запись секторов (`disk.write`) |
| `POST` | `/api/v1/storage/disks/{source}/clone` | Запуск клонирования диск-в-диск (`disk.clone`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/image` | Создание raw-образа диска (`disk.image.create`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/restore` | Восстановление диска из образа (`disk.image.restore`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/verify` | Посекторная верификация диска (`disk.verify`) |
| `POST` | `/api/v1/storage/disks/{disk_id}/hash` | Вычисление SHA-256 хеша секторов (`disk.hash`) |
| `GET` | `/api/v1/storage/tasks` | Список фоновых задач |
| `GET` | `/api/v1/storage/tasks/{task_id}` | Прогресс и статус задачи |
| `DELETE` | `/api/v1/storage/tasks/{task_id}` | Отмена выполняющейся задачи |
| `GET` | `/api/v1/storage/report` | Сводный отчет о накопителях и томах |
| `GET` | `/api/v1/storage/volumes` | Список логических томов |
| `GET` | `/api/v1/storage/fs/features` | Состояние TRIM, 8.3 имен, сжатия |

---

## 🖥️ Использование через CLI

```powershell
# Сводный TUI дашборд
py -m apps.windows.sdk.modules.storage_manager

# Список накопителей в формате JSON
py -m apps.windows.sdk.modules.storage_manager list --json

# Детальная инспекция геометрии и разделов PhysicalDrive0
py -m apps.windows.sdk.modules.storage_manager info 0

# Чтение и дамп LBA 0 (MBR)
py -m apps.windows.sdk.modules.storage_manager read 0 --lba 0 --count 1

# Симуляция клонирования PhysicalDrive1 в PhysicalDrive2 (Dry-Run)
py -m apps.windows.sdk.modules.storage_manager clone --source 1 --target 2 --mode raw --dry-run

# Создание raw-образа диска
py -m apps.windows.sdk.modules.storage_manager image --disk 1 --out D:\backup.img --dry-run

# Расчет SHA-256 хеша первых 2048 секторов диска 0
py -m apps.windows.sdk.modules.storage_manager hash 0 --lba 0 --count 2048

# Запуск выделенного REST API микросервиса
py -m apps.windows.sdk.modules.storage_manager server --port 8120
```


---

## Нативный сенсор накопителей (WindowsStorageSensor)

Диагностика NVMe/SATA/HDD/USB без внешних утилит (Smartmontools, AIDA64). Файл: [core/windows_storage_sensor.py](core/windows_storage_sensor.py).

### Источники данных
1. **WMI / CIM (`root/cimv2`)**:
   - `Win32_DiskDrive`: физические устройства, размеры, интерфейсы, базовый статус.
   - `Win32_DiskPartition` и `Win32_LogicalDisk`: разделы и логические диски.
   - `Win32_Volume`: файловые тома.
2. **Microsoft Storage Management (`root/Microsoft/Windows/Storage`)**:
   - `MSFT_PhysicalDisk`: тип шины (BusType: NVMe, SATA, SAS, USB), тип носителя (MediaType: SSD, HDD), серийные номера, статус здоровья (`HealthStatus`, `OperationalStatus`).
   - `MSFT_VirtualDisk`, `MSFT_StoragePool`, `MSFT_Partition`: дисковые пулы и виртуальные диски.
   - `StorageReliabilityCounter`: процент износа (Wear), температура дисков в °C, общее время наработки (PowerOnHours), счетчики ошибок чтения/записи (`ReadErrorsTotal`, `WriteErrorsTotal`), максимальные задержки (`ReadLatencyMax`, `WriteLatencyMax`).
3. **Счетчики производительности Windows (`PhysicalDisk`)**:
   - Скорости чтения/записи (Bytes/sec), длина очереди (`Current Disk Queue Length`), среднее время отклика (`Avg. Disk sec/Read`, `Avg. Disk sec/Write`).
4. **Журнал событий Windows (Event Log)**:
   - События драйверов Storport, файловых систем NTFS/ReFS и разбиения разделов.

### Использование в коде

```python
from apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor import WindowsStorageSensor

sensor = WindowsStorageSensor()
disks = sensor.get_physical_disks()

for disk in disks:
    print(f"Диск: {disk.friendly_name} ({disk.bus_type} {disk.media_type})")
    print(f"  Здоровье: {disk.health_status}, Износ: {disk.wear_percentage}%")
    print(f"  Температура: {disk.temperature_c}°C, Наработка: {disk.power_on_hours} ч.")
```

### CLI
```powershell
python -m apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor --output storage_snapshot.json
```
