/**
 * Модуль визуальной формы параметров телеметрии и таблицы сенсоров.
 * Файл: apps/windows/api/webgui/tab_telemetry_config/panel_form/panel.js
 * Updated: 2026-10-30 13:10:00
 */

import { setVal, getVal, setChecked, getChecked, SENSOR_META } from '../common/ui_utils.js';

/**
 * Отрисовывает значения конфигурации в полях GUI формы.
 * @param {Object} cfg - Объект конфигурации.
 */
export function renderGuiForm(cfg) {
  setVal('tc-field-telemetry-mode', cfg.telemetry_mode || 'telemetry');
  setVal('tc-field-standard-flush-interval', cfg.standard_flush_interval_seconds ?? 30.0);
  setVal('tc-field-tc-flush-interval', cfg.tc_flush_interval_seconds ?? 5.0);
  setVal('tc-field-tc-mode-timeout', cfg.tc_mode_timeout_seconds ?? 300.0);
  setVal('tc-field-max-db-size', cfg.max_db_size_mb ?? 100.0);

  setVal('tc-field-mode', cfg.mode || 'hybrid');
  setVal('tc-field-process-mode', cfg.process_mode || 'top_n');
  setVal('tc-field-interval', cfg.interval_seconds ?? 5.0);
  setVal('tc-field-heavy-interval', cfg.heavy_interval_seconds ?? 60.0);
  setVal('tc-field-top-processes', cfg.top_processes ?? 10);
  setVal('tc-field-agg-interval', cfg.aggregation_interval_seconds ?? 3600);
  setChecked('tc-field-low-priority', cfg.low_priority !== false);
  setChecked('tc-field-heavy-auto-switch', cfg.heavy_mode_auto_switch_enabled !== false);

  setVal('tc-field-retention-days', cfg.retention_days ?? 7);
  setVal('tc-field-history-retention', cfg.history_retention || 'forever');
  setVal('tc-field-db-cleanup-interval', cfg.db_cleanup_interval_seconds ?? 300.0);
  setVal('tc-field-flush-interval', cfg.flush_interval_seconds ?? 5.0);
  setVal('tc-field-buffer-mode', cfg.buffer_mode || 'memory');
  setVal('tc-field-buffer-size', cfg.buffer_size ?? 50);
  setChecked('tc-field-auto-vacuum', cfg.auto_vacuum_enabled !== false);

  const hc = cfg.heavy_collectors || {};
  setChecked('tc-hc-hw-sensors', hc.hardware_sensors !== false);
  setChecked('tc-hc-smart', hc.storage_smart !== false);
  setChecked('tc-hc-ping', hc.network_ping !== false);
  setChecked('tc-hc-wmi', hc.inventory_wmi === true);

  const w64 = cfg.w64_collector || {};
  setChecked('tc-w64-enabled', w64.enabled !== false);
  setChecked('tc-w64-file', w64.enable_file_monitoring !== false);
  setChecked('tc-w64-proc', w64.enable_process_monitoring !== false);
  setChecked('tc-w64-reg', w64.enable_registry_monitoring !== false);
  setChecked('tc-w64-net', w64.enable_network_monitoring !== false);
  setChecked('tc-w64-evlog', w64.enable_event_log_monitoring !== false);
  setChecked('tc-w64-etw-proc', w64.enable_process_trace !== false);
  setChecked('tc-w64-etw-disk', w64.enable_disk_trace !== false);

  renderSensorsTable(cfg.sensors || {});
}

/**
 * Отрисовывает таблицу сенсоров телеметрии.
 * @param {Object} sensorsConfig - Словарь настроек сенсоров.
 */
export function renderSensorsTable(sensorsConfig) {
  const tbody = document.getElementById('tc-sensors-tbody');
  if (!tbody) return;

  tbody.innerHTML = '';
  const sensorKeys = Object.keys(SENSOR_META);

  Object.keys(sensorsConfig).forEach((k) => {
    if (!sensorKeys.includes(k)) sensorKeys.push(k);
  });

  const countBadge = document.getElementById('tc-sensors-count-badge');
  if (countBadge) countBadge.innerText = `${sensorKeys.length} сенсоров`;

  sensorKeys.forEach((key) => {
    const sMeta = SENSOR_META[key] || {
      name: key,
      icon: 'bi-activity',
      defaultInterval: 10.0,
      defaultMetrics: [],
    };
    const sConf = sensorsConfig[key] || {
      enabled: true,
      interval_seconds: sMeta.defaultInterval,
      metrics: sMeta.defaultMetrics,
    };

    const tr = document.createElement('tr');
    tr.className = 'border-bottom border-secondary border-opacity-10';

    const isEnabled = sConf.enabled !== false;
    const intervalSec = sConf.interval_seconds ?? sMeta.defaultInterval;
    const metricsList = Array.isArray(sConf.metrics) ? sConf.metrics.join(', ') : '';

    tr.innerHTML = `
      <td class="text-center">
        <div class="form-check form-switch mb-0">
          <input class="form-check-input tc-sensor-enabled" type="checkbox" role="switch" data-sensor="${key}" ${isEnabled ? 'checked' : ''}>
        </div>
      </td>
      <td>
        <div class="d-flex align-items-center gap-2">
          <i class="bi ${sMeta.icon} text-info"></i>
          <div>
            <span class="fw-semibold text-white">${sMeta.name}</span>
            <span class="text-secondary d-block fs-9 font-monospace">${key}</span>
          </div>
        </div>
      </td>
      <td>
        <div class="input-group input-group-sm" style="max-width: 120px;">
          <input type="number" step="0.5" min="0.1" class="form-control form-control-sm bg-dark text-white border-secondary tc-sensor-interval" data-sensor="${key}" value="${intervalSec}">
          <span class="input-group-text bg-dark text-muted border-secondary fs-9">с</span>
        </div>
      </td>
      <td>
        <span class="text-secondary fs-9 font-monospace" title="${metricsList}">${metricsList || '—'}</span>
      </td>
    `;

    tbody.appendChild(tr);
  });
}

/**
 * Собирает значения из GUI формы в объект конфигурации.
 * @param {Object} baseConfig - Базовый объект конфигурации.
 * @returns {Object} Собранный объект конфигурации.
 */
export function gatherFormConfig(baseConfig = {}) {
  const cfg = JSON.parse(JSON.stringify(baseConfig));

  cfg.telemetry_mode = getVal('tc-field-telemetry-mode') || 'telemetry';
  cfg.standard_flush_interval_seconds = parseFloat(getVal('tc-field-standard-flush-interval')) || 30.0;
  cfg.tc_flush_interval_seconds = parseFloat(getVal('tc-field-tc-flush-interval')) || 5.0;
  cfg.tc_mode_timeout_seconds = parseFloat(getVal('tc-field-tc-mode-timeout')) || 300.0;
  cfg.max_db_size_mb = parseFloat(getVal('tc-field-max-db-size')) || 100.0;

  cfg.mode = getVal('tc-field-mode') || 'hybrid';
  cfg.process_mode = getVal('tc-field-process-mode') || 'top_n';
  cfg.interval_seconds = parseFloat(getVal('tc-field-interval')) || 5.0;
  cfg.heavy_interval_seconds = parseFloat(getVal('tc-field-heavy-interval')) || 60.0;
  cfg.top_processes = parseInt(getVal('tc-field-top-processes'), 10) || 10;
  cfg.aggregation_interval_seconds = parseInt(getVal('tc-field-agg-interval'), 10) || 3600;
  cfg.low_priority = getChecked('tc-field-low-priority');
  cfg.heavy_mode_auto_switch_enabled = getChecked('tc-field-heavy-auto-switch');

  cfg.retention_days = parseInt(getVal('tc-field-retention-days'), 10) || 7;
  cfg.history_retention = getVal('tc-field-history-retention') || 'forever';
  cfg.db_cleanup_interval_seconds = parseFloat(getVal('tc-field-db-cleanup-interval')) || 300.0;
  cfg.flush_interval_seconds = parseFloat(getVal('tc-field-flush-interval')) || 5.0;
  cfg.buffer_mode = getVal('tc-field-buffer-mode') || 'memory';
  cfg.buffer_size = parseInt(getVal('tc-field-buffer-size'), 10) || 50;
  cfg.auto_vacuum_enabled = getChecked('tc-field-auto-vacuum');

  cfg.heavy_collectors = cfg.heavy_collectors || {};
  cfg.heavy_collectors.hardware_sensors = getChecked('tc-hc-hw-sensors');
  cfg.heavy_collectors.storage_smart = getChecked('tc-hc-smart');
  cfg.heavy_collectors.network_ping = getChecked('tc-hc-ping');
  cfg.heavy_collectors.inventory_wmi = getChecked('tc-hc-wmi');

  cfg.w64_collector = cfg.w64_collector || {};
  cfg.w64_collector.enabled = getChecked('tc-w64-enabled');
  cfg.w64_collector.enable_file_monitoring = getChecked('tc-w64-file');
  cfg.w64_collector.enable_process_monitoring = getChecked('tc-w64-proc');
  cfg.w64_collector.enable_registry_monitoring = getChecked('tc-w64-reg');
  cfg.w64_collector.enable_network_monitoring = getChecked('tc-w64-net');
  cfg.w64_collector.enable_event_log_monitoring = getChecked('tc-w64-evlog');
  cfg.w64_collector.enable_process_trace = getChecked('tc-w64-etw-proc');
  cfg.w64_collector.enable_disk_trace = getChecked('tc-w64-etw-disk');

  cfg.sensors = cfg.sensors || {};
  document.querySelectorAll('.tc-sensor-enabled').forEach((cb) => {
    const sKey = cb.getAttribute('data-sensor');
    if (!sKey) return;
    cfg.sensors[sKey] = cfg.sensors[sKey] || {};
    cfg.sensors[sKey].enabled = cb.checked;
  });

  document.querySelectorAll('.tc-sensor-interval').forEach((inp) => {
    const sKey = inp.getAttribute('data-sensor');
    if (!sKey) return;
    cfg.sensors[sKey] = cfg.sensors[sKey] || {};
    cfg.sensors[sKey].interval_seconds = parseFloat(inp.value) || 5.0;
  });

  return cfg;
}
