/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Preview Panel
 * =============================================================================
 * Description:
 *   Модуль живого предпросмотра (Live Preview): применение стилей к песочнице,
 *   скругления, эффекты Glassmorphism и CRT Scanlines, полноэкранный режим.
 *
 * File: panel_preview/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_theme_editor/panel_preview
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:45:00
 * =============================================================================
 */

import { collectTokensFromUI } from '../panel_tokens/panel.js';

/**
 * Обновляет стили и токены в песочнице предпросмотра (Live Preview).
 */
export function updateLivePreview() {
  const sandbox = document.getElementById('theme-preview-sandbox');
  if (!sandbox) return;

  const tokens = collectTokensFromUI();

  // Применяем токены к контейнеру песочницы
  for (const [prop, val] of Object.entries(tokens)) {
    sandbox.style.setProperty(prop, val);
  }

  // Применение скругления к дочерним карточкам и кнопкам стенда
  const radiusMd = tokens['--radius-md'];
  const radiusSm = tokens['--radius-sm'];
  sandbox.querySelectorAll('.card, .preview-kpi-card, .table-responsive').forEach((el) => {
    el.style.borderRadius = radiusMd;
  });
  sandbox.querySelectorAll('.btn, .form-control, .badge').forEach((el) => {
    el.style.borderRadius = radiusSm;
  });

  // Заголовки панелей .panel-header (размер H3)
  const panelH3Size = tokens['--panel-header-font-size'];
  const panelH3Color = tokens['--panel-header-color'];
  const panelH3Bg = tokens['--panel-header-bg'];
  sandbox.querySelectorAll('.preview-panel-header-card .panel-header, .preview-panel-header-card .panel-title').forEach((el) => {
    if (panelH3Size) el.style.fontSize = panelH3Size;
    if (panelH3Color) el.style.color = panelH3Color;
  });
  sandbox.querySelectorAll('.preview-panel-header-card div.panel-header').forEach((el) => {
    if (panelH3Bg) el.style.backgroundColor = panelH3Bg;
  });

  // Заголовки страниц и вкладок .tab-header
  const tabTitleSize = tokens['--tab-header-title-size'];
  const tabTitleColor = tokens['--tab-header-title-color'];
  const tabSubColor = tokens['--tab-header-subtitle-color'];
  sandbox.querySelectorAll('.preview-tab-header-box .tab-header-title, .preview-tab-header-box h3').forEach((el) => {
    if (tabTitleSize) el.style.fontSize = tabTitleSize;
    if (tabTitleColor) el.style.color = tabTitleColor;
  });
  sandbox.querySelectorAll('.preview-tab-header-box .tab-header-subtitle').forEach((el) => {
    if (tabSubColor) el.style.color = tabSubColor;
  });

  // Эффект Glassmorphism
  const isGlass = document.getElementById('toggle-glassmorphism')?.checked;
  sandbox.querySelectorAll('.preview-kpi-card, .card').forEach((el) => {
    if (isGlass) {
      el.style.backdropFilter = 'blur(10px)';
      el.style.backgroundColor = `${tokens['--surface-1']}cc`;
    } else {
      el.style.backdropFilter = '';
      el.style.backgroundColor = tokens['--surface-1'];
    }
  });

  // Применение фона строк таблицы
  const tableRowBg = tokens['--table-row-bg'] || tokens['--surface-1'];
  const tableHeaderBg = tokens['--table-header-bg'] || tokens['--surface-2'];
  sandbox.querySelectorAll('.table, .interactive-table-row, .interactive-table-row td').forEach((el) => {
    if (tableRowBg) el.style.backgroundColor = tableRowBg;
  });
  sandbox.querySelectorAll('.table thead th').forEach((el) => {
    if (tableHeaderBg) el.style.backgroundColor = tableHeaderBg;
  });

  // Эффект CRT Scanlines
  const isCrt = document.getElementById('toggle-crt-scanlines')?.checked;
  if (isCrt) {
    sandbox.classList.add('crt-scanline-effect');
  } else {
    sandbox.classList.remove('crt-scanline-effect');
  }

  // Динамическое применение к глобальному ThemeEngine для немедленного отклика во всем окне
  const presetSelect = document.getElementById('theme-preset-select');
  if (presetSelect?.value && window.themeEngine) {
    window.themeEngine.previewTheme(presetSelect.value);
  }
  if (window.themeEngine) {
    window.themeEngine.applyCustomOverrides(tokens, false);
  }
}

/**
 * Инициализирует элементы управления песочницей предпросмотра.
 */
export function initPreviewControls() {
  const btnToggleFull = document.getElementById('preview-btn-toggle-fullscreen');
  if (btnToggleFull) {
    btnToggleFull.addEventListener('click', () => {
      const sandbox = document.getElementById('theme-preview-sandbox');
      if (sandbox) {
        sandbox.classList.toggle('preview-expanded');
        btnToggleFull.innerHTML = sandbox.classList.contains('preview-expanded')
          ? '<i class="bi bi-fullscreen-exit me-1"></i>Свернуть превью'
          : '<i class="bi bi-arrows-fullscreen me-1"></i>Развернуть превью';
      }
    });
  }
}
