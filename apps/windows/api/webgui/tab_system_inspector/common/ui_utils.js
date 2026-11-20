/**
 * =============================================================================
 * Process Name: System Inspector - Common UI Utilities
 * =============================================================================
 * Description:
 *   Общие вспомогательные функции визуализации (Gauge, Slider, форматирование времени,
 *   безопасное экранирование HTML, селекторы интервалов) для панелей вкладки tab_system_inspector.
 *
 * File: ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Экранирование спецсимволов HTML для безопасной вставки в DOM.
 * @param {string} str - Исходная строка
 * @returns {string} Экранированная строка
 */
export function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Форматирование байтов в читаемый вид (B, KB, MB, GB, TB).
 * @param {number|string} v - Байты
 * @returns {string} Форматированная строка
 */
export function formatBytes(v) {
  const n = Number(v) || 0;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let x = n;
  while (x >= 1024 && i < units.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/**
 * Форматирование скорости передачи (B/s, KB/s, MB/s, GB/s).
 * @param {number|string} v - Байты в секунду
 * @returns {string} Скорость передачи
 */
export function formatBytesPerSec(v) {
  const n = Number(v) || 0;
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  let i = 0;
  let x = n;
  while (x >= 1024 && i < units.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/**
 * Форматирование временной метки для подписей графиков в зависимости от шага выборки.
 * @param {number|string|Date} ts - Временная метка
 * @param {string} interval - Интервал ('seconds', 'minutes', 'hours', 'days', 'weeks', 'all')
 * @returns {string} Читаемая метка времени
 */
export function formatSparkTimeLabel(ts, interval = 'seconds') {
  if (!ts) return '--:--:--';
  let d = null;
  if (typeof ts === 'number') {
    d = new Date(ts > 1e11 ? ts : ts * 1000);
  } else {
    d = new Date(ts);
  }
  if (isNaN(d.getTime())) return String(ts);

  const pad = (n) => String(n).padStart(2, '0');
  const hh = pad(d.getHours());
  const mm = pad(d.getMinutes());
  const ss = pad(d.getSeconds());
  const DD = pad(d.getDate());
  const MM = pad(d.getMonth() + 1);
  const YY = String(d.getFullYear()).slice(-2);

  if (interval === 'seconds' || interval === 'minutes') {
    return `${hh}:${mm}:${ss}`;
  }
  if (interval === 'hours') {
    return `${hh}:${mm}`;
  }
  if (interval === 'days' || interval === 'weeks') {
    return `${DD}.${MM} ${hh}:${mm}`;
  }
  return `${DD}.${MM}.${YY} ${hh}:${mm}`;
}

/**
 * Построение сглаженной кубической кривой Безье (SVG path) по массиву точек {x, y}.
 * @param {Array<{x: number, y: number}>} pts - Массив координат точек
 * @returns {string} Атрибут d для SVG path
 */
export function buildSmoothSvgPath(pts) {
  if (!pts || pts.length === 0) return '';
  if (pts.length === 1) return `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  let d = `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = i > 0 ? pts[i - 1] : pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = i !== pts.length - 2 ? pts[i + 2] : p2;

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

/**
 * Генерация полукругового SVG-спидометра (Gauge) со стрелкой.
 * @param {number|null} percent - Значение в процентах (0-100)
 * @param {number} width - Ширина SVG (px)
 * @param {number} height - Высота SVG (px)
 * @returns {string} HTML разметка SVG
 */
export function createGaugeSvg(percent, width = 100, height = 56) {
  const val = percent == null ? 0 : Math.min(100, Math.max(0, Number(percent)));
  const angle = -90 + (val / 100) * 180;
  const needleColor = val > 80 ? '#ef4444' : val > 50 ? '#f59e0b' : '#38bdf8';

  return `
    <svg width="${width}" height="${height}" viewBox="0 0 100 56" preserveAspectRatio="xMidYMid meet" style="display:block;margin:0 auto;overflow:visible;">
      <defs>
        <linearGradient id="sysGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#10b981"/>
          <stop offset="50%" stop-color="#f59e0b"/>
          <stop offset="100%" stop-color="#ef4444"/>
        </linearGradient>
      </defs>
      <path d="M 12 50 A 38 38 0 0 1 88 50" fill="none" stroke="var(--border-color, rgba(128,128,128,0.25))" stroke-width="9" stroke-linecap="round"/>
      <path d="M 12 50 A 38 38 0 0 1 88 50" fill="none" stroke="url(#sysGaugeGrad)" stroke-width="9" stroke-linecap="round" opacity="0.9"/>
      <g transform="rotate(${angle.toFixed(1)}, 50, 50)" style="transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);">
        <polygon points="48,50 50,14 52,50" fill="${needleColor}" filter="drop-shadow(0 2px 3px rgba(0,0,0,0.6))"/>
        <line x1="50" y1="50" x2="50" y2="14" stroke="#ffffff" stroke-width="1.2" opacity="0.9"/>
      </g>
      <circle cx="50" cy="50" r="6" fill="#38bdf8"/>
      <circle cx="50" cy="50" r="2.5" fill="var(--surface-1, #0f172a)"/>
    </svg>
  `;
}

/**
 * Генерация цветного термо-слайдера с бегунком.
 * @param {number|null} tempC - Температура в градусах Цельсия
 * @param {number} minTemp - Мин. шкала (по умолчанию 30°C)
 * @param {number} maxTemp - Макс. шкала (по умолчанию 95°C)
 * @param {boolean} isLarge - Флаг увеличенного отображения для шапки
 * @returns {string} HTML разметка
 */
export function createTempSliderHtml(tempC, minTemp = 30, maxTemp = 95, isLarge = false) {
  if (tempC == null) {
    return `<div class="sys-temp-slider-empty">-- °C</div>`;
  }
  const val = Number(tempC);
  const pct = Math.min(100, Math.max(0, ((val - minTemp) / (maxTemp - minTemp)) * 100));

  let barColor = '#10b981';
  let badgeClass = 'text-success';
  if (val >= 80) {
    barColor = '#ef4444';
    badgeClass = 'text-danger fw-bold';
  } else if (val >= 68) {
    barColor = '#f97316';
    badgeClass = 'text-warning fw-bold';
  } else if (val >= 50) {
    barColor = '#eab308';
    badgeClass = 'text-warning';
  }

  const wrapClass = isLarge ? 'sys-temp-slider-wrap sys-temp-slider-lg' : 'sys-temp-slider-wrap';
  const fontSize = isLarge ? 'font-size: 0.85rem;' : 'font-size: 0.78rem;';

  return `
    <div class="${wrapClass}">
      <div class="d-flex justify-content-between align-items-center mb-1" style="${fontSize}">
        <span class="text-muted"><i class="bi bi-thermometer-half me-1"></i>t°</span>
        <span class="font-monospace ${badgeClass}" style="font-weight: 700;">${val.toFixed(0)}°C</span>
      </div>
      <div class="sys-temp-slider-track">
        <div class="sys-temp-slider-bar" style="width: ${pct.toFixed(1)}%; background: ${barColor};"></div>
        <div class="sys-temp-slider-thumb" style="left: ${pct.toFixed(1)}%; background: ${barColor};"></div>
      </div>
    </div>
  `;
}

/**
 * Генерация процентного слайдера загрузки ресурса.
 * @param {number|null} percent - Значение от 0 до 100
 * @param {boolean} isLarge - Флаг крупного отображения
 * @param {string} labelText - Кастомная текстовая подпись
 * @returns {string} HTML разметка
 */
export function createPercentSliderHtml(percent, isLarge = false, labelText = '') {
  const val = percent == null ? 0 : Math.min(100, Math.max(0, Number(percent)));
  let barColor = '#10b981';
  let badgeClass = 'text-success';
  if (val >= 85) {
    barColor = '#ef4444';
    badgeClass = 'text-danger fw-bold';
  } else if (val >= 70) {
    barColor = '#f97316';
    badgeClass = 'text-warning fw-bold';
  } else if (val >= 50) {
    barColor = '#eab308';
    badgeClass = 'text-warning';
  }

  const wrapClass = isLarge ? 'sys-temp-slider-wrap sys-temp-slider-lg' : 'sys-temp-slider-wrap';
  const fontSize = isLarge ? 'font-size: 0.85rem;' : 'font-size: 0.78rem;';
  const displayLabel = labelText || `${val.toFixed(0)}%`;

  return `
    <div class="${wrapClass}">
      <div class="d-flex justify-content-between align-items-center mb-1" style="${fontSize}">
        <span class="text-muted"><i class="bi bi-speedometer2 me-1"></i>Загрузка</span>
        <span class="font-monospace ${badgeClass}" style="font-weight: 700;">${displayLabel}</span>
      </div>
      <div class="sys-temp-slider-track">
        <div class="sys-temp-slider-bar" style="width: ${val.toFixed(1)}%; background: ${barColor};"></div>
        <div class="sys-temp-slider-thumb" style="left: ${val.toFixed(1)}%; background: ${barColor};"></div>
      </div>
    </div>
  `;
}

/**
 * Загрузка доступных диапазонов агрегации телеметрии.
 * @returns {Promise<Object>} Данные интервалов
 */
export async function fetchAvailableTimeRanges() {
  try {
    const res = await fetch('/api/v1/telemetry/time-ranges');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    populateIntervalSelectors(data.intervals || []);
    return data;
  } catch (e) {
    console.warn('[SystemInspector] Ошибка загрузки диапазонов времени:', e);
    const fallback = [
      { id: 'seconds', label: 'Секунды', is_available: true },
      { id: 'all', label: 'Все', is_available: true }
    ];
    populateIntervalSelectors(fallback);
    return { intervals: fallback };
  }
}

/**
 * Заполнение выпадающих списков выбора интервала времени в графиках.
 * @param {Array<{id: string, label: string}>} intervals - Список интервалов
 */
export function populateIntervalSelectors(intervals) {
  if (!Array.isArray(intervals) || intervals.length === 0) return;

  const selectIds = [
    'sel-cpu-spark-interval',
    'sel-ram-spark-interval',
    'sel-net-spark-interval',
    'sel-storage-spark-interval'
  ];

  document.querySelectorAll('.sys-spark-interval-select').forEach(el => {
    if (el.id && !selectIds.includes(el.id)) selectIds.push(el.id);
  });

  selectIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const currentVal = el.value || 'seconds';
    el.innerHTML = intervals.map(item => `
      <option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>
    `).join('');
    if (intervals.some(i => i.id === currentVal)) {
      el.value = currentVal;
    } else {
      el.value = intervals[0].id;
    }
  });
}
