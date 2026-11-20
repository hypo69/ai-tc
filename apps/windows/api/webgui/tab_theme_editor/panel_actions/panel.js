/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Actions Panel
 * =============================================================================
 * Description:
 *   Модуль панели действий (тулбара): сохранение дочерней темы, создание
 *   дочерней темы на базе стандартной, сброс к родителю, удаление, переименование,
 *   экспорт/импорт JSON и копирование CSS.
 *
 * File: panel_actions/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_theme_editor/panel_actions
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { showToast } from '../common/ui_utils.js';
import { PRESETS, loadPreset, getPreset } from '../panel_presets/panel.js';
import {
  collectTokensFromUI,
  collectFullStateFromUI,
  applyStateToUI,
  generateCssString
} from '../panel_tokens/panel.js';

/**
 * Загружает текущее сохраненное состояние темы или активный пресет.
 * @param {Function} onUpdate - Колбэк обновления превью.
 */
export function loadCurrentThemeState(onUpdate) {
  const presetSelect = document.getElementById('theme-preset-select');
  const savedMode = window.themeEngine ? window.themeEngine.getSavedMode() : 'theme-dark-slate';
  const targetPreset = presetSelect && presetSelect.value ? presetSelect.value : savedMode;

  loadPreset(targetPreset, () => {
    if (window.themeEngine) {
      window.themeEngine.previewTheme(targetPreset);
    }
    if (typeof onUpdate === 'function') onUpdate();
  });
}

/**
 * Открывает модальное окно создания дочерней темы.
 * @param {string} [defaultParentId] - ID базовой родительской темы.
 */
export function openCreateChildModal(defaultParentId) {
  const presetSelect = document.getElementById('theme-preset-select');
  const currentKey = defaultParentId || presetSelect?.value || 'theme-dark-slate';

  let parentId = currentKey;
  if (window.themeEngine?.isChildTheme(currentKey)) {
    const currentChild = window.themeEngine.getChildTheme(currentKey);
    parentId = currentChild?.parentId || 'theme-dark-slate';
  }

  const parentTheme = window.themeEngine?.getTheme(parentId) || window.themeEngine?.getTheme('theme-dark-slate');
  const parentName = parentTheme?.name || parentId;

  // Наполнение селектора базовых тем в модальном окне
  const parentSelect = document.getElementById('child-theme-parent-select');
  if (parentSelect && window.themeEngine) {
    const standardThemes = window.themeEngine.getStandardThemes();
    parentSelect.innerHTML = standardThemes
      .map((t) => `<option value="${t.id}"${t.id === parentId ? ' selected' : ''}>${t.name}</option>`)
      .join('\n');
  }

  // Предзаполнение названия
  const nameInput = document.getElementById('child-theme-name-input');
  if (nameInput) {
    nameInput.value = `${parentName} (Моя копия)`;
  }

  const descInput = document.getElementById('child-theme-desc-input');
  if (descInput) {
    descInput.value = `Пользовательская модификация на базе ${parentName}`;
  }

  const modalEl = document.getElementById('themeCreateChildModal');
  if (modalEl && window.bootstrap) {
    const modalInstance = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
  }
}

/**
 * Подключает слушатели событий к кнопкам действий тулбара.
 * @param {Function} onUpdate - Колбэк обновления превью.
 */
export function bindActions(onUpdate) {
  const presetSelect = document.getElementById('theme-preset-select');

  // Кнопка Сохранить тему
  const btnSave = document.getElementById('theme-btn-save');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      const isChild = window.themeEngine?.isChildTheme(selectedPreset);

      if (isChild) {
        // Сохранение в существующую дочернюю тему
        const tokens = collectTokensFromUI();
        const state = collectFullStateFromUI();
        const updated = window.themeEngine.updateChildTheme(selectedPreset, {
          tokens,
          settings: state,
        });
        showToast('Тема оформления', `Изменения успешно сохранены в дочернюю тему «${updated.name}»!`, 'success');
      } else {
        // Стандартные темы защищены от изменений — предлагаем создать дочернюю тему
        openCreateChildModal(selectedPreset);
      }
    });
  }

  // Кнопка «Создать дочернюю тему» в карточке пресетов
  const btnCreateChild = document.getElementById('theme-btn-create-child');
  if (btnCreateChild) {
    btnCreateChild.addEventListener('click', () => {
      openCreateChildModal();
    });
  }

  // Кнопка подтверждения создания дочерней темы в модалке
  const btnConfirmCreate = document.getElementById('btn-confirm-create-child');
  if (btnConfirmCreate) {
    btnConfirmCreate.addEventListener('click', () => {
      const nameInput = document.getElementById('child-theme-name-input');
      const parentSelectEl = document.getElementById('child-theme-parent-select');
      const descInput = document.getElementById('child-theme-desc-input');

      const name = nameInput?.value.trim();
      const parentId = parentSelectEl?.value || 'theme-dark-slate';
      const desc = descInput?.value.trim() || '';

      if (!name) {
        showToast('Создание темы', 'Пожалуйста, введите название дочерней темы.', 'warning');
        return;
      }

      if (!window.themeEngine) return;

      try {
        const tokens = collectTokensFromUI();
        const state = collectFullStateFromUI();

        const createdTheme = window.themeEngine.createChildTheme({
          name,
          parentId,
          tokens,
          settings: state,
          description: desc,
        });

        // Применяем созданную тему
        window.themeEngine.applyTheme(createdTheme.id);

        // Закрываем модальное окно
        const modalEl = document.getElementById('themeCreateChildModal');
        if (modalEl && window.bootstrap) {
          window.bootstrap.Modal.getInstance(modalEl)?.hide();
        }

        const parentTheme = window.themeEngine.getTheme(parentId);
        showToast('Тема оформления', `Дочерняя тема «${name}» успешно создана на базе «${parentTheme?.name || parentId}»!`, 'success');
      } catch (err) {
        showToast('Ошибка создания', err.message, 'danger');
      }
    });
  }

  // Кнопка Удалить дочернюю тему
  const btnDeleteChild = document.getElementById('theme-btn-delete-child');
  if (btnDeleteChild) {
    btnDeleteChild.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const parentTheme = window.themeEngine.getTheme(childTheme?.parentId);

      if (confirm(`Удалить дочернюю тему «${childTheme?.name || selectedPreset}»? Это действие нельзя отменить.`)) {
        window.themeEngine.deleteChildTheme(selectedPreset);
        showToast('Удаление темы', `Дочерняя тема удалена. Активирована базовая тема «${parentTheme?.name || 'Стандартная'}».`, 'info');
      }
    });
  }

  // Кнопка Сбросить к родителю
  const btnResetToParent = document.getElementById('theme-btn-reset-to-parent');
  if (btnResetToParent) {
    btnResetToParent.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const parentTheme = window.themeEngine.getTheme(childTheme?.parentId);

      if (confirm(`Сбросить все параметры темы «${childTheme?.name}» к исходным значениям родителя «${parentTheme?.name || 'Стандартная'}»?`)) {
        window.themeEngine.resetChildThemeToParent(selectedPreset);
        loadPreset(selectedPreset, () => {
          if (window.themeEngine) window.themeEngine.previewTheme(selectedPreset);
          if (typeof onUpdate === 'function') onUpdate();
        });
        showToast('Сброс к родителю', `Параметры темы сброшены к базовым значениям «${parentTheme?.name || 'Стандартная'}».`, 'info');
      }
    });
  }

  // Кнопка Переименовать дочернюю тему
  const btnRenameChild = document.getElementById('theme-btn-rename-child');
  if (btnRenameChild) {
    btnRenameChild.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const renameInput = document.getElementById('child-theme-rename-input');
      if (renameInput) renameInput.value = childTheme?.name || '';

      const modalEl = document.getElementById('themeRenameChildModal');
      if (modalEl && window.bootstrap) {
        window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    });
  }

  // Кнопка подтверждения переименования в модалке
  const btnConfirmRename = document.getElementById('btn-confirm-rename-child');
  if (btnConfirmRename) {
    btnConfirmRename.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const renameInput = document.getElementById('child-theme-rename-input');
      const newName = renameInput?.value.trim();
      if (!newName) {
        showToast('Переименование', 'Введите новое имя темы.', 'warning');
        return;
      }

      window.themeEngine.updateChildTheme(selectedPreset, { name: newName });

      const modalEl = document.getElementById('themeRenameChildModal');
      if (modalEl && window.bootstrap) {
        window.bootstrap.Modal.getInstance(modalEl)?.hide();
      }

      showToast('Переименование', `Тема переименована в «${newName}».`, 'success');
    });
  }

  // Кнопка Сбросить тему (в тулбаре)
  const btnReset = document.getElementById('theme-btn-reset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      if (confirm('Сбросить несохраненные изменения редактора к исходным значениям текущей темы?')) {
        if (window.themeEngine) {
          window.themeEngine.clearCustomOverrides();
        }
        loadPreset(selectedPreset, () => {
          if (window.themeEngine) {
            window.themeEngine.previewTheme(selectedPreset);
          }
          if (typeof onUpdate === 'function') onUpdate();
        });
        showToast('Сброс настроек', 'Несохраненные настройки формы сброшены к текущей теме.', 'info');
      }
    });
  }

  // Кнопка Экспорт JSON
  const btnExport = document.getElementById('theme-btn-export');
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      const isChild = window.themeEngine?.isChildTheme(selectedPreset);
      const childTheme = isChild ? window.themeEngine.getChildTheme(selectedPreset) : null;
      const state = collectFullStateFromUI();

      if (isChild && childTheme) {
        state.isChild = true;
        state.parentId = childTheme.parentId;
        state.name = childTheme.name;
      }

      const jsonStr = JSON.stringify(state, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-theme-${(state.name || 'custom').toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Экспорт темы', 'Конфигурация темы сохранена в файл JSON.', 'info');
    });
  }

  // Импорт JSON
  const fileImport = document.getElementById('theme-file-import');
  if (fileImport) {
    fileImport.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(event.target?.result);
          applyStateToUI(imported);
          if (typeof onUpdate === 'function') onUpdate();

          // Если в импортированном файле указана дочерняя тема, предлагаем сохранить ее в дочерние
          if (imported.parentId && window.themeEngine) {
            const themeName = imported.name || 'Импортированная тема';
            if (confirm(`Импортирована дочерняя тема «${themeName}» на базе «${imported.parentId}». Зарегистрировать ее как отдельную дочернюю тему?`)) {
              const tokens = collectTokensFromUI();
              const newChild = window.themeEngine.createChildTheme({
                name: themeName,
                parentId: imported.parentId,
                tokens,
                settings: imported,
              });
              window.themeEngine.applyTheme(newChild.id);
            }
          }

          showToast('Импорт темы', `Тема «${imported.name || 'Пользовательская'}» успешно импортирована!`, 'success');
        } catch (err) {
          showToast('Ошибка импорта', `Не удалось распарсить JSON: ${err.message}`, 'danger');
        }
        fileImport.value = '';
      };
      reader.readAsText(file);
    });
  }

  // Кнопка Копировать CSS
  const btnCopyCss = document.getElementById('theme-btn-copy-css');
  if (btnCopyCss) {
    btnCopyCss.addEventListener('click', () => {
      const css = generateCssString();
      const output = document.getElementById('theme-css-output');
      if (output) output.value = css;

      const modalEl = document.getElementById('themeCssModal');
      if (modalEl && window.bootstrap) {
        new window.bootstrap.Modal(modalEl).show();
      } else {
        navigator.clipboard.writeText(css).then(() => {
          showToast('Копирование CSS', 'CSS-код переменных скопирован в буфер обмена!', 'success');
        });
      }
    });
  }

  // Кнопка копирования внутри модального окна
  const btnCopyModal = document.getElementById('btn-copy-css-modal');
  if (btnCopyModal) {
    btnCopyModal.addEventListener('click', () => {
      const output = document.getElementById('theme-css-output');
      if (output) {
        navigator.clipboard.writeText(output.value).then(() => {
          showToast('Буфер обмена', 'CSS-код скопирован!', 'success');
        });
      }
    });
  }
}
