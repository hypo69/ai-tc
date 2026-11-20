/**
 * @file apps/windows/api/webgui/tab_skills/main.js
 * @description Корневой модуль-оркестратор вкладки управления навыками (Skills Tab Orchestrator)
 * @author hypo69
 * @version 2.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { apiFetch, formatBytes } from './common/ui_utils.js';
import { filterSkills, updateStats, renderCatalog } from './panel_catalog/panel.js';
import { SKILL_PRESETS, renderPresets } from './panel_presets/panel.js';
import {
  goToStep,
  wizardNextStep,
  wizardPrevStep,
  generateSlugFromName,
  onCategoryChanged,
  fillStandardInstructions,
  syncInstructionsFromFields,
  toggleScriptEditor,
  toggleRefEditor,
  syncWizardPreview,
  createSkillFromWizard,
  showCreateAlert,
  clearCreateAlert
} from './panel_wizard/panel.js';
import {
  generateSkillWithAi,
  applyAiResultToWizard,
  saveAiSkillDirectly
} from './panel_ai_generator/panel.js';
import {
  openSkillDetails,
  openSkillSandbox,
  runSandboxTest,
  saveCurrentSkill,
  packageSkill,
  packageCurrentSkill,
  deleteSkill,
  deleteCurrentSkill
} from './panel_details_modal/panel.js';

export class SkillsTabManager {
  constructor() {
    this.skills = [];
    this.filteredSkills = [];
    this.viewMode = 'cards';
    this.searchQuery = '';
    this.activeFilter = 'all';
    this.isInitialized = false;
    this.createMode = 'wizard';
  }

  async init() {
    if (this.isInitialized) {
      await this.refresh();
      return;
    }
    this.bindEvents();
    renderPresets();
    this.isInitialized = true;
    await this.refresh();
  }

  bindEvents() {
    const searchInput = document.getElementById('skills-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.searchQuery = e.target.value.trim().toLowerCase();
        this.applyFilters();
      });
    }

    const wizardNameInput = document.getElementById('wizard-skill-name');
    if (wizardNameInput) {
      wizardNameInput.addEventListener('input', (e) => {
        const val = e.target.value;
        const normalized = val.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
        if (val !== normalized) {
          e.target.value = normalized;
        }
        syncWizardPreview();
      });
    }

    ['wizard-inst-purpose', 'wizard-inst-triggers', 'wizard-inst-protocol', 'wizard-inst-rules'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => syncInstructionsFromFields());
      }
    });

    ['wizard-skill-desc-ru', 'wizard-skill-desc-en', 'wizard-skill-dir'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => syncWizardPreview());
        el.addEventListener('change', () => syncWizardPreview());
      }
    });
  }

  async refresh() {
    this.showLoading(true);
    try {
      const response = await apiFetch('/api/v1/skills');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      this.skills = data.skills || [];
      updateStats(this.skills);
      this.applyFilters();
    } catch (err) {
      console.error('[SkillsTab] Load error:', err);
      const cardsContainer = document.getElementById('skills-cards-container');
      if (cardsContainer) {
        cardsContainer.innerHTML = `
          <div class="col-12">
            <div class="alert alert-danger d-flex align-items-center justify-content-between p-3 shadow-sm">
              <div><i class="bi bi-exclamation-triangle-fill me-2"></i><strong>Ошибка загрузки навыков:</strong> ${err.message}</div>
              <button class="btn btn-sm btn-outline-light" onclick="window.skillsTab?.refresh()">Повторить</button>
            </div>
          </div>
        `;
      }
    } finally {
      this.showLoading(false);
    }
  }

  applyFilters() {
    const filterSelect = document.getElementById('skills-filter-select');
    this.activeFilter = filterSelect ? filterSelect.value : 'all';
    this.filteredSkills = filterSkills(this.skills, this.searchQuery, this.activeFilter);
    renderCatalog(this.filteredSkills, this.viewMode);
  }

  clearSearch() {
    const searchInput = document.getElementById('skills-search-input');
    if (searchInput) searchInput.value = '';
    this.searchQuery = '';
    this.applyFilters();
  }

  setViewMode(mode) {
    this.viewMode = mode;
    const btnCards = document.getElementById('btn-view-cards');
    const btnTable = document.getElementById('btn-view-table');

    if (mode === 'cards') {
      btnCards?.classList.add('active');
      btnTable?.classList.remove('active');
    } else {
      btnCards?.classList.remove('active');
      btnTable?.classList.add('active');
    }
    renderCatalog(this.filteredSkills, this.viewMode);
  }

  switchCreateMode(mode) {
    this.createMode = mode;
  }

  // Делегирование методов мастера
  goToStep(step) { goToStep(step); }
  wizardNextStep() { wizardNextStep(); }
  wizardPrevStep() { wizardPrevStep(); }
  generateSlugFromName() { generateSlugFromName(); }
  onCategoryChanged() { onCategoryChanged(SKILL_PRESETS); }
  fillStandardInstructions() { fillStandardInstructions(); }
  toggleScriptEditor() { toggleScriptEditor(); }
  toggleRefEditor() { toggleRefEditor(); }
  syncWizardPreview() { syncWizardPreview(); }

  async createSkillFromWizard() {
    await createSkillFromWizard(async (name) => {
      await this.refresh();
      await openSkillDetails(name);
    });
  }

  // Делегирование методов генератора ИИ
  async generateSkillWithAi() { await generateSkillWithAi(); }
  applyAiResultToWizard() { applyAiResultToWizard(goToStep, syncWizardPreview); }
  async saveAiSkillDirectly() {
    await saveAiSkillDirectly(async (name) => {
      await this.refresh();
      await openSkillDetails(name);
    });
  }

  // Делегирование методов пресетов
  applyPreset(presetId) {
    const preset = SKILL_PRESETS.find(p => p.id === presetId);
    if (!preset) return;

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };

    setVal('wizard-skill-name', preset.name);
    setVal('wizard-skill-desc-en', preset.descEn);
    setVal('wizard-skill-desc-ru', preset.descRu);
    setVal('wizard-skill-category', preset.category);
    setVal('wizard-skill-dir', '.agents/skills');
    setVal('wizard-inst-purpose', preset.purpose);
    setVal('wizard-inst-triggers', preset.triggers);
    setVal('wizard-inst-protocol', preset.protocol);
    setVal('wizard-inst-rules', preset.rules);

    syncInstructionsFromFields();

    const scriptChk = document.getElementById('wizard-enable-script');
    if (scriptChk) {
      scriptChk.checked = preset.hasScript;
      if (preset.hasScript) {
        document.getElementById('wizard-script-container')?.classList.remove('d-none');
        setVal('wizard-script-code', preset.scriptCode || '');
      } else {
        document.getElementById('wizard-script-container')?.classList.add('d-none');
      }
    }

    const refChk = document.getElementById('wizard-enable-ref');
    if (refChk) {
      refChk.checked = preset.hasRef;
      if (preset.hasRef) {
        document.getElementById('wizard-ref-container')?.classList.remove('d-none');
        setVal('wizard-ref-content', preset.refContent || '');
      } else {
        document.getElementById('wizard-ref-container')?.classList.add('d-none');
      }
    }

    const wizardTabBtn = document.getElementById('mode-wizard-tab');
    if (wizardTabBtn && window.bootstrap && window.bootstrap.Tab) {
      const tab = new window.bootstrap.Tab(wizardTabBtn);
      tab.show();
    }
    goToStep(1);
    syncWizardPreview();
  }

  // Делегирование методов модального окна деталей
  async openSkillDetails(name) { await openSkillDetails(name); }
  async openSkillSandbox(name) { await openSkillSandbox(name); }
  async runSandboxTest() { await runSandboxTest(); }
  async saveCurrentSkill() { await saveCurrentSkill(() => this.refresh()); }
  async packageSkill(name) { await packageSkill(name, () => this.refresh()); }
  async packageCurrentSkill() { await packageCurrentSkill(() => this.refresh()); }
  async deleteSkill(name) { await deleteSkill(name, () => this.refresh()); }
  async deleteCurrentSkill() { await deleteCurrentSkill(() => this.refresh()); }

  showLoading(show) {
    const loadingEl = document.getElementById('skills-loading');
    if (loadingEl) {
      if (show) loadingEl.classList.remove('d-none');
      else loadingEl.classList.add('d-none');
    }
  }

  formatBytes(bytes) {
    return formatBytes(bytes);
  }
}

// Глобальная инициализация и экспорт для контейнера WebGUI
window.SkillsTabManager = SkillsTabManager;
if (!window.skillsTab) {
  window.skillsTab = new SkillsTabManager();
}
window.initSkillsTab = function() {
  if (window.skillsTab) {
    window.skillsTab.init();
  }
};

if (document.getElementById('skills-tab-root')) {
  window.skillsTab.init();
}
