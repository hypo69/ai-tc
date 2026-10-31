/**
 * Клиент API диагностики сетевой инфраструктуры и общие хелперы отображения.
 * Файл: apps/windows/api/webgui/tab_network/panel_infra/api.js
 * Updated: 2026-10-28 16:30:00
 */

const BASE = '/api/network/infra';

/** Метаданные статусов данных (ТЗ § 6.2): подпись и CSS-классы темы. */
export const STATUS_META = {
  ok: { label: 'Данные получены', cls: 'bg-success-subtle text-success border border-success' },
  partial: { label: 'Получено частично', cls: 'bg-warning-subtle text-warning border border-warning' },
  source_unavailable: { label: 'Источник недоступен', cls: 'bg-secondary-subtle text-body border border-secondary' },
  not_installed: { label: 'Компонент не установлен', cls: 'bg-secondary-subtle text-body border border-secondary' },
  data_unavailable: { label: 'Сведения недоступны', cls: 'bg-warning-subtle text-warning border border-warning' },
  error: { label: 'Ошибка сбора', cls: 'bg-danger-subtle text-danger border border-danger' },
  unknown: { label: 'Не определено', cls: 'bg-secondary-subtle text-body border border-secondary' },
};

/** Классы бейджей важности диагностики. */
export const SEVERITY_META = {
  info: { label: 'info', cls: 'bg-info-subtle text-info border border-info' },
  warning: { label: 'warning', cls: 'bg-warning-subtle text-warning border border-warning' },
  error: { label: 'error', cls: 'bg-danger-subtle text-danger border border-danger' },
  critical: { label: 'critical', cls: 'bg-danger text-white' },
};

/**
 * Экранирует строку для вставки в HTML.
 * @param {*} value - Исходное значение.
 * @returns {string}
 */
export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/**
 * Форматирует ISO-время в локальный вид.
 * @param {string} iso - Время ISO-8601.
 * @returns {string}
 */
export function fmtTime(iso) {
  if (!iso) return '--';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? esc(iso) : d.toLocaleString();
}

/**
 * Возвращает HTML бейджа статуса данных.
 * @param {string} status - Код статуса.
 * @returns {string}
 */
export function statusBadge(status) {
  const m = STATUS_META[status] || STATUS_META.unknown;
  return `<span class="badge rounded-pill ${m.cls}" data-status="${esc(status)}">${m.label}</span>`;
}

/**
 * Возвращает HTML бейджа важности.
 * @param {string} severity - Уровень важности.
 * @returns {string}
 */
export function severityBadge(severity) {
  const m = SEVERITY_META[severity] || SEVERITY_META.info;
  return `<span class="badge ${m.cls}">${m.label}</span>`;
}

/**
 * Выполняет запрос к API и возвращает JSON; бросает Error с текстом HTTP-ошибки.
 * @param {string} path - Путь относительно /api/network/infra.
 * @param {{method?: string, params?: Object}} [opts] - Параметры запроса.
 * @returns {Promise<Object>}
 */
export async function infraRequest(path, opts = {}) {
  const qs = opts.params ? '?' + new URLSearchParams(opts.params).toString() : '';
  const res = await fetch(`${BASE}${path}${qs}`, { method: opts.method || 'GET' });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch (_) { /* тело не JSON */ }
    throw new Error(`HTTP ${res.status}${detail ? ': ' + detail : ''}`);
  }
  return res.json();
}
