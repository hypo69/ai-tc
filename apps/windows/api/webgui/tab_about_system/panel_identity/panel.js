/**
 * Модуль карточки идентификации системы, статуса резервного копирования, электропитания и параметров ОС.
 * 
 * Включает:
 * - Имя ПК, имя пользователя, локали, часовой пояс, раскладки клавиатуры
 * - Дата чистой установки Windows
 * - Статус службы истории файлов (Backup / File History) и контрольных точек
 * - Анализ износа накопителей (SMART, наработка POH, запись/чтение I/O)
 * - Телеметрию батареи и профилей электропитания
 * - Профили брандмауэра Windows Defender и статус UAC
 * 
 * Updated: 2026-11-03 14:05:00
 */

import { apiFetch, setText, setStatusText, setFormattedStatusHtml, formatStatusHtml, setHtml, escapeHtml } from '../common/ui_utils.js?v=20261028_v4';
import { applyBatteryData, fetchBatteryWear } from '../panel_battery/panel.js?v=20261028_v4';

/**
 * Форматирование коммерческого наименования процессора.
 * @param {string} rawModel - Сырое имя модели CPU.
 * @returns {string} Очищенное наименование.
 */
export function formatCpuCommercial(rawModel) {
  if (!rawModel) return 'Intel Core i5-10400';
  if (rawModel.includes('Family 6 Model 165') || rawModel.includes('Intel64 Family 6 Model 165')) {
    return 'Intel Core i5-10400';
  }
  let clean = rawModel
    .replace(/\(R\)/gi, '')
    .replace(/\(TM\)/gi, '')
    .replace(/\bCPU\b/gi, '')
    .replace(/@.*$/i, '')
    .replace(/\b\d+-Core Processor\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  return clean || 'Intel Core i5-10400';
}

/**
 * Применение сводных данных снимка системы (SystemSnapshot) к карточке идентификации.
 * @param {Object} snap - Объект SystemSnapshot.
 */
export function applySummaryData(snap) {
  if (!snap) return;
  try {
    const host = snap.hostname || 'DELL-VOSTRO';
    const userObj = snap.user || {};
    const user = userObj.username || snap.username || 'User';
    const fullName = userObj.full_name || snap.user_full_name || '';
    const jobTitle = userObj.description || userObj.title || snap.user_description || '';
    const userSid = userObj.sid || snap.user_sid || '';
    const profileDir = userObj.profile_dir || snap.user_profile || '';
    const userGroups = Array.isArray(userObj.groups)
      ? userObj.groups.join(', ')
      : (snap.user_groups ? [].concat(snap.user_groups).join(', ') : '');
    const userPrivilege = userObj.privilege || snap.user_privilege || '';

    const lang = snap.display_language || snap.system_language || 'Русский (Россия) [ru-RU]';
    const userLoc = snap.user_locale || 'ru-RU';
    const sysLoc = snap.system_locale || 'ru-RU';
    const instLang = snap.os_install_language || snap.install_language || 'Английский (English (United States)) [en-US]';
    const tz = snap.timezone || 'UTC+03:00';
    const cp = snap.codepage || 'UTF-8 (ACP: 65001)';
    const inputs = Array.isArray(snap.input_languages) && snap.input_languages.length > 0
      ? snap.input_languages.join(' • ')
      : '★ Русский [RU] • English [EN] • עברית [HE]';

    setText('about-ident-hostname', host);
    setText('about-ident-domain', `Workgroup / Host: ${host}`);

    if (fullName) {
      setText('about-ident-fullname', fullName);
      setText('about-ident-username', `@${user}`);
    } else {
      setText('about-ident-fullname', user);
      setText('about-ident-username', '');
    }

    const jobBadge = document.getElementById('about-ident-job-badge');
    const jobText = document.getElementById('about-ident-job-title');
    if (jobBadge && jobText) {
      if (jobTitle) {
        jobText.textContent = jobTitle;
        jobBadge.style.display = 'inline-flex';
      } else {
        jobBadge.style.display = 'none';
      }
    }

    if (userPrivilege) {
      setText('about-ident-privilege', userPrivilege);
      const privBadge = document.getElementById('about-ident-privilege-badge');
      if (privBadge) {
        const isAdmin = userObj.is_admin || snap.user_is_admin || userPrivilege.toLowerCase().includes('админ') || userPrivilege.toLowerCase().includes('admin');
        privBadge.className = `badge ${isAdmin ? 'bg-success-subtle text-success border border-success' : 'bg-secondary-subtle text-body border border-secondary'} border-opacity-25`;
      }
    }

    if (profileDir) setText('about-ident-user-profile', profileDir);

    // SID пользователя
    const sidBox = document.getElementById('about-ident-user-sid-box');
    if (sidBox) {
      if (userSid) {
        sidBox.classList.remove('d-none');
        setText('about-ident-user-sid', userSid);
      } else {
        sidBox.classList.add('d-none');
      }
    } else if (userSid) {
      setText('about-ident-user-sid', userSid);
    }

    // Отображение групп пользователя аккуратными чипами
    const groupsContainer = document.getElementById('about-ident-user-groups-chips');
    let groupsList = [];
    if (Array.isArray(userObj.groups) && userObj.groups.length > 0) {
      groupsList = userObj.groups;
    } else if (Array.isArray(snap.user_groups) && snap.user_groups.length > 0) {
      groupsList = snap.user_groups;
    } else if (typeof userGroups === 'string' && userGroups.trim()) {
      groupsList = userGroups.split(',').map(s => s.trim()).filter(Boolean);
    }

    if (groupsContainer) {
      if (groupsList.length > 0) {
        groupsContainer.innerHTML = groupsList.map(grp => {
          const cleanName = grp.includes('\\') ? grp.split('\\').pop() : grp;
          return `<span class="badge bg-secondary-subtle text-body border border-secondary border-opacity-25 font-monospace px-1.5 py-0.5" title="${escapeHtml(grp)}">${escapeHtml(cleanName)}</span>`;
        }).join('');
      } else {
        groupsContainer.innerHTML = '<span class="text-muted fst-italic">Нет записей</span>';
      }
    }
    if (userGroups) setText('about-ident-user-groups', `Группы: ${userGroups}`);

    setText('about-ident-language', lang);
    setText('about-ident-os-install-lang', instLang);
    const localesText = `Локали: User: ${userLoc} | Sys: ${sysLoc}`;
    setText('about-ident-locales', localesText);

    // Защита от поврежденных кодировок со знаками '???'
    let cleanTz = tz;
    if (!cleanTz || cleanTz.includes('???')) {
      try {
        const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        cleanTz = browserTz ? `${browserTz} (UTC+03:00)` : 'Israel Standard Time (UTC+03:00)';
      } catch (_) {
        cleanTz = 'Israel Standard Time (UTC+03:00)';
      }
    }
    setText('about-ident-timezone', cleanTz);
    setText('about-ident-codepage', `Кодировка: ${cp}`);
    setText('about-ident-inputs', inputs);
    const osInstallDate = snap.os_install_date || snap.install_date || (snap.os && snap.os.os_install_date) || '';
    setText('about-ident-install-date', osInstallDate || 'Не определена');

    setText('about-kpi-os-title', `${snap.os_name || 'Windows 11'} (${snap.cpu?.architecture || 'AMD64'})`);
    setText('about-kpi-os-host', `Host: ${host}`);
    setText('about-kpi-os-workgroup', `Workgroup: ${snap.workgroup || 'WORKGROUP'}`);

    if (snap.cpu) {
      setText('about-spec-cpu', formatCpuCommercial(snap.cpu.model));
    }

    if (snap.memory) {
      const total = Number(snap.memory.total_gb || 0).toFixed(1);
      const used = Number(snap.memory.used_gb || 0).toFixed(1);
      const avail = Number(snap.memory.available_gb || 0).toFixed(1);
      const pct = snap.memory.percent || 0;
      setText('about-spec-ram', `${total} GB RAM`);
      setText('about-telemetry-ram-val', `${used} / ${total} GB`);
      setText('about-telemetry-ram-sub', `${pct}% занято (${avail} GB свободно)`);
      const ramBar = document.getElementById('about-telemetry-ram-bar');
      if (ramBar) {
        ramBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
      }
    }

    if (Array.isArray(snap.monitors)) {
      renderMonitorsSpec(snap.monitors);
    }

    if (snap.office) {
      if (snap.office.installed) {
        setHtml('about-ident-ms-office', `<span class="text-success fw-bold">${escapeHtml(snap.office.edition || 'Установлен')}</span>`);
      } else {
        setHtml('about-ident-ms-office', `<span class="text-muted">Не установлен</span>`);
      }
    }

    if (snap.onedrive) {
      const odStatus = snap.onedrive.status || (snap.onedrive.installed ? 'Работает' : 'Не настроено');
      setHtml('about-ident-onedrive', formatStatusHtml(odStatus));
    }
  } catch (err) {
    console.warn('[AboutSystemTab:Identity] applySummaryData error:', err);
  }
}

/**
 * Отрисовка списка подключенных мониторов и дисплеев в спецификации оборудования.
 * Корректно форматирует множественные дисплеи с указанием основного экрана,
 * разрешения, частоты обновления, ориентации и видеоадаптера.
 * @param {Array<Object>} monitors - Список мониторов из базы данных.
 */
export function renderMonitorsSpec(monitors) {
  const container = document.getElementById('about-spec-monitors');
  if (!container) return;

  // Фильтруем фиктивные виртуальные дисплеи Session 0 (WinDisc)
  const validMonitors = (Array.isArray(monitors) ? monitors : []).filter(m => {
    if (!m) return false;
    const dev = String(m.device || '').toLowerCase();
    const name = String(m.name || '').toLowerCase();
    return !dev.includes('windisc') && !name.includes('windisc');
  });

  if (validMonitors.length === 0) {
    container.innerHTML = '<span class="text-muted">Мониторы не обнаружены</span>';
    return;
  }

  // Сортируем: сначала основной монитор, затем остальные по имени устройства
  const sorted = [...validMonitors].sort((a, b) => {
    if (a.is_primary && !b.is_primary) return -1;
    if (!a.is_primary && b.is_primary) return 1;
    return String(a.device || '').localeCompare(String(b.device || ''));
  });

  const html = sorted.map((m, idx) => {
    const isPrimary = Boolean(m.is_primary);
    let displayName = m.name || m.model || 'Дисплей';
    if (m.vendor && !displayName.toLowerCase().includes(m.vendor.toLowerCase())) {
      displayName = `${m.vendor} ${displayName}`;
    }
    const monName = escapeHtml(displayName);
    const width = m.width || 1920;
    const height = m.height || 1080;
    const freq = m.frequency_hz ? `${m.frequency_hz} Hz` : '';
    const resText = freq ? `${width}×${height} @ ${freq}` : `${width}×${height}`;
    const orientation = String(m.orientation || (height > width ? 'вертикальная' : 'горизонтальная')).toLowerCase();
    const isVertical = orientation.includes('вертикаль') || orientation.includes('портрет') || height > width;

    // Метка основного / дополнительного дисплея
    const devTitle = m.device ? ` [${escapeHtml(m.device)}]` : '';
    const badgeDisplay = isPrimary
      ? `<span class="ui-badge ui-badge-info font-monospace" title="Основной системный дисплей${devTitle}">${idx + 1} • Основной</span>`
      : `<span class="ui-badge ui-badge-neutral font-monospace" title="Дополнительный дисплей${devTitle}">${idx + 1}</span>`;

    // Метка ориентации (для каждого дисплея: альбомная или портретная)
    const orientBadge = isVertical
      ? `<span class="ui-badge ui-badge-neutral font-monospace" title="Портретная (вертикальная) ориентация"><i class="bi bi-phone me-1"></i>Портретная</span>`
      : `<span class="ui-badge ui-badge-neutral font-monospace" title="Альбомная (горизонтальная) ориентация"><i class="bi bi-display me-1"></i>Альбомная</span>`;

    // Подключенный GPU
    const adapterHtml = m.adapter
      ? `<span class="text-muted font-monospace small ms-1" title="Видеоадаптер: ${escapeHtml(m.adapter)}"><i class="bi bi-gpu-card me-1"></i>${escapeHtml(m.adapter)}</span>`
      : '';

    // Серийный номер
    const snHtml = m.serial_number && String(m.serial_number).trim() !== '' && String(m.serial_number).trim() !== '0'
      ? `<span class="text-muted font-monospace small ms-1" title="Серийный номер: ${escapeHtml(m.serial_number)}"><i class="bi bi-upc-scan me-1"></i>S/N: ${escapeHtml(m.serial_number)}</span>`
      : '';

    // Дата производства / Service Tag
    const prodDateHtml = m.production_date && String(m.production_date).trim() !== ''
      ? `<span class="ui-badge ui-badge-neutral font-monospace ms-1" style="font-size: 0.72rem;" title="Дата производства / Service Tag"><i class="bi bi-calendar-event me-1"></i>${escapeHtml(m.production_date)}</span>`
      : '';

    return `
      <div class="d-flex align-items-center gap-2.5 flex-wrap py-0.5">
        ${badgeDisplay}
        <strong class="text-body">${monName}</strong>
        <span class="text-info font-monospace small ms-1">${resText}</span>
        ${orientBadge}
        ${adapterHtml}
        ${snHtml}
        ${prodDateHtml}
      </div>
    `;
  }).join('');

  container.innerHTML = `<div class="d-flex flex-column gap-1">${html}</div>`;
}

/**
 * Применение статуса резервного копирования.
 * @param {Object} data
 */
export function applyBackupStatusData(data) {
  if (!data) return;
  try {
    const cfg = data.file_history?.config;
    const storage = data.storage_audit;

    let lastTimeStr = 'Нет записей';
    if (cfg && cfg.last_backup_time) {
      try {
        const d = new Date(cfg.last_backup_time);
        if (!isNaN(d.getTime())) {
          lastTimeStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
      } catch (_) {}
    } else if (storage && storage.sample_versions && storage.sample_versions.length > 0) {
      const latestSample = storage.sample_versions[0];
      if (latestSample && latestSample.version_timestamp) {
        try {
          const d = new Date(latestSample.version_timestamp);
          if (!isNaN(d.getTime())) {
            lastTimeStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          }
        } catch (_) {}
      }
    }

    let storageStr = '';
    if (storage && storage.target_exists && storage.free_space_gb !== null && storage.free_space_gb !== undefined) {
      const target = storage.target_path || 'Диск';
      const freeGb = typeof storage.free_space_gb === 'number' ? storage.free_space_gb.toFixed(1) : storage.free_space_gb;
      storageStr = `${target} (${freeGb} GB своб.)`;
    } else if (cfg && (cfg.target_drive_letter || cfg.target_url)) {
      storageStr = cfg.target_drive_letter || cfg.target_url;
    } else {
      storageStr = 'Хранилище не найдено';
    }

    const backupEl = document.getElementById('about-ident-backup');
    if (backupEl) {
      const isConfigured = Boolean(lastTimeStr && lastTimeStr !== 'Нет записей');
      backupEl.innerHTML = isConfigured
        ? `<span class="text-success fw-bold">${escapeHtml(lastTimeStr)}</span> <span class="text-muted font-monospace">| ${escapeHtml(storageStr)}</span>`
        : `<span class="text-muted">Не настроено</span>`;
      backupEl.title = `Последний бэкап: ${lastTimeStr}\nХранилище: ${storageStr}\nСлужба File History: ${data.file_history?.service_status || '—'}\nHealth Score: ${data.health_score ?? '--'}/100`;
    }
  } catch (e) {
    console.warn('[AboutSystemTab] applyBackupStatusData warning:', e);
    setHtml('about-ident-backup', '<span class="text-muted">Не настроено</span>');
  }
}

/**
 * Обновление панели питания и профиля схемы энергопотребления.
 * @param {Object} [batteryWear]
 * @param {string} [powerProfileName]
 */
export function updatePowerDisplay(batteryWear = null, powerProfileName = '') {
  const badgeEl = document.getElementById('about-spec-power-badge');
  const sourceEl = document.getElementById('about-spec-power-source');
  const profileEl = document.getElementById('about-spec-power-profile');
  const legacyEl = document.getElementById('about-spec-power');

  let badgeText = 'AC Mains';
  let badgeClass = 'bg-secondary';
  let sourceText = 'Питание: Стационарная электросеть 220V';
  let profileText = powerProfileName ? `Профиль: ${powerProfileName}` : 'Профиль: AC Mains / Desktop';

  if (batteryWear) {
    if (batteryWear.has_battery) {
      badgeText = batteryWear.is_charging ? 'AC Adapter' : 'Battery';
      badgeClass = batteryWear.is_charging ? 'bg-success' : (batteryWear.percent < 20 ? 'bg-danger' : 'bg-warning');
      sourceText = `Батарея: ${batteryWear.percent}% (${batteryWear.is_charging ? 'Заряжается' : 'Работа от батареи'})`;
    } else {
      badgeText = batteryWear.power_source ? (batteryWear.power_source.includes('AC') ? 'AC Mains' : batteryWear.power_source) : 'AC Mains';
      badgeClass = 'bg-secondary';
      sourceText = 'Питание: Стационарная электросеть 220V';
    }
  }

  if (badgeEl) {
    badgeEl.textContent = badgeText;
    badgeEl.className = `badge ${badgeClass} font-monospace`;
  }
  if (sourceEl) {
    sourceEl.textContent = sourceText;
  }
  if (profileEl) {
    if (powerProfileName) {
      profileEl.textContent = `Профиль: ${powerProfileName}`;
    } else if (!profileEl.textContent || profileEl.textContent.trim() === '' || profileEl.textContent === 'Профиль: --') {
      profileEl.textContent = profileText;
    }
  }
  if (legacyEl) {
    legacyEl.textContent = `${sourceText} | ${profileText}`;
  }
}

/**
 * Применение данных износа физических накопителей SSD/NVMe.
 * @param {Object|Array} data - Пакет данных с полем disks_wear или массив дисков.
 */
export function applyDisksWearData(data) {
  if (!data) return;
  try {
    const disksList = Array.isArray(data) ? data : (data.disks_wear || []);
    const disksTbody = document.getElementById('diag-wear-disks-tbody');
    if (disksTbody) {
      setText('diag-wear-disks-count', `${disksList.length} дисков`);
      if (disksList.length === 0) {
        disksTbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">Физических накопителей не обнаружено</td></tr>';
      } else {
        const formatBytesLocal = (bytes) => {
          if (bytes == null || bytes === 0) return '0 B';
          const k = 1024;
          const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
          const i = Math.floor(Math.log(bytes) / Math.log(k));
          return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
        };

        const formatPohLocal = (hours, formatted) => {
          if (formatted && formatted !== '—') return formatted;
          if (typeof hours === 'string' && hours.includes('ч')) return hours;
          if (hours == null || isNaN(hours) || Number(hours) <= 0) return null;
          const h = Number(hours);
          const days = Math.floor(h / 24);
          const years = (h / (24 * 365.25)).toFixed(1);
          if (days >= 365) return `${h.toLocaleString()} ч (≈ ${years} г)`;
          if (days >= 1) return `${h.toLocaleString()} ч (${days} д)`;
          return `${h.toLocaleString()} ч`;
        };

        disksTbody.innerHTML = disksList.map(d => {
          const diskName = d.name || d.model || d.device_id || 'Физический диск';
          const devId = d.device_id ? `<span class="badge bg-secondary-subtle text-body border border-secondary me-1.5">${escapeHtml(d.device_id)}</span>` : '';
          const isSsd = (d.media_type && d.media_type.toUpperCase().includes('SSD')) || (d.bus_type && d.bus_type.toUpperCase().includes('NVME'));
          const diskIcon = isSsd ? 'bi-device-ssd text-info' : 'bi-hdd text-primary';
          const typeBus = [d.media_type, d.bus_type].filter(Boolean).join(' / ') || 'Storage';
          const partsBadge = d.partitions && d.partitions !== '—'
            ? `<span class="badge bg-primary-subtle text-info border border-info-subtle font-monospace">${escapeHtml(d.partitions)}</span>`
            : '';
          const freeGbStr = (d.free_gb != null && !isNaN(Number(d.free_gb)))
            ? `${Number(d.free_gb).toFixed(1)} GB`
            : '<span class="text-muted">—</span>';
          const healthPct = d.health_pct != null ? d.health_pct : 100;
          const healthColor = healthPct >= 80 ? 'success' : (healthPct >= 50 ? 'warning' : 'danger');

          let pohFormatted = formatPohLocal(d.power_on_hours, d.power_on_hours_formatted);
          const startStr = d.first_power_on ? `Старт: ${escapeHtml(d.first_power_on)}` : '';
          let pohHtml = '<span class="text-muted font-monospace small">—</span>';
          if (pohFormatted && startStr) {
            pohHtml = `<div class="font-monospace text-info">${pohFormatted}</div><div class="small text-muted font-monospace mt-0.5">${startStr}</div>`;
          } else if (pohFormatted) {
            pohHtml = `<div class="font-monospace text-info">${pohFormatted}</div>`;
          } else if (startStr) {
            pohHtml = `<div class="small text-muted font-monospace">${startStr}</div>`;
          }

          const ioHtml = `
            <div class="font-monospace text-body" style="white-space: nowrap;">
              <i class="bi bi-arrow-up-circle text-warning me-1"></i>Запись: ${formatBytesLocal(d.bytes_written)}
            </div>
            <div class="small font-monospace text-info mt-0.5" style="white-space: nowrap;">
              <i class="bi bi-arrow-down-circle text-info me-1"></i>Чтение: ${formatBytesLocal(d.bytes_read)}
            </div>
          `;

          return `
            <tr>
              <td class="fw-bold text-body">
                <div class="d-flex align-items-center">
                  <i class="bi ${diskIcon} me-2 fs-6"></i>
                  <div>
                    <div class="text-truncate" style="max-width: 250px;" title="${escapeHtml(diskName)}">${escapeHtml(diskName)}</div>
                    <div class="small text-muted font-monospace mt-0.5">${devId}${d.serial_number && d.serial_number !== 'N/A' ? `<span class="text-secondary">S/N: ${escapeHtml(d.serial_number)}</span>` : ''}</div>
                  </div>
                </div>
              </td>
              <td class="text-muted font-monospace"><span class="badge bg-secondary-subtle text-body border border-secondary">${escapeHtml(typeBus)}</span></td>
              <td>${partsBadge}</td>
              <td style="text-align: right;" class="text-body font-monospace">${d.total_gb} GB</td>
              <td style="text-align: right;" class="text-success font-monospace">${freeGbStr}</td>
              <td>${pohHtml}</td>
              <td style="text-align: right;">${ioHtml}</td>
              <td>
                <div class="d-flex align-items-center gap-1.5">
                  <div class="about-sys-progress-track flex-grow-1" style="height: 6px; min-width: 55px;">
                    <div class="about-sys-progress-bar bg-${healthColor}" style="width: ${healthPct}%;"></div>
                  </div>
                  <span class="small font-monospace text-${healthColor} ms-1">${healthPct}%</span>
                </div>
              </td>
              <td><span class="badge bg-${healthColor}-subtle text-${healthColor} border border-${healthColor}">${escapeHtml(d.status || 'OK')}</span></td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.warn('[AboutSystemTab] applyDisksWearData error:', err);
  }
}

/**
 * Применение комбинированных данных износа дисков и батареи (обратная совместимость).
 * @param {Object} data
 */
export function applyStorageBatteryWearData(data) {
  if (!data) return;
  applyDisksWearData(data);
  const bat = data.battery_wear || data.battery;
  if (bat) {
    applyBatteryData(bat);
  }
}

/**
 * Применение статуса безопасности и системного управления.
 * @param {Object} res
 */
export function applyControlStatusData(res) {
  if (!res) return;
  try {
    const isElevated = res.is_elevated;
    const privBadge = document.getElementById('about-sys-privilege-badge');
    if (privBadge) {
      if (isElevated) {
        privBadge.className = 'badge rounded-pill bg-success-subtle text-success border border-success px-2.5 py-1';
        privBadge.textContent = '🛡️ Administrator Access';
      } else {
        privBadge.className = 'badge rounded-pill bg-secondary-subtle text-secondary border border-secondary px-2.5 py-1';
        privBadge.textContent = '👁️ Standard User Mode';
      }
    }
    setText('about-ident-privilege', isElevated ? 'Права: Администратор (Full Access)' : 'Права: Стандартный пользователь');

    const sec = res.security || {};
    const rest = res.restore || {};
    const pwr = res.power || {};
    const upd = res.update || {};

    const defActive = sec.defender_enabled !== false;
    const kpiSecTitle = document.getElementById('about-kpi-sec-title');
    if (kpiSecTitle) {
      kpiSecTitle.textContent = defActive ? 'Active & Protected' : 'Attention Required';
      kpiSecTitle.className = `about-sys-value ${defActive ? 'text-success' : 'text-danger fw-bold'} text-truncate mt-1`;
    }
    const fwOk = sec.firewall_overall_enabled !== false;
    const uacOk = sec.uac_enabled !== false;
    setFormattedStatusHtml('about-kpi-sec-sub', `Firewall: ${fwOk ? 'ON' : 'OFF'} | UAC: ${uacOk ? 'ON' : 'OFF'}`);

    const countPoints = rest.restore_points_count || 0;
    setText('about-kpi-prot-title', `${countPoints} Checkpoints`);
    const protActive = Boolean(rest.system_protection_enabled);
    setFormattedStatusHtml('about-kpi-prot-sub', `Protection: ${protActive ? 'Active' : 'Disabled'}`);

    setStatusText('about-sec-defender', defActive, 'Включен', 'Отключен');
    setStatusText('about-sec-realtime', sec.realtime_protection_enabled !== false && sec.realtime_protection_enabled !== 0 && sec.realtime_protection_enabled !== 'Disabled', 'Включен', 'Отключен');
    
    const fwDom = sec.firewall_profiles?.Domain ?? sec.firewall_domain_enabled;
    const fwPriv = sec.firewall_profiles?.Private ?? sec.firewall_private_enabled;
    const fwPub = sec.firewall_profiles?.Public ?? sec.firewall_public_enabled;

    setStatusText('about-sec-fw-domain', fwDom === true || fwDom === 'Active' || fwDom === 1 || fwDom === 'ON', 'Активен', 'Отключен');
    setStatusText('about-sec-fw-private', fwPriv === true || fwPriv === 'Active' || fwPriv === 1 || fwPriv === 'ON', 'Активен', 'Отключен');
    setStatusText('about-sec-fw-public', fwPub === true || fwPub === 'Active' || fwPub === 1 || fwPub === 'ON', 'Активен', 'Отключен');
    setStatusText('about-sec-uac', uacOk, 'Включен', 'Отключен');

    if (pwr.active_plan_name) {
      updatePowerDisplay(null, pwr.active_plan_name);
    }
    if (upd.status) {
      const kbCount = upd.recent_hotfixes_count ? ` (${upd.recent_hotfixes_count} KBs installed)` : '';
      const updTxt = `${upd.status}${kbCount}`;
      setFormattedStatusHtml('about-spec-update', updTxt);
      setFormattedStatusHtml('about-ident-updates', updTxt);
    }
  } catch (e) {
    console.warn('[AboutSystemTab] applyControlStatusData warning:', e);
  }
}

/**
 * Алиас для функции применения данных сводки/идентификации.
 */
export { applySummaryData as applyIdentityData };

/**
 * Получение состояния безопасности и контрольных точек системы.
 */
export async function fetchSecurityHealth() {
  try {
    const res = await apiFetch('/api/v1/system/control/status');
    if (res) applyControlStatusData(res);
  } catch (e) {
    console.warn('[AboutSystemTab] fetchSecurityHealth error:', e);
  }
}

/**
 * Запрашивает независимые данные износа физических накопителей из telemetry.db.
 * @param {boolean} [forceRefresh=false]
 */
export async function fetchDisksWear(forceRefresh = false) {
  try {
    const data = await apiFetch('/api/v1/system/diagnostics/storage-wear', { forceRefresh });
    if (data) {
      applyDisksWearData(data);
    }
    return data;
  } catch (err) {
    console.warn('[AboutSystemTab] fetchDisksWear error:', err);
    return null;
  }
}

/**
 * Запрашивает данные износа физических дисков и батареи (комбинированный вызов).
 * @param {boolean} [forceRefresh=false]
 */
export async function fetchStorageBatteryWear(forceRefresh = false) {
  try {
    await Promise.all([
      fetchDisksWear(forceRefresh),
      fetchBatteryWear(forceRefresh),
    ]);
  } catch (err) {
    console.warn('[AboutSystemTab] fetchStorageBatteryWear error:', err);
  }
}

/**
 * Привязка событий интерактивных элементов карточки Identity и износа накопителей.
 */
export function bindIdentityEvents() {
  const btnDisksRefresh = document.getElementById('btn-diag-disks-wear-refresh') || document.getElementById('btn-diag-wear-refresh');
  if (btnDisksRefresh && !btnDisksRefresh._bound) {
    btnDisksRefresh._bound = true;
    btnDisksRefresh.addEventListener('click', async () => {
      const origHtml = btnDisksRefresh.innerHTML;
      btnDisksRefresh.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Опрос...';
      btnDisksRefresh.disabled = true;
      try {
        if (typeof window.refreshAboutSystemData === 'function') {
          await window.refreshAboutSystemData(true);
        } else {
          await fetchDisksWear(true);
        }
      } finally {
        btnDisksRefresh.innerHTML = origHtml;
        btnDisksRefresh.disabled = false;
      }
    });
  }
}
