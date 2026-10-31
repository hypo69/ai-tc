# Веб-интерфейс Windows (`apps/windows/api/webgui`)

Фронтенд (WebGUI) — часть основного модуля [`api`](../README.md). Оболочки (shells) с навигацией и набором вкладок `tab_<id>`; общая логика жизненного цикла и опросов — в `js/tab-core.js`. Подробный стандарт — [`UI_ARCHITECTURE.md`](UI_ARCHITECTURE.md), правила для ИИ-агентов — [`GEMINI.md`](GEMINI.md).

---

## 📁 Структура

```
webgui/
├── index.html, login.html, system_inspector.html   # Страницы-оболочки
├── core/tab-registry.js     # TAB_DEFINITIONS — единый источник правды по вкладкам (id, иконка, html, js)
├── tab_<id>/                # 77 вкладок: index.html + main.js (+ README.md); правила — UI_ARCHITECTURE.md
├── js/                      # Общие ES-модули (tab-core, i18n, chatService, api-cache, ai_table_modal и др.)
├── css/                     # base, variables, themes, components, nav, overrides (см. css/README.md)
├── themes/                  # Темы оформления (dark, light, nordic-frost, cyberpunk и др.)
├── components/              # Общие HTML-компоненты (universal_ai_table_modal, privacy_radar_panel)
├── ai_modal_dialog/         # Универсальное модальное окно ИИ-ассистента
├── config/, config_menues/  # Меню: tc_menu_config.json, su_menu_config.json
├── templates/tab_template/  # Шаблон новой вкладки
├── locales/                 # i18n: en, ru, uk, he (+ user_*)
├── admin/, apps/            # apps/ — оболочка /, /tc, /apps, /su; admin/ — отдельная страница (статика)
├── assets/, icons/, static/ # Ресурсы
├── cosmicplayer/, rc/, remote_mic/, messenger/, user/, user_tts/, sources/, help/  # Дополнительные портлеты
└── tab_sitemap/             # Интерактивная карта сайта (generate_sitemap_data.py → sitemap_data.json)
```

## 🧭 Оболочки

Маршруты `/`, `/tc`, `/apps`, `/su` отдают `apps/index.html` (меню — `config/tc_menu_config.json`). Файлы `admin/index.html`, `user/index.html`, `index.html` доступны как статика под `/html/...`.
Статика отдаётся сервером под `/html` и `/webinterface` (`SmartMultiDirStaticFiles`: этот каталог → общий `apps/common/webgui`).

## 🧩 Правила

- **Active-Only polling**: опрашивает API только активная вкладка (см. `UI_ARCHITECTURE.md`).
- **Темизация без хардкода**: цвета только через CSS-переменные и классы дизайн-системы.
- **Cache-busting**: версия ассетов `?v=YYYYMMDD_vN` при любом изменении.
- **Новая/изменённая вкладка** → обновить `core/tab-registry.js` и карту сайта: `py apps/windows/api/webgui/tab_sitemap/generate_sitemap_data.py`.
- Каталог вкладки — строго `tab_<tab_id>`; у каждой вкладки есть собственный `README.md`.

---

**Updated:** 2026-10-31 16:45:00
**Package:** `windows/api/webgui`
**Author:** hypo69
