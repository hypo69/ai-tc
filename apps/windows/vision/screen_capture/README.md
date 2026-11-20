# 📸 Подсистема Windows.Graphics.Capture & Screen Capture Engine

Инженерный компонент захвата экранов, рабочих столов и окон приложений Windows с поддержкой аппаратного ускорения, дифференциального анализа (`Screen Diff`) и корреляции с системной ETW-телеметрией.

---

## 🎯 Назначение

Подсистема реализует конспект интеграции графического API Windows в AI-TC:
1. **Windows.Graphics.Capture**: захват дисплеев и окон через графическую подсистему Windows (Direct3D 11 / DXGI FramePool).
2. **Win32 GDI & PrintWindow**: универсальный и стабильный нативный fallback-механизм захвата с поддержкой `PW_RENDERFULLCONTENT`.
3. **Screen Diff Engine**: вычисление динамики изменений между последовательными кадрами (`diff_ratio`, зоны активности, bounding boxes).
4. **Visual Intelligence Engine**: сопоставление визуального состояния с метриками CPU, RAM, диска, а также детекция зависания приложений (`IsHungAppWindow` в связке с нулевым screen diff при высокой нагрузке).
5. **Streaming Service**: фоновый потоковый захват с контролем частоты кадров (FPS) и формированием истории состояний.

---

## 🏗️ Архитектура

```text
apps/windows/vision/screen_capture/
├── models.py                     # Модели данных (DisplayInfo, WindowInfo, CapturedFrame, Config)
├── screen_diff.py                # Движок сравнения кадров (Screen Diff)
├── visual_intelligence.py        # Корреляция снимков с ETW/телеметрией и детекция зависаний
├── engine.py                     # Главный фасад ScreenCaptureEngine
├── backends/
│   ├── base.py                   # Базовый интерфейс BaseCaptureBackend
│   ├── gdi_backend.py            # Win32 GDI / BitBlt / PrintWindow бэкенд
│   └── wgc_backend.py            # Бэкенд Windows.Graphics.Capture / DirectX
└── README.md                     # Документация модуля
```

---

## 🚀 Примеры использования в Python

```python
from apps.windows.vision.screen_capture import ScreenCaptureEngine, CaptureEngineConfig

# 1. Инициализация движка
engine = ScreenCaptureEngine()

# 2. Получение списка мониторов и окон
displays = engine.list_displays()
windows = engine.list_windows()

# 3. Моментальный снимок основного экрана
frame = engine.capture_display(display_id=0)
print(f"Кадр {frame.frame_id}: {frame.width}x{frame.height}, diff={frame.diff_ratio}")

# 4. Захват конкретного окна по HWND
if windows:
    win_frame = engine.capture_window(window_id=windows[0].id)

# 5. Запуск потокового захвата
engine.start_stream(target=0)  # захват экрана 0
latest = engine.get_latest_frame()
status = engine.get_stream_status()
engine.stop_stream()
```

---

## ⚙️ Параметры конфигурации

- `backend`: выбор бэкенда (`auto`, `wgc`, `gdi`).
- `fps_limit`: частота захвата при стриминге (1..60 FPS).
- `image_format`: формат кодирования кадров (`jpeg`, `png`).
- `image_quality`: качество компрессии JPEG (10..100).
- `diff_threshold`: порог значимого визуального изменения (по умолчанию 0.02 = 2%).
- `enable_etw_correlation`: включение сопоставления снимков с показателями телеметрии.
- `history_buffer_size`: глубина кольцевого буфера истории состояний.
