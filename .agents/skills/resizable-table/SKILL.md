---
name: resizable-table
description: "Инженерное руководство и стандарт создания интерактивных веб-таблиц с ползунком растягивания высоты (resizer), пропорциональным расчетом высоты под количество строк и поддержкой режима 100%."
---

<!-- Updated: 2026-11-01 11:45:00 -->

# Навык: Создание адаптивных таблиц с ползунком изменения высоты и пропорциональным авто-расчетом

## 📌 1. Назначение и концепция

В интерфейсах **AI Windows Admin / Test Computer** (например, `http://localhost:8001/tc#tab-system-control#activity`) стандарт отображения табличных данных решает две ключевые UX-задачи:
1. **Компактность и пропорциональность**: пустая таблица или таблица с 1–3 строками не должна оставлять гигантское пустое поле, а автоматически сжимается до высоты содержимого. При добавлении строк высота контейнера плавно растет пропорционально их количеству до заданного безопасного лимита (`maxAutoHeight`).
2. **Гибкий пользовательский контроль**: оператор может потянуть нижний ползунок (drag-and-drop ресайзер) на нужную высоту, раскрыть таблицу на 100% без внутреннего вертикального скроллера либо сбросить размер к автоматическому двойным кликом.

В кодовой базе проекта этот функционал представлен двумя уровнями:
- **Локальный модульный уровень** (пример в `tab_system_control`): контейнеры `#scc-activity-table-container` и `#scc-activity-table-resizer`, обслуживаемые через `setupResizer()` в `apps/windows/api/webgui/tab_system_control/common/ui_utils.js`.
- **Глобальный уровень дизайн-системы**: универсальный движок `TableResizerInstance` в `apps/windows/api/webgui/js/table-resizer.js` (`window.setupTableResizer`, `window.autoAdjustTableHeight`).

---

## 🏗️ 2. Анатомия DOM-структуры таблицы

Каждая адаптивная таблица компонуется из 3 обязательных блоков:
1. **Шапка панели / панели управления** (опционально с кнопкой разворачивания `100%` и счетчиком/обновлением).
2. **Скроллируемый контейнер таблицы** (`.table-responsive` с ограничениями `min-height`, `max-height` и `overflow-y: auto`).
3. **Интерактивный ползунок ресайзера** (`.slc-table-resizer` или `.sys-table-resizer`) с маркером захвата (`grip`).

### Пример разметки (по образцу Activity Log):

```html
<!-- Контейнер панели таблицы -->
<div class="p-3" id="slc-activity-container">
  
  <!-- Панель управления и заголовок -->
  <div class="d-flex justify-content-between align-items-center mb-2">
    <span class="fw-bold">
      <i class="bi bi-journal-text me-1 text-primary"></i>
      <span data-i18n="systemControl.activityTitle">Журнал активности</span>
    </span>
    <div class="d-flex align-items-center gap-2">
      <!-- Кнопка раскрытия на 100% (опционально) -->
      <button class="btn btn-xs btn-outline-secondary btn-table-expand-100" 
              data-target-container="scc-activity-table-container"
              title="Раскрыть таблицу на 100% высоты без скроллера">
        100%
      </button>
      <!-- Кнопка обновления данных -->
      <button class="btn btn-sm btn-outline-secondary rounded-pill px-3" id="btn-scc-refresh-logs">
        <i class="bi bi-arrow-clockwise me-1"></i>
        <span data-i18n="systemControl.btnRefresh">Обновить</span>
      </button>
    </div>
  </div>

  <!-- Скроллируемый контейнер таблицы -->
  <div class="table-responsive" 
       id="scc-activity-table-container" 
       data-resizable-table="true"
       style="min-height: 200px; max-height: calc(100vh - 310px); overflow-y: auto;">
    <table class="slc-table">
      <thead>
        <tr>
          <th style="width: 180px;">Время</th>
          <th style="width: 160px;">Действие</th>
          <th>Объект</th>
          <th style="width: 120px;">Статус</th>
          <th style="width: 30%;">Детали</th>
        </tr>
      </thead>
      <tbody id="scc-logs-tbody">
        <!-- Первоначальное состояние ожидания загрузки -->
        <tr>
          <td colspan="5" class="text-center text-muted p-3">
            Загрузка журнала активности...
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Ползунок изменения высоты (Resizer) -->
  <div class="slc-table-resizer" 
       id="scc-activity-table-resizer" 
       data-container-id="scc-activity-table-container"
       title="Потяните для изменения высоты таблицы (двойной клик — сброс)">
    <div class="slc-table-resizer-grip"></div>
  </div>

</div>
```

---

## 🎨 3. Стилизация (CSS)

> [!IMPORTANT]
> Все цвета и границы оформляются исключительно через CSS-переменные дизайн-системы (`var(--surface-2)`, `var(--border-color)`, `var(--text-color)`). Никаких жестко закодированных HEX/RGB!

```css
/* Ползунок ресайзера */
.slc-table-resizer,
.sys-table-resizer {
  height: 8px;
  cursor: row-resize;
  background: var(--surface-2);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease;
  user-select: none;
}

/* Состояние при наведении курсора и во время перетаскивания */
.slc-table-resizer:hover,
.slc-table-resizer.resizing,
.sys-table-resizer:hover,
.sys-table-resizer.resizing {
  background: var(--primary, #0ea5e9) !important;
}

/* Центральный маркер (grip) ползунка */
.slc-table-resizer-grip,
.sys-table-resizer-grip {
  width: 36px;
  height: 3px;
  background: var(--border-strong, #666);
  border-radius: 2px;
}

/* Подсветка активной строки при наведении и выборе */
.slc-table tr:hover td {
  background: rgba(56, 189, 248, 0.06) !important;
}

.slc-table tr.table-active td {
  background: rgba(14, 165, 233, 0.18) !important;
  font-weight: 600;
}
```

---

## ⚙️ 4. Логика JavaScript

### 4.1. Алгоритм пропорционального расчета высоты по количеству строк

Расчет предотвращает появление пустот и одновременно ограничивает максимальную высоту:

```javascript
/**
 * Расчет оптимальной высоты контейнера пропорционально количеству строк.
 * 
 * @param {HTMLElement} container - DOM-элемент .table-responsive
 * @param {number} [forcedRowCount] - Принудительное число строк
 * @param {Object} [options] - Параметры высоты строк и заголовка
 */
export function calculateAdaptiveTableHeight(container, forcedRowCount, options = {}) {
  const minHeight = options.minHeight || 140;
  const maxAutoHeight = options.maxAutoHeight || 660;
  const rowHeight = options.rowHeight || 34;
  const headerHeight = options.headerHeight || 38;

  let count = 0;
  if (typeof forcedRowCount === 'number') {
    count = forcedRowCount;
  } else {
    const rows = container.querySelectorAll('tbody tr');
    // Игнорируем одиночные строки-заглушки (colspan) с сообщениями о загрузке или отсутствии данных
    if (rows.length === 1 && rows[0].querySelector('td[colspan]')) {
      count = 0;
    } else {
      count = rows.length;
    }
  }

  let calculatedH;
  if (count <= 0) {
    // Для пустой таблицы оставляем компактную высоту
    calculatedH = Math.min(180, minHeight + 30);
  } else if (count <= 3) {
    // Для малого числа строк задаем чуть больше простора на строку
    calculatedH = Math.max(minHeight, headerHeight + count * 42 + 15);
  } else {
    // Основная формула: шапка + строки * высота строки + отступы
    calculatedH = headerHeight + count * rowHeight + 16;
    calculatedH = Math.max(minHeight, Math.min(maxAutoHeight, calculatedH));
  }

  return calculatedH;
}
```

### 4.2. Инициализация ползунка (Drag, Drop, DoubleClick)

```javascript
/**
 * Настройка перетаскивания ползунка ресайзера высоты таблицы.
 * 
 * @param {string} resizerId - ID элемента-ползунка
 * @param {string} containerId - ID контейнера таблицы
 * @param {number} [defaultHeight=480] - Высота по умолчанию
 * @param {number} [minH=140] - Минимальная допустимая высота
 * @param {number} [maxH=1500] - Максимальная высота при растягивании
 */
export function setupResizer(resizerId, containerId, defaultHeight = 480, minH = 140, maxH = 1500) {
  const resizer = document.getElementById(resizerId);
  const container = document.getElementById(containerId);
  if (!resizer || !container || resizer._resizerBound) return;
  resizer._resizerBound = true;

  let startY = 0;
  let startHeight = 0;

  const onMouseMove = (e) => {
    const delta = e.clientY - startY;
    const newH = Math.max(minH, Math.min(maxH, startHeight + delta));
    container.style.maxHeight = 'none';
    container.style.height = `${newH}px`;
  };

  const onMouseUp = () => {
    resizer.classList.remove('resizing');
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);

    // Сохраняем пользовательский размер в localStorage
    try {
      localStorage.setItem(`tbl_height_${containerId}`, parseInt(container.style.height, 10));
    } catch (_) {}
  };

  resizer.onmousedown = (e) => {
    e.preventDefault();
    startY = e.clientY;
    startHeight = container.getBoundingClientRect().height || 
                  parseInt(window.getComputedStyle(container).height, 10) || 
                  defaultHeight;
    resizer.classList.add('resizing');
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // Двойной клик сбрасывает пользовательский размер и возвращает адаптивную высоту
  resizer.ondblclick = () => {
    try {
      localStorage.removeItem(`tbl_height_${containerId}`);
    } catch (_) {}
    container.style.height = '';
    container.style.maxHeight = '';
    
    // Пересчет высоты под текущие строки
    const newHeight = calculateAdaptiveTableHeight(container);
    container.style.height = `${newHeight}px`;
  };
}
```

### 4.3. Автоматическое отслеживание через MutationObserver

Чтобы таблица сама меняла высоту при поступлении новых порций данных (например, через WebSocket или REST polling), привязывается `MutationObserver`:

```javascript
export function observeTableRows(containerId) {
  const container = document.getElementById(containerId);
  const tbody = container?.querySelector('tbody');
  if (!tbody || tbody._observerBound) return;
  tbody._observerBound = true;

  let timer = null;
  const observer = new MutationObserver(() => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      // Если пользователь не зафиксировал размер вручную — адаптируем
      const isCustom = localStorage.getItem(`tbl_height_${containerId}`);
      if (!isCustom) {
        const h = calculateAdaptiveTableHeight(container);
        container.style.height = `${h}px`;
      }
    }, 50);
  });

  observer.observe(tbody, { childList: true, subtree: false });
}
```

---

## 🚀 5. Регламент внедрения в новую вкладку

При создании новой таблицы выполните следующие 4 шага:

1. **Разметка в HTML**:
   - Оберните `<table>` в `<div class="table-responsive" id="<name>-table-container">`.
   - Непосредственно под ним разместите `<div class="slc-table-resizer" id="<name>-table-resizer"><div class="slc-table-resizer-grip"></div></div>`.
2. **Подключение стилей**:
   - Убедитесь в наличии классов `.slc-table`, `.slc-table-resizer` и `.slc-table-resizer-grip` (либо глобальных `.sys-table-resizer`).
3. **Инициализация в `panel.js`**:
   - При инициализации панели вызовите:
     ```javascript
     setupResizer('<name>-table-resizer', '<name>-table-container', 480, 140, 1200);
     observeTableRows('<name>-table-container');
     ```
   - Либо используйте глобальный хелпер ядра:
     ```javascript
     window.setupTableResizer({ containerId: '<name>-table-container' });
     ```
4. **Рендеринг строк**:
   - При получении массива данных (например, `items`), отрендерите строки в `tbody.innerHTML`.
   - `MutationObserver` автоматически рассчитает пропорциональную высоту. При необходимости мгновенной подгонки вызовите:
     ```javascript
     window.autoAdjustTableHeight('<name>-table-container', items.length);
     ```
