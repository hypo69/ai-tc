/**
 * =============================================================================
 * Process Name: Windows Forensics Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом форензики и суб-вкладками:
 *   Хронологический таймлайн активности (Telemetry Timeline) и
 *   Форензика запуска программ из реестра Windows (UserAssist ROT13).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_forensics/main.js?v=20261016_v2" type="module"></script>
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_forensics
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 16:42:00
 * =============================================================================
 */

(function () {
  'use strict';

  let autoRefreshTimer = null;
  const POLL_ID = 'forensics';
  const SUBTAB_STORAGE_KEY = 'forensics_active_subtab';

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

  function formatTime(isoStr) {
    if (!isoStr) return '--:--:--';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
             ' (' + d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) + ')';
    } catch (_) {
      return isoStr;
    }
  }

  async function apiFetch(url) {
    if (window.api && typeof window.api.fetch === 'function') {
      return await window.api.fetch(url);
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }

  async function fetchForensicsActivity(forceRefresh = false) {
    try {
      const url = forceRefresh ? '/api/v1/system/diagnostics/forensics?refresh=true' : '/api/v1/system/diagnostics/forensics';
      const data = await apiFetch(url);
      if (!data) return;

      if (data.foreground_window) {
        setText('diag-fg-title', data.foreground_window.title || 'Рабочий стол Windows');
        setText('diag-fg-proc', `Процесс: ${data.foreground_window.process_name || 'unknown'} (PID: ${data.foreground_window.pid || 0})`);
      }

      const idleSec = data.user_idle_seconds !== undefined ? Number(data.user_idle_seconds) : 0;
      setText('diag-user-idle-time', `${idleSec.toFixed(1)} сек`);
      const statusBadge = document.getElementById('diag-user-status-badge');
      if (statusBadge) {
        if (idleSec > 300) {
          statusBadge.className = 'badge bg-warning-subtle text-warning border border-warning';
          statusBadge.textContent = 'Пользователь отошел (>5 мин)';
        } else {
          statusBadge.className = 'badge bg-success-subtle text-success border border-success';
          statusBadge.textContent = 'Пользователь активен';
        }
      }

      // Camera Apps
      const camContainer = document.getElementById('diag-cam-access-list');
      if (camContainer) {
        if (data.camera_active_apps && data.camera_active_apps.length > 0) {
          camContainer.innerHTML = data.camera_active_apps.map(a => `
            <div class="d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle">
              <span class="text-truncate" style="max-width: 140px;" title="${escapeHtml(a.app_name)}">${escapeHtml(a.app_name)}</span>
              <span class="badge ${a.is_active_now ? 'bg-danger' : 'bg-secondary'}" style="font-size: 0.65rem;">
                ${a.is_active_now ? 'Захват камеры' : 'В доступе'}
              </span>
            </div>
          `).join('');
        } else {
          camContainer.innerHTML = '<span class="text-muted small">Нет активных обращений к камере</span>';
        }
      }

      // Mic Apps
      const micContainer = document.getElementById('diag-mic-access-list');
      if (micContainer) {
        if (data.microphone_active_apps && data.microphone_active_apps.length > 0) {
          micContainer.innerHTML = data.microphone_active_apps.map(a => `
            <div class="d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle">
              <span class="text-truncate" style="max-width: 140px;" title="${escapeHtml(a.app_name)}">${escapeHtml(a.app_name)}</span>
              <span class="badge ${a.is_active_now ? 'bg-danger' : 'bg-secondary'}" style="font-size: 0.65rem;">
                ${a.is_active_now ? 'Запись звука' : 'В доступе'}
              </span>
            </div>
          `).join('');
        } else {
          micContainer.innerHTML = '<span class="text-muted small">Нет активных обращений к микрофону</span>';
        }
      }

      // Timeline History Table
      const timelineTbody = document.getElementById('diag-timeline-tbody');
      if (timelineTbody) {
        const historyList = data.history || [];
        setText('diag-timeline-count', `${historyList.length} срезов`);
        setText('subtab-forensics-timeline-badge', `${historyList.length}`);
        if (historyList.length === 0) {
          timelineTbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Снимков активности в базе пока нет. Они накапливаются демоном телеметрии...</td></tr>';
        } else {
          timelineTbody.innerHTML = historyList.map(h => {
            const fg = h.foreground_window || {};
            const timeStr = formatTime(h.timestamp);
            const idle = Number(h.user_idle_seconds || 0).toFixed(0);
            const hasCam = (h.camera_active_apps || []).some(x => x.is_active_now);
            const hasMic = (h.microphone_active_apps || []).some(x => x.is_active_now);
            let sensorBadge = '<span class="text-muted">-</span>';
            if (hasCam && hasMic) {
              sensorBadge = '<span class="badge bg-danger" title="Камера + Микрофон">Cam + Mic</span>';
            } else if (hasCam) {
              sensorBadge = '<span class="badge bg-danger" title="Камера активна">Cam</span>';
            } else if (hasMic) {
              sensorBadge = '<span class="badge bg-warning text-dark" title="Микрофон активен">Mic</span>';
            }

            return `
              <tr>
                <td class="text-muted font-monospace small">${escapeHtml(timeStr)}</td>
                <td class="fw-bold text-info"><i class="bi bi-window text-secondary me-1"></i>${escapeHtml(fg.process_name || 'unknown')} <span class="text-muted small">(${fg.pid || 0})</span></td>
                <td class="text-body text-truncate" style="max-width: 320px;" title="${escapeHtml(fg.title || '')}">${escapeHtml(fg.title || '-')}</td>
                <td style="text-align: right;" class="font-monospace ${idle > 300 ? 'text-warning' : 'text-body'}">${idle} с</td>
                <td style="text-align: center;">${sensorBadge}</td>
              </tr>
            `;
          }).join('');
        }
      }

      // UserAssist Apps Table
      const uaTbody = document.getElementById('diag-userassist-tbody');
      if (uaTbody && data.userassist_top_apps) {
        setText('diag-userassist-count', `${data.userassist_top_apps.length} программ`);
        setText('subtab-forensics-userassist-badge', `${data.userassist_top_apps.length}`);
        if (data.userassist_top_apps.length === 0) {
          uaTbody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-muted">Данных UserAssist в реестре не обнаружено (или трекинг отключен в Windows)</td></tr>';
        } else {
          uaTbody.innerHTML = data.userassist_top_apps.map(a => `
            <tr>
              <td class="fw-bold text-white"><i class="bi bi-app text-info me-1.5"></i>${escapeHtml(a.name)}</td>
              <td style="text-align: right;" class="text-info font-monospace">${a.run_count} раз</td>
              <td style="text-align: right;" class="text-warning font-monospace">${escapeHtml(a.focus_formatted)}</td>
              <td class="small text-muted text-truncate" style="max-width: 280px;" title="${escapeHtml(a.path)}">${escapeHtml(a.path)}</td>
            </tr>
          `).join('');
        }
      }
    } catch (err) {
      console.warn('[ForensicsTab] fetchForensicsActivity error:', err);
    }
  }

  /**
   * Программное переключение между суб-вкладками форензики (как в tab-processes-load-inspector).
   * @param {string} subtabId - Идентификатор субвкладки ('timeline' | 'userassist')
   */
  function switchForensicsSubTab(subtabId) {
    let btnId = 'subtab-forensics-timeline-btn';
    const cleanId = String(subtabId || '').toLowerCase();
    if (cleanId === 'userassist' || cleanId === 'rot13' || cleanId === 'apps' || cleanId === 'registry') {
      btnId = 'subtab-forensics-userassist-btn';
    } else {
      btnId = 'subtab-forensics-timeline-btn';
    }

    const btn = document.getElementById(btnId);
    if (btn) {
      if (window.bootstrap && typeof window.bootstrap.Tab === 'function') {
        const tabInstance = window.bootstrap.Tab.getOrCreateInstance(btn);
        tabInstance.show();
      } else {
        btn.click();
      }
      try {
        localStorage.setItem(SUBTAB_STORAGE_KEY, btnId === 'subtab-forensics-userassist-btn' ? 'userassist' : 'timeline');
      } catch (_) {}
    }
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
      window.unregisterTabPoller(`tab-forensics_${POLL_ID}`);
    }
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  function applyPoller(freq, runInitial = false) {
    stopPolling();
    if (freq === 'start' || freq === 'manual') {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-forensics') : true)) {
        fetchForensicsActivity();
      }
      return;
    }

    const intervalSec = parseInt(freq, 10);
    if (isNaN(intervalSec) || intervalSec <= 0) return;

    const intervalMs = intervalSec * 1000;
    const pollerId = `tab-forensics_${POLL_ID}`;

    if (window.registerTabPoller) {
      window.registerTabPoller('tab-forensics', fetchForensicsActivity, intervalMs, { pollerId, immediate: runInitial });
    } else {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-forensics') : true)) {
        fetchForensicsActivity();
      }
      autoRefreshTimer = setInterval(() => {
        if (window.isTabActive ? window.isTabActive('tab-forensics') : true) {
          fetchForensicsActivity();
        }
      }, intervalMs);
    }
  }

  function bindEvents() {
    const btnRefresh = document.getElementById('btn-diag-forensics-refresh');
    if (btnRefresh) {
      btnRefresh.onclick = () => fetchForensicsActivity(true);
    }

    const select = document.getElementById('diag-forensics-poll-freq');
    if (select) {
      select.onchange = (e) => {
        const newFreq = e.target.value;
        setFrequency(newFreq);
        if (newFreq !== 'manual' && newFreq !== 'start') {
          fetchForensicsActivity();
        }
        if (window.showToast) {
          const label = select.options[select.selectedIndex]?.text || newFreq;
          window.showToast(`Частота опроса форензики: ${label}`, 'info');
        }
      };
    }

    // Слушатель переключения суб-вкладок для сохранения состояния
    const subtabsNav = document.getElementById('forensics-subtabs-nav');
    if (subtabsNav) {
      subtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach(btn => {
        btn.addEventListener('shown.bs.tab', (e) => {
          const pId = e.target.getAttribute('data-panel-id') || normalizeSubTabId(e.target.getAttribute('data-bs-target'));
          updateUrlWithPanel(pId);
          try {
            localStorage.setItem(SUBTAB_STORAGE_KEY, pId);
          } catch (_) {}
        });
        btn.addEventListener('click', () => {
          const pId = btn.getAttribute('data-panel-id') || normalizeSubTabId(btn.getAttribute('data-bs-target'));
          updateUrlWithPanel(pId);
        });
      });

      window.addEventListener('hashchange', () => {
        if (!isForensicsTabActive()) return;
        const target = getPanelFromHash();
        if (target) {
          switchForensicsSubTab(target, false);
        }
      });

      document.addEventListener('tab:activated', (e) => {
        const tid = e.detail?.tabId;
        if (tid === TAB_ID || tid === 'forensics') {
          const target = getPanelFromHash();
          if (target) {
            switchForensicsSubTab(target, false);
          } else {
            updateUrlWithPanel('timeline');
          }
        }
      });
    }
  }

  async function initForensicsTab() {
    bindEvents();
    const currentFreq = getFrequency();
    const select = document.getElementById('diag-forensics-poll-freq');
    if (select) select.value = currentFreq;

    // Восстановление активной суб-вкладки из URL hash или хранилища
    const panelFromHash = getPanelFromHash();
    if (panelFromHash) {
      switchForensicsSubTab(panelFromHash, false);
    } else {
      try {
        const savedSubtab = localStorage.getItem(SUBTAB_STORAGE_KEY);
        if (savedSubtab) {
          switchForensicsSubTab(savedSubtab, false);
        } else {
          updateUrlWithPanel('timeline');
        }
      } catch (_) {}
    }

    applyPoller(currentFreq, true);
  }

  window.initForensicsTab = initForensicsTab;
  window.switchForensicsSubTab = switchForensicsSubTab;
  window.getForensicsPanelFromHash = getPanelFromHash;
  window.updateForensicsUrlWithPanel = updateUrlWithPanel;
  window.normalizeForensicsSubTabId = normalizeSubTabId;
  window.activateForensicsTab = () => {
    applyPoller(getFrequency(), true);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (window.isTabActive ? window.isTabActive('tab-forensics') : false) {
        initForensicsTab();
      } else {
        bindEvents();
      }
    });
  } else {
    if (window.isTabActive ? window.isTabActive('tab-forensics') : false) {
      initForensicsTab();
    } else {
      bindEvents();
    }
  }
})();
