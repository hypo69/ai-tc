# Подсистема Windows Runtime (WinRT) и Universal Windows Platform (UWP) для AI-TC

## 📋 Обзор архитектуры

Пакет `apps.windows.sdk.winrt` реализует современный адаптер системного уровня **WinRTProvider**, дополняющий классический Win32 API и WMI/CIM в архитектуре сбора телеметрии AI-TC.

```
       AI-TC | System Providers
       +----------+----------+
       |          |          |
     Win32      WinRT     WMI/CIM
       |          |          |
       +----------+----------+
             |
       Telemetry Bus
             |
       telemetry.db
             |
       Analysis Engine
```

## 🧩 Ключевые различия WinRT, UWP и Win32

| Характеристика | Win32 | WinRT | UWP |
|---|---|---|---|
| **Модель API** | Системные функции C (DLL экспорты) | Компонентная модель с метаданными (`.winmd`) | Модель жизненного цикла поверх WinRT |
| **Изоляция** | Зависит от процесса (Desktop) | Интеграция с AppContainer | Строгая изоляция в AppContainer |
| **Асинхронность** | Callback, сигналы, события потоков | Встроенная модель `IAsyncOperation<T>` / `IAsyncAction` | Встроенный жизненный цикл приложения |
| **Манифесты** | Ресурсы PE (manifest.xml) | Метаданные типов WinRT | Декларативный `Package.appxmanifest` |
| **Распространение**| EXE / MSI инсталляторы | DLL / COM Activation | MSIX / APPX / Microsoft Store |

## 🚀 Поддерживаемые пространства имён WinRT

1. **`Windows.System.Power`** (`subsystems/power.py`):
   - Статус аккумулятора (`BatteryStatus`: NotPresent, Discharging, Idle, Charging).
   - Режим экономии заряда (`EnergySaverStatus`).
   - Состояние сетевого питания (`PowerSupplyStatus`).
   - Расчётный остаток заряда в процентах (`RemainingChargePercent`).

2. **`Windows.Networking.Connectivity`** (`subsystems/network.py`):
   - Активный сетевой профиль (`ProfileName`).
   - Уровень связности с интернетом (`GetNetworkConnectivityLevel`).
   - Статус корпоративного домена (`GetDomainConnectivityLevel`).
   - Тип интерфейса (WLAN, WWAN, IANA interface type).
   - Уровень сигнала (`GetSignalBars`).

3. **`Windows.Media.Control` и `Windows.Media.Capture`** (`subsystems/media.py`):
   - Глобальный системный диспетчер медиасессий (`GlobalSystemMediaTransportControlsSessionManager`).
   - Идентификатор активного приложения (`SourceAppUserModelId`).
   - Состояние воспроизведения (`PlaybackStatus`: Playing, Paused, Stopped).
   - Возможности управления и аппаратного захвата медиапотока.

4. **`Windows.Graphics.Capture` и `Windows.Graphics.Imaging`** (`subsystems/graphics.py`):
   - Проверка аппаратно-ускоренного захвата экрана/окон без мерцания (`GraphicsCaptureSession.IsSupported()`).
   - Инвентарь зарегистрированных декодеров и энкодеров WIC/WinRT (HEIF, WebP, JPEG XL, PNG, DDS).

5. **`Windows.Devices.Enumeration`** (`subsystems/devices.py`):
   - Обнаружение и классификация устройств по `DeviceClass` (AudioRender, AudioCapture, VideoCapture).
   - Подсчёт подключённых камер, микрофонов и динамиков.

6. **`Windows.ApplicationModel`** (`subsystems/appmodel.py`):
   - Аудит UWP/MSIX приложений пользователя.
   - Детальный анализ системного приложения **«Связь с телефоном» (Phone Link / Microsoft.YourPhone)**.
   - Разбор декларированных прав доступа в `Package.appxmanifest` (телефонные вызовы, контакты, Bluetooth).

## 💻 Примеры использования

### Python API

```python
from apps.windows.sdk import windows_sdk
from apps.windows.sdk.winrt import WinRTProvider

# Через фасад WindowsSDK (Слой 6)
snapshot = windows_sdk.winrt.get_snapshot()
print(f"Статус батареи: {snapshot.power.battery_status}")
print(f"Сеть: {snapshot.network.profile_name} ({snapshot.network.connectivity_level})")
print(f"Медиасессия: {snapshot.media.source_app_user_model_id} - {snapshot.media.playback_status}")

# Прямой вызов системного провайдера
provider = WinRTProvider()
power = provider.power.get_power_telemetry_sync()
```

### CLI

```powershell
# Полная сводка всех WinRT подсистем
py -m apps.windows.cli --winrt

# Запрос конкретной подсистемы
py -m apps.windows.cli --winrt-subsystem power
py -m apps.windows.cli --winrt-subsystem network
py -m apps.windows.cli --winrt-subsystem media
py -m apps.windows.cli --winrt-subsystem graphics
py -m apps.windows.cli --winrt-subsystem devices
py -m apps.windows.cli --winrt-subsystem appmodel

# Вывод в формате JSON
py -m apps.windows.cli --winrt --json
```

### REST API

- `GET /api/windows/winrt/snapshot`
- `GET /api/windows/winrt/status`
- `GET /api/windows/winrt/power`
- `GET /api/windows/winrt/network`
- `GET /api/windows/winrt/media`
- `GET /api/windows/winrt/graphics`
- `GET /api/windows/winrt/devices`
- `GET /api/windows/winrt/appmodel`
