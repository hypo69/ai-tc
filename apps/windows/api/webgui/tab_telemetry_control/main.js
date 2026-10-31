/**
 * =============================================================================
 * Process Name: Windows Telemetry Control Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления панелью конфигурации и контроля телеметрии:
 *   - Загрузка и сохранение параметров режима тщательного сбора (Thorough Mode)
 *   - Индивидуальные интервалы и тумблеры для каждого тяжелого сенсора
 *   - Запуск каскадного усреднения снимков на лету
 *   - Применение изменений в config.json через Hot Reload.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_telemetry_control
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 17:48:00
 * =============================================================================
 */

(function () {
  'use strict';

  let currentConfig = {};

  async function loadConfig() {
    try {
      const res = await fetch(`/api/windows/telemetry/config?v=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentConfig = data.config || {};
      const heavyIntervals = currentConfig.heavy_polls_intervals || {};
      const heavyCollectors = currentConfig.heavy_collectors || {};

      const pathEl = document.getElementById('tc-ctrl-config-path');
      if (pathEl) pathEl.textContent = data.config_path || 'config.json';

      const mtimeEl = document.getElementById('tc-ctrl-mtime');
      if (mtimeEl) mtimeEl.textContent = data.last_modified ? new Date(data.last_modified).toLocaleString() : 'Только что';

      // 1. Политика агрегации и режим тщательного сбора
      const thoroughSw = document.getElementById('tc-ctrl-thorough-mode');
      if (thoroughSw) thoroughSw.checked = currentConfig.thorough_mode === true;

      // 2. Базовые интервалы
      const fastInput = document.getElementById('tc-ctrl-fast-interval');
      if (fastInput) fastInput.value = currentConfig.interval_seconds || 5.0;

      const flushInput = document.getElementById('tc-ctrl-flush-interval');
      if (flushInput) flushInput.value = currentConfig.flush_interval_seconds || 5.0;

      const triggerModeSelect = document.getElementById('tc-ctrl-trigger-mode');
      if (triggerModeSelect) triggerModeSelect.value = currentConfig.trigger_mode || 'INTERVAL_BASED';

      const seqHeavySw = document.getElementById('tc-ctrl-sequential-heavy');
      if (seqHeavySw) seqHeavySw.checked = currentConfig.sequential_heavy_execution !== false;

      // 3. Процессы и белый список
      const topProcInput = document.getElementById('tc-ctrl-top-processes');
      if (topProcInput) topProcInput.value = currentConfig.top_processes || 10;

      const procModeSelect = document.getElementById('tc-ctrl-process-mode');
      if (procModeSelect) procModeSelect.value = currentConfig.process_mode || 'top_n';

      const whitelistArea = document.getElementById('tc-ctrl-whitelist');
      if (whitelistArea) {
        const wl = currentConfig.process_whitelist || [];
        whitelistArea.value = Array.isArray(wl) ? wl.join(', ') : '';
      }

      const fgSw = document.getElementById('tc-ctrl-fg-window');
      if (fgSw) fgSw.checked = currentConfig.enable_foreground_window !== false;

      // 4. Индивидуальные интервалы тяжелых сенсоров
      const setVal = (id, val, defVal) => {
        const el = document.getElementById(id);
        if (el) el.value = val !== undefined ? val : defVal;
      };
      setVal('tc-ctrl-hw-sensors-interval', heavyIntervals.hardware_audit_interval_sec, 60);
      setVal('tc-ctrl-ports-interval', heavyIntervals.network_ports_interval_sec, 30);
      setVal('tc-ctrl-net-activity-interval', heavyIntervals.network_activity_interval_sec, 30);
      setVal('tc-ctrl-leaks-interval', heavyIntervals.handles_interval_sec, 30);
      setVal('tc-ctrl-smart-interval', heavyIntervals.disk_scan_interval_sec || heavyIntervals.smart_interval_sec, 43200);
      setVal('tc-ctrl-startup-interval', heavyIntervals.startup_audit_interval_sec, 0);
      setVal('tc-ctrl-defender-interval', heavyIntervals.defender_audit_interval_sec, 120);
      setVal('tc-ctrl-software-interval', heavyIntervals.software_audit_interval_sec, 0);
      setVal('tc-ctrl-proc-activity-interval', heavyIntervals.process_activity_sync_interval_sec, 60);

      // 5. Индивидуальные тумблеры тяжелых сенсоров
      const setSw = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.checked = val !== false;
      };
      setSw('tc-ctrl-hw-sensors', heavyCollectors.hardware_sensors);
      setSw('tc-ctrl-ports', heavyCollectors.listening_ports !== undefined ? heavyCollectors.listening_ports : heavyCollectors.system_snapshot);
      setSw('tc-ctrl-net-activity', heavyCollectors.network_activity);
      setSw('tc-ctrl-leaks', heavyCollectors.process_leaks);
      setSw('tc-ctrl-smart', heavyCollectors.deep_disk_smart !== undefined ? heavyCollectors.deep_disk_smart : heavyCollectors.storage_smart);
      setSw('tc-ctrl-startup', heavyCollectors.startup_audit);
      setSw('tc-ctrl-defender', heavyCollectors.defender_audit);
      setSw('tc-ctrl-software', heavyCollectors.software_audit);
      setSw('tc-ctrl-proc-activity', heavyCollectors.process_activity);

    } catch (err) {
      console.warn('[TelemetryControl] Ошибка загрузки конфигурации:', err);
    }
  }

  async function saveConfig() {
    try {
      const getNum = (id, defVal) => parseFloat(document.getElementById(id)?.value || String(defVal));
      const getSw = (id, defVal = true) => document.getElementById(id)?.checked ?? defVal;

      const thoroughVal = getSw('tc-ctrl-thorough-mode', false);
      const fastVal = getNum('tc-ctrl-fast-interval', 5.0);
      const flushVal = getNum('tc-ctrl-flush-interval', 5.0);
      const triggerModeVal = document.getElementById('tc-ctrl-trigger-mode')?.value || 'INTERVAL_BASED';
      const seqHeavyVal = getSw('tc-ctrl-sequential-heavy', true);
      const topProcVal = parseInt(document.getElementById('tc-ctrl-top-processes')?.value || '10', 10);
      const procModeVal = document.getElementById('tc-ctrl-process-mode')?.value || 'top_n';

      const whitelistRaw = document.getElementById('tc-ctrl-whitelist')?.value || '';
      const whitelist = whitelistRaw.split(',').map(s => s.trim()).filter(Boolean);
      const enableFg = getSw('tc-ctrl-fg-window', true);

      // Значения интервалов матрицы тяжелых сенсоров
      const hwInterval = getNum('tc-ctrl-hw-sensors-interval', 60.0);
      const portsInterval = getNum('tc-ctrl-ports-interval', 30.0);
      const netActInterval = getNum('tc-ctrl-net-activity-interval', 30.0);
      const leaksInterval = getNum('tc-ctrl-leaks-interval', 30.0);
      const smartInterval = getNum('tc-ctrl-smart-interval', 43200.0);
      const startupInterval = getNum('tc-ctrl-startup-interval', 0.0);
      const defenderInterval = getNum('tc-ctrl-defender-interval', 120.0);
      const softwareInterval = getNum('tc-ctrl-software-interval', 0.0);
      const procActInterval = getNum('tc-ctrl-proc-activity-interval', 60.0);

      // Значения тумблеров матрицы тяжелых сенсоров
      const hwSensorsSw = getSw('tc-ctrl-hw-sensors', true);
      const portsSw = getSw('tc-ctrl-ports', true);
      const netActSw = getSw('tc-ctrl-net-activity', true);
      const leaksSw = getSw('tc-ctrl-leaks', true);
      const smartSw = getSw('tc-ctrl-smart', true);
      const startupSw = getSw('tc-ctrl-startup', true);
      const defenderSw = getSw('tc-ctrl-defender', true);
      const softwareSw = getSw('tc-ctrl-software', true);
      const procActSw = getSw('tc-ctrl-proc-activity', true);

      const updated = {
        ...currentConfig,
        thorough_mode: thoroughVal,
        interval_seconds: fastVal,
        light_poll_interval_seconds: fastVal,
        flush_interval_seconds: flushVal,
        trigger_mode: triggerModeVal,
        sequential_heavy_execution: seqHeavyVal,
        top_processes: topProcVal,
        process_mode: procModeVal,
        process_whitelist: whitelist,
        enable_foreground_window: enableFg,
        heavy_polls_intervals: {
          ...(currentConfig.heavy_polls_intervals || {}),
          hardware_audit_interval_sec: hwInterval,
          network_ports_interval_sec: portsInterval,
          network_activity_interval_sec: netActInterval,
          handles_interval_sec: leaksInterval,
          disk_scan_interval_sec: smartInterval,
          smart_interval_sec: smartInterval,
          startup_audit_interval_sec: startupInterval,
          defender_audit_interval_sec: defenderInterval,
          software_audit_interval_sec: softwareInterval,
          process_activity_sync_interval_sec: procActInterval,
        },
        heavy_collectors: {
          ...(currentConfig.heavy_collectors || {}),
          hardware_sensors: hwSensorsSw,
          listening_ports: portsSw,
          system_snapshot: portsSw,
          network_activity: netActSw,
          process_leaks: leaksSw,
          deep_disk_smart: smartSw,
          storage_smart: smartSw,
          startup_audit: startupSw,
          defender_audit: defenderSw,
          software_audit: softwareSw,
          process_activity: procActSw,
        }
      };

      const res = await fetch('/api/windows/telemetry/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: updated })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      currentConfig = updated;

      if (window.showToast) {
        window.showToast('Параметры и таймеры сенсоров успешно обновлены на лету (Hot Reload)', 'success');
      } else {
        alert('Параметры и таймеры сенсоров успешно обновлены (Hot Reload)');
      }

      await loadConfig();
    } catch (err) {
      console.error('[TelemetryControl] Ошибка сохранения:', err);
      if (window.showToast) {
        window.showToast('Ошибка сохранения конфигурации: ' + err.message, 'danger');
      } else {
        alert('Ошибка сохранения: ' + err.message);
      }
    }
  }

  async function runCascadeCompaction() {
    try {
      const btn = document.getElementById('tc-ctrl-btn-compact-now');
      if (btn) btn.disabled = true;
      const res = await fetch('/api/windows/telemetry/config/compact-now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const stats = data.stats || {};
      if (stats.skipped) {
        const msg = stats.reason === 'thorough_mode'
          ? 'Каскадное усреднение пропущено: активен режим тщательного сбора (все точки сохраняются)'
          : 'Каскадное усреднение пропущено';
        if (window.showToast) window.showToast(msg, 'warning');
        else alert(msg);
      } else {
        const s30 = stats.step_30s || {};
        const msg = `Каскадное усреднение выполнено! Создано 30с бакетов: ${s30.rollups_created || 0}, очищено сырых снимков: ${s30.snapshots_deleted || 0}`;
        if (window.showToast) window.showToast(msg, 'success');
        else alert(msg);
      }
    } catch (err) {
      console.error('[TelemetryControl] Ошибка каскадного усреднения:', err);
      if (window.showToast) window.showToast('Ошибка усреднения: ' + err.message, 'danger');
      else alert('Ошибка усреднения: ' + err.message);
    } finally {
      const btn = document.getElementById('tc-ctrl-btn-compact-now');
      if (btn) btn.disabled = false;
    }
  }

  async function runHeavySequentially() {
    try {
      const res = await fetch('/api/windows/telemetry/collect-heavy-sequentially', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collectors: ['wmi', 'smart', 'ports', 'handles'] })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const count = data.results?.length || 0;
      if (window.showToast) {
        window.showToast(`Последовательный сбор тяжелой телеметрии завершен (${count} коллекторов)`, 'success');
      } else {
        alert(`Последовательный сбор завершен (${count} коллекторов)`);
      }
    } catch (err) {
      console.error('[TelemetryControl] Ошибка последовательного сбора:', err);
      if (window.showToast) {
        window.showToast('Ошибка сбора: ' + err.message, 'danger');
      } else {
        alert('Ошибка: ' + err.message);
      }
    }
  }

  function initTelemetryControlTab() {
    loadConfig();

    const refreshBtn = document.getElementById('tc-ctrl-btn-refresh');
    if (refreshBtn) refreshBtn.addEventListener('click', loadConfig);

    const saveBtn = document.getElementById('tc-ctrl-btn-save');
    if (saveBtn) saveBtn.addEventListener('click', saveConfig);

    const runSeqBtn = document.getElementById('tc-ctrl-btn-run-heavy-seq');
    if (runSeqBtn) runSeqBtn.addEventListener('click', runHeavySequentially);

    const compactBtn = document.getElementById('tc-ctrl-btn-compact-now');
    if (compactBtn) compactBtn.addEventListener('click', runCascadeCompaction);
  }

  window.initTelemetryControlTab = initTelemetryControlTab;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTelemetryControlTab);
  } else {
    initTelemetryControlTab();
  }
})();
