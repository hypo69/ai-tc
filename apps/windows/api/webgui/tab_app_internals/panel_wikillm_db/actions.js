/**
 * =============================================================================
 * Process Name: Windows App Internals - WikiLLM DB Actions
 * =============================================================================
 * Description:
 *   Модуль операций с базой данных WikiLLM (создание БД, инициализация таблиц, импорт).
 *
 * File: actions.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_app_internals/panel_wikillm_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:05:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261031_v2';

/**
 * Создание базы данных MariaDB.
 * @param {Function} getDbFormParams
 * @param {Function} checkWikiLLMDbConnection
 * @returns {Promise<void>}
 */
export async function createWikiLLMDatabase(getDbFormParams, checkWikiLLMDbConnection) {
  const btn = document.getElementById('wikillm-btn-act-create-db');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Создание базы...';
  }
  try {
    const payload = getDbFormParams();
    const res = await fetch('/api/v1/wikillm/db/create-database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      notifyUser(data.message || 'База данных успешно создана', 'success');
      await checkWikiLLMDbConnection();
    } else {
      alert('Ошибка создания базы: ' + (data.message || data.error));
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-database-add me-1"></i>Создать базу данных';
      }
    }
  } catch (e) {
    alert('Ошибка при создании базы: ' + e);
    if (btn) btn.disabled = false;
  }
}

/**
 * Создание пустых таблиц WikiLLM.
 * @param {Function} getDbFormParams
 * @param {Function} checkWikiLLMDbConnection
 * @returns {Promise<void>}
 */
export async function initWikiLLMEmptyTables(getDbFormParams, checkWikiLLMDbConnection) {
  const btn = document.getElementById('wikillm-btn-act-init-tables');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Создание таблиц...';
  }
  try {
    const payload = getDbFormParams();
    const res = await fetch('/api/v1/wikillm/db/init-tables', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      notifyUser('Пустые таблицы WikiLLM успешно инициализированы', 'success');
      await checkWikiLLMDbConnection();
    } else {
      alert('Ошибка инициализации таблиц: ' + (data.message || data.error));
      if (btn) btn.disabled = false;
    }
  } catch (e) {
    alert('Ошибка при создании таблиц: ' + e);
    if (btn) btn.disabled = false;
  }
}

/**
 * Импорт данных из локальной SQLite в MariaDB.
 * @param {Function} getDbFormParams
 * @param {Function} checkWikiLLMDbConnection
 * @returns {Promise<void>}
 */
export async function importWikiLLMFromSqlite(getDbFormParams, checkWikiLLMDbConnection) {
  const importBtn = document.getElementById('wikillm-btn-act-import-sqlite') || document.getElementById('wikillm-btn-act-reimport');
  if (importBtn) {
    importBtn.disabled = true;
    importBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выполняется импорт...';
  }
  try {
    const payload = getDbFormParams();
    const res = await fetch('/api/v1/wikillm/db/import-sqlite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      notifyUser(data.message || 'Данные успешно импортированы', 'success');
      await checkWikiLLMDbConnection();
    } else {
      alert('Ошибка импорта данных: ' + (data.message || data.error));
      if (importBtn) importBtn.disabled = false;
    }
  } catch (e) {
    alert('Ошибка при импорте данных: ' + e);
    if (importBtn) importBtn.disabled = false;
  }
}
