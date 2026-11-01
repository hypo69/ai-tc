/**
 * =============================================================================
 * Process Name: Windows Web Interface - User Environment: Windows & Desktop Panel
 * =============================================================================
 * Description:
 *   Клиентский контроллер активных окон рабочего стола Windows.
 *   Обеспечивает мониторинг всех окон, переключение фокуса, сворачивание,
 *   разворачивание, закрытие, пакетные операции и глубокий ИИ-анализ (AI Copilot).
 *
 * File: panel_windows.js
 * Package: apps.windows.api.webgui.tab_user_environment
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:01:30
 * =============================================================================
 */

let _windowsCache = [];

/**
 * Вызов всплывающего уведомления Toast.
 * @param {string} msg Текст сообщения.
 * @param {'info'|'success'|'warning'|'danger'} type Тип уведомления.
 */
function showToast(msg, type = 'info') {
  if (window.showToast && typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    console.log(`[UEWindows] [${type}] ${msg}`);
  }
}

/**
 * Экранирование HTML.
 * @param {string} str Входная строка.
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Возвращает текущий кэш окон.
 * @returns {Array<Object>}
 */
export function getWindowsCache() {
  return _windowsCache;
}

/**
 * Загрузка списка открытых окон рабочего стола.
 */
export async function loadWindows() {
  const tbody = document.getElementById('ue-tbody-windows-list');
  try {
    const res = await fetch('/api/v1/taskbar/windows?only_visible=false&only_taskbar=false');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _windowsCache = await res.json();
    renderWindowsTable();
    populateWindowSelects();
    updateWindowsKpis();
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-danger p-3 text-center">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

/**
 * Обновление счетчиков и активного окна в KPI блоке.
 */
function updateWindowsKpis() {
  const kpiCount = document.getElementById('ue-kpi-windows-count');
  const kpiFg = document.getElementById('ue-kpi-windows-fg');
  if (kpiCount) kpiCount.textContent = _windowsCache.length;

  const fgWin = _windowsCache.find((w) => w.is_foreground);
  if (kpiFg) {
    kpiFg.textContent = fgWin ? (fgWin.title || fgWin.process_name || 'Окно без имени') : '—';
  }
}

/**
 * Отрисовка таблицы окон с учетом фильтра.
 */
export function renderWindowsTable() {
  const tbody = document.getElementById('ue-tbody-windows-list');
  const filter = (document.getElementById('ue-input-search-windows')?.value || '').toLowerCase();
  if (!tbody) return;

  const filtered = _windowsCache.filter((w) => {
    if (!filter) return w.title;
    return (w.title || '').toLowerCase().includes(filter) ||
           (w.process_name || '').toLowerCase().includes(filter) ||
           String(w.hwnd).includes(filter);
  });

  const countBadge = document.getElementById('ue-badge-windows-count');
  if (countBadge) countBadge.textContent = filtered.length;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted p-4 text-center">Окна по фильтру не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map((w) => {
    const isFg = w.is_foreground ? '<span class="badge bg-warning text-dark me-1">Фокус</span>' : '';
    const stateBadge = w.is_hung
      ? '<span class="badge bg-danger">Не отвечает</span>'
      : w.is_minimized
        ? '<span class="badge bg-secondary">Свернуто</span>'
        : w.is_maximized
          ? '<span class="badge bg-success">Развернуто</span>'
          : '<span class="badge bg-info text-dark">Нормальное</span>';

    return `
      <tr class="${w.is_foreground ? 'table-active' : ''} interactive-table-row" data-hwnd="${w.hwnd}" style="cursor: pointer;" title="Нажмите для подробного ИИ-разбора окна и процесса">
        <td><code class="user-select-all">${w.hwnd}</code></td>
        <td class="text-truncate" style="max-width: 280px;" title="${escapeHtml(w.title)}">
          ${isFg}<strong>${escapeHtml(w.title || '(Без названия)')}</strong>
          ${w.class_name ? `<div class="text-muted small text-truncate" style="max-width: 260px;">Класс: ${escapeHtml(w.class_name)}</div>` : ''}
        </td>
        <td>
          <div class="fw-semibold text-truncate" style="max-width: 160px;" title="${escapeHtml(w.exe_path || w.process_name || '')}">${escapeHtml(w.process_name || '—')}</div>
          <div class="text-muted small">PID: ${w.process_id}${w.memory_mb ? ` • ${w.memory_mb} МБ` : ''}</div>
        </td>
        <td>
          <small class="text-muted d-block">${w.rect.width} × ${w.rect.height}</small>
          <small class="text-secondary" style="font-size: 0.72rem;">(${w.rect.left}, ${w.rect.top})</small>
        </td>
        <td>${stateBadge}</td>
        <td class="text-end no-modal-trigger">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary ue-btn-win-activate" data-hwnd="${w.hwnd}" title="На передний план">
              <i class="bi bi-box-arrow-in-up-right"></i>
            </button>
            <button class="btn btn-outline-secondary ue-btn-win-minimize" data-hwnd="${w.hwnd}" title="Свернуть">
              <i class="bi bi-dash"></i>
            </button>
            <button class="btn btn-outline-secondary ue-btn-win-maximize" data-hwnd="${w.hwnd}" title="Развернуть">
              <i class="bi bi-square"></i>
            </button>
            <button class="btn btn-outline-secondary ue-btn-win-restore" data-hwnd="${w.hwnd}" title="Восстановить">
              <i class="bi bi-arrow-counterclockwise"></i>
            </button>
            <button class="btn btn-outline-danger ue-btn-win-close" data-hwnd="${w.hwnd}" title="Закрыть окно">
              <i class="bi bi-x"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Привязка действий над окнами
  tbody.querySelectorAll('.ue-btn-win-activate').forEach((btn) => {
    const hwnd = parseInt(btn.getAttribute('data-hwnd'), 10);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeWindowAction(hwnd, 'activate');
    });
  });

  tbody.querySelectorAll('.ue-btn-win-minimize').forEach((btn) => {
    const hwnd = parseInt(btn.getAttribute('data-hwnd'), 10);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeWindowAction(hwnd, 'minimize');
    });
  });

  tbody.querySelectorAll('.ue-btn-win-maximize').forEach((btn) => {
    const hwnd = parseInt(btn.getAttribute('data-hwnd'), 10);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeWindowAction(hwnd, 'maximize');
    });
  });

  tbody.querySelectorAll('.ue-btn-win-restore').forEach((btn) => {
    const hwnd = parseInt(btn.getAttribute('data-hwnd'), 10);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeWindowAction(hwnd, 'restore');
    });
  });

  tbody.querySelectorAll('.ue-btn-win-close').forEach((btn) => {
    const hwnd = parseInt(btn.getAttribute('data-hwnd'), 10);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      executeWindowAction(hwnd, 'close');
    });
  });

  // Клик по строке открывает модальное окно анализа
  tbody.querySelectorAll('tr.interactive-table-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('.no-modal-trigger')) return;
      const hwnd = parseInt(row.getAttribute('data-hwnd'), 10);
      openWindowCopilotModal(hwnd);
    });
  });
}

/**
 * Заполнение выпадающих списков выбора окон (например, для UX progress).
 */
export function populateWindowSelects() {
  const selProgress = document.getElementById('ue-tb-select-progress-hwnd');
  if (!selProgress) return;

  const currentVal = selProgress.value;
  selProgress.innerHTML = '<option value="">-- Выберите целевое окно --</option>' +
    _windowsCache
      .filter((w) => w.title && !w.is_minimized)
      .map((w) => `<option value="${w.hwnd}">${escapeHtml(w.title)} [${w.process_name}]</option>`)
      .join('');

  if (currentVal) selProgress.value = currentVal;
}

/**
 * Выполнение действия над окном.
 * @param {number} hwnd Дескриптор окна.
 * @param {'activate'|'minimize'|'maximize'|'restore'|'close'} action Действие.
 */
export async function executeWindowAction(hwnd, action) {
  try {
    let url = `/api/v1/taskbar/windows/${hwnd}/${action}`;
    let method = 'POST';
    if (action === 'close') {
      url = `/api/v1/taskbar/windows/${hwnd}`;
      method = 'DELETE';
    }
    const res = await fetch(url, { method });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`Действие '${action}' успешно выполнено`, 'success');
    await loadWindows();
  } catch (err) {
    showToast(`Ошибка операции с окном: ${err.message}`, 'danger');
  }
}

/**
 * Пакетное действие над окнами (minimize_all, restore_all).
 * @param {'minimize_all'|'restore_all'} action Пакетная команда.
 */
export async function executeBatchWindowAction(action) {
  try {
    const res = await fetch('/api/v1/taskbar/windows/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(action === 'minimize_all' ? 'Все окна свернуты' : 'Все окна восстановлены', 'info');
    await loadWindows();
  } catch (err) {
    showToast(`Ошибка пакетной операции: ${err.message}`, 'danger');
  }
}

/**
 * Открытие универсального модального окна ИИ-Copilot для глубокой инспекции окна и процесса.
 * @param {number} hwnd Дескриптор окна.
 */
export async function openWindowCopilotModal(hwnd) {
  let win = _windowsCache.find((w) => w.hwnd === hwnd);
  if (!win) return;

  // Запрашиваем свежий срез данных конкретного окна по HWND для максимальной точности
  try {
    const freshRes = await fetch(`/api/v1/taskbar/windows/${hwnd}`);
    if (freshRes.ok) {
      const freshWin = await freshRes.json();
      if (freshWin && freshWin.hwnd) {
        win = freshWin;
      }
    }
  } catch (_) {}

  const badges = [
    {
      text: win.is_foreground ? 'Активный фокус' : 'Фоновое окно',
      class: win.is_foreground ? 'badge bg-warning text-dark' : 'badge bg-secondary'
    },
    {
      text: win.is_hung ? 'Не отвечает (Зависло)' : win.is_minimized ? 'Свернуто' : win.is_maximized ? 'Развернуто' : 'Нормальное',
      class: win.is_hung ? 'badge bg-danger' : win.is_maximized ? 'badge bg-success' : 'badge bg-info text-dark'
    }
  ];

  if (win.is_topmost) {
    badges.push({ text: 'Поверх всех окон (Topmost)', class: 'badge bg-primary-subtle text-primary border border-primary-subtle' });
  }
  if (win.is_tool_window) {
    badges.push({ text: 'ToolWindow', class: 'badge bg-secondary-subtle text-secondary border border-secondary-subtle' });
  }

  const styleFlagsStr = Array.isArray(win.style_flags) && win.style_flags.length > 0
    ? win.style_flags.join(', ')
    : `${win.style_hex || '—'} / ${win.ex_style_hex || '—'}`;

  const parentStr = win.parent_process_name
    ? `${win.parent_process_name} (PPID: ${win.parent_pid || 0})`
    : (win.parent_pid ? `PPID: ${win.parent_pid}` : '—');

  const metadataItems = [
    { label: 'Заголовок окна', value: win.title || '(Без названия)' },
    { label: 'Дескриптор HWND / TID', value: `${win.hwnd} (Поток TID: ${win.thread_id || '—'})` },
    { label: 'Класс окна (Win32)', value: win.class_name || 'Неизвестно' },
    { label: 'Назначение / Роль окна', value: win.window_role_hint || 'Стандартное окно рабочего стола' },
    { label: 'Процесс-владелец', value: `${win.process_name || 'Неизвестно'} (PID: ${win.process_id})` },
    { label: 'Родительский процесс', value: parentStr },
    { label: 'Исполняемый файл (.exe)', value: win.exe_path || win.process_name || 'Недоступно (системный процесс)' },
    { label: 'Командная строка', value: win.cmdline || win.exe_path || '—' },
    { label: 'Пользователь', value: win.username || 'Текущая сессия' },
    { label: 'Габариты (Ш × В)', value: `${win.rect.width} × ${win.rect.height} пикс.` },
    { label: 'Координаты экрана (X, Y)', value: `Лево: ${win.rect.left}, Верх: ${win.rect.top} (Право: ${win.rect.right}, Низ: ${win.rect.bottom})` },
    { label: 'Память и потоки процесса', value: `${win.memory_mb || 0} МБ (Working Set) • Потоков: ${win.threads_count || '—'}` },
    { label: 'Флаги стилей Win32', value: styleFlagsStr },
    { label: 'Статус отклика окна', value: win.is_hung ? 'Зависло (IsHungAppWindow = True)' : 'Отвечает штатно' }
  ];

  if (window.AIModalDialog && typeof window.AIModalDialog.show === 'function') {
    window.AIModalDialog.show({
      title: win.title || win.process_name || `Окно HWND ${win.hwnd}`,
      subtitle: `${win.process_name || 'Процесс'} (PID: ${win.process_id}) | Класс: ${win.class_name || 'Win32'} | HWND: ${win.hwnd}`,
      icon: '🪟',
      panelId: 'panel-windows',
      tableType: 'desktop_window',
      badges,
      metadata: metadataItems,
      requestData: {
        hwnd: win.hwnd,
        title: win.title,
        process_id: win.process_id,
        process_name: win.process_name,
        class_name: win.class_name,
        window_role_hint: win.window_role_hint,
        exe_path: win.exe_path,
        cmdline: win.cmdline,
        parent_pid: win.parent_pid,
        parent_process_name: win.parent_process_name,
        username: win.username,
        memory_mb: win.memory_mb,
        threads_count: win.threads_count,
        dimensions: `${win.rect.width} × ${win.rect.height}`,
        coordinates: `(${win.rect.left}, ${win.rect.top}) - (${win.rect.right}, ${win.rect.bottom})`,
        style_flags: styleFlagsStr,
        is_foreground: win.is_foreground,
        is_minimized: win.is_minimized,
        is_maximized: win.is_maximized,
        is_topmost: win.is_topmost,
        is_tool_window: win.is_tool_window,
        is_layered: win.is_layered,
        is_hung: win.is_hung
      },
      rawTitle: 'Полная телеметрия окна Win32 и процесса (JSON)',
      rawContent: JSON.stringify(win, null, 2),
      autoRun: true,
      actions: [
        {
          label: 'На передний план',
          icon: 'bi-box-arrow-in-up-right',
          class: 'btn-outline-primary',
          onClick: () => executeWindowAction(win.hwnd, 'activate')
        },
        {
          label: 'Свернуть',
          icon: 'bi-dash-square',
          class: 'btn-outline-secondary',
          onClick: () => executeWindowAction(win.hwnd, 'minimize')
        },
        {
          label: 'Восстановить',
          icon: 'bi-arrow-counterclockwise',
          class: 'btn-outline-secondary',
          onClick: () => executeWindowAction(win.hwnd, 'restore')
        },
        {
          label: 'Закрыть окно (WM_CLOSE)',
          icon: 'bi-x-circle',
          class: 'btn-outline-danger',
          closeOnFinish: true,
          onClick: () => executeWindowAction(win.hwnd, 'close')
        }
      ]
    });
  } else {
    showToast(`Окно: ${win.title || win.process_name} (HWND: ${win.hwnd})`, 'info');
  }
}

/**
 * Привязка событий вкладки окон.
 */
export function bindWindowsEvents() {
  document.getElementById('ue-btn-refresh-windows')?.addEventListener('click', loadWindows);
  document.getElementById('ue-input-search-windows')?.addEventListener('input', renderWindowsTable);
  document.getElementById('ue-btn-batch-minimize-all')?.addEventListener('click', () => executeBatchWindowAction('minimize_all'));
  document.getElementById('ue-btn-batch-restore-all')?.addEventListener('click', () => executeBatchWindowAction('restore_all'));
}
