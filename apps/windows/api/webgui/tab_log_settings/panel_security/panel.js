/**
 * =============================================================================
 * Process Name: Windows Log Settings - Security Audit & Telemetry Panel
 * =============================================================================
 * Description:
 *   Модуль контроля политик аудита безопасности (CommandLine Event 4688),
 *   проверки SeSecurityPrivilege, управления закладками (Bookmark) и запуска
 *   инкрементального сбора событий в telemetry.db.
 *
 * File: panel_security/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_security
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { checkTabActive } from '../common/ui_utils.js';

/**
 * Загружает статус политик аудита и сборщика телеметрии.
 */
export async function fetchAuditStatus() {
  if (!checkTabActive('tab-log-settings')) return;

  try {
    const res = await fetch('/api/v1/log-settings/audit-status');
    if (!res.ok) return;
    const data = await res.json();

    const cmdStatusEl = document.getElementById('ls-cmdline-status');
    const cmdBadgeEl = document.getElementById('ls-audit-cmdline-badge');
    if (cmdStatusEl) {
      cmdStatusEl.textContent = data.cmdline_audit_enabled ? 'Включен ✅' : 'Отключен ⚠️';
      cmdStatusEl.className = `fs-4 fw-bold mt-1 ${data.cmdline_audit_enabled ? 'text-success' : 'text-warning'}`;
    }
    if (cmdBadgeEl) {
      cmdBadgeEl.textContent = data.cmdline_audit_enabled ? 'АКТИВЕН' : 'НЕ АКТИВЕН';
      cmdBadgeEl.className = `badge ${data.cmdline_audit_enabled ? 'bg-success' : 'bg-warning text-dark'}`;
    }

    const bmIdEl = document.getElementById('ls-bookmark-id');
    const bmTimeEl = document.getElementById('ls-bookmark-time');
    const dbEventsBadge = document.getElementById('ls-db-events-badge');
    const bmCurrIdEl = document.getElementById('ls-bm-curr-id');
    const bmDbCountEl = document.getElementById('ls-bm-db-count');

    if (bmIdEl) bmIdEl.textContent = data.last_bookmark_record_id ? `ID: ${data.last_bookmark_record_id.toLocaleString()}` : 'ID: Начало';
    if (bmTimeEl) bmTimeEl.textContent = `Закладка: ${data.last_bookmark_timestamp || 'Не задана'}`;
    if (dbEventsBadge) dbEventsBadge.textContent = `${data.db_security_events_count.toLocaleString()} в БД`;
    if (bmCurrIdEl) bmCurrIdEl.textContent = data.last_bookmark_record_id ? data.last_bookmark_record_id.toLocaleString() : 'Нет (tail)';
    if (bmDbCountEl) bmDbCountEl.textContent = data.db_security_events_count.toLocaleString();

    const privStatusEl = document.getElementById('ls-sec-priv-status');
    if (privStatusEl) {
      if (data.security_channel_accessible) {
        privStatusEl.className = 'alert alert-success border-success p-2 small mb-0 d-flex align-items-center gap-2';
        privStatusEl.innerHTML = '<i class="bi bi-shield-check fs-5"></i><span>Доступ к каналу Security разрешен. Привилегии SeSecurityPrivilege активны.</span>';
      } else {
        privStatusEl.className = 'alert alert-danger border-danger p-2 small mb-0 d-flex align-items-center gap-2';
        privStatusEl.innerHTML = '<i class="bi bi-shield-x fs-5"></i><span>Доступ к каналу Security ограничен. Требуется запуск с правами Администратора.</span>';
      }
    }
  } catch (err) {
    console.debug('[LogSettings] Ошибка проверки аудита:', err);
  }
}

/**
 * Переключает состояние политики аудита командной строки процессов в реестре.
 * @param {boolean} [enable=true] - Включить или отключить аудит.
 */
export async function toggleCmdlineAudit(enable = true) {
  try {
    const res = await fetch('/api/v1/log-settings/audit-status/cmdline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enable }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    if (window.toast) {
      window.toast.success('Политика обновлена', data.message);
    }
    await fetchAuditStatus();
  } catch (err) {
    if (window.toast) {
      window.toast.error('Ошибка изменения политики', err.message);
    }
  }
}

/**
 * Запускает сбор свежих событий безопасности в базу данных telemetry.db.
 * @param {Function} [onComplete=null] - Колбэк после завершения сбора.
 */
export async function runCollector(onComplete = null) {
  const batchSelect = document.getElementById('ls-collect-batch-size');
  const batchSize = batchSelect ? batchSelect.value : 500;
  const banner = document.getElementById('ls-collector-result-banner');

  const btn = document.getElementById('ls-run-collector-btn');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сбор...';

  try {
    const res = await fetch(`/api/v1/log-settings/collector/collect?limit=${batchSize}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    if (banner) {
      banner.className = 'small mt-2 text-success';
      banner.textContent = data.message || `Собрано ${data.total_events_ingested} событий.`;
      banner.classList.remove('d-none');
    }

    if (window.toast) {
      window.toast.success('Телеметрия обновлена', data.message);
    }

    await fetchAuditStatus();
    if (typeof onComplete === 'function') {
      await onComplete();
    }
  } catch (err) {
    if (banner) {
      banner.className = 'small mt-2 text-danger';
      banner.textContent = `Ошибка сбора: ${err.message}`;
      banner.classList.remove('d-none');
    }
    if (window.toast) {
      window.toast.error('Ошибка сбора', err.message);
    }
  } finally {
    if (btn) btn.innerHTML = origHtml;
  }
}

/**
 * Сбрасывает или устанавливает целевой Record ID для инкрементальной закладки.
 * @param {number|null} [customRecordId=null] - Задаваемый номер записи.
 */
export async function resetBookmark(customRecordId = null) {
  try {
    const res = await fetch('/api/v1/log-settings/collector/reset-bookmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: 'Security', record_id: customRecordId }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    if (window.toast) {
      window.toast.success('Закладка сброшена', data.message);
    }
    await fetchAuditStatus();
  } catch (err) {
    if (window.toast) {
      window.toast.error('Ошибка сброса закладки', err.message);
    }
  }
}
