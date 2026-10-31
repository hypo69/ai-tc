/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки Редактора тем оформления. Координирует
 *   двустороннее связывание формы, пресеты, живой предпросмотр (Live Preview)
 *   и действия тулбара (сохранение, экспорт/импорт, CSS).
 *
 * Usage Examples:
 *   Ленивая загрузка вкладки через tab-core.js:
 *     await loadTab('theme-editor', '/html/tab_theme_editor/index.html?v=20261017_v1', '/html/tab_theme_editor/main.js?v=20261017_v1');
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_theme_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:05:00
 * =============================================================================
 */

import { COLOR_PAIRS } from './common/ui_utils.js';
import { initPresetsControls } from './panel_presets/panel.js';
import { updateLivePreview, initPreviewControls } from './panel_preview/panel.js';
import { bindActions, loadCurrentThemeState } from './panel_actions/panel.js';

let isInitialized = false;

/**
 * Подключение слушателей событий ко всем элементам управления формы.
 */
function bindFormControls() {
  // Связывание колорпикеров и текстовых полей (двустороннее)
  COLOR_PAIRS.forEach(({ picker, text }) => {
    const pickerEl = document.getElementById(picker);
    const textEl = document.getElementById(text);

    if (pickerEl && textEl) {
      pickerEl.addEventListener('input', () => {
        textEl.value = pickerEl.value;
        updateLivePreview();
      });

      textEl.addEventListener('input', () => {
        const val = textEl.value.trim();
        if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
          pickerEl.value = val;
        }
        updateLivePreview();
      });
    }
  });

  // Слайдер масштаба шрифта
  const rangeFontSize = document.getElementById('range-font-size');
  const valFontSize = document.getElementById('val-font-size');
  if (rangeFontSize && valFontSize) {
    rangeFontSize.addEventListener('input', () => {
      valFontSize.textContent = `${rangeFontSize.value}px`;
      updateLivePreview();
    });
  }

  // Слайдер размера H3 заголовка панели (.panel-header)
  const rangePanelHeader = document.getElementById('range-panel-header-font-size');
  const valPanelHeader = document.getElementById('val-panel-header-font-size');
  if (rangePanelHeader && valPanelHeader) {
    rangePanelHeader.addEventListener('input', () => {
      valPanelHeader.textContent = `${rangePanelHeader.value}px`;
      updateLivePreview();
    });
  }

  // Слайдер размера заголовка вкладки (.tab-header)
  const rangeTabHeader = document.getElementById('range-tab-header-font-size');
  const valTabHeader = document.getElementById('val-tab-header-font-size');
  if (rangeTabHeader && valTabHeader) {
    rangeTabHeader.addEventListener('input', () => {
      valTabHeader.textContent = `${rangeTabHeader.value}px`;
      updateLivePreview();
    });
  }

  // Слайдер скругления углов
  const rangeRadius = document.getElementById('range-border-radius');
  const valRadius = document.getElementById('val-border-radius');
  if (rangeRadius && valRadius) {
    rangeRadius.addEventListener('input', () => {
      valRadius.textContent = `${rangeRadius.value}px`;
      updateLivePreview();
    });
  }

  // Слайдер высоты KPI
  const rangeKpiHeight = document.getElementById('range-kpi-height');
  const valKpiHeight = document.getElementById('val-kpi-height');
  if (rangeKpiHeight && valKpiHeight) {
    rangeKpiHeight.addEventListener('input', () => {
      valKpiHeight.textContent = `${rangeKpiHeight.value}px`;
      updateLivePreview();
    });
  }

  // Слайдер ширины модальных окон
  const rangeModalWidth = document.getElementById('range-modal-width');
  const valModalWidth = document.getElementById('val-modal-width');
  if (rangeModalWidth && valModalWidth) {
    rangeModalWidth.addEventListener('input', () => {
      valModalWidth.textContent = `${rangeModalWidth.value}vw`;
      updateLivePreview();
    });
  }

  // Слайдер высоты модальных окон
  const rangeModalHeight = document.getElementById('range-modal-height');
  const valModalHeight = document.getElementById('val-modal-height');
  if (rangeModalHeight && valModalHeight) {
    rangeModalHeight.addEventListener('input', () => {
      valModalHeight.textContent = `${rangeModalHeight.value}vh`;
      updateLivePreview();
    });
  }

  // Радиокнопки плотности интерфейса
  document.querySelectorAll('input[name="theme-density"]').forEach((radio) => {
    radio.addEventListener('change', () => updateLivePreview());
  });

  // Селекты шрифта и теней
  const fontSel = document.getElementById('select-font-family');
  if (fontSel) fontSel.addEventListener('change', () => updateLivePreview());

  const shadowSel = document.getElementById('select-shadow-style');
  if (shadowSel) shadowSel.addEventListener('change', () => updateLivePreview());

  // Переключатели эффектов
  const glassSwitch = document.getElementById('toggle-glassmorphism');
  if (glassSwitch) glassSwitch.addEventListener('change', () => updateLivePreview());

  const crtSwitch = document.getElementById('toggle-crt-scanlines');
  if (crtSwitch) crtSwitch.addEventListener('change', () => updateLivePreview());
}

/**
 * Инициализирует вкладку Редактора тем оформления.
 */
export async function initThemeEditorTab() {
  console.log('[ThemeEditorTab] Инициализация вкладки...');

  if (!isInitialized) {
    bindFormControls();
    initPresetsControls(updateLivePreview);
    initPreviewControls();
    bindActions(updateLivePreview);
    isInitialized = true;
  }

  // При переключении сразу загружаем и отображаем тему из theme-preset-select
  loadCurrentThemeState(updateLivePreview);
}

/**
 * Активация вкладки при переходе в раздел.
 */
export function activateThemeEditorTab() {
  console.log('[ThemeEditorTab] Вкладка активирована, включение темы выбранного пресета...');
  loadCurrentThemeState(updateLivePreview);
}

/**
 * Деактивация вкладки при переходе в другой раздел.
 * Восстанавливает выбранную пользователем тему без сохранения изменений предпросмотра.
 */
export function deactivateThemeEditorTab() {
  console.log('[ThemeEditorTab] Вкладка деактивирована, восстановление темы пользователя...');
  if (window.themeEngine) {
    window.themeEngine.restoreUserTheme();
  }
}

// Регистрация глобальных слушателей событий жизненного цикла вкладок
if (typeof document !== 'undefined') {
  document.addEventListener('tab:activated', (e) => {
    if (e.detail?.tabId === 'tab-theme-editor') {
      loadCurrentThemeState(updateLivePreview);
    }
  });

  document.addEventListener('tab:deactivated', (e) => {
    if (e.detail?.tabId === 'tab-theme-editor') {
      deactivateThemeEditorTab();
    }
  });
}

// Экспорт для оркестратора хоста и глобальной доступности
if (typeof window !== 'undefined') {
  window.initThemeEditorTab = initThemeEditorTab;
  window.activateThemeEditorTab = activateThemeEditorTab;
  window.deactivateThemeEditorTab = deactivateThemeEditorTab;
  window.applySelectedPresetPreview = () => loadCurrentThemeState(updateLivePreview);
}

