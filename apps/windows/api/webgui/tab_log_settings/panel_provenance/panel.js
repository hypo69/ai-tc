/**
 * =============================================================================
 * Process Name: Windows Log Settings - Process Provenance Graph Panel
 * =============================================================================
 * Description:
 *   Модуль реконструкции происхождения процессов (Process Provenance):
 *   цепочки User → Process → Parent → Service → Task на основе Event 4688.
 *
 * File: panel_provenance/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_provenance
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Строит граф происхождения процессов по имени процесса или для всего хоста.
 */
export async function buildProcessProvenance() {
  const input = document.getElementById('ls-prov-process-input');
  const processName = input ? input.value.trim() : '';
  const container = document.getElementById('ls-prov-tree-view');
  if (!container) return;

  container.innerHTML = '<div class="text-center text-warning py-4"><div class="spinner-border spinner-border-sm me-2"></div>Построение графа происхождения процессов...</div>';

  try {
    const params = new URLSearchParams();
    if (processName) params.append('process_name', processName);
    params.append('hours', '72');

    const res = await fetch(`/api/v1/log-settings/provenance/process?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const nodes = data.nodes || [];
    const links = data.links || [];

    if (nodes.length === 0) {
      container.innerHTML = `
        <div class="text-center text-muted py-5">
          <i class="bi bi-info-circle fs-3 text-secondary d-block mb-2"></i>
          События создания процессов (Event 4688) для <strong>${escapeHtml(processName || 'хоста')}</strong> не найдены в telemetry.db.<br>
          <small class="text-secondary">Убедитесь, что аудит CommandLine включен и выполнен сбор новых событий.</small>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="mb-3 d-flex justify-content-between align-items-center">
        <span class="badge bg-warning text-dark font-monospace">${nodes.length} Узлов (Nodes)</span>
        <span class="badge bg-info text-dark font-monospace">${links.length} Связей (Spawns / Forks)</span>
      </div>
      <div class="d-flex flex-column gap-2">
        ${nodes.map((n) => {
          let typeBadge = 'bg-primary';
          if (n.type === 'parent_process') typeBadge = 'bg-info text-dark';
          else if (n.type === 'service') typeBadge = 'bg-success';

          return `
            <div class="p-2 bg-dark rounded border border-secondary d-flex align-items-center justify-content-between flex-wrap gap-2">
              <div class="d-flex align-items-center gap-2">
                <span class="badge ${typeBadge} font-monospace" style="font-size: 0.72rem;">${escapeHtml(n.role || n.type)}</span>
                <strong class="text-light font-monospace">${escapeHtml(n.name)}</strong>
                ${n.pid ? `<span class="badge bg-secondary font-monospace">PID ${n.pid}</span>` : ''}
              </div>
              <div class="small text-muted font-monospace">${escapeHtml(n.user || '')} • ${escapeHtml(n.timestamp || '')}</div>
              ${n.command_line ? `<div class="w-100 bg-black p-1.5 rounded font-monospace small text-success text-break" style="font-size: 0.72rem;">${escapeHtml(n.command_line)}</div>` : ''}
            </div>
          `;
        }).join('')}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="text-center text-danger py-4">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}
