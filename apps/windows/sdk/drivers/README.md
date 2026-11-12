# Слой драйверов (`apps.windows.sdk.drivers`)

**Updated:** 2026-11-01 14:40:00

[Слой 2] SDK: определение GPU, работа с каталогами драйверов, инвентаризация драйверов ядра и защита системы (Kernel & Protection).

| Класс / Компонент | Назначение |
|---|---|
| `DriverInventoryManager` | Инвентаризация системных драйверов Win32_SystemDriver, парсинг файловых минифильтров `fltmc` и высот Altitudes |
| `ProtectionMechanismsAuditor` | Аудит механизмов защиты: HVCI (Memory Integrity), Secure Boot, UCPD, Defender Tamper Protection, WDAC, Smart App Control, ELAM |
| `OperationBlockerDetector` | Интеллектуальный анализатор причин отказа в доступе (Access Denied / Blocker Detection) с дифференциацией UCPD, Tamper Protection, ACL, UAC, GPO |
| `KernelSafeOpsManager` | Безопасное управление параметрами драйверов с оценкой рисков и созданием точек отката (Rollback) |
| `GpuHardwareDetector` | Определение GPU/вендора, нормализация версии драйвера (`format_driver_version`) |
| `NvidiaCatalogManager` / `AmdCatalogManager` | Каталоги релизов драйверов NVIDIA и AMD |
| `DriverDownloader` | Загрузка пакетов драйверов |
