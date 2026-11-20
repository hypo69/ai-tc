/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - Results & Chart Panel
 * =============================================================================
 * Description:
 *   Модуль визуализации результатов бенчмарка дисков и графика пропускной способности.
 *
 * File: panel_results_chart/panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed/panel_results_chart
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

let mbChartInstance = null;
let lastResult = null;

/**
 * Инициализация графика Chart.js.
 */
export function initChart() {
  const ctx = document.getElementById('bench-mb-chart');
  if (!ctx || typeof Chart === 'undefined') return;

  if (mbChartInstance) {
    mbChartInstance.destroy();
  }

  mbChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['SEQ1M Q8T1', 'SEQ1M Q1T1', 'RND4K Q32T16', 'RND4K Q1T1'],
      datasets: [
        {
          label: 'Read (MB/s)',
          data: [0, 0, 0, 0],
          backgroundColor: 'rgba(13, 202, 240, 0.75)',
          borderColor: '#0dcaf0',
          borderWidth: 1,
        },
        {
          label: 'Write (MB/s)',
          data: [0, 0, 0, 0],
          backgroundColor: 'rgba(255, 193, 7, 0.75)',
          borderColor: '#ffc107',
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: '#334155' },
          ticks: { color: '#94a3b8' },
        },
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8' },
        },
      },
      plugins: {
        legend: { labels: { color: '#f8fafc' } },
      },
    },
  });
}

/**
 * Обновление данных графика.
 * @param {Array<Object>} points
 */
export function updateChartData(points) {
  if (!mbChartInstance) return;
  const labels = points.map(p => p.label);
  const reads = points.map(p => p.read || 0);
  const writes = points.map(p => p.write || 0);

  mbChartInstance.data.labels = labels;
  mbChartInstance.data.datasets[0].data = reads;
  mbChartInstance.data.datasets[1].data = writes;
  mbChartInstance.update();
}

/**
 * Обновление строки таблицы CDM.
 * @param {string} rowKey
 * @param {number} readMb
 * @param {number} writeMb
 * @param {string} iops
 * @param {string} lat
 */
export function updateRowValues(rowKey, readMb, writeMb, iops, lat) {
  const rEl = document.getElementById(`val-${rowKey}-read`);
  const wEl = document.getElementById(`val-${rowKey}-write`);
  const iopsEl = document.getElementById(`val-${rowKey}-iops`);
  const latEl = document.getElementById(`val-${rowKey}-lat`);

  if (rEl) rEl.textContent = (readMb || 0).toFixed(2);
  if (wEl) wEl.textContent = (writeMb || 0).toFixed(2);
  if (iopsEl) iopsEl.textContent = iops;
  if (latEl) latEl.textContent = lat;
}

/**
 * Загрузка последнего результата и заполнение таблицы CDM.
 */
export async function loadLatestHistoryResult() {
  try {
    const res = await fetch('/api/v1/storage/benchmark/history?limit=1');
    if (!res.ok) return;
    const items = await res.json();
    if (!items || items.length === 0) return;

    const latest = items[0];
    lastResult = latest;

    const summaryTime = document.getElementById('bench-summary-time');
    if (summaryTime) summaryTime.textContent = latest.created_at;

    // SEQ1M Q8T1
    updateRowValues('seq1m_q8t1', latest.seq1m_read_mb_s, latest.seq1m_write_mb_s, '-- / --', '-- µs');
    // RND4K Q32T16
    updateRowValues('rnd4k_q32t16', latest.rnd4k_read_mb_s, latest.rnd4k_write_mb_s, `${Math.round(latest.rnd4k_read_iops)} / ${Math.round(latest.rnd4k_write_iops)}`, '-- µs');

    updateChartData([
      { label: 'SEQ1M Q8T1', read: latest.seq1m_read_mb_s, write: latest.seq1m_write_mb_s },
      { label: 'RND4K Q32T16', read: latest.rnd4k_read_mb_s, write: latest.rnd4k_write_mb_s },
    ]);
  } catch (err) {
    console.debug('[DiskSpeed] Ошибка загрузки свежих результатов:', err);
  }
}

/**
 * Получение последнего закэшированного результата.
 * @returns {Object|null}
 */
export function getLastResult() {
  return lastResult;
}
