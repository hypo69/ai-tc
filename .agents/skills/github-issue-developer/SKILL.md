---
name: github-issue-developer
description: "Autonomous agent skill for end-to-end task execution from GitHub Issue specifications: requirements decomposition, git branching, TDD validation, and automated pull requests with auto-close linking."
description_i18n:
  en: "Autonomous agent skill for end-to-end task execution from GitHub Issue specifications: requirements decomposition, git branching, TDD validation, and automated pull requests with auto-close linking."
  ru: "Автономный навык сквозной разработки по спецификациям GitHub Issues: декомпозиция ТЗ, создание Git-веток, TDD-валидация и автоматическое создание Pull Request со связкой закрытия."
---

# Автономная разработка по GitHub Issue (GitHub Issue Developer)

## 🎯 Назначение (Purpose)
Навык реализует методологию **Issue-driven AI Development**. Он берет задачу (GitHub Issue), разбирает её на формализованные требования, подготавливает изолированную ветку Git, выполняет реализацию изменений в кодовой базе с прогоном тестов (TDD) и публикует Pull Request, автоматически закрывающий связанный Issue при слиянии.

## 🚀 Триггеры и применение (When to Use & Triggers)
- Запросы пользователя: «возьми в работу issue #125», «сделай ветку под задачу #125», «создай PR по задаче #125», «разработай фичу из тикета #125».
- Необходимость провести полный цикл разработки: `Issue -> Branch -> Code -> Test -> PR -> Close`.

## ⚙️ Протокол выполнения (Execution Protocol)
1. **Анализ ТЗ из Issue:**
   - Чтение структуры задачи: тип (`bug`/`feat`), компонент (`telemetry`, `windows`, etc.), шаги воспроизведения, критерии приемки.
2. **Создание рабочей ветки:**
   - Генерация имени: `fix/<number>-<slug>` (для багов) или `feat/<number>-<slug>` (для фич).
   - Выполнение `git checkout -B <branch_name>`.
3. **Разработка и TDD:**
   - Следование стандартам `GEMINI.md`: комментарии и docstrings на русском языке, обновление даты в шапке, лимит 500 строк.
   - Проверка существующего кода на переиспользование (`REUSE.md`).
4. **Валидация тестами:**
   - Запуск `pytest tests/` для проверки отсутствия регрессий.
5. **Публикация Pull Request:**
   - Формирование описания с директивой `Fixes #<number>` или `Closes #<number>`.
   - Вызов `gh pr create` и уведомление в комментариях Issue.

## 💻 Использование через консоль и CLI
```bash
# 1. Сформировать ТЗ и план работ по тикету
py .agents/skills/github-issue-developer/scripts/issue_to_pr_runner.py plan 125

# 2. Создать рабочую ветку под тикет
py .agents/skills/github-issue-developer/scripts/issue_to_pr_runner.py start-branch 125

# 3. После завершения написания кода — запустить тесты и открыть Pull Request
py .agents/skills/github-issue-developer/scripts/issue_to_pr_runner.py verify-and-pr 125 --summary "Устранено падение при отсутствии config.json"
```
