/**
 * =============================================================================
 * Process Name: Windows Ninite Updater Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления вкладкой установки и автообновления Ninite.
 *   Поддерживает изолированную инициализацию в нескольких контейнерах DOM
 *   (отдельная вкладка #tab-ninite-updater и встроенный блок #block-ninite).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_ninite_updater/main.js?v=20261120_v2" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_ninite_updater
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 17:10:00
 * =============================================================================
 */

(function () {
  'use strict';

  const boundControllers = new WeakMap();

  /**
   * Создаёт и привязывает изолированный контроллер Ninite к конкретному контейнеру.
   *
   * @param {HTMLElement} root - Корневой элемент `.ninite-container`.
   * @returns {{ loadStatus: () => Promise<void> }} Контроллер экземпляра.
   */
  function bindNiniteRoot(root) {
    if (boundControllers.has(root)) {
      return boundControllers.get(root);
    }

    let selectedFile = null;
    const q = (selector) => root.querySelector(selector);

    /**
     * Отображение информационного сообщения в текущем контейнере.
     */
    function showAlert(message, type = 'info') {
      const box = q('#ninite-alert-box');
      if (!box) return;

      box.className = `alert alert-${type} alert-dismissible fade show small mt-3`;
      box.innerHTML = `
        <div>${message}</div>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
      `;
    }

    /**
     * Обработка выбора файла установщика Ninite.
     */
    function handleFileSelect(file) {
      selectedFile = file;
      const label = q('#ninite-file-label');
      if (label) {
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        label.innerHTML = `✅ Выбран файл: <strong class="text-info">${file.name}</strong> (${sizeMb} MB)`;
      }
    }

    /**
     * Загрузка текущего статуса файла и задачи в Task Scheduler.
     */
    async function loadStatus() {
      const statusBadge = q('#ninite-status-badge');
      const fileStatus = q('#ninite-file-status');
      const fileDetails = q('#ninite-file-details');
      const taskStatus = q('#ninite-task-status');
      const taskDetails = q('#ninite-task-details');
      const taskNext = q('#ninite-task-next');
      const logViewer = q('#ninite-log-viewer');
      const logTimestamp = q('#ninite-log-timestamp');

      try {
        const res = await fetch(`/api/v1/ninite/status?t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.file && fileStatus && fileDetails) {
          if (data.file.installed) {
            const sizeMb = (data.file.size_bytes / (1024 * 1024)).toFixed(2);
            fileStatus.innerHTML = `<span class="text-success">● Установлен</span>`;
            fileDetails.textContent = `Путь: ${data.file.path} | Размер: ${sizeMb} MB | Изменён: ${data.file.modified_time}`;
          } else {
            fileStatus.innerHTML = `<span class="text-warning">● Не установлен</span>`;
            fileDetails.textContent = `Файл ninite.exe отсутствует в Program Files`;
          }
        }

        if (data.task && taskStatus && taskDetails && taskNext) {
          if (data.task.exists) {
            taskStatus.innerHTML = `<span class="text-success">● Активна (${data.task.state})</span>`;
            taskDetails.textContent = `Задача: ${data.task.task_name} | Посл. запуск: ${data.task.last_run_time || 'нет'}`;
            taskNext.textContent = data.task.next_run_time || 'По расписанию';
          } else {
            taskStatus.innerHTML = `<span class="text-secondary">● Не запланирована</span>`;
            taskDetails.textContent = `Задача ${data.task.task_name || 'NiniteAutoUpdate'} отсутствует в Task Scheduler`;
            taskNext.textContent = '--';
          }
        }

        if (statusBadge) {
          if (data.file?.installed && data.task?.exists) {
            statusBadge.className = 'ui-badge ui-badge-success px-2.5 py-1.5';
            statusBadge.textContent = '● Автообновление активно';
          } else if (data.file?.installed) {
            statusBadge.className = 'ui-badge ui-badge-warning px-2.5 py-1.5';
            statusBadge.textContent = '● Файл готов, расписание не задано';
          } else {
            statusBadge.className = 'ui-badge ui-badge-neutral px-2.5 py-1.5';
            statusBadge.textContent = '● Ожидание установки';
          }
        }

        if (logViewer && data.log) {
          logViewer.textContent = data.log;
          if (logTimestamp) {
            logTimestamp.textContent = `Обновлено: ${new Date().toLocaleTimeString()}`;
          }
        }
      } catch (err) {
        console.error('Ошибка загрузки статуса Ninite:', err);
        if (statusBadge) {
          statusBadge.className = 'ui-badge ui-badge-danger px-2.5 py-1.5';
          statusBadge.textContent = '● Ошибка связи с сервером';
        }
      }
    }

    /**
     * Отправка формы (загрузка файла + настройка Task Scheduler).
     */
    async function handleFormSubmit(e) {
      e.preventDefault();

      if (!selectedFile) {
        showAlert('Пожалуйста, выберите файл инсталлятора Ninite для загрузки.', 'warning');
        return;
      }

      const interval = q('#ninite-interval')?.value || '2';
      const timeStr = q('#ninite-time')?.value || '20:00';
      const submitBtn = q('#btn-ninite-submit');

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('interval_weeks', interval);
      formData.append('time_str', timeStr);

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Копирование в Program Files и регистрация задачи...`;
      }

      try {
        const res = await fetch('/api/v1/ninite/upload', {
          method: 'POST',
          body: formData,
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        showAlert(`Успешно! ${data.message}`, 'success');
        selectedFile = null;
        const inputEl = q('#ninite-file-input');
        if (inputEl) inputEl.value = '';
        await loadStatus();
      } catch (err) {
        showAlert(`Ошибка: ${err.message}`, 'danger');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> Установить в Program Files и активировать Task Scheduler`;
        }
      }
    }

    /**
     * Обновление только расписания без перезагрузки файла.
     */
    async function handleScheduleOnly() {
      const interval = parseInt(q('#ninite-interval')?.value || '2', 10);
      const timeStr = q('#ninite-time')?.value || '20:00';
      const day = q('#ninite-day')?.value || 'Sunday';

      try {
        const res = await fetch('/api/v1/ninite/schedule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            interval_weeks: interval,
            time_str: timeStr,
            days_of_week: day,
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        showAlert(`Расписание обновлено: каждые ${interval} нед. в ${timeStr}`, 'success');
        await loadStatus();
      } catch (err) {
        showAlert(`Ошибка обновления расписания: ${err.message}`, 'danger');
      }
    }

    /**
     * Ручной запуск обновления сейчас.
     */
    async function handleRunNow() {
      const btn = q('#btn-ninite-run-now');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Запуск обновления...`;
      }

      try {
        const res = await fetch('/api/v1/ninite/run-now', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        showAlert(`Обновление запущено: ${data.message}`, 'info');
        setTimeout(loadStatus, 3000);
      } catch (err) {
        showAlert(`Ошибка запуска: ${err.message}`, 'danger');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<i class="bi bi-play-circle-fill me-1"></i> Запустить обновление прямо сейчас`;
        }
      }
    }

    // Привязка обработчиков событий строго внутри root
    const dropzone = q('#ninite-dropzone');
    const fileInput = q('#ninite-file-input');
    const form = q('#ninite-upload-form');
    const refreshBtn = q('#btn-ninite-refresh');
    const runNowBtn = q('#btn-ninite-run-now');
    const scheduleOnlyBtn = q('#btn-ninite-update-schedule-only');

    if (fileInput) {
      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          handleFileSelect(e.target.files[0]);
        }
      });
    }

    if (dropzone) {
      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFileSelect(e.dataTransfer.files[0]);
        }
      });
    }

    if (form) {
      form.addEventListener('submit', handleFormSubmit);
    }

    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => loadStatus());
    }

    if (runNowBtn) {
      runNowBtn.addEventListener('click', handleRunNow);
    }

    if (scheduleOnlyBtn) {
      scheduleOnlyBtn.addEventListener('click', handleScheduleOnly);
    }

    const controller = { loadStatus };
    boundControllers.set(root, controller);
    return controller;
  }

  /**
   * Инициализация вкладки (и всех встроенных экземпляров) Ninite Updater.
   */
  function initNiniteUpdaterTab() {
    const roots = document.querySelectorAll('.ninite-container');
    roots.forEach((root) => {
      const ctrl = bindNiniteRoot(root);
      ctrl.loadStatus();
    });
  }

  // Экспорт для жизненного цикла tab-core.js и глобального контекста
  window.initNiniteUpdaterTab = initNiniteUpdaterTab;
  window.initNiniteupdaterTab = initNiniteUpdaterTab;
  window.initNinite_updaterTab = initNiniteUpdaterTab;

  // Автоматический запуск при загрузке скрипта
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNiniteUpdaterTab);
  } else {
    initNiniteUpdaterTab();
  }
})();
