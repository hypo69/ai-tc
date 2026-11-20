/**
 * =============================================================================
 * Process Name: Windows Log Settings - Channels Panel
 * =============================================================================
 * Description:
 *   Модуль мониторинга и настройки каналов Windows Event Log: размеры, лимиты,
 *   политики ротации, очистка с бэкапом и верхние карточки Security-журнала.
 *
 * File: panel_channels/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_log_settings/panel_channels
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml, checkTabActive } from '../common/ui_utils.js';

let channelsData = [];

/**
 * Загружает сводку и список параметров всех каналов.
 */
export async function fetchChannelsList() {
  if (!checkTabActive('tab-log-settings')) return;

  try {
    const res = await fetch('/api/v1/log-settings/channels');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    channelsData = data.channels || [];
    renderChannelsCards(channelsData);
    renderChannelsTable(channelsData);
  } catch (err) {
    console.warn('[LogSettings] Ошибка загрузки каналов:', err);
  }
}

/**
 * Отрисовывает верхнюю карточку Security-канала.
 * @param {Array} channels - Список каналов.
 */
export function renderChannelsCards(channels) {
  const sec = channels.find((c) => c.channel_name === 'Security') || {};

  const secSizeEl = document.getElementById('ls-sec-size');
  const secProgEl = document.getElementById('ls-sec-progress');
  const secRecordsEl = document.getElementById('ls-sec-records');
  const secStatusEl = document.getElementById('ls-sec-status');

  if (secSizeEl) secSizeEl.textContent = `${sec.file_size_mb || 0} / ${sec.max_size_mb || 20} MB`;
  if (secProgEl) {
    const pct = sec.usage_pct || 0;
    secProgEl.style.width = `${Math.min(100, pct)}%`;
    secProgEl.className = `progress-bar ${pct > 90 ? 'bg-danger' : pct > 75 ? 'bg-warning' : 'bg-info'}`;
  }
  if (secRecordsEl) secRecordsEl.textContent = `Записей: ${(sec.record_count || 0).toLocaleString()}`;
  if (secStatusEl) secStatusEl.textContent = sec.is_enabled ? 'Активен' : 'Отключен';
}

/**
 * Отрисовывает таблицу каналов Event Log.
 * @param {Array} channels - Список каналов.
 */
export function renderChannelsTable(channels) {
  const tbody = document.getElementById('ls-channels-tbody');
  const countLabel = document.getElementById('ls-table-count');
  if (!tbody) return;

  const filterInput = document.getElementById('ls-channel-filter-input');
  const filterQuery = (filterInput ? filterInput.value : '').toLowerCase().trim();

  const filtered = channels.filter((c) => {
    if (!filterQuery) return true;
    return c.channel_name.toLowerCase().includes(filterQuery) ||
           (c.description || '').toLowerCase().includes(filterQuery);
  });

  if (countLabel) countLabel.textContent = `${filtered.length} из ${channels.length}`;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Каналы не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map((c) => {
    const pct = c.usage_pct || 0;
    const isFull = pct >= 95.0;
    const badgeColor = isFull ? 'bg-danger' : (pct > 75 ? 'bg-warning text-dark' : 'bg-success');
    const rotPolicy = c.auto_backup ? 'Auto-Backup (Архивация)' : (c.retention ? 'Retention (Удержание)' : 'FIFO (Перезапись)');

    return `
      <tr>
        <td>
          <div class="fw-bold text-light font-monospace">${escapeHtml(c.channel_name)}</div>
          <div class="small text-muted text-truncate" style="max-width: 280px; font-size: 0.72rem;" title="${escapeHtml(c.description)}">
            ${escapeHtml(c.description || c.log_file_path)}
          </div>
        </td>
        <td>
          <span class="font-monospace text-light">${c.file_size_mb} MB</span>
          <span class="text-muted small">/ ${c.max_size_mb} MB</span>
        </td>
        <td>
          <div class="d-flex align-items-center gap-2">
            <div class="progress flex-grow-1 bg-secondary" style="height: 6px;">
              <div class="progress-bar ${pct > 90 ? 'bg-danger' : (pct > 70 ? 'bg-warning' : 'bg-info')}" style="width: ${Math.min(100, pct)}%;"></div>
            </div>
            <span class="badge ${badgeColor} font-monospace" style="font-size: 0.7rem;">${pct}%</span>
          </div>
        </td>
        <td class="font-monospace text-info">${(c.record_count || 0).toLocaleString()}</td>
        <td class="font-monospace text-secondary small" style="font-size: 0.72rem;">
          ${c.oldest_record_id ? `${c.oldest_record_id.toLocaleString()}..${c.newest_record_id.toLocaleString()}` : '--'}
        </td>
        <td>
          <span class="badge bg-secondary-subtle text-light border border-secondary small" style="font-size: 0.72rem;">${rotPolicy}</span>
        </td>
        <td>
          ${c.is_enabled ? '<span class="badge bg-success">Вкл</span>' : '<span class="badge bg-secondary">Выкл</span>'}
        </td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-info py-0 px-2 ls-btn-config" data-channel="${escapeHtml(c.channel_name)}" title="Настроить параметры">
              <i class="bi bi-gear"></i>
            </button>
            <button class="btn btn-outline-danger py-0 px-2 ls-btn-clear" data-channel="${escapeHtml(c.channel_name)}" title="Очистить журнал">
              <i class="bi bi-trash3"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.ls-btn-config').forEach((btn) => {
    btn.addEventListener('click', () => openConfigModal(btn.dataset.channel));
  });

  tbody.querySelectorAll('.ls-btn-clear').forEach((btn) => {
    btn.addEventListener('click', () => openClearModal(btn.dataset.channel));
  });
}

/**
 * Открывает модальное окно настройки параметров канала.
 * @param {string} channelName - Имя канала.
 */
export function openConfigModal(channelName) {
  const channel = channelsData.find((c) => c.channel_name === channelName);
  if (!channel) return;

  document.getElementById('ls-modal-channel-name').value = channel.channel_name;
  document.getElementById('ls-modal-channel-title').textContent = channel.channel_name;
  document.getElementById('ls-modal-channel-path').textContent = channel.log_file_path || 'Стандартный путь Winevt\\Logs';
  document.getElementById('ls-modal-maxsize-input').value = channel.max_size_mb || 20;
  document.getElementById('ls-modal-enabled-switch').checked = channel.is_enabled !== false;
  document.getElementById('ls-modal-autobackup-switch').checked = !!channel.auto_backup;
  document.getElementById('ls-modal-retention-switch').checked = !!channel.retention;

  const modalEl = document.getElementById('ls-config-modal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

/**
 * Сохраняет параметры конфигурации канала на сервере.
 */
export async function saveChannelConfig() {
  const channelName = document.getElementById('ls-modal-channel-name').value;
  const maxSizeMb = parseInt(document.getElementById('ls-modal-maxsize-input').value, 10);
  const isEnabled = document.getElementById('ls-modal-enabled-switch').checked;
  const autoBackup = document.getElementById('ls-modal-autobackup-switch').checked;
  const retention = document.getElementById('ls-modal-retention-switch').checked;

  const saveBtn = document.getElementById('ls-modal-save-btn');
  const origHtml = saveBtn ? saveBtn.innerHTML : '';
  if (saveBtn) saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сохранение...';

  try {
    const res = await fetch('/api/v1/log-settings/channel/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_name: channelName,
        max_size_mb: maxSizeMb || null,
        is_enabled: isEnabled,
        auto_backup: autoBackup,
        retention: retention,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    if (window.toast) {
      window.toast.success('Параметры обновлены', data.message || `Настройки журнала ${channelName} сохранены.`);
    }

    const modalEl = document.getElementById('ls-config-modal');
    if (modalEl && window.bootstrap) {
      window.bootstrap.Modal.getInstance(modalEl)?.hide();
    }

    await fetchChannelsList();
  } catch (err) {
    if (window.toast) {
      window.toast.error('Ошибка сохранения', err.message);
    }
  } finally {
    if (saveBtn) saveBtn.innerHTML = origHtml;
  }
}

/**
 * Открывает модальное окно очистки журнала.
 * @param {string} channelName - Имя канала.
 */
export function openClearModal(channelName) {
  document.getElementById('ls-clear-modal-channel-name').value = channelName;
  document.getElementById('ls-clear-modal-title').textContent = channelName;

  const nowStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const cleanName = channelName.replace(/[^a-zA-Z0-9]/g, '_');
  document.getElementById('ls-clear-backup-path-input').value = `C:\\Windows\\Temp\\evtx_backup_${cleanName}_${nowStr}.evtx`;

  const modalEl = document.getElementById('ls-clear-modal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

/**
 * Выполняет подтвержденную очистку журнала.
 */
export async function confirmClearChannel() {
  const channelName = document.getElementById('ls-clear-modal-channel-name').value;
  const withBackup = document.getElementById('ls-clear-backup-checkbox').checked;
  const backupPath = withBackup ? document.getElementById('ls-clear-backup-path-input').value : null;

  const clearBtn = document.getElementById('ls-confirm-clear-btn');
  const origHtml = clearBtn ? clearBtn.innerHTML : '';
  if (clearBtn) clearBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Очистка...';

  try {
    const res = await fetch('/api/v1/log-settings/channel/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_name: channelName,
        backup_path: backupPath,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    if (window.toast) {
      window.toast.success('Журнал очищен', data.message || `Журнал ${channelName} очищен.`);
    }

    const modalEl = document.getElementById('ls-clear-modal');
    if (modalEl && window.bootstrap) {
      window.bootstrap.Modal.getInstance(modalEl)?.hide();
    }

    await fetchChannelsList();
  } catch (err) {
    if (window.toast) {
      window.toast.error('Ошибка очистки', err.message);
    }
  } finally {
    if (clearBtn) clearBtn.innerHTML = origHtml;
  }
}
