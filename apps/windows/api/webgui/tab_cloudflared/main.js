// =============================================================================
// Process Name: Cloudflared Monitor Web Tab Module
// =============================================================================
// Description:
//   Клиентский JavaScript-контроллер для вкладки веб-интерфейса Cloudflare Tunnel
//   (kino.davidka.net).
//
// File: main.js
// Project: ai-windows-admin
// Package: apps.windows.api.webgui.tab_cloudflared
// Author: hypo69
// Copyright: © 2026 hypo69
// Updated: 2026-10-30 14:00:00
// =============================================================================

(function() {
  let isCfInitialized = false;
  let cfPollInterval = null;

  async function fetchTunnelStatus() {
    try {
      const res = await fetch('/api/cloudflared/status');
      if (!res.ok) return;
      const data = await res.json();
      
      const badge = document.getElementById('cf-daemon-badge');
      const ingressEl = document.getElementById('cf-ingress-url');
      const endpointEl = document.getElementById('cf-endpoint-status');
      const usageEl = document.getElementById('cf-process-usage');
      const healthEl = document.getElementById('cf-health-score');

      const isRunning = Boolean(data.is_running || data.daemon_running);

      if (badge) {
        badge.className = isRunning
          ? 'badge rounded-pill bg-success-subtle text-success border border-success px-2.5 py-1'
          : 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-2.5 py-1';
        badge.innerText = isRunning ? '● Туннель активен' : '● Туннель остановлен';
      }

      if (ingressEl) ingressEl.innerText = data.public_url || 'https://kino.davidka.net';
      if (endpointEl) {
        const reachable = Boolean(data.endpoint_reachable);
        endpointEl.innerText = reachable ? `Доступен (${data.endpoint_latency_ms || data.latency_ms || 0} мс)` : 'Недоступен';
        endpointEl.className = reachable ? 'cf-value text-success' : 'cf-value text-danger';
      }
      if (usageEl) {
        usageEl.innerText = `${data.cpu_percent || 0}% / ${data.memory_mb || 0} MB`;
      }
      if (healthEl) {
        const score = data.health_score !== undefined ? data.health_score : 100;
        healthEl.innerText = `${score}/100`;
        healthEl.className = score >= 80 ? 'cf-value text-success' : (score >= 50 ? 'cf-value text-warning' : 'cf-value text-danger');
      }
    } catch (e) {
      console.warn('[CloudflaredTab] Ошибка получения статуса:', e);
    }
  }

  async function fetchLogs() {
    try {
      const res = await fetch('/api/cloudflared/logs?limit=50');
      if (!res.ok) return;
      const data = await res.json();
      const logs = data.logs || [];
      
      const terminal = document.getElementById('cf-log-terminal-output');
      const countBadge = document.getElementById('cf-log-count-badge');
      if (countBadge) countBadge.innerText = `${logs.length} строк`;

      if (terminal) {
        if (logs.length === 0) {
          terminal.innerText = 'Журнал cloudflared пуст.';
          return;
        }
        terminal.innerHTML = logs.map(l => {
          const lvl = (l.level || 'INFO').toUpperCase();
          const color = lvl === 'ERROR' || lvl === 'ERR' ? 'var(--status-danger, #f87171)' : ((lvl === 'WARN' || lvl === 'WRN') ? 'var(--status-warning, #fbbf24)' : 'var(--text-muted, #94a3b8)');
          const time = l.timestamp || l.time || '';
          const msg = l.message || l.msg || l.raw || '';
          return `<div style="color: ${color};">[${time}] [${lvl}] ${msg}</div>`;
        }).join('');
      }
    } catch (e) {
      console.warn('[CloudflaredTab] Ошибка получения журналов:', e);
    }
  }

  async function runDiagnostics() {
    try {
      const res = await fetch('/api/cloudflared/diagnostic');
      if (!res.ok) return;
      const report = await res.json();

      const titleEl = document.getElementById('cf-diag-summary-title');
      const descEl = document.getElementById('cf-diag-summary-desc');
      const recList = document.getElementById('cf-recommendations-list');

      if (titleEl) titleEl.innerText = `Здоровье: ${report.status || 'OK'} (${report.health_score || 100}/100)`;
      if (descEl) descEl.innerText = report.summary || 'Все туннельные соединения стабильны.';

      if (recList && Array.isArray(report.recommendations)) {
        recList.innerHTML = report.recommendations.map(r => `
          <li class="list-group-item bg-transparent text-light border-secondary border-opacity-25 py-1 px-0">• ${r}</li>
        `).join('');
      }
    } catch (e) {
      console.warn('[CloudflaredTab] Ошибка запуска диагностики:', e);
    }
  }

  function initCloudflaredTab() {
    console.log('[CloudflaredTab] Инициализация вкладки Cloudflare Tunnel Monitor...');
    fetchTunnelStatus();
    fetchLogs();
    runDiagnostics();

    if (!isCfInitialized) {
      const refreshBtn = document.getElementById('btn-cf-refresh');
      const diagBtn = document.getElementById('btn-cf-run-diagnostics');
      const testBtn = document.getElementById('btn-cf-test-endpoint');
      const restartBtn = document.getElementById('btn-cf-restart-daemon');

      if (refreshBtn) {
        refreshBtn.onclick = () => {
          fetchTunnelStatus();
          fetchLogs();
          runDiagnostics();
        };
      }

      if (diagBtn) diagBtn.onclick = runDiagnostics;

      if (restartBtn) {
        restartBtn.onclick = async () => {
          if (!confirm('Перезапустить туннель Cloudflare?')) return;
          restartBtn.disabled = true;
          try {
            const res = await fetch('/api/cloudflared/restart', { method: 'POST' });
            const data = await res.json();
            alert(data.message || 'Перезапуск инициирован');
          } catch (e) {
            alert('Ошибка перезапуска: ' + e.message);
          } finally {
            restartBtn.disabled = false;
            fetchTunnelStatus();
          }
        };
      }

      if (testBtn) {
        testBtn.onclick = async () => {
          testBtn.disabled = true;
          testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Опрос...';
          try {
            const res = await fetch('/api/cloudflared/test-endpoint', { method: 'POST' });
            const data = await res.json();
            const msg = `Результат проверки Ingress:\nДоступен: ${data.is_reachable ? 'ДА' : 'НЕТ'}\nКод ответа: ${data.status_code || 'N/A'}\nЗадержка: ${data.response_time_ms || 0} мс`;
            alert(msg);
          } catch (e) {
            alert('Ошибка проверки эндпоинта: ' + e.message);
          } finally {
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="bi bi-broadcast me-1"></i> Проверить Ingress';
            fetchTunnelStatus();
          }
        };
      }

      isCfInitialized = true;
    }

    if (!cfPollInterval) {
      cfPollInterval = setInterval(() => {
        fetchTunnelStatus();
      }, 5000);
    }
  }

  function deactivateCloudflaredTab() {
    if (cfPollInterval) {
      clearInterval(cfPollInterval);
      cfPollInterval = null;
    }
  }

  window.initCloudflaredTab = initCloudflaredTab;
  window.deactivateCloudflaredTab = deactivateCloudflaredTab;
})();
