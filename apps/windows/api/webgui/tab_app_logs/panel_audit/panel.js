/**
 * =============================================================================
 * Process Name: Windows App Logs - AI Diagnostics and Audit Panel
 * =============================================================================
 * Description:
 *   Модуль интеллектуального аудита, оценки стабильности (Health Score),
 *   поиска первопричин сбоев, выработки рекомендаций и кластеризации инцидентов.
 *
 * File: panel_audit/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_app_logs/panel_audit
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { state, escapeHtml } from '../common/ui_utils.js';
import { openItemAiModal } from '../panel_table/panel.js';

/**
 * Запускает глубокую AI-диагностику и кластеризацию сбоев журнала.
 */
export async function runAiDiagnostics() {
  const summaryEl = document.getElementById('apl-audit-summary-text');
  const healthScoreEl = document.getElementById('apl-audit-health-score');
  const healthBar = document.getElementById('apl-audit-health-bar');
  const recsContainer = document.getElementById('apl-audit-recommendations-list');
  const clustersBody = document.getElementById('apl-audit-clusters-body');

  if (summaryEl) {
    summaryEl.innerHTML = '<div class="spinner-border spinner-border-sm text-info me-2"></div>Глубокий анализ логов, поиск первопричин и кластеризация сбоев...';
  }

  try {
    const res = await fetch('/api/v1/app_logs/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: state.currentFile,
        limit: 150,
        focus_errors_only: true,
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (healthScoreEl) healthScoreEl.textContent = `${data.health_score}%`;
    if (healthBar) {
      healthBar.style.width = `${data.health_score}%`;
      healthBar.className = `progress-bar ${data.health_score > 80 ? 'bg-success' : (data.health_score > 50 ? 'bg-warning' : 'bg-danger')}`;
    }

    if (summaryEl) summaryEl.textContent = data.summary;

    // Отрисовка рекомендаций
    if (recsContainer) {
      if (!data.recommendations || data.recommendations.length === 0) {
        recsContainer.innerHTML = '<div class="alert alert-success small mb-0"><i class="bi bi-check-circle me-1"></i>Активных сбоев и критических предупреждений не зафиксировано.</div>';
      } else {
        recsContainer.innerHTML = data.recommendations.map((r) => `
          <div class="card apl-card border-${r.severity === 'high' ? 'danger' : 'warning'} p-2.5 mb-2 shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-1">
              <span class="fw-bold text-${r.severity === 'high' ? 'danger' : 'warning'} small"><i class="bi bi-exclamation-triangle me-1"></i>${escapeHtml(r.title)}</span>
              <span class="badge bg-${r.severity === 'high' ? 'danger' : 'warning'} small">${r.severity.toUpperCase()}</span>
            </div>
            <div class="small text-body mb-1">${escapeHtml(r.description)}</div>
            <div class="small text-info"><i class="bi bi-arrow-right-circle me-1"></i><strong>Рекомендуемое действие:</strong> ${escapeHtml(r.action)}</div>
          </div>
        `).join('');
      }
    }

    // Отрисовка кластеров
    if (clustersBody) {
      if (!data.clusters || data.clusters.length === 0) {
        clustersBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Ошибок и повторяющихся инцидентов не зафиксировано.</td></tr>';
      } else {
        clustersBody.innerHTML = data.clusters.map((c, idx) => `
          <tr class="interactive-cluster-row" data-cluster-idx="${idx}" style="cursor: pointer;" title="Кликните для AI инспекции кластера">
            <td><span class="badge bg-danger fw-bold">${c.count}x</span></td>
            <td><span class="badge apl-card border border-danger text-danger">${escapeHtml(c.level)}</span></td>
            <td class="font-monospace small text-muted text-nowrap">${escapeHtml(c.last_seen || '--')}</td>
            <td class="font-monospace small text-break">
              <div class="fw-bold text-warning">${escapeHtml(c.pattern)}</div>
              <div class="text-muted small mt-0.5">${escapeHtml(c.sample_message)}</div>
            </td>
          </tr>
        `).join('');

        clustersBody.querySelectorAll('.interactive-cluster-row').forEach((row) => {
          row.addEventListener('click', (e) => {
            if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;
            const idx = parseInt(row.getAttribute('data-cluster-idx'), 10);
            const cluster = data.clusters[idx];
            if (!cluster) return;

            openItemAiModal({
              id: `cluster-${idx}`,
              level: cluster.level,
              component: 'Error Cluster',
              timestamp: cluster.last_seen,
              repeat_count: cluster.count,
              message: cluster.sample_message,
              exc_info: cluster.exc_info,
              raw: cluster.sample_message
            });
          });
        });
      }
    }
  } catch (err) {
    console.error('[AppLogs] Ошибка AI диагностики:', err);
    if (summaryEl) summaryEl.innerHTML = `<span class="text-danger">Ошибка диагностики: ${escapeHtml(err.message)}</span>`;
  }
}
