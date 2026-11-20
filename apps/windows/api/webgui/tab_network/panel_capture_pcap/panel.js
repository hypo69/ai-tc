/**
 * Модуль панели живого перехвата трафика (DPI) и анализа PCAP файлов.
 * Файл: apps/windows/api/webgui/tab_network/panel_capture_pcap/panel.js
 * Updated: 2026-11-20 16:45:00
 */

let capturedPackets = [];
let netEventSource = null;

/**
 * Возвращает текущее количество захваченных пакетов.
 * @returns {number}
 */
export function getCapturedPacketsCount() {
  return capturedPackets.length;
}

/**
 * Очищает буфер захваченных пакетов.
 */
export function clearCapturedPackets() {
  capturedPackets = [];
  renderPacketsTable();
}

/**
 * Отрисовывает таблицу пакетов.
 */
export function renderPacketsTable() {
  const tbody = document.getElementById('net-packets-tbody');
  const badge = document.getElementById('net-captured-badge');
  const filterInput = document.getElementById('net-table-filter');
  const filter = (filterInput?.value || '').toLowerCase().trim();

  if (!tbody) return;
  if (badge) badge.innerText = `${capturedPackets.length} пакетов`;

  if (capturedPackets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Нет захваченных пакетов. Выберите интерфейс и нажмите "Старт захвата".</td></tr>';
    return;
  }

  const filtered = capturedPackets.filter(p => {
    if (!filter) return true;
    const str = `${p.number || p.packet_number || ''} ${p.source || ''} ${p.destination || ''} ${p.protocol || ''} ${p.info || ''}`.toLowerCase();
    return str.includes(filter);
  });

  const pagePackets = filtered.slice(-100);
  tbody.innerHTML = pagePackets.map((p, idx) => {
    const proto = (p.protocol || 'OTHER').toUpperCase();
    let protoClass = 'proto-other';
    if (proto.includes('TCP')) protoClass = 'proto-tcp';
    else if (proto.includes('UDP')) protoClass = 'proto-udp';
    else if (proto.includes('TLS') || proto.includes('SSL')) protoClass = 'proto-tls';
    else if (proto.includes('HTTP')) protoClass = 'proto-http';
    else if (proto.includes('DNS')) protoClass = 'proto-dns';

    return `
      <tr class="net-packet-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для детального AI-анализа пакета">
        <td class="text-muted font-monospace">${p.number || p.packet_number || '--'}</td>
        <td>${p.timestamp ? (typeof p.timestamp === 'number' ? new Date(p.timestamp * 1000).toLocaleTimeString() : p.timestamp) : '--'}</td>
        <td class="text-info font-monospace">${p.source || '--'}</td>
        <td class="text-primary font-monospace">${p.destination || '--'}</td>
        <td><span class="proto-badge ${protoClass}">${proto}</span></td>
        <td style="text-align: right;" class="font-monospace">${p.length || 0} B</td>
        <td class="text-truncate text-body" style="max-width: 320px;">${p.info || '--'}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.net-packet-row').forEach(row => {
    row.onclick = () => {
      const idx = parseInt(row.getAttribute('data-idx'), 10);
      const p = pagePackets[idx];
      if (!p || !window.AITableModal) return;

      window.AITableModal.show({
        icon: '🌐',
        title: `Сетевой пакет #${p.number || p.packet_number || 'N/A'} [${p.protocol || 'TCP'}]`,
        subtitle: `${p.source || '0.0.0.0'} ➔ ${p.destination || '0.0.0.0'}`,
        panelId: 'panel-network-packets',
        tableType: 'network',
        badges: [
          { text: (p.protocol || 'TCP').toUpperCase(), class: 'badge bg-primary' },
          { text: `${p.length || 0} Bytes`, class: 'badge bg-secondary' }
        ],
        metadata: [
          { label: 'Номер пакета', value: String(p.number || p.packet_number || '-') },
          { label: 'Протокол', value: (p.protocol || 'TCP').toUpperCase() },
          { label: 'Источник', value: p.source || '-' },
          { label: 'Назначение', value: p.destination || '-' },
          { label: 'Размер', value: `${p.length || 0} байт` },
          { label: 'Инфо', value: p.info || 'Нет данных', fullWidth: true }
        ],
        rawTitle: 'Сырые данные пакета',
        rawContent: JSON.stringify(p, null, 2),
        requestData: p
      });
    };
  });
}

/**
 * Запускает перехват трафика в реальном времени через SSE.
 */
export async function startLiveCapture() {
  const ifaceSelect = document.getElementById('net-interface-select');
  const filterInput = document.getElementById('net-capture-filter');
  const startBtn = document.getElementById('btn-start-live-capture');
  const stopBtn = document.getElementById('btn-stop-live-capture');

  const iface = ifaceSelect?.value || '1';
  const filter = filterInput?.value || '';

  try {
    const res = await fetch(`/api/v1/network/start-capture?interface=${encodeURIComponent(iface)}&display_filter=${encodeURIComponent(filter)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;

    if (netEventSource) netEventSource.close();
    netEventSource = new EventSource('/api/v1/network/packets/stream');
    netEventSource.onmessage = async () => {
      try {
        const packRes = await fetch('/api/v1/network/packets?limit=50');
        if (packRes.ok) {
          const data = await packRes.json();
          if (Array.isArray(data.packets)) {
            capturedPackets = data.packets;
            renderPacketsTable();
          }
        }
      } catch (e) {
        console.warn('[NetworkTab] Packet poll error:', e);
      }
    };
  } catch (e) {
    console.error('[NetworkTab] Live capture error:', e);
    window.showToast?.('Ошибка запуска захвата пакетов: ' + e.message, 'danger') || alert('Ошибка запуска захвата пакетов: ' + e.message);
  }
}

/**
 * Останавливает живой захват трафика.
 */
export async function stopLiveCapture() {
  const startBtn = document.getElementById('btn-start-live-capture');
  const stopBtn = document.getElementById('btn-stop-live-capture');

  if (netEventSource) {
    netEventSource.close();
    netEventSource = null;
  }

  try {
    await fetch('/api/v1/network/stop-capture', { method: 'POST' });
  } catch (e) {
    console.warn('[NetworkTab] Stop capture error:', e);
  }

  if (startBtn) startBtn.disabled = false;
  if (stopBtn) stopBtn.disabled = true;
}

/**
 * Загружает и отправляет на AI-анализ файл PCAP/PCAPNG.
 */
export async function analyzePcapFile() {
  const fileInput = document.getElementById('net-pcap-file');
  const statusEl = document.getElementById('net-upload-status');
  const healthEl = document.getElementById('pcap-health-score');
  const anomaliesEl = document.getElementById('pcap-anomalies-count');
  const heuristicsEl = document.getElementById('pcap-heuristics-list');
  const recommendationsEl = document.getElementById('pcap-ai-recommendations');

  const file = fileInput?.files?.[0];
  if (!file) {
    window.showToast?.('Пожалуйста, выберите .pcap или .pcapng файл', 'warning') || alert('Пожалуйста, выберите .pcap или .pcapng файл');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('max_packets', '500');

  if (statusEl) statusEl.innerText = 'Анализ пакетов...';

  try {
    const res = await fetch('/api/v1/network/analyze/pcap', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();

    if (statusEl) statusEl.innerText = `Анализ завершён: ${report.stats?.total_packets || 0} пакетов`;
    if (healthEl) healthEl.innerText = `${report.ai_report?.health_score || 100}/100`;

    const anomaliesCount = (report.heuristics?.length || 0) + (report.ai_report?.anomalies?.length || 0);
    if (anomaliesEl) {
      anomaliesEl.innerText = String(anomaliesCount);
      anomaliesEl.className = `net-value mt-1 ${anomaliesCount > 0 ? 'text-danger' : 'text-success'}`;
    }

    if (heuristicsEl) {
      if (Array.isArray(report.heuristics) && report.heuristics.length > 0) {
        heuristicsEl.innerHTML = report.heuristics.map(h => `<div class="text-warning mb-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>${h}</div>`).join('');
      } else {
        heuristicsEl.innerHTML = '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Эвристических угроз не выявлено.</span>';
      }
    }

    if (recommendationsEl) {
      if (Array.isArray(report.ai_report?.recommended_actions) && report.ai_report.recommended_actions.length > 0) {
        recommendationsEl.innerHTML = report.ai_report.recommended_actions.map(r => `<div class="text-info mb-1"><i class="bi bi-arrow-right-short me-1"></i>${r}</div>`).join('');
      } else {
        recommendationsEl.innerHTML = '<span class="text-muted">Рекомендаций нет, система функционирует штатно.</span>';
      }
    }

    if (Array.isArray(report.sample_packets) && report.sample_packets.length > 0) {
      capturedPackets = report.sample_packets;
      renderPacketsTable();
    }
  } catch (e) {
    console.error('[NetworkTab] PCAP upload error:', e);
    if (statusEl) statusEl.innerText = 'Ошибка анализа: ' + e.message;
    window.showToast?.('Ошибка при анализе PCAP: ' + e.message, 'danger') || alert('Ошибка при анализе PCAP: ' + e.message);
  }
}
