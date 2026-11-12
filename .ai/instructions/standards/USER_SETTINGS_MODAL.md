# Стандарт единого модального окна настроек пользователя (User Settings Modal)

<!--
=============================================================================
Process Name: Engineering Standard - User Settings Modal Architecture
=============================================================================
Description:
  Инженерный стандарт архитектуры, интеграции, геометрии (90vw × 90vh),
  выбора темы, языка локализации и модели ИИ для единого модального окна
  #userSettingsModal в экосистеме проектов AI-Assistant, AI-TC и AI-Breadboard.

File: USER_SETTINGS_MODAL.md
Package: .ai/instructions/standards
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-03 15:00:00
=============================================================================
-->

## 1. Назначение и контекст мастер-диалога

Настоящий стандарт регламентирует архитектуру, поведение, разметку и кросс-проектную синхронизацию системного модального окна пользовательских настроек (`#userSettingsModal`).

> [!IMPORTANT]
> **Мастер-диалог архитектуры:** Все принципы построения окна интерфейса, интеграции выбора языка, темы оформления и модели ИИ утверждены в диалоге:
> 🔗 **[conversation 5bda405e-140b-4205-b1af-3020aea81e71](conversation://5bda405e-140b-4205-b1af-3020aea81e71)**.
> Модальное окно является **единым и общим** для всех трех проектов:
> - `AI-Assistant` (`%localappdata%\AI-Assistant\apps\common\webgui`)
> - `AI-TC` (`%localappdata%\AI-TC\apps\common\webgui`)
> - `AI-Breadboard` (`%localappdata%\AI-Breadboard\apps\common\webgui`)

---

## 2. Архитектурная спецификация окна

### 2.1 Единое размещение и Single Source of Truth
Все общие элементы модального окна располагаются строго в `apps/common/webgui/`:
- Декларативная разметка: `components/user_settings_modal.html`
- Клиентский контроллер: `js/userSettings.js`
- Каталог тем оформления: `themes/` (13 тем + `themes_catalog.json`)
- Стили и переменные: `css/components.css`, `css/variables.css`, `css/themes.css`
- Словари локализации: `locales/{ru,en,he,uk}.json`

### 2.2 Стандарт геометрии 90% экрана (WEBGUI.md § 5.4)
Все модальные окна WebGUI обязаны занимать **90% экрана** по ширине и высоте:
```css
.modal .modal-dialog {
  --bs-modal-width: var(--modal-width, 90vw) !important;
  width: var(--modal-width, 90vw) !important;
  max-width: var(--modal-width, 90vw) !important;
  height: var(--modal-height, 90vh) !important;
  max-height: var(--modal-height, 90vh) !important;
  min-height: var(--modal-height, 90vh) !important;
  margin: calc((100vh - var(--modal-height, 90vh)) / 2) auto !important;
}
```

### 2.3 Бейдж активной модели и переход во вкладку выбора
1. В шапке окна (`#user-settings-active-model-badge-top`) и в секции проверки модели (`#user-settings-active-model-badge`) размещен интерактивный бейдж.
2. При загрузке и открытии окна контроллер опрашивает `/api/v1/chat/active-model` или `/auth/settings` и выводит отображаемое имя модели (например, `gemini-2.5-flash`).
3. При клике (`onclick`) вызывается функция `openModelsTab()`, которая:
   - Закрывает модальное окно через `bootstrap.Modal.getInstance(modalEl).hide()`;
   - Выполняет мгновенный переход на унифицированную вкладку каталога моделей через `window.switchTab('tab-models')`.

### 2.4 Темы оформления (13 тем)
Селектор `#modal-theme-selector` включает в себя:
- `system` — системный адаптивный режим
- **🌙 Тёмные темы**: `dark`, `theme-dark-slate`, `theme-cyberpunk`, `terminal`, `nordic-frost`, `solarized-dark`, `theme-high-contrast`
- **☀️ Светлые темы**: `light`, `nightview` (Тёплая бумага), `nightview-70` (Тёплая бумага 70%), `brick`, `theme-light-enterprise`

### 2.5 Языковая локализация (i18n)
Поддерживаются 4 локали: `ru-RU`, `en-US`, `he-IL` (RTL), `uk-UA`. При переключении через селектор `#modal-lang-selector` обновляется атрибут `<html lang="..." dir="...">` и пересчитываются ключи через `i18next`.

---

## 3. Автоматизированный надзор и синхронизация (User Settings Sync Agent)

Для предотвращения рассинхронизации и поломок логики при модификациях кода разработан специальный агент и инструментарий:
- **Навык**: `.agents/skills/user-settings-sync-agent/SKILL.md`
- **Аудитор контрактов DOM и локалей**: `.agents/skills/user-settings-sync-agent/scripts/verify_modal_integrity.py`
- **Синхронизатор репозиториев**: `.agents/skills/user-settings-sync-agent/scripts/sync_user_settings.py`

### CLI команды:
```powershell
# Проверка совместимости и целостности
py manage_tools.py ui check-user-settings

# Каскадная синхронизация во все 3 проекта
py manage_tools.py ui sync-user-settings
```
