# Стратегия релизов и обновлений (Git Tags / SemVer 2.0)

**Updated:** 2026-11-20 22:08:00

## 1. Архитектурный принцип

Обновление рабочих установок `ai-tc` (включая локальные и портативные USB-инсталляции) выполняется **строго по релизным Git-тегам** (SemVer 2.0), а не путём слияния (`git merge`) ветки разработки `master`.

- Ветка `master` остаётся веткой активной разработки (допустимы промежуточные `checkpoint`-коммиты).
- Клиентские установки работают на выделенной локальной ветке **`release`**, которая атомарно переставляется на коммит целевого тега:
  `git checkout -B release refs/tags/vX.Y.Z`.
- Это полностью исключает конфликты слияния, предупреждения `detached HEAD` и случайное попадание незавершённого кода на рабочие машины.

---

## 2. Правила версионирования и каналы

Используется спецификация **SemVer 2.0** с обязательным префиксом `v`:

| Канал (`config.json -> updates.channel`) | Формат тега | Назначение |
|---|---|---|
| `stable` (по умолчанию) | `vMAJOR.MINOR.PATCH` (напр. `v1.0.0`, `v1.2.3`) | Проверенные релизы для всех установок |
| `prerelease` | `vMAJOR.MINOR.PATCH-<tag>` (напр. `v1.2.0-rc.1`, `v1.2.0-beta.2`) | Тестовые и предрелизные сборки |

Все релизные теги создаются **аннотированными** (`git tag -a vX.Y.Z -m "..."`) с перечнем изменений относительно предыдущего тега.

---

## 3. Конфигурация (`config.json`)

Все параметры стратегии вынесены в секцию `"updates"` файла `config.json` (хардкод запрещён):

```json
"updates": {
    "strategy": "tags",
    "remote": "origin",
    "channel": "stable",
    "release_branch": "release",
    "dev_branch": "master",
    "tag_prefix": "v",
    "auto_check_on_startup": true,
    "auto_apply_on_startup": true,
    "restart_after_update": true,
    "startup_timeout_sec": 8,
    "auto_install_deps": true,
    "keep_backups": 5,
    "backup_items": [
        "config.json",
        ".env",
        "requirements.txt",
        "pyproject.toml"
    ]
}
```

---

## 4. Алгоритм безопасного обновления (`VersionManager`)

Модуль реализации: [`src/version_manager.py`](../../../src/version_manager.py), утилиты SemVer: [`src/utils/versioning.py`](../../../src/utils/versioning.py).

1. **Pre-flight**: проверка чистоты рабочего дерева (`git status --porcelain --untracked-files=no`). При наличии незакоммиченных правок обновление блокируется (если не указан `--allow-dirty`).
2. **Загрузка тегов**: `git fetch origin --tags --force`.
3. **Выбор целевого тега**: явный `--tag vX.Y.Z` или лучший тег канала через `choose_best_tag()` и `compare_versions()`.
4. **Точка отката**: создание бэкапа `backup_items` и атомарная запись метаданных `.backup_info.json` (`previous_commit`, `previous_branch`, `previous_tag`).
5. **Переключение**: `git checkout -B release refs/tags/<target_tag>`.
6. **Пост-обновление**:
   - Проверка `git diff` по `requirements.txt`: если файл изменился и `auto_install_deps=true`, выполняется `pip install -r requirements.txt --quiet`.
   - Применение миграций БД (если в окружении подключён `MigrationManager`).
   - Ротация старых бэкапов (`keep_backups`) и запись JSON-лога обновления.
7. **Автоматический откат**: при ошибке на шагах 5–6 автоматически восстанавливаются прежнее состояние Git и файлы из бэкапа.

---

## 5. Команды CLI (`manage_tools.py`)

### Для пользователей и администраторов
```powershell
py manage_tools.py update check                  # Проверка наличия нового стабильного тега
py manage_tools.py update list                   # Список доступных релизных тегов
py manage_tools.py update apply                  # Обновление до последнего стабильного тега
py manage_tools.py update apply --tag v1.1.0     # Переход на конкретный тег
py manage_tools.py update rollback               # Откат на последний бэкап
py manage_tools.py update rollback --tag v1.0.0  # Откат на конкретный тег
```

### Для разработчиков (выпуск релиза)
```powershell
py manage_tools.py release list                          # Список локальных тегов
py manage_tools.py release create --tag v1.0.0 --push    # Первый релиз v1.0.0
py manage_tools.py release create --bump patch --push    # Инкремент patch (v1.0.0 -> v1.0.1)
py manage_tools.py release create --bump minor --push    # Инкремент minor (v1.0.1 -> v1.1.0)
py manage_tools.py release create --bump minor --prerelease rc.1 --push
```

При отправке тега `v*.*.*` в GitHub автоматически запускается workflow [`.github/workflows/release.yml`](../../../.github/workflows/release.yml), создающий GitHub Release с автогенерацией Release Notes.

---

## 6. Автообновление при старте приложения (`StartupUpdater`)

Модуль реализации: [`src/startup_updater.py`](../../../src/startup_updater.py). Подключён в самом начале `main.py` и `tc.py` до поднятия сервера и импорта модулей WebGUI/API:

1. При запуске проверяет наличие новых тегов с коротким таймаутом (`startup_timeout_sec: 8`).
2. Если доступен новый стабильный тег и рабочее дерево чистое — создаёт резервную копию, переключает ветку `release` на новый тег, при необходимости доустанавливает `requirements.txt` и выполняет миграции БД.
3. Автоматически перезапускает процесс с выставленным маркером окружения `AITC_SKIP_STARTUP_UPDATE=1` (защита от цикла перезапуска).
4. При отсутствии интернета, ошибке Git, отсутствии тегов или незакоммиченных изменениях — не прерывает запуск приложения.
5. Для разового отключения используется флаг `--no-update` (`.\tc.ps1 --no-update`, `py main.py --no-update`, `py tc.py --no-update`).

