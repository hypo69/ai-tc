/**
 * Модуль панели тестирования скорости интернета и пинга.
 * Файл: apps/windows/api/webgui/tab_network/panel_speedtest/panel.js
 * Updated: 2026-10-30 11:05:00
 */

let isSpeedtestRunning = false;

/**
 * Вспомогательная функция обновления текста для нескольких элементов.
 * @param {string} selector - Селектор элементов
 * @param {string} text - Новый текст
 */
function updateAllText(selector, text) {
  document.querySelectorAll(selector).forEach(el => {
    el.innerText = text;
  });
}

/**
 * Вспомогательная функция обновления HTML для нескольких элементов.
 * @param {string} selector - Селектор элементов
 * @param {string} html - Новый HTML
 */
function updateAllHtml(selector, html) {
  document.querySelectorAll(selector).forEach(el => {
    el.innerHTML = html;
  });
}

/**
 * Вспомогательная функция обновления состояния кнопок запуска тестирования скорости.
 * @param {boolean} disabled - Флаг блокировки
 * @param {string} html - Содержимое кнопки
 */
function updateAllButtons(disabled, html) {
  document.querySelectorAll('#btn-run-speedtest, #sys-btn-run-speedtest, .btn-run-speedtest').forEach(btn => {
    btn.disabled = disabled;
    if (html) btn.innerHTML = html;
  });
}

/**
 * Загружает последний сохраненный результат speedtest из кэша.
 */
export async function fetchLatestSpeedtest() {
  try {
    const res = await fetch('/api/network/speedtest/latest');
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.download) {
      renderSpeedtestResults(data);
    }
  } catch (e) {
    console.debug('[NetworkTab] No latest speedtest data:', e);
  }
}

/**
 * Запускает полный замер скорости интернет-соединения.
 */
export async function runInternetSpeedtest() {
  if (isSpeedtestRunning) return;
  isSpeedtestRunning = true;

  updateAllButtons(true, '<span class="spinner-border spinner-border-sm me-1"></span> Тестирование...');
  updateAllText('#speedtest-status-text, #sys-speedtest-status-text, .speedtest-status-text', 'Измерение Ping, Download и Upload...');
  updateAllText('#speed-summary-text, #sys-speed-summary-text, .speed-summary-text', 'Выполняется подключение к узлам Cloudflare & DNS серверам для замера скорости...');

  try {
    const res = await fetch('/api/network/speedtest/run', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderSpeedtestResults(data);
    updateAllText('#speedtest-status-text, #sys-speedtest-status-text, .speedtest-status-text', `Завершено в ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    console.error('[NetworkTab] Speedtest error:', e);
    window.showToast?.('Ошибка при выполнении теста скорости: ' + e.message, 'danger') || alert('Ошибка при выполнении теста скорости: ' + e.message);
    updateAllText('#speedtest-status-text, #sys-speedtest-status-text, .speedtest-status-text', 'Ошибка теста скорости');
  } finally {
    isSpeedtestRunning = false;
    updateAllButtons(false, '<i class="bi bi-play-fill me-1"></i> Запустить тест скорости');
  }
}

/**
 * Отрисовывает результаты замера скорости в интерфейсе.
 * @param {Object} data - Результаты speedtest.
 */
export function renderSpeedtestResults(data) {
  const downMbps = data?.download?.speed_mbps || 0;
  const downMBs = data?.download?.speed_mb_s || 0;
  const upMbps = data?.upload?.speed_mbps || 0;
  const upMBs = data?.upload?.speed_mb_s || 0;
  const pingMs = data?.ping_ms || 0;
  const jitterMs = data?.jitter_ms || 0;
  const meta = data?.meta || {};
  const quality = data?.quality || {};

  updateAllText('#speed-val-download, #sys-speed-val-download, .speed-val-download', `${downMbps} Mbps`);
  updateAllText('#speed-sub-download, #sys-speed-sub-download, .speed-sub-download', `${downMBs} MB/s (${data?.download?.duration_s || 0}s)`);
  updateAllText('#speed-val-upload, #sys-speed-val-upload, .speed-val-upload', `${upMbps} Mbps`);
  updateAllText('#speed-sub-upload, #sys-speed-sub-upload, .speed-sub-upload', `${upMBs} MB/s (${data?.upload?.duration_s || 0}s)`);
  updateAllText('#speed-val-ping, #sys-speed-val-ping, .speed-val-ping', `${pingMs} ms`);
  updateAllText('#speed-sub-jitter, #sys-speed-sub-jitter, .speed-sub-jitter', `Jitter: ${jitterMs} ms`);

  document.querySelectorAll('#speed-val-grade, #sys-speed-val-grade, .speed-val-grade').forEach(el => {
    el.innerText = quality.rating || '--';
    el.style.color = quality.color || 'var(--ui-warning, #fbbf24)';
  });

  updateAllText('#speed-sub-isp, #sys-speed-sub-isp, .speed-sub-isp', `Провайдер: ${meta.isp || 'Неизвестно'}`);
  updateAllText('#speed-badge-ip, #sys-speed-badge-ip, .speed-badge-ip', `Внешний IP: ${meta.ip || '--'}`);
  updateAllText('#speed-badge-location, #sys-speed-badge-location, .speed-badge-location', `Локация: ${meta.city || ''} ${meta.country || ''} (${meta.colo || 'Edge'})`.trim());
  updateAllText('#speed-summary-text, #sys-speed-summary-text, .speed-summary-text', `${quality.grade || 'Готово'}. ${quality.summary || ''}`);

  updateAllText('#net-kpi-speed', `${downMbps} Mbps`);
  updateAllText('#net-kpi-ping', `Ping: ${pingMs} ms`);

  if (Array.isArray(data?.servers)) {
    const rowsHtml = data.servers.map(s => {
      const isOnline = s.avg_ms > 0;
      const statusBadge = isOnline 
        ? '<span class="proto-badge status-badge-up">Online</span>' 
        : '<span class="proto-badge status-badge-down">Offline</span>';

      return `
        <tr>
          <td class="fw-bold text-body"><i class="bi bi-hdd-network me-1 text-info"></i>${s.name}</td>
          <td class="text-secondary font-monospace">${s.host}</td>
          <td style="text-align: right;" class="text-info fw-bold font-monospace">${isOnline ? `${s.avg_ms} ms` : '--'}</td>
          <td style="text-align: right;" class="text-muted font-monospace">${isOnline ? `${s.min_ms} ms` : '--'}</td>
          <td style="text-align: right;" class="text-muted font-monospace">${isOnline ? `${s.max_ms} ms` : '--'}</td>
          <td style="text-align: right;" class="text-warning font-monospace">${isOnline ? `${s.jitter_ms} ms` : '--'}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    }).join('');

    updateAllHtml('#speed-servers-tbody, #sys-speed-servers-tbody, .speed-servers-tbody', rowsHtml);
  }
}
