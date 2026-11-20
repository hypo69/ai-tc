/**
 * Модуль панели активных сетевых подключений и слушающих портов.
 * Файл: apps/windows/api/webgui/tab_network/panel_connections/panel.js
 * Updated: 2026-11-20 16:45:00
 */

let allConnections = [];
let activeConnFilter = 'all';

/**
 * Устанавливает текущий фильтр подключений (all, LISTEN, ESTABLISHED, UDP).
 * @param {string} filter - Идентификатор фильтра.
 */
export function setActiveConnFilter(filter) {
  activeConnFilter = filter || 'all';
}

/**
 * Запрашивает активные соединения и слушающие порты с сервера.
 */
export async function fetchConnections() {
  const tbody = document.getElementById('net-conns-tbody');
  const badgeConn = document.getElementById('badge-conn-count');
  const kpiConns = document.getElementById('net-kpi-conns');
  const kpiListening = document.getElementById('net-kpi-listening');

  try {
    const res = await fetch('/api/v1/network/connections?limit=250');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const conns = Array.isArray(data.connections) ? data.connections : [];
    const listening = Array.isArray(data.listening_ports) ? data.listening_ports : [];
    allConnections = [...listening, ...conns];

    if (badgeConn) badgeConn.innerText = allConnections.length;
    if (kpiConns) kpiConns.innerText = conns.length;
    if (kpiListening) kpiListening.innerText = `${listening.length} слушающих`;

    renderConnectionsTable();
  } catch (e) {
    console.error('[NetworkTab] Failed to fetch connections:', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center py-3 text-danger">Ошибка загрузки соединений: ${e.message}</td></tr>`;
  }
}

/**
 * Отрисовывает таблицу сетевых подключений с учетом фильтра и поискового запроса.
 */
export function renderConnectionsTable() {
  const tbody = document.getElementById('net-conns-tbody');
  const searchInput = document.getElementById('net-conns-filter');
  const query = (searchInput?.value || '').toLowerCase().trim();

  if (!tbody) return;

  const filtered = allConnections.filter(c => {
    if (activeConnFilter === 'LISTEN' && c.status !== 'LISTEN') return false;
    if (activeConnFilter === 'ESTABLISHED' && c.status !== 'ESTABLISHED') return false;
    if (activeConnFilter === 'UDP' && c.protocol !== 'UDP') return false;

    if (query) {
      const text = `${c.protocol} ${c.local_address} ${c.remote_address} ${c.status} ${c.pid} ${c.process_name}`.toLowerCase();
      return text.includes(query);
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Соединения, удовлетворяющие критериям, не найдены.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.slice(0, 150).map((c, idx) => {
    const protoClass = c.protocol === 'TCP' ? 'proto-tcp' : (c.protocol === 'UDP' ? 'proto-udp' : 'proto-other');
    let statusClass = 'proto-other';
    if (c.status === 'LISTEN') statusClass = 'status-badge-listen';
    else if (c.status === 'ESTABLISHED') statusClass = 'status-badge-established';

    return `
      <tr class="net-conn-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для детальной инспекции процесса и сокета">
        <td><span class="proto-badge ${protoClass}">${c.protocol || 'TCP'}</span></td>
        <td class="text-info font-monospace">${c.local_address || '-'}</td>
        <td class="text-secondary font-monospace">${c.remote_address || '-'}</td>
        <td><span class="proto-badge ${statusClass}">${c.status || '-'}</span></td>
        <td class="text-muted font-monospace">${c.pid || '-'}</td>
        <td class="fw-semibold text-body"><i class="bi bi-app me-1 text-muted"></i>${c.process_name || 'Неизвестно'}</td>
      </tr>
    `;
  }).join('');

  // Инспекция через универсальный модал AITableModal при клике
  tbody.querySelectorAll('.net-conn-row').forEach(row => {
    row.onclick = () => {
      const idx = parseInt(row.getAttribute('data-idx'), 10);
      const item = filtered[idx];
      if (!item || !window.AITableModal) return;

      window.AITableModal.show({
        icon: '📡',
        title: `Сетевое подключение [${item.protocol || 'TCP'}]`,
        subtitle: `${item.process_name} (PID: ${item.pid || 'N/A'})`,
        panelId: 'panel-network-connections',
        tableType: 'network',
        badges: [
          { text: item.protocol || 'TCP', class: 'badge bg-primary' },
          { text: item.status || 'UNKNOWN', class: 'badge bg-info' },
          { text: `PID ${item.pid || '-'}`, class: 'badge bg-secondary' }
        ],
        metadata: [
          { label: 'Процесс', value: item.process_name || '-' },
          { label: 'PID', value: String(item.pid || '-') },
          { label: 'Протокол', value: item.protocol || '-' },
          { label: 'Локальный адрес:Порт', value: item.local_address || '-' },
          { label: 'Удалённый адрес:Порт', value: item.remote_address || '-' },
          { label: 'Статус сокета', value: item.status || '-' }
        ],
        rawTitle: 'Детали сокета',
        rawContent: JSON.stringify(item, null, 2),
        requestData: item
      });
    };
  });
}
