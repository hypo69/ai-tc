/**
 * =============================================================================
 * Process Name: Common WebGUI - User Settings Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля userSettings.
 *   Обеспечивает синхронизацию профиля Google OAuth, выбор языка локализации,
 *   выбор темы оформления, динамическую инициализацию модального окна настроек
 *   #userSettingsModal, быстрые пользовательские действия, а также настройку
 *   и тестирование сетевых соединений (Hostinger MariaDB, SQLite, FTP, SSH, SMTP, IMAP).
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/js/userSettings.js?v=20261103_v2" type="module"></script>
 *
 *   JavaScript Import:
 *     import { initUserSettings, ensureUserSettingsModal, executeUserAction, isUserAdmin } from '/html/js/userSettings.js';
 *
 * File: userSettings.js
 * Project: ai-assistant
 * Package: apps.common.webgui.js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 16:38:00
 * =============================================================================
 */

'use strict';

/**
 * Гарантирует наличие модального окна #userSettingsModal в DOM-дереве документа.
 * Если окно отсутствует, загружает компонент user_settings_modal.html.
 * @returns {Promise<HTMLElement|null>} Элемент модального окна
 */
export async function ensureUserSettingsModal() {
  const existing = document.getElementById('userSettingsModal');
  if (existing) {
    return existing;
  }
  try {
    const res = await fetch('/html/components/user_settings_modal.html');
    if (res.ok) {
      const html = await res.text();
      const div = document.createElement('div');
      div.innerHTML = html;
      const modalEl = div.querySelector('#userSettingsModal');
      if (modalEl) {
        document.body.appendChild(modalEl);
        if (window.i18n && typeof window.i18n.translatePage === 'function') {
          window.i18n.translatePage();
        }
        return modalEl;
      }
    }
  } catch (err) {
    console.warn('[userSettings] Could not dynamically load user_settings_modal.html:', err);
  }
  return null;
}

export function executeUserAction(actionType) {
  // Ensure chat tab is active
  if (typeof window.switchToTab === 'function') {
    window.switchToTab('chat');
  } else if (typeof window.switchTab === 'function') {
    window.switchTab('tab-chat');
  } else {
    const chatTabBtn = document.querySelector('[data-bs-target="#tab-chat"], [data-tab="tab-chat"]');
    if (chatTabBtn && window.bootstrap?.Tab) {
      bootstrap.Tab.getOrCreateInstance(chatTabBtn).show();
    }
  }

  const msgInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-button');

  const send = () => {
    if (typeof window.sendChatMessage === 'function') {
      window.sendChatMessage();
    } else if (sendBtn) {
      sendBtn.click();
    }
  };

  if (actionType === 'mail') {
    if (msgInput) {
      msgInput.value = 'Проверь мою почту Gmail и покажи последние непрочитанные письма.';
      setTimeout(send, 100);
    }
  } else if (actionType === 'docs') {
    const query = prompt('Введите поисковый запрос для поиска документов в Google Docs / Drive:');
    if (query && query.trim() && msgInput) {
      msgInput.value = `Найди в Google Docs / Google Drive документы по запросу: "${query.trim()}".`;
      setTimeout(send, 100);
    }
  } else if (actionType === 'sheets') {
    const query = prompt('Введите ID таблицы или команду для Google Sheets:');
    if (query && query.trim() && msgInput) {
      msgInput.value = `Google Sheets: ${query.trim()}`;
      setTimeout(send, 100);
    }
  } else if (actionType === 'news') {
    if (msgInput) {
      msgInput.value = 'Покажи свежие новости и краткий дайджест.';
      setTimeout(send, 100);
    }
  } else if (actionType === 'facebook') {
    if (msgInput) {
      msgInput.value = 'Сформируй черновик публикации для социальных сетей.';
      setTimeout(send, 100);
    }
  }
}

/**
 * Закрывает модальное окно настроек пользователя и выполняет переход на вкладку каталога моделей.
 */
export function openModelsTab() {
  const modalEl = document.getElementById('userSettingsModal');
  if (modalEl && window.bootstrap && typeof window.bootstrap.Modal === 'function') {
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) {
      modalInstance.hide();
    }
  }
  if (typeof window.switchTab === 'function') {
    window.switchTab('tab-models');
  } else if (typeof window.switchToTab === 'function') {
    window.switchToTab('tab-models');
  }
}

/**
 * Опрашивает сервер и обновляет бейдж активной модели ИИ в модальном окне настроек.
 * @returns {Promise<void>}
 */
export async function refreshActiveModelBadge() {
  try {
    let modelName = 'gemini-2.5-flash';
    try {
      const res = await fetch('/api/v1/chat/active-model');
      if (res.ok) {
        const data = await res.json();
        if (data.model_name) modelName = data.model_name;
      }
    } catch (_) {
      try {
        const authRes = await fetch('/auth/settings');
        if (authRes.ok) {
          const authData = await authRes.json();
          if (authData.model_name) modelName = authData.model_name;
        }
      } catch (__) {}
    }

    const displayName = modelName.includes(':') ? modelName.split(':')[1] : modelName;

    document.querySelectorAll('#user-settings-active-model-name, .user-settings-model-val, #modal-header-active-model-name').forEach((el) => {
      el.textContent = displayName;
    });
    document.querySelectorAll('#user-settings-active-model-badge, .user-settings-model-badge, #user-settings-active-model-badge-top').forEach((badge) => {
      badge.setAttribute('title', `Активная модель: ${modelName} (нажмите для выбора)`);
    });
  } catch (err) {
    console.warn('[userSettings] Could not refresh active model badge:', err);
  }
}

/**
 * Загружает конфигурацию сетевых подключений из бэкенда и заполняет поля формы.
 * @returns {Promise<void>}
 */
export async function loadConnectionsSettings() {
  try {
    const res = await fetch('/api/v1/connections/config');
    if (!res.ok) return;
    const cfg = await res.json();

    // 1. Hostinger & MariaDB
    const h = cfg.hostinger_mariadb || {};
    const engineSel = document.getElementById('conn-db-engine');
    if (engineSel) engineSel.value = h.connection_type === 'php_api' ? 'hostinger' : (h.enabled ? 'mariadb' : 'sqlite');
    if (document.getElementById('conn-hostinger-host')) document.getElementById('conn-hostinger-host').value = h.host || 'srv1502.hstgr.io';
    if (document.getElementById('conn-hostinger-port')) document.getElementById('conn-hostinger-port').value = h.port || 3306;
    if (document.getElementById('conn-hostinger-db')) document.getElementById('conn-hostinger-db').value = h.database || 'u177424397_comp_knowledge';
    if (document.getElementById('conn-hostinger-user')) document.getElementById('conn-hostinger-user').value = h.user || 'u177424397_davidka';
    if (document.getElementById('conn-hostinger-pass')) document.getElementById('conn-hostinger-pass').value = h.password || '@Davidka#1969';
    if (document.getElementById('conn-hostinger-fallback-ip')) document.getElementById('conn-hostinger-fallback-ip').value = h.ip_fallback || '77.37.35.16';
    if (document.getElementById('conn-hostinger-api-url')) document.getElementById('conn-hostinger-api-url').value = h.php_api_url || 'https://srv1502.hstgr.io/wikillm_hostinger.php';

    // 2. SQLite
    const sq = cfg.sqlite || {};
    if (document.getElementById('conn-sqlite-path')) document.getElementById('conn-sqlite-path').value = sq.path || 'data/ai_instruments/ai_instruments.db';

    // 3. FTP
    const f = cfg.ftp || {};
    if (document.getElementById('conn-ftp-protocol')) document.getElementById('conn-ftp-protocol').value = f.protocol || 'ftp';
    if (document.getElementById('conn-ftp-host')) document.getElementById('conn-ftp-host').value = f.host || '';
    if (document.getElementById('conn-ftp-port')) document.getElementById('conn-ftp-port').value = f.port || 21;
    if (document.getElementById('conn-ftp-user')) document.getElementById('conn-ftp-user').value = f.username || '';
    if (document.getElementById('conn-ftp-pass')) document.getElementById('conn-ftp-pass').value = f.password || '';
    if (document.getElementById('conn-ftp-remote-dir')) document.getElementById('conn-ftp-remote-dir').value = f.remote_dir || '/';

    // 4. SSH
    const s = cfg.ssh || {};
    if (document.getElementById('conn-ssh-host')) document.getElementById('conn-ssh-host').value = s.host || '';
    if (document.getElementById('conn-ssh-port')) document.getElementById('conn-ssh-port').value = s.port || 22;
    if (document.getElementById('conn-ssh-user')) document.getElementById('conn-ssh-user').value = s.username || 'root';
    if (document.getElementById('conn-ssh-auth-type')) document.getElementById('conn-ssh-auth-type').value = s.auth_type || 'password';
    if (document.getElementById('conn-ssh-pass')) document.getElementById('conn-ssh-pass').value = s.password || '';
    if (document.getElementById('conn-ssh-key-path')) document.getElementById('conn-ssh-key-path').value = s.key_path || '';

    // 5. Mail (SMTP / IMAP)
    const sm = cfg.smtp || {};
    const im = cfg.imap || {};
    if (document.getElementById('conn-smtp-host')) document.getElementById('conn-smtp-host').value = sm.host || 'smtp.gmail.com';
    if (document.getElementById('conn-smtp-port')) document.getElementById('conn-smtp-port').value = sm.port || 587;
    if (document.getElementById('conn-imap-host')) document.getElementById('conn-imap-host').value = im.host || 'imap.gmail.com';
    if (document.getElementById('conn-imap-port')) document.getElementById('conn-imap-port').value = im.port || 993;
    if (document.getElementById('conn-mail-user')) document.getElementById('conn-mail-user').value = sm.username || im.username || '';
    if (document.getElementById('conn-mail-pass')) document.getElementById('conn-mail-pass').value = sm.password || im.password || '';
  } catch (err) {
    console.warn('[userSettings] Не удалось загрузить конфигурацию подключений:', err);
  }
}

/**
 * Сохраняет конфигурацию всех сетевых подключений на сервере.
 * @returns {Promise<boolean>}
 */
export async function saveConnectionsSettings() {
  const feedbackEl = document.getElementById('conn-save-feedback');
  const getT = (k, fb) => (typeof window !== 'undefined' && window.i18next?.t(k)) || fb;

  const engine = document.getElementById('conn-db-engine')?.value || 'mariadb';
  const payload = {
    hostinger_mariadb: {
      enabled: engine !== 'sqlite',
      connection_type: engine === 'hostinger' ? 'php_api' : 'direct',
      host: document.getElementById('conn-hostinger-host')?.value || 'srv1502.hstgr.io',
      port: parseInt(document.getElementById('conn-hostinger-port')?.value || '3306', 10),
      database: document.getElementById('conn-hostinger-db')?.value || 'u177424397_comp_knowledge',
      user: document.getElementById('conn-hostinger-user')?.value || 'u177424397_davidka',
      password: document.getElementById('conn-hostinger-pass')?.value || '',
      ip_fallback: document.getElementById('conn-hostinger-fallback-ip')?.value || '77.37.35.16',
      php_api_url: document.getElementById('conn-hostinger-api-url')?.value || 'https://srv1502.hstgr.io/wikillm_hostinger.php',
    },
    sqlite: {
      path: document.getElementById('conn-sqlite-path')?.value || 'data/ai_instruments/ai_instruments.db',
    },
    ftp: {
      protocol: document.getElementById('conn-ftp-protocol')?.value || 'ftp',
      host: document.getElementById('conn-ftp-host')?.value || '',
      port: parseInt(document.getElementById('conn-ftp-port')?.value || '21', 10),
      username: document.getElementById('conn-ftp-user')?.value || '',
      password: document.getElementById('conn-ftp-pass')?.value || '',
      remote_dir: document.getElementById('conn-ftp-remote-dir')?.value || '/',
      enabled: Boolean(document.getElementById('conn-ftp-host')?.value),
    },
    ssh: {
      host: document.getElementById('conn-ssh-host')?.value || '',
      port: parseInt(document.getElementById('conn-ssh-port')?.value || '22', 10),
      username: document.getElementById('conn-ssh-user')?.value || 'root',
      auth_type: document.getElementById('conn-ssh-auth-type')?.value || 'password',
      password: document.getElementById('conn-ssh-pass')?.value || '',
      key_path: document.getElementById('conn-ssh-key-path')?.value || '',
      enabled: Boolean(document.getElementById('conn-ssh-host')?.value),
    },
    smtp: {
      host: document.getElementById('conn-smtp-host')?.value || 'smtp.gmail.com',
      port: parseInt(document.getElementById('conn-smtp-port')?.value || '587', 10),
      username: document.getElementById('conn-mail-user')?.value || '',
      password: document.getElementById('conn-mail-pass')?.value || '',
      use_tls: true,
      enabled: Boolean(document.getElementById('conn-smtp-host')?.value),
    },
    imap: {
      host: document.getElementById('conn-imap-host')?.value || 'imap.gmail.com',
      port: parseInt(document.getElementById('conn-imap-port')?.value || '993', 10),
      username: document.getElementById('conn-mail-user')?.value || '',
      password: document.getElementById('conn-mail-pass')?.value || '',
      use_ssl: true,
      enabled: Boolean(document.getElementById('conn-imap-host')?.value),
    },
  };

  try {
    const res = await fetch('/api/v1/connections/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      if (feedbackEl) {
        feedbackEl.className = 'small text-success';
        feedbackEl.textContent = getT('userSettings.connSavedSuccess', 'Настройки подключений успешно сохранены!');
      }
      return true;
    } else {
      throw new Error(`Статус ${res.status}`);
    }
  } catch (err) {
    if (feedbackEl) {
      feedbackEl.className = 'small text-danger';
      feedbackEl.textContent = `${getT('userSettings.connSaveError', 'Ошибка сохранения:')} ${err.message}`;
    }
    return false;
  }
}

/**
 * Тестирует выбранное подключение через эндпоинт /api/v1/connections/test.
 * @param {string} serviceType - 'hostinger_mariadb', 'ftp', 'ssh', 'smtp', 'imap'
 * @param {HTMLElement} badgeEl - элемент бейджа для отображения результата
 */
export async function testConnectionAction(serviceType, badgeEl) {
  if (!badgeEl) return;
  const getT = (k, fb) => (typeof window !== 'undefined' && window.i18next?.t(k)) || fb;
  badgeEl.className = 'badge bg-warning-subtle text-warning border border-warning-subtle font-size-75';
  badgeEl.textContent = getT('userSettings.connTesting', 'Проверка...');

  let config = {};
  if (serviceType === 'hostinger_mariadb') {
    config = {
      host: document.getElementById('conn-hostinger-host')?.value || 'srv1502.hstgr.io',
      port: parseInt(document.getElementById('conn-hostinger-port')?.value || '3306', 10),
      database: document.getElementById('conn-hostinger-db')?.value || 'u177424397_comp_knowledge',
      user: document.getElementById('conn-hostinger-user')?.value || 'u177424397_davidka',
      password: document.getElementById('conn-hostinger-pass')?.value || '',
      ip_fallback: document.getElementById('conn-hostinger-fallback-ip')?.value || '77.37.35.16',
    };
  } else if (serviceType === 'ftp') {
    config = {
      host: document.getElementById('conn-ftp-host')?.value || '',
      port: parseInt(document.getElementById('conn-ftp-port')?.value || '21', 10),
      username: document.getElementById('conn-ftp-user')?.value || '',
      password: document.getElementById('conn-ftp-pass')?.value || '',
    };
  } else if (serviceType === 'ssh') {
    config = {
      host: document.getElementById('conn-ssh-host')?.value || '',
      port: parseInt(document.getElementById('conn-ssh-port')?.value || '22', 10),
      username: document.getElementById('conn-ssh-user')?.value || '',
      password: document.getElementById('conn-ssh-pass')?.value || '',
    };
  } else if (serviceType === 'smtp') {
    config = {
      host: document.getElementById('conn-smtp-host')?.value || 'smtp.gmail.com',
      port: parseInt(document.getElementById('conn-smtp-port')?.value || '587', 10),
    };
  }

  try {
    const res = await fetch('/api/v1/connections/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_type: serviceType, config }),
    });
    const data = await res.json();
    if (data.success) {
      badgeEl.className = 'badge bg-success-subtle text-success border border-success-subtle font-size-75';
      badgeEl.textContent = `OK (${data.latency_ms} ms)`;
    } else {
      badgeEl.className = 'badge bg-danger-subtle text-danger border border-danger-subtle font-size-75';
      badgeEl.textContent = `Сбой: ${data.error ? data.error.slice(0, 30) : 'Ошибка'}`;
    }
  } catch (err) {
    badgeEl.className = 'badge bg-danger-subtle text-danger border border-danger-subtle font-size-75';
    badgeEl.textContent = 'Ошибка сети';
  }
}

/**
 * Привязывает обработчики событий вкладки сетевых подключений.
 */
export function bindConnectionsEvents() {
  const btnTestDb = document.getElementById('btn-test-db-conn');
  if (btnTestDb && !btnTestDb._bound) {
    btnTestDb._bound = true;
    btnTestDb.addEventListener('click', () => {
      const badge = document.getElementById('test-db-result-badge');
      testConnectionAction('hostinger_mariadb', badge);
    });
  }

  const btnTestFtp = document.getElementById('btn-test-ftp-conn');
  if (btnTestFtp && !btnTestFtp._bound) {
    btnTestFtp._bound = true;
    btnTestFtp.addEventListener('click', () => {
      const badge = document.getElementById('test-ftp-result-badge');
      testConnectionAction('ftp', badge);
    });
  }

  const btnTestSsh = document.getElementById('btn-test-ssh-conn');
  if (btnTestSsh && !btnTestSsh._bound) {
    btnTestSsh._bound = true;
    btnTestSsh.addEventListener('click', () => {
      const badge = document.getElementById('test-ssh-result-badge');
      testConnectionAction('ssh', badge);
    });
  }

  const btnTestMail = document.getElementById('btn-test-mail-conn');
  if (btnTestMail && !btnTestMail._bound) {
    btnTestMail._bound = true;
    btnTestMail.addEventListener('click', () => {
      const badge = document.getElementById('test-mail-result-badge');
      testConnectionAction('smtp', badge);
    });
  }

  const btnSave = document.getElementById('btn-save-connections');
  if (btnSave && !btnSave._bound) {
    btnSave._bound = true;
    btnSave.addEventListener('click', () => {
      saveConnectionsSettings();
    });
  }

  const btnReset = document.getElementById('btn-reset-connections');
  if (btnReset && !btnReset._bound) {
    btnReset._bound = true;
    btnReset.addEventListener('click', () => {
      loadConnectionsSettings();
    });
  }

  const connTabBtn = document.getElementById('user-settings-tab-btn-connections');
  if (connTabBtn && !connTabBtn._bound) {
    connTabBtn._bound = true;
    connTabBtn.addEventListener('shown.bs.tab', () => {
      loadConnectionsSettings();
    });
  }
}

export async function initUserSettings() {
  await ensureUserSettingsModal();
  await refreshUserProfile();
  await refreshActiveModelBadge();

  // Инициализация событий подключений
  bindConnectionsEvents();
  loadConnectionsSettings();

  // Bind User Menu Action Buttons
  document.querySelectorAll('#user-menu-btn-mail, #nav-btn-check-mail, .action-btn-mail').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      executeUserAction('mail');
    });
  });

  document.querySelectorAll('#user-menu-btn-docs, #nav-btn-search-gdocs, .action-btn-docs').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      executeUserAction('docs');
    });
  });

  document.querySelectorAll('#user-menu-btn-sheets, #nav-btn-gsheets, .action-btn-sheets').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      executeUserAction('sheets');
    });
  });

  document.querySelectorAll('#user-menu-btn-news, #nav-btn-news-digest, .action-btn-news').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      executeUserAction('news');
    });
  });

  document.querySelectorAll('#user-menu-btn-facebook, #nav-btn-facebook-post, .action-btn-facebook').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      executeUserAction('facebook');
    });
  });

  // Handle Google Login Click
  document.querySelectorAll('.btn-google-login, #user-settings-google-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const nextUrl = window.location.pathname + window.location.search;
      window.location.href = `/auth/google?next=${encodeURIComponent(nextUrl)}`;
    });
  });

  // Handle Logout Click
  document.querySelectorAll('.btn-user-logout, #user-settings-logout-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        await fetch('/auth/logout', { method: 'POST' });
      } catch (err) {
        console.error('Logout error:', err);
      } finally {
        window.location.href = '/';
      }
    });
  });

  // Обработка переключения темы в модальном окне настроек
  document.querySelectorAll('.theme-selector').forEach((sel) => {
    sel.addEventListener('change', (e) => {
      const theme = e.target.value;
      if (window.themeEngine && typeof window.themeEngine.applyTheme === 'function') {
        window.themeEngine.applyTheme(theme);
      }
    });
  });

  // Обработка переключения языка в модальном окне настроек
  document.querySelectorAll('.lang-selector').forEach((sel) => {
    sel.addEventListener('change', (e) => {
      const lang = e.target.value;
      if (window.i18n && typeof window.i18n.setLanguage === 'function') {
        window.i18n.setLanguage(lang);
      }
    });
  });

  // Handle Model Ping send
  const pingBtn = document.getElementById('btn-model-ping-send');
  const pingInput = document.getElementById('model-ping-input');
  const pingRespContainer = document.getElementById('model-ping-response-container');
  const pingResp = document.getElementById('model-ping-response');

  if (pingBtn && pingInput) {
    pingBtn.addEventListener('click', async () => {
      const text = pingInput.value.trim();
      if (!text) return;

      const getT = (k, fb) => (typeof window !== 'undefined' && window.i18next?.t(k)) || fb;
      const sendingText = getT('userSettings.modelPingSending', 'Отправка...');
      const sendBtnText = getT('userSettings.modelPingSendBtn', 'Отправить');
      const waitingText = getT('userSettings.modelPingWaiting', 'Ожидание ответа модели...');
      const emptyText = getT('userSettings.modelPingEmptyResponse', '[Пустой ответ]');

      pingBtn.disabled = true;
      const btnSpan = document.getElementById('model-ping-btn-text');
      if (btnSpan) btnSpan.textContent = sendingText;
      if (pingRespContainer) pingRespContainer.classList.remove('d-none');
      if (pingResp) pingResp.textContent = waitingText;

      try {
        const res = await fetch('/api/v1/chat/ping', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        });
        if (res.ok) {
          const data = await res.json();
          if (pingResp) pingResp.textContent = data.response || emptyText;
        } else {
          if (pingResp) pingResp.textContent = `Ошибка сервера: ${res.status}`;
        }
      } catch (err) {
        if (pingResp) pingResp.textContent = `Ошибка сети: ${err.message}`;
      } finally {
        pingBtn.disabled = false;
        if (btnSpan) btnSpan.textContent = sendBtnText;
      }
    });
  }

  // Handle Open Theme Editor click
  const openThemeEditorBtn = document.getElementById('modal-btn-open-theme-editor');
  if (openThemeEditorBtn) {
    openThemeEditorBtn.addEventListener('click', () => {
      if (typeof window.switchTab === 'function') {
        window.switchTab('tab-theme-editor');
      } else if (typeof window.switchToTab === 'function') {
        window.switchToTab('tab-theme-editor');
      }
    });
  }
}

export function isUserAdmin() {
  if (!window.currentUser) return false;
  return Boolean(window.currentUser.is_admin || (window.currentUser.role && String(window.currentUser.role).toLowerCase() === 'admin'));
}

export async function refreshUserProfile() {
  try {
    const res = await fetch('/auth/check');
    if (!res.ok) return;
    const data = await res.json();
    window.currentUser = data;

    const authCard = document.getElementById('user-settings-auth-card');
    const guestCard = document.getElementById('user-settings-guest-card');
    const navGoogleBtn = document.getElementById('nav-google-btn');
    const userSettingsBtn = document.getElementById('user-settings-btn');
    const navAvatar = document.getElementById('nav-user-avatar');
    const navIcon = document.getElementById('nav-user-icon');
    const navLabel = document.getElementById('nav-user-label');

    if (data && data.authenticated) {
      if (authCard) authCard.classList.remove('d-none');
      if (guestCard) guestCard.classList.add('d-none');

      if (navGoogleBtn) navGoogleBtn.classList.add('d-none');
      if (userSettingsBtn) {
        userSettingsBtn.classList.remove('d-none');
        userSettingsBtn.classList.add('d-flex');
      }

      const defaultUserName = (typeof window !== 'undefined' && window.i18next?.t('userSettings.userDefault')) || 'Пользователь';
      const name = data.name || data.email || defaultUserName;
      const email = data.email || '';
      const picture = data.picture || '';
      const role = data.role || (data.is_admin ? 'Admin' : 'User');
      const hasGoogle = Boolean(data.has_google);

      const avatarEl = document.getElementById('user-settings-avatar');
      const nameEl = document.getElementById('user-settings-name');
      const emailEl = document.getElementById('user-settings-email');
      const roleBadge = document.getElementById('user-settings-role-badge');
      const googleBadge = document.getElementById('user-settings-google-badge');

      if (avatarEl) {
        if (picture) {
          avatarEl.src = picture;
          avatarEl.classList.remove('d-none');
        } else {
          avatarEl.classList.add('d-none');
        }
      }
      if (nameEl) nameEl.textContent = name;
      if (emailEl) emailEl.textContent = email;
      if (roleBadge) {
        roleBadge.textContent = role;
        roleBadge.className = `badge ${role.toLowerCase() === 'admin' ? 'bg-danger' : 'bg-primary'}`;
      }
      const isOauthEnabled = data.oauth_enabled !== false;

      if (googleBadge) {
        const getT = (k, fb) => (typeof window !== 'undefined' && window.i18next?.t(k)) || fb;
        const oauthLabel = getT('userSettings.googleOAuth', 'Google OAuth:');
        const syncedLabel = getT('userSettings.googleSynced', 'Синхронизирован');
        const notConnectedLabel = getT('userSettings.googleNotConnected', 'Не подключен');
        const syncBtnLabel = getT('userSettings.googleSyncBtn', 'Синхронизировать');
        const disabledLabel = getT('userSettings.googleDisabled', 'Отключен');

        if (hasGoogle) {
          googleBadge.innerHTML = `<i class="bi bi-google text-danger me-1"></i><span id="user-settings-google-oauth-label">${oauthLabel}</span> <span class="text-success fw-bold" id="user-settings-google-status">${syncedLabel}</span>`;
        } else if (isOauthEnabled) {
          googleBadge.innerHTML = `<i class="bi bi-google text-muted me-1"></i><span id="user-settings-google-oauth-label">${oauthLabel}</span> <span class="text-warning" id="user-settings-google-status">${notConnectedLabel}</span> <button type="button" class="btn btn-sm btn-outline-danger ms-2 py-0 px-2 btn-google-login" id="user-settings-google-sync-btn">${syncBtnLabel}</button>`;
        } else {
          googleBadge.innerHTML = `<i class="bi bi-google text-muted me-1"></i><span id="user-settings-google-oauth-label">${oauthLabel}</span> <span class="text-muted" id="user-settings-google-status">${disabledLabel}</span>`;
        }
      }

      const menuWrapper = document.getElementById('user-menu-dropdown-wrapper');
      const menuDisplayName = document.getElementById('user-menu-display-name');
      const menuDisplayEmail = document.getElementById('user-menu-display-email');
      if (menuWrapper) {
        menuWrapper.classList.remove('d-none');
        menuWrapper.classList.add('d-flex');
      }
      if (menuDisplayName) menuDisplayName.textContent = name;
      if (menuDisplayEmail) menuDisplayEmail.textContent = email;

      if (navAvatar && picture) {
        navAvatar.src = picture;
        navAvatar.classList.remove('d-none');
        if (navIcon) navIcon.classList.add('d-none');
      }
      if (navLabel) {
        const shortName = name.split(' ')[0] || name;
        navLabel.textContent = shortName;
      }
    } else {
      if (authCard) authCard.classList.add('d-none');
      if (guestCard) guestCard.classList.remove('d-none');

      const isOauthEnabled = data && data.oauth_enabled !== false;

      if (navGoogleBtn) {
        if (isOauthEnabled) {
          navGoogleBtn.classList.remove('d-none');
          navGoogleBtn.classList.add('d-flex');
        } else {
          navGoogleBtn.classList.add('d-none');
          navGoogleBtn.classList.remove('d-flex');
        }
      }
      const menuWrapper = document.getElementById('user-menu-dropdown-wrapper');
      if (menuWrapper) {
        if (isOauthEnabled) {
          menuWrapper.classList.add('d-none');
          menuWrapper.classList.remove('d-flex');
        } else {
          menuWrapper.classList.remove('d-none');
          menuWrapper.classList.add('d-flex');
        }
      }
      if (userSettingsBtn) {
        if (isOauthEnabled) {
          userSettingsBtn.classList.add('d-none');
          userSettingsBtn.classList.remove('d-flex');
        } else {
          userSettingsBtn.classList.remove('d-none');
          userSettingsBtn.classList.add('d-flex');
        }
      }

      const guestGoogleBtn = guestCard ? guestCard.querySelector('.btn-google-login') : null;
      if (guestGoogleBtn) {
        if (isOauthEnabled) {
          guestGoogleBtn.classList.remove('d-none');
        } else {
          guestGoogleBtn.classList.add('d-none');
        }
      }

      if (navAvatar) navAvatar.classList.add('d-none');
      if (navIcon) navIcon.classList.remove('d-none');
      if (navLabel) navLabel.textContent = 'User Settings';
    }
  } catch (err) {
    console.error('Failed to refresh user profile:', err);
  }
}

window.openModelsTab = openModelsTab;
window.refreshActiveModelBadge = refreshActiveModelBadge;
window.initUserSettings = initUserSettings;
window.refreshUserProfile = refreshUserProfile;
window.isUserAdmin = isUserAdmin;
window.executeUserAction = executeUserAction;
window.ensureUserSettingsModal = ensureUserSettingsModal;
window.loadConnectionsSettings = loadConnectionsSettings;
window.saveConnectionsSettings = saveConnectionsSettings;
window.testConnectionAction = testConnectionAction;
