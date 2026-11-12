/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Tokens Engine
 * =============================================================================
 * Description:
 *   Модуль генерации, сбора и маппинга токенов CSS-переменных темы оформления,
 *   сериализации состояния в JSON и генерации валидного CSS-кода.
 *
 * File: panel_tokens/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_theme_editor/panel_tokens
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:45:00
 * =============================================================================
 */

import {
  getColorValue,
  setColorPair,
  setInputValue,
  setTextContent,
  setSelectValue,
  setCheckboxValue
} from '../common/ui_utils.js';

/**
 * Определяет, является ли шестнадцатеричный цвет светлым.
 * @param {string} hex
 * @returns {boolean}
 */
function isColorLight(hex) {
  if (!hex || typeof hex !== 'string') return false;
  const clean = hex.replace('#', '').trim();
  if (clean.length < 6) return false;
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 >= 128;
}

/**
 * Собирает словарь CSS-переменных из текущих значений формы.
 * @returns {Object<string, string>} Словарь CSS-токенов.
 */
export function collectTokensFromUI() {
  const fontSize = document.getElementById('range-font-size')?.value || '16';
  const radius = parseInt(document.getElementById('range-border-radius')?.value || '8', 10);
  const kpiHeight = document.getElementById('range-kpi-height')?.value || '72';
  const panelHeaderFontSize = document.getElementById('range-panel-header-font-size')?.value || '28';
  const tabHeaderFontSize = document.getElementById('range-tab-header-font-size')?.value || '22';
  const modalWidth = document.getElementById('range-modal-width')?.value || '90';
  const modalHeight = document.getElementById('range-modal-height')?.value || '90';

  const density = document.querySelector('input[name="theme-density"]:checked')?.value || 'normal';
  const fontFamKey = document.getElementById('select-font-family')?.value || 'system';
  const shadowKey = document.getElementById('select-shadow-style')?.value || 'soft';

  const bgBase = getColorValue('bg-base', '#0b0f19');
  const bgSurface = getColorValue('bg-surface', '#111827');
  const bgElevated = getColorValue('bg-elevated', '#1f2937');
  const bgNav = getColorValue('bg-nav', '#111827');
  const tableRowBg = getColorValue('table-row-bg', bgSurface);
  const panelHeaderText = getColorValue('panel-header-text', '#f9fafb');
  const panelHeaderBg = getColorValue('panel-header-bg', bgElevated);
  const tabHeaderText = getColorValue('tab-header-text', '#f9fafb');
  const tabHeaderSub = getColorValue('tab-header-sub', '#9ca3af');

  const textPrimary = getColorValue('text-primary', '#f9fafb');
  const textMuted = getColorValue('text-muted', '#9ca3af');
  const accent = getColorValue('accent', '#38bdf8');
  const accentHover = getColorValue('accent-hover', '#0ea5e9');

  const border = getColorValue('border', '#374151');
  const borderStrong = getColorValue('border-strong', '#596b82');

  const success = getColorValue('status-success', '#10b981');
  const warning = getColorValue('status-warning', '#f59e0b');
  const danger = getColorValue('status-danger', '#ef4444');
  const info = getColorValue('status-info', '#38bdf8');

  // Расчет радиусов
  const radiusXs = `${Math.max(0, radius - 4)}px`;
  const radiusSm = `${Math.max(0, radius - 2)}px`;
  const radiusMd = `${radius}px`;
  const radiusLg = `${radius + 4}px`;

  // Расчет отступов плотности
  let kpiPadding = '0.65rem 0.9rem';
  let subnavPadding = '0.35rem 0.75rem';
  if (density === 'compact') {
    kpiPadding = '0.4rem 0.6rem';
    subnavPadding = '0.2rem 0.5rem';
  } else if (density === 'comfortable') {
    kpiPadding = '0.9rem 1.25rem';
    subnavPadding = '0.5rem 1rem';
  }

  // Расчет шрифтов
  let fontFamilyStr = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
  if (fontFamKey === 'mono') {
    fontFamilyStr = '"Consolas", "Cascadia Code", "Courier New", ui-monospace, monospace';
  } else if (fontFamKey === 'inter') {
    fontFamilyStr = '"Inter", system-ui, -apple-system, sans-serif';
  } else if (fontFamKey === 'georgia') {
    fontFamilyStr = '"Georgia", "Cambria", serif';
  }

  // Расчет теней
  let shadowSm = '0 1px 2px 0 rgba(0, 0, 0, 0.3)';
  let shadowMd = '0 4px 6px -1px rgba(0, 0, 0, 0.4)';
  if (shadowKey === 'none') {
    shadowSm = 'none';
    shadowMd = 'none';
  } else if (shadowKey === 'deep') {
    shadowSm = '0 2px 8px rgba(0, 0, 0, 0.6)';
    shadowMd = '0 8px 24px rgba(0, 0, 0, 0.75)';
  } else if (shadowKey === 'neon') {
    shadowSm = `0 0 8px ${accent}4d`;
    shadowMd = `0 0 16px ${accent}66`;
  }

  const isLight = isColorLight(bgBase);
  const badgeAlphaBg = isLight ? '1f' : '26';
  const badgeAlphaBorder = isLight ? '40' : '40';
  const badgeNeutralBg = isLight ? '#e2e8f0' : '#1f2937';
  const badgeNeutralBorder = isLight ? '#cbd5e1' : '#374151';

  return {
    '--ui-font-size-base': `${fontSize}px`,
    '--font-sans': fontFamilyStr,

    '--radius-xs': radiusXs,
    '--radius-sm': radiusSm,
    '--radius-md': radiusMd,
    '--radius-lg': radiusLg,

    '--kpi-padding': kpiPadding,
    '--kpi-min-height': `${kpiHeight}px`,
    '--modal-width': `${modalWidth}vw`,
    '--modal-height': `${modalHeight}vh`,
    '--subnav-btn-padding': subnavPadding,

    '--bg-color': bgBase,
    '--ui-bg-base': bgBase,

    '--surface-1': bgSurface,
    '--card-bg': bgSurface,
    '--ui-bg-surface': bgSurface,
    '--panel-bg': bgSurface,
    '--kpi-bg': bgSurface,
    '--modal-bg': bgSurface,

    '--surface-2': bgElevated,
    '--ui-bg-surface-elevated': bgElevated,
    '--panel-header-bg': panelHeaderBg,
    '--panel-header-color': panelHeaderText,
    '--panel-header-font-size': `${panelHeaderFontSize}px`,

    '--tab-header-title-size': `${tabHeaderFontSize}px`,
    '--tab-header-title-color': tabHeaderText,
    '--tab-header-subtitle-color': tabHeaderSub,

    '--nav-bg': bgNav,

    '--text-color': textPrimary,
    '--card-text': textPrimary,
    '--modal-text': textPrimary,
    '--ui-text-primary': textPrimary,

    '--text-muted': textMuted,
    '--ui-text-muted': textMuted,
    '--ui-text-secondary': textMuted,

    '--nav-active': accent,
    '--ui-accent': accent,
    '--kpi-accent': accent,

    '--ui-accent-hover': accentHover,

    '--border-color': border,
    '--ui-border-color': border,
    '--border-subtle': `${border}66`,
    '--divider-color': border,
    '--modal-border': border,

    '--border-strong': borderStrong,

    '--ui-success': success,
    '--status-success-text': success,
    '--badge-success-text': success,
    '--badge-success-bg': `${success}${badgeAlphaBg}`,
    '--badge-success-border': `${success}${badgeAlphaBorder}`,
    '--status-success-bg': `${success}${badgeAlphaBg}`,
    '--status-success-border': `${success}${badgeAlphaBorder}`,

    '--ui-warning': warning,
    '--status-warning-text': warning,
    '--badge-warning-text': warning,
    '--badge-warning-bg': `${warning}${badgeAlphaBg}`,
    '--badge-warning-border': `${warning}${badgeAlphaBorder}`,
    '--status-warning-bg': `${warning}${badgeAlphaBg}`,
    '--status-warning-border': `${warning}${badgeAlphaBorder}`,

    '--ui-danger': danger,
    '--status-danger-text': danger,
    '--badge-danger-text': danger,
    '--badge-danger-bg': `${danger}${badgeAlphaBg}`,
    '--badge-danger-border': `${danger}${badgeAlphaBorder}`,
    '--status-danger-bg': `${danger}${badgeAlphaBg}`,
    '--status-danger-border': `${danger}${badgeAlphaBorder}`,

    '--ui-info': info,
    '--status-info-text': info,
    '--badge-info-text': info,
    '--badge-info-bg': `${info}${badgeAlphaBg}`,
    '--badge-info-border': `${info}${badgeAlphaBorder}`,
    '--status-info-bg': `${info}${badgeAlphaBg}`,
    '--status-info-border': `${info}${badgeAlphaBorder}`,

    '--badge-neutral-bg': badgeNeutralBg,
    '--badge-neutral-text': textMuted,
    '--badge-neutral-border': badgeNeutralBorder,

    '--bs-body-bg': bgBase,
    '--bs-body-color': textPrimary,
    '--bs-card-bg': bgSurface,
    '--bs-card-color': textPrimary,
    '--bs-modal-bg': bgSurface,
    '--bs-modal-color': textPrimary,
    '--bs-tertiary-bg': bgElevated,
    '--bs-secondary-bg': bgElevated,
    '--bs-list-group-bg': bgSurface,
    '--bs-dropdown-bg': bgSurface,
    '--bs-border-color': border,

    '--card-border': border,
    '--ui-border-color-subtle': `${border}66`,

    '--table-bg': tableRowBg,
    '--table-row-bg': tableRowBg,
    '--table-header-bg': bgElevated,
    '--table-color': textPrimary,
    '--table-border-color': border,
    '--kpi-border': border,

    'color-scheme': isLight ? 'light' : 'dark',

    '--ui-shadow-sm': shadowSm,
    '--ui-shadow-md': shadowMd,
  };
}

/**
 * Собирает полный объект состояния конфигурации темы для экспорта в JSON.
 * @returns {Object} Объект темы.
 */
export function collectFullStateFromUI() {
  return {
    version: '20261017_v1',
    name: 'Пользовательская тема',
    created: new Date().toISOString(),
    fontSize: parseInt(document.getElementById('range-font-size')?.value || '16', 10),
    panelHeaderFontSize: parseInt(document.getElementById('range-panel-header-font-size')?.value || '28', 10),
    tabHeaderFontSize: parseInt(document.getElementById('range-tab-header-font-size')?.value || '22', 10),
    borderRadius: parseInt(document.getElementById('range-border-radius')?.value || '8', 10),
    kpiHeight: parseInt(document.getElementById('range-kpi-height')?.value || '72', 10),
    modalWidth: parseInt(document.getElementById('range-modal-width')?.value || '90', 10),
    modalHeight: parseInt(document.getElementById('range-modal-height')?.value || '90', 10),
    density: document.querySelector('input[name="theme-density"]:checked')?.value || 'normal',
    fontFamily: document.getElementById('select-font-family')?.value || 'system',
    shadowStyle: document.getElementById('select-shadow-style')?.value || 'soft',
    glassmorphism: !!document.getElementById('toggle-glassmorphism')?.checked,
    crtScanlines: !!document.getElementById('toggle-crt-scanlines')?.checked,
    colors: {
      bgBase: getColorValue('bg-base'),
      bgSurface: getColorValue('bg-surface'),
      bgElevated: getColorValue('bg-elevated'),
      bgNav: getColorValue('bg-nav'),
      tableRowBg: getColorValue('table-row-bg', getColorValue('bg-surface')),
      textPrimary: getColorValue('text-primary'),
      textMuted: getColorValue('text-muted'),
      accent: getColorValue('accent'),
      accentHover: getColorValue('accent-hover'),
      border: getColorValue('border'),
      borderStrong: getColorValue('border-strong'),
      success: getColorValue('status-success'),
      warning: getColorValue('status-warning'),
      danger: getColorValue('status-danger'),
      info: getColorValue('status-info'),
      panelHeaderText: getColorValue('panel-header-text'),
      panelHeaderBg: getColorValue('panel-header-bg'),
      tabHeaderText: getColorValue('tab-header-text'),
      tabHeaderSub: getColorValue('tab-header-sub'),
    }
  };
}

/**
 * Применяет импортированное состояние к элементам формы.
 * @param {Object} state - Импортированное состояние темы.
 */
export function applyStateToUI(state) {
  if (!state || typeof state !== 'object') return;

  if (state.fontSize) {
    setInputValue('range-font-size', state.fontSize);
    setTextContent('val-font-size', `${state.fontSize}px`);
  }
  if (state.panelHeaderFontSize) {
    setInputValue('range-panel-header-font-size', state.panelHeaderFontSize);
    setTextContent('val-panel-header-font-size', `${state.panelHeaderFontSize}px`);
  }
  if (state.tabHeaderFontSize) {
    setInputValue('range-tab-header-font-size', state.tabHeaderFontSize);
    setTextContent('val-tab-header-font-size', `${state.tabHeaderFontSize}px`);
  }
  if (state.borderRadius !== undefined) {
    setInputValue('range-border-radius', state.borderRadius);
    setTextContent('val-border-radius', `${state.borderRadius}px`);
  }
  if (state.kpiHeight) {
    setInputValue('range-kpi-height', state.kpiHeight);
    setTextContent('val-kpi-height', `${state.kpiHeight}px`);
  }
  if (state.modalWidth) {
    setInputValue('range-modal-width', state.modalWidth);
    setTextContent('val-modal-width', `${state.modalWidth}vw`);
  }
  if (state.modalHeight) {
    setInputValue('range-modal-height', state.modalHeight);
    setTextContent('val-modal-height', `${state.modalHeight}vh`);
  }
  if (state.density) {
    const radio = document.getElementById(`density-${state.density}`);
    if (radio) radio.checked = true;
  }
  if (state.fontFamily) setSelectValue('select-font-family', state.fontFamily);
  if (state.shadowStyle) setSelectValue('select-shadow-style', state.shadowStyle);

  setCheckboxValue('toggle-glassmorphism', state.glassmorphism);
  setCheckboxValue('toggle-crt-scanlines', state.crtScanlines);

  if (state.colors && typeof state.colors === 'object') {
    const c = state.colors;
    if (c.bgBase) setColorPair('bg-base', c.bgBase);
    if (c.bgSurface) setColorPair('bg-surface', c.bgSurface);
    if (c.bgElevated) setColorPair('bg-elevated', c.bgElevated);
    if (c.bgNav) setColorPair('bg-nav', c.bgNav);
    if (c.tableRowBg) setColorPair('table-row-bg', c.tableRowBg);

    if (c.textPrimary) setColorPair('text-primary', c.textPrimary);
    if (c.textMuted) setColorPair('text-muted', c.textMuted);
    if (c.accent) setColorPair('accent', c.accent);
    if (c.accentHover) setColorPair('accent-hover', c.accentHover);

    if (c.border) setColorPair('border', c.border);
    if (c.borderStrong) setColorPair('border-strong', c.borderStrong);

    if (c.success) setColorPair('status-success', c.success);
    if (c.warning) setColorPair('status-warning', c.warning);
    if (c.danger) setColorPair('status-danger', c.danger);
    if (c.info) setColorPair('status-info', c.info);
    if (c.panelHeaderText) setColorPair('panel-header-text', c.panelHeaderText);
    if (c.panelHeaderBg) setColorPair('panel-header-bg', c.panelHeaderBg);
    if (c.tabHeaderText) setColorPair('tab-header-text', c.tabHeaderText);
    if (c.tabHeaderSub) setColorPair('tab-header-sub', c.tabHeaderSub);
  }
}

/**
 * Восстанавливает поля формы из сохраненных переопределений ThemeEngine.
 * @param {Object<string, string>} tokens - Карта токенов.
 */
export function mapTokensToUI(tokens) {
  if (tokens['--ui-font-size-base']) {
    const size = parseInt(tokens['--ui-font-size-base'], 10);
    if (!isNaN(size)) {
      setInputValue('range-font-size', size);
      setTextContent('val-font-size', `${size}px`);
    }
  }

  if (tokens['--panel-header-font-size']) {
    const h3Size = parseInt(tokens['--panel-header-font-size'], 10);
    if (!isNaN(h3Size)) {
      setInputValue('range-panel-header-font-size', h3Size);
      setTextContent('val-panel-header-font-size', `${h3Size}px`);
    }
  }

  if (tokens['--tab-header-title-size']) {
    const tabSize = parseInt(tokens['--tab-header-title-size'], 10);
    if (!isNaN(tabSize)) {
      setInputValue('range-tab-header-font-size', tabSize);
      setTextContent('val-tab-header-font-size', `${tabSize}px`);
    }
  }

  if (tokens['--radius-md']) {
    const rad = parseInt(tokens['--radius-md'], 10);
    if (!isNaN(rad)) {
      setInputValue('range-border-radius', rad);
      setTextContent('val-border-radius', `${rad}px`);
    }
  }

  if (tokens['--kpi-min-height']) {
    const h = parseInt(tokens['--kpi-min-height'], 10);
    if (!isNaN(h)) {
      setInputValue('range-kpi-height', h);
      setTextContent('val-kpi-height', `${h}px`);
    }
  }

  if (tokens['--modal-width']) {
    const w = parseInt(tokens['--modal-width'], 10);
    if (!isNaN(w)) {
      setInputValue('range-modal-width', w);
      setTextContent('val-modal-width', `${w}vw`);
    }
  }

  if (tokens['--modal-height']) {
    const mh = parseInt(tokens['--modal-height'], 10);
    if (!isNaN(mh)) {
      setInputValue('range-modal-height', mh);
      setTextContent('val-modal-height', `${mh}vh`);
    }
  }

  if (tokens['--ui-bg-base']) setColorPair('bg-base', tokens['--ui-bg-base']);
  if (tokens['--surface-1']) setColorPair('bg-surface', tokens['--surface-1']);
  if (tokens['--surface-2']) setColorPair('bg-elevated', tokens['--surface-2']);
  if (tokens['--nav-bg']) setColorPair('bg-nav', tokens['--nav-bg']);
  if (tokens['--table-row-bg'] || tokens['--table-bg']) setColorPair('table-row-bg', tokens['--table-row-bg'] || tokens['--table-bg']);

  if (tokens['--text-color']) setColorPair('text-primary', tokens['--text-color']);
  if (tokens['--text-muted']) setColorPair('text-muted', tokens['--text-muted']);
  if (tokens['--ui-accent']) setColorPair('accent', tokens['--ui-accent']);
  if (tokens['--ui-accent-hover']) setColorPair('accent-hover', tokens['--ui-accent-hover']);

  if (tokens['--border-color']) setColorPair('border', tokens['--border-color']);
  if (tokens['--border-strong']) setColorPair('border-strong', tokens['--border-strong']);

  if (tokens['--ui-success']) setColorPair('status-success', tokens['--ui-success']);
  if (tokens['--ui-warning']) setColorPair('status-warning', tokens['--ui-warning']);
  if (tokens['--ui-danger']) setColorPair('status-danger', tokens['--ui-danger']);
  if (tokens['--status-info-text']) setColorPair('status-info', tokens['--status-info-text']);

  if (tokens['--panel-header-color']) setColorPair('panel-header-text', tokens['--panel-header-color']);
  if (tokens['--panel-header-bg']) setColorPair('panel-header-bg', tokens['--panel-header-bg']);
  if (tokens['--tab-header-title-color']) setColorPair('tab-header-text', tokens['--tab-header-title-color']);
  if (tokens['--tab-header-subtitle-color']) setColorPair('tab-header-sub', tokens['--tab-header-subtitle-color']);
}

/**
 * Генерирует готовый CSS-код для экспорта и вставки в стили.
 * @returns {string} CSS-код.
 */
export function generateCssString() {
  const tokens = collectTokensFromUI();
  let css = '/* =============================================================================\n';
  css += ' * Custom Theme - AI Windows Admin WebGUI\n';
  css += ` * Generated: ${new Date().toLocaleString('ru-RU')}\n`;
  css += ' * ============================================================================= */\n\n';
  css += ':root, html, body {\n';

  for (const [prop, val] of Object.entries(tokens)) {
    css += `  ${prop}: ${val};\n`;
  }

  css += '}\n\n';
  css += '/* Компоненты UI Kit */\n';
  css += `.card, .modal-content, .ui-card {\n  border-radius: ${tokens['--radius-md']} !important;\n}\n\n`;
  css += `.btn, .form-control, .form-select, .badge {\n  border-radius: ${tokens['--radius-sm']} !important;\n}\n\n`;
  css += '/* Заголовки панелей (panel-header, размер H3) */\n';
  css += `.panel-header {\n  font-size: ${tokens['--panel-header-font-size']} !important;\n  color: ${tokens['--panel-header-color']} !important;\n  background-color: ${tokens['--panel-header-bg']} !important;\n}\n\n`;
  css += `.panel-title, .panel-header .panel-title, h3.panel-header, .panel-header h3 {\n  font-size: ${tokens['--panel-header-font-size']} !important;\n  color: ${tokens['--panel-header-color']} !important;\n}\n\n`;
  css += '/* Заголовки страниц и вкладок (tab-header) */\n';
  css += `.tab-header-title, .tab-header h3, .ui-tab-header h3 {\n  font-size: ${tokens['--tab-header-title-size']} !important;\n  color: ${tokens['--tab-header-title-color']} !important;\n  background: transparent !important;\n  border: none !important;\n  padding: 0 !important;\n}\n`;
  css += `.tab-header-subtitle, .tab-header small, .ui-tab-header small {\n  color: ${tokens['--tab-header-subtitle-color']} !important;\n}\n`;

  return css;
}
