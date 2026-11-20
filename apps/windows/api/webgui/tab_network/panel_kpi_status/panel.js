/**
 * Модуль панели статуса и KPI сетевой подсистемы.
 * Файл: apps/windows/api/webgui/tab_network/panel_kpi_status/panel.js
 * Updated: 2026-11-20 16:45:00
 */

/**
 * Запрашивает общий статус сетевой подсистемы и доступность TShark DPI.
 * @param {number} [fallbackPacketsCount=0] - Количество перехваченных пакетов при отсутствии в API.
 */
export async function fetchNetworkStatus(fallbackPacketsCount = 0) {
  const engineBadge = document.getElementById('net-engine-status');
  const tsharkBadge = document.getElementById('net-tshark-status');
  const kpiAdapters = document.getElementById('net-kpi-adapters');
  const kpiConns = document.getElementById('net-kpi-conns');
  const kpiListening = document.getElementById('net-kpi-listening');
  const kpiPackets = document.getElementById('net-kpi-packets');
  const kpiAnomalies = document.getElementById('net-kpi-anomalies');

  try {
    const res = await fetch('/api/v1/network/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (engineBadge) {
      engineBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-2 py-1';
      engineBadge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Windows Net: Active';
    }

    if (tsharkBadge) {
      if (data.tshark_available) {
        tsharkBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-2 py-1';
        tsharkBadge.innerText = 'TShark DPI: Доступен';
      } else {
        tsharkBadge.className = 'badge rounded-pill bg-warning-subtle text-warning border border-warning px-2 py-1';
        tsharkBadge.innerText = 'TShark DPI: Не установлен';
      }
    }

    if (kpiAdapters) kpiAdapters.innerText = data.total_adapters ?? '--';
    if (kpiConns) kpiConns.innerText = data.active_connections_count ?? '--';
    if (kpiListening) kpiListening.innerText = `${data.listening_ports_count || 0} слушающих`;
    if (kpiPackets) kpiPackets.innerText = data.total_packets ?? fallbackPacketsCount;

    const anomaliesCount = (data.latest_heuristics?.length || 0) + (data.latest_ai_report?.anomalies?.length || 0);
    if (kpiAnomalies) {
      kpiAnomalies.innerText = `${anomaliesCount} аномалий`;
      kpiAnomalies.className = `small ${anomaliesCount > 0 ? 'text-danger' : 'text-success'}`;
      kpiAnomalies.style.fontSize = '0.68rem';
    }
  } catch (e) {
    console.warn('[NetworkTab] Status check error:', e);
    if (engineBadge) {
      engineBadge.className = 'badge rounded-pill bg-danger-subtle text-danger border border-danger px-2 py-1';
      engineBadge.innerText = 'Windows Net: Ошибка';
    }
  }
}
