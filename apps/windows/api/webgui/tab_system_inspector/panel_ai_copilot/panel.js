/**
 * =============================================================================
 * Process Name: System Inspector - AI Copilot Panel
 * =============================================================================
 * Description:
 *   Модуль панели AI Copilot для интеллектуальной диагностики оборудования,
 *   выявления аномалий подсистем (CPU/RAM/GPU/Storage) и вывода рекомендаций.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_ai_copilot
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Инициализация панели AI Copilot и привязка кнопок аудита.
 */
export function initAiCopilotPanel() {
  const btnAudit = document.getElementById('btn-sys-run-audit');
  if (btnAudit) {
    btnAudit.onclick = () => runAiDiagnostics();
  }
}

/**
 * Запуск глубокого AI-аудита системы и оборудования.
 */
export async function runAiDiagnostics() {
  const summaryEl = document.getElementById('sys-ai-summary-text');
  const badgeEl = document.getElementById('sys-ai-health-badge');
  const anomaliesEl = document.getElementById('sys-ai-anomalies-container');
  const engineTagEl = document.getElementById('sys-ai-model-tag');

  if (summaryEl) summaryEl.innerText = 'Запуск глубокого AI-аудита системы и оборудования...';

  try {
    const res = await fetch('/api/v1/system/diagnose', { method: 'POST' });
    if (!res.ok) throw new Error('AI Diagnosis error');
    const report = await res.json();

    if (badgeEl) {
      badgeEl.innerText = `Health: ${report.health_score || 100}/100`;
      badgeEl.className = `badge ${report.health_score >= 80 ? 'bg-success' : report.health_score >= 60 ? 'bg-warning' : 'bg-danger'}`;
    }

    if (engineTagEl) {
      engineTagEl.innerText = report.ai_model_used || 'Heuristic Engine';
    }

    if (anomaliesEl) {
      if (Array.isArray(report.anomalies) && report.anomalies.length > 0) {
        anomaliesEl.innerHTML = report.anomalies.map(a => `<span class="anomaly-tag">⚠️ [${a.subsystem}] ${escapeHtml(a.title)}</span>`).join('');
      } else {
        anomaliesEl.innerHTML = '<span style="color: #4ade80; font-size: 0.75rem;"><i class="bi bi-check-circle me-1"></i> Аномалий в работе оборудования не обнаружено</span>';
      }
    }

    if (summaryEl) {
      const recs = Array.isArray(report.recommendations) && report.recommendations.length > 0
        ? `\nРекомендации: ${report.recommendations.join(', ')}`
        : '';
      summaryEl.innerText = `${report.summary || 'Телеметрия в норме.'}${recs}`;
    }
  } catch (e) {
    console.error('[AiCopilotPanel] Ошибка AI-диагностики:', e);
    if (summaryEl) summaryEl.innerText = 'Ошибка выполнения AI-диагностики: ' + e.message;
  }
}
