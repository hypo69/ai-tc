/**
 * Модуль параметров (values) реестра, их редактирования и интеграции с ИИ-диагностикой.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/panel_values/panel.js
 * Updated: 2026-10-17 01:55:00
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentKeyData = null;

export function getCurrentKeyData() {
  return currentKeyData;
}

export function setCurrentKeyData(data) {
  currentKeyData = data;
}

/**
 * Отрисовывает параметры текущего ключа в таблице.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onReload - Коллбек перезагрузки раздела.
 */
export function renderValues(currentHive, currentPath, onReload) {
  const valuesTbody = document.getElementById('reg-values-tbody');
  const valuesCountBadge = document.getElementById('reg-values-count-badge');
  if (!valuesTbody || !currentKeyData) return;

  const filterText = (document.getElementById('reg-filter-input')?.value || '').toLowerCase().trim();
  const values = currentKeyData.values || [];

  const filtered = values.filter(v => {
    if (!filterText) return true;
    return (v.name || '').toLowerCase().includes(filterText) ||
           String(v.data).toLowerCase().includes(filterText) ||
           (v.type_name || '').toLowerCase().includes(filterText);
  });

  if (valuesCountBadge) valuesCountBadge.innerText = `${filtered.length} / ${values.length}`;

  if (filtered.length === 0) {
    valuesTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted p-4">Параметры отсутствуют или не соответствуют фильтру</td></tr>';
    return;
  }

  valuesTbody.innerHTML = filtered.map((v, idx) => {
    let dataDisplay = v.data;
    if (dataDisplay === null || dataDisplay === undefined) {
      dataDisplay = '<span class="text-muted">(Значение не задано)</span>';
    } else if (typeof dataDisplay === 'object') {
      dataDisplay = `<pre class="mb-0 text-info" style="font-size: 0.75rem;">${JSON.stringify(dataDisplay, null, 2)}</pre>`;
    } else {
      dataDisplay = `<span class="text-light text-break">${escapeHtml(String(dataDisplay))}</span>`;
    }

    const isDefault = v.name === '(Default / По умолчанию)' || v.name === '(Default)';
    const rawNameAttr = escapeHtml(isDefault ? '' : v.name);

    return `
      <tr class="reg-val-row" data-idx="${idx}" style="cursor: pointer;" title="Нажмите для AI-объяснения параметра реестра">
        <td>
          <div class="fw-bold text-white text-truncate" style="max-width: 220px;" title="${v.name}">
            <i class="bi bi-file-earmark-binary text-secondary me-1"></i>
            ${escapeHtml(v.name)}
          </div>
        </td>
        <td>
          <span class="reg-type-badge">${v.type_name}</span>
        </td>
        <td>
          ${dataDisplay}
        </td>
        <td class="text-center">
          <button class="btn btn-xs btn-outline-info py-0 px-2 me-1 btn-edit-val" data-idx="${idx}" title="Редактировать">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-xs btn-outline-danger py-0 px-2 btn-del-val" data-name="${rawNameAttr}" title="Удалить">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  // Интеграция с AITableModal при клике на строку
  valuesTbody.querySelectorAll('.reg-val-row').forEach(row => {
    row.onclick = (evt) => {
      if (evt.target.closest('.btn-edit-val') || evt.target.closest('.btn-del-val')) return;
      const idx = parseInt(row.getAttribute('data-idx'), 10);
      const v = filtered[idx];
      if (!v) return;

      if (window.AITableModal) {
        window.AITableModal.show({
          icon: '🔑',
          title: v.name || '(Default)',
          subtitle: `${currentHive}\\${currentPath}`,
          tableType: 'registry',
          badges: [
            { text: v.type_name || 'REG_SZ', class: 'badge bg-info text-dark' },
            { text: currentHive, class: 'badge bg-secondary' }
          ],
          metadata: [
            { label: 'Параметр', value: v.name || '(По умолчанию)' },
            { label: 'Тип данных', value: v.type_name },
            { label: 'Ветка реестра (Hive)', value: currentHive },
            { label: 'Путь к разделу', value: currentPath, isCode: true, fullWidth: true },
            { label: 'Значение', value: String(v.data ?? ''), isCode: true, fullWidth: true }
          ],
          rawTitle: 'Значение параметра',
          rawContent: typeof v.data === 'object' ? JSON.stringify(v.data, null, 2) : String(v.data ?? ''),
          requestData: {
            hive: currentHive,
            path: currentPath,
            name: v.name,
            type: v.type_name,
            data: v.data
          }
        });
      }
    };
  });

  valuesTbody.querySelectorAll('.btn-edit-val').forEach(btn => {
    btn.onclick = (evt) => {
      evt.stopPropagation();
      const idx = parseInt(btn.getAttribute('data-idx'), 10);
      const valObj = filtered[idx];
      if (valObj) openEditValueModal(valObj);
    };
  });

  valuesTbody.querySelectorAll('.btn-del-val').forEach(btn => {
    btn.onclick = (evt) => {
      evt.stopPropagation();
      const valName = btn.getAttribute('data-name');
      confirmDeleteValue(valName, currentHive, currentPath, onReload);
    };
  });
}

/**
 * Открывает модальное окно редактирования параметра.
 * @param {Object} valObj - Объект параметра.
 */
export function openEditValueModal(valObj) {
  const isDefault = !valObj.name || valObj.name === '(Default / По умолчанию)' || valObj.name === '(Default)';
  const nameInput = document.getElementById('regModalValueName');
  const typeSelect = document.getElementById('regModalValueType');
  const dataInput = document.getElementById('regModalValueData');
  const title = document.getElementById('regValueModalTitle');

  if (title) title.innerText = '✏️ Редактирование параметра';
  if (nameInput) {
    nameInput.value = isDefault ? '' : valObj.name;
    nameInput.disabled = true;
  }
  if (typeSelect) typeSelect.value = valObj.type_name || 'REG_SZ';
  if (dataInput) {
    if (Array.isArray(valObj.data)) {
      dataInput.value = valObj.data.join('\n');
    } else {
      dataInput.value = valObj.data !== null && valObj.data !== undefined ? String(valObj.data) : '';
    }
  }

  const modalEl = document.getElementById('regValueModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

/**
 * Открывает модальное окно создания нового параметра.
 */
export function openCreateValueModal() {
  const nameInput = document.getElementById('regModalValueName');
  const typeSelect = document.getElementById('regModalValueType');
  const dataInput = document.getElementById('regModalValueData');
  const title = document.getElementById('regValueModalTitle');

  if (title) title.innerText = '➕ Создание нового параметра';
  if (nameInput) {
    nameInput.value = '';
    nameInput.disabled = false;
  }
  if (typeSelect) typeSelect.value = 'REG_SZ';
  if (dataInput) dataInput.value = '';

  const modalEl = document.getElementById('regValueModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

/**
 * Сохраняет параметр из модального окна через REST API.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onReload - Коллбек перезагрузки раздела.
 */
export async function saveModalValue(currentHive, currentPath, onReload) {
  const nameInput = document.getElementById('regModalValueName');
  const typeSelect = document.getElementById('regModalValueType');
  const dataInput = document.getElementById('regModalValueData');
  const backupCheck = document.getElementById('regModalBackupCheck');

  const name = nameInput ? nameInput.value.trim() : '';
  const type_name = typeSelect ? typeSelect.value : 'REG_SZ';
  const rawData = dataInput ? dataInput.value : '';
  const create_backup = backupCheck ? backupCheck.checked : true;

  try {
    const payload = {
      hive: currentHive,
      path: currentPath,
      name: name,
      type_name: type_name,
      data: rawData,
      create_backup: create_backup
    };

    const res = await fetch('/api/registry/value', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }

    const modalEl = document.getElementById('regValueModal');
    if (modalEl && window.bootstrap) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }

    if (onReload) await onReload(currentHive, currentPath);
  } catch (e) {
    window.showToast?.(`Ошибка сохранения параметра: ${e.message}`, 'danger') || alert(`Ошибка сохранения параметра: ${e.message}`);
  }
}

/**
 * Удаляет параметр реестра с созданием резервной копии.
 * @param {string} name - Имя параметра.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onReload - Коллбек перезагрузки раздела.
 */
export async function confirmDeleteValue(name, currentHive, currentPath, onReload) {
  const displayName = name ? `'${name}'` : '(По умолчанию)';
  if (!confirm(`Вы действительно хотите удалить параметр ${displayName}? Перед удалением будет автоматически создан бэкап.`)) {
    return;
  }

  try {
    const res = await fetch('/api/registry/value', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hive: currentHive,
        path: currentPath,
        name: name,
        create_backup: true
      })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }

    window.showToast?.(`Параметр ${displayName} удален`, 'success');
    if (onReload) await onReload(currentHive, currentPath);
  } catch (e) {
    window.showToast?.(`Ошибка удаления параметра: ${e.message}`, 'danger') || alert(`Ошибка удаления параметра: ${e.message}`);
  }
}
