/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - Engine and Targets Panel
 * =============================================================================
 * Description:
 *   Модуль проверки статуса DiskSpd и обнаружения целевых накопителей/разделов.
 *
 * File: panel_engine_targets/panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed/panel_engine_targets
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

let cachedTargets = [];

/**
 * Получение кешированного списка накопителей.
 * @returns {Array<Object>}
 */
export function getCachedTargets() {
  return cachedTargets;
}

/**
 * Проверка статуса утилиты DiskSpd.
 */
export async function checkEngineStatus() {
  try {
    const res = await fetch('/api/v1/storage/benchmark/engine');
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById('bench-engine-badge');
    if (badge) {
      if (data.available) {
        badge.className = 'badge bg-success-subtle text-success border border-success-subtle px-2 py-1';
        badge.innerHTML = '<i class="bi bi-check-circle-fill"></i> DiskSpd Ready';
      } else {
        badge.className = 'badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1';
        badge.innerHTML = '<i class="bi bi-exclamation-triangle"></i> DiskSpd не установлен';
      }
    }
  } catch (err) {
    console.debug('[DiskSpeed] Ошибка проверки движка:', err);
  }
}

/**
 * Загрузка списка доступных дисков и разделов.
 */
export async function loadTargets() {
  try {
    const res = await fetch('/api/v1/storage/benchmark/targets');
    if (!res.ok) return;
    cachedTargets = await res.json();

    const select = document.getElementById('bench-drive-select');
    if (!select) return;

    select.innerHTML = '';
    cachedTargets.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.drive_letter;
      const tag = t.is_system ? ' [Системный]' : '';
      opt.textContent = `${t.drive_letter} (${t.label || t.drive_letter})${tag} — ${t.free_gb} ГБ свободно`;
      select.appendChild(opt);
    });

    updateDriveDetails();
  } catch (err) {
    console.error('[DiskSpeed] Ошибка загрузки списка накопителей:', err);
  }
}

/**
 * Обновление информации о выбранном диске и пути безопасного файла.
 */
export function updateDriveDetails() {
  const select = document.getElementById('bench-drive-select');
  if (!select) return;
  const drive = select.value;
  const target = cachedTargets.find(t => t.drive_letter === drive);

  const fsEl = document.getElementById('bench-drive-fs');
  const freeEl = document.getElementById('bench-drive-free');
  const pathEl = document.getElementById('bench-safe-filepath');
  const summaryDisk = document.getElementById('bench-summary-disk');

  if (target) {
    if (fsEl) fsEl.textContent = `ФС: ${target.fs_type}`;
    if (freeEl) freeEl.textContent = `Свободно: ${target.free_gb} ГБ`;
    if (pathEl) pathEl.textContent = `${target.recommended_dir}\\diskspd-test.dat`;
    if (summaryDisk) summaryDisk.textContent = `${target.drive_letter} (${target.fs_type})`;
  }
}
