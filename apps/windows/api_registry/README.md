# 🪟 AI-TC Windows API Registry & Smart Platform Dispatcher

Единый архитектурный реестр и интеллектуальный диспетчер системных интерфейсов Windows: **WinRT**, **Win32**, **COM**, **WMI/CIM**, **ETW**, **DirectX**, **WFP** и **Windows App SDK**.

---

## 🎯 Назначение

В Windows существует огромное количество нативных API-пакетов, которые превосходят обычные Python-библиотеки с точки зрения полноты системной диагностики, надежности и производительности.

Подсистема решает ключевые задачи:
1. **Единый каталог системных возможностей (SSOT)**: классификация по 6 платформенным подсистемам с сигнатурами функций, версиями Windows, требуемыми привилегиями и Python-привязками.
2. **Приоритет Zero-Dependency**: выявление возможностей, доступных напрямую через встроенный `ctypes` без необходимости установки сторонних pip-пакетов.
3. **Умный диспетчер (Smart API Resolver)**: подбор оптимального системного интерфейса под конкретную задачу пользователя или AI-агента с генерацией готового исполняемого кода на Python и PowerShell.
4. **Безопасные диагностические зонды**: прямое тестирование доступности DLL и функций в текущей среде.

---

## 🏗️ Шесть ключевых подсистем Platform Layer

```text
AI-TC — Windows Platform Layer
├── 1. Hardware & Devices       (CPU, GPU, RAM, PCI, USB, PnP, Sensors)
│   └── SetupAPI · CfgMgr32 · WMI · Windows.Devices · Windows.Devices.Sensors
├── 2. System Diagnostics      (Processes, Services, Events, ETW, Performance)
│   └── Kernel32 · Advapi32 · Psapi · Wevtapi · Windows.System.Diagnostics
├── 3. Network Intelligence    (Adapters, TCP/IP, DNS, Routing, Firewall, VPN)
│   └── Iphlpapi · WFP (Filtering Platform) · Windows.Networking · NetFwPolicy2
├── 4. Graphics & Vision       (Screen Capture, Imaging, OCR, GPU, DirectX)
│   └── Windows.Graphics.Capture · Direct3D 11 · DXGI · Windows.Media.Ocr
├── 5. Security Intelligence   (Tokens, ACL, UAC, Audit, Defender, Credentials)
│   └── Advapi32 · Windows.Security · DPAPI · Windows Hello
└── 6. Storage Intelligence    (Disks, Volumes, SMART, VSS, Search AQS)
    └── Storage API · DeviceIoControl · VSS COM · Windows.Storage.Search
```

---

## 🚀 Пример использования API Диспетчера в Python

```python
from apps.windows.api_registry import get_api_registry_service, ApiRecommendationQuery

service = get_api_registry_service()

# 1. Поиск интерфейса под задачу
query = ApiRecommendationQuery(
    task_description="получить список сетевых адаптеров и их IP",
    prefer_zero_dependency=True
)
result = service.recommend(query)

print("Рекомендованный API:", result.recommended_api.name)
print("Библиотека:", result.recommended_api.binary_or_namespace)
print("Обоснование:", result.rationale)
print("Python код:\n", result.python_snippet)
```
