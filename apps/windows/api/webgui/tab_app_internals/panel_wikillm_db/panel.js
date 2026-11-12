/**
 * =============================================================================
 * Process Name: Windows App Internals - WikiLLM Database Panel
 * =============================================================================
 * Description:
 *   Модуль управления подключением к базе данных базы знаний WikiLLM
 *   (MariaDB direct TCP / REST API gateway / SQLite локально), проверки связи,
 *   инициализации таблиц и миграции данных.
 *
 * File: panel.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_wikillm_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 12:40:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v3';
import {
  createWikiLLMDatabase as createDbAction,
  initWikiLLMEmptyTables as initTablesAction,
  importWikiLLMFromSqlite as importSqliteAction
} from './actions.js?v=20261031_v3';

/**
 * Получение текущего активного режима подключения к БД.
 * @returns {'php_api' | 'direct' | 'sqlite'}
 */
export function getActiveConnMode() {
  const checked = document.querySelector('input[name="wikillm-conn-mode"]:checked');
  return checked ? checked.value : 'sqlite';
}

/**
 * Установка активного режима подключения и переключение видимости блоков.
 * @param {'php_api' | 'direct' | 'sqlite'} mode
 */
export function setActiveConnMode(mode) {
  const radio = document.querySelector(`input[name="wikillm-conn-mode"][value="${mode}"]`);
  if (radio) radio.checked = true;
  applyConnModeVisibility(mode);
}

/**
 * Переключение видимости блоков формы строго в соответствии с выбранным режимом.
 * @param {'php_api' | 'direct' | 'sqlite'} mode
 */
export function applyConnModeVisibility(mode) {
  const secApi = document.getElementById('wikillm-sec-api');
  const secDirect = document.getElementById('wikillm-sec-direct');
  const secSqlite = document.getElementById('wikillm-sec-sqlite');
  const badge = document.getElementById('wikillm-db-engine-badge');

  if (secApi) secApi.style.display = (mode === 'php_api') ? '' : 'none';
  if (secDirect) secDirect.style.display = (mode === 'direct') ? '' : 'none';
  if (secSqlite) secSqlite.style.display = (mode === 'sqlite') ? '' : 'none';

  if (badge) {
    if (mode === 'php_api') {
      badge.textContent = 'Через API (PHP скрипт)';
      badge.className = 'ui-badge ui-badge-info';
    } else if (mode === 'direct') {
      badge.textContent = 'MariaDB (Прямое TCP)';
      badge.className = 'ui-badge ui-badge-info';
    } else {
      badge.textContent = 'SQLite (Локально)';
      badge.className = 'ui-badge ui-badge-neutral';
    }
  }
}

/**
 * Обновление информационного баннера активной базы данных.
 * @param {string} engine - 'mariadb' или 'sqlite'
 * @param {string} connType - 'direct' или 'php_api'
 */
export function updateActiveDbBanner(engine, connType) {
  const badge = document.getElementById('wikillm-active-db-badge');
  const typeBadge = document.getElementById('wikillm-active-type-badge');
  const detail = document.getElementById('wikillm-active-db-detail');

  if (!badge || !detail) return;

  if (engine === 'sqlite') {
    const path = document.getElementById('wikillm-db-sqlite-path')?.value || '%ProgramData%/{app_name}/apps/windows/knowledge.db';
    const resolvedPathEl = document.getElementById('wikillm-db-resolved-path');
    const resolvedPath = resolvedPathEl?.textContent || '';
    badge.innerHTML = '<i class="bi bi-hdd me-1"></i>Локальная база (SQLite)';
    badge.className = 'ui-badge ui-badge-neutral fw-bold';
    if (typeBadge) {
      typeBadge.textContent = 'Локальная';
      typeBadge.className = 'ui-badge ui-badge-neutral';
    }
    detail.textContent = resolvedPath ? `${path} (${resolvedPath})` : path;
  } else if (connType === 'php_api') {
    const url = document.getElementById('wikillm-db-php-url')?.value || 'wikillm_hostinger.php';
    const dbName = document.getElementById('wikillm-db-api-name')?.value || 'u177424397_comp_knowledge';
    badge.innerHTML = '<i class="bi bi-cloud-check-fill me-1"></i>Удаленная MariaDB (через API)';
    badge.className = 'ui-badge ui-badge-info fw-bold';
    if (typeBadge) {
      typeBadge.textContent = 'Удаленная';
      typeBadge.className = 'ui-badge ui-badge-info';
    }
    detail.textContent = 'REST Gateway: ' + url.split('/').pop() + ' (БД: ' + dbName + ')';
  } else {
    const host = document.getElementById('wikillm-db-host')?.value || 'srv1502.hstgr.io';
    const port = document.getElementById('wikillm-db-port')?.value || '3306';
    const dbName = document.getElementById('wikillm-db-direct-name')?.value || 'u177424397_comp_knowledge';
    badge.innerHTML = '<i class="bi bi-hdd-network-fill me-1"></i>Удаленная MariaDB (Прямое подключение)';
    badge.className = 'ui-badge ui-badge-info fw-bold';
    if (typeBadge) {
      typeBadge.textContent = 'Удаленная';
      typeBadge.className = 'ui-badge ui-badge-info';
    }
    detail.textContent = 'Direct TCP: ' + host + ':' + port + ' (БД: ' + dbName + ')';
  }
}

/**
 * Загрузка настроек сервера базы данных (MariaDB / SQLite).
 * @returns {Promise<void>}
 */
export async function loadWikiLLMDbConfig() {
  try {
    const res = await fetch('/api/v1/wikillm/db/config');
    if (!res.ok) return;
    const data = await res.json();
    const engine = data.engine || 'mariadb';
    const m = data.mariadb || {};
    const connType = m.connection_type || 'php_api';

    let mode = 'php_api';
    if (engine === 'sqlite') {
      mode = 'sqlite';
    } else if (connType === 'direct') {
      mode = 'direct';
    } else {
      mode = 'php_api';
    }

    // Поля API
    if (document.getElementById('wikillm-db-php-url')) document.getElementById('wikillm-db-php-url').value = m.php_api_url || 'https://srv1502.hstgr.io/wikillm_hostinger.php';
    if (document.getElementById('wikillm-db-php-key')) document.getElementById('wikillm-db-php-key').value = m.php_api_key || '';
    if (document.getElementById('wikillm-db-api-name')) document.getElementById('wikillm-db-api-name').value = m.database || 'u177424397_comp_knowledge';
    if (document.getElementById('wikillm-db-api-timeout')) document.getElementById('wikillm-db-api-timeout').value = m.connect_timeout ?? 15;

    // Поля прямого подключения TCP
    if (document.getElementById('wikillm-db-host')) document.getElementById('wikillm-db-host').value = m.host || 'srv1502.hstgr.io';
    if (document.getElementById('wikillm-db-port')) document.getElementById('wikillm-db-port').value = m.port ?? 3306;
    if (document.getElementById('wikillm-db-direct-timeout')) document.getElementById('wikillm-db-direct-timeout').value = m.connect_timeout ?? 10;
    if (document.getElementById('wikillm-db-direct-name')) document.getElementById('wikillm-db-direct-name').value = m.database || 'u177424397_comp_knowledge';
    if (document.getElementById('wikillm-db-user')) document.getElementById('wikillm-db-user').value = m.user || 'u177424397_davidka';
    if (document.getElementById('wikillm-db-pass')) document.getElementById('wikillm-db-pass').value = m.password || '';
    if (document.getElementById('wikillm-db-ip-fallback')) document.getElementById('wikillm-db-ip-fallback').value = m.ip_fallback || '77.37.35.16';

    // Поле SQLite
    const s = data.sqlite || {};
    if (document.getElementById('wikillm-db-sqlite-path')) {
      document.getElementById('wikillm-db-sqlite-path').value = s.path || '%ProgramData%/{app_name}/apps/windows/knowledge.db';
    }
    if (document.getElementById('wikillm-db-resolved-path') && s.resolved_path) {
      document.getElementById('wikillm-db-resolved-path').textContent = s.resolved_path;
    }

    const hasModeRadios = document.querySelectorAll('input[name="wikillm-conn-mode"]').length > 0;
    const effectiveEngine = hasModeRadios ? engine : 'sqlite';
    const effectiveMode = hasModeRadios ? mode : 'sqlite';

    setActiveConnMode(effectiveMode);
    updateActiveDbBanner(effectiveEngine, connType);
  } catch (e) {
    console.warn('[WikiLLM DB] Не удалось загрузить конфигурацию БД:', e);
  }
}

/**
 * Получение текущих введенных параметров подключения в зависимости от активного режима.
 * @returns {object}
 */
export function getDbFormParams() {
  const mode = getActiveConnMode();
  if (mode === 'sqlite') {
    return {
      engine: 'sqlite',
      connection_type: 'sqlite',
      sqlite_path: document.getElementById('wikillm-db-sqlite-path')?.value || '%ProgramData%/{app_name}/apps/windows/knowledge.db'
    };
  }

  if (mode === 'direct') {
    return {
      engine: 'mariadb',
      connection_type: 'direct',
      host: document.getElementById('wikillm-db-host')?.value || 'srv1502.hstgr.io',
      port: parseInt(document.getElementById('wikillm-db-port')?.value || '3306', 10),
      database: document.getElementById('wikillm-db-direct-name')?.value || 'u177424397_comp_knowledge',
      user: document.getElementById('wikillm-db-user')?.value || 'u177424397_davidka',
      password: document.getElementById('wikillm-db-pass')?.value || '',
      ip_fallback: document.getElementById('wikillm-db-ip-fallback')?.value || '77.37.35.16',
      connect_timeout: parseInt(document.getElementById('wikillm-db-direct-timeout')?.value || '10', 10),
      sqlite_path: document.getElementById('wikillm-db-sqlite-path')?.value || '%ProgramData%/{app_name}/apps/windows/knowledge.db'
    };
  }

  return {
    engine: 'mariadb',
    connection_type: 'php_api',
    php_api_url: document.getElementById('wikillm-db-php-url')?.value || 'https://srv1502.hstgr.io/wikillm_hostinger.php',
    php_api_key: document.getElementById('wikillm-db-php-key')?.value || '',
    database: document.getElementById('wikillm-db-api-name')?.value || 'u177424397_comp_knowledge',
    connect_timeout: parseInt(document.getElementById('wikillm-db-api-timeout')?.value || '15', 10),
    sqlite_path: document.getElementById('wikillm-db-sqlite-path')?.value || '%ProgramData%/{app_name}/apps/windows/knowledge.db'
  };
}

/**
 * Сохранение конфигурации базы данных на сервере.
 * @returns {Promise<void>}
 */
export async function saveWikiLLMDbConfig() {
  const mode = getActiveConnMode();
  const payload = {
    engine: (mode === 'sqlite') ? 'sqlite' : 'mariadb',
    mariadb: {
      connection_type: (mode === 'direct') ? 'direct' : 'php_api',
      host: document.getElementById('wikillm-db-host')?.value || 'srv1502.hstgr.io',
      port: parseInt(document.getElementById('wikillm-db-port')?.value || '3306', 10),
      database: (mode === 'direct')
        ? (document.getElementById('wikillm-db-direct-name')?.value || 'u177424397_comp_knowledge')
        : (document.getElementById('wikillm-db-api-name')?.value || 'u177424397_comp_knowledge'),
      user: document.getElementById('wikillm-db-user')?.value || 'u177424397_davidka',
      password: document.getElementById('wikillm-db-pass')?.value || '',
      ip_fallback: document.getElementById('wikillm-db-ip-fallback')?.value || '77.37.35.16',
      connect_timeout: (mode === 'direct')
        ? parseInt(document.getElementById('wikillm-db-direct-timeout')?.value || '10', 10)
        : parseInt(document.getElementById('wikillm-db-api-timeout')?.value || '15', 10),
      php_api_url: document.getElementById('wikillm-db-php-url')?.value || 'https://srv1502.hstgr.io/wikillm_hostinger.php',
      php_api_key: document.getElementById('wikillm-db-php-key')?.value || ''
    },
    sqlite_path: document.getElementById('wikillm-db-sqlite-path')?.value || '%ProgramData%/{app_name}/apps/windows/knowledge.db'
  };

  try {
    const res = await fetch('/api/v1/wikillm/db/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      updateActiveDbBanner(payload.engine, payload.mariadb.connection_type);
      notifyUser('Активная база данных успешно изменена и сохранена', 'success');
    } else {
      const err = await res.json();
      alert('Ошибка сохранения настроек БД: ' + (err.detail || 'Неизвестная ошибка'));
    }
  } catch (e) {
    console.error('[WikiLLM DB] Ошибка сохранения настроек:', e);
    alert('Ошибка соединения при сохранении настроек БД');
  }
}

/**
 * Проверка подключения к MariaDB и аудит таблиц.
 * @returns {Promise<void>}
 */
export async function checkWikiLLMDbConnection() {
  const resultBox = document.getElementById('wikillm-db-check-result');
  const spinner = document.getElementById('wikillm-db-spinner');
  const headerStatus = document.getElementById('wikillm-db-header-status');
  if (!resultBox) return;

  const mode = getActiveConnMode();
  const statusMsg = (mode === 'sqlite')
    ? 'Выполняется проверка локальной базы данных SQLite и структуры таблиц...'
    : 'Выполняется проверка сервера MariaDB и структуры базы данных...';

  if (spinner) spinner.style.display = 'inline-block';
  resultBox.style.display = 'block';
  resultBox.innerHTML = `
    <div class="alert alert-secondary py-2 px-3 small d-flex align-items-center gap-2 mb-0">
      <span class="spinner-border spinner-border-sm text-info" role="status"></span>
      <span>${statusMsg}</span>
    </div>
  `;

  try {
    const payload = getDbFormParams();
    const res = await fetch('/api/v1/wikillm/db/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (spinner) spinner.style.display = 'none';

    // 1. Сбой связи
    if (!data.ok || !data.connected) {
      if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i>Ошибка связи</span>';
      resultBox.innerHTML = `
        <div class="alert alert-danger py-2 px-3 mb-0">
          <div class="d-flex align-items-center gap-2 mb-1">
            <i class="bi bi-x-circle-fill fs-5 text-danger"></i>
            <strong class="text-danger">Ошибка проверки базы данных</strong>
          </div>
          <div class="small mb-2">${data.message || data.error || 'Не удалось получить доступ к базе данных.'}</div>
        </div>
      `;
      return;
    }

    // Режим SQLite
    if (data.engine === 'sqlite') {
      if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>SQLite готов</span>';
      const count = data.total_records || data.sqlite_info?.total_records || 0;
      const path = data.sqlite_info?.path || document.getElementById('wikillm-db-sqlite-path')?.value || 'data/windows_wikillm/knowledge.db';
      resultBox.innerHTML = `
        <div class="alert alert-success py-2 px-3 mb-0">
          <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-1">
            <div class="d-flex align-items-center gap-2">
              <i class="bi bi-check-circle-fill fs-5 text-success"></i>
              <strong>Локальная база подсказок SQLite готова к работе!</strong>
            </div>
            <span class="ui-badge ui-badge-neutral">SQLite (${count} подсказок)</span>
          </div>
          <div class="small mb-1">Файл: <code>${path}</code></div>
          <div class="small text-secondary">${data.message}</div>
        </div>
      `;
      return;
    }

    // 2. База данных отсутствует
    if (data.stage === 'database_missing') {
      if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i>База отсутствует</span>';
      resultBox.innerHTML = `
        <div class="alert alert-warning py-2 px-3 mb-0">
          <div class="d-flex align-items-center gap-2 mb-1">
            <i class="bi bi-exclamation-triangle-fill fs-5 text-warning"></i>
            <strong>Сервер доступен (${data.active_host}, ${data.server_version}), но база данных не найдена</strong>
          </div>
          <div class="small mb-2">База данных <code>${data.database}</code> отсутствует на сервере MariaDB.</div>
          <div class="d-flex align-items-center gap-2 mt-2">
            <button type="button" class="btn btn-sm btn-warning fw-bold" id="wikillm-btn-act-create-db">
              <i class="bi bi-database-add me-1"></i>Создать базу данных "${data.database}"
            </button>
          </div>
        </div>
      `;
      const createBtn = document.getElementById('wikillm-btn-act-create-db');
      if (createBtn) createBtn.addEventListener('click', createWikiLLMDatabase);
      return;
    }

    // 3. База найдена, но пустая или нет таблиц
    const tables = data.tables || {};
    const knowledgeTbl = tables.wikillm_knowledge || {};
    const toolsTbl = tables.wikillm_procedural_tools || {};
    const profilesTbl = tables.wiki_llm_profiles || {};

    if (data.stage === 'tables_setup_needed' || data.is_empty) {
      if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-info"><i class="bi bi-info-circle-fill me-1"></i>Требуется настройка</span>';
      const sqliteRecords = data.sqlite_info?.total_records || 0;
      const sqlitePath = data.sqlite_info?.path || 'knowledge.db';

      resultBox.innerHTML = `
        <div class="alert alert-info py-2 px-3 mb-0">
          <div class="d-flex align-items-center gap-2 mb-1">
            <i class="bi bi-info-circle-fill fs-5 text-info"></i>
            <strong>База данных "${data.database}" найдена (${data.server_version})</strong>
          </div>
          <div class="small mb-2">
            Состояние таблиц базы данных:
            <ul class="mb-2 ps-3 mt-1">
              <li><code>wikillm_knowledge</code>: ${knowledgeTbl.exists ? '<span class="text-success fw-semibold">создана</span> (записей: ' + knowledgeTbl.count + ')' : '<span class="text-danger">отсутствует</span>'}</li>
              <li><code>wikillm_procedural_tools</code>: ${toolsTbl.exists ? '<span class="text-success fw-semibold">создана</span> (записей: ' + toolsTbl.count + ')' : '<span class="text-danger">отсутствует</span>'}</li>
              <li><code>wiki_llm_profiles</code>: ${profilesTbl.exists ? '<span class="text-success fw-semibold">создана</span> (записей: ' + profilesTbl.count + ')' : '<span class="text-danger">отсутствует</span>'}</li>
            </ul>
            Таблицы еще не заполнены данными или требуют инициализации. Выберите действие:
          </div>
          <div class="d-flex gap-2 flex-wrap mt-2">
            <button type="button" class="btn btn-sm btn-outline-primary" id="wikillm-btn-act-init-tables">
              <i class="bi bi-table me-1"></i>Создать пустые таблицы
            </button>
            <button type="button" class="btn btn-sm btn-success fw-bold" id="wikillm-btn-act-import-sqlite">
              <i class="bi bi-box-arrow-in-down me-1"></i>Импортировать из локальной базы (${sqliteRecords} записей из ${sqlitePath})
            </button>
          </div>
        </div>
      `;
      const initBtn = document.getElementById('wikillm-btn-act-init-tables');
      if (initBtn) initBtn.addEventListener('click', initWikiLLMEmptyTables);
      const importBtn = document.getElementById('wikillm-btn-act-import-sqlite');
      if (importBtn) importBtn.addEventListener('click', importWikiLLMFromSqlite);
      return;
    }

    // 4. Готово
    if (headerStatus) headerStatus.innerHTML = '<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i>Подключено (Готово)</span>';
    resultBox.innerHTML = `
      <div class="alert alert-success py-2 px-3 mb-0">
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-1">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-check-circle-fill fs-5 text-success"></i>
            <strong>База данных "${data.database}" полностью готова к работе!</strong>
          </div>
          <span class="ui-badge ui-badge-success">${data.active_host} (${data.server_version})</span>
        </div>
        <div class="small mb-2">
          Таблицы активны:
          <strong>wikillm_knowledge</strong> (${knowledgeTbl.count} сущностей),
          <strong>wikillm_procedural_tools</strong> (${toolsTbl.count} инструментов),
          <strong>wiki_llm_profiles</strong> (${profilesTbl.count} профилей).
        </div>
        <div class="d-flex gap-2 align-items-center mt-2 flex-wrap">
          <button type="button" class="btn btn-sm btn-outline-secondary" id="wikillm-btn-act-reimport">
            <i class="bi bi-arrow-repeat me-1"></i>Синхронизировать / Ре-импорт из SQLite
          </button>
        </div>
      </div>
    `;
    const reimportBtn = document.getElementById('wikillm-btn-act-reimport');
    if (reimportBtn) reimportBtn.addEventListener('click', importWikiLLMFromSqlite);

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
 * Создание базы данных MariaDB.
 * @returns {Promise<void>}
 */
export async function createWikiLLMDatabase() {
  return createDbAction(getDbFormParams, checkWikiLLMDbConnection);
}

/**
 * Создание пустых таблиц WikiLLM.
 * @returns {Promise<void>}
 */
export async function initWikiLLMEmptyTables() {
  return initTablesAction(getDbFormParams, checkWikiLLMDbConnection);
}

/**
 * Импорт данных из локальной SQLite в MariaDB.
 * @returns {Promise<void>}
 */
export async function importWikiLLMFromSqlite() {
  return importSqliteAction(getDbFormParams, checkWikiLLMDbConnection);
}

/**
 * Привязка событий к элементам карточки базы данных.
 */
export function bindWikiLLMDbButtons() {
  document.querySelectorAll('input[name="wikillm-conn-mode"]').forEach(radio => {
    if (!radio._bound) {
      radio._bound = true;
      radio.addEventListener('change', () => {
        applyConnModeVisibility(radio.value);
      });
    }
  });

  const togglePassBtn = document.getElementById('wikillm-db-toggle-pass');
  if (togglePassBtn && !togglePassBtn._bound) {
    togglePassBtn._bound = true;
    togglePassBtn.addEventListener('click', () => {
      const passInp = document.getElementById('wikillm-db-pass');
      if (!passInp) return;
      const isPass = (passInp.type === 'password');
      passInp.type = isPass ? 'text' : 'password';
      togglePassBtn.innerHTML = isPass ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  }

  const checkBtn = document.getElementById('wikillm-db-btn-check');
  if (checkBtn && !checkBtn._bound) {
    checkBtn._bound = true;
    checkBtn.addEventListener('click', checkWikiLLMDbConnection);
  }

  const initTablesBtn = document.getElementById('wikillm-db-btn-init-tables');
  if (initTablesBtn && !initTablesBtn._bound) {
    initTablesBtn._bound = true;
    initTablesBtn.addEventListener('click', initWikiLLMEmptyTables);
  }

  const saveCfgBtn = document.getElementById('wikillm-db-btn-save-cfg');
  if (saveCfgBtn && !saveCfgBtn._bound) {
    saveCfgBtn._bound = true;
    saveCfgBtn.addEventListener('click', saveWikiLLMDbConfig);
  }
}

/**
 * Инициализация панели конфигурации БД WikiLLM.
 * @returns {Promise<void>}
 */
export async function initWikiLLMDbPanel() {
  bindWikiLLMDbButtons();
  await loadWikiLLMDbConfig();
}
