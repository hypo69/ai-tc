/**
 * =============================================================================
 * Process Name: Windows Log Settings - OS Lifecycle Timeline Panel
 * =============================================================================
 * Description:
 *   Модуль реконструкции хронологии жизненного цикла операционной системы:
 *   события включения, входа, гибернации, выключения и аварийных падений (Crash).
 *
 * File: panel_lifecycle/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_lifecycle
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Загружает и отображает таймлайн жизненного цикла операционной системы.
 */
export async function fetchPowerLifecycle() {
  const select = document.getElementById('ls-lifecycle-hours-select');
  const hours = select ? select.value : 72;
  const container = document.getElementById('ls-lifecycle-timeline');
  if (!container) return;

  container.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm text-danger me-2"></div>Реконструкция жизненного цикла ОС...</div>';

  try {
    const res = await fetch(`/api/v1/log-settings/lifecycle/power?hours=${hours}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const timeline = data.timeline || [];

    if (timeline.length === 0) {
      container.innerHTML = '<div class="text-center text-muted py-4">События жизненного цикла за указанный период не найдены.</div>';
      return;
    }

    container.innerHTML = timeline.map((item) => {
      let badgeClass = 'border-info text-info';
      if (item.severity === 'critical') badgeClass = 'border-danger text-danger bg-danger-subtle';
      else if (item.severity === 'warning') badgeClass = 'border-warning text-warning bg-warning-subtle';

      return `
        <div class="mb-3 position-relative pb-2 border-bottom border-secondary">
          <div class="d-flex align-items-center gap-2 mb-1">
            <span class="fs-5">${item.icon}</span>
            <span class="badge border ${badgeClass} font-monospace" style="font-size: 0.72rem;">${escapeHtml(item.phase)}</span>
            <span class="badge bg-dark border border-secondary font-monospace" style="font-size: 0.72rem;">ID ${item.event_id}</span>
            <span class="small text-secondary font-monospace ms-auto">${escapeHtml(item.timestamp)}</span>
          </div>
          <div class="text-light small fw-medium">${escapeHtml(item.message)}</div>
          <div class="text-muted font-monospace small" style="font-size: 0.72rem;">Источник: ${escapeHtml(item.provider)}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="text-center text-danger py-4">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}
