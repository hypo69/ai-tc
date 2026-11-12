/**
 * =============================================================================
 * Process Name: Common WebGUI - Universal Table Templater (TableTemplate)
 * =============================================================================
 * Description:
 *   Центральный шаблонизатор адаптивных интерактивных таблиц для экосистемы
 *   AI Windows Admin и Test Computer.
 *
 *   Функционал:
 *     1. Генерация стандартной DOM-триады таблицы (шапка с тумблером 100%,
 *        адаптивный скроллируемый контейнер, нижний ползунок-ресайзер).
 *     2. Пропорциональный авто-расчет высоты контейнера под объем строк.
 *     3. Ручной drag-and-drop ресайз с фиксацией размера в localStorage.
 *     4. Режим 100% высоты без скроллера (.expanded-100).
 *     5. Сброс к авто-высоте по двойному клику на ползунок.
 *     6. Автоматическая инъекция недостающих элементов управления (100% и resizer).
 *
 * Usage Examples:
 *   HTML:
 *     <div id="my-table-slot"></div>
 *
 *   JavaScript:
 *     const html = TableTemplate.render({
 *       id: 'winadmin-groups',
 *       title: 'Группы безопасности',
 *       icon: 'bi-diagram-3',
 *       columns: ['Имя', 'SID', 'Тип', 'Действия']
 *     });
 *     document.getElementById('my-table-slot').innerHTML = html;
 *     TableTemplate.apply('winadmin-groups-table-container');
 *
 * File: table-template.js
 * Project: ai-windows-admin
 * Package: apps.common.webgui.js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 16:25:00
 * =============================================================================
 */

(function () {
  'use strict';

  /**
   * Экранирование HTML.
   * @param {string} str 
   * @returns {string}
   */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Центральный объект шаблонизатора таблиц.
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
     * Рендеринг стандартной шапки панели таблицы.
     * @param {Object} options 
     * @returns {string}
     */
    renderHeader(options = {}) {
      const {
        id = 'table',
        title = 'Таблица',
        icon = 'bi-table',
        badgeText = '0 записей',
        searchPlaceholder = 'Поиск...',
        hasSearch = true,
        hasExpandBtn = true,
        extraActionsHtml = ''
      } = options;

      const containerId = `${id}-table-container`;
      const expandBtnHtml = hasExpandBtn ? this.renderExpandButtonHtml(containerId) : '';
      const searchHtml = hasSearch
        ? `<div class="input-group input-group-sm" style="width: 220px;">
             <span class="input-group-text"><i class="bi bi-search"></i></span>
             <input class="form-control" id="${id}-search-input" placeholder="${escapeHtml(searchPlaceholder)}" type="text"/>
           </div>`
        : '';

      return `
        <div class="panel-header d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div class="d-flex align-items-center gap-2">
            <span class="panel-title"><i class="bi ${escapeHtml(icon)} me-1 text-primary"></i> ${escapeHtml(title)}</span>
            <span class="ui-badge ui-badge-neutral" id="${id}-badge">${escapeHtml(badgeText)}</span>
          </div>
          <div class="d-flex align-items-center gap-2 flex-wrap">
            ${expandBtnHtml}
            ${extraActionsHtml}
            ${searchHtml}
          </div>
        </div>
      `;
    },

    /**
     * Полная генерация HTML-компонента адаптивной таблицы.
     * @param {Object} options 
     * @returns {string}
     */
    render(options = {}) {
      const {
        id = 'dynamic',
        title = 'Реестр данных',
        icon = 'bi-table',
        badgeText = '0 записей',
        columns = [],
        hasDrilldown = false,
        minHeight = 140,
        maxHeight = 480,
        emptyText = 'Загрузка данных...'
      } = options;

      const containerId = `${id}-table-container`;
      const headerHtml = this.renderHeader(options);

      let theadCols = '';
      if (hasDrilldown) {
        theadCols += '<th style="width: 36px; text-align: center;" title="Drill-down: Детальный анализ"></th>';
      }
      columns.forEach(col => {
        if (typeof col === 'string') {
          theadCols += `<th>${escapeHtml(col)}</th>`;
        } else {
          const style = col.width ? ` style="width: ${col.width};"` : '';
          const cls = col.align === 'right' ? ' class="text-end"' : '';
          theadCols += `<th${cls}${style}>${escapeHtml(col.label || col.name || '')}</th>`;
        }
      });

      const colsCount = columns.length + (hasDrilldown ? 1 : 0);

      return `
        <div class="winadmin-panel sys-panel card" data-panel-id="panel-${id}" id="panel-${id}">
          ${headerHtml}
          <div class="p-0 table-responsive" id="${containerId}" data-resizable-table="true" style="min-height: ${minHeight}px; max-height: ${maxHeight}px; overflow-y: auto;">
            <table class="table table-hover align-middle mb-0 winadmin-table" id="${id}-table">
              <thead class="sticky-top">
                <tr>${theadCols}</tr>
              </thead>
              <tbody id="${id}-tbody">
                <tr><td colspan="${colsCount}" class="text-center text-muted p-4">${escapeHtml(emptyText)}</td></tr>
              </tbody>
            </table>
          </div>
          ${this.renderResizerHtml(containerId)}
        </div>
      `;
    },

    /**
     * Применяет шаблонизатор к контейнеру таблицы в DOM:
     * настраивает ресайзер, кнопку 100%, MutationObserver и авто-высоту.
     * @param {string|HTMLElement} containerOrId - Контейнер таблицы или его ID.
     * @param {Object} [options={}] - Настройки ресайзера.
     * @returns {any} Экземпляр TableResizerInstance
     */
    apply(containerOrId, options = {}) {
      if (window.setupTableResizer) {
        return window.setupTableResizer({ container: containerOrId, autoCreate: true, ...options });
      }
      return null;
    },

    /**
     * Пропорциональная подгонка высоты под число строк.
     * @param {string|HTMLElement} containerOrId 
     * @param {number} [rowCount] 
     */
    autoAdjust(containerOrId, rowCount) {
      if (window.autoAdjustTableHeight) {
        window.autoAdjustTableHeight(containerOrId, rowCount);
      }
    },

    /**
     * Инициализирует все таблицы в корневом элементе.
     * @param {HTMLElement|Document} [root=document] 
     */
    initAll(root = document) {
      if (window.initAllTableResizers) {
        window.initAllTableResizers(root);
      }
    }
  };

  // Экспорт в глобальный контекст
  window.TableTemplate = TableTemplate;
  if (!window.TableResizerHelper) {
    window.TableResizerHelper = {};
  }
  window.TableResizerHelper.template = TableTemplate;
  window.TableResizerHelper.apply = TableTemplate.apply;

  // Экспорт как ES6-модуль, если поддерживается
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = TableTemplate;
  }
})();
