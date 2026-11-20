---
name: system-updater
description: "Update checker, backup creator, and safe tag-based updater/rollback tool for ai-tc."
description_i18n:
  en: Update checker, backup creator, and safe tag-based updater/rollback tool for ai-tc.
  ru: Проверка новых SemVer-тегов, создание резервных копий, безопасное обновление и откат ai-tc по релизным тегам Git.
updated: 2026-11-20 21:12:00
---

# 🔄 System Updater Skill (Tag-Based Strategy)

Навык для проверки релизных тегов (SemVer 2.0), создания резервных копий, безопасного переключения релизной ветки `release` на целевой Git-тег и мгновенного отката в `ai-tc`.

> [!IMPORTANT]
> **Стратегия обновлений**: Обновление клиентских установок выполняется **строго по релизным Git-тегам** (`vX.Y.Z`), а не через `git merge` ветки разработки `master`. Подробный регламент: [`.ai/instructions/standards/RELEASE_AND_UPDATES.md`](../../../.ai/instructions/standards/RELEASE_AND_UPDATES.md).

---

## 🎯 Назначение и триггеры

Используйте этот навык, когда:
- Пользователь просит проверить обновления или обновиться до последнего стабильного релиза.
- Требуется переключиться на конкретную версию (`v1.1.0`) или выполнить откат (`rollback`) на предыдущий релиз.
- Требуется выпустить новый релизный тег (`release create`).

---

## 🚀 Протокол выполнения

### Шаг 1 — Проверка доступных тегов и статуса
```powershell
py manage_tools.py update check
py manage_tools.py update list
```
Для проверки пререлизов (`-rc`, `-beta`):
```powershell
py manage_tools.py update check --prerelease
```

### Шаг 2 — Безопасное обновление до последнего (или указанного) тега
```powershell
# Обновление до последнего стабильного тега
py manage_tools.py update apply

# Обновление до конкретного тега
py manage_tools.py update apply --tag v1.1.0
```
Процесс автоматически выполняет:
1. Проверку чистоты рабочего дерева (`git status --porcelain`).
2. Создание резервной копии конфигов (`config.json`, `.env`, `requirements.txt`, `pyproject.toml`) и фиксацию текущего состояния Git.
3. `git fetch origin --tags --force` и атомарное переключение ветки `release` на `refs/tags/<target_tag>`.
4. Автоматическую доустановку зависимостей (`pip install -r requirements.txt`), если файл изменился.
5. Запуск миграций БД (если доступен `MigrationManager`).
6. Автоматический откат при ошибке на любом шаге.

### Шаг 3 — Откат (Rollback)
```powershell
# Откат на состояние из последнего бэкапа
py manage_tools.py update rollback

# Откат на конкретный релизный тег
py manage_tools.py update rollback --tag v1.0.0
```

### Шаг 4 — Выпуск нового релиза (для разработчиков)
```powershell
# Автоинкремент patch/minor/major + обновление pyproject.toml + аннотированный тег + push
py manage_tools.py release create --bump patch --push

# Явный выпуск тега v1.0.0
py manage_tools.py release create --tag v1.0.0 --push
```
