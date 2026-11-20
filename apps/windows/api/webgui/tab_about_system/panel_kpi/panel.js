/**
 * Модуль верхней полосы ключевых показателей эффективности (KPI) вкладки «О Системе».
 * 
 * Отображает агрегированные данные:
 * - Спецификацию и билд операционной системы Windows
 * - Статус безопасности (Defender, Real-Time Protection)
 * - Контрольные точки восстановления (Checkpoints / Restore Points)
 * - Накопители и сводную емкость дисков
 * 
 * Updated: 2026-11-12 12:40:00
 */

import { setText, setFormattedStatusHtml } from '../common/ui_utils.js';

/**
 * Применение объекта KPI к DOM элементам интерфейса.
 * 
 * @param {Object} kpi - Данные ключевых показателей.
 */
export function applyKpiData(kpi) {
  if (!kpi) return;
  if (kpi.os) {
    if (kpi.os.display_title) setText('about-kpi-os-title', kpi.os.display_title);
    if (kpi.os.display_host) setText('about-kpi-os-host', kpi.os.display_host);
    if (kpi.os.workgroup) setText('about-kpi-os-workgroup', `Workgroup: ${kpi.os.workgroup}`);
    else if (kpi.os.display_workgroup) setText('about-kpi-os-workgroup', kpi.os.display_workgroup);
    if (kpi.os.uptime_human) setText('about-spec-uptime', `Uptime: ${kpi.os.uptime_human}`);
    if (kpi.os.os_build) setText('about-spec-os', kpi.os.os_build);
    if (kpi.os.os_install_date) setText('about-ident-install-date', kpi.os.os_install_date);
  }
  if (kpi.security) {
    if (kpi.security.display_title) {
      const el = document.getElementById('about-kpi-sec-title');
      if (el) {
        el.textContent = kpi.security.display_title;
        el.className = `about-sys-value ${kpi.security.status === 'Active & Protected' ? 'text-success' : 'text-danger fw-bold'} text-truncate mt-1`;
      }
    }
    if (kpi.security.display_subtitle) setFormattedStatusHtml('about-kpi-sec-sub', kpi.security.display_subtitle);
  }
  if (kpi.checkpoints) {
    if (kpi.checkpoints.display_title) setText('about-kpi-prot-title', kpi.checkpoints.display_title);
    if (kpi.checkpoints.display_subtitle) setFormattedStatusHtml('about-kpi-prot-sub', kpi.checkpoints.display_subtitle);
  }
  if (kpi.storage) {
    if (kpi.storage.display_title) setText('about-kpi-stor-title', kpi.storage.display_title);
    if (kpi.storage.display_subtitle) setText('about-kpi-stor-clean', kpi.storage.display_subtitle);
    if (kpi.storage.volume_name) {
      const cardTitleEl = document.querySelector('#panel-about-storage .ui-kpi-label span');
      if (cardTitleEl) cardTitleEl.textContent = `Системный диск ${kpi.storage.volume_name} (C:)`;
    }
  }
}

/**
 * Опрос живой телеметрии или локальных часов.
 * @param {Function} updateClockFn
 */
export function pollLiveTelemetry(updateClockFn = () => {}) {
  if (typeof updateClockFn === 'function') {
    updateClockFn();
  }
}
