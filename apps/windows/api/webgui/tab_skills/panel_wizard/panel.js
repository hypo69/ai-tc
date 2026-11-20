/**
 * @file apps/windows/api/webgui/tab_skills/panel_wizard/panel.js
 * @description Пошаговый мастер создания навыков (Wizard: метаданные, инструкции SKILL.md, скрипты, предпросмотр)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { apiFetch } from '../common/ui_utils.js';

let currentWizardStep = 1;

/**
 * Получение текущего шага мастера
 * @returns {number}
 */
export function getCurrentWizardStep() {
  return currentWizardStep;
}

/**
 * Переход к определенному шагу мастера (1..4)
 * @param {number} step
 */
export function goToStep(step) {
  if (step < 1 || step > 4) return;
  currentWizardStep = step;

  for (let i = 1; i <= 4; i++) {
    const stepEl = document.getElementById(`wizard-step-${i}`);
    const badgeEl = document.getElementById(`step-badge-${i}`);
    const labelEl = document.getElementById(`step-label-${i}`);

    if (stepEl) {
      if (i === step) stepEl.classList.remove('d-none');
      else stepEl.classList.add('d-none');
    }

    if (badgeEl && labelEl) {
      if (i === step) {
        badgeEl.className = 'badge rounded-circle p-2 bg-primary step-indicator';
        labelEl.className = 'small fw-semibold text-white';
      } else if (i < step) {
        badgeEl.className = 'badge rounded-circle p-2 bg-success step-indicator';
        labelEl.className = 'small text-success';
      } else {
        badgeEl.className = 'badge rounded-circle p-2 bg-secondary step-indicator';
        labelEl.className = 'small text-muted';
      }
    }
  }

  const prevBtn = document.getElementById('btn-wizard-prev');
  const nextBtn = document.getElementById('btn-wizard-next');
  const submitBtn = document.getElementById('btn-wizard-submit');

  if (prevBtn) prevBtn.disabled = (step === 1);
  if (nextBtn) {
    if (step === 4) nextBtn.classList.add('d-none');
    else nextBtn.classList.remove('d-none');
  }
  if (submitBtn) {
    if (step === 4) submitBtn.classList.remove('d-none');
    else submitBtn.classList.add('d-none');
  }

  if (step === 4) {
    syncWizardPreview();
  }
}

/**
 * Переход к следующему шагу мастера
 */
export function wizardNextStep() {
  if (currentWizardStep === 1) {
    const name = document.getElementById('wizard-skill-name')?.value.trim();
    if (!name) {
      showCreateAlert('Укажите имя навыка (kebab-case)', 'danger');
      return;
    }
    clearCreateAlert();
  }
  goToStep(currentWizardStep + 1);
}

/**
 * Переход к предыдущему шагу мастера
 */
export function wizardPrevStep() {
  goToStep(currentWizardStep - 1);
}

/**
 * Генерация kebab-case имени из описания
 */
export function generateSlugFromName() {
  const descRu = document.getElementById('wizard-skill-desc-ru')?.value.trim();
  const descEn = document.getElementById('wizard-skill-desc-en')?.value.trim();
  const source = descEn || descRu || 'custom-skill';

  let slug = source.toLowerCase()
    .replace(/[а-яё]/g, char => {
      const tr = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'};
      return tr[char] || char;
    })
    .replace(/[^a-z0-9_-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 32);

  if (slug) {
    const nameInput = document.getElementById('wizard-skill-name');
    if (nameInput) nameInput.value = slug;
    syncWizardPreview();
  }
}

/**
 * Обработка изменения категории и подстановка описаний
 * @param {Array<Object>} presets
 */
export function onCategoryChanged(presets) {
  const cat = document.getElementById('wizard-skill-category')?.value;
  const descRuInput = document.getElementById('wizard-skill-desc-ru');
  const descEnInput = document.getElementById('wizard-skill-desc-en');

  if (cat && (!descRuInput?.value || !descEnInput?.value) && presets) {
    const preset = presets.find(p => p.category === cat);
    if (preset) {
      if (!descRuInput.value) descRuInput.value = preset.descRu;
      if (!descEnInput.value) descEnInput.value = preset.descEn;
    }
  }
  syncWizardPreview();
}

/**
 * Заполнение стандартного набора инструкций
 */
export function fillStandardInstructions() {
  const descRu = document.getElementById('wizard-skill-desc-ru')?.value.trim() || 'Выполнение специализированных задач';
  const descEn = document.getElementById('wizard-skill-desc-en')?.value.trim() || 'Specialized agent task execution';

  const elPurp = document.getElementById('wizard-inst-purpose');
  if (elPurp) elPurp.value = descEn;

  const elTrig = document.getElementById('wizard-inst-triggers');
  if (elTrig) elTrig.value = `Activate when the user asks to perform tasks matching: ${descRu}.`;

  const elProt = document.getElementById('wizard-inst-protocol');
  if (elProt) elProt.value = `1. Validate input query and preconditions.\n2. Execute core logic and inspect helper scripts in scripts/.\n3. Return structured markdown response.`;

  const elRules = document.getElementById('wizard-inst-rules');
  if (elRules) elRules.value = `- Ensure English logging via src.logger.logger.\n- Gracefully catch and report all execution errors.`;

  syncInstructionsFromFields();
}

/**
 * Синхронизация инструкций из структурированных полей в общий Markdown
 */
export function syncInstructionsFromFields() {
  const name = document.getElementById('wizard-skill-name')?.value.trim() || 'custom-skill';
  const title = name.replace('-', ' ').replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  const purpose = document.getElementById('wizard-inst-purpose')?.value.trim() || 'Provide specialized agent capability.';
  const triggers = document.getElementById('wizard-inst-triggers')?.value.trim() || 'Activate upon relevant user requests.';
  const protocol = document.getElementById('wizard-inst-protocol')?.value.trim() || '1. Parse input.\n2. Execute action.\n3. Output result.';
  const rules = document.getElementById('wizard-inst-rules')?.value.trim() || '- Maintain fail-fast validation.\n- Report status clearly.';

  const md = `# ${title}\n\n## 🎯 Purpose\n${purpose}\n\n## 🚀 When to Use & Triggers\n${triggers}\n\n## 📋 Execution Protocol\n${protocol}\n\n## ⚙️ Rules & Constraints\n${rules}\n`;
  const instEl = document.getElementById('wizard-skill-instructions');
  if (instEl) instEl.value = md;
  syncWizardPreview();
}

/**
 * Переключение редактора скрипта main.py
 */
export function toggleScriptEditor() {
  const chk = document.getElementById('wizard-enable-script');
  const container = document.getElementById('wizard-script-container');
  const scriptCode = document.getElementById('wizard-script-code');

  if (chk?.checked) {
    container?.classList.remove('d-none');
    if (!scriptCode.value.trim()) {
      const name = document.getElementById('wizard-skill-name')?.value.trim() || 'custom-skill';
      scriptCode.value = `# -*- coding: utf-8 -*-\n"""Executable tool helper for ${name}."""\n\nimport sys\n\ndef main():\n    print("Running helper script...")\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n`;
    }
  } else {
    container?.classList.add('d-none');
  }
  syncWizardPreview();
}

/**
 * Переключение редактора справочника guide.md
 */
export function toggleRefEditor() {
  const chk = document.getElementById('wizard-enable-ref');
  const container = document.getElementById('wizard-ref-container');
  const refContent = document.getElementById('wizard-ref-content');

  if (chk?.checked) {
    container?.classList.remove('d-none');
    if (!refContent.value.trim()) {
      const name = document.getElementById('wizard-skill-name')?.value.trim() || 'custom-skill';
      refContent.value = `# ${name.replace('-', ' ').toUpperCase()} Specification\n\nDetailed operational rules and reference data.\n`;
    }
  } else {
    container?.classList.add('d-none');
  }
  syncWizardPreview();
}

/**
 * Синхронизация предпросмотра навыка
 */
export function syncWizardPreview() {
  const name = document.getElementById('wizard-skill-name')?.value.trim() || 'custom-skill';
  const dir = document.getElementById('wizard-skill-dir')?.value || '.agents/skills';
  const descEn = document.getElementById('wizard-skill-desc-en')?.value.trim() || `Agent skill for ${name}.`;
  const descRu = document.getElementById('wizard-skill-desc-ru')?.value.trim() || descEn;
  const instructions = document.getElementById('wizard-skill-instructions')?.value.trim() || `# ${name}\n\n## 🎯 Purpose\n${descEn}\n`;

  const hasScript = document.getElementById('wizard-enable-script')?.checked;
  const hasRef = document.getElementById('wizard-enable-ref')?.checked;

  const nameEl = document.getElementById('preview-skill-name');
  const pathEl = document.getElementById('preview-skill-path');
  const badgeScript = document.getElementById('preview-badge-script');
  const badgeRef = document.getElementById('preview-badge-ref');
  const previewFull = document.getElementById('preview-skillmd-full');

  if (nameEl) nameEl.textContent = name;
  if (pathEl) pathEl.textContent = `${dir}/${name}`;
  if (badgeScript) {
    if (hasScript) badgeScript.classList.remove('d-none');
    else badgeScript.classList.add('d-none');
  }
  if (badgeRef) {
    if (hasRef) badgeRef.classList.remove('d-none');
    else badgeRef.classList.add('d-none');
  }

  const fullSkillMd = `---
name: ${name}
description: ${descEn}
description_i18n:
  en: ${descEn}
  ru: ${descRu}
---

${instructions}`;

  if (previewFull) previewFull.textContent = fullSkillMd;

  const readmeEl = document.getElementById('wizard-skill-readme');
  if (readmeEl && !readmeEl.value.trim()) {
    readmeEl.value = `# ${name.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}\n\n## Overview\n${descEn}\n\n## Location\n\`${dir}/${name}/\`\n`;
  }
}

/**
 * Создание навыка через API на основе параметров мастера
 * @param {Function} onSuccess Callback при успешном создании
 */
export async function createSkillFromWizard(onSuccess) {
  const name = document.getElementById('wizard-skill-name')?.value.trim().toLowerCase();
  if (!name) {
    goToStep(1);
    showCreateAlert('Укажите имя навыка', 'danger');
    return;
  }

  const spinner = document.getElementById('wizard-submit-spinner');
  spinner?.classList.remove('d-none');

  const descEn = document.getElementById('wizard-skill-desc-en')?.value.trim() || `Agent skill for ${name}.`;
  const descRu = document.getElementById('wizard-skill-desc-ru')?.value.trim() || descEn;
  const targetDir = document.getElementById('wizard-skill-dir')?.value || '.agents/skills';
  const category = document.getElementById('wizard-skill-category')?.value || 'general';
  const instructions = document.getElementById('wizard-skill-instructions')?.value.trim() || '';
  const readme = document.getElementById('wizard-skill-readme')?.value.trim() || '';

  const scripts = {};
  if (document.getElementById('wizard-enable-script')?.checked) {
    scripts['main.py'] = document.getElementById('wizard-script-code')?.value || '';
  }

  const references = {};
  if (document.getElementById('wizard-enable-ref')?.checked) {
    references['guide.md'] = document.getElementById('wizard-ref-content')?.value || '';
  }

  try {
    const res = await apiFetch('/api/v1/skills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        description: descEn,
        description_ru: descRu,
        category,
        target_dir: targetDir,
        instructions,
        readme,
        scripts,
        references
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

    if (onSuccess) await onSuccess(name);
  } catch (err) {
    console.error('[SkillsTab] Create error:', err);
    showCreateAlert(`Ошибка создания навыка: ${err.message}`, 'danger');
  } finally {
    spinner?.classList.add('d-none');
  }
}

/**
 * Вывод алерта в модальном окне создания навыка
 */
export function showCreateAlert(msg, type = 'danger') {
  const alertEl = document.getElementById('create-skill-alert');
  if (alertEl) {
    alertEl.className = `alert alert-${type} py-2 mt-3 mb-0`;
    alertEl.textContent = msg;
    alertEl.classList.remove('d-none');
  }
}

/**
 * Скрытие алерта создания навыка
 */
export function clearCreateAlert() {
  const alertEl = document.getElementById('create-skill-alert');
  if (alertEl) alertEl.classList.add('d-none');
}
