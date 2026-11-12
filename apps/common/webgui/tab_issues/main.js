/**
 * =============================================================================
 * Process Name: Common WebGUI - GitHub Issues Tab Controller
 * =============================================================================
 * Description:
 *   Контроллер глобальной вкладки управления GitHub Issues, вехами Milestones,
 *   метками, шаблонами и связью с локальным Git-репозиторием.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: apps/common/webgui/tab_issues
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 14:41:44
 * =============================================================================
 */

(function () {
  'use strict';

  let currentIssues = [];
  let availableTemplates = [];
  let currentActiveIssue = null;

  /**
   * Инициализация вкладки Issues.
   */
  async function initIssuesTab() {
    console.log('[IssuesTab] Инициализация вкладки GitHub Issues...');
    bindEvents();
    await Promise.all([
      loadGitInfo(),
      loadTemplates(),
      loadLabels(),
      loadIssues()
    ]);
  }

  /**
   * Привязка событий элементов управления.
   */
  function bindEvents() {
    const refreshBtn = document.getElementById('btn-refresh-issues');
    if (refreshBtn) {
      refreshBtn.onclick = () => {
        loadGitInfo();
        loadIssues();
      };
    }

    // Фильтры
    const stateSelect = document.getElementById('filter-state-select');
    const typeSelect = document.getElementById('filter-type-select');
    const compSelect = document.getElementById('filter-component-select');
    const searchInput = document.getElementById('filter-search-text');
    const resetBtn = document.getElementById('btn-reset-filters');

    if (stateSelect) stateSelect.onchange = () => loadIssues();
    if (typeSelect) typeSelect.onchange = () => renderFilteredIssues();
    if (compSelect) compSelect.onchange = () => renderFilteredIssues();
    if (searchInput) searchInput.oninput = () => renderFilteredIssues();
    if (resetBtn) {
      resetBtn.onclick = () => {
        if (stateSelect) stateSelect.value = 'open';
        if (typeSelect) typeSelect.value = '';
        if (compSelect) compSelect.value = '';
        if (searchInput) searchInput.value = '';
        loadIssues();
      };
    }

    // Шаблоны
    const tplSelect = document.getElementById('new-issue-template-select');
    if (tplSelect) {
      tplSelect.onchange = (e) => applyTemplate(e.target.value);
    }

    // Форма создания
    const form = document.getElementById('form-create-issue');
    if (form) {
      form.onsubmit = handleCreateIssue;
    }

    // Синхронизация меток
    const syncBtn = document.getElementById('btn-sync-labels');
    if (syncBtn) {
      syncBtn.onclick = handleSyncLabels;
    }

    // Действия модального окна
    const branchBtn = document.getElementById('modal-btn-create-branch');
    if (branchBtn) branchBtn.onclick = handleModalCreateBranch;

    const planBtn = document.getElementById('modal-btn-build-plan');
    if (planBtn) planBtn.onclick = handleModalBuildPlan;

    const toggleStateBtn = document.getElementById('modal-btn-toggle-state');
    if (toggleStateBtn) toggleStateBtn.onclick = handleModalToggleState;

    const commentBtn = document.getElementById('modal-btn-send-comment');
    if (commentBtn) commentBtn.onclick = handleModalSendComment;
  }

  /**
   * Загрузка информации о локальном Git-репозитории.
   */
  async function loadGitInfo() {
    try {
      const res = await fetch('/api/issues/git-info');
      const data = await res.json();
      if (data.status !== 'ok') return;

      const info = data.data;
      const repoEl = document.getElementById('git-repo-name');
      const branchEl = document.getElementById('git-branch-name');
      const remoteEl = document.getElementById('git-remote-url');
      const commitEl = document.getElementById('git-last-commit');
      const statusBadge = document.getElementById('git-status-badge');
      const statusText = document.getElementById('git-status-text');
      const ghIndicator = document.getElementById('gh-cli-indicator');
      const ghText = document.getElementById('gh-cli-text');
      const issuesLink = document.getElementById('btn-open-github-issues');

      if (repoEl) repoEl.textContent = info.repo_name || 'Локальный репозиторий';
      if (branchEl) branchEl.textContent = info.branch || 'detached';
      if (remoteEl) remoteEl.textContent = info.remote_url || 'Remote не настроен';
      if (commitEl) commitEl.textContent = info.last_commit || 'Нет коммитов';

      if (statusBadge && statusText) {
        if (info.is_clean) {
          statusBadge.className = 'badge git-badge-clean px-2 py-1';
          statusText.textContent = 'Рабочая копия чистая';
        } else {
          statusBadge.className = 'badge git-badge-dirty px-2 py-1';
          statusText.textContent = 'Есть незафиксированные изменения';
        }
      }

      if (ghIndicator && ghText) {
        if (info.gh_ready) {
          ghIndicator.className = 'badge bg-success-subtle text-success px-2.5 py-1.5';
          ghText.textContent = 'gh CLI: авторизован';
        } else if (info.gh_cli_installed) {
          ghIndicator.className = 'badge bg-warning-subtle text-warning px-2.5 py-1.5';
          ghText.textContent = 'gh CLI: не авторизован';
        } else {
          ghIndicator.className = 'badge bg-danger-subtle text-danger px-2.5 py-1.5';
          ghText.textContent = 'gh CLI: не установлен';
        }
      }

      if (issuesLink && info.issues_url) {
        issuesLink.href = info.issues_url;
      }
    } catch (err) {
      console.warn('[IssuesTab] Ошибка загрузки Git-информации:', err);
    }
  }

  /**
   * Загрузка списка задач.
   */
  async function loadIssues() {
    const tbody = document.getElementById('issues-table-body');
    const stateSelect = document.getElementById('filter-state-select');
    const state = stateSelect ? stateSelect.value : 'open';

    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">
        <div class="spinner-border spinner-border-sm me-2"></div>Загрузка задач из репозитория...
      </td></tr>`;
    }

    try {
      const res = await fetch(`/api/issues?state=${encodeURIComponent(state)}&limit=100`);
      const data = await res.json();
      currentIssues = data.issues || [];

      updateKpis(currentIssues);
      renderFilteredIssues();
      renderMilestones(currentIssues);
    } catch (err) {
      console.error('[IssuesTab] Ошибка получения списка задач:', err);
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>Не удалось загрузить задачи: ${err.message}
        </td></tr>`;
      }
    }
  }

  /**
   * Обновление показателей KPI.
   */
  function updateKpis(issues) {
    const total = issues.length;
    const openCount = issues.filter(i => i.state === 'open').length;
    const closedCount = issues.filter(i => i.state === 'closed').length;
    const bugsCount = issues.filter(i => i.issue_type === 'bug').length;
    const featsCount = issues.filter(i => i.issue_type === 'feature').length;
    const critCount = issues.filter(i => i.priority && i.priority.includes('critical')).length;

    const elTotal = document.getElementById('kpi-total');
    const elOpen = document.getElementById('kpi-open');
    const elClosed = document.getElementById('kpi-closed');
    const elBugs = document.getElementById('kpi-bugs');
    const elFeats = document.getElementById('kpi-features');
    const elCrit = document.getElementById('kpi-critical');
    const badgeTotal = document.getElementById('badge-total-count');

    if (elTotal) elTotal.textContent = total;
    if (elOpen) elOpen.textContent = openCount;
    if (elClosed) elClosed.textContent = closedCount;
    if (elBugs) elBugs.textContent = bugsCount;
    if (elFeats) elFeats.textContent = featsCount;
    if (elCrit) elCrit.textContent = critCount;
    if (badgeTotal) badgeTotal.textContent = total;
  }

  /**
   * Фильтрация и рендеринг таблицы задач.
   */
  function renderFilteredIssues() {
    const tbody = document.getElementById('issues-table-body');
    if (!tbody) return;

    const typeFilter = (document.getElementById('filter-type-select')?.value || '').toLowerCase();
    const compFilter = (document.getElementById('filter-component-select')?.value || '').toLowerCase();
    const searchVal = (document.getElementById('filter-search-text')?.value || '').trim().toLowerCase();

    const filtered = currentIssues.filter(item => {
      if (typeFilter && item.issue_type.toLowerCase() !== typeFilter) return false;
      if (compFilter && !item.labels.some(l => l.toLowerCase() === compFilter)) return false;
      if (searchVal) {
        const text = `#${item.number} ${item.title} ${item.body || ''}`.toLowerCase();
        if (!text.includes(searchVal)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">
        <i class="bi bi-inbox me-2"></i>Задачи, соответствующие фильтрам, не найдены.
      </td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(item => {
      const isOpen = item.state === 'open';
      const stateBadge = isOpen
        ? '<span class="badge bg-success-subtle text-success">Open</span>'
        : '<span class="badge bg-secondary-subtle text-secondary">Closed</span>';

      const prioClass = (item.priority || '').includes('critical') ? 'badge bg-danger-subtle text-danger' :
                        (item.priority || '').includes('high') ? 'badge bg-warning-subtle text-warning' :
                        'badge bg-secondary-subtle text-secondary';

      const labelsHtml = (item.labels || []).slice(0, 4).map(l => {
        return `<span class="issue-label-pill bg-body-secondary text-body">${escapeHtml(l)}</span>`;
      }).join('');

      return `
        <tr class="issue-row" data-number="${item.number}">
          <td class="fw-bold font-monospace text-primary">#${item.number}</td>
          <td>${stateBadge}</td>
          <td>
            <div class="fw-semibold text-truncate" style="max-width: 480px;">${escapeHtml(item.title)}</div>
            <div class="mt-1">${labelsHtml}</div>
          </td>
          <td><span class="badge bg-info-subtle text-info font-monospace">${escapeHtml(item.component || 'core')}</span></td>
          <td><span class="${prioClass}">${escapeHtml(item.priority || 'medium')}</span></td>
          <td class="small text-muted">${escapeHtml((item.assignees || []).join(', ') || '---')}</td>
          <td class="text-end">
            <button type="button" class="btn btn-xs btn-outline-primary btn-view-issue" data-number="${item.number}" title="Детали и AI действия">
              <i class="bi bi-eye"></i>
            </button>
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn btn-xs btn-outline-secondary ms-1" title="Открыть в GitHub">
              <i class="bi bi-box-arrow-up-right"></i>
            </a>
          </td>
        </tr>
      `;
    }).join('');

    // Привязка кликов по строкам и кнопкам
    tbody.querySelectorAll('.btn-view-issue, tr.issue-row').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        const num = el.getAttribute('data-number');
        if (num) showIssueDetails(parseInt(num, 10));
      });
    });
  }

  /**
   * Отображение модального окна с деталями задачи.
   */
  async function showIssueDetails(number) {
    const issue = currentIssues.find(i => i.number === number);
    if (!issue) return;
    currentActiveIssue = issue;

    const modalTitle = document.getElementById('modal-issue-title');
    const modalBadge = document.getElementById('modal-issue-badge');
    const modalMeta = document.getElementById('modal-issue-meta');
    const modalBody = document.getElementById('modal-issue-body');
    const modalUrl = document.getElementById('modal-issue-url');
    const toggleStateBtn = document.getElementById('modal-btn-toggle-state-text');
    const actionResult = document.getElementById('modal-ai-action-result');

    if (actionResult) actionResult.classList.add('d-none');
    if (modalTitle) modalTitle.textContent = issue.title;
    if (modalBadge) modalBadge.textContent = `#${issue.number}`;
    if (modalUrl) modalUrl.href = issue.url;

    if (toggleStateBtn) {
      toggleStateBtn.textContent = issue.state === 'open' ? 'Закрыть задачу' : 'Повторно открыть';
    }

    if (modalMeta) {
      modalMeta.innerHTML = `
        <span class="badge ${issue.state === 'open' ? 'bg-success' : 'bg-secondary'}">${issue.state.toUpperCase()}</span>
        <span class="badge bg-primary-subtle text-primary">${escapeHtml(issue.issue_type)}</span>
        <span class="badge bg-warning-subtle text-warning">${escapeHtml(issue.priority)}</span>
        <span class="badge bg-info-subtle text-info">${escapeHtml(issue.component)}</span>
        <span class="small text-muted ms-2">Исполнитель: ${escapeHtml((issue.assignees || []).join(', ') || 'Не назначен')}</span>
      `;
    }

    if (modalBody) {
      modalBody.textContent = issue.body || '(Описание отсутствует)';
    }

    const modalEl = document.getElementById('issue-details-modal');
    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
      const modal = new window.bootstrap.Modal(modalEl);
      modal.show();
    }
  }

  /**
   * Создание ветки Git под активную задачу.
   */
  async function handleModalCreateBranch() {
    if (!currentActiveIssue) return;
    const actionResult = document.getElementById('modal-ai-action-result');
    const actionText = document.getElementById('modal-ai-action-text');

    try {
      const res = await fetch(`/api/issues/${currentActiveIssue.number}/create-branch`, { method: 'POST' });
      const data = await res.json();
      if (actionResult && actionText) {
        actionResult.classList.remove('d-none');
        if (data.status === 'ok') {
          actionText.innerHTML = `✅ Git-ветка успешно создана и переключена: <strong>${data.branch}</strong>`;
          loadGitInfo();
        } else {
          actionText.innerHTML = `❌ Ошибка: ${data.detail || 'Не удалось создать ветку'}`;
        }
      }
    } catch (err) {
      if (actionResult && actionText) {
        actionResult.classList.remove('d-none');
        actionText.textContent = `Ошибка: ${err.message}`;
      }
    }
  }

  /**
   * Формирование формализованного плана ТЗ для AI.
   */
  async function handleModalBuildPlan() {
    if (!currentActiveIssue) return;
    const actionResult = document.getElementById('modal-ai-action-result');
    const actionText = document.getElementById('modal-ai-action-text');

    try {
      const res = await fetch(`/api/issues/${currentActiveIssue.number}/ai-plan`);
      const data = await res.json();
      if (actionResult && actionText) {
        actionResult.classList.remove('d-none');
        if (data.status === 'ok') {
          const plan = data.plan;
          actionText.innerHTML = `
            <strong>🎯 ТЗ для AI-разработчика:</strong><br>
            • Целевая ветка: <code>${plan.suggested_branch}</code><br>
            • Директива PR: <code>${plan.closing_keyword} #${plan.issue_number}</code><br>
            • Затронутые файлы: ${plan.target_files.length ? plan.target_files.map(f => `<code>${f}</code>`).join(', ') : 'Определяются по ходу задачи'}<br>
            • Сценариев TDD проверки: ${plan.test_cases.length}
          `;
        }
      }
    } catch (err) {
      if (actionResult && actionText) {
        actionResult.classList.remove('d-none');
        actionText.textContent = `Ошибка построения плана: ${err.message}`;
      }
    }
  }

  /**
   * Переключение состояния задачи (закрытие/открытие).
   */
  async function handleModalToggleState() {
    if (!currentActiveIssue) return;
    const isClosing = currentActiveIssue.state === 'open';
    const endpoint = isClosing ? `/api/issues/${currentActiveIssue.number}/close` : `/api/issues/${currentActiveIssue.number}/reopen`;
    const payload = isClosing ? { reason: 'completed', comment: 'Закрыто через WebGUI AI-TC' } : {};

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        await loadIssues();
        const updated = currentIssues.find(i => i.number === currentActiveIssue.number);
        if (updated) showIssueDetails(updated.number);
      }
    } catch (err) {
      alert(`Ошибка: ${err.message}`);
    }
  }

  /**
   * Отправка комментария к задаче.
   */
  async function handleModalSendComment() {
    if (!currentActiveIssue) return;
    const input = document.getElementById('modal-comment-input');
    const val = input ? input.value.trim() : '';
    if (!val) return;

    try {
      const res = await fetch(`/api/issues/${currentActiveIssue.number}/comment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: val })
      });
      if (res.ok) {
        if (input) input.value = '';
        alert('Комментарий успешно добавлен!');
      }
    } catch (err) {
      alert(`Ошибка отправки комментария: ${err.message}`);
    }
  }

  /**
   * Загрузка шаблонов задач.
   */
  async function loadTemplates() {
    try {
      const res = await fetch('/api/issues/templates');
      const data = await res.json();
      availableTemplates = data.templates || [];
      const select = document.getElementById('new-issue-template-select');
      if (select) {
        select.innerHTML = '<option value="">-- Без шаблона --</option>' +
          availableTemplates.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
      }
    } catch (err) {
      console.warn('[IssuesTab] Не удалось загрузить шаблоны задач:', err);
    }
  }

  /**
   * Применение выбранного шаблона к форме создания задачи.
   */
  function applyTemplate(templateId) {
    const tpl = availableTemplates.find(t => t.id === templateId);
    const titleInput = document.getElementById('new-issue-title');
    const bodyTextarea = document.getElementById('new-issue-body');
    const typeSelect = document.getElementById('new-issue-type');

    if (!tpl) return;
    if (titleInput && tpl.default_title && !titleInput.value) {
      titleInput.value = tpl.default_title;
    }
    if (bodyTextarea) {
      bodyTextarea.value = tpl.body;
    }
    if (typeSelect) {
      if (templateId.includes('bug')) typeSelect.value = 'bug';
      else if (templateId.includes('feat')) typeSelect.value = 'feature';
      else if (templateId.includes('enhance')) typeSelect.value = 'enhancement';
      else if (templateId.includes('doc')) typeSelect.value = 'documentation';
      else if (templateId.includes('refactor')) typeSelect.value = 'refactoring';
      else if (templateId.includes('research')) typeSelect.value = 'research';
    }
  }

  /**
   * Отправка формы создания новой задачи.
   */
  async function handleCreateIssue(e) {
    e.preventDefault();
    const title = document.getElementById('new-issue-title')?.value.trim();
    const type = document.getElementById('new-issue-type')?.value;
    const priority = document.getElementById('new-issue-priority')?.value;
    const component = document.getElementById('new-issue-component')?.value;
    const assignee = document.getElementById('new-issue-assignee')?.value.trim();
    const body = document.getElementById('new-issue-body')?.value;

    if (!title) {
      alert('Пожалуйста, укажите название задачи.');
      return;
    }

    const payload = {
      title,
      body,
      issue_type: type,
      priority,
      component,
      assignee: assignee || '@me'
    };

    try {
      const res = await fetch('/api/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'ok') {
        alert(`Задача успешно создана на GitHub: ${data.url || ''}`);
        e.target.reset();
        // Переключение на список задач
        const listTabBtn = document.getElementById('pill-issues-list-tab');
        if (listTabBtn) listTabBtn.click();
        loadIssues();
      } else {
        alert(`Ошибка создания: ${data.detail || 'Неизвестная ошибка'}`);
      }
    } catch (err) {
      alert(`Ошибка: ${err.message}`);
    }
  }

  /**
   * Загрузка стандартных меток AI-TC.
   */
  async function loadLabels() {
    try {
      const res = await fetch('/api/issues/labels');
      const data = await res.json();
      const tbody = document.getElementById('labels-table-body');
      if (!tbody || !data.labels) return;

      tbody.innerHTML = data.labels.map(l => {
        return `
          <tr>
            <td><span class="badge text-dark" style="background-color: #${l.color};">${escapeHtml(l.name)}</span></td>
            <td>${escapeHtml(l.description)}</td>
            <td class="font-monospace small">#${l.color}</td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.warn('[IssuesTab] Ошибка загрузки меток:', err);
    }
  }

  /**
   * Синхронизация типовых меток.
   */
  async function handleSyncLabels() {
    try {
      const res = await fetch('/api/issues/labels/sync', { method: 'POST' });
      const data = await res.json();
      alert(`Синхронизировано меток: ${data.synced_count || 0}`);
    } catch (err) {
      alert(`Ошибка синхронизации меток: ${err.message}`);
    }
  }

  /**
   * Рендеринг вех (Milestones).
   */
  function renderMilestones(issues) {
    const container = document.getElementById('milestones-container');
    if (!container) return;

    // Группировка по milestone или предопределенные вехи
    const predefined = [
      { name: 'v0.5 — Telemetry & Windows API', prefix: 'telemetry' },
      { name: 'v0.6 — Network Diagnostics & Tshark', prefix: 'network' },
      { name: 'v0.7 — AI Integration & Task Agents', prefix: 'ai' }
    ];

    container.innerHTML = predefined.map(m => {
      const related = issues.filter(i => (i.component || '').includes(m.prefix));
      const total = related.length;
      const closed = related.filter(i => i.state === 'closed').length;
      const pct = total > 0 ? Math.round((closed / total) * 100) : 0;

      return `
        <div class="mb-3 p-3 border border-subtle rounded bg-body-tertiary">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-bold">${m.name}</span>
            <span class="small text-muted">${closed} из ${total} задач (${pct}%)</span>
          </div>
          <div class="progress" style="height: 10px;">
            <div class="progress-bar bg-success" role="progressbar" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  window.initIssuesTab = initIssuesTab;

  // Автоматический запуск, если вкладка уже активна в DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIssuesTab);
  } else {
    initIssuesTab();
  }
})();
