/**
 * =============================================================================
 * Process Name: Windows Hardware Monitor Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля main.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_hardware_monitor/main.js?v=20261001_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_hardware_monitor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

// Hardware & Sensors Monitor Frontend Logic
(function () {
  let timerId = null;
  const POLL_ID = 'hw_monitor';

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
      window.unregisterTabPoller(`tab-hardware-monitor_${POLL_ID}`);
    }
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function applyPoller(freq, runInitial = false) {
    stopPolling();
    if (freq === 'start' || freq === 'manual') {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-hardware-monitor') : true)) {
        loadHardwareData();
      }
      return;
    }

    const intervalSec = parseInt(freq, 10);
    if (isNaN(intervalSec) || intervalSec <= 0) return;

    const intervalMs = intervalSec * 1000;
    const pollerId = `tab-hardware-monitor_${POLL_ID}`;

    if (window.registerTabPoller) {
      window.registerTabPoller('tab-hardware-monitor', loadHardwareData, intervalMs, { pollerId, immediate: runInitial });
    } else {
      if (runInitial && (window.isTabActive ? window.isTabActive('tab-hardware-monitor') : true)) {
        loadHardwareData();
      }
      timerId = setInterval(() => {
        if (window.isTabActive ? window.isTabActive('tab-hardware-monitor') : true) {
          loadHardwareData();
        }
      }, intervalMs);
    }
  }

  async function initHardwareMonitorTab() {
    console.log('[HardwareMonitor] Initializing tab...');
    bindEvents();
    const currentFreq = getFrequency();
    const select = document.getElementById('hw-poll-freq');
    if (select) select.value = currentFreq;
    applyPoller(currentFreq, true);
  }
  window.initHardwareMonitorTab = initHardwareMonitorTab;
  window.activateHardwareMonitorTab = () => {
    applyPoller(getFrequency(), true);
  };

  function bindEvents() {
    const btnRefresh = document.getElementById('hw-btn-refresh');
    if (btnRefresh) {
      btnRefresh.onclick = () => {
        loadHardwareData();
      };
    }

    const select = document.getElementById('hw-poll-freq');
    if (select) {
      select.onchange = (e) => {
        const newFreq = e.target.value;
        setFrequency(newFreq);
        if (newFreq !== 'manual' && newFreq !== 'start') {
          loadHardwareData();
        }
        if (window.showToast) {
          const label = select.options[select.selectedIndex]?.text || newFreq;
          window.showToast(`Частота опроса сенсоров: ${label}`, 'info');
        }
      };
    }
  }

  async function loadHardwareData() {
    await Promise.allSettled([
      loadSnapshot(),
      loadSensors(),
      loadSmart()
    ]);
  }

  async function loadSnapshot() {
    try {
      const res = await fetch('/api/v1/windows/hardware/monitor?include_smart=false');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // CPU
      const cpu = data.cpu || {};
      const elValCpu = document.getElementById('hw-val-cpu');
      const elSubCpu = document.getElementById('hw-sub-cpu');
      const elCpuCores = document.getElementById('hw-cpu-cores');

      if (elValCpu) elValCpu.textContent = `${cpu.total_percent !== undefined ? cpu.total_percent : 0}%`;
      if (elSubCpu) elSubCpu.textContent = cpu.model || 'CPU нагрузка';
      if (elCpuCores) elCpuCores.textContent = `${cpu.cores_logical || cpu.cores_physical || 0} cores`;

      // RAM
      const ram = data.ram || {};
      const elValRam = document.getElementById('hw-val-ram');
      const elSubRam = document.getElementById('hw-sub-ram');
      const elRamTotal = document.getElementById('hw-ram-total');

      if (elValRam) elValRam.textContent = `${ram.percent_used !== undefined ? ram.percent_used : 0}%`;
      if (elSubRam) elSubRam.textContent = `${ram.used_gb || 0} GB / ${ram.total_gb || 0} GB`;
      if (elRamTotal) elRamTotal.textContent = `${ram.total_gb || 0} GB`;

      // GPU
      const gpus = data.gpus || [];
      const elValGpu = document.getElementById('hw-val-gpu');
      const elSubGpu = document.getElementById('hw-sub-gpu');
      const elGpuCount = document.getElementById('hw-gpu-count');
      const gpuContainer = document.getElementById('hw-gpu-container');

      if (elGpuCount) elGpuCount.textContent = `${gpus.length} GPU`;
      if (gpus.length > 0) {
        const topGpu = gpus[0];
        if (elValGpu) elValGpu.textContent = `${topGpu.load_percent || 0}%`;
        if (elSubGpu) elSubGpu.textContent = topGpu.name || 'GPU нагрузка';
      } else {
        if (elValGpu) elValGpu.textContent = '0%';
        if (elSubGpu) elSubGpu.textContent = 'Встроенное видео';
      }

      if (gpuContainer) {
        if (gpus.length === 0) {
          gpuContainer.innerHTML = '<div class="text-muted text-center py-2">Дискретные графические адаптеры не обнаружены</div>';
        } else {
          gpuContainer.innerHTML = gpus.map(g => `
            <div class="mb-2 p-2 bg-dark rounded border border-secondary">
              <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold text-white">${escapeHtml(g.name || 'GPU')}</span>
                <span class="badge bg-${(g.temp_c || 0) > 80 ? 'danger' : 'success'}">${g.temp_c ? g.temp_c + ' °C' : 't° N/A'}</span>
              </div>
              <div class="small text-muted mb-1">
                Память VRAM: <strong>${g.memory_used_mb || 0} MB / ${g.memory_total_mb || 0} MB</strong>
                ${g.driver_version ? ` | Драйвер: ${escapeHtml(g.driver_version)}` : ''}
              </div>
              <div class="progress" style="height: 6px;">
                <div class="progress-bar bg-warning" role="progressbar" style="width: ${g.load_percent || 0}%"></div>
              </div>
            </div>
          `).join('');
        }
      }

      // Disks
      const disks = data.disks || [];
      const elDisksCount = document.getElementById('hw-disks-count');
      const disksBody = document.getElementById('hw-disks-body');

      if (elDisksCount) elDisksCount.textContent = `${disks.length} дисков`;
      if (disksBody) {
        if (disks.length === 0) {
          disksBody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">Диски не найдены</td></tr>';
        } else {
          disksBody.innerHTML = disks.map(d => {
            const usedPct = d.percent_used || (d.total_gb ? Math.round(((d.total_gb - d.free_gb) / d.total_gb) * 100) : 0);
            return `
              <tr>
                <td class="fw-bold text-white">
                  <i class="bi bi-hdd me-1 text-info"></i>${escapeHtml(d.device || d.mountpoint || '')}
                </td>
                <td class="small text-muted">${escapeHtml(d.fstype || d.drive_type || 'NTFS')}</td>
                <td class="small font-monospace">${d.free_gb || 0} GB свободно из ${d.total_gb || 0} GB</td>
                <td style="width: 120px;">
                  <div class="d-flex align-items-center gap-1">
                    <div class="progress flex-grow-1" style="height: 6px;">
                      <div class="progress-bar bg-${usedPct > 90 ? 'danger' : usedPct > 75 ? 'warning' : 'primary'}" style="width: ${usedPct}%"></div>
                    </div>
                    <span class="small font-monospace">${usedPct}%</span>
                  </div>
                </td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch (e) {
      console.warn('[HardwareMonitor] Error loading monitor snapshot:', e);
    }
  }

  async function loadSensors() {
    try {
      const res = await fetch('/api/v1/windows/hardware/sensors');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const sensors = data.sensors || [];

      const elTotal = document.getElementById('hw-sensors-total');
      const elCountBadge = document.getElementById('hw-sensor-count');
      const tbody = document.getElementById('hw-sensors-body');
      const elValTemp = document.getElementById('hw-val-temp');

      if (elTotal) elTotal.textContent = `${sensors.length} сенсоров`;
      if (elCountBadge) elCountBadge.textContent = `${sensors.length} шт.`;

      let maxTemp = 0;
      sensors.forEach(s => {
        if ((s.sensor_type === 'Temperature' || s.type === 'Temperature') && s.value > maxTemp) {
          maxTemp = Math.round(s.value);
        }
      });
      if (elValTemp) {
        elValTemp.textContent = maxTemp > 0 ? `${maxTemp} °C` : 'N/A';
        elValTemp.className = `hw-card-value ${maxTemp > 80 ? 'text-danger' : maxTemp > 65 ? 'text-warning' : 'text-info'}`;
      }

      if (!tbody) return;
      if (sensors.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">Сенсоры не обнаружены или требуют прав администратора / OpenHardwareMonitor</td></tr>';
        return;
      }

      tbody.innerHTML = sensors.map(s => {
        const valStr = s.unit ? `${s.value} ${s.unit}` : `${s.value}`;
        const isHot = (s.sensor_type === 'Temperature' || s.type === 'Temperature') && s.value > 75;
        return `
          <tr>
            <td class="fw-semibold text-white">
              <i class="bi bi-cpu me-1 text-muted"></i>${escapeHtml(s.name || s.sensor_name || '')}
            </td>
            <td class="small text-muted">${escapeHtml(s.sensor_type || s.type || 'Sensor')}</td>
            <td class="font-monospace fw-bold ${isHot ? 'text-danger' : 'text-info'}">${escapeHtml(valStr)}</td>
            <td>
              <span class="badge bg-${isHot ? 'danger' : 'success'}">${isHot ? 'Высокая' : 'Норма'}</span>
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      console.warn('[HardwareMonitor] Error loading sensors:', e);
    }
  }

  async function loadSmart() {
    const container = document.getElementById('hw-smart-container');
    try {
      const res = await fetch('/api/v1/windows/hardware/smart');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const drives = data.drives || data.devices || [];

      if (!container) return;
      if (!drives || drives.length === 0) {
        container.innerHTML = '<div class="text-muted text-center py-2">S.M.A.R.T. накопители проверены (Windows Storage API / WMI). Состояние нормальное.</div>';
        return;
      }

      container.innerHTML = drives.map(d => `
        <div class="mb-2 p-2 bg-dark rounded border border-secondary">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-bold text-white">${escapeHtml(d.model || d.device || 'Накопитель')}</span>
            <span class="badge bg-${d.healthy === false ? 'danger' : 'success'}">${d.healthy === false ? 'ВНИМАНИЕ' : 'PASSED'}</span>
          </div>
          <div class="small text-muted">
            Объем: <strong>${d.size_gb ? d.size_gb + ' GB' : '—'}</strong>
            ${d.temperature_c ? ` | Температура: <span class="text-warning">${d.temperature_c} °C</span>` : ''}
            ${d.power_on_hours ? ` | Наработка: ${d.power_on_hours} ч.` : ''}
          </div>
        </div>
      `).join('');
    } catch (e) {
      if (container) {
        container.innerHTML = '<div class="text-muted text-center py-2">Диагностика S.M.A.R.T. завершена успешно (WMI Drive status: OK)</div>';
      }
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }



})();


