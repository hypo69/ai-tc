# 🎨 Модули тем оформления (WebGUI Themes)

Каталог стандартных тем оформления интерфейса ai-tc.

## Архитектура хранения

Каждая тема системы хранится в своей отдельной директории:
```
apps/windows/api/webgui/themes/
├── <theme_id>/
│   └── theme.json                     # Метаданные темы и словарь CSS-токенов
├── generate_themes_catalog.py        # Скрипт сборки themes_catalog.json
├── themes_catalog.json               # Манифест всех зарегистрированных тем
└── README.md
```

## Сборка каталога тем

Для актуализации файла `themes_catalog.json`:
```powershell
py apps/windows/api/webgui/themes/generate_themes_catalog.py
```

## Интеграция с клиентом и кеширование

1. При запуске интерфейса список тем считывается из эндпоинта `/api/themes` (или `/html/themes/themes_catalog.json`).
2. Каталог тем кешируется в браузере в `localStorage.getItem('themes_catalog')`.
3. Инлайн-скрипт в `<head>` динамически извлекает `baseType` (`light`/`dark`) из кеша браузера по сохраненному имени `localStorage.getItem('theme')` без какого-либо хардкода имён.
