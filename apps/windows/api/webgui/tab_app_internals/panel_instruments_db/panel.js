/**
 * =============================================================================
 * Process Name: Windows App Internals - AI Instruments Database Panel
 * =============================================================================
 * Description:
 *   Модуль управления подключением к изолированной базе данных инструментов
 *   ИИ-агента (ai_instruments: Hostinger REST API gateway / MariaDB direct TCP /
 *   SQLite локально), проверки связи, параметров рантайма и каталога инструментов.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_instruments_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 17:44:30
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v3';
import {
  loadInstrumentsRuntimeConfig,
  saveInstrumentsRuntimeConfig,
  bindInstrumentsRuntimeButtons,
} from './runtime.js?v=20261031_v3';
import {
  loadInstrumentsCatalog,
  bindInstrumentsCatalogButtons,
  openInstrumentEditorModal,
  saveInstrumentFromModal,
  exportInstrumentsCatalogCsv,
  importInstrumentsCatalogCsv,
} from './catalog.js?v=20261101_v1';

export {
  loadInstrumentsRuntimeConfig,
  saveInstrumentsRuntimeConfig,
  bindInstrumentsRuntimeButtons,
  loadInstrumentsCatalog,
  bindInstrumentsCatalogButtons,
  openInstrumentEditorModal,
  saveInstrumentFromModal,
  exportInstrumentsCatalogCsv,
  importInstrumentsCatalogCsv,
};

/**
 * Получение текущего активного режима подключения к БД инструментов.
 * @returns {'php_api' | 'direct' | 'sqlite'}
 */
export function getActiveInstrumentsConnMode() {
  const checked = document.querySelector('input[name="instruments-conn-mode"]:checked');
  return checked ? checked.value : 'sqlite';
}

/**
 * Установка активного режима подключения и переключение видимости блоков.
 * @param {'php_api' | 'direct' | 'sqlite'} mode
 */
export function setActiveInstrumentsConnMode(mode) {
  const radio = document.querySelector(`input[name="instruments-conn-mode"][value="${mode}"]`);
  if (radio) radio.checked = true;
  applyInstrumentsConnModeVisibility(mode);
}

/**
 * Переключение видимости секций формы для базы инструментов.
 * @param {'php_api' | 'direct' | 'sqlite'} mode
 */
export function applyInstrumentsConnModeVisibility(mode) {
  const secApi = document.getElementById('instruments-sec-api');
  const secDirect = document.getElementById('instruments-sec-direct');
  const secSqlite = document.getElementById('instruments-sec-sqlite');
  const badge = document.getElementById('instruments-db-engine-badge');

  if (secApi) secApi.style.display = (mode === 'php_api') ? '' : 'none';
  if (secDirect) secDirect.style.display = (mode === 'direct') ? '' : 'none';
  if (secSqlite) secSqlite.style.display = (mode === 'sqlite') ? '' : 'none';

  if (badge) {
    if (mode === 'php_api') {
      badge.textContent = 'Hostinger API (PHP)';
      badge.className = 'ui-badge ui-badge-info';
    } else if (mode === 'direct') {
      badge.textContent = 'MariaDB (Прямой TCP)';
      badge.className = 'ui-badge ui-badge-info';
    } else {
      badge.textContent = 'SQLite (ai_instruments.db)';
      badge.className = 'ui-badge ui-badge-neutral';
    }
  }
}

/**
 * Обновление информационного баннера активной базы данных инструментов.
 * @param {string} engine - 'sqlite' или 'mariadb' / 'hostinger'
 * @param {string} connType - 'php_api' или 'direct'
 * @param {number} count - количество инструментов
 */
export function updateActiveInstrumentsDbBanner(engine, connType, count = 0) {
  const badge = document.getElementById('instruments-active-db-badge');
  const typeBadge = document.getElementById('instruments-active-type-badge');
  const detail = document.getElementById('instruments-active-db-detail');

  if (!badge || !typeBadge || !detail) return;

  const countStr = count > 0 ? ` (${count} инструментов)` : '';

  if (engine === 'sqlite') {
    const path = document.getElementById('instruments-db-sqlite-path')?.value || 'data/ai_instruments/ai_instruments.db';
    badge.innerHTML = `<i class="bi bi-hdd me-1"></i>Локальная база (ai_instruments.db)${countStr}`;
    badge.className = 'ui-badge ui-badge-neutral fw-bold';
    typeBadge.textContent = 'Локальная';
    typeBadge.className = 'ui-badge ui-badge-neutral';
    detail.textContent = path;
  } else if (connType === 'php_api') {
    const url = document.getElementById('instruments-db-php-url')?.value || 'wikillm_hostinger.php';
    const dbName = document.getElementById('instruments-db-api-name')?.value || 'u177424397_comp_knowledge';
    badge.innerHTML = `<i class="bi bi-cloud-check-fill me-1"></i>Удаленная на Hostinger (PHP API)${countStr}`;
    badge.className = 'ui-badge ui-badge-info fw-bold';
    typeBadge.textContent = 'Удаленная';
    typeBadge.className = 'ui-badge ui-badge-info';
    detail.textContent = 'REST Gateway: ' + url.split('/').pop() + ' (БД: ' + dbName + ', таблица: ai_instruments)';
  } else {
    const host = document.getElementById('instruments-db-host')?.value || 'srv1502.hstgr.io';
    const port = document.getElementById('instruments-db-port')?.value || '3306';
    const dbName = document.getElementById('instruments-db-direct-name')?.value || 'u177424397_comp_knowledge';
    badge.innerHTML = `<i class="bi bi-hdd-network-fill me-1"></i>Удаленная MariaDB (Direct TCP)${countStr}`;
    badge.className = 'ui-badge ui-badge-info fw-bold';
    typeBadge.textContent = 'Удаленная';
    typeBadge.className = 'ui-badge ui-badge-info';
    detail.textContent = 'Direct TCP: ' + host + ':' + port + ' (БД: ' + dbName + ')';
  }
}

/**
 * Загрузка конфигурации подключения к базе данных инструментов.
 * @returns {Promise<void>}
 */
export async function loadInstrumentsDbConfig() {
  try {
    const res = await fetch('/api/v1/ai-instruments/db/config');
    if (!res.ok) return;
    const data = await res.json();
    const engine = (data.engine || 'sqlite').toLowerCase();
    const h = data.hostinger || {};
    const connType = h.connection_type || 'php_api';

    let mode = 'sqlite';
    if (engine === 'sqlite') {
      mode = 'sqlite';
    } else if (connType === 'direct') {
      mode = 'direct';
    } else {
      mode = 'php_api';
    }

    // Поле SQLite
    const sq = data.sqlite || {};
    if (document.getElementById('instruments-db-sqlite-path')) {
      document.getElementById('instruments-db-sqlite-path').value = sq.path || 'data/ai_instruments/ai_instruments.db';
    }

    // Поля API Hostinger
    if (document.getElementById('instruments-db-php-url')) {
      document.getElementById('instruments-db-php-url').value = h.php_api_url || 'https://srv1502.hstgr.io/wikillm_hostinger.php';
    }
    if (document.getElementById('instruments-db-php-key')) {
      document.getElementById('instruments-db-php-key').value = h.php_api_key || '';
    }
    if (document.getElementById('instruments-db-api-name')) {
      document.getElementById('instruments-db-api-name').value = h.database || 'u177424397_comp_knowledge';
    }
    if (document.getElementById('instruments-db-api-timeout')) {
      document.getElementById('instruments-db-api-timeout').value = h.connect_timeout ?? 10;
    }

    // Поля прямого подключения TCP
    if (document.getElementById('instruments-db-host')) {
      document.getElementById('instruments-db-host').value = h.host || 'srv1502.hstgr.io';
    }
    if (document.getElementById('instruments-db-port')) {
      document.getElementById('instruments-db-port').value = h.port ?? 3306;
    }
    if (document.getElementById('instruments-db-direct-name')) {
      document.getElementById('instruments-db-direct-name').value = h.database || 'u177424397_comp_knowledge';
    }
    if (document.getElementById('instruments-db-user')) {
      document.getElementById('instruments-db-user').value = h.user || 'u177424397_davidka';
    }
    if (document.getElementById('instruments-db-pass')) {
      document.getElementById('instruments-db-pass').value = h.password || '';
    }

    setActiveInstrumentsConnMode(mode);
    updateActiveInstrumentsDbBanner(engine, connType);
  } catch (e) {
    console.warn('[AI Instruments DB] Не удалось загрузить конфигурацию:', e);
  }
}

/**
 * Получение текущих параметров формы для базы инструментов.
 * @returns {object}
 */
export function getInstrumentsDbFormParams() {
  const mode = getActiveInstrumentsConnMode();
  if (mode === 'sqlite') {
    return {
      engine: 'sqlite',
      sqlite_path: document.getElementById('instruments-db-sqlite-path')?.value || 'data/ai_instruments/ai_instruments.db',
      connection_type: 'sqlite',
      host: 'localhost',
      port: 0,
      database: 'ai_instruments.db',
      user: '',
      password: '',
      table_name: 'ai_instruments',
      php_api_url: '',
      php_api_key: '',
      connect_timeout: 10
    };
  }

  if (mode === 'direct') {
    return {
      engine: 'mariadb',
      sqlite_path: document.getElementById('instruments-db-sqlite-path')?.value || 'data/ai_instruments/ai_instruments.db',
      connection_type: 'direct',
      host: document.getElementById('instruments-db-host')?.value || 'srv1502.hstgr.io',
      port: parseInt(document.getElementById('instruments-db-port')?.value || '3306', 10),
      database: document.getElementById('instruments-db-direct-name')?.value || 'u177424397_comp_knowledge',
      user: document.getElementById('instruments-db-user')?.value || 'u177424397_davidka',
      password: document.getElementById('instruments-db-pass')?.value || '',
      table_name: 'ai_instruments',
      php_api_url: document.getElementById('instruments-db-php-url')?.value || 'https://srv1502.hstgr.io/wikillm_hostinger.php',
      php_api_key: document.getElementById('instruments-db-php-key')?.value || '',
      connect_timeout: 10
    };
  }

  return {
    engine: 'mariadb',
    sqlite_path: document.getElementById('instruments-db-sqlite-path')?.value || 'data/ai_instruments/ai_instruments.db',
    connection_type: 'php_api',
    host: 'srv1502.hstgr.io',
    port: 3306,
    database: document.getElementById('instruments-db-api-name')?.value || 'u177424397_comp_knowledge',
    user: 'u177424397_davidka',
    password: '',
    table_name: 'ai_instruments',
    php_api_url: document.getElementById('instruments-db-php-url')?.value || 'https://srv1502.hstgr.io/wikillm_hostinger.php',
    php_api_key: document.getElementById('instruments-db-php-key')?.value || '',
    connect_timeout: parseInt(document.getElementById('instruments-db-api-timeout')?.value || '10', 10)
  };
}

/**
 * Проверка подключения к базе данных инструментов.
 * @returns {Promise<void>}
 */
export async function checkInstrumentsDbConnection() {
  const spinner = document.getElementById('instruments-db-spinner');
  const headerStatus = document.getElementById('instruments-db-header-status');
  const resultBox = document.getElementById('instruments-db-check-result');

  if (spinner) spinner.style.display = 'inline-block';
  if (resultBox) {
    resultBox.style.display = 'block';
    resultBox.innerHTML = '<div class="alert alert-info py-2 px-3 mb-0 small"><span class="spinner-border spinner-border-sm me-2"></span>Проверка соединения с базой инструментов...</div>';
  }

  try {
    const payload = getInstrumentsDbFormParams();
    const res = await fetch('/api/v1/ai-instruments/db/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (spinner) spinner.style.display = 'none';

    if (!data.ok) {
      if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i>Ошибка связи</span>';
      resultBox.innerHTML = `
        <div class="alert alert-danger py-2 px-3 mb-0 small">
          <div class="fw-bold mb-1"><i class="bi bi-exclamation-octagon-fill me-1"></i>Ошибка подключения:</div>
          <div>${data.message || data.error}</div>
        </div>
      `;
      return;
    }

    if (headerStatus) {
      headerStatus.innerHTML = '<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>Подключено (Активна)</span>';
    }
    resultBox.innerHTML = `
      <div class="alert alert-success py-2 px-3 mb-0">
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-1">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-tools fs-5 text-primary"></i>
            <strong>База инструментов готова к работе!</strong>
          </div>
          <span class="ui-badge ui-badge-success">${data.engine === 'sqlite' ? 'SQLite' : 'Hostinger'}</span>
        </div>
        <div class="small mb-1">
          Таблица: <strong>ai_instruments</strong> (${data.count} зарегистрированных инструментов агента).
        </div>
        <div class="small text-secondary">${data.message}</div>
      </div>
    `;

    updateActiveInstrumentsDbBanner(payload.engine, payload.connection_type, data.count);
  } catch (e) {
    if (spinner) spinner.style.display = 'none';
    if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-danger">Ошибка сети</span>';
    resultBox.innerHTML = `
      <div class="alert alert-danger py-2 px-3 mb-0 small">
        <strong>Ошибка выполнения запроса:</strong> ${e.message || e}
      </div>
    `;
  }
}

/**
 * Сохранение конфигурации базы данных инструментов на сервере.
 * @returns {Promise<void>}
 */
export async function saveInstrumentsDbConfig() {
  const btn = document.getElementById('instruments-db-btn-save-cfg');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сохранение...';
  }
  try {
    const payload = getInstrumentsDbFormParams();
    const res = await fetch('/api/v1/ai-instruments/db/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success || data.ok) {
      notifyUser('Конфигурация базы инструментов успешно сохранена!', 'success');
      await checkInstrumentsDbConnection();
    } else {
      alert('Ошибка сохранения: ' + (data.message || data.detail));
    }
  } catch (e) {
    alert('Ошибка при сохранении конфигурации базы инструментов: ' + e);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Сделать активной и сохранить';
    }
  }
}

/**
 * Привязка событий к элементам карточки базы данных инструментов.
 */
export function bindInstrumentsDbButtons() {
  document.querySelectorAll('input[name="instruments-conn-mode"]').forEach(radio => {
    if (!radio._bound) {
      radio._bound = true;
      radio.addEventListener('change', () => {
        applyInstrumentsConnModeVisibility(radio.value);
      });
    }
  });

  const checkBtn = document.getElementById('instruments-db-btn-check');
  if (checkBtn && !checkBtn._bound) {
    checkBtn._bound = true;
    checkBtn.addEventListener('click', checkInstrumentsDbConnection);
  }

  const saveCfgBtn = document.getElementById('instruments-db-btn-save-cfg');
  if (saveCfgBtn && !saveCfgBtn._bound) {
    saveCfgBtn._bound = true;
    saveCfgBtn.addEventListener('click', saveInstrumentsDbConfig);
  }

  const togglePassBtn = document.getElementById('instruments-db-toggle-pass');
  if (togglePassBtn && !togglePassBtn._bound) {
    togglePassBtn._bound = true;
    togglePassBtn.addEventListener('click', () => {
      const passInp = document.getElementById('instruments-db-pass');
      if (!passInp) return;
      const isPass = (passInp.type === 'password');
      passInp.type = isPass ? 'text' : 'password';
      togglePassBtn.innerHTML = isPass ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  }

  bindInstrumentsRuntimeButtons();
  bindInstrumentsCatalogButtons();
}

/**
 * Инициализация панели базы данных инструментов.
 * @returns {Promise<void>}
 */
export async function initInstrumentsDbPanel() {
  bindInstrumentsDbButtons();
  await loadInstrumentsDbConfig();
  await loadInstrumentsRuntimeConfig();
  await loadInstrumentsCatalog();
}
