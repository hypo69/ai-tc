# Стандарт построения меню панелей (субвкладок) и подменю блоков WebGUI

<!--
=============================================================================
Process Name: Engineering Standard - Subtabs and Blocks Menu Architecture
=============================================================================
Description:
  Единый стандарт и архитектурные правила построения меню панелей (субвкладок)
  и подменю блоков внутри WebGUI с обязательной поддержкой шаблонизации,
  мгновенных статических тултипов (без обращения к AI-модели), сквозного i18n
  и синхронизации с URL.

File: SUBTABS_AND_BLOCKS_MENU.md
Package: .ai/instructions/standards
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 02:30:00
=============================================================================
-->

## 1. Концепция и базовый принцип: «Меню — всегда меню»

Во всех разделах и вкладках веб-интерфейса действует единый принцип унификации навигации:
> **«Меню — всегда меню и выглядит одинаково во всех панелях и блоках».**

Запрещено строить разрозненные варианты переключателей (аккордеоны, вертикальные простыни скролла, нестандартные радио-кнопки). Любой составной экран организуется в строгую двухуровневую иерархию:
1. **Уровень 1: Меню панелей субвкладок (`panelId` / `subtabId`)** — горизонтальная линейка переключения функциональных экранов раздела. Располагается **ПОД заголовком вкладки, строго СЛЕВА**.
2. **Уровень 2: Подменю блоков внутри панели (`blockId`)** — горизонтальная или компактная линейка переключения подсекций внутри конкретной панели (например, внутри панели файлов: Git, слежение, заметки, внешние источники).

---

## 2. Иерархия маршрутизации URL (Канонический стандарт)

Каждое переключение обязано синхронизироваться с адресной строкой браузера:

```text
# Одноуровневая субпанель:
http://localhost:8002/#tab-<tabId>#panel-<panelId>

# Субпанель с внутренним блоком:
http://localhost:8002/#tab-<tabId>#panel-<panelId>#block-<blockId>

# Субпанель с рабочим пространством:
http://localhost:8002/#tab-workspace#panel-files#workspace=<workspace_id>

# Субпанель с подменю блока и рабочим пространством:
http://localhost:8002/#tab-workspace#panel-files#block-<blockId>#workspace=<workspace_id>
```

### Правила обработки URL:
- **Двусторонняя реактивность**: Клик по кнопке обновляет хэш через `history.replaceState` / `history.pushState` без перезагрузки страницы; переход по ссылке или кнопкам браузера «Назад / Вперёд» мгновенно активирует нужную панель и блок.
- **Fail-Safe парсер**: Парсер хэша обязан игнорировать порядок сегментов и поддерживать как полный путь, так и дефолтные fallbacks, если блок или панель не указаны.

---

## 3. Требование к всплывающим подсказкам (Тултипам): «Делать сразу, БЕЗ модели»

> [!IMPORTANT]
> **Категорический запрет на обращение к LLM/модели для подсказок меню:**
> Тексты всплывающих подсказок **ОБЯЗАНЫ быть сформулированы и внедрены СРАЗУ** на этапе верстки и генерации компонентов. Запрещено использовать запросы к AI-модели, динамические генерации подсказок на лету или отложенные AI-промпты для элементов навигации.

### Правила написания тултипов:
1. **Мгновенность и детерминированность**: Подсказка должна отображаться мгновенно при наведении мыши (через нативный `title` и Bootstrap tooltip `data-bs-title`).
2. **Информативность и полезность**: Тултип обязан кратко и ёмко отвечать на 2 вопроса:
   - *Что делает этот раздел/блок?* (например: «Просмотр дерева файлов репозитория и истории изменений Git»);
   - *Какое действие произойдет при клике?* (например: «Переключить на форму добавления локальных файлов и директорий в слежение»).
3. **Строгая интернационализация**: Текст тултипа никогда не хардкодится во фронтенд-скриптах — он прописывается в словарях локализации под ключом вида `*Title` / `*Tooltip` и связывается атрибутом `data-i18n-title`.

---

## 4. Контракт разметки HTML и семантические классы

### 4.1. Разметка меню панелей субвкладок (Уровень 1)

```html
<!-- Заголовок вкладки -->
<div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
  <div class="d-flex align-items-center gap-2">
    <span class="fs-4 text-primary"><i class="bi bi-folder2-open"></i></span>
    <div>
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <h5 class="mb-0 fw-bold text-white" data-i18n="tabFilesTitle">Управление файлами</h5>
        <span class="badge bg-secondary-subtle text-secondary border border-secondary border-opacity-25" id="files-counter-badge">0</span>
      </div>
      <small class="text-secondary" data-i18n="tabFilesSubtitle">Просмотр репозитория, Git-слежение и конвертация</small>
    </div>
  </div>
</div>

<!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->
<div class="d-flex align-items-center mb-3 pb-2 border-bottom border-secondary border-opacity-25 flex-wrap gap-2">
  <div class="d-flex align-items-center gap-1 flex-wrap" id="files-subtabs-nav" role="tablist">
    <button class="btn btn-sm btn-outline-primary active d-flex align-items-center gap-1.5 py-1 px-2.5 rounded"
            id="subtab-files-browse-btn"
            data-bs-toggle="pill"
            data-bs-target="#subpane-files-browse"
            type="button"
            role="tab"
            data-panel-id="panel-browse"
            data-i18n-title="subtabBrowseTitle"
            title="Просмотр структуры каталогов и файлов проекта">
      <i class="bi bi-folder2-open"></i>
      <span data-i18n="subtabBrowseLabel">Обзор файлов</span>
    </button>
  </div>
</div>
```

### 4.2. Разметка подменю блоков внутри панели (Уровень 2)

```html
<!-- Подменю блоков внутри панели. Выбранный блок добавляется в URL как #block-<id> -->
<div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom border-secondary border-opacity-25 flex-wrap gap-2">
  <div class="btn-group btn-group-sm" id="files-blocks-nav" role="group">
    <button type="button" 
            class="btn btn-outline-secondary active d-flex align-items-center gap-1"
            id="btn-block-dir"
            data-block-id="block-dir"
            data-bs-toggle="pill"
            data-bs-target="#subpane-block-dir"
            data-i18n-title="blockDirTitle"
            title="Отображение текущего дерева файлов Git-репозитория">
      <i class="bi bi-folder-check"></i>
      <span data-i18n="blockDirLabel">Содержимое репозитория</span>
    </button>
    <button type="button" 
            class="btn btn-outline-secondary d-flex align-items-center gap-1"
            id="btn-block-track"
            data-block-id="block-track"
            data-bs-toggle="pill"
            data-bs-target="#subpane-block-track"
            data-i18n-title="blockTrackTitle"
            title="Добавить новые файлы и папки в список отслеживания">
      <i class="bi bi-plus-circle"></i>
      <span data-i18n="blockTrackLabel">Добавление в слежение</span>
    </button>
  </div>
</div>
```

---

## 5. Стандарт локализации (i18n)

Каждая кнопка обязана содержать пару ключей во всех 4 языковых файлах (`ru.json`, `en.json`, `he.json`, `uk.json`):
1. `*Label` — текст кнопки для атрибута `data-i18n`;
2. `*Title` — исчерпывающий статический текст подсказки для атрибутов `data-i18n-title` и `title`.

Пример структуры в словарях:
```json
{
  "subtabBrowseLabel": "Обзор файлов",
  "subtabBrowseTitle": "Просмотр структуры каталогов, метаданных и содержимого файлов проекта",
  "blockDirLabel": "Содержимое репозитория (Git)",
  "blockDirTitle": "Отображение текущего рабочего дерева и статуса файлов репозитория",
  "blockTrackLabel": "Добавление файлов в слежение",
  "blockTrackTitle": "Выбор файлов и каталогов с диска для добавления в индекс и версионирование"
}
```

---

## 6. Принцип изоляции запросов (Active-Only API Fetching)

> [!IMPORTANT]
> **Неактивная панель или блок НЕ ДОЛЖНЫ опрашивать API.**

1. При инициализации вкладки запросы отправляются **строго для активной панели/блока**, определённого из URL-хэша;
2. При переключении панели или блока:
   - Немедленно останавливаются таймеры (`clearInterval`, `stopAutoRefresh()`) деактивируемого экрана;
   - Запускается первичная загрузка данных для вновь активированного экрана;
3. Если вкладка свернута или не видна на экране, глобальный опрос останавливается.

---

## 7. Перетаскиваемость кнопок (Drag & Drop) и локальные файлы `menu_config.json`

В соответствии с правилом модульности и кастомизации навигации:
1. **Локальный файл конфигурации меню:**
   Каждая вкладка, содержащая меню субпанелей или подменю блоков, **ОБЯЗАНА** хранить конфигурационный файл `menu_config.json` непосредственно в своей директории (`apps/*/api/webgui/tab_<tab_id>/menu_config.json`).
   
2. **Структура `menu_config.json`:**
   - `$schema`: `"webgui-menu-v1"`;
   - `tab_id`: `"tab-<name>"`;
   - `draggable`: `true` (признак поддержки горизонтального перетаскивания);
   - `subtabs`: конфигурация меню субпанелей (Уровень 1) с `nav_id`, `storage_key` и массивом `items`;
   - `blocks`: конфигурация подменю блоков (Уровень 2).

3. **Горизонтальное перетаскивание (влево <-> вправо):**
   - Кнопки меню поддерживают HTML5 Drag & Drop (`menu_dnd.js`, класс `.menu-btn-draggable`);
   - При перемещении кнопок пользователем их порядок мгновенно перестраивается в DOM;
   - Новый порядок автоматически сохраняется в `localStorage` браузера (`webgui_menu_order_<storage_key>`);
   - Порядок может быть персистентно сохранен в `menu_config.json` на диске через `PUT /api/v1/tabs/{tab_id}/menu-config`.
