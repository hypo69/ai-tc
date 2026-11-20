# 🎨 Руководство по темам оформления, дизайн-токенам и стилизации WebGUI

Файлы стилей и логики:
- Таблица переменных дизайн-токенов: `apps/windows/api/webgui/css/variables.css`
- Дизайн-система компонентов v2.0: `apps/windows/api/webgui/css/themes.css`
- Базовые стили и геометрия: `apps/windows/api/webgui/css/base.css`
- Ядро шаблонизатора тем: `apps/windows/api/webgui/js/theme-engine.js`
- Фасадный модуль управления: `apps/windows/api/webgui/js/theme.js`
- Интерактивный редактор тем: `apps/windows/api/webgui/theme_editor_tab/`

---

## 🏗️ 1. Архитектура дизайн-токенов

Веб-интерфейс ai-tc поддерживает мульти-темизацию (светлые, тёмные, системную и высококонтрастные темы оформления) на основе CSS-переменных и адаптивных классов Bootstrap 5.

### Атрибуты корневого элемента
При переключении темы скрипт `theme-engine.js` устанавливает на `<html>` и `<body>` следующие атрибуты:
```html
<html data-theme="theme-dark-slate" data-bs-theme="dark" data-theme-mode="theme-dark-slate">
<body class="theme-dark-slate">
```

### Сводная таблица дизайн-токенов

| Токен CSS | Назначение | Рекомендуемый класс Bootstrap |
|---|---|---|
| `--bg-color` / `--ui-bg-base` | Основной фон страницы | `bg-body`, `body` |
| `--surface-1` / `--card-bg` / `--ui-bg-surface` | Фон карточек, модальных окон и панелей | `card bg-body`, `modal-content` |
| `--surface-2` / `--ui-bg-surface-elevated` | Фон шапок карточек, тулбаров и разделителей | `card-header bg-body-tertiary` |
| `--nav-bg` | Фон верхней панели и меню навигации | `bg-body-tertiary` |
| `--text-color` / `--ui-text-primary` | Основной текст высокой читаемости | `text-body` |
| `--text-muted` / `--ui-text-muted` | Вторичный текст, подписи параметров | `text-muted` |
| `--ui-accent` / `--nav-active` | Главный акцентный цвет (кнопки, ссылки, иконки) | `text-primary`, `btn-primary` |
| `--ui-accent-hover` | Цвет акцента при наведении | `btn-primary:hover` |
| `--border-color` / `--ui-border-color` | Границы карточек, таблиц и разделители | `border-subtle`, `border` |
| `--border-strong` | Активные контуры элементов в фокусе | `border-primary` |
| `--radius-xs` / `--radius-sm` | Скругление кнопок, инпутов и бейджей (4px-6px) | `rounded`, `btn`, `badge` |
| `--radius-md` | Скругление карточек и контейнеров (8px) | `rounded`, `card` |
| `--radius-lg` | Скругление крупных модальных окон (12px) | `modal-dialog` |
| `--kpi-padding` / `--kpi-min-height` | Внутренние отступы и высота KPI-виджетов | `.preview-kpi-card` |

---

## 🚫 2. Правила верстки без хардкода цветов

> [!IMPORTANT]
> **Категорически запрещен хардкод цветов в атрибутах `style` и CSS!**
> Любой элемент должен органично отображаться как в глубокой тёмной теме, так и в светлой пастельной бумаге (NightView) или высококонтрастной теме.

### Примеры правильной и ошибочной верстки:

#### Карточки и контейнеры:
```html
<!-- ✅ ПРАВИЛЬНО: Адаптируется под любую тему -->
<div class="card border-subtle shadow-sm bg-body">
  <div class="card-header bg-body-tertiary text-body py-2 px-3">
    <span>Заголовок виджета</span>
  </div>
  <div class="card-body p-3">...</div>
</div>

<!-- ❌ ЗАПРЕЩЕНО: Разрушает светлые темы и инверсию -->
<div class="card bg-dark text-white" style="background-color: #12151a; border: 1px solid #333;">...</div>
```

#### Таблицы:
```html
<!-- ✅ ПРАВИЛЬНО: Строка с подсветкой и поддержкой AIModalDialog -->
<table class="table table-hover align-middle mb-0">
  <thead class="table-light border-bottom">...</thead>
  <tbody>
    <tr class="interactive-table-row">
      <td class="text-body fw-medium">Служба</td>
      <td class="text-muted font-monospace">PID 1234</td>
    </tr>
  </tbody>
</table>
```

#### Статусные бейджи:
```html
<!-- ✅ ПРАВИЛЬНО: Унифицированные бейджи дизайн-системы (ui-badge) с привязкой к CSS-токенам темы -->
<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>2666 MHz (⚠️ занижена на 534 MHz)</span>
<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>Оптимально</span>
<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i>Отключен</span>
<span class="ui-badge ui-badge-info">3200 MHz</span>
<span class="ui-badge ui-badge-neutral">NTFS</span>

<!-- ✅ ПРАВИЛЬНО: Адаптивные субтильные бейджи Bootstrap 5 (без инлайн-стилей) -->
<span class="badge bg-success-subtle text-success border border-success-subtle">Активен</span>
<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Внимание</span>

<!-- ❌ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: Любой инлайновый хардкод цветов разрушает светлые и контрастные темы! -->
<span class="badge" style="color: #facc15; background: rgba(234, 179, 8, 0.18);">...</span>
<span class="badge" style="background: green; color: white;">...</span>
```

---

## ⚙️ 3. Программный API ThemeEngine

Доступен через ES-модуль `apps/windows/api/webgui/js/theme.js` или глобально в объекте `window.themeEngine`.

### Основные методы:

```javascript
// 1. Применить встроенную тему по ID
window.setTheme('theme-dark-slate');
// Доступные ID: 'system', 'theme-dark-slate', 'theme-light-enterprise', 'theme-cyberpunk', 'theme-high-contrast', 'light', 'brick', 'terminal'

// 2. Получить текущий сохраненный режим
const mode = window.getThemeMode(); // 'theme-dark-slate'

// 3. Получить эффективный ID темы с учетом системных настроек
const resolved = window.getResolvedTheme();

// 4. Регистрация новой темы в рантайме
window.themeEngine.registerTheme({
  id: 'custom-ocean',
  name: 'Океан (Deep Ocean)',
  category: 'dark',
  icon: 'bi-water',
  tokens: {
    '--bg-color': '#031b26',
    '--surface-1': '#062939',
    '--ui-accent': '#00d2ff'
  }
});

// 5. Применение кастомных переопределений токенов (из Редактора тем)
window.themeEngine.applyCustomOverrides({
  '--radius-md': '14px',
  '--ui-font-size-base': '15px',
  '--ui-accent': '#ff007f'
}, true); // true = сохранить в LocalStorage

// 6. Сброс кастомных переопределений к базовой теме
window.themeEngine.clearCustomOverrides();
```

---

## 🎛️ 4. Редактор тем оформления (`theme_editor_tab`)

Редактор тем позволяет пользователю или администратору настраивать внешний вид системы:
- **Размеры:** Базовый шрифт 12px-20px, скругление углов 0px-24px, высота KPI, плотность (Compact / Normal / Comfortable).
- **Цвета:** Палитры поверхностей, текста, границ и статусов с синхронизированными пикерами цвета.
- **Элементы:** Стили теней, шрифты интерфейса, Glassmorphism и CRT Scanlines.
- **Быстрый доступ:** Кнопка перехода встроена прямо в модальное окно настроек пользователя (`#userSettingsModal`):
```html
<button class="btn btn-outline-primary btn-sm w-100" data-tab="tab-theme-editor" data-bs-dismiss="modal">
  <i class="bi bi-palette2 text-primary"></i>
  <span>Редактор тем оформления</span>
</button>
```
