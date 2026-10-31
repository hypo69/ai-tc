# Слой драйверов (`apps.windows.sdk.drivers`)

[Слой 2] SDK: определение GPU и работа с каталогами драйверов.

| Класс | Назначение |
|---|---|
| `GpuHardwareDetector` | Определение GPU/вендора, нормализация версии драйвера (`format_driver_version`) |
| `NvidiaCatalogManager` / `AmdCatalogManager` | Каталоги релизов драйверов NVIDIA и AMD |
| `DriverDownloader` | Загрузка пакетов драйверов |
| `VendorType`, `DriverBranch`, `DriverRelease` | Типы вендора, ветки и релизы |

Доступ через фасад: `windows_sdk.drivers`. Ошибки: `DriverSubsystemError` и наследники (`DriverNotFoundError`, `HardwareProbeError`, `DriverDownloadError`).

**Updated:** 2026-10-31 16:40:00