/**
 * =============================================================================
 * Process Name: Windows Chat - Server Sync Engine
 * =============================================================================
 * Description:
 *   Модуль синхронизации локальных сессий чата с серверным API.
 *
 * File: panel_sessions/sync.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/panel_sessions
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { cachedApiFetch } from '../../js/api-cache.js';
import { CACHE_TAG } from '../common/ui_utils.js';

/**
 * Отправляет сессию на бэкенд.
 * @param {Object} session - Данные сессии.
 */
export async function syncSessionToServer(session) {
  if (!session || !session.id) return;
  try {
    await fetch('/api/v1/chat/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: session.id,
        title: session.title || 'Новый чат',
        isCustomTitle: Boolean(session.isCustomTitle),
        createdAt: session.createdAt || Date.now(),
        updatedAt: session.updatedAt || Date.now(),
        messages: session.messages || [],
        chatHistory: session.chatHistory || []
      })
    });
  } catch (err) {
    console.debug('Синхронизация сессии с сервером пропущена:', err);
  }
}

/**
 * Удаляет сессию на сервере.
 * @param {string} sessionId - ID удаляемой сессии.
 */
export async function deleteSessionFromServer(sessionId) {
  if (!sessionId) return;
  try {
    await fetch(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE'
    });
  } catch (err) {
    console.debug('Не удалось удалить сессию на сервере:', err);
  }
}

/**
 * Очищает все сессии на сервере.
 */
export async function clearAllSessionsFromServer() {
  try {
    await fetch('/api/v1/chat/sessions', {
      method: 'DELETE'
    });
  } catch (err) {
    console.debug('Не удалось очистить сессии на сервере:', err);
  }
}

/**
 * Синхронизирует массив локальных сессий с данными сервера.
 * @param {Array} currentSessions - Локальные сессии.
 * @returns {Promise<Array>} Обновленный массив сессий.
 */
export async function fetchAndMergeServerSessions(currentSessions) {
  try {
    const res = await cachedApiFetch('/api/v1/chat/sessions', {
      tags: [CACHE_TAG, 'chat-sessions']
    });
    if (!res.ok) return currentSessions;
    const data = await res.json();
    const serverSessions = data.sessions || [];

    if (currentSessions.length > 0 && serverSessions.length === 0) {
      const syncRes = await fetch('/api/v1/chat/sessions/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessions: currentSessions })
      });
      if (syncRes.ok) {
        const syncData = await syncRes.json();
        if (syncData.sessions && syncData.sessions.length > 0) {
          return syncData.sessions;
        }
      }
      return currentSessions;
    }

    if (serverSessions.length > 0) {
      const serverMap = new Map();
      serverSessions.forEach((s) => serverMap.set(s.id, s));

      const localOnly = [];
      currentSessions.forEach((ls) => {
        if (!serverMap.has(ls.id)) {
          localOnly.push(ls);
        } else {
          const ss = serverMap.get(ls.id);
          if ((ls.updatedAt || 0) > (ss.updatedAt || 0)) {
            serverMap.set(ls.id, ls);
            syncSessionToServer(ls);
          }
        }
      });

      if (localOnly.length > 0) {
        await fetch('/api/v1/chat/sessions/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessions: localOnly })
        });
      }

      return Array.from(serverMap.values()).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    }

    return currentSessions;
  } catch (err) {
    console.debug('Работа сессий в автономном/локальном режиме:', err);
    return currentSessions;
  }
}
