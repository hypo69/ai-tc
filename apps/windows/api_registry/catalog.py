# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Core Catalog
# =============================================================================
# Description:
#   Справочный реестр Windows API (Win32 DLL, WinRT namespaces, WMI/CIM, COM, ETW)
#   для 6 подсистем платформы AI-TC с метаданными и сниппетами.
#
# Usage Examples:
#   from apps.windows.api_registry.catalog import get_all_api_entries, get_api_by_id
#
# File: catalog.py
# Project: ai-windows-admin
# Package: apps.windows.api_registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:54:00
# =============================================================================

from __future__ import annotations
"""Единый каталог системных API Windows (SSOT) для AI-TC."""

from typing import Dict, List, Optional
from apps.windows.api_registry.models import (
    ApiFamily,
    PlatformSubsystem,
    PrivilegeLevel,
    WindowsApiEntry,
)

_WINDOWS_API_CATALOG: List[WindowsApiEntry] = [
    # -------------------------------------------------------------------------
    # 1. Hardware & Devices
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="setupapi_devices",
        name="SetupAPI & CfgMgr32 (PnP Device Manager)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.HARDWARE_DEVICES,
        binary_or_namespace="SetupAPI.dll / CfgMgr32.dll",
        description="Обнаружение оборудования, перечисление PnP устройств, драйверов и аппаратных идентификаторов (Hardware IDs / Vendor ID).",
        functions=["SetupDiGetClassDevsW", "SetupDiEnumDeviceInfo", "SetupDiGetDeviceRegistryPropertyW", "CM_Get_DevNode_Status"],
        min_win_version="Windows 2000 / XP / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\nsetupapi = ctypes.windll.setupapi\nhdev = setupapi.SetupDiGetClassDevsW(None, 'USB', None, 0x12) # DIGCF_ALLCLASSES | DIGCF_PRESENT",
            "powershell": "Get-PnpDevice -PresentOnly | Select-Object FriendlyName, InstanceId, Status",
        },
        limitations="Требует аккуратного освобождения дескрипторов SetupDiDestroyDeviceInfoList.",
        alternatives=["WMI Win32_PnPEntity", "Windows.Devices.Enumeration"],
    ),
    WindowsApiEntry(
        id="winrt_devices_sensors",
        name="Windows.Devices.Sensors (Датчики движения и положения)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.HARDWARE_DEVICES,
        binary_or_namespace="Windows.Devices.Sensors",
        description="Потоковые данные с датчиков: акселерометр, гироскоп, компас, освещённость, датчик ориентации и присутствия.",
        functions=["Accelerometer.GetDefault()", "Gyrometer.GetDefault()", "LightSensor.GetDefault()", "HumanPresenceSensor"],
        min_win_version="Windows 10 (Build 10240+)",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "winrt"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.devices.sensors import Accelerometer\nsensor = Accelerometer.get_default()",
            "powershell": "[Windows.Devices.Sensors.Accelerometer, Windows.Devices.Sensors, ContentType=WindowsRuntime]::GetDefault()",
        },
        limitations="Датчики должны присутствовать на устройстве (планшеты, ноутбуки, сенсорные ПК).",
        alternatives=["Win32 Sensor API (ISensorManager COM)", "WMI Win32_CurrentProbe"],
    ),
    WindowsApiEntry(
        id="winrt_devices_bluetooth",
        name="Windows.Devices.Bluetooth (Bluetooth LE & Classic)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.HARDWARE_DEVICES,
        binary_or_namespace="Windows.Devices.Bluetooth",
        description="Сканирование эфира, сопряжение, опрос GATT-сервисов, чтение характеристик Bluetooth Low Energy и Classic.",
        functions=["BluetoothDevice.FromIdAsync", "BluetoothLEAdvertisementWatcher", "GattCharacteristic.ReadValueAsync"],
        min_win_version="Windows 10",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "bleak"],
        zero_dependency=False,
        code_examples={
            "python": "import asyncio\nfrom bleak import BleakScanner\ndevices = asyncio.run(BleakScanner.discover())",
            "powershell": "Get-Service bthserv | Select-Object Status",
        },
        limitations="Требует включенного радиомодуля Bluetooth и прав доступа к устройствам.",
        alternatives=["Win32 BluetoothFindFirstDevice (Bthprops.cpl)", "WMI Win32_PnPEntity"],
    ),

    # -------------------------------------------------------------------------
    # 2. System Diagnostics
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="kernel32_process_mem",
        name="Kernel32 & Psapi (Управление процессами и памятью)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.SYSTEM_DIAGNOSTICS,
        binary_or_namespace="Kernel32.dll / Psapi.dll",
        description="Создание моментальных снимков процессов, анализ потоков, дескрипторов, виртуальной памяти и загруженных модулей.",
        functions=["CreateToolhelp32Snapshot", "Process32FirstW", "Process32NextW", "EnumProcesses", "GetProcessMemoryInfo", "VirtualQueryEx"],
        min_win_version="Windows NT / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32", "psutil"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes, ctypes.wintypes\nk32 = ctypes.windll.kernel32\nsnap = k32.CreateToolhelp32Snapshot(0x00000002, 0) # TH32CS_SNAPPROCESS",
            "powershell": "Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10",
        },
        limitations="Для чтения чужой памяти (OpenProcess) системных процессов требуется SeDebugPrivilege или SYSTEM.",
        alternatives=["WMI Win32_Process", "NtQuerySystemInformation (ntdll.dll)"],
    ),
    WindowsApiEntry(
        id="advapi32_scm_services",
        name="Advapi32 Service Control Manager (Службы Windows SCM)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.SYSTEM_DIAGNOSTICS,
        binary_or_namespace="Advapi32.dll",
        description="Низкоуровневое управление системными службами Windows: запуск, остановка, изменение конфигурации запуска и опрос статусов.",
        functions=["OpenSCManagerW", "EnumServicesStatusExW", "OpenServiceW", "QueryServiceStatusEx", "StartServiceW", "ControlService"],
        min_win_version="Windows NT / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\nadv = ctypes.windll.advapi32\nhscm = adv.OpenSCManagerW(None, None, 0x0004) # SC_MANAGER_ENUMERATE_SERVICE",
            "powershell": "Get-Service | Where-Object Status -eq 'Running'",
        },
        limitations="Мутирующие операции (Start/Stop) требуют прав локального администратора.",
        alternatives=["WMI Win32_Service", "sc.exe CLI"],
    ),
    WindowsApiEntry(
        id="wevtapi_event_log",
        name="Wevtapi (Windows Event Log 2.0)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.SYSTEM_DIAGNOSTICS,
        binary_or_namespace="Wevtapi.dll",
        description="Чтение, фильтрация через структурированный XPath и подписка в реальном времени на события журналов Windows (Application, System, Security).",
        functions=["EvtQuery", "EvtNext", "EvtRender", "EvtSubscribe", "EvtOpenChannelEnum"],
        min_win_version="Windows Vista / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\nwevt = ctypes.windll.wevtapi\nh_query = wevt.EvtQuery(None, 'System', '*[System[(Level=1 or Level=2)]]', 1)",
            "powershell": "Get-WinEvent -FilterXPath \"*[System[(Level=1 or Level=2)]]\" -MaxEvents 20",
        },
        limitations="Чтение журнала Security требует прав SeSecurityPrivilege (Администратор).",
        alternatives=["WMI Win32_NTLogEvent", "ETW Real-Time Tracing"],
    ),
    WindowsApiEntry(
        id="etw_tracing_core",
        name="ETW (Event Tracing for Windows)",
        family=ApiFamily.ETW,
        subsystem=PlatformSubsystem.SYSTEM_DIAGNOSTICS,
        binary_or_namespace="ntdll.dll / advapi32.dll / tdh.dll",
        description="Ультра-высокопроизводительный механизм трассировки ядра Windows (диск, сеть, процессор, системные вызовы) с минимальным оверхедом < 1%.",
        functions=["StartTraceW", "EnableTraceEx2", "OpenTraceW", "ProcessTrace", "CloseTrace", "TdhGetEventInformation"],
        min_win_version="Windows 2000 / 10 / 11",
        privileges=PrivilegeLevel.ADMIN,
        python_bindings=["ctypes", "KrabsETW"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\n# Запуск сессии ядра ETW через advapi32\nadv = ctypes.windll.advapi32",
            "powershell": "logman create trace \"AI_TC_Trace\" -p \"Microsoft-Windows-Kernel-Process\" -o \"C:\\trace.etl\"",
        },
        limitations="Создание сессий трассировки ядра требует прав локального администратора.",
        alternatives=["Performance Counters (PDH)", "Windows Event Log"],
    ),
    WindowsApiEntry(
        id="winrt_system_diagnostics",
        name="Windows.System.Diagnostics (Диагностика UWP и процессов)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.SYSTEM_DIAGNOSTICS,
        binary_or_namespace="Windows.System.Diagnostics",
        description="Чтение CPU usage, виртуальной памяти, активности диска и сетевых портов для процессов и UWP-контейнеров.",
        functions=["ProcessDiagnosticInfo.GetForProcesses()", "SystemDiagnosticInfo.GetForCurrentSystem()"],
        min_win_version="Windows 10 (Build 14393+)",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "winrt"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.system.diagnostics import ProcessDiagnosticInfo\nprocs = ProcessDiagnosticInfo.get_for_processes()",
            "powershell": "[Windows.System.Diagnostics.ProcessDiagnosticInfo, Windows.System, ContentType=WindowsRuntime]::GetForProcesses()",
        },
        limitations="Некоторые расширенные счетчики доступны только для packaged приложений.",
        alternatives=["psutil", "Win32 Psapi.dll"],
    ),

    # -------------------------------------------------------------------------
    # 3. Network Intelligence
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="iphlpapi_network",
        name="Iphlpapi (IP Helper API)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.NETWORK_INTELLIGENCE,
        binary_or_namespace="Iphlpapi.dll",
        description="Низкоуровневая информация о сетевых адаптерах, IP-адресах, таблицах маршрутизации IPv4/IPv6, ARP/NDP кэше и активных TCP/UDP сокетах.",
        functions=["GetAdaptersAddresses", "GetExtendedTcpTable", "GetExtendedUdpTable", "GetIpForwardTable2", "GetBestRoute2"],
        min_win_version="Windows XP / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\niphlp = ctypes.windll.iphlpapi\n# GetAdaptersAddresses возвращает полные сведения об адаптерах без WMI",
            "powershell": "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, MacAddress, LinkSpeed",
        },
        limitations="Структуры IP_ADAPTER_ADDRESSES содержат связанные списки (linked lists) и требуют точного выравнивания ctypes.",
        alternatives=["WMI Win32_NetworkAdapterConfiguration", "Windows.Networking.Connectivity"],
    ),
    WindowsApiEntry(
        id="wfp_filtering_platform",
        name="Windows Filtering Platform (WFP & NetFwPolicy2)",
        family=ApiFamily.WFP,
        subsystem=PlatformSubsystem.NETWORK_INTELLIGENCE,
        binary_or_namespace="Fwpuclnt.dll / HNetCfg.FwPolicy2 COM",
        description="Перехват, глубокая инспекция и фильтрация сетевых пакетов на уровнях ALE (Application Layer Enforcement), брандмауэр Windows.",
        functions=["FwpmEngineOpen0", "FwpmFilterAdd0", "FwpmCalloutAdd0", "INetFwPolicy2.Rules"],
        min_win_version="Windows Vista / 10 / 11",
        privileges=PrivilegeLevel.ADMIN,
        python_bindings=["ctypes", "pywin32 (COM win32com.client)"],
        zero_dependency=True,
        code_examples={
            "python": "import win32com.client\nfw = win32com.client.Dispatch('HNetCfg.FwPolicy2')\nprint('Брандмауэр включен:', fw.FirewallEnabled(1))",
            "powershell": "Get-NetFirewallRule -Enabled True | Measure-Object",
        },
        limitations="Прямой вызов WFP требует прав администратора и создания сессии фильтрации.",
        alternatives=["PowerShell NetSecurity", "netsh advfirewall"],
    ),
    WindowsApiEntry(
        id="winrt_networking_connectivity",
        name="Windows.Networking.Connectivity (Сетевой статус и профили)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.NETWORK_INTELLIGENCE,
        binary_or_namespace="Windows.Networking.Connectivity",
        description="Определение типа подключения (Ethernet, Wi-Fi, Cellular), лимитных сетей (Metered Network), качества связи и расхода трафика.",
        functions=["NetworkInformation.GetInternetConnectionProfile()", "NetworkInformation.GetConnectionProfiles()"],
        min_win_version="Windows 8 / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "winrt"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.networking.connectivity import NetworkInformation\nprofile = NetworkInformation.get_internet_connection_profile()\nprint('Online:', profile is not None)",
            "powershell": "[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking, ContentType=WindowsRuntime]::GetInternetConnectionProfile()",
        },
        limitations="Ориентирован на диагностику статуса подключения и профилей, а не сырых сокетов.",
        alternatives=["Iphlpapi.dll", "WMI Win32_NetworkAdapter"],
    ),

    # -------------------------------------------------------------------------
    # 4. Graphics & Vision
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="winrt_graphics_capture",
        name="Windows.Graphics.Capture (Аппаратный захват экрана и окон)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.GRAPHICS_VISION,
        binary_or_namespace="Windows.Graphics.Capture",
        description="Захват рабочего стола и отдельных окон приложений на GPU через Direct3D 11 без копирования в системную память (Zero-Copy).",
        functions=["GraphicsCaptureItem", "Direct3D11CaptureFramePool", "GraphicsCaptureSession", "GraphicsCapturePicker"],
        min_win_version="Windows 10 (Build 17134+)",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "ctypes (D3D11 Interop)"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.graphics.capture import GraphicsCaptureSession\n# Аппаратный захват кадра без GDI",
            "powershell": "Add-Type -AssemblyName 'Windows.Graphics.Capture'",
        },
        limitations="Защищённый медиаконтент (DRM) отображается черным цветом.",
        alternatives=["DXGI Desktop Duplication", "Win32 GDI BitBlt / PrintWindow"],
    ),
    WindowsApiEntry(
        id="winrt_media_ocr",
        name="Windows.Media.Ocr (Встроенное оптическое распознавание текста)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.GRAPHICS_VISION,
        binary_or_namespace="Windows.Media.Ocr",
        description="Локальное распознавание текста на изображениях на базе встроенных OCR-моделей Windows без использования сторонних тяжелых библиотек.",
        functions=["OcrEngine.TryCreateFromLanguage()", "OcrEngine.RecognizeAsync()"],
        min_win_version="Windows 10",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "winrt"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.media.ocr import OcrEngine\nfrom winsdk.windows.globalization import Language\nengine = OcrEngine.try_create_from_language(Language('ru'))",
            "powershell": "[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]::AvailableRecognizerLanguages",
        },
        limitations="Требует установленного языкового пакета OCR в настройках системы.",
        alternatives=["Tesseract OCR", "EasyOCR"],
    ),
    WindowsApiEntry(
        id="dxgi_desktop_duplication",
        name="DXGI Desktop Duplication API",
        family=ApiFamily.DIRECTX,
        subsystem=PlatformSubsystem.GRAPHICS_VISION,
        binary_or_namespace="dxgi.dll / d3d11.dll",
        description="Аппаратный захват кадров рабочего стола с GPU с минимальной задержкой (< 5 мс) и получением dirty rects (областей изменений).",
        functions=["IDXGIOutput1::DuplicateOutput", "IDXGIOutputDuplication::AcquireNextFrame", "IDXGIOutputDuplication::ReleaseFrame"],
        min_win_version="Windows 8 / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "d3dshot"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\ndxgi = ctypes.windll.dxgi\n# Захват кадров монитора через IDXGIOutputDuplication",
            "powershell": "# Требует вызова через C#/C++ COM vtable",
        },
        limitations="Работает только для полных мониторов, не позволяет напрямую адресовать отдельное перекрытое окно.",
        alternatives=["Windows.Graphics.Capture", "Win32 BitBlt"],
    ),

    # -------------------------------------------------------------------------
    # 5. Security Intelligence
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="advapi32_security_tokens",
        name="Advapi32 Security & Tokens (Токены, привилегии и ACL)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.SECURITY_INTELLIGENCE,
        binary_or_namespace="Advapi32.dll",
        description="Аудит токенов безопасности процессов, групп доступа (SID), привилегий (SeDebugPrivilege), целостности (Integrity Level) и списков ACL.",
        functions=["OpenProcessToken", "GetTokenInformation", "LookupPrivilegeValueW", "AdjustTokenPrivileges", "GetSecurityInfo"],
        min_win_version="Windows NT / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\nadv = ctypes.windll.advapi32\nh_token = ctypes.c_void_p()\n# Чтение Integrity Level и проверка повышенных прав (IsUserAnAdmin)",
            "powershell": "whoami /priv ; whoami /groups",
        },
        limitations="Активация некоторых привилегий требует, чтобы они изначально присутствовали в токене учетной записи.",
        alternatives=["Windows.Security.Credentials", "WMI Win32_UserAccount"],
    ),
    WindowsApiEntry(
        id="winrt_security_credentials",
        name="Windows.Security.Credentials (Диспетчер учетных данных и биометрия)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.SECURITY_INTELLIGENCE,
        binary_or_namespace="Windows.Security.Credentials",
        description="Безопасное хранение паролей и токенов в Windows Credential Locker, проверка биометрии через Windows Hello.",
        functions=["PasswordVault", "KeyCredentialManager", "UserConsentVerifier.RequestVerificationAsync()"],
        min_win_version="Windows 8 / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "keyring"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.security.credentials import PasswordVault\nvault = PasswordVault()\ncreds = vault.retrieve_all()",
            "powershell": "cmdkey /list",
        },
        limitations="Доступ к защищенным ключам Windows Hello требует интерактивного присутствия пользователя.",
        alternatives=["Win32 CredReadW (Advapi32.dll)", "DPAPI (CryptProtectData)"],
    ),

    # -------------------------------------------------------------------------
    # 6. Storage Intelligence
    # -------------------------------------------------------------------------
    WindowsApiEntry(
        id="storage_device_iocontrol",
        name="DeviceIoControl & Storage API (SMART, диски и секторы)",
        family=ApiFamily.WIN32,
        subsystem=PlatformSubsystem.STORAGE_INTELLIGENCE,
        binary_or_namespace="Kernel32.dll",
        description="Низкоуровневый опрос физических накопителей, SMART-телеметрия, температура дисков, NVMe Health Log и геометрия томов.",
        functions=["CreateFileW (\\\\.\\PhysicalDrive0)", "DeviceIoControl", "IOCTL_STORAGE_QUERY_PROPERTY", "SMART_RCV_DRIVE_DATA"],
        min_win_version="Windows NT / 10 / 11",
        privileges=PrivilegeLevel.ADMIN,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import ctypes\nk32 = ctypes.windll.kernel32\nh_disk = k32.CreateFileW(r'\\\\.\\PhysicalDrive0', 0, 3, None, 3, 0, None)",
            "powershell": "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, OperationalStatus, HealthStatus",
        },
        limitations="Прямое открытие физического диска (PhysicalDriveX) требует запуска от имени Администратора.",
        alternatives=["WMI MSStorageDriver_ATAPISmartData", "Storage Management API CIM"],
    ),
    WindowsApiEntry(
        id="com_vss_shadow_copies",
        name="VSS (Volume Shadow Copy Service COM)",
        family=ApiFamily.COM,
        subsystem=PlatformSubsystem.STORAGE_INTELLIGENCE,
        binary_or_namespace="VssApi.dll / IVssBackupComponents COM",
        description="Создание консистентных теневых снимков томов в реальном времени, восстановление файлов и анализ точек восстановления.",
        functions=["CreateVssBackupComponents", "IVssBackupComponents::GatherWriterMetadata", "IVssBackupComponents::DoSnapshotSet"],
        min_win_version="Windows XP / Server / 10 / 11",
        privileges=PrivilegeLevel.ADMIN,
        python_bindings=["ctypes", "pywin32"],
        zero_dependency=True,
        code_examples={
            "python": "import subprocess\n# Опрос состояния провайдеров VSS\nres = subprocess.check_output(['vssadmin', 'list', 'shadows'], text=True)",
            "powershell": "Get-CimInstance -ClassName Win32_ShadowCopy | Select-Object ID, DeviceObject, InstallDate",
        },
        limitations="Требует прав администратора и запущенной службы VSS (Volume Shadow Copy).",
        alternatives=["vssadmin CLI", "WMI Win32_ShadowCopy"],
    ),
    WindowsApiEntry(
        id="winrt_storage_search",
        name="Windows.Storage.Search (Системный индексированный поиск AQS)",
        family=ApiFamily.WINRT,
        subsystem=PlatformSubsystem.STORAGE_INTELLIGENCE,
        binary_or_namespace="Windows.Storage.Search",
        description="Мгновенный поиск файлов по метаданным и содержимому с использованием Advanced Query Syntax (AQS) через системный поисковый индекс Windows.",
        functions=["StorageFolder.CreateFileQueryWithOptions()", "QueryOptions", "CommonFileQuery"],
        min_win_version="Windows 8 / 10 / 11",
        privileges=PrivilegeLevel.USER,
        python_bindings=["winsdk", "winrt"],
        zero_dependency=False,
        code_examples={
            "python": "from winsdk.windows.storage.search import QueryOptions, CommonFileQuery\n# Быстрый AQS поиск по индексу Windows Search",
            "powershell": "# Windows Search Index OLEDB Provider",
        },
        limitations="Каталоги должны входить в область индексации службы Windows Search.",
        alternatives=["Win32 FindFirstFileW", "Everything SDK"],
    ),
]


def get_all_api_entries() -> List[WindowsApiEntry]:
    """Возвращает полный список зарегистрированных API в каталоге."""
    return list(_WINDOWS_API_CATALOG)


def get_api_by_id(api_id: str) -> Optional[WindowsApiEntry]:
    """Возвращает карточку API по его системному идентификатору."""
    return next((entry for entry in _WINDOWS_API_CATALOG if entry.id == api_id), None)


def get_apis_by_subsystem(subsystem: PlatformSubsystem) -> List[WindowsApiEntry]:
    """Фильтрует список API по указанной подсистеме платформы."""
    return [entry for entry in _WINDOWS_API_CATALOG if entry.subsystem == subsystem]


def get_subsystems_summary() -> Dict[str, Dict[str, Any]]:
    """Возвращает сводную статистику по 6 ключевым подсистемам AI-TC."""
    subsystems_meta = {
        PlatformSubsystem.HARDWARE_DEVICES: {
            "title": "Hardware & Devices",
            "desc": "CPU, GPU, RAM, PCI, USB, PnP-драйверы и аппаратные сенсоры",
            "icon": "bi-cpu",
        },
        PlatformSubsystem.SYSTEM_DIAGNOSTICS: {
            "title": "System Diagnostics",
            "desc": "Процессы, службы Windows, журналы событий и трассировка ядра ETW",
            "icon": "bi-activity",
        },
        PlatformSubsystem.NETWORK_INTELLIGENCE: {
            "title": "Network Intelligence",
            "desc": "Адаптеры, IP-маршрутизация, таблицы портов, брандмауэр и WFP",
            "icon": "bi-globe",
        },
        PlatformSubsystem.GRAPHICS_VISION: {
            "title": "Graphics & Vision",
            "desc": "Захват экрана WGC, Direct3D 11, OCR распознавание и DXGI",
            "icon": "bi-display",
        },
        PlatformSubsystem.SECURITY_INTELLIGENCE: {
            "title": "Security Intelligence",
            "desc": "Токены безопасности, аудит, ACL, права доступа и Windows Defender",
            "icon": "bi-shield-lock",
        },
        PlatformSubsystem.STORAGE_INTELLIGENCE: {
            "title": "Storage Intelligence",
            "desc": "Физические диски, SMART, тома, теневые копии VSS и AQS-поиск",
            "icon": "bi-hdd-network",
        },
    }

    result: Dict[str, Dict[str, Any]] = {}
    for sub, meta in subsystems_meta.items():
        apis = get_apis_by_subsystem(sub)
        zero_dep_count = sum(1 for a in apis if a.zero_dependency)
        result[sub.value] = {
            "title": meta["title"],
            "description": meta["desc"],
            "icon": meta["icon"],
            "total_apis": len(apis),
            "zero_dependency_apis": zero_dep_count,
            "api_ids": [a.id for a in apis],
        }
    return result
