/**
 * =============================================================================
 * Process Name: ai-tc UI - WikiLLM Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер интерактивного фильтра категорий, тегов и поиска статей WikiLLM.
 *   Обеспечивает синхронизацию с REST API (/api/v1/wikillm/articles), двухъязычную локализацию (RU/EN)
 *   и управление состоянием Category Filter Pills и Tag Cloud (Задача №33).
 *
 * File: wikillm_controller.js
 * Project: ai-tc
 * Package: windows/api/webgui/static/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

'use strict';

/**
 * Словарь локализации RU/EN для интерфейса WikiLLM.
 */
const WIKILLM_I18N = {
  ru: {
    title: 'База знаний процессов и оптимизации WikiLLM',
    subtitle: 'Интерактивный фильтр категорий процессов, популярных тегов и рекомендаций',
    searchPlaceholder: 'Поиск по процессу, заголовку или паттерну...',
    categoryTitle: 'Категории процессов:',
    categories: {
      all: 'Все',
      browser: '🌐 Браузеры',
      system_service: '⚙️ Системные службы',
      dev_tool: '🛠️ Инструменты разработчика',
      background_agent: '🤖 Фоновые агенты',
      user_app: '👤 Пользовательское ПО',
    },
    tooltips: {
      all: 'Показать статьи всех категорий',
      browser: 'Веб-браузеры и расширения (msedge.exe, chrome.exe)',
      system_service: 'Системные службы Windows и драйверы (svchost.exe, spoolsv.exe)',
      dev_tool: 'Инструменты разработки и компиляторы (code.exe, git.exe)',
      background_agent: 'Фоновые агенты и локальные ИИ (ollama.exe, searchindexer.exe)',
      user_app: 'Пользовательское программное обеспечение (telegram.exe)',
      tag_memory_leak: 'Фильтрация по утечкам оперативной памяти (RAM leak)',
      tag_gpu_acceleration: 'Фильтрация по видеопамяти и аппаратным проблемам GPU',
      tag_high_cpu: 'Фильтрация по высокой утилизации процессора (High CPU)',
      tag_untrusted_path: 'Фильтрация по исполнению из временных и недоверенных папок',
    },
    tagsTitle: 'Облако популярных тегов:',
    tags: {
      memory_leak: 'Утечка памяти',
      gpu_acceleration: 'GPU-ускорение',
      high_cpu: 'Высокий CPU',
      untrusted_path: 'Недоверенный путь',
    },
    clearTag: 'Сбросить тег',
    totalFound: 'Найдено статей:',
    noResults: 'Статей по выбранным критериям не найдено.',
    resetFilters: 'Сбросить все фильтры',
    loading: 'Загрузка базы знаний WikiLLM...',
    error: 'Не удалось получить статьи с сервера',
    retry: 'Повторить попытку',
    actionPattern: 'Рекомендация / Паттерн решения:',
  },
  en: {
    title: 'WikiLLM Process & Optimization Knowledge Base',
    subtitle: 'Interactive filter for process categories, popular tags, and tuning recommendations',
    searchPlaceholder: 'Search by process name, title, or pattern...',
    categoryTitle: 'Process Categories:',
    categories: {
      all: 'All',
      browser: '🌐 Browsers',
      system_service: '⚙️ System Services',
      dev_tool: '🛠️ Developer Tools',
      background_agent: '🤖 Background Agents',
      user_app: '👤 User Software',
    },
    tooltips: {
      all: 'Display articles across all categories',
      browser: 'Web browsers and browser extensions (msedge.exe, chrome.exe)',
      system_service: 'Windows system services and drivers (svchost.exe, spoolsv.exe)',
      dev_tool: 'Developer tools, IDEs, and compilers (code.exe, git.exe)',
      background_agent: 'Background daemon agents and local AI runners (ollama.exe, searchindexer.exe)',
      user_app: 'Desktop applications and user software (telegram.exe)',
      tag_memory_leak: 'Filter by process memory leaks (RAM leak)',
      tag_gpu_acceleration: 'Filter by GPU acceleration and VRAM issues',
      tag_high_cpu: 'Filter by excessive CPU utilization (High CPU)',
      tag_untrusted_path: 'Filter by execution from untrusted or temporary paths',
    },
    tagsTitle: 'Popular Tag Cloud:',
    tags: {
      memory_leak: 'Memory Leak',
      gpu_acceleration: 'GPU Acceleration',
      high_cpu: 'High CPU',
      untrusted_path: 'Untrusted Path',
    },
    clearTag: 'Clear Tag',
    totalFound: 'Articles found:',
    noResults: 'No articles match the current filter criteria.',
    resetFilters: 'Reset all filters',
    loading: 'Loading WikiLLM Knowledge Base...',
    error: 'Failed to retrieve articles from server',
    retry: 'Retry',
    actionPattern: 'Recommendation / Action Pattern:',
  },
};

/**
 * Основной класс контроллера интерактивного фильтра WikiLLM.
 */
class WikiLLMController {
  constructor(options = {}) {
    this.apiBase = options.apiBase || '/api/v1/wikillm';
    this.containerId = options.containerId || 'wikillm-container';

    // Состояние фильтрации
    this.selectedCategory = 'all';
    this.selectedTag = null;
    this.searchQuery = '';
    this.currentLang = this.detectLanguage();
    this.articles = [];
    this.isLoading = false;
    this.searchDebounceTimer = null;

    // Ссылки на элементы DOM
    this.dom = {};
  }

  /**
   * Определяет активный язык интерфейса (RU по умолчанию).
   * @returns {string} Код языка ('ru' или 'en').
   */
  detectLanguage() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const urlLang = urlParams.get('lang');
      if (urlLang && (urlLang === 'en' || urlLang === 'ru')) return urlLang;

      const stored = localStorage.getItem('app_language');
      if (stored && (stored === 'en' || stored === 'ru')) return stored;

      if (window.I18nManager && window.I18nManager.lang) {
        return window.I18nManager.lang === 'en' ? 'en' : 'ru';
      }
    } catch (_) {}
    return 'ru';
  }

  /**
   * Инициализирует контроллер: находит элементы DOM, привязывает события и загружает статьи.
   */
  init() {
    this.cacheDomElements();
    this.bindEvents();
    this.applyLocalization();
    this.loadArticles();
  }

  /**
   * Кэширует ссылки на ключевые элементы разметки.
   */
  cacheDomElements() {
    this.dom.container = document.getElementById(this.containerId);
    this.dom.categoryPills = document.querySelectorAll('.wikillm-category-pill');
    this.dom.tagCloud = document.getElementById('wikillm-tag-cloud');
    this.dom.tagPills = document.querySelectorAll('.wikillm-tag-pill');
    this.dom.searchInput = document.getElementById('wikillm-search-input');
    this.dom.searchClearBtn = document.getElementById('wikillm-search-clear');
    this.dom.articlesList = document.getElementById('wikillm-articles-list');
    this.dom.loadingSpinner = document.getElementById('wikillm-loading');
    this.dom.errorAlert = document.getElementById('wikillm-error');
    this.dom.emptyState = document.getElementById('wikillm-empty');
    this.dom.articlesCounter = document.getElementById('wikillm-total-counter');
    this.dom.activeTagBadge = document.getElementById('wikillm-active-tag-badge');
    this.dom.langToggleBtn = document.getElementById('wikillm-lang-toggle');
    this.dom.resetFiltersBtn = document.getElementById('wikillm-reset-btn');
  }

  /**
   * Регистрирует обработчики событий пользовательского ввода.
   */
  bindEvents() {
    // 1. Клик по переключателям категорий (Category Filter Pills)
    if (this.dom.categoryPills) {
      this.dom.categoryPills.forEach((pill) => {
        pill.addEventListener('click', (e) => {
          e.preventDefault();
          const category = pill.getAttribute('data-category');
          this.setCategory(category);
        });
      });
    }

    // 2. Клик по облаку тегов (Tag Cloud)
    if (this.dom.tagPills) {
      this.dom.tagPills.forEach((pill) => {
        pill.addEventListener('click', (e) => {
          e.preventDefault();
          const tag = pill.getAttribute('data-tag');
          this.toggleTag(tag);
        });
      });
    }

    // 3. Поисковый ввод с дебаунсом (Search Input)
    if (this.dom.searchInput) {
      this.dom.searchInput.addEventListener('input', (e) => {
        clearTimeout(this.searchDebounceTimer);
        this.searchDebounceTimer = setTimeout(() => {
          this.searchQuery = e.target.value.trim();
          this.toggleSearchClearBtn();
          this.loadArticles();
        }, 300);
      });
    }

    // 4. Очистка поиска
    if (this.dom.searchClearBtn) {
      this.dom.searchClearBtn.addEventListener('click', () => {
        if (this.dom.searchInput) {
          this.dom.searchInput.value = '';
        }
        this.searchQuery = '';
        this.toggleSearchClearBtn();
        this.loadArticles();
      });
    }

    // 5. Сброс активного тега
    if (this.dom.activeTagBadge) {
      this.dom.activeTagBadge.addEventListener('click', () => {
        this.selectedTag = null;
        this.updateTagPillsState();
        this.loadArticles();
      });
    }

    // 6. Кнопка полного сброса фильтров
    if (this.dom.resetFiltersBtn) {
      this.dom.resetFiltersBtn.addEventListener('click', () => {
        this.resetAllFilters();
      });
    }

    // 7. Переключатель языка интерфейса
    if (this.dom.langToggleBtn) {
      this.dom.langToggleBtn.addEventListener('click', () => {
        this.setLanguage(this.currentLang === 'ru' ? 'en' : 'ru');
      });
    }
  }

  /**
   * Устанавливает выбранную категорию и перезагружает статьи.
   * @param {string} category Идентификатор категории ('all', 'browser', etc.).
   */
  setCategory(category) {
    if (this.selectedCategory === category) return;
    this.selectedCategory = category || 'all';

    // Обновляем визуальное состояние кнопок категорий
    if (this.dom.categoryPills) {
      this.dom.categoryPills.forEach((pill) => {
        const cat = pill.getAttribute('data-category');
        if (cat === this.selectedCategory) {
          pill.classList.add('active');
          pill.classList.remove('btn-outline-primary');
          pill.classList.add('btn-primary');
        } else {
          pill.classList.remove('active');
          pill.classList.remove('btn-primary');
          pill.classList.add('btn-outline-primary');
        }
      });
    }

    this.loadArticles();
  }

  /**
   * Переключает выбор тега (клик по активному тегу снимает фильтр).
   * @param {string} tag Имя тега.
   */
  toggleTag(tag) {
    if (this.selectedTag === tag) {
      this.selectedTag = null;
    } else {
      this.selectedTag = tag;
    }
    this.updateTagPillsState();
    this.loadArticles();
  }

  /**
   * Обновляет состояние и подсветку пиллов тегов.
   */
  updateTagPillsState() {
    if (this.dom.tagPills) {
      this.dom.tagPills.forEach((pill) => {
        const tag = pill.getAttribute('data-tag');
        if (tag === this.selectedTag) {
          pill.classList.add('active', 'bg-warning', 'text-dark', 'fw-bold');
          pill.classList.remove('bg-dark-subtle', 'text-secondary');
        } else {
          pill.classList.remove('active', 'bg-warning', 'text-dark', 'fw-bold');
          pill.classList.add('bg-dark-subtle', 'text-secondary');
        }
      });
    }

    if (this.dom.activeTagBadge) {
      if (this.selectedTag) {
        this.dom.activeTagBadge.style.display = 'inline-flex';
        const tagText = this.getTagLabel(this.selectedTag);
        this.dom.activeTagBadge.innerHTML = `<i class="bi bi-tag-fill me-1"></i>${tagText} <i class="bi bi-x ms-1"></i>`;
      } else {
        this.dom.activeTagBadge.style.display = 'none';
      }
    }
  }

  /**
   * Сбрасывает все активные фильтры в исходное состояние.
   */
  resetAllFilters() {
    this.selectedCategory = 'all';
    this.selectedTag = null;
    this.searchQuery = '';
    if (this.dom.searchInput) {
      this.dom.searchInput.value = '';
    }
    this.toggleSearchClearBtn();

    if (this.dom.categoryPills) {
      this.dom.categoryPills.forEach((pill) => {
        if (pill.getAttribute('data-category') === 'all') {
          pill.classList.add('active', 'btn-primary');
          pill.classList.remove('btn-outline-primary');
        } else {
          pill.classList.remove('active', 'btn-primary');
          pill.classList.add('btn-outline-primary');
        }
      });
    }

    this.updateTagPillsState();
    this.loadArticles();
  }

  /**
   * Показывает или скрывает кнопку очистки поиска.
   */
  toggleSearchClearBtn() {
    if (this.dom.searchClearBtn) {
      this.dom.searchClearBtn.style.display = this.searchQuery ? 'block' : 'none';
    }
  }

  /**
   * Загружает статьи с REST API с текущими фильтрами:
   * GET /api/v1/wikillm/articles?category=browser&tag=memory_leak&search_query=...
   */
  async loadArticles() {
    this.isLoading = true;
    this.showLoading(true);
    this.showError(false);

    try {
      const params = new URLSearchParams();
      if (this.selectedCategory && this.selectedCategory !== 'all') {
        params.append('category', this.selectedCategory);
      }
      if (this.selectedTag) {
        params.append('tag', this.selectedTag);
      }
      if (this.searchQuery) {
        params.append('search_query', this.searchQuery);
      }

      const queryString = params.toString();
      const url = `${this.apiBase}/articles${queryString ? '?' + queryString : ''}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.articles = Array.isArray(data.articles) ? data.articles : [];
      this.renderArticles(this.articles);
    } catch (err) {
      console.error('[WikiLLM Controller] Ошибка загрузки статей:', err);
      this.showError(true, err.message);
    } finally {
      this.isLoading = false;
      this.showLoading(false);
    }
  }

  /**
   * Отрисовывает список карточек статей в контейнере.
   * @param {Array} articles Список статей.
   */
  renderArticles(articles) {
    if (!this.dom.articlesList) return;

    // Обновляем счётчик
    if (this.dom.articlesCounter) {
      const i18n = WIKILLM_I18N[this.currentLang];
      this.dom.articlesCounter.textContent = `${i18n.totalFound} ${articles.length}`;
    }

    if (!articles || articles.length === 0) {
      this.dom.articlesList.innerHTML = '';
      if (this.dom.emptyState) {
        this.dom.emptyState.style.display = 'block';
      }
      return;
    }

    if (this.dom.emptyState) {
      this.dom.emptyState.style.display = 'none';
    }

    const html = articles
      .map((article) => {
        const catBadgeClass = this.getCategoryBadgeClass(article.category);
        const catLabel = this.getCategoryLabel(article.category);
        const tagsHtml = (article.tags || [])
          .map((t) => {
            const isSelected = t === this.selectedTag;
            const badgeClass = isSelected ? 'bg-warning text-dark fw-bold' : 'bg-secondary-subtle text-secondary';
            return `<button type="button" class="btn btn-sm py-0 px-2 rounded-pill me-1 mb-1 border-0 ${badgeClass} wikillm-card-tag-btn" data-tag="${this.escapeHtml(t)}" title="Фильтровать по тегу: ${this.escapeHtml(t)}">#${this.escapeHtml(t)}</button>`;
          })
          .join('');

        const i18n = WIKILLM_I18N[this.currentLang];

        return `
          <div class="col-12 col-md-6 col-xl-4">
            <div class="card h-100 shadow-sm border-secondary-subtle bg-dark-subtle text-light wikillm-article-card">
              <div class="card-header d-flex justify-content-between align-items-center py-2 bg-transparent border-secondary-subtle">
                <span class="badge font-monospace text-uppercase bg-info-subtle text-info border border-info-subtle">
                  <i class="bi bi-cpu me-1"></i>${this.escapeHtml(article.process_name || 'process')}
                </span>
                <span class="badge ${catBadgeClass}">
                  ${catLabel}
                </span>
              </div>
              <div class="card-body py-2">
                <h6 class="card-title fw-bold text-white mb-2">${this.escapeHtml(article.title || '')}</h6>
                <div class="p-2 rounded bg-black bg-opacity-40 border border-secondary border-opacity-25 mb-2 font-monospace small text-light">
                  <div class="text-secondary small mb-1"><i class="bi bi-lightbulb me-1 text-warning"></i>${i18n.actionPattern}</div>
                  ${this.escapeHtml(article.content_pattern || '')}
                </div>
              </div>
              <div class="card-footer bg-transparent border-secondary-subtle py-2 d-flex flex-wrap align-items-center">
                ${tagsHtml}
              </div>
            </div>
          </div>
        `;
      })
      .join('');

    this.dom.articlesList.innerHTML = `<div class="row g-3">${html}</div>`;

    // Привязываем клик по тегам внутри карточек
    this.dom.articlesList.querySelectorAll('.wikillm-card-tag-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const tag = btn.getAttribute('data-tag');
        this.toggleTag(tag);
      });
    });
  }

  /**
   * Возвращает класс Bootstrap для бейджа категории.
   * @param {string} category
   * @returns {string}
   */
  getCategoryBadgeClass(category) {
    const map = {
      browser: 'bg-primary-subtle text-primary border border-primary-subtle',
      system_service: 'bg-success-subtle text-success border border-success-subtle',
      dev_tool: 'bg-warning-subtle text-warning border border-warning-subtle',
      background_agent: 'bg-info-subtle text-info border border-info-subtle',
      user_app: 'bg-purple-subtle text-light border border-secondary',
    };
    return map[category] || 'bg-secondary-subtle text-secondary';
  }

  /**
   * Возвращает переведённый лейбл для категории.
   * @param {string} category
   * @returns {string}
   */
  getCategoryLabel(category) {
    const i18n = WIKILLM_I18N[this.currentLang];
    return (i18n.categories && i18n.categories[category]) || category;
  }

  /**
   * Возвращает переведённый лейбл для тега.
   * @param {string} tag
   * @returns {string}
   */
  getTagLabel(tag) {
    const i18n = WIKILLM_I18N[this.currentLang];
    return (i18n.tags && i18n.tags[tag]) || tag;
  }

  /**
   * Переключает язык интерфейса (RU/EN) и обновляет DOM.
   * @param {string} lang
   */
  setLanguage(lang) {
    this.currentLang = lang === 'en' ? 'en' : 'ru';
    try {
      localStorage.setItem('app_language', this.currentLang);
    } catch (_) {}
    this.applyLocalization();
    this.renderArticles(this.articles);
  }

  /**
   * Применяет текущую локализацию ко всем элементам разметки.
   */
  applyLocalization() {
    const i18n = WIKILLM_I18N[this.currentLang];
    if (!i18n) return;

    // 1. Заголовки
    const titleEl = document.getElementById('wikillm-title-text');
    if (titleEl) titleEl.textContent = i18n.title;

    const subEl = document.getElementById('wikillm-subtitle-text');
    if (subEl) subEl.textContent = i18n.subtitle;

    const catTitleEl = document.getElementById('wikillm-category-title-text');
    if (catTitleEl) catTitleEl.textContent = i18n.categoryTitle;

    const tagsTitleEl = document.getElementById('wikillm-tags-title-text');
    if (tagsTitleEl) tagsTitleEl.textContent = i18n.tagsTitle;

    // 2. Поисковый плейсхолдер
    if (this.dom.searchInput) {
      this.dom.searchInput.placeholder = i18n.searchPlaceholder;
    }

    // 3. Категории
    if (this.dom.categoryPills) {
      this.dom.categoryPills.forEach((pill) => {
        const cat = pill.getAttribute('data-category');
        if (i18n.categories[cat]) {
          const textSpan = pill.querySelector('.pill-text');
          if (textSpan) {
            textSpan.textContent = i18n.categories[cat];
          } else {
            pill.textContent = i18n.categories[cat];
          }
        }
        if (i18n.tooltips[cat]) {
          pill.setAttribute('title', i18n.tooltips[cat]);
        }
      });
    }

    // 4. Теги
    if (this.dom.tagPills) {
      this.dom.tagPills.forEach((pill) => {
        const tag = pill.getAttribute('data-tag');
        const tooltipKey = `tag_${tag}`;
        if (i18n.tooltips[tooltipKey]) {
          pill.setAttribute('title', i18n.tooltips[tooltipKey]);
        }
      });
    }

    // 5. Кнопка смены языка
    if (this.dom.langToggleBtn) {
      this.dom.langToggleBtn.textContent = this.currentLang === 'ru' ? 'EN' : 'RU';
      this.dom.langToggleBtn.title = this.currentLang === 'ru' ? 'Switch to English' : 'Переключить на русский';
    }

    // 6. Сброс фильтров
    if (this.dom.resetFiltersBtn) {
      this.dom.resetFiltersBtn.textContent = i18n.resetFilters;
    }

    // 7. Счётчик статей
    if (this.dom.articlesCounter && this.articles) {
      this.dom.articlesCounter.textContent = `${i18n.totalFound} ${this.articles.length}`;
    }
  }

  /**
   * Отображает или скрывает спиннер загрузки.
   * @param {boolean} show
   */
  showLoading(show) {
    if (this.dom.loadingSpinner) {
      this.dom.loadingSpinner.style.display = show ? 'block' : 'none';
    }
  }

  /**
   * Отображает или скрывает сообщение об ошибке.
   * @param {boolean} show
   * @param {string} message
   */
  showError(show, message = '') {
    if (this.dom.errorAlert) {
      this.dom.errorAlert.style.display = show ? 'block' : 'none';
      if (show && message) {
        const msgEl = this.dom.errorAlert.querySelector('.wikillm-error-msg');
        if (msgEl) msgEl.textContent = message;
      }
    }
  }

  /**
   * Экранирует HTML спецсимволы.
   * @param {string} str
   * @returns {string}
   */
  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Экспорт для сред модулей или глобального окна
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { WikiLLMController, WIKILLM_I18N };
} else {
  window.WikiLLMController = WikiLLMController;
  window.WIKILLM_I18N = WIKILLM_I18N;
}

// Автоматическая инициализация при загрузке документа
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('wikillm-container')) {
    window.wikillmApp = new WikiLLMController();
    window.wikillmApp.init();
  }
});
