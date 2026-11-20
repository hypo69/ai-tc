/**
 * =============================================================================
 * Название: Панель аудита привилегий и редактирования политики безопасности SAM
 * =============================================================================
 * Описание:
 *   Экспресс-проверки безопасности (Who is Admin?, SeServiceLogonRight, RDP,
 *   осиротевшие SID/профили) и полный интерактивный редактор локальной политики
 *   паролей, блокировки учетных записей и системного доступа Windows SAM.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_audit_sam/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml, safeApiFetch } from '../common/ui_utils.js';

/** Последняя загруженная с сервера политика SAM для вычисления diff при сохранении. */
let _currentSamPolicy = null;

/**
 * Отображает статусное сообщение в блоке обратной связи формы политики SAM.
 * @param {string} message - Текст уведомления.
 * @param {'success'|'danger'|'warning'|'info'} [type='info'] - Тип уведомления.
 */
function showSamPolicyFeedback(message, type = 'info') {
  const el = document.getElementById('sam-policy-feedback');
  if (!el) return;
  el.className = `alert alert-${type} py-1 px-2 small mb-2`;
  el.textContent = message;
  el.classList.remove('d-none');
}

/**
 * Скрывает блок обратной связи формы политики SAM.
 */
function hideSamPolicyFeedback() {
  const el = document.getElementById('sam-policy-feedback');
  if (!el) return;
  el.classList.add('d-none');
  el.textContent = '';
}

/**
 * Обновляет активность полей длительности и окна сброса блокировки в зависимости от порога.
 */
function syncLockoutFieldsState() {
  const thresholdInput = document.getElementById('sam-lockout-threshold');
  const durationInput = document.getElementById('sam-lockout-duration');
  const windowInput = document.getElementById('sam-lockout-window');
  if (!thresholdInput || !durationInput || !windowInput) return;

  const threshold = parseInt(thresholdInput.value, 10) || 0;
  const disabled = threshold <= 0;
  durationInput.disabled = disabled;
  windowInput.disabled = disabled;
}

/**
 * Собирает текущие значения всех полей формы политики SAM.
 * @returns {Object} Словарь параметров политики.
 */
function readSamFormValues() {
  const numVal = (id, fallback = 0) => {
    const el = document.getElementById(id);
    if (!el) return fallback;
    const parsed = parseInt(el.value, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };
  const boolVal = (id) => {
    const el = document.getElementById(id);
    return el ? Boolean(el.checked) : false;
  };
  const strVal = (id) => {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  };

  const data = {
    min_password_length: numVal('sam-min-pw-len', 0),
    max_password_age_days: numVal('sam-max-pw-age', 42),
    min_password_age_days: numVal('sam-min-pw-age', 0),
    password_history_length: numVal('sam-pw-history', 0),
    password_complexity: boolVal('sam-pw-complexity'),
    reversible_encryption: boolVal('sam-reversible-enc'),

    lockout_threshold: numVal('sam-lockout-threshold', 0),
    lockout_duration_minutes: numVal('sam-lockout-duration', 30),
    lockout_window_minutes: numVal('sam-lockout-window', 30),
    allow_admin_lockout: boolVal('sam-allow-admin-lockout'),

    force_logoff_when_hour_expire: boolVal('sam-force-logoff'),
    require_logon_to_change_password: boolVal('sam-require-logon-chg'),
    lsa_anonymous_name_lookup: boolVal('sam-lsa-anon-lookup'),
    new_admin_name: strVal('sam-new-admin-name'),
    new_guest_name: strVal('sam-new-guest-name'),
  };

  const adminEnableEl = document.getElementById('sam-enable-admin');
  if (adminEnableEl) data.enable_admin_account = Boolean(adminEnableEl.checked);
  const guestEnableEl = document.getElementById('sam-enable-guest');
  if (guestEnableEl) data.enable_guest_account = Boolean(guestEnableEl.checked);

  return data;
}

/**
 * Вычисляет словарь только измененных полей относительно _currentSamPolicy.
 * @param {Object} formValues - Текущие значения формы.
 * @returns {Object} Словарь измененных параметров для PUT-запроса.
 */
function buildSamPatchPayload(formValues) {
  if (!_currentSamPolicy) return formValues;
  const patch = {};
  for (const [key, value] of Object.entries(formValues)) {
    const prev = _currentSamPolicy[key];
    // Если порог блокировки 0, поля длительности и окна не отправляем
    if ((key === 'lockout_duration_minutes' || key === 'lockout_window_minutes') && formValues.lockout_threshold === 0) {
      continue;
    }
    // Не отправляем пустые имена встроенных аккаунтов, если они изначально были пустыми
    if ((key === 'new_admin_name' || key === 'new_guest_name') && !value && !prev) {
      continue;
    }
    if (value !== prev) {
      patch[key] = value;
    }
  }
  return patch;
}

/**
 * Обновляет состояние кнопки «Сохранить» в зависимости от наличия изменений.
 */
function updateSamSaveButtonState() {
  const saveBtn = document.getElementById('btn-save-sam-policy');
  const dirtyBadge = document.getElementById('sam-dirty-indicator');
  if (!saveBtn) return;

  const patch = buildSamPatchPayload(readSamFormValues());
  const hasChanges = Object.keys(patch).length > 0;
  saveBtn.disabled = !hasChanges;
  if (dirtyBadge) {
    dirtyBadge.classList.toggle('d-none', !hasChanges);
  }
}

/**
 * Валидирует значения формы политики SAM перед отправкой на сервер.
 * @param {Object} values - Значения формы.
 * @returns {string|null} Сообщение об ошибке или null, если валидация пройдена.
 */
function validateSamPolicyForm(values) {
  if (values.min_password_length < 0 || values.min_password_length > 20) {
    return 'Минимальная длина пароля должна быть от 0 до 20 символов.';
  }
  if (values.max_password_age_days < 0 || values.max_password_age_days > 999) {
    return 'Максимальный срок действия пароля должен быть от 0 (бессрочно) до 999 дней.';
  }
  if (values.min_password_age_days < 0 || values.min_password_age_days > 998) {
    return 'Минимальный срок действия пароля должен быть от 0 до 998 дней.';
  }
  if (values.max_password_age_days > 0 && values.min_password_age_days >= values.max_password_age_days) {
    return `Минимальный срок действия (${values.min_password_age_days} дн.) должен быть строго меньше максимального (${values.max_password_age_days} дн.).`;
  }
  if (values.password_history_length < 0 || values.password_history_length > 24) {
    return 'Глубина истории паролей должна быть от 0 до 24.';
  }
  if (values.lockout_threshold < 0 || values.lockout_threshold > 999) {
    return 'Порог блокировки должен быть от 0 (отключено) до 999 попыток.';
  }
  if (values.lockout_threshold > 0) {
    if (values.lockout_duration_minutes < 0 || values.lockout_duration_minutes > 99999) {
      return 'Длительность блокировки должна быть от 0 (до разблокировки админом) до 99999 минут.';
    }
    if (values.lockout_window_minutes < 1 || values.lockout_window_minutes > 99999) {
      return 'Окно сброса счетчика блокировки должно быть от 1 до 99999 минут.';
    }
    if (values.lockout_duration_minutes > 0 && values.lockout_window_minutes > values.lockout_duration_minutes) {
      return `Окно сброса блокировки (${values.lockout_window_minutes} мин.) не может превышать длительность блокировки (${values.lockout_duration_minutes} мин.).`;
    }
  }
  return null;
}

/**
 * Рендерит интерактивную редактируемую форму политики SAM.
 * @param {HTMLElement} container - Контейнер #password-policy-container.
 * @param {Object} pol - Данные политики PasswordPolicy.
 */
function renderSamPolicyForm(container, pol) {
  _currentSamPolicy = { ...pol };

  const roleBadge = document.getElementById('sam-computer-role-badge');
  if (roleBadge) {
    if (pol.computer_role) {
      roleBadge.textContent = pol.computer_role;
      roleBadge.classList.remove('d-none');
    } else {
      roleBadge.classList.add('d-none');
    }
  }

  const lockoutDisabledAttr = (pol.lockout_threshold || 0) <= 0 ? 'disabled' : '';
  const hasAdminToggle = pol.enable_admin_account !== null && pol.enable_admin_account !== undefined;
  const hasGuestToggle = pol.enable_guest_account !== null && pol.enable_guest_account !== undefined;

  container.innerHTML = `
    <form id="sam-policy-form" autocomplete="off">
      <div class="d-none" id="sam-policy-feedback" role="alert"></div>

      <!-- Секция 1: Политика паролей -->
      <div class="mb-2">
        <div class="winadmin-label mb-1"><i class="bi bi-shield-lock me-1"></i>Политика паролей</div>
        <div class="row g-2">
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-min-pw-len">Мин. длина (0–20 симв.)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-min-pw-len" type="number" min="0" max="20" value="${pol.min_password_length ?? 0}"/>
          </div>
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-pw-history">История паролей (0–24)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-pw-history" type="number" min="0" max="24" value="${pol.password_history_length ?? 0}"/>
          </div>
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-max-pw-age">Макс. срок (дн., 0=∞)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-max-pw-age" type="number" min="0" max="999" value="${pol.max_password_age_days ?? 42}"/>
          </div>
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-min-pw-age">Мин. срок (0–998 дн.)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-min-pw-age" type="number" min="0" max="998" value="${pol.min_password_age_days ?? 0}"/>
          </div>
        </div>
        <div class="mt-2 d-flex flex-column gap-1">
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-pw-complexity" type="checkbox" ${pol.password_complexity ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-pw-complexity">Требования сложности пароля</label>
          </div>
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-reversible-enc" type="checkbox" ${pol.reversible_encryption ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-reversible-enc">Обратимое шифрование паролей (ClearText)</label>
          </div>
        </div>
      </div>

      <hr class="my-2 border-secondary border-opacity-25"/>

      <!-- Секция 2: Политика блокировки -->
      <div class="mb-2">
        <div class="winadmin-label mb-1"><i class="bi bi-lock-fill me-1"></i>Блокировка учетных записей</div>
        <div class="row g-2">
          <div class="col-4">
            <label class="form-label small text-muted mb-0" for="sam-lockout-threshold">Порог (0=откл.)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-lockout-threshold" type="number" min="0" max="999" value="${pol.lockout_threshold ?? 0}"/>
          </div>
          <div class="col-4">
            <label class="form-label small text-muted mb-0" for="sam-lockout-duration">Длит. (мин., 0=∞)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-lockout-duration" type="number" min="0" max="99999" value="${pol.lockout_duration_minutes ?? 30}" ${lockoutDisabledAttr}/>
          </div>
          <div class="col-4">
            <label class="form-label small text-muted mb-0" for="sam-lockout-window">Сброс (мин.)</label>
            <input class="form-control form-control-sm font-monospace" id="sam-lockout-window" type="number" min="1" max="99999" value="${pol.lockout_window_minutes ?? 30}" ${lockoutDisabledAttr}/>
          </div>
        </div>
        <div class="form-check form-switch mt-2 mb-0">
          <input class="form-check-input" id="sam-allow-admin-lockout" type="checkbox" ${pol.allow_admin_lockout ? 'checked' : ''}/>
          <label class="form-check-label text-body" for="sam-allow-admin-lockout">Блокировка встроенного Администратора</label>
        </div>
      </div>

      <hr class="my-2 border-secondary border-opacity-25"/>

      <!-- Секция 3: Системный доступ и встроенные аккаунты SAM -->
      <div class="mb-2">
        <div class="winadmin-label mb-1"><i class="bi bi-person-gear me-1"></i>Системный доступ SAM</div>
        <div class="d-flex flex-column gap-1 mb-2">
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-force-logoff" type="checkbox" ${pol.force_logoff_when_hour_expire ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-force-logoff">Принудительный выход по истечении часов входа</label>
          </div>
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-require-logon-chg" type="checkbox" ${pol.require_logon_to_change_password ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-require-logon-chg">Требовать вход для смены пароля</label>
          </div>
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-lsa-anon-lookup" type="checkbox" ${pol.lsa_anonymous_name_lookup ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-lsa-anon-lookup">Анонимный поиск SID/имен (LSA)</label>
          </div>
          ${hasAdminToggle ? `
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-enable-admin" type="checkbox" ${pol.enable_admin_account ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-enable-admin">Встроенный Администратор включен</label>
          </div>` : ''}
          ${hasGuestToggle ? `
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" id="sam-enable-guest" type="checkbox" ${pol.enable_guest_account ? 'checked' : ''}/>
            <label class="form-check-label text-body" for="sam-enable-guest">Встроенный Гость включен</label>
          </div>` : ''}
        </div>
        <div class="row g-2">
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-new-admin-name">Имя Администратора</label>
            <input class="form-control form-control-sm font-monospace" id="sam-new-admin-name" type="text" maxlength="20" value="${escapeHtml(pol.new_admin_name || '')}" placeholder="Administrator"/>
          </div>
          <div class="col-6">
            <label class="form-label small text-muted mb-0" for="sam-new-guest-name">Имя Гостя</label>
            <input class="form-control form-control-sm font-monospace" id="sam-new-guest-name" type="text" maxlength="20" value="${escapeHtml(pol.new_guest_name || '')}" placeholder="Guest"/>
          </div>
        </div>
      </div>

      <!-- Панель действий -->
      <div class="d-flex justify-content-between align-items-center gap-2 pt-2 mt-2 border-top border-secondary border-opacity-25">
        <span class="ui-badge ui-badge-warning small d-none" id="sam-dirty-indicator">Есть изменения</span>
        <div class="d-flex gap-2 ms-auto">
          <button class="btn btn-sm btn-outline-secondary" id="btn-reset-sam-policy" type="button">Сбросить</button>
          <button class="btn btn-sm btn-primary d-inline-flex align-items-center gap-1" id="btn-save-sam-policy" type="submit" disabled>
            <i class="bi bi-check2-circle"></i>
            <span>Сохранить</span>
          </button>
        </div>
      </div>
    </form>
  `;

  const form = document.getElementById('sam-policy-form');
  if (form) {
    form.addEventListener('input', () => {
      syncLockoutFieldsState();
      updateSamSaveButtonState();
    });
    form.addEventListener('change', () => {
      syncLockoutFieldsState();
      updateSamSaveButtonState();
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await savePasswordPolicy();
    });
  }

  const resetBtn = document.getElementById('btn-reset-sam-policy');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (_currentSamPolicy) {
        renderSamPolicyForm(container, _currentSamPolicy);
      } else {
        loadPasswordPolicy();
      }
    });
  }
}

/**
 * Сохраняет измененные параметры политики безопасности SAM через REST API.
 */
export async function savePasswordPolicy() {
  hideSamPolicyFeedback();
  const values = readSamFormValues();
  const validationError = validateSamPolicyForm(values);
  if (validationError) {
    showSamPolicyFeedback(validationError, 'warning');
    return;
  }

  const payload = buildSamPatchPayload(values);
  if (Object.keys(payload).length === 0) {
    showSamPolicyFeedback('Изменений нет — политика актуальна.', 'info');
    return;
  }

  const saveBtn = document.getElementById('btn-save-sam-policy');
  const prevHtml = saveBtn ? saveBtn.innerHTML : '';
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сохранение...';
  }

  try {
    const resp = await safeApiFetch('/api/v1/windows/identity/auth/policies', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    const container = document.getElementById('password-policy-container');
    if (container && resp && resp.policy) {
      renderSamPolicyForm(container, resp.policy);
    }
    showSamPolicyFeedback(resp?.message || 'Политика безопасности SAM успешно обновлена.', 'success');
  } catch (err) {
    showSamPolicyFeedback(`Ошибка сохранения политики SAM: ${err.message}`, 'danger');
    if (saveBtn) {
      saveBtn.innerHTML = prevHtml;
      updateSamSaveButtonState();
    }
  }
}

/**
 * Загрузка и отображение редактируемой локальной политики безопасности SAM.
 */
export async function loadPasswordPolicy() {
  const container = document.getElementById('password-policy-container');
  if (!container) return;
  container.innerHTML = '<div class="text-muted">Загрузка политики безопасности SAM...</div>';
  try {
    const pol = await safeApiFetch('/api/v1/windows/identity/auth/policies');
    renderSamPolicyForm(container, pol);
  } catch (err) {
    container.innerHTML = `<div class="text-danger">Ошибка загрузки политики SAM: ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Экспресс-аудит: Who is Admin? (Прямой и вложенный административный доступ).
 */
export async function runWhoIsAdminCheck() {
  const outputEl = document.getElementById('security-audit-results');
  if (outputEl) outputEl.innerHTML = '<div class="text-muted text-center py-3">Анализ администраторов системы...</div>';
  try {
    const admins = await safeApiFetch('/api/v1/windows/identity/who-is-admin');
    if (!admins || admins.length === 0) {
      if (outputEl) outputEl.innerHTML = '<div>Администраторы не найдены</div>';
      return;
    }
    const html = admins.map(a => `
      <div class="mb-2 pb-1 border-bottom border-secondary">
        <div class="fw-bold text-danger"><i class="bi bi-shield-lock-fill me-1"></i> ${escapeHtml(a.username)} <span class="ui-badge ui-badge-neutral">${a.is_direct ? 'Прямой доступ' : 'Вложенное членство'}</span></div>
        <div class="small text-muted font-monospace">SID: ${escapeHtml(a.sid)}</div>
        <div class="small text-primary">Цепочка: ${(a.path_to_admin || []).map(escapeHtml).join(' → ')}</div>
      </div>
    `).join('');
    if (outputEl) outputEl.innerHTML = html;
  } catch (err) {
    if (outputEl) outputEl.innerHTML = `<div class="text-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Экспресс-аудит: Учетные записи с правом входа в качестве службы (SeServiceLogonRight).
 */
export async function runServiceLogonCheck() {
  const outputEl = document.getElementById('security-audit-results');
  if (outputEl) outputEl.innerHTML = '<div class="text-muted text-center py-3">Поиск аккаунтов с SeServiceLogonRight...</div>';
  try {
    const list = await safeApiFetch('/api/v1/windows/identity/who-can-logon-as-service');
    if (!list || list.length === 0) {
      if (outputEl) outputEl.innerHTML = '<div class="text-success">Специфических сервисных учетных записей не назначено.</div>';
      return;
    }
    const html = `<h6>Аккаунты с правом SeServiceLogonRight:</h6>` + list.map(a => `<div class="font-monospace text-primary mb-1">• ${escapeHtml(a)}</div>`).join('');
    if (outputEl) outputEl.innerHTML = html;
  } catch (err) {
    if (outputEl) outputEl.innerHTML = `<div class="text-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Экспресс-аудит: Доступ к удаленному рабочему столу (RDP).
 */
export async function runRdpCheck() {
  const outputEl = document.getElementById('security-audit-results');
  if (outputEl) outputEl.innerHTML = '<div class="text-muted text-center py-3">Поиск аккаунтов с доступом к RDP...</div>';
  try {
    const list = await safeApiFetch('/api/v1/windows/identity/who-can-rdp');
    const html = `<h6>Аккаунты и группы с доступом к Remote Desktop:</h6>` + list.map(a => `<div class="font-monospace text-warning mb-1">• ${escapeHtml(a)}</div>`).join('');
    if (outputEl) outputEl.innerHTML = html;
  } catch (err) {
    if (outputEl) outputEl.innerHTML = `<div class="text-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Экспресс-аудит: Поиск осиротевших SID в реестре и профилей без учетных записей.
 */
export async function runOrphanedCheck() {
  const outputEl = document.getElementById('security-audit-results');
  if (outputEl) outputEl.innerHTML = '<div class="text-muted text-center py-3">Поиск осиротевших SID и профилей...</div>';
  try {
    const [sids, profiles] = await Promise.all([
      safeApiFetch('/api/v1/windows/identity/orphaned-sids'),
      safeApiFetch('/api/v1/windows/identity/orphaned-profiles'),
    ]);

    if ((!sids || sids.length === 0) && (!profiles || profiles.length === 0)) {
      if (outputEl) outputEl.innerHTML = '<div class="text-success"><i class="bi bi-check-circle-fill me-1"></i> Осиротевших SID и профилей в системе не обнаружено.</div>';
      return;
    }

    let html = '<h6>Осиротевшие субъекты:</h6>';
    for (const s of sids) {
      html += `<div class="text-danger font-monospace mb-1">⚠️ SID: ${escapeHtml(s.sid)} (${escapeHtml(s.location)})</div>`;
    }
    for (const p of profiles) {
      html += `<div class="text-warning font-monospace mb-1">📁 Профиль без пользователя: ${escapeHtml(p.profile_path)} (SID: ${escapeHtml(p.sid)})</div>`;
    }
    if (outputEl) outputEl.innerHTML = html;
  } catch (err) {
    if (outputEl) outputEl.innerHTML = `<div class="text-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}
