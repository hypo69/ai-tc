/**
 * =============================================================================
 * Process Name: Windows Storage Wear Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_storage_wear/main.js?v=20261001_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_storage_wear
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

(function () {
  'use strict';

  let autoRefreshTimer = null;

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

  async function fetchStorageBatteryWear() {
    try {
      const data = await apiFetch('/api/v1/system/diagnostics/storage-battery');
      if (!data) return;

      // Disks
      const disksTbody = document.getElementById('diag-wear-disks-tbody');
      if (disksTbody && data.disks_wear) {
        setText('diag-wear-disks-count', `${data.disks_wear.length} дисков`);
        if (data.disks_wear.length === 0) {
          disksTbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">Физических накопителей не обнаружено</td></tr>';
        } else {
          const formatBytesLocal = (bytes) => {
            if (bytes == null || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
          };

          const formatPohLocal = (hours, formatted) => {
            if (formatted && formatted !== '—') return formatted;
            if (typeof hours === 'string' && hours.includes('ч')) return hours;
            if (hours == null || isNaN(hours) || Number(hours) <= 0) return null;
            const h = Number(hours);
            const days = Math.floor(h / 24);
            const years = (h / (24 * 365.25)).toFixed(1);
            if (days >= 365) return `${h.toLocaleString()} ч (≈ ${years} г)`;
            if (days >= 1) return `${h.toLocaleString()} ч (${days} д)`;
            return `${h.toLocaleString()} ч`;
          };

          disksTbody.innerHTML = data.disks_wear.map(d => {
            const diskName = d.name || d.model || d.device_id || 'Физический диск';
            const devId = d.device_id ? `<span class="badge bg-secondary-subtle text-light border border-secondary me-1.5">${escapeHtml(d.device_id)}</span>` : '';
            const isSsd = (d.media_type && d.media_type.toUpperCase().includes('SSD')) || (d.bus_type && d.bus_type.toUpperCase().includes('NVME'));
            const diskIcon = isSsd ? 'bi-device-ssd text-info' : 'bi-hdd text-primary';
            const typeBus = [d.media_type, d.bus_type].filter(Boolean).join(' / ') || 'Storage';
            const partsBadge = (d.partitions && d.partitions !== '—')
              ? `<span class="badge bg-primary-subtle text-info border border-info-subtle font-monospace">${escapeHtml(d.partitions)}</span>`
              : '';
            let freeVal = d.free_gb;
            if ((freeVal == null || isNaN(Number(freeVal))) && d.partitions && window.__aboutSystemBundle?.summary?.disks) {
              const matchedLetters = String(d.partitions).match(/[A-Za-z]:/g) || [];
              let sumFree = 0;
              let foundAny = false;
              const allDisks = window.__aboutSystemBundle.summary.disks;
              matchedLetters.forEach(letter => {
                const upperLet = letter.toUpperCase();
                const foundPart = allDisks.find(p => (p.device || p.mountpoint || '').toUpperCase().startsWith(upperLet));
                if (foundPart && foundPart.free_gb != null && !isNaN(Number(foundPart.free_gb))) {
                  sumFree += Number(foundPart.free_gb);
                  foundAny = true;
                }
              });
              if (foundAny) {
                freeVal = Math.round(sumFree * 10) / 10;
              }
            }
            const freeGbStr = (freeVal != null && !isNaN(Number(freeVal)))
              ? `${Number(freeVal).toFixed(1)} GB`
              : '<span class="text-muted">—</span>';
            const healthPct = d.health_pct != null ? d.health_pct : 100;
            const healthColor = healthPct >= 80 ? 'success' : (healthPct >= 50 ? 'warning' : 'danger');

            // Наработка и дата первого включения
            let pohFormatted = formatPohLocal(d.power_on_hours, d.power_on_hours_formatted);
            if (!pohFormatted && d.first_power_on) {
              try {
                const sDate = new Date(d.first_power_on);
                if (!isNaN(sDate.getTime())) {
                  const diffH = Math.max(1, Math.floor((Date.now() - sDate.getTime()) / (1000 * 3600)));
                  pohFormatted = formatPohLocal(diffH);
                }
              } catch (_) {}
            }
            const startStr = d.first_power_on ? `Старт: ${escapeHtml(d.first_power_on)}` : '';
            let pohHtml = '<span class="text-muted font-monospace small">—</span>';
            if (pohFormatted && startStr) {
              pohHtml = `<div class="font-monospace text-info">${pohFormatted}</div><div class="small text-muted font-monospace mt-0.5">${startStr}</div>`;
            } else if (pohFormatted) {
              pohHtml = `<div class="font-monospace text-info">${pohFormatted}</div>`;
            } else if (startStr) {
              pohHtml = `<div class="small text-muted font-monospace">${startStr}</div>`;
            }

            // Объемы ввода/вывода (запись и чтение)
            const ioHtml = `
              <div class="font-monospace text-light" style="white-space: nowrap;" title="Записано за сессию">
                <i class="bi bi-arrow-up-circle text-warning me-1"></i>Записано: ${formatBytesLocal(d.bytes_written)}
              </div>
              <div class="small font-monospace text-info mt-0.5" style="white-space: nowrap;" title="Прочитано за сессию">
                <i class="bi bi-arrow-down-circle text-info me-1"></i>Прочитано: ${formatBytesLocal(d.bytes_read)}
              </div>
            `;

            return `
            <tr>
              <td class="fw-bold text-white">
                <div class="d-flex align-items-center">
                  <i class="bi ${diskIcon} me-2 fs-6"></i>
                  <div>
                    <div class="text-truncate" style="max-width: 250px;" title="${escapeHtml(diskName)}">${escapeHtml(diskName)}</div>
                    <div class="small text-muted font-monospace mt-0.5">${devId}${d.serial_number && d.serial_number !== 'N/A' ? `<span class="text-secondary">S/N: ${escapeHtml(d.serial_number)}</span>` : ''}</div>
                  </div>
                </div>
              </td>
              <td class="text-muted font-monospace"><span class="badge bg-dark border border-secondary text-light">${escapeHtml(typeBus)}</span></td>
              <td>${partsBadge}</td>
              <td style="text-align: right;" class="text-light font-monospace">${d.total_gb} GB</td>
              <td style="text-align: right;" class="text-success font-monospace">${freeGbStr}</td>
              <td>${pohHtml}</td>
              <td style="text-align: right;">${ioHtml}</td>
              <td>
                <div class="d-flex align-items-center gap-1.5">
                  <div class="about-sys-progress-track flex-grow-1" style="height: 6px; min-width: 55px;">
                    <div class="about-sys-progress-bar bg-${healthColor}" style="width: ${healthPct}%;"></div>
                  </div>
                  <span class="small font-monospace text-${healthColor} ms-1">${healthPct}%</span>
                </div>
              </td>
              <td><span class="badge bg-${healthColor}-subtle text-${healthColor} border border-${healthColor}">${escapeHtml(d.status || 'OK')}</span></td>
            </tr>
          `;}).join('');
        }
      }

      // Battery
      const batContainer = document.getElementById('diag-battery-details-container');
      const batSourceBadge = document.getElementById('diag-battery-source-badge');
      if (batContainer && data.battery_wear) {
        const b = data.battery_wear;
        if (batSourceBadge) {
          batSourceBadge.textContent = b.power_source || 'AC Mains';
        }
        if (!b.has_battery) {
          batContainer.innerHTML = `
            <div class="text-center py-4 text-muted small">
              <i class="bi bi-plug-fill fs-4 text-info d-block mb-1"></i>
              Стационарный компьютер — питание напрямую от электросети
            </div>
          `;
        } else {
          batContainer.innerHTML = `
            <table class="about-sys-spec-table">
              <tbody>
                <tr>
                  <td class="about-sys-spec-key"><i class="bi bi-battery-charging me-1.5 text-warning"></i>Уровень заряда</td>
                  <td class="about-sys-spec-val fw-bold text-white">${b.percent}% (${b.is_charging ? 'Заряжается' : 'Разряд'})</td>
                </tr>
                <tr>
                  <td class="about-sys-spec-key"><i class="bi bi-shield-shaded me-1.5 text-info"></i>Заводская емкость</td>
                  <td class="about-sys-spec-val font-monospace">${b.design_capacity_mwh ? b.design_capacity_mwh + ' mWh' : '--'}</td>
                </tr>
                <tr>
                  <td class="about-sys-spec-key"><i class="bi bi-battery-full me-1.5 text-success"></i>Текущая емкость</td>
                  <td class="about-sys-spec-val font-monospace">${b.full_charge_capacity_mwh ? b.full_charge_capacity_mwh + ' mWh' : '--'}</td>
                </tr>
                <tr>
                  <td class="about-sys-spec-key"><i class="bi bi-heart-pulse me-1.5 text-danger"></i>Деградация (Износ)</td>
                  <td class="about-sys-spec-val ${b.wear_level_pct > 20 ? 'text-danger fw-bold' : 'text-success'}">
                    ${b.wear_level_pct}% износа
                  </td>
                </tr>
              </tbody>
            </table>
          `;
        }
      }
    } catch (err) {
      console.warn('[StorageWearTab] fetchStorageBatteryWear error:', err);
    }
  }

  const POLL_ID = 'storage_wear';

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
      window.unregisterTabPoller(`tab-storage-wear_${POLL_ID}`);
    }
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  function applyPoller(freq, runInitial = false) {
    stopPolling();
    if (freq === 'start' || freq === 'manual') {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-storage-wear') : true)) {
        fetchStorageBatteryWear();
      }
      return;
    }

    const intervalSec = parseInt(freq, 10);
    if (isNaN(intervalSec) || intervalSec <= 0) return;

    const intervalMs = intervalSec * 1000;
    const pollerId = `tab-storage-wear_${POLL_ID}`;

    if (window.registerTabPoller) {
      window.registerTabPoller('tab-storage-wear', fetchStorageBatteryWear, intervalMs, { pollerId, immediate: runInitial });
    } else {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-storage-wear') : true)) {
        fetchStorageBatteryWear();
      }
      autoRefreshTimer = setInterval(() => {
        if (window.isTabActive ? window.isTabActive('tab-storage-wear') : true) {
          fetchStorageBatteryWear();
        }
      }, intervalMs);
    }
  }

  function bindEvents() {
    const btnRefresh = document.getElementById('btn-diag-wear-refresh');
    if (btnRefresh) {
      btnRefresh.onclick = () => fetchStorageBatteryWear();
    }

    const select = document.getElementById('diag-wear-poll-freq');
    if (select) {
      select.onchange = (e) => {
        const newFreq = e.target.value;
        setFrequency(newFreq);
        if (newFreq !== 'manual' && newFreq !== 'start') {
          fetchStorageBatteryWear();
        }
        if (window.showToast) {
          const label = select.options[select.selectedIndex]?.text || newFreq;
          window.showToast(`Частота опроса износа: ${label}`, 'info');
        }
      };
    }
  }

  async function initStorageWearTab() {
    bindEvents();
    const currentFreq = getFrequency();
    const select = document.getElementById('diag-wear-poll-freq');
    if (select) select.value = currentFreq;
    applyPoller(currentFreq, true);
  }

  window.initStorageWearTab = initStorageWearTab;
  window.activateStorageWearTab = () => {
    applyPoller(getFrequency(), true);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (window.isTabActive ? window.isTabActive('tab-storage-wear') : false) {
        initStorageWearTab();
      } else {
        bindEvents();
      }
    });
  } else {
    if (window.isTabActive ? window.isTabActive('tab-storage-wear') : false) {
      initStorageWearTab();
    } else {
      bindEvents();
    }
  }
})();
