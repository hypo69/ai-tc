# Вкладка настройки звука (Sound Settings Tab)

## Назначение
Вкладка `tab_sound_settings` предоставляет графический веб-интерфейс для управления звуковой подсистемой Windows в рамках ai-tc (`tc.ps1`):
- Регулировка громкости системных звуков Windows (System Sounds) и Mute.
- Проверка звуковых сигналов Windows (Asterisk, Exclamation, Beep, Question).
- Переключение звука запуска Windows (Startup Boot Sound).
- Регулировка мастер-громкости аудиоустройства по умолчанию.
- Аудио-микшер запущенных процессов (Volume Mixer): громкость и глушение отдельных приложений.
- Быстрый запуск нативных системных утилит: `ms-settings:sound`, `sndvol.exe`, `mmsys.cpl`.

## Структура файлов
- `index.html` — разметка вкладки без скриптов, семантическая верстка на CSS-переменных темы.
- `main.js` — модуль управления, экспорт `window.initSoundSettingsTab()` и `window.deactivateSoundSettingsTab()`.

## API Эндпоинты
- `GET /api/v1/sound/state` — текущее состояние подсистемы звука.
- `POST /api/v1/sound/system-sounds-volume` — уровень громкости системных звуков (0-100%).
- `POST /api/v1/sound/system-sounds-mute` — переключение mute системных звуков.
- `POST /api/v1/sound/master-volume` — мастер-громкость (0-100%).
- `POST /api/v1/sound/master-mute` — master mute.
- `POST /api/v1/sound/session-volume` — громкость приложения.
- `POST /api/v1/sound/session-mute` — mute приложения.
- `POST /api/v1/sound/startup-sound` — звук при запуске Windows.
- `POST /api/v1/sound/test-sound` — воспроизведение тестового сигнала.
- `POST /api/v1/sound/launch-tool` — открытие апплетов звука Windows.
