/**
 * =============================================================================
 * Название: Панель управления драйвером User Choice Protection Driver (UCPD)
 * =============================================================================
 * Описание:
 *   Инженерный модуль аудита и управления системным драйвером UCPD и задачей
 *   планировщика UcpdVelocity в Windows 11 с контролем восстановления исходной
 *   конфигурации, диагностикой перезагрузки и тестированием связи с TaskbarDa.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_ucpd/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-01 14:40:00
 * =============================================================================
 */

import { escapeHtml, safeApiFetch } from '../common/ui_utils.js';

let ucpdStatusCache = null;

/**
 * Инициализация панели UCPD при активации вкладки или переключении.
 */
export async function initUcpdPanel() {
  bindUcpdEvents();
  await loadUcpdStatus();
}

/**
 * Привязка обработчиков событий элементов управления панели UCPD.
 */
export function bindUcpdEvents() {
  const refreshBtn = document.getElementById('winadmin-ucpd-btn-refresh');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      await loadUcpdStatus();
      refreshBtn.disabled = false;
    });
  }

  // Кнопка переключения состояния (Toggle)
  const toggleBtn = document.getElementById('winadmin-ucpd-btn-toggle');
  if (toggleBtn && !toggleBtn.dataset.bound) {
    toggleBtn.dataset.bound = 'true';
    toggleBtn.addEventListener('click', handleUcpdToggleClick);
  }

  // Кнопка запуска эксперимента TaskbarDa
  const testTaskbarBtn = document.getElementById('winadmin-ucpd-btn-test-taskbarda');
  if (testTaskbarBtn && !testTaskbarBtn.dataset.bound) {
    testTaskbarBtn.dataset.bound = 'true';
    testTaskbarBtn.addEventListener('click', handleRunTaskbarDaExperiment);
  }

  // Чекбокс управления фоновой задачей планировщика
  const taskManageCheckbox = document.getElementById('winadmin-ucpd-checkbox-manage-task');
  if (taskManageCheckbox && !taskManageCheckbox.dataset.bound) {
    taskManageCheckbox.dataset.bound = 'true';
  }
}

/**
 * Загрузка согласованного статуса драйвера UCPD, задачи и ядра.
 */
export async function loadUcpdStatus() {
  appendUcpdLog('Запрос согласованного статуса UCPD и задачи UcpdVelocity...');
  try {
    const data = await safeApiFetch('/api/kernel-protection/ucpd/status');
    ucpdStatusCache = data;
    renderUcpdStatus(data);
    appendUcpdLog(`Статус получен: ${data.status_label_ru} (${data.windows_version})`);
  } catch (err) {
    appendUcpdLog(`Ошибка загрузки статуса UCPD: ${err.message}`);
    console.error('[UCPD Panel] Ошибка:', err);
  }
}

/**
 * Отрисовка элементов интерфейса на основе полученного статуса.
 * @param {Object} data - Объект UcpdFullStatus.
 */
export function renderUcpdStatus(data) {
  // 1. Заголовочный бейдж и ОС
  const mainBadge = document.getElementById('winadmin-ucpd-main-badge');
  const osVerEl = document.getElementById('winadmin-ucpd-os-ver');
  const toggleBtn = document.getElementById('winadmin-ucpd-btn-toggle');

  if (osVerEl) osVerEl.textContent = data.windows_version || 'Windows 11';

  let badgeClass = 'ui-badge ui-badge-success';
  let isCurrentlyActive = (data.overall_state === 'enabled');

  if (data.overall_state === 'disabled') {
    badgeClass = 'ui-badge ui-badge-neutral';
  } else if (data.overall_state === 'reboot_pending') {
    badgeClass = 'ui-badge ui-badge-warning';
  } else if (data.overall_state === 'partially_disabled') {
    badgeClass = 'ui-badge ui-badge-warning';
  }

  if (mainBadge) {
    mainBadge.className = badgeClass;
    mainBadge.textContent = data.status_label_ru;
  }

  // Обновление кнопки действия
  if (toggleBtn) {
    if (data.overall_state === 'disabled') {
      toggleBtn.className = 'btn btn-sm btn-outline-success d-flex align-items-center gap-1.5';
      toggleBtn.innerHTML = '<i class="bi bi-play-circle-fill"></i> <span>Восстановить исходную защиту UCPD</span>';
      toggleBtn.setAttribute('data-target-state', 'enabled');
    } else {
      toggleBtn.className = 'btn btn-sm btn-outline-danger d-flex align-items-center gap-1.5';
      toggleBtn.innerHTML = '<i class="bi bi-pause-circle-fill"></i> <span>Временно деактивировать UCPD</span>';
      toggleBtn.setAttribute('data-target-state', 'disabled');
    }
  }

  // 2. Драйвер в ядре (Driver Card)
  const drvStartEl = document.getElementById('winadmin-ucpd-drv-start');
  const drvStateEl = document.getElementById('winadmin-ucpd-drv-state');
  const drvAltEl = document.getElementById('winadmin-ucpd-drv-altitude');
  const drvInstEl = document.getElementById('winadmin-ucpd-drv-instances');

  if (drvStartEl) {
    drvStartEl.textContent = `${data.driver.start_type_name.toUpperCase()} (Код ${data.driver.start_type})`;
    drvStartEl.className = data.driver.start_type === 4 ? 'text-secondary fw-semibold' : 'text-primary fw-semibold';
  }
  if (drvStateEl) {
    drvStateEl.textContent = data.driver.is_running ? 'ВЫПОЛНЯЕТСЯ (Running)' : 'ОСТАНОВЛЕН (Stopped)';
    drvStateEl.className = data.driver.is_running ? 'text-success fw-semibold' : 'text-danger fw-semibold';
  }
  if (drvAltEl) {
    drvAltEl.textContent = data.driver.altitude ? `${data.driver.altitude} (fltmc)` : 'Не загружен';
  }
  if (drvInstEl) {
    drvInstEl.textContent = `${data.driver.instances_count} томов`;
  }

  // 3. Фоновая задача планировщика UcpdVelocity
  const taskStateEl = document.getElementById('winadmin-ucpd-task-state');
  const taskNameEl = document.getElementById('winadmin-ucpd-task-name');

  if (taskStateEl) {
    const isEn = data.task.is_enabled;
    taskStateEl.textContent = `${data.task.state} (${isEn ? 'Активна' : 'Отключена'})`;
    taskStateEl.className = isEn ? 'text-warning fw-semibold' : 'text-secondary fw-semibold';
  }
  if (taskNameEl) {
    taskNameEl.textContent = `${data.task.task_path}${data.task.task_name}`;
  }

  // 4. Баннер требования перезагрузки
  const rebootAlert = document.getElementById('winadmin-ucpd-reboot-alert');
  const rebootReasonEl = document.getElementById('winadmin-ucpd-reboot-reason');
  if (rebootAlert && rebootReasonEl) {
    if (data.reboot.reboot_required) {
      rebootAlert.classList.remove('d-none');
      rebootReasonEl.textContent = data.reboot.reason_ru;
    } else {
      rebootAlert.classList.add('d-none');
    }
  }

  // 5. Баннер дрейфа конфигурации (Windows Update Drift)
  const driftAlert = document.getElementById('winadmin-ucpd-drift-alert');
  const driftMsgEl = document.getElementById('winadmin-ucpd-drift-msg');
  if (driftAlert && driftMsgEl) {
    if (data.last_audit_drift) {
      driftAlert.classList.remove('d-none');
      driftMsgEl.textContent = data.last_audit_drift;
    } else {
      driftAlert.classList.add('d-none');
    }
  }

  // 6. Исходная конфигурация в бэкапе
  const backupBox = document.getElementById('winadmin-ucpd-backup-info');
  if (backupBox) {
    if (data.backup_config) {
      const b = data.backup_config;
      backupBox.innerHTML = `
        <div class="small text-secondary">
          <div>Исходный режим старта: <strong>${escapeHtml(b.original_start_name || '')} (${b.original_start_type})</strong></div>
          <div>Желаемое состояние: <strong>${escapeHtml(b.user_intent || '')}</strong> | Время: <strong>${escapeHtml(b.updated_at || '')}</strong></div>
        </div>
      `;
    } else {
      backupBox.innerHTML = '<div class="small text-secondary">Исходная конфигурация не сохранялась (штатное состояние ОС)</div>';
    }
  }
}

/**
 * Обработчик переключения UCPD с предупреждением безопасности.
 */
async function handleUcpdToggleClick() {
  const toggleBtn = document.getElementById('winadmin-ucpd-btn-toggle');
  const targetState = toggleBtn?.getAttribute('data-target-state') || 'disabled';
  const manageTask = document.getElementById('winadmin-ucpd-checkbox-manage-task')?.checked ?? true;

  if (targetState === 'disabled') {
    const confirmed = confirm(
      '⚠️ ПРЕДУПРЕЖДЕНИЕ БЕЗОПАСНОСТИ WINDOWS 11:\n\n' +
      'Отключение драйвера UCPD временно снимает системную защиту от изменения ассоциаций браузера по умолчанию и типов файлов (.pdf, .html).\n' +
      'Это позволит изменять параметры реестра, однако снижает изоляцию пользовательских предпочтений.\n\n' +
      'Вы подтверждаете деактивацию UCPD?'
    );
    if (!confirmed) {
      appendUcpdLog('Отключение UCPD отменено пользователем.');
      return;
    }
  }

  appendUcpdLog(`Применение состояния: ${targetState.toUpperCase()} (управление задачей: ${manageTask})...`);
  if (toggleBtn) toggleBtn.disabled = true;

  try {
    const res = await safeApiFetch('/api/kernel-protection/ucpd/set-state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_state: targetState,
        manage_scheduled_task: manageTask,
        confirm_security_risk: true
      })
    });

    if (res.partial_success) {
      appendUcpdLog(`[ВНИМАНИЕ] ${res.message}`);
      if (res.warnings && res.warnings.length > 0) {
        res.warnings.forEach(w => appendUcpdLog(`  -> Предупреждение: ${w}`));
      }
      alert(`⚠️ ЧАСТИЧНЫЙ РЕЗУЛЬТАТ:\n${res.message}\n\nПроверьте журнал для деталей.`);
    } else if (res.success) {
      appendUcpdLog(`[УСПЕХ] ${res.message}`);
    } else {
      appendUcpdLog(`[ОТКЛОНЕНО] ${res.message}`);
      alert(`Ошибка: ${res.message}`);
    }

    await loadUcpdStatus();
  } catch (err) {
    appendUcpdLog(`[СБОЙ API] ${err.message}`);
    alert(`Ошибка запроса к API: ${err.message}`);
  } finally {
    if (toggleBtn) toggleBtn.disabled = false;
  }
}

/**
 * Запуск эмпирического эксперимента с TaskbarDa.
 */
async function handleRunTaskbarDaExperiment() {
  const btn = document.getElementById('winadmin-ucpd-btn-test-taskbarda');
  const resultBox = document.getElementById('winadmin-ucpd-taskbarda-result');

  if (btn) btn.disabled = true;
  appendUcpdLog('Запуск экспериментальной проверки блокировки TaskbarDa в реестре...');

  if (resultBox) {
    resultBox.innerHTML = '<div class="text-secondary small"><span class="spinner-border spinner-border-sm me-1"></span>Выполнение тестовой записи в HKCU...Advanced\\TaskbarDa...</div>';
  }

  try {
    const res = await safeApiFetch('/api/kernel-protection/ucpd/test-taskbarda', {
      method: 'POST'
    });

    appendUcpdLog(`Результат теста TaskbarDa: ${res.is_blocked ? 'БЛОКИРУЕТСЯ (Access Denied)' : 'ДОСТУПНО ДЛЯ ЗАПИСИ'}`);

    if (resultBox) {
      const badgeClass = res.is_blocked ? 'ui-badge ui-badge-danger' : 'ui-badge ui-badge-success';
      const statusText = res.is_blocked ? 'БЛОКИРОВКА ЗАФИКСИРОВАНА' : 'ЗАПИСЬ РАЗРЕШЕНА';

      resultBox.innerHTML = `
        <div class="border rounded p-2.5 mt-2 border-secondary border-opacity-25">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-semibold small">Результат на текущей сборке:</span>
            <span class="${badgeClass} small">${statusText}</span>
          </div>
          <div class="small text-secondary mb-1">${escapeHtml(res.conclusion_ru)}</div>
          ${res.error_message ? `<div class="font-monospace text-danger small">${escapeHtml(res.error_message)}</div>` : ''}
          <div class="small text-muted mt-1">Текущее значение TaskbarDa: <strong>${res.current_value !== null ? res.current_value : 'не задано'}</strong></div>
        </div>
      `;
    }
  } catch (err) {
    appendUcpdLog(`Ошибка эксперимента: ${err.message}`);
    if (resultBox) {
      resultBox.innerHTML = `<div class="text-danger small">Сбой эксперимента: ${escapeHtml(err.message)}</div>`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Добавление строки в журнал действий панели UCPD.
 * @param {string} text - Текст сообщения.
 */
export function appendUcpdLog(text) {
  const consoleEl = document.getElementById('winadmin-ucpd-console-output');
  if (!consoleEl) return;
  const ts = new Date().toLocaleTimeString();
  consoleEl.textContent = `[${ts}] ${text}\n` + consoleEl.textContent;
}
