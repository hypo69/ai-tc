/**
 * =============================================================================
 * Process Name: Windows App Internals - Codebase AST & Diagnostic RAG Panel
 * =============================================================================
 * Description:
 *   Модуль клиентского управления базой знаний кода (Codebase AST RAG)
 *   и генерацией структурированных заключений (Root Cause Analysis & Remediation)
 *   по вопросам, спискам логов и сообщениям об ошибках.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_codebase_rag
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 18:36:00
 * =============================================================================
 */

import { notifyUser, escapeHtml } from '../common/ui_utils.js?v=20261031_v5';

let cachedIndexes = [];

/**
 * Загрузка списка всех доступных AST-индексов кодовой базы.
 * @returns {Promise<void>}
 */
export async function loadCodebaseIndexes() {
  const selectDiagnose = document.getElementById('code-rag-diagnose-index');
  const selectSearch = document.getElementById('code-rag-search-index');
  const tableContainer = document.getElementById('code-rag-indexes-list');
  const badgeTotal = document.getElementById('code-rag-total-indexes-badge');

  try {
    const res = await fetch('/api/rag/codebase/indexes');
    if (!res.ok) return;
    const data = await res.json();
    cachedIndexes = data.indexes || [];

    if (badgeTotal) {
      badgeTotal.textContent = `${cachedIndexes.length} инд.`;
    }

    const optionsHtml = cachedIndexes.length > 0
      ? cachedIndexes.map((idx) => {
          const files = idx.total_files || 0;
          const chunks = idx.total_chunks || 0;
          const syms = idx.total_symbols || 0;
          return `<option value="${escapeHtml(idx.name)}">${escapeHtml(idx.name)} (${files} файлов, ${chunks} чанков, ${syms} AST)</option>`;
        }).join('')
      : '<option value="codebase">codebase (По умолчанию)</option>';

    if (selectDiagnose) {
      const cur = selectDiagnose.value;
      selectDiagnose.innerHTML = optionsHtml;
      if (cur && cachedIndexes.some((i) => i.name === cur)) {
        selectDiagnose.value = cur;
      }
    }
    if (selectSearch) {
      const cur = selectSearch.value;
      selectSearch.innerHTML = optionsHtml;
      if (cur && cachedIndexes.some((i) => i.name === cur)) {
        selectSearch.value = cur;
      }
    }

    if (tableContainer) {
      if (cachedIndexes.length === 0) {
        tableContainer.innerHTML = `
          <div class="text-center text-secondary py-3 small">
            <i class="bi bi-folder-x fs-3 d-block mb-1 opacity-50"></i>
            Индексы кодовой базы еще не созданы. Нажмите «Собрать индекс» ниже.
          </div>`;
      } else {
        tableContainer.innerHTML = cachedIndexes.map((idx) => `
          <div class="p-2.5 mb-2 rounded border" style="background: var(--surface-2); border-color: var(--border-color) !important;">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-1">
              <div class="d-flex align-items-center gap-2">
                <i class="bi bi-file-earmark-code text-primary fs-5"></i>
                <span class="fw-bold">${escapeHtml(idx.name)}</span>
                <span class="ui-badge ui-badge-info small">${escapeHtml(idx.scope || 'global')}</span>
              </div>
              <small class="text-secondary font-monospace">${escapeHtml(idx.updated_at || '')}</small>
            </div>
            <div class="small text-secondary mb-1">
              <span>Корень: <code>${escapeHtml(idx.project_root || '.')}</code></span>
            </div>
            <div class="d-flex gap-3 small text-body flex-wrap">
              <span><i class="bi bi-file-text me-1 text-info"></i>Файлов: <strong>${idx.total_files || 0}</strong></span>
              <span><i class="bi bi-layers me-1 text-success"></i>Чанков: <strong>${idx.total_chunks || 0}</strong></span>
              <span><i class="bi bi-tag-fill me-1 text-warning"></i>Символов AST: <strong>${idx.total_symbols || 0}</strong></span>
              <span><i class="bi bi-stopwatch me-1 text-secondary"></i>Время: ${idx.elapsed_seconds || 0}с</span>
            </div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.warn('[CodebaseRAG] Ошибка загрузки индексов:', err);
  }
}

/**
 * Запуск построения или переиндексации кодовой базы.
 * @returns {Promise<void>}
 */
export async function executeBuildIndex() {
  const btn = document.getElementById('btn-code-rag-build');
  const spinner = document.getElementById('code-rag-build-spinner');
  const alertEl = document.getElementById('code-rag-build-status');
  const rootInput = document.getElementById('code-rag-build-root');
  const nameInput = document.getElementById('code-rag-build-name');
  const dirsInput = document.getElementById('code-rag-build-dirs');
  const mdCheck = document.getElementById('code-rag-build-md');

  const projectRoot = rootInput?.value?.trim() || '.';
  const indexName = nameInput?.value?.trim() || 'codebase';
  const dirsStr = dirsInput?.value?.trim() || '';
  const includeDirs = dirsStr ? dirsStr.split(',').map((s) => s.trim()).filter(Boolean) : [];
  const includeMarkdown = mdCheck ? Boolean(mdCheck.checked) : true;

  if (btn) btn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';
  if (alertEl) {
    alertEl.style.display = 'block';
    alertEl.className = 'alert alert-info py-2 small mb-0';
    alertEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сканирование файлов, парсинг AST и генерация эмбеддингов...';
  }

  try {
    const res = await fetch('/api/rag/codebase/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_root: projectRoot,
        index_name: indexName,
        include_dirs: includeDirs,
        include_markdown: includeMarkdown,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    const st = data.result || {};
    if (alertEl) {
      alertEl.className = 'alert alert-success py-2 small mb-0';
      alertEl.innerHTML = `<strong>✓ Индекс «${escapeHtml(indexName)}» успешно создан!</strong><br>
        Файлов: ${st.total_files || 0} | Чанков: ${st.total_chunks || 0} | AST-символов: ${st.total_symbols || 0} (${st.elapsed_seconds || 0}с)`;
    }
    notifyUser(`Индекс «${indexName}» успешно создан (${st.total_chunks} чанков)`, 'success');
    await loadCodebaseIndexes();
  } catch (err) {
    console.error('[CodebaseRAG] Ошибка сборки индекса:', err);
    if (alertEl) {
      alertEl.className = 'alert alert-danger py-2 small mb-0';
      alertEl.textContent = `Ошибка сборки: ${err.message}`;
    }
    notifyUser(`Ошибка сборки индекса: ${err.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (spinner) spinner.style.display = 'none';
  }
}

/**
 * Запуск формирования структурированного заключения по вопросу, логам или ошибке.
 * @returns {Promise<void>}
 */
export async function executeDiagnose() {
  const btn = document.getElementById('btn-code-rag-diagnose');
  const spinner = document.getElementById('code-rag-diagnose-spinner');
  const questionInput = document.getElementById('code-rag-diag-question');
  const errorInput = document.getElementById('code-rag-diag-error');
  const logsInput = document.getElementById('code-rag-diag-logs');
  const selectIndex = document.getElementById('code-rag-diagnose-index');
  const useLlmCheck = document.getElementById('code-rag-diag-use-llm');
  const resultsContainer = document.getElementById('code-rag-diagnose-results');

  const question = questionInput?.value?.trim() || '';
  const errorMessage = errorInput?.value?.trim() || '';
  const rawLogs = logsInput?.value?.trim() || '';
  const logs = rawLogs ? rawLogs.split('\n').map((l) => l.trim()).filter(Boolean) : [];
  const indexName = selectIndex?.value || 'codebase';
  const useLlm = useLlmCheck ? Boolean(useLlmCheck.checked) : true;

  if (!question && !errorMessage && logs.length === 0) {
    notifyUser('Укажите хотя бы один параметр: вопрос, сообщение об ошибке или список логов', 'warning');
    return;
  }

  if (btn) btn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';
  if (resultsContainer) {
    resultsContainer.innerHTML = `
      <div class="text-center py-4 text-primary">
        <span class="spinner-border spinner-border-sm me-2"></span>
        Анализ AST-деревьев, поиск сигнатур и синтез заключения по кодовой базе...
      </div>`;
  }

  try {
    const res = await fetch('/api/rag/codebase/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        logs,
        error_message: errorMessage,
        index_name: indexName,
        top_k: 6,
        use_llm: useLlm,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    }

    renderDiagnosticConclusion(data, resultsContainer);
    notifyUser('Диагностическое заключение сформировано', 'success');
  } catch (err) {
    console.error('[CodebaseRAG] Ошибка диагностики:', err);
    if (resultsContainer) {
      resultsContainer.innerHTML = `
        <div class="alert alert-danger py-2 small mb-0">
          <i class="bi bi-x-circle me-1"></i>Ошибка диагностики: ${escapeHtml(err.message)}
        </div>`;
    }
    notifyUser(`Ошибка диагностики: ${err.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (spinner) spinner.style.display = 'none';
  }
}

/**
 * Рендеринг структурированного диагностического заключения (CodeDiagnosticConclusion).
 * @param {Object} data - Результат от бэкенда
 * @param {HTMLElement} container - DOM-контейнер для вывода
 */
function renderDiagnosticConclusion(data, container) {
  if (!container) return;

  const severityBadge = data.severity === 'critical'
    ? '<span class="ui-badge ui-badge-danger fw-bold"><i class="bi bi-shield-slash-fill me-1"></i>CRITICAL</span>'
    : (data.severity === 'error'
      ? '<span class="ui-badge ui-badge-danger fw-bold"><i class="bi bi-exclamation-octagon-fill me-1"></i>ERROR</span>'
      : (data.severity === 'warning'
        ? '<span class="ui-badge ui-badge-warning fw-bold"><i class="bi bi-exclamation-triangle-fill me-1"></i>WARNING</span>'
        : '<span class="ui-badge ui-badge-info fw-bold"><i class="bi bi-info-circle-fill me-1"></i>INFO</span>'));

  const modeBadge = data.source_mode === 'hybrid_llm'
    ? '<span class="ui-badge ui-badge-success small"><i class="bi bi-robot me-1"></i>Hybrid LLM</span>'
    : '<span class="ui-badge ui-badge-neutral small"><i class="bi bi-cpu me-1"></i>Deterministic AST</span>';

  const locationsHtml = (data.affected_locations || []).length > 0
    ? data.affected_locations.map((loc, idx) => `
        <div class="card mb-2 border shadow-sm">
          <div class="card-header py-1 px-2.5 d-flex justify-content-between align-items-center flex-wrap gap-2" style="background: var(--surface-2);">
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-secondary">#${idx + 1}</span>
              <span class="fw-semibold small font-monospace">
                <i class="bi bi-file-earmark-code me-1 text-primary"></i>${escapeHtml(loc.file_path)}:${loc.start_line}-${loc.end_line}
              </span>
              ${loc.symbol_name ? `<span class="badge bg-primary-subtle text-primary-emphasis">${escapeHtml(loc.symbol_name)} (${escapeHtml(loc.symbol_type)})</span>` : ''}
            </div>
            <span class="ui-badge ui-badge-info small">Score: ${loc.relevance_score || 0}</span>
          </div>
          ${loc.snippet ? `
            <div class="card-body p-2 font-monospace small bg-body-tertiary" style="white-space: pre-wrap; font-size: 0.8rem; max-height: 160px; overflow-y: auto;">
              ${escapeHtml(loc.snippet)}
            </div>` : ''}
        </div>
      `).join('')
    : '<div class="text-muted small">Участки кода не сопоставлены.</div>';

  const remediationHtml = (data.remediation_steps || []).length > 0
    ? data.remediation_steps.map((st, idx) => `
        <li class="list-group-item p-2.5" style="background: var(--surface-2);">
          <div class="fw-semibold text-primary mb-1">
            <span class="badge bg-primary me-1.5">${idx + 1}</span>${escapeHtml(st.title)}
          </div>
          <div class="small text-secondary mb-1">${escapeHtml(st.description)}</div>
          ${st.target_file ? `<div class="small text-muted font-monospace">Целевой файл: <code>${escapeHtml(st.target_file)}</code></div>` : ''}
          ${st.suggested_code ? `<pre class="p-2 mt-1 mb-0 rounded bg-body-tertiary small font-monospace text-body" style="font-size: 0.78rem;"><code>${escapeHtml(st.suggested_code)}</code></pre>` : ''}
        </li>
      `).join('')
    : '<div class="text-muted small">Рекомендации по устранению не сформированы.</div>';

  const signals = data.extracted_signals || {};
  const exceptionsHtml = (signals.exceptions || []).map((e) => `<span class="badge bg-danger-subtle text-danger-emphasis me-1">${escapeHtml(e.type)}</span>`).join('') || '<span class="text-muted small">—</span>';
  const filesHtml = (signals.files || []).map((f) => `<span class="badge bg-secondary-subtle text-secondary-emphasis me-1 font-monospace">${escapeHtml(f)}</span>`).join('') || '<span class="text-muted small">—</span>';
  const symbolsHtml = (signals.symbols || []).slice(0, 10).map((s) => `<span class="badge bg-info-subtle text-info-emphasis me-1 font-monospace">${escapeHtml(s)}</span>`).join('') || '<span class="text-muted small">—</span>';

  container.innerHTML = `
    <div class="card border mb-3 shadow-sm" style="border-color: var(--border-color) !important;">
      <div class="card-header py-2 d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div class="d-flex align-items-center gap-2">
          ${severityBadge}
          <h6 class="mb-0 fw-bold">Инженерное заключение по коду</h6>
          ${modeBadge}
        </div>
        <div class="small text-secondary">
          <span>Уверенность: <strong>${Math.round((data.confidence || 0) * 100)}%</strong></span>
          <span class="ms-2">(${data.execution_time_ms || 0} мс)</span>
        </div>
      </div>
      <div class="card-body p-3">
        <!-- Резюме -->
        <div class="alert alert-secondary py-2 px-3 mb-3 small d-flex align-items-start gap-2">
          <i class="bi bi-info-circle-fill text-primary fs-5 mt-0.5"></i>
          <div>
            <strong>Резюме:</strong> ${escapeHtml(data.summary || '')}
          </div>
        </div>

        <!-- Первопричина -->
        <div class="p-2.5 mb-3 rounded border" style="background: var(--surface-2); border-color: var(--border-color) !important;">
          <div class="fw-bold text-danger mb-1"><i class="bi bi-bullseye me-1.5"></i>Первопричина (Root Cause):</div>
          <div class="small text-body">${escapeHtml(data.root_cause || '')}</div>
        </div>

        <!-- Объяснение -->
        ${data.explanation ? `
          <div class="mb-3">
            <div class="fw-semibold small text-secondary mb-1"><i class="bi bi-body-text me-1"></i>Развернутое техническое объяснение:</div>
            <div class="small text-body p-2.5 rounded border" style="background: var(--surface-1);">${escapeHtml(data.explanation)}</div>
          </div>` : ''}

        <!-- Извлеченные сигналы -->
        <div class="mb-3 p-2 rounded border small" style="background: var(--surface-2);">
          <div class="fw-semibold text-secondary mb-1.5"><i class="bi bi-radar me-1"></i>Сигналы, извлеченные из логов и ошибки:</div>
          <div class="mb-1"><strong>Исключения:</strong> ${exceptionsHtml}</div>
          <div class="mb-1"><strong>Файлы:</strong> ${filesHtml}</div>
          <div><strong>Символы AST:</strong> ${symbolsHtml}</div>
        </div>

        <!-- Затронутые участки кода -->
        <div class="mb-3">
          <div class="fw-semibold small text-secondary mb-1.5"><i class="bi bi-diagram-3 me-1"></i>Затронутые файлы и функции в кодовой базе (${(data.affected_locations || []).length}):</div>
          ${locationsHtml}
        </div>

        <!-- Шаги устранения -->
        <div>
          <div class="fw-semibold small text-secondary mb-1.5"><i class="bi bi-wrench-adjustable me-1"></i>Рекомендуемые шаги исправления (Remediation):</div>
          <ul class="list-group list-group-flush border rounded shadow-sm">
            ${remediationHtml}
          </ul>
        </div>
      </div>
    </div>
  `;
}

/**
 * Запуск поиска по AST-символам.
 * @returns {Promise<void>}
 */
export async function executeSymbolSearch() {
  const input = document.getElementById('code-rag-symbol-query');
  const select = document.getElementById('code-rag-search-index');
  const resultsContainer = document.getElementById('code-rag-search-results');
  const query = input?.value?.trim() || '';

  if (!query) {
    notifyUser('Введите имя символа (функции, класса или метода)', 'warning');
    return;
  }

  const indexName = select?.value || 'codebase';
  if (resultsContainer) {
    resultsContainer.innerHTML = '<div class="text-center py-3 text-primary"><span class="spinner-border spinner-border-sm me-2"></span> Поиск по символам AST...</div>';
  }

  try {
    const res = await fetch('/api/rag/codebase/symbols', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: query, index_name: indexName, limit: 12 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    const results = data.results || [];
    if (results.length === 0) {
      resultsContainer.innerHTML = `<div class="text-center text-muted py-3 small">Символ «${escapeHtml(query)}» не найден.</div>`;
      return;
    }

    resultsContainer.innerHTML = results.map((s) => `
      <div class="card mb-2 border shadow-sm">
        <div class="card-header py-1 px-2.5 d-flex justify-content-between align-items-center" style="background: var(--surface-2);">
          <div class="d-flex align-items-center gap-1.5">
            <i class="bi bi-tag-fill text-success"></i>
            <span class="fw-bold small">${escapeHtml(s.symbol)}</span>
            <span class="badge bg-secondary small">${escapeHtml(s.type)}</span>
          </div>
          <span class="small font-monospace text-muted">${escapeHtml(s.path)}:${s.start_line}-${s.end_line}</span>
        </div>
        <div class="card-body p-2 small">
          ${s.signature ? `<div class="font-monospace text-primary mb-1"><code>${escapeHtml(s.signature)}</code></div>` : ''}
          ${s.docstring ? `<div class="text-secondary mb-1"><em>${escapeHtml(s.docstring)}</em></div>` : ''}
          ${(s.related_symbols || []).length > 0 ? `<div class="text-muted small">Связи: ${escapeHtml(s.related_symbols.slice(0, 8).join(', '))}</div>` : ''}
        </div>
      </div>
    `).join('');
  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `<div class="alert alert-danger py-2 small mb-0">Ошибка: ${escapeHtml(err.message)}</div>`;
    }
  }
}

/**
 * Запуск гибридного поиска по коду и чанкам документации.
 * @returns {Promise<void>}
 */
export async function executeCodeSearch() {
  const input = document.getElementById('code-rag-code-query');
  const select = document.getElementById('code-rag-search-index');
  const resultsContainer = document.getElementById('code-rag-search-results');
  const query = input?.value?.trim() || '';

  if (!query) {
    notifyUser('Введите поисковый запрос по коду', 'warning');
    return;
  }

  const indexName = select?.value || 'codebase';
  if (resultsContainer) {
    resultsContainer.innerHTML = '<div class="text-center py-3 text-primary"><span class="spinner-border spinner-border-sm me-2"></span> Гибридный семантический поиск...</div>';
  }

  try {
    const res = await fetch('/api/rag/codebase/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, index_name: indexName, top_k: 6 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    const results = data.results || [];
    if (results.length === 0) {
      resultsContainer.innerHTML = `<div class="text-center text-muted py-3 small">По запросу «${escapeHtml(query)}» совпадений не найдено.</div>`;
      return;
    }

    resultsContainer.innerHTML = results.map((r) => `
      <div class="card mb-2 border shadow-sm">
        <div class="card-header py-1 px-2.5 d-flex justify-content-between align-items-center" style="background: var(--surface-2);">
          <span class="small fw-semibold text-truncate">
            <i class="bi bi-code-slash me-1 text-primary"></i>${escapeHtml(r.id)}
          </span>
          <span class="ui-badge ui-badge-info small">Score: ${r.similarity_score || 0}</span>
        </div>
        <div class="card-body p-2 font-monospace small bg-body-tertiary" style="white-space: pre-wrap; font-size: 0.8rem; max-height: 140px; overflow-y: auto;">
          ${escapeHtml(r.text)}
        </div>
      </div>
    `).join('');
  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `<div class="alert alert-danger py-2 small mb-0">Ошибка: ${escapeHtml(err.message)}</div>`;
    }
  }
}

/**
 * Привязка событий кнопок и полей ввода панели Codebase RAG.
 */
export function bindCodebaseRagButtons() {
  const btnBuild = document.getElementById('btn-code-rag-build');
  if (btnBuild && !btnBuild._bound) {
    btnBuild._bound = true;
    btnBuild.addEventListener('click', executeBuildIndex);
  }

  const btnDiagnose = document.getElementById('btn-code-rag-diagnose');
  if (btnDiagnose && !btnDiagnose._bound) {
    btnDiagnose._bound = true;
    btnDiagnose.addEventListener('click', executeDiagnose);
  }

  const btnSymbolSearch = document.getElementById('btn-code-rag-symbol-search');
  if (btnSymbolSearch && !btnSymbolSearch._bound) {
    btnSymbolSearch._bound = true;
    btnSymbolSearch.addEventListener('click', executeSymbolSearch);
  }

  const btnCodeSearch = document.getElementById('btn-code-rag-code-search');
  if (btnCodeSearch && !btnCodeSearch._bound) {
    btnCodeSearch._bound = true;
    btnCodeSearch.addEventListener('click', executeCodeSearch);
  }

  const symbolInput = document.getElementById('code-rag-symbol-query');
  if (symbolInput && !symbolInput._bound) {
    symbolInput._bound = true;
    symbolInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') executeSymbolSearch();
    });
  }

  const codeInput = document.getElementById('code-rag-code-query');
  if (codeInput && !codeInput._bound) {
    codeInput._bound = true;
    codeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') executeCodeSearch();
    });
  }
}

/**
 * Инициализация суб-панели управления Codebase AST & Diagnostic RAG.
 * @returns {Promise<void>}
 */
export async function initCodebaseRagPanel() {
  bindCodebaseRagButtons();
  await loadCodebaseIndexes();
}
