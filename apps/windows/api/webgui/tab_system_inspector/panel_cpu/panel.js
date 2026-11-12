/**
 * =============================================================================
 * Process Name: System Inspector - CPU Panel
 * =============================================================================
 * Description:
 *   Модуль панели процессора (CPU) для вкладки tab_system_inspector.
 *   Отображение нагрузки ядер, частот, температур, мощности пакета,
 *   мульти-осевого SVG-графика с историей и селектором интервалов.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_system_inspector/panel_cpu
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 16:10:00
 * =============================================================================
 */

import {
  escapeHtml,
  formatSparkTimeLabel,
  createGaugeSvg,
  createTempSliderHtml
} from '../common/ui_utils.js';
import { renderCpuSpark as renderCpuSparkSvg } from './spark.js';

let lastCpuCoresData = [];
let lastCpuSensorsData = [];
let lastCpuData = null;
let lastCpuSparkData = null;
const _cpuSparkHistory = [];
let currentCpuSparkInterval = 'seconds';
let currentCpuSparkScale = 'lin';

/**
 * Инициализация панели процессора и привязка событий.
 */
export function initCpuPanel() {
  const selInterval = document.getElementById('sel-cpu-spark-interval');
  if (selInterval) {
    selInterval.onchange = async () => {
      currentCpuSparkInterval = selInterval.value;
      if (currentCpuSparkInterval === 'seconds') {
        await fetchCpuLoadFromApi();
      } else {
        await fetchCpuHistoryByInterval(currentCpuSparkInterval);
      }
    };
  }

  const btnLog = document.getElementById('btn-cpu-spark-log');
  const btnLin = document.getElementById('btn-cpu-spark-lin');
  if (btnLog) btnLog.onclick = () => setCpuSparkScale('log');
  if (btnLin) btnLin.onclick = () => setCpuSparkScale('lin');

  // Экспорт функции масштабирования в глобальную область
  window.setCpuSparkScale = setCpuSparkScale;
}

/**
 * Переключение масштаба графика (линейный / логарифмический).
 * @param {'lin'|'log'} scale - Тип шкалы
 */
export function setCpuSparkScale(scale) {
  currentCpuSparkScale = scale;
  const btnLog = document.getElementById('btn-cpu-spark-log');
  const btnLin = document.getElementById('btn-cpu-spark-lin');
  if (btnLog && btnLin) {
    if (scale === 'log') {
      btnLog.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLin.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    } else {
      btnLin.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLog.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    }
  }
  if (lastCpuSparkData && lastCpuSparkData.length) {
    renderCpuSpark(lastCpuSparkData);
  }
}

/**
 * Запрос данных загрузки CPU из REST API.
 */
export async function fetchCpuLoadFromApi() {
  try {
    const res = await fetch('/api/v1/panel/cpu-load');
    if (!res.ok) return;
    const data = await res.json();
    lastCpuData = data;
    updateCpuUi(data);
  } catch (e) {
    console.warn('[CpuPanel] Ошибка получения загрузки CPU:', e);
  }
}

/**
 * Запрос архивной истории CPU по выбранному интервалу времени.
 * @param {string} interval - Интервал выборки
 */
export async function fetchCpuHistoryByInterval(interval) {
  try {
    const res = await fetch(`/api/v1/telemetry/history?interval=${encodeURIComponent(interval)}&metric=cpu&limit=120`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && Array.isArray(data.history) && data.history.length > 0) {
      lastCpuSparkData = data.history.map(r => ({
        timestamp: r.timestamp,
        time_label: formatSparkTimeLabel(r.timestamp || r.created_at, interval),
        load_percent: Number(r.cpu_total_percent || 0),
        temperature_c: r.gpu_temp_c != null ? Number(r.gpu_temp_c) : null,
        power_w: null
      }));
      renderCpuSpark(lastCpuSparkData);
    }
  } catch (e) {
    console.warn('[CpuPanel] Ошибка получения истории CPU по интервалу:', e);
  }
}

/**
 * Обновление метрик CPU из живого снимка WebSocket телеметрии.
 * @param {Object} cpuData - Срез телеметрии cpu из SystemSnapshot
 */
export function updateCpuTelemetry(cpuData) {
  if (!cpuData) return;
  const cpuVal = document.getElementById('sys-metric-cpu-val');
  const cpuModel = document.getElementById('sys-metric-cpu-model');
  const cpuFill = document.getElementById('sys-metric-cpu-fill');
  const cpuSub = document.getElementById('sys-metric-cpu-sub');
  const cpuGauge = document.getElementById('sys-metric-cpu-gauge');

  const pct = Number(cpuData.total_percent || 0);
  if (cpuVal) cpuVal.innerText = `${pct.toFixed(1)}%`;
  if (cpuModel && cpuData.name) {
    cpuModel.innerText = cpuData.name;
  } else if (cpuModel && cpuData.model && !cpuData.model.includes('Stepping') && (!cpuModel.innerText || cpuModel.innerText === '--')) {
    cpuModel.innerText = cpuData.model;
  }
  if (cpuFill) cpuFill.style.width = `${Math.min(100, pct)}%`;
  if (cpuSub && (cpuData.physical_cores || cpuData.logical_cores)) {
    cpuSub.innerText = `${cpuData.physical_cores || '--'} ядер • ${cpuData.logical_cores || '--'} потоков`;
  }
  if (cpuGauge) cpuGauge.innerHTML = createGaugeSvg(pct, 120, 68);

  const kpiCores = document.getElementById('sys-cpu-kpi-cores');
  if (kpiCores && (cpuData.physical_cores || cpuData.logical_cores)) {
    kpiCores.innerText = `${cpuData.physical_cores || '--'}C / ${cpuData.logical_cores || '--'}T`;
  }
}

/**
 * Отрисовка данных процессора в элементах DOM.
 * @param {Object} data - Ответ от /api/v1/panel/cpu-load
 */
function updateCpuUi(data) {
  const cpuVal = document.getElementById('sys-metric-cpu-val');
  const cpuFill = document.getElementById('sys-metric-cpu-fill');
  const cpuSub = document.getElementById('sys-metric-cpu-sub');
  const cpuModel = document.getElementById('sys-metric-cpu-model');
  const cpuGauge = document.getElementById('sys-metric-cpu-gauge');
  const cpuPkgSlider = document.getElementById('sys-metric-cpu-package-slider');
  const cpuPkgTemp = document.getElementById('sys-metric-cpu-package-temp');

  const pct = Number(data.total_percent || 0);
  const cores = Array.isArray(data.cores) ? data.cores : [];
  const threads = Array.isArray(data.threads) ? data.threads : [];
  const history = Array.isArray(data.history) ? data.history : [];

  if (cpuVal) {
    cpuVal.innerText = `${pct.toFixed(1)}%`;
    if (pct >= 85) {
      cpuVal.style.color = '#ef4444';
      cpuVal.style.textShadow = '0 0 14px rgba(239, 68, 68, 0.6)';
    } else if (pct >= 70) {
      cpuVal.style.color = '#f97316';
      cpuVal.style.textShadow = '0 0 12px rgba(249, 115, 22, 0.45)';
    } else if (pct >= 50) {
      cpuVal.style.color = '#eab308';
      cpuVal.style.textShadow = '0 0 10px rgba(234, 179, 8, 0.4)';
    } else {
      cpuVal.style.color = '#0dcaf0';
      cpuVal.style.textShadow = '0 0 10px rgba(13, 202, 240, 0.35)';
    }
  }
  if (cpuFill) cpuFill.style.width = `${Math.min(100, pct)}%`;

  if (cpuModel && data.name) {
    cpuModel.innerText = data.name;
    cpuModel.title = data.name;
  }

  const pkgTemp = data.package_temperature_c != null ? Number(data.package_temperature_c) : null;
  const pkgPower = data.package_power_w != null ? Number(data.package_power_w) : null;
  if (cpuSub) {
    const t = pkgTemp == null ? '' : ` · ${pkgTemp.toFixed(0)} °C`;
    const p = pkgPower == null ? '' : ` · ${pkgPower.toFixed(0)} W`;
    const cCount = data.cores_count || cores.length;
    const thCount = data.threads_count || threads.length;
    cpuSub.innerText = cCount ? `${cCount} ядер • ${thCount} потоков${t}${p}` : '-- Ядер';
  }
  if (cpuPkgTemp) {
    const pStr = pkgPower != null ? ` · ${pkgPower.toFixed(0)} W` : '';
    cpuPkgTemp.innerText = pkgTemp != null ? `Пакет: ${pkgTemp.toFixed(0)} °C${pStr}` : 'Пакет: -- °C';
    if (pkgTemp != null) {
      if (pkgTemp >= 80) {
        cpuPkgTemp.className = 'text-danger fw-bold font-monospace';
      } else if (pkgTemp >= 65) {
        cpuPkgTemp.className = 'text-warning fw-bold font-monospace';
      } else {
        cpuPkgTemp.className = 'text-info font-monospace';
      }
    }
  }

  // Сводка характеристик
  const specs = data.specs || {};
  const setSpec = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
  if (specs.socket || specs.physical_cores) {
    setSpec('sys-cpu-spec-arch', specs.architecture || 'x86_64');
    setSpec('sys-cpu-spec-socket', specs.socket || 'LGA1200');
    setSpec('sys-cpu-spec-cores', `${specs.physical_cores || cores.length}C / ${specs.logical_cores || threads.length}T`);
    setSpec('sys-cpu-spec-base-freq', specs.base_frequency_str || '--');
    setSpec('sys-cpu-spec-max-freq', specs.max_frequency_str || '--');
    setSpec('sys-cpu-spec-cache', specs.cache_combined_str || '--');
  }

  // KPI баннер
  const kpiPower = document.getElementById('sys-cpu-kpi-power');
  const kpiTemp = document.getElementById('sys-cpu-kpi-temp');
  const kpiCores = document.getElementById('sys-cpu-kpi-cores');
  const kpiFreq = document.getElementById('sys-cpu-kpi-freq');
  const cCount = data.cores_count || (specs.physical_cores || cores.length);
  const thCount = data.threads_count || (specs.logical_cores || threads.length);

  if (kpiPower) kpiPower.textContent = pkgPower != null ? `${pkgPower.toFixed(0)} W` : (data.package_power_w != null ? `${Number(data.package_power_w).toFixed(0)} W` : '-- W');
  if (kpiTemp) {
    kpiTemp.textContent = pkgTemp != null ? `${pkgTemp.toFixed(0)} °C` : '-- °C';
    if (pkgTemp != null) {
      kpiTemp.className = pkgTemp >= 80 ? 'sys-kpi-value text-danger' : pkgTemp >= 65 ? 'sys-kpi-value text-warning' : 'sys-kpi-value text-info';
    }
  }
  if (kpiCores) kpiCores.textContent = cCount ? `${cCount}C / ${thCount}T` : '-- / --';
  if (kpiFreq) {
    const fMax = specs.max_frequency_str || (specs.max_frequency_ghz ? `${specs.max_frequency_ghz} GHz` : null);
    const fBase = specs.base_frequency_str || (specs.base_frequency_ghz ? `${specs.base_frequency_ghz} GHz` : null);
    kpiFreq.textContent = fMax || fBase || '-- GHz';
  }

  const vendorBadge = document.getElementById('sys-metric-cpu-vendor-badge');
  if (vendorBadge) {
    const cpus = Array.isArray(data.cpus) && data.cpus.length > 0 ? data.cpus : [];
    if (cpus.length > 1) {
      vendorBadge.innerHTML = cpus.map((c, i) => `<div class="text-truncate font-monospace" style="font-size: 0.74rem;">CPU #${c.id ?? i}: ${escapeHtml(c.description || `${c.raw_descriptor || c.name} (${c.logical_cores || 12} logical cores)`)}</div>`).join('');
    } else if (data.description || specs.description) {
      vendorBadge.innerText = data.description || specs.description;
    } else {
      const rawDesc = specs.raw_descriptor || 'Intel64 Family 6 Model 165 Stepping 3, GenuineIntel';
      const logCores = data.threads_count || specs.logical_cores || (threads ? threads.length : 12) || 12;
      vendorBadge.innerText = `${rawDesc} (${logCores} logical cores)`;
    }
  }

  if (cpuGauge) {
    cpuGauge.innerHTML = createGaugeSvg(pct, 120, 68);
  }
  if (cpuPkgSlider) {
    cpuPkgSlider.innerHTML = createTempSliderHtml(pkgTemp, 30, 95, false);
  }

  // Физические ядра
  renderCpuCores(cores, data.threads_count || threads.length);

  // Общие системные сенсоры CPU
  renderCpuSensors(data.sensors || []);

  // График истории
  if (history && history.length > 0) {
    renderCpuSpark(history);
  } else {
    _cpuSparkHistory.push({ load: pct, temp: pkgTemp, power: pkgPower, time: new Date() });
    if (_cpuSparkHistory.length > 60) _cpuSparkHistory.shift();
    renderCpuSpark(_cpuSparkHistory);
  }
}

/**
 * Отрисовка списка ядер и потоков процессора.
 * @param {Array} cores - Ядра CPU
 * @param {number} totalThreadsCount - Общее число потоков
 */
export function renderCpuCores(cores, totalThreadsCount) {
  const box = document.getElementById('sys-metric-cpu-cores');
  const badgeCount = document.getElementById('sys-cores-count-badge');
  if (!box) return;

  if (Array.isArray(cores)) {
    lastCpuCoresData = cores;
  } else if (lastCpuCoresData && lastCpuCoresData.length) {
    cores = lastCpuCoresData;
  }

  const cCount = cores ? cores.length : 0;
  const thCount = totalThreadsCount || (cores ? cores.reduce((acc, c) => acc + (c.threads ? c.threads.length : 0), 0) : 0);

  if (badgeCount) {
    badgeCount.textContent = cCount ? `${cCount} ядер • ${thCount} потоков` : '0 ядер';
  }

  if (!Array.isArray(cores) || cores.length === 0) {
    box.innerHTML = `<div class="text-muted small text-center py-3 col-12">Опрос ядер CPU выполняется...</div>`;
    return;
  }

  box.innerHTML = cores.map(c => {
    const load = c.load_percent == null ? null : Number(c.load_percent);
    const temp = c.temperature_c == null ? null : Number(c.temperature_c);
    const freqStr = c.frequency_str || (c.frequency_mhz ? (c.frequency_mhz >= 1000 ? (c.frequency_mhz / 1000).toFixed(2) + ' GHz' : c.frequency_mhz.toFixed(0) + ' MHz') : '--');
    const powerStr = c.power_w != null ? `${Number(c.power_w).toFixed(1)} W` : (c.power_str || '--');
    const loadStr = load == null ? '--' : `${load.toFixed(0)}%`;
    const tempStr = temp != null ? `${temp.toFixed(0)} °C` : '-- °C';
    const gaugeSvg = createGaugeSvg(load, 100, 54);
    const tempHtml = createTempSliderHtml(temp, 30, 95, false);

    return `
      <div class="sys-core-card p-2 rounded-2" style="background: var(--surface-2, rgba(255,255,255,0.03)); border: 1px solid var(--border-color, rgba(255,255,255,0.08));" title="Ядро #${c.index}: Нагрузка ${loadStr}, Температура ${tempStr}">
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom" style="border-color: var(--border-subtle, rgba(255,255,255,0.06)) !important;">
          <div class="d-flex align-items-center gap-1.5">
            <i class="bi bi-cpu text-info"></i>
            <span class="sys-core-title fw-bold" style="font-size: 0.82rem;">Core #${c.index}</span>
          </div>
          <span class="badge ${load != null && load >= 80 ? 'bg-danger' : 'bg-info-subtle text-info border border-info'}" style="font-size: 0.70rem;">${loadStr}</span>
        </div>
        
        <div class="d-flex align-items-center gap-2 mb-2">
          <div class="d-flex flex-column align-items-center justify-content-center" style="width: 96px; flex-shrink: 0;">
            <div style="width: 96px; height: 52px;">
              ${gaugeSvg}
            </div>
            <div class="w-100 mt-1">
              ${tempHtml}
            </div>
          </div>
          <div class="flex-grow-1 ps-1" style="min-width: 0;">
            <div class="sys-core-param-table">
              <div class="sys-core-param-row">
                <span class="sys-core-param-key"><i class="bi bi-activity text-info me-1"></i>Нагрузка</span>
                <span class="sys-core-param-val text-info">${loadStr}</span>
              </div>
              <div class="sys-core-param-row">
                <span class="sys-core-param-key"><i class="bi bi-thermometer-half text-danger me-1"></i>Температура</span>
                <span class="sys-core-param-val ${temp != null && temp >= 75 ? 'text-danger' : 'text-warning'}">${tempStr}</span>
              </div>
              <div class="sys-core-param-row">
                <span class="sys-core-param-key"><i class="bi bi-speedometer2 text-info me-1"></i>Частота</span>
                <span class="sys-core-param-val text-info">${escapeHtml(freqStr)}</span>
              </div>
              <div class="sys-core-param-row">
                <span class="sys-core-param-key"><i class="bi bi-lightning text-warning me-1"></i>Мощность</span>
                <span class="sys-core-param-val text-warning">${escapeHtml(powerStr)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Отрисовка общих системных сенсоров CPU (температуры, частоты, мощности, напряжения).
 * @param {Array} sensors - Список сенсоров CPU
 */
export function renderCpuSensors(sensors) {
  const box = document.getElementById('sys-metric-cpu-sensors');
  const badgeCount = document.getElementById('sys-cpu-sensors-count-badge');
  if (!box) return;

  if (Array.isArray(sensors)) {
    lastCpuSensorsData = sensors;
  } else if (lastCpuSensorsData && lastCpuSensorsData.length) {
    sensors = lastCpuSensorsData;
  }

  const sCount = sensors ? sensors.length : 0;
  if (badgeCount) {
    badgeCount.textContent = `${sCount} параметров`;
  }

  if (!Array.isArray(sensors) || sensors.length === 0) {
    box.innerHTML = `<div class="text-muted small text-center py-2 col-12">Датчики системы опрашиваются...</div>`;
    return;
  }

  box.innerHTML = sensors.map(s => {
    const valStr = s.value_raw || (s.value != null ? `${s.value} ${s.unit || ''}` : '--');
    let icon = 'bi-activity text-info';
    let statusClass = 'bg-info-subtle text-info border-info';
    const cat = (s.category || '').toLowerCase();

    if (cat.includes('temp')) {
      icon = 'bi-thermometer-half text-danger';
      statusClass = s.value >= 80 ? 'bg-danger text-light' : s.value >= 68 ? 'bg-warning text-dark' : 'bg-success-subtle text-success border-success';
    } else if (cat.includes('power')) {
      icon = 'bi-lightning-charge text-warning';
      statusClass = 'bg-warning-subtle text-warning border-warning';
    } else if (cat.includes('volt')) {
      icon = 'bi-broadcast text-primary';
      statusClass = 'bg-primary-subtle text-primary border-primary';
    } else if (cat.includes('clock')) {
      icon = 'bi-speedometer2 text-info';
      statusClass = 'bg-info-subtle text-info border-info';
    } else if (cat.includes('load')) {
      icon = 'bi-cpu text-info';
      statusClass = s.value >= 85 ? 'bg-danger text-light' : s.value >= 70 ? 'bg-warning text-dark' : 'bg-info-subtle text-info border-info';
    }

    return `
      <div class="sys-sensor-widget-item p-2 rounded-2 d-flex align-items-center justify-content-between gap-2" style="background: var(--surface-2); border: 1px solid var(--border-color);" title="${escapeHtml(s.name)}: ${escapeHtml(valStr)}">
        <div class="d-flex align-items-center gap-1.5 text-truncate" style="min-width: 0;">
          <i class="bi ${icon} fs-6 flex-shrink-0"></i>
          <span class="text-truncate" style="font-size: 0.76rem; color: var(--text-color); font-weight: 600;" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
        </div>
        <div class="d-flex align-items-center gap-1 flex-shrink-0">
          <span class="font-monospace fw-bold" style="font-size: 0.78rem;">${escapeHtml(valStr)}</span>
          <span class="badge ${statusClass} border" style="font-size: 0.62rem; padding: 1px 4px;">${escapeHtml(s.status || 'OK')}</span>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Отрисовка SVG-графика истории CPU.
 * @param {Array} history - Массив точек
 */
export function renderCpuSpark(history) {
  const state = { lastCpuSparkData, _cpuSparkHistory };
  renderCpuSparkSvg(history, currentCpuSparkScale, state);
  if (state.lastCpuSparkData) {
    lastCpuSparkData = state.lastCpuSparkData;
  }
}
