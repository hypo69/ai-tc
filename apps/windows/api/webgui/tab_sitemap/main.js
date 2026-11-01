/**
 * =============================================================================
 * Process Name: Windows Web Interface - Sitemap Controller Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер интерактивной карты сайта (Sitemap) веб-интерфейса
 *   AI Windows Admin (/tc). Динамически сопоставляет реестр вкладок с активной
 *   конфигурацией меню (tc_menu_config.json), рассчитывает статус активности,
 *   обеспечивает живую фильтрацию, поиск и мгновенный переход к разделам.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/tab_sitemap/main.js?v=20261015_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initSitemapTab, deactivateSitemapTab } from '/html/tab_sitemap/main.js';
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_sitemap
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-15 17:00:00
 * =============================================================================
 */

let allTabsData = [];
let activeMenuConfig = null;
let currentSearchTerm = '';
let currentStatusFilter = 'all';
let currentCategoryFilter = 'all';

/**
 * Инициализирует вкладку карты сайта при ее активации.
 */
export async function initSitemapTab() {
  const container = document.getElementById('sitemap-container');
  if (!container) return;

  setupEventListeners();
  await loadSitemapData();
}

/**
 * Деактивирует вкладку при переключении на другой раздел.
 */
export function deactivateSitemapTab() {
  // Очистка таймеров или ресурсов при необходимости
}

// Экспорт в глобальную область видимости для tab-loader
window.initSitemapTab = initSitemapTab;
window.deactivateSitemapTab = deactivateSitemapTab;

/**
 * Устанавливает обработчики событий для элементов поиска и фильтрации.
 */
function setupEventListeners() {
  const searchInput = document.getElementById('sitemap-search-input');
  const clearBtn = document.getElementById('sitemap-search-clear-btn');
  const statusFilter = document.getElementById('sitemap-status-filter');
  const categoryFilter = document.getElementById('sitemap-category-filter');
  const refreshBtn = document.getElementById('sitemap-refresh-btn');

  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    let debounceTimer = null;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentSearchTerm = (e.target.value || '').trim().toLowerCase();
        renderCards();
      }, 120);
    });
  }

  if (clearBtn && !clearBtn.dataset.bound) {
    clearBtn.dataset.bound = 'true';
    clearBtn.addEventListener('click', () => {
      if (searchInput) {
        searchInput.value = '';
        currentSearchTerm = '';
        renderCards();
        searchInput.focus();
      }
    });
  }

  if (statusFilter && !statusFilter.dataset.bound) {
    statusFilter.dataset.bound = 'true';
    statusFilter.addEventListener('change', (e) => {
      currentStatusFilter = e.target.value || 'all';
      renderCards();
    });
  }

  if (categoryFilter && !categoryFilter.dataset.bound) {
    categoryFilter.dataset.bound = 'true';
    categoryFilter.addEventListener('change', (e) => {
      currentCategoryFilter = e.target.value || 'all';
      renderCards();
    });
  }

  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = 'true';
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      const icon = refreshBtn.querySelector('i');
      if (icon) icon.classList.add('spin-animation');
      await loadSitemapData();
      refreshBtn.disabled = false;
      if (icon) icon.classList.remove('spin-animation');
      if (window.toast) {
        window.toast.success('Карта сайта', 'Статусы меню успешно обновлены');
      }
    });
  }
}

/**
 * Загружает метаданные вкладок и актуальную конфигурацию меню.
 */
async function loadSitemapData() {
  const grid = document.getElementById('sitemap-cards-grid');
  const spinner = document.getElementById('sitemap-loading-spinner');
  if (spinner) spinner.classList.remove('d-none');

  try {
    // 1. Загрузка базы описаний вкладок
    const resData = await fetch(`/html/tab_sitemap/sitemap_data.json?v=${Date.now()}`);
    if (!resData.ok) {
      throw new Error(`Ошибка загрузки sitemap_data.json: HTTP ${resData.status}`);
    }
    allTabsData = await resData.json();

    // 2. Загрузка актуального состояния меню из API / файла
    activeMenuConfig = await fetchActiveMenuConfig();

    // 3. Сопоставление активности вкладок
    enrichTabsWithMenuStatus(allTabsData, activeMenuConfig);

    // 4. Обновление сводной статистики
    updateHeaderStats(allTabsData);

    // 5. Рендеринг карточек
    renderCards();
  } catch (err) {
    console.error('[tab_sitemap] Ошибка инициализации карты сайта:', err);
    if (grid) {
      grid.innerHTML = `
        <div class="col-12">
          <div class="alert alert-danger border-danger-subtle p-3">
            <h6 class="fw-bold mb-1"><i class="bi bi-exclamation-triangle-fill"></i> Не удалось загрузить карту сайта</h6>
            <div class="small">${escapeHtml(err.message)}</div>
          </div>
        </div>
      `;
    }
  } finally {
    if (spinner) spinner.classList.add('d-none');
  }
}

/**
 * Запрашивает конфигурацию меню у сервера (с запасным локальным статическим файлом).
 */
async function fetchActiveMenuConfig() {
  try {
    const res = await fetch(`/api/v1/menu/config?target=tc&t=${Date.now()}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (_) {}

  try {
    const resStatic = await fetch(`/html/config_menues/tc_menu_config.json?t=${Date.now()}`);
    if (resStatic.ok) {
      return await resStatic.json();
    }
  } catch (_) {}

  return { menu: { topButtons: [], sidebarItems: [] } };
}

/**
 * Обогащает данные вкладок реальным статусом из меню.
 * @param {Array} tabs 
 * @param {Object} menuCfg 
 */
function enrichTabsWithMenuStatus(tabs, menuCfg) {
  const topButtons = (menuCfg && menuCfg.menu && menuCfg.menu.topButtons) || [];
  const sidebarItems = (menuCfg && menuCfg.menu && menuCfg.menu.sidebarItems) || [];

  const topMap = new Map();
  topButtons.forEach(item => {
    if (item.tab) topMap.set(normalizeTabId(item.tab), item);
    if (item.id) topMap.set(item.id, item);
  });

  const sidebarMap = new Map();
  sidebarItems.forEach(item => {
    if (item.tab) sidebarMap.set(normalizeTabId(item.tab), item);
    if (item.id) sidebarMap.set(item.id, item);
  });

  tabs.forEach(tab => {
    const normId = normalizeTabId(tab.tabId);
    const idKey = tab.id;

    if (topMap.has(normId) || topMap.has(idKey)) {
      const item = topMap.get(normId) || topMap.get(idKey);
      const isVis = item.visible !== false;
      tab.menuPlacement = 'top';
      tab.menuLabel = 'Верхняя панель';
      tab.menuOrder = item.order || 0;
      tab.isActiveInMenu = isVis;
      tab.statusBadge = isVis
        ? { text: `Активна (Верхняя панель #${item.order || 0})`, cls: 'bg-success-subtle text-success border border-success-subtle', icon: 'bi-check-circle-fill' }
        : { text: 'Скрыта в меню', cls: 'bg-secondary-subtle text-body-secondary border border-secondary-subtle', icon: 'bi-eye-slash' };
    } else if (sidebarMap.has(normId) || sidebarMap.has(idKey)) {
      const item = sidebarMap.get(normId) || sidebarMap.get(idKey);
      const isVis = item.visible !== false;
      tab.menuPlacement = 'sidebar';
      tab.menuLabel = 'Боковое меню';
      tab.menuOrder = item.order || 0;
      tab.isActiveInMenu = isVis;
      tab.statusBadge = isVis
        ? { text: `Активна (Боковое меню #${item.order || 0})`, cls: 'bg-info-subtle text-info border border-info-subtle', icon: 'bi-check-circle-fill' }
        : { text: 'Скрыта в меню', cls: 'bg-secondary-subtle text-body-secondary border border-secondary-subtle', icon: 'bi-eye-slash' };
    } else {
      tab.menuPlacement = 'none';
      tab.menuLabel = 'Служебная / Не в меню';
      tab.menuOrder = 999;
      tab.isActiveInMenu = false;
      tab.statusBadge = { text: 'Служебная / Скрыта', cls: 'bg-secondary-subtle text-body-secondary border border-secondary-subtle', icon: 'bi-dash-circle' };
    }
  });
}

/**
 * Нормализует идентификатор вкладки к виду 'tab-...'.
 * @param {string} str 
 * @returns {string}
 */
function normalizeTabId(str) {
  if (!str) return '';
  return str.startsWith('tab-') ? str : `tab-${str}`;
}

/**
 * Обновляет числовые счетчики в шапке страницы.
 * @param {Array} tabs 
 */
function updateHeaderStats(tabs) {
  const total = tabs.length;
  const activeCount = tabs.filter(t => t.isActiveInMenu).length;
  const hiddenCount = total - activeCount;

  const totalBadge = document.getElementById('sitemap-total-badge');
  const statActive = document.getElementById('sitemap-stat-active');
  const statHidden = document.getElementById('sitemap-stat-hidden');

  if (totalBadge) totalBadge.textContent = `Всего вкладок: ${total}`;
  if (statActive) statActive.textContent = String(activeCount);
  if (statHidden) statHidden.textContent = String(hiddenCount);
}

/**
 * Отрисовывает карточки вкладок с учетом активных фильтров и поиска.
 */
function renderCards() {
  const grid = document.getElementById('sitemap-cards-grid');
  const emptyAlert = document.getElementById('sitemap-empty-alert');
  if (!grid) return;

  const filtered = allTabsData.filter(tab => {
    // 1. Фильтр поиска
    if (currentSearchTerm) {
      const matchTitle = (tab.title || '').toLowerCase().includes(currentSearchTerm);
      const matchDesc = (tab.description || '').toLowerCase().includes(currentSearchTerm);
      const matchId = (tab.id || '').toLowerCase().includes(currentSearchTerm) || (tab.tabId || '').toLowerCase().includes(currentSearchTerm);
      const matchCat = (tab.categoryTitle || '').toLowerCase().includes(currentSearchTerm);
      const matchFeatures = Array.isArray(tab.features) && tab.features.some(f => f.toLowerCase().includes(currentSearchTerm));

      if (!matchTitle && !matchDesc && !matchId && !matchCat && !matchFeatures) {
        return false;
      }
    }

    // 2. Фильтр по статусу
    if (currentStatusFilter === 'active' && !tab.isActiveInMenu) return false;
    if (currentStatusFilter === 'top' && (tab.menuPlacement !== 'top' || !tab.isActiveInMenu)) return false;
    if (currentStatusFilter === 'sidebar' && (tab.menuPlacement !== 'sidebar' || !tab.isActiveInMenu)) return false;
    if (currentStatusFilter === 'hidden' && tab.isActiveInMenu) return false;

    // 3. Фильтр по категории
    if (currentCategoryFilter !== 'all' && tab.category !== currentCategoryFilter) return false;

    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (emptyAlert) emptyAlert.classList.remove('d-none');
    return;
  }

  if (emptyAlert) emptyAlert.classList.add('d-none');

  grid.innerHTML = filtered.map(tab => createTabCardHtml(tab)).join('');

  // Привязка кликов к кнопкам перехода
  grid.querySelectorAll('.btn-open-tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetTabId = btn.dataset.tabId;
      if (targetTabId && typeof window.switchTab === 'function') {
        window.switchTab(targetTabId);
      }
    });
  });
}

/**
 * Генерирует HTML разметку для карточки вкладки.
 * @param {Object} tab 
 * @returns {string}
 */
function createTabCardHtml(tab) {
  const badge = tab.statusBadge || { text: 'Скрыта', cls: 'bg-secondary text-white', icon: 'bi-eye-slash' };
  const iconHtml = tab.icon.startsWith('bi-')
    ? `<i class="bi ${escapeHtml(tab.icon)} fs-5 text-primary"></i>`
    : `<span class="fs-5">${escapeHtml(tab.icon)}</span>`;

  const featuresList = (Array.isArray(tab.features) && tab.features.length > 0)
    ? tab.features.map(f => `<li class="mb-1"><i class="bi bi-check2 text-primary me-1.5"></i>${escapeHtml(f)}</li>`).join('')
    : '<li class="text-body-secondary fst-italic">Специфические параметры настраиваются на вкладке</li>';

  const folderName = `apps/windows/api/webgui/tab_${escapeHtml(tab.id)}`;

  return `
    <div class="col-12 col-md-6 col-xl-4 d-flex">
      <div class="card bg-body-tertiary border-secondary-subtle shadow-sm w-100 d-flex flex-column transition-hover">
        <div class="card-header bg-body border-secondary-subtle p-3 d-flex align-items-start justify-content-between gap-2">
          <div class="d-flex align-items-center gap-2">
            ${iconHtml}
            <div>
              <h6 class="mb-0 fw-bold text-body" style="font-size: 0.92rem;">${escapeHtml(tab.title)}</h6>
              <span class="badge rounded-pill bg-body-secondary text-body-secondary border border-secondary-subtle mt-1" style="font-size: 0.7rem;">
                ${escapeHtml(tab.categoryTitle || 'Общие')}
              </span>
            </div>
          </div>
          <span class="badge rounded-pill px-2 py-1 small d-flex align-items-center gap-1 flex-shrink-0 ${badge.cls}" style="font-size: 0.72rem;">
            <i class="bi ${badge.icon}"></i>
            <span>${escapeHtml(badge.text)}</span>
          </span>
        </div>

        <div class="card-body p-3 d-flex flex-column flex-grow-1">
          <!-- Технические идентификаторы -->
          <div class="d-flex align-items-center justify-content-between small text-body-secondary mb-2 font-monospace" style="font-size: 0.75rem;">
            <span>ID: <code class="text-primary">${escapeHtml(tab.tabId)}</code></span>
            <span class="text-truncate ms-2" title="${folderName}"><i class="bi bi-folder2 text-secondary me-1"></i>tab_${escapeHtml(tab.id)}</span>
          </div>

          <!-- Описание вкладки -->
          <p class="text-body small mb-3 flex-grow-0" style="line-height: 1.45; font-size: 0.82rem;">
            ${escapeHtml(tab.description)}
          </p>

          <!-- Перечень того, что можно найти / настроить -->
          <div class="mt-auto pt-2 border-top border-secondary-subtle">
            <div class="small fw-semibold text-body-secondary mb-1.5 text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">
              Что можно найти и настроить:
            </div>
            <ul class="list-unstyled small text-body-secondary mb-3 ps-0" style="font-size: 0.78rem; line-height: 1.4;">
              ${featuresList}
            </ul>
          </div>

          <!-- Кнопка перехода на вкладку 
          <div class="d-flex justify-content-end pt-2 border-top border-secondary-subtle">
            <button class="btn btn-sm btn-outline-primary d-flex align-items-center gap-1.5 px-3 py-1.5 w-100 justify-content-center btn-open-tab"
                    type="button"
                    data-tab-id="${escapeHtml(tab.tabId)}"
                    title="Открыть раздел ${escapeHtml(tab.title)}">
              <span>Открыть вкладку</span>
              <i class="bi bi-arrow-right-short fs-6"></i>
            </button>
                    -->
                    
          <!-- Кнопка перехода на вкладку -->
          <div class="d-flex justify-content-end pt-2 border-top border-secondary-subtle">
            <button class="btn btn-sm btn-outline-primary d-flex align-items-center gap-1.5 px-3 py-1.5 w-100 justify-content-center btn-open-tab"
                    type="button"
                    data-tab-id="${escapeHtml(tab.tabId)}"
                    title="Открыть раздел ${escapeHtml(tab.title)}">
              <span>Открыть вкладку</span>
              <i class="bi bi-arrow-right-short fs-6"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Экранирует HTML спецсимволы для безопасного рендеринга.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
