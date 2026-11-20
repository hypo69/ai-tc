/**
 * =============================================================================
 * Process Name: Windows Process Leaks Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления вкладкой аудита утечек ресурсов и микрофризов.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_process_leaks/main.js?v=20261013_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_process_leaks
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

(function () {
  'use strict';

  let rawLeakProcesses = [];
  let leakFilter = 'all';
  let autoRefreshTimer = null;
  const POLL_ID = 'process_leaks';

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text !== null && text !== undefined ? String(text) : '--';
  }

  async function apiFetch(url) {
    if (window.api && typeof window.api.fetch === 'function') {
      return await window.api.fetch(url);
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }

  async function fetchProcessLeaks() {
    const tbody = document.getElementById('diag-leaks-tbody');
    const refreshBtn = document.getElementById('btn-diag-leaks-refresh');
    const refreshIcon = refreshBtn?.querySelector('i');

    if (refreshBtn) refreshBtn.disabled = true;
    if (refreshIcon) refreshIcon.classList.add('spin-animation');

    // Если таблица пуста, отображаем индикатор загрузки
    if (tbody && (!rawLeakProcesses || rawLeakProcesses.length === 0)) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" class="text-center py-4 text-muted">
            <div class="spinner-border spinner-border-sm text-info me-2" role="status"></div>
            Загрузка данных глубокой диагностики процессов...
          </td>
        </tr>
      `;
    }

    try {
      const data = await apiFetch('/api/v1/system/diagnostics/leaks?limit=100');
      if (!data) return;

      setText('diag-leaks-total-proc', data.total_processes ?? 0);
      setText('diag-leaks-suspicious-count', data.suspicious_count ?? 0);

      if (data.top_handle_hogs && data.top_handle_hogs.length > 0) {
        const topH = data.top_handle_hogs[0];
        setText('diag-leaks-peak-handles', `${(topH.handles_count || 0).toLocaleString()} шт.`);
        setText('diag-leaks-peak-handles-proc', `Процесс: ${topH.name || 'неизвестно'} (PID ${topH.pid})`);
      } else {
        setText('diag-leaks-peak-handles', '0 шт.');
        setText('diag-leaks-peak-handles-proc', 'Аномалий не обнаружено');
      }

      if (data.top_gdi_hogs && data.top_gdi_hogs.length > 0) {
        const topG = data.top_gdi_hogs[0];
        setText('diag-leaks-peak-gdi', `${(topG.gdi_objects || 0).toLocaleString()} шт.`);
        setText('diag-leaks-peak-gdi-proc', `Процесс: ${topG.name || 'неизвестно'} (PID ${topG.pid})`);
      } else {
        setText('diag-leaks-peak-gdi', '0 шт.');
        setText('diag-leaks-peak-gdi-proc', 'Лимит OS: 10 000');
      }

      rawLeakProcesses = data.all_processes || [];
      renderProcessLeaksTable(rawLeakProcesses);
    } catch (err) {
      console.warn('[ProcessLeaksTab] fetchProcessLeaks error:', err);
      if (tbody && rawLeakProcesses.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="10" class="text-center py-4 text-danger">
              <i class="bi bi-exclamation-triangle-fill me-2"></i>
              Не удалось загрузить данные телеметрии: ${escapeHtml(err.message)}
            </td>
          </tr>
        `;
      }
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
      if (refreshIcon) refreshIcon.classList.remove('spin-animation');
    }
  }

  function renderProcessLeaksTable(processes) {
    const tbody = document.getElementById('diag-leaks-tbody');
    if (!tbody) return;

    const query = (document.getElementById('diag-leaks-search')?.value || '').trim().toLowerCase();

    const list = Array.isArray(processes) ? processes : [];
    let filtered = list.filter(p => {
      if (!p) return false;
      const name = String(p.name || '').toLowerCase();
      const pidStr = String(p.pid || '');
      if (query && !name.includes(query) && !pidStr.includes(query)) {
        return false;
      }
      if (leakFilter === 'suspicious') return p.leak_risk_score !== 'normal';
      if (leakFilter === 'gdi') return (p.gdi_objects || 0) > 500;
      if (leakFilter === 'handles') return (p.handles_count || 0) > 1500;
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-muted">Процессов по заданным критериям не найдено</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(p => {
      let riskBadge = '<span class="diag-badge-normal">Норма</span>';
      if (p.leak_risk_score === 'critical') {
        riskBadge = '<span class="diag-badge-critical">Критический</span>';
      } else if (p.leak_risk_score === 'warning') {
        riskBadge = '<span class="diag-badge-warning">Внимание</span>';
      }

      const reasons = (p.leak_risk_reasons && p.leak_risk_reasons.length > 0)
        ? p.leak_risk_reasons.map(r => `<span class="badge bg-dark border border-secondary text-warning me-1">${escapeHtml(r)}</span>`).join('')
        : '<span class="text-muted small">Штатное поведение</span>';

      const handles = Number(p.handles_count || 0);
      const gdi = Number(p.gdi_objects || 0);
      const userObj = Number(p.user_objects || 0);
      const pageFaults = Number(p.page_faults_total || 0);
      const memMb = Number(p.memory_mb || 0);
      const threads = Number(p.threads_count || 0);

      return `
        <tr>
          <td><span class="text-info font-monospace">${p.pid}</span></td>
          <td class="fw-bold text-white text-truncate" style="max-width: 180px;" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</td>
          <td style="text-align: right;" class="${handles > 1500 ? 'text-danger fw-bold' : 'text-light'}">${handles.toLocaleString()}</td>
          <td style="text-align: right;" class="${gdi > 800 ? 'text-danger fw-bold' : 'text-light'}">${gdi.toLocaleString()}</td>
          <td style="text-align: right;" class="${userObj > 400 ? 'text-warning' : 'text-light'}">${userObj.toLocaleString()}</td>
          <td style="text-align: right;" class="text-muted font-monospace">${pageFaults.toLocaleString()}</td>
          <td style="text-align: right;" class="text-warning">${memMb.toFixed(1)} MB</td>
          <td style="text-align: right;" class="text-muted">${threads}</td>
          <td>${riskBadge}</td>
          <td>${reasons}</td>
        </tr>
      `;
    }).join('');
  }

  function getFrequency() {
    try {
      const saved = localStorage.getItem(`poll_freq_${POLL_ID}`);
      if (saved) return saved;
    } catch (_) {}
    return 'manual';
  }

  function setFrequency(freq) {
    try {
      localStorage.setItem(`poll_freq_${POLL_ID}`, freq);
    } catch (_) {}
    applyPoller(freq, false);
  }

  function stopPolling() {
    if (window.unregisterTabPoller) {
      window.unregisterTabPoller(`tab-process-leaks_${POLL_ID}`);
    }
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  function applyPoller(freq, runInitial = false) {
    stopPolling();
    if (freq === 'start' || freq === 'manual') {
      if (runInitial) {
        fetchProcessLeaks();
      }
      return;
    }

    const intervalSec = parseInt(freq, 10);
    if (isNaN(intervalSec) || intervalSec <= 0) return;

    const intervalMs = intervalSec * 1000;
    const pollerId = `tab-process-leaks_${POLL_ID}`;

    if (window.registerTabPoller) {
      window.registerTabPoller('tab-process-leaks', fetchProcessLeaks, intervalMs, { pollerId, immediate: runInitial });
    } else {
      if (runInitial) {
        fetchProcessLeaks();
      }
      autoRefreshTimer = setInterval(() => {
        if (window.isTabActive ? window.isTabActive('tab-process-leaks') : true) {
          fetchProcessLeaks();
        }
      }, intervalMs);
    }
  }

  function bindEvents() {
    const leakFilters = document.getElementById('diag-leaks-filter-group');
    if (leakFilters) {
      leakFilters.querySelectorAll('button').forEach(btn => {
        btn.onclick = () => {
          leakFilters.querySelectorAll('button').forEach(b => {
            b.classList.remove('active', 'btn-info', 'btn-danger');
            b.classList.add('btn-outline-secondary');
          });
          const f = btn.getAttribute('data-filter') || 'all';
          btn.classList.add('active', f === 'suspicious' ? 'btn-danger' : 'btn-info');
          btn.classList.remove('btn-outline-secondary');
          leakFilter = f;
          renderProcessLeaksTable(rawLeakProcesses);
        };
      });
    }

    const leakSearch = document.getElementById('diag-leaks-search');
    if (leakSearch) {
      leakSearch.oninput = () => renderProcessLeaksTable(rawLeakProcesses);
    }

    const btnLeaksRefresh = document.getElementById('btn-diag-leaks-refresh');
    if (btnLeaksRefresh) {
      btnLeaksRefresh.onclick = () => {
        fetchProcessLeaks();
      };
    }

    const select = document.getElementById('diag-leaks-poll-freq');
    if (select) {
      select.onchange = (e) => {
        const newFreq = e.target.value;
        setFrequency(newFreq);
        if (newFreq !== 'manual' && newFreq !== 'start') {
          fetchProcessLeaks();
        }
        if (window.showToast) {
          const label = select.options[select.selectedIndex]?.text || newFreq;
          window.showToast(`Частота опроса утечек: ${label}`, 'info');
        }
      };
    }
  }

  async function initProcessLeaksTab() {
    bindEvents();
    const currentFreq = getFrequency();
    const select = document.getElementById('diag-leaks-poll-freq');
    if (select) select.value = currentFreq;
    applyPoller(currentFreq, true);
  }

  window.initProcessLeaksTab = initProcessLeaksTab;
  window.activateProcessLeaksTab = () => {
    applyPoller(getFrequency(), true);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initProcessLeaksTab();
    });
  } else {
    initProcessLeaksTab();
  }
})();

