/**
 * =============================================================================
 * Process Name: Windows Peripherals Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_peripherals/main.js?v=20261001_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_peripherals
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

  async function fetchPeripheralsNetwork() {
    try {
      const data = await apiFetch('/api/v1/system/diagnostics/peripherals');
      if (!data) return;

      // Wi-Fi
      if (data.wifi_telemetry) {
        const w = data.wifi_telemetry;
        setText('diag-wifi-ssid', w.ssid || 'Не подключено');
        setText('diag-wifi-bssid', w.bssid || '--');
        setText('diag-wifi-signal', `${w.signal_pct}% (${w.rssi_dbm} dBm)`);
        setText('diag-wifi-channel', w.channel || '--');
        setText('diag-wifi-radio', w.radio_type || '--');
        setText('diag-wifi-auth', w.auth_cipher || '--');

        const wifiBadge = document.getElementById('diag-wifi-status-badge');
        if (wifiBadge) {
          if (w.is_connected) {
            wifiBadge.className = 'badge bg-success-subtle text-success border border-success';
            wifiBadge.textContent = 'Wi-Fi Подключено';
          } else {
            wifiBadge.className = 'badge bg-secondary';
            wifiBadge.textContent = 'Wi-Fi Отключено';
          }
        }
      }

      // Audio Endpoints
      const audioContainer = document.getElementById('diag-audio-container');
      if (audioContainer && data.audio_endpoints) {
        setText('diag-audio-count', `${data.audio_endpoints.length} устр.`);
        if (data.audio_endpoints.length === 0) {
          audioContainer.innerHTML = '<div class="text-center py-4 text-muted small">Аудиоустройств не обнаружено</div>';
        } else {
          audioContainer.innerHTML = data.audio_endpoints.map(a => `
            <div class="p-2 mb-1 rounded bg-black bg-opacity-30 border border-secondary-subtle d-flex align-items-center justify-content-between">
              <div>
                <strong class="text-white"><i class="bi bi-speaker me-1.5 text-warning"></i>${escapeHtml(a.name)}</strong>
                <div class="small text-muted">${escapeHtml(a.type)}</div>
              </div>
              <span class="badge ${a.is_default ? 'bg-info text-dark fw-bold' : 'bg-secondary'}">${a.is_default ? 'По умолчанию' : 'Доступно'}</span>
            </div>
          `).join('');
        }
      }

      // Bluetooth Devices Table
      const btTbody = document.getElementById('diag-bt-tbody');
      if (btTbody && data.bluetooth_devices) {
        setText('diag-bt-count', `${data.bluetooth_devices.length} устройств`);
        if (data.bluetooth_devices.length === 0) {
          btTbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Bluetooth устройств не обнаружено</td></tr>';
        } else {
          btTbody.innerHTML = data.bluetooth_devices.map(b => {
            let icon = 'bi-bluetooth text-primary';
            const t = (b.type || '').toLowerCase();
            if (t.includes('аудио') || t.includes('гарнитур') || t.includes('наушник')) icon = 'bi-headphones text-warning';
            else if (t.includes('смартфон') || t.includes('мобильн') || t.includes('телефон')) icon = 'bi-phone text-info';
            else if (t.includes('ввод') || t.includes('мышь') || t.includes('клавиатур')) icon = 'bi-mouse text-success';
            else if (t.includes('контроллер') || t.includes('адаптер')) icon = 'bi-cpu text-primary';

            const statusBadge = b.has_problem
              ? '<span class="badge bg-danger">Ошибка</span>'
              : '<span class="badge bg-success-subtle text-success border border-success">Подключено</span>';

            return `
              <tr>
                <td class="fw-bold"><i class="bi ${icon} me-1.5"></i>${escapeHtml(b.name)}</td>
                <td><span class="badge bg-secondary-subtle text-body border border-secondary-subtle">${escapeHtml(b.type)}</span></td>
                <td class="font-monospace text-info">${escapeHtml(b.mac_address || '--')}</td>
                <td class="text-muted small">${escapeHtml(b.manufacturer || '--')}</td>
                <td>${statusBadge}</td>
                <td class="small text-muted font-monospace text-truncate" style="max-width: 220px;" title="${escapeHtml(b.device_id || '')}">${escapeHtml(b.device_id || '--')}</td>
              </tr>
            `;
          }).join('');
        }
      }

      // Printers Table
      const prnTbody = document.getElementById('diag-printers-tbody');
      if (prnTbody && data.printers) {
        setText('diag-printers-count', `${data.printers.length} принтеров`);
        if (data.printers.length === 0) {
          prnTbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Принтеры не обнаружены</td></tr>';
        } else {
          prnTbody.innerHTML = data.printers.map(p => {
            let connBadgeClass = 'bg-secondary';
            const cType = (p.connection_type || '').toLowerCase();
            if (cType.includes('wsd') || cType.includes('сеть')) connBadgeClass = 'bg-primary-subtle text-primary border border-primary';
            else if (cType.includes('usb')) connBadgeClass = 'bg-info-subtle text-info border border-info';
            else if (cType.includes('виртуал')) connBadgeClass = 'bg-secondary-subtle text-body border border-secondary-subtle';

            const defBadge = p.is_default
              ? '<span class="badge bg-warning text-dark fw-bold"><i class="bi bi-star-fill me-1"></i>Основной</span>'
              : '<span class="text-muted small">—</span>';

            const statusBadge = (p.status || 'OK').toUpperCase() === 'OK'
              ? '<span class="badge bg-success-subtle text-success border border-success">Готов к печати</span>'
              : `<span class="badge bg-warning-subtle text-warning border border-warning">${escapeHtml(p.status)}</span>`;

            return `
              <tr>
                <td class="fw-bold">
                  <i class="bi bi-printer text-success me-1.5"></i>${escapeHtml(p.name)}
                  ${p.is_default ? ' <span class="badge bg-warning-subtle text-warning border border-warning ms-1">По умолчанию</span>' : ''}
                </td>
                <td><span class="badge ${connBadgeClass}">${escapeHtml(p.connection_type || 'Локальный')}</span></td>
                <td class="font-monospace text-truncate" style="max-width: 220px;" title="${escapeHtml(p.port || '')}">${escapeHtml(p.port || '--')}</td>
                <td class="text-muted small text-truncate" style="max-width: 200px;" title="${escapeHtml(p.driver || '')}">${escapeHtml(p.driver || '--')}</td>
                <td>${statusBadge}</td>
                <td class="text-center">${defBadge}</td>
              </tr>
            `;
          }).join('');
        }
      }

      // USB PnP Table
      const usbTbody = document.getElementById('diag-usb-tbody');
      if (usbTbody && data.usb_devices) {
        setText('diag-usb-count', `${data.usb_devices.length} устройств`);
        if (data.usb_devices.length === 0) {
          usbTbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">USB устройств не обнаружено</td></tr>';
        } else {
          usbTbody.innerHTML = data.usb_devices.map(u => `
            <tr>
              <td class="fw-bold"><i class="bi bi-usb-symbol text-info me-1.5"></i>${escapeHtml(u.name)}</td>
              <td class="font-monospace text-warning">${escapeHtml(u.vendor_id)}</td>
              <td class="font-monospace text-info">${escapeHtml(u.product_id)}</td>
              <td class="text-muted small">${escapeHtml(u.device_class || 'USB Device')}</td>
              <td><span class="badge ${u.has_problem ? 'bg-danger' : 'bg-success-subtle text-success border border-success'}">${escapeHtml(u.status)}</span></td>
              <td class="small text-muted font-monospace text-truncate" style="max-width: 220px;" title="${escapeHtml(u.device_id)}">${escapeHtml(u.device_id)}</td>
            </tr>
          `).join('');
        }
      }
    } catch (err) {
      console.warn('[PeripheralsTab] fetchPeripheralsNetwork error:', err);
    }
  }

  const POLL_ID = 'peripherals';

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
      window.unregisterTabPoller(`tab-peripherals_${POLL_ID}`);
    }
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  function applyPoller(freq, runInitial = false) {
    stopPolling();
    if (freq === 'start' || freq === 'manual') {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-peripherals') : true)) {
        fetchPeripheralsNetwork();
      }
      return;
    }

    const intervalSec = parseInt(freq, 10);
    if (isNaN(intervalSec) || intervalSec <= 0) return;

    const intervalMs = intervalSec * 1000;
    const pollerId = `tab-peripherals_${POLL_ID}`;

    if (window.registerTabPoller) {
      window.registerTabPoller('tab-peripherals', fetchPeripheralsNetwork, intervalMs, { pollerId, immediate: runInitial });
    } else {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-peripherals') : true)) {
        fetchPeripheralsNetwork();
      }
      autoRefreshTimer = setInterval(() => {
        if (window.isTabActive ? window.isTabActive('tab-peripherals') : true) {
          fetchPeripheralsNetwork();
        }
      }, intervalMs);
    }
  }

  function bindEvents() {
    const btnRefresh = document.getElementById('btn-diag-peripherals-refresh');
    if (btnRefresh) {
      btnRefresh.onclick = () => fetchPeripheralsNetwork();
    }

    const select = document.getElementById('diag-peripherals-poll-freq');
    if (select) {
      select.onchange = (e) => {
        const newFreq = e.target.value;
        setFrequency(newFreq);
        if (newFreq !== 'manual' && newFreq !== 'start') {
          fetchPeripheralsNetwork();
        }
        if (window.showToast) {
          const label = select.options[select.selectedIndex]?.text || newFreq;
          window.showToast(`Частота опроса периферии: ${label}`, 'info');
        }
      };
    }
  }

  async function initPeripheralsTab() {
    bindEvents();
    const currentFreq = getFrequency();
    const select = document.getElementById('diag-peripherals-poll-freq');
    if (select) select.value = currentFreq;
    applyPoller(currentFreq, true);
  }

  window.initPeripheralsTab = initPeripheralsTab;
  window.activatePeripheralsTab = () => {
    applyPoller(getFrequency(), true);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (window.isTabActive ? window.isTabActive('tab-peripherals') : false) {
        initPeripheralsTab();
      } else {
        bindEvents();
      }
    });
  } else {
    if (window.isTabActive ? window.isTabActive('tab-peripherals') : false) {
      initPeripheralsTab();
    } else {
      bindEvents();
    }
  }
})();

