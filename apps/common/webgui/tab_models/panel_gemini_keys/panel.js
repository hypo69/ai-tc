/**
 * Модуль управления API-ключами Google Gemini (ротация, квоты, проверка валидности).
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_gemini_keys/panel.js
 * Updated: 2026-11-01 17:37:00
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';

/**
 * Загружает и отрисовывает список API-ключей Google Gemini.
 * @param {HTMLElement} container - DOM-контейнер tbody для списка ключей.
 */
export async function refreshKeysList(container) {
  const loadingIndicator = document.getElementById('loadingIndicator') || document.getElementById('keys-loading-indicator') || document.getElementById('modal-test-key-progress');
  if (loadingIndicator) loadingIndicator.style.display = 'block';

  try {
    container.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка ключей...</td></tr>';
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/keys/');
    const keysData = typeof res.json === 'function' ? await res.json() : res;
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
        openKeyTestModal(key, container);
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
          await activateApiKey(key.name, container);
        };
        tdActions.appendChild(btnMakeActive);
      }

      const btnTest = document.createElement('button');
      btnTest.className = 'btn btn-xs btn-outline-info btn-sm me-1';
      btnTest.innerHTML = '<i class="bi bi-lightning-charge"></i> Тест';
      btnTest.onclick = (e) => {
        e.stopPropagation();
        openKeyTestModal(key, container);
      };
      tdActions.appendChild(btnTest);

      const btnToggle = document.createElement('button');
      btnToggle.className = `btn btn-xs btn-sm me-1 ${isEnabled ? 'btn-outline-secondary' : 'btn-outline-success'}`;
      btnToggle.textContent = isEnabled ? 'Откл' : 'Вкл';
      btnToggle.onclick = (e) => {
        e.stopPropagation();
        toggleKeyStatus(key.name, isEnabled ? 'disabled' : 'active', container);
      };
      tdActions.appendChild(btnToggle);

      if (isExhausted) {
        const btnReset = document.createElement('button');
        btnReset.className = 'btn btn-xs btn-outline-warning btn-sm me-1';
        btnReset.innerHTML = 'Сброс';
        btnReset.onclick = (e) => {
          e.stopPropagation();
          resetKeyQuota(key.name, container);
        };
        tdActions.appendChild(btnReset);
      }

      const btnDelete = document.createElement('button');
      btnDelete.className = 'btn btn-xs btn-outline-danger btn-sm';
      btnDelete.textContent = 'Удалить';
      btnDelete.onclick = (e) => {
        e.stopPropagation();
        deleteKey(key.name, container);
      };
      tdActions.appendChild(btnDelete);

      row.appendChild(tdActions);
      container.appendChild(row);
    });

  } catch (err) {
    console.error('Ошибка загрузки ключей:', err);
    container.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Ошибка: ${err.message}</td></tr>`;
  } finally {
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
  }
}

/**
 * Делает ключ активным в ротации.
 * @param {string} name - Имя ключа.
 * @param {HTMLElement} [container] - DOM-контейнер для обновления.
 */
export async function activateApiKey(name, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/keys/${encodeURIComponent(name)}/activate`, {
      method: 'POST'
    });
    showModelsNotification(`Ключ "${name}" успешно назначен активным`, 'success');
    if (container) await refreshKeysList(container);
  } catch (err) {
    console.error('Ошибка активации ключа:', err);
    showModelsNotification('Ошибка активации ключа: ' + err.message, 'danger');
  }
}

/**
 * Открывает модальное окно тестирования ключа.
 * @param {Object} key - Данные ключа.
 * @param {HTMLElement} container - DOM-контейнер списка ключей.
 * @param {string} [provider='gemini'] - Имя провайдера.
 */
export async function openKeyTestModal(key, container, provider = 'gemini') {
  const modalEl = document.getElementById('modal-test-key');
  if (!modalEl) return;

  const keyNameEl = document.getElementById('modal-test-key-name');
  const keyMaskedEl = document.getElementById('modal-test-key-masked');
  const keyStatusEl = document.getElementById('modal-test-key-status-badge');
  const keyDurationEl = document.getElementById('modal-test-key-duration');
  const resultBox = document.getElementById('modal-test-key-result-box');
  const promptInput = document.getElementById('modal-test-key-prompt');
  const modelSelect = document.getElementById('modal-test-key-model');
  const retryBtn = document.getElementById('modal-test-key-retry-btn');

  if (keyNameEl) keyNameEl.textContent = key.name || '-';
  if (keyMaskedEl) keyMaskedEl.textContent = key.masked_key || key.api_key_masked || '****************';
  if (keyStatusEl) {
    const isAct = key.status === 'active';
    keyStatusEl.className = `badge ${isAct ? 'bg-success' : 'bg-secondary'}`;
    keyStatusEl.textContent = isAct ? 'Активен' : 'Отключен';
  }
  if (keyDurationEl) keyDurationEl.textContent = '⏱️ -- ms';
  if (resultBox) resultBox.style.display = 'none';

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
  }

  if (retryBtn) {
    retryBtn.onclick = () => runKeyTest(key.name, promptInput?.value || 'hello world', modelSelect?.value || 'gemini-3.1-flash-lite', container, provider);
  }

  await runKeyTest(key.name, promptInput?.value || 'hello world', modelSelect?.value || 'gemini-3.1-flash-lite', container, provider);
}

/**
 * Отправляет тестовый запрос для проверки ключа.
 * @param {string} keyName - Имя ключа.
 * @param {string} message - Текст запроса.
 * @param {string} model - Имя модели.
 * @param {HTMLElement} container - DOM-контейнер списка ключей.
 * @param {string} [provider='gemini'] - Провайдер ('gemini' или 'agy').
 */
export async function runKeyTest(keyName, message, model, container, provider = 'gemini') {
  const loadingIndicator = document.getElementById('loadingIndicator') || document.getElementById('modal-test-key-progress');
  const progressEl = document.getElementById('modal-test-key-progress');
  const resultBox = document.getElementById('modal-test-key-result-box');
  const resultContent = document.getElementById('modal-test-key-result-content');
  const validBadge = document.getElementById('modal-test-key-valid-badge');
  const keyDurationEl = document.getElementById('modal-test-key-duration');
  const retryBtn = document.getElementById('modal-test-key-retry-btn');

  if (progressEl) progressEl.style.display = 'block';
  if (loadingIndicator) loadingIndicator.style.display = 'block';
  if (resultBox) resultBox.style.display = 'none';
  if (retryBtn) retryBtn.disabled = true;

  try {
    const endpoint = provider === 'agy'
      ? `/api/keys/agy/${encodeURIComponent(keyName)}/test`
      : `/api/keys/${encodeURIComponent(keyName)}/test`;

    const fetchFn = (window.api && window.api.fetch) || fetch;
    const response = await fetchFn(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message || 'hello world', model: model || 'gemini-3.1-flash-lite' }),
    });

    const res = typeof response.json === 'function' ? await response.json() : response;

    if (resultBox) resultBox.style.display = 'block';

    if (keyDurationEl && res && res.duration_ms !== undefined) {
      keyDurationEl.textContent = `⏱️ ${res.duration_ms} ms`;
    }

    if (res && res.status === 'success' && res.valid) {
      if (validBadge) {
        validBadge.className = 'badge bg-success';
        validBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i> Валиден (OK)';
      }
      if (resultContent) {
        resultContent.className = 'p-2.5 rounded font-monospace small border border-success-subtle bg-success-subtle text-success-emphasis';
        resultContent.textContent = res.response || '(Пустой ответ)';
      }
      showModelsNotification(`Ключ "${keyName}" успешно прошел проверку (${res.duration_ms} мс)`, 'success');
    } else {
      if (validBadge) {
        validBadge.className = 'badge bg-danger';
        validBadge.innerHTML = '<i class="bi bi-x-circle me-1"></i> Ошибка валидации';
      }
      if (resultContent) {
        resultContent.className = 'p-2.5 rounded font-monospace small border border-danger-subtle bg-danger-subtle text-danger-emphasis';
        resultContent.textContent = (res && (res.error || res.message)) ? (res.error || res.message) : 'Неизвестная ошибка валидации ключа';
      }
      showModelsNotification(`Ошибка проверки ключа "${keyName}": ${(res && res.error) ? res.error : 'Ошибка API'}`, 'danger');
    }

    if (container) {
      await refreshKeysList(container);
    }
  } catch (err) {
    console.error('Ошибка проверки ключа:', err);
    if (resultBox) resultBox.style.display = 'block';
    if (validBadge) {
      validBadge.className = 'badge bg-danger';
      validBadge.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Сбой сети / API';
    }
    if (resultContent) {
      resultContent.className = 'p-2.5 rounded font-monospace small border border-danger-subtle bg-danger-subtle text-danger-emphasis';
      resultContent.textContent = err.message || String(err);
    }
    showModelsNotification('Сбой запроса проверки ключа: ' + err.message, 'danger');
  } finally {
    if (progressEl) progressEl.style.display = 'none';
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
    if (retryBtn) retryBtn.disabled = false;
  }
}

/**
 * Переключает статус активности ключа (active / disabled).
 */
export async function toggleKeyStatus(name, newStatus, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/keys/${name}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    showModelsNotification(`Статус ключа "${name}" изменен на ${newStatus === 'active' ? 'активный' : 'отключенный'}`, 'success');
    await refreshKeysList(container);
  } catch (err) {
    console.error('Ошибка переключения статуса ключа:', err);
    showModelsNotification('Ошибка изменения статуса: ' + err.message, 'danger');
  }
}

/**
 * Сбрасывает 24-часовую блокировку квоты ключа.
 */
export async function resetKeyQuota(name, container) {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/keys/${name}/reset-quota`, { method: 'POST' });
    showModelsNotification(`Квота для ключа "${name}" успешно сброшена`, 'success');
    await refreshKeysList(container);
  } catch (err) {
    console.error('Ошибка сброса квоты:', err);
    showModelsNotification('Ошибка сброса квоты: ' + err.message, 'danger');
  }
}

/**
 * Удаляет API-ключ.
 */
export async function deleteKey(name, container) {
  if (!confirm(`Вы уверены, что хотите удалить ключ "${name}"?`)) return;
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    await fetchFn(`/api/keys/${name}`, { method: 'DELETE' });
    showModelsNotification(`Ключ "${name}" успешно удален`, 'success');
    await refreshKeysList(container);
  } catch (err) {
    console.error('Ошибка удаления ключа:', err);
    showModelsNotification('Ошибка удаления: ' + err.message, 'danger');
  }
}
