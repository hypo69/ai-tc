/**
 * =============================================================================
 * Process Name: Windows Network Terminal - LAN Device Discovery Panel
 * =============================================================================
 * Description:
 *   Модуль панели автоматического обнаружения компьютеров и устройств
 *   в локальной сети (LAN Device Discovery).
 *   Обеспечивает обнаружение через ARP-кеш ядра, параллельный ARP-свип,
 *   SSDP/UPnP, NetBIOS/DNS разрешение имён, экспресс-проверку открытых
 *   портов (SMB, RDP, HTTP) и интеграцию с универсальным окном AIModalDialog.
 *
 * File: panel.js
 * Package: apps/windows/api/webgui/tab_network/panel_discovery
 * Updated: 2026-10-28 19:04:00
 * =============================================================================
 */

let discoveredDevices = [];
let activeFilter = 'all';
let isScanning = false;
let autoRefreshTimer = null;
let isAutoRefreshActive = true;
const probedPortsMap = new Map();

/**
 * Экранирует HTML-символы для безопасного рендеринга в DOM.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Определяет категорию устройства (компьютер, шлюз, смартфон, сетевое оборудование).
 * @param {Object} device
 * @returns {{type: string, icon: string, label: string}}
 */
function categorizeDevice(device) {
  if (device.is_gateway) return { type: 'gateway', icon: 'bi-router', label: 'Маршрутизатор / Шлюз' };
  if (device.is_local) return { type: 'computer', icon: 'bi-pc-display', label: 'Этот компьютер (Хост)' };
  const v = (device.vendor || '').toLowerCase();
  const h = (device.hostname || '').toLowerCase();
  if (/apple|samsung|xiaomi|huawei/.test(v) || /iphone|ipad|android|galaxy/.test(h)) {
    return { type: 'mobile', icon: 'bi-phone', label: 'Мобильное устройство' };
  }
  if (/mikrotik|keenetic|tp-link|d-link|netgear|ubiquiti|zyxel|espressif|raspberry/.test(v)) {
    return { type: 'network', icon: 'bi-hdd-network', label: 'Сетевое оборудование' };
  }
  return { type: 'computer', icon: 'bi-display', label: 'Компьютер / ПК' };
}

/**
 * Загружает доступные локальные подсети хоста в выпадающий список.
 */
export async function fetchSubnets() {
  const select = document.getElementById('net-discovery-subnet-select');
  if (!select) return;

  try {
    const res = await fetch('/api/network/subnets');
    if (!res.ok) return;
    const data = await res.json();
    const subnets = data.subnets || [];

    const optionsHtml = ['<option value="">Все активные подсети</option>'];
    subnets.forEach((s) => {
      optionsHtml.push(
        `<option value="${escapeHtml(s.cidr)}">${escapeHtml(s.name)} (${escapeHtml(s.cidr)})</option>`
      );
    });
    select.innerHTML = optionsHtml.join('');
  } catch (err) {
    console.debug('[LAN Discovery] Не удалось загрузить подсети:', err);
  }
}

/**
 * Проверяет статус системного сетевого обнаружения Windows и профиль сети.
 */
export async function fetchWindowsDiscoveryStatus() {
  const statusEl = document.getElementById('net-win-discovery-status');
  if (!statusEl) return;

  try {
    const res = await fetch('/api/v1/system/network-profile');
    if (!res.ok) return;
    const data = await res.json();

    const isEnabled = data.is_discovery_enabled === true;
    const category = data.current_category || 'Public';
    const isPrivate = category.toLowerCase() === 'private';

    if (isEnabled && isPrivate) {
      statusEl.innerHTML = '<span class="badge bg-success-subtle text-success border border-success d-inline-flex align-items-center gap-1 px-2.5 py-1"><i class="bi bi-shield-check"></i>Обнаружение сети Windows активно (Частная сеть)</span>';
    } else {
      statusEl.innerHTML = `<div class="d-inline-flex align-items-center gap-2 flex-wrap"><span class="badge bg-warning-subtle text-warning border border-warning px-2.5 py-1"><i class="bi bi-exclamation-triangle me-1"></i>Обнаружение сети: ${isEnabled ? 'Включено' : 'Отключено'} (Профиль: ${escapeHtml(category)})</span><button class="btn btn-xs btn-outline-warning rounded-pill px-2.5 py-0.5" id="btn-enable-win-discovery" title="Включить обнаружение"><i class="bi bi-toggle-on me-1"></i>Включить обнаружение</button></div>`;
      const enableBtn = document.getElementById('btn-enable-win-discovery');
      if (enableBtn) {
        enableBtn.onclick = async () => {
          enableBtn.disabled = true;
          enableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Включение...';
          try {
            const toggleRes = await fetch('/api/v1/system/network-discovery/toggle', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ enabled: true, set_category: 'Private' }),
            });
            if (toggleRes.ok) {
              window.showToast?.('Сетевое обнаружение Windows активировано', 'success');
              fetchWindowsDiscoveryStatus();
              fetchDiscoveredDevices(true);
            } else { throw new Error(`HTTP ${toggleRes.status}`); }
          } catch (e) {
            window.showToast?.('Ошибка активации: ' + e.message, 'danger');
            enableBtn.disabled = false;
            enableBtn.innerHTML = '<i class="bi bi-toggle-on me-1"></i>Повторить';
          }
        };
      }
    }
  } catch (err) {
    console.debug('[LAN Discovery] Ошибка проверки профиля сети:', err);
  }
}

/**
 * Запрашивает список обнаруженных компьютеров и устройств с сервера.
 * @param {boolean} [fullScan=false] - Выполнить ли глубокое параллельное ARP-сканирование подсети.
 */
export async function fetchDiscoveredDevices(fullScan = false) {
  if (isScanning) return;
  isScanning = true;

  const tbody = document.getElementById('net-discovery-tbody');
  const btnRefresh = document.getElementById('btn-refresh-discovery');
  const btnDeepScan = document.getElementById('btn-deep-scan-discovery');
  const statusMsg = document.getElementById('net-discovery-status-msg');
  const subnetSelect = document.getElementById('net-discovery-subnet-select');
  const selectedSubnet = subnetSelect?.value || '';

  if (fullScan) {
    if (btnDeepScan) {
      btnDeepScan.disabled = true;
      btnDeepScan.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сканирование сети...';
    }
    if (statusMsg) statusMsg.innerText = 'Выполняется параллельный ARP-свип и опрос UPnP/SSDP...';
  } else {
    if (btnRefresh) {
      btnRefresh.disabled = true;
      btnRefresh.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Опрос кеша...';
    }
  }

  try {
    const url = `/api/network/devices?scan=${fullScan ? 'true' : 'false'}${selectedSubnet ? `&subnet=${encodeURIComponent(selectedSubnet)}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    discoveredDevices = Array.isArray(data.devices) ? data.devices : [];
    updateDiscoveryKpis();
    renderDiscoveryTable();

    if (statusMsg) {
      const timeStr = new Date().toLocaleTimeString();
      statusMsg.innerText = `Найдено узлов: ${discoveredDevices.length} (${fullScan ? 'Глубокое сканирование' : 'Кэш соседей'}, ${timeStr})`;
    }
  } catch (err) {
    console.error('[LAN Discovery] Ошибка опроса устройств:', err);
    if (tbody && discoveredDevices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>Ошибка обнаружения устройств: ${escapeHtml(err.message)}</td></tr>`;
    }
    if (statusMsg) statusMsg.innerText = `Ошибка опроса: ${err.message}`;
  } finally {
    isScanning = false;
    if (btnRefresh) {
      btnRefresh.disabled = false;
      btnRefresh.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Кеш соседей';
    }
    if (btnDeepScan) {
      btnDeepScan.disabled = false;
      btnDeepScan.innerHTML = '<i class="bi bi-search me-1"></i>Глубокое сканирование';
    }
  }
}

/**
 * Обновляет KPI-счетчики обнаруженных компьютеров и сетевых узлов.
 */
function updateDiscoveryKpis() {
  const kpiTotal = document.getElementById('kpi-discovery-total');
  const kpiComputers = document.getElementById('kpi-discovery-computers');
  const kpiGateways = document.getElementById('kpi-discovery-gateways');
  const kpiOnline = document.getElementById('kpi-discovery-online');

  let total = discoveredDevices.length;
  let computers = 0;
  let gateways = 0;
  let online = 0;

  discoveredDevices.forEach((d) => {
    const cat = categorizeDevice(d);
    if (cat.type === 'computer') computers++;
    if (d.is_gateway) gateways++;
    if (d.state === 'Online' || d.state === 'LocalHost' || d.state === 'Reachable' || d.state === 'DYNAMIC') online++;
  });

  if (kpiTotal) kpiTotal.innerText = total;
  if (kpiComputers) kpiComputers.innerText = computers;
  if (kpiGateways) kpiGateways.innerText = gateways;
  if (kpiOnline) kpiOnline.innerText = online;
}

/**
 * Отрисовывает таблицу обнаруженных компьютеров в DOM.
 */
export function renderDiscoveryTable() {
  const tbody = document.getElementById('net-discovery-tbody');
  const searchInput = document.getElementById('net-discovery-filter');
  const query = (searchInput?.value || '').toLowerCase().trim();

  if (!tbody) return;

  const filtered = discoveredDevices.filter((d) => {
    const cat = categorizeDevice(d);
    if (activeFilter === 'computer' && cat.type !== 'computer') return false;
    if (activeFilter === 'gateway' && !d.is_gateway) return false;
    if (activeFilter === 'mobile' && cat.type !== 'mobile') return false;
    if (activeFilter === 'online' && !['Online', 'LocalHost', 'Reachable', 'DYNAMIC'].includes(d.state)) return false;

    if (query) {
      const target = `${d.ip || ''} ${d.hostname || ''} ${d.mac || ''} ${d.vendor || ''}`.toLowerCase();
      return target.includes(query);
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-wifi-off fs-4 d-block mb-1 text-secondary"></i>Устройства не обнаружены по текущим фильтрам. Нажмите «Глубокое сканирование» для поиска хостов.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((d) => {
    const cat = categorizeDevice(d);
    let roleBadge = '';
    if (d.is_gateway) {
      roleBadge = '<span class="badge bg-warning-subtle text-warning border border-warning ms-1.5" style="font-size: 0.65rem;">Шлюз (Router)</span>';
    } else if (d.is_local) {
      roleBadge = '<span class="badge bg-info-subtle text-info border border-info ms-1.5" style="font-size: 0.65rem;">Этот ПК</span>';
    }

    const displayName = d.hostname || d.ip;
    const hostSubtitle = d.hostname ? d.ip : 'Имя хоста не разрешено';
    const macDisplay = d.mac || '—';
    const vendorDisplay = d.vendor ? `<span class="badge bg-body-secondary border text-body me-1">${escapeHtml(d.vendor)}</span>` : '';
    const latencyDisplay = d.latency_ms !== null && d.latency_ms !== undefined
      ? `<span class="badge bg-success-subtle text-success border border-success">${d.latency_ms} ms</span>`
      : '<span class="text-muted small">Кеш ядра</span>';

    const methods = (d.discovery_methods || []).map(m => {
      const lbl = m === 'arp_cache' ? 'ARP Cache' : (m === 'arp_sweep' ? 'ARP Sweep' : (m === 'ssdp' ? 'SSDP/UPnP' : m));
      return `<span class="badge bg-secondary-subtle text-body border" style="font-size: 0.65rem;">${lbl}</span>`;
    }).join(' ');

    const probed = probedPortsMap.get(d.ip);
    let portsHtml = '<span class="text-muted small" style="font-size: 0.68rem;">Не опрашивались</span>';
    if (probed?.open_ports?.length > 0) {
      portsHtml = probed.open_ports.map(port => {
        let name = String(port);
        let colorClass = 'bg-primary-subtle text-primary border-primary';
        if (port === 445) { name = 'SMB:445'; colorClass = 'bg-info-subtle text-info border-info'; }
        else if (port === 3389) { name = 'RDP:3389'; colorClass = 'bg-warning-subtle text-warning border-warning'; }
        else if (port === 80 || port === 443) { name = `Web:${port}`; colorClass = 'bg-success-subtle text-success border-success'; }
        else if (port === 22) { name = 'SSH:22'; colorClass = 'bg-danger-subtle text-danger border-danger'; }
        return `<span class="badge ${colorClass} border me-1" style="font-size: 0.68rem;">${name}</span>`;
      }).join('');
    } else if (probed?.open_ports) {
      portsHtml = '<span class="text-muted small" style="font-size: 0.68rem;">Закрыты</span>';
    }

    return `
      <tr data-ip="${escapeHtml(d.ip)}">
        <td>
          <div class="d-flex align-items-center gap-2">
            <span class="fs-5 ${cat.type === 'gateway' ? 'text-warning' : (d.is_local ? 'text-info' : 'text-primary')}"><i class="bi ${cat.icon}"></i></span>
            <div>
              <div class="fw-bold text-body d-flex align-items-center"><span>${escapeHtml(displayName)}</span>${roleBadge}</div>
              <div class="text-muted small font-monospace" style="font-size: 0.72rem;">${escapeHtml(hostSubtitle)}</div>
            </div>
          </div>
        </td>
        <td class="font-monospace text-info">${escapeHtml(d.ip)}</td>
        <td>
          <div class="small text-body font-monospace">${escapeHtml(macDisplay)}</div>
          <div class="mt-0.5">${vendorDisplay}</div>
        </td>
        <td><div class="d-flex align-items-center flex-wrap gap-1">${portsHtml}</div></td>
        <td>${latencyDisplay}</td>
        <td><div class="d-flex flex-wrap gap-1">${methods}</div></td>
        <td style="text-align: right;">
          <div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-xs btn-outline-info rounded-pill px-2 btn-device-ai" data-ip="${escapeHtml(d.ip)}" title="AI Диагностика компьютера"><i class="bi bi-cpu me-1"></i>AI</button>
            <button class="btn btn-xs btn-outline-secondary rounded-pill px-2 ms-1 btn-device-probe" data-ip="${escapeHtml(d.ip)}" title="Проверить открытые порты"><i class="bi bi-lightning-charge"></i></button>
            <button class="btn btn-xs btn-outline-secondary rounded-pill px-2 ms-1 btn-device-smb" data-ip="${escapeHtml(d.ip)}" title="Скопировать путь SMB"><i class="bi bi-folder2-open"></i></button>
            <a href="http://${escapeHtml(d.ip)}" target="_blank" rel="noopener" class="btn btn-xs btn-outline-secondary rounded-pill px-2 ms-1" title="Открыть веб-интерфейс"><i class="bi bi-globe"></i></a>
          </div>
        </td>
      </tr>`;
  }).join('');

  // Навешиваем обработчики кнопок таблицы
  tbody.querySelectorAll('.btn-device-ai').forEach((btn) => {
    btn.onclick = () => {
      const ip = btn.getAttribute('data-ip');
      openDeviceInAiModal(ip);
    };
  });

  tbody.querySelectorAll('.btn-device-probe').forEach((btn) => {
    btn.onclick = () => {
      const ip = btn.getAttribute('data-ip');
      probeHostPorts(ip, btn);
    };
  });

  tbody.querySelectorAll('.btn-device-smb').forEach((btn) => {
    btn.onclick = () => {
      const ip = btn.getAttribute('data-ip');
      const unc = `\\\\${ip}`;
      navigator.clipboard?.writeText(unc);
      window.showToast?.(`Путь SMB ${unc} скопирован в буфер обмена`, 'info');
    };
  });
}

/**
 * Опрашивает открытые порты конкретного хоста и обновляет представление.
 * @param {string} ip
 * @param {HTMLElement} [btn]
 */
export async function probeHostPorts(ip, btn) {
  if (!ip) return;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
  }

  try {
    const res = await fetch(`/api/network/devices/probe?ip=${encodeURIComponent(ip)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    probedPortsMap.set(ip, data);
    renderDiscoveryTable();

    const openCount = data.open_ports?.length || 0;
    const msg = openCount > 0
      ? `Узел ${ip}: открыто портов: ${openCount} (${data.open_ports.join(', ')})`
      : `Узел ${ip}: стандартные порты (SMB, RDP, HTTP, SSH) закрыты`;
    window.showToast?.(msg, openCount > 0 ? 'success' : 'secondary');
  } catch (err) {
    console.error(`[LAN Discovery] Ошибка проверки портов ${ip}:`, err);
    window.showToast?.(`Ошибка опроса портов ${ip}: ${err.message}`, 'danger');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-lightning-charge"></i>';
    }
  }
}

/**
 * Открывает универсальное модальное окно AIModalDialog с диагностикой сетевого узла.
 * @param {string} ip
 */
export function openDeviceInAiModal(ip) {
  const dev = discoveredDevices.find((d) => d.ip === ip);
  if (!dev) return;

  if (typeof window !== 'undefined' && window.AIModalDialog) {
    const probed = probedPortsMap.get(ip);
    const portsList = probed?.open_ports?.length ? probed.open_ports.join(', ') : 'Не сканировались или закрыты';
    window.AIModalDialog.show({
      title: `Сетевой узел: ${dev.hostname || dev.ip}`,
      subtitle: `${dev.vendor || 'Производитель не определен'} (${dev.ip})`,
      icon: dev.is_gateway ? '🌐' : '🖥️',
      tableType: 'lan_device',
      badges: [
        { text: dev.is_gateway ? 'Шлюз (Gateway)' : (dev.is_local ? 'Этот компьютер' : 'Сетевой компьютер'), class: dev.is_gateway ? 'badge bg-warning text-dark' : 'badge bg-primary' },
        { text: dev.state || 'Online', class: 'badge bg-success' },
      ],
      metadata: [
        { label: 'IP-адрес', value: dev.ip },
        { label: 'Сетевое имя (Hostname)', value: dev.hostname || 'Не разрешено' },
        { label: 'MAC-адрес', value: dev.mac || 'Н/Д' },
        { label: 'Производитель (OUI)', value: dev.vendor || 'Не определен' },
        { label: 'Сетевой интерфейс', value: dev.interface_name || 'Авто' },
        { label: 'Задержка отклика (Ping)', value: dev.latency_ms !== null && dev.latency_ms !== undefined ? `${dev.latency_ms} ms` : 'Кеш ядра' },
        { label: 'Открытые службы', value: portsList },
        { label: 'Методы обнаружения', value: (dev.discovery_methods || []).join(', ') },
      ],
      rawTitle: 'Структура телеметрии сетевого устройства (JSON)',
      rawContent: JSON.stringify({ ...dev, probed_ports: probed }, null, 2),
      autoRun: false,
    });
  } else {
    alert(`Сетевой узел: ${dev.hostname || dev.ip}\nIP: ${dev.ip}\nMAC: ${dev.mac || 'Н/Д'}`);
  }
}

/**
 * Устанавливает текущий фильтр списка устройств.
 * @param {string} filter - 'all' | 'computer' | 'gateway' | 'mobile' | 'online'
 */
export function setDiscoveryFilter(filter) {
  activeFilter = filter || 'all';
  renderDiscoveryTable();
}

/**
 * Запускает периодическое фоновое автообновление таблицы компьютеров (каждые 30 секунд).
 */
export function startDiscoveryAutoRefresh() {
  if (autoRefreshTimer) return;
  autoRefreshTimer = setInterval(() => {
    const pane = document.getElementById('tab-net-discovery');
    const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
    if (!isActive) {
      stopDiscoveryAutoRefresh();
      return;
    }
    if (isAutoRefreshActive && !isScanning) {
      fetchDiscoveredDevices(false);
    }
  }, 30000);
}

/**
 * Останавливает таймер периодического фонового автообновления.
 */
export function stopDiscoveryAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

/**
 * Инициализирует модуль панели автоматического обнаружения компьютеров.
 */
export function loadDiscoveryData(force = false) {
  fetchSubnets();
  fetchWindowsDiscoveryStatus();
  fetchDiscoveredDevices(force);
  startDiscoveryAutoRefresh();
}

export function initDiscoveryPanel() {
  // Привязка управляющих кнопок
  const btnRefresh = document.getElementById('btn-refresh-discovery');
  const btnDeepScan = document.getElementById('btn-deep-scan-discovery');
  const searchInput = document.getElementById('net-discovery-filter');
  const subnetSelect = document.getElementById('net-discovery-subnet-select');
  const autoRefreshCheck = document.getElementById('check-discovery-autorefresh');

  if (btnRefresh) {
    btnRefresh.onclick = () => fetchDiscoveredDevices(false);
  }

  if (btnDeepScan) {
    btnDeepScan.onclick = () => fetchDiscoveredDevices(true);
  }

  if (searchInput) {
    searchInput.oninput = () => renderDiscoveryTable();
  }

  if (subnetSelect) {
    subnetSelect.onchange = () => fetchDiscoveredDevices(false);
  }

  if (autoRefreshCheck) {
    autoRefreshCheck.onchange = (e) => {
      isAutoRefreshActive = !!e.target.checked;
      if (isAutoRefreshActive) {
        startDiscoveryAutoRefresh();
      } else {
        stopDiscoveryAutoRefresh();
      }
    };
  }

  // Фильтры-кнопки
  document.querySelectorAll('.btn-filter-discovery').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('.btn-filter-discovery').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      setDiscoveryFilter(btn.getAttribute('data-filter') || 'all');
    };
  });
}
