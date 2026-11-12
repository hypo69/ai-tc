/**
 * Модуль управления пулом API-ключей Antigravity (AGY) и OpenAI-совместимых сервисов.
 * Файл: apps/windows/api/webgui/tab_models/panel_agy_keys/panel.js
 * Updated: 2026-11-03 15:54:00
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';
import { openKeyTestModal } from '../panel_gemini_keys/panel.js';

/**
 * Активирует ключ AGY в качестве основного в ротации.
 * @param {string} name - Имя ключа.
 * @param {HTMLElement} [container] - DOM-контейнер таблицы.
 */
export async function activateAgyKey(name, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/v1/keys/agy/${encodeURIComponent(name)}/activate`, {
      method: 'POST'
    });
    showModelsNotification(`Ключ AGY "${name}" успешно назначен активным`, 'success');
    if (window.toast && typeof window.toast.success === 'function') {
      window.toast.success('Ключ активирован', `Ключ AGY "${name}" теперь активен`);
    }
    if (container) await refreshAgyKeysList(container);
  } catch (err) {
    console.error('Ошибка активации ключа AGY:', err);
    showModelsNotification('Ошибка активации ключа AGY: ' + err.message, 'danger');
  }
}

/**
 * Переключает статус ключа AGY (active / disabled).
 */
export async function toggleAgyKeyStatus(name, newStatus, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/v1/keys/agy/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    showModelsNotification(`Статус ключа AGY "${name}" изменен на ${newStatus === 'active' ? 'активный' : 'отключенный'}`, 'success');
    if (container) await refreshAgyKeysList(container);
  } catch (err) {
    console.error('Ошибка переключения статуса ключа AGY:', err);
    showModelsNotification('Ошибка изменения статуса: ' + err.message, 'danger');
  }
}

/**
 * Сбрасывает суточный бан квоты ключа AGY.
 */
export async function resetAgyKeyQuota(name, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/v1/keys/agy/${encodeURIComponent(name)}/reset-quota`, { method: 'POST' });
    showModelsNotification(`Квота для ключа AGY "${name}" успешно сброшена`, 'success');
    if (container) await refreshAgyKeysList(container);
  } catch (err) {
    console.error('Ошибка сброса квоты AGY:', err);
    showModelsNotification('Ошибка сброса квоты AGY: ' + err.message, 'danger');
  }
}

/**
 * Удаляет ключ AGY.
 */
export async function deleteAgyKey(name, container) {
  if (!confirm(`Вы уверены, что хотите удалить ключ AGY "${name}"?`)) return;
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/v1/keys/agy/${encodeURIComponent(name)}`, { method: 'DELETE' });
    showModelsNotification(`Ключ AGY "${name}" успешно удален`, 'success');
    if (container) await refreshAgyKeysList(container);
  } catch (err) {
    console.error('Ошибка удаления ключа AGY:', err);
    showModelsNotification('Ошибка удаления AGY: ' + err.message, 'danger');
  }
}

/**
 * Загрузка и отрисовка пула ключей Google Antigravity (AGY).
 * @param {HTMLElement} container - Элемент tbody таблицы ключей AGY.
 */
export async function refreshAgyKeysList(container) {
  if (!container) return;
  const loadingIndicator = document.getElementById('agyLoadingIndicator') || document.getElementById('loadingIndicator');
  if (loadingIndicator) loadingIndicator.style.display = 'block';

  try {
    container.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка ключей...</td></tr>';
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const response = await fetchFn('/api/v1/keys/agy');
    const keysData = typeof response.json === 'function' ? await response.json() : response;
    const keys = Array.isArray(keysData) ? keysData : (keysData.keys || []);

    if (keys.length === 0) {
      container.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Список ключей пуст</td></tr>';
      return;
    }

    container.innerHTML = '';
    keys.forEach(key => {
      const row = document.createElement('tr');
      row.style.cursor = 'pointer';
      row.title = `Нажмите для проверки ключа "${key.name}"`;

      const isCurrentActive = Boolean(key.is_active);
      const isExhausted = Boolean(key.exhausted || key.status === 'exhausted' || key.exhausted_at);
      const isEnabled = key.status === 'active';

      if (isCurrentActive) {
        row.className = 'table-success border border-2 border-success align-middle';
      } else {
        row.className = 'align-middle';
      }

      row.addEventListener('click', (e) => {
        if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input')) return;
        openKeyTestModal(key, container, 'agy');
      });

      const tdName = document.createElement('td');
      if (isCurrentActive) {
        tdName.innerHTML = `<strong class="text-success">${escapeHtml(key.name)}</strong> <span class="badge bg-success font-monospace ms-1" style="font-size: 0.72rem;"><i class="bi bi-check-circle-fill me-1"></i>Активен</span>`;
      } else {
        tdName.innerHTML = `<strong>${escapeHtml(key.name)}</strong>`;
      }
      row.appendChild(tdName);

      const tdKey = document.createElement('td');
      tdKey.className = 'font-monospace text-muted small';
      tdKey.textContent = key.masked_key || key.api_key_masked || '';
      row.appendChild(tdKey);

      const tdStatus = document.createElement('td');
      if (isCurrentActive) {
        tdStatus.innerHTML = `<span class="badge bg-success" title="Используется моделью в данный момент"><i class="bi bi-play-circle-fill me-1"></i>Используется</span>`;
      } else if (isExhausted) {
        tdStatus.innerHTML = `<span class="badge bg-danger" title="Превышена суточная квота запросов"><i class="bi bi-exclamation-octagon me-1"></i>Превысил квоту</span>`;
      } else if (isEnabled) {
        tdStatus.innerHTML = `<span class="badge bg-primary-subtle text-primary border border-primary" title="Включен в резерве"><i class="bi bi-check2 me-1"></i>Включен</span>`;
      } else {
        tdStatus.innerHTML = `<span class="badge bg-secondary" title="Отключен пользователем"><i class="bi bi-slash-circle me-1"></i>Выключен</span>`;
      }
      row.appendChild(tdStatus);

      const tdQuota = document.createElement('td');
      if (isExhausted) {
        let resetText = 'Лимит исчерпан';
        if (key.reset_in_seconds) {
          const hours = Math.floor(key.reset_in_seconds / 3600);
          const mins = Math.floor((key.reset_in_seconds % 3600) / 60);
          resetText = `Сброс через ${hours}ч ${mins}м`;
        }
        tdQuota.innerHTML = `<span class="badge bg-danger d-block mb-1">${resetText}</span>`;
      } else {
        tdQuota.innerHTML = `<span class="badge bg-success-subtle text-success border border-success d-block mb-1">OK</span>`;
      }
      row.appendChild(tdQuota);

      const tdActions = document.createElement('td');
      tdActions.className = 'text-end text-nowrap';

      if (isCurrentActive) {
        const activeBadge = document.createElement('span');
        activeBadge.className = 'badge bg-success text-white py-1 px-2 me-1 font-monospace';
        activeBadge.innerHTML = '<i class="bi bi-star-fill text-warning me-1"></i>Активен';
        tdActions.appendChild(activeBadge);
      } else {
        const btnMakeActive = document.createElement('button');
        btnMakeActive.className = 'btn btn-xs btn-outline-success btn-sm me-1';
        btnMakeActive.innerHTML = '<i class="bi bi-star me-1"></i>Сделать активным';
        btnMakeActive.onclick = async (e) => {
          e.stopPropagation();
          await activateAgyKey(key.name, container);
        };
        tdActions.appendChild(btnMakeActive);
      }

      const btnTest = document.createElement('button');
      btnTest.className = 'btn btn-xs btn-outline-info btn-sm me-1';
      btnTest.innerHTML = '<i class="bi bi-lightning-charge"></i> Тест';
      btnTest.onclick = (e) => {
        e.stopPropagation();
        openKeyTestModal(key, container, 'agy');
      };
      tdActions.appendChild(btnTest);

      const btnToggle = document.createElement('button');
      btnToggle.className = `btn btn-xs btn-sm me-1 ${isEnabled ? 'btn-outline-secondary' : 'btn-outline-success'}`;
      btnToggle.textContent = isEnabled ? 'Откл' : 'Вкл';
      btnToggle.onclick = (e) => {
        e.stopPropagation();
        toggleAgyKeyStatus(key.name, isEnabled ? 'disabled' : 'active', container);
      };
      tdActions.appendChild(btnToggle);

      if (isExhausted) {
        const btnReset = document.createElement('button');
        btnReset.className = 'btn btn-xs btn-outline-warning btn-sm me-1';
        btnReset.innerHTML = 'Сброс';
        btnReset.onclick = (e) => {
          e.stopPropagation();
          resetAgyKeyQuota(key.name, container);
        };
        tdActions.appendChild(btnReset);
      }

      const btnDelete = document.createElement('button');
      btnDelete.className = 'btn btn-xs btn-outline-danger btn-sm';
      btnDelete.textContent = 'Удалить';
      btnDelete.onclick = (e) => {
        e.stopPropagation();
        deleteAgyKey(key.name, container);
      };
      tdActions.appendChild(btnDelete);

      row.appendChild(tdActions);
      container.appendChild(row);
    });

  } catch (err) {
    console.error('Ошибка загрузки ключей AGY:', err);
    container.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Ошибка: ${err.message}</td></tr>`;
  } finally {
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
  }
}
