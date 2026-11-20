/**
 * =============================================================================
 * Process Name: Windows Chat - Sessions Panel
 * =============================================================================
 * Description:
 *   Модуль управления сессиями диалогов чата: сохранение в localStorage,
 *   вызов синхронизации с сервером, создание, удаление, переименование и отображение списка.
 *
 * File: panel_sessions/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/panel_sessions
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { clearCacheByTag } from '../../js/api-cache.js';
import {
  STORAGE_KEY_SESSIONS,
  STORAGE_KEY_ACTIVE_SESSION_ID,
  STORAGE_KEY_SIDEBAR_COLLAPSED,
  LEGACY_STORAGE_KEY,
  CACHE_TAG,
  generateSessionTitle
} from '../common/ui_utils.js';
import {
  syncSessionToServer,
  deleteSessionFromServer,
  clearAllSessionsFromServer,
  fetchAndMergeServerSessions
} from './sync.js';

let sessions = [];
let activeSessionId = null;
let syncDebounceTimer = null;
let onSessionSwitchCallback = null;

/**
 * Получает список всех текущих сессий.
 * @returns {Array} Список объектов сессий.
 */
export function getSessions() {
  return sessions;
}

/**
 * Получает идентификатор активной сессии.
 * @returns {string|null} ID сессии.
 */
export function getActiveSessionId() {
  return activeSessionId;
}

/**
 * Устанавливает колбэк при переключении сессии.
 * @param {Function} cb - Функция обратного вызова.
 */
export function setOnSessionSwitch(cb) {
  onSessionSwitchCallback = cb;
}

/**
 * Возвращает активную сессию или создает новую при отсутствии.
 * @returns {Object} Активная сессия.
 */
export function getActiveSession() {
  if (!activeSessionId || sessions.length === 0) {
    return createNewSession('Новый чат', true);
  }
  let session = sessions.find((s) => s.id === activeSessionId);
  if (!session) {
    session = sessions[0];
    activeSessionId = session.id;
  }
  return session;
}

/**
 * Сохраняет сессии исключительно в localStorage.
 */
export function saveLocalSessionsOnly() {
  try {
    localStorage.setItem(STORAGE_KEY_SESSIONS, JSON.stringify(sessions));
    if (activeSessionId) {
      localStorage.setItem(STORAGE_KEY_ACTIVE_SESSION_ID, activeSessionId);
    }
  } catch (err) {
    console.warn('Не удалось сохранить сессии чата в localStorage:', err);
  }
}

/**
 * Сохраняет сессии с отложенной синхронизацией на сервер.
 * @param {boolean} [syncToServer=true] - Флаг синхронизации с сервером.
 */
export function saveSessions(syncToServer = true) {
  saveLocalSessionsOnly();
  if (syncToServer) {
    debounceSyncActiveSession();
  }
}

/**
 * Отложенный запуск синхронизации активной сессии с бэкендом.
 */
function debounceSyncActiveSession() {
  if (syncDebounceTimer) {
    clearTimeout(syncDebounceTimer);
  }
  syncDebounceTimer = setTimeout(() => {
    const active = getActiveSession();
    if (active) {
      syncSessionToServer(active);
    }
  }, 500);
}

/**
 * Синхронизирует локальные сессии с сервером.
 */
export async function syncSessionsWithServer() {
  sessions = await fetchAndMergeServerSessions(sessions);

  if (sessions.length === 0) {
    createNewSession('Новый чат', true);
    return;
  }

  const savedActiveId = localStorage.getItem(STORAGE_KEY_ACTIVE_SESSION_ID);
  if (savedActiveId && sessions.some((s) => s.id === savedActiveId)) {
    activeSessionId = savedActiveId;
  } else {
    activeSessionId = sessions[0].id;
  }

  saveLocalSessionsOnly();
  renderSessionsList();
  if (typeof onSessionSwitchCallback === 'function') {
    onSessionSwitchCallback(getActiveSession());
  }
}

/**
 * Загружает сессии из хранилища и мигрирует устаревшие структуры при необходимости.
 */
export function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_SESSIONS);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        sessions = parsed;
        const savedActiveId = localStorage.getItem(STORAGE_KEY_ACTIVE_SESSION_ID);
        if (savedActiveId && sessions.some((s) => s.id === savedActiveId)) {
          activeSessionId = savedActiveId;
        } else {
          activeSessionId = sessions[0].id;
        }
        syncSessionsWithServer();
        return;
      }
    }

    const legacyRaw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (legacyRaw) {
      try {
        const legacyLog = JSON.parse(legacyRaw);
        if (Array.isArray(legacyLog) && legacyLog.length > 0) {
          const firstUserMsg = legacyLog.find((m) => m.sender === 'user');
          const title = firstUserMsg ? generateSessionTitle(firstUserMsg.text) : 'Предыдущий диалог';
          const legacyHistory = [];
          for (const item of legacyLog) {
            legacyHistory.push({
              role: item.sender === 'user' ? 'user' : 'model',
              parts: [item.text || item.voiceText || '']
            });
          }

          const legacySession = {
            id: 'session_' + Date.now(),
            title: title,
            isCustomTitle: false,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messages: legacyLog,
            chatHistory: legacyHistory
          };
          sessions = [legacySession];
          activeSessionId = legacySession.id;
          saveSessions();
          syncSessionsWithServer();
          return;
        }
      } catch (e) {
        console.warn('Ошибка миграции устаревшей истории диалогов:', e);
      }
    }

    createNewSession('Новый чат', true);
    syncSessionsWithServer();
  } catch (err) {
    console.warn('Ошибка загрузки сессий чата:', err);
    sessions = [];
    createNewSession('Новый чат', true);
    syncSessionsWithServer();
  }
}

/**
 * Создает новый диалог и опционально делает его активным.
 * @param {string} [title='Новый чат'] - Заголовок.
 * @param {boolean} [makeActive=true] - Сделать активным.
 * @returns {Object} Созданная сессия.
 */
export function createNewSession(title = 'Новый чат', makeActive = true) {
  const newSession = {
    id: 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
    title: title,
    isCustomTitle: false,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
    chatHistory: []
  };

  sessions.unshift(newSession);
  if (makeActive) {
    activeSessionId = newSession.id;
  }
  saveSessions();
  renderSessionsList();
  if (typeof onSessionSwitchCallback === 'function') {
    onSessionSwitchCallback(newSession);
  }
  return newSession;
}

/**
 * Переключает активный диалог.
 * @param {string} sessionId - ID сессии.
 */
export function switchSession(sessionId) {
  if (sessionId === activeSessionId) return;
  const session = sessions.find((s) => s.id === sessionId);
  if (!session) return;

  activeSessionId = sessionId;
  saveSessions(false);
  renderSessionsList();
  if (typeof onSessionSwitchCallback === 'function') {
    onSessionSwitchCallback(session);
  }

  const msgInput = document.getElementById('message-input');
  if (msgInput) msgInput.focus();
}

/**
 * Переименовывает указанную сессию.
 * @param {string} sessionId - ID сессии.
 * @param {string|null} [newTitle=null] - Новое название.
 */
export function renameSession(sessionId, newTitle = null) {
  const session = sessions.find((s) => s.id === sessionId);
  if (!session) return;

  let title = newTitle;
  if (title === null) {
    title = prompt('Введите новое название диалога:', session.title);
  }

  if (title && title.trim()) {
    session.title = title.trim();
    session.isCustomTitle = true;
    session.updatedAt = Date.now();
    saveSessions();
    renderSessionsList();
    if (session.id === activeSessionId) {
      updateCurrentSessionHeader();
    }
  }
}

/**
 * Удаляет сессию из списка.
 * @param {string} sessionId - ID сессии.
 */
export function deleteSession(sessionId) {
  const index = sessions.findIndex((s) => s.id === sessionId);
  if (index === -1) return;

  sessions.splice(index, 1);
  if (sessions.length === 0) {
    createNewSession('Новый чат', true);
  } else if (activeSessionId === sessionId) {
    activeSessionId = sessions[0].id;
    if (typeof onSessionSwitchCallback === 'function') {
      onSessionSwitchCallback(getActiveSession());
    }
  }

  saveSessions(false);
  deleteSessionFromServer(sessionId);
  renderSessionsList();
}

/**
 * Очищает все сохраненные сессии.
 */
export function clearAllSessions() {
  if (!confirm('Вы уверены, что хотите удалить ВСЕ сохраненные диалоги?')) return;

  sessions = [];
  try {
    localStorage.removeItem(STORAGE_KEY_SESSIONS);
    localStorage.removeItem(STORAGE_KEY_ACTIVE_SESSION_ID);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch (e) {}

  clearCacheByTag(CACHE_TAG).catch((err) => console.debug('Не удалось очистить кеш чата:', err));
  clearAllSessionsFromServer();
  createNewSession('Новый чат', true);
}

/**
 * Актуализирует заголовок текущего активного чата в шапке.
 */
export function updateCurrentSessionHeader() {
  const titleEl = document.getElementById('chat-current-title');
  const session = getActiveSession();
  if (titleEl && session) {
    titleEl.textContent = session.title || 'Новый чат';
    titleEl.title = session.title || 'Новый чат';
  }
}

/**
 * Рендерит боковой список диалогов.
 */
export function renderSessionsList() {
  const listEl = document.getElementById('chat-sessions-list');
  const countEl = document.getElementById('chat-sessions-count');
  if (!listEl) return;

  listEl.innerHTML = '';
  if (countEl) {
    countEl.textContent = `${sessions.length} ${sessions.length === 1 ? 'чат' : sessions.length < 5 ? 'чата' : 'чатов'}`;
  }

  updateCurrentSessionHeader();

  sessions.forEach((session) => {
    const item = document.createElement('div');
    const isActive = session.id === activeSessionId;
    item.className = 'chat-session-item d-flex align-items-center justify-content-between p-1 px-2 rounded mb-1' + (isActive ? ' active' : '');
    item.dataset.sessionId = session.id;

    item.innerHTML = `
      <div class="chat-session-title d-flex align-items-center gap-1 text-truncate flex-grow-1 me-1" title="${session.title}">
        <i class="bi bi-chat-text ${isActive ? 'text-primary' : 'text-muted'} flex-shrink-0"></i>
        <span class="text-truncate">${session.title}</span>
      </div>
      <div class="chat-session-actions d-flex align-items-center gap-1 flex-shrink-0">
        <button class="btn btn-sm btn-link text-muted p-0 btn-rename" title="Переименовать" type="button">
          <i class="bi bi-pencil" style="font-size: 0.8rem;"></i>
        </button>
        <button class="btn btn-sm btn-link text-danger p-0 btn-delete" title="Удалить" type="button">
          <i class="bi bi-trash" style="font-size: 0.8rem;"></i>
        </button>
      </div>
    `;

    item.addEventListener('click', (e) => {
      if (e.target.closest('.btn-rename') || e.target.closest('.btn-delete')) return;
      switchSession(session.id);
    });

    const renameBtn = item.querySelector('.btn-rename');
    if (renameBtn) {
      renameBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        renameSession(session.id);
      });
    }

    const deleteBtn = item.querySelector('.btn-delete');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm(`Удалить диалог "${session.title}"?`)) {
          deleteSession(session.id);
        }
      });
    }

    listEl.appendChild(item);
  });
}

/**
 * Обновляет бейдж коэффициента кэша API.
 */
export function updateChatCacheStatus() {
  const badge = document.getElementById('chat-cache-badge');
  const ratio = document.getElementById('chat-cache-ratio');
  if (!badge || !ratio) return;

  try {
    const stats = window.apiCacheStats || { hits: 0, total: 0 };
    const hitRate = stats.total > 0 ? Math.round((stats.hits / stats.total) * 100) : 0;
    ratio.textContent = `${hitRate}%`;

    badge.className = 'badge cache-badge';
    if (hitRate >= 70) {
      badge.classList.add('bg-success-subtle', 'text-success');
    } else if (hitRate >= 40) {
      badge.classList.add('bg-warning-subtle', 'text-warning');
    } else {
      badge.classList.add('bg-secondary-subtle', 'text-secondary');
    }
  } catch (err) {
    console.debug('Ошибка обновления статуса кеша:', err);
  }
}

/**
 * Очищает кэш сессий и чата.
 */
export async function clearChatCache() {
  try {
    await clearCacheByTag(CACHE_TAG);
    updateChatCacheStatus();
  } catch (err) {
    console.error('Ошибка очистки кеша чата:', err);
  }
}

/**
 * Инициализирует интерактивные кнопки боковой панели сессий.
 */
export function initSidebarControls() {
  const sidebar = document.getElementById('chat-sidebar');
  const sidebarToggleBtn = document.getElementById('chat-sidebar-toggle-btn');
  if (sidebar && sidebarToggleBtn) {
    const isCollapsed = localStorage.getItem(STORAGE_KEY_SIDEBAR_COLLAPSED) === 'true';
    if (isCollapsed) {
      sidebar.classList.add('collapsed');
      sidebar.style.display = 'none';
    }

    sidebarToggleBtn.addEventListener('click', () => {
      const isCurrentlyCollapsed = sidebar.classList.toggle('collapsed');
      sidebar.style.display = isCurrentlyCollapsed ? 'none' : 'flex';
      localStorage.setItem(STORAGE_KEY_SIDEBAR_COLLAPSED, isCurrentlyCollapsed);
    });
  }

  const newSessionBtn = document.getElementById('chat-new-session-btn');
  if (newSessionBtn) {
    newSessionBtn.addEventListener('click', () => {
      createNewSession('Новый чат', true);
      const msgInput = document.getElementById('message-input');
      if (msgInput) msgInput.focus();
    });
  }

  const clearAllBtn = document.getElementById('chat-clear-all-sessions-btn');
  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', () => {
      clearAllSessions();
    });
  }

  const clearCacheBtn = document.getElementById('chat-clear-cache-btn');
  if (clearCacheBtn) {
    clearCacheBtn.addEventListener('click', async () => {
      await clearChatCache();
      await syncSessionsWithServer();
      renderSessionsList();
    });
  }

  const renameCurrentBtn = document.getElementById('chat-rename-current-btn');
  if (renameCurrentBtn) {
    renameCurrentBtn.addEventListener('click', () => {
      if (activeSessionId) {
        renameSession(activeSessionId);
      }
    });
  }
}
