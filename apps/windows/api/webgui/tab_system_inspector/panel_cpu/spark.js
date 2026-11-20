/**
 * =============================================================================
 * Process Name: System Inspector - CPU Sparkline SVG Renderer
 * =============================================================================
 * Description:
 *   Модуль отрисовки мульти-осевого SVG-графика истории CPU (нагрузка, температура, мощность).
 *
 * File: spark.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_cpu
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml, buildSmoothSvgPath } from '../common/ui_utils.js';

/**
 * Отрисовка SVG-графика истории CPU.
 * @param {Array} history - Массив точек
 * @param {'lin'|'log'} currentCpuSparkScale - Тип шкалы
 * @param {Object} state - Состояние для кэширования
 */
export function renderCpuSpark(history, currentCpuSparkScale = 'lin', state = {}) {
  const box = document.getElementById('sys-cpu-spark');
  const tooltip = document.getElementById('sys-cpu-spark-tooltip');
  if (!box) return;

  let ptsData = Array.isArray(history) && history.length > 0 ? history : (state.lastCpuSparkData && state.lastCpuSparkData.length > 0 ? state.lastCpuSparkData : (state._cpuSparkHistory && state._cpuSparkHistory.length > 0 ? state._cpuSparkHistory : []));
  if (!ptsData || ptsData.length === 0) {
    ptsData = [{ load: 0, temp: null, power: null, time: new Date() }];
  }
  if (ptsData.length === 1) {
    ptsData = [ptsData[0], { ...ptsData[0], time: ptsData[0].time || new Date() }];
  }
  if (state) state.lastCpuSparkData = ptsData;
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

  const defs = document.createElementNS(ns, 'defs');
  defs.innerHTML = `
    <linearGradient id="cpuGradLoad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0dcaf0" stop-opacity="0.38"/>
      <stop offset="60%" stop-color="#0dcaf0" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#0dcaf0" stop-opacity="0.0"/>
    </linearGradient>
  `;
  svg.appendChild(defs);

  const count = history.length;
  const isLog = currentCpuSparkScale === 'log';

  const rawTemps = history.map(h => Number(h.temperature_c != null ? h.temperature_c : (h.temp || 0))).filter(t => t > 0);
  const tMin = rawTemps.length ? Math.min(...rawTemps) : 30;
  const tMax = rawTemps.length ? Math.max(...rawTemps) : 90;
  const tDelta = Math.max(6, tMax - tMin);

  const rawPowers = history.map(h => Number(h.power_w != null ? h.power_w : (h.power || 0))).filter(p => p > 0);
  const pMin = rawPowers.length ? Math.min(...rawPowers) : 5;
  const pMax = rawPowers.length ? Math.max(...rawPowers) : 100;
  const pDelta = Math.max(8, pMax - pMin);

  const rawLoads = history.map(h => Number(h.load_percent != null ? h.load_percent : (h.load || 0)));
  const maxLoad = rawLoads.length ? Math.max(...rawLoads) : 0;
  const loadMaxScale = Math.min(100, Math.max(5, maxLoad * 1.15));

  const transformLoad = (v) => {
    const cl = Math.min(100, Math.max(0, Number(v || 0)));
    if (!isLog) return Math.min(1, cl / loadMaxScale);
    return Math.log10(1 + 9 * (cl / 100));
  };

  const transformTemp = (v) => {
    if (v == null) return 0.20;
    const tVal = Number(v);
    const frac = Math.min(1, Math.max(0, (tVal - (tMin - 2)) / (tDelta + 4)));
    return 0.15 + frac * 0.75;
  };

  const transformPower = (v) => {
    if (v == null) return 0.15;
    const pVal = Number(v);
    const frac = Math.min(1, Math.max(0, (pVal - (pMin - 2)) / (pDelta + 4)));
    return 0.10 + frac * 0.70;
  };

  const loadPts = [];
  const tempPts = [];
  const powerPts = [];

  history.forEach((h, i) => {
    const x = (i / (count - 1)) * W;
    const lVal = Number(h.load_percent != null ? h.load_percent : (h.load || 0));
    const tVal = h.temperature_c != null ? Number(h.temperature_c) : (h.temp != null ? Number(h.temp) : null);
    const pVal = h.power_w != null ? Number(h.power_w) : (h.power != null ? Number(h.power) : null);

    const yLoad = H - padBottom - transformLoad(lVal) * innerH;
    const yTemp = H - padBottom - transformTemp(tVal) * innerH;
    const yPower = H - padBottom - transformPower(pVal) * innerH;

    loadPts.push({ x, y: yLoad, raw: lVal, time: h.time_label || h.timestamp });
    tempPts.push({ x, y: yTemp, raw: tVal });
    powerPts.push({ x, y: yPower, raw: pVal });
  });

  const drawSeries = (pts, strokeColor, fillColor, strokeWidth = 1.8) => {
    if (pts.length < 2) return;
    const linePath = buildSmoothSvgPath(pts);
    if (fillColor) {
      const areaPath = `${linePath} L ${pts[pts.length - 1].x.toFixed(1)} ${H - padBottom} L ${pts[0].x.toFixed(1)} ${H - padBottom} Z`;
      const aEl = document.createElementNS(ns, 'path');
      aEl.setAttribute('d', areaPath);
      aEl.setAttribute('fill', fillColor);
      svg.appendChild(aEl);
    }
    const pEl = document.createElementNS(ns, 'path');
    pEl.setAttribute('d', linePath);
    pEl.setAttribute('fill', 'none');
    pEl.setAttribute('stroke', strokeColor);
    pEl.setAttribute('stroke-width', String(strokeWidth));
    pEl.setAttribute('stroke-linejoin', 'round');
    pEl.setAttribute('stroke-linecap', 'round');
    svg.appendChild(pEl);
  };

  drawSeries(powerPts, '#f59e0b', null, 1.2);
  drawSeries(tempPts, '#ef4444', null, 1.3);
  drawSeries(loadPts, '#0dcaf0', 'url(#cpuGradLoad)', 2.0);

  // Hover курсор
  const crosshair = document.createElementNS(ns, 'line');
  crosshair.setAttribute('y1', '0');
  crosshair.setAttribute('y2', String(H));
  crosshair.setAttribute('stroke', 'var(--text-muted, rgba(128,128,128,0.5))');
  crosshair.setAttribute('stroke-dasharray', '2,2');
  crosshair.setAttribute('stroke-width', '1');
  crosshair.style.display = 'none';
  svg.appendChild(crosshair);

  svg.addEventListener('mousemove', (evt) => {
    const rect = svg.getBoundingClientRect();
    const mouseX = Math.max(0, Math.min(rect.width, evt.clientX - rect.left));
    const ratio = mouseX / rect.width;
    const idx = Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));
    const pt = loadPts[idx];
    const hItem = history[idx];

    if (pt && tooltip) {
      crosshair.setAttribute('x1', pt.x.toFixed(1));
      crosshair.setAttribute('x2', pt.x.toFixed(1));
      crosshair.style.display = 'block';

      const tStr = hItem.time_label || (hItem.timestamp ? new Date(hItem.timestamp).toLocaleTimeString() : (hItem.time ? new Date(hItem.time).toLocaleTimeString() : '--:--:--'));
      const lStr = `${pt.raw.toFixed(1)}%`;
      const tempVal = tempPts[idx] && tempPts[idx].raw != null ? `${tempPts[idx].raw.toFixed(0)} °C` : '--';
      const powVal = powerPts[idx] && powerPts[idx].raw != null ? `${powerPts[idx].raw.toFixed(1)} W` : '--';

      tooltip.innerHTML = `
        <div class="d-flex align-items-center justify-content-between gap-2 border-bottom pb-0.5 mb-1" style="border-color: rgba(255,255,255,0.1) !important;">
          <span class="text-muted"><i class="bi bi-clock me-1"></i>${escapeHtml(tStr)}</span>
          <span class="badge ${isLog ? 'bg-info-subtle text-info' : 'bg-secondary text-light'}" style="font-size:0.62rem;">${isLog ? 'Log (0–100%)' : 'Lin (0–' + Math.round(loadMaxScale) + '%)'}</span>
        </div>
        <div class="d-flex gap-2 font-monospace">
          <span class="text-info fw-bold"><i class="bi bi-activity me-0.5"></i>${lStr}</span>
          <span class="text-danger fw-bold"><i class="bi bi-thermometer-half me-0.5"></i>${tempVal}</span>
          <span class="text-warning fw-bold"><i class="bi bi-lightning me-0.5"></i>${powVal}</span>
        </div>
      `;
      tooltip.style.display = 'block';
      const tipX = Math.min(rect.width - 150, Math.max(10, mouseX - 60));
      tooltip.style.left = `${tipX}px`;
    }
  });

  svg.addEventListener('mouseleave', () => {
    crosshair.style.display = 'none';
    if (tooltip) tooltip.style.display = 'none';
  });

  box.appendChild(svg);
}
