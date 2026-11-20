/**
 * =============================================================================
 * Process Name: Windows Software Scanner - Heavy Resources Panel
 * =============================================================================
 * Description:
 *   Модуль мониторинга ресурсоемких программ: процессов с высокой утилизацией
 *   процессора (CPU), оперативной памяти (RAM) и дискового I/O с поддержкой кэша IndexedDB.
 *
 * File: panel_heavy/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_scanner/panel_heavy
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentHeavyProcesses = [];

/**
 * Инициализирует панель ресурсоемких программ.
 * @param {boolean} [forceRefresh=false] - Принудительный сетевой запрос в обход кэша.
 */
export async function initHeavyResourcesPanel(forceRefresh = false) {
  const tableBody = document.getElementById('sw-heavy-table-body');
  if (!tableBody) return;

  // 1. Быстрое чтение из кэша IndexedDB (< 10 мс)
  if (!forceRefresh && window.IndexedDBCache) {
    try {
      const cached = await window.IndexedDBCache.get('software_heavy', 'list');
      if (cached && Array.isArray(cached) && cached.length > 0) {
        renderHeavyTable(cached);
      }
    } catch (err) {
      console.debug('[SoftwareHub] Ошибка чтения heavy из кэша:', err);
    }
  }

  // 2. Если данных нет или forceRefresh — сетевой запрос
  if (forceRefresh || tableBody.querySelectorAll('tr').length <= 1) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-4 text-warning">
          <div class="spinner-border spinner-border-sm me-2" role="status"></div>
          Сбор наиболее ресурсоемких процессов Windows...
        </td>
      </tr>
    `;

    try {
      const signal = window.IndexedDBCache ? window.IndexedDBCache.getFreshAbortSignal() : undefined;
      const res = await fetch('/api/v1/software/heavy', { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = data.processes || [];

      if (window.IndexedDBCache && list.length > 0) {
        await window.IndexedDBCache.put('software_heavy', 'list', list);
      }
      renderHeavyTable(list);
    } catch (err) {
      if (err.name === 'AbortError') return;
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-4 text-danger">
            <i class="bi bi-exclamation-triangle me-1"></i>Ошибка загрузки процессов: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
  }

  const refreshBtn = document.getElementById('sw-btn-refresh-heavy');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.onclick = () => initHeavyResourcesPanel(true);
  }
}

/**
 * Отрисовывает строки таблицы ресурсоемких процессов.
 * @param {Array} processes - Список процессов.
 */
export function renderHeavyTable(processes) {
  const tableBody = document.getElementById('sw-heavy-table-body');
  if (!tableBody) return;

  if (!processes || processes.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-4 text-muted">
          Нет активных процессов с высокой нагрузкой.
        </td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = processes.map((p, idx) => {
    const isHighCpu = (p.cpu_percent || 0) > 20.0;
    const isHighRam = (p.memory_mb || 0) > 1000;
    const cpuClass = isHighCpu ? 'text-danger fw-bold' : ((p.cpu_percent || 0) > 5.0 ? 'text-warning' : 'text-light');
    const ramClass = isHighRam ? 'text-danger fw-bold' : ((p.memory_mb || 0) > 400 ? 'text-warning' : 'text-light');

    return `
      <tr class="sw-heavy-row" style="cursor: pointer;" onclick="window.triggerHeavyAnomalyAnalysis(${idx})" title="Кликните для анализа аномалии ИИ">
        <td class="font-monospace text-secondary">${p.pid || '—'}</td>
        <td>
          <div class="fw-semibold text-light">${escapeHtml(p.name)}</div>
          <div class="small text-muted font-monospace text-truncate" style="max-width: 320px;" title="${escapeHtml(p.path || p.cmdline || '')}">${escapeHtml(p.path || p.cmdline || '—')}</div>
        </td>
        <td class="${cpuClass}">${p.cpu_percent != null ? p.cpu_percent.toFixed(1) + '%' : '0.0%'}</td>
        <td class="${ramClass}">${p.memory_mb != null ? p.memory_mb.toFixed(1) + ' МБ' : '0.0 МБ'}</td>
        <td class="font-monospace text-muted">${p.io_read_mbs != null ? p.io_read_mbs.toFixed(2) + ' МБ/с' : '0.00 МБ/с'}</td>
      </tr>
    `;
  }).join('');

  currentHeavyProcesses = processes;
  window._currentHeavyProcesses = processes;
}

/**
 * Запускает экспертный ИИ-анализ аномального потребления ресурсов процессом.
 * @param {number} idx - Индекс процесса в списке.
 */
export function triggerHeavyAnomalyAnalysis(idx) {
  const p = (window._currentHeavyProcesses || currentHeavyProcesses || [])[idx];
  if (!p) return;

  if (window.AIModalDialog && typeof window.AIModalDialog.open === 'function') {
    window.AIModalDialog.open({
      program: {
        name: p.name,
        pid: p.pid,
        path: p.path,
        cmdline: p.cmdline,
        cpu_percent: p.cpu_percent,
        memory_mb: p.memory_mb,
        risk_level: p.risk_level || 'Medium'
      },
      panelId: 'heavy-resources',
      tableType: 'software',
      prompt: 'Проведи углубленный анализ аномального потребления ресурсов CPU и памяти'
    });
  } else {
    alert(`Анализ аномалии для процесса ${p.name} (PID ${p.pid})`);
  }
}

// Экспорт для глобального использования в inline onclick
if (typeof window !== 'undefined') {
  window.triggerHeavyAnomalyAnalysis = triggerHeavyAnomalyAnalysis;
}
