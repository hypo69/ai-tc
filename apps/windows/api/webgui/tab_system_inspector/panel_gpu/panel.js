/**
 * =============================================================================
 * Process Name: System Inspector - GPU Panel
 * =============================================================================
 * Description:
 *   Модуль панели графических адаптеров (GPU) для tab_system_inspector.
 *   Поддержка мульти-GPU, нагрузки ядер/движков 3D/Video, памяти VRAM,
 *   температур HotSpot, энергопотребления и SVG-спарклайнов.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_gpu
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 15:17:00
 * =============================================================================
 */

import {
  escapeHtml,
  formatSparkTimeLabel,
  createGaugeSvg,
  createTempSliderHtml,
  createPercentSliderHtml,
  buildSmoothSvgPath
} from '../common/ui_utils.js';

let lastGpuData = null;
let lastGpuDevices = [];
const _gpuSparkHistories = {};
const currentGpuSparkScales = {};
const currentGpuSparkIntervals = {};
const lastGpuSparkDataMap = {};

/**
 * Инициализация панели GPU.
 */
export function initGpuPanel() {
  window.setGpuSparkScale = setGpuSparkScale;
  window.setGpuSparkInterval = setGpuSparkInterval;
  window.inspectGpuSpecsWithAi = (idx) => {
    const gpu = lastGpuDevices[idx] || (lastGpuData && lastGpuData.gpus ? lastGpuData.gpus[idx] : null);
    if (!gpu) return;
    if (window.AITableModal) {
      window.AITableModal.show({
        icon: '🎮',
        title: gpu.name || 'GPU Card',
        subtitle: `Видеоадаптер #${idx} · ${gpu.vendor || 'PCIe'}`,
        panelId: 'gpu',
        tableType: 'hardware',
        badges: [
          { text: `GPU #${idx}`, class: 'badge bg-warning text-dark' },
          { text: `${Number(gpu.core_load_percent || 0).toFixed(0)}%`, class: 'badge bg-primary' }
        ],
        metadata: [
          { label: 'Модель видеокарты', value: gpu.name },
          { label: 'Производитель', value: gpu.vendor || 'GPU' },
          { label: 'Загрузка ядра', value: `${Number(gpu.core_load_percent || 0).toFixed(1)}%` },
          { label: 'Температура ядра', value: gpu.core_temperature_c != null ? `${gpu.core_temperature_c}°C` : '--' },
          { label: 'HotSpot', value: gpu.hotspot_temperature_c != null ? `${gpu.hotspot_temperature_c}°C` : '--' },
          { label: 'Мощность', value: gpu.power_w != null ? `${gpu.power_w} W` : '--' }
        ],
        rawTitle: 'JSON Телеметрии GPU',
        rawContent: JSON.stringify(gpu, null, 2),
        requestData: gpu
      });
    }
  };
}

/**
 * Запрос данных всех GPU из API.
 */
export async function fetchGpuLoadFromApi() {
  try {
    const res = await fetch('/api/v1/panel/gpu-load');
    if (!res.ok) return;
    const data = await res.json();
    lastGpuData = data;
    let devices = Array.isArray(data.devices) && data.devices.length > 0
      ? data.devices
      : (Array.isArray(data.gpus) && data.gpus.length > 0
        ? data.gpus
        : (Array.isArray(data.available_gpus) && data.available_gpus.length > 0
          ? data.available_gpus
          : []));
    if (devices.length === 0 && data.name && data.name !== 'GPU') {
      devices = [data];
    }

    // Клиентская дедупликация: исключаем повторный вывод одной и той же видеокарты
    const seenNames = new Set();
    const uniqueDevices = [];
    for (const d of devices) {
      const cleanName = String(d.name || '').toLowerCase().replace(/\((r|tm)\)/g, '').replace(/[^a-z0-9]+/g, '');
      let isDuplicate = false;
      for (const prev of seenNames) {
        if (prev === cleanName || (cleanName.length > 6 && (prev.includes(cleanName) || cleanName.includes(prev)))) {
          isDuplicate = true;
          break;
        }
      }
      if (!isDuplicate && cleanName) {
        seenNames.add(cleanName);
        uniqueDevices.push(d);
      }
    }
    devices = uniqueDevices.length > 0 ? uniqueDevices : devices;
    devices.forEach((d, i) => { d.index = i; });
    lastGpuDevices = devices;

    const container = document.getElementById('sys-gpu-panels-container') || document.getElementById('sys-gpu-container');
    if (container) {
      if (devices.length > 0) {
        const currentCardsCount = container.querySelectorAll('.sys-card-gpu').length;
        if (currentCardsCount !== devices.length) {
          container.innerHTML = devices.map((g, i) => renderGpuCardHtml(g, i, devices.length)).join('');
        }
        devices.forEach((g, i) => updateSingleGpuCard(g, i, devices.length));
      } else {
        container.innerHTML = `
          <div class="alert alert-dark border-secondary text-center text-muted py-3 my-2">
            <i class="bi bi-gpu-card me-2"></i>Видеоадаптеры не обнаружены
          </div>
        `;
      }
    }
  } catch (e) {
    console.warn('[GpuPanel] Ошибка получения данных GPU из API:', e);
  }
}

/**
 * Запрос истории метрик GPU по выбранному интервалу.
 * @param {number} idx - Индекс GPU
 * @param {string} interval - Интервал
 */
export async function fetchGpuHistoryByInterval(idx, interval) {
  try {
    const res = await fetch(`/api/v1/telemetry/history?interval=${encodeURIComponent(interval)}&metric=gpu&limit=120`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && Array.isArray(data.history) && data.history.length > 0) {
      lastGpuSparkDataMap[idx] = data.history.map(r => ({
        timestamp: r.timestamp,
        time_label: formatSparkTimeLabel(r.timestamp || r.created_at, interval),
        core_load_percent: Number(r.gpu_load_percent || 0),
        core_temperature_c: r.gpu_temp_c != null ? Number(r.gpu_temp_c) : null,
        power_w: null
      }));
      renderGpuSpark(lastGpuSparkDataMap[idx], idx);
    }
  } catch (e) {
    console.warn(`[GpuPanel] Ошибка получения истории GPU #${idx}:`, e);
  }
}

/**
 * Установка интервала графика GPU.
 * @param {number} idx - Индекс GPU
 * @param {string} interval - Интервал
 */
export async function setGpuSparkInterval(idx, interval) {
  currentGpuSparkIntervals[idx] = interval;
  const el = document.getElementById(`sel-gpu-spark-interval-${idx}`);
  if (el) el.value = interval;
  if (interval === 'seconds') {
    await fetchGpuLoadFromApi();
  } else {
    await fetchGpuHistoryByInterval(idx, interval);
  }
}

/**
 * Установка масштаба графика GPU.
 * @param {number} idx - Индекс GPU
 * @param {'lin'|'log'} scale - Тип шкалы
 */
export function setGpuSparkScale(idx, scale) {
  currentGpuSparkScales[idx] = scale;
  const btnLog = document.getElementById(`btn-gpu-spark-log-${idx}`);
  const btnLin = document.getElementById(`btn-gpu-spark-lin-${idx}`);
  if (btnLog && btnLin) {
    if (scale === 'log') {
      btnLog.className = 'btn btn-xs btn-outline-warning active py-0 px-2 fw-bold';
      btnLin.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    } else {
      btnLin.className = 'btn btn-xs btn-outline-warning active py-0 px-2 fw-bold';
      btnLog.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    }
  }
  const sparkData = lastGpuSparkDataMap[idx];
  if (sparkData && sparkData.length) {
    renderGpuSpark(sparkData, idx);
  }
}

/**
 * Обновление метрик GPU из живого снимка телеметрии.
 * @param {Object|Array} gpuData - Срез telemetry.gpu или telemetry.gpus из SystemSnapshot
 */
export function updateGpuTelemetry(gpuData) {
  if (!gpuData) return;
  const list = Array.isArray(gpuData) ? gpuData : [gpuData];
  list.forEach((gpu, snapIdx) => {
    // Сопоставляем устройство по имени или исходному индексу
    let idx = snapIdx;
    if (lastGpuDevices && lastGpuDevices.length > 0) {
      const gName = String(gpu.name || '').toLowerCase().replace(/\((r|tm)\)/g, '').replace(/[^a-z0-9]+/g, '');
      const foundIdx = lastGpuDevices.findIndex(d => {
        const dName = String(d.name || '').toLowerCase().replace(/\((r|tm)\)/g, '').replace(/[^a-z0-9]+/g, '');
        return dName === gName || (gName.length > 6 && (dName.includes(gName) || gName.includes(dName)));
      });
      if (foundIdx !== -1) {
        idx = foundIdx;
      }
    }
    const pct = Number(gpu.load_percent != null ? gpu.load_percent : (gpu.core_load_percent || 0));
    const temp = gpu.temperature_c != null ? Number(gpu.temperature_c) : (gpu.temperature_celsius != null ? Number(gpu.temperature_celsius) : null);
    const vramUsedGb = Number(gpu.memory_used_gb != null ? gpu.memory_used_gb : (gpu.vram_mb ? gpu.vram_mb / 1024 : 0));
    const vramTotalGb = Number(gpu.memory_total_gb != null ? gpu.memory_total_gb : (gpu.vram_gb ? gpu.vram_gb : 0));

    const gpuVal = document.getElementById(`sys-metric-gpu-val-${idx}`);
    const gpuGauge = document.getElementById(`sys-metric-gpu-gauge-${idx}`);
    const gpuCoreTemp = document.getElementById(`sys-metric-gpu-core-temp-${idx}`);
    const gpuKpiVram = document.getElementById(`sys-gpu-kpi-vram-${idx}`);
    const gpuKpiTemp = document.getElementById(`sys-gpu-kpi-temp-${idx}`);
    const gpuTempSlider = document.getElementById(`sys-metric-gpu-temp-slider-${idx}`);

    if (gpuVal) gpuVal.innerText = `${pct.toFixed(1)}%`;
    if (gpuGauge) gpuGauge.innerHTML = createGaugeSvg(pct, 120, 68);
    if (gpuCoreTemp && temp != null) gpuCoreTemp.innerText = `GPU: ${temp.toFixed(0)} °C`;
    if (gpuKpiTemp && temp != null) gpuKpiTemp.innerText = `${temp.toFixed(0)} °C`;
    if (gpuTempSlider && temp != null) gpuTempSlider.innerHTML = createTempSliderHtml(temp, 30, 95, false);
    if (gpuKpiVram && vramTotalGb > 0) gpuKpiVram.innerText = `${vramUsedGb.toFixed(1)} / ${vramTotalGb.toFixed(1)} GB`;
  });
}

/**
 * Генерация HTML разметки карточки GPU.
 */
function renderGpuCardHtml(gpu, idx, totalDevices) {
  const gpuName = escapeHtml(gpu.name || `GPU #${idx}`);
  const vendor = escapeHtml(gpu.vendor || 'GPU');
  const headerTitle = totalDevices > 1 ? `Загрузка GPU #${gpu.index != null ? gpu.index : idx}: ${gpuName}` : `Загрузка GPU: ${gpuName}`;

  return `
    <div class="sys-card sys-card-gpu h-100" id="sys-card-gpu-${idx}" data-panel-id="panel-gpu-${idx}">
      <div class="sys-card-header-bar">
        <div class="d-flex align-items-center gap-2">
          <span class="sys-label">
            <i class="bi bi-gpu-card text-warning me-1.5"></i>${headerTitle}
          </span>
          <span class="badge bg-dark border border-secondary text-info font-monospace ms-1" style="font-size: 0.74rem;">
            ${vendor}
          </span>
        </div>
        <span class="small text-truncate font-monospace badge bg-dark border border-secondary text-warning" style="font-size: 0.84rem; max-width: 320px;" id="sys-metric-gpu-sub-${idx}">--</span>
      </div>

      <div class="sys-card-top-banner" id="sys-card-gpu-banner-${idx}" onclick="window.toggleSysCardDrill && window.toggleSysCardDrill('sys-card-gpu-${idx}', ${idx}, event)" title="Нажмите для развертывания/сворачивания деталей GPU">
        <div class="sys-banner-col-info">
          <div class="text-start mb-1 d-flex align-items-center">
            <button type="button" class="sys-drill-btn" id="sys-drill-btn-gpu-${idx}" onclick="event.stopPropagation(); window.toggleSysCardDrill && window.toggleSysCardDrill('sys-card-gpu-${idx}', ${idx}, event)" title="">
              <img src="/html/assets/red_drill.png?v=20261113_v1" alt="" title="">
            </button>
            <div class="text-truncate">
              <span class="panel-title sys-metric-model-title text-truncate" id="sys-metric-gpu-model-${idx}">${gpuName}</span>
              <div class="d-flex align-items-center gap-1.5 mt-0.5">
                <span class="badge bg-dark border border-secondary text-light font-monospace" id="sys-metric-gpu-vendor-badge-${idx}" style="font-size: 0.70rem;">${vendor} · PCIe</span>
                <span class="badge bg-success-subtle text-success border border-success font-monospace" id="sys-gpu-status-badge-${idx}" style="font-size: 0.70rem;">● Ready</span>
              </div>
            </div>
          </div>
          <div class="sys-banner-kpi-grid">
            <div class="sys-kpi-pill">
              <span class="sys-kpi-label"><i class="bi bi-memory text-info me-1"></i>VRAM Память</span>
              <span class="sys-kpi-value text-info" id="sys-gpu-kpi-vram-${idx}">-- / -- GB</span>
            </div>
            <div class="sys-kpi-pill">
              <span class="sys-kpi-label"><i class="bi bi-lightning-charge text-warning me-1"></i>Мощность</span>
              <span class="sys-kpi-value text-warning" id="sys-gpu-kpi-power-${idx}">-- W</span>
            </div>
            <div class="sys-kpi-pill">
              <span class="sys-kpi-label"><i class="bi bi-speedometer2 text-primary me-1"></i>Частота Core</span>
              <span class="sys-kpi-value text-primary" id="sys-gpu-kpi-clock-${idx}">-- MHz</span>
            </div>
            <div class="sys-kpi-pill">
              <span class="sys-kpi-label"><i class="bi bi-thermometer-half text-danger me-1"></i>GPU t°</span>
              <span class="sys-kpi-value text-warning" id="sys-gpu-kpi-temp-${idx}">-- °C</span>
            </div>
          </div>
        </div>

        <div class="sys-banner-col-gauge">
          <div class="sys-gauge-box">
            <div class="sys-gauge-svg-wrap" id="sys-metric-gpu-gauge-${idx}"></div>
            <div class="sys-gauge-val-wrap">
              <div class="sys-value text-warning" id="sys-metric-gpu-val-${idx}">0.0%</div>
              <div class="sys-gauge-subtext text-light" id="sys-metric-gpu-core-temp-${idx}">GPU: -- °C</div>
            </div>
          </div>
          <div class="sys-gauge-slider-wrap" id="sys-metric-gpu-temp-slider-${idx}"></div>
        </div>

        <div class="sys-banner-col-specs">
          <div class="sys-specs-card sys-gpu-specs-card" 
               id="sys-gpu-specs-card-${idx}"
               onclick="window.inspectGpuSpecsWithAi && window.inspectGpuSpecsWithAi(${idx})"
               title="AI-аудит графического процессора">
            <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom" style="border-color: var(--border-subtle) !important;">
              <span class="text-light fw-bold d-flex align-items-center gap-1" style="font-size: 0.78rem;">
                <i class="bi bi-info-circle text-warning"></i>Характеристики GPU
                <span class="badge bg-primary-subtle text-primary border border-primary-subtle font-monospace ms-1" style="font-size: 0.62rem;"><i class="bi bi-stars me-0.5"></i>AI</span>
              </span>
              <span class="badge bg-dark border border-secondary text-warning font-monospace" style="font-size: 0.68rem;" id="sys-gpu-spec-directx-${idx}">DirectX 12</span>
            </div>
            <div class="sys-specs-grid sys-gpu-specs-grid">
              <div class="d-flex justify-content-between"><span class="text-muted">VRAM:</span><span class="font-monospace text-light fw-bold" id="sys-gpu-spec-vram-${idx}">-- GB</span></div>
              <div class="d-flex justify-content-between"><span class="text-muted">Занято:</span><span class="font-monospace text-info fw-bold" id="sys-gpu-spec-vram-used-${idx}">--%</span></div>
              <div class="d-flex justify-content-between"><span class="text-muted">Частота:</span><span class="font-monospace text-warning fw-bold" id="sys-gpu-spec-core-clock-${idx}">-- MHz</span></div>
              <div class="d-flex justify-content-between"><span class="text-muted">Драйвер:</span><span class="font-monospace text-light text-truncate" style="max-width: 110px;" id="sys-gpu-spec-driver-${idx}">--</span></div>
              <div class="d-flex justify-content-between" style="grid-column: span 2;"><span class="text-muted">Интерфейс:</span><span class="font-monospace text-warning fw-bold" id="sys-gpu-spec-bus-${idx}">PCI Express · Active</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Скрытый блок деталей GPU (открывается по клику на панель с красной дрелью) -->
      <div id="sys-card-gpu-${idx}-details" class="sys-card-details-collapse">
        <div class="row g-2 mb-2 sys-full-only" id="sys-gpu-engines-row-${idx}"></div>

        <div class="sys-spark-wrap p-2.5 rounded-3 mb-2 sys-full-only">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <div class="d-flex align-items-center gap-2">
              <span class="text-light fw-semibold" style="font-size: 0.82rem;"><i class="bi bi-graph-up text-warning me-1"></i>История GPU (Загрузка %, Температура °C, Мощность W)</span>
              <div class="btn-group btn-group-xs" role="group">
                <button type="button" class="btn btn-xs btn-outline-warning active py-0 px-2 fw-bold" id="btn-gpu-spark-lin-${idx}" onclick="window.setGpuSparkScale && window.setGpuSparkScale(${idx}, 'lin')">Lin</button>
                <button type="button" class="btn btn-xs btn-outline-secondary py-0 px-2" id="btn-gpu-spark-log-${idx}" onclick="window.setGpuSparkScale && window.setGpuSparkScale(${idx}, 'log')">Log</button>
              </div>
            </div>
            <div class="d-flex align-items-center gap-1.5">
              <select class="form-select form-select-xs bg-dark text-light border-secondary font-monospace sys-spark-interval-select" 
                      id="sel-gpu-spark-interval-${idx}" 
                      style="font-size: 0.72rem; padding: 1px 20px 1px 6px; width: auto;"
                      onchange="window.setGpuSparkInterval && window.setGpuSparkInterval(${idx}, this.value)">
                <option value="seconds" selected>Секунды</option>
                <option value="minutes">Минуты</option>
                <option value="hours">Часы</option>
                <option value="days">Дни</option>
                <option value="weeks">Недели</option>
                <option value="all">Все</option>
              </select>
            </div>
          </div>
          <div id="sys-gpu-spark-container-${idx}" style="position: relative; width: 100%; height: 84px;">
            <div id="sys-gpu-spark-${idx}" style="width: 100%; height: 100%;"></div>
            <div class="sys-spark-tooltip" id="sys-gpu-spark-tooltip-${idx}" style="display: none;"></div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Обновление полей карточки конкретного GPU.
 */
function updateSingleGpuCard(gpu, idx, totalDevices) {
  const pct = Number(gpu.core_load_percent || 0);
  const coreTemp = gpu.core_temperature_c != null ? Number(gpu.core_temperature_c) : null;
  const hotspotTemp = gpu.hotspot_temperature_c != null ? Number(gpu.hotspot_temperature_c) : null;
  const powerW = gpu.power_w != null ? Number(gpu.power_w) : null;
  const clocks = gpu.clocks || {};
  const memory = gpu.memory || {};
  const specs = gpu.specs || {};

  const gpuVal = document.getElementById(`sys-metric-gpu-val-${idx}`);
  const gpuModel = document.getElementById(`sys-metric-gpu-model-${idx}`);
  const gpuSub = document.getElementById(`sys-metric-gpu-sub-${idx}`);
  const gpuGauge = document.getElementById(`sys-metric-gpu-gauge-${idx}`);
  const gpuTempSlider = document.getElementById(`sys-metric-gpu-temp-slider-${idx}`);
  const gpuCoreTemp = document.getElementById(`sys-metric-gpu-core-temp-${idx}`);

  if (gpuVal) gpuVal.innerText = `${pct.toFixed(1)}%`;
  if (gpuModel) gpuModel.innerText = gpu.name || 'GPU';

  if (gpuCoreTemp) {
    let tempText = coreTemp != null ? `GPU: ${coreTemp.toFixed(0)} °C` : 'GPU: -- °C';
    if (hotspotTemp != null) tempText += ` (HotSpot: ${hotspotTemp.toFixed(0)}°C)`;
    gpuCoreTemp.innerText = tempText;
  }

  if (gpuSub) {
    let subText = '';
    if (clocks && clocks.core_mhz) subText += `${Math.round(clocks.core_mhz)} MHz`;
    if (memory && memory.total_mb) subText += (subText ? ' · ' : '') + `${(memory.total_mb / 1024).toFixed(1)} GB VRAM`;
    gpuSub.innerText = subText || (gpu.name || 'GPU');
  }

  const specVram = document.getElementById(`sys-gpu-spec-vram-${idx}`);
  const specVramUsed = document.getElementById(`sys-gpu-spec-vram-used-${idx}`);
  const specCoreClock = document.getElementById(`sys-gpu-spec-core-clock-${idx}`);
  const specDriver = document.getElementById(`sys-gpu-spec-driver-${idx}`);
  const specDirectX = document.getElementById(`sys-gpu-spec-directx-${idx}`);
  const specBus = document.getElementById(`sys-gpu-spec-bus-${idx}`);

  if (specVram) specVram.textContent = specs.vram_str || (memory.total_mb ? `${(memory.total_mb/1024).toFixed(1)} GB` : '--');
  if (specVramUsed) specVramUsed.textContent = specs.vram_used_str || (memory.used_percent != null ? `${memory.used_percent.toFixed(0)}%` : '--');
  if (specCoreClock) specCoreClock.textContent = specs.core_clock_str || (clocks.core_mhz ? `${Math.round(clocks.core_mhz)} MHz` : '--');
  if (specDriver) specDriver.textContent = specs.driver_version || gpu.driver_version || '--';
  if (specDirectX && (specs.directx || gpu.directx_version)) {
    specDirectX.textContent = specs.directx || gpu.directx_version;
  }
  if (specBus) {
    specBus.textContent = specs.bus_interface || (gpu.pci_bus ? `PCIe ${gpu.pci_bus}` : 'PCI Express · Active');
  }

  const kpiVram = document.getElementById(`sys-gpu-kpi-vram-${idx}`);
  const kpiPower = document.getElementById(`sys-gpu-kpi-power-${idx}`);
  const kpiClock = document.getElementById(`sys-gpu-kpi-clock-${idx}`);
  const kpiTemp = document.getElementById(`sys-gpu-kpi-temp-${idx}`);

  if (kpiVram && memory.total_mb) {
    kpiVram.textContent = `${((memory.used_mb || 0)/1024).toFixed(1)} / ${(memory.total_mb/1024).toFixed(1)} GB`;
  }
  if (kpiPower) kpiPower.textContent = powerW != null ? `${powerW.toFixed(0)} W` : '-- W';
  if (kpiClock) kpiClock.textContent = clocks.core_mhz ? `${Math.round(clocks.core_mhz)} MHz` : '-- MHz';
  if (kpiTemp) kpiTemp.textContent = coreTemp != null ? `${coreTemp.toFixed(0)} °C` : '-- °C';

  if (gpuGauge) gpuGauge.innerHTML = createGaugeSvg(pct, 120, 68);
  if (gpuTempSlider) gpuTempSlider.innerHTML = createTempSliderHtml(coreTemp, 30, 95, false);

  // Отрисовка движков GPU
  const enginesRow = document.getElementById(`sys-gpu-engines-row-${idx}`);
  if (enginesRow) {
    const engines = Array.isArray(gpu.engines) ? gpu.engines : [];
    if (engines.length > 0) {
      enginesRow.innerHTML = engines.map(eng => {
        const engLoad = eng.load_percent != null ? Number(eng.load_percent) : (typeof eng.load === 'number' ? eng.load : 0);
        return `
          <div class="col-6 col-md-4 col-lg-3 col-xl-2">
            <div class="p-2 rounded-2 h-100 d-flex flex-column justify-content-between" style="background: var(--surface-2); border: 1px solid var(--border-color);">
              <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="small text-truncate fw-semibold" style="font-size: 0.72rem;" title="${escapeHtml(eng.name)}">${escapeHtml(eng.name)}</span>
                <span class="badge ${engLoad >= 80 ? 'bg-danger' : 'bg-dark border border-secondary text-info'} font-monospace" style="font-size: 0.68rem;">${engLoad.toFixed(0)}%</span>
              </div>
              <div class="progress" style="height: 5px; background: rgba(255,255,255,0.08);">
                <div class="progress-bar ${engLoad >= 80 ? 'bg-danger' : engLoad >= 50 ? 'bg-warning' : 'bg-info'}" style="width: ${Math.min(100, Math.max(0, engLoad))}%;"></div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    } else {
      enginesRow.innerHTML = `<div class="text-muted small text-center py-2 col-12">Движки GPU не обнаружены или неактивны</div>`;
    }
  }

  // Спарклайн GPU
  const history = Array.isArray(gpu.history) ? gpu.history : [];
  if (!_gpuSparkHistories[idx]) _gpuSparkHistories[idx] = [];
  if (history && history.length > 0) {
    renderGpuSpark(history, idx);
  } else {
    _gpuSparkHistories[idx].push({ core_load_percent: pct, core_temperature_c: coreTemp, power_w: powerW, time: new Date() });
    if (_gpuSparkHistories[idx].length > 60) _gpuSparkHistories[idx].shift();
    renderGpuSpark(_gpuSparkHistories[idx], idx);
  }
}

/**
 * Отрисовка SVG-спарклайна GPU.
 */
export function renderGpuSpark(history, idx = 0) {
  const box = document.getElementById(`sys-gpu-spark-${idx}`);
  const tooltip = document.getElementById(`sys-gpu-spark-tooltip-${idx}`);
  if (!box) return;

  let ptsData = Array.isArray(history) && history.length > 0 ? history : (lastGpuSparkDataMap[idx] || _gpuSparkHistories[idx] || []);
  if (!ptsData || ptsData.length === 0) {
    ptsData = [{ core_load_percent: 0, core_temperature_c: null, power_w: null, time: new Date() }];
  }
  if (ptsData.length === 1) {
    ptsData = [ptsData[0], { ...ptsData[0], time: ptsData[0].time || new Date() }];
  }
  lastGpuSparkDataMap[idx] = ptsData;
  history = ptsData;

  box.replaceChildren();
  const ns = 'http://www.w3.org/2000/svg';
  const W = 600, H = 84;
  const padTop = 6, padBottom = 6;
  const innerH = H - padTop - padBottom;

  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.style.cssText = 'width:100%;height:100%;display:block;cursor:crosshair;';

  const count = history.length;
  const isLog = currentGpuSparkScales[idx] === 'log';

  const loadPts = [];
  const tempPts = [];
  const powerPts = [];

  history.forEach((h, i) => {
    const x = (i / (count - 1)) * W;
    const lVal = Number(h.core_load_percent != null ? h.core_load_percent : (h.load || 0));
    const tVal = h.core_temperature_c != null ? Number(h.core_temperature_c) : (h.temp != null ? Number(h.temp) : null);
    const pVal = h.power_w != null ? Number(h.power_w) : (h.power != null ? Number(h.power) : null);

    const yLoad = H - padBottom - Math.min(1, lVal / 100) * innerH;
    const yTemp = H - padBottom - (tVal ? Math.min(1, Math.max(0, (tVal - 30) / 65)) : 0.2) * innerH;
    const yPower = H - padBottom - (pVal ? Math.min(1, Math.max(0, pVal / 250)) : 0.1) * innerH;

    loadPts.push({ x, y: yLoad, raw: lVal, time: h.time_label || h.timestamp });
    tempPts.push({ x, y: yTemp, raw: tVal });
    powerPts.push({ x, y: yPower, raw: pVal });
  });

  const drawSeries = (pts, strokeColor, strokeWidth = 1.8) => {
    if (pts.length < 2) return;
    const linePath = buildSmoothSvgPath(pts);
    const pEl = document.createElementNS(ns, 'path');
    pEl.setAttribute('d', linePath);
    pEl.setAttribute('fill', 'none');
    pEl.setAttribute('stroke', strokeColor);
    pEl.setAttribute('stroke-width', String(strokeWidth));
    svg.appendChild(pEl);
  };

  drawSeries(powerPts, '#f59e0b', 1.2);
  drawSeries(tempPts, '#ef4444', 1.3);
  drawSeries(loadPts, '#eab308', 2.0);

  box.appendChild(svg);
}
