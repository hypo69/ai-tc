/**
 * =============================================================================
 * Process Name: Windows App Internals - WikiLLM Settings & Editor Panel
 * =============================================================================
 * Description:
 *   Модуль управления конфигурацией модели WikiLLM, порогом уверенности,
 *   температурой генерации, размером контекста и встроенным редактором базы
 *   знаний WikiLLM Knowledge Editor.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_wikillm_settings
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:05:00
 * =============================================================================
 */

import { loadScript, notifyUser } from '../common/ui_utils.js?v=20261031_v2';

/**
 * Загрузка сохраненных настроек WikiLLM с сервера.
 * @returns {Promise<void>}
 */
export async function loadWikiLLMSettings() {
  try {
    const res = await fetch('/api/v1/wikillm/settings');
    if (!res.ok) return;
    const data = await res.json();
    if (document.getElementById('wikillm-cfg-model')) {
      document.getElementById('wikillm-cfg-model').value = data.model_name || 'gemini-3.1-flash-lite';
    }
    if (document.getElementById('wikillm-cfg-threshold')) {
      document.getElementById('wikillm-cfg-threshold').value = data.confidence_threshold ?? 0.85;
    }
    if (document.getElementById('wikillm-cfg-db-path')) {
      document.getElementById('wikillm-cfg-db-path').value = data.db_path || 'data/wikillm.db';
    }
    if (document.getElementById('wikillm-cfg-temperature')) {
      document.getElementById('wikillm-cfg-temperature').value = data.temperature ?? 0.2;
    }
    if (document.getElementById('wikillm-cfg-context-window')) {
      document.getElementById('wikillm-cfg-context-window').value = data.max_context_tokens ?? 4096;
    }
    if (document.getElementById('wikillm-cfg-auto-enrich')) {
      document.getElementById('wikillm-cfg-auto-enrich').checked = Boolean(data.auto_enrichment ?? true);
    }
    if (document.getElementById('wikillm-cfg-auto-index')) {
      document.getElementById('wikillm-cfg-auto-index').checked = Boolean(data.auto_indexing ?? true);
    }
  } catch (e) {
    console.warn('[WikiLLM] Не удалось загрузить настройки:', e);
  }
}

/**
 * Инициализация встроенного редактора базы знаний WikiLLM Knowledge Editor.
 * @returns {Promise<void>}
 */
export async function initWikiLLMEditor() {
  const container = document.getElementById('wikillm_editor-container');
  if (!container) return;
  if (typeof window.WikiLLMEditorComponent !== 'function') {
    try {
      await loadScript('/html/js/wikillm_editor.js?v=' + Date.now());
    } catch (e) {
      console.error('[WikiLLM] Не удалось загрузить скрипт редактора:', e);
    }
  }
  if (typeof window.WikiLLMEditorComponent === 'function') {
    if (!window.wikiEditor || window.wikiEditor.container !== container) {
      window.wikiEditor = new window.WikiLLMEditorComponent('wikillm_editor-container');
    }
    await window.wikiEditor.init();
  }
}

/**
 * Привязка событий сохранения и обновления настроек WikiLLM.
 */
export function bindWikiLLMButtons() {
  const saveBtn = document.getElementById('wikillm-btn-save');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', async () => {
      const model = document.getElementById('wikillm-cfg-model')?.value || 'gemini-3.1-flash-lite';
      const threshold = parseFloat(document.getElementById('wikillm-cfg-threshold')?.value || '0.85');
      const dbPath = document.getElementById('wikillm-cfg-db-path')?.value || 'data/wikillm.db';
      const temp = parseFloat(document.getElementById('wikillm-cfg-temperature')?.value || '0.2');
      const contextTokens = parseInt(document.getElementById('wikillm-cfg-context-window')?.value || '4096', 10);
      const autoEnrich = document.getElementById('wikillm-cfg-auto-enrich')?.checked ?? true;
      const autoIndex = document.getElementById('wikillm-cfg-auto-index')?.checked ?? true;

      const payload = {
        model_name: model,
        confidence_threshold: threshold,
        db_path: dbPath,
        temperature: temp,
        max_context_tokens: contextTokens,
        auto_enrichment: autoEnrich,
        auto_indexing: autoIndex,
        editor_enabled: true
      };

      try {
        const res = await fetch('/api/v1/wikillm/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          notifyUser('Настройки WikiLLM успешно сохранены', 'success');
        } else {
          notifyUser('Ошибка сохранения параметров WikiLLM', 'warning');
        }
      } catch (e) {
        console.error('[WikiLLM] Ошибка сохранения настроек:', e);
        notifyUser('Сетевая ошибка при сохранении настроек WikiLLM', 'danger');
      }
    });
  }

  const retryBtn = document.getElementById('wikillm-btn-retry');
  if (retryBtn && !retryBtn._bound) {
    retryBtn._bound = true;
    retryBtn.addEventListener('click', async () => {
      await loadWikiLLMSettings();
      notifyUser('Параметры WikiLLM обновлены', 'info');
    });
  }
}

/**
 * Инициализация панели параметров и редактора WikiLLM.
 * @returns {Promise<void>}
 */
export async function initWikiLLMSettingsPanel() {
  bindWikiLLMButtons();
  await loadWikiLLMSettings();
  await initWikiLLMEditor();
}
