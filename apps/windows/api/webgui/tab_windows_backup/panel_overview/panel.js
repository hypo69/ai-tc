/**
 * =============================================================================
 * Process Name: Windows Backup - Overview & File History Status Panel
 * =============================================================================
 * Description:
 *   Модуль общей сводки состояния резервного копирования: индекс готовности
 *   (Health Score), статус службы «История файлов» (File History), целевой путь,
 *   политика хранения и триггер немедленной архивации.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_windows_backup/panel_overview
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

/**
 * Загрузка отчета о состоянии безопасности и индекса готовности системы бэкапа.
 * @returns {Promise<void>}
 */
export async function loadHealthReport() {
  try {
    const res = await fetch('/api/v1/windows-backup/health');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const elHealth = document.getElementById('wb-val-health');
    const elBadge = document.getElementById('wb-badge-status');
    const elSub = document.getElementById('wb-sub-health');

    const score = data.health_score ?? 0;
    if (elHealth) elHealth.textContent = `${score} / 100`;
    if (elBadge) {
      elBadge.textContent = score >= 80 ? 'Готов' : score >= 50 ? 'Внимание' : 'Критично';
      elBadge.className = `badge bg-${score >= 80 ? 'success' : score >= 50 ? 'warning' : 'danger'}`;
    }
    if (elSub) {
      elSub.textContent = data.service_running ? 'Служба активна' : 'Служба остановлена';
    }

    const recList = document.getElementById('wb-recommendations-list');
    if (recList && Array.isArray(data.recommendations)) {
      if (data.recommendations.length === 0) {
        recList.innerHTML = '<li class="text-success small"><i class="bi bi-check-circle me-1"></i>Все проверки безопасности данных пройдены успешно.</li>';
      } else {
        recList.innerHTML = data.recommendations.map(r => `
          <li class="mb-1.5 text-warning d-flex align-items-start gap-1">
            <i class="bi bi-exclamation-triangle-fill text-warning flex-shrink-0 mt-0.5"></i>
            <span>${escapeHtml(r)}</span>
          </li>
        `).join('');
      }
    }
  } catch (e) {
    console.warn('[WindowsBackup] Error loading health:', e);
  }
}

/**
 * Загрузка конфигурации и состояния службы File History.
 * @returns {Promise<void>}
 */
export async function loadFileHistoryStatus() {
  try {
    const res = await fetch('/api/v1/windows-backup/file-history/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const elService = document.getElementById('wb-val-service');
    const elSubService = document.getElementById('wb-sub-service');
    const elTarget = document.getElementById('wb-fh-target');
    const elConfig = document.getElementById('wb-fh-config');
    const elInterval = document.getElementById('wb-fh-interval');
    const elRetention = document.getElementById('wb-fh-retention');
    const elLast = document.getElementById('wb-fh-last-backup');

    const isRunning = data.is_service_running;
    if (elService) {
      elService.textContent = isRunning ? 'Работает' : 'Остановлена';
      elService.className = `wb-card-value ${isRunning ? 'text-success' : 'text-danger'}`;
    }
    if (elSubService) {
      elSubService.textContent = `Запуск: ${data.service_start_type || 'Manual'}`;
    }

    const cfg = data.config;
    if (cfg) {
      if (elTarget) elTarget.textContent = cfg.target_path || cfg.target_url || 'Не настроено';
      if (elConfig) elConfig.textContent = cfg.config_file_path || 'Стандартный профиль';
      if (elInterval) elInterval.textContent = cfg.backup_interval_minutes ? `${cfg.backup_interval_minutes} мин.` : 'По умолчанию (1 ч)';
      if (elRetention) elRetention.textContent = cfg.retention_policy || 'Всегда';
      if (elLast) elLast.textContent = cfg.last_backup_time || 'Нет записей';
    } else {
      if (elTarget) elTarget.textContent = 'Конфигурация отсутствует';
      if (elConfig) elConfig.textContent = '—';
      if (elInterval) elInterval.textContent = '—';
      if (elRetention) elRetention.textContent = '—';
      if (elLast) elLast.textContent = '—';
    }
  } catch (e) {
    console.warn('[WindowsBackup] Error loading File History status:', e);
  }
}

/**
 * Запуск фонового процесса архивации File History.
 */
export async function triggerFileHistoryBackup() {
  const btnTrigger = document.getElementById('wb-btn-trigger-backup');
  if (!btnTrigger) return;

  btnTrigger.disabled = true;
  btnTrigger.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Запуск...';

  try {
    const res = await fetch('/api/v1/windows-backup/file-history/trigger', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      alert('Архивация File History успешно запущена: ' + (data.message || 'OK'));
    } else {
      alert('Ошибка запуска: ' + (data.detail || JSON.stringify(data)));
    }
  } catch (e) {
    alert('Сетевая ошибка при запуске архивации: ' + e.message);
  } finally {
    btnTrigger.disabled = false;
    btnTrigger.innerHTML = '<i class="bi bi-play-fill"></i> <span>Запустить бэкап</span>';
    if (typeof window.loadBackupData === 'function') {
      await window.loadBackupData();
    }
  }
}

/**
 * Привязка событий элементов сводной панели бэкапа.
 */
export function bindOverviewEvents() {
  const btnTrigger = document.getElementById('wb-btn-trigger-backup');
  if (btnTrigger && !btnTrigger._bound) {
    btnTrigger._bound = true;
    btnTrigger.onclick = triggerFileHistoryBackup;
  }
}
