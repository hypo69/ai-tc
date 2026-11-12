/**
 * Модуль панели подразделов реестра (subkeys) и операций над разделами.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/panel_subkeys/panel.js
 * Updated: 2026-10-17 01:55:00
 */

/**
 * Отрисовывает подразделы ключа в левом дереве.
 * @param {Array<string>} subkeys - Список подразделов.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onNavigate - Коллбек перехода в подраздел.
 */
export function renderSubkeys(subkeys, currentHive, currentPath, onNavigate) {
  const subkeysList = document.getElementById('reg-subkeys-list');
  const subkeysCountBadge = document.getElementById('reg-subkeys-count-badge');
  if (!subkeysList) return;

  const list = subkeys || [];
  if (subkeysCountBadge) subkeysCountBadge.innerText = list.length;

  if (list.length === 0) {
    subkeysList.innerHTML = '<div class="text-muted text-center py-4 small">Нет подразделов</div>';
    return;
  }

  subkeysList.innerHTML = list.map(sk => `
    <div class="reg-tree-item" data-subkey="${sk}" title="${sk}">
      <i class="bi bi-folder-fill text-warning"></i>
      <span class="text-truncate">${sk}</span>
    </div>
  `).join('');

  subkeysList.querySelectorAll('.reg-tree-item').forEach(item => {
    item.onclick = () => {
      const subkey = item.getAttribute('data-subkey');
      const newPath = currentPath ? `${currentPath}\\${subkey}` : subkey;
      if (onNavigate) onNavigate(currentHive, newPath);
    };
  });
}

/**
 * Открывает модальное окно создания нового подраздела.
 */
export function openCreateKeyModal() {
  const keyNameInput = document.getElementById('regModalNewKeyName');
  if (keyNameInput) keyNameInput.value = '';

  const modalEl = document.getElementById('regKeyModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

/**
 * Сохраняет новый подраздел через API.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onReload - Коллбек обновления после создания.
 */
export async function saveModalKey(currentHive, currentPath, onReload) {
  const keyNameInput = document.getElementById('regModalNewKeyName');
  const newKeyName = keyNameInput ? keyNameInput.value.trim() : '';
  if (!newKeyName) {
    window.showToast?.('Введите имя подраздела', 'warning') || alert('Введите имя подраздела');
    return;
  }

  const newPath = currentPath ? `${currentPath}\\${newKeyName}` : newKeyName;

  try {
    const res = await fetch('/api/registry/key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hive: currentHive,
        path: newPath
      })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }

    const modalEl = document.getElementById('regKeyModal');
    if (modalEl && window.bootstrap) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }

    window.showToast?.(`Подраздел '${newKeyName}' успешно создан`, 'success');
    if (onReload) await onReload(currentHive, currentPath);
  } catch (e) {
    window.showToast?.(`Ошибка создания ключа: ${e.message}`, 'danger') || alert(`Ошибка создания ключа: ${e.message}`);
  }
}

/**
 * Удаляет текущий раздел со всеми подразделами и значениями.
 * @param {string} currentHive - Текущий улей.
 * @param {string} currentPath - Текущий путь.
 * @param {Function} onGoUp - Функция подъема на уровень вверх после удаления.
 */
export async function deleteCurrentKey(currentHive, currentPath, onGoUp) {
  if (!currentPath) {
    window.showToast?.('Нельзя удалить корневой раздел', 'warning') || alert('Нельзя удалить корневой раздел');
    return;
  }

  if (!confirm(`ВНИМАНИЕ: Вы действительно хотите удалить раздел '${currentHive}\\${currentPath}' со всеми подразделами и значениями? Будет создан снимок резервной копии.`)) {
    return;
  }

  try {
    const res = await fetch('/api/registry/key', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hive: currentHive,
        path: currentPath,
        recursive: true,
        create_backup: true
      })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }

    window.showToast?.('Раздел реестра успешно удален', 'success');
    if (onGoUp) onGoUp();
  } catch (e) {
    window.showToast?.(`Ошибка удаления раздела: ${e.message}`, 'danger') || alert(`Ошибка удаления раздела: ${e.message}`);
  }
}
