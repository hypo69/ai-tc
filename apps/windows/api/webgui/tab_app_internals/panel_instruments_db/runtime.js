/**
 * =============================================================================
 * Process Name: Windows App Internals - AI Instruments Runtime Settings
 * =============================================================================
 * Description:
 *   Модуль управления параметрами выполнения инструментов в агентной цепочке
 *   рассуждений (Tool Calling, таймауты, права администратора, политика SafeOps
 *   и автоизвлечение из советов модели, см. conversation 8bdc91cc-bd8f-4a2b-b7d9-d13455e82580).
 *
 * File: runtime.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_instruments_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:05:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v2';

/**
 * Загрузка конфигурации рантайма выполнения инструментов агента.
 * @returns {Promise<void>}
 */
export async function loadInstrumentsRuntimeConfig() {
  try {
    const res = await fetch('/api/v1/ai-instruments/runtime/config');
    if (!res.ok) return;
    const data = await res.json();
    const cfg = data.runtime || {};

    const timeoutInp = document.getElementById('inst-runtime-timeout');
    if (timeoutInp) timeoutInp.value = cfg.execution_timeout ?? 15;

    const prefixInp = document.getElementById('inst-runtime-prefix');
    if (prefixInp) prefixInp.value = cfg.title_prefix || 'Инструмент агента';

    const elevateCb = document.getElementById('inst-runtime-elevate');
    if (elevateCb) elevateCb.checked = Boolean(cfg.elevate_powershell ?? true);

    const safeopsCb = document.getElementById('inst-runtime-safeops');
    if (safeopsCb) safeopsCb.checked = Boolean(cfg.safe_ops_enabled ?? true);

    const autoextractCb = document.getElementById('inst-runtime-autoextract');
    if (autoextractCb) autoextractCb.checked = Boolean(cfg.auto_extract_from_reasoning ?? true);
  } catch (err) {
    console.warn('[AI Instruments Runtime] Ошибка загрузки параметров рантайма:', err);
  }
}

/**
 * Сохранение параметров рантайма выполнения инструментов.
 * @returns {Promise<void>}
 */
export async function saveInstrumentsRuntimeConfig() {
  const btn = document.getElementById('inst-runtime-btn-save');
  const resultBox = document.getElementById('inst-runtime-result');
  if (btn) btn.disabled = true;

  const payload = {
    execution_timeout: parseInt(document.getElementById('inst-runtime-timeout')?.value || '15', 10),
    title_prefix: document.getElementById('inst-runtime-prefix')?.value || 'Инструмент агента',
    elevate_powershell: document.getElementById('inst-runtime-elevate')?.checked ?? true,
    safe_ops_enabled: document.getElementById('inst-runtime-safeops')?.checked ?? true,
    auto_extract_from_reasoning: document.getElementById('inst-runtime-autoextract')?.checked ?? true,
  };

  try {
    const res = await fetch('/api/v1/ai-instruments/runtime/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success || data.status === 'ok') {
      notifyUser('Параметры цепочки размышлений успешно сохранены', 'success');
      if (resultBox) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `
          <div class="alert alert-success py-2 px-3 mb-0 small">
            <i class="bi bi-check-circle-fill me-1"></i>
            Параметры агентного контура и Tool Calling обновлены.
          </div>
        `;
        setTimeout(() => {
          if (resultBox) resultBox.style.display = 'none';
        }, 4000);
      }
    } else {
      notifyUser('Ошибка сохранения параметров: ' + (data.message || 'Ошибка сервера'), 'warning');
    }
  } catch (err) {
    console.error('[AI Instruments Runtime] Ошибка сети при сохранении:', err);
    notifyUser('Сетевая ошибка при сохранении параметров рантайма', 'danger');
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Привязка кнопок панели параметров цепочки размышлений.
 */
export function bindInstrumentsRuntimeButtons() {
  const saveBtn = document.getElementById('inst-runtime-btn-save');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', saveInstrumentsRuntimeConfig);
  }
}
