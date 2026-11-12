# 🖥️ Вкладка универсального редактора файлов Rust + WebAssembly (`apps/common/webgui/tab_file_editor`)

**Статус:** ✅ Активно  
**Версия:** 1.0.0  
**Пакет:** `apps.common.webgui.tab_file_editor`  
**Автор:** hypo69  
**Updated:** 2026-10-28 17:11:00  

---

## 📋 Назначение

Вкладка `tab_file_editor` предоставляет полнофункциональную среду редактирования файлов в стиле **Visual Studio Code**, работающую на базе общего модуля [`apps/common/file_editor`](../../file_editor/README.md) и бинарного ядра **Rust + WebAssembly** (`file_editor_core.wasm`).

Вкладка расположена в общем репозитории ассетов `apps/common/webgui/tab_file_editor` и прозрачно раздаётся через `SmartMultiDirStaticFiles` по маршруту `/html/tab_file_editor/*` во всех веб-интерфейсах проекта.

---

## 🧩 Поддерживаемые режимы редактирования (VS Code Parity)

1. **`code` (Код и Текст — 70+ языков)**:
   - Редактирование исходного кода (`Python`, `Rust`, `JS/TS`, `HTML/CSS`, `JSON`, `YAML`, `TOML`, `XML`, `SQL`, `PowerShell`, `Bash`, `C/C++/C#`, `Go`, `Dockerfile`, `.env`, `.ini`, `.log`).
   - Нумерация строк с синхронным скроллингом, панель поиска и замены (`Ctrl+F`), боковое дерево структурных символов (`Outline`: классы, функции, структуры, ключи), автоформатирование (`Alt+Shift+F`) и сохранение с коммитом в Git (`Ctrl+S`).
2. **`markdown` (Markdown Split-View)**:
   - Двухпанельное редактирование Markdown с живым рендерингом справа и навигацией по заголовкам в панели `Outline`.
3. **`tabular` (Табличный редактор CSV / TSV)**:
   - Интерактивная таблица (`Grid View`) с редактированием ячеек на месте, добавлением строк и столбцов и двусторонней синхронизацией с сырым CSV/TSV-буфером.
4. **`notebook` (Редактор Jupyter Notebook `.ipynb`)**:
   - Интерактивное редактирование ячеек `Code` и `Markdown`, добавление и удаление ячеек с сохранением валидной JSON-схемы `nbformat 4`.
5. **`media_studio` (SVG, Растровые изображения, PDF, Аудио/Видео)**:
   - **SVG**: живой векторный предпросмотр параллельно с редактированием XML.
   - **Изображения (`.png`, `.jpg`, `.webp`, `.gif`, `.bmp`, `.ico`)**: холст HTML5 Canvas с поворотом на `-90°/+90°`, отражением по горизонтали/вертикали и сохранением изменённого бинарного изображения обратно на диск.
   - **PDF (`.pdf`)**: встроенный просмотрщик страниц и кнопка мгновенного извлечения текста в режим `Markdown`.
6. **`hex` (VS Code Hex Editor + Wasm Data Inspector)**:
   - Побайтовая сетка `Offset | 16 байт Hex | ASCII` с пагинацией по 4 КБ.
   - Двойной клик по любому байту позволяет изменить его Hex-значение (`00..FF`) на месте с отправкой точечных патчей (`hex_patches`) на сервер.
   - Боковая панель **Data Inspector** в реальном времени декодирует выбранное смещение в `8-bit binary`, `UInt8`, `Int8`, `UInt16 LE`, `Int16 LE`, `UInt32 LE`, `Int32 LE`, `Float32` и `ASCII/UTF-8`.
7. **`diff` (Построчное сравнение Unified Diff)**:
   - Сравнение текущего несохранённого буфера с версией файла на диске перед сохранением.

---

## 📁 Архитектура файлов вкладки

```text
apps/common/webgui/tab_file_editor/
├── index.html                      # Чистая разметка вкладки (без <script> и хардкода цветов, i18n)
├── style.css                       # Стили на базе CSS-переменных дизайн-системы (var(--...))
├── main.js                         # Главный оркестратор: initFileEditorTab, openFileInWasmEditor
├── wasm_bridge.js                  # Мост к WebAssembly (file_editor_core.wasm) и Data Inspector
├── panel_code_editor.js            # Нумерация строк, Outline, Markdown Split и Find/Replace
├── panel_specialized_editors.js    # Hex Editor, CSV Grid, Jupyter .ipynb и Media/Canvas Studio
└── README.md                       # Документация модуля
```

---

## 🔗 Программный вызов из других модулей WebGUI

Любой компонент проводника файлов или контекстного меню может открыть файл прямо во вкладке универсального редактора:

```javascript
if (typeof window.openFileInWasmEditor === 'function') {
  await window.openFileInWasmEditor('src/main.py', 'demo', true);
}
```
