/**
 * @file apps/windows/api/webgui/tab_skills/panel_ai_generator/panel.js
 * @description Панель генерации навыков с помощью ИИ (Natural Language to Skill)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { apiFetch } from '../common/ui_utils.js';
import { showCreateAlert, clearCreateAlert } from '../panel_wizard/panel.js';

let aiGeneratedData = null;

/**
 * Получение текущих данных, сгенерированных ИИ
 * @returns {Object|null}
 */
export function getAiGeneratedData() {
  return aiGeneratedData;
}

/**
 * Генерация структуры навыка через ИИ по текстовому описанию
 */
export async function generateSkillWithAi() {
  const prompt = document.getElementById('ai-skill-prompt')?.value.trim();
  if (!prompt) {
    showCreateAlert('Введите описание задачи для генерации навыка', 'warning');
    return;
  }

  const spinner = document.getElementById('ai-gen-spinner');
  const resBox = document.getElementById('ai-result-box');
  const resSlug = document.getElementById('ai-res-slug');
  const resPreview = document.getElementById('ai-res-preview');

  spinner?.classList.remove('d-none');
  clearCreateAlert();

  try {
    const category = document.getElementById('ai-skill-category')?.value || 'general';
    const targetDir = document.getElementById('ai-skill-dir')?.value || '.agents/skills';

    const res = await apiFetch('/api/v1/skills/generate-ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, category, target_dir: targetDir })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }

    const data = await res.json();
    aiGeneratedData = data.generated;

    if (resSlug) resSlug.textContent = `⚡ ${aiGeneratedData.name}`;
    if (resPreview) resPreview.textContent = aiGeneratedData.instructions;
    resBox?.classList.remove('d-none');
  } catch (err) {
    console.error('[SkillsTab] AI generate error:', err);
    showCreateAlert(`Ошибка генерации навыка: ${err.message}`, 'danger');
  } finally {
    spinner?.classList.add('d-none');
  }
}

/**
 * Перенос сгенерированных данных в пошаговый мастер
 * @param {Function} goToStep Функция перехода к шагу
 * @param {Function} syncPreview Функция обновления предпросмотра
 */
export function applyAiResultToWizard(goToStep, syncPreview) {
  if (!aiGeneratedData) return;
  const g = aiGeneratedData;

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
  };

  setVal('wizard-skill-name', g.name);
  setVal('wizard-skill-desc-en', g.description);
  setVal('wizard-skill-desc-ru', g.description_ru);
  setVal('wizard-skill-category', g.category || 'general');
  setVal('wizard-skill-dir', g.target_dir || '.agents/skills');
  setVal('wizard-skill-instructions', g.instructions);
  setVal('wizard-skill-readme', g.readme);

  if (g.scripts && g.scripts['main.py']) {
    const scriptChk = document.getElementById('wizard-enable-script');
    if (scriptChk) scriptChk.checked = true;
    document.getElementById('wizard-script-container')?.classList.remove('d-none');
    setVal('wizard-script-code', g.scripts['main.py']);
  }

  if (g.references && g.references['guide.md']) {
    const refChk = document.getElementById('wizard-enable-ref');
    if (refChk) refChk.checked = true;
    document.getElementById('wizard-ref-container')?.classList.remove('d-none');
    setVal('wizard-ref-content', g.references['guide.md']);
  }

  const wizardTabBtn = document.getElementById('mode-wizard-tab');
  if (wizardTabBtn && window.bootstrap && window.bootstrap.Tab) {
    const tab = new window.bootstrap.Tab(wizardTabBtn);
    tab.show();
  }

  if (goToStep) goToStep(1);
  if (syncPreview) syncPreview();
}

/**
 * Непосредственное сохранение навыка, созданного ИИ, без ручной доработки
 * @param {Function} onSuccess Callback успешного сохранения
 */
export async function saveAiSkillDirectly(onSuccess) {
  if (!aiGeneratedData) return;
  const g = aiGeneratedData;

  try {
    const res = await apiFetch('/api/v1/skills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: g.name,
        description: g.description,
        description_ru: g.description_ru,
        category: g.category,
        target_dir: g.target_dir,
        instructions: g.instructions,
        readme: g.readme,
        scripts: g.scripts || {},
        references: g.references || {}
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }

    const modalEl = document.getElementById('createSkillModal');
    if (window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      modal?.hide();
    }

    if (onSuccess) await onSuccess(g.name);
  } catch (err) {
    console.error('[SkillsTab] AI Direct Save error:', err);
    showCreateAlert(`Ошибка сохранения: ${err.message}`, 'danger');
  }
}
