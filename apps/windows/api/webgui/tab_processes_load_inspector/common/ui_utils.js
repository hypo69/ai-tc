/**
 * Общие вспомогательные утилиты для вкладки инспектора процессов.
 * Файл: apps/windows/api/webgui/tab_processes_load_inspector/common/ui_utils.js
 * Updated: 2026-10-31 19:25:00
 */

export const TAB_ID = 'tab-processes-load-inspector';

/**
 * Проверяет, активна ли данная вкладка в текущий момент.
 * @returns {boolean} Флаг активности вкладки.
 */
export function isProcessesTabActive() {
  if (typeof document !== 'undefined' && document.hidden) {
    return false;
  }
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive(TAB_ID) || window.isTabActive('processes-load-inspector'));
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('processes-load-inspector');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор субвкладки/панели к каноническому виду.
 * @param {string} subtabId - Строковый идентификатор.
 * @returns {string} Канонический ID панели ('manager' | 'top' | 'net' | 'files' | 'leaks').
 */
export function normalizeSubTabId(subtabId) {
  if (!subtabId) return 'manager';
  const s = String(subtabId).toLowerCase().trim().replace(/^#/, '');
  if (s.includes('leak')) return 'leaks';
  if (s.includes('top') || s.includes('stream') || s.includes('host') || s.includes('live')) return 'top';
  if (s.includes('net') || s.includes('socket')) return 'net';
  if (s.includes('file') || s.includes('watch')) return 'files';
  if (s.includes('manager') || s.includes('task') || s.includes('pm') || s.includes('app')) return 'manager';
  return 'manager';
}

/**
 * Возвращает идентификатор текущей активной суб-панели инспектора процессов.
 * @returns {'manager' | 'top' | 'net' | 'files' | 'leaks'}
 */
export function getActiveSubTabId() {
  const leaksPane = document.getElementById('subpane-proc-leaks');
  if (leaksPane && leaksPane.classList.contains('active')) return 'leaks';

  const topPane = document.getElementById('subpane-proc-top');
  if (topPane && topPane.classList.contains('active')) return 'top';

  const netPane = document.getElementById('subpane-proc-net');
  if (netPane && netPane.classList.contains('active')) return 'net';

  const filesPane = document.getElementById('subpane-proc-files');
  if (filesPane && filesPane.classList.contains('active')) return 'files';

  const managerPane = document.getElementById('subpane-proc-manager');
  if (managerPane && managerPane.classList.contains('active')) return 'manager';

  const activeBtn = document.querySelector('#processes-subtabs-nav button.active');
  if (activeBtn) {
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(target);
  }

  return 'manager';
}

/**
 * Считывает суб-панель из URL hash.
 * @returns {string|null} ID субпанели или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'processes-load-inspector' || mainPart === 'tab-processes-load-inspector') {
      return normalizeSubTabId(parts[1]);
    }
  } else if (parts.length === 1) {
    const single = parts[0];
    if (single !== TAB_ID && single !== 'processes-load-inspector' && single !== 'tab-processes-load-inspector') {
      const norm = normalizeSubTabId(single);
      if (norm) return norm;
    }
  }
  return null;
}

/**
 * Обновляет URL hash активной суб-панелью (#tab-processes-load-inspector#<panel_id>) без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели.
 */
export function updateUrlWithPanel(panelId) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';
  const newHash = `#${TAB_ID}#${canonical}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
    } catch (_) {}
  }
}

/**
 * Безопасно экранирует спецсимволы HTML.
 * @param {*} str - Входное значение.
 * @returns {string} Экранированная строка.
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
 * Форматирует число байтов в человекочитаемый вид (B, KB, MB, GB, TB).
 * @param {number} bytes - Количество байт.
 * @returns {string} Форматированная строка.
 */
export function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Форматирует секунды в строку вида HH:MM:SS.
 * @param {number} seconds - Число секунд.
 * @returns {string} Время в формате HH:MM:SS.
 */
export function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '00:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/**
 * Отображает всплывающее уведомление пользователю.
 * @param {string} msg - Текст сообщения.
 * @param {string} [type='info'] - Тип сообщения ('info', 'success', 'warning', 'danger').
 */
export function showToast(msg, type = 'info') {
  if (window.showToast) {
    window.showToast(msg, type);
  } else if (window.toast && typeof window.toast[type] === 'function') {
    window.toast[type]('Уведомление', msg);
  } else {
    console.log(`[Toast ${type}] ${msg}`);
  }
}

/**
 * Открывает модальное окно через Bootstrap или fallback-стили.
 * @param {HTMLElement} modalEl - DOM-элемент модального окна.
 */
export function openGenericModal(modalEl) {
  if (!modalEl) return;
  if (!modalEl._hideAriaBound) {
    modalEl._hideAriaBound = true;
    modalEl.addEventListener('hide.bs.modal', () => {
      if (document.activeElement && modalEl.contains(document.activeElement)) {
        document.activeElement.blur();
      }
    });
  }
  if (window.bootstrap && window.bootstrap.Modal) {
    try {
      const bs = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      bs.show();
      return;
    } catch (_) {}
  }
  modalEl.classList.add('show');
  modalEl.style.display = 'block';
  modalEl.removeAttribute('aria-hidden');
  modalEl.setAttribute('aria-modal', 'true');

  const backdropId = `${modalEl.id}-backdrop`;
  let backdrop = document.getElementById(backdropId);
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.id = backdropId;
    backdrop.className = 'modal-backdrop fade show';
    document.body.appendChild(backdrop);
    backdrop.addEventListener('click', () => closeGenericModal(modalEl));
  }
}

/**
 * Закрывает модальное окно.
 * @param {HTMLElement} modalEl - DOM-элемент модального окна.
 */
export function closeGenericModal(modalEl) {
  if (!modalEl) return;
  if (document.activeElement && modalEl.contains(document.activeElement)) {
    document.activeElement.blur();
  }
  if (window.bootstrap && window.bootstrap.Modal) {
    try {
      const bs = window.bootstrap.Modal.getInstance(modalEl);
      if (bs) bs.hide();
    } catch (_) {}
  }
  modalEl.classList.remove('show');
  modalEl.style.display = 'none';
  modalEl.setAttribute('aria-hidden', 'true');
  modalEl.removeAttribute('aria-modal');

  const backdropId = `${modalEl.id}-backdrop`;
  const backdrop = document.getElementById(backdropId);
  if (backdrop) backdrop.remove();
}

/**
 * Возвращает кэшированную информацию ИИ / WikiLLM по имени процесса.
 * @param {string} procName - Имя исполняемого файла процесса.
 * @returns {Object|null} Объект с данными анализа или null.
 */
export function getProcessAIInfo(procName) {
  if (!procName) return null;
  const cache = window.TooltipCache || (window.parent && window.parent.TooltipCache);
  if (!cache || typeof cache.get !== 'function') return null;

  const clean = String(procName).toLowerCase().trim();
  const cleanNoExt = clean.replace(/\.exe$/i, '');
  return cache.get(clean) ||
         cache.get(cleanNoExt) ||
         cache.get(`process:${clean}`) ||
         cache.get(`process:${cleanNoExt}`) ||
         null;
}

/**
 * Генерирует HTML бейджа справки для процесса, если по нему есть описание в базе локализации или кэше.
 * @param {string} procName - Имя процесса.
 * @returns {string} HTML бейджа или пустая строка.
 */
export function renderAIBadge(procName) {
  const info = getProcessAIInfo(procName);
  if (!info) return '';
  const clean = String(procName).toLowerCase().trim();
  const summaryText = info.summary || info.title || 'Доступно экспертное описание ИИ (наведите для просмотра)';
  return `<span class="badge bg-primary-subtle text-primary border border-primary ms-1.5 px-1 py-0.5 ai-proc-badge" data-ai-tooltip="true" data-term="${escapeHtml(clean)}" data-title="${escapeHtml(info.title || procName)}" data-table-type="process" data-process-name="${escapeHtml(procName)}" data-general-summary="${escapeHtml(summaryText)}" style="font-size: 0.68rem; vertical-align: middle; cursor: help;" title="Доступно экспертное описание ИИ (наведите для просмотра)"><i class="bi bi-robot me-1"></i>ИИ</span>`;
}

/**
 * Формирует атрибуты для подключения умного тултипа ИИ к строке процесса.
 * Тултип подвешивается ТОЛЬКО если по процессу есть информация.
 * @param {string} procName - Имя процесса.
 * @param {number|string} [pid=''] - PID процесса.
 * @param {string} [title=''] - Читаемый заголовок процесса.
 * @returns {string} Строка атрибутов data-ai-tooltip и др.
 */
export function getProcessTooltipAttributes(procName, pid = '', title = '') {
  if (!procName) return '';
  const info = getProcessAIInfo(procName);
  if (!info) return '';

  const clean = String(procName).toLowerCase().trim();
  const displayTitle = title || info.title || procName;
  const safePid = pid ? String(pid) : '';

  return ` data-ai-tooltip="true" data-term="${escapeHtml(clean)}" data-explain-key="${escapeHtml(clean)}" data-table-type="process" data-pid="${escapeHtml(safePid)}" data-process-name="${escapeHtml(procName)}" data-title="${escapeHtml(displayTitle)}"`;
}

/**
 * Инициализирует AI Smart Tooltips для указанного контейнера или таблицы.
 * @param {HTMLElement|Document} [container=document] - Целевой контейнер.
 */
export function initTableSmartTooltips(container = document) {
  const tooltipMgr = window.AISmartTooltip || (window.parent && window.parent.AISmartTooltip);
  if (tooltipMgr && typeof tooltipMgr.initAll === 'function') {
    tooltipMgr.initAll(container);
  }
}

/**
 * Асинхронно синхронизирует верифицированные знания о процессах из WikiLLM в TooltipCache.
 */
export async function syncWikiLLMProcessKnowledge() {
  const cache = window.TooltipCache || (window.parent && window.parent.TooltipCache);
  if (!cache || typeof cache.set !== 'function') return;

  try {
    const res = await fetch('/api/v1/wikillm/entities?type=process&limit=500');
    if (!res.ok) return;
    const list = await res.json();
    if (!Array.isArray(list)) return;

    list.forEach(ent => {
      if (!ent || !ent.canonical_key) return;
      const rawName = ent.canonical_key.replace(/^process:/i, '');
      const title = ent.title || rawName;
      const rec = {
        title: title,
        fullTitle: `${title} (${rawName})`,
        icon: '🤖',
        summary: ent.summary || (ent.claims && ent.claims[0] ? ent.claims[0].statement : ''),
        category: ent.category || 'Процесс Windows',
        source: 'wikillm',
        isVerified: true
      };
      cache.set(rawName.toLowerCase(), rec);
      cache.set(rawName.toLowerCase().replace(/\.exe$/i, ''), rec);
      cache.set(ent.canonical_key.toLowerCase(), rec);
    });
  } catch (e) {
    console.debug('[ProcessInspector] syncWikiLLMProcessKnowledge error:', e);
  }
}

