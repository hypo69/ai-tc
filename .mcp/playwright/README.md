# 🌐 Playwright MCP Orchestration (`playwright/`)

**Описание:** Легковесный TypeScript-сервер оркестрации для браузерной автоматизации Playwright MCP, выполнения атомарных pre-commit коммитов и контролируемого обновления файлов в рабочем пространстве.

**Статус:** ✅ Production Ready  
**Версия:** 1.0  
**Автор:** hypo69  
**Updated:** 2026-10-31 17:08:00

---

## 🏗️ Архитектура

Компонент расположен в `.mcp/playwright/` и компилируется из TypeScript (`src/index.ts`) в CommonJS (`dist/index.js`).
Основные задачи:
- Обеспечение безопасных REST-эндпоинтов `/health`, `/precommit` и `/apply`.
- Строгая защита от выхода за пределы корневой директории репозитория (`resolveSafePath`).
- Безопасный вызов `git` через `execFileSync` с передачей массива аргументов без интерполяции командной оболочки.

---

## 🚀 Использование

```powershell
cd .mcp/playwright
npm ci
npm run build
npm start
```

---

## 📂 Файлы

- `package.json` — Манифест пакета и скриптов сборки (`build`, `start`, `dev`)
- `tsconfig.json` — Конфигурация компилятора TypeScript
- `src/index.ts` — Исходный код сервера оркестрации Playwright MCP
- `README.md` — Документация модуля

---

## 🔗 Ссылки

- [`../README.md`](../README.md) — Документация родительского пакета `.mcp/`
- [`../../.github/workflows/playwright-mcp.yml`](../../.github/workflows/playwright-mcp.yml) — CI-пайплайн сборки Playwright MCP
