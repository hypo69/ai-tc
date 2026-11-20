/**
 * Вспомогательные утилиты интерфейса конфигуратора телеметрии.
 * Файл: apps/windows/api/webgui/tab_telemetry_config/common/ui_utils.js
 * Updated: 2026-11-20 16:45:00
 */

export const API_BASE = '/api/v1/windows/telemetry/config';

export const SENSOR_META = {
  cpu: { name: 'Процессор (CPU)', icon: 'bi-cpu', defaultInterval: 5.0, defaultMetrics: ['temperature', 'load', 'clocks'] },
  gpu: { name: 'Видеокарта (GPU)', icon: 'bi-gpu-card', defaultInterval: 10.0, defaultMetrics: ['temperature', 'load', 'memory', 'power'] },
  ram: { name: 'Оперативная память (RAM)', icon: 'bi-memory', defaultInterval: 10.0, defaultMetrics: ['usage', 'swap'] },
  disk: { name: 'Диски и разделы (Disk)', icon: 'bi-hdd', defaultInterval: 30.0, defaultMetrics: ['usage', 'io'] },
  network: { name: 'Сетевые адаптеры (Network)', icon: 'bi-ethernet', defaultInterval: 10.0, defaultMetrics: ['throughput', 'connections'] },
  sensors: { name: 'Сенсоры и вентиляторы', icon: 'bi-fan', defaultInterval: 10.0, defaultMetrics: ['temperature', 'fan', 'voltage'] },
  internet: { name: 'Скорость Fast.com / Latency', icon: 'bi-globe2', defaultInterval: 3600.0, defaultMetrics: ['ping', 'download', 'upload', 'bufferbloat', 'latency_loaded'] },
  storage: { name: 'SMART здоровье накопителей', icon: 'bi-hdd-network', defaultInterval: 32000.0, defaultMetrics: ['smart_attributes', 'temperature', 'wear_level'] },
  device_flapping: { name: 'Детектор PnP Flapping', icon: 'bi-usb-symbol', defaultInterval: 30.0, defaultMetrics: ['connect_events', 'disconnect_events', 'flapping_count'] },
};

export function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

export function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value : '';
}

export function setChecked(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = Boolean(val);
}

export function getChecked(id) {
  const el = document.getElementById(id);
  return el ? Boolean(el.checked) : false;
}

export function showAlert(msg, type = 'info', autoHideMs = 4000) {
  const alertBox = document.getElementById('tc-cfg-alert');
  const alertMsg = document.getElementById('tc-cfg-alert-msg');
  const alertIcon = document.getElementById('tc-cfg-alert-icon');
  if (!alertBox || !alertMsg) return;

  alertMsg.innerText = msg;
  alertBox.className = `alert alert-${type} alert-dismissible fade show mb-3 py-2 px-3 shadow-sm border`;

  if (alertIcon) {
    alertIcon.className =
      type === 'success' ? 'bi bi-check-circle-fill text-success fs-5' :
      type === 'danger' ? 'bi bi-exclamation-triangle-fill text-danger fs-5' :
      type === 'warning' ? 'bi bi-exclamation-circle-fill text-warning fs-5' :
      'bi bi-info-circle-fill text-info fs-5';
  }

  alertBox.classList.remove('d-none');

  if (autoHideMs > 0) {
    setTimeout(() => {
      if (!alertBox.classList.contains('d-none')) {
        alertBox.classList.add('d-none');
      }
    }, autoHideMs);
  }
}

export function showJsonError(msg) {
  const errBox = document.getElementById('tc-json-error');
  const errText = document.getElementById('tc-json-error-text');
  const statusBadge = document.getElementById('tc-json-status');
  if (errBox && errText) {
    errText.innerText = msg;
    errBox.classList.remove('d-none');
  }
  if (statusBadge) {
    statusBadge.innerText = 'Ошибка синтаксиса';
    statusBadge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle fs-8';
  }
}

export function hideJsonError() {
  const errBox = document.getElementById('tc-json-error');
  const statusBadge = document.getElementById('tc-json-status');
  if (errBox) errBox.classList.add('d-none');
  if (statusBadge) {
    statusBadge.innerText = 'Синтаксис корректен';
    statusBadge.className = 'badge bg-success-subtle text-success border border-success-subtle fs-8';
  }
}
