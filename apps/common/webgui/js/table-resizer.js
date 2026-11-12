/**
 * =============================================================================
 * Process Name: Windows WebGUI - Universal Table Resizer & Adaptive Height
 * =============================================================================
 * Description:
 *   Универсальный модуль управления высотой и интерактивными ползунками таблиц
 *   для всех интерфейсов Test Computer / AI Windows Admin.
 *
 *   Функциональные возможности:
 *     1. Пропорциональное адаптивное увеличение высоты таблицы под объем данных.
 *     2. Интерактивный ползунок (.sys-table-resizer) для ручного растягивания
 *        и сжатия высоты с сохранением настроек пользователя в localStorage.
 *     3. Кнопка "100%" (.btn-table-expand-100) в заголовке панели для мгновенного
 *        раскрытия таблицы на полную высоту содержимого без вертикального скроллера.
 *     4. Двойной клик по ползунку ресайзера сбрасывает кастомную высоту и
 *        возвращает адаптивный автоматический расчет.
 *     5. Автоматическое отслеживание изменений строк через MutationObserver.
 *
 * Usage Examples:
 *   HTML:
 *     <button class="btn btn-xs btn-outline-secondary btn-table-expand-100" id="btn-top-expand">100%</button>
 *     <div class="table-responsive" id="my-table-container"><table>...</table></div>
 *     <div class="sys-table-resizer" data-container-id="my-table-container">
 *       <div class="sys-table-resizer-grip"></div>
 *     </div>
 *
 *   JavaScript:
 *     window.setupTableResizer({ containerId: 'my-table-container' });
 *     window.autoAdjustTableHeight('my-table-container', rowCount);
 *
 * File: table-resizer.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 15:05:00
 * =============================================================================
 */

(function () {
  'use strict';

  /** Хранилище активных экземпляров контроллеров таблиц: containerId -> TableResizerInstance */
  const resizersRegistry = new Map();

  /**
   * Класс контроллера изменения высоты таблицы.
   */
  class TableResizerInstance {
    constructor(options = {}) {
      this.container = typeof options.container === 'string'
        ? document.getElementById(options.container)
        : options.container;

      if (!this.container) return;

      this.containerId = this.container.id || `tbl-container-${Math.random().toString(36).slice(2, 9)}`;
      if (!this.container.id) this.container.id = this.containerId;

      this.resizer = typeof options.resizer === 'string'
        ? document.getElementById(options.resizer)
        : (options.resizer || this.findResizerElement() || (options.autoCreate !== false ? this.createResizerElement() : null));

      this.expandBtn = typeof options.expandBtn === 'string'
        ? document.getElementById(options.expandBtn)
        : (options.expandBtn || this.findExpandButton() || (options.autoCreate !== false ? this.createExpandButton() : null));

      this.minHeight = options.minHeight || 140;
      this.maxHeight = options.maxHeight || 1200;
      this.maxAutoHeight = options.maxAutoHeight || 660;
      this.rowHeight = options.rowHeight || 34;
      this.headerHeight = options.headerHeight || 38;
      this.storageKey = options.storageKey || `sys_tbl_height_${this.containerId}`;

      this.isExpanded100 = false;
      this.isCustomHeight = false;
      this.customHeight = null;
      this.savedHeightBefore100 = null;
      this.isDragging = false;
      this.startY = 0;
      this.startHeight = 0;
      this.observer = null;

      this.init();
    }
    /**
     * Поиск элемента ползунка resizer рядом с контейнером.
     */
    findResizerElement() {
      // 1. Поиск по data-container-id
      let el = document.querySelector(`.sys-table-resizer[data-container-id="${this.containerId}"], .slc-table-resizer[data-container-id="${this.containerId}"], .table-resizer[data-container-id="${this.containerId}"]`);
      if (el) return el;

      // 2. Следующий сосед
      if (this.container.nextElementSibling && (this.container.nextElementSibling.classList.contains('sys-table-resizer') || this.container.nextElementSibling.classList.contains('slc-table-resizer') || this.container.nextElementSibling.classList.contains('table-resizer'))) {
        return this.container.nextElementSibling;
      }
      // 3. Внутри родительской панели
      const panel = this.container.closest('.sys-panel, .card, [data-panel-id]');
      if (panel) {
        el = panel.querySelector('.sys-table-resizer, .slc-table-resizer, .table-resizer');
        if (el) return el;
      }
      return null;
    }
    /**
     * Поиск кнопки 100% в шапке панели или по контейнеру.
     */
    findExpandButton() {
      if (this.containerId) {
        const directBtn = document.querySelector(`.btn-table-expand-100[data-target-container="${this.containerId}"]`) ||
                          document.getElementById(`${this.containerId}-expand`) ||
                          (this.containerId === 'pm-table-container' ? document.getElementById('pm-btn-table-expand') : null);
        if (directBtn) return directBtn;
      }
      const panel = this.container.closest('.winadmin-panel, .sys-panel, .card, [data-panel-id]');
      if (panel) {
        return panel.querySelector('.btn-table-expand-100');
      }
      return null;
    }
    /**
     * Создание и вставка ползунка resizer через центральный шаблонизатор.
     */
    createResizerElement() {
      if (!this.container || !this.container.parentNode) return null;
      const resizer = document.createElement('div');
      resizer.className = 'sys-table-resizer';
      resizer.id = `${this.containerId}-resizer`;
      resizer.setAttribute('data-container-id', this.containerId);
      resizer.title = 'Потяните для изменения высоты таблицы (двойной клик — авто-высота)';
      resizer.innerHTML = '<div class="sys-table-resizer-grip"></div>';
      if (this.container.nextSibling) {
        this.container.parentNode.insertBefore(resizer, this.container.nextSibling);
      } else {
        this.container.parentNode.appendChild(resizer);
      }
      return resizer;
    }
    /**
     * Создание и вставка кнопки 100% в шапку панели через центральный шаблонизатор.
     */
    createExpandButton() {
      if (!this.container) return null;
      const panel = this.container.closest('.winadmin-panel, .sys-panel, .card, [data-panel-id]');
      if (!panel) return null;
      const header = panel.querySelector('.panel-header, .card-header');
      if (!header) return null;

      const btn = document.createElement('button');
      btn.className = 'btn btn-xs btn-outline-secondary btn-table-expand-100';
      btn.id = `${this.containerId}-btn-table-expand`;
      btn.setAttribute('data-target-container', this.containerId);
      btn.title = 'Раскрыть таблицу на 100% высоты без скроллера';
      btn.textContent = '100%';

      const actionsGroup = header.querySelector('.d-flex.align-items-center.gap-2, .d-flex.align-items-center, .card-header-actions');
      if (actionsGroup) {
        actionsGroup.insertBefore(btn, actionsGroup.firstChild);
      } else {
        header.appendChild(btn);
      }
      return btn;
    }
    /**
     * Инициализация событий, localStorage и MutationObserver.
     */
    init() {
      if (this.container._tableResizerBound) return;
      this.container._tableResizerBound = true;

      // Восстановление высоты из localStorage
      try {
        const saved = localStorage.getItem(this.storageKey);
        if (saved) {
          const parsed = parseInt(saved, 10);
          if (!isNaN(parsed) && parsed >= this.minHeight && parsed <= this.maxHeight) {
            this.container.style.height = `${parsed}px`;
            this.customHeight = parsed;
            this.isCustomHeight = true;
          }
        }
      } catch (_) {}

      // Привязка событий перетаскивания ползунка
      if (this.resizer) {
        this.resizer.setAttribute('data-container-id', this.containerId);
        this.setupDragEvents();
      }
      // Привязка кнопки 100%
      if (this.expandBtn) {
        this.expandBtn.addEventListener('click', (e) => {
          e.preventDefault();
          this.toggle100();
        });
      }
      // Наблюдатель за обновлением строк tbody
      this.setupMutationObserver();

      // Начальный авто-расчет при отсутствии кастомной высоты
      if (!this.isCustomHeight) {
        this.autoAdjust();
      }
    }
    /**
     * Настройка перетаскивания ползунка мышь/тач.
     */
    setupDragEvents() {
      const onStart = (e) => {
        this.isDragging = true;
        this.startY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
        this.startHeight = this.container.getBoundingClientRect().height;

        if (this.isExpanded100) {
          this.isExpanded100 = false;
          this.container.classList.remove('expanded-100');
          if (this.expandBtn) {
            this.expandBtn.classList.remove('active', 'btn-info', 'text-dark');
            this.expandBtn.classList.add('btn-outline-secondary');
            this.expandBtn.title = 'Раскрыть таблицу на 100% высоты без скроллера';
          }
        }
        this.resizer.classList.add('resizing');
        document.body.style.cursor = 'row-resize';
        document.body.style.userSelect = 'none';

        window.addEventListener('mousemove', onMove, { passive: false });
        window.addEventListener('mouseup', onEnd);
        window.addEventListener('touchmove', onMove, { passive: false });
        window.addEventListener('touchend', onEnd);
        e.preventDefault();
      };
      const onMove = (e) => {
        if (!this.isDragging) return;
        const currentY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : null);
        if (currentY === null) return;

        const delta = currentY - this.startY;
        let newH = this.startHeight + delta;
        newH = Math.max(this.minHeight, Math.min(this.maxHeight, newH));

        this.container.style.height = `${newH}px`;
        this.container.style.maxHeight = 'none';
      };
      const onEnd = () => {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.resizer.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onEnd);
        window.removeEventListener('touchmove', onMove);
        window.removeEventListener('touchend', onEnd);

        const finalH = parseInt(this.container.style.height, 10);
        if (!isNaN(finalH)) {
          this.isCustomHeight = true;
          this.customHeight = finalH;
          try {
            localStorage.setItem(this.storageKey, String(finalH));
          } catch (_) {}
        }
      };
      this.resizer.addEventListener('mousedown', onStart);
      this.resizer.addEventListener('touchstart', onStart, { passive: false });

      // Двойной клик сбрасывает сохраненный размер
      this.resizer.addEventListener('dblclick', () => {
        this.resetToAuto();
      });
    }
    /**
     * Сброс пользовательской высоты и возврат к авто-расчету.
     */
    resetToAuto() {
      this.isCustomHeight = false;
      this.customHeight = null;
      this.isExpanded100 = false;
      try {
        localStorage.removeItem(this.storageKey);
      } catch (_) {}

      this.container.classList.remove('expanded-100');
      this.container.style.maxHeight = '';
      this.container.style.overflowY = 'auto';

      if (this.expandBtn) {
        this.expandBtn.classList.remove('active', 'btn-info', 'text-dark');
        this.expandBtn.classList.add('btn-outline-secondary');
        this.expandBtn.title = 'Раскрыть таблицу на 100% высоты без скроллера';
      }
      this.autoAdjust();
    }
    /**
     * Переключение режима 100% высоты без скроллера.
     */
    toggle100() {
      if (this.isExpanded100) {
        // Выключение режима 100%
        this.isExpanded100 = false;
        this.container.classList.remove('expanded-100');
        this.container.style.maxHeight = '';
        this.container.style.overflowY = 'auto';

        if (this.expandBtn) {
          this.expandBtn.classList.remove('active', 'btn-info', 'text-dark');
          this.expandBtn.classList.add('btn-outline-secondary');
          this.expandBtn.title = 'Раскрыть таблицу на 100% высоты без скроллера';
        }
        if (this.isCustomHeight && this.customHeight) {
          this.container.style.height = `${this.customHeight}px`;
        } else if (this.savedHeightBefore100) {
          this.container.style.height = `${this.savedHeightBefore100}px`;
        } else {
          this.autoAdjust();
        }
      } else {
        // Включение режима 100%
        this.isExpanded100 = true;
        this.savedHeightBefore100 = this.container.getBoundingClientRect().height || parseInt(this.container.style.height, 10) || 320;
        this.container.classList.add('expanded-100');

        const table = this.container.querySelector('table');
        const fullContentH = Math.max(
          table ? table.scrollHeight : 0,
          this.container.scrollHeight,
          this.minHeight
        );

        this.container.style.maxHeight = 'none';
        this.container.style.height = `${fullContentH + 8}px`;
        this.container.style.overflowY = 'visible';

        if (this.expandBtn) {
          this.expandBtn.classList.add('active', 'btn-info', 'text-dark');
          this.expandBtn.classList.remove('btn-outline-secondary');
          this.expandBtn.title = 'Свернуть таблицу к обычной высоте';
        }
      }
    }
    /**
     * Наблюдатель за изменением содержимого tbody.
     */
    setupMutationObserver() {
      const targetTbody = this.container.querySelector('tbody');
      if (!targetTbody || typeof MutationObserver === 'undefined') return;

      let debounceTimer = null;
      this.observer = new MutationObserver(() => {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          this.autoAdjust();
        }, 40);
      });

      this.observer.observe(targetTbody, { childList: true, subtree: false });
    }
    /**
     * Адаптивный расчет высоты таблицы пропорционально числу строк.
     * @param {number} [forcedRowCount] - Принудительное количество строк
     */
    autoAdjust(forcedRowCount) {
      if (this.isExpanded100) {
        // В режиме 100% всегда обновляем высоту под полный scrollHeight
        const table = this.container.querySelector('table');
        const fullContentH = Math.max(
          table ? table.scrollHeight : 0,
          this.container.scrollHeight,
          this.minHeight
        );
        this.container.style.maxHeight = 'none';
        this.container.style.height = `${fullContentH + 8}px`;
        return;
      }
      // Если пользователь вручную зафиксировал высоту ползунком — не перебиваем
      if (this.isCustomHeight && this.customHeight) {
        return;
      }
      let count = 0;
      if (typeof forcedRowCount === 'number') {
        count = forcedRowCount;
      } else {
        const rows = this.container.querySelectorAll('tbody tr');
        // Отсекаем одиночные строки-заглушки типа "Ожидание потока...", "Нет данных"
        if (rows.length === 1) {
          const firstRow = rows[0];
          if (firstRow.querySelector('td[colspan]')) {
            count = 0;
          } else {
            count = 1;
          }
        } else {
          count = rows.length;
        }
      }
      let calculatedH;
      if (count <= 0) {
        calculatedH = Math.min(180, this.minHeight + 30);
      } else if (count <= 3) {
        calculatedH = Math.max(this.minHeight, this.headerHeight + count * 42 + 15);
      } else {
        calculatedH = this.headerHeight + count * this.rowHeight + 16;
        calculatedH = Math.max(this.minHeight, Math.min(this.maxAutoHeight, calculatedH));
      }
      this.container.style.height = `${calculatedH}px`;
    }
  }
  /**
   * Настройка и регистрация контроллера для контейнера таблицы.
   * @param {Object} options 
   * @returns {TableResizerInstance}
   */
  function setupTableResizer(options) {
    if (!options) return null;
    const container = typeof options.container === 'string'
      ? document.getElementById(options.container)
      : (options.container || (options.containerId ? document.getElementById(options.containerId) : null));

    if (!container) return null;

    const id = container.id;
    if (resizersRegistry.has(id)) {
      const existing = resizersRegistry.get(id);
      if (options.resizer && !existing.resizer) {
        existing.resizer = typeof options.resizer === 'string' ? document.getElementById(options.resizer) : options.resizer;
        existing.setupDragEvents();
      }
      if (options.expandBtn && !existing.expandBtn) {
        existing.expandBtn = typeof options.expandBtn === 'string' ? document.getElementById(options.expandBtn) : options.expandBtn;
        existing.expandBtn?.addEventListener('click', (e) => { e.preventDefault(); existing.toggle100(); });
      }
      return existing;
    }
    const instance = new TableResizerInstance({
      ...options,
      container,
      resizer: options.resizer || options.resizerId,
      expandBtn: options.expandBtn || options.expandBtnId
    });

    if (instance.containerId) {
      resizersRegistry.set(instance.containerId, instance);
    }
    return instance;
  }
  /**
   * Адаптивная подгонка высоты для зарегистрированного контейнера.
   * @param {string|HTMLElement} containerOrId 
   * @param {number} [rowCount] 
   */
  function autoAdjustTableHeight(containerOrId, rowCount) {
    const id = typeof containerOrId === 'string' ? containerOrId : containerOrId?.id;
    if (!id) return;

    let inst = resizersRegistry.get(id);
    if (!inst) {
      const el = document.getElementById(id);
      if (el) {
        inst = setupTableResizer({ container: el });
      }
    }
    if (inst) {
      inst.autoAdjust(rowCount);
    }
  }
  /**
   * Автоматическое обнаружение и инициализация всех таблиц с ползунками
   * внутри переданного корневого элемента.
   * @param {HTMLElement|Document} [root=document] 
   */
  function initAllTableResizers(root = document) {
    if (!root || typeof root.querySelectorAll !== 'function') return;

    // 1. Поиск всех явных ползунков .sys-table-resizer
    const resizers = root.querySelectorAll('.sys-table-resizer, .slc-table-resizer, .table-resizer');
    resizers.forEach((resizer) => {
      const containerId = resizer.getAttribute('data-container-id');
      let container = containerId ? document.getElementById(containerId) : null;
      if (!container) {
        // Предыдущий элемент .table-responsive
        let prev = resizer.previousElementSibling;
        while (prev) {
          if (prev.classList.contains('table-responsive')) {
            container = prev;
            break;
          }
          prev = prev.previousElementSibling;
        }
      }
      if (container) {
        setupTableResizer({ container, resizer });
      }
    });

    // 2. Поиск таблиц с атрибутом data-resizable-table или data-table-template
    const resizableContainers = root.querySelectorAll('[data-resizable-table], [data-table-template]');
    resizableContainers.forEach((container) => {
      setupTableResizer({ container, autoCreate: true });
    });
  }
  /**
   * Центральный шаблонизатор таблиц WebGUI (AI Windows Admin).
   * Обеспечивает стандартизацию всех таблиц системы:
   * - Кнопка "100%" (.btn-table-expand-100) для полного разворачивания без внутреннего скроллера
   * - Адаптивный скроллируемый контейнер (.table-responsive[data-resizable-table="true"])
   * - Нижний интерактивный ползунок (.sys-table-resizer) для изменения высоты
   */
  const TableTemplate = {
    /**
     * Возвращает HTML кнопки 100%.
     * @param {string} containerId - ID контейнера таблицы.
     * @param {string} [extraClass=''] - Дополнительные CSS классы.
     * @returns {string}
     */
    renderExpandButtonHtml(containerId, extraClass = '') {
      const cls = extraClass ? ` ${extraClass}` : '';
      return `<button class="btn btn-xs btn-outline-secondary btn-table-expand-100${cls}" id="${containerId}-btn-table-expand" data-target-container="${containerId}" title="Раскрыть таблицу на 100% высоты без скроллера">100%</button>`;
    },

    /**
     * Возвращает HTML нижнего ползунка ресайзера.
     * @param {string} containerId - ID контейнера таблицы.
     * @param {string} [extraClass=''] - Дополнительные CSS классы.
     * @returns {string}
     */
    renderResizerHtml(containerId, extraClass = '') {
      const cls = extraClass ? ` ${extraClass}` : '';
      return `<div class="sys-table-resizer${cls}" id="${containerId}-resizer" data-container-id="${containerId}" title="Потяните для изменения высоты таблицы (двойной клик — авто-высота)"><div class="sys-table-resizer-grip"></div></div>`;
    },

    /**
     * Применяет центральный шаблон к таблице или контейнеру,
     * гарантируя наличие кнопки 100% и ползунка-ресайзера.
     * @param {string|HTMLElement} containerOrId - Контейнер таблицы или его ID.
     * @param {Object} [options={}] - Настройки ресайзера.
     * @returns {TableResizerInstance}
     */
    apply(containerOrId, options = {}) {
      return setupTableResizer({ container: containerOrId, autoCreate: true, ...options });
    },

    /**
     * Инициализирует центральный шаблонизатор для всех таблиц в корневом элементе.
     * @param {HTMLElement|Document} [root=document]
     */
    initAll(root = document) {
      initAllTableResizers(root);
    }
  };

  // Экспорт в глобальный контекст window
  window.TableTemplate = TableTemplate;
  window.TableResizerHelper = {
    instances: resizersRegistry,
    setup: setupTableResizer,
    autoAdjust: autoAdjustTableHeight,
    initAll: initAllTableResizers,
    template: TableTemplate,
    apply: TableTemplate.apply
  };

  window.setupTableResizer = setupTableResizer;
  window.autoAdjustTableHeight = autoAdjustTableHeight;
  window.initAllTableResizers = initAllTableResizers;

  // Автоматический запуск при готовности страницы
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initAllTableResizers(document));
  } else {
    setTimeout(() => initAllTableResizers(document), 60);
  }

  // Автоматическая инициализация при переключении вкладок
  document.addEventListener('tab:activated', (e) => {
    const tabId = e.detail?.tabId;
    if (tabId) {
      const tabPane = document.getElementById(tabId);
      if (tabPane) {
        initAllTableResizers(tabPane);
      }
    }
  });
})();
