/**
 * =============================================================================
 * Название: Модальное окно безопасности, паролей и политик учетной записи
 * =============================================================================
 * Описание:
 *   Модальное окно Drill-Down (#userSecurityModal) с вкладками:
 *   - Вкладка 1: Безопасность и пароли (Смена пароля, политики SAM,
 *     быстрый запуск параметров Windows Hello, PIN, ms-settings и оснасток).
 *   - Вкладка 2: Политики UAC и повышение прав (роль UAC Admin/Standard,
 *     FilterAdministratorToken, Elevation Prompt Behavior, Secure Desktop, Virtualization).
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_users/security_modal.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-01 15:48:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';
import { fetchAccounts, getCurrentUserFilter } from './panel.js';
import { fetchStatus } from '../panel_overview/panel.js';

let _currentSecUser = null;
let _currentSecConfig = null;
let _isSecEventsBound = false;

/**
 * Получить имя текущего выбранного пользователя в модальном окне безопасности.
 * @returns {string|null} Имя пользователя.
 */
export function getCurrentSecurityUser() {
  return _currentSecUser;
}

/**
 * Открытие модального окна параметров безопасности для выбранного пользователя.
 * @param {string} username - Имя учетной записи Windows.
 * @param {string} [initialTab='security'] - Целевая вкладка ('security' или 'uac').
 */
export async function openUserSecurityModal(username, initialTab = 'security') {
  if (!username) return;
  _currentSecUser = username;

  const modalEl = document.getElementById('userSecurityModal');
  if (!modalEl) {
    console.warn('[UserSecurityModal] Элемент #userSecurityModal не найден в DOM');
    return;
  }

  initUserSecurityModalEvents();

  const titleUser = document.getElementById('user-security-modal-username');
  if (titleUser) titleUser.innerText = username;

  const loadingEl = document.getElementById('user-security-modal-loading');
  const contentEl = document.getElementById('user-security-modal-content');
  const errorEl = document.getElementById('user-security-modal-error');
  const msgEl = document.getElementById('sec-password-result-msg');

  if (loadingEl) loadingEl.style.display = 'block';
  if (contentEl) contentEl.style.display = 'none';
  if (errorEl) errorEl.style.display = 'none';
  if (msgEl) {
    msgEl.style.display = 'none';
    msgEl.innerText = '';
  }

  // Очистка полей ввода пароля
  const pwdInput = document.getElementById('sec-user-new-password');
  const pwdConfirm = document.getElementById('sec-user-confirm-password');
  if (pwdInput) pwdInput.value = '';
  if (pwdConfirm) pwdConfirm.value = '';

  // Активация запрошенной вкладки
  const secTabBtn = document.getElementById('sec-tab-btn-security');
  const uacTabBtn = document.getElementById('sec-tab-btn-uac');
  const targetBtn = initialTab === 'uac' ? uacTabBtn : secTabBtn;
  if (targetBtn && window.bootstrap) {
    const tab = window.bootstrap.Tab.getOrCreateInstance(targetBtn);
    tab.show();
  } else if (targetBtn) {
    targetBtn.click();
  }

  if (window.bootstrap) {
    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  try {
    const res = await fetch(`/api/sysadmin/accounts/${encodeURIComponent(username)}/uac`);
    if (!res.ok) throw new Error(`Ошибка ${res.status}: не удалось загрузить параметры пользователя`);
    const cfg = await res.json();
    _currentSecConfig = cfg;

    // 1. Заполнение информационных бейджей безопасности
    const sidEl = document.getElementById('sec-info-sid');
    if (sidEl) sidEl.innerText = cfg.sid || '—';

    const roleEl = document.getElementById('sec-info-role');
    if (roleEl) {
      roleEl.className = cfg.is_admin ? 'ui-badge ui-badge-warning' : 'ui-badge ui-badge-info';
      roleEl.innerText = cfg.is_admin ? 'Администратор' : 'Стандартный пользователь';
    }

    const statusEl = document.getElementById('sec-info-status');
    if (statusEl) {
      statusEl.className = cfg.enabled ? 'ui-badge ui-badge-success' : 'ui-badge ui-badge-danger';
      statusEl.innerText = cfg.enabled ? 'Активен' : 'Отключен';
    }

    // 2. Заполнение чекбоксов политик SAM
    const enabledChk = document.getElementById('sec-policy-enabled');
    if (enabledChk) enabledChk.checked = Boolean(cfg.enabled);

    const neverExpChk = document.getElementById('sec-policy-never-expires');
    if (neverExpChk) neverExpChk.checked = Boolean(cfg.password_never_expires);

    const cannotChgChk = document.getElementById('sec-policy-cannot-change');
    if (cannotChgChk) cannotChgChk.checked = Boolean(cfg.cannot_change_password);

    const mustChgChk = document.getElementById('sec-policy-must-change');
    if (mustChgChk) mustChgChk.checked = Boolean(cfg.password_expired);

    const pwdReqChk = document.getElementById('sec-policy-pwd-required');
    if (pwdReqChk) pwdReqChk.checked = Boolean(cfg.password_required);

    const secRoleAdmin = document.getElementById('sec-role-admin');
    const secRoleStd = document.getElementById('sec-role-standard');
    if (cfg.uac_role === 'admin' || cfg.is_admin) {
      if (secRoleAdmin) secRoleAdmin.checked = true;
    } else {
      if (secRoleStd) secRoleStd.checked = true;
    }

    // 3. Заполнение вкладки UAC
    const uacSidEl = document.getElementById('uac-info-sid');
    if (uacSidEl) uacSidEl.innerText = cfg.sid || '—';

    const luaEl = document.getElementById('uac-info-lua');
    if (luaEl) {
      luaEl.className = cfg.enable_lua ? 'ui-badge ui-badge-success' : 'ui-badge ui-badge-danger';
      luaEl.innerText = cfg.enable_lua ? 'Включен (LUA = 1)' : 'Отключен (LUA = 0)';
    }

    const uacRoleEl = document.getElementById('uac-info-role');
    if (uacRoleEl) {
      uacRoleEl.className = cfg.is_admin ? 'ui-badge ui-badge-warning' : 'ui-badge ui-badge-info';
      uacRoleEl.innerText = cfg.is_admin ? 'Администратор (UAC Admin)' : 'Стандартный пользователь';
    }

    const uacRoleAdmin = document.getElementById('uac-role-admin');
    const uacRoleStd = document.getElementById('uac-role-standard');
    if (cfg.uac_role === 'admin' || cfg.is_admin) {
      if (uacRoleAdmin) uacRoleAdmin.checked = true;
    } else {
      if (uacRoleStd) uacRoleStd.checked = true;
    }

    const builtinWrap = document.getElementById('uac-builtin-admin-wrap');
    const filterAdminToken = document.getElementById('uac-filter-admin-token');
    if (builtinWrap && filterAdminToken) {
      if (cfg.is_builtin_admin) {
        builtinWrap.style.display = 'block';
        filterAdminToken.checked = !!cfg.filter_admin_token;
      } else {
        builtinWrap.style.display = 'none';
      }
    }

    const promptAdmin = document.getElementById('uac-prompt-admin');
    if (promptAdmin) promptAdmin.value = String(cfg.consent_prompt_behavior_admin ?? 5);

    const promptUser = document.getElementById('uac-prompt-user');
    if (promptUser) promptUser.value = String(cfg.consent_prompt_behavior_user ?? 3);

    const secureDesk = document.getElementById('uac-secure-desktop');
    if (secureDesk) secureDesk.checked = !!cfg.prompt_on_secure_desktop;

    const enableVirt = document.getElementById('uac-enable-virt');
    if (enableVirt) enableVirt.checked = !!cfg.enable_virtualization;

    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'block';
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    if (errorEl) {
      errorEl.style.display = 'block';
      errorEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Ошибка загрузки: ${escapeHtml(err.message)}`;
    }
  }
}

/**
 * Сохранение измененных политик учетной записи SAM.
 */
export async function handleSaveSecurityPolicies() {
  if (!_currentSecUser) return;
  const username = _currentSecUser;
  const saveBtn = document.getElementById('btn-sec-save-policies');

  const roleAdmin = document.getElementById('sec-role-admin');
  const uacRole = roleAdmin?.checked ? 'admin' : 'standard';

  const samEnabled = Boolean(document.getElementById('sec-policy-enabled')?.checked);
  const samNeverExp = Boolean(document.getElementById('sec-policy-never-expires')?.checked);
  const samCannotChg = Boolean(document.getElementById('sec-policy-cannot-change')?.checked);
  const samMustChg = Boolean(document.getElementById('sec-policy-must-change')?.checked);
  const samPwdReq = Boolean(document.getElementById('sec-policy-pwd-required')?.checked);

  const payload = {
    uac_role: uacRole,
    enabled: samEnabled,
    password_never_expires: samNeverExp,
    cannot_change_password: samCannotChg,
    password_required: samPwdReq,
    password_expired: samMustChg,
  };

  try {
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сохранение...';
    }

    const res = await fetch(`/api/sysadmin/accounts/${encodeURIComponent(username)}/uac`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось применить политики пользователя');

    // Обновляем статус в модалке
    const statusEl = document.getElementById('sec-info-status');
    if (statusEl) {
      statusEl.className = samEnabled ? 'ui-badge ui-badge-success' : 'ui-badge ui-badge-danger';
      statusEl.innerText = samEnabled ? 'Активен' : 'Отключен';
    }
    const roleEl = document.getElementById('sec-info-role');
    if (roleEl) {
      roleEl.className = uacRole === 'admin' ? 'ui-badge ui-badge-warning' : 'ui-badge ui-badge-info';
      roleEl.innerText = uacRole === 'admin' ? 'Администратор' : 'Стандартный пользователь';
    }

    alert(`Политики учетной записи ${username} успешно обновлены!`);
    await fetchAccounts(getCurrentUserFilter());
    await fetchStatus();
  } catch (err) {
    alert(`Ошибка сохранения политик: ${err.message}`);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="bi bi-shield-check me-1"></i> <span>Сохранить политики SAM</span>';
    }
  }
}

/**
 * Сохранение измененных параметров UAC для пользователя.
 */
export async function handleSaveUserUac() {
  if (!_currentSecUser) return;
  const username = _currentSecUser;
  const saveBtn = document.getElementById('btn-save-user-uac');

  const roleAdmin = document.getElementById('uac-role-admin');
  const uacRole = roleAdmin?.checked ? 'admin' : 'standard';

  const filterAdminToken = document.getElementById('uac-filter-admin-token')?.checked;
  const promptAdmin = parseInt(document.getElementById('uac-prompt-admin')?.value || '5', 10);
  const promptUser = parseInt(document.getElementById('uac-prompt-user')?.value || '3', 10);
  const secureDesk = !!document.getElementById('uac-secure-desktop')?.checked;
  const enableVirt = !!document.getElementById('uac-enable-virt')?.checked;

  const payload = {
    uac_role: uacRole,
    filter_admin_token: filterAdminToken,
    consent_prompt_behavior_admin: promptAdmin,
    consent_prompt_behavior_user: promptUser,
    prompt_on_secure_desktop: secureDesk,
    enable_virtualization: enableVirt,
  };

  try {
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сохранение...';
    }

    const res = await fetch(`/api/sysadmin/accounts/${encodeURIComponent(username)}/uac`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось применить параметры UAC');

    // Обновляем бейджи роли в обеих вкладках
    const roleEl = document.getElementById('sec-info-role');
    if (roleEl) {
      roleEl.className = uacRole === 'admin' ? 'ui-badge ui-badge-warning' : 'ui-badge ui-badge-info';
      roleEl.innerText = uacRole === 'admin' ? 'Администратор' : 'Стандартный пользователь';
    }
    const uacRoleEl = document.getElementById('uac-info-role');
    if (uacRoleEl) {
      uacRoleEl.className = uacRole === 'admin' ? 'ui-badge ui-badge-warning' : 'ui-badge ui-badge-info';
      uacRoleEl.innerText = uacRole === 'admin' ? 'Администратор (UAC Admin)' : 'Стандартный пользователь';
    }

    alert(`Параметры UAC пользователя ${username} успешно обновлены!`);
    await fetchAccounts(getCurrentUserFilter());
    await fetchStatus();
  } catch (err) {
    alert(`Ошибка сохранения UAC: ${err.message}`);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="bi bi-shield-lock me-1"></i> <span>Применить параметры UAC</span>';
    }
  }
}

/**
 * Административная смена / сброс пароля пользователя.
 */
export async function handleChangePassword() {
  if (!_currentSecUser) return;
  const username = _currentSecUser;
  const pwdInput = document.getElementById('sec-user-new-password');
  const pwdConfirm = document.getElementById('sec-user-confirm-password');
  const changeBtn = document.getElementById('btn-sec-change-password');
  const msgEl = document.getElementById('sec-password-result-msg');

  const newPwd = pwdInput?.value || '';
  const confirmPwd = pwdConfirm?.value || '';

  if (!newPwd) {
    alert('Пожалуйста, введите новый пароль');
    pwdInput?.focus();
    return;
  }

  if (newPwd !== confirmPwd) {
    alert('Введенные пароли не совпадают!');
    pwdConfirm?.focus();
    return;
  }

  try {
    if (changeBtn) {
      changeBtn.disabled = true;
      changeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Смена пароля...';
    }
    if (msgEl) {
      msgEl.style.display = 'none';
      msgEl.innerText = '';
    }

    const res = await fetch(`/api/sysadmin/accounts/${encodeURIComponent(username)}/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_password: newPwd }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || 'Не удалось изменить пароль');
    }

    if (msgEl) {
      msgEl.className = 'text-success small fw-semibold';
      msgEl.innerText = 'Пароль успешно обновлен!';
      msgEl.style.display = 'inline-block';
    }
    if (pwdInput) pwdInput.value = '';
    if (pwdConfirm) pwdConfirm.value = '';
  } catch (err) {
    if (msgEl) {
      msgEl.className = 'text-danger small fw-semibold';
      msgEl.innerText = `Ошибка: ${err.message}`;
      msgEl.style.display = 'inline-block';
    }
  } finally {
    if (changeBtn) {
      changeBtn.disabled = false;
      changeBtn.innerHTML = '<i class="bi bi-key-fill"></i> <span>Сменить</span>';
    }
  }
}

/**
 * Быстрый запуск нативных параметров Windows через системный API.
 * @param {string} target - URI настройки (ms-settings:...) или имя оснастки.
 */
export async function launchWindowsSetting(target) {
  if (!target) return;
  try {
    const res = await fetch('/api/sysadmin/launch-setting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      if (target.startsWith('ms-settings:')) {
        window.location.href = target;
      } else {
        alert(data.detail || data.error || 'Не удалось запустить системную оснастку');
      }
    }
  } catch (err) {
    if (target.startsWith('ms-settings:')) {
      window.location.href = target;
    } else {
      alert(`Ошибка вызова системного окна: ${err.message}`);
    }
  }
}

/**
 * Инициализация обработчиков событий модального окна безопасности и UAC.
 */
export function initUserSecurityModalEvents() {
  if (_isSecEventsBound) return;
  _isSecEventsBound = true;

  const savePoliciesBtn = document.getElementById('btn-sec-save-policies');
  if (savePoliciesBtn) {
    savePoliciesBtn.onclick = handleSaveSecurityPolicies;
  }

  const saveUacBtn = document.getElementById('btn-save-user-uac');
  if (saveUacBtn) {
    saveUacBtn.onclick = handleSaveUserUac;
  }

  const changePwdBtn = document.getElementById('btn-sec-change-password');
  if (changePwdBtn) {
    changePwdBtn.onclick = handleChangePassword;
  }

  // Переключение видимости пароля
  const togglePwdChk = document.getElementById('sec-toggle-password-visibility');
  if (togglePwdChk) {
    togglePwdChk.onchange = () => {
      const type = togglePwdChk.checked ? 'text' : 'password';
      const pwdInput = document.getElementById('sec-user-new-password');
      const pwdConfirm = document.getElementById('sec-user-confirm-password');
      if (pwdInput) pwdInput.type = type;
      if (pwdConfirm) pwdConfirm.type = type;
    };
  }

  // Делегирование кликов по кнопкам запуска системных параметров Windows
  const modalEl = document.getElementById('userSecurityModal');
  if (modalEl) {
    modalEl.querySelectorAll('.btn-launch-win-setting').forEach(btn => {
      btn.onclick = (e) => {
        e.preventDefault();
        const target = btn.getAttribute('data-target');
        if (target) launchWindowsSetting(target);
      };
    });
  }
}
