/**
 * =============================================================================
 * Process Name: AI-Windows-Admin UI - Windows API Registry Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер вкладки Windows API Registry & Smart Platform Dispatcher.
 *   Обеспечивает интерактивный обзор подсистем, поиск системных API, AI-резолвер
 *   задач, мониторинг Python-библиотек и запуск нативных зондов.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_windows_api_registry
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 03:00:00
 * =============================================================================
 */

(function () {
  'use strict';

  let state = {
    catalog: [],
    subsystems: {},
    bindings: {},
    activeSubsystemFilter: '',
    activeFamilyFilter: '',
    searchQuery: '',
    zeroDepOnly: false,
  };

  /**
   * Инициализация при входе на вкладку.
   */
  window.initWindowsApiRegistryTab = function () {
    bindEvents();
    loadSubsystems();
    loadCatalog();
    loadBindings();
    loadSettings();
  };

  /**
   * Деактивация вкладки.
   */
  window.deactivateWindowsApiRegistryTab = function () {
    // Очистка таймеров при необходимости
  };

  function bindEvents() {
    // Кнопка обновления
    const btnRefresh = document.getElementById('winapi-btn-refresh');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        loadSubsystems();
        loadCatalog();
        loadBindings();
      });
    }

    // Быстрый зонд
    const btnQuickProbe = document.getElementById('winapi-btn-quick-probe');
    if (btnQuickProbe) {
      btnQuickProbe.addEventListener('click', () => runProbe('kernel32_process_mem'));
    }

    // Фильтры
    const searchInput = document.getElementById('winapi-filter-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        state.searchQuery = searchInput.value.trim();
        renderCatalog();
      });
    }

    const subSelect = document.getElementById('winapi-filter-subsystem');
    if (subSelect) {
      subSelect.addEventListener('change', () => {
        state.activeSubsystemFilter = subSelect.value;
        renderCatalog();
      });
    }

    const famSelect = document.getElementById('winapi-filter-family');
    if (famSelect) {
      famSelect.addEventListener('change', () => {
        state.activeFamilyFilter = famSelect.value;
        renderCatalog();
      });
    }

    const zeroCheck = document.getElementById('winapi-filter-zero-dep');
    if (zeroCheck) {
      zeroCheck.addEventListener('change', () => {
        state.zeroDepOnly = zeroCheck.checked;
        renderCatalog();
      });
    }

    // Кнопка решения задачи
    const btnSolve = document.getElementById('winapi-btn-solve');
    if (btnSolve) {
      btnSolve.addEventListener('click', handleRecommend);
    }

    // Пресеты задач
    document.querySelectorAll('.winapi-preset-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const input = document.getElementById('winapi-task-input');
        if (input) {
          input.value = btn.getAttribute('data-query') || '';
          handleRecommend();
        }
      });
    });

    // Кнопки зондов
    document.querySelectorAll('.winapi-probe-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        if (targetId) runProbe(targetId);
      });
    });

    // Сохранение настроек
    const btnSaveCfg = document.getElementById('winapi-btn-save-settings');
    if (btnSaveCfg) {
      btnSaveCfg.addEventListener('click', saveSettings);
    }
  }

  /**
   * Загрузка 6 платформенных подсистем.
   */
  async function loadSubsystems() {
    try {
      const res = await fetch('/api/v1/windows-api/subsystems');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.subsystems = await res.json();
      renderSubsystemsCards();
    } catch (err) {
      console.error('[WinApiRegistry] Ошибка загрузки подсистем:', err);
    }
  }

  function renderSubsystemsCards() {
    const container = document.getElementById('winapi-subsystems-cards');
    if (!container) return;

    const cardsHtml = Object.entries(state.subsystems).map(([key, item]) => {
      const isActive = state.activeSubsystemFilter === key;
      return `
        <div class="col-12 col-md-4 col-lg-2">
          <div class="card border-subtle shadow-sm h-100 cursor-pointer ${isActive ? 'border-primary' : 'bg-body'}" 
               style="cursor: pointer; transition: all 0.2s;" data-subsystem="${key}">
            <div class="card-body p-2 d-flex flex-column gap-1">
              <div class="d-flex align-items-center justify-content-between">
                <i class="bi ${item.icon} text-primary fs-5"></i>
                <span class="badge bg-secondary-subtle text-body border border-subtle small">${item.total_apis} API</span>
              </div>
              <div class="fw-semibold small text-truncate" title="${item.title}">${item.title}</div>
              <small class="text-secondary" style="font-size: 0.75rem; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                ${item.description}
              </small>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = cardsHtml;

    container.querySelectorAll('[data-subsystem]').forEach((card) => {
      card.addEventListener('click', () => {
        const sub = card.getAttribute('data-subsystem');
        const select = document.getElementById('winapi-filter-subsystem');
        if (state.activeSubsystemFilter === sub) {
          state.activeSubsystemFilter = '';
          if (select) select.value = '';
        } else {
          state.activeSubsystemFilter = sub;
          if (select) select.value = sub;
        }
        renderSubsystemsCards();
        renderCatalog();
      });
    });
  }

  /**
   * Загрузка каталога API.
   */
  async function loadCatalog() {
    try {
      const res = await fetch('/api/v1/windows-api/catalog');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.catalog = await res.json();

      const totalBadge = document.getElementById('winapi-total-badge');
      if (totalBadge) totalBadge.textContent = `${state.catalog.length} системных API`;

      renderCatalog();
    } catch (err) {
      console.error('[WinApiRegistry] Ошибка загрузки каталога:', err);
    }
  }

  function renderCatalog() {
    const tbody = document.getElementById('winapi-table-body');
    const countBadge = document.getElementById('winapi-filtered-count');
    if (!tbody) return;

    let filtered = state.catalog;

    if (state.activeSubsystemFilter) {
      filtered = filtered.filter((a) => a.subsystem === state.activeSubsystemFilter);
    }

    if (state.activeFamilyFilter) {
      filtered = filtered.filter((a) => a.family === state.activeFamilyFilter);
    }

    if (state.zeroDepOnly) {
      filtered = filtered.filter((a) => a.zero_dependency);
    }

    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.binary_or_namespace.toLowerCase().includes(q) ||
          a.description.toLowerCase().includes(q) ||
          a.functions.some((f) => f.toLowerCase().includes(q))
      );
    }

    if (countBadge) countBadge.textContent = `${filtered.length} из ${state.catalog.length}`;

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary py-4">Нет API, соответствующих критериям фильтрации</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map((item) => {
      const familyBadge = getFamilyBadge(item.family);
      const depBadge = item.zero_dependency
        ? '<span class="badge bg-success-subtle text-success border border-success-subtle small">ctypes (0 dep)</span>'
        : `<span class="badge bg-secondary-subtle text-body border border-subtle small">${item.python_bindings[0] || 'SDK'}</span>`;

      const privBadge = item.privileges === 'admin'
        ? '<span class="badge bg-warning-subtle text-warning border border-warning-subtle small">Admin</span>'
        : '<span class="badge bg-info-subtle text-info border border-info-subtle small">User</span>';

      const fnsShort = item.functions.slice(0, 3).map((f) => `<code class="small text-body-secondary">${escapeHtml(f)}</code>`).join(', ');

      return `
        <tr>
          <td>
            <div class="fw-semibold small text-body">${escapeHtml(item.name)}</div>
            <small class="text-secondary text-truncate d-block" style="max-width: 200px;">${escapeHtml(item.description)}</small>
          </td>
          <td>${familyBadge}</td>
          <td><span class="font-monospace small text-primary">${escapeHtml(item.binary_or_namespace)}</span></td>
          <td><div class="text-truncate" style="max-width: 320px;">${fnsShort}</div></td>
          <td>${depBadge}</td>
          <td>${privBadge}</td>
          <td class="text-center">
            <button type="button" class="btn btn-sm btn-outline-primary py-0 px-2 small winapi-view-btn" data-id="${item.id}" title="Спецификация и код">
              <i class="bi bi-code"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.winapi-view-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        openApiDetails(id);
      });
    });
  }

  function getFamilyBadge(family) {
    const map = {
      win32: '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">Win32</span>',
      winrt: '<span class="badge bg-info-subtle text-info border border-info-subtle">WinRT</span>',
      com: '<span class="badge bg-secondary-subtle text-body border border-subtle">COM</span>',
      etw: '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">ETW</span>',
      directx: '<span class="badge bg-dark-subtle text-body border border-subtle">DirectX</span>',
      wfp: '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">WFP</span>',
    };
    return map[family] || `<span class="badge bg-body-secondary text-body">${family}</span>`;
  }

  /**
   * Интеллектуальный диспетчер подбора интерфейсов.
   */
  async function handleRecommend() {
    const taskInput = document.getElementById('winapi-task-input');
    const zeroCheck = document.getElementById('winapi-prefer-zero-dep-check');
    const container = document.getElementById('winapi-resolver-result-container');
    const subBadge = document.getElementById('winapi-result-subsystem');

    if (!taskInput || !taskInput.value.trim()) {
      alert('Пожалуйста, введите описание задачи для подбора API');
      return;
    }

    if (container) {
      container.innerHTML = '<div class="text-center text-secondary py-5"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Анализ системных контрактов Windows...</div>';
    }

    try {
      const res = await fetch('/api/v1/windows-api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_description: taskInput.value.trim(),
          prefer_zero_dependency: zeroCheck ? zeroCheck.checked : true,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const rec = data.recommended_api;

      if (subBadge) subBadge.textContent = rec.subsystem;

      if (container) {
        container.innerHTML = `
          <div class="alert alert-success border-success-subtle bg-success-subtle text-success-emphasis d-flex align-items-start gap-2 mb-0">
            <i class="bi bi-check-circle-fill fs-5 mt-0.5"></i>
            <div>
              <div class="fw-bold">${rec.name} (${rec.binary_or_namespace})</div>
              <small class="d-block mt-1">${data.rationale}</small>
            </div>
          </div>

          <div class="d-flex flex-column gap-1">
            <div class="d-flex justify-content-between align-items-center">
              <label class="form-label small fw-medium text-body mb-0">Готовый сниппет для Python:</label>
              <button type="button" class="btn btn-sm btn-link p-0 text-decoration-none small" id="winapi-copy-code-btn">Копировать</button>
            </div>
            <pre class="p-3 bg-body-tertiary rounded border border-subtle font-monospace small mb-0" style="white-space: pre-wrap;" id="winapi-code-block">${escapeHtml(data.python_snippet)}</pre>
          </div>

          ${data.powershell_equivalent ? `
            <div class="d-flex flex-column gap-1">
              <label class="form-label small fw-medium text-body mb-0">Эквивалент PowerShell:</label>
              <pre class="p-2 bg-body-tertiary rounded border border-subtle font-monospace small mb-0">${escapeHtml(data.powershell_equivalent)}</pre>
            </div>
          ` : ''}

          <div class="p-2 bg-body-tertiary rounded border border-subtle small d-flex flex-wrap gap-2 justify-content-between">
            <span><strong>Минимум:</strong> ${rec.min_win_version}</span>
            <span><strong>Права:</strong> ${rec.privileges}</span>
            <span><strong>Зависимости:</strong> ${rec.zero_dependency ? 'Zero-Dependency (ctypes)' : rec.python_bindings.join(', ')}</span>
          </div>
        `;

        const copyBtn = document.getElementById('winapi-copy-code-btn');
        if (copyBtn) {
          copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(data.python_snippet);
            copyBtn.textContent = 'Скопировано!';
            setTimeout(() => { copyBtn.textContent = 'Копировать'; }, 2000);
          });
        }
      }
    } catch (err) {
      console.error('[WinApiRegistry] Ошибка диспетчера:', err);
      if (container) {
        container.innerHTML = `<div class="alert alert-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  /**
   * Загрузка статуса привязок Python.
   */
  async function loadBindings() {
    try {
      const res = await fetch('/api/v1/windows-api/bindings-status');
      if (!res.ok) return;
      const data = await res.json();
      state.bindings = data;

      const tbody = document.getElementById('winapi-bindings-table-body');
      if (!tbody) return;

      tbody.innerHTML = Object.entries(data).map(([key, item]) => {
        const badge = item.installed
          ? '<span class="badge bg-success-subtle text-success border border-success-subtle">Доступен</span>'
          : '<span class="badge bg-secondary-subtle text-secondary border border-subtle">Отсутствует</span>';

        return `
          <tr>
            <td><code class="fw-semibold text-primary">${key}</code></td>
            <td>${badge}</td>
            <td class="small text-secondary">${escapeHtml(item.role)}</td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.error('[WinApiRegistry] Ошибка загрузки bindings:', err);
    }
  }

  /**
   * Запуск нативного проверочного зонда.
   */
  async function runProbe(apiId) {
    const out = document.getElementById('winapi-probe-output');
    if (out) {
      out.textContent = `Запуск нативного зонда для ${apiId}...\n`;
    }

    try {
      const res = await fetch('/api/v1/windows-api/execute-probe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_id: apiId }),
      });
      const data = await res.json();
      if (out) {
        out.textContent = JSON.stringify(data, null, 2);
      }
    } catch (err) {
      if (out) out.textContent = `Ошибка зонда: ${err.message}`;
    }
  }

  /**
   * Модальное окно спецификации API.
   */
  async function openApiDetails(apiId) {
    try {
      const res = await fetch(`/api/v1/windows-api/entry/${apiId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const api = await res.json();

      const modalTitle = document.getElementById('winapi-modal-title');
      const modalBody = document.getElementById('winapi-modal-body');
      if (!modalTitle || !modalBody) return;

      modalTitle.textContent = `${api.name} — ${api.binary_or_namespace}`;

      const fnsList = api.functions.map((f) => `<li class="font-monospace small">${escapeHtml(f)}</li>`).join('');

      modalBody.innerHTML = `
        <div class="d-flex align-items-center gap-2 flex-wrap">
          ${getFamilyBadge(api.family)}
          <span class="badge bg-secondary-subtle text-body border border-subtle">${api.subsystem}</span>
          <span class="badge bg-info-subtle text-info border border-info-subtle">${api.min_win_version}</span>
          ${api.zero_dependency ? '<span class="badge bg-success-subtle text-success border border-success-subtle">Zero-Dependency</span>' : ''}
        </div>

        <div>
          <h6 class="fw-semibold small text-body mb-1">Описание и назначение:</h6>
          <p class="small text-secondary mb-0">${escapeHtml(api.description)}</p>
        </div>

        <div>
          <h6 class="fw-semibold small text-body mb-1">Ключевые функции и классы:</h6>
          <ul class="mb-0 ps-3">${fnsList}</ul>
        </div>

        ${api.code_examples && api.code_examples.python ? `
          <div>
            <h6 class="fw-semibold small text-body mb-1">Пример вызова в Python:</h6>
            <pre class="p-3 bg-body-tertiary rounded border border-subtle font-monospace small mb-0" style="white-space: pre-wrap;">${escapeHtml(api.code_examples.python)}</pre>
          </div>
        ` : ''}

        ${api.limitations ? `
          <div class="alert alert-warning border-warning-subtle bg-warning-subtle text-warning-emphasis small py-2 mb-0">
            <strong>Ограничения:</strong> ${escapeHtml(api.limitations)}
          </div>
        ` : ''}
      `;

      const modalEl = document.getElementById('winapi-modal-details');
      if (modalEl && window.bootstrap) {
        const modal = new window.bootstrap.Modal(modalEl);
        modal.show();
      }
    } catch (err) {
      alert('Ошибка загрузки спецификации: ' + err.message);
    }
  }

  /**
   * Настройки реестра.
   */
  async function loadSettings() {
    try {
      const res = await fetch('/api/v1/windows-api/settings');
      if (!res.ok) return;
      const cfg = await res.json();

      const zeroChk = document.getElementById('winapi-cfg-prefer-zero-dep');
      if (zeroChk) zeroChk.checked = Boolean(cfg.prefer_zero_dependency);

      const hideDep = document.getElementById('winapi-cfg-hide-deprecated');
      if (hideDep) hideDep.checked = Boolean(cfg.hide_deprecated);

      const maxRecs = document.getElementById('winapi-cfg-max-recs');
      if (maxRecs) maxRecs.value = cfg.max_recommendations || 5;
    } catch (err) {
      console.error('[WinApiRegistry] Ошибка загрузки настроек:', err);
    }
  }

  async function saveSettings() {
    const payload = {
      prefer_zero_dependency: document.getElementById('winapi-cfg-prefer-zero-dep')?.checked ?? true,
      hide_deprecated: document.getElementById('winapi-cfg-hide-deprecated')?.checked ?? true,
      max_recommendations: parseInt(document.getElementById('winapi-cfg-max-recs')?.value || '5', 10),
    };

    try {
      const res = await fetch('/api/v1/windows-api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      alert('Настройки платформы Windows API успешно сохранены!');
    } catch (err) {
      alert('Ошибка сохранения настроек: ' + err.message);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
})();
