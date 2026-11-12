/**
 * Модуль панели интеллектуального аудита журналов (Smart Digest & Pattern Deduplication).
 * 
 * Отвечает за:
 * - Кластеризацию и маскирование шаблонов событий (Template Extraction)
 * - Расчет индекса здоровья системы и надежности каналов
 * - Анализ стабильности электропитания и истории операций
 * 
 * Updated: 2026-11-11 23:20:00
 */

import { escapeHtml, formatTime, getSeverityClass, t } from '../common/ui_utils.js';
import { BrowserRagCache } from '../panel_rag/rag_db.js';

/**
 * Рендеринг интерфейса сводки аудита и кластеризованных шаблонов.
 * @param {Object} data
 * @param {boolean} fromCache
 */
export function renderAuditDigest(data, fromCache = false) {
  const contentEl = document.getElementById('slc-audit-content');
  if (!contentEl || !data) return;

  const totalEvents = data.total_events || 0;
  const critSum = data.critical_count || 0;
  const errSum = data.error_count || 0;
  const warnSum = data.warning_count || 0;

  const hasAnomalies = (data.anomalies && data.anomalies.length > 0) || critSum > 0 || errSum > 5;
  const alertIcon = hasAnomalies ? '⚠️' : '✅';
  const alertTitle = hasAnomalies ? t('systemControl.anomaliesDetected', 'Обнаружены системные аномалии или ошибки') : t('systemControl.normalStatus', 'Журнал в норме, критических сбоев не выявлено');
  const alertDesc = hasAnomalies ? t('systemControl.anomaliesDesc', 'В выбранном канале обнаружены критические события или аномальные всплески активности.') : t('systemControl.normalDesc', 'Шаблоны событий стабильны, ошибок высокой важности не обнаружено.');
  const alertBgColor = hasAnomalies ? 'rgba(239, 68, 68, 0.12)' : 'rgba(34, 197, 94, 0.12)';
  const alertBorderColor = hasAnomalies ? '#ef4444' : '#22c55e';

  let anomaliesItemsHtml = '';
  if (data.anomalies && data.anomalies.length > 0) {
    anomaliesItemsHtml = `
      <div class="mt-2 pt-2 border-top" style="border-color: rgba(255,255,255,0.1) !important;">
        <div class="small fw-bold mb-1 text-danger">Детали аномалий:</div>
        <ul class="mb-0 ps-3 small">
          ${data.anomalies.map(a => `<li>${escapeHtml(a.description || a.message || JSON.stringify(a))}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  const alertBannerHtml = `
    <div class="audit-alert-card ${hasAnomalies ? 'alert' : 'ok'} mb-2 shadow-sm" style="border-left: 5px solid ${alertBorderColor}; background: ${alertBgColor}; border-radius: var(--radius-md, 8px); padding: 0.75rem 1rem;">
      <div class="d-flex align-items-center">
        <div class="fs-4 me-2">${alertIcon}</div>
        <div>
          <div class="fw-bold" style="color: ${hasAnomalies ? '#d32f2f' : '#2e7d32'};">${alertTitle}</div>
          <div class="small text-muted">${alertDesc}</div>
        </div>
      </div>
      ${anomaliesItemsHtml}
    </div>
  `;

  const clustersList = data.clusters || data.top_clusters || [];
  let clustersHtml = '';
  if (clustersList && clustersList.length > 0) {
    clustersHtml = clustersList.slice(0, 15).map((c, i) => `
      <tr class="slc-cluster-row" data-idx="${i}" style="cursor: pointer;" title="Нажмите для AI-диагностики кластера">
        <td class="font-monospace" style="color: var(--text-muted);">${i + 1}</td>
        <td><span class="badge ${getSeverityClass(c.level)}">${escapeHtml(c.level || 'Info')}</span></td>
        <td class="text-truncate" style="max-width: 140px; color: var(--text-color);" title="${escapeHtml(c.provider)}">${escapeHtml(c.provider)}</td>
        <td class="font-monospace fw-bold" style="color: #0284c7;">${c.event_id || '-'}</td>
        <td class="small text-truncate" style="max-width: 340px; color: var(--text-color);" title="${escapeHtml(c.pattern || c.template)}">${escapeHtml(c.pattern || c.template)}</td>
        <td class="font-monospace fw-bold" style="color: var(--text-color);">${c.count}</td>
        <td class="font-monospace small" style="color: var(--text-muted);">${escapeHtml(formatTime(c.first_seen || data.generated_at))}</td>
      </tr>
    `).join('');
  } else {
    clustersHtml = `<tr><td colspan="7" class="text-center text-muted py-3">${escapeHtml(t('systemControl.noClusters', 'Кластеры не сформированы.'))}</td></tr>`;
  }

  contentEl.innerHTML = `
    ${fromCache ? `<div class="d-flex justify-content-between align-items-center mb-2 px-1"><span class="badge bg-info-subtle text-info border border-info-subtle font-monospace"><i class="bi bi-hdd me-1"></i>Загружено из кеша браузера</span><span class="small text-muted">${escapeHtml(data.generated_at || '')}</span></div>` : ''}
    <div class="row g-2 mb-3">
      <div class="col-sm-3 col-6">
        <div class="p-2 rounded border" style="background: var(--surface-1); border-color: var(--border-color) !important;">
          <div class="small text-muted" style="font-size: 0.72rem;">Всего проанализировано</div>
          <div class="fs-5 fw-bold text-info font-monospace">${totalEvents.toLocaleString()}</div>
        </div>
      </div>
      <div class="col-sm-3 col-6">
        <div class="p-2 rounded border" style="background: var(--surface-1); border-color: var(--border-color) !important;">
          <div class="small text-muted" style="font-size: 0.72rem;">Критических сбоев</div>
          <div class="fs-5 fw-bold text-danger font-monospace">${critSum}</div>
        </div>
      </div>
      <div class="col-sm-3 col-6">
        <div class="p-2 rounded border" style="background: var(--surface-1); border-color: var(--border-color) !important;">
          <div class="small text-muted" style="font-size: 0.72rem;">Ошибок</div>
          <div class="fs-5 fw-bold text-danger font-monospace">${errSum}</div>
        </div>
      </div>
      <div class="col-sm-3 col-6">
        <div class="p-2 rounded border" style="background: var(--surface-1); border-color: var(--border-color) !important;">
          <div class="small text-muted" style="font-size: 0.72rem;">Предупреждений</div>
          <div class="fs-5 fw-bold text-warning font-monospace">${warnSum}</div>
        </div>
      </div>
    </div>

    ${alertBannerHtml}

    <div class="slc-card shadow-sm">
      <div class="slc-card-header fw-bold d-flex justify-content-between align-items-center py-1.5 px-3">
        <span><i class="bi bi-collection me-2 text-primary"></i>Топ шаблонов событий (Дедупликация)</span>
        <span class="small text-muted">Топ 15 кластеров</span>
      </div>
      <div class="table-responsive">
        <table class="slc-table mb-0">
          <thead>
            <tr>
              <th style="width: 40px;">#</th>
              <th style="width: 80px;">Уровень</th>
              <th style="width: 140px;">Поставщик</th>
              <th style="width: 60px;">ID</th>
              <th>Шаблон сообщения (Masked)</th>
              <th style="width: 70px;">Кол-во</th>
              <th style="width: 140px;">Впервые</th>
            </tr>
          </thead>
          <tbody>
            ${clustersHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentEl.querySelectorAll('.slc-cluster-row').forEach(row => {
    row.onclick = () => {
      const idx = parseInt(row.getAttribute('data-idx'), 10);
      const c = clustersList[idx];
      if (!c) return;

      const modal = window.AIModalDialog || window.AITableModal;
      if (modal) {
        modal.show({
          icon: '📊',
          title: `Кластер #${c.event_id || 'GRP'} (${c.provider || 'Windows'})`,
          subtitle: `Повторений: ${c.count} | Уровень: ${c.level || 'Info'}`,
          panelId: 'panel-system-control-2',
          tableType: 'security_event',
          badges: [
            { text: `${c.count} повторений`, class: 'badge bg-warning text-dark font-monospace' },
            { text: c.level || 'Info', class: `badge ${getSeverityClass(c.level)}` }
          ],
          metadata: [
            { label: 'Event ID', value: String(c.event_id || '-') },
            { label: 'Поставщик', value: c.provider || '-' },
            { label: 'Уровень', value: c.level || 'Info' },
            { label: 'Всего повторений', value: String(c.count) },
            { label: 'Первое появление', value: c.first_seen || '-' }
          ],
          rawTitle: 'Шаблон сообщения (Masked Pattern)',
          rawContent: c.pattern || c.template || '',
          requestData: {
            event_id: c.event_id,
            provider: c.provider,
            count: c.count,
            pattern: c.pattern || c.template
          }
        });
      }
    };
  });
}

/**
 * Аудит стабильности электропитания и сессий.
 * @param {HTMLElement} contentEl
 */
export async function loadPowerAudit(contentEl) {
  contentEl.innerHTML = `<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm text-info me-2"></div>Аудит стабильности электропитания и сессий...</div>`;
  try {
    const sumRes = await fetch('/api/v1/power/summary');
    if (!sumRes.ok) throw new Error(`HTTP ${sumRes.status}`);
    const summary = await sumRes.json();
    const dirty = summary.unexpected_shutdowns_count || 0;
    const clean = summary.clean_shutdowns_count || 0;
    const crashes = summary.bsod_count || 0;
    const totalSess = summary.total_sessions_count || (clean + dirty);
    const uptimeStr = summary.current_uptime_human || 'N/A';
    const healthScore = Math.max(0, 100 - (dirty * 15 + crashes * 25));

    contentEl.innerHTML = `
      <div class="row g-2 mb-3">
        <div class="col-sm-3 col-6">
          <div class="slc-card p-2 text-center">
            <div class="text-muted small">Время непрерывной работы</div>
            <div class="fs-5 fw-bold font-monospace text-info">${escapeHtml(uptimeStr)}</div>
          </div>
        </div>
        <div class="col-sm-3 col-6">
          <div class="slc-card p-2 text-center">
            <div class="text-muted small">Штатных выключений</div>
            <div class="fs-4 fw-bold font-monospace text-success">${clean}</div>
          </div>
        </div>
        <div class="col-sm-3 col-6">
          <div class="slc-card p-2 text-center">
            <div class="text-muted small">Аварийных выключений (Dirty/BSOD)</div>
            <div class="fs-4 fw-bold font-monospace ${dirty + crashes > 0 ? 'text-danger' : 'text-muted'}">${dirty + crashes}</div>
          </div>
        </div>
        <div class="col-sm-3 col-6">
          <div class="slc-card p-2 text-center">
            <div class="text-muted small">Индекс стабильности питания</div>
            <div class="fs-4 fw-bold font-monospace ${healthScore >= 80 ? 'text-success' : 'text-warning'}">${healthScore}/100</div>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    contentEl.innerHTML = `<div class="alert alert-danger">Ошибка проведения аудита: ${escapeHtml(e.message)}</div>`;
  }
}

/**
 * Основная функция запуска аудита для активного источника или канала.
 * @param {string} targetChannel
 * @param {string} activeSource
 * @param {string} currentFilePath
 */
export async function loadAuditDigest(targetChannel, activeSource = 'event-logs', currentFilePath = '') {
  const contentEl = document.getElementById('slc-audit-content');
  if (!contentEl) return;

  if (activeSource === 'power-lifecycle') {
    loadPowerAudit(contentEl);
    return;
  }

  const cleanChan = (targetChannel || 'System').replace(/^evt:/i, '');
  const hoursSelect = document.getElementById('slc-hours-select');
  const hours = hoursSelect ? hoursSelect.value : '24';
  const cacheKey = `audit_${cleanChan}_${hours}_${currentFilePath}`;

  const cached = BrowserRagCache.get(cacheKey);
  if (cached) {
    renderAuditDigest(cached, true);
  } else {
    contentEl.innerHTML = `<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm text-info me-2"></div>Формирование сводки аудита и дедупликации... (${escapeHtml(cleanChan)})</div>`;
  }

  try {
    const res = await fetch(`/api/v1/system_logs/audit?channel=${encodeURIComponent(cleanChan)}&hours=${hours}&limit=300&file_path=${encodeURIComponent(currentFilePath || '')}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    BrowserRagCache.set(cacheKey, data);
    renderAuditDigest(data, false);
  } catch (err) {
    if (!cached) {
      contentEl.innerHTML = `<div class="alert alert-danger">Ошибка проведения аудита: ${escapeHtml(err.message)}</div>`;
    }
  }
}
