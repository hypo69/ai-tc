/**
 * =============================================================================
 * Process Name: System Inspector - Storage Panel
 * =============================================================================
 * Description:
 *   Модуль панели накопителей и дисковых массивов (Storage Panel).
 *   Отображение физических дисков NVMe/SSD/HDD, SMART-статусов,
 *   интенсивности IOPS, температуры, наработки и интеграции с AIModalDialog.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_system_inspector/panel_storage
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-13 13:40:00
 * =============================================================================
 */

import {
  escapeHtml,
  formatSparkTimeLabel,
  createGaugeSvg,
  createTempSliderHtml,
  buildSmoothSvgPath
} from '../common/ui_utils.js';

let lastStorageSparkData = null;
const _storageSparkHistory = [];
let currentStorageSparkInterval = 'seconds';
let currentStorageSparkScale = 'lin';

/**
 * Инициализация панели накопителей.
 */
export function initStoragePanel() {
  const selInterval = document.getElementById('sel-storage-spark-interval');
  if (selInterval) {
    selInterval.onchange = async () => {
      currentStorageSparkInterval = selInterval.value;
      if (currentStorageSparkInterval === 'seconds') {
        await fetchStorageLoadFromApi();
      } else {
        await fetchStorageHistoryByInterval(currentStorageSparkInterval);
      }
    };
  }

  const btnLog = document.getElementById('btn-storage-spark-log');
  const btnLin = document.getElementById('btn-storage-spark-lin');
  if (btnLog) btnLog.onclick = () => setStorageSparkScale('log');
  if (btnLin) btnLin.onclick = () => setStorageSparkScale('lin');

  window.setStorageSparkScale = setStorageSparkScale;
  window.inspectStorageSpecsWithAi = () => {
    if (window.AITableModal) {
      const storageModel = document.getElementById('sys-metric-storage-model')?.innerText || 'Storage';
      const pct = document.getElementById('sys-storage-pct')?.innerText || '0%';
      const used = document.getElementById('sys-storage-used')?.innerText || '';
      window.AITableModal.show({
        icon: '💾',
        title: storageModel,
        subtitle: 'Дисковая подсистема, накопители и тома Windows',
        panelId: 'storage',
        tableType: 'hardware',
        badges: [
          { text: 'Storage', class: 'badge bg-info' },
          { text: pct, class: 'badge bg-primary' }
        ],
        metadata: [
          { label: 'Подсистема', value: storageModel },
          { label: 'Загрузка', value: pct },
          { label: 'Использование', value: used }
        ],
        rawTitle: 'JSON Телеметрии Дисков',
        rawContent: JSON.stringify(lastStorageSparkData || {}, null, 2),
        requestData: lastStorageSparkData || {}
      });
    }
  };
}

/**
 * Переключение масштаба спарклайна дисков.
 * @param {'lin'|'log'} scale - Тип шкалы
 */
export function setStorageSparkScale(scale) {
  currentStorageSparkScale = scale;
  const btnLog = document.getElementById('btn-storage-spark-log');
  const btnLin = document.getElementById('btn-storage-spark-lin');
  if (btnLog && btnLin) {
    if (scale === 'log') {
      btnLog.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLin.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    } else {
      btnLin.className = 'btn btn-xs btn-outline-info active py-0 px-2 fw-bold';
      btnLog.className = 'btn btn-xs btn-outline-secondary py-0 px-2';
    }
  }
  if (lastStorageSparkData && lastStorageSparkData.length) {
    renderStorageSpark(lastStorageSparkData);
  }
}

/**
 * Получение текущей нагрузки накопителей из API.
 */
export async function fetchStorageLoadFromApi() {
  try {
    const res = await fetch('/api/v1/panel/storage-load?t=' + Date.now());
    if (!res.ok) return;
    const data = await res.json();
    renderStorageCards(data);
    if (data.physical_disks && data.physical_disks.length > 0) {
      renderPhysicalDisksStorage(data.physical_disks);
    }
  } catch (e) {
    console.warn('[StoragePanel] Ошибка получения загрузки накопителей:', e);
  }
}

/**
 * Запрос архивной истории накопителей.
 * @param {string} interval - Интервал выборки
 */
export async function fetchStorageHistoryByInterval(interval) {
  try {
    const res = await fetch(`/api/v1/telemetry/history?interval=${encodeURIComponent(interval)}&metric=storage&limit=120`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && Array.isArray(data.history) && data.history.length > 0) {
      const rows = data.history.map(r => ({
        timestamp: r.timestamp,
        time_label: formatSparkTimeLabel(r.timestamp || r.created_at, interval),
        read_bytes_sec: Number(r.disk_read_bytes_sec || 0),
        write_bytes_sec: Number(r.disk_write_bytes_sec || 0)
      }));
      lastStorageSparkData = rows;
      renderStorageSpark(rows);
    }
  } catch (e) {
    console.warn('[StoragePanel] Ошибка истории накопителей по интервалу:', e);
  }
}

function formatDriveOps(cnt) {
  if (cnt == null) return '--';
  const n = Number(cnt);
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

function formatDriveHours(hours) {
  if (hours == null) return '--';
  const h = Number(hours);
  if (h >= 8760) {
    const years = (h / 8760).toFixed(1);
    return `${h.toLocaleString()} ч (~${years} г.)`;
  }
  return `${h.toLocaleString()} ч`;
}

/**
 * Открытие модального окна AI-анализа диска.
 * @param {Object} d - Данные диска
 */
export function openDriveAiModal(d) {
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) {
    console.warn('[StoragePanel] AIModalDialog не найден');
    return;
  }

  const pct = d.used_percent != null ? Number(d.used_percent).toFixed(1) : '--';
  const totGb = d.total_gb != null ? Number(d.total_gb).toFixed(1) : '--';
  const usedGb = d.used_gb != null ? Number(d.used_gb).toFixed(1) : '--';
  const freeGb = d.free_gb != null ? Number(d.free_gb).toFixed(1) : '--';
  const temp = d.temperature_c != null ? `${Number(d.temperature_c).toFixed(0)} °C` : 'N/A';

  modal.show({
    title: d.name,
    subtitle: `${d.id} | ${d.media_type} | ${totGb} GB`,
    icon: '💾',
    panelId: 'storage',
    tableType: 'disk',
    badges: [
      { text: d.media_type, class: d.media_type === 'NVMe' ? 'badge bg-primary' : d.media_type === 'SSD' ? 'badge bg-info text-dark' : 'badge bg-warning text-dark' },
      { text: d.health_status || 'SMART OK', class: 'badge bg-success' },
      { text: temp, class: 'badge bg-dark border text-light' }
    ],
    metadata: [
      { label: 'Модель накопителя', value: d.name },
      { label: 'Идентификатор устройства', value: d.id, isCode: true },
      { label: 'Тип носителя / Интерфейс', value: `${d.media_type} (${d.interface_type || 'SATA/NVMe'})` },
      { label: 'Общий объем', value: `${totGb} GB` },
      { label: 'Занятый объем', value: `${usedGb} GB (${pct}%)` },
      { label: 'Свободное пространство', value: `${freeGb} GB` },
      { label: 'Температура', value: temp },
      { label: 'Интенсивность обращений', value: d.activity_percent != null ? `${d.activity_percent}%` : 'N/A' },
      { label: 'Скорость чтения / записи', value: `Чтение: ${d.read_rate_raw || '0 B/s'}, Запись: ${d.write_rate_raw || '0 B/s'}` },
      { label: 'Всего записано (TBW)', value: d.data_written_raw || 'N/A' },
      { label: 'Всего прочитано', value: d.data_read_raw || 'N/A' },
      { label: 'Время наработки (Power-On)', value: formatDriveHours(d.power_on_hours) },
      { label: 'Серийный номер', value: d.serial_number || 'N/A', isCode: true }
    ],
    rawTitle: 'Дамп телеметрии физического накопителя',
    rawContent: JSON.stringify(d, null, 2),
    autoRun: false
  });
}

/**
 * Отрисовка карточек накопителей.
 * @param {Object} data - Ответ /api/v1/panel/storage-load
 */
export function renderStorageCards(data) {
  const box = document.getElementById('sys-metric-storage-cards');
  const badgeDrives = document.getElementById('sys-storage-drives-badge');
  const badgeParts = document.getElementById('sys-storage-parts-badge');
  const badgeSummary = document.getElementById('sys-storage-summary-badge');

  const drives = Array.isArray(data.drives) ? data.drives : [];
  const partitions = Array.isArray(data.partitions) ? data.partitions : [];
  const summary = data.summary || {};
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };

  const totGb = Number(summary.total_gb || 0);
  const usedGb = Number(summary.used_gb || 0);
  const freeGb = Number(summary.free_gb || (totGb - usedGb));
  const usedPct = Number(summary.used_percent || (totGb > 0 ? (usedGb / totGb) * 100 : 0));
  const maxTemp = summary.max_temperature_c != null ? Number(summary.max_temperature_c) : null;

  // Обновление верхнего баннера накопителей
  set('sys-storage-kpi-used', `${usedGb.toFixed(1)} GB`);
  set('sys-storage-kpi-free', `${freeGb.toFixed(1)} GB`);
  set('sys-storage-kpi-drives', `${drives.length} / ${partitions.length}`);
  set('sys-storage-kpi-temp', maxTemp != null ? `${maxTemp.toFixed(0)} °C` : '-- °C');
  set('sys-storage-pct', `${usedPct.toFixed(1)}%`);
  set('sys-storage-used', `${usedGb.toFixed(1)} / ${totGb.toFixed(1)} GB`);
  set('sys-storage-temp-label', maxTemp != null ? `${maxTemp.toFixed(0)} °C` : '-- °C');
  set('sys-storage-spec-drives', `${drives.length}`);
  set('sys-storage-spec-parts', `${partitions.length}`);
  set('sys-storage-spec-free', `${freeGb.toFixed(1)} GB`);
  set('sys-storage-spec-used', `${usedGb.toFixed(1)} GB`);

  const storageGauge = document.getElementById('sys-metric-storage-gauge');
  if (storageGauge) storageGauge.innerHTML = createGaugeSvg(usedPct, 120, 68);

  const storageTempSlider = document.getElementById('sys-metric-storage-temp-slider');
  if (storageTempSlider) storageTempSlider.innerHTML = createTempSliderHtml(maxTemp, 25, 75, false);

  if (!box) return;

  if (badgeDrives) badgeDrives.textContent = `${drives.length} дисков`;
  if (badgeParts) badgeParts.textContent = `${partitions.length} разделов`;
  if (badgeSummary) {
    badgeSummary.textContent = `${usedGb.toFixed(1)} / ${totGb.toFixed(1)} GB (${usedPct.toFixed(1)}%)`;
  }

  if (drives.length === 0 && partitions.length === 0) {
    box.innerHTML = `<div class="text-muted small text-center py-3 col-12">Опрос накопителей выполняется...</div>`;
    return;
  }

  const drivesToRender = drives.length > 0 ? drives : partitions.map((p, idx) => ({
    id: p.device || p.mountpoint || `Vol${idx}`,
    name: `Логический том ${p.device || p.mountpoint}`,
    media_type: p.fstype || 'Volume',
    health_status: 'Healthy',
    total_gb: p.total_gb,
    used_gb: p.used_gb,
    free_gb: p.free_gb,
    used_percent: p.used_percent,
    temperature_c: null,
    read_rate_raw: '0 B/s',
    write_rate_raw: '0 B/s',
    power_on_hours: null,
    data_written_raw: '--',
  }));

  if (drivesToRender.length > 0) {
    box.innerHTML = drivesToRender.map((d, idx) => {
      const pct = d.used_percent != null ? Number(d.used_percent) : 0;
      const temp = d.temperature_c != null ? Number(d.temperature_c) : null;
      const totGb = d.total_gb != null ? Number(d.total_gb) : 0;
      const usedGb = d.used_gb != null ? Number(d.used_gb) : 0;
      const freeGb = Math.max(0, totGb - usedGb);

      const tempSliderHtml = temp != null
        ? createTempSliderHtml(temp, 20, 75, false)
        : `
          <div class="sys-temp-slider-wrap">
            <div class="d-flex justify-content-between align-items-center mb-1" style="font-size: 0.78rem;">
              <span class="text-muted"><i class="bi bi-thermometer-half me-1"></i>t° накопителя</span>
              <span class="font-monospace text-muted fw-bold">-- °C</span>
            </div>
            <div class="sys-temp-slider-track">
              <div class="sys-temp-slider-bar" style="width: 0%; background: var(--border-color);"></div>
            </div>
          </div>
        `;

      let mediaBadgeClass = 'bg-warning-subtle text-warning border-warning';
      let iconHtml = '<i class="bi bi-hdd-fill text-warning fs-5"></i>';
      if (d.media_type === 'NVMe') {
        mediaBadgeClass = 'bg-primary-subtle text-primary border-primary';
        iconHtml = '<i class="bi bi-lightning-charge-fill text-info fs-5"></i>';
      } else if (d.media_type === 'SSD') {
        mediaBadgeClass = 'bg-info-subtle text-info border-info';
        iconHtml = '<i class="bi bi-device-ssd-fill text-primary fs-5"></i>';
      }

      return `
        <div class="sys-panel p-3 mb-2 rounded-3 w-100 border sys-drive-full-card interactive-table-row" data-drive-idx="${idx}" style="background: var(--surface-1); border-color: var(--border-color) !important; cursor: pointer;">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 pb-2 mb-2 border-bottom" style="border-color: var(--border-color) !important;">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              ${iconHtml}
              <span class="fw-bold text-body" style="font-size: 1.02rem;">${escapeHtml(d.name)}</span>
              <span class="badge ${mediaBadgeClass} font-monospace" style="font-size: 0.72rem;">${escapeHtml(d.media_type)}</span>
              <span class="badge bg-secondary-subtle text-body border font-monospace" style="font-size: 0.70rem;">${escapeHtml(d.id)}</span>
              <span class="badge bg-success-subtle text-success border border-success font-monospace" style="font-size: 0.70rem;">● ${escapeHtml(d.health_status || 'SMART OK')}</span>
            </div>
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-dark border text-light font-monospace px-2.5 py-1" style="font-size: 0.80rem; font-variant-numeric: tabular-nums;">${usedGb.toFixed(1)} / ${totGb.toFixed(1)} GB (${pct.toFixed(1)}%)</span>
            </div>
          </div>
          <div class="row g-3 align-items-stretch">
            <!-- 1. Заполнение накопителя (Спидометр) + Температурный слайдер -->
            <div class="col-12 col-md-4">
              <div class="p-2.5 rounded-2 h-100 d-flex flex-column justify-content-between" style="background: var(--surface-2); border: 1px solid var(--border-color);">
                <div>
                  <div class="d-flex justify-content-between align-items-center mb-1.5">
                    <span class="small text-muted fw-bold d-flex align-items-center gap-1">
                      <i class="bi bi-pie-chart text-info"></i>Заполнение накопителя
                    </span>
                    <span class="fw-bold font-monospace ${pct >= 85 ? 'text-danger' : 'text-info'}" style="font-size: 0.88rem; font-variant-numeric: tabular-nums;">${pct.toFixed(1)}%</span>
                  </div>
                  <div class="d-flex align-items-center gap-2.5 my-1">
                    <div style="width: 86px; height: 50px; flex-shrink: 0;">${createGaugeSvg(pct, 86, 50)}</div>
                    <div class="flex-grow-1" style="min-width: 0;">
                      <div class="font-monospace fw-bold text-body text-truncate" style="font-size: 0.86rem; font-variant-numeric: tabular-nums;">${usedGb.toFixed(1)} / ${totGb.toFixed(1)} GB</div>
                      <div class="small text-muted font-monospace text-truncate" style="font-size: 0.74rem; font-variant-numeric: tabular-nums;">Свободно: <span class="text-success fw-semibold">${freeGb.toFixed(1)} GB</span></div>
                    </div>
                  </div>
                </div>
                <div class="mt-2 pt-1.5 border-top" style="border-color: var(--border-subtle) !important;">
                  ${tempSliderHtml}
                </div>
              </div>
            </div>
            <!-- 2. Интенсивность ввода-вывода (I/O, Скорость чтения/записи) -->
            <div class="col-12 col-md-4">
              <div class="p-2.5 rounded-2 h-100 d-flex flex-column justify-content-between" style="background: var(--surface-2); border: 1px solid var(--border-color);">
                <div>
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="small text-muted fw-bold d-flex align-items-center gap-1">
                      <i class="bi bi-arrow-left-right text-warning"></i>Интенсивность I/O
                    </span>
                    <span class="badge bg-dark border border-secondary text-light font-monospace" style="font-size: 0.68rem;">
                      ${d.activity_percent != null ? d.activity_percent.toFixed(0) + '% нагр.' : 'I/O Stream'}
                    </span>
                  </div>
                  <div class="d-flex flex-column gap-1.5 font-monospace" style="font-size: 0.80rem; font-variant-numeric: tabular-nums;">
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-arrow-down-circle text-info me-1"></i>Чтение (Read):</span>
                      <span class="text-info fw-bold text-truncate">${escapeHtml(d.read_rate_raw || '0 B/s')}</span>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-arrow-up-circle text-warning me-1"></i>Запись (Write):</span>
                      <span class="text-warning fw-bold text-truncate">${escapeHtml(d.write_rate_raw || '0 B/s')}</span>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-file-earmark-arrow-down text-secondary me-1"></i>Σ Прочитано:</span>
                      <span class="text-body fw-semibold text-truncate">${escapeHtml(d.data_read_raw || '--')}</span>
                    </div>
                  </div>
                </div>
                <div class="mt-2 pt-1.5 border-top d-flex justify-content-between align-items-center font-monospace small" style="border-color: var(--border-subtle) !important; font-size: 0.74rem;">
                  <span class="text-muted">Активность шины:</span>
                  <span class="${(d.activity_percent || 0) > 60 ? 'text-danger fw-bold' : (d.activity_percent || 0) > 20 ? 'text-warning fw-bold' : 'text-success'}">
                    ${d.activity_percent != null ? d.activity_percent.toFixed(1) + '%' : 'В норме'}
                  </span>
                </div>
              </div>
            </div>
            <!-- 3. Ресурс накопителя, Наработка и SMART-состояние -->
            <div class="col-12 col-md-4">
              <div class="p-2.5 rounded-2 h-100 d-flex flex-column justify-content-between" style="background: var(--surface-2); border: 1px solid var(--border-color);">
                <div>
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="small text-muted fw-bold d-flex align-items-center gap-1">
                      <i class="bi bi-shield-check text-success"></i>Ресурс и Состояние
                    </span>
                    <span class="badge bg-success-subtle text-success border border-success font-monospace" style="font-size: 0.68rem;">
                      ● ${escapeHtml(d.health_status || 'SMART OK')}
                    </span>
                  </div>
                  <div class="d-flex flex-column gap-1.5 font-monospace" style="font-size: 0.80rem; font-variant-numeric: tabular-nums;">
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-disc text-primary me-1"></i>Σ Записано (TBW):</span>
                      <span class="text-warning fw-bold text-truncate">${escapeHtml(d.data_written_raw || '--')}</span>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-clock-history text-secondary me-1"></i>Наработка:</span>
                      <span class="text-body fw-semibold text-truncate">${formatDriveHours(d.power_on_hours)}</span>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                      <span class="text-muted"><i class="bi bi-power text-secondary me-1"></i>${d.life_percent != null ? 'Ресурс SSD (Life):' : 'Циклы включения:'}</span>
                      <span class="text-body fw-semibold text-truncate">${d.life_percent != null ? d.life_percent + '%' : (d.power_on_count != null ? d.power_on_count.toLocaleString() + ' раз' : '--')}</span>
                    </div>
                  </div>
                </div>
                <div class="mt-2 pt-1.5 border-top d-flex justify-content-between align-items-center font-monospace small" style="border-color: var(--border-subtle) !important; font-size: 0.74rem;">
                  <span class="text-muted">Интерфейс:</span>
                  <span class="text-body fw-semibold">${escapeHtml(d.interface_type || d.media_type || 'SATA/NVMe')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');

    box.querySelectorAll('.sys-drive-full-card').forEach(card => {
      card.addEventListener('click', () => {
        const idx = Number(card.getAttribute('data-drive-idx'));
        if (drivesToRender[idx]) openDriveAiModal(drivesToRender[idx]);
      });
    });
  }
}

/**
 * Отрисовка таблицы физических дисков.
 */
export function renderPhysicalDisksStorage(disks) {
  const tbody = document.getElementById('sys-storage-disks-tbody');
  if (!tbody || !Array.isArray(disks)) return;
  tbody.innerHTML = disks.map((d, i) => `
    <tr>
      <td class="font-monospace text-info">${escapeHtml(d.device_id || `Drive #${i}`)}</td>
      <td class="fw-bold">${escapeHtml(d.model || d.name || '--')}</td>
      <td><span class="badge bg-secondary">${escapeHtml(d.media_type || 'Unknown')}</span></td>
      <td class="font-monospace">${d.size_gb ? d.size_gb + ' GB' : '--'}</td>
      <td><span class="badge bg-success-subtle text-success">${escapeHtml(d.status || 'OK')}</span></td>
    </tr>
  `).join('');
}

/**
 * Отрисовка SVG-спарклайна накопителей.
 */
export function renderStorageSpark(history) {
  const box = document.getElementById('sys-storage-spark');
  if (!box) return;

  let ptsData = Array.isArray(history) && history.length > 0 ? history : (lastStorageSparkData || _storageSparkHistory || []);
  if (!ptsData || ptsData.length === 0) {
    ptsData = [{ read_bytes_sec: 0, write_bytes_sec: 0, time: new Date() }];
  }
  if (ptsData.length === 1) {
    ptsData = [ptsData[0], { ...ptsData[0], time: ptsData[0].time || new Date() }];
  }
  lastStorageSparkData = ptsData;

  box.replaceChildren();
  const ns = 'http://www.w3.org/2000/svg';
  const W = 600, H = 84;
  const padBottom = 6;
  const innerH = H - 12;

  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.style.cssText = 'width:100%;height:100%;display:block;';

  const count = ptsData.length;
  const readPts = [];
  const writePts = [];

  ptsData.forEach((h, i) => {
    const x = (i / (count - 1)) * W;
    const rd = Number(h.read_bytes_sec || 0);
    const wr = Number(h.write_bytes_sec || 0);
    const yR = H - padBottom - Math.min(1, rd / (50 * 1024 * 1024)) * innerH;
    const yW = H - padBottom - Math.min(1, wr / (50 * 1024 * 1024)) * innerH;
    readPts.push({ x, y: yR });
    writePts.push({ x, y: yW });
  });

  const drawLine = (pts, col) => {
    if (pts.length < 2) return;
    const linePath = buildSmoothSvgPath(pts);
    const pEl = document.createElementNS(ns, 'path');
    pEl.setAttribute('d', linePath);
    pEl.setAttribute('fill', 'none');
    pEl.setAttribute('stroke', col);
    pEl.setAttribute('stroke-width', '1.5');
    svg.appendChild(pEl);
  };

  drawLine(writePts, '#f59e0b');
  drawLine(readPts, '#0dcaf0');
  box.appendChild(svg);
}
