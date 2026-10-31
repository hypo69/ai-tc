import { fetchLatestSpeedtest, runInternetSpeedtest } from '../../tab_network/panel_speedtest/panel.js';
/**
 * =============================================================================
 * Process Name: System Inspector - Network Load Panel
 * =============================================================================
 * Description:
 *   Модуль панели аппаратной нагрузки сети (Network Load).
 *   Отображение сетевых интерфейсов, скорости Rx/Tx, загрузки канала (Gbps),
 *   статусов Wi-Fi / Bluetooth и SVG-графика истории трафика.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_system_inspector/panel_network
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 11:05:00
 * =============================================================================
 */

import {
  escapeHtml,
  formatBytes,
  formatBytesPerSec,
  formatSparkTimeLabel,
  createGaugeSvg,
  createPercentSliderHtml,
  buildSmoothSvgPath
} from '../common/ui_utils.js';

let lastNetSparkData = null;
const _netSparkHistory = [];
let currentNetSparkInterval = 'seconds';
let currentNetSparkScale = 'lin';

/**
 * Инициализация панели сети.
 */
export function initNetworkPanel() {
  const selInterval = document.getElementById('sel-net-spark-interval');
  if (selInterval) {
    selInterval.onchange = async () => {
      currentNetSparkInterval = selInterval.value;
      if (currentNetSparkInterval === 'seconds') {
        await fetchNetworkLoadFromApi();
      } else {
        await fetchNetHistoryByInterval(currentNetSparkInterval);
      }
    };
  }

  const btnLog = document.getElementById('btn-net-spark-log');
  const btnLin = document.getElementById('btn-net-spark-lin');
  if (btnLog) btnLog.onclick = () => setNetSparkScale('log');
  if (btnLin) btnLin.onclick = () => setNetSparkScale('lin');

  window.setNetSparkScale = setNetSparkScale;

  // Обработчик кнопки запуска Speedtest в карточке сети
  const btnSpeedtest = document.getElementById('sys-btn-run-speedtest');
  if (btnSpeedtest) {
    btnSpeedtest.onclick = runInternetSpeedtest;
  }

  // Загрузка последних результатов теста скорости
  fetchLatestSpeedtest();

  // Глубокая маршрутизация по хешу URL (#tab-hardware-load-inspector#speedtest)
  handleNetworkHashRouting();
  window.addEventListener('hashchange', handleNetworkHashRouting);
  document.addEventListener('panel:activated', (e) => {
    if (e?.detail?.panelId === 'speedtest' || e?.detail?.panelId === 'panel-network') {
      handleNetworkHashRouting();
    }
  });
}

/**
 * Обработка глубокой маршрутизации по хешу URL для раскрытия и фокусировки Speedtest.
 */
export function handleNetworkHashRouting() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (hash.includes('speedtest') || hash.includes('panel-network')) {
    const card = document.getElementById('sys-card-net');
    if (card && !card.classList.contains('sys-card-drill-expanded')) {
      card.classList.add('sys-card-drill-expanded');
      const drillBtn = card.querySelector('.sys-drill-btn') || document.getElementById('sys-drill-btn-net');
      if (drillBtn) drillBtn.classList.add('active');
    }
    if (hash.includes('speedtest')) {
      const speedSection = document.getElementById('sys-net-speedtest');
      if (speedSection) {
        setTimeout(() => {
          speedSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 150);
      }
    }
  }
}

/**
 * Установка масштаба графика сети.
 * @param {'lin'|'log'} scale - Тип шкалы
 */
export function setNetSparkScale(scale) {
  currentNetSparkScale = scale;
  const btnLog = document.getElementById('btn-net-spark-log');
  const btnLin = document.getElementById('btn-net-spark-lin');
  if (btnLog && btnLin) {
    if (scale === 'log') {
      btnLog.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLin.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    } else {
      btnLin.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLog.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    }
  }
  if (lastNetSparkData && lastNetSparkData.length) {
    renderNetSpark(lastNetSparkData);
  }
}

/**
 * Запрос показателей сетевой нагрузки из REST API.
 */
export async function fetchNetworkLoadFromApi() {
  try {
    const res = await fetch('/api/v1/panel/network-load');
    if (!res.ok) return;
    const data = await res.json();
    updateNetworkUi(data);
  } catch (e) {
    console.warn('[NetworkPanel] Ошибка получения сетевой нагрузки:', e);
  }
}

/**
 * Запрос архивной истории сетевого трафика.
 * @param {string} interval - Интервал выборки
 */
export async function fetchNetHistoryByInterval(interval) {
  try {
    const res = await fetch(`/api/v1/telemetry/history?interval=${encodeURIComponent(interval)}&metric=network&limit=120`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && Array.isArray(data.history) && data.history.length > 0) {
      const rows = data.history.map(r => ({
        timestamp: r.timestamp,
        time_label: formatSparkTimeLabel(r.timestamp || r.created_at, interval),
        download_bytes_sec: Number(r.net_recv_bytes_sec || 0),
        upload_bytes_sec: Number(r.net_sent_bytes_sec || 0)
      }));
      lastNetSparkData = rows;
      renderNetSpark(rows);
    }
  } catch (e) {
    console.warn('[NetworkPanel] Ошибка получения истории сети по интервалу:', e);
  }
}

/**
 * Обновление метрик сети из живого снимка WebSocket телеметрии.
 * @param {Object} netData - Срез telemetry.network из SystemSnapshot
 */
export function updateNetworkTelemetry(netData) {
  if (!netData) return;
  const rxBps = Number(netData.download_bytes_sec || 0);
  const txBps = Number(netData.upload_bytes_sec || 0);
  const utilPct = Number(netData.utilization_percent || 0);

  const set = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };
  set('sys-net-kpi-rx', formatBytesPerSec(rxBps));
  set('sys-net-kpi-tx', formatBytesPerSec(txBps));
  set('sys-net-kpi-util', `${utilPct.toFixed(1)}%`);
  set('sys-net-speed-val', formatBytesPerSec(rxBps + txBps));

  const netGauge = document.getElementById('sys-metric-net-gauge');
  if (netGauge) netGauge.innerHTML = createGaugeSvg(utilPct, 130, 74);
}

/**
 * Отрисовка данных сети в DOM.
 */
function updateNetworkUi(data) {
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };

  const rxBps = Number(data.download_bytes_sec || 0);
  const txBps = Number(data.upload_bytes_sec || 0);
  const totalBps = rxBps + txBps;
  const utilPct = Number(data.utilization_percent || 0);

  const rxFormatted = formatBytesPerSec(rxBps);
  const txFormatted = formatBytesPerSec(txBps);
  const totalFormatted = formatBytesPerSec(totalBps);

  const rxTotalFormatted = formatBytes(data.download_total_bytes || 0);
  const txTotalFormatted = formatBytes(data.upload_total_bytes || 0);
  const sumTotalFormatted = formatBytes((data.download_total_bytes || 0) + (data.upload_total_bytes || 0));

  const netModel = document.getElementById('sys-metric-net-model');
  if (netModel) netModel.innerText = data.name || 'Сетевые адаптеры (Ethernet / Wi-Fi / BT)';

  set('sys-net-ts', data.timestamp || 'Live');
  set('sys-net-speed-val', totalFormatted);
  set('sys-net-sub-details', `⬇ ${rxFormatted} · ⬆ ${txFormatted} (Всего: ${sumTotalFormatted})`);
  set('sys-net-util-label', `Загрузка канала: ${utilPct.toFixed(1)}% (Линк: ${data.link_speed_mbps || 1000} Mbps)`);
  set('sys-net-speed-badge', `${data.link_speed_mbps || 1000} Mbps Full Duplex`);

  set('sys-net-kpi-rx', rxFormatted);
  set('sys-net-kpi-tx', txFormatted);
  set('sys-net-kpi-total', sumTotalFormatted);
  set('sys-net-kpi-util', `${utilPct.toFixed(1)}%`);

  const netGauge = document.getElementById('sys-metric-net-gauge');
  if (netGauge) netGauge.innerHTML = createGaugeSvg(utilPct, 130, 74);

  const netSlider = document.getElementById('sys-metric-net-slider');
  if (netSlider) netSlider.innerHTML = createPercentSliderHtml(utilPct, true, `Канал ${utilPct.toFixed(1)}%`);

  // Rx
  set('sys-rx-sub-badge', rxFormatted);
  set('sys-rx-total-text', `${rxTotalFormatted} всего`);
  const maxSpeedScale = 12.5 * 1024 * 1024;
  const rxPct = Math.min(100, (rxBps / maxSpeedScale) * 100);
  const rxSubGauge = document.getElementById('sys-rx-sub-gauge');
  if (rxSubGauge) rxSubGauge.innerHTML = createGaugeSvg(rxPct, 100, 56);
  const rxSubBar = document.getElementById('sys-rx-sub-bar');
  if (rxSubBar) rxSubBar.style.width = `${rxPct.toFixed(1)}%`;

  // Tx
  set('sys-tx-sub-badge', txFormatted);
  set('sys-tx-total-text', `${txTotalFormatted} всего`);
  const txPct = Math.min(100, (txBps / maxSpeedScale) * 100);
  const txSubGauge = document.getElementById('sys-tx-sub-gauge');
  if (txSubGauge) txSubGauge.innerHTML = createGaugeSvg(txPct, 100, 56);
  const txSubBar = document.getElementById('sys-tx-sub-bar');
  if (txSubBar) txSubBar.style.width = `${txPct.toFixed(1)}%`;

  // Wi-Fi
  const wifi = data.wifi || {};
  const wifiSignal = wifi.signal_percent != null ? Number(wifi.signal_percent) : 0;
  set('sys-wifi-sub-badge', wifi.ssid ? `SSID: ${wifi.ssid}` : (wifi.radio_status || 'On'));
  set('sys-wifi-status-text', wifi.ssid ? `${wifi.ssid} (${wifiSignal}%)` : (wifi.state || 'Disconnected'));
  const wifiSubGauge = document.getElementById('sys-wifi-sub-gauge');
  if (wifiSubGauge) wifiSubGauge.innerHTML = createGaugeSvg(wifiSignal, 100, 56);

  // Bluetooth
  const bt = data.bluetooth || {};
  const btDevCount = bt.devices_count || 0;
  set('sys-bt-sub-badge', bt.status || 'Active');
  set('sys-bt-devices-text', btDevCount > 0 ? `${btDevCount} устр.` : 'Активен (0 устр.)');
  const btPct = Math.min(100, btDevCount * 25);
  const btSubGauge = document.getElementById('sys-bt-sub-gauge');
  if (btSubGauge) btSubGauge.innerHTML = createGaugeSvg(btPct > 0 ? btPct : 10, 100, 56);

  // Спарклайн
  if (Array.isArray(data.history) && data.history.length > 0) {
    renderNetSpark(data.history);
  } else {
    _netSparkHistory.push({ download_bytes_sec: rxBps, upload_bytes_sec: txBps, time: new Date() });
    if (_netSparkHistory.length > 60) _netSparkHistory.shift();
    renderNetSpark(_netSparkHistory);
  }
}

/**
 * Отрисовка SVG-спарклайна сетевого трафика.
 */
export function renderNetSpark(history) {
  const box = document.getElementById('sys-net-spark');
  const tooltip = document.getElementById('sys-net-spark-tooltip');
  if (!box) return;

  let ptsData = Array.isArray(history) && history.length > 0 ? history : (lastNetSparkData || _netSparkHistory || []);
  if (!ptsData || ptsData.length === 0) {
    ptsData = [{ download_bytes_sec: 0, upload_bytes_sec: 0, time: new Date() }];
  }
  if (ptsData.length === 1) {
    ptsData = [ptsData[0], { ...ptsData[0], time: ptsData[0].time || new Date() }];
  }
  lastNetSparkData = ptsData;
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
  const isLog = currentNetSparkScale === 'log';

  const rawRx = history.map(h => Number(h.download_bytes_sec || 0));
  const rawTx = history.map(h => Number(h.upload_bytes_sec || 0));
  const maxBytes = Math.max(1024 * 1024, ...rawRx, ...rawTx);
  const netMaxScale = maxBytes * 1.15;

  const rxPts = [];
  const txPts = [];

  history.forEach((h, i) => {
    const x = (i / (count - 1)) * W;
    const rVal = Number(h.download_bytes_sec || 0);
    const tVal = Number(h.upload_bytes_sec || 0);

    const yRx = H - padBottom - (isLog ? Math.log10(1 + 9 * (rVal / netMaxScale)) : Math.min(1, rVal / netMaxScale)) * innerH;
    const yTx = H - padBottom - (isLog ? Math.log10(1 + 9 * (tVal / netMaxScale)) : Math.min(1, tVal / netMaxScale)) * innerH;

    rxPts.push({ x, y: yRx, raw: rVal, time: h.timestamp || h.time });
    txPts.push({ x, y: yTx, raw: tVal });
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

  drawSeries(txPts, '#f59e0b', 1.4);
  drawSeries(rxPts, '#0dcaf0', 2.0);

  box.appendChild(svg);
}
