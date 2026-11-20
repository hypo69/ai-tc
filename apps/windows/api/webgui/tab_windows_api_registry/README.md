# 🪟 Вкладка WebGUI: Windows API Registry & Smart Platform Dispatcher

Интерактивный веб-интерфейс единого реестра системных интерфейсов Windows (Win32, WinRT, COM, WMI/CIM, ETW, DirectX, WFP) и умного AI-диспетчера.

---

## 📋 Функциональные возможности

1. **Обзор 6 подсистем Platform Layer**:
   - Hardware & Devices, System Diagnostics, Network Intelligence, Graphics & Vision, Security Intelligence, Storage Intelligence.
   - Фильтрация по подсистеме, семейству API (Win32, WinRT, COM, ETW, etc.), наличию нулевых зависимостей (`ctypes`) и текстовый поиск.
   - Модальное окно полной спецификации API со сниппетами на Python и PowerShell.

2. **Smart AI Диспетчер (Resolver)**:
   - Анализ текстовой формулировки задачи пользователя или системного сценария.
   - Автоматический подбор оптимального интерфейса с объяснением выбора и готовым к запуску сниппетом Python.
   - Пресеты частых задач Windows-администрирования.

3. **Python Bindings & Нативные зонды**:
   - Аудит доступности библиотек в окружении (`ctypes`, `pywin32`, `winsdk`, `psutil`, `comtypes`, `wmi`).
   - Кнопки запуска безопасных нативных зондов в реальном времени.

4. **Настройки платформенного слоя**:
   - Приоритет Zero-Dependency, глубина рекомендаций, сокрытие устаревших API.
