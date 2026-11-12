/**
 * Корневой оркестратор вкладки «О системе» (About System).
 * Координирует работу панелей KPI, Identity, Hardware, AI Diagnostics, Regional/Network и History.
 * Запрашивает единый агрегированный срез данных через /api/v1/about-system/bundle
 * без отправки разрозненных сетевых запросов от каждой панели.
 * Файл: apps/windows/api/webgui/tab_about_system/main.js
 * Updated: 2026-11-11 21:24:00
 */

import { apiFetch, clearTabCache, showGlobalSpinner, setText } from './common/ui_utils.js?v=20261103_v1';
import { applyKpiData } from './panel_kpi/panel.js?v=20261103_v1';
import { applyIdentityData, applyControlStatusData, applyDisksWearData, applyStorageBatteryWearData, bindIdentityEvents, fetchSecurityHealth, fetchDisksWear, fetchStorageBatteryWear } from './panel_identity/panel.js?v=20261103_v1';
import { applyBatteryData, fetchBatteryWear, bindBatteryEvents } from './panel_battery/panel.js?v=20261103_v1';
import { applyHardwareData, bindHardwareEvents, fetchHardwareTree, renderDisksTable } from './panel_hardware/panel.js?v=20261111_v1';
import { openHardwareComponentHistory } from './panel_hardware/enrichment.js?v=20261103_v1';
import { initAIDiagnosticsPanel, runAIDiagnostics } from './panel_ai_diagnostics/panel.js?v=20261103_v1';
import { bindRegionalEvents, loadRegionalOptions, openRegionalModal } from './panel_regional_network/regional.js?v=20261103_v1';
import { fetchNetworkProfile, updateNetworkProfileUI, setNetworkInterfaceIndex } from './panel_regional_network/network.js?v=20261103_v1';
import { initHistoryPanel, fetchAboutSystemHistory } from './panel_history/panel.js?v=20261103_v1';

let clockInterval = null;
let isInitialized = false;

/**
 * Обновляет отображение локальных часов на странице хоста.
 */
function updateLocalClock() {
  const clockEl = document.getElementById('about-ident-time-badge') || document.getElementById('about-local-clock');
  if (!clockEl) return;
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  clockEl.textContent = `Локальное время: ${timeStr}`;
}

/**
 * Запрашивает сводные данные системы через единый bundle.
 * Сохранено для обратной совместимости вызовов.
 * @param {boolean} [forceRefresh=false] - Флаг принудительного обновления.
 */
async function fetchSystemSummary(forceRefresh = false) {
  return refreshAllData(forceRefresh);
}

/**
 * Применяет готовый пакет бандла данных хоста ко всем подсистемам без отправки отдельных сетевых запросов.
 * @param {Object} bundle - Единый пакет телеметрии от бэкенда.
 */
function applyBundleData(bundle) {
  if (!bundle) return;
  const summary = bundle.summary || bundle;

  // 0. KPI показатели и карточка идентичности хоста
  const kpiData = bundle.kpi || summary.kpi || summary;
  applyKpiData(kpiData);
  applyIdentityData(summary);

  // 1. Статус безопасности (Defender, Firewall, UAC)
  if (bundle.control_status) {
    applyControlStatusData(bundle.control_status);
  }

  // 2. Дерево спецификации оборудования (Full Hardware Specification Tree)
  const hwNodes = bundle.hardware_tree || bundle.hardware || summary.hardware || [];
  applyHardwareData(hwNodes);

  // 3. Износ накопителей SSD/NVMe (Disks Health & Wear Panel)
  const disksWear = bundle.disks_wear || (bundle.storage_battery && bundle.storage_battery.disks_wear) || (summary.storage_battery && summary.storage_battery.disks_wear) || [];
  applyDisksWearData(disksWear);

  // 4. Деградация и состояние батареи (Battery Deep Telemetry Panel)
  const batteryData = bundle.battery || bundle.battery_wear || (bundle.storage_battery && bundle.storage_battery.battery_wear) || (summary.storage_battery && summary.storage_battery.battery_wear) || summary.battery || {};
  applyBatteryData(batteryData);

  // 5. Обратная совместимость для комбинированного вызова
  const wearData = bundle.storage_battery || summary.storage_battery || bundle;
  applyStorageBatteryWearData(wearData);

  // 6. Дисковые разделы и тома (Storage Volumes & Partitions)
  const disks = summary.disks || bundle.disks || [];
  renderDisksTable(disks);

  // 7. Сетевой профиль и обнаружение (Network Profile & Discovery)
  if (bundle.network_profile) {
    const net = bundle.network_profile;
    const ifaceAlias = net.primary_interface_alias || (net.primary_interface_index ? `IF #${net.primary_interface_index}` : 'Ethernet');
    setNetworkInterfaceIndex(net.primary_interface_index || null);
    updateNetworkProfileUI(net.current_category, ifaceAlias, net.is_discovery_enabled);
  }
}

// Активный сетевой промис для дедупликации параллельных вызовов bundle
let inFlightBundlePromise = null;

/**
 * Полностью обновляет все данные на вкладке «О системе» через один запрос bundle.
 * Каждая отдельная панель изолирована от отправки собственных независимых запросов.
 * @param {boolean} [forceRefresh=false] - Принудительный сброс кеша.
 */
async function refreshAllData(forceRefresh = false) {
  if (inFlightBundlePromise && !forceRefresh) {
    return inFlightBundlePromise;
  }
  showGlobalSpinner(true);
  const promise = (async () => {
    try {
      if (forceRefresh) {
        clearTabCache();
      }
      const endpoint = forceRefresh ? '/api/v1/about-system/bundle?force=true' : '/api/v1/about-system/bundle';
      const bundle = await apiFetch(endpoint);
      if (bundle) {
        applyBundleData(bundle);
      }
      return bundle;
    } catch (err) {
      console.error('[AboutSystemTab] refreshAllData error:', err);
    } finally {
      showGlobalSpinner(false);
      if (inFlightBundlePromise === promise) {
        inFlightBundlePromise = null;
      }
    }
  })();
  inFlightBundlePromise = promise;
  return promise;
}

/**
 * Привязывает глобальные события к кнопкам и элементам управления вкладки.
 */
function bindGlobalEvents() {
  const btnRefresh = document.getElementById('btn-about-sys-refresh');
  if (btnRefresh) {
    btnRefresh.onclick = () => refreshAllData(true);
  }

  const btnAiLaunch = document.getElementById('btn-about-ai-launch-modal');
  if (btnAiLaunch) {
    btnAiLaunch.onclick = () => {
      const modalEl = document.getElementById('aboutAiDiagnosticsModal');
      if (modalEl && window.bootstrap && window.bootstrap.Modal) {
        const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
        runAIDiagnostics(false);
      }
    };
  }
}

/**
 * Точка входа инициализации вкладки «О системе».
 */
export function initAboutSystemTab() {
  if (isInitialized) {
    return;
  }
  isInitialized = true;

  updateLocalClock();
  if (clockInterval) clearInterval(clockInterval);
  clockInterval = setInterval(updateLocalClock, 1000);

  bindGlobalEvents();
  bindIdentityEvents();
  bindBatteryEvents();
  bindHardwareEvents();
  initAIDiagnosticsPanel();
  bindRegionalEvents({
    updateClock: updateLocalClock,
    refreshSummary: () => refreshAllData(true),
    refreshAll: () => refreshAllData(true),
  });
  initHistoryPanel();

  refreshAllData(false);
}

// Регистрация глобальных функций для обратной совместимости с хост-контейнером
window.initAboutSystemTab = initAboutSystemTab;
window.refreshAboutSystemData = refreshAllData;
window.applyAboutSystemBundle = applyBundleData;
window.openHardwareComponentHistory = openHardwareComponentHistory;
window.openRegionalSettingsModal = openRegionalModal;
window.openRegionalModal = openRegionalModal;
