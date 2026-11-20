/**
 * =============================================================================
 * Process Name: Windows Network Terminal - Remote Computer Login Modal
 * =============================================================================
 * Description:
 *   Модальное окно удалённого входа на обнаруженный в локальной сети компьютер.
 *   Открывается по правому клику мыши (ПКМ) на строке таблицы устройств LAN.
 *   Запрашивает имя пользователя, пароль и протокол (Авто / SMB / WinRM),
 *   отправляет запрос на /api/v1/network/devices/login и отображает результат.
 *
 * File: remote_login_modal.js
 * Package: apps/windows/api/webgui/tab_network/panel_discovery
 * Updated: 2026-11-20 17:17:00
 * =============================================================================
 */

const MODAL_ID = 'net-remote-login-modal';
const authenticatedDevicesMap = new Map();
let currentDevice = null;
let onLoginSuccessCallback = null;

/**
 * Экранирует HTML-символы для безопасного рендеринга.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Возвращает карту устройств с успешной авторизацией в текущей сессии.
 * @returns {Map<string, Object>}
 */
export function getAuthenticatedDevicesMap() {
  return authenticatedDevicesMap;
}

/**
 * Создаёт DOM-разметку модального окна удалённого входа, если она ещё не существует.
 * @returns {HTMLElement}
 */
function ensureModalElement() {
  let modalEl = document.getElementById(MODAL_ID);
  if (modalEl) return modalEl;

  modalEl = document.createElement('div');
  modalEl.id = MODAL_ID;
  modalEl.className = 'modal fade';
  modalEl.tabIndex = -1;
  modalEl.setAttribute('aria-hidden', 'true');
  modalEl.innerHTML = `
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content border" style="background: var(--surface-1); color: var(--text-color); border-color: var(--border-color) !important;">
        <div class="modal-header py-2.5 border-bottom" style="border-color: var(--border-color) !important;">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-key-fill text-primary fs-5"></i>
            <div>
              <h6 class="modal-title mb-0 fw-bold">Вход на удалённый компьютер</h6>
              <small class="text-muted font-monospace" id="net-remote-login-target">—</small>
            </div>
          </div>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
        </div>
        <form id="net-remote-login-form" autocomplete="off">
          <div class="modal-body">
            <div class="p-2 rounded mb-3 small border d-flex justify-content-between align-items-center flex-wrap gap-1" style="background: var(--surface-2); border-color: var(--border-color) !important;">
              <span><i class="bi bi-pc-display me-1 text-info"></i><strong id="net-remote-login-hostname">—</strong></span>
              <span class="badge bg-info-subtle text-info border border-info font-monospace" id="net-remote-login-ip">—</span>
            </div>

            <div class="mb-3">
              <label for="net-remote-login-username" class="form-label small fw-semibold mb-1">Имя пользователя</label>
              <input
                type="text"
                class="form-control form-control-sm"
                id="net-remote-login-username"
                placeholder="Administrator или DOMAIN\\User"
                required
              />
            </div>

            <div class="mb-3">
              <label for="net-remote-login-password" class="form-label small fw-semibold mb-1">Пароль</label>
              <div class="input-group input-group-sm">
                <input
                  type="password"
                  class="form-control"
                  id="net-remote-login-password"
                  placeholder="Введите пароль учётной записи"
                />
                <button class="btn btn-outline-secondary" type="button" id="btn-toggle-remote-pass" title="Показать / скрыть пароль">
                  <i class="bi bi-eye"></i>
                </button>
              </div>
            </div>

            <div class="mb-3">
              <label for="net-remote-login-protocol" class="form-label small fw-semibold mb-1">Протокол подключения</label>
              <select class="form-select form-select-sm" id="net-remote-login-protocol">
                <option value="auto" selected>Авто (SMB 445 + WinRM 5985)</option>
                <option value="smb">SMB (Windows IPC$ / порт 445)</option>
                <option value="winrm">WinRM (PowerShell Remoting / порт 5985)</option>
              </select>
            </div>

            <div id="net-remote-login-result" class="d-none"></div>
          </div>
          <div class="modal-footer py-2 border-top" style="border-color: var(--border-color) !important;">
            <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-3" data-bs-dismiss="modal">Отмена</button>
            <button type="submit" class="btn btn-sm btn-primary rounded-pill px-4 fw-semibold" id="btn-submit-remote-login">
              <i class="bi bi-box-arrow-in-right me-1"></i>Войти
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.appendChild(modalEl);

  const togglePassBtn = modalEl.querySelector('#btn-toggle-remote-pass');
  const passInput = modalEl.querySelector('#net-remote-login-password');
  if (togglePassBtn && passInput) {
    togglePassBtn.onclick = () => {
      const isHidden = passInput.type === 'password';
      passInput.type = isHidden ? 'text' : 'password';
      togglePassBtn.innerHTML = isHidden ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    };
  }

  const form = modalEl.querySelector('#net-remote-login-form');
  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      await submitRemoteLogin(modalEl);
    };
  }

  modalEl.addEventListener('shown.bs.modal', () => {
    const userInput = modalEl.querySelector('#net-remote-login-username');
    userInput?.focus();
  });

  return modalEl;
}

/**
 * Отправляет запрос на аутентификацию к удалённому компьютеру.
 * @param {HTMLElement} modalEl
 */
async function submitRemoteLogin(modalEl) {
  if (!currentDevice?.ip) return;

  const userInput = modalEl.querySelector('#net-remote-login-username');
  const passInput = modalEl.querySelector('#net-remote-login-password');
  const protoSelect = modalEl.querySelector('#net-remote-login-protocol');
  const submitBtn = modalEl.querySelector('#btn-submit-remote-login');
  const resultBox = modalEl.querySelector('#net-remote-login-result');

  const username = (userInput?.value || '').trim();
  const password = passInput?.value || '';
  const protocol = protoSelect?.value || 'auto';

  if (!username) {
    if (resultBox) {
      resultBox.className = 'alert alert-warning py-2 px-3 small mb-0';
      resultBox.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Укажите имя пользователя.';
    }
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выполняется вход...';
  }
  if (resultBox) {
    resultBox.className = 'alert alert-info py-2 px-3 small mb-0';
    resultBox.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Подключение к <strong>${escapeHtml(currentDevice.ip)}</strong>...`;
  }

  try {
    const res = await fetch('/api/v1/network/devices/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip: currentDevice.ip,
        username,
        password,
        protocol,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    if (data.success) {
      authenticatedDevicesMap.set(currentDevice.ip, {
        username: data.username,
        protocol: data.protocol_used,
        details: data.details || {},
        timestamp: Date.now(),
      });

      const detailsParts = [];
      if (data.protocol_used) {
        detailsParts.push(`Протокол: <strong>${escapeHtml(String(data.protocol_used).toUpperCase())}</strong>`);
      }
      if (data.latency_ms !== undefined) {
        detailsParts.push(`Отклик: <strong>${escapeHtml(String(data.latency_ms))} мс</strong>`);
      }
      if (data.details?.computer) {
        detailsParts.push(`ПК: <strong>${escapeHtml(data.details.computer)}</strong>`);
      }
      if (data.details?.os) {
        detailsParts.push(`ОС: <strong>${escapeHtml(data.details.os)}</strong>`);
      }

      let sharesHtml = '';
      if (Array.isArray(data.details?.shares) && data.details.shares.length > 0) {
        const badges = data.details.shares
          .map((s) => `<span class="badge bg-body-secondary border text-body font-monospace me-1 mb-1">${escapeHtml(s)}</span>`)
          .join('');
        sharesHtml = `<div class="mt-2 pt-2 border-top"><div class="fw-semibold mb-1">Доступные общие ресурсы (${data.details.shares.length}):</div><div>${badges}</div></div>`;
      }

      if (resultBox) {
        resultBox.className = 'alert alert-success py-2 px-3 small mb-0';
        resultBox.innerHTML = `
          <div class="fw-bold"><i class="bi bi-check-circle-fill me-1"></i>${escapeHtml(data.message)}</div>
          <div class="mt-1">${detailsParts.join(' · ')}</div>
          ${sharesHtml}
        `;
      }

      window.showToast?.(`Успешный вход на ${currentDevice.ip} (${data.username})`, 'success');
      if (typeof onLoginSuccessCallback === 'function') {
        onLoginSuccessCallback(currentDevice.ip, data);
      }
    } else {
      const codeStr = data.error_code !== null && data.error_code !== undefined
        ? ` <span class="badge bg-danger-subtle text-danger border border-danger ms-1">Код: ${escapeHtml(String(data.error_code))}</span>`
        : '';
      if (resultBox) {
        resultBox.className = 'alert alert-danger py-2 px-3 small mb-0';
        resultBox.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>${escapeHtml(data.message || 'Не удалось выполнить вход')}${codeStr}`;
      }
      window.showToast?.(`Ошибка входа на ${currentDevice.ip}: ${data.message || 'отказано'}`, 'danger');
    }
  } catch (err) {
    console.error('[LAN Remote Login] Ошибка запроса входа:', err);
    if (resultBox) {
      resultBox.className = 'alert alert-danger py-2 px-3 small mb-0';
      resultBox.innerHTML = `<i class="bi bi-exclamation-octagon-fill me-1"></i>Ошибка соединения с сервером: ${escapeHtml(err.message)}`;
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-box-arrow-in-right me-1"></i>Войти';
    }
  }
}

/**
 * Открывает модальное окно удалённого входа для выбранного устройства.
 * @param {Object} device - Объект устройства из списка обнаруженных хостов.
 * @param {Function} [onSuccess] - Колбэк при успешной аутентификации.
 */
export function openRemoteLoginModal(device, onSuccess) {
  if (!device?.ip) return;

  currentDevice = device;
  onLoginSuccessCallback = typeof onSuccess === 'function' ? onSuccess : null;

  const modalEl = ensureModalElement();
  const targetEl = modalEl.querySelector('#net-remote-login-target');
  const hostEl = modalEl.querySelector('#net-remote-login-hostname');
  const ipEl = modalEl.querySelector('#net-remote-login-ip');
  const userInput = modalEl.querySelector('#net-remote-login-username');
  const passInput = modalEl.querySelector('#net-remote-login-password');
  const resultBox = modalEl.querySelector('#net-remote-login-result');

  const displayName = device.hostname || device.ip;
  if (targetEl) targetEl.textContent = `${displayName} (${device.ip})`;
  if (hostEl) hostEl.textContent = displayName;
  if (ipEl) ipEl.textContent = device.ip;

  const prevAuth = authenticatedDevicesMap.get(device.ip);
  if (userInput) userInput.value = prevAuth?.username || '';
  if (passInput) {
    passInput.value = '';
    passInput.type = 'password';
  }
  const togglePassBtn = modalEl.querySelector('#btn-toggle-remote-pass');
  if (togglePassBtn) togglePassBtn.innerHTML = '<i class="bi bi-eye"></i>';

  if (resultBox) {
    if (prevAuth) {
      resultBox.className = 'alert alert-success py-2 px-3 small mb-0';
      resultBox.innerHTML = `<i class="bi bi-shield-check me-1"></i>Ранее выполнен вход под пользователем <strong>${escapeHtml(prevAuth.username)}</strong> (${escapeHtml(String(prevAuth.protocol || '').toUpperCase())}).`;
    } else {
      resultBox.className = 'd-none';
      resultBox.innerHTML = '';
    }
  }

  if (window.bootstrap?.Modal) {
    const instance = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    instance.show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}
