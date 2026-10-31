/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Presets Panel
 * =============================================================================
 * Description:
 *   Модуль эталонных встроенных пресетов оформления (тёмные, светлые, неоновые,
 *   контрастные) и их загрузки в элементы интерфейса редактора.
 *
 * File: panel_presets/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_theme_editor/panel_presets
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:05:00
 * =============================================================================
 */

import {
  setInputValue,
  setTextContent,
  setSelectValue,
  setCheckboxValue,
  setColorPair
} from '../common/ui_utils.js';

/**
 * Словарь эталонных пресетов оформления интерфейса.
 */
export const PRESETS = {
  'dark': {
    name: 'Стандартная тёмная',
    fontSize: 15,
    borderRadius: 8,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#0b0f17',
      bgSurface: '#151b23',
      bgElevated: '#1e2633',
      bgNav: '#151b23',
      textPrimary: '#f3f6fa',
      textMuted: '#a3b1c2',
      accent: '#58a6ff',
      accentHover: '#1f6feb',
      border: '#3b4758',
      borderStrong: '#596b82',
      success: '#3fb950',
      warning: '#d29922',
      danger: '#f85149',
      info: '#388bfd',
    }
  },
  'theme-dark-slate': {
    name: 'Dark Slate (Тёмный сланец)',
    fontSize: 16,
    borderRadius: 8,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#0f172a',
      bgSurface: '#1e293b',
      bgElevated: '#334155',
      bgNav: '#1e293b',
      textPrimary: '#f8fafc',
      textMuted: '#94a3b8',
      accent: '#38bdf8',
      accentHover: '#0ea5e9',
      border: '#334155',
      borderStrong: '#475569',
      success: '#34d399',
      warning: '#fbbf24',
      danger: '#f87171',
      info: '#38bdf8',
    }
  },
  'theme-light-enterprise': {
    name: 'Light Enterprise (Светлый корпоративный)',
    fontSize: 15,
    borderRadius: 6,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'inter',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#e2e8f0',
      bgSurface: '#eaedf2',
      bgElevated: '#dbe2ea',
      bgNav: '#e2e8f0',
      textPrimary: '#0f172a',
      textMuted: '#475569',
      accent: '#0284c7',
      accentHover: '#0369a1',
      border: '#cbd5e1',
      borderStrong: '#94a3b8',
      success: '#059669',
      warning: '#78350f',
      danger: '#dc2626',
      info: '#0284c7',
    }
  },
  'theme-cyberpunk': {
    name: 'Cyberpunk Neon (Киберпанк неон)',
    fontSize: 15,
    borderRadius: 4,
    density: 'compact',
    kpiHeight: 68,
    fontFamily: 'mono',
    shadowStyle: 'neon',
    glassmorphism: true,
    crtScanlines: true,
    colors: {
      bgBase: '#05050a',
      bgSurface: '#0a0a16',
      bgElevated: '#121124',
      bgNav: '#0a0a16',
      textPrimary: '#00f0ff',
      textMuted: '#a855f7',
      accent: '#00f0ff',
      accentHover: '#ff007f',
      border: '#f43f5e',
      borderStrong: '#00f0ff',
      success: '#00ff66',
      warning: '#ffe600',
      danger: '#ff0055',
      info: '#00f0ff',
    }
  },
  'theme-high-contrast': {
    name: 'High Contrast (Высокая контрастность)',
    fontSize: 16,
    borderRadius: 0,
    density: 'normal',
    kpiHeight: 76,
    fontFamily: 'system',
    shadowStyle: 'none',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#000000',
      bgSurface: '#000000',
      bgElevated: '#111111',
      bgNav: '#000000',
      textPrimary: '#ffffff',
      textMuted: '#ffff00',
      accent: '#00ffff',
      accentHover: '#ffff00',
      border: '#ffffff',
      borderStrong: '#ffff00',
      success: '#00ff00',
      warning: '#ffff00',
      danger: '#ff0000',
      info: '#00ffff',
    }
  },
  'light': {
    name: 'Windows System Light',
    fontSize: 15,
    borderRadius: 8,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#e2e8f0',
      bgSurface: '#eaedf2',
      bgElevated: '#dbe2ea',
      bgNav: '#e2e8f0',
      textPrimary: '#0f172a',
      textMuted: '#475569',
      accent: '#0284c7',
      accentHover: '#0369a1',
      border: '#cbd5e1',
      borderStrong: '#94a3b8',
      success: '#059669',
      warning: '#b43418',
      danger: '#b91c1c',
      info: '#0284c7',
    }
  },
  'nightview': {
    name: 'NightView (Тёплая бумага)',
    fontSize: 15,
    borderRadius: 8,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#ede6d9',
      bgSurface: '#f6f1e8',
      bgElevated: '#e2dac9',
      bgNav: '#f6f1e8',
      tableRowBg: '#f6f1e8',
      textPrimary: '#18181b',
      textMuted: '#3f3f46',
      accent: '#1d4ed8',
      accentHover: '#1e40af',
      border: '#cfc5b4',
      borderStrong: '#9ca3af',
      success: '#185223',
      warning: '#b43418',
      danger: '#9e2b17',
      info: '#184674',
    }
  },
  'brick': {
    name: 'Кирпичная (Терракота)',
    fontSize: 15,
    borderRadius: 8,
    density: 'normal',
    kpiHeight: 72,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#f7f3ee',
      bgSurface: '#fcfaf6',
      bgElevated: '#faefe7',
      bgNav: '#fcfaf6',
      textPrimary: '#2c221e',
      textMuted: '#7d6b63',
      accent: '#b84228',
      accentHover: '#d05034',
      border: '#dfcebf',
      borderStrong: '#bc9e8c',
      success: '#1e6b37',
      warning: '#8a520f',
      danger: '#9e2b17',
      info: '#1c5480',
    }
  },
  'terminal': {
    name: 'Терминал (Matrix / CRT)',
    fontSize: 14,
    borderRadius: 4,
    density: 'compact',
    kpiHeight: 64,
    fontFamily: 'mono',
    shadowStyle: 'neon',
    glassmorphism: false,
    crtScanlines: true,
    colors: {
      bgBase: '#060a06',
      bgSurface: '#0b120c',
      bgElevated: '#101c12',
      bgNav: '#0b120c',
      textPrimary: '#d8ffd8',
      textMuted: '#599863',
      accent: '#00ff66',
      accentHover: '#33ff88',
      border: '#1a4223',
      borderStrong: '#00ff66',
      success: '#00ff66',
      warning: '#ffb000',
      danger: '#ff3344',
      info: '#00ddff',
    }
  },
  'nordic-frost': {
    name: 'Nordic Frost (Скандинавский морозный)',
    fontSize: 15,
    borderRadius: 10,
    density: 'comfortable',
    kpiHeight: 76,
    fontFamily: 'inter',
    shadowStyle: 'soft',
    glassmorphism: true,
    crtScanlines: false,
    colors: {
      bgBase: '#0f172a',
      bgSurface: '#1e293b',
      bgElevated: '#334155',
      bgNav: '#1e293b',
      textPrimary: '#f1f5f9',
      textMuted: '#94a3b8',
      accent: '#38bdf8',
      accentHover: '#7dd3fc',
      border: '#475569',
      borderStrong: '#64748b',
      success: '#34d399',
      warning: '#fbbf24',
      danger: '#f87171',
      info: '#38bdf8',
    }
  },
  'solarized-dark': {
    name: 'Solarized Deep (Глубокий сине-зеленый)',
    fontSize: 15,
    borderRadius: 6,
    density: 'normal',
    kpiHeight: 70,
    fontFamily: 'system',
    shadowStyle: 'soft',
    glassmorphism: false,
    crtScanlines: false,
    colors: {
      bgBase: '#002b36',
      bgSurface: '#073642',
      bgElevated: '#094352',
      bgNav: '#073642',
      textPrimary: '#93a1a1',
      textMuted: '#657b83',
      accent: '#268bd2',
      accentHover: '#2aa198',
      border: '#0d5465',
      borderStrong: '#2aa198',
      success: '#859900',
      warning: '#b58900',
      danger: '#dc322f',
      info: '#268bd2',
    }
  }
};

/**
 * Возвращает пресет темы по ключу, с поддержкой дочерних тем и наследования от стандартных.
 * @param {string} presetKey - Ключ темы/пресета.
 * @returns {Object} Объект конфигурации пресета.
 */
export function getPreset(presetKey) {
  if (presetKey in PRESETS) {
    return PRESETS[presetKey];
  }

  // Поиск среди дочерних тем в ThemeEngine
  if (typeof window !== 'undefined' && window.themeEngine) {
    const child = window.themeEngine.getChildTheme(presetKey);
    if (child) {
      const parentPreset = PRESETS[child.parentId] || PRESETS['theme-dark-slate'];
      const savedSettings = child.settings || {};
      const savedColors = child.settings?.colors || {};

      return {
        ...parentPreset,
        ...savedSettings,
        name: child.name,
        parentId: child.parentId,
        isChild: true,
        colors: {
          ...parentPreset.colors,
          ...savedColors,
        },
      };
    }
  }

  return PRESETS['theme-dark-slate'];
}

/**
 * Обновляет индикаторы статуса (стандартная/дочерняя тема) и тулбар действий темы в UI.
 * @param {string} presetKey - Идентификатор текущей темы.
 */
export function updateThemeStatusUI(presetKey) {
  const isChild = typeof window !== 'undefined' && window.themeEngine ? window.themeEngine.isChildTheme(presetKey) : false;
  const childTheme = isChild ? window.themeEngine.getChildTheme(presetKey) : null;
  const parentTheme = isChild ? window.themeEngine.getTheme(childTheme?.parentId) : null;
  const parentName = parentTheme?.name || childTheme?.parentId || 'Стандартная';

  // Бейдж типа темы
  const typeBadge = document.getElementById('theme-type-badge');
  if (typeBadge) {
    if (isChild) {
      typeBadge.className = 'badge bg-primary-subtle text-primary border border-primary-subtle small px-2 py-0.5';
      typeBadge.innerHTML = `<i class="bi bi-diagram-3-fill me-1"></i>Дочерняя (от ${parentName})`;
    } else {
      typeBadge.className = 'badge bg-secondary-subtle text-secondary border border-secondary-subtle small px-2 py-0.5';
      typeBadge.innerHTML = '<i class="bi bi-lock-fill me-1"></i>Стандартная (только чтение)';
    }
  }

  // Информационный алерт наследования
  const inheritAlert = document.getElementById('theme-inheritance-alert');
  if (inheritAlert) {
    if (isChild) {
      inheritAlert.className = 'alert alert-info py-2 px-3 small d-flex align-items-center gap-2 mb-2';
      inheritAlert.innerHTML = `
        <i class="bi bi-diagram-3-fill fs-6 text-info"></i>
        <span>Дочерняя тема <strong>«${childTheme?.name || presetKey}»</strong> наследует базовые стили от темы <strong>«${parentName}»</strong>.</span>
      `;
    } else {
      inheritAlert.className = 'alert alert-secondary py-2 px-3 small d-flex align-items-center gap-2 mb-2';
      inheritAlert.innerHTML = `
        <i class="bi bi-shield-lock-fill fs-6 text-secondary"></i>
        <span>Стандартные темы системы защищены от перезаписи. Чтобы изменить оформление, создайте дочернюю тему на базе этой.</span>
      `;
    }
  }

  // Видимость кнопок управления дочерней темой
  const btnDeleteChild = document.getElementById('theme-btn-delete-child');
  const btnResetToParent = document.getElementById('theme-btn-reset-to-parent');
  const btnRenameChild = document.getElementById('theme-btn-rename-child');

  if (btnDeleteChild) {
    btnDeleteChild.style.display = isChild ? 'inline-flex' : 'none';
  }
  if (btnResetToParent) {
    btnResetToParent.style.display = isChild ? 'inline-flex' : 'none';
  }
  if (btnRenameChild) {
    btnRenameChild.style.display = isChild ? 'inline-flex' : 'none';
  }

  // Кнопка сохранения в главном тулбаре
  const btnSave = document.getElementById('theme-btn-save');
  if (btnSave) {
    if (isChild) {
      btnSave.className = 'btn btn-sm btn-primary d-flex align-items-center gap-2 shadow-sm';
      btnSave.innerHTML = '<i class="bi bi-check-circle-fill"></i><span>Сохранить тему</span>';
      btnSave.setAttribute('title', `Сохранить изменения в дочернюю тему «${childTheme?.name || presetKey}»`);
    } else {
      btnSave.className = 'btn btn-sm btn-outline-primary d-flex align-items-center gap-2 shadow-sm';
      btnSave.innerHTML = '<i class="bi bi-diagram-3"></i><span>Создать дочернюю</span>';
      btnSave.setAttribute('title', 'Стандартная тема защищена. Нажмите для создания дочерней темы на её основе');
    }
  }
}

/**
 * Динамически наполняет селект #theme-preset-select списками стандартных и дочерних тем.
 * @param {string} [selectedKey] - Выбранный ключ темы.
 */
export function populatePresetSelect(selectedKey) {
  const presetSelect = document.getElementById('theme-preset-select');
  if (!presetSelect) return;

  const currentVal = selectedKey || presetSelect.value || 'theme-dark-slate';
  const customThemes = typeof window !== 'undefined' && window.themeEngine ? window.themeEngine.getCustomThemes() : [];

  let html = '';

  // 1. Блок пользовательских дочерних тем (если есть)
  if (customThemes.length > 0) {
    html += '<optgroup label="✨ Мои дочерние темы">\n';
    for (const t of customThemes) {
      const isSelected = t.id === currentVal ? ' selected' : '';
      const parent = window.themeEngine.getTheme(t.parentId);
      const parentName = parent ? parent.name : t.parentId;
      html += `  <option value="${t.id}"${isSelected}>🎨 ${t.name} (на базе: ${parentName})</option>\n`;
    }
    html += '</optgroup>\n';
  }

  // 2. Блок стандартных тёмных тем
  html += '<optgroup label="🌙 Стандартные тёмные темы">\n';
  html += `  <option value="dark"${currentVal === 'dark' ? ' selected' : ''}>🌙 Стандартная тёмная</option>\n`;
  html += `  <option value="theme-dark-slate"${currentVal === 'theme-dark-slate' ? ' selected' : ''}>🌑 Dark Slate (Тёмный сланец)</option>\n`;
  html += `  <option value="theme-cyberpunk"${currentVal === 'theme-cyberpunk' ? ' selected' : ''}>⚡ Cyberpunk Neon (Киберпанк неон)</option>\n`;
  html += `  <option value="terminal"${currentVal === 'terminal' ? ' selected' : ''}>📟 Терминал (Matrix / CRT)</option>\n`;
  html += `  <option value="nordic-frost"${currentVal === 'nordic-frost' ? ' selected' : ''}>❄️ Nordic Frost (Скандинавский морозный)</option>\n`;
  html += `  <option value="solarized-dark"${currentVal === 'solarized-dark' ? ' selected' : ''}>🌲 Solarized Deep (Глубокий сине-зеленый)</option>\n`;
  html += `  <option value="theme-high-contrast"${currentVal === 'theme-high-contrast' ? ' selected' : ''}>👁️ High Contrast (Высокая контрастность)</option>\n`;
  html += '</optgroup>\n';

  // 3. Блок стандартных светлых тем
  html += '<optgroup label="☀️ Стандартные светлые темы">\n';
  html += `  <option value="light"${currentVal === 'light' ? ' selected' : ''}>🪟 Windows System Light</option>\n`;
  html += `  <option value="nightview"${currentVal === 'nightview' ? ' selected' : ''}>📖 NightView (Тёплая бумага)</option>\n`;
  html += `  <option value="brick"${currentVal === 'brick' ? ' selected' : ''}>🧱 Кирпичная (Терракота)</option>\n`;
  html += `  <option value="theme-light-enterprise"${currentVal === 'theme-light-enterprise' ? ' selected' : ''}>🏢 Light Enterprise (Светлый корпоративный)</option>\n`;
  html += '</optgroup>\n';

  presetSelect.innerHTML = html;
  if (currentVal) {
    presetSelect.value = currentVal;
  }
}

/**
 * Применяет выбранный пресет оформления к элементам формы редактора.
 * @param {string} presetKey - Ключ пресета.
 * @param {Function} [onApplied=null] - Колбэк после применения.
 */
export function loadPreset(presetKey, onApplied = null) {
  const preset = getPreset(presetKey);

  // Размеры и геометрия
  setInputValue('range-font-size', preset.fontSize || 16);
  setTextContent('val-font-size', `${preset.fontSize || 16}px`);

  const panelH3Size = preset.panelHeaderFontSize || 28;
  setInputValue('range-panel-header-font-size', panelH3Size);
  setTextContent('val-panel-header-font-size', `${panelH3Size}px`);

  const tabHeaderSize = preset.tabHeaderFontSize || 22;
  setInputValue('range-tab-header-font-size', tabHeaderSize);
  setTextContent('val-tab-header-font-size', `${tabHeaderSize}px`);

  setInputValue('range-border-radius', preset.borderRadius !== undefined ? preset.borderRadius : 8);
  setTextContent('val-border-radius', `${preset.borderRadius !== undefined ? preset.borderRadius : 8}px`);

  setInputValue('range-kpi-height', preset.kpiHeight || 72);
  setTextContent('val-kpi-height', `${preset.kpiHeight || 72}px`);

  setInputValue('range-modal-width', preset.modalWidth || 80);
  setTextContent('val-modal-width', `${preset.modalWidth || 80}vw`);

  setInputValue('range-modal-height', preset.modalHeight || 80);
  setTextContent('val-modal-height', `${preset.modalHeight || 80}vh`);

  const densityRadio = document.getElementById(`density-${preset.density || 'normal'}`);
  if (densityRadio) densityRadio.checked = true;

  setSelectValue('select-font-family', preset.fontFamily || 'system');
  setSelectValue('select-shadow-style', preset.shadowStyle || 'soft');

  setCheckboxValue('toggle-glassmorphism', preset.glassmorphism || false);
  setCheckboxValue('toggle-crt-scanlines', preset.crtScanlines || false);

  // Цвета
  if (preset.colors) {
    setColorPair('bg-base', preset.colors.bgBase);
    setColorPair('bg-surface', preset.colors.bgSurface);
    setColorPair('bg-elevated', preset.colors.bgElevated);
    setColorPair('bg-nav', preset.colors.bgNav);
    setColorPair('table-row-bg', preset.colors.tableRowBg || preset.colors.bgSurface);

    setColorPair('text-primary', preset.colors.textPrimary);
    setColorPair('text-muted', preset.colors.textMuted);
    setColorPair('accent', preset.colors.accent);
    setColorPair('accent-hover', preset.colors.accentHover);

    setColorPair('border', preset.colors.border);
    setColorPair('border-strong', preset.colors.borderStrong);

    setColorPair('status-success', preset.colors.success);
    setColorPair('status-warning', preset.colors.warning);
    setColorPair('status-danger', preset.colors.danger);
    setColorPair('status-info', preset.colors.info);

    setColorPair('panel-header-text', preset.colors.panelHeaderText || preset.colors.textPrimary || '#f9fafb');
    setColorPair('panel-header-bg', preset.colors.panelHeaderBg || preset.colors.bgElevated || '#1f2937');
    setColorPair('tab-header-text', preset.colors.tabHeaderText || preset.colors.textPrimary || '#f9fafb');
    setColorPair('tab-header-sub', preset.colors.tabHeaderSub || preset.colors.textMuted || '#9ca3af');
  }

  const presetSelect = document.getElementById('theme-preset-select');
  if (presetSelect && presetSelect.value !== presetKey) {
    presetSelect.value = presetKey;
  }

  // Обновление интерфейса статуса (стандартная тема или дочерняя)
  updateThemeStatusUI(presetKey);

  if (typeof onApplied === 'function') {
    onApplied();
  }
}

/**
 * Инициализирует элементы выбора пресетов.
 * @param {Function} onPresetChange - Колбэк обновления.
 */
export function initPresetsControls(onPresetChange) {
  const btnApplyPreset = document.getElementById('theme-btn-apply-preset');
  const presetSelect = document.getElementById('theme-preset-select');

  // Начальное наполнение списка пресетов
  populatePresetSelect(presetSelect?.value || 'theme-dark-slate');

  const applySelected = () => {
    const presetKey = presetSelect?.value;
    if (!presetKey) return;
    loadPreset(presetKey, () => {
      if (window.themeEngine) {
        window.themeEngine.previewTheme(presetKey);
      }
      if (typeof onPresetChange === 'function') {
        onPresetChange();
      }
    });
  };

  if (presetSelect) {
    presetSelect.addEventListener('change', applySelected);
  }

  if (btnApplyPreset) {
    btnApplyPreset.addEventListener('click', () => {
      const presetKey = presetSelect?.value;
      if (!presetKey) return;
      if (window.themeEngine) {
        window.themeEngine.applyTheme(presetKey);
      }
      loadPreset(presetKey, () => {
        if (typeof onPresetChange === 'function') {
          onPresetChange();
        }
      });
    });
  }

  // Слушатель изменения списка тем (создание, удаление, сброс дочерних тем)
  if (typeof window !== 'undefined') {
    window.addEventListener('themelistchanged', (e) => {
      const currentKey = presetSelect?.value;
      const targetKey = e.detail?.theme?.id || (e.detail?.action === 'delete' ? 'theme-dark-slate' : currentKey);
      populatePresetSelect(targetKey);
      loadPreset(targetKey, onPresetChange);
    });
  }
}

