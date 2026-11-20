/**
 * =============================================================================
 * Process Name: Windows Chat - Messages Panel
 * =============================================================================
 * Description:
 *   Модуль отрисовки окна сообщений, форматирования реплик пользователя и бота,
 *   кнопок озвучивания ответа через TTS и обработки удаленных транскриптов.
 *
 * File: panel_messages/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/panel_messages
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { parseContentToHtml, generateSessionTitle } from '../common/ui_utils.js';
import {
  getActiveSession,
  saveSessions,
  renderSessionsList,
  updateCurrentSessionHeader
} from '../panel_sessions/panel.js';

/**
 * Очищает текущий активный диалог.
 */
export function clearCurrentSession() {
  const session = getActiveSession();
  if (!session) return;

  session.messages = [];
  session.chatHistory = [];
  session.title = 'Новый чат';
  session.isCustomTitle = false;
  session.updatedAt = Date.now();

  saveSessions();
  renderSessionsList();
  renderActiveSessionMessages();
}

/**
 * Добавляет элемент реплики в DOM чата.
 * @param {string} sender - Отправитель ('user' или 'bot').
 * @param {string} text - Текст сообщения.
 * @param {string|null} [voiceText=null] - Текст голосового ответа.
 * @param {string|null} [timeStr=null] - Строка времени.
 * @param {string|null} [outputMode=null] - Режим вывода.
 * @returns {HTMLElement|null} Созданный DOM-элемент.
 */
export function addMessageToDom(sender, text, voiceText = null, timeStr = null, outputMode = null) {
  const win = document.getElementById('chat-window');
  if (!win) return null;

  const el = document.createElement('div');
  el.className = 'message ' + (sender === 'user' ? 'user-message' : 'bot-message');

  const displayText = parseContentToHtml(text);
  const formattedTime = timeStr || new Date().toLocaleTimeString();

  if (sender === 'user') {
    el.innerHTML = `<strong>Вы</strong> (${formattedTime}): <div class="message-content">${displayText}</div>`;
  } else {
    const modeBadge = outputMode === 'voice_only' ? '<span class="badge bg-secondary-subtle text-secondary me-1"><i class="bi bi-volume-up"></i> Голос</span>' : '';
    el.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-1">
        <div><strong>AI Assistant</strong> ${modeBadge}<span class="text-muted">(${formattedTime})</span></div>
        <button class="btn btn-sm btn-outline-secondary py-0 px-2 btn-speak-message" title="Озвучить ответ" type="button">
          <i class="bi bi-volume-up"></i>
        </button>
      </div>
      <div class="message-content">${displayText || (voiceText ? `<em><i class="bi bi-soundwave me-1"></i>${parseContentToHtml(voiceText)}</em>` : '')}</div>
    `;
    const speakBtn = el.querySelector('.btn-speak-message');
    if (speakBtn) {
      speakBtn.addEventListener('click', () => {
        if (window.chatService?.speak) {
          window.chatService.speak(voiceText || text);
        }
      });
    }
  }

  win.appendChild(el);
  win.scrollTop = win.scrollHeight;
  return el;
}

/**
 * Рендерит всю историю сообщений для активной сессии.
 * @param {Object} [targetSession=null] - Сессия для рендеринга.
 */
export function renderActiveSessionMessages(targetSession = null) {
  const chatWindow = document.getElementById('chat-window');
  if (!chatWindow) return;

  chatWindow.innerHTML = '';
  const session = targetSession || getActiveSession();

  if (session && session.messages && session.messages.length > 0) {
    for (const msg of session.messages) {
      addMessageToDom(msg.sender, msg.text, msg.voiceText, msg.timeStr, msg.mode);
    }
  } else {
    const welcome = document.createElement('div');
    welcome.className = 'message bot-message';
    welcome.innerHTML = '<strong>AI Assistant</strong>: Добро пожаловать! Задайте любой вопрос в поле ввода.';
    chatWindow.appendChild(welcome);
  }

  chatWindow.scrollTop = chatWindow.scrollHeight;
  updateCurrentSessionHeader();
}

/**
 * Обрабатывает удаленный входящий голосовой транскрипт (например, от ассистента или фонового стрима).
 * @param {string} text - Распознанный текст речи.
 */
export function handleRemoteTranscript(text) {
  if (!text || !text.trim()) return;
  const cleanText = text.trim();

  const session = getActiveSession();
  if (!session) return;

  const userTimeStr = new Date().toLocaleTimeString();

  const chatWin = document.getElementById('chat-window');
  if (chatWin && session.messages.length === 0) {
    chatWin.innerHTML = '';
  }

  addMessageToDom('user', cleanText, null, userTimeStr);
  session.messages.push({ sender: 'user', text: cleanText, timeStr: userTimeStr });

  if ((!session.title || session.title === 'Новый чат' || session.title === 'Предыдущий диалог') && !session.isCustomTitle) {
    session.title = generateSessionTitle(cleanText);
    renderSessionsList();
  }

  session.updatedAt = Date.now();
  saveSessions();

  if (chatWin) {
    chatWin.scrollTop = chatWin.scrollHeight;
  }
}

/**
 * Инициализирует элементы управления окном сообщений.
 */
export function initMessagesControls() {
  const clearBtn = document.getElementById('chat-clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (confirm('Очистить сообщения текущего диалога?')) {
        clearCurrentSession();
      }
    });
  }
}
