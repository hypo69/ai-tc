/**
 * =============================================================================
 * Process Name: Windows App Internals - Common UI Utilities
 * =============================================================================
 * Description:
 *   Общие утилиты интерфейса вкладки «Внутренняя кухня»: навигация по URL hash,
 *   нормализация идентификаторов панелей, динамическая загрузка скриптов и системные нотификации.
 *
 * File: ui_utils.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:30:00
 * =============================================================================
 */

export const TAB_ID = 'tab-app-internals';

/**
 * Проверяет, активна ли данная вкладка в текущий момент.
 * @returns {boolean} Флаг активности вкладки.
 */
export function isAppInternalsTabActive() {
  if (typeof document !== 'undefined' && document.hidden) {
    return false;
  }
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive(TAB_ID) || window.isTabActive('app-internals'));
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('app-internals');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор или алиас суб-панели к каноническому виду.
 * @param {string} rawId - Сырой идентификатор панели.
 * @returns {string} Канонический идентификатор панели.
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'telemetry';
  const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^panel-/, '');
  if (s.includes('codebase') || s.includes('code-rag') || s.includes('coderag') || s.includes('diag')) return 'codebase-rag';
  if (s.includes('telemetry') || s.includes('metric') || s.includes('cpu')) return 'telemetry';
  if (s.includes('model') || s.includes('provider') || s.includes('foundry') || s.includes('ollama')) return 'models';
  if (s.includes('activity')) return 'activity';
  if (s.includes('log-setting') || s.includes('logging-setting')) return 'settings';
  if (s.includes('log') || s.includes('journal')) return 'logs';
  if (s.includes('etw') || s.includes('tracing') || s.includes('trace') || s.includes('perf')) return 'etw';
  if (s.includes('setting') || (s.includes('param') && !s.includes('wikillm'))) return 'settings';
  if (s.includes('tooltip')) return 'tooltips-editor';
  if (s.includes('helppage') || s.includes('help-page') || s.includes('help-editor') || s.includes('helppages-editor')) return 'helppages-editor';
  if (s.includes('instrument') || s.includes('tool') || s.includes('hostinger')) return 'instruments';
  if (s.includes('wikillm') || s.includes('system') || s.includes('editor') || s.includes('article') || s.includes('knowledge') || s.includes('statya')) return 'wikillm-system';
  return 'telemetry';
}

/**
 * Нормализует идентификатор блока подменю внутри активной панели.
 * @param {string} blockId - Исходный ID блока
 * @param {string} [panelId=''] - Канонический ID панели
 * @returns {string} Канонический ID блока
 */
export function normalizeBlockId(blockId, panelId = '') {
  if (!blockId) {
    if (panelId === 'codebase-rag') return 'block-code-diagnose';
    return panelId === 'instruments' ? 'block-inst-hostinger' : 'block-sys-storage';
  }
  const s = String(blockId).toLowerCase().trim().replace(/^#/, '');

  // Блоки для Codebase RAG
  if (panelId === 'codebase-rag' || s.includes('code')) {
    if (s.includes('index') || s.includes('build')) return 'block-code-index';
    if (s.includes('search') || s.includes('symbol')) return 'block-code-search';
    return 'block-code-diagnose';
  }

  // Блоки для инструментов агента (Hostinger)
  if (panelId === 'instruments' || s.includes('inst')) {
    if (s.includes('runtime') || s.includes('chain') || s.includes('reason') || s.includes('param')) {
      return 'block-inst-runtime';
    }
    if (s.includes('catalog') || s.includes('list') || s.includes('all')) {
      return 'block-inst-catalog';
    }
    return 'block-inst-hostinger';
  }

  // Блоки для системных подсказок (WikiLLM)
  if (s.includes('param') || s.includes('model') || s.includes('setting')) {
    return 'block-sys-params';
  }
  if (s.includes('article') || s.includes('editor') || s.includes('statya')) {
    return 'block-sys-articles';
  }
  return 'block-sys-storage';
}

/**
 * Возвращает идентификатор текущей активной суб-панели.
 * @returns {string} Канонический ID суб-панели.
 */
export function getActiveSubTabId() {
  const activeBtn = document.querySelector('#app-internals-subtabs-nav button.active');
  if (activeBtn) {
    const pId = activeBtn.getAttribute('data-panel-id');
    if (pId) return normalizeSubTabId(pId);
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(target);
  }
  return 'telemetry';
}

/**
 * Возвращает идентификатор активного блока подменю в указанной панели.
 * @param {string} panelId - 'wikillm-system', 'instruments' или 'codebase-rag'
 * @returns {string}
 */
export function getActiveBlockId(panelId) {
  let navId = 'wikillm-sys-blocks-nav';
  if (panelId === 'instruments') navId = 'instruments-blocks-nav';
  else if (panelId === 'codebase-rag') navId = 'codebase-blocks-nav';
  const activeBtn = document.querySelector(`#${navId} button.active`);
  if (activeBtn) {
    const bId = activeBtn.getAttribute('data-block-id');
    if (bId) return normalizeBlockId(bId, panelId);
  }
  return normalizeBlockId('', panelId);
}

/**
 * Считывает суб-панель из URL hash (#tab-app-internals#<panel_id>#block-<block_id>).
 * @returns {string|null} ID субпанели или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'app-internals' || mainPart === 'tab-app-internals') {
      return normalizeSubTabId(parts[1]);
    }
  } else if (parts.length === 1) {
    const single = parts[0];
    if (single !== TAB_ID && single !== 'app-internals' && single !== 'tab-app-internals') {
      const norm = normalizeSubTabId(single);
      if (norm) return norm;
    }
  }
  return null;
}

/**
 * Извлекает блок подменю (block-<id>) из URL hash.
 * @param {string} [panelId=''] - Канонический ID панели
 * @returns {string|null} ID блока или null
 */
export function getBlockFromHash(panelId = '') {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');

  // Поиск прямого сегмента block-*
  const blockPart = parts.find((p) => p.startsWith('block-'));
  if (blockPart) {
    return normalizeBlockId(blockPart, panelId);
  }

  // Обратная совместимость для старых URL хешей
  if (parts.length >= 2) {
    const rawSub = parts[1].toLowerCase();
    if (rawSub === 'wikillm-db') return 'block-sys-storage';
    if (rawSub === 'wikillm-params') return 'block-sys-params';
    if (rawSub === 'wikillm-editor') return 'block-sys-articles';
  }

  return null;
}

/**
 * Обновляет URL hash активной суб-панелью и блоком (#tab-app-internals#<panel_id>[#block-<block_id>]) без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели.
 * @param {string|null} [blockId=null] - Идентификатор блока подменю
 */
export function updateUrlWithPanel(panelId, blockId = null) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';

  let blockSuffix = '';
  if (canonical === 'wikillm-system' || canonical === 'instruments' || canonical === 'codebase-rag') {
    const effectiveBlock = blockId ? normalizeBlockId(blockId, canonical) : getActiveBlockId(canonical);
    if (effectiveBlock) {
      blockSuffix = `#${effectiveBlock}`;
    }
  }

  const newHash = `#${TAB_ID}#panel-${canonical}${blockSuffix}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
    } catch (_) {}
  }
}

/**
 * Динамическая загрузка и выполнение скрипта модуля с ожиданием onload.
 * @param {string} src - Путь к файлу скрипта
 * @returns {Promise<void>}
 */
export function loadScript(src) {
  return new Promise((resolve) => {
    const cleanSrc = src.split('?')[0];
    const existing = document.querySelector(`script[src^="${cleanSrc}"]`);
    if (existing) {
      resolve();
      return;
    }
    const s = document.createElement('script');
    s.type = 'module';
    s.src = src;
    s.onload = () => resolve();
    s.onerror = (err) => {
      console.warn(`[AppInternals] Не удалось загрузить скрипт ${src}:`, err);
      resolve();
    };
    document.body.appendChild(s);
  });
}

/**
 * Отображение всплывающего уведомления toast.
 * @param {string} message - Текст уведомления
 * @param {'info' | 'success' | 'warning' | 'danger'} [type='info'] - Тип уведомления
 */
export function notifyUser(message, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(message, type);
  } else {
    console.info(`[AppInternals Toast: ${type}] ${message}`);
  }
}

/**
 * Экранирует специальные символы HTML для безопасного вывода в DOM.
 * @param {string} str - Исходная строка
 * @returns {string} Экранированная строка
 */
export function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
