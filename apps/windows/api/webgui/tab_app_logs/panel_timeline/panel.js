/**
 * =============================================================================
 * Process Name: Windows App Logs - Timeline and Analytics Panel
 * =============================================================================
 * Description:
 *   Модуль визуализации распределения логов во времени (Timeline-гистограмма),
 *   аналитики ошибок и распределения по модулям приложения.
 *
 * File: panel_timeline/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_timeline
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, escapeHtml } from '../common/ui_utils.js';

/**
 * Отрисовывает интерактивный график временной шкалы и статистику компонентов.
 * @param {Function} [onTimeSlotClick=null] - Обработчик клика по столбцу времени.
 * @param {Function} [onComponentClick=null] - Обработчик клика по карточке модуля.
 */
export function renderTimelineChart(onTimeSlotClick = null, onComponentClick = null) {
  const barsContainer = document.getElementById('apl-timeline-bars');
  const compContainer = document.getElementById('apl-top-components-container');
  if (!state.stats) return;

  const timeline = state.stats.timeline || [];
  if (barsContainer) {
    if (timeline.length === 0) {
      barsContainer.innerHTML = '<div class="text-muted small p-3 text-center w-100">Недостаточно временных меток для построения графика.</div>';
    } else {
      const maxTotal = Math.max(...timeline.map((t) => t.total), 1);
      barsContainer.innerHTML = timeline.map((t) => {
        const heightPct = Math.max(10, (t.total / maxTotal) * 100);
        const timeLabel = t.time.slice(11, 16);

        const hasErr = t.errors > 0;
        const hasWarn = t.warnings > 0;
        let barBg = 'linear-gradient(to top, var(--nav-active, #0284c7) 0%, var(--nav-active, #38bdf8) 100%)';
        if (hasErr) {
          barBg = 'linear-gradient(to top, #ef4444 0%, #dc2626 100%)';
        } else if (hasWarn) {
          barBg = 'linear-gradient(to top, #f59e0b 0%, #d97706 100%)';
        }

        return `
          <div class="d-flex flex-column align-items-center apl-timeline-bar-item" data-time="${t.time}" style="flex: 1; min-width: 32px; height: 100%; justify-content: flex-end;" title="${t.time}: Всего событий: ${t.total}, Ошибок: ${t.errors}, Предупреждений: ${t.warnings}">
            <span class="small font-monospace text-muted" style="font-size: 0.65rem;">${t.total}</span>
            <div class="w-100 rounded-top" style="height: ${heightPct}%; background: ${barBg}; position: relative;">
            </div>
            <span class="small font-monospace text-muted text-truncate" style="font-size: 0.65rem; margin-top: 4px;">${timeLabel}</span>
          </div>
        `;
      }).join('');

      barsContainer.querySelectorAll('.apl-timeline-bar-item').forEach((bar) => {
        bar.addEventListener('click', () => {
          const tVal = bar.getAttribute('data-time');
          if (typeof onTimeSlotClick === 'function') {
            onTimeSlotClick(tVal);
          }
        });
      });
    }
  }

  if (compContainer && state.stats.components) {
    compContainer.innerHTML = state.stats.components.map((c) => `
      <div class="col-md-3 col-sm-6">
        <div class="card apl-card p-2 d-flex flex-row justify-content-between align-items-center shadow-sm" style="cursor: pointer;" title="Фильтровать по модулю: ${escapeHtml(c.name)}">
          <span class="font-monospace small text-info text-truncate" style="max-width: 130px;">${escapeHtml(c.name)}</span>
          <span class="badge bg-primary rounded-pill font-monospace">${c.count}</span>
        </div>
      </div>
    `).join('');

    compContainer.querySelectorAll('.card').forEach((card, idx) => {
      card.addEventListener('click', () => {
        const cName = state.stats.components[idx]?.name;
        if (typeof onComponentClick === 'function') {
          onComponentClick(cName);
        }
      });
    });
  }
}
