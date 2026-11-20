/**
 * @file apps/windows/api/webgui/tab_skills/panel_details_modal/panel.js
 * @description Модальное окно инспектора навыка (просмотр SKILL.md, README, файлов, тестирование в Sandbox, сборка архива)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-20 16:45:00
 */

import { apiFetch, formatBytes } from '../common/ui_utils.js';

let currentSkill = null;

/**
 * Получение текущего открытого навыка
 * @returns {Object|null}
 */
export function getCurrentSkill() {
  return currentSkill;
}

/**
 * Открытие модального окна деталей навыка
 * @param {string} name Имя навыка
 * @param {string} defaultTab Идентификатор кнопки вкладки по умолчанию
 */
export async function openSkillDetails(name, defaultTab = 'detail-tab-skillmd') {
  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error(`Failed to load skill details: ${res.statusText}`);
    const data = await res.json();
    currentSkill = data.skill;

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val !== undefined ? val : '';
    };

    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val !== undefined ? val : '';
    };

    setText('detail-skill-title', currentSkill.name);
    setText('detail-skill-path', currentSkill.relative_path);
    setVal('detail-skill-desc-input', currentSkill.description || '');
    setVal('detail-skill-desc-ru-input', currentSkill.descriptions_i18n?.ru || '');
    setVal('detail-skill-instructions', currentSkill.instructions || '');
    setVal('detail-skill-readme', currentSkill.readme_raw || '');

    const filesContainer = document.getElementById('detail-files-list');
    if (filesContainer) {
      if (currentSkill.files && currentSkill.files.length > 0) {
        filesContainer.innerHTML = currentSkill.files.map(f => `
          <div class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center py-1 small">
            <span><i class="bi bi-file-earmark text-secondary"></i> ${f.rel_path}</span>
            <span class="badge bg-secondary font-monospace">${formatBytes(f.size)}</span>
          </div>
        `).join('');
      } else {
        filesContainer.innerHTML = '<div class="text-muted small py-2">Файлы отсутствуют</div>';
      }
    }

    const contractEl = document.getElementById('detail-json-contract');
    if (contractEl) {
      const contractObj = {
        name: currentSkill.name,
        description: currentSkill.description,
        descriptions_i18n: currentSkill.descriptions_i18n,
        metadata: currentSkill.metadata,
        manifest: currentSkill.manifest,
      };
      contractEl.textContent = JSON.stringify(contractObj, null, 2);
    }

    const sandboxOutput = document.getElementById('sandbox-output-box');
    if (sandboxOutput) {
      sandboxOutput.textContent = `Готов к тестированию навыка '${currentSkill.name}'. Введите тестовый запрос и нажмите «Запустить».`;
    }

    const alertEl = document.getElementById('detail-skill-alert');
    if (alertEl) alertEl.classList.add('d-none');

    const modalEl = document.getElementById('skillDetailsModal');
    if (window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }

    const targetTabBtn = document.getElementById(defaultTab);
    if (targetTabBtn && window.bootstrap && window.bootstrap.Tab) {
      const tab = new window.bootstrap.Tab(targetTabBtn);
      tab.show();
    }
  } catch (err) {
    console.error('[SkillsTab] Details error:', err);
    if (window.showToast) {
      window.showToast(`Ошибка открытия деталей навыка: ${err.message}`, 'danger');
    } else {
      alert(`Ошибка открытия деталей навыка: ${err.message}`);
    }
  }
}

/**
 * Быстрое открытие вкладки Sandbox в модальном окне
 * @param {string} name
 */
export async function openSkillSandbox(name) {
  await openSkillDetails(name, 'detail-tab-sandbox');
}

/**
 * Запуск тестового прогона навыка в песочнице (Sandbox)
 */
export async function runSandboxTest() {
  if (!currentSkill) return;
  const promptInput = document.getElementById('sandbox-test-prompt');
  const outputBox = document.getElementById('sandbox-output-box');
  const spinner = document.getElementById('sandbox-spinner');

  const prompt = promptInput?.value.trim() || `Test execute skill ${currentSkill.name}`;
  spinner?.classList.remove('d-none');
  if (outputBox) outputBox.textContent = `⏳ Отправка запроса к модели для навыка '${currentSkill.name}'...\n`;

  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(currentSkill.name)}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }

    const data = await res.json();
    if (outputBox) {
      outputBox.textContent = `[Model: ${data.model_used}]\n\n${data.response}`;
    }
  } catch (err) {
    console.error('[SkillsTab] Sandbox test error:', err);
    if (outputBox) outputBox.textContent = `❌ Ошибка тестирования: ${err.message}`;
  } finally {
    spinner?.classList.add('d-none');
  }
}

/**
 * Сохранение отредактированных инструкций и документации навыка
 * @param {Function} onRefresh Callback обновления каталога
 */
export async function saveCurrentSkill(onRefresh) {
  if (!currentSkill) return;
  const spinner = document.getElementById('save-skill-spinner');
  const alertEl = document.getElementById('detail-skill-alert');

  spinner?.classList.remove('d-none');
  try {
    const description = document.getElementById('detail-skill-desc-input')?.value.trim();
    const description_ru = document.getElementById('detail-skill-desc-ru-input')?.value.trim();
    const instructions = document.getElementById('detail-skill-instructions')?.value;
    const readme = document.getElementById('detail-skill-readme')?.value;

    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(currentSkill.name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, description_ru, instructions, readme })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }

    if (alertEl) {
      alertEl.className = 'alert alert-success py-2 mt-3 mb-0';
      alertEl.textContent = '✅ Изменения успешно сохранены';
      alertEl.classList.remove('d-none');
    }
    if (window.showToast) window.showToast('Изменения навыка успешно сохранены', 'success');

    if (onRefresh) await onRefresh();
  } catch (err) {
    console.error('[SkillsTab] Save error:', err);
    if (alertEl) {
      alertEl.className = 'alert alert-danger py-2 mt-3 mb-0';
      alertEl.textContent = `Ошибка сохранения: ${err.message}`;
      alertEl.classList.remove('d-none');
    }
    if (window.showToast) window.showToast(`Ошибка сохранения: ${err.message}`, 'danger');
  } finally {
    spinner?.classList.add('d-none');
  }
}

/**
 * Сборка архивного пакета (.skill)
 * @param {string} name
 * @param {Function} onRefresh
 */
export async function packageSkill(name, onRefresh) {
  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(name)}/package`, {
      method: 'POST'
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }
    const data = await res.json();
    const msg = `✅ Навык '${name}' успешно упакован в архив:\n${data.archive?.path} (${formatBytes(data.archive?.size)})`;
    if (window.showToast) window.showToast(msg, 'success');
    if (onRefresh) await onRefresh();
  } catch (err) {
    console.error('[SkillsTab] Package error:', err);
    if (window.showToast) {
      window.showToast(`Ошибка сборки архива: ${err.message}`, 'danger');
    } else {
      alert(`Ошибка сборки архива: ${err.message}`);
    }
  }
}

/**
 * Сборка архива текущего открытого навыка
 * @param {Function} onRefresh
 */
export async function packageCurrentSkill(onRefresh) {
  if (!currentSkill) return;
  await packageSkill(currentSkill.name, onRefresh);
  await openSkillDetails(currentSkill.name);
}

/**
 * Удаление навыка и его директории
 * @param {string} name
 * @param {Function} onRefresh
 */
export async function deleteSkill(name, onRefresh) {
  if (!confirm(`Вы действительно хотите удалить навык '${name}' и все его файлы? Это действие необратимо.`)) {
    return;
  }

  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || res.statusText);
    }

    const modalEl = document.getElementById('skillDetailsModal');
    if (window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      modal?.hide();
    }

    if (window.showToast) window.showToast(`Навык '${name}' успешно удален`, 'success');
    if (onRefresh) await onRefresh();
  } catch (err) {
    console.error('[SkillsTab] Delete error:', err);
    if (window.showToast) {
      window.showToast(`Ошибка удаления навыка: ${err.message}`, 'danger');
    } else {
      alert(`Ошибка удаления навыка: ${err.message}`);
    }
  }
}

/**
 * Удаление текущего открытого навыка
 * @param {Function} onRefresh
 */
export async function deleteCurrentSkill(onRefresh) {
  if (!currentSkill) return;
  await deleteSkill(currentSkill.name, onRefresh);
}
