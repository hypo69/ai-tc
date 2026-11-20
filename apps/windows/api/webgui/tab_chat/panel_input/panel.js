/**
 * =============================================================================
 * Process Name: Windows Chat - Input and Controls Panel
 * =============================================================================
 * Description:
 *   Модуль обработки параметров отправки, настроек RAG, режима вывода (текст/голос),
 *   индикации выполнения запроса и перехвата внешних промптов.
 *
 * File: panel_input/panel.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/panel_input
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

/**
 * Управляет отображением индикатора выполнения запроса.
 * @param {string} statusText - Сообщение о статусе.
 * @param {boolean} [isVisible=true] - Видимость индикатора.
 */
export function setStatus(statusText, isVisible = true) {
  const indicator = document.getElementById('chat-status-indicator');
  const textEl = document.getElementById('chat-status-text');
  if (!indicator || !textEl) return;

  if (isVisible) {
    textEl.textContent = statusText || 'Обработка запроса...';
    indicator.classList.remove('d-none');
  } else {
    indicator.classList.add('d-none');
  }
}

/**
 * Переключает доступность полей конфигурации RAG.
 * @param {boolean} enabled - Флаг активности.
 */
function updateRagInputsState(enabled) {
  const topKInput = document.getElementById('chat-top-k');
  const minScoreInput = document.getElementById('chat-min-score');
  if (topKInput) {
    topKInput.disabled = !enabled;
    topKInput.style.opacity = enabled ? '1' : '0.5';
  }
  if (minScoreInput) {
    minScoreInput.disabled = !enabled;
    minScoreInput.style.opacity = enabled ? '1' : '0.5';
  }
}

/**
 * Извлекает текущие значения параметров конфигурации запроса.
 * @returns {Object} Объект параметров генерации.
 */
export function getGenerationParams() {
  const topKInput = document.getElementById('chat-top-k');
  const minScoreInput = document.getElementById('chat-min-score');
  const modeSelect = document.getElementById('chat-output-mode');
  const ragToggle = document.getElementById('chat-rag-toggle');

  const topK = topKInput ? parseInt(topKInput.value, 10) || 3 : 3;
  const minScore = minScoreInput ? parseFloat(minScoreInput.value) || 0.45 : 0.45;
  const outputMode = modeSelect ? modeSelect.value : 'text_only';
  const isRagEnabled = ragToggle ? ragToggle.checked : true;
  const shouldSpeak = outputMode === 'voice_only' || outputMode === 'text_and_voice';

  return {
    topK,
    minScore,
    outputMode,
    isRagEnabled,
    shouldSpeak
  };
}

/**
 * Обрабатывает внешний промпт (из расширения Chrome или параметров URL).
 * @param {Object} payload - Полезная нагрузка промпта.
 * @param {Function} [onSend=null] - Колбэк на отправку.
 */
export function handleExternalChatPrompt(payload, onSend = null) {
  if (!payload || !payload.prompt) return;

  const chatTabBtn = document.querySelector('[data-bs-target="#tab-chat"]');
  if (chatTabBtn && window.bootstrap?.Tab) {
    bootstrap.Tab.getOrCreateInstance(chatTabBtn).show();
  }

  const msgInput = document.getElementById('message-input');
  if (msgInput) {
    msgInput.value = payload.prompt;
    if (payload.autoSend !== false && typeof onSend === 'function') {
      setTimeout(() => {
        onSend();
      }, 150);
    }
  }
}

/**
 * Инициализирует элементы панели управления и перехваты внешних запросов.
 * @param {Function} onSendMessage - Обработчик отправки сообщения.
 */
export function initInputControls(onSendMessage) {
  const sendBtn = document.getElementById('send-button');
  const msgInput = document.getElementById('message-input');
  const ragToggle = document.getElementById('chat-rag-toggle');
  const modeSelect = document.getElementById('chat-output-mode');

  if (ragToggle) {
    const savedRagPref = localStorage.getItem('chat_rag_enabled');
    if (savedRagPref !== null) {
      ragToggle.checked = savedRagPref === 'true';
      updateRagInputsState(ragToggle.checked);
    }
    fetch('/api/v1/auth/settings', { cache: 'no-cache' })
      .then((res) => (res.ok ? res.json() : null))
      .then((settings) => {
        if (settings && typeof settings.rag_enabled !== 'undefined') {
          const isEnabled = settings.rag_enabled !== 0;
          ragToggle.checked = isEnabled;
          localStorage.setItem('chat_rag_enabled', isEnabled);
          updateRagInputsState(isEnabled);
        }
      })
      .catch(() => {});

    ragToggle.addEventListener('change', async (e) => {
      const isEnabled = e.target.checked;
      localStorage.setItem('chat_rag_enabled', isEnabled);
      updateRagInputsState(isEnabled);
      try {
        await fetch('/api/v1/auth/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rag_enabled: isEnabled ? 1 : 0 })
        });
      } catch (err) {
        console.error('Ошибка сохранения настроек RAG:', err);
      }
    });
  }

  if (modeSelect) {
    const savedMode = localStorage.getItem('chat_output_mode');
    if (savedMode) {
      modeSelect.value = savedMode;
    } else {
      modeSelect.value = 'text_only';
    }
    modeSelect.addEventListener('change', (e) => {
      localStorage.setItem('chat_output_mode', e.target.value);
      if (e.target.value === 'text_only' && window.chatService?.stop) {
        window.chatService.stop();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', onSendMessage);
  }
  if (msgInput) {
    msgInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        onSendMessage();
      }
    });
  }

  // Проверка отложенных полезных нагрузок из расширения или URL
  try {
    const pending = sessionStorage.getItem('pending_ai_tc_chat');
    if (pending) {
      const payload = JSON.parse(pending);
      sessionStorage.removeItem('pending_ai_tc_chat');
      setTimeout(() => handleExternalChatPrompt(payload, onSendMessage), 300);
    } else {
      const urlParams = new URLSearchParams(window.location.search);
      const promptParam = urlParams.get('prompt') || urlParams.get('message');
      if (promptParam) {
        setTimeout(() => {
          handleExternalChatPrompt(
            {
              prompt: promptParam,
              autoSend: urlParams.get('autosend') !== 'false'
            },
            onSendMessage
          );
        }, 300);
      }
    }
  } catch (e) {
    console.error('Ошибка проверки очереди внешних промптов:', e);
  }
}
