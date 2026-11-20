/**
 * =============================================================================
 * Process Name: Windows Backup - Common UI Utilities
 * =============================================================================
 * Description:
 *   Общие утилиты пользовательского интерфейса вкладки Windows Backup:
 *   экранирование HTML, общее состояние библиотек и папок, вспомогательные
 *   методы отображения модальных окон.
 *
 * File: ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Общее состояние загруженных данных для панелей.
 */
export const sharedState = {
  userFoldersData: null,
  librariesData: []
};

/**
 * Безопасное экранирование специальных символов HTML.
 * @param {any} str - Входная строка
 * @returns {string} Экранированная строка
 */
export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Открытие модального окна Bootstrap.
 * @param {HTMLElement|string} modalElOrId - DOM-элемент или ID модального окна
 */
export function showModal(modalElOrId) {
  const modalEl = typeof modalElOrId === 'string' ? document.getElementById(modalElOrId) : modalElOrId;
  if (!modalEl) return;
  if (window.bootstrap?.Modal) {
    new window.bootstrap.Modal(modalEl).show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}

/**
 * Закрытие модального окна Bootstrap.
 * @param {HTMLElement|string} modalElOrId - DOM-элемент или ID модального окна
 */
export function hideModal(modalElOrId) {
  const modalEl = typeof modalElOrId === 'string' ? document.getElementById(modalElOrId) : modalElOrId;
  if (!modalEl) return;
  if (window.bootstrap?.Modal) {
    const modalInst = window.bootstrap.Modal.getInstance(modalEl);
    if (modalInst) modalInst.hide();
  } else {
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
  }
}
