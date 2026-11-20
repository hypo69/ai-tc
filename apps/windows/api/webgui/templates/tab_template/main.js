/**
 * =============================================================================
 * Process Name: Windows Web Interface - Reference Tab Controller
 * =============================================================================
 * Description:
 *   Эталонный JavaScript-контроллер жизненного цикла вкладки WebGUI.
 *   Демонстрирует:
 *   - Инициализацию window.initTemplateTab() и очистку window.deactivateTemplateTab()
 *   - Регистрацию безопасного опросника через window.registerTabPoller (Active-Only)
 *   - Бесшовную интеграцию с универсальным ИИ-модальным окном (window.AIModalDialog.show)
 *   - Клиентскую фильтрацию, поиск, обработку состояний загрузки и ошибок API
 *
 * Usage Examples:
 *   Ленивая загрузка вкладки (через tab-core.js):
 *     await loadTab('template', '/html/tab_template/index.html?v=20261015_v1', '/html/tab_template/main.js?v=20261015_v1');
 *
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/templates/tab_template
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

// Локальное состояние вкладки
let templateItems = [];
let isInitialized = false;
const TAB_ID = 'tab-template';
const API_ENDPOINT = '/api/v1/template-data'; // Замените на реальный эндпоинт подсистемы

/**
 * Инициализация вкладки (вызывается оркестратором при первой загрузке или активации).
 */
export async function initTemplateTab() {
  console.log('[TemplateTab] Инициализация вкладки...');

  if (!isInitialized) {
    bindEventListeners();
    isInitialized = true;
  }

  // 1. Первичная загрузка данных
  await loadTabTelemetry();

  // 2. Регистрация опросника через tab-core (тикает ТОЛЬКО пока вкладка на экране)
  if (typeof window.registerTabPoller === 'function') {
    window.registerTabPoller(TAB_ID, async () => {
      await loadTabTelemetry(true);
    }, 5000, { immediate: false });
  }
}

// Экспорт для глобального доступа оболочки
window.initTemplateTab = initTemplateTab;

/**
 * Хук деактивации вкладки (вызывается при переключении на другой раздел).
 */
export function deactivateTemplateTab() {
  console.log('[TemplateTab] Вкладка деактивирована, фоновые ресурсы освобождены.');
}
window.deactivateTemplateTab = deactivateTemplateTab;

/**
 * Подключение слушателей событий DOM.
 */
function bindEventListeners() {
  // Кнопка ручного обновления
  const btnRefresh = document.getElementById('template-btn-refresh');
  if (btnRefresh) {
    btnRefresh.onclick = async () => {
      const spinner = document.getElementById('template-refresh-spinner');
      spinner?.classList.add('spin-animation');
      await loadTabTelemetry();
      spinner?.classList.remove('spin-animation');
    };
  }

  // Тумблер Live-опроса
  const liveToggle = document.getElementById('template-live-toggle');
  if (liveToggle) {
    liveToggle.onchange = () => {
      if (typeof window.setTabPollerEnabled === 'function') {
        window.setTabPollerEnabled(`${TAB_ID}_default`, liveToggle.checked);
      }
    };
  }

  // Поле поиска с мгновенной фильтрацией
  const searchInput = document.getElementById('template-search-input');
  if (searchInput) {
    searchInput.oninput = () => renderTable();
  }

  // Очистка поиска
  const btnClearSearch = document.getElementById('template-search-clear');
  if (btnClearSearch && searchInput) {
    btnClearSearch.onclick = () => {
      searchInput.value = '';
      renderTable();
      searchInput.focus();
    };
  }

  // Фильтр по категории
  const filterCategory = document.getElementById('template-filter-category');
  if (filterCategory) {
    filterCategory.onchange = () => renderTable();
  }
}

/**
 * Загрузка актуальных данных из REST API или системного бэкенда.
 * @param {boolean} isBackground - Флаг фонового обновления без мигания индикатором загрузки
 */
async function loadTabTelemetry(isBackground = false) {
  const loadingIndicator = document.getElementById('template-loading-indicator');
  const tableContainer = document.getElementById('template-table-container');

  if (!isBackground && loadingIndicator && tableContainer) {
    loadingIndicator.classList.remove('d-none');
    tableContainer.classList.add('opacity-50');
  }

  try {
    const response = await fetch(API_ENDPOINT);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    templateItems = Array.isArray(data.items) ? data.items : [];
    updateMetricsSummary();
    renderTable();
  } catch (err) {
    console.warn('[TemplateTab] Ошибка получения данных, использование демо-данных:', err);
    // Демо-данные для наглядности при отсутствии связи с API
    templateItems = getMockTemplateData();
    updateMetricsSummary();
    renderTable();
  } finally {
    if (!isBackground && loadingIndicator && tableContainer) {
      loadingIndicator.classList.add('d-none');
      tableContainer.classList.remove('opacity-50');
    }
  }
}

/**
 * Обновление счетчиков в шапке и карточке фильтров.
 */
function updateMetricsSummary() {
  const counterBadge = document.getElementById('template-counter-badge');
  const metricActive = document.getElementById('template-metric-active');
  const metricStopped = document.getElementById('template-metric-stopped');
  const metricWarnings = document.getElementById('template-metric-warnings');

  if (counterBadge) counterBadge.textContent = `${templateItems.length} записей`;
  if (metricActive) metricActive.textContent = templateItems.filter(i => i.status === 'Active').length;
  if (metricStopped) metricStopped.textContent = templateItems.filter(i => i.status === 'Stopped').length;
  if (metricWarnings) metricWarnings.textContent = templateItems.filter(i => i.status === 'Warning').length;
}

/**
 * Отрисовка строк таблицы с учетом поискового запроса и фильтров.
 */
function renderTable() {
  const tbody = document.getElementById('template-table-body');
  const emptyState = document.getElementById('template-empty-state');
  const searchInput = document.getElementById('template-search-input');
  const filterCat = document.getElementById('template-filter-category');
  const footerSummary = document.getElementById('template-footer-summary');

  if (!tbody) return;

  const query = (searchInput?.value || '').trim().toLowerCase();
  const category = filterCat?.value || 'all';

  const filtered = templateItems.filter(item => {
    const matchesQuery = !query ||
      item.name.toLowerCase().includes(query) ||
      (item.description && item.description.toLowerCase().includes(query));
    const matchesCat = category === 'all' || item.category === category;
    return matchesQuery && matchesCat;
  });

  if (footerSummary) {
    footerSummary.textContent = `Показано: ${filtered.length} из ${templateItems.length}`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    emptyState?.classList.remove('d-none');
    return;
  }

  emptyState?.classList.add('d-none');

  tbody.innerHTML = filtered.map(item => `
    <tr class="interactive-table-row" data-id="${escapeHtml(item.id)}" style="cursor: pointer;">
      <td>
        <div class="fw-semibold text-body d-flex align-items-center gap-2">
          <span>${item.icon || '📄'}</span>
          <span>${escapeHtml(item.name)}</span>
        </div>
        <div class="text-muted font-monospace small">${escapeHtml(item.path || item.identifier || '')}</div>
      </td>
      <td>
        <span class="badge bg-body-secondary text-body">${escapeHtml(item.category || 'Общая')}</span>
      </td>
      <td>
        ${getStatusBadge(item.status)}
      </td>
      <td class="font-monospace">
        ${escapeHtml(item.metric_value || '—')}
      </td>
      <td class="text-end no-modal-trigger">
        <button type="button" class="btn btn-sm btn-outline-primary me-1" title="Инспекция ИИ" data-action="inspect" data-id="${escapeHtml(item.id)}">
          <i class="bi bi-robot"></i>
        </button>
        <button type="button" class="btn btn-sm btn-outline-secondary" title="Параметры" data-action="settings" data-id="${escapeHtml(item.id)}">
          <i class="bi bi-gear"></i>
        </button>
      </td>
    </tr>
  `).join('');

  // Привязка обработчиков клика по интерактивным строкам
  tbody.querySelectorAll('.interactive-table-row').forEach(row => {
    row.addEventListener('click', (event) => {
      // Игнорируем клики по кнопкам действий
      if (event.target.closest('button, a, input, select, .no-modal-trigger')) {
        return;
      }
      const itemId = row.getAttribute('data-id');
      const item = templateItems.find(x => String(x.id) === String(itemId));
      if (item) {
        openItemAiModal(item);
      }
    });
  });

  // Обработчики кнопок действий внутри строк
  tbody.querySelectorAll('button[data-action="inspect"]').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const itemId = btn.getAttribute('data-id');
      const item = templateItems.find(x => String(x.id) === String(itemId));
      if (item) openItemAiModal(item);
    };
  });
}

/**
 * Вызов универсального ИИ-модального окна (AIModalDialog / AITableModal).
 * @param {Object} item Данные выбранной строки
 */
function openItemAiModal(item) {
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) {
    console.warn('[TemplateTab] Модуль AIModalDialog не найден в window. Подключите /html/ai_modal_dialog/main.js');
    if (window.toast) window.toast.warning('Модальное окно', 'Компонент ИИ-ассистента недоступен.');
    return;
  }

  modal.show({
    title: item.name,
    subtitle: `Идентификатор: ${item.id} | Категория: ${item.category}`,
    icon: item.icon || '⚙️',
    tableType: 'generic', // 'process' | 'service' | 'software' | 'task' | 'network' | 'registry' | 'user' | 'disk' | 'generic'
    badges: [
      { text: item.status, class: item.status === 'Active' ? 'badge bg-success' : 'badge bg-secondary' },
      { text: item.category, class: 'badge bg-body-secondary text-body' }
    ],
    metadata: [
      { label: 'Системный путь', value: item.path || 'N/A', isCode: true, fullWidth: true },
      { label: 'Статус выполнения', value: item.status },
      { label: 'Основная метрика', value: item.metric_value || 'Норма' },
      { label: 'Время фиксации', value: new Date().toLocaleTimeString() }
    ],
    rawTitle: 'Телеметрия сущности (JSON dump)',
    rawContent: JSON.stringify(item, null, 2),
    autoRun: false, // Быстрый опрос WikiLLM кэша без расхода токенов LLM
    actions: [
      {
        label: 'Перезапустить',
        icon: 'bi-arrow-repeat',
        class: 'btn-outline-warning',
        onClick: (opts) => {
          if (window.toast) window.toast.info('Действие', `Команда перезапуска отправлена для ${opts.title}`);
        }
      }
    ]
  });
}

/**
 * Получение бейджа статуса с адаптивными Bootstrap классами.
 * @param {string} status 
 * @returns {string} HTML-разметка бейджа
 */
function getStatusBadge(status) {
  switch (status) {
    case 'Active':
      return '<span class="badge bg-success-subtle text-success border border-success-subtle">Активен</span>';
    case 'Stopped':
      return '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">Остановлен</span>';
    case 'Warning':
      return '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Предупреждение</span>';
    default:
      return `<span class="badge bg-light text-dark">${escapeHtml(status || 'Неизвестно')}</span>`;
  }
}

/**
 * Экранирование спецсимволов HTML для безопасного вывода.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Генерация тестовых демо-данных.
 * @returns {Array<Object>}
 */
function getMockTemplateData() {
  return [
    { id: 'item_01', name: 'Системный планировщик задач', path: 'C:\\Windows\\System32\\taskschd.msc', category: 'system', status: 'Active', metric_value: '0.2% CPU', icon: '⏱️' },
    { id: 'item_02', name: 'Служба журнала событий', path: 'EventLog (services.msc)', category: 'system', status: 'Active', metric_value: '18 MB RAM', icon: '📋' },
    { id: 'item_03', name: 'Пользовательский автостарт фонового агента', path: 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run', category: 'user', status: 'Stopped', metric_value: '0 MB', icon: '🚀' },
    { id: 'item_04', name: 'Мониторинг сетевых соединений', path: 'TCP/IP Stack (NetIO)', category: 'system', status: 'Warning', metric_value: '4 открытых сокета', icon: '🌐' }
  ];
}

