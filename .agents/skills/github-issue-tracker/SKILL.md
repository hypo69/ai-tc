---
name: github-issue-tracker
description: "Comprehensive toolkit for managing GitHub Issues, Projects, Milestones, labels taxonomy, and task lifecycles in AI-TC."
description_i18n:
  en: "Comprehensive toolkit for managing GitHub Issues, Projects, Milestones, labels taxonomy, and task lifecycles in AI-TC."
  ru: "Инструментарий управления задачами GitHub Issues, досками проектов, вехами релизов, метками и жизненным циклом разработки в AI-TC."
---

# Управление задачами GitHub Issues & Projects (GitHub Issue Tracker)

## 🎯 Назначение (Purpose)
Навык предназначен для программного и CLI-управления задачами GitHub Issues, отслеживания прогресса по контрольным точкам (Milestones), ведения Kanban-досок GitHub Projects, классификации задач по стандартизированной сетке меток (тип, приоритет, компонент) и синхронизации шаблонов задач.

## 🚀 Триггеры и применение (When to Use & Triggers)
- Запросы пользователя: «покажи открытые issues», «создай задачу на исправление бага», «какой прогресс по релизу v0.5», «настрой метки в репозитории», «посмотри issue #125».
- Необходимость зарегистрировать ошибку, улучшение или запрос на новую функцию.
- Аудит бэклога и распределение задач по компонентам (`telemetry`, `windows`, `network`, `ai`, `mcp`, `gui`).

## ⚙️ Протокол выполнения (Execution Protocol)
1. **Проверка готовности окружения:**
   - Проверка наличия `gh` CLI и авторизации через `GitHubClient.is_ready()`.
2. **Анализ или выборка задач:**
   - Фильтрация по статусу (`open`/`closed`), меткам (`bug`, `feature`) или компонентам.
3. **Классификация задач:**
   - Назначение ровно трёх обязательных меток: 1 тип + 1 приоритет + 1 компонент.
4. **Контроль этапов (Milestones):**
   - Группировка задач по версиям релиза (`v0.5`, `v0.6`) и расчет процента закрытия (`closed / total * 100%`).
5. **Использование шаблонов:**
   - Использование стандартизированных Markdown-форм из `.github/ISSUE_TEMPLATE/`.

## 💻 Использование через Python API и CLI
```bash
# Список открытых задач по компоненту Windows
py .agents/skills/github-issue-tracker/scripts/manage_issues.py list --state open --label component:windows

# Просмотр детальной информации по задаче
py .agents/skills/github-issue-tracker/scripts/manage_issues.py view 125

# Создание новой задачи
py .agents/skills/github-issue-tracker/scripts/manage_issues.py create "Оптимизация опроса SMART" --type enhancement --priority medium --component windows

# Синхронизация стандартных меток AI-TC
py .agents/skills/github-issue-tracker/scripts/manage_issues.py sync-labels
```
