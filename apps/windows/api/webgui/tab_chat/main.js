/**
 * =============================================================================
 * Process Name: Windows Chat - Main Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки AI Chat. Координирует работу панелей сессий,
 *   истории сообщений, параметров запросов и стриминговой генерации ответов.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/tab_chat/main.js?v=20261017_v1" type="module"></script>
 *
 * File: main.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import {
  loadSessions,
  renderSessionsList,
  initSidebarControls,
  updateChatCacheStatus,
  setOnSessionSwitch,
  createNewSession,
  switchSession,
  renameSession,
  deleteSession
} from './panel_sessions/panel.js';

import {
  renderActiveSessionMessages,
  initMessagesControls,
  clearCurrentSession,
  handleRemoteTranscript
} from './panel_messages/panel.js';

import {
  initInputControls,
  handleExternalChatPrompt
} from './panel_input/panel.js';

import { sendMessage } from './panel_stream/panel.js';

/**
 * Инициализирует вкладку Windows Chat.
 */
export function initChatTab() {
  // Настройка обратной связи при смене сессии
  setOnSessionSwitch((session) => {
    renderActiveSessionMessages(session);
  });

  // Загрузка сессий и первичный рендеринг
  loadSessions();
  renderSessionsList();
  renderActiveSessionMessages();
  updateChatCacheStatus();

  // Инициализация контролов панелей
  initSidebarControls();
  initMessagesControls();
  initInputControls(sendMessage);

  // Экспорт функции отправки в глобальную область
  window.sendChatMessage = sendMessage;
}

// Экспорт методов в window для внешних сценариев и хост-контейнера
if (typeof window !== 'undefined') {
  window.initChatTab = initChatTab;
  window.sendChatMessage = sendMessage;
  window.handleExternalChatPrompt = (payload) => handleExternalChatPrompt(payload, sendMessage);
  window.handleRemoteTranscript = handleRemoteTranscript;
  window.clearChatHistory = clearCurrentSession;
  window.createNewSession = createNewSession;
  window.switchSession = switchSession;
  window.renameSession = renameSession;
  window.deleteSession = deleteSession;

  if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && msg.action === 'ai_tc_external_chat_prompt') {
        handleExternalChatPrompt(msg, sendMessage);
      }
    });
  }
}
