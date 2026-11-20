/**
 * =============================================================================
 * Process Name: Common WebGUI - Universal Table Column Sorter
 * =============================================================================
 * Description:
 *   Универсальный модуль сортировки (asc/desc) по любому столбцу для абсолютно
 *   всех HTML-таблиц веб-интерфейса ai-tc / Test Computer.
 *
 *   Функциональные возможности:
 *     1. Автоматическое обнаружение и подключение ко всем <table> в документе
 *        (включая динамически подгружаемые вкладки, модальные окна и AJAX-таблицы)
 *        через делегирование кликов и MutationObserver.
 *     2. Умное сравнение значений: числа, проценты, единицы измерения (B/KB/MB/GB/TB,
 *        Hz/MHz/GHz, ms/s, °C), IPv4-адреса, даты (ISO и DD.MM.YYYY) и локализованные
 *        строки (localeCompare с numeric: true).
 *     3. Корректная обработка строк-заглушек (colspan) и привязанных детальных строк.
 *     4. Визуальная индикация направления сортировки через data-sort-dir="asc|desc"
 *        и aria-sort без изменения текстового содержимого заголовков (совместимо с i18n).
 *
 * Usage Examples:
 *   JavaScript:
 *     window.TableSorter.initAll(document);
 *     window.TableSorter.sortTableByColumn(tableEl, colIndex, 'asc');
 *
 * File: table-sorter.js
 * Project: ai-tc
 * Package: apps.common.webgui.js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 15:45:00
 * =============================================================================
 */

(function () {
  'use strict';

  /** Множители для перевода размеров памяти/данных в байты. */
  const SIZE_MULTIPLIERS = {
    b: 1,
    byte: 1,
    bytes: 1,
    'б': 1,
    kb: 1024,
    kib: 1024,
    'кб': 1024,
    mb: 1024 ** 2,
    mib: 1024 ** 2,
    'мб': 1024 ** 2,
    gb: 1024 ** 3,
    gib: 1024 ** 3,
    'гб': 1024 ** 3,
    tb: 1024 ** 4,
    tib: 1024 ** 4,
    'тб': 1024 ** 4,
    pb: 1024 ** 5,
    pib: 1024 ** 5,
    'пб': 1024 ** 5
  };

  /** Регулярные выражения для распознавания типов данных ячеек. */
  const RE_EMPTY = /^(\s*|[-—–]+|n\/?a|null|undefined|none|н\/?д)$/i;
  const RE_IPV4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?::(\d+))?$/;
  const RE_SIZE = /^([+-]?\d+(?:[.,]\d+)?)\s*(b|bytes?|kb|kib|mb|mib|gb|gib|tb|tib|pb|pib|б|кб|мб|гб|тб|пб)(?:\/s|\/с)?$/i;
  const RE_ISO_DATE = /^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)?/;
  const RE_DMY_DATE = /^(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/;
  const RE_NUMERIC = /^([+-]?\d[\d\s\u00A0]*(?:[.,]\d+)?)\s*(%|ms|мс|s|с|sec|сек|min|мин|h|ч|hz|khz|mhz|ghz|°c|c|w|v|rpm|fps|mbps|kbps|gbps|шт\.?|дн\.?)?$/i;

  /**
   * Извлекает типизированное значение ячейки для корректного сравнения.
   *
   * @param {HTMLTableCellElement|null} cell - Ячейка таблицы.
   * @returns {{ empty: boolean, type: string, value: number|string }}
   */
  function parseCellValue(cell) {
    if (!cell) {
      return { empty: true, type: 'empty', value: '' };
    }

    const explicit = cell.getAttribute('data-sort-value') ?? cell.getAttribute('data-sort');
    const raw = (explicit !== null ? explicit : (cell.textContent || '')).trim();

    if (!raw || RE_EMPTY.test(raw)) {
      return { empty: true, type: 'empty', value: '' };
    }

    // 1. IPv4-адрес (с опциональным портом)
    const ipMatch = raw.match(RE_IPV4);
    if (ipMatch) {
      const octets = [
        Number(ipMatch[1]),
        Number(ipMatch[2]),
        Number(ipMatch[3]),
        Number(ipMatch[4])
      ];
      if (octets.every((o) => o >= 0 && o <= 255)) {
        const port = ipMatch[5] ? Number(ipMatch[5]) : 0;
        const ipNum = ((octets[0] * 16777216) + (octets[1] * 65536) + (octets[2] * 256) + octets[3]) * 65536 + port;
        return { empty: false, type: 'number', value: ipNum };
      }
    }

    // 2. Размеры файлов и памяти (B, KB, MB, GB, TB и русские аналоги)
    const sizeMatch = raw.match(RE_SIZE);
    if (sizeMatch) {
      const num = parseFloat(sizeMatch[1].replace(',', '.'));
      const unit = sizeMatch[2].toLowerCase();
      const mult = SIZE_MULTIPLIERS[unit];
      if (!Number.isNaN(num) && mult) {
        return { empty: false, type: 'number', value: num * mult };
      }
    }

    // 3. Даты формата DD.MM.YYYY [HH:MM[:SS]]
    const dmyMatch = raw.match(RE_DMY_DATE);
    if (dmyMatch) {
      const ts = new Date(
        Number(dmyMatch[3]),
        Number(dmyMatch[2]) - 1,
        Number(dmyMatch[1]),
        Number(dmyMatch[4] || 0),
        Number(dmyMatch[5] || 0),
        Number(dmyMatch[6] || 0)
      ).getTime();
      if (!Number.isNaN(ts)) {
        return { empty: false, type: 'number', value: ts };
      }
    }

    // 4. Даты формата ISO (YYYY-MM-DD...)
    if (RE_ISO_DATE.test(raw)) {
      const ts = Date.parse(raw.replace(' ', 'T'));
      if (!Number.isNaN(ts)) {
        return { empty: false, type: 'number', value: ts };
      }
    }

    // 5. Числа, проценты и числа с единицами измерения
    const numMatch = raw.match(RE_NUMERIC);
    if (numMatch) {
      const normalized = numMatch[1].replace(/[\s\u00A0]/g, '').replace(',', '.');
      const num = parseFloat(normalized);
      if (!Number.isNaN(num)) {
        return { empty: false, type: 'number', value: num };
      }
    }

    // 6. Текстовое значение
    return { empty: false, type: 'string', value: raw.toLowerCase() };
  }

  /**
   * Сравнивает два распарсенных значения с учетом направления сортировки.
   * Пустые значения всегда опускаются в конец таблицы.
   *
   * @param {{ empty: boolean, type: string, value: number|string }} a
   * @param {{ empty: boolean, type: string, value: number|string }} b
   * @param {number} dir - 1 для asc, -1 для desc.
   * @returns {number}
   */
  function compareParsedValues(a, b, dir) {
    if (a.empty && b.empty) return 0;
    if (a.empty) return 1;
    if (b.empty) return -1;

    if (a.type === 'number' && b.type === 'number') {
      return (a.value - b.value) * dir;
    }

    return String(a.value).localeCompare(String(b.value), undefined, {
      numeric: true,
      sensitivity: 'base'
    }) * dir;
  }

  /**
   * Проверяет, может ли конкретный заголовок <th> использоваться для универсальной сортировки.
   *
   * @param {HTMLTableCellElement} th - Элемент заголовка столбца.
   * @returns {boolean}
   */
  function isHeaderSortable(th) {
    if (!th || th.tagName !== 'TH') return false;
    if (th.getAttribute('data-no-sort') === 'true' || th.classList.contains('no-sort')) {
      return false;
    }

    const table = th.closest('table');
    if (!table || table.getAttribute('data-no-sort') === 'true' || table.getAttribute('data-custom-sort') === 'true') {
      return false;
    }

    // Не перехватываем таблицы с собственной встроенной сортировкой
    if (typeof th.onclick === 'function' || th.hasAttribute('data-col') || th.hasAttribute('data-sort-field')) {
      return false;
    }

    // Пропускаем технические пустые колонки (например, колонка дрели drill-down или чекбокс без текста)
    const text = (th.textContent || '').trim();
    if (!text) {
      return false;
    }

    return true;
  }

  /**
   * Возвращает фактический индекс столбца для элемента <th> в строке заголовка.
   *
   * @param {HTMLTableCellElement} th
   * @returns {number}
   */
  function getColumnIndex(th) {
    const row = th.parentElement;
    if (!row) return -1;
    let index = 0;
    for (const cell of row.children) {
      if (cell === th) return index;
      index += Number(cell.colSpan || 1);
    }
    return -1;
  }

  /**
   * Находит ячейку <td>/<th> в строке по логическому индексу столбца с учетом colSpan.
   *
   * @param {HTMLTableRowElement} row
   * @param {number} targetIndex
   * @returns {HTMLTableCellElement|null}
   */
  function getCellByColumnIndex(row, targetIndex) {
    let index = 0;
    for (const cell of row.children) {
      const span = Number(cell.colSpan || 1);
      if (targetIndex >= index && targetIndex < index + span) {
        return cell;
      }
      index += span;
    }
    return null;
  }

  /**
   * Сортирует строки <tbody> таблицы по указанному индексу столбца.
   *
   * @param {HTMLTableElement} table - DOM-элемент таблицы.
   * @param {number} colIndex - Индекс столбца (0-based).
   * @param {'asc'|'desc'} direction - Направление сортировки.
   */
  function sortTableByColumn(table, colIndex, direction = 'asc') {
    if (!table || colIndex < 0) return;

    const tbodies = Array.from(table.tBodies || []);
    if (tbodies.length === 0) return;

    const dir = direction === 'desc' ? -1 : 1;

    tbodies.forEach((tbody) => {
      const allRows = Array.from(tbody.children).filter((el) => el.tagName === 'TR');
      if (allRows.length <= 1) return;

      // Если единственная строка — заглушка colspan, сортировка не требуется
      if (allRows.length === 1 && allRows[0].querySelector('td[colspan]')) return;

      // Группируем основные строки с их дочерними строками-деталями (colspan), если они есть
      const groups = [];
      for (let i = 0; i < allRows.length; i++) {
        const row = allRows[i];
        const isFullColspan = row.children.length === 1 && Number(row.children[0].colSpan || 1) > 1;
        if (isFullColspan && groups.length > 0) {
          groups[groups.length - 1].details.push(row);
        } else {
          const cell = getCellByColumnIndex(row, colIndex);
          groups.push({
            row,
            details: [],
            parsed: parseCellValue(cell),
            origIndex: i
          });
        }
      }

      if (groups.length <= 1) return;

      groups.sort((a, b) => {
        const cmp = compareParsedValues(a.parsed, b.parsed, dir);
        return cmp !== 0 ? cmp : (a.origIndex - b.origIndex);
      });

      const fragment = document.createDocumentFragment();
      groups.forEach((g) => {
        fragment.appendChild(g.row);
        g.details.forEach((detRow) => fragment.appendChild(detRow));
      });
      tbody.appendChild(fragment);
    });
  }

  /**
   * Подготавливает заголовки <thead> таблицы для визуального отображения сортировки.
   *
   * @param {HTMLTableElement} table
   */
  function attach(table) {
    if (!table || table.tagName !== 'TABLE') return;
    if (table.getAttribute('data-no-sort') === 'true' || table.getAttribute('data-custom-sort') === 'true') {
      return;
    }

    const thead = table.tHead || table.querySelector('thead');
    if (!thead) return;

    const headerRows = thead.querySelectorAll('tr');
    if (headerRows.length === 0) return;

    // Для многоуровневых шапок берем последнюю строку заголовков столбцов
    const targetRow = headerRows[headerRows.length - 1];
    const headers = targetRow.querySelectorAll('th');

    headers.forEach((th) => {
      if (isHeaderSortable(th)) {
        th.classList.add('ut-sortable');
        if (!th.hasAttribute('title')) {
          th.setAttribute('title', 'Нажмите для сортировки (по возрастанию / убыванию)');
        }
      }
    });
  }

  /**
   * Инициализирует универсальную сортировку для всех таблиц внутри корневого элемента.
   *
   * @param {Document|HTMLElement} [root=document]
   */
  function initAll(root = document) {
    if (!root || typeof root.querySelectorAll !== 'function') return;
    if (root.tagName === 'TABLE') {
      attach(root);
      return;
    }
    root.querySelectorAll('table').forEach((table) => attach(table));
  }

  /**
   * Глобальный делегированный обработчик кликов по заголовкам <th>.
   */
  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!target || typeof target.closest !== 'function') return;

    // Игнорируем клики по интерактивным элементам внутри <th> (кнопки, ссылки, чекбоксы, 100%)
    if (target.closest('button, a, input, select, textarea, label, .btn-table-expand-100, .no-sort')) {
      return;
    }

    const th = target.closest('thead th');
    if (!th) return;

    if (!th.classList.contains('ut-sortable')) {
      if (!isHeaderSortable(th)) return;
      th.classList.add('ut-sortable');
    }

    const table = th.closest('table');
    if (!table) return;

    const colIndex = getColumnIndex(th);
    if (colIndex < 0) return;

    const currentDir = th.getAttribute('data-sort-dir');
    const nextDir = currentDir === 'asc' ? 'desc' : 'asc';

    // Сбрасываем индикаторы на остальных заголовках этой таблицы
    const thead = th.closest('thead');
    if (thead) {
      thead.querySelectorAll('th[data-sort-dir]').forEach((otherTh) => {
        if (otherTh !== th) {
          otherTh.removeAttribute('data-sort-dir');
          otherTh.removeAttribute('aria-sort');
        }
      });
    }

    th.setAttribute('data-sort-dir', nextDir);
    th.setAttribute('aria-sort', nextDir === 'asc' ? 'ascending' : 'descending');

    sortTableByColumn(table, colIndex, nextDir);
  });

  // Автоматическая инициализация для всех новых таблиц в DOM
  let domObserver = null;
  let pendingRoots = new Set();
  let observerTimer = null;

  function startGlobalObserver() {
    if (domObserver || typeof MutationObserver === 'undefined' || !document.body) return;

    domObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;
          if (node.tagName === 'TABLE' || node.tagName === 'THEAD' || node.tagName === 'TH') {
            pendingRoots.add(node.closest ? (node.closest('table') || node) : node);
          } else if (node.querySelector && node.querySelector('table')) {
            pendingRoots.add(node);
          }
        }
      }

      if (pendingRoots.size > 0 && !observerTimer) {
        observerTimer = setTimeout(() => {
          const batch = Array.from(pendingRoots);
          pendingRoots.clear();
          observerTimer = null;
          batch.forEach((el) => {
            if (el && el.isConnected) initAll(el);
          });
        }, 60);
      }
    });

    domObserver.observe(document.body, { childList: true, subtree: true });
  }

  // Экспорт в глобальный контекст
  window.TableSorter = {
    attach,
    initAll,
    sortTableByColumn,
    parseCellValue
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initAll(document);
      startGlobalObserver();
    });
  } else {
    setTimeout(() => {
      initAll(document);
      startGlobalObserver();
    }, 50);
  }

  document.addEventListener('tab:activated', (e) => {
    const tabId = e.detail?.tabId;
    if (tabId) {
      const tabPane = document.getElementById(tabId);
      if (tabPane) initAll(tabPane);
    }
  });
})();
