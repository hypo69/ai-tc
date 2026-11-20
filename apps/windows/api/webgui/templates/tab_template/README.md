<!--
=============================================================================
Process Name: Windows Web Interface - Reference Tab Template Documentation
=============================================================================
Description:
  Руководство разработчика по созданию новых вкладок на базе эталонного шаблона.

File: README.md
Project: ai-tc
Package: windows/api/webgui/templates/tab_template
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 05:00:00
=============================================================================
-->

# Шаблон Вкладки WebGUI (Tab Reference Template)

Данный каталог содержит эталонную структуру и исходные коды для быстрого создания новых функциональных вкладок в веб-интерфейсе **ai-tc**.

---

## 📁 Структура шаблона

```text
templates/tab_template/
├── index.html        # Эталонная HTML-разметка вкладки (без тегов <script>)
├── main.js           # Эталонный ES-контроллер жизненного цикла и поллинга
└── README.md         # Настоящее руководство разработчика
```

---

## 🚀 Пошаговое руководство по созданию новой вкладки

### Шаг 1. Скопируйте папку шаблона в корень WebGUI
Создайте новую директорию с суффиксом `_tab` в `apps/windows/api/webgui/`:
```powershell
Copy-Item -Path "apps/windows/api/webgui/templates/tab_template" -Destination "apps/windows/api/webgui/tab_my_feature" -Recurse
```

### Шаг 2. Отредактируйте идентификаторы
1. В `index.html`:
   - Замените префиксы `template-` на ваш уникальный префикс (например, `myfeat-`).
   - Настройте заголовок, описание и колонки таблицы.
2. В `main.js`:
   - Задайте имя функции инициализации `window.initMyFeatureTab`.
   - Задайте `TAB_ID = 'tab-my-feature'`.
   - Настройте эндпоинт API `API_ENDPOINT`.
   - Настройте параметры вызова `window.AIModalDialog.show({...})`.

### Шаг 3. Зарегистрируйте вкладку в едином реестре (`core/tab-registry.js`)
Добавьте запись в массив `TAB_DEFINITIONS`:
```javascript
{
  id: 'my_feature',
  label: 'Моя Функция',
  icon: 'bi-stars',
  tab: 'my-feature',
  tabId: 'tab-my-feature',
  html: '/html/tab_my_feature/index.html?v=20261015_v1',
  js: '/html/tab_my_feature/main.js?v=20261015_v1'
}
```

### Шаг 4. Добавьте вкладку в конфигурацию меню (`config/tc_menu_config.json`)
```json
{
  "id": "my_feature",
  "tab": "tab-my-feature",
  "icon": "bi-stars",
  "label": "Моя Функция",
  "order": 15,
  "visible": true
}
```

---

## ⚠️ Критические правила и архитектурные запреты

1. **Никакого `setInterval`**: Все периодические опросы регистрируются **только** через `window.registerTabPoller(tabId, pollerFn, intervalMs)`. При переключении вкладок или сворачивании окна таймеры автоматически засыпают.
2. **Никакого хардкода цветов**: Запрещены классы `bg-black`, `bg-dark`, `text-white` и жесткие HEX-цвета `#000`. Все стили должны опираться на переменные CSS темы (`var(--surface-1)`, `var(--text-color)`) и адаптивные Bootstrap 5 классы (`bg-body`, `bg-body-tertiary`, `text-body`, `border-subtle`).
3. **Навигация строго через `data-tab`**: Запрещены `data-bs-target`, `onclick` для переключения вкладок.
4. **Обязательный заголовок файла**: При любом редактировании файлов шапка `Updated: YYYY-MM-DD HH:MM:SS` обязана обновляться.

