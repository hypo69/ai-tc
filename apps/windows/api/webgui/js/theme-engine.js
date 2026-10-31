/**
 * =============================================================================
 * Process Name: Windows Web Styles - Theme Engine
 * =============================================================================
 * Description:
 *   Шаблонизатор и менеджер тем оформления для веб-интерфейса AI Windows Admin.
 *   Поддерживает светлые темы (Light, Brick), тёмные темы (Dark Contrast, Terminal),
 *   системный режим, динамическую регистрацию и шаблонизацию UI-селекторов.
 *
 * Usage Examples:
 *   import { themeEngine } from './theme-engine.js';
 *   themeEngine.applyTheme('brick');
 *   themeEngine.registerTheme({ id: 'custom', name: 'Custom Theme', category: 'dark' });
 *
 * File: theme-engine.js
 * Project: ai-windows-admin
 * Package: apps.windows.api.webgui.js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:34:00
 * =============================================================================
 */

/**
 * Ключ хранения выбранного режима темы в LocalStorage
 */
export const THEME_STORAGE_KEY = 'theme';

/**
 * Ключ хранения пользовательских дочерних тем в LocalStorage
 */
export const CUSTOM_THEMES_STORAGE_KEY = 'theme_custom_themes';

/**
 * Ключ хранения сканированного каталога стандартных тем в LocalStorage
 */
export const THEMES_CATALOG_STORAGE_KEY = 'themes_catalog';

/**
 * Ключ хранения пользовательских переопределений токенов темы в LocalStorage
 */
export const CUSTOM_OVERRIDES_STORAGE_KEY = 'theme_custom_overrides';

/**
 * Режим по умолчанию
 */
export const DEFAULT_THEME_MODE = 'system';

/**
 * Определение стандартных встроенных тем
 */
export const BUILTIN_THEMES = [
  {
    id: 'system',
    name: 'Системная',
    nameEn: 'System',
    category: 'system',
    icon: 'bi-circle-half',
    iconColor: 'text-info',
    description: 'Автоматический выбор темы на основе настроек операционной системы',
    baseType: 'system',
  },
  {
    id: 'dark',
    name: 'Стандартная тёмная',
    nameEn: 'Default Dark',
    category: 'dark',
    icon: 'bi-moon-stars-fill',
    iconColor: 'text-primary',
    description: 'Классическая глубокая контрастная тёмная тема',
    baseType: 'dark',
  },
  {
    id: 'brick',
    name: 'Кирпичная (Терракота)',
    nameEn: 'Brick (Terracotta)',
    category: 'light',
    icon: 'bi-bricks',
    iconColor: 'text-danger',
    description: 'Теплая светлая тема в стиле клинкерного кирпича и обожженной глины',
    baseType: 'light',
    tokens: { '--about-card-bg': 'linear-gradient(135deg, #f5e8d4 0%, #e2c8b8 100%)' },
  },
  {
    id: 'light',
    name: 'Windows System Light',
    nameEn: 'Windows System Light',
    category: 'light',
    icon: 'bi-window-sidebar',
    iconColor: 'text-primary',
    description: 'Стандартная светлая тема Windows в спокойных нейтрально-серых тонах (Slate)',
    baseType: 'light',
    tokens: {
      '--bg-color': '#e2e8f0',
      '--surface-1': '#eaedf2',
      '--surface-2': '#dbe2ea',
      '--card-bg': '#eaedf2',
      '--card-text': '#0f172a',
      '--nav-bg': '#e2e8f0',
      '--modal-bg': '#eaedf2',
      '--ui-bg-base': '#e2e8f0',
      '--ui-bg-surface': '#eaedf2',
      '--ui-bg-surface-elevated': '#dbe2ea',
      '--text-color': '#0f172a',
      '--text-muted': '#475569',
      '--ui-text-primary': '#0f172a',
      '--ui-text-secondary': '#475569',
      '--ui-text-muted': '#64748b',
      '--nav-text': '#1e293b',
      '--nav-active': '#0284c7',
      '--ui-accent': '#0284c7',
      '--ui-accent-hover': '#0369a1',
      '--border-color': '#cbd5e1',
      '--border-strong': '#94a3b8',
      '--border-subtle': '#e2e8f0',
      '--divider-color': '#cbd5e1',
      '--modal-border': '#cbd5e1',
      '--ui-border-color': '#cbd5e1',
      '--ui-border-color-subtle': '#e2e8f0',
      '--card-border': '#cbd5e1',
      '--ui-success': '#059669',
      '--ui-warning': '#b43418',
      '--ui-danger': '#b91c1c',
      '--ui-info': '#0284c7',
      '--badge-success-bg': 'rgba(5, 150, 105, 0.12)',
      '--badge-success-text': '#059669',
      '--badge-success-border': 'rgba(5, 150, 105, 0.25)',
      '--badge-warning-bg': 'rgba(180, 52, 24, 0.12)',
      '--badge-warning-text': '#b43418',
      '--badge-warning-border': 'rgba(180, 52, 24, 0.25)',
      '--badge-danger-bg': 'rgba(185, 28, 28, 0.12)',
      '--badge-danger-text': '#b91c1c',
      '--badge-danger-border': 'rgba(185, 28, 28, 0.25)',
      '--badge-info-bg': 'rgba(2, 132, 199, 0.12)',
      '--badge-info-text': '#0284c7',
      '--badge-info-border': 'rgba(2, 132, 199, 0.25)',
      '--badge-neutral-bg': '#e2e8f0',
      '--badge-neutral-text': '#475569',
      '--badge-neutral-border': '#cbd5e1',
      '--status-success-bg': 'rgba(5, 150, 105, 0.12)',
      '--status-success-text': '#059669',
      '--status-success-border': 'rgba(5, 150, 105, 0.25)',
      '--status-warning-bg': 'rgba(180, 52, 24, 0.12)',
      '--status-warning-text': '#b43418',
      '--status-warning-border': 'rgba(180, 52, 24, 0.25)',
      '--status-danger-bg': 'rgba(185, 28, 28, 0.12)',
      '--status-danger-text': '#b91c1c',
      '--status-danger-border': 'rgba(185, 28, 28, 0.25)',
      '--status-info-bg': 'rgba(2, 132, 199, 0.12)',
      '--status-info-text': '#0284c7',
      '--status-info-border': 'rgba(2, 132, 199, 0.25)',
      '--bs-body-bg': '#e2e8f0',
      '--bs-body-color': '#0f172a',
      '--bs-card-bg': '#eaedf2',
      '--bs-card-color': '#0f172a',
      '--bs-modal-bg': '#eaedf2',
      '--bs-modal-color': '#0f172a',
      '--bs-tertiary-bg': '#dbe2ea',
      '--bs-secondary-bg': '#dbe2ea',
      '--bs-list-group-bg': '#eaedf2',
      '--bs-dropdown-bg': '#eaedf2',
      '--bs-border-color': '#cbd5e1',
      '--table-bg': '#eaedf2',
      '--table-row-bg': '#eaedf2',
      '--table-color': '#0f172a',
      '--table-border-color': '#cbd5e1',
      '--about-card-bg': 'linear-gradient(135deg, #edf2f7 0%, #e2e8f0 100%)',
      '--badge-font-size': 'calc(0.72rem + 1pt)',
      'color-scheme': 'light',
    },
  },
  {
    id: 'nightview',
    name: 'NightView (Тёплая бумага)',
    nameEn: 'NightView (Warm Paper)',
    category: 'light',
    icon: 'bi-journal-bookmark-fill',
    iconColor: 'text-warning',
    description: 'Аутентичная пастельная тема NightView в стиле мягкой тёплой бумаги для комфортного ночного чтения',
    baseType: 'light',
    tokens: {
      '--bg-color': '#ede6d9',
      '--surface-1': '#f6f1e8',
      '--surface-2': '#e2dac9',
      '--card-bg': '#f6f1e8',
      '--card-text': '#18181b',
      '--nav-bg': '#f6f1e8',
      '--modal-bg': '#f6f1e8',
      '--ui-bg-base': '#ede6d9',
      '--ui-bg-surface': '#f6f1e8',
      '--ui-bg-surface-elevated': '#e2dac9',
      '--text-color': '#18181b',
      '--text-muted': '#3f3f46',
      '--ui-text-primary': '#18181b',
      '--ui-text-secondary': '#3f3f46',
      '--ui-text-muted': '#52525b',
      '--nav-text': '#27272a',
      '--nav-active': '#1d4ed8',
      '--ui-accent': '#1d4ed8',
      '--ui-accent-hover': '#1e40af',
      '--border-color': '#cfc5b4',
      '--border-strong': '#9ca3af',
      '--border-subtle': '#ded6c7',
      '--divider-color': '#cfc5b4',
      '--modal-border': '#cfc5b4',
      '--ui-border-color': '#cfc5b4',
      '--ui-border-color-subtle': '#ded6c7',
      '--card-border': '#cfc5b4',
      '--ui-success': '#185223',
      '--ui-warning': '#b43418',
      '--ui-danger': '#9e2b17',
      '--ui-info': '#184674',
      '--badge-success-bg': 'rgba(24, 82, 35, 0.12)',
      '--badge-success-text': '#185223',
      '--badge-success-border': 'rgba(24, 82, 35, 0.25)',
      '--badge-warning-bg': 'rgba(180, 52, 24, 0.12)',
      '--badge-warning-text': '#b43418',
      '--badge-warning-border': 'rgba(180, 52, 24, 0.25)',
      '--badge-danger-bg': 'rgba(158, 43, 23, 0.12)',
      '--badge-danger-text': '#9e2b17',
      '--badge-danger-border': 'rgba(158, 43, 23, 0.25)',
      '--badge-info-bg': 'rgba(24, 70, 116, 0.12)',
      '--badge-info-text': '#184674',
      '--badge-info-border': 'rgba(24, 70, 116, 0.25)',
      '--badge-neutral-bg': '#e2dac9',
      '--badge-neutral-text': '#3f3f46',
      '--badge-neutral-border': '#cfc5b4',
      '--status-success-bg': 'rgba(24, 82, 35, 0.12)',
      '--status-success-text': '#185223',
      '--status-success-border': 'rgba(24, 82, 35, 0.25)',
      '--status-warning-bg': 'rgba(180, 52, 24, 0.12)',
      '--status-warning-text': '#b43418',
      '--status-warning-border': 'rgba(180, 52, 24, 0.25)',
      '--status-danger-bg': 'rgba(158, 43, 23, 0.12)',
      '--status-danger-text': '#9e2b17',
      '--status-danger-border': 'rgba(158, 43, 23, 0.25)',
      '--status-info-bg': 'rgba(24, 70, 116, 0.12)',
      '--status-info-text': '#184674',
      '--status-info-border': 'rgba(24, 70, 116, 0.25)',
      '--bs-body-bg': '#ede6d9',
      '--bs-body-color': '#18181b',
      '--bs-card-bg': '#f6f1e8',
      '--bs-card-color': '#18181b',
      '--bs-modal-bg': '#f6f1e8',
      '--bs-modal-color': '#18181b',
      '--bs-tertiary-bg': '#e2dac9',
      '--bs-secondary-bg': '#e2dac9',
      '--bs-list-group-bg': '#f6f1e8',
      '--bs-dropdown-bg': '#f6f1e8',
      '--bs-border-color': '#cfc5b4',
      '--table-bg': '#f6f1e8',
      '--table-row-bg': '#f6f1e8',
      '--table-color': '#18181b',
      '--table-border-color': '#cfc5b4',
      '--about-card-bg': 'linear-gradient(135deg, #f6f1e8 0%, #ede6d9 100%)',
      '--badge-font-size': 'calc(0.72rem + 1pt)',
      '--bs-warning': '#b43418',
      '--bs-warning-rgb': '180, 52, 24',
      '--bs-info': '#184674',
      '--bs-info-rgb': '24, 70, 116',
      '--bs-primary': '#1d4ed8',
      '--bs-primary-rgb': '29, 78, 216',
      '--bs-danger': '#9e2b17',
      '--bs-danger-rgb': '158, 43, 23',
      '--bs-success': '#185223',
      '--bs-success-rgb': '24, 82, 35',
      '--bs-offcanvas-bg': '#f6f1e8',
      '--panel-bg': '#f6f1e8',
      '--panel-header-bg': '#e2dac9',
      'color-scheme': 'light',
    },
  },
  {
    id: 'theme-dark-slate',
    name: 'Dark Slate (Тёмный сланец)',
    nameEn: 'Dark Slate',
    category: 'dark',
    icon: 'bi-moon-fill',
    iconColor: 'text-primary',
    description: 'Глубокий благородный сланцевый стиль для комфортной работы в ночное время (Slate-900 / Sky-400)',
    baseType: 'dark',
    tokens: {
      "--bg-color": "#0f172a",
      "--surface-1": "#1e293b",
      "--surface-2": "#334155",
      "--card-bg": "#1e293b",
      "--card-text": "#f8fafc",
      "--nav-bg": "#1e293b",
      "--modal-bg": "#1e293b",
      "--modal-text": "#f8fafc",
      "--modal-border": "#334155",
      "--ui-bg-base": "#0f172a",
      "--ui-bg-surface": "#1e293b",
      "--ui-bg-surface-elevated": "#334155",
      "--text-color": "#f8fafc",
      "--text-muted": "#94a3b8",
      "--ui-text-primary": "#f8fafc",
      "--ui-text-secondary": "#cbd5e1",
      "--ui-text-muted": "#94a3b8",
      "--nav-text": "#cbd5e1",
      "--nav-active": "#38bdf8",
      "--nav-hover-bg": "#334155",
      "--ui-accent": "#38bdf8",
      "--ui-accent-hover": "#0ea5e9",
      "--border-color": "#334155",
      "--border-strong": "#475569",
      "--border-subtle": "rgba(100, 116, 139, 0.25)",
      "--border-contrast": "#64748b",
      "--divider-color": "#334155",
      "--ui-border-color": "#334155",
      "--ui-border-color-subtle": "rgba(100, 116, 139, 0.25)",
      "--card-border": "#334155",
      "--ui-success": "#34d399",
      "--ui-warning": "#fbbf24",
      "--ui-danger": "#f87171",
      "--ui-info": "#38bdf8",
      "--badge-success-bg": "rgba(52, 211, 153, 0.15)",
      "--badge-success-text": "#34d399",
      "--badge-success-border": "rgba(52, 211, 153, 0.3)",
      "--badge-warning-bg": "rgba(251, 191, 36, 0.15)",
      "--badge-warning-text": "#fbbf24",
      "--badge-warning-border": "rgba(251, 191, 36, 0.3)",
      "--badge-danger-bg": "rgba(248, 113, 113, 0.15)",
      "--badge-danger-text": "#f87171",
      "--badge-danger-border": "rgba(248, 113, 113, 0.3)",
      "--badge-info-bg": "rgba(56, 189, 248, 0.15)",
      "--badge-info-text": "#38bdf8",
      "--badge-info-border": "rgba(56, 189, 248, 0.3)",
      "--badge-neutral-bg": "#334155",
      "--badge-neutral-text": "#cbd5e1",
      "--badge-neutral-border": "#475569",
      "--status-success-bg": "rgba(52, 211, 153, 0.15)",
      "--status-success-text": "#34d399",
      "--status-success-border": "rgba(52, 211, 153, 0.3)",
      "--status-warning-bg": "rgba(251, 191, 36, 0.15)",
      "--status-warning-text": "#fbbf24",
      "--status-warning-border": "rgba(251, 191, 36, 0.3)",
      "--status-danger-bg": "rgba(248, 113, 113, 0.15)",
      "--status-danger-text": "#f87171",
      "--status-danger-border": "rgba(248, 113, 113, 0.3)",
      "--status-info-bg": "rgba(56, 189, 248, 0.15)",
      "--status-info-text": "#38bdf8",
      "--status-info-border": "rgba(56, 189, 248, 0.3)",
      "--bs-body-bg": "#0f172a",
      "--bs-body-bg-rgb": "15, 23, 42",
      "--bs-body-color": "#f8fafc",
      "--bs-card-bg": "#1e293b",
      "--bs-card-color": "#f8fafc",
      "--bs-modal-bg": "#1e293b",
      "--bs-modal-color": "#f8fafc",
      "--bs-offcanvas-bg": "#1e293b",
      "--bs-tertiary-bg": "#334155",
      "--bs-tertiary-bg-rgb": "51, 65, 85",
      "--bs-secondary-bg": "#334155",
      "--bs-secondary-bg-rgb": "51, 65, 85",
      "--bs-list-group-bg": "#1e293b",
      "--bs-dropdown-bg": "#1e293b",
      "--bs-dropdown-color": "#f8fafc",
      "--bs-dropdown-border-color": "#334155",
      "--bs-border-color": "#334155",
      "--table-bg": "#1e293b",
      "--table-color": "#f8fafc",
      "--table-border-color": "#334155",
      "--table-header-bg": "#334155",
      "--table-row-bg": "#1e293b",
      "--table-hover-bg": "#283548",
      "--about-card-bg": "linear-gradient(135deg, #1e293b 0%, #162032 100%)",
      "--badge-font-size": "calc(0.72rem + 1pt)",
      "color-scheme": "dark",
      "--bs-primary": "#38bdf8",
      "--bs-primary-rgb": "56, 189, 248",
      "--bs-info": "#38bdf8",
      "--bs-info-rgb": "56, 189, 248",
      "--panel-bg": "#1e293b",
      "--panel-header-bg": "#334155",
      "--panel-header-color": "#f8fafc",
      "--panel-header-font-size": "1.75rem",
      "--tab-header-title-color": "#f8fafc",
      "--tab-header-subtitle-color": "#94a3b8"
},
  },
  {
    id: 'theme-light-enterprise',
    name: 'Light Enterprise (Светлый корпоративный)',
    nameEn: 'Light Enterprise',
    category: 'light',
    icon: 'bi-building',
    iconColor: 'text-primary',
    description: 'Чистый корпоративный светлый стиль (UI Kit v2.0)',
    baseType: 'light',
  },
  {
    id: 'theme-cyberpunk',
    name: 'Cyberpunk Neon (Киберпанк неон)',
    nameEn: 'Cyberpunk Neon',
    category: 'dark',
    icon: 'bi-lightning-fill',
    iconColor: 'text-warning',
    description: 'Высокотехнологичный неоновый стиль с киберпанк-акцентами',
    baseType: 'dark',
  },
  {
    id: 'terminal',
    name: 'Терминал (Matrix / CRT)',
    nameEn: 'Terminal (Matrix / CRT)',
    category: 'dark',
    icon: 'bi-terminal-fill',
    iconColor: 'text-success',
    description: 'Тёмная тема в ретро-стиле зеленого фосфорного терминала с моноширинными акцентами',
    baseType: 'dark',
  },
  {
    id: 'nordic-frost',
    name: 'Nordic Frost (Скандинавский морозный)',
    nameEn: 'Nordic Frost',
    category: 'dark',
    icon: 'bi-snow',
    iconColor: 'text-info',
    description: 'Прохладный минималистичный скандинавский синий стиль',
    baseType: 'dark',
    tokens: {
      '--bg-color': '#0f172a',
      '--surface-1': '#1e293b',
      '--surface-2': '#334155',
      '--ui-accent': '#38bdf8'
    }
  },
  {
    id: 'solarized-dark',
    name: 'Solarized Deep (Глубокий сине-зеленый)',
    nameEn: 'Solarized Deep',
    category: 'dark',
    icon: 'bi-tree-fill',
    iconColor: 'text-success',
    description: 'Классическая мягкая палитра глубоких сине-зеленых тонов',
    baseType: 'dark',
    tokens: {
      '--bg-color': '#002b36',
      '--surface-1': '#073642',
      '--surface-2': '#094352',
      '--ui-accent': '#268bd2'
    }
  },
  {
    id: 'theme-high-contrast',
    name: 'High Contrast (Высокая контрастность)',
    nameEn: 'High Contrast',
    category: 'dark',
    icon: 'bi-eye-fill',
    iconColor: 'text-light',
    description: 'Максимально контрастная черно-белая тема для доступности',
    baseType: 'dark',
  },
];

/**
 * Класс шаблонизатора и оркестратора тем оформления
 */
export class ThemeEngine {
  constructor() {
    /** @type {Map<string, Object>} */
    this.registry = new Map();
    this.mediaQueryListenerAttached = false;
    this._dynamicStyleEl = null;
    this._customStyleEl = null;

    // Регистрация встроенных стандартных тем (неизменяемых)
    for (const theme of BUILTIN_THEMES) {
      this.registry.set(theme.id, { ...theme, isBuiltin: true, isChild: false });
    }

    // Первичное наполнение реестра каталогом тем из кеша браузера
    this.loadCatalogThemes();

    // Загрузка сохранённых дочерних тем из LocalStorage
    this.loadCustomThemes();

    // Сохранение актуального каталога тем в кеш браузера для инлайн-скрипта в <head>
    this.saveCatalogThemes();
  }

  /**
   * Загружает сохраненный каталог стандартных тем из кеша браузера (LocalStorage).
   */
  loadCatalogThemes() {
    if (typeof localStorage === 'undefined') return;
    try {
      const raw = localStorage.getItem(THEMES_CATALOG_STORAGE_KEY);
      if (!raw) return;
      const list = JSON.parse(raw);
      if (Array.isArray(list)) {
        for (const t of list) {
          if (t && t.id && !this.registry.has(t.id)) {
            this.registry.set(t.id, {
              ...t,
              isBuiltin: true,
              isChild: false,
              baseType: t.baseType || (t.category === 'light' ? 'light' : 'dark'),
            });
          }
        }
      }
    } catch (e) {
      console.warn('[ThemeEngine] Ошибка чтения каталога тем из кеша:', e);
    }
  }

  /**
   * Сохраняет полный каталог стандартных тем в кеш браузера для быстрого доступа инлайн-скрипта в <head>.
   */
  saveCatalogThemes() {
    if (typeof localStorage === 'undefined') return;
    try {
      const themes = this.getStandardThemes().map((t) => ({
        id: t.id,
        name: t.name,
        nameEn: t.nameEn,
        category: t.category,
        baseType: t.baseType,
        icon: t.icon,
        iconColor: t.iconColor,
        description: t.description,
        tokens: t.tokens || null,
      }));
      localStorage.setItem(THEMES_CATALOG_STORAGE_KEY, JSON.stringify(themes));
    } catch (e) {
      console.warn('[ThemeEngine] Не удалось сохранить каталог тем в кеш браузера:', e);
    }
  }

  /**
   * Асинхронно запрашивает актуальный каталог тем с бэкенда (/api/themes) или статического JSON.
   */
  async fetchThemesCatalog() {
    if (typeof window === 'undefined' || typeof fetch !== 'function') return;
    try {
      let res = await fetch('/api/themes').catch(() => null);
      if (!res || !res.ok) {
        res = await fetch('/html/themes/themes_catalog.json').catch(() => null);
      }
      if (res && res.ok) {
        const data = await res.json();
        const themesList = Array.isArray(data) ? data : (data.themes || []);
        if (Array.isArray(themesList) && themesList.length > 0) {
          let hasUpdates = false;
          for (const t of themesList) {
            if (t && t.id) {
              const existing = this.registry.get(t.id);
              this.registry.set(t.id, {
                ...(existing || {}),
                ...t,
                isBuiltin: true,
                isChild: false,
                baseType: t.baseType || (t.category === 'light' ? 'light' : 'dark'),
              });
              hasUpdates = true;
            }
          }
          if (hasUpdates) {
            this.saveCatalogThemes();
            this.syncSelectInputs();
          }
        }
      }
    } catch (e) {
      // Игнорируем ошибки сети - используется сохраненный кеш
    }
  }

  /**
   * Загружает сохраненные дочерние темы из LocalStorage и регистрирует их в реестре.
   */
  loadCustomThemes() {
    if (typeof localStorage === 'undefined') return;
    try {
      const raw = localStorage.getItem(CUSTOM_THEMES_STORAGE_KEY);
      if (!raw) return;
      const themes = JSON.parse(raw);
      if (Array.isArray(themes)) {
        for (const t of themes) {
          if (t && t.id && t.parentId) {
            const parent = this.registry.get(t.parentId) || this.registry.get('dark');
            const baseType = t.baseType || parent?.baseType || (parent?.category === 'light' ? 'light' : 'dark');
            const category = t.category || parent?.category || baseType;

            this.registry.set(t.id, {
              id: t.id,
              name: t.name || t.id,
              nameEn: t.nameEn || t.name || t.id,
              parentId: t.parentId,
              isChild: true,
              isBuiltin: false,
              category,
              baseType,
              icon: t.icon || 'bi-palette2',
              iconColor: t.iconColor || parent?.iconColor || 'text-info',
              description: t.description || `Дочерняя тема на базе ${parent?.name || t.parentId}`,
              createdAt: t.createdAt || new Date().toISOString(),
              updatedAt: t.updatedAt || new Date().toISOString(),
              settings: t.settings || null,
              tokens: {
                ...(parent?.tokens || {}),
                ...(t.tokens || {}),
              },
            });
          }
        }
      }
    } catch (e) {
      console.warn('[ThemeEngine] Ошибка загрузки пользовательских тем:', e);
    }
  }

  /**
   * Сохраняет все дочерние темы в LocalStorage.
   */
  saveCustomThemes() {
    if (typeof localStorage === 'undefined') return;
    try {
      const childThemes = this.getCustomThemes();
      localStorage.setItem(CUSTOM_THEMES_STORAGE_KEY, JSON.stringify(childThemes));
    } catch (e) {
      console.warn('[ThemeEngine] Ошибка сохранения пользовательских тем:', e);
    }
  }

  /**
   * Создает новую дочернюю тему на базе указанной родительской стандартной темы.
   * @param {Object} params
   * @param {string} params.name - Название дочерней темы
   * @param {string} params.parentId - Идентификатор родительской темы
   * @param {Object} [params.tokens={}] - CSS токены переопределений
   * @param {Object} [params.settings={}] - Полное состояние редактора (слайдеры, эффекты)
   * @param {string} [params.description=''] - Описание темы
   * @returns {Object} Созданная дочерняя тема
   */
  createChildTheme({ name, parentId, tokens = {}, settings = {}, description = '' }) {
    if (!name || !parentId) {
      throw new Error('Имя темы и идентификатор базовой темы обязательны.');
    }
    const parent = this.getTheme(parentId);
    if (!parent) {
      throw new Error(`Базовая тема "${parentId}" не найдена.`);
    }

    const cleanSlug = name.toLowerCase().replace(/[^a-z0-9а-яё]/gi, '-').replace(/-+/g, '-').slice(0, 24);
    const id = `child-${parentId.replace(/^theme-/, '')}-${cleanSlug || 'theme'}-${Date.now().toString(36)}`;

    const baseType = parent.baseType || (parent.category === 'light' ? 'light' : 'dark');
    const category = parent.category || baseType;
    const now = new Date().toISOString();

    const childDef = {
      id,
      name,
      nameEn: name,
      parentId,
      isChild: true,
      isBuiltin: false,
      category,
      baseType,
      icon: 'bi-palette2',
      iconColor: parent.iconColor || 'text-info',
      description: description || `Дочерняя тема на базе "${parent.name}"`,
      createdAt: now,
      updatedAt: now,
      settings: { ...settings },
      tokens: {
        ...(parent.tokens || {}),
        ...tokens,
      },
    };

    this.registry.set(id, childDef);
    this.saveCustomThemes();
    this._applyDynamicTokens();

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('themelistchanged', { detail: { action: 'create', theme: childDef } }));
    }
    return childDef;
  }

  /**
   * Обновляет параметры существующей дочерней темы.
   * @param {string} id - ID дочерней темы
   * @param {Object} params - Обновляемые параметры
   * @returns {Object} Обновленная тема
   */
  updateChildTheme(id, { name, tokens, settings, description }) {
    const existing = this.registry.get(id);
    if (!existing) {
      throw new Error(`Тема "${id}" не найдена.`);
    }
    if (existing.isBuiltin) {
      throw new Error('Стандартные темы системы защищены от перезаписи. Создайте дочернюю тему.');
    }
    if (!existing.isChild) {
      throw new Error(`Тема "${id}" не является дочерней темой.`);
    }

    const parent = this.getTheme(existing.parentId) || this.getTheme('dark');
    if (name) existing.name = name;
    if (description !== undefined) existing.description = description;
    if (settings) existing.settings = { ...(existing.settings || {}), ...settings };
    if (tokens) {
      existing.tokens = {
        ...(parent?.tokens || {}),
        ...(existing.tokens || {}),
        ...tokens,
      };
    }
    existing.updatedAt = new Date().toISOString();

    this.registry.set(id, existing);
    this.saveCustomThemes();
    this._applyDynamicTokens();

    if (this.getSavedMode() === id) {
      this.applyTheme(id);
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('themelistchanged', { detail: { action: 'update', theme: existing } }));
    }
    return existing;
  }

  /**
   * Удаляет дочернюю тему.
   * @param {string} id - ID темы
   * @returns {boolean}
   */
  deleteChildTheme(id) {
    const existing = this.registry.get(id);
    if (!existing) return false;
    if (existing.isBuiltin) {
      throw new Error('Нельзя удалять встроенные стандартные темы.');
    }

    this.registry.delete(id);
    this.saveCustomThemes();
    this._applyDynamicTokens();

    if (this.getSavedMode() === id) {
      const fallbackMode = existing.parentId && this.registry.has(existing.parentId) ? existing.parentId : 'dark';
      this.applyTheme(fallbackMode);
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('themelistchanged', { detail: { action: 'delete', id } }));
    }
    return true;
  }

  /**
   * Сбрасывает токены и настройки дочерней темы к эталонным значениям ее родителя.
   * @param {string} id - ID дочерней темы
   * @returns {Object|null}
   */
  resetChildThemeToParent(id) {
    const existing = this.registry.get(id);
    if (!existing || !existing.isChild) return null;
    const parent = this.getTheme(existing.parentId);
    if (!parent) return null;

    existing.tokens = { ...(parent.tokens || {}) };
    existing.settings = null;
    existing.updatedAt = new Date().toISOString();

    this.registry.set(id, existing);
    this.saveCustomThemes();
    this._applyDynamicTokens();

    if (this.getSavedMode() === id) {
      this.applyTheme(id);
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('themelistchanged', { detail: { action: 'reset', theme: existing } }));
    }
    return existing;
  }

  /**
   * Возвращает список всех зарегистрированных дочерних тем.
   * @returns {Array<Object>}
   */
  getCustomThemes() {
    return Array.from(this.registry.values()).filter((t) => t.isChild);
  }

  /**
   * Возвращает дочернюю тему по ее идентификатору.
   * @param {string} id
   * @returns {Object|null}
   */
  getChildTheme(id) {
    const t = this.registry.get(id);
    return t && t.isChild ? t : null;
  }

  /**
   * Возвращает список всех стандартных тем.
   * @returns {Array<Object>}
   */
  getStandardThemes() {
    return Array.from(this.registry.values()).filter((t) => t.isBuiltin && t.id !== 'system');
  }

  /**
   * Проверяет, является ли тема стандартной (встроенной).
   * @param {string} id
   * @returns {boolean}
   */
  isBuiltinTheme(id) {
    const t = this.registry.get(id);
    return !!(t && t.isBuiltin);
  }

  /**
   * Проверяет, является ли тема дочерней (пользовательской).
   * @param {string} id
   * @returns {boolean}
   */
  isChildTheme(id) {
    const t = this.registry.get(id);
    return !!(t && t.isChild);
  }

  /**
   * Возвращает родительскую тему для дочерней темы.
   * @param {string} childId
   * @returns {Object|null}
   */
  getParentTheme(childId) {
    const child = this.getChildTheme(childId);
    if (!child || !child.parentId) return null;
    return this.getTheme(child.parentId);
  }

  /**
   * Регистрирует новую тему в реестре шаблонизатора.
   * @param {Object} themeDef - Определение темы
   * @param {string} themeDef.id - Уникальный идентификатор темы
   * @param {string} themeDef.name - Отображаемое имя темы (русский)
   * @param {string} [themeDef.nameEn] - Отображаемое имя темы (английский)
   * @param {'light'|'dark'|'system'} themeDef.category - Категория темы
   * @param {string} [themeDef.icon] - Иконка Bootstrap Icons (например, 'bi-palette')
   * @param {string} [themeDef.iconColor] - CSS класс цвета иконки (например, 'text-warning')
   * @param {string} [themeDef.description] - Описание темы
   * @param {'light'|'dark'} [themeDef.baseType] - Базовый тип темы (светлая/тёмная)
   * @param {Object<string, string>} [themeDef.tokens] - Словарь CSS-переменных
   */
  registerTheme(themeDef) {
    if (!themeDef || !themeDef.id) {
      console.warn('[ThemeEngine] Некорректное определение темы:', themeDef);
      return;
    }

    const baseType = themeDef.baseType || (themeDef.category === 'dark' ? 'dark' : 'light');
    this.registry.set(themeDef.id, {
      id: themeDef.id,
      name: themeDef.name || themeDef.id,
      nameEn: themeDef.nameEn || themeDef.name || themeDef.id,
      category: themeDef.category || 'dark',
      icon: themeDef.icon || 'bi-palette',
      iconColor: themeDef.iconColor || 'text-info',
      description: themeDef.description || '',
      baseType,
      tokens: themeDef.tokens || null,
    });

    if (themeDef.tokens) {
      this._applyDynamicTokens();
    }
  }

  /**
   * Возвращает определение темы по идентификатору.
   * @param {string} themeId
   * @returns {Object|null}
   */
  getTheme(themeId) {
    return this.registry.get(themeId) || null;
  }

  /**
   * Возвращает список всех зарегистрированных тем.
   * @returns {Array<Object>}
   */
  getAllThemes() {
    return Array.from(this.registry.values());
  }

  /**
   * Возвращает темы, отфильтрованные по категории ('light' | 'dark' | 'system').
   * @param {'light'|'dark'|'system'} category
   * @returns {Array<Object>}
   */
  getThemesByCategory(category) {
    return this.getAllThemes().filter((t) => t.category === category);
  }

  /**
   * Получает сохранённый режим темы из LocalStorage.
   * @returns {string}
   */
  getSavedMode() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved && this.registry.has(saved)) {
      return saved;
    }
    return DEFAULT_THEME_MODE;
  }

  /**
   * Разрешает эффективный идентификатор темы ('light', 'dark', 'brick', 'terminal' и т.д.)
   * @param {string} [mode]
   * @returns {string}
   */
  resolveTheme(mode = this.getSavedMode()) {
    if (mode === 'system') {
      const prefersDark =
        typeof window !== 'undefined' &&
        window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches;
      return prefersDark ? 'dark' : 'light';
    }

    if (this.registry.has(mode)) {
      return mode;
    }
    return 'dark';
  }

  /**
   * Определяет базовый режим Bootstrap ('light' | 'dark') для текущей темы.
   * @param {string} resolvedThemeId
   * @returns {'light'|'dark'}
   */
  getBsTheme(resolvedThemeId) {
    const theme = this.getTheme(resolvedThemeId);
    if (theme) {
      return theme.baseType || (theme.category === 'dark' ? 'dark' : 'light');
    }
    return resolvedThemeId === 'light' || resolvedThemeId === 'brick' ? 'light' : 'dark';
  }

  /**
   * Применяет тему к DOM, обновляет атрибуты и UI-элементы.
   * @param {string} mode
   */
  applyTheme(mode) {
    if (!mode || !this.registry.has(mode)) {
      mode = DEFAULT_THEME_MODE;
    }

    localStorage.setItem(THEME_STORAGE_KEY, mode);

    const resolved = this.resolveTheme(mode);
    const themeDef = this.getTheme(resolved);
    const parentTheme = themeDef?.isChild ? this.getTheme(themeDef.parentId) : null;
    const bsTheme = this.getBsTheme(resolved);

    if (typeof document !== 'undefined') {
      // Очищаем оверрайды предпросмотра и сохраненные переопределения при переключении на стандартные темы
      if (this.isBuiltinTheme(mode)) {
        if (this._customStyleEl) {
          this._customStyleEl.textContent = '';
        }
        try {
          localStorage.removeItem(CUSTOM_OVERRIDES_STORAGE_KEY);
        } catch {}
      } else if (this._customStyleEl && !this.getCustomOverrides()) {
        this._customStyleEl.textContent = '';
      }

      // 1. Установка атрибутов на <html>
      document.documentElement.setAttribute('data-theme', resolved);
      document.documentElement.setAttribute('data-bs-theme', bsTheme);
      document.documentElement.setAttribute('data-theme-mode', mode);
      if (parentTheme) {
        document.documentElement.setAttribute('data-parent-theme', parentTheme.id);
      } else {
        document.documentElement.removeAttribute('data-parent-theme');
      }

      // 1b. Применение классов тем на <html> и body для themes.css (10_UI_DESIGN_SYSTEM)
      const themeClasses = ['theme-dark-slate', 'theme-light-enterprise', 'theme-cyberpunk', 'theme-high-contrast', 'theme-nightview', 'theme-light', 'dark-theme'];
      themeClasses.forEach((cls) => {
        if (document.documentElement?.classList?.remove) document.documentElement.classList.remove(cls);
        if (document.body?.classList?.remove) document.body.classList.remove(cls);
      });
      if (typeof document.documentElement?.className === 'string') {
        document.documentElement.className = document.documentElement.className.replace(/\bchild-theme\S*/g, '').trim();
      }
      if (typeof document.body?.className === 'string') {
        document.body.className = document.body.className.replace(/\bchild-theme\S*/g, '').trim();
      }

      let baseClass = parentTheme ? parentTheme.id : resolved;
      if (baseClass === 'dark') baseClass = 'theme-dark-slate';
      if (baseClass === 'light') baseClass = 'theme-light-enterprise';
      if (baseClass === 'nightview') baseClass = 'theme-nightview';

      if (themeClasses.includes(baseClass)) {
        if (document.documentElement?.classList?.add) document.documentElement.classList.add(baseClass);
        if (document.body?.classList?.add) document.body.classList.add(baseClass);
      } else if (themeClasses.includes(mode)) {
        if (document.documentElement?.classList?.add) document.documentElement.classList.add(mode);
        if (document.body?.classList?.add) document.body.classList.add(mode);
      }

      if (themeDef?.isChild) {
        if (document.documentElement?.classList?.add) {
          document.documentElement.classList.add('child-theme');
          document.documentElement.classList.add(`child-theme-${themeDef.id}`);
        }
        if (document.body?.classList?.add) {
          document.body.classList.add('child-theme');
          document.body.classList.add(`child-theme-${themeDef.id}`);
        }
      }

      // 2. Обновление иконок и кнопок
      this._updateThemeUI(mode, resolved);

      // 3. Синхронизация селекторов выбора тем
      this.syncSelectInputs(mode);
    }

    // 4. Оповещение слушателей через CustomEvent
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('themechanged', {
          detail: {
            mode,
            resolved,
            bsTheme,
            themeMeta: this.getTheme(resolved),
            isChild: !!themeDef?.isChild,
            parentTheme: parentTheme || null,
          },
        })
      );
    }
  }

  /**
   * Применяет тему во временном режиме предварительного просмотра без сохранения в LocalStorage
   * и без изменения выбранной пользователем темы.
   * @param {string} mode - Идентификатор темы (пресета) для предпросмотра
   */
  previewTheme(mode) {
    if (!mode || !this.registry.has(mode)) {
      return;
    }

    const resolved = this.resolveTheme(mode);
    const themeDef = this.getTheme(resolved);
    const parentTheme = themeDef?.isChild ? this.getTheme(themeDef.parentId) : null;
    const bsTheme = this.getBsTheme(resolved);

    if (typeof document !== 'undefined') {
      // При предпросмотре встроенной темы очищаем временный блок оверрайдов
      if (this._customStyleEl && this.isBuiltinTheme(mode)) {
        this._customStyleEl.textContent = '';
      }

      // 1. Установка атрибутов на <html>
      document.documentElement.setAttribute('data-theme', resolved);
      document.documentElement.setAttribute('data-bs-theme', bsTheme);
      document.documentElement.setAttribute('data-theme-mode', mode);
      if (parentTheme) {
        document.documentElement.setAttribute('data-parent-theme', parentTheme.id);
      } else {
        document.documentElement.removeAttribute('data-parent-theme');
      }

      // 2. Применение классов тем на <html> и body для themes.css
      const themeClasses = ['theme-dark-slate', 'theme-light-enterprise', 'theme-cyberpunk', 'theme-high-contrast', 'theme-nightview', 'theme-light', 'dark-theme'];
      themeClasses.forEach((cls) => {
        if (document.documentElement?.classList?.remove) document.documentElement.classList.remove(cls);
        if (document.body?.classList?.remove) document.body.classList.remove(cls);
      });
      if (typeof document.documentElement?.className === 'string') {
        document.documentElement.className = document.documentElement.className.replace(/\bchild-theme\S*/g, '').trim();
      }
      if (typeof document.body?.className === 'string') {
        document.body.className = document.body.className.replace(/\bchild-theme\S*/g, '').trim();
      }

      let baseClass = parentTheme ? parentTheme.id : resolved;
      if (baseClass === 'dark') baseClass = 'theme-dark-slate';
      if (baseClass === 'light') baseClass = 'theme-light-enterprise';
      if (baseClass === 'nightview') baseClass = 'theme-nightview';

      if (themeClasses.includes(baseClass)) {
        if (document.documentElement?.classList?.add) document.documentElement.classList.add(baseClass);
        if (document.body?.classList?.add) document.body.classList.add(baseClass);
      } else if (themeClasses.includes(mode)) {
        if (document.documentElement?.classList?.add) document.documentElement.classList.add(mode);
        if (document.body?.classList?.add) document.body.classList.add(mode);
      }

      if (themeDef?.isChild) {
        if (document.documentElement?.classList?.add) {
          document.documentElement.classList.add('child-theme');
          document.documentElement.classList.add(`child-theme-${themeDef.id}`);
        }
        if (document.body?.classList?.add) {
          document.body.classList.add('child-theme');
          document.body.classList.add(`child-theme-${themeDef.id}`);
        }
      }
    }

    // 3. Оповещение слушателей о временном предпросмотре без персистентности
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('themepreviewchanged', {
          detail: {
            mode,
            resolved,
            bsTheme,
            themeMeta: this.getTheme(resolved),
            isChild: !!themeDef?.isChild,
            parentTheme: parentTheme || null,
          },
        })
      );
    }
  }

  /**
   * Восстанавливает сохраненную пользователем тему и сбрасывает временные стили предпросмотра.
   */
  restoreUserTheme() {
    const savedMode = this.getSavedMode();
    this.applyTheme(savedMode);
    this._applyStoredOverrides();
  }

  /**
   * Генерирует HTML-разметку опций для тега <select> с группировкой по категориям.
   * @param {string} [currentMode]
   * @returns {string}
   */
  renderOptionsHTML(currentMode = this.getSavedMode()) {
    const customThemes = this.getCustomThemes();
    const lightThemes = this.getThemesByCategory('light').filter((t) => !t.isChild);
    const darkThemes = this.getThemesByCategory('dark').filter((t) => !t.isChild);
    const systemThemes = this.getThemesByCategory('system');

    const getIcon = (t) => {
      if (t.isChild) return '🎨';
      if (t.id === 'system') return '🌓';
      if (t.id === 'brick') return '🧱';
      if (t.id === 'light') return '🪟';
      if (t.id === 'nightview') return '📖';
      if (t.id === 'dark') return '🌙';
      if (t.id === 'terminal') return '📟';
      if (t.id === 'theme-dark-slate') return '🌑';
      if (t.id === 'theme-light-enterprise') return '🏢';
      if (t.id === 'theme-cyberpunk') return '⚡';
      if (t.id === 'theme-high-contrast') return '👁️';
      if (t.id === 'nordic-frost') return '❄️';
      if (t.id === 'solarized-dark') return '🌲';
      return t.category === 'light' ? '☀️' : '🌙';
    };

    let html = '';

    if (systemThemes.length > 0) {
      for (const t of systemThemes) {
        const isSelected = t.id === currentMode ? ' selected' : '';
        html += `<option value="${t.id}"${isSelected}>${getIcon(t)} ${t.name}</option>\n`;
      }
    }

    if (customThemes.length > 0) {
      html += '<optgroup label="✨ Пользовательские (дочерние) темы">\n';
      for (const t of customThemes) {
        const isSelected = t.id === currentMode ? ' selected' : '';
        const parent = this.getTheme(t.parentId);
        const parentName = parent ? parent.name : t.parentId;
        html += `  <option value="${t.id}"${isSelected}>${getIcon(t)} ${t.name} (на базе: ${parentName})</option>\n`;
      }
      html += '</optgroup>\n';
    }

    if (lightThemes.length > 0) {
      html += '<optgroup label="☀️ Светлые темы">\n';
      for (const t of lightThemes) {
        const isSelected = t.id === currentMode ? ' selected' : '';
        html += `  <option value="${t.id}"${isSelected}>${getIcon(t)} ${t.name}</option>\n`;
      }
      html += '</optgroup>\n';
    }

    if (darkThemes.length > 0) {
      html += '<optgroup label="🌙 Тёмные темы">\n';
      for (const t of darkThemes) {
        const isSelected = t.id === currentMode ? ' selected' : '';
        html += `  <option value="${t.id}"${isSelected}>${getIcon(t)} ${t.name}</option>\n`;
      }
      html += '</optgroup>\n';
    }

    return html;
  }

  /**
   * Синхронизирует все элементы <select> выбора темы на странице.
   * @param {string} [mode]
   */
  syncSelectInputs(mode = this.getSavedMode()) {
    if (typeof document === 'undefined') return;

    const selectors = document.querySelectorAll(
      '.theme-selector, #apps-theme-selector, #settings-theme, #modal-theme-selector, #quick-theme-selector'
    );

    const generatedHTML = this.renderOptionsHTML(mode);

    selectors.forEach((selectEl) => {
      selectEl.innerHTML = generatedHTML;
      selectEl.value = mode;
    });
  }

  /**
   * Инициализирует менеджер тем, регистрирует обработчики событий и применяет начальную тему.
   */
  init() {
    const currentMode = this.getSavedMode();
    this.applyTheme(currentMode);
    this._applyStoredOverrides();
    this.fetchThemesCatalog();

    // Подписка на изменение системной темы
    if (!this.mediaQueryListenerAttached && typeof window !== 'undefined' && window.matchMedia) {
      try {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handler = () => {
          if (this.getSavedMode() === 'system') {
            this.applyTheme('system');
          }
        };
        if (mediaQuery.addEventListener) {
          mediaQuery.addEventListener('change', handler);
        } else if (mediaQuery.addListener) {
          mediaQuery.addListener(handler);
        }
        this.mediaQueryListenerAttached = true;
      } catch (e) {
        console.warn('[ThemeEngine] Не удалось подписаться на prefers-color-scheme:', e);
      }
    }

    if (typeof document === 'undefined') return;

    // Наполнение всех селекторов опциями
    this.syncSelectInputs(currentMode);

    // Привязка слушателей изменений к селекторам тем
    document.querySelectorAll(
      '.theme-selector, #apps-theme-selector, #settings-theme, #modal-theme-selector, #quick-theme-selector'
    ).forEach((sel) => {
      sel.addEventListener('change', (e) => {
        this.applyTheme(e.target.value);
      });
    });

    // Привязка кликов по кнопкам data-theme-value
    document.querySelectorAll('[data-theme-value]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const selected = btn.getAttribute('data-theme-value');
        if (selected) {
          this.applyTheme(selected);
        }
      });
    });

    // Привязка кнопки быстрого циклического переключения тем (legacy / toggle button)
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn && !toggleBtn.hasAttribute('data-bs-toggle')) {
      toggleBtn.addEventListener('click', () => {
        const mode = this.getSavedMode();
        // Цикл переключения: system -> light -> brick -> dark -> terminal -> system
        const cycle = ['system', 'light', 'brick', 'dark', 'terminal'];
        const currentIndex = cycle.indexOf(mode);
        const nextMode = cycle[(currentIndex + 1) % cycle.length];
        this.applyTheme(nextMode);
      });
    }
  }

  /**
   * Обновляет UI-иконки, подсказки и активные состояния в выпадающих меню.
   * @private
   */
  _updateThemeUI(mode, resolved) {
    const activeTheme = this.getTheme(resolved) || this.getTheme('dark');
    const modeTheme = this.getTheme(mode);

    const iconEl = document.getElementById('theme-icon');
    const toggleBtn = document.getElementById('theme-toggle');
    const dropdownBtn = document.getElementById('theme-dropdown');

    const iconClass = modeTheme ? modeTheme.icon : 'bi-circle-half';
    const iconColor = modeTheme ? modeTheme.iconColor : 'text-info';
    const titleText =
      mode === 'system'
        ? `Системная тема (${activeTheme ? activeTheme.name : resolved})`
        : modeTheme
        ? modeTheme.name
        : resolved;

    if (iconEl) {
      iconEl.className = `bi ${iconClass} ${iconColor}`;
    }

    if (dropdownBtn) {
      dropdownBtn.setAttribute('title', titleText);
    }

    if (toggleBtn) {
      toggleBtn.innerHTML = `<i class="bi ${iconClass} ${iconColor}"></i>`;
      toggleBtn.setAttribute('title', titleText);
    }

    // Обновление галочек в выпадающих меню
    document.querySelectorAll('.theme-check-icon').forEach((icon) => {
      const target = icon.getAttribute('data-theme-check');
      if (target === mode) {
        icon.classList.remove('d-none');
      } else {
        icon.classList.add('d-none');
      }
    });

    // Обновление active класса
    document.querySelectorAll('[data-theme-value]').forEach((item) => {
      const val = item.getAttribute('data-theme-value');
      if (val === mode) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  }

  /**
   * Инжектирует динамические стили для зарегистрированных кастомных тем с токенами.
   * @private
   */
  _applyDynamicTokens() {
    if (typeof document === 'undefined') return;

    let css = '';
    for (const [id, def] of this.registry.entries()) {
      if (def.tokens && typeof def.tokens === 'object') {
        const tokens = def.tokens;
        css += `:root[data-theme="${id}"], [data-theme="${id}"] {\n`;
        for (const [prop, val] of Object.entries(tokens)) {
          if (val !== undefined && val !== null && String(val).trim() !== '') {
            css += `  ${prop}: ${val};\n`;
          }
        }
        css += '}\n';

        // Индивидуальные стили компонентов для дочерних тем
        if (def.isChild) {
          if (tokens['--radius-md']) {
            css += `[data-theme="${id}"] .card, [data-theme="${id}"] .modal-content, [data-theme="${id}"] .ui-card { border-radius: ${tokens['--radius-md']} !important; }\n`;
          }
          if (tokens['--radius-sm']) {
            css += `[data-theme="${id}"] .btn, [data-theme="${id}"] .form-control, [data-theme="${id}"] .form-select, [data-theme="${id}"] .badge { border-radius: ${tokens['--radius-sm']} !important; }\n`;
          }
          if (tokens['--ui-font-size-base']) {
            css += `html[data-theme="${id}"] { font-size: ${tokens['--ui-font-size-base']} !important; }\n`;
          }
          if (tokens['--panel-header-font-size'] || tokens['--panel-header-color'] || tokens['--panel-header-bg']) {
            css += `[data-theme="${id}"] .panel-header, [data-theme="${id}"] h3.panel-header { font-size: ${tokens['--panel-header-font-size'] || '1.75rem'} !important; color: ${tokens['--panel-header-color'] || 'inherit'} !important; background-color: ${tokens['--panel-header-bg'] || 'inherit'} !important; }\n`;
          }
          if (tokens['--tab-header-title-size'] || tokens['--tab-header-title-color'] || tokens['--tab-header-subtitle-color']) {
            css += `[data-theme="${id}"] .tab-header-title { font-size: ${tokens['--tab-header-title-size'] || '1.35rem'} !important; color: ${tokens['--tab-header-title-color'] || 'inherit'} !important; }\n`;
            css += `[data-theme="${id}"] .tab-header-subtitle { color: ${tokens['--tab-header-subtitle-color'] || 'inherit'} !important; }\n`;
          }
        }
      }
    }

    if (!this._dynamicStyleEl) {
      this._dynamicStyleEl = document.getElementById('theme-engine-dynamic-styles');
      if (!this._dynamicStyleEl) {
        this._dynamicStyleEl = document.createElement('style');
        this._dynamicStyleEl.id = 'theme-engine-dynamic-styles';
        document.head.appendChild(this._dynamicStyleEl);
      }
    }
    this._dynamicStyleEl.textContent = css;
  }

  /**
   * Возвращает сохраненные пользовательские переопределения токенов из LocalStorage.
   * @returns {Object<string, string>|null} Объект с CSS-переменными или null
   */
  getCustomOverrides() {
    try {
      const data = localStorage.getItem(CUSTOM_OVERRIDES_STORAGE_KEY);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      console.warn('[ThemeEngine] Ошибка чтения кастомных токенов:', e);
      return null;
    }
  }

  /**
   * Применяет кастомные переопределения CSS-переменных к корневому документу.
   * @param {Object<string, string>} tokens - Словарь CSS переменных и значений
   * @param {boolean} [save=true] - Сохранять ли параметры в LocalStorage
   */
  applyCustomOverrides(tokens, save = true) {
    if (!tokens || typeof tokens !== 'object') return;
    if (save) {
      try {
        localStorage.setItem(CUSTOM_OVERRIDES_STORAGE_KEY, JSON.stringify(tokens));
      } catch (e) {
        console.warn('[ThemeEngine] Не удалось сохранить кастомные токены в LocalStorage:', e);
      }
    }
    this._applyCustomStyles(tokens);

    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('themecustomoverrideschanged', {
          detail: { tokens },
        })
      );
    }
  }

  /**
   * Сбрасывает сохраненные пользовательские переопределения оформления.
   */
  clearCustomOverrides() {
    try {
      localStorage.removeItem(CUSTOM_OVERRIDES_STORAGE_KEY);
    } catch {}
    if (this._customStyleEl) {
      this._customStyleEl.textContent = '';
    }
    this.applyTheme(this.getSavedMode());

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('themecustomoverridescleared'));
    }
  }

  /**
   * Автоматически применяет сохраненные переопределения при инициализации.
   * @private
   */
  _applyStoredOverrides() {
    const currentMode = this.getSavedMode();
    // Стандартные темы защищены от перезаписи — оверрайды к ним не применяются
    if (this.isBuiltinTheme(currentMode)) {
      if (this._customStyleEl) {
        this._customStyleEl.textContent = '';
      }
      return;
    }

    const overrides = this.getCustomOverrides();
    if (overrides && typeof overrides === 'object' && Object.keys(overrides).length > 0) {
      this._applyCustomStyles(overrides);
    } else if (this._customStyleEl) {
      this._customStyleEl.textContent = '';
    }
  }

  /**
   * Инжектирует динамический блок стилей с кастомными токенами оформления.
   * @private
   * @param {Object<string, string>} tokens
   */
  _applyCustomStyles(tokens) {
    if (typeof document === 'undefined') return;

    if (!this._customStyleEl) {
      this._customStyleEl = document.getElementById('theme-engine-custom-overrides');
      if (!this._customStyleEl) {
        this._customStyleEl = document.createElement('style');
        this._customStyleEl.id = 'theme-engine-custom-overrides';
        document.head.appendChild(this._customStyleEl);
      }
    }

    let css = ':root, html, body {\n';
    for (const [prop, val] of Object.entries(tokens)) {
      if (val !== undefined && val !== null && String(val).trim() !== '') {
        css += `  ${prop}: ${val} !important;\n`;
      }
    }
    css += '}\n';

    if (tokens['--bg-color']) {
      css += `body { background-color: ${tokens['--bg-color']} !important; color: ${tokens['--text-color'] || 'inherit'} !important; }\n`;
    }

    if (tokens['--radius-md']) {
      css += `
.card, .modal-content, .ui-card {
  border-radius: ${tokens['--radius-md']} !important;
}
`;
    }
    if (tokens['--radius-sm']) {
      css += `
.btn, .form-control, .form-select, .badge, .input-group-text {
  border-radius: ${tokens['--radius-sm']} !important;
}
`;
    }
    if (tokens['--ui-font-size-base']) {
      css += `
html {
  font-size: ${tokens['--ui-font-size-base']} !important;
}
`;
    }
    if (tokens['--panel-header-font-size'] || tokens['--panel-header-color'] || tokens['--panel-header-bg']) {
      css += `
.panel-header {
  font-size: ${tokens['--panel-header-font-size'] || '1.75rem'} !important;
  color: ${tokens['--panel-header-color'] || 'inherit'} !important;
  background-color: ${tokens['--panel-header-bg'] || 'inherit'} !important;
}
h3.panel-header, .panel-header h3, .panel-header .panel-title {
  font-size: ${tokens['--panel-header-font-size'] || '1.75rem'} !important;
  color: ${tokens['--panel-header-color'] || 'inherit'} !important;
}
`;
    }
    if (tokens['--tab-header-title-size'] || tokens['--tab-header-title-color'] || tokens['--tab-header-subtitle-color']) {
      css += `
.tab-header-title, .tab-header h3, .ui-tab-header h3, .tab-header h3.panel-header, .ui-tab-header h3.panel-header {
  font-size: ${tokens['--tab-header-title-size'] || '1.35rem'} !important;
  color: ${tokens['--tab-header-title-color'] || 'inherit'} !important;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}
.tab-header-subtitle, .tab-header small, .ui-tab-header small {
  color: ${tokens['--tab-header-subtitle-color'] || 'inherit'} !important;
}
`;
    }

    this._customStyleEl.textContent = css;
  }
}

/**
 * Синглтон экземпляр движка тем
 */
export const themeEngine = new ThemeEngine();

// Глобальный экспорт на window
if (typeof window !== 'undefined') {
  window.ThemeEngine = ThemeEngine;
  window.themeEngine = themeEngine;
}
