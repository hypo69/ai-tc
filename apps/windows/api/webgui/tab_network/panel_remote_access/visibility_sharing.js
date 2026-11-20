/**
 * =============================================================================
 * Process Name: Windows Network Terminal - LAN Visibility & SMB Sharing Panel
 * =============================================================================
 * Description:
 *   Клиентский модуль 4-уровневой диагностики видимости ПК в локальной сети
 *   (L1 Профиль, L2 Службы, L3 Брандмауэр, L4 SMB 1.0/2/3), инвентаризации
 *   общих папок (Get-SmbShare), активных SMB-сессий и отката конфигурации
 *   из снимков (Rollback).
 *
 * File: visibility_sharing.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_network/panel_remote_access
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 22:02:00
 * =============================================================================
 */

let isVisBusy = false;
let isVisBound = false;
let latestSnapshotId = null;

/**
 * Экранирует HTML-символы.
 * @param {string} value
 * @returns {string}
 */
function esc(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Возвращает HTML-бейдж по статусу уровня (ok / warning / error / info).
 * @param {string} severity
 * @param {string} text
 * @returns {string}
 */
function severityBadge(severity, text) {
  const s = (severity || '').toLowerCase();
  if (s === 'ok') return `<span class="badge status-badge-up">${esc(text)}</span>`;
  if (s === 'error') return `<span class="badge status-badge-down">${esc(text)}</span>`;
  if (s === 'warning') return `<span class="badge bg-warning-subtle text-warning-emphasis border border-warning">${esc(text)}</span>`;
  return `<span class="badge status-badge-listen">${esc(text)}</span>`;
}

/**
 * Блокирует кнопки панели на время сетевой операции.
 * @param {boolean} busy
 */
function setVisBusy(busy) {
  isVisBusy = busy;
  const root = document.getElementById('vis-sharing-section');
  if (!root) return;
  root.querySelectorAll('button').forEach((btn) => {
    if (btn.id === 'btn-vis-rollback') {
      btn.disabled = busy || !latestSnapshotId;
    } else {
      btn.disabled = busy;
    }
  });
}

/**
 * Отрисовывает 4 уровня диагностики и список находок VIS001..VIS010.
 * @param {Object} report
 */
function renderVisibilityReport(report) {
  if (!report) return;

  const levelsEl = document.getElementById('vis-levels-grid');
  if (levelsEl) {
    const levels = Array.isArray(report.levels) ? report.levels : [];
    levelsEl.innerHTML = levels
      .map((lvl) => {
        const label = lvl.status === 'ok' ? 'OK' : (lvl.status === 'warning' ? 'Внимание' : 'Проблема');
        return `
          <div class="col-6 col-lg-3">
            <div class="net-card h-100">
              <div class="d-flex justify-content-between align-items-center gap-1">
                <span class="net-label">${esc(lvl.level)} · ${esc(lvl.name)}</span>
                ${severityBadge(lvl.status, label)}
              </div>
              <div class="small text-muted mt-1">${esc(lvl.summary)}</div>
            </div>
          </div>
        `;
      })
      .join('');
  }

  const findingsEl = document.getElementById('vis-findings-list');
  if (findingsEl) {
    const findings = Array.isArray(report.findings) ? report.findings : [];
    if (findings.length === 0) {
      findingsEl.innerHTML = `
        <div class="alert alert-success py-2 px-3 mb-0 small">
          <i class="bi bi-check-circle-fill me-1"></i>Все 4 уровня видимости в локальной сети работают штатно.
        </div>
      `;
    } else {
      findingsEl.innerHTML = findings
        .map(
          (f) => `
          <div class="d-flex align-items-start justify-content-between gap-2 py-1 border-bottom border-secondary border-opacity-25 small">
            <div>
              <span class="me-1">${severityBadge(f.severity, `${f.code} · ${f.level}`)}</span>
              <strong>${esc(f.title)}</strong>
              <div class="text-muted">${esc(f.detail)}</div>
              ${f.recommendation ? `<div class="text-info"><i class="bi bi-lightbulb me-1"></i>${esc(f.recommendation)}</div>` : ''}
            </div>
          </div>
        `
        )
        .join('');
    }
  }

  // Таблица 6 служб из уровня L2
  const svcTbody = document.getElementById('vis-services-tbody');
  if (svcTbody) {
    const l2 = (report.levels || []).find((l) => l.level === 'L2');
    const details = (l2 && l2.details) || {};
    const serviceOrder = [
      { key: 'FDResPub', role: 'Публикация ресурсов (Discovery)' },
      { key: 'fdPHost', role: 'Поставщик обнаружения (Discovery)' },
      { key: 'SSDPSRV', role: 'Обнаружение SSDP' },
      { key: 'upnphost', role: 'Узел UPnP-устройств' },
      { key: 'LanmanServer', role: 'SMB-сервер (общие папки)' },
      { key: 'LanmanWorkstation', role: 'SMB-клиент (подключение к шарам)' },
    ];
    svcTbody.innerHTML = serviceOrder
      .map(({ key, role }) => {
        const info = details[key] || {};
        const statusText = info.status || info.Status || 'Unknown';
        const startType = info.start_type || info.StartType || 'Unknown';
        const running = info.running === true || String(statusText).toLowerCase() === 'running';
        return `
          <tr>
            <td class="fw-semibold">${esc(key)}</td>
            <td class="text-muted">${esc(role)}</td>
            <td>${severityBadge(running ? 'ok' : 'warning', statusText)}</td>
            <td>${esc(startType)}</td>
          </tr>
        `;
      })
      .join('');
  }
}

/**
 * Отрисовывает сводку SMB1/2/3, правил @FirewallAPI.dll,-28502 и список общих папок.
 * @param {Object} status
 */
function renderSmbSharingStatus(status) {
  if (!status) return;

  const cfg = status.server_config || {};
  const smb1El = document.getElementById('vis-smb1-badge');
  if (smb1El) {
    if (!cfg.available) {
      smb1El.innerHTML = '<span class="badge bg-secondary">Недоступно</span>';
    } else if (cfg.smb1_enabled) {
      smb1El.innerHTML = severityBadge('warning', 'SMB 1.0: Включён (Риск)');
    } else {
      smb1El.innerHTML = severityBadge('ok', 'SMB 1.0: Отключён');
    }
  }

  const smb2El = document.getElementById('vis-smb2-badge');
  if (smb2El) {
    if (!cfg.available) {
      smb2El.innerHTML = '<span class="badge bg-secondary">Недоступно</span>';
    } else if (cfg.smb2_enabled) {
      smb2El.innerHTML = severityBadge('ok', 'SMB 2/3: Активен');
    } else {
      smb2El.innerHTML = severityBadge('error', 'SMB 2/3: Отключён');
    }
  }

  const fwEl = document.getElementById('vis-sharing-fw-badge');
  if (fwEl) {
    const fw = status.firewall || {};
    const text = fw.is_enabled
      ? `Firewall: ${fw.enabled_rules || 0}/${fw.total_rules || 0}`
      : 'Firewall: Отключён';
    fwEl.innerHTML = severityBadge(fw.is_enabled ? 'ok' : 'warning', text);
  }

  const sharesTbody = document.getElementById('vis-shares-tbody');
  if (sharesTbody) {
    const shares = Array.isArray(status.shares) ? status.shares : [];
    if (shares.length === 0) {
      sharesTbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-2">Общие папки не найдены</td></tr>';
    } else {
      sharesTbody.innerHTML = shares
        .map((sh) => {
          const typeBadge = sh.is_special
            ? '<span class="badge bg-secondary">Системная</span>'
            : '<span class="badge status-badge-up">Пользовательская</span>';
          const actionBtn = sh.is_special
            ? '<span class="text-muted small">Защищена</span>'
            : `<button class="btn btn-xs btn-outline-danger py-0 px-2" data-vis-remove-share="${esc(sh.name)}" type="button">Удалить</button>`;
          return `
            <tr>
              <td class="fw-semibold">${esc(sh.name)}</td>
              <td>${esc(sh.path || '—')}</td>
              <td>${typeBadge}</td>
              <td class="text-muted">${esc(sh.description || '—')}</td>
              <td class="text-end">${actionBtn}</td>
            </tr>
          `;
        })
        .join('');
    }
  }
}

/**
 * Отрисовывает активные входящие SMB-сессии.
 * @param {Array} sessions
 */
function renderSmbSessions(sessions) {
  const el = document.getElementById('vis-sessions-list');
  if (!el) return;
  if (!Array.isArray(sessions) || sessions.length === 0) {
    el.innerHTML = '<span class="text-muted small">Активных входящих SMB-сессий нет.</span>';
    return;
  }
  el.innerHTML = sessions
    .map(
      (s) =>
        `<span class="badge status-badge-listen me-1 mb-1">${esc(s.client_computer_name)} (${esc(s.client_user_name || 'guest')}, SMB ${esc(s.dialect || '?')}, файлов: ${esc(s.num_opens)})</span>`
    )
    .join('');
}

/**
 * Обновляет информацию о последнем снимке отката.
 * @param {Array} snapshots
 */
function renderSnapshotsInfo(snapshots) {
  const infoEl = document.getElementById('vis-snapshot-info');
  const rbBtn = document.getElementById('btn-vis-rollback');
  const list = Array.isArray(snapshots) ? snapshots : [];
  latestSnapshotId = list.length > 0 ? list[0].snapshot_id : null;

  if (rbBtn) rbBtn.disabled = isVisBusy || !latestSnapshotId;
  if (infoEl) {
    infoEl.textContent = latestSnapshotId
      ? `Последний снимок: ${latestSnapshotId} (всего: ${list.length})`
      : 'Снимков для отката пока нет';
  }
}

/**
 * Загружает полный набор данных диагностики L1–L4, SMB-статуса, сессий и снимков.
 */
export async function fetchVisibilityAndSharingData() {
  const hint = document.getElementById('vis-status-hint');
  if (hint) hint.textContent = 'Выполняется 4-уровневая диагностика...';

  try {
    const [diagRes, shareRes, sessRes, snapRes] = await Promise.all([
      fetch('/api/v1/network/visibility/diagnose'),
      fetch('/api/v1/network/sharing/status'),
      fetch('/api/v1/network/sharing/sessions'),
      fetch('/api/v1/network/visibility/snapshots?limit=10'),
    ]);

    if (diagRes.ok) renderVisibilityReport(await diagRes.json());
    if (shareRes.ok) renderSmbSharingStatus(await shareRes.json());
    if (sessRes.ok) {
      const sData = await sessRes.json();
      renderSmbSessions(sData.sessions || []);
    }
    if (snapRes.ok) {
      const snData = await snapRes.json();
      renderSnapshotsInfo(snData.snapshots || []);
    }
    if (hint) hint.textContent = `Обновлено: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.warn('[VisibilitySharing] Ошибка загрузки диагностики:', err);
    if (hint) hint.textContent = `Ошибка диагностики: ${err.message}`;
  }
}

/**
 * Переключает группу правил File & Printer Sharing (@FirewallAPI.dll,-28502).
 * @param {boolean} enable
 */
async function toggleFileSharing(enable) {
  if (isVisBusy) return;
  setVisBusy(true);
  try {
    const res = await fetch('/api/v1/network/sharing/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enable, profiles: ['Private', 'Domain'], start_server_service: enable }),
    });
    const data = await res.json();
    if (window.toast) {
      if (data.success) window.toast.success('File & Printer Sharing', data.message);
      else window.toast.warning('File & Printer Sharing', data.message);
    }
    await fetchVisibilityAndSharingData();
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка SMB', err.message);
  } finally {
    setVisBusy(false);
  }
}

/**
 * Выполняет откат конфигурации из последнего снимка.
 */
async function rollbackLatestSnapshot() {
  if (isVisBusy || !latestSnapshotId) return;
  if (!window.confirm(`Откатить сетевые настройки к снимку ${latestSnapshotId}?`)) return;
  setVisBusy(true);
  try {
    const res = await fetch(`/api/v1/network/visibility/rollback/${encodeURIComponent(latestSnapshotId)}`, {
      method: 'POST',
    });
    const data = await res.json();
    if (window.toast) {
      if (data.success) window.toast.success('Откат выполнен', data.message);
      else window.toast.warning('Откат', data.message || data.detail);
    }
    await fetchVisibilityAndSharingData();
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка отката', err.message);
  } finally {
    setVisBusy(false);
  }
}

/**
 * Удаляет пользовательскую общую папку.
 * @param {string} shareName
 */
async function removeUserShare(shareName) {
  if (isVisBusy || !shareName) return;
  if (!window.confirm(`Закрыть общий доступ к папке "${shareName}"? Локальные файлы на диске останутся нетронутыми.`)) return;
  setVisBusy(true);
  try {
    const res = await fetch(`/api/v1/network/sharing/shares/${encodeURIComponent(shareName)}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    if (window.toast) {
      if (data.success) window.toast.success('Общие папки', data.message);
      else window.toast.warning('Общие папки', data.message);
    }
    await fetchVisibilityAndSharingData();
  } catch (err) {
    if (window.toast) window.toast.error('Ошибка удаления шары', err.message);
  } finally {
    setVisBusy(false);
  }
}

/**
 * Инициализирует обработчики блока диагностики видимости и File & Printer Sharing.
 */
export function initVisibilityAndSharingSection() {
  if (isVisBound) return;
  const section = document.getElementById('vis-sharing-section');
  if (!section) return;
  isVisBound = true;

  document.getElementById('btn-vis-diagnose')?.addEventListener('click', () => fetchVisibilityAndSharingData());
  document.getElementById('btn-vis-sharing-on')?.addEventListener('click', () => toggleFileSharing(true));
  document.getElementById('btn-vis-sharing-off')?.addEventListener('click', () => toggleFileSharing(false));
  document.getElementById('btn-vis-rollback')?.addEventListener('click', () => rollbackLatestSnapshot());

  section.addEventListener('click', (e) => {
    const rmBtn = e.target.closest('[data-vis-remove-share]');
    if (rmBtn) {
      removeUserShare(rmBtn.getAttribute('data-vis-remove-share'));
    }
  });
}
