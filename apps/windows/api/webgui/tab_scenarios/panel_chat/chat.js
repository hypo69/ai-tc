/**
 * =============================================================================
 * Название: AI Ассистент сценариев и интерактивный чат хоста (/tc)
 * =============================================================================
 * Описание:
 *   Управление диалогом, генерация 3 динамических вопросов хоста от модели,
 *   потоковая передача рассуждений UniversalLangChainAgent через SSE,
 *   исполнение инструментов WikiLLM Toolbox и безопасных команд PowerShell.
 *
 * Файл: apps/windows/api/webgui/tab_scenarios/panel_chat/chat.js
 * Пакет: windows/api/webgui/tab_scenarios
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml, formatMarkdown } from '../common/ui_utils.js';
import {
  renderLiveStreamContent,
  parseModelResponse,
  attachInteractiveCommandHandlers
} from './pipeline.js';

let isChatSubmitting = false;
let currentQuestions = [
  'Где посмотреть, почему компьютер вчера внезапно сам выключился?',
  'Какие службы с автозапуском сейчас остановлены или завершились со сбоем?',
  'Оцени свободное место на системном диске и нагрузку на память'
];

/**
 * Отрисовывает динамические кнопки быстрых запросов и кнопку их обновления.
 */
export function renderQuickButtons() {
  const container = document.getElementById('chat-quick-prompts');
  if (!container) return;

  const buttonsHtml = currentQuestions.map(qText => `
    <button class="btn btn-outline-secondary btn-sm py-0 px-2 quick-prompt-btn" style="font-size: 0.75rem;" data-prompt="${escapeHtml(qText)}" title="Нажмите для отправки запроса">
      💡 ${escapeHtml(qText)}
    </button>
  `).join('');

  container.innerHTML = `
    <div class="d-flex align-items-center gap-1.5 flex-wrap">
      ${buttonsHtml}
      <button class="btn btn-sm btn-outline-info py-0 px-2 rounded-pill d-inline-flex align-items-center gap-1" id="btn-refresh-suggested-questions" style="font-size: 0.73rem;" title="Сгенерировать 3 новых вопроса от модели">
        <i class="bi bi-arrow-clockwise" id="icon-refresh-questions"></i>
        <span>Другие вопросы</span>
      </button>
    </div>
  `;

  // Навешиваем клик на вопросы
  container.querySelectorAll('.quick-prompt-btn').forEach(btn => {
    btn.onclick = () => {
      if (isChatSubmitting) return;
      const text = btn.dataset.prompt || btn.innerText.replace(/^[^\wа-яА-ЯёЁ«"]+/, '').trim();
      const chatInput = document.getElementById('scenario-chat-input');
      if (chatInput) {
        chatInput.value = text;
        submitChat();
      }
    };
  });

  // Навешиваем клик на кнопку обновления вопросов
  const btnRefresh = document.getElementById('btn-refresh-suggested-questions');
  if (btnRefresh) {
    btnRefresh.onclick = () => loadSuggestedQuestions(true);
  }
}

/**
 * Отрисовывает динамические вопросы в теле приветственного блока.
 */
export function renderGreetingPrompts() {
  const greetingContainer = document.getElementById('chat-greeting-prompts');
  if (!greetingContainer) return;

  greetingContainer.innerHTML = currentQuestions.map(q => `
    <div>• <a href="#" class="chat-prompt-link text-decoration-none border-bottom border-primary border-opacity-50" data-prompt="${escapeHtml(q)}">«${escapeHtml(q)}»</a></div>
  `).join('');
}

/**
 * Генерирует HTML-разметку приветственного сообщения.
 * @returns {string} HTML-разметка.
 */
export function getGreetingHtml() {
  const promptsHtml = currentQuestions.map(q => `
    <div>• <a href="#" class="chat-prompt-link text-decoration-none border-bottom border-primary border-opacity-50" data-prompt="${escapeHtml(q)}">«${escapeHtml(q)}»</a></div>
  `).join('');

  return `
    <div class="chat-message-row bot-row mb-3">
      <div class="chat-msg-avatar">🤖</div>
      <div class="chat-msg-bot">
        <div class="mb-2">
          Привет! Я интеллектуальный ассистент Test Computer на базе <strong>LangChain ReAct Agent</strong>. Вы можете задать мне любой вопрос о состоянии или конфигурации хоста:
        </div>
        <div id="chat-greeting-prompts" class="d-flex flex-column gap-1 my-2">
          ${promptsHtml}
        </div>
        <div class="text-muted small mt-2">
          ⚙️ Если для решения задачи нет готового инструмента в <strong>WikiLLM Toolbox</strong>, агент на лету синтезирует новый PowerShell-зонд через <code>create_custom_tool</code>, выполнит его на хосте и сформирует развернутый отчет.
        </div>
      </div>
    </div>
  `;
}

/**
 * Загружает 3 актуальных диагностических вопроса от модели через API.
 * @param {boolean} forceRefresh - Принудительно запросить новые вопросы.
 */
export async function loadSuggestedQuestions(forceRefresh = false) {
  const icon = document.getElementById('icon-refresh-questions');
  if (icon) icon.classList.add('spinner-border', 'spinner-border-sm');

  try {
    const res = await fetch('/api/v1/diagnostics/suggest-questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        table_type: 'scenarios',
        panel_id: 'panel-scenarios',
        title: 'Сценарии тестирования и автоматизации',
        subtitle: 'Интерактивная диагностика и решение задач хоста',
        force_refresh: forceRefresh
      })
    });

    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.questions) && data.questions.length > 0) {
        currentQuestions = data.questions.slice(0, 3);
      }
    }
  } catch (err) {
    console.debug('[ScenariosTab] Ошибка загрузки 3 вопросов:', err);
  } finally {
    renderQuickButtons();
    renderGreetingPrompts();
    if (icon) icon.classList.remove('spinner-border', 'spinner-border-sm');
  }
}

/**
 * Инициализирует мини-чат и привязывает слушатели событий.
 */
export function setupMiniChat() {
  const chatForm = document.getElementById('scenario-chat-form');
  const chatInput = document.getElementById('scenario-chat-input');
  const chatHistory = document.getElementById('scenario-chat-history');
  const statusInd = document.getElementById('chat-status-indicator');

  if (!chatForm || !chatInput || !chatHistory) return;

  loadSuggestedQuestions(false);

  const btnNewChat = document.getElementById('btn-scenario-new-chat');
  if (btnNewChat) {
    btnNewChat.onclick = () => {
      chatHistory.innerHTML = getGreetingHtml();
      loadSuggestedQuestions(true);
      if (statusInd) statusInd.innerText = 'Новая сессия начата';
      chatInput.focus();
    };
  }

  const btnClearDialog = document.getElementById('btn-clear-dialog');
  if (btnClearDialog) {
    btnClearDialog.onclick = () => {
      chatHistory.innerHTML = getGreetingHtml();
      if (statusInd) statusInd.innerText = 'Диалог очищен';
    };
  }

  // Делегирование кликов по ссылкам на вопросы в истории
  chatHistory.onclick = (e) => {
    const link = e.target.closest('.chat-prompt-link');
    if (link) {
      e.preventDefault();
      e.stopPropagation();
      if (isChatSubmitting) return;
      const promptText = link.dataset.prompt || link.innerText.replace(/^[«"']|[»"']$/g, '').trim();
      if (promptText) {
        chatInput.value = promptText;
        submitChat();
      }
    }
  };

  chatForm.onsubmit = (e) => {
    e.preventDefault();
    submitChat();
  };
}

/**
 * Отправляет пользовательское сообщение через SSE-поток UniversalLangChainAgent.
 */
export async function submitChat() {
  const chatInput = document.getElementById('scenario-chat-input');
  const chatHistory = document.getElementById('scenario-chat-history');
  const sendBtn = document.getElementById('btn-scenario-chat-send');
  const statusInd = document.getElementById('chat-status-indicator');

  if (!chatInput || !chatHistory) return;
  const message = chatInput.value.trim();
  if (!message || isChatSubmitting) return;

  isChatSubmitting = true;
  chatInput.value = '';
  chatInput.disabled = true;
  if (sendBtn) sendBtn.disabled = true;
  if (statusInd) statusInd.innerText = '🧠 Подключение к UniversalLangChainAgent...';

  // Сообщение пользователя
  const userMsgHtml = `
    <div class="chat-message-row user-row mb-2">
      <div class="chat-msg-user">
        ${escapeHtml(message)}
      </div>
    </div>
  `;
  chatHistory.insertAdjacentHTML('beforeend', userMsgHtml);
  chatHistory.scrollTop = chatHistory.scrollHeight;

  // Обработка встроенной команды /skills
  const cleanCmd = message.trim().toLowerCase();
  if (cleanCmd === '/skills' || cleanCmd === '/skills list' || cleanCmd.startsWith('/skills search')) {
    try {
      const searchParam = cleanCmd.startsWith('/skills search') ? cleanCmd.replace('/skills search', '').trim() : '';
      const url = searchParam ? `/api/v1/admin/skills?q=${encodeURIComponent(searchParam)}` : '/api/v1/admin/skills';
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const skills = data.skills || [];

      let replyMd = `### 📚 Каталог зарегистрированных навыков (.skills)\n\n`;
      if (skills.length === 0) {
        replyMd += `*Навыки не найдены.*`;
      } else {
        replyMd += `Всего доступно навыков: **${skills.length}**\n\n`;
        skills.forEach((s, idx) => {
          const pathStr = s.root_relative || s.path || `.skills/${s.name}/SKILL.md`;
          const desc = s.description_ru || s.description || 'Без описания';
          replyMd += `${idx + 1}. 🧩 **${escapeHtml(s.name)}** — *${escapeHtml(desc)}* (\`${escapeHtml(pathStr)}\`)\n`;
        });
      }

      const botHtml = `
        <div class="chat-message-row bot-row mb-3">
          <div class="chat-msg-avatar">🤖</div>
          <div class="chat-msg-bot">
            <div>${formatMarkdown(replyMd)}</div>
          </div>
        </div>
      `;
      chatHistory.insertAdjacentHTML('beforeend', botHtml);
      if (statusInd) statusInd.innerText = 'Список навыков выведен';
    } catch (err) {
      const errHtml = `
        <div class="chat-message-row bot-row mb-3">
          <div class="chat-msg-avatar">⚠️</div>
          <div class="chat-msg-bot border-danger text-danger">Ошибка: ${escapeHtml(err.message)}</div>
        </div>
      `;
      chatHistory.insertAdjacentHTML('beforeend', errHtml);
    } finally {
      isChatSubmitting = false;
      chatInput.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      chatInput.focus();
      chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    return;
  }

  // Создаем контейнер для потокового ответа ассистента
  const msgId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
  const botRowHtml = `
    <div class="chat-message-row bot-row mb-3" id="${msgId}-container">
      <div class="chat-msg-avatar">🤖</div>
      <div class="chat-msg-bot shadow-sm" id="${msgId}-body">
        <span class="uai-matrix-cursor">▌</span> Инициализация расследования...
      </div>
    </div>
  `;
  chatHistory.insertAdjacentHTML('beforeend', botRowHtml);
  chatHistory.scrollTop = chatHistory.scrollHeight;

  const bodyElem = document.getElementById(`${msgId}-body`);

  try {
    const res = await fetch('/api/v1/diagnostics/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: message,
        stream: true,
        table_type: 'scenarios',
        panel_id: 'panel-scenarios',
        context: {
          title: 'Сценарии тестирования и автоматизации',
          tab_id: 'tab_scenarios'
        }
      })
    });

    if (!res.ok) throw new Error(`Ошибка HTTP ${res.status}: ${res.statusText}`);

    let fullAnswerText = '';

    if (res.headers.get('content-type')?.includes('text/event-stream')) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let streamBuf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        streamBuf += decoder.decode(value, { stream: true });
        const lines = streamBuf.split('\n\n');
        streamBuf = lines.pop() || '';

        for (const line of lines) {
          const cleanLine = line.trim();
          if (!cleanLine.startsWith('data:')) continue;
          const raw = cleanLine.substring(5).trim();
          if (raw === '[DONE]') break;

          try {
            const chunkObj = JSON.parse(raw);
            if (chunkObj.error) throw new Error(chunkObj.error);

            if (chunkObj.chunk) {
              fullAnswerText += chunkObj.chunk;
              renderLiveStreamContent(bodyElem, fullAnswerText);
              chatHistory.scrollTop = chatHistory.scrollHeight;
            }

            if (chunkObj.status === 'done') {
              if (chunkObj.dialogue && !fullAnswerText) {
                fullAnswerText = chunkObj.dialogue;
              }
            }
          } catch (pErr) {
            // Если пришел невалидный JSON, добавляем текст напрямую
            if (raw && !raw.startsWith('{')) {
              fullAnswerText += raw;
              renderLiveStreamContent(bodyElem, fullAnswerText);
            }
          }
        }
      }
    } else {
      const respData = await res.json();
      fullAnswerText = respData.dialogue || respData.answer || JSON.stringify(respData);
    }

    // Завершающая структуризация и отрисовка ответа
    if (bodyElem && fullAnswerText) {
      bodyElem.innerHTML = parseModelResponse(fullAnswerText);
      attachInteractiveCommandHandlers(bodyElem);
    }

    if (statusInd) statusInd.innerText = 'Ответ сформирован на основе фактов хоста';
  } catch (err) {
    console.error('[ScenariosTab] Ошибка чата:', err);
    if (bodyElem) {
      bodyElem.innerHTML = `
        <div class="text-danger p-2 bg-danger bg-opacity-10 border border-danger border-opacity-40 rounded">
          <div class="fw-semibold"><i class="bi bi-exclamation-triangle-fill me-1"></i>Ошибка расследования:</div>
          <div class="small mt-1">${escapeHtml(err.message || 'Сбой выполнения')}</div>
        </div>
      `;
    }
    if (statusInd) statusInd.innerText = `Сбой: ${err.message || 'Ошибка'}`;
  } finally {
    isChatSubmitting = false;
    chatInput.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
    chatInput.focus();
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }
}

// Алиас для обратной совместимости с внешними модулями
export const loadQuestionsFromConfig = loadSuggestedQuestions;

