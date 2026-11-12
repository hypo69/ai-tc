# 📝 Модуль универсального редактора файлов Rust + WebAssembly (`apps/common/file_editor`)

**Статус:** ✅ Активно  
**Версия:** 1.0.0  
**Пакет:** `apps.common.file_editor`  
**Автор:** hypo69  
**Updated:** 2026-10-28 17:02:00  

---

## 📋 Назначение

Модуль `apps/common/file_editor` предоставляет единое высокоскоростное ядро редактирования файлов на базе **Rust + WebAssembly**, поддерживающее редактирование всех категорий файлов, с которыми работает **Visual Studio Code**:

1. **Исходный код и скрипты (`EditorMode.CODE`)**:
   - Более 60 языков программирования и конфигураций (`Python`, `Rust`, `JavaScript`, `TypeScript`, `HTML`, `CSS`, `SCSS`, `JSON`, `YAML`, `TOML`, `XML`, `SQL`, `PowerShell`, `Bash`, `C/C++`, `C#`, `Go`, `Java`, `Kotlin`, `Dockerfile`, `Makefile`, `.env`, `.ini`, `.log`).
   - Подсветка синтаксиса, нумерация строк, миникарта, навигация по символам (Outline), автоформатирование и встроенный Unified Diff.
2. **Markdown и документация (`EditorMode.MARKDOWN`)**:
   - Двухпанельный режим Split-View (исходный текст + живой рендеринг Markdown), панель быстрой разметки и оглавление заголовков.
3. **Табличные данные CSV / TSV (`EditorMode.TABULAR`)**:
   - Интерактивный табличный редактор ячеек (добавление/удаление строк и колонок, сортировка, редактирование на месте) с мгновенной синхронизацией с сырым CSV/TSV-текстом.
4. **Интерактивные блокноты Jupyter (`EditorMode.NOTEBOOK`, `.ipynb`)**:
   - Полноценное редактирование ячеек `Code` и `Markdown`, добавление, перемещение и удаление ячеек с сохранением структуры JSON-схемы `.ipynb`.
5. **Векторная графика SVG (`EditorMode.VECTOR_SVG`, `.svg`)**:
   - Двусторонний режим: редактирование XML-разметки SVG + интерактивный векторный холст с масштабированием.
6. **Растровые изображения (`EditorMode.IMAGE`, `.png`, `.jpg`, `.webp`, `.gif`, `.bmp`, `.ico`)**:
   - Графическая студия на базе HTML5 Canvas / Wasm: поворот на 90°, отражение по горизонтали/вертикали, изменение масштаба, инспекция пикселей и сохранение обратно в рабочее пространство.
7. **Документы PDF (`EditorMode.PDF`, `.pdf`)**:
   - Клиентский Wasm-движок постраничного рендеринга PDF с мгновенным извлечением текста и структуры заголовков в Markdown для прямого редактирования.
8. **Аудио и Видео (`EditorMode.MEDIA`, `.mp3`, `.wav`, `.ogg`, `.mp4`, `.webm`)**:
   - Встроенный медиа-инспектор с воспроизведением, метаданными потока и переключением в побайтовый Hex-режим.
9. **Бинарные файлы и WebAssembly (`EditorMode.HEX`, `.bin`, `.wasm`, `.exe`, `.dll`, `.sqlite`, `.db`, `.zip` и любые бинарные форматы)**:
   - Полнофункциональный **VS Code Hex Editor**: таблица `Offset | 16 байт Hex | ASCII` с побайтовым редактированием на месте и боковой панелью **Data Inspector** (`8-bit binary`, `Int8`, `UInt8`, `Int16 LE`, `UInt16 LE`, `Int32 LE`, `UInt32 LE`, `Float32`, `Float64`, `UTF-8`).

---

## 🏗️ Структура каталога

```text
apps/common/file_editor/
├── __init__.py                 # Экспорт публичного API пакета
├── models.py                   # Pydantic-модели и перечисления режимов EditorMode
├── catalog.py                  # Реестр более 85 типов файлов и языковых режимов VS Code
├── wasm_compiler.py            # Сборщик и валидатор нативного модуля file_editor_core.wasm
├── service.py                  # Чтение, запись, Hex-патчинг, форматирование и Unified Diff
├── router.py                   # FastAPI маршрутизатор /api/v1/file-editor/*
├── README.md                   # Документация модуля
├── wasm/
│   └── file_editor_core.wasm   # Скомпилированный бинарный модуль WebAssembly 1.0
└── rust_engine/                # Исходный крейт Rust для wasm-pack
    ├── Cargo.toml
    └── src/
        ├── lib.rs              # Экспорты Wasm: fnv1a_hash, count_lines, is_binary_buffer
        ├── hex_inspector.rs    # Декодер числовых типов Data Inspector
        └── syntax_analyzer.rs  # Извлечение дерева символов (Outline)
```

---

## 🔌 Контракты REST API (`/api/v1/file-editor`)

| Метод | Маршрут | Назначение |
|---|---|---|
| `GET` | `/api/v1/file-editor/catalog` | Возвращает полный каталог поддерживаемых расширений и режимов VS Code |
| `GET` | `/api/v1/file-editor/wasm` | Отдаёт бинарный модуль `file_editor_core.wasm` (`application/wasm`) |
| `GET` | `/api/v1/file-editor/read` | Читает файл рабочей области (текст, Base64, хеш FNV-1a, дескриптор режима) |
| `POST` | `/api/v1/file-editor/save` | Сохраняет изменения (текст, Base64 или список байтовых правок `hex_patches`) с коммитом в Git |
| `POST` | `/api/v1/file-editor/format` | Форматирует и проверяет синтаксис буфера (JSON, XML, SVG, CSV, `.ipynb`, код) |
| `POST` | `/api/v1/file-editor/diff` | Вычисляет построчный Unified Diff между буфером редактора и файлом на диске |
