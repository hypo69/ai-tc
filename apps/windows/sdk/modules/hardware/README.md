# 🖥️ Windows Hardware Monitor & Diagnostics
# =============================================================================
# Package: apps.windows.hardware
# Author: hypo69
# Copyright: © 2026 hypo69
# =============================================================================

Пакет низкоуровневой аппаратной диагностики, мониторинга оборудования в реальном времени и контролируемого стресс-тестирования для операционных систем Windows.

---

## 📌 Возможности

1. **Hardware Monitor (Мониторинг реального времени)**:
   - **CPU**: Загрузка ядер/потоков, текущие и предельные частоты, прерывания и переключения контекста.
   - **RAM & Swap**: Объем физической памяти, использование, резерв и файл подкачки.
   - **GPU Telemetry**: Поддержка видеокарт NVIDIA (`nvidia-smi`), AMD (`amd-smi`), Intel Arc (`xpu-smi`) и WMI fallback (температуры, память VRAM, энергопотребление, кулеры).
   - **Storage & SMART**: Скорости чтения/записи (IOPS / MB/s), свободное место томов, детальный статус накопителей через Windows Storage API и WMI.
   - **Датчики (Sensors)**: Температуры ACPI / материнской платы, обороты вентиляторов (RPM), напряжения через нативный WMI / CIM и системные счетчики.
   - **Сеть и Электропитание**: Пропускная способность сети (KB/s, MB/s), активные сокеты, состояние батареи и зарядного устройства.

2. **Аппаратный аудит (Hardware Audit)**:
   - Сбор спецификаций CPU, сокета, материнской платы и таймингов памяти через `CPU-Z`, `AIDA64` или WMI.

3. **Стресс-тестирование (SafeOps Stress Benchmark)**:
   - Контролируемый тест стабильности CPU и GPU с активным аварийным прерыванием при достижении критической температуры (`max_safe_temp_c`).

---

## 🚀 Быстрый старт в коде

```python
from apps.windows.hardware import HardwareMonitor

monitor = HardwareMonitor()

# Получение полного моментального снимка
snapshot = monitor.get_snapshot()
print(f"Загрузка CPU: {snapshot.cpu.utilization_pct}%")
print(f"Занято RAM: {snapshot.memory.used_gb} GB / {snapshot.memory.total_gb} GB")

# Оценка здоровья оборудования
summary = monitor.get_summary()
print(f"Статус системы: {summary['status']}")
```

---

## 🌐 API Эндпоинты

- `GET /api/windows/hardware/monitor` — Полный моментальный снимок всех компонентов оборудования.
- `GET /api/windows/hardware/monitor/summary` — Краткая сводка здоровья и превышения пороговых значений.
- `GET /api/windows/hardware/sensors` — Показания всех активных датчиков температуры, вентиляторов и напряжений.
- `GET /api/windows/hardware/gpu` — Детальная телеметрия графических процессоров.
- `GET /api/windows/hardware/smart` — S.M.A.R.T. здоровье дисков.
- `POST /api/windows/benchmark/stress` — Запуск контролируемого стресс-теста.

## 🧩 PawnIO (Tier 5 — опциональный Kernel Hardware Access)

**Полностью опционален:** если `PawnIOLib.dll` не найдена, провайдер молча недоступен (`NOT_FOUND`), остальная диагностика работает как раньше. Если установлен — `PawnIOProvider` (`providers/pawnio_provider.py`, клиент `pawnio_client.py`) сам определяет процессор, перебирая модули (`PawnIO.Modules`), и читает максимум датчиков; каждый регистр читается независимо — отклонённые драйвером пропускаются.

| Модуль | CPU | Датчики |
|---|---|---|
| `IntelMSR` | Intel | температура пакета, thermal/power-limit throttling, множитель×100 МГц, VID, лимит PL1, мощность пакета/ядер/графики/DRAM/платформы (RAPL) |
| `AMDFamily17` | AMD Zen (17h+) | Tctl/Tdie (SMN), мощность пакета |
| `AMDFamily10` | AMD K10–K15 | температура сокетов (MISCCTL) |
| `AMDFamily0F` | AMD K8 | температура сокетов (THERMTRIP) |

- Данные идут в существующие `SensorReading` / `SensorSnapshot`; инвентаризацию дают остальные провайдеры (без дублирования).
- `PawnIOLib.dll` ищется через `UtilityDiscovery` (ключ `pawnio`); модули `*.bin` — в `modules/` рядом с DLL.
- Безопасность: белый список read-ioctl (`read_msr`, `read_smn`, `read_miscctl`, `get_thermtrip`); запись, произвольный Pawn-код и unrestricted-сборка запрещены; SMN/PCI-доступ под мьютексом `Global\Access_PCI`.
- Имена ioctl и размеры сверены с исходниками `PawnIO.Modules`; формулы декодирования (Zen/K10/K8, ratio/VID Intel) взяты из публичных описаний и **не проверены на железе**.
- Не реализовано: `RyzenSMU` PM-table (раскладка зависит от версии), `ZhaoxinMSR`, SMBus/LPC/EC/GPU/PCH (отдельные модули, другая модель данных).
- Лицензия: PawnIO — GPL-2.0 с исключением для IOCTL, модули — LGPL-2.1+. Перед распространением бинарников проверьте совместимость.