/**
 * =============================================================================
 * Process Name: Windows Forensics Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт цифровой криминалистики (Digital Forensics & Incident Response):
 *   - Интеллектуальное расследование инцидентов (AI Incident Reconstruction & Root Cause)
 *   - Единый супер-таймлайн артефактов (Super-Timeline)
 *   - Артефакты запусков программ (Prefetch & UserAssist)
 *   - Внешние накопители (USBSTOR Registry)
 *   - Хронология жизненного цикла ОС и сбоев (Reboots, Crashes, BSOD)
 *   - Оперативная телеметрия и звук в реальном времени (WASAPI Live Monitor)
 *   - Юридическая цепочка сохранности доказательств (Chain of Custody SHA-256)
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_forensics/main.js?v=20261112_v2" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_forensics
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 12:45:00
 * =============================================================================
 */

(function () {
  'use strict';

  let autoRefreshTimer = null;
  const TAB_ID = 'tab-forensics';
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

  async function apiFetch(url, options) {
    if (window.api && typeof window.api.fetch === 'function') {
      return await window.api.fetch(url, options);
    }
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }

  function normalizeSubTabId(targetId) {
    if (!targetId) return 'investigation';
    const clean = String(targetId).replace('#subpane-forensics-', '').replace('subpane-forensics-', '').replace('#', '').toLowerCase();
    const valid = ['investigation', 'supertimeline', 'execution', 'usb', 'reboots', 'live'];
    return valid.includes(clean) ? clean : 'investigation';
  }

  function getPanelFromHash() {
    try {
      const hash = window.location.hash || '';
      if (!hash.includes('forensics')) return null;
      const parts = hash.split('#');
      for (const p of parts) {
        if (!p) continue;
        const norm = normalizeSubTabId(p);
        if (norm && norm !== 'investigation') return norm;
      }
    } catch (_) {}
    return null;
  }

  function updateUrlWithPanel(panelId) {
    try {
      const norm = normalizeSubTabId(panelId);
      const curHash = window.location.hash || '';
      const baseTab = '#tab-forensics';
      const newHash = `${baseTab}#${norm}`;
      if (curHash !== newHash && window.history && window.history.replaceState) {
        window.history.replaceState(null, '', newHash);
      }
    } catch (_) {}
  }

  function isForensicsTabActive() {
    if (typeof window.isTabActive === 'function') {
      return window.isTabActive('tab-forensics') || window.isTabActive('forensics');
    }
    return true;
  }

  // 1. Загрузка живой телеметрии и звуковых сессий
  async function fetchLiveForensics(forceRefresh = false) {
    try {
      const url = forceRefresh ? '/api/v1/system/diagnostics/forensics?refresh=true' : '/api/v1/system/diagnostics/forensics';
      const data = await apiFetch(url);
      if (!data) return;

      if (data.foreground_window) {
        setText('diag-fg-title', data.foreground_window.title || 'Рабочий стол Windows');
        setText('diag-fg-proc', `Процесс: ${data.foreground_window.process_name || 'unknown'} (PID: ${data.foreground_window.pid || 0})`);
      }

      const idleSec = data.user_idle_seconds !== undefined ? Number(data.user_idle_seconds) : 0;
      setText('diag-user-idle-time', `${idleSec.toFixed(1)} с`);
      const statusBadge = document.getElementById('diag-user-status-badge');
      if (statusBadge) {
        statusBadge.textContent = idleSec > 300 ? 'Пользователь отошел (>5 мин)' : 'Пользователь активен';
        statusBadge.className = idleSec > 300 ? 'badge bg-warning-subtle text-warning border border-warning' : 'badge bg-success-subtle text-success border border-success';
      }

      const sessions = data.audio_sessions || [];
      const playbackSessions = sessions.filter(s => s.device_flow !== 'capture');
      const captureSessions = sessions.filter(s => s.device_flow === 'capture');
      const activePlayback = playbackSessions.filter(s => s.is_active_now);
      const activeCapture = captureSessions.filter(s => s.is_active_now);

      // Радар - Звук (Наушники / Колонки)
      const soundListEl = document.getElementById('diag-sound-access-list');
      if (soundListEl) {
        if (activePlayback.length > 0) {
          soundListEl.innerHTML = activePlayback.map(s => `
            <div class="d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle">
              <span class="text-truncate fw-semibold" style="max-width: 110px;" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
              <span class="badge bg-success" style="font-size: 0.65rem;">Звук Live</span>
            </div>
          `).join('');
        } else {
          soundListEl.innerHTML = '<span class="text-muted small">Нет активного звука</span>';
        }
      }

      // Радар - Микрофон
      const micListEl = document.getElementById('diag-mic-access-list');
      if (micListEl) {
        if (activeCapture.length > 0) {
          micListEl.innerHTML = activeCapture.map(s => `
            <div class="d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle">
              <span class="text-truncate fw-semibold" style="max-width: 110px;" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
              <span class="badge bg-danger" style="font-size: 0.65rem;">Запись звука</span>
            </div>
          `).join('');
        } else {
          micListEl.innerHTML = '<span class="text-muted small">Нет записи</span>';
        }
      }

      // Радар - Камера
      const camListEl = document.getElementById('diag-cam-access-list');
      if (camListEl) {
        const camApps = data.camera_active_apps || [];
        if (camApps.length > 0) {
          camListEl.innerHTML = camApps.map(a => `
            <div class="d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle">
              <span class="text-truncate" style="max-width: 110px;">${escapeHtml(a.app_name)}</span>
              <span class="badge ${a.is_active_now ? 'bg-danger' : 'bg-secondary'}" style="font-size: 0.65rem;">${a.is_active_now ? 'Камера' : 'В доступе'}</span>
            </div>
          `).join('');
        } else {
          camListEl.innerHTML = '<span class="text-muted small">Нет обращений</span>';
        }
      }

      // Таблица звуковых сессий WASAPI
      const soundTbody = document.getElementById('diag-sound-sessions-tbody');
      setText('diag-sound-streams-count', `${sessions.length} сессий`);
      if (soundTbody) {
        if (sessions.length === 0) {
          soundTbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Звуковые сессии не обнаружены</td></tr>';
        } else {
          soundTbody.innerHTML = sessions.map(s => {
            const isCap = s.device_flow === 'capture';
            const flowBadge = isCap
              ? '<span class="badge bg-warning-subtle text-warning border border-warning"><i class="bi bi-mic me-1"></i>Микрофон</span>'
              : '<span class="badge bg-success-subtle text-success border border-success"><i class="bi bi-headphones me-1"></i>Наушники/Звук</span>';
            const statusBadge = s.is_active_now
              ? `<span class="badge ${isCap ? 'bg-warning text-dark' : 'bg-success'}">Активен</span>`
              : '<span class="badge bg-body-secondary text-secondary">В покое</span>';
            const peakVal = Number(s.peak_level || 0);
            const meterPct = Math.min(100, Math.round(peakVal * 100));

            return `
              <tr>
                <td>${flowBadge}</td>
                <td class="fw-bold text-info"><i class="bi bi-window text-secondary me-1"></i>${escapeHtml(s.name)} <span class="text-muted small">(${s.pid || 0})</span></td>
                <td class="text-body text-truncate" style="max-width: 200px;">${escapeHtml(s.device_name || 'Аудиоустройство')}</td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: right;" class="font-monospace">${s.volume}%</td>
                <td style="text-align: center;">
                  <div class="d-inline-flex align-items-center gap-1">
                    <div class="live-meter-bar" style="width: 50px;"><div class="live-meter-fill" style="width: ${meterPct}%;"></div></div>
                    <span class="font-monospace small text-muted">${(peakVal*100).toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch (e) {
      console.warn('[Forensics] fetchLiveForensics error:', e);
    }
  }

  // 2. Супер-таймлайн цифровых доказательств
  async function fetchSuperTimeline() {
    try {
      const cat = document.getElementById('supertimeline-cat-filter')?.value || '';
      const q = document.getElementById('supertimeline-search')?.value || '';
      let url = '/api/v1/system/diagnostics/forensics/super-timeline?limit=100';
      if (cat) url += `&category=${encodeURIComponent(cat)}`;
      if (q) url += `&query=${encodeURIComponent(q)}`;

      const list = await apiFetch(url);
      const tbody = document.getElementById('supertimeline-tbody');
      setText('subtab-supertimeline-badge', String(list.length));

      if (tbody) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Артефактов по заданным критериям не найдено</td></tr>';
        } else {
          tbody.innerHTML = list.map(t => {
            let catBadge = '<span class="badge bg-secondary">Прочее</span>';
            if (t.category === 'execution') catBadge = '<span class="badge bg-primary-subtle text-primary border border-primary">Запуск</span>';
            else if (t.category === 'usb') catBadge = '<span class="badge bg-info-subtle text-info border border-info">USB</span>';
            else if (t.category === 'system_lifecycle') catBadge = '<span class="badge bg-danger-subtle text-danger border border-danger">Событие ОС</span>';
            else if (t.category === 'security') catBadge = '<span class="badge bg-warning-subtle text-warning border border-warning">Безопасность</span>';

            return `
              <tr>
                <td class="font-monospace text-muted small">${escapeHtml(formatTime(t.timestamp))}</td>
                <td>${catBadge}</td>
                <td class="small text-secondary">${escapeHtml(t.source)}</td>
                <td class="fw-semibold text-body">${escapeHtml(t.action)}</td>
                <td class="fw-bold text-info">${escapeHtml(t.entity)}</td>
                <td class="text-muted small text-truncate" style="max-width: 280px;" title="${escapeHtml(t.details)}">${escapeHtml(t.details)}</td>
                <td class="font-monospace small text-secondary" style="text-align: center;">${escapeHtml((t.sha256 || '').slice(0, 10))}</td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch (e) {
      console.warn('[Forensics] fetchSuperTimeline error:', e);
    }
  }

  // 3. Артефакты запусков (Prefetch & UserAssist)
  async function fetchExecutionArtifacts() {
    try {
      const list = await apiFetch('/api/v1/system/diagnostics/forensics/artifacts/prefetch?limit=100');
      const tbody = document.getElementById('exec-tbody');
      setText('exec-count-badge', `${list.length} артефактов`);
      setText('subtab-execution-badge', String(list.length));

      if (tbody) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Prefetch-артефактов не обнаружено</td></tr>';
        } else {
          tbody.innerHTML = list.map(a => `
            <tr>
              <td class="fw-bold text-info"><i class="bi bi-file-earmark-binary text-secondary me-1"></i>${escapeHtml(a.name)}</td>
              <td><span class="badge bg-body-secondary text-body border border-secondary-subtle">${escapeHtml(a.source)}</span></td>
              <td style="text-align: right;" class="font-monospace fw-bold text-warning">${a.run_count} раз</td>
              <td class="font-monospace small text-muted">${escapeHtml(formatTime(a.last_run_time))}</td>
              <td class="small text-muted font-monospace text-truncate" style="max-width: 320px;" title="${escapeHtml(a.path)}">${escapeHtml(a.path)}</td>
            </tr>
          `).join('');
        }
      }
    } catch (e) {
      console.warn('[Forensics] fetchExecutionArtifacts error:', e);
    }
  }

  // 4. Накопители (USBSTOR Registry)
  async function fetchUsbArtifacts() {
    try {
      const list = await apiFetch('/api/v1/system/diagnostics/forensics/artifacts/usb');
      const tbody = document.getElementById('usb-tbody');
      setText('usb-count-badge', `${list.length} устройств`);
      setText('subtab-usb-badge', String(list.length));

      if (tbody) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">В реестре USBSTOR записей не обнаружено</td></tr>';
        } else {
          tbody.innerHTML = list.map(u => `
            <tr>
              <td class="fw-bold text-body"><i class="bi bi-usb-symbol text-info me-1"></i>${escapeHtml(u.friendly_name || u.product)}</td>
              <td class="text-secondary">${escapeHtml(u.vendor)}</td>
              <td class="font-monospace text-info small fw-semibold">${escapeHtml(u.serial_number || 'Generic')}</td>
              <td class="font-monospace text-muted small">${escapeHtml(u.revision || '-')}</td>
              <td class="font-monospace text-muted small text-truncate" style="max-width: 280px;" title="${escapeHtml(u.device_id)}">${escapeHtml(u.device_id)}</td>
            </tr>
          `).join('');
        }
      }
    } catch (e) {
      console.warn('[Forensics] fetchUsbArtifacts error:', e);
    }
  }

  // 5. Жизненный цикл ОС, сбои и перезагрузки
  async function fetchRebootArtifacts() {
    try {
      const list = await apiFetch('/api/v1/system/diagnostics/forensics/artifacts/reboots?limit=50');
      const tbody = document.getElementById('reboots-tbody');
      setText('reboots-count-badge', `${list.length} событий`);
      setText('subtab-reboots-badge', String(list.length));

      if (tbody) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Событий перезагрузок в журнале не обнаружено</td></tr>';
        } else {
          tbody.innerHTML = list.map(r => {
            let typeBadge = '<span class="badge bg-secondary">Событие</span>';
            if (r.shutdown_type === 'crash_bsod') typeBadge = '<span class="badge bg-danger">BSOD Сбой</span>';
            else if (r.shutdown_type === 'dirty_shutdown') typeBadge = '<span class="badge bg-warning text-dark">Внезапное выключение</span>';
            else if (r.shutdown_type === 'graceful') typeBadge = '<span class="badge bg-success">Штатное выключение</span>';
            else if (r.shutdown_type === 'boot') typeBadge = '<span class="badge bg-info text-dark">Запуск ядра</span>';

            return `
              <tr>
                <td class="font-monospace text-muted small">${escapeHtml(formatTime(r.timestamp))}</td>
                <td style="text-align: center;"><span class="badge bg-body-secondary text-body font-monospace">${r.event_id}</span></td>
                <td>${typeBadge}</td>
                <td class="fw-semibold text-info small text-truncate" style="max-width: 180px;">${escapeHtml(r.initiator || r.source)}</td>
                <td class="small text-secondary text-truncate" style="max-width: 380px;" title="${escapeHtml(r.details || r.reason)}">${escapeHtml(r.details || r.reason)}</td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch (e) {
      console.warn('[Forensics] fetchRebootArtifacts error:', e);
    }
  }

  // 6. Интеллектуальное расследование инцидента (AI Incident Investigation)
  async function runInvestigation() {
    const btn = document.getElementById('btn-run-investigation');
    const badge = document.getElementById('investigation-status-badge');
    const scenario = document.getElementById('investigation-scenario-select')?.value || 'reboot_crash';
    const targetTime = document.getElementById('investigation-target-time')?.value || '';
    const winMin = parseInt(document.getElementById('investigation-window-minutes')?.value || '30', 10);

    if (btn) btn.disabled = true;
    if (badge) {
      badge.className = 'badge bg-warning text-dark';
      badge.textContent = 'Исследование цифровых доказательств...';
    }

    try {
      const rep = await apiFetch('/api/v1/system/diagnostics/forensics/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_type: scenario,
          timestamp_target: targetTime || null,
          window_minutes: winMin,
        }),
      });

      if (!rep) return;

      setText('rep-case-id', rep.investigation_id || 'CASE-001');
      setText('rep-confidence', `Достоверность: ${Math.round((rep.confidence_score || 0.9) * 100)}%`);
      setText('rep-target-time', `Ориентир: ${formatTime(rep.target_time)}`);
      setText('rep-root-cause-text', rep.root_cause_analysis || 'Анализ завершен.');

      const findingsList = document.getElementById('rep-findings-list');
      if (findingsList) {
        const items = rep.key_findings || [];
        if (items.length > 0) {
          findingsList.innerHTML = items.map(f => `<li class="mb-1">${escapeHtml(f)}</li>`).join('');
        } else {
          findingsList.innerHTML = '<li>Критических аномалий в исследованном окне не зафиксировано</li>';
        }
      }

      const cocList = document.getElementById('rep-coc-list');
      setText('rep-coc-count', `${(rep.chain_of_custody || []).length} доказательств`);
      if (cocList) {
        cocList.innerHTML = (rep.chain_of_custody || []).map(c => `
          <div class="d-flex align-items-center justify-content-between py-0.5 border-bottom border-secondary-subtle">
            <span class="text-truncate me-2">[${escapeHtml(c.artifact_type)}] ${escapeHtml(c.evidence_id)}</span>
            <span class="text-info">${escapeHtml(c.sha256_hash.slice(0, 16))}...</span>
          </div>
        `).join('');
      }

      if (badge) {
        badge.className = 'badge bg-success-subtle text-success border border-success';
        badge.textContent = 'Заключение сформировано';
      }
      if (window.showToast) window.showToast(`Расследование ${rep.investigation_id} завершено`, 'success');
    } catch (e) {
      console.warn('[Forensics] runInvestigation error:', e);
      if (badge) {
        badge.className = 'badge bg-danger-subtle text-danger border border-danger';
        badge.textContent = 'Ошибка расследования';
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // Переключение вкладок
  function switchForensicsSubTab(subtabId, updateUrl = true) {
    const cleanId = normalizeSubTabId(subtabId);
    const btnId = `subtab-forensics-${cleanId}-btn`;
    const btn = document.getElementById(btnId);
    if (btn) {
      if (window.bootstrap && typeof window.bootstrap.Tab === 'function') {
        window.bootstrap.Tab.getOrCreateInstance(btn).show();
      } else {
        btn.click();
      }
      try { localStorage.setItem(SUBTAB_STORAGE_KEY, cleanId); } catch (_) {}
      if (updateUrl) updateUrlWithPanel(cleanId);
    }
    loadCurrentSubTab(cleanId);
  }

  function loadCurrentSubTab(subtabId) {
    if (subtabId === 'supertimeline') fetchSuperTimeline();
    else if (subtabId === 'execution') fetchExecutionArtifacts();
    else if (subtabId === 'usb') fetchUsbArtifacts();
    else if (subtabId === 'reboots') fetchRebootArtifacts();
    else if (subtabId === 'live') fetchLiveForensics();
    else if (subtabId === 'investigation') {
      const caseIdEl = document.getElementById('rep-case-id');
      if (caseIdEl && caseIdEl.textContent.includes('--')) {
        runInvestigation();
      }
    }
  }

  function loadAllForensicData(force = false) {
    fetchLiveForensics(force);
    fetchSuperTimeline();
    fetchExecutionArtifacts();
    fetchUsbArtifacts();
    fetchRebootArtifacts();
  }

  function bindEvents() {
    const btnRefresh = document.getElementById('btn-diag-forensics-refresh');
    if (btnRefresh) btnRefresh.onclick = () => loadAllForensicData(true);

    const btnInvestigate = document.getElementById('btn-run-investigation');
    if (btnInvestigate) btnInvestigate.onclick = runInvestigation;

    const catFilter = document.getElementById('supertimeline-cat-filter');
    if (catFilter) catFilter.onchange = fetchSuperTimeline;

    const searchInput = document.getElementById('supertimeline-search');
    if (searchInput) {
      searchInput.oninput = () => {
        clearTimeout(searchInput._timer);
        searchInput._timer = setTimeout(fetchSuperTimeline, 300);
      };
    }

    const subtabsNav = document.getElementById('forensics-subtabs-nav');
    if (subtabsNav) {
      subtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach(btn => {
        btn.addEventListener('shown.bs.tab', (e) => {
          const pId = normalizeSubTabId(e.target.getAttribute('data-panel-id'));
          updateUrlWithPanel(pId);
          try { localStorage.setItem(SUBTAB_STORAGE_KEY, pId); } catch (_) {}
          loadCurrentSubTab(pId);
        });
      });
    }

    const pollSelect = document.getElementById('diag-forensics-poll-freq');
    if (pollSelect) {
      pollSelect.onchange = (e) => {
        applyPoller(e.target.value);
      };
    }
  }

  function applyPoller(freq) {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    const sec = parseInt(freq, 10);
    if (!isNaN(sec) && sec > 0) {
      autoRefreshTimer = setInterval(() => {
        if (isForensicsTabActive()) fetchLiveForensics();
      }, sec * 1000);
    }
  }

  async function initForensicsTab() {
    bindEvents();
    const saved = getPanelFromHash() || localStorage.getItem(SUBTAB_STORAGE_KEY) || 'investigation';
    switchForensicsSubTab(saved, false);
    loadAllForensicData(false);
  }

  window.initForensicsTab = initForensicsTab;
  window.switchForensicsSubTab = switchForensicsSubTab;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (isForensicsTabActive()) initForensicsTab();
    });
  } else {
    if (isForensicsTabActive()) initForensicsTab();
  }
})();
