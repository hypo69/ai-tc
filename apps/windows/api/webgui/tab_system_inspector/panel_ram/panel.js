/**
 * =============================================================================
 * Process Name: System Inspector - RAM & Memory IO Panel
 * =============================================================================
 * Description:
 *   Модуль панели оперативной памяти (RAM) и файла подкачки (Swap).
 *   Отображение занятой/свободной памяти, дискового ввода-вывода (IO),
 *   Gauge-индикаторов и SVG-спарклайна с историей потребления.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_system_inspector/panel_ram
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 16:10:00
 * =============================================================================
 */

import {
  escapeHtml,
  formatBytesPerSec,
  formatSparkTimeLabel,
  createGaugeSvg,
  createPercentSliderHtml,
  buildSmoothSvgPath
} from '../common/ui_utils.js';

let lastMemIoSparkData = null;
const _memIoSparkHistory = [];
let currentRamSparkInterval = 'seconds';
let currentRamSparkScale = 'lin';

/**
 * Инициализация панели оперативной памяти и обработчиков событий.
 */
export function initRamPanel() {
  const selInterval = document.getElementById('sel-ram-spark-interval');
  if (selInterval) {
    selInterval.onchange = async () => {
      currentRamSparkInterval = selInterval.value;
      if (currentRamSparkInterval === 'seconds') {
        await fetchMemoryIoFromApi();
      } else {
        await fetchRamHistoryByInterval(currentRamSparkInterval);
      }
    };
  }

  const btnLog = document.getElementById('btn-ram-spark-log');
  const btnLin = document.getElementById('btn-ram-spark-lin');
  if (btnLog) btnLog.onclick = () => setRamSparkScale('log');
  if (btnLin) btnLin.onclick = () => setRamSparkScale('lin');

  window.setRamSparkScale = setRamSparkScale;
}

/**
 * Переключение масштаба спарклайна памяти (линейный / логарифмический).
 * @param {'lin'|'log'} scale - Тип шкалы
 */
export function setRamSparkScale(scale) {
  currentRamSparkScale = scale;
  const btnLog = document.getElementById('btn-ram-spark-log');
  const btnLin = document.getElementById('btn-ram-spark-lin');
  if (btnLog && btnLin) {
    if (scale === 'log') {
      btnLog.className = 'btn btn-xs btn-outline-success active py-0 px-2 fw-bold';
      btnLin.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    } else {
      btnLin.className = 'btn btn-xs btn-outline-success active py-0 px-2 fw-bold';
      btnLog.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    }
  }
  if (lastMemIoSparkData && lastMemIoSparkData.length) {
    renderMemIoSpark(lastMemIoSparkData);
  }
}

/**
 * Получение текущих метрик памяти и дискового IO из REST API.
 */
export async function fetchMemoryIoFromApi() {
  try {
    const res = await fetch('/api/v1/panel/memory-io?limit=60');
    if (!res.ok) return;
    const data = await res.json();
    updateRamUi(data);
  } catch (e) {
    console.warn('[RamPanel] Ошибка получения памяти/IO из API:', e);
  }
}

/**
 * Запрос архивной истории RAM по выбранному интервалу.
 * @param {string} interval - Интервал выборки
 */
export async function fetchRamHistoryByInterval(interval) {
  try {
    const res = await fetch(`/api/v1/telemetry/history?interval=${encodeURIComponent(interval)}&metric=ram&limit=120`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && Array.isArray(data.history) && data.history.length > 0) {
      const rows = data.history.map(r => ({
        timestamp: r.timestamp,
        time_label: formatSparkTimeLabel(r.timestamp || r.created_at, interval),
        memory_percent: Number(r.memory_percent || 0),
        read_bytes_sec: Number(r.disk_read_bytes_sec || 0),
        write_bytes_sec: Number(r.disk_write_bytes_sec || 0)
      }));
      lastMemIoSparkData = rows;
      renderMemIoSpark(rows);
    }
  } catch (e) {
    console.warn('[RamPanel] Ошибка получения истории RAM по интервалу:', e);
  }
}

/**
 * Обновление метрик RAM из живого снимка WebSocket телеметрии.
 * @param {Object} memoryData - Срез telemtry.memory из SystemSnapshot
 */
export function updateRamTelemetry(memoryData) {
  if (!memoryData) return;
  const ramVal = document.getElementById('sys-metric-ram-val');
  const ramFill = document.getElementById('sys-metric-ram-fill');
  const ramSub = document.getElementById('sys-metric-ram-sub');
  const ramModel = document.getElementById('sys-metric-ram-model');

  const usedGb = Number(memoryData.used_gb || 0);
  const totalGb = Number(memoryData.total_gb || 0);
  const pct = Number(memoryData.percent || 0);
  const swapPct = Number(memoryData.swap_percent || 0);

  if (ramModel && totalGb > 0) ramModel.innerText = `${Math.round(totalGb)} GB RAM`;
  if (ramVal) ramVal.innerText = `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB`;
  if (ramFill) ramFill.style.width = `${pct}%`;
  if (ramSub) ramSub.innerText = `${pct}% занято (${Number(memoryData.available_gb || 0).toFixed(1)} GB свободно)`;

  const memioPct = document.getElementById('sys-memio-pct');
  if (memioPct) memioPct.innerText = `${pct.toFixed(1)}%`;
  const memioUsed = document.getElementById('sys-memio-used');
  if (memioUsed) memioUsed.innerText = `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB (свободно ${Number(memoryData.available_gb || (totalGb - usedGb)).toFixed(1)} GB)`;
  const memioSwap = document.getElementById('sys-memio-swap');
  if (memioSwap) memioSwap.innerText = `Файл подкачки: ${swapPct.toFixed(1)}%`;

  const freeGb = Number(memoryData.available_gb || (totalGb - usedGb));
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };
  set('sys-ram-kpi-used', `${usedGb.toFixed(1)} GB`);
  set('sys-ram-kpi-free', `${freeGb.toFixed(1)} GB`);
  set('sys-ram-kpi-swap', `${swapPct.toFixed(1)}%`);

  const ramGauge = document.getElementById('sys-metric-ram-gauge');
  if (ramGauge) ramGauge.innerHTML = createGaugeSvg(pct, 130, 74);
  const ramSlider = document.getElementById('sys-metric-ram-slider');
  if (ramSlider) ramSlider.innerHTML = createPercentSliderHtml(pct, true, `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB`);
  const ramSubGauge = document.getElementById('sys-ram-sub-gauge');
  if (ramSubGauge) ramSubGauge.innerHTML = createGaugeSvg(pct, 100, 56);
}

/**
 * Отрисовка данных памяти в элементах DOM.
 * @param {Object} data - Ответ /api/v1/panel/memory-io
 */
function updateRamUi(data) {
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };
  const m = data.memory || {};
  const io = data.disk_io || {};
  const pct = Number(m.percent || 0);
  const swapPct = Number(m.swap_percent || 0);
  const usedGb = Number(m.used_gb || 0);
  const totalGb = Number(m.total_gb || 0);
  const freeGb = Number(m.free_gb || 0);

  const ramModel = document.getElementById('sys-metric-ram-model');
  if (ramModel) {
    ramModel.innerText = data.name || (m.name || (m.total_gb ? `${Math.round(m.total_gb)} GB RAM` : 'RAM'));
  }
  set('sys-memio-pct', `${pct.toFixed(1)}%`);
  set('sys-memio-used', `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB (свободно ${freeGb.toFixed(1)} GB)`);
  set('sys-memio-swap', `Файл подкачки: ${swapPct.toFixed(1)}%`);
  set('sys-memio-ts', data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '--');

  set('sys-ram-kpi-used', `${usedGb.toFixed(1)} GB`);
  set('sys-ram-kpi-free', `${freeGb.toFixed(1)} GB`);
  set('sys-ram-kpi-swap', `${swapPct.toFixed(1)}%`);
  set('sys-ram-kpi-io', formatBytesPerSec((Number(io.read_bytes_sec || 0)) + (Number(io.write_bytes_sec || 0))));

  const ramGauge = document.getElementById('sys-metric-ram-gauge');
  if (ramGauge) ramGauge.innerHTML = createGaugeSvg(pct, 130, 74);

  const ramSlider = document.getElementById('sys-metric-ram-slider');
  if (ramSlider) ramSlider.innerHTML = createPercentSliderHtml(pct, true, `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB`);

  // Блок 1: Физическая RAM
  set('sys-ram-sub-badge', `${pct.toFixed(0)}%`);
  const ramSubGauge = document.getElementById('sys-ram-sub-gauge');
  if (ramSubGauge) ramSubGauge.innerHTML = createGaugeSvg(pct, 100, 56);
  const ramSubSlider = document.getElementById('sys-ram-sub-slider');
  if (ramSubSlider) ramSubSlider.innerHTML = createPercentSliderHtml(pct, false, `${usedGb.toFixed(1)} / ${totalGb.toFixed(1)} GB`);

  // Блок 2: Файл подкачки (Swap)
  set('sys-swap-sub-badge', `${swapPct.toFixed(1)}%`);
  const swapSubGauge = document.getElementById('sys-swap-sub-gauge');
  if (swapSubGauge) swapSubGauge.innerHTML = createGaugeSvg(swapPct, 100, 56);
  const swapSubSlider = document.getElementById('sys-swap-sub-slider');
  if (swapSubSlider) swapSubSlider.innerHTML = createPercentSliderHtml(swapPct, false, `Подкачка ${swapPct.toFixed(1)}%`);

  // Блок 3 & 4: Чтение и запись на диск (IO)
  const rBps = Number(io.read_bytes_sec || 0);
  const wBps = Number(io.write_bytes_sec || 0);
  const readFormatted = formatBytesPerSec(rBps);
  const writeFormatted = formatBytesPerSec(wBps);

  set('sys-memio-read', readFormatted);
  set('sys-read-sub-badge', readFormatted);
  set('sys-memio-write', writeFormatted);
  set('sys-write-sub-badge', writeFormatted);

  const maxIoScale = 50 * 1024 * 1024; // 50 MB/s
  const readPct = Math.min(100, (rBps / maxIoScale) * 100);
  const writePct = Math.min(100, (wBps / maxIoScale) * 100);

  const readSubGauge = document.getElementById('sys-read-sub-gauge');
  if (readSubGauge) readSubGauge.innerHTML = createGaugeSvg(readPct, 100, 56);
  const readSubBar = document.getElementById('sys-read-sub-bar');
  const readSubThumb = document.getElementById('sys-read-sub-thumb');
  if (readSubBar) readSubBar.style.width = `${readPct.toFixed(1)}%`;
  if (readSubThumb) readSubThumb.style.left = `${readPct.toFixed(1)}%`;

  const writeSubGauge = document.getElementById('sys-write-sub-gauge');
  if (writeSubGauge) writeSubGauge.innerHTML = createGaugeSvg(writePct, 100, 56);
  const writeSubBar = document.getElementById('sys-write-sub-bar');
  const writeSubThumb = document.getElementById('sys-write-sub-thumb');
  if (writeSubBar) writeSubBar.style.width = `${writePct.toFixed(1)}%`;
  if (writeSubThumb) writeSubThumb.style.left = `${writePct.toFixed(1)}%`;

  // Спарклайн RAM
  if (Array.isArray(data.history) && data.history.length > 0) {
    renderMemIoSpark(data.history);
  } else {
    _memIoSparkHistory.push({ memory_percent: pct, read_bytes_sec: rBps, write_bytes_sec: wBps, time: new Date() });
    if (_memIoSparkHistory.length > 60) _memIoSparkHistory.shift();
    renderMemIoSpark(_memIoSparkHistory);
  }
}

/**
 * Отрисовка SVG-спарклайна памяти и дисковых операций.
 * @param {Array} history - Точки истории
 */
export function renderMemIoSpark(history) {
  const box = document.getElementById('sys-memio-spark');
  const tooltip = document.getElementById('sys-memio-spark-tooltip');
  if (!box) return;

  let ptsData = Array.isArray(history) && history.length > 0 ? history : (lastMemIoSparkData && lastMemIoSparkData.length > 0 ? lastMemIoSparkData : (_memIoSparkHistory && _memIoSparkHistory.length > 0 ? _memIoSparkHistory : []));
  if (!ptsData || ptsData.length === 0) {
    ptsData = [{ pct: 0, used: 0, swap: 0, time: new Date() }];
  }
  if (ptsData.length === 1) {
    ptsData = [ptsData[0], { ...ptsData[0], time: ptsData[0].time || new Date() }];
  }
  lastMemIoSparkData = ptsData;
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
    <linearGradient id="ramGradLoad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.38"/>
      <stop offset="60%" stop-color="#10b981" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
    </linearGradient>
  `;
  svg.appendChild(defs);

  const count = history.length;
  const isLog = currentRamSparkScale === 'log';

  const rawRams = history.map(h => Number(h.memory_percent != null ? h.memory_percent : (h.ram || 0)));
  const maxRam = rawRams.length ? Math.max(...rawRams) : 0;
  const ramMaxScale = Math.min(100, Math.max(10, maxRam * 1.15));

  const rawReads = history.map(h => Number(h.read_bytes_sec != null ? h.read_bytes_sec : (h.disk_read || 0)));
  const rawWrites = history.map(h => Number(h.write_bytes_sec != null ? h.write_bytes_sec : (h.disk_write || 0)));
  const maxIoBytes = Math.max(1024 * 1024, ...rawReads, ...rawWrites);
  const ioMaxScale = maxIoBytes * 1.15;

  const transformRam = (v) => {
    const cl = Math.min(100, Math.max(0, Number(v || 0)));
    if (!isLog) return Math.min(1, cl / ramMaxScale);
    return Math.log10(1 + 9 * (cl / 100));
  };

  const transformIo = (v) => {
    if (!v || v <= 0) return 0;
    const nv = Number(v);
    if (!isLog) return Math.min(1, nv / ioMaxScale);
    return Math.log10(1 + 9 * (Math.min(ioMaxScale, nv) / ioMaxScale));
  };

  const ramPts = [];
  const readPts = [];
  const writePts = [];

  history.forEach((h, i) => {
    const x = (i / (count - 1)) * W;
    const rVal = Number(h.memory_percent != null ? h.memory_percent : (h.ram || 0));
    const rdVal = Number(h.read_bytes_sec != null ? h.read_bytes_sec : (h.disk_read || 0));
    const wrVal = Number(h.write_bytes_sec != null ? h.write_bytes_sec : (h.disk_write || 0));

    const yRam = H - padBottom - transformRam(rVal) * innerH;
    const yRead = H - padBottom - (0.04 + transformIo(rdVal) * 0.44) * innerH;
    const yWrite = H - padBottom - (0.04 + transformIo(wrVal) * 0.44) * innerH;

    ramPts.push({ x, y: yRam, raw: rVal, time: h.timestamp || h.time });
    readPts.push({ x, y: yRead, raw: rdVal });
    writePts.push({ x, y: yWrite, raw: wrVal });
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

  drawSeries(writePts, '#f59e0b', null, 1.3);
  drawSeries(readPts, '#0dcaf0', null, 1.3);
  drawSeries(ramPts, '#10b981', 'url(#ramGradLoad)', 2.0);

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
    const curIndex = Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));
    const pt = ramPts[curIndex];
    const hItem = history[curIndex];

    if (pt && tooltip) {
      crosshair.setAttribute('x1', pt.x.toFixed(1));
      crosshair.setAttribute('x2', pt.x.toFixed(1));
      crosshair.style.display = 'block';

      const tStr = hItem.timestamp ? new Date(hItem.timestamp).toLocaleTimeString() : (hItem.time ? new Date(hItem.time).toLocaleTimeString() : '--:--:--');
      const rStr = `${pt.raw.toFixed(1)}%`;
      const rdStr = readPts[curIndex] ? formatBytesPerSec(readPts[curIndex].raw) : '0 B/s';
      const wrStr = writePts[curIndex] ? formatBytesPerSec(writePts[curIndex].raw) : '0 B/s';

      tooltip.innerHTML = `
        <div class="d-flex align-items-center justify-content-between gap-2 border-bottom pb-0.5 mb-1" style="border-color: rgba(255,255,255,0.1) !important;">
          <span class="text-muted"><i class="bi bi-clock me-1"></i>${escapeHtml(tStr)}</span>
          <span class="badge ${isLog ? 'bg-success-subtle text-success' : 'bg-secondary text-light'}" style="font-size:0.62rem;">${isLog ? 'Log (0–100%)' : 'Lin (0–' + Math.round(ramMaxScale) + '%)'}</span>
        </div>
        <div class="d-flex gap-2 font-monospace">
          <span class="text-success fw-bold"><i class="bi bi-memory me-0.5"></i>RAM: ${rStr}</span>
          <span class="text-info fw-bold"><i class="bi bi-arrow-down me-0.5"></i>R: ${rdStr}</span>
          <span class="text-warning fw-bold"><i class="bi bi-arrow-up me-0.5"></i>W: ${wrStr}</span>
        </div>
      `;
      tooltip.style.display = 'block';
      const tipX = Math.min(rect.width - 160, Math.max(10, mouseX - 60));
      tooltip.style.left = `${tipX}px`;
    }
  });

  svg.addEventListener('mouseleave', () => {
    crosshair.style.display = 'none';
    if (tooltip) tooltip.style.display = 'none';
  });

  box.appendChild(svg);
}
