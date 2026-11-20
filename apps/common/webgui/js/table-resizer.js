/**
 * =============================================================================
 * Process Name: Windows WebGUI - Universal Table Resizer & Adaptive Height
 * =============================================================================
 * Description:
 *   Универсальный модуль управления высотой, интерактивными ползунками и
 *   ссылкой раскрытия 100% для абсолютно всех таблиц веб-интерфейса ai-tc.
 *
 *   Функциональные возможности:
 *     1. Автоматическое обнаружение и подключение ко всем <table> в DOM
 *        (включая динамические вкладки, модальные окна и AJAX-таблицы).
 *     2. Если в таблице много строк (> 10 или превышает maxAutoHeight):
 *        - отображается нижний ползунок (.sys-table-resizer) для растягивания
 *          нижней границы вниз/вверх с сохранением высоты в localStorage;
 *        - в шапке таблицы (или панели) отображается ссылка «100%»,
 *          разворачивающая таблицу на все 100% строк без вертикального скроллера.
 *     3. Двойной клик по ползунку сбрасывает ручную высоту к авто-расчету.
 *     4. Автоматическое отслеживание изменений строк через MutationObserver.
 *
 * Usage Examples:
 *   JavaScript:
 *     window.setupTableResizer({ containerId: 'my-table-container' });
 *     window.autoAdjustTableHeight('my-table-container', rowCount);
 *     window.initAllTableResizers(document);
 *
 * File: table-resizer.js
 * Project: ai-tc
 * Package: apps.common.webgui.js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 15:45:00
 * =============================================================================
 */

(function () {
  'use strict';

  /** Хранилище активных экземпляров контроллеров таблиц: containerId -> TableResizerInstance */
  const resizersRegistry = new Map();

  /** Порог количества строк, после которого таблица считается длинной. */
  const MANY_ROWS_THRESHOLD = 10;

  /**
   * Подсчитывает фактическое количество строк данных в tbody таблицы.
   *
   * @param {HTMLElement} container
   * @returns {number}
   */
  function countTableRows(container) {
    const rows = container.querySelectorAll('tbody tr');
    if (rows.length === 1 && rows[0].querySelector('td[colspan]')) {
      return 0;
    }
    return rows.length;
  }

  /**
   * Класс контроллера изменения высоты таблицы и ссылки 100%.
   */
  class TableResizerInstance {
    constructor(options = {}) {
      this.container = typeof options.container === 'string'
        ? document.getElementById(options.container)
        : options.container;

      if (!this.container) return;

      this.containerId = this.container.id || `tbl-container-${Math.random().toString(36).slice(2, 9)}`;
      if (!this.container.id) this.container.id = this.containerId;

      this.isAutoDiscovered = Boolean(options.isAutoDiscovered);
      this.autoCreatedResizer = false;
      this.autoCreatedExpand = false;
      this.headerBar = null;

      const existingResizer = typeof options.resizer === 'string'
        ? document.getElementById(options.resizer)
        : (options.resizer || this.findResizerElement());

      if (existingResizer) {
        this.resizer = existingResizer;
      } else if (options.autoCreate !== false) {
        this.resizer = this.createResizerElement();
        this.autoCreatedResizer = Boolean(this.resizer);
      } else {
        this.resizer = null;
      }

      const existingExpand = typeof options.expandBtn === 'string'
        ? document.getElementById(options.expandBtn)
        : (options.expandBtn || this.findExpandButton());

      if (existingExpand) {
        this.expandBtn = existingExpand;
      } else if (options.autoCreate !== false) {
        this.expandBtn = this.createExpandButton();
        this.autoCreatedExpand = Boolean(this.expandBtn);
      } else {
        this.expandBtn = null;
      }

      this.minHeight = options.minHeight || 140;
      this.maxHeight = options.maxHeight || 1800;
      this.maxAutoHeight = options.maxAutoHeight || (this.isAutoDiscovered ? 440 : 660);
      this.rowHeight = options.rowHeight || 34;
      this.headerHeight = options.headerHeight || 38;
      this.manyRowsThreshold = options.manyRowsThreshold || MANY_ROWS_THRESHOLD;
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
      let el = document.querySelector(
        `.sys-table-resizer[data-container-id="${this.containerId}"], ` +
        `.slc-table-resizer[data-container-id="${this.containerId}"], ` +
        `.table-resizer[data-container-id="${this.containerId}"]`
      );
      if (el) return el;

      const next = this.container.nextElementSibling;
      if (next && (
        next.classList.contains('sys-table-resizer') ||
        next.classList.contains('slc-table-resizer') ||
        next.classList.contains('table-resizer')
      )) {
        return next;
      }

      const panel = this.container.closest('.sys-panel, .card, [data-panel-id]');
      if (panel && panel.querySelectorAll('table').length === 1) {
        el = panel.querySelector('.sys-table-resizer, .slc-table-resizer, .table-resizer');
        if (el) return el;
      }
      return null;
    }

    /**
     * Поиск существующей кнопки/ссылки 100% в шапке панели или по контейнеру.
     */
    findExpandButton() {
      if (this.containerId) {
        const directBtn =
          document.querySelector(`.btn-table-expand-100[data-target-container="${this.containerId}"]`) ||
          document.getElementById(`${this.containerId}-expand`) ||
          document.getElementById(`${this.containerId}-btn-table-expand`) ||
          (this.containerId === 'pm-table-container' ? document.getElementById('pm-btn-table-expand') : null);
        if (directBtn) return directBtn;
      }

      const panel = this.container.closest('.winadmin-panel, .sys-panel, .card, [data-panel-id]');
      if (panel && panel.querySelectorAll('table').length === 1) {
        return panel.querySelector('.btn-table-expand-100');
      }
      return null;
    }

    /**
     * Создание и вставка нижнего ползунка resizer непосредственно под контейнером.
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
     * Создание и вставка ссылки «100%» в шапку панели либо в компактную шапку таблицы.
     */
    createExpandButton() {
      if (!this.container || !this.container.parentNode) return null;

      const link = document.createElement('a');
      link.href = '#';
      link.setAttribute('role', 'button');
      link.className = 'btn btn-xs btn-outline-secondary btn-table-expand-100';
      link.id = `${this.containerId}-btn-table-expand`;
      link.setAttribute('data-target-container', this.containerId);
      link.title = 'Раскрыть таблицу на все 100% строк без скроллера';
      link.textContent = '100%';

      const panel = this.container.closest('.winadmin-panel, .sys-panel, .card, [data-panel-id]');
      const isSingleTablePanel = panel && panel.querySelectorAll('table').length === 1;
      const header = isSingleTablePanel ? panel.querySelector('.panel-header, .card-header') : null;

      if (header) {
        const actionsGroup = header.querySelector('.d-flex.align-items-center.gap-2, .d-flex.align-items-center, .card-header-actions');
        if (actionsGroup) {
          actionsGroup.insertBefore(link, actionsGroup.firstChild);
        } else {
          link.classList.add('ms-auto');
          header.appendChild(link);
        }
        return link;
      }

      // Если у таблицы нет внешней шапки панели — создаем компактную шапку таблицы
      const bar = document.createElement('div');
      bar.className = 'ut-table-header-bar';
      bar.setAttribute('data-for-container', this.containerId);
      bar.appendChild(link);
      this.container.parentNode.insertBefore(bar, this.container);
      this.headerBar = bar;
      return link;
    }

    /**
     * Управляет видимостью авто-созданных контролов (ползунок и ссылка 100%).
     *
     * @param {boolean} visible
     */
    setAutoControlsVisible(visible) {
      if (!this.isAutoDiscovered) return;
      if (this.autoCreatedResizer && this.resizer) {
        this.resizer.hidden = !visible;
      }
      if (this.autoCreatedExpand) {
        if (this.headerBar) {
          this.headerBar.hidden = !visible;
        } else if (this.expandBtn) {
          this.expandBtn.hidden = !visible;
        }
      }
    }

    /**
     * Инициализация событий, localStorage и MutationObserver.
     */
    init() {
      if (this.container._tableResizerBound) return;
      this.container._tableResizerBound = true;

      // Восстановление пользовательской высоты из localStorage
      try {
        const saved = localStorage.getItem(this.storageKey);
        if (saved) {
          const parsed = parseInt(saved, 10);
          if (!isNaN(parsed) && parsed >= this.minHeight && parsed <= this.maxHeight) {
            this.container.style.height = `${parsed}px`;
            this.container.style.maxHeight = 'none';
            this.container.style.overflowY = 'auto';
            this.customHeight = parsed;
            this.isCustomHeight = true;
          }
        }
      } catch (_) {}

      if (this.resizer) {
        this.resizer.setAttribute('data-container-id', this.containerId);
        this.setupDragEvents();
      }

      if (this.expandBtn && !this.expandBtn._expandBound) {
        this.expandBtn._expandBound = true;
        this.expandBtn.addEventListener('click', (e) => {
          e.preventDefault();
          this.toggle100();
        });
      }

      this.setupMutationObserver();

      if (!this.isCustomHeight) {
        this.autoAdjust();
      } else {
        this.setAutoControlsVisible(true);
      }
    }

    /**
     * Настройка перетаскивания ползунка (мышь и сенсорный экран).
     */
    setupDragEvents() {
      if (this.resizer._dragBound) return;
      this.resizer._dragBound = true;

      const onStart = (e) => {
        this.isDragging = true;
        this.startY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
        this.startHeight = this.container.getBoundingClientRect().height || this.maxAutoHeight;

        if (this.isExpanded100) {
          this.isExpanded100 = false;
          this.container.classList.remove('expanded-100');
          this.container.style.overflowY = 'auto';
          this.updateExpandBtnState(false);
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
        const newH = Math.max(this.minHeight, Math.min(this.maxHeight, this.startHeight + delta));

        this.container.style.height = `${newH}px`;
        this.container.style.maxHeight = 'none';
        this.container.style.overflowY = 'auto';
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
      this.resizer.addEventListener('dblclick', () => this.resetToAuto());
    }

    /**
     * Обновляет визуальное состояние кнопки/ссылки 100%.
     *
     * @param {boolean} active
     */
    updateExpandBtnState(active) {
      if (!this.expandBtn) return;
      if (active) {
        this.expandBtn.classList.add('active', 'btn-info', 'text-dark');
        this.expandBtn.classList.remove('btn-outline-secondary');
        this.expandBtn.setAttribute('aria-pressed', 'true');
        this.expandBtn.title = 'Свернуть таблицу к обычной высоте';
      } else {
        this.expandBtn.classList.remove('active', 'btn-info', 'text-dark');
        this.expandBtn.classList.add('btn-outline-secondary');
        this.expandBtn.setAttribute('aria-pressed', 'false');
        this.expandBtn.title = 'Раскрыть таблицу на все 100% строк без скроллера';
      }
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
      this.container.style.height = '';
      this.container.style.overflowY = 'auto';
      this.updateExpandBtnState(false);
      this.autoAdjust();
    }

    /**
     * Переключение режима 100% высоты без вертикального скроллера.
     */
    toggle100() {
      if (this.isExpanded100) {
        this.isExpanded100 = false;
        this.container.classList.remove('expanded-100');
        this.container.style.maxHeight = '';
        this.container.style.overflowY = 'auto';
        this.updateExpandBtnState(false);

        if (this.isCustomHeight && this.customHeight) {
          this.container.style.height = `${this.customHeight}px`;
          this.container.style.maxHeight = 'none';
        } else if (this.savedHeightBefore100) {
          this.container.style.height = `${this.savedHeightBefore100}px`;
        } else {
          this.autoAdjust();
        }
      } else {
        this.isExpanded100 = true;
        this.savedHeightBefore100 =
          this.container.getBoundingClientRect().height ||
          parseInt(this.container.style.height, 10) ||
          this.maxAutoHeight;

        this.container.classList.add('expanded-100');
        this.container.style.maxHeight = 'none';
        this.container.style.height = 'auto';
        this.container.style.overflowY = 'visible';
        this.updateExpandBtnState(true);
      }
    }

    /**
     * Наблюдатель за изменением содержимого tbody или заменой таблицы.
     */
    setupMutationObserver() {
      if (typeof MutationObserver === 'undefined') return;

      let debounceTimer = null;
      const onMutate = () => {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => this.autoAdjust(), 50);
      };

      const targetTbody = this.container.querySelector('tbody');
      const observeTarget = targetTbody || this.container;
      this.observer = new MutationObserver(onMutate);
      this.observer.observe(observeTarget, {
        childList: true,
        subtree: !targetTbody
      });
    }

    /**
     * Адаптивный расчет высоты таблицы пропорционально числу строк.
     *
     * @param {number} [forcedRowCount] - Принудительное количество строк.
     */
    autoAdjust(forcedRowCount) {
      if (this.isExpanded100) {
        this.container.style.maxHeight = 'none';
        this.container.style.height = 'auto';
        this.container.style.overflowY = 'visible';
        return;
      }

      if (this.isCustomHeight && this.customHeight) {
        this.setAutoControlsVisible(true);
        return;
      }

      const count = typeof forcedRowCount === 'number'
        ? forcedRowCount
        : countTableRows(this.container);

      const table = this.container.querySelector('table');
      const tableHeight = table ? table.scrollHeight : 0;

      // Для авто-обнаруженных таблиц: показываем ползунок и 100% только если строк много
      if (this.isAutoDiscovered) {
        const isLongTable = count > this.manyRowsThreshold || (tableHeight > this.maxAutoHeight + 24);
        if (!isLongTable) {
          this.container.style.height = '';
          this.container.style.maxHeight = '';
          this.setAutoControlsVisible(false);
          return;
        }

        this.container.style.overflowY = 'auto';
        this.container.style.maxHeight = 'none';
        this.container.style.height = `${this.maxAutoHeight}px`;
        this.setAutoControlsVisible(true);
        return;
      }

      // Для таблиц с явным data-resizable-table / .sys-table-resizer
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
   * Возвращает или создает скроллируемый контейнер для произвольной таблицы <table>.
   *
   * @param {HTMLTableElement} table
   * @returns {HTMLElement|null}
   */
  function ensureTableContainer(table) {
    if (!table || !table.parentElement) return null;

    // 1. Таблица уже внутри .table-responsive
    const resp = table.closest('.table-responsive');
    if (resp && resp.querySelectorAll('table').length === 1) {
      return resp;
    }

    // 2. Если родительский <div> содержит только эту таблицу — используем его напрямую
    const parent = table.parentElement;
    if (
      parent.tagName === 'DIV' &&
      parent.children.length === 1 &&
      !parent.classList.contains('card-body') &&
      !parent.classList.contains('modal-body') &&
      !parent.classList.contains('tab-pane')
    ) {
      parent.classList.add('table-responsive');
      return parent;
    }

    // 3. Оборачиваем таблицу в .table-responsive.ut-auto-table-container
    const wrapper = document.createElement('div');
    wrapper.className = 'table-responsive ut-auto-table-container';
    parent.insertBefore(wrapper, table);
    wrapper.appendChild(table);
    return wrapper;
  }

  /**
   * Настройка и регистрация контроллера для контейнера таблицы.
   *
   * @param {Object} options
   * @returns {TableResizerInstance|null}
   */
  function setupTableResizer(options) {
    if (!options) return null;
    const container = typeof options.container === 'string'
      ? document.getElementById(options.container)
      : (options.container || (options.containerId ? document.getElementById(options.containerId) : null));

    if (!container) return null;

    const id = container.id;
    if (id && resizersRegistry.has(id)) {
      const existing = resizersRegistry.get(id);
      if (options.resizer && !existing.resizer) {
        existing.resizer = typeof options.resizer === 'string' ? document.getElementById(options.resizer) : options.resizer;
        if (existing.resizer) existing.setupDragEvents();
      }
      if (options.expandBtn && !existing.expandBtn) {
        existing.expandBtn = typeof options.expandBtn === 'string' ? document.getElementById(options.expandBtn) : options.expandBtn;
        if (existing.expandBtn && !existing.expandBtn._expandBound) {
          existing.expandBtn._expandBound = true;
          existing.expandBtn.addEventListener('click', (e) => {
            e.preventDefault();
            existing.toggle100();
          });
        }
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
   *
   * @param {string|HTMLElement} containerOrId
   * @param {number} [rowCount]
   */
  function autoAdjustTableHeight(containerOrId, rowCount) {
    const id = typeof containerOrId === 'string' ? containerOrId : containerOrId?.id;
    if (!id) return;

    let inst = resizersRegistry.get(id);
    if (!inst) {
      const el = document.getElementById(id);
      if (el) inst = setupTableResizer({ container: el });
    }
    if (inst) inst.autoAdjust(rowCount);
  }

  /**
   * Автоматическое обнаружение и инициализация абсолютно всех таблиц
   * внутри переданного корневого элемента.
   *
   * @param {HTMLElement|Document} [root=document]
   */
  function initAllTableResizers(root = document) {
    if (!root || typeof root.querySelectorAll !== 'function') return;

    // 1. Явные ползунки .sys-table-resizer / .slc-table-resizer / .table-resizer
    root.querySelectorAll('.sys-table-resizer, .slc-table-resizer, .table-resizer').forEach((resizer) => {
      const containerId = resizer.getAttribute('data-container-id');
      let container = containerId ? document.getElementById(containerId) : null;
      if (!container) {
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

    // 2. Контейнеры с явным data-resizable-table или data-table-template
    root.querySelectorAll('[data-resizable-table], [data-table-template]').forEach((container) => {
      setupTableResizer({ container, autoCreate: true });
    });

    // 3. Все остальные <table> в DOM (универсальное покрытие)
    const allTables = root.tagName === 'TABLE' ? [root] : Array.from(root.querySelectorAll('table'));
    allTables.forEach((table) => {
      if (table.getAttribute('data-no-resize') === 'true') return;
      // Пропускаем вложенные таблицы внутри ячейки другой таблицы
      if (table.parentElement && table.parentElement.closest('td, th')) return;

      const existingBound = table.closest('.table-responsive');
      if (existingBound && existingBound._tableResizerBound) return;

      const container = ensureTableContainer(table);
      if (!container || container._tableResizerBound) return;

      setupTableResizer({
        container,
        autoCreate: true,
        isAutoDiscovered: true
      });
    });

    // 4. Синхронизация с универсальной сортировкой столбцов
    if (window.TableSorter && typeof window.TableSorter.initAll === 'function') {
      window.TableSorter.initAll(root);
    }
  }

  /**
   * Центральный шаблонизатор таблиц WebGUI (ai-tc).
   */
  const TableTemplate = {
    renderExpandButtonHtml(containerId, extraClass = '') {
      const cls = extraClass ? ` ${extraClass}` : '';
      return `<a href="#" role="button" class="btn btn-xs btn-outline-secondary btn-table-expand-100${cls}" id="${containerId}-btn-table-expand" data-target-container="${containerId}" title="Раскрыть таблицу на все 100% строк без скроллера">100%</a>`;
    },

    renderResizerHtml(containerId, extraClass = '') {
      const cls = extraClass ? ` ${extraClass}` : '';
      return `<div class="sys-table-resizer${cls}" id="${containerId}-resizer" data-container-id="${containerId}" title="Потяните для изменения высоты таблицы (двойной клик — авто-высота)"><div class="sys-table-resizer-grip"></div></div>`;
    },

    apply(containerOrId, options = {}) {
      return setupTableResizer({ container: containerOrId, autoCreate: true, ...options });
    },

    initAll(root = document) {
      initAllTableResizers(root);
    }
  };

  // Глобальный MutationObserver для автоматического охвата всех динамически добавляемых таблиц
  let globalDomObserver = null;
  let pendingNodes = new Set();
  let observerTimer = null;

  function startGlobalTableObserver() {
    if (globalDomObserver || typeof MutationObserver === 'undefined' || !document.body) return;

    globalDomObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;
          if (
            node.classList.contains('sys-table-resizer') ||
            node.classList.contains('ut-table-header-bar') ||
            node.classList.contains('ut-auto-table-container')
          ) {
            continue;
          }
          if (node.tagName === 'TABLE' || (node.querySelector && node.querySelector('table'))) {
            pendingNodes.add(node);
          }
        }
      }

      if (pendingNodes.size > 0 && !observerTimer) {
        observerTimer = setTimeout(() => {
          const batch = Array.from(pendingNodes);
          pendingNodes.clear();
          observerTimer = null;
          batch.forEach((el) => {
            if (el && el.isConnected) initAllTableResizers(el);
          });
        }, 80);
      }
    });

    globalDomObserver.observe(document.body, { childList: true, subtree: true });
  }

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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initAllTableResizers(document);
      startGlobalTableObserver();
    });
  } else {
    setTimeout(() => {
      initAllTableResizers(document);
      startGlobalTableObserver();
    }, 60);
  }

  /**
   * Пересчитывает адаптивную высоту для уже инициализированных таблиц внутри видимого корня.
   *
   * @param {HTMLElement|Document} root
   */
  function refreshTablesInRoot(root) {
    if (!root || typeof root.querySelectorAll !== 'function') return;
    initAllTableResizers(root);
    resizersRegistry.forEach((inst) => {
      if (inst && inst.container && root.contains(inst.container)) {
        inst.autoAdjust();
      }
    });
  }

  document.addEventListener('tab:activated', (e) => {
    const tabId = e.detail?.tabId;
    if (tabId) {
      const tabPane = document.getElementById(tabId);
      if (tabPane) refreshTablesInRoot(tabPane);
    }
  });

  document.addEventListener('shown.bs.modal', (e) => {
    if (e.target) refreshTablesInRoot(e.target);
  });

  document.addEventListener('shown.bs.tab', () => {
    refreshTablesInRoot(document);
  });
})();
