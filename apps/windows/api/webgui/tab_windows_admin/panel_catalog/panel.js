/**
 * =============================================================================
 * Название: Панель каталога системных операций Accounts & Identity
 * =============================================================================
 * Описание:
 *   Реестр системных Win32 API и CLI операций (~180 функций) с классификацией
 *   уровней риска (SAFE, ADMIN, ADVANCED, DANGEROUS) и поиском.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_catalog/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let _catalogCache = [];

export function getCatalogCache() {
  return _catalogCache;
}

/**
 * Загрузка реестра системных операций каталога.
 */
export async function loadCatalog() {
  const tbody = document.getElementById('catalog-table-body');
  try {
    const res = await fetch('/api/v1/windows/identity/catalog');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _catalogCache = await res.json();
    renderCatalogTable(_catalogCache);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Ошибка загрузки каталога: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Отрисовка таблицы операций каталога.
 * @param {Array} items - Список операций.
 */
export function renderCatalogTable(items) {
  const tbody = document.getElementById('catalog-table-body');
  if (!tbody) return;
  tbody.innerHTML = items.map(op => {
    let riskBadge = '<span class="ui-badge ui-badge-success">SAFE</span>';
    if (op.risk_level.includes('ADMIN')) riskBadge = '<span class="ui-badge ui-badge-warning">ADMIN</span>';
    if (op.risk_level.includes('DANGEROUS')) riskBadge = '<span class="ui-badge ui-badge-danger">DANGEROUS</span>';
    if (op.risk_level.includes('ADVANCED')) riskBadge = '<span class="ui-badge ui-badge-neutral">ADVANCED</span>';

    return `
      <tr>
        <td class="text-muted fw-bold">${op.id}</td>
        <td class="fw-semibold text-body">${escapeHtml(op.name_ru)}</td>
        <td class="small text-muted">${escapeHtml(op.subsystem_name_ru)}</td>
        <td class="small font-monospace"><code>${escapeHtml(op.mechanism)}</code></td>
        <td class="small font-monospace"><code>${escapeHtml(op.win32_api || op.ps_or_cli || '—')}</code></td>
        <td>${riskBadge}</td>
      </tr>
    `;
  }).join('');
}

/**
 * Фильтрация таблицы каталога по поисковому запросу.
 * @param {string} query - Поисковая строка.
 */
export function filterCatalogTable(query) {
  const q = (query || '').toLowerCase().trim();
  if (!q) {
    renderCatalogTable(_catalogCache);
    return;
  }
  const filtered = _catalogCache.filter(op =>
    (op.name_ru && op.name_ru.toLowerCase().includes(q)) ||
    (op.subsystem_name_ru && op.subsystem_name_ru.toLowerCase().includes(q)) ||
    (op.mechanism && op.mechanism.toLowerCase().includes(q)) ||
    (op.win32_api && op.win32_api.toLowerCase().includes(q))
  );
  renderCatalogTable(filtered);
}
