/**
 * Универсальный рендер таблиц (сортировка, поиск, раскрытие подробностей) и баннеров статуса.
 * Файл: apps/windows/api/webgui/tab_network/panel_infra/render.js
 * Updated: 2026-10-28 16:30:00
 */

import { esc, fmtTime, statusBadge } from './api.js';

/**
 * Рендерит баннер статуса источника: статус, источник, время, ошибки, предупреждение о правах.
 * @param {Object} env - Ответ API (status, source, collected_at, errors, notes, needs_elevation).
 * @returns {string}
 */
export function renderStatusBanner(env) {
  const parts = [`<div class="d-flex flex-wrap align-items-center gap-2 mb-2 small">${statusBadge(env.status)}`,
    `<span class="text-muted">Источник: ${esc(env.source || '--')}</span>`,
    `<span class="text-muted">Обновлено: ${fmtTime(env.collected_at)}</span></div>`];
  if (env.needs_elevation) {
    parts.push('<div class="alert alert-warning py-1 px-2 small mb-2"><i class="bi bi-shield-exclamation me-1"></i>'
      + 'Для полных данных нужны повышенные права. Указанные ниже сведения получить не удалось.</div>');
  }
  if ((env.errors || []).length) {
    parts.push(`<div class="alert alert-danger py-1 px-2 small mb-2"><b>Ошибки сбора:</b><ul class="mb-0">${env.errors.map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div>`);
  }
  const notes = (env.notes || []).filter((n) => n && !n.startsWith('__'));
  if (notes.length) {
    parts.push(`<div class="small text-muted mb-2"><i class="bi bi-info-circle me-1"></i>${notes.map(esc).join(' ')}</div>`);
  }
  return parts.join('');
}

/**
 * Возвращает пояснение пустого результата, различающее «нет объектов» и «нет данных».
 * @param {string} status - Статус источника.
 * @param {string} emptyText - Текст для действительно пустого результата.
 * @returns {string}
 */
export function emptyMessage(status, emptyText) {
  if (status === 'ok') return emptyText;
  if (status === 'not_installed') return 'Компонент не установлен — объекты не собирались.';
  return 'Данные не получены (см. статус и ошибки выше): это не означает отсутствие объектов.';
}

/**
 * Монтирует интерактивную таблицу в контейнер.
 * @param {HTMLElement} el - Контейнер.
 * @param {{columns: Array<{label: string, value: Function, sort?: Function}>, rows: Array<Object>,
 *   search?: Function, detail?: Function, emptyText: string, status: string}} cfg - Конфигурация.
 */
export function mountTable(el, cfg) {
  const state = { sortCol: -1, dir: 1, query: '', open: new Set() };
  const draw = () => {
    let rows = cfg.rows.map((r, i) => ({ r, i }));
    if (state.query) {
      const q = state.query.toLowerCase();
      rows = rows.filter(({ r }) => (cfg.search ? cfg.search(r) : JSON.stringify(r)).toLowerCase().includes(q));
    }
    if (state.sortCol >= 0) {
      const col = cfg.columns[state.sortCol];
      const key = col.sort || col.value;
      rows.sort((a, b) => {
        const x = key(a.r); const y = key(b.r);
        return (x > y ? 1 : x < y ? -1 : 0) * state.dir;
      });
    }
    const head = cfg.columns.map((c, i) => `<th role="button" data-col="${i}" class="user-select-none">${esc(c.label)}${state.sortCol === i ? (state.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('');
    const body = rows.length ? rows.map(({ r, i }) => {
      const open = state.open.has(i);
      const main = `<tr data-row="${i}" ${cfg.detail ? 'role="button"' : ''}>${cfg.columns.map((c) => `<td>${c.value(r)}</td>`).join('')}</tr>`;
      const det = open && cfg.detail ? `<tr><td colspan="${cfg.columns.length}" class="net-well small">${cfg.detail(r)}</td></tr>` : '';
      return main + det;
    }).join('') : `<tr><td colspan="${cfg.columns.length}" class="text-center py-3 text-muted">${esc(emptyMessage(cfg.status, cfg.emptyText))}</td></tr>`;
    el.innerHTML = `<div class="d-flex justify-content-between align-items-center mb-1">
      <input type="search" class="form-control form-control-sm" style="max-width: 260px;" placeholder="Поиск..." value="${esc(state.query)}" data-role="search">
      <span class="small text-muted">${rows.length} из ${cfg.rows.length}</span></div>
      <div class="table-responsive"><table class="net-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
    const search = el.querySelector('[data-role="search"]');
    search.oninput = () => { state.query = search.value; draw(); const s = el.querySelector('[data-role="search"]'); s.focus(); s.setSelectionRange(s.value.length, s.value.length); };
    el.querySelectorAll('th[data-col]').forEach((th) => {
      th.onclick = () => {
        const c = Number(th.dataset.col);
        state.dir = state.sortCol === c ? -state.dir : 1;
        state.sortCol = c;
        draw();
      };
    });
    el.querySelectorAll('tr[data-row]').forEach((tr) => {
      tr.onclick = () => {
        if (!cfg.detail) return;
        const i = Number(tr.dataset.row);
        if (state.open.has(i)) state.open.delete(i); else state.open.add(i);
        draw();
      };
    });
  };
  draw();
}

/**
 * Возвращает HTML блока «исходные данные» для раскрытой строки.
 * @param {*} raw - Исходные данные источника.
 * @param {string} source - Название источника.
 * @returns {string}
 */
export function rawDetails(raw, source) {
  return `<div class="text-muted mb-1">Источник: ${esc(source)}</div><pre class="mb-0 small" style="max-height: 220px; overflow: auto;">${esc(JSON.stringify(raw, null, 2))}</pre>`;
}
