/**
 * Модуль пула аккаунтов Google Workspace / Cloud Console (OAuth2 & Service Accounts).
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_google_accounts/panel.js
 * Updated: 2026-11-01 17:37:00
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';

/**
 * Загружает и отрисовывает список аккаунтов Google Workspace.
 * @param {HTMLElement} container - DOM-элемент tbody для списка.
 */
export async function refreshGoogleAccountsList(container) {
  if (!container) return;
  try {
    container.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка аккаунтов...</td></tr>';
    
    let data = null;
    if (window.api?.googleAccounts?.list) {
      data = await window.api.googleAccounts.list();
    } else {
      const fetchFn = (window.api && window.api.fetch) || fetch;
      const res = await fetchFn('/api/v1/auth/google-accounts');
      data = typeof res.json === 'function' ? await res.json() : res;
    }

    const accounts = data?.accounts || [];

    if (accounts.length === 0) {
      container.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">Список аккаунтов пуст. Загрузите файл credentials.json или service_account.json.</td></tr>';
      return;
    }

    container.innerHTML = '';
    accounts.forEach(acc => {
      const row = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <strong>${escapeHtml(acc.name)}</strong>
          ${acc.is_default ? '<span class="badge bg-warning text-dark"><i class="bi bi-star-fill"></i> Default</span>' : ''}
        </div>
        ${acc.email ? `<div class="small text-muted font-monospace">${escapeHtml(acc.email)}</div>` : ''}
      `;
      row.appendChild(tdName);

      const tdType = document.createElement('td');
      const isOAuth = acc.type === 'oauth2';
      tdType.innerHTML = isOAuth
        ? '<span class="badge bg-primary-subtle text-primary border border-primary-subtle"><i class="bi bi-person me-1"></i>OAuth 2.0</span>'
        : '<span class="badge bg-info-subtle text-info border border-info-subtle"><i class="bi bi-cpu me-1"></i>Service Account</span>';
      row.appendChild(tdType);

      const tdStatus = document.createElement('td');
      const isActive = acc.status === 'active';
      if (isActive) {
        tdStatus.innerHTML = '<span class="badge bg-success">Активен</span>';
      } else if (acc.status === 'exhausted') {
        tdStatus.innerHTML = '<span class="badge bg-danger" title="Исчерпан суточный лимит квоты">Лимит</span>';
      } else {
        tdStatus.innerHTML = `<span class="badge bg-secondary">${escapeHtml(acc.status)}</span>`;
      }
      row.appendChild(tdStatus);

      const tdToken = document.createElement('td');
      if (acc.has_token || acc.type === 'service_account') {
        tdToken.innerHTML = '<span class="badge bg-success-subtle text-success"><i class="bi bi-shield-check me-1"></i>Готов</span>';
      } else {
        tdToken.innerHTML = '<span class="badge bg-warning-subtle text-warning"><i class="bi bi-key me-1"></i>Нужен токен</span>';
      }
      row.appendChild(tdToken);

      const tdActions = document.createElement('td');
      tdActions.className = 'text-end';

      if (!acc.is_default) {
        const btnDefault = document.createElement('button');
        btnDefault.className = 'btn btn-xs btn-outline-warning btn-sm me-1';
        btnDefault.title = 'Сделать аккаунтом по умолчанию';
        btnDefault.innerHTML = '<i class="bi bi-star"></i>';
        btnDefault.onclick = () => setGoogleAccountDefault(acc.name, container);
        tdActions.appendChild(btnDefault);
      }

      if (acc.status === 'exhausted') {
        const btnReset = document.createElement('button');
        btnReset.className = 'btn btn-xs btn-outline-info btn-sm me-1';
        btnReset.title = 'Сбросить статус исчерпания';
        btnReset.innerHTML = '<i class="bi bi-arrow-repeat"></i>';
        btnReset.onclick = () => resetGoogleAccountStatus(acc.name, container);
        tdActions.appendChild(btnReset);
      }

      const btnTest = document.createElement('button');
      btnTest.className = 'btn btn-xs btn-outline-info btn-sm me-1';
      btnTest.title = 'Проверить доступ и авторизацию';
      btnTest.innerHTML = '<i class="bi bi-play-circle"></i> Тест';
      btnTest.onclick = () => testGoogleAccount(acc.name);
      tdActions.appendChild(btnTest);

      const btnDelete = document.createElement('button');
      btnDelete.className = 'btn btn-xs btn-outline-danger btn-sm';
      btnDelete.title = 'Удалить аккаунт из пула';
      btnDelete.innerHTML = '<i class="bi bi-trash"></i>';
      btnDelete.onclick = () => deleteGoogleAccount(acc.name, container);
      tdActions.appendChild(btnDelete);

      row.appendChild(tdActions);
      container.appendChild(row);
    });

  } catch (err) {
    console.error('Ошибка загрузки аккаунтов Google Workspace:', err);
    container.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

/**
 * Обрабатывает добавление нового Google аккаунта из формы.
 * @param {HTMLElement} container - DOM-элемент таблицы аккаунтов.
 */
export async function handleAddGoogleAccount(container) {
  const nameInput = document.getElementById('new-gacc-name');
  const typeSelect = document.getElementById('new-gacc-type');
  const emailInput = document.getElementById('new-gacc-email');
  const fileInput = document.getElementById('new-gacc-file');
  const jsonTextarea = document.getElementById('new-gacc-json');
  const defaultCheckbox = document.getElementById('new-gacc-default');
  const addBtn = document.getElementById('btn-add-gacc');

  if (!nameInput || !addBtn) return;

  const accountName = nameInput.value.trim();
  const accountType = typeSelect ? typeSelect.value : 'oauth2';
  const email = emailInput ? emailInput.value.trim() : '';
  const setAsDefault = defaultCheckbox ? defaultCheckbox.checked : false;

  if (!accountName) {
    showModelsNotification('Введите имя аккаунта (например: work, personal)', 'warning');
    nameInput.focus();
    return;
  }

  const file = fileInput && fileInput.files && fileInput.files[0];
  const jsonContent = jsonTextarea ? jsonTextarea.value.trim() : '';

  if (!file && !jsonContent) {
    showModelsNotification('Загрузите файл credentials.json / service_account.json или вставьте JSON', 'warning');
    return;
  }

  addBtn.disabled = true;
  const originalText = addBtn.innerHTML;
  addBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сохранение...';

  try {
    if (file) {
      const formData = new FormData();
      formData.append('account_name', accountName);
      formData.append('account_type', accountType);
      if (email) formData.append('email', email);
      formData.append('set_as_default', setAsDefault ? 'true' : 'false');
      formData.append('file', file);

      if (window.api?.googleAccounts?.upload) {
        await window.api.googleAccounts.upload(formData);
      } else {
        await fetch('/api/v1/auth/google-accounts/upload', {
          method: 'POST',
          body: formData
        });
      }
    } else {
      let parsedJson = null;
      try {
        parsedJson = JSON.parse(jsonContent);
      } catch (e) {
        throw new Error('Некорректный JSON в поле учетных данных');
      }

      if (window.api?.googleAccounts?.create) {
        await window.api.googleAccounts.create({
          account_name: accountName,
          account_type: accountType,
          email: email || undefined,
          credentials_dict: parsedJson,
          set_as_default: setAsDefault
        });
      } else {
        const fetchFn = (window.api && window.api.fetch) || fetch;
        await fetchFn('/api/v1/auth/google-accounts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            account_name: accountName,
            account_type: accountType,
            email: email || undefined,
            credentials_dict: parsedJson,
            set_as_default: setAsDefault
          })
        });
      }
    }

    showModelsNotification(`Аккаунт Google "${accountName}" успешно сохранен в пул`, 'success');
    nameInput.value = '';
    if (emailInput) emailInput.value = '';
    if (fileInput) fileInput.value = '';
    if (jsonTextarea) jsonTextarea.value = '';
    if (defaultCheckbox) defaultCheckbox.checked = false;

    if (container) await refreshGoogleAccountsList(container);
  } catch (err) {
    console.error('Ошибка сохранения аккаунта Google:', err);
    showModelsNotification('Ошибка сохранения: ' + err.message, 'danger');
  } finally {
    addBtn.disabled = false;
    addBtn.innerHTML = originalText;
  }
}

/**
 * Назначает аккаунт дефолтным.
 */
export async function setGoogleAccountDefault(name, container) {
  try {
    if (window.api?.googleAccounts?.setDefault) {
      await window.api.googleAccounts.setDefault(name);
    } else {
      const fetchFn = (window.api && window.api.fetch) || fetch;
      await fetchFn(`/api/v1/auth/google-accounts/${encodeURIComponent(name)}/set-default`, { method: 'POST' });
    }
    showModelsNotification(`Аккаунт "${name}" назначен по умолчанию`, 'success');
    if (container) await refreshGoogleAccountsList(container);
  } catch (err) {
    console.error('Ошибка установки аккаунта по умолчанию:', err);
    showModelsNotification('Ошибка: ' + err.message, 'danger');
  }
}

/**
 * Сбрасывает статус исчерпания аккаунта.
 */
export async function resetGoogleAccountStatus(name, container) {
  try {
    if (window.api?.googleAccounts?.resetStatus) {
      await window.api.googleAccounts.resetStatus(name);
    } else {
      const fetchFn = (window.api && window.api.fetch) || fetch;
      await fetchFn(`/api/v1/auth/google-accounts/${encodeURIComponent(name)}/reset-status`, { method: 'POST' });
    }
    showModelsNotification(`Статус аккаунта "${name}" сброшен в активный`, 'success');
    if (container) await refreshGoogleAccountsList(container);
  } catch (err) {
    console.error('Ошибка сброса статуса аккаунта:', err);
    showModelsNotification('Ошибка сброса: ' + err.message, 'danger');
  }
}

/**
 * Тестирует доступ к API через выбранный Google аккаунт.
 */
export async function testGoogleAccount(name) {
  const testCard = document.getElementById('gaccount-test-card');
  const testBody = document.getElementById('gaccount-test-body');

  if (testCard && testBody) {
    testCard.style.display = 'block';
    testBody.innerHTML = `<span class="spinner-border spinner-border-sm me-2 text-info"></span>Проверка аутентификации для аккаунта <strong>${escapeHtml(name)}</strong>...`;
  }

  try {
    let res = null;
    if (window.api?.googleAccounts?.test) {
      res = await window.api.googleAccounts.test(name);
    } else {
      const fetchFn = (window.api && window.api.fetch) || fetch;
      const resp = await fetchFn(`/api/v1/auth/google-accounts/${encodeURIComponent(name)}/test`, { method: 'POST' });
      res = typeof resp.json === 'function' ? await resp.json() : resp;
    }

    if (testBody) {
      const isSuccess = res.status === 'success';
      const isWarning = res.status === 'warning';
      const badgeClass = isSuccess ? 'bg-success' : isWarning ? 'bg-warning text-dark' : 'bg-danger';
      
      testBody.innerHTML = `
        <div class="mb-2 d-flex align-items-center gap-2">
          <span class="badge ${badgeClass}">${res.status.toUpperCase()}</span>
          <strong>${escapeHtml(name)}</strong>
        </div>
        <div class="mb-1">${escapeHtml(res.message || '')}</div>
        ${res.scopes && res.scopes.length > 0 ? `<div class="text-muted mt-2"><strong>Доступные Scopes:</strong><br>${res.scopes.map(s => '• ' + escapeHtml(s)).join('<br>')}</div>` : ''}
      `;
    }
  } catch (err) {
    if (testBody) {
      testBody.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>Ошибка проверки: ${escapeHtml(err.message)}</span>`;
    }
  }
}

/**
 * Удаляет аккаунт Google из пула.
 */
export async function deleteGoogleAccount(name, container) {
  if (!confirm(`Вы уверены, что хотите удалить аккаунт "${name}" из пула Google Workspace?`)) return;
  try {
    if (window.api?.googleAccounts?.delete) {
      await window.api.googleAccounts.delete(name);
    } else {
      const fetchFn = (window.api && window.api.fetch) || fetch;
      await fetchFn(`/api/v1/auth/google-accounts/${encodeURIComponent(name)}`, { method: 'DELETE' });
    }
    showModelsNotification(`Аккаунт "${name}" успешно удален`, 'success');
    if (container) await refreshGoogleAccountsList(container);
  } catch (err) {
    console.error('Ошибка удаления аккаунта Google:', err);
    showModelsNotification('Ошибка удаления: ' + err.message, 'danger');
  }
}
