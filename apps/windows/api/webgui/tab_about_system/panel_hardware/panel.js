/**
 * Модуль дерева спецификации оборудования (Hardware Tree) и таблиц дисков/процессов.
 * 
 * Отображает:
 * - Иерархическое дерево компонентов оборудования (CPU, RAM, GPU, Материнская плата, Накопители)
 * - Сортировку по технической важности компонентов
 * - Таблицу дисковых разделов и таблицу запущенных процессов
 * 
 * Updated: 2026-10-30 11:15:00
 */

import { escapeHtml, apiFetch, formatStatusHtml } from '../common/ui_utils.js?v=20261018_v4';
import { getHardwareEnrichmentHtml, openHardwareComponentHistory, requestComponentProductionDate } from './enrichment.js?v=20261020_v6';
import { renderMonitorsSpec } from '../panel_identity/panel.js?v=20261030_v1';

let hardwareData = [];

export function getHardwareData() {
  return hardwareData;
}

export function getHardwareCategoryPriority(category) {
  const cat = (category || '').toLowerCase();
  if (cat.includes('processor') || cat.includes('cpu') || cat.includes('процессор')) return 10;
  if (cat.includes('motherboard') || cat.includes('mainboard') || cat.includes('плат') || cat.includes('чипсет') || cat.includes('chipset')) return 20;
  if (cat.includes('system memory') || cat.includes('память')) return 30;
  if (cat.includes('memory module') || cat.includes('ram') || cat.includes('планка')) return 35;
  if (cat.includes('display adapter') || cat.includes('gpu') || cat.includes('видеокарт') || cat.includes('видеоадаптер') || cat.includes('graphics')) return 40;
  if (cat.includes('monitors') || cat.includes('display') || cat.includes('монитор') || cat.includes('дисплей') || cat.includes('экран')) return 50;
  if (cat.includes('physical disk') || cat.includes('диск') || cat.includes('накопител')) return 60;
  if (cat.includes('storage volume') || cat.includes('том') || cat.includes('раздел')) return 70;
  if (cat.includes('system') || cat.includes('система') || cat.includes('bios') || cat.includes('tpm') || cat.includes('security')) return 80;
  if (cat.includes('network') || cat.includes('сетев') || cat.includes('ethernet') || cat.includes('wi-fi') || cat.includes('wifi')) return 90;
  if (cat.includes('audio') || cat.includes('sound') || cat.includes('звук')) return 100;
  if (cat.includes('bluetooth')) return 110;
  if (cat.includes('usb controller') || cat.includes('контроллер usb')) return 120;
  if (cat.includes('usb')) return 130;
  if (cat.includes('keyboard') || cat.includes('mouse') || cat.includes('клавиатур') || cat.includes('мышь') || cat.includes('pointing') || cat.includes('input')) return 140;
  if (cat.includes('printer') || cat.includes('imaging') || cat.includes('принтер') || cat.includes('сканер')) return 150;
  if (cat.includes('updates') || cat.includes('обновлен')) return 160;
  if (cat.includes('pnp') || cat.includes('plug') || cat.includes('устройства pnp')) return 170;
  return 200;
}

export function getNodeIcon(category) {
  const cat = (category || '').toLowerCase();
  if (cat.includes('processor') || cat.includes('cpu')) return 'bi bi-cpu';
  if (cat.includes('module') || cat.includes('планка')) return 'bi bi-memory';
  if (cat.includes('memory') || cat.includes('ram')) return 'bi bi-sd-card';
  if (cat.includes('system') || cat.includes('os')) return 'bi bi-laptop';
  if (cat.includes('motherboard') || cat.includes('mainboard')) return 'bi bi-motherboard';
  if (cat.includes('display') || cat.includes('gpu') || cat.includes('video') || cat.includes('graphics')) return 'bi bi-gpu-card';
  if (cat.includes('monitor') || cat.includes('screen') || cat.includes('экран')) return 'bi bi-display';
  if (cat.includes('physical') || cat.includes('диск')) return 'bi bi-hdd-fill';
  if (cat.includes('disk') || cat.includes('storage') || cat.includes('drive') || cat.includes('volume')) return 'bi bi-hdd-stack';
  if (cat.includes('network') || cat.includes('adapter') || cat.includes('ethernet') || cat.includes('wi-fi') || cat.includes('сеть')) return 'bi bi-ethernet';
  if (cat.includes('bluetooth')) return 'bi bi-bluetooth';
  if (cat.includes('keyboard') || cat.includes('клавиатур')) return 'bi bi-keyboard';
  if (cat.includes('mouse') || cat.includes('pointing') || cat.includes('мышь')) return 'bi bi-mouse';
  if (cat.includes('printer') || cat.includes('принтер')) return 'bi bi-printer';
  if (cat.includes('audio') || cat.includes('sound') || cat.includes('звук')) return 'bi bi-volume-up-fill';
  if (cat.includes('usb') || cat.includes('контроллер')) return 'bi bi-usb-symbol';
  if (cat.includes('update') || cat.includes('servicing')) return 'bi bi-arrow-repeat';
  if (cat.includes('security') || cat.includes('tpm') || cat.includes('защит')) return 'bi bi-shield-check';
  if (cat.includes('pnp') || cat.includes('plug')) return 'bi bi-hdd-network';
  return 'bi bi-gear-fill';
}

/**
 * Консолидирует разрозненные узлы pnp_device в единую группу «Устройства PnP».
 * @param {Array<Object>} nodes - Исходный массив узлов оборудования.
 * @returns {Array<Object>} Консолидированный массив узлов.
 */
export function consolidateHardwareNodes(nodes) {
  if (!Array.isArray(nodes)) return [];
  const pnpList = [];
  const otherNodes = [];

  for (const node of nodes) {
    const cat = (node.category || '').toLowerCase();
    if (cat === 'pnp_device' || cat === 'pnp' || cat === 'устройства pnp' || node.is_pnp_group) {
      if (node.devices && Array.isArray(node.devices)) {
        pnpList.push(...node.devices);
      } else if (node.children && Array.isArray(node.children) && node.children.length > 0) {
        pnpList.push(...node.children);
      } else {
        pnpList.push({
          name: node.name || 'PnP Device',
          component_key: node.component_key || '',
          device_class: node.properties?.['Класс'] || node.properties?.['Класс устройства'] || node.properties?.['Категория'] || 'Other',
          vendor: node.properties?.['Производитель'] || '',
          status: node.properties?.['Состояние'] || 'OK',
          health_status: node.properties?.['Здоровье'] || 'OK',
          install_date: node.properties?.['Дата установки'] || node.properties?.['Первая регистрация'] || '',
          device_id: node.properties?.['Идентификатор PnP'] || node.properties?.['Идентификатор устройства'] || node.component_key || '',
          properties: node.properties || {}
        });
      }
    } else {
      otherNodes.push(node);
    }
  }

  if (pnpList.length > 0) {
    const seenKeys = new Set();
    const uniqueDevices = [];
    for (const dev of pnpList) {
      const key = dev.device_id || dev.component_key || dev.name;
      if (!seenKeys.has(key)) {
        seenKeys.add(key);
        uniqueDevices.push(dev);
      }
    }

    const classCounts = {};
    let problemCount = 0;
    for (const dev of uniqueDevices) {
      const cls = dev.device_class || 'Other';
      classCounts[cls] = (classCounts[cls] || 0) + 1;
      const st = String(dev.status || '').toLowerCase();
      const hst = String(dev.health_status || '').toLowerCase();
      if (st.includes('problem') || st.includes('error') || hst.includes('problem')) {
        problemCount += 1;
      }
    }

    const topClasses = Object.entries(classCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([cls, cnt]) => `${cls} (${cnt})`)
      .join(', ');

    otherNodes.push({
      category: 'Устройства PnP',
      name: `Plug and Play (${uniqueDevices.length} устройств)`,
      component_key: 'pnp_device_group',
      properties: {
        'Всего PnP-устройств': `${uniqueDevices.length} шт.`,
        'Основные классы': topClasses || 'Различные',
        'Состояние': problemCount === 0 ? `Все исправны (${uniqueDevices.length})` : `${problemCount} с предупреждением`
      },
      devices: uniqueDevices,
      children: uniqueDevices,
      is_pnp_group: true,
      enrichment_status: 'completed'
    });
  }

  return otherNodes;
}

export function applyHardwareData(nodes) {
  const container = document.getElementById('about-sys-tree-container');
  const badgeCount = document.getElementById('about-sys-node-count');
  if (!container) return;

  const rawNodes = Array.isArray(nodes) ? nodes : [];
  hardwareData = consolidateHardwareNodes(rawNodes);

  if (badgeCount) {
    badgeCount.textContent = `${hardwareData.length} категорий`;
  }

  const searchInput = document.getElementById('about-sys-search');
  const filter = searchInput ? searchInput.value.trim().toLowerCase() : '';
  renderHardwareTree(hardwareData, filter);

  // Резервное наполнение строки мониторов в спецификации оборудования
  const monSpecEl = document.getElementById('about-spec-monitors');
  if (monSpecEl && (monSpecEl.textContent.includes('Опрос') || monSpecEl.textContent.trim() === '')) {
    const monNodes = rawNodes.filter(n => (n.category || '').toLowerCase().includes('monitor'));
    if (monNodes.length > 0) {
      const parsedMonitors = monNodes.map(mn => {
        const p = mn.properties || {};
        const resParts = (p['Разрешение экрана'] || '').split('x');
        const w = parseInt(resParts[0], 10) || 1920;
        const h = parseInt(resParts[1], 10) || 1080;
        const freq = parseInt((p['Частота развертки'] || '').replace('Hz', ''), 10) || 60;
        return {
          device: p['Устройство'] || '',
          name: p['Название дисплея (EDID)'] || mn.name || 'Дисплей',
          vendor: p['Производитель'] || '',
          adapter: p['Подключенный видеоадаптер'] || '',
          width: w,
          height: h,
          frequency_hz: freq,
          is_primary: (p['Основной монитор'] || '').includes('Основной'),
          orientation: p['Ориентация'] || (h > w ? 'вертикальная' : 'горизонтальная'),
        };
      });
      renderMonitorsSpec(parsedMonitors);
    }
  }
}

export function renderHardwareTree(nodes, filter) {
  const container = document.getElementById('about-sys-tree-container');
  if (!container) return;

  if (!Array.isArray(nodes) || nodes.length === 0) {
    container.innerHTML = '<div class="text-center py-4 text-muted small">Оборудование не обнаружено или опрашивается...</div>';
    return;
  }

  const filtered = nodes.filter(node => {
    if (!filter) return true;
    const catMatch = (node.category || '').toLowerCase().includes(filter);
    const nameMatch = (node.name || '').toLowerCase().includes(filter);
    const propsMatch = Object.entries(node.properties || {}).some(
      ([k, v]) => k.toLowerCase().includes(filter) || String(v).toLowerCase().includes(filter)
    );
    let devMatch = false;
    if (node.is_pnp_group && Array.isArray(node.devices)) {
      devMatch = node.devices.some(d =>
        (d.name || '').toLowerCase().includes(filter) ||
        (d.device_class || '').toLowerCase().includes(filter) ||
        (d.vendor || '').toLowerCase().includes(filter) ||
        (d.device_id || '').toLowerCase().includes(filter)
      );
    }
    return catMatch || nameMatch || propsMatch || devMatch;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div class="text-center py-4 text-muted small">По запросу «${escapeHtml(filter)}» компонентов не найдено</div>`;
    return;
  }

  filtered.sort((a, b) => {
    const prioA = getHardwareCategoryPriority(a.category);
    const prioB = getHardwareCategoryPriority(b.category);
    if (prioA !== prioB) return prioA - prioB;
    return String(a.name || '').localeCompare(String(b.name || ''));
  });

  container.innerHTML = filtered.map((node, idx) => {
    const propsEntries = Object.entries(node.properties || {});
    const propsHtml = propsEntries.length > 0
      ? `<div class="about-sys-spec-table-responsive">
          <table class="about-sys-spec-table">
            <tbody>
              ${propsEntries.map(([k, v]) => {
                const cleanKey = escapeHtml(k);
                const valStr = String(v ?? '');
                let valHtml = escapeHtml(valStr);

                if (cleanKey.includes('Номинальная частота')) {
                  valHtml = `<span class="ui-badge ui-badge-info">${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Текущая рабочая частота')) {
                  const isWarning = valStr.includes('⚠️') || valStr.includes('занижена');
                  if (isWarning) {
                    valHtml = `<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>${escapeHtml(valStr)}</span>`;
                  } else if (valStr && valStr !== 'N/A') {
                    valHtml = `<span class="ui-badge ui-badge-success">${escapeHtml(valStr)}</span>`;
                  }
                } else if (valStr.includes('⚠️') || valStr.includes('Потенциал не раскрыт') || valStr.includes('Узкое место')) {
                  valHtml = `<span class="ui-badge ui-badge-warning text-wrap text-start"><i class="bi bi-exclamation-triangle-fill me-1"></i>${escapeHtml(valStr.replace(/^⚠️\s*/, ''))}</span>`;
                } else if (valStr.includes('✅') || valStr.includes('Оптимально')) {
                  valHtml = `<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>${escapeHtml(valStr.replace(/^✅\s*/, ''))}</span>`;
                } else if (cleanKey.includes('Эффективность планки')) {
                  valHtml = `<span class="ui-badge ui-badge-info">${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Время наработки') || cleanKey.includes('Power-On Hours')) {
                  valHtml = `<span class="ui-badge ui-badge-info"><i class="bi bi-clock-history me-1"></i>${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Первый запуск')) {
                  valHtml = `<span class="ui-badge ui-badge-info"><i class="bi bi-calendar-event me-1"></i>${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Первая регистрация') || cleanKey.includes('Первая установка')) {
                  valHtml = `<span class="ui-badge ui-badge-neutral"><i class="bi bi-hdd-rack me-1"></i>${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Здоровье накопителя')) {
                  valHtml = `<span class="ui-badge ui-badge-success"><i class="bi bi-shield-check me-1"></i>${escapeHtml(valStr)}</span>`;
                } else if (cleanKey.includes('Температура накопителя')) {
                  valHtml = `<span class="ui-badge ui-badge-warning"><i class="bi bi-thermometer-half me-1"></i>${escapeHtml(valStr)}</span>`;
                } else if (typeof v === 'boolean' || valStr.toLowerCase() === 'true' || valStr.toLowerCase() === 'false') {
                  const bVal = typeof v === 'boolean' ? v : valStr.toLowerCase() === 'true';
                  valHtml = bVal
                    ? `<span class="text-success fw-bold"><i class="bi bi-check-circle me-1"></i>Да (Включено)</span>`
                    : `<span class="text-danger fw-bold"><i class="bi bi-x-circle me-1"></i>Нет (Отключено)</span>`;
                } else {
                  valHtml = formatStatusHtml(valStr);
                }

                return `
                  <tr>
                    <td class="about-sys-spec-key" style="width: 32%; min-width: 200px; max-width: 340px;">
                      ${cleanKey}
                    </td>
                    <td class="about-sys-spec-val font-monospace">
                      ${valHtml}
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>`
      : '<div class="text-muted small py-2 px-3">Свойства не указаны</div>';

    let pnpDevicesHtml = '';
    if (node.is_pnp_group && Array.isArray(node.devices) && node.devices.length > 0) {
      const devices = node.devices;
      const devRowsHtml = devices.map(d => {
        const isProblem = String(d.status || '').toLowerCase().includes('problem') || 
                          String(d.status || '').toLowerCase().includes('error') || 
                          String(d.health_status || '').toLowerCase().includes('problem');
        const searchBlob = `${d.name || ''} ${d.device_class || ''} ${d.vendor || ''} ${d.device_id || ''}`.toLowerCase();
        return `
          <tr data-pnp-search="${escapeHtml(searchBlob)}">
            <td class="ps-3 py-1.5" style="max-width: 320px;">
              <div class="fw-semibold text-truncate" title="${escapeHtml(d.name)}" style="color: var(--text-color);">${escapeHtml(d.name)}</div>
              <div class="text-muted text-truncate font-monospace" style="font-size: 0.70rem;" title="${escapeHtml(d.device_id || '')}">
                ${escapeHtml(d.vendor ? d.vendor + ' • ' : '')}${escapeHtml(d.device_id || '')}
              </div>
            </td>
            <td class="py-1.5">
              <span class="ui-badge ui-badge-neutral">${escapeHtml(d.device_class || 'Other')}</span>
            </td>
            <td class="py-1.5 font-monospace small text-muted">
              ${escapeHtml(d.install_date || '—')}
            </td>
            <td class="pe-3 py-1.5">
              ${isProblem 
                ? `<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>${escapeHtml(d.status || 'Problem')}</span>`
                : `<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>${escapeHtml(d.status || 'OK')}</span>`}
            </td>
          </tr>
        `;
      }).join('');

      pnpDevicesHtml = `
        <div class="p-3 border-top" style="border-color: var(--border-color) !important;">
          <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
            <div class="d-flex align-items-center gap-2 flex-grow-1" style="max-width: 360px;">
              <div class="input-group input-group-sm">
                <span class="input-group-text border-end-0" style="background: var(--surface-color); border-color: var(--border-color); color: var(--text-muted);">
                  <i class="bi bi-search"></i>
                </span>
                <input type="text" class="form-control border-start-0" 
                       placeholder="Фильтр в устройствах PnP..." 
                       style="background: var(--surface-color); color: var(--text-color); border-color: var(--border-color);"
                       oninput="window.filterPnpSubTable(${idx}, this.value)">
              </div>
            </div>
            <span class="ui-badge ui-badge-neutral font-monospace" id="about-sys-pnp-count-${idx}">
              Всего: ${devices.length}
            </span>
          </div>
          <div class="about-sys-spec-table-responsive" style="max-height: 440px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 6px;">
            <table class="table table-sm table-hover align-middle mb-0" style="color: var(--text-color);">
              <thead class="sticky-top" style="background: var(--surface-color); border-bottom: 2px solid var(--border-color); z-index: 2;">
                <tr>
                  <th class="ps-3" style="min-width: 220px;">Устройство</th>
                  <th style="width: 140px;">Класс</th>
                  <th style="width: 160px;">Дата установки</th>
                  <th class="pe-3" style="width: 120px;">Статус</th>
                </tr>
              </thead>
              <tbody id="about-sys-pnp-tbody-${idx}">
                ${devRowsHtml}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    const enrichHtml = getHardwareEnrichmentHtml(node);
    const iconClass = getNodeIcon(node.category);
    const isSearchActive = Boolean(filter);
    const bodyClass = isSearchActive ? 'about-sys-tree-body' : 'about-sys-tree-body d-none';
    const chevronChar = isSearchActive ? '▲' : '▼';
    const countBadgeText = node.is_pnp_group ? `${node.devices?.length || 0} устройств` : `${propsEntries.length} параметров`;

    return `
      <div class="about-sys-tree-node" data-component-key="${escapeHtml(node.component_key || '')}">
        <div class="about-sys-tree-title" onclick="window.toggleNode(${idx})">
          <span class="d-flex align-items-center gap-2 text-truncate me-2">
            <i class="${iconClass} text-info fs-6"></i>
            <strong style="color: var(--text-color);">${escapeHtml(node.category)}:</strong>
            <span style="color: var(--text-color); font-weight: 500;">${escapeHtml(node.name || '')}</span>
          </span>
          <div class="d-flex align-items-center gap-2 flex-shrink-0 ms-auto">
            <span class="ui-badge ui-badge-neutral font-monospace">${countBadgeText}</span>
            <span class="about-sys-chevron" id="about-chevron-${idx}">${chevronChar}</span>
          </div>
        </div>
        <div class="${bodyClass}" id="about-node-body-${idx}">
          <div class="about-sys-enrichment-slot">${enrichHtml}</div>
          ${propsHtml}
          ${pnpDevicesHtml}
        </div>
      </div>
    `;
  }).join('');
}

window.filterPnpSubTable = function(idx, query) {
  const tbody = document.getElementById(`about-sys-pnp-tbody-${idx}`);
  if (!tbody) return;
  const q = (query || '').toLowerCase().trim();
  const rows = tbody.querySelectorAll('tr[data-pnp-search]');
  let matched = 0;
  rows.forEach(row => {
    const text = row.getAttribute('data-pnp-search') || '';
    if (!q || text.includes(q)) {
      row.style.display = '';
      matched += 1;
    } else {
      row.style.display = 'none';
    }
  });
  const countEl = document.getElementById(`about-sys-pnp-count-${idx}`);
  if (countEl) {
    countEl.textContent = q ? `Найдено: ${matched} из ${rows.length}` : `Всего: ${rows.length}`;
  }
};

window.toggleNode = function(idx) {
  const body = document.getElementById(`about-node-body-${idx}`);
  const chevron = document.getElementById(`about-chevron-${idx}`);
  if (body) {
    body.classList.toggle('d-none');
    if (chevron) {
      chevron.textContent = body.classList.contains('d-none') ? '▼' : '▲';
    }
    const btnTreeToggle = document.getElementById('btn-about-sys-tree-toggle');
    if (btnTreeToggle) {
      const allBodies = document.querySelectorAll('.about-sys-tree-body');
      const hasHidden = Array.from(allBodies).some(b => b.classList.contains('d-none'));
      if (hasHidden) {
        btnTreeToggle.classList.add('collapsed');
        btnTreeToggle.title = '';
      } else {
        btnTreeToggle.classList.remove('collapsed');
        btnTreeToggle.title = '';
      }
    }
  }
};

window.openHardwareComponentHistory = openHardwareComponentHistory;
window.requestComponentProductionDate = (key) => requestComponentProductionDate(key, hardwareData);

export function renderDisksTable(disks) {
  const tbody = document.getElementById('about-sys-disks-tbody');
  const countBadge = document.getElementById('about-disks-count');
  if (!tbody) return;

  if (!Array.isArray(disks) || disks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted">Дисковые разделы не обнаружены</td></tr>';
    return;
  }

  if (countBadge) countBadge.textContent = `${disks.length} Drives`;

  tbody.innerHTML = disks.map(d => {
    const pct = Math.min(100, Math.max(0, Math.round(d.percent || 0)));
    let barClass = 'bg-info';
    if (pct > 88) barClass = 'bg-danger';
    else if (pct > 70) barClass = 'bg-warning';

    const driveLabel = escapeHtml(d.device || d.mountpoint || '-');
    const volName = d.volume_name ? `<span class="small text-muted ms-1">(${escapeHtml(d.volume_name)})</span>` : '';
    const totalGb = d.total_gb != null ? `${Number(d.total_gb).toFixed(1)} GB` : '-';
    const usedGb = d.used_gb != null ? `${Number(d.used_gb).toFixed(1)} GB` : '-';
    const freeGb = d.free_gb != null ? `${Number(d.free_gb).toFixed(1)} GB` : '-';
    const smartStatus = d.smart_status || 'OK';
    const sLower = String(smartStatus).toLowerCase();
    let smartBadgeClass = 'ui-badge-success';
    let smartIcon = 'bi-check-circle-fill';
    if (sLower.includes('bad') || sLower.includes('error') || sLower.includes('fail') || sLower.includes('problem')) {
      smartBadgeClass = 'ui-badge-danger';
      smartIcon = 'bi-x-circle-fill';
    } else if (sLower.includes('warn') || sLower.includes('caution')) {
      smartBadgeClass = 'ui-badge-warning';
      smartIcon = 'bi-exclamation-triangle-fill';
    }

    return `
      <tr>
        <td class="font-monospace fw-bold text-info">${driveLabel}${volName}</td>
        <td class="font-monospace">${escapeHtml(d.fstype || 'NTFS')}</td>
        <td class="font-monospace">${totalGb}</td>
        <td class="font-monospace text-warning">${usedGb}</td>
        <td class="font-monospace text-success">${freeGb}</td>
        <td>
          <div class="d-flex align-items-center gap-2">
            <div class="about-sys-progress-track flex-grow-1">
              <div class="about-sys-progress-bar ${barClass}" style="width: ${pct}%;"></div>
            </div>
            <span class="font-monospace small text-end" style="min-width: 38px;">${pct}%</span>
          </div>
        </td>
        <td><span class="ui-badge ${smartBadgeClass}"><i class="bi ${smartIcon} me-1"></i>${escapeHtml(smartStatus)}</span></td>
      </tr>
    `;
  }).join('');
}

export function renderProcessesTable(procs) {
  const tbody = document.getElementById('about-sys-procs-tbody');
  const countBadge = document.getElementById('about-procs-count');
  if (!tbody) return;

  if (!Array.isArray(procs) || procs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Процессы не обнаружены</td></tr>';
    return;
  }

  if (countBadge) countBadge.textContent = `${procs.length} Processes`;

  tbody.innerHTML = procs.map(p => {
    const pStatus = p.status || 'running';
    const isRunning = String(pStatus).toLowerCase() === 'running';
    const statusBadgeClass = isRunning
      ? 'badge bg-success-subtle text-success border border-success'
      : 'badge bg-secondary-subtle text-secondary border border-secondary';

    return `
      <tr>
        <td class="font-monospace text-muted">${p.pid || '-'}</td>
        <td class="fw-semibold text-truncate" style="max-width: 220px;" title="${escapeHtml(p.name)}">${escapeHtml(p.name || '-')}</td>
        <td class="font-monospace text-info">${Number(p.cpu_percent || 0).toFixed(1)}%</td>
        <td class="font-monospace text-warning">${Number(p.memory_percent || 0).toFixed(1)}%</td>
        <td class="font-monospace">${Number(p.memory_mb || 0).toFixed(0)} MB</td>
        <td><span class="${statusBadgeClass} font-monospace" style="font-size: 0.72rem;">${escapeHtml(pStatus)}</span></td>
      </tr>
    `;
  }).join('');
}

/**
 * Запрашивает дерево спецификации оборудования хоста.
 * @param {boolean} [forceRefresh=false]
 */
export async function fetchHardwareTree(forceRefresh = false) {
  try {
    const data = await apiFetch('/api/v1/system/hardware', { forceRefresh });
    if (data) {
      const nodes = Array.isArray(data) ? data : (data.hardware || data.hardware_tree || []);
      applyHardwareData(nodes);
    }
  } catch (err) {
    console.error('[HardwarePanel] fetchHardwareTree error:', err);
  }
}

/**
 * Привязывает события элементов управления дерева оборудования (поиск, сворачивание).
 */
export function bindHardwareEvents() {
  const searchInput = document.getElementById('about-sys-search');
  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener('input', () => {
      const filter = searchInput.value.trim().toLowerCase();
      renderHardwareTree(hardwareData, filter);
    });
  }

  const btnTreeToggle = document.getElementById('btn-about-sys-tree-toggle');
  if (btnTreeToggle && !btnTreeToggle._bound) {
    btnTreeToggle._bound = true;
    btnTreeToggle.addEventListener('click', () => {
      const isCollapsed = btnTreeToggle.classList.contains('collapsed');
      const allBodies = document.querySelectorAll('.about-sys-tree-body');
      allBodies.forEach(body => {
        if (isCollapsed) {
          body.classList.remove('d-none');
        } else {
          body.classList.add('d-none');
        }
      });
      const allChevrons = document.querySelectorAll('.about-sys-chevron, .about-sys-tree-header span[style*="cursor: pointer"]');
      allChevrons.forEach(ch => {
        ch.textContent = isCollapsed ? '▲' : '▼';
      });
      if (isCollapsed) {
        btnTreeToggle.classList.remove('collapsed');
        btnTreeToggle.title = '';
      } else {
        btnTreeToggle.classList.add('collapsed');
        btnTreeToggle.title = '';
      }
    });
  }
}
