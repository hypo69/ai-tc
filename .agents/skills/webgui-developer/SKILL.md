---
name: webgui-developer
description: Архитектурный стандарт, шаблоны, кодогенератор и пошаговые протоколы для разработки, модификации и отладки веб-интерфейсов, вкладок (*_tab) и интеграции с AIModalDialog и tab-core в AI Windows Admin.
description_i18n:
  en: Architectural standards, templates, scaffolding CLI, and step-by-step protocols for developing, modifying, and debugging WebGUI tabs (*_tab) with AIModalDialog and tab-core integration in AI Windows Admin.
  ru: Архитектурный стандарт, шаблоны, кодогенератор и пошаговые протоколы для разработки, модификации и отладки веб-интерфейсов, вкладок (*_tab) и интеграции с AIModalDialog и tab-core в AI Windows Admin.
---

# 🌐 Навык: Разработчик WebGUI (WebGUI Developer)

Этот навык предназначен для проектирования, создания, модификации и поддержки вкладок (`*_tab`) и веб-интерфейсов в экосистеме **AI Windows Admin** (`apps/windows/api/webgui`).

---

## 🎯 Когда активировать этот навык

- Разработка новой функциональной вкладки (`*_tab`) для системных панелей (`/tc`, `/admin`, `/apps`, `/`).
- Модификация или рефакторинг существующей вкладки WebGUI.
- Интеграция таблиц и списков с универсальным модальным окном ИИ-ассистента (`window.AIModalDialog.show`).
- Настройка и отладка фонового опроса телеметрии через `tab-core.js` (Active-Only Polling).
- Аудит верстки на соответствие темной/светлой темам и исключение хардкода цветов.
- Регистрация вкладок в `core/tab-registry.js` и меню `config/tc_menu_config.json`.

---

## 🏗️ Архитектурная карта WebGUI

```text
apps/windows/api/webgui/
├── core/
│   └── tab-registry.js          # Единый реестр вкладок (SSOT)
├── js/
│   ├── tab-core.js              # Ядро переключения вкладок, lazy load и поллинга
│   ├── theme-engine.js          # Переключение тем оформления (Dark, Light, Terminal, etc.)
│   └── toast.js                 # Уведомления toast
├── ai_modal_dialog/             # Универсальное окно ИИ-анализа сущностей
├── templates/
│   └── tab_template/            # Эталонный шаблон вкладки (index.html, main.js, README.md)
└── <name>_tab/                  # Изолированный модуль вкладки
    ├── index.html               # Чистая разметка (БЕЗ тегов <script>)
    ├── main.js                  # Контроллер: window.init<Name>Tab, window.deactivate<Name>Tab
    └── README.md                # Документация модуля
```

---

## 🚀 Пошаговый протокол: Создание новой вкладки

### 1. Автоматическая генерация через CLI (Рекомендуется)
Выполните скрипт генератора из навыка:
```powershell
py .agents/skills/webgui-developer/scripts/scaffold_tab.py <name> --title "<Заголовок RU>" --icon "<bi-icon>" --table-type "<type>"

# Пример:
py .agents/skills/webgui-developer/scripts/scaffold_tab.py storage_health --title "Здоровье дисков" --icon "bi-hdd-network" --table-type "disk"
```
Скрипт автоматически:
- Создаст каталог `apps/windows/api/webgui/storage_health_tab/`
- Сгенерирует `index.html` и `main.js` с правильными именами и заголовками `Updated:`
- Выведет готовые блоки кода для регистрации в `tab-registry.js` и `tc_menu_config.json`.

### 2. Ручное создание на базе шаблона
Если генератор не используется:
1. Скопируйте `apps/windows/api/webgui/templates/tab_template/` в `apps/windows/api/webgui/<name>_tab/`.
2. Замените префиксы `template-` на `<name>-`.
3. В `main.js` объявите функцию `window.init<PascalName>Tab`.
4. Подключите реальный API endpoint вместо мока.

### 3. Регистрация вкладки в SSOT реестре
Откройте [tab-registry.js](file:///c:/Users/onela/AppData/Local/ai-tc/apps/windows/api/webgui/core/tab-registry.js) и добавьте вкладку в `TAB_DEFINITIONS`:
```javascript
{
  id: 'storage_health',
  label: 'Здоровье дисков',
  icon: 'bi-hdd-network',
  tab: 'storage-health',
  tabId: 'tab-storage-health',
  html: '/html/storage_health_tab/index.html?v=20261015_v1',
  js: '/html/storage_health_tab/main.js?v=20261015_v1'
}
```

### 4. Добавление в меню навигации
Откройте `apps/windows/api/webgui/config/tc_menu_config.json` и добавьте пункт в `sidebarItems` или `topButtons`:
```json
{
  "id": "storage_health",
  "tab": "tab-storage-health",
  "icon": "bi-hdd-network",
  "label": "Здоровье дисков",
  "order": 25,
  "visible": true
}
```

### 5. Создание и внедрение суб-меню панелей (Subtabs Nav-Pills Hub)
Когда вкладка объединяет несколько функциональных панелей (как в `tab_software_scanner` и `tab_processes_load_inspector`), запрещено располагать их длинной вертикальной «простыней». Все панели скрываются под горизонтальным меню закругленных пилюль (`nav nav-pills` с `rounded-pill`).

Для автоматической генерации разметки шапки и JS переключателя используйте встроенный инструмент:
```powershell
py .agents/skills/webgui-developer/scripts/subtabs_builder.py generate \
  --title "Мониторинг процессов" \
  --subtitle "Диспетчер задач и активность хоста" \
  --icon "⚡" \
  --prefix "proc" \
  --tabs "manager:'Диспетчер процессов':bi-layout-text-window-reverse:text-primary top:'Топ процессов':bi-speedometer2:text-warning net:'Сетевая активность':bi-globe:text-info files:'Изменения файлов':bi-activity:text-success"
```
Инструмент выводит готовую HTML разметку шапки, контейнеров `tab-pane` и экспорт функции `switch<Prefix>SubTab(id)` для программного переключения.

---

## ⚡ Обязательные стандарты разработки

### 1. Навигация строго через `data-tab`
```html
<!-- ✅ ПРАВИЛЬНО -->
<button type="button" data-tab="tab-storage-health">Диски</button>

<!-- ❌ ЗАПРЕЩЕНО -->
<button type="button" data-bs-target="#tab-storage-health" data-bs-toggle="tab">...</button>
<button type="button" onclick="switchTab('storage-health')">...</button>
```

### 2. Поллинг строго через `registerTabPoller`
```javascript
// ✅ ПРАВИЛЬНО: Опрос засыпает при неактивной вкладке или свернутом браузере
window.registerTabPoller('tab-storage-health', async () => {
  await fetchDriveMetrics();
}, 5000, { immediate: false });

// ❌ ЗАПРЕЩЕНО: Обычный setInterval приводит к утечкам ресурсов и блокировке бэкенда!
setInterval(fetchDriveMetrics, 5000);
```

### 3. Полный запрет хардкода в стилях (Всё только через механизм тем)

> [!CAUTION]
> **Никакого хардкода в стилях!**
> Категорически запрещено прописывать цвета, фоны и границы через HEX (`#facc15`, `#12151a`), RGB/RGBA или в инлайновых атрибутах `style="color:...", style="background:..."`.
> Всё оформление реализуется **строго через механизм тем** и дизайн-токены CSS-переменных, либо системные классы компонентов.

Все компоненты ОБЯЗАНЫ использовать стандартные CSS-переменные дизайн-системы и классы Bootstrap 5:
- Фоны: `bg-body`, `bg-body-tertiary`, `var(--bg-color)`, `var(--surface-1)`, `var(--surface-2)`
- Текст: `text-body`, `text-muted`, `var(--text-color)`, `var(--ui-text-primary)`
- Границы: `border-subtle`, `border-secondary-subtle`, `var(--border-color)`
- Акценты: `text-primary`, `btn-primary`, `var(--ui-accent)`, `var(--nav-active)`
- Скругления: `var(--radius-sm)`, `var(--radius-md)`, `var(--radius-lg)`
- Подробный справочник токенов: [references/themes_and_styling.md](references/themes_and_styling.md)

#### Статусные бейджи (`ui-badge`):
```html
<!-- ✅ ПРАВИЛЬНО: Семантические бейджи дизайн-системы (адаптивны для Light, Brick, Dark, Terminal) -->
<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>2666 MHz (⚠️ занижена на 534 MHz)</span>
<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>Оптимально</span>
<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i>Отключен</span>
<span class="ui-badge ui-badge-info">3200 MHz</span>
<span class="ui-badge ui-badge-neutral">NTFS</span>

<!-- ❌ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: Инлайновый хардкод цветов разрушает светлые и контрастные темы! -->
<span class="badge border border-warning-subtle" style="color: #facc15; background: rgba(234, 179, 8, 0.18);">...</span>
```

#### Карточки и контейнеры:
```html
<!-- ✅ ПРАВИЛЬНО -->
<div class="card bg-body border-subtle shadow-sm">
  <div class="card-header bg-body-tertiary text-body">Заголовок</div>
</div>

<!-- ❌ ЗАПРЕЩЕНО -->
<div class="card bg-dark text-white" style="background-color: #12151a;">...</div>
```

### 4. Интеграция с `window.AIModalDialog.show({...})`
Строки таблиц должны иметь класс `interactive-table-row` и навешанный обработчик:
```javascript
modal.show({
  title: drive.model,
  subtitle: `Серийный номер: ${drive.serial}`,
  icon: '💽',
  tableType: 'disk',
  badges: [{ text: drive.health, class: 'badge bg-success' }],
  metadata: [
    { label: 'Размер', value: `${drive.size_gb} GB` },
    { label: 'Температура', value: `${drive.temperature_c} °C` }
  ],
  rawTitle: 'SMART телеметрия',
  rawContent: JSON.stringify(drive.smart_attributes, null, 2),
  autoRun: false
});
```

### 5. Стандарт Drill-down в таблицах (Иконка дрели СЛЕВА)
Если сущности в таблице поддерживают углубленный анализ (Drill-down / Deep Dive / переход к инспектору инстанса):
- **Запрет текстовых кнопок справа:** Запрещено размещать кнопки вида `🔬 Deep Dive` в конце строки или теле таблицы.
- **Размещение строго СЛЕВА:** Кнопка Drill-down размещается в **первой колонке СЛЕВА** от строки (`<th>` и `<td>`).
- **Иконка:** Стандартизированная красная дрель `/html/assets/red_drill.png`.
- **Изоляция клика:** Кнопка или ячейка помечается классом `no-modal-trigger` и вызывает `e.stopPropagation()`, чтобы переход к детальному представлению не конфликтовал с открытием модального окна `AIModalDialog`.

```html
<!-- Колонка дрели в заголовке таблицы -->
<th style="width: 36px; text-align: center;" title="Drill-down: Детальный анализ"></th>

<!-- Ячейка дрели в строке -->
<td class="text-center no-modal-trigger" style="width: 36px;">
  <button type="button" class="btn-drilldown-proc" title="Drill-down: Глубокий анализ">
    <img src="/html/assets/red_drill.png?v=YYYYMMDD_vN" alt="Drill-down">
  </button>
</td>
```

### 6. Интерактивный Редактор тем (`theme_editor_tab`)
В экосистему встроен модуль кастомизации оформления:
- Вкладка: `theme-editor` (`apps/windows/api/webgui/theme_editor_tab/`)
- Быстрый доступ: кнопка навигации встроена в модальное окно настроек профиля (`#userSettingsModal`):
  `<button class="btn btn-outline-primary btn-sm w-100" data-tab="tab-theme-editor" data-bs-dismiss="modal">`
- Программное управление: `window.themeEngine.applyCustomOverrides(tokens, save)`, `window.themeEngine.clearCustomOverrides()`.

---

## 📋 Чек-лист верификации перед коммитом

- [ ] В `index.html` нет `<script>` тегов.
- [ ] Опрос бэкенда зарегистрирован через `window.registerTabPoller`.
- [ ] Кнопка навигации содержит `data-tab="tab-<name>"`.
- [ ] **Никакого хардкода в стилях:** Проверено отсутствие HEX/RGB/RGBA и инлайновых стилей оформления (`style="color:...", style="background:..."`). Всё оформление (фоны, текст, рамки, бейджи `ui-badge-*`) подключено строго через механизм тем.
- [ ] Табличные строки поддерживают вызов `AIModalDialog.show()`.
- [ ] Drill-down сущностей оформлен иконкой дрели (`/html/assets/red_drill.png`) строго СЛЕВА от строки таблицы.
- [ ] Вкладка зарегистрирована в `core/tab-registry.js`, `apps/modules/tabs-config.js` и `config/tc_menu_config.json`.
- [ ] Версия ассетов обновлена: `?v=YYYYMMDD_vN`.
- [ ] В шапке каждого файла присутствует `Updated: YYYY-MM-DD HH:MM:SS`.
- [ ] Комментарии, docstrings и документация на русском языке.

