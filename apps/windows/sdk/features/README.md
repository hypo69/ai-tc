# Windows Optional Features (`apps.windows.sdk.features`)

[Слой 3] SDK. [`manager.py`](manager.py) управляет компонентами Windows через PowerShell/DISM.

- `get_features()` — список компонентов и их состояние;
- `enable_feature(name, all_dependencies=True)` — включение с зависимостями;
- `disable_feature(name)` — отключение.

Доступ: `windows_sdk.features`. Ошибки: `WindowsFeatureError`, `FeatureNotFoundError`, `FeatureInstallationError`.

**Updated:** 2026-10-31 16:40:00