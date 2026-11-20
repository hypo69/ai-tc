/**
 * =============================================================================
 * Process Name: Windows Chat - Streaming and Dispatch Panel
 * =============================================================================
 * Description:
 *   Модуль отправки сообщений, стриминговой генерации ответа модели с RAF,
 *   озвучивания ответов через TTS и обработки ошибок инференса.
 *
 * File: panel_stream/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/panel_stream
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import { parseContentToHtml, generateSessionTitle } from '../common/ui_utils.js';
import {
  getActiveSession,
  saveSessions,
  renderSessionsList
} from '../panel_sessions/panel.js';
import { addMessageToDom } from '../panel_messages/panel.js';
import { setStatus, getGenerationParams } from '../panel_input/panel.js';

/**
 * Отправляет пользовательское сообщение и инициирует потоковый ответ модели.
 */
export async function sendMessage() {
  const input = document.getElementById('message-input');
  const btn = document.getElementById('send-button');

  if (!input || !btn) return;

  if (!window.activeModelName) {
    input.disabled = true;
    btn.disabled = true;
    input.placeholder = 'Ни одна модель не выбрана. Выберите модель во вкладке «Модели и API».';
    input.classList.add('is-invalid');
    return;
  }

  const msg = input.value.trim();
  if (!msg) return;

  const session = getActiveSession();
  if (!session) return;

  const { topK, minScore, outputMode, isRagEnabled, shouldSpeak } = getGenerationParams();

  input.value = '';
  input.disabled = true;
  btn.disabled = true;

  setStatus('Отправка запроса...', true);
  const userTimeStr = new Date().toLocaleTimeString();

  const chatWin = document.getElementById('chat-window');
  if (chatWin && session.messages.length === 0) {
    chatWin.innerHTML = '';
  }

  addMessageToDom('user', msg, null, userTimeStr);
  session.messages.push({ sender: 'user', text: msg, timeStr: userTimeStr });

  if ((!session.title || session.title === 'Новый чат' || session.title === 'Предыдущий диалог') && !session.isCustomTitle) {
    session.title = generateSessionTitle(msg);
    renderSessionsList();
  }

  saveSessions();

  const win = document.getElementById('chat-window');
  const botMessageEl = document.createElement('div');
  botMessageEl.className = 'message bot-message';
  const timeStr = new Date().toLocaleTimeString();
  const modeBadge = outputMode === 'voice_only' ? '<span class="badge bg-secondary-subtle text-secondary me-1"><i class="bi bi-volume-up"></i> Голос</span>' : '';
  botMessageEl.innerHTML = `
    <div class="d-flex align-items-center justify-content-between mb-1">
      <div><strong>AI Assistant</strong> ${modeBadge}<span class="text-muted">(${timeStr})</span></div>
      <button class="btn btn-sm btn-outline-secondary py-0 px-2 btn-speak-message d-none" title="Озвучить ответ" type="button">
        <i class="bi bi-volume-up"></i>
      </button>
    </div>
    <div class="bot-text"><span class="text-muted">⏳ Ожидание ответа...</span></div>
  `;
  if (win) {
    win.appendChild(botMessageEl);
    win.scrollTop = win.scrollHeight;
  }
  const textDiv = botMessageEl.querySelector('.bot-text');
  const speakBtn = botMessageEl.querySelector('.btn-speak-message');

  let fullReply = '';
  let started = false;

  try {
    const generationConfig = {
      top_k: topK,
      min_score: minScore,
      threshold: minScore,
      rag_enabled: isRagEnabled,
      output_mode: outputMode,
      tts_enabled: shouldSpeak,
      model: window.activeModelName || undefined,
      search_engine: window.activeSearchEngine || undefined
    };

    let rafId = null;
    const scheduleRender = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (textDiv) {
          textDiv.innerHTML = parseContentToHtml(fullReply);
        }
        if (win) win.scrollTop = win.scrollHeight;
      });
    };

    const replyObj = await window.chatService.sendChatMessage(
      msg,
      (chunk, status) => {
        if (status) {
          setStatus(status, true);
        }
        if (chunk) {
          if (!started) {
            if (textDiv) textDiv.textContent = '';
            started = true;
          }
          fullReply += chunk;
          scheduleRender();
        }
      },
      session.chatHistory || [],
      generationConfig
    );

    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }

    const finalReply = replyObj.text || fullReply;
    if (textDiv) {
      if (outputMode === 'voice_only' && !finalReply.trim() && replyObj.voice) {
        textDiv.innerHTML = `<em><i class="bi bi-soundwave me-1"></i>${parseContentToHtml(replyObj.voice)}</em>`;
      } else {
        textDiv.innerHTML = parseContentToHtml(finalReply);
      }
    }

    if (speakBtn) {
      speakBtn.classList.remove('d-none');
      speakBtn.addEventListener('click', () => {
        if (window.chatService?.speak) {
          window.chatService.speak(replyObj || finalReply);
        }
      });
    }

    if (shouldSpeak && window.chatService?.speak) {
      window.chatService.speak(replyObj || finalReply);
    }

    if (!session.chatHistory) session.chatHistory = [];
    session.chatHistory.push({ role: 'user', parts: [msg] });
    session.chatHistory.push({ role: 'model', parts: [finalReply || replyObj.voice || ''] });

    session.messages.push({
      sender: 'bot',
      text: finalReply,
      voiceText: replyObj.voice || null,
      timeStr: timeStr,
      mode: outputMode
    });
    session.updatedAt = Date.now();
    saveSessions();

    setStatus('', false);
  } catch (err) {
    const errText = err instanceof Error ? err.message : typeof err === 'object' && err !== null ? JSON.stringify(err) : String(err);
    if (textDiv) {
      textDiv.innerHTML = `<span style="color: #ff7070;">Ошибка: ${errText}</span>`;
    }
    setStatus('Ошибка исполнения', true);
    setTimeout(() => setStatus('', false), 4000);
  } finally {
    if (window.activeModelName) {
      input.disabled = false;
      btn.disabled = false;
      input.placeholder = 'Введите сообщение...';
      input.classList.remove('is-invalid');
      input.focus();
    } else {
      input.disabled = true;
      btn.disabled = true;
      input.placeholder = 'Ни одна модель не выбрана. Выберите модель во вкладке «Модели и API».';
      input.classList.add('is-invalid');
    }
    if (win) win.scrollTop = win.scrollHeight;
  }
}
