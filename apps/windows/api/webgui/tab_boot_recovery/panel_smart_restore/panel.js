/**
 * =============================================================================
 * Process Name: Windows Boot Recovery - Smart Restore Advisor Panel
 * =============================================================================
 * Description:
 *   Модуль умного создания и мониторинга контрольных точек восстановления
 *   Windows (RestorePointAdvisor).
 *
 * File: panel_smart_restore/panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_boot_recovery/panel_smart_restore
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

let isSmartRestoreInitialized = false;
let _lastEvaluation = null;

/**
 * Инициализация панели умного восстановления.
 */
export async function initSmartRestorePanel() {
  bindSmartRestoreEvents();
  if (!isSmartRestoreInitialized) {
    isSmartRestoreInitialized = true;
    await loadAdvisorData();
    await loadAdvisorJournalData();
  }
}

/**
 * Привязка событий элементов управления умного восстановления.
 */
export function bindSmartRestoreEvents() {
  const btnEval = document.getElementById('btn-smart-restore-evaluate');
  if (btnEval && !btnEval.dataset.bound) {
    btnEval.dataset.bound = 'true';
    btnEval.onclick = async () => {
      await loadAdvisorData();
    };
  }

  const btnCreate = document.getElementById('btn-smart-restore-create');
  if (btnCreate && !btnCreate.dataset.bound) {
    btnCreate.dataset.bound = 'true';
    btnCreate.onclick = async () => {
      await executeSmartCreate();
    };
  }

  const btnExplain = document.getElementById('btn-smart-restore-explain');
  if (btnExplain && !btnExplain.dataset.bound) {
    btnExplain.dataset.bound = 'true';
    btnExplain.onclick = async () => {
      await showAdvisorAiExplanation();
    };
  }
}

/**
 * Загрузка оценки необходимости создания точки восстановления.
 */
export async function loadAdvisorData() {
  const triggerSel = document.getElementById('smart-restore-trigger');
  const trigger = triggerSel ? triggerSel.value : 'USER_REQUEST';
  const btnEval = document.getElementById('btn-smart-restore-evaluate');

  if (btnEval) {
    btnEval.disabled = true;
    btnEval.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Оценка...';
  }

  try {
    const res = await fetch(`/api/v1/windows-checkpoints/advisor/evaluate?trigger=${encodeURIComponent(trigger)}`);
    if (!res.ok) {
      throw new Error(`Ошибка сервера: ${res.status}`);
    }
    const data = await res.json();
    _lastEvaluation = data;
    renderAdvisorEvaluation(data);
  } catch (e) {
    console.error('[SmartRestore] Ошибка получения оценки:', e);
    renderAdvisorError(e.message);
  } finally {
    if (btnEval) {
      btnEval.disabled = false;
      btnEval.innerHTML = '<i class="bi bi-search"></i> <span>Оценить</span>';
    }
  }
}

/**
 * Рендеринг карточек и вердиктов оценки Advisor.
 * @param {Object} data
 */
export function renderAdvisorEvaluation(data) {
  if (!data) return;

  // Решение Advisor
  const kpiDecision = document.getElementById('kpi-advisor-decision');
  const kpiDecisionSub = document.getElementById('kpi-advisor-decision-sub');
  const decision = data.decision || 'UNKNOWN';

  let decisionClass = 'text-muted';
  let decisionText = decision;

  if (decision === 'CREATE') {
    decisionClass = 'text-success';
    decisionText = '🟢 СОЗДАТЬ';
  } else if (decision === 'SKIP') {
    decisionClass = 'text-primary';
    decisionText = '🔵 ПРОПУСТИТЬ';
  } else if (decision === 'MONITOR') {
    decisionClass = 'text-warning';
    decisionText = '🟡 НАБЛЮДЕНИЕ';
  } else if (decision === 'CLARIFY') {
    decisionClass = 'text-danger';
    decisionText = '🔴 УТОЧНИТЬ';
  }

  if (kpiDecision) {
    kpiDecision.className = `fs-4 fw-bold mt-2 ${decisionClass}`;
    kpiDecision.textContent = decisionText;
  }
  if (kpiDecisionSub) {
    kpiDecisionSub.textContent = data.summary || 'Оценка выполнена';
  }

  // Вопрос 1: Есть ли смысл?
  const q1 = data.questions?.q1 || {};
  const kpiQ1 = document.getElementById('kpi-advisor-q1');
  const kpiQ1Sub = document.getElementById('kpi-advisor-q1-sub');
  const badgeQ1 = document.getElementById('badge-q1-verdict');
  const textQ1 = document.getElementById('text-q1-explanation');

  if (kpiQ1) {
    kpiQ1.textContent = q1.verdict || '--';
    kpiQ1.className = `fs-4 fw-bold mt-2 ${q1.meaningful_changes ? 'text-success' : 'text-muted'}`;
  }
  if (kpiQ1Sub) kpiQ1Sub.textContent = q1.meaningful_changes ? 'Есть значимые изменения' : 'Без изменений';
  if (badgeQ1) {
    badgeQ1.className = `badge ${q1.meaningful_changes ? 'bg-success' : 'bg-secondary'}`;
    badgeQ1.textContent = q1.verdict || '--';
  }
  if (textQ1) textQ1.textContent = q1.explanation || '';

  // Вопрос 2: Не дублирует ли?
  const q2 = data.questions?.q2 || {};
  const kpiQ2 = document.getElementById('kpi-advisor-q2');
  const kpiQ2Sub = document.getElementById('kpi-advisor-q2-sub');
  const badgeQ2 = document.getElementById('badge-q2-verdict');
  const textQ2 = document.getElementById('text-q2-explanation');

  if (kpiQ2) {
    kpiQ2.textContent = q2.verdict || '--';
    kpiQ2.className = `fs-4 fw-bold mt-2 ${q2.is_duplicate ? 'text-primary' : 'text-info'}`;
  }
  if (kpiQ2Sub) kpiQ2Sub.textContent = q2.is_duplicate ? 'Отпечаток совпадает' : 'Отпечаток уникален';
  if (badgeQ2) {
    badgeQ2.className = `badge ${q2.is_duplicate ? 'bg-primary' : 'bg-info text-dark'}`;
    badgeQ2.textContent = q2.verdict || '--';
  }
  if (textQ2) textQ2.textContent = q2.explanation || '';

  // Вопрос 3: Условия VSS и защита
  const q3 = data.questions?.q3 || {};
  const kpiQ3 = document.getElementById('kpi-advisor-q3');
  const kpiQ3Sub = document.getElementById('kpi-advisor-q3-sub');
  const badgeQ3 = document.getElementById('badge-q3-verdict');
  const textQ3 = document.getElementById('text-q3-explanation');

  if (kpiQ3) {
    kpiQ3.textContent = q3.verdict || '--';
    kpiQ3.className = `fs-4 fw-bold mt-2 ${q3.can_restore ? 'text-success' : 'text-danger'}`;
  }
  if (kpiQ3Sub) kpiQ3Sub.textContent = q3.can_restore ? 'Защита включена (OK)' : 'Защита отключена / сбой';
  if (badgeQ3) {
    badgeQ3.className = `badge ${q3.can_restore ? 'bg-success' : 'bg-danger'}`;
    badgeQ3.textContent = q3.verdict || '--';
  }
  if (textQ3) textQ3.textContent = q3.explanation || '';

  // Композитный отпечаток
  const badgeHash = document.getElementById('badge-composite-hash');
  if (badgeHash) {
    const compHash = data.composite_fingerprint || '';
    badgeHash.textContent = compHash ? `Fingerprint: ${compHash.substring(0, 16)}...` : 'Fingerprint: --';
    badgeHash.title = compHash;
  }

  // Резюме и рекомендация
  const summaryText = document.getElementById('text-advisor-summary');
  const recText = document.getElementById('text-advisor-recommendation');
  if (summaryText) summaryText.textContent = data.summary || '';
  if (recText) recText.textContent = data.recommended_action ? `💡 ${data.recommended_action}` : '';

  renderAdvisorCategoriesTable(data.categories || {});
  renderAdvisorDeltasTable(data.deltas || []);
}

/**
 * Отрисовка таблицы категорий телеметрии системы.
 * @param {Object} categories
 */
export function renderAdvisorCategoriesTable(categories) {
  const tbody = document.getElementById('tbody-categories');
  if (!tbody) return;

  const entries = Object.entries(categories);
  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Нет данных категорий.</td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(([key, cat]) => {
    let impBadge = 'bg-secondary';
    if (cat.importance === 'HIGH') impBadge = 'bg-danger';
    else if (cat.importance === 'MEDIUM') impBadge = 'bg-warning text-dark';

    const changedBadge = cat.changed
      ? '<span class="badge bg-warning text-dark">Изменено</span>'
      : '<span class="badge bg-success">Без изменений</span>';

    return `
      <tr>
        <td class="px-3 py-2 fw-semibold">${cat.category_title_ru || key}</td>
        <td class="px-3 py-2"><span class="badge ${impBadge}">${cat.importance}</span></td>
        <td class="px-3 py-2 font-monospace">${cat.items_count || 0}</td>
        <td class="px-3 py-2 font-monospace text-muted" title="${cat.hash}">${cat.hash ? cat.hash.substring(0, 12) + '...' : '--'}</td>
        <td class="px-3 py-2">${changedBadge}</td>
        <td class="px-3 py-2 small text-muted">${cat.details || ''}</td>
      </tr>
    `;
  }).join('');
}

/**
 * Отрисовка таблицы изменений (дельт) с прошлой точки.
 * @param {Array<Object>} deltas
 */
export function renderAdvisorDeltasTable(deltas) {
  const tbody = document.getElementById('tbody-deltas');
  const badgeCount = document.getElementById('badge-deltas-count');

  if (badgeCount) {
    badgeCount.textContent = deltas.length;
    badgeCount.className = `badge ${deltas.length > 0 ? 'bg-warning text-dark' : 'bg-secondary'} ms-1`;
  }

  if (!tbody) return;

  if (!deltas.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">Нет зафиксированных изменений с момента предыдущей точки восстановления.</td></tr>';
    return;
  }

  tbody.innerHTML = deltas.map(d => {
    let typeBadge = 'bg-info text-dark';
    if (d.change_type === 'ADDED') typeBadge = 'bg-success';
    else if (d.change_type === 'REMOVED') typeBadge = 'bg-danger';
    else if (d.change_type === 'MODIFIED') typeBadge = 'bg-warning text-dark';

    let impBadge = d.importance === 'HIGH' ? 'bg-danger' : (d.importance === 'MEDIUM' ? 'bg-warning text-dark' : 'bg-secondary');

    return `
      <tr>
        <td class="px-3 py-2 fw-semibold">${d.category}</td>
        <td class="px-3 py-2"><span class="badge ${typeBadge}">${d.change_type}</span></td>
        <td class="px-3 py-2 font-monospace text-truncate" style="max-width: 180px;" title="${d.item_key}">${d.item_key}</td>
        <td class="px-3 py-2"><span class="badge ${impBadge}">${d.importance}</span></td>
        <td class="px-3 py-2 small">${d.details || ''}</td>
      </tr>
    `;
  }).join('');
}

/**
 * Загрузка журнала решений советника точек восстановления.
 */
export async function loadAdvisorJournalData() {
  const tbody = document.getElementById('tbody-journal');
  try {
    const res = await fetch('/api/v1/windows-checkpoints/advisor/journal?limit=25');
    if (!res.ok) return;
    const list = await res.json();

    if (!tbody) return;

    if (!list || !list.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Журнал состояний пуст.</td></tr>';
      return;
    }

    tbody.innerHTML = list.map(item => {
      let decBadge = 'bg-secondary';
      if (item.decision === 'CREATE') decBadge = 'bg-success';
      else if (item.decision === 'SKIP') decBadge = 'bg-primary';
      else if (item.decision === 'MONITOR') decBadge = 'bg-warning text-dark';
      else if (item.decision === 'CLARIFY') decBadge = 'bg-danger';

      const createdIcon = item.is_restore_point
        ? '<span class="badge bg-success"><i class="bi bi-check-lg me-1"></i>Создана</span>'
        : '<span class="badge bg-secondary">Пропущена</span>';

      const timeStr = item.timestamp ? item.timestamp.substring(0, 19).replace('T', ' ') : '--';
      const compHash = item.composite_fingerprint ? item.composite_fingerprint.substring(0, 12) + '...' : '--';

      return `
        <tr>
          <td class="px-3 py-2 small font-monospace">${timeStr}</td>
          <td class="px-3 py-2 small fw-semibold">${item.trigger_event || 'USER_REQUEST'}</td>
          <td class="px-3 py-2"><span class="badge ${decBadge}">${item.decision || ''}</span></td>
          <td class="px-3 py-2">${createdIcon}</td>
          <td class="px-3 py-2 small font-monospace text-muted" title="${item.composite_fingerprint}">${compHash}</td>
          <td class="px-3 py-2 small text-truncate" style="max-width: 260px;" title="${item.summary || ''}">${item.summary || ''}</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.warn('[SmartRestore] Не удалось загрузить журнал:', e);
  }
}

/**
 * Выполнение умного создания контрольной точки.
 */
export async function executeSmartCreate() {
  const btnCreate = document.getElementById('btn-smart-restore-create');
  const triggerSel = document.getElementById('smart-restore-trigger');
  const titleInput = document.getElementById('smart-restore-title');
  const forceCheck = document.getElementById('smart-restore-force');

  const trigger = triggerSel ? triggerSel.value : 'USER_REQUEST';
  const title = titleInput ? titleInput.value.trim() : '';
  const force = forceCheck ? forceCheck.checked : false;

  if (btnCreate) {
    btnCreate.disabled = true;
    btnCreate.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Выполнение...';
  }

  try {
    const payload = {
      title: title || null,
      trigger: trigger,
      force: force,
      checkpoint_type: 'PERIODIC',
    };

    const res = await fetch('/api/v1/windows-checkpoints/advisor/create-smart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const result = await res.json();

    if (result.created) {
      alert(`✅ Точка восстановления успешно создана!\n\n${result.message || ''}`);
    } else {
      alert(`ℹ️ Создание точки не потребовалось:\n\n${result.message || ''}\nРешение: ${result.decision || ''}`);
    }

    await loadAdvisorData();
    await loadAdvisorJournalData();
  } catch (e) {
    alert(`❌ Ошибка выполнения: ${e.message}`);
  } finally {
    if (btnCreate) {
      btnCreate.disabled = false;
      btnCreate.innerHTML = '<i class="bi bi-shield-plus"></i> <span>Умное создание</span>';
    }
  }
}

/**
 * Запрос ИИ-пояснения логики советника точек восстановления.
 */
export async function showAdvisorAiExplanation() {
  const triggerSel = document.getElementById('smart-restore-trigger');
  const trigger = triggerSel ? triggerSel.value : 'USER_REQUEST';

  try {
    const res = await fetch('/api/v1/windows-checkpoints/advisor/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trigger }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    alert(`🤖 Пояснение советника RestorePointAdvisor:\n\n${data.explanation || data.summary || 'Нет данных'}`);
  } catch (e) {
    alert(`Ошибка получения пояснения: ${e.message}`);
  }
}

/**
 * Отображение ошибки оценки Advisor в интерфейсе.
 * @param {string} msg
 */
export function renderAdvisorError(msg) {
  const summaryText = document.getElementById('text-advisor-summary');
  if (summaryText) summaryText.textContent = `Ошибка оценки: ${msg}`;
}
