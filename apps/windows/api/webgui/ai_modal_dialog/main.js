/**
 * =============================================================================
 * Process Name: Windows WebGUI - AI Modal Dialog Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер и интерфейс универсального всплывающего окна
 *   с ИИ-анализатором записей, WikiLLM-интеграцией, прямым редактором системной
 *   инструкции и привязкой к ID панели интерфейса.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/html/ai_modal_dialog/main.js?v=20261020_v1"></script>
 *
 *   JS Execution:
 *     window.AIModalDialog.show({
 *       title: 'Administrator',
 *       subtitle: 'SID: S-1-5-21-...',
 *       icon: '👤',
 *       panelId: 'panel-winadmin-users',
 *       tableType: 'user_account',
 *       metadata: [{ label: 'SID', value: 'S-1-5-21-...' }]
 *     });
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: apps.windows.api.webgui.ai_modal_dialog
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-01 13:12:00
 * =============================================================================
 */

// Universal AI Modal Dialog Module for AI-Windows-Admin
// Enables interactive row inspection, WikiLLM grounding, in-place system instruction editing, and AI contextual explanation.

(function () {
  const MODAL_ID = 'universal-ai-table-modal';
  const PROMPT_MODAL_ID = 'universal-ai-prompt-editor-modal';

  /**
   * Возвращает текущий режим работы ассистента: 'model_only' или 'model_wikillm'.
   * @returns {'model_only'|'model_wikillm'}
   */
  function getAssistantMode() {
    try {
      const saved = localStorage.getItem('uai_assistant_mode');
      if (saved === 'model_only' || saved === 'model_wikillm') return saved;
    } catch (_) {}
    return 'model_wikillm';
  }

  /**
   * Устанавливает и сохраняет режим работы ассистента.
   * @param {'model_only'|'model_wikillm'} mode
   */
  function setAssistantMode(mode) {
    try {
      localStorage.setItem('uai_assistant_mode', mode);
    } catch (_) {}
    updateModeButtonsUI(mode);
  }

  /**
   * Актуализирует активное визуальное состояние кнопок переключателя режима.
   * @param {'model_only'|'model_wikillm'} [mode]
   */
  function updateModeButtonsUI(mode) {
    const curMode = mode || getAssistantMode();
    const btnOnly = document.getElementById('btn-mode-model-only');
    const btnWiki = document.getElementById('btn-mode-model-wikillm');
    if (btnOnly && btnWiki) {
      if (curMode === 'model_only') {
        btnOnly.classList.add('active');
        btnWiki.classList.remove('active');
      } else {
        btnWiki.classList.add('active');
        btnOnly.classList.remove('active');
      }
    }
  }

  /**
   * Возвращает текущий активный код языка интерфейса (ru, en, etc.).
   * @returns {string} Код языка
   */
  function getCurrentLang() {
    try {
      const saved = localStorage.getItem('app_locale') || localStorage.getItem('app_language');
      if (saved) {
        const norm = saved.toLowerCase().split('-')[0].split('_')[0];
        if (norm) return norm;
      }
      const docLang = document.documentElement.lang;
      if (docLang) {
        return docLang.toLowerCase().split('-')[0].split('_')[0];
      }
    } catch (_) {}
    return 'ru';
  }

  /**
   * Нормализует строковый тип таблицы с учетом алиасов.
   * @param {string} tType Тип таблицы
   * @returns {string} Нормализованный ключ
   */
  function normalizeTableType(tType) {
    if (!tType) return 'generic';
    const low = String(tType).toLowerCase().trim();
    if (low === 'user' || low === 'users' || low === 'account' || low === 'accounts') return 'user_account';
    if (low === 'event' || low === 'events' || low === 'security') return 'security_event';
    if (low === 'tasks') return 'task';
    if (low === 'services') return 'service';
    if (low === 'processes') return 'process';
    if (low === 'disks') return 'disk';
    if (low === 'apps' || low === 'app') return 'software';
    if (low === 'autorun' || low === 'autoruns') return 'startup';
    if (low === 'power' || low === 'powersession' || low === 'power_session' || low === 'power_sessions' || low === 'power_lifecycle') return 'power_session';
    if (low === 'powerevent' || low === 'power_event' || low === 'power_events') return 'power_event';
    if (low === 'window' || low === 'windows' || low === 'desktop_window' || low === 'desktop_windows' || low === 'hwnd') return 'desktop_window';
    return low;
  }

  /**
   * Гарантирует наличие DOM-элемента модального окна AI-анализатора.
   * @returns {HTMLElement} Элемент модального окна
   */
  function ensureModalElement() {
    let modalEl = document.getElementById(MODAL_ID);
    if (!modalEl) {
      modalEl = document.createElement('div');
      modalEl.id = MODAL_ID;
      modalEl.className = 'modal fade';
      modalEl.tabIndex = -1;
      modalEl.setAttribute('aria-hidden', 'true');
      modalEl.innerHTML = `
        <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
          <div class="modal-content shadow-lg">
            <div class="modal-header py-2 px-3">
              <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="fs-5 text-info" id="uai-modal-icon">🔍</span>
                <h5 class="modal-title fw-bold text-info mb-0" id="uai-modal-title">Детали записи</h5>
                <div id="uai-modal-badges" class="d-flex align-items-center gap-1"></div>
              </div>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
            </div>
            <div class="modal-body py-3 px-3">
              <!-- Metadata Grid -->
              <div class="row g-2 mb-3 small" id="uai-modal-metadata-grid"></div>

              <!-- AI Contextual Diagnostic Card (Чистый ответ ИИ и интерактивный диалог) -->
              <div class="card border-info p-3 uai-ai-section mb-3" id="uai-modal-ai-section">
                <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                  <div class="d-flex align-items-center gap-2 flex-wrap">
                    <h6 class="fw-bold text-info mb-0"><i class="bi bi-robot me-1"></i> AI Contextual Explanation</h6>
                    <span class="badge border border-info text-info small px-2 py-0.5" id="uai-modal-web-status" title="Сведения обогащаются поиском в интернете">
                      <i class="bi bi-globe me-1"></i>Web Grounding
                    </span>
                    <!-- Переключатель режима: только модель / модель + wikillm -->
                    <div class="uai-mode-toggle-group ms-1" role="group" aria-label="Режим работы AI-ассистента" id="uai-assistant-mode-group">
                      <button type="button" class="uai-mode-btn" data-mode="model_only" id="btn-mode-model-only" title="Прямой запрос к модели без использования и проверки базы знаний WikiLLM">
                        <i class="bi bi-cpu me-1"></i>Только модель
                      </button>
                      <button type="button" class="uai-mode-btn active" data-mode="model_wikillm" id="btn-mode-model-wikillm" title="Комплексный режим: сначала проверяется локальная база знаний WikiLLM, контекст обогащается статьями и доступно сохранение знаний">
                        <i class="bi bi-database-check me-1"></i>Модель + WikiLLM
                      </button>
                    </div>
                  </div>
                  <div class="d-flex align-items-center gap-1.5 flex-wrap">
                    <label class="d-flex align-items-center gap-1 small text-secondary me-1" style="font-size: 0.78rem; cursor: pointer;" title="Авто-обогащение через Gemini при Cache Miss (01_FRONTEND.md)">
                      <input type="checkbox" id="toggle-auto-enrich-on-miss" class="ui-toggle-checkbox form-check-input m-0" checked>
                      <span>Авто-обогащение</span>
                    </label>
                    <button class="btn btn-sm btn-outline-secondary py-0 px-2 rounded-pill" id="btn-uai-modal-edit-prompt" title="Настроить расширенный шаблон промпта">
                      <i class="bi bi-gear-fill me-1"></i>Промпт
                    </button>
                    <button class="btn btn-sm btn-outline-info py-0 px-2 rounded-pill" id="btn-uai-modal-refresh" title="Обновить AI-анализ" style="display: none;">
                      <i class="bi bi-arrow-clockwise me-1"></i>Обновить
                    </button>
                  </div>
                </div>

                <!-- Основное окно ответов модели и базы знаний WikiLLM -->
                <div class="uai-explanation-content" id="uai-modal-ai-explanation"></div>

                <!-- Нить диалога Q&A (дополнительные вопросы и ответы модели) -->
                <div id="uai-qa-conversation-thread" class="mt-3"></div>

                <!-- Блок быстрых вопросов: расположен ПОД окнами ответов модели -->
                <div class="mt-3 pt-3 border-top border-secondary border-opacity-25" id="uai-modal-chat-section">
                  <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
                    <div class="d-flex align-items-center gap-1.5">
                      <span class="fs-6 text-primary">💬</span>
                      <h6 class="fw-bold text-light mb-0 small">Рекомендуемые вопросы по сущности:</h6>
                    </div>
                    <span class="badge border border-info text-info small" style="font-size: 0.7rem;">Gemini Streaming Chat</span>
                  </div>

                  <!-- Быстрые вопросы списком один под другим (в стиле chat-greeting-prompts) -->
                  <div class="d-flex flex-column gap-1.5 my-2 w-100" id="uai-chat-quick-buttons">
                    <div class="text-secondary small py-1 px-1 d-inline-flex align-items-center gap-2" id="uai-quick-buttons-loading" style="font-size: 0.95rem;">
                      <div class="spinner-border spinner-border-sm text-primary" style="width: 0.95rem; height: 0.95rem;" role="status"></div>
                      <span>Генерация актуальных вопросов...</span>
                    </div>
                  </div>

                  <div class="input-group input-group-sm" id="uai-chat-input-group" style="display: none !important;">
                    <input type="text" class="form-control bg-dark text-light border-secondary" id="uai-chat-input" placeholder="Задать уточняющий вопрос по сущности...">
                    <button class="btn btn-primary d-inline-flex align-items-center gap-1" id="uai-chat-send-btn" type="button">
                      <i class="bi bi-send-fill"></i> Отправить
                    </button>
                  </div>

                  <!-- Скрытый контейнер для совместимости со старыми селекторами -->
                  <div id="uai-chat-messages-container" style="display: none;"></div>
                </div>
              </div>

              <!-- Collapsible Technical Sections (Скрыты по умолчанию) -->
              <div class="mt-3 pt-2 border-top border-secondary border-opacity-25" id="uai-modal-spoilers-container">
                <div class="d-flex align-items-center gap-2 flex-wrap mb-2">
                  <!-- Spoiler Toggle 1: Raw Content -->
                  <button class="btn btn-sm btn-outline-secondary rounded-pill px-3 py-1 font-monospace" 
                          type="button" data-bs-toggle="collapse" data-bs-target="#collapseRawData" aria-expanded="false" id="btn-toggle-raw-data" style="display: none;">
                    <i class="bi bi-code-slash me-1"></i> Показать сырой код / данные
                  </button>

                  <!-- Spoiler Toggle 2: Developer Advice & Automation -->
                  <button class="btn btn-sm btn-outline-info rounded-pill px-3 py-1 font-monospace" 
                          type="button" data-bs-toggle="collapse" data-bs-target="#collapseDevAdvice" aria-expanded="false" id="btn-toggle-dev-advice" style="display: none;">
                    <i class="bi bi-code-slash me-1"></i> Советы разработчику
                  </button>

                  <!-- Spoiler Toggle 3: System Instruction & Config -->
                  <button class="btn btn-sm btn-outline-secondary rounded-pill px-3 py-1 font-monospace" 
                          type="button" data-bs-toggle="collapse" data-bs-target="#collapseSysInstruction" aria-expanded="false" id="btn-toggle-sys-instruction">
                    <i class="bi bi-shield-lock me-1"></i> Показать системную инструкцию
                  </button>
                </div>

                <!-- Developer Advice & Automation Scripts Section -->
                <div class="collapse mb-2" id="collapseDevAdvice">
                  <div class="card p-3 uai-dev-card" id="uai-modal-dev-card">
                    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                      <div class="d-flex align-items-center gap-2">
                        <span class="fs-6 text-info">🛠️</span>
                        <h6 class="fw-bold text-info mb-0">Советы разработчику и документация по компоненту</h6>
                      </div>
                      <div class="d-flex align-items-center gap-1.5 flex-wrap">
                        <button type="button" class="btn btn-xs btn-outline-warning py-0 px-2 rounded" id="btn-uai-dev-save-instrument" title="Сохранить эти скрипты и утилиты в базу инструментов агента ai_instruments.db">
                          <i class="bi bi-tools me-1"></i>Сохранить в ai_instruments.db
                        </button>
                      </div>
                    </div>
                    <div class="uai-dev-content text-light small" id="uai-modal-dev-content"></div>
                  </div>
                </div>

                <!-- Raw / Code Content Section -->
                <div class="collapse mb-2" id="collapseRawData">
                  <div class="card p-3 uai-raw-container bg-black bg-opacity-50 border border-secondary" id="uai-modal-raw-container">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                      <h6 class="small text-uppercase text-muted fw-bold mb-0" id="uai-modal-raw-title">Контекст / Данные</h6>
                    </div>
                    <pre class="m-0 small font-monospace text-info uai-raw-content" id="uai-modal-raw-content" style="white-space: pre-wrap; word-break: break-all; max-height: 220px; overflow-y: auto;"></pre>
                  </div>
                </div>

                <!-- System Instruction & Model Configuration Section -->
                <div class="collapse" id="collapseSysInstruction">
                  <div class="card p-3 border-secondary-subtle uai-system-card" id="uai-modal-system-card">
                    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                      <div class="d-flex align-items-center gap-2">
                        <span class="fs-6 text-warning">🤖</span>
                        <h6 class="fw-bold text-warning mb-0">Системная инструкция и конфигурация ИИ</h6>
                      </div>
                      <div class="d-flex align-items-center gap-1.5 flex-wrap">
                        <span class="badge bg-secondary-subtle text-secondary border small" id="uai-modal-panel-badge" title="ID вызывающей панели">Панель: -</span>
                        <span class="badge bg-secondary-subtle text-secondary border small" id="uai-modal-type-badge">Тип: -</span>
                        <span class="badge border border-info text-info small" id="uai-modal-custom-badge" style="display: none;">Кастомная</span>
                      </div>
                    </div>

                    <div class="row g-2 mb-2 align-items-center">
                      <div class="col-sm-6">
                        <div class="input-group input-group-sm">
                          <span class="input-group-text text-secondary small py-0">Провайдер</span>
                          <select class="form-select form-select-sm" id="uai-modal-provider-select">
                            <option value="gemini">Google Gemini (Direct SDK)</option>
                            <option value="gemini_cli">Google Gemini CLI</option>
                            <option value="agy">Antigravity (AGY SDK)</option>
                            <option value="openai">OpenAI / Compatible</option>
                            <option value="ollama">Ollama Local</option>
                            <option value="foundry">Foundry Local</option>
                            <option value="windows_ai">Windows Copilot+ AI</option>
                          </select>
                        </div>
                      </div>
                      <div class="col-sm-6">
                        <div class="input-group input-group-sm">
                          <span class="input-group-text text-secondary small py-0">Модель</span>
                          <input type="text" class="form-control form-control-sm" id="uai-modal-model-input" placeholder="По умолчанию (из config.json)">
                        </div>
                      </div>
                    </div>

                    <div class="mb-1">
                      <div class="d-flex justify-content-between align-items-center mb-1">
                        <label class="form-label small text-secondary fw-bold mb-0">Системная инструкция (System Instruction):</label>
                        <div class="d-flex gap-1">
                          <button type="button" class="btn btn-xs btn-outline-info py-0 px-2" id="btn-uai-modal-save-system" title="Сохранить измененную инструкцию для этой сущности">
                            <i class="bi bi-floppy me-1"></i>Сохранить
                          </button>
                          <button type="button" class="btn btn-xs btn-outline-secondary py-0 px-2" id="btn-uai-modal-reset-system" title="Сбросить к системной инструкции по умолчанию">
                            <i class="bi bi-arrow-counterclockwise me-1"></i>Сброс
                          </button>
                        </div>
                      </div>
                      <textarea class="form-control form-control-sm font-monospace" id="uai-modal-system-instruction" rows="3" placeholder="Роль эксперта, правила анализа и формат ответа для модели..."></textarea>
                      <div class="d-flex justify-content-between align-items-center mt-1">
                        <span class="text-secondary small" style="font-size: 0.72rem;" id="uai-modal-system-status">Инструкция передается при вызове модели и анализе</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="modal-footer py-2 px-3 d-flex justify-content-between">
              <div id="uai-modal-custom-actions" class="d-flex gap-1.5 flex-wrap"></div>
              <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Закрыть</button>
            </div>
          </div>
        </div>
      `;
      modalEl.addEventListener('hide.bs.modal', () => {
        if (modalEl.contains(document.activeElement) && typeof document.activeElement.blur === 'function') {
          document.activeElement.blur();
        }
      });
      document.body.appendChild(modalEl);
    }
    return modalEl;
  }

  /**
   * Надежный унифицированный fetch для всех запросов модального окна.
   * @param {string} url URL запроса
   * @param {Object} opts Опции fetch
   * @param {number} timeoutMs Таймаут в миллисекундах (0 = без таймаута, терпеливое ожидание)
   * @returns {Promise<any>}
   */
  async function safeApiFetch(url, opts = {}, timeoutMs = 0) {
    const controller = new AbortController();
    let timeoutId = null;
    if (timeoutMs && timeoutMs > 0) {
      timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    }

    try {
      const fetchOptions = Object.assign({}, opts, { signal: controller.signal });
      const res = await window.fetch(url, fetchOptions);
      if (timeoutId) clearTimeout(timeoutId);

      if (!res.ok) {
        let errMsg = `${res.status} ${res.statusText}`;
        let rawErrorData = null;
        try {
          const errData = await res.json();
          rawErrorData = errData;
          if (errData && errData.detail) {
            errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          } else if (errData && errData.message) {
            errMsg = errData.message;
          }
        } catch (_) {}
        const error = new Error(errMsg);
        error.status = res.status;
        error.errorData = rawErrorData;
        throw error;
      }

      return await res.json();
    } catch (err) {
      if (timeoutId) clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error(`Превышено время ожидания ответа (${timeoutMs / 1000}с)`);
      }
      throw err;
    }
  }

  /**
   * Расшифровывает суть ошибки модели ИИ и извлекает сырой JSON/сообщение.
   * @param {any} err Объект или текст ошибки
   * @returns {{ friendlyReason: string, message: string, jsonString: string, code: any, status: string }}
   */
  function decipherModelError(err) {
    let errorObj = null;
    let rawText = '';

    if (err && err.errorData) {
      if (err.errorData.detail && typeof err.errorData.detail === 'object') {
        errorObj = err.errorData.detail;
      } else if (err.errorData.error) {
        errorObj = err.errorData;
      } else {
        errorObj = err.errorData;
      }
    }

    if (!errorObj && err && typeof err.message === 'string') {
      rawText = err.message;
      try {
        const match = rawText.match(/(\{[\s\S]*\})/);
        if (match) {
          errorObj = JSON.parse(match[1]);
        }
      } catch (_) {}
    }

    if (!rawText && err) {
      rawText = typeof err === 'string' ? err : (err.message || String(err));
    }

    const errCore = (errorObj && errorObj.error && typeof errorObj.error === 'object') ? errorObj.error : errorObj;

    const code = errCore?.code || errorObj?.code || err?.status || null;
    const status = errCore?.status || errorObj?.status || '';
    const msg = errCore?.message || errorObj?.message || rawText || 'Неизвестная ошибка модели';

    let friendlyReason = '';
    const searchStr = `${code || ''} ${status} ${msg}`.toLowerCase();

    if (searchStr.includes('429') || searchStr.includes('resource_exhausted') || searchStr.includes('quota') || searchStr.includes('исчерпан')) {
      friendlyReason = 'Превышена квота запросов или суточный лимит скорости API (Rate Limit / Quota Exhausted / 429). Повторите попытку позже или смените API-ключ / модель.';
    } else if (searchStr.includes('401') || searchStr.includes('403') || searchStr.includes('unauthenticated') || searchStr.includes('permission_denied') || searchStr.includes('api_key_invalid') || searchStr.includes('api key not valid')) {
      friendlyReason = 'Ошибка аутентификации API-ключа (недействительный ключ или недостаточные права). Проверьте настройки API-ключей в .env.';
    } else if (searchStr.includes('404') || searchStr.includes('not_found') || searchStr.includes('model_not_found')) {
      friendlyReason = 'Запрошенная модель ИИ не найдена или не поддерживается выбранным провайдером.';
    } else if (searchStr.includes('503') || searchStr.includes('unavailable') || searchStr.includes('overloaded') || searchStr.includes('deadline_exceeded')) {
      friendlyReason = 'Сервер модели ИИ перегружен или временно недоступен (Service Unavailable). Повторите попытку через некоторое время.';
    } else if (searchStr.includes('empty_response') || searchStr.includes('пустой ответ')) {
      friendlyReason = 'Модель вернула пустой ответ. Возможно, запрос заблокирован фильтрами безопасности провайдера или модель не смогла сгенерировать текст.';
    } else if (searchStr.includes('invalid_argument') || searchStr.includes('400')) {
      friendlyReason = 'Некорректный запрос к модели (недопустимые параметры или превышен размер контекстного окна).';
    } else if (searchStr.includes('invalid_json')) {
      friendlyReason = 'Модель вернула ответ не в формате JSON. Не удалось разобрать структуру диагностической карточки.';
    } else if (searchStr.includes('missing_summary')) {
      friendlyReason = 'В ответе модели отсутствует обязательное поле краткого назначения (summary).';
    }

    const jsonString = errorObj ? JSON.stringify(errorObj, null, 2) : (rawText ? JSON.stringify({ error: { message: rawText } }, null, 2) : '');

    return {
      friendlyReason,
      message: msg,
      jsonString,
      code,
      status
    };
  }

  /**
   * Проверяет, содержит ли текст ответа маркеры ошибки модели или провайдера.
   * @param {string} text Проверяемый текст
   * @returns {boolean} True, если текст представляет собой ошибку
   */
  function isModelErrorText(text) {
    if (!text || typeof text !== 'string') return false;
    const lower = text.trim().toLowerCase();
    if (lower.length < 10) return false;
    const markers = [
      'streaming error:',
      'model error:',
      'все api ключи исчерпаны',
      'service unavailable',
      '503 service unavailable',
      'this model is currently experiencing high demand',
      'resourceexhausted',
      'resource_exhausted',
      '429 too many requests',
      'quota exceeded',
      'rate limit',
      'api_key_invalid',
      'harness process exited',
      'ошибка провайдера',
      'сбой ответа модели'
    ];
    if (markers.some(m => lower.includes(m))) return true;
    if (lower.startsWith('{') && lower.includes('"error"') && (lower.includes('"code"') || lower.includes('"message"'))) {
      return true;
    }
    return false;
  }

  /**
   * Экранирование HTML спецсимволов.
   * @param {string} str Входная строка
   * @returns {string} Экранированная строка
   */
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Разэкранирование HTML спецсимволов.
   * @param {string} str Входная строка
   * @returns {string} Исходная строка
   */
  function unescapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'");
  }

  /**
   * Рендерит карточку готового инструмента / SafeOps действия с возможностью редактирования и запуска.
   * @param {Object} toolObj Объект с описанием инструмента
   * @returns {string} HTML карточки
   */
  function renderReadyToolWidget(toolObj) {
    if (!toolObj) return '';
    const title = toolObj.title || toolObj.tool_title || toolObj.tool_name || toolObj.name || 'Готовый инструмент решения';
    const description = toolObj.description || toolObj.instructions || toolObj.description_ru || '';
    const cmd = (toolObj.execution_command || toolObj.probe_script || toolObj.command || toolObj.script || '').trim();
    if (!cmd) return '';

    const actionId = toolObj.action_id || toolObj.id || 'tool-' + Math.random().toString(36).substring(2, 8);
    const termId = 'uai-term-' + String(actionId).replace(/[^a-zA-Z0-9_-]/g, '') + '-' + Math.random().toString(36).substring(2, 6);
    const risk = (toolObj.risk || 'safe').toLowerCase();
    const riskBadge = risk === 'danger'
      ? '<span class="badge bg-danger small px-2 py-0.5"><i class="bi bi-exclamation-octagon-fill me-1"></i>Опасно</span>'
      : (risk === 'caution' || risk === 'warning'
        ? '<span class="badge bg-warning text-dark small px-2 py-0.5"><i class="bi bi-exclamation-triangle-fill me-1"></i>Внимание</span>'
        : '<span class="badge bg-primary bg-opacity-25 border border-primary text-info small px-2 py-0.5"><i class="bi bi-terminal-fill me-1"></i>PowerShell Tool</span>');

    const isCmdLike = (toolObj.shell === 'cmd') || /^(?:cmd\b|net\b|reg\b|taskkill\b|sc\b)/i.test(cmd);
    const shellDefault = isCmdLike ? 'cmd' : (toolObj.shell === 'pwsh' ? 'pwsh' : 'powershell');
    const shellTitle = shellDefault === 'cmd' ? 'CMD Console' : (shellDefault === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');

    const lineCount = cmd.split('\n').length;
    // Полноценная адаптивная высота поля ввода для удобного редактирования
    const rows = Math.min(Math.max(lineCount, 2), 10);
    const escapedCmd = escapeHtml(cmd);

    return `
      <div class="uai-ready-tool-card" id="${termId}-card" data-action-id="${escapeHtml(actionId)}" data-term-id="${termId}">
        <div class="uai-tool-card-header d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div class="d-flex align-items-center gap-2">
            <span class="uai-tool-header-icon text-warning">⚡</span>
            <div>
              <div class="fw-bold text-info uai-tool-title">${escapeHtml(title)}</div>
              ${description ? `<div class="small text-muted uai-tool-desc">${escapeHtml(description)}</div>` : ''}
            </div>
          </div>
          <div class="uai-tool-risk-wrapper">${riskBadge}</div>
        </div>
        <div class="uai-terminal-window" id="${termId}">
          <div class="uai-terminal-header" id="${termId}-header">
            <div class="d-flex align-items-center gap-2">
              <span class="uai-terminal-dot uai-dot-red"></span>
              <span class="uai-terminal-dot uai-dot-yellow"></span>
              <span class="uai-terminal-dot uai-dot-green"></span>
              <span class="uai-terminal-title font-monospace ms-1" id="${termId}-title"><i class="bi bi-terminal-fill me-1 text-info"></i>${shellTitle}</span>
            </div>
            <div class="d-flex align-items-center gap-1.5">
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-term-settings" id="${termId}-btn-settings" title="Параметры и настройки терминала">
                <i class="bi bi-gear me-1"></i>Настройки
              </button>
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-save-instrument" id="${termId}-btn-save-inst" title="Сохранить этот инструмент в ai_instruments.db">
                <i class="bi bi-tools me-1 text-warning"></i>В AI Instruments
              </button>
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-copy-cmd" id="${termId}-btn-copy" title="Скопировать команду в буфер обмена">
                <i class="bi bi-clipboard me-1"></i>Копировать
              </button>
              <button type="button" class="btn btn-sm uai-term-btn-run uai-btn-run-cmd" id="${termId}-btn-run" title="Выполнить команду в консоли">
                <i class="bi bi-play-fill me-1"></i>Run
              </button>
            </div>
          </div>
          <div class="uai-terminal-settings-panel" id="${termId}-settings-panel" style="display: none;">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 w-100">
              <div class="d-flex align-items-center flex-wrap gap-2">
                <div class="d-flex align-items-center gap-1">
                  <label class="small text-secondary mb-0" for="${termId}-opt-shell">Оболочка:</label>
                  <select class="form-select form-select-sm py-0 px-1 uai-opt-shell" id="${termId}-opt-shell" style="width: auto; font-size: 0.8rem;">
                    <option value="powershell" ${shellDefault === 'powershell' ? 'selected' : ''}>PowerShell</option>
                    <option value="pwsh" ${shellDefault === 'pwsh' ? 'selected' : ''}>PowerShell Core (pwsh)</option>
                    <option value="cmd" ${shellDefault === 'cmd' ? 'selected' : ''}>CMD</option>
                  </select>
                </div>
                <div class="d-flex align-items-center gap-1">
                  <label class="small text-secondary mb-0" for="${termId}-opt-timeout">Таймаут:</label>
                  <select class="form-select form-select-sm py-0 px-1 uai-opt-timeout" id="${termId}-opt-timeout" style="width: auto; font-size: 0.8rem;">
                    <option value="15">15с</option>
                    <option value="30">30с</option>
                    <option value="35" selected>35с</option>
                    <option value="60">60с</option>
                    <option value="120">120с</option>
                  </select>
                </div>
                <div class="form-check form-switch m-0 d-flex align-items-center gap-1">
                  <input class="form-check-input uai-opt-admin" type="checkbox" id="${termId}-opt-admin" style="cursor: pointer;">
                  <label class="form-check-label small text-secondary" for="${termId}-opt-admin" title="Запуск с повышенными привилегиями RunAs">
                    <i class="bi bi-shield-lock me-0.5"></i>Админ
                  </label>
                </div>
                <div class="form-check form-switch m-0 d-flex align-items-center gap-1">
                  <input class="form-check-input uai-opt-wrap" type="checkbox" id="${termId}-opt-wrap" checked style="cursor: pointer;">
                  <label class="form-check-label small text-secondary" for="${termId}-opt-wrap" title="Перенос длинных строк">Перенос</label>
                </div>
              </div>
              <div class="d-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm uai-term-btn uai-btn-clear-term" id="${termId}-btn-clear" title="Очистить команду и вывод">
                  <i class="bi bi-trash me-1"></i>Очистить
                </button>
              </div>
            </div>
          </div>
          <div class="uai-terminal-body" id="${termId}-body" style="background-color: #000000 !important; padding: 0 !important;">
            <textarea class="font-monospace uai-cmd-input border-0" id="${termId}-input" rows="${rows}" spellcheck="false" placeholder="Введите команду PowerShell..." style="background-color: #000000 !important; color: #ffffff !important; font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace !important; font-weight: 600 !important; font-size: 0.9rem !important; line-height: 1.45 !important; width: 100% !important; padding: 0.6rem 0.8rem !important; border: none !important; outline: none !important; resize: vertical !important; white-space: pre-wrap !important;">${escapedCmd}</textarea>
          </div>
        </div>
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div class="small text-muted uai-cmd-hint" id="${termId}-hint" style="font-size: 0.78rem;">
            <i class="bi bi-shield-check me-1 text-success"></i>Безопасный запуск на хосте (${shellTitle} timeout 35s)
          </div>
        </div>
        <div class="uai-cmd-output-container mt-1" id="${termId}-output-container" style="display: none;">
          <div class="d-flex align-items-center justify-content-between mb-1 flex-wrap gap-1">
            <span class="small fw-semibold text-secondary uai-cmd-status-text" id="${termId}-status-text"><i class="bi bi-terminal me-1"></i>Результат выполнения:</span>
            <span class="badge uai-cmd-result-badge" id="${termId}-result-badge"></span>
          </div>
          <pre class="uai-cmd-output font-monospace" id="${termId}-output"></pre>
        </div>
      </div>
    `;
  }

  /**
   * Проверяет, является ли строка одиночной или блочной командой консоли / PowerShell.
   * @param {string} str Проверяемая строка
   * @returns {boolean}
   */
  function isCommandLineString(str) {
    if (!str || typeof str !== 'string') return false;
    const s = str.trim();
    if (!s) return false;
    return /^(?:powershell(?:\.exe)?\s+|pwsh(?:\.exe)?\s+|(?:Stop|Get|Start|Restart|Set|New|Remove|Test|Invoke|Select|Where)-[A-Za-z]+|cmd(?:\.exe)?(?:\s+\/c)?\s+|net(?:\.exe)?\s+(?:user|localgroup|start|stop|use|share|session)|taskkill\b|sc(?:\.exe)?\s+|reg(?:\.exe)?\s+|wmic\b|sfc\b|dism\b|gpupdate\b|ipconfig\b|route\b)/i.test(s) ||
           /\b(?:Stop-Process|Get-Process|Restart-Service|Start-Service|Set-Service|Get-Service|Get-CimInstance|Get-WmiObject)\b/i.test(s) ||
           /^\$(?:user|p|svc)\s*=/i.test(s);
  }

  /**
   * Рендерит интерактивный виджет запуска и редактирования команды PowerShell.
   * @param {string} cmdText Текст команды
   * @param {string} lang Язык (по умолчанию powershell)
   * @returns {string} HTML виджета
   */
  function renderInteractiveCommandWidget(cmdText, lang = 'powershell') {
    if (!cmdText) return '';
    const cleanCmd = String(cmdText).trim();
    const lineCount = cleanCmd.split('\n').length;
    const rows = Math.min(Math.max(lineCount, 2), 10);
    const escapedCmd = escapeHtml(cleanCmd);
    const termId = 'uai-term-cmd-' + Math.random().toString(36).substring(2, 9);
    const shellDefault = (lang && lang.toLowerCase() === 'cmd') ? 'cmd' : (lang && lang.toLowerCase() === 'pwsh' ? 'pwsh' : 'powershell');
    const shellTitle = shellDefault === 'cmd' ? 'CMD Console' : (shellDefault === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');

    return `
      <div class="uai-code-runner-box" id="${termId}-card" data-term-id="${termId}">
        <div class="uai-terminal-window" id="${termId}">
          <div class="uai-terminal-header" id="${termId}-header">
            <div class="d-flex align-items-center gap-2">
              <span class="uai-terminal-dot uai-dot-red"></span>
              <span class="uai-terminal-dot uai-dot-yellow"></span>
              <span class="uai-terminal-dot uai-dot-green"></span>
              <span class="uai-terminal-title font-monospace ms-1" id="${termId}-title"><i class="bi bi-terminal-fill me-1 text-info"></i>${escapeHtml(shellTitle)}</span>
            </div>
            <div class="d-flex align-items-center gap-1.5">
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-term-settings" id="${termId}-btn-settings" title="Параметры и настройки терминала">
                <i class="bi bi-gear me-1"></i>Настройки
              </button>
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-save-instrument" id="${termId}-btn-save-inst" title="Сохранить этот инструмент в ai_instruments.db">
                <i class="bi bi-tools me-1 text-warning"></i>В AI Instruments
              </button>
              <button type="button" class="btn btn-sm uai-term-btn uai-btn-copy-cmd" id="${termId}-btn-copy" title="Скопировать команду в буфер обмена">
                <i class="bi bi-clipboard me-1"></i>Копировать
              </button>
              <button type="button" class="btn btn-sm uai-term-btn-run uai-btn-run-cmd" id="${termId}-btn-run" title="Выполнить команду в консоли">
                <i class="bi bi-play-fill me-1"></i>Run
              </button>
            </div>
          </div>
          <div class="uai-terminal-settings-panel" id="${termId}-settings-panel" style="display: none;">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 w-100">
              <div class="d-flex align-items-center flex-wrap gap-2">
                <div class="d-flex align-items-center gap-1">
                  <label class="small text-secondary mb-0" for="${termId}-opt-shell">Оболочка:</label>
                  <select class="form-select form-select-sm py-0 px-1 uai-opt-shell" id="${termId}-opt-shell" style="width: auto; font-size: 0.8rem;">
                    <option value="powershell" ${shellDefault === 'powershell' ? 'selected' : ''}>PowerShell</option>
                    <option value="pwsh" ${shellDefault === 'pwsh' ? 'selected' : ''}>PowerShell Core (pwsh)</option>
                    <option value="cmd" ${shellDefault === 'cmd' ? 'selected' : ''}>CMD</option>
                  </select>
                </div>
                <div class="d-flex align-items-center gap-1">
                  <label class="small text-secondary mb-0" for="${termId}-opt-timeout">Таймаут:</label>
                  <select class="form-select form-select-sm py-0 px-1 uai-opt-timeout" id="${termId}-opt-timeout" style="width: auto; font-size: 0.8rem;">
                    <option value="15">15с</option>
                    <option value="30">30с</option>
                    <option value="35" selected>35с</option>
                    <option value="60">60с</option>
                    <option value="120">120с</option>
                  </select>
                </div>
                <div class="form-check form-switch m-0 d-flex align-items-center gap-1">
                  <input class="form-check-input uai-opt-admin" type="checkbox" id="${termId}-opt-admin" style="cursor: pointer;">
                  <label class="form-check-label small text-secondary" for="${termId}-opt-admin" title="Запуск с повышенными привилегиями RunAs">
                    <i class="bi bi-shield-lock me-0.5"></i>Админ
                  </label>
                </div>
                <div class="form-check form-switch m-0 d-flex align-items-center gap-1">
                  <input class="form-check-input uai-opt-wrap" type="checkbox" id="${termId}-opt-wrap" checked style="cursor: pointer;">
                  <label class="form-check-label small text-secondary" for="${termId}-opt-wrap" title="Перенос длинных строк">Перенос</label>
                </div>
              </div>
              <div class="d-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm uai-term-btn uai-btn-clear-term" id="${termId}-btn-clear" title="Очистить команду и вывод">
                  <i class="bi bi-trash me-1"></i>Очистить
                </button>
              </div>
            </div>
          </div>
          <div class="uai-terminal-body" id="${termId}-body" style="background-color: #000000 !important; padding: 0 !important;">
            <textarea class="font-monospace uai-cmd-input border-0" id="${termId}-input" rows="${rows}" spellcheck="false" placeholder="Введите команду..." style="background-color: #000000 !important; color: #ffffff !important; font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace !important; font-weight: 600 !important; font-size: 0.9rem !important; line-height: 1.45 !important; width: 100% !important; padding: 0.6rem 0.8rem !important; border: none !important; outline: none !important; resize: vertical !important; white-space: pre-wrap !important;">${escapedCmd}</textarea>
          </div>
        </div>
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div class="small text-muted uai-cmd-hint" id="${termId}-hint" style="font-size: 0.78rem;">
            <i class="bi bi-shield-check me-1 text-success"></i>Безопасный запуск на хосте (${shellTitle} timeout 35s)
          </div>
        </div>
        <div class="uai-cmd-output-container mt-1" id="${termId}-output-container" style="display: none;">
          <div class="d-flex align-items-center justify-content-between mb-1 flex-wrap gap-1">
            <span class="small fw-semibold text-secondary uai-cmd-status-text" id="${termId}-status-text"><i class="bi bi-terminal me-1"></i>Результат выполнения:</span>
            <span class="badge uai-cmd-result-badge" id="${termId}-result-badge"></span>
          </div>
          <pre class="uai-cmd-output font-monospace" id="${termId}-output"></pre>
        </div>
      </div>
    `;
  }

  /**
   * Навешивает интерактивные обработчики для кнопок Run и Копировать в блоках команд.
   * @param {HTMLElement} rootEl Корневой элемент контейнера
   */
  function attachInteractiveCommandHandlers(rootEl) {
    if (!rootEl) return;
    const boxes = rootEl.querySelectorAll('.uai-ready-tool-card, .uai-code-runner-box');
    boxes.forEach(box => {
      if (box.dataset.handlerAttached === 'true') return;
      box.dataset.handlerAttached = 'true';

      const textarea = box.querySelector('.uai-cmd-input');
      const copyBtn = box.querySelector('.uai-btn-copy-cmd');
      const runBtn = box.querySelector('.uai-btn-run-cmd');
      const saveInstrumentBtn = box.querySelector('.uai-btn-save-instrument');
      const settingsBtn = box.querySelector('.uai-btn-term-settings');
      const settingsPanel = box.querySelector('.uai-terminal-settings-panel');
      const shellSelect = box.querySelector('.uai-opt-shell');
      const timeoutSelect = box.querySelector('.uai-opt-timeout');
      const adminCheck = box.querySelector('.uai-opt-admin');
      const wrapCheck = box.querySelector('.uai-opt-wrap');
      const clearBtn = box.querySelector('.uai-btn-clear-term');
      const titleSpan = box.querySelector('.uai-terminal-title');
      const hintDiv = box.querySelector('.uai-cmd-hint');
      const outputContainer = box.querySelector('.uai-cmd-output-container');
      const outputPre = box.querySelector('.uai-cmd-output');
      const badge = box.querySelector('.uai-cmd-result-badge');

      if (settingsBtn && settingsPanel) {
        settingsBtn.onclick = () => {
          const isClosed = settingsPanel.style.display === 'none';
          settingsPanel.style.display = isClosed ? 'block' : 'none';
          settingsBtn.classList.toggle('active', isClosed);
          settingsBtn.classList.toggle('btn-secondary', isClosed);
          settingsBtn.classList.toggle('btn-outline-secondary', !isClosed);
        };
      }

      if (shellSelect && titleSpan) {
        shellSelect.onchange = () => {
          const val = shellSelect.value;
          const label = val === 'cmd' ? 'CMD Console' : (val === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');
          titleSpan.innerHTML = `<i class="bi bi-terminal-fill me-1"></i>${label}`;
          if (hintDiv) {
            const timeoutVal = timeoutSelect ? timeoutSelect.value : '35';
            const adminText = adminCheck && adminCheck.checked ? ' (Admin)' : '';
            hintDiv.innerHTML = `<i class="bi bi-shield-check me-1 text-success"></i>Запуск в ${label}${adminText} (timeout ${timeoutVal}s)`;
          }
        };
      }

      if (timeoutSelect && hintDiv) {
        timeoutSelect.onchange = () => {
          const val = shellSelect ? shellSelect.value : 'powershell';
          const label = val === 'cmd' ? 'CMD Console' : (val === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');
          const adminText = adminCheck && adminCheck.checked ? ' (Admin)' : '';
          hintDiv.innerHTML = `<i class="bi bi-shield-check me-1 text-success"></i>Запуск в ${label}${adminText} (timeout ${timeoutSelect.value}s)`;
        };
      }

      if (adminCheck && hintDiv) {
        adminCheck.onchange = () => {
          const val = shellSelect ? shellSelect.value : 'powershell';
          const label = val === 'cmd' ? 'CMD Console' : (val === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');
          const timeoutVal = timeoutSelect ? timeoutSelect.value : '35';
          const adminText = adminCheck.checked ? ' [С правами Администратора]' : '';
          hintDiv.innerHTML = `<i class="bi bi-shield-check me-1 text-success"></i>Запуск в ${label}${adminText} (timeout ${timeoutVal}s)`;
        };
      }

      if (wrapCheck && textarea) {
        wrapCheck.onchange = () => {
          if (wrapCheck.checked) {
            textarea.style.whiteSpace = 'pre-wrap';
            textarea.style.wordBreak = 'break-word';
          } else {
            textarea.style.whiteSpace = 'pre';
            textarea.style.wordBreak = 'normal';
          }
        };
      }

      if (clearBtn) {
        clearBtn.onclick = () => {
          if (outputContainer) outputContainer.style.display = 'none';
          if (outputPre) outputPre.textContent = '';
          if (badge) {
            badge.className = 'badge';
            badge.textContent = '';
          }
        };
      }

      if (copyBtn && textarea) {
        copyBtn.onclick = async () => {
          try {
            await navigator.clipboard.writeText(textarea.value);
            const origHtml = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="bi bi-check-lg me-1 text-success"></i>Скопировано';
            setTimeout(() => {
              copyBtn.innerHTML = origHtml;
            }, 2000);
          } catch (_) {
            textarea.select();
            document.execCommand('copy');
          }
        };
      }

      if (runBtn && textarea) {
        runBtn.onclick = async () => {
          const cmdToRun = textarea.value.trim();
          if (!cmdToRun) return;

          const chosenShell = shellSelect ? shellSelect.value : 'powershell';
          const chosenTimeout = timeoutSelect ? parseInt(timeoutSelect.value, 10) : 35;
          const chosenAsAdmin = adminCheck ? adminCheck.checked : false;

          runBtn.disabled = true;
          const origRunHtml = runBtn.innerHTML;
          runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Запуск...';

          if (outputContainer) outputContainer.style.display = 'block';
          if (badge) {
            badge.className = 'badge bg-secondary small';
            badge.textContent = chosenAsAdmin ? 'Запуск (Admin)...' : 'Выполнение...';
          }
          if (outputPre) {
            outputPre.textContent = `Выполнение команды [${chosenShell}${chosenAsAdmin ? ' | Elevated Admin' : ''}] на хосте...`;
          }

          try {
            const resp = await window.fetch('/api/v1/diagnostics/execute-powershell', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                command: cmdToRun,
                timeout_sec: chosenTimeout,
                shell: chosenShell,
                as_admin: chosenAsAdmin
              })
            });

            if (!resp.ok) {
              const errData = await resp.json().catch(() => ({}));
              throw new Error(errData.detail || `HTTP ${resp.status}`);
            }

            const result = await resp.json();
            if (badge) {
              const shellTag = chosenShell === 'cmd' ? 'CMD' : (chosenShell === 'pwsh' ? 'pwsh' : 'PS');
              const adminTag = chosenAsAdmin ? 'Admin ' : '';
              if (result.success) {
                badge.className = 'badge bg-success small';
                badge.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>[${adminTag}${shellTag}] Код 0 (${result.execution_time_ms} мс)`;
              } else {
                badge.className = 'badge bg-danger small';
                badge.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>[${adminTag}${shellTag}] Код ${result.returncode} (${result.execution_time_ms} мс)`;
              }
            }

            let outText = '';
            if (result.stdout && result.stdout.trim()) {
              outText += result.stdout;
            }
            if (result.stderr && result.stderr.trim()) {
              if (outText) outText += '\n[Ошибки stderr]:\n';
              outText += result.stderr;
            }
            if (!outText) {
              outText = result.success ? '(Команда выполнена успешно, вывод отсутствует)' : '(Команда завершилась с ошибкой, вывод пуст)';
            }

            if (outputPre) {
              outputPre.textContent = outText;
            }
          } catch (err) {
            if (badge) {
              badge.className = 'badge bg-danger small';
              badge.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Сбой запроса';
            }
            if (outputPre) {
              outputPre.textContent = `Ошибка отправки запроса: ${err.message}`;
            }
          } finally {
            runBtn.disabled = false;
            runBtn.innerHTML = origRunHtml;
          }
        };
      }
    });
  }

  /**
   * Проверяет, является ли строка строкой статуса рассуждений (Reasoning Step).
   * @param {string} line Строка текста
   * @returns {boolean}
   */
  function isInvestigationStatusLine(line) {
    if (!line) return false;
    const s = String(line).trim();
    if (!s) return false;
    if (/^>\s*[*_]?[💡⚙️🛠️✨📝🏁🔍🧠]/.test(s)) return true;
    if (/^[>*\s﻿ ​�]*[💡⚙️🛠️✨📝🏁🔍🧠]/.test(s)) return true;
    if (/^[>*\s﻿ ​�]*(?:WikiLLM Toolbox:|Анализ задачи|Шаг рассуждения|Выполнение инструмента из ящика|Синтез инструмента|Формирование итогового)/i.test(s)) return true;
    return false;
  }

  /**
   * Проверяет, является ли строка заголовком блока данных инструмента (Telemetry Data).
   * @param {string} line Строка текста
   * @returns {boolean}
   */
  function isInvestigationDataLine(line) {
    if (!line) return false;
    const s = String(line).trim();
    if (!s) return false;
    return /^[>*\s﻿ ​�]*(?:📊|Данные от|\*\*Данные|Результаты зонда|Telemetry preview)/i.test(s);
  }

  /**
   * Рендерит отдельный шаг рассуждения вслух в стиле Матрицы (Matrix Reasoning Theme).
   * @param {Object} st Объект шага ({ type: 'status'|'data', text?: string, title?: string, data?: string })
   * @returns {string} HTML строка шага
   */
  function renderMatrixStepHtml(st) {
    if (!st) return '';
    if (st.type === 'status') {
      const rawText = String(st.text || '').trim();
      let badgeType = 'uai-mb-think';
      let badgeIcon = 'bi-cpu';
      let badgeText = 'REASON';

      if (rawText.includes('🛠️') || rawText.includes('✨') || rawText.includes('Синтез') || rawText.includes('Synthesis')) {
        badgeType = 'uai-mb-synth';
        badgeIcon = 'bi-hammer';
        badgeText = 'SYNTHESIS';
      } else if (rawText.includes('⚙️') || rawText.includes('Toolbox') || rawText.includes('Запуск') || rawText.includes('Выполнение инструмента')) {
        badgeType = 'uai-mb-tool';
        badgeIcon = 'bi-gear-wide-connected';
        badgeText = 'TOOLBOX';
      } else if (rawText.includes('📝') || rawText.includes('Формирование')) {
        badgeType = 'uai-mb-synth';
        badgeIcon = 'bi-file-earmark-text';
        badgeText = 'SYNTHESIS';
      } else if (rawText.includes('🏁') || rawText.includes('завершено')) {
        badgeType = 'uai-mb-done';
        badgeIcon = 'bi-check2-circle';
        badgeText = 'COMPLETE';
      }

      let cleanText = escapeHtml(rawText)
        .replace(/^[>*\s﻿ ​�]*(?:[💡⚙️🛠️✨📝🏁🔍🧠]\s*)+/g, '')
        .replace(/^[>*\s﻿ ​�]*(?:[💡⚙️🛠️✨📝🏁🔍🧠]\s*)+/g, '')
        .replace(/^[*_\s]+/, '')
        .replace(/[*_\s]+$/, '')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>');

      if (!cleanText) cleanText = escapeHtml(rawText);

      return `
        <div class="uai-investigation-step uai-matrix-step">
          <span class="uai-matrix-prompt">&gt;</span>
          <span class="uai-matrix-badge ${badgeType}"><i class="bi ${badgeIcon}"></i>${badgeText}</span>
          <span class="uai-matrix-text">${cleanText}</span>
        </div>
      `;
    } else if (st.type === 'data') {
      const cleanTitle = escapeHtml(st.title || 'Данные инструмента')
        .replace(/^[>*\s﻿ ​�]*(?:[📊\s]*)+/g, '')
        .replace(/^[*_\s]+/, '')
        .replace(/[*_\s]+$/, '')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>');

      return `
        <div class="uai-investigation-step uai-matrix-step uai-matrix-step-data d-flex flex-column gap-1 w-100">
          <div class="d-flex align-items-center gap-1.5 flex-wrap">
            <span class="uai-matrix-prompt">&gt;</span>
            <span class="uai-matrix-badge uai-mb-data"><i class="bi bi-database-fill"></i>TELEMETRY</span>
            <span class="uai-matrix-text fw-semibold">${cleanTitle}</span>
          </div>
          <pre class="uai-data-preview uai-matrix-preview">${escapeHtml(st.data || '')}</pre>
        </div>
      `;
    }
    return '';
  }

  /**
   * Отрисовывает входящий поток ответа модели в реальном времени.
   * Шаги рассуждения вслух (> 💡, > ⚙️, > 🛠️, > 📊) оформляются в живой терминал стиля Матрицы.
   * @param {HTMLElement} containerEl Контейнер ответа
   * @param {string} rawStreamText Текущий накопленный текст ответа
   */
  function renderLiveStreamContent(containerEl, rawStreamText) {
    if (!containerEl) return;
    if (!rawStreamText) {
      containerEl.innerHTML = '<span class="uai-matrix-cursor">▌</span>';
      return;
    }

    const lines = rawStreamText.split('\n');
    const liveSteps = [];
    const dialogueLines = [];
    let inData = false;
    let dataBuffer = [];
    let currentTitle = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (isInvestigationDataLine(trimmed)) {
        if (inData && dataBuffer.length > 0) {
          liveSteps.push({
            type: 'data',
            title: currentTitle || 'Данные инструмента',
            data: dataBuffer.join('\n').trim()
          });
        }
        currentTitle = trimmed.replace(/^[>*\s﻿ ​�]+/, '');
        inData = true;
        dataBuffer = [];
        continue;
      }

      if (inData) {
        if (trimmed.startsWith('```json') || trimmed === '```') {
          if (trimmed === '```' && dataBuffer.length > 0) {
            liveSteps.push({
              type: 'data',
              title: currentTitle || 'Данные инструмента',
              data: dataBuffer.join('\n').trim()
            });
            inData = false;
            dataBuffer = [];
          }
          continue;
        }

        if (isInvestigationStatusLine(trimmed) || isInvestigationDataLine(trimmed) || (!trimmed.startsWith('>') && (trimmed.startsWith('###') || trimmed.startsWith('```')))) {
          if (dataBuffer.length > 0) {
            liveSteps.push({
              type: 'data',
              title: currentTitle || 'Данные инструмента',
              data: dataBuffer.join('\n').trim()
            });
          }
          inData = false;
          dataBuffer = [];
        } else {
          dataBuffer.push(line.replace(/^[>*\s﻿ ​�]+/, ''));
          continue;
        }
      }

      if (isInvestigationStatusLine(trimmed)) {
        liveSteps.push({
          type: 'status',
          text: trimmed.replace(/^[>*\s﻿ ​�]+/, '')
        });
        continue;
      }

      dialogueLines.push(line);
    }

    if (inData && dataBuffer.length > 0) {
      liveSteps.push({
        type: 'data',
        title: currentTitle || 'Данные инструмента',
        data: dataBuffer.join('\n').trim()
      });
    }

    let outHtml = '';

    if (liveSteps.length > 0) {
      let matrixStepsHtml = '';
      liveSteps.forEach(st => {
        matrixStepsHtml += renderMatrixStepHtml(st);
      });

      outHtml += `
        <div class="uai-matrix-terminal uai-matrix-live-terminal mb-3">
          <div class="uai-matrix-header">
            <div class="d-flex align-items-center gap-2">
              <span class="uai-matrix-indicator"></span>
              <span class="badge uai-matrix-steps-count font-monospace">${liveSteps.length} NODES</span>
              <span class="uai-matrix-title font-monospace"><i class="bi bi-terminal-fill me-1"></i>[MATRIX REASONING] Рассуждение вслух &bull; Зондирование хоста</span>
            </div>
            <span class="uai-matrix-toggle-hint small font-monospace"><span class="uai-matrix-cursor">▌</span> LIVE</span>
          </div>
          <div class="uai-matrix-body">
            ${matrixStepsHtml}
          </div>
        </div>
      `;
    }

    const dialogueText = dialogueLines.join('\n').trim();
    if (dialogueText) {
      outHtml += `<div>${formatMarkdownText(dialogueText)}<span class="uai-matrix-cursor">▌</span></div>`;
    } else if (liveSteps.length === 0) {
      outHtml += `<div>${escapeHtml(rawStreamText).replace(/\n/g, '<br>')}<span class="uai-matrix-cursor">▌</span></div>`;
    }

    containerEl.innerHTML = outHtml;
  }

  /**
   * Собственный парсер ответа модели: распознает готовые инструменты (```action),
   * команды PowerShell, этапы расследования WikiLLM Toolbox и структурирует диалог.
   * @param {string} rawText Текст ответа модели
   * @returns {string} Итоговый HTML диалога
   */
  function parseModelResponse(rawText) {
    if (!rawText) return '';
    let text = cleanChatGreetings(String(rawText));

    // 1. Поиск и извлечение готовых инструментов (блоки ```action { ... } ```)
    const actionBlocks = [];
    text = text.replace(/```action\s*({[\s\S]*?})\s*```/gi, (match, jsonStr) => {
      try {
        const parsed = JSON.parse(jsonStr.trim());
        if (parsed && (parsed.execution_command || parsed.command || parsed.probe_script)) {
          actionBlocks.push(parsed);
          return `###__ACTION_PLACEHOLDER_${actionBlocks.length - 1}__###`;
        }
      } catch (_) {}
      return match;
    });

    // 2. Поиск вызовов создания инструментов create_custom_tool в ```tool_call или ```json
    text = text.replace(/```(?:tool_call|json)?\s*({[\s\S]*?"(?:tool_name|create_custom_tool)"[\s\S]*?})\s*```/gi, (match, jsonStr) => {
      try {
        const parsed = JSON.parse(jsonStr.trim());
        const tName = parsed.tool_name || '';
        const args = parsed.arguments || parsed;
        if (tName === 'create_custom_tool' || args.probe_script || args.execution_command) {
          actionBlocks.push({
            title: args.tool_title || args.title || tName || 'Синтезированный инструмент',
            description: args.description_ru || args.description || args.instructions || '',
            execution_command: args.probe_script || args.execution_command || args.command || '',
            action_id: args.tool_name || tName || 'custom_tool'
          });
          return `###__ACTION_PLACEHOLDER_${actionBlocks.length - 1}__###`;
        }
      } catch (_) {}
      return match;
    });

    // 3. Выделение шагов расследования (> 💡 ..., > ⚙️ ..., > 🛠️ ..., > 📊 ...)
    const investigationSteps = [];
    const lines = text.split('\n');
    const remainingLines = [];
    let inDataBlock = false;
    let dataBuffer = [];
    let currentStepTitle = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (isInvestigationDataLine(trimmed)) {
        if (inDataBlock && dataBuffer.length > 0) {
          investigationSteps.push({
            type: 'data',
            title: currentStepTitle || 'Данные инструмента',
            data: dataBuffer.join('\n').trim()
          });
        }
        currentStepTitle = trimmed.replace(/^[>*\s﻿ ​�]+/, '');
        inDataBlock = true;
        dataBuffer = [];
        continue;
      }

      if (inDataBlock) {
        if (trimmed.startsWith('```json') || trimmed === '```') {
          if (trimmed === '```' && dataBuffer.length > 0) {
            investigationSteps.push({
              type: 'data',
              title: currentStepTitle || 'Данные инструмента',
              data: dataBuffer.join('\n').trim()
            });
            inDataBlock = false;
            dataBuffer = [];
          }
          continue;
        }

        if (isInvestigationStatusLine(trimmed) || isInvestigationDataLine(trimmed) || (!trimmed.startsWith('>') && (trimmed.startsWith('###') || trimmed.startsWith('```')))) {
          if (dataBuffer.length > 0) {
            investigationSteps.push({
              type: 'data',
              title: currentStepTitle || 'Данные инструмента',
              data: dataBuffer.join('\n').trim()
            });
          }
          inDataBlock = false;
          dataBuffer = [];
        } else {
          dataBuffer.push(line.replace(/^[>*\s﻿ ​�]+/, ''));
          continue;
        }
      }

      if (isInvestigationStatusLine(trimmed)) {
        investigationSteps.push({
          type: 'status',
          text: trimmed.replace(/^[>*\s﻿ ​�]+/, '')
        });
        continue;
      }

      remainingLines.push(line);
    }

    if (inDataBlock && dataBuffer.length > 0) {
      investigationSteps.push({
        type: 'data',
        title: currentStepTitle || 'Данные инструмента',
        data: dataBuffer.join('\n').trim()
      });
    }

    // Сжимаем множественные переносы строк после удаления блоков расследования
    let parsedMainText = remainingLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();

    // 4. Поиск блоков команд Windows (powershell, pwsh, cmd, bat, batch, bash, sh) или блоков без языка
    parsedMainText = parsedMainText.replace(/```(?:powershell|pwsh|ps1|cmd|bat|batch|bash|sh)?\s*([\s\S]*?)```/gi, (match, code) => {
      const rawCode = unescapeHtml(code).trim();
      if (!rawCode) return match;
      const lowerMatch = match.toLowerCase();
      const isCmdLang = lowerMatch.startsWith('```cmd') || lowerMatch.startsWith('```bat') || lowerMatch.startsWith('```batch');
      const isPsLang = lowerMatch.startsWith('```powershell') || lowerMatch.startsWith('```pwsh') || lowerMatch.startsWith('```ps1');
      const isCmd = isCmdLang || isPsLang || isCommandLineString(rawCode);

      if (isCmd) {
        const isCmdShell = isCmdLang || /^(?:cmd\b|net\b|reg\b|taskkill\b|sc\b)/i.test(rawCode);
        const title = isCmdShell
          ? 'Команда CMD / net user к выполнению'
          : 'Команда PowerShell к выполнению';
        actionBlocks.push({
          title: title,
          description: 'Сгенерирована моделью для решения задачи',
          execution_command: rawCode,
          shell: isCmdShell ? 'cmd' : 'powershell',
          risk: /\b(?:delete|remove|format|drop|stop-computer|restart-computer)\b/i.test(rawCode) ? 'danger' : 'safe'
        });
        return `###__ACTION_PLACEHOLDER_${actionBlocks.length - 1}__###`;
      }
      return match;
    });

    // 5. Форматируем основной Markdown текст
    let html = formatMarkdownText(parsedMainText);

    // Удаляем избыточные <br> вокруг плейсхолдеров карточек инструментов
    html = html.replace(/(?:<br\s*\/?>\s*)+###__ACTION_PLACEHOLDER_/gi, '###__ACTION_PLACEHOLDER_');
    html = html.replace(/###__ACTION_PLACEHOLDER_(\d+)__(?:<br\s*\/?>\s*)+/gi, '###__ACTION_PLACEHOLDER_$1__');

    // 6. Подставляем готовые инструменты обратно
    actionBlocks.forEach((act, idx) => {
      const toolHtml = renderReadyToolWidget(act);
      html = html.replace(`###__ACTION_PLACEHOLDER_${idx}__###`, toolHtml);
    });

    // 7. Если были шаги расследования — оборачиваем их в красивый аккордеон в стиле Matrix
    if (investigationSteps.length > 0) {
      let stepsHtml = '';
      investigationSteps.forEach(st => {
        stepsHtml += renderMatrixStepHtml(st);
      });

      const accordionHtml = `
        <details class="uai-investigation-accordion uai-matrix-terminal mb-3" open>
          <summary class="uai-matrix-header">
            <div class="d-flex align-items-center gap-2">
              <span class="uai-matrix-indicator"></span>
              <span class="badge uai-matrix-steps-count font-monospace">${investigationSteps.length} NODES</span>
              <span class="uai-matrix-title font-monospace"><i class="bi bi-terminal-fill me-1"></i>[MATRIX REASONING] Ход рассуждений и зонды хоста</span>
            </div>
            <span class="uai-matrix-toggle-hint small font-monospace">CLICK TO TOGGLE</span>
          </summary>
          <div class="uai-investigation-body uai-matrix-body">
            ${stepsHtml}
          </div>
        </details>
      `;

      html = accordionHtml + html;
    }

    return html;
  }

  /**
   * Удаляет из начала ответа модели ритуальные приветствия, самопрезентации и вводную воду.
   * @param {string} text Исходный текст
   * @returns {string} Очищенный текст
   */
  function cleanChatGreetings(text) {
    if (!text || typeof text !== 'string') return text || '';
    let cleaned = text.trim();

    // 1. Ритуальное приветствие в начале
    cleaned = cleaned.replace(/^(?:Приветствую(?:,\s*коллега)?|Здравствуйте|Добрый\s+(?:день|вечер|утро)|Доброго\s+времени\s+суток)[!\.,]?\s*/i, '');

    // 2. Вводное предложение с самопредставлением и фактом анализа данных
    // "Как эксперт по системному администрированию и безопасности Windows, я провел анализ установленного пакета Python 3.14.7 (Freethreaded) на вашей рабочей станции."
    const patternExpert = /^(?:Как\s+(?:эксперт|системный|ведущий|главный|старший|инженер|архитектор|специалист|консультант|администратор)[^\n]*?(?:я\s+(?:провел[а]?|проанализировал[а]?|изучил[а]?)|проанализировал[а]?|провел[а]?|изучил[а]?)[^\n]*?(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))/i;
    cleaned = cleaned.replace(patternExpert, '');

    // 3. Вводное предложение типа 'Я провел анализ представленных данных...'
    const patternYa = /^(?:Я\s+(?:провел[а]?|проанализировал[а]?|изучил[а]?)\s+(?:детальный\s+|технический\s+|глубокий\s+)?(?:анализ|представленные\s+данные|данные|информацию|телеметрию)[^\n]*?(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))/i;
    cleaned = cleaned.replace(patternYa, '');

    // 4. Преамбулы типа 'Относительно вашего вопроса...' или 'В качестве эксперта...'
    const patternIntro = /^(?:(?:В\s+качестве\s+эксперта|Относительно\s+(?:вашего|заданного)?\s*вопроса)[^\n]*?(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))/i;
    cleaned = cleaned.replace(patternIntro, '');

    // 5. Заголовок-заглушка "### Экспертное заключение по..."
    cleaned = cleaned.replace(/^(?:###\s+Экспертное\s+заключение\s+по[^\n]*\n+)/i, '');

    return cleaned.trim();
  }

  /**
   * Форматирует Markdown разметку в читаемый и семантически корректный HTML диалога.
   * Поддерживает блоки кода, инлайн-код, markdown таблицы, callout цитаты, заголовки,
   * списки, разделители, жирный/курсив и ссылки.
   * @param {string} text Текст Markdown
   * @returns {string} HTML
   */
  function formatMarkdownText(text) {
    if (!text) return '';
    let str = String(text);

    // 1. Извлечение и защита многострочных блоков кода
    const codeBlocks = [];
    str = str.replace(/```(\w+)?\s*([\s\S]*?)```/g, (match, lang, code) => {
      const rawCode = unescapeHtml(code).trim();
      const normalizedLang = (lang || '').toLowerCase().trim();
      const isPowershell = ['powershell', 'pwsh', 'ps1', 'ps'].includes(normalizedLang) ||
                           (!normalizedLang && isCommandLineString(rawCode));
      let blockHtml = '';
      if (isPowershell) {
        blockHtml = renderInteractiveCommandWidget(rawCode, 'powershell');
      } else if (['cmd', 'bat', 'batch'].includes(normalizedLang)) {
        blockHtml = renderInteractiveCommandWidget(rawCode, 'cmd');
      } else {
        const displayLang = normalizedLang || (rawCode.startsWith('{') || rawCode.startsWith('[') ? 'json' : '');
        blockHtml = `<pre class="uai-code-block p-2.5 rounded small my-2 font-monospace ${displayLang ? 'language-' + displayLang : ''}" style="overflow-x: auto;"><code>${escapeHtml(rawCode)}</code></pre>`;
      }
      codeBlocks.push(blockHtml);
      return `\n\n@@@UAI_CODE_BLOCK_${codeBlocks.length - 1}@@@\n\n`;
    });

    // 2. Извлечение и защита инлайн-кода `код`
    const inlineCodes = [];
    str = str.replace(/`([^`\n]+)`/g, (match, inline) => {
      const cleanInline = inline.trim();
      inlineCodes.push(`<code class="uai-inline-code px-1 py-0.5 rounded font-monospace small">${escapeHtml(cleanInline)}</code>`);
      return `@@@UAI_INLINE_CODE_${inlineCodes.length - 1}@@@`;
    });

    // 3. Безопасное экранирование спецсимволов HTML в основном тексте
    str = str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

    // Возвращаем &gt; в начале строк обратно в '>', чтобы работали цитаты `> `
    str = str.replace(/^(\s*)&gt;/gm, '$1>');

    // 4. Парсинг Markdown таблиц (| col1 | col2 |)
    str = str.replace(/((?:^[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$))+)/gm, (tableBlock) => {
      const rows = tableBlock.trim().split('\n').map(r => r.trim()).filter(Boolean);
      if (rows.length < 2) return tableBlock;
      if (!/^[ \t]*\|(?:\s*:?-+:?\s*\|)+[ \t]*$/.test(rows[1])) {
        return tableBlock;
      }
      const parseCells = (row) => {
        const inner = row.replace(/^[ \t]*\|/, '').replace(/\|[ \t]*$/, '');
        return inner.split('|').map(c => c.trim());
      };

      const headerCells = parseCells(rows[0]);
      let theadHtml = '<thead><tr>' + headerCells.map(c => `<th class="py-1 px-2">${c}</th>`).join('') + '</tr></thead>';

      let tbodyHtml = '<tbody>';
      for (let r = 2; r < rows.length; r++) {
        const cells = parseCells(rows[r]);
        tbodyHtml += '<tr>' + cells.map(c => `<td class="py-1 px-2">${c}</td>`).join('') + '</tr>';
      }
      tbodyHtml += '</tbody>';

      return `\n<div class="table-responsive my-2"><table class="table table-sm table-bordered uai-markdown-table mb-0">${theadHtml}${tbodyHtml}</table></div>\n`;
    });

    // 5. Блоки цитат и callout (> 💡, > ⚠️, > ❌, > ...)
    str = str.replace(/((?:^[ \t]*>[^\n]*(?:\r?\n|$))+)/gm, (bqBlock) => {
      const rawLines = bqBlock.split('\n')
        .map(l => l.replace(/^[ \t]*>[ \t]?/, '').trim())
        .filter(Boolean);
      if (rawLines.length === 0) return '';

      // Группируем последовательные строки в отдельные цитаты, если следующая строка начинается с callout-иконки
      const groups = [];
      let currentGroup = [];

      rawLines.forEach(line => {
        const isCalloutStart = /^[💡⚠️❌ℹ️]|^\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i.test(line);
        if (isCalloutStart && currentGroup.length > 0) {
          groups.push(currentGroup.join('<br>'));
          currentGroup = [line];
        } else {
          currentGroup.push(line);
        }
      });
      if (currentGroup.length > 0) {
        groups.push(currentGroup.join('<br>'));
      }

      return groups.map(content => {
        let bqClass = 'uai-blockquote';
        if (/^[⚠️❌\s]|WARNING|DANGER|CAUTION/i.test(content) || content.includes('⚠️') || content.includes('❌')) {
          bqClass += ' uai-bq-warning';
        } else if (/^[💡\s]|TIP|RECOMMENDATION/i.test(content) || content.includes('💡')) {
          bqClass += ' uai-bq-tip';
        } else if (/^[ℹ️\s]|NOTE|INFO/i.test(content) || content.includes('ℹ️')) {
          bqClass += ' uai-bq-info';
        }
        return `\n<blockquote class="${bqClass} my-2 p-2 border-start border-3 rounded-end">${content}</blockquote>\n`;
      }).join('');
    });

    // 6. Заголовки ######, #####, ####, ###, ##, #
    str = str.replace(/^[ \t]*######[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.8rem;">$1</h6>');
    str = str.replace(/^[ \t]*#####[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.85rem;">$1</h6>');
    str = str.replace(/^[ \t]*####[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.9rem;">$1</h6>');
    str = str.replace(/^[ \t]*###[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info mt-2.5 mb-1.5 fs-6">$1</h6>');
    str = str.replace(/^[ \t]*##[ \t]+(.*$)/gm, '<h5 class="fw-bold text-info mt-3 mb-2 fs-6">$1</h5>');
    str = str.replace(/^[ \t]*#[ \t]+(.*$)/gm, '<h5 class="fw-bold text-info mt-3 mb-2">$1</h5>');

    // 7. Горизонтальные линии ---, ***, ___
    str = str.replace(/^[ \t]*(?:---|\*\*\*|___)[ \t]*$/gm, '<hr class="uai-divider my-2 border-secondary border-opacity-25">');

    // 8. Ссылки [текст](url)
    str = str.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="uai-markdown-link text-info text-decoration-underline">$1</a>');

    // 9. Жирный и курсив
    str = str.replace(/\*\*\*(.+?)\*\*\*/g, '<strong class="text-light"><em class="text-secondary-emphasis">$1</em></strong>');
    str = str.replace(/\*\*(.+?)\*\*/g, '<strong class="text-light">$1</strong>');
    str = str.replace(/(^|[^*])\*([^*]+?)\*([^*]|$)/g, '$1<em class="text-secondary-emphasis">$2</em>$3');

    // 10. Нумерованные и маркированные списки
    str = str.replace(/^[ \t]*(\d+)\.[ \t]+(.*$)/gm, '<div class="ms-2 mb-1 d-flex align-items-start gap-1.5"><span class="badge bg-secondary font-monospace" style="font-size: 0.72rem;">$1</span><span>$2</span></div>');
    str = str.replace(/^[ \t]*[-*•][ \t]+(.*$)/gm, '<li class="ms-3 mb-1">$1</li>');

    // 11. Переносы строк и очистка <br> вокруг блочных элементов
    str = str.replace(/\n/g, '<br>');
    str = str.replace(/(?:<br\s*\/?>\s*)*(<\/?(?:div|blockquote|table|thead|tbody|tr|th|td|h[1-6]|ul|ol|li|hr|pre)[^>]*>)(?:<br\s*\/?>\s*)*/gi, '$1');
    str = str.replace(/(?:<br\s*\/?>\s*)*(@@@UAI_(?:CODE_BLOCK|INLINE_CODE)_\d+@@@)(?:<br\s*\/?>\s*)*/gi, '$1');

    // 12. Восстановление инлайн-кода
    inlineCodes.forEach((codeHtml, idx) => {
      str = str.replace(`@@@UAI_INLINE_CODE_${idx}@@@`, codeHtml);
    });

    // 13. Восстановление блоков кода
    codeBlocks.forEach((blockHtml, idx) => {
      str = str.replace(`@@@UAI_CODE_BLOCK_${idx}@@@`, blockHtml);
    });

    return str;
  }

  /**
   * Рендерит секцию документации и советов разработчику.
   * Конвертирует встроенные кодовые блоки (PowerShell/CMD/Bash/Python) в интерактивный терминал с кнопками Run и Копировать.
   * @param {string|object} adviceText Текст советов или объект от модели
   * @returns {string} Отформатированный HTML
   */
  function renderDevAdviceContent(adviceText) {
    if (!adviceText) return '';
    let text = typeof adviceText === 'object' ? JSON.stringify(adviceText, null, 2) : String(adviceText);
    return formatMarkdownText(text);
  }

  /**
   * Конвертирует сырой JSON или структурированный ответ модели в читаемый диалоговый формат.
   * @param {any} raw Ответ модели (строка или объект)
   * @returns {string} Отформатированный HTML диалога
   */
  function convertJsonToDialogue(raw) {
    if (!raw) return '';
    let obj = null;

    if (typeof raw === 'object' && raw !== null) {
      obj = raw;
    } else if (typeof raw === 'string') {
      let trimmed = raw.trim();
      const isPlainDialogue = trimmed.includes('#') || trimmed.includes('> 💡') || trimmed.includes('💡') || trimmed.includes('```');

      // Снимаем любые markdown fences с 1, 2, 3 или 4 бэктиками (например ```json, ``json, ````json)
      const mdJsonMatch = trimmed.match(/^`{1,4}(?:json)?\s*([\s\S]*?)\s*`{1,4}$/i);
      if (mdJsonMatch) {
        trimmed = mdJsonMatch[1].trim();
      }
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
          obj = JSON.parse(trimmed);
        } catch (_) {}
      } else if (!isPlainDialogue && trimmed.includes('{') && trimmed.includes('}')) {
        try {
          const s = trimmed.indexOf('{');
          const e = trimmed.lastIndexOf('}') + 1;
          obj = JSON.parse(trimmed.substring(s, e));
        } catch (_) {}
      }
    }

    if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
      // Разворачиваем вложенные словари-обертки (analysis_report, report, diagnostic, data, result и т.д.)
      while (obj && typeof obj === 'object' && !Array.isArray(obj)) {
        const keys = Object.keys(obj);
        if (keys.length === 1 && typeof obj[keys[0]] === 'object' && obj[keys[0]] !== null && !Array.isArray(obj[keys[0]])) {
          obj = obj[keys[0]];
        } else if (obj.analysis_report && typeof obj.analysis_report === 'object') {
          obj = obj.analysis_report;
        } else if (obj.report && typeof obj.report === 'object') {
          obj = obj.report;
        } else if (obj.diagnostic && typeof obj.diagnostic === 'object') {
          obj = obj.diagnostic;
        } else if (obj.data && typeof obj.data === 'object') {
          obj = obj.data;
        } else if (obj.result && typeof obj.result === 'object') {
          obj = obj.result;
        } else {
          break;
        }
      }

      // 1. Проверяем наличие детального технического заключения (technical_assessment)
      const techAssessment = obj.technical_assessment || obj.assessment || obj.analysis;
      if (techAssessment && typeof techAssessment === 'string') {
        let techHtml = '';

        // Заголовочная информация о сущности
        const entityName = obj.entity || obj.name || obj.title;
        const pid = obj.pid;
        if (entityName || pid) {
          techHtml += `
            <div class="mb-2 d-flex align-items-center gap-1.5 flex-wrap">
              <span class="badge bg-secondary font-monospace fs-6 px-2 py-1"><i class="bi bi-cpu me-1"></i>${escapeHtml(entityName || 'Процесс')}</span>
              ${pid ? `<span class="badge bg-dark border border-secondary font-monospace px-2 py-1">PID: ${escapeHtml(pid)}</span>` : ''}
            </div>
          `;
        }

        // Суть проблемы
        const issue = obj.issue_summary || obj.issue;
        if (issue) {
          techHtml += `
            <div class="p-2.5 mb-3 rounded bg-warning bg-opacity-10 border border-warning border-opacity-25 text-warning small">
              <strong class="d-flex align-items-center gap-1.5"><i class="bi bi-exclamation-triangle-fill"></i> Суть проблемы:</strong>
              <div class="mt-1 text-light">${formatMarkdownText(issue)}</div>
            </div>
          `;
        }

        // Основное тело технического отчета
        techHtml += `<div class="dialogue-block mb-3 text-light" style="line-height: 1.6;">${parseModelResponse(techAssessment)}</div>`;

        // Рекомендация эксперта
        const rec = obj.recommendation || obj.recommendations;
        if (rec && typeof rec === 'string' && !techAssessment.includes(rec)) {
          techHtml += `
            <div class="p-2.5 mb-2 rounded dialogue-block uai-recommendation-box bg-dark bg-opacity-50 border border-warning border-opacity-25">
              <strong class="text-warning"><i class="bi bi-lightbulb me-1"></i>Рекомендация эксперта:</strong> <span class="text-light">${formatMarkdownText(rec)}</span>
            </div>
          `;
        }

        // Вердикт безопасности
        const verdict = obj.security_verdict || obj.verdict;
        if (verdict && typeof verdict === 'string' && !techAssessment.includes(verdict)) {
          techHtml += `<div class="dialogue-block mb-2"><strong class="text-warning"><i class="bi bi-shield-check me-1"></i>Вердикт:</strong> <span class="text-light">${formatMarkdownText(verdict)}</span></div>`;
        }

        // Рекомендуемые действия
        const actions = obj.action_steps || obj.actions;
        if (Array.isArray(actions) && actions.length > 0) {
          techHtml += `
            <div class="dialogue-block mt-2">
              <strong class="text-info small text-uppercase fw-bold"><i class="bi bi-list-check me-1"></i>Рекомендуемые действия:</strong>
              <div class="mt-1 small text-light">
                ${actions.map(s => {
                  const sStr = typeof s === 'object' ? JSON.stringify(s) : String(s);
                  if (isCommandLineString(sStr)) {
                    return `<div class="mb-1.5">${renderInteractiveCommandWidget(sStr, 'powershell')}</div>`;
                  }
                  return `<li class="ms-3 mb-1">${escapeHtml(sStr)}</li>`;
                }).join('')}
              </div>
            </div>
          `;
        }

        // Прямая команда на исполнение (при наличии в ответе модели)
        const directCmd = obj.execution_command || obj.powershell_command || obj.command || (obj.action && obj.action.execution_command);
        if (directCmd && typeof directCmd === 'string') {
          techHtml += `
            <div class="dialogue-block mt-2">
              <strong class="text-info small text-uppercase fw-bold"><i class="bi bi-play-circle-fill me-1"></i>Команда действия:</strong>
              ${renderInteractiveCommandWidget(directCmd, 'powershell')}
            </div>
          `;
        }

        const devAdvTech = obj.developer_advice || obj.developer_tips || obj.dev_advice;
        if (devAdvTech) {
          techHtml += `
            <div class="uai-dev-advice-wrapper mt-3 pt-2 border-top border-secondary border-opacity-25">
              <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
                <button class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5 py-1 px-3 rounded-pill uai-btn-toggle-dev" 
                        type="button" data-bs-toggle="collapse" data-bs-target="#uai-dev-advice-collapse" aria-expanded="true">
                  <i class="bi bi-code-slash"></i>
                  <strong class="small">Советы разработчику &amp; Автоматизация</strong>
                  <i class="bi bi-chevron-down ms-1"></i>
                </button>
                <div class="d-flex align-items-center gap-1.5">
                  <span class="badge border border-info text-info small" style="font-size: 0.72rem;">
                    <i class="bi bi-cpu me-1"></i>API &amp; Scripting
                  </span>
                </div>
              </div>
              <div class="collapse show" id="uai-dev-advice-collapse">
                <div class="p-3 rounded uai-dev-advice-box">
                  ${renderDevAdviceContent(devAdvTech)}
                </div>
              </div>
            </div>
          `;
        }

        return techHtml;
      }

      // 2. Стандартный разбор полей
      let html = '';
      if (obj.answer) {
        html += `<div class="dialogue-block mb-2 text-light" style="line-height: 1.6;">${parseModelResponse(obj.answer)}</div>`;
      }
      if (obj.summary) {
        html += `<div class="dialogue-block mb-2"><strong class="text-info"><i class="bi bi-card-text me-1"></i>Суть / Назначение:</strong> <span class="text-light">${formatMarkdownText(obj.summary)}</span></div>`;
      }
      if (obj.developer || obj.category) {
        const dev = escapeHtml(obj.developer || 'Неизвестен');
        const cat = escapeHtml(obj.category || 'Компонент');
        html += `<div class="dialogue-block mb-2"><strong class="text-secondary"><i class="bi bi-building me-1"></i>Разработчик / Категория:</strong> <span class="text-light">${dev} (${cat})</span></div>`;
      }
      if (obj.security_verdict) {
        html += `<div class="dialogue-block mb-2"><strong class="text-warning"><i class="bi bi-shield-check me-1"></i>Оценка безопасности:</strong> <span class="text-light">${formatMarkdownText(obj.security_verdict)}</span></div>`;
      }
      if (obj.performance_impact) {
        html += `<div class="dialogue-block mb-2"><strong class="text-info"><i class="bi bi-speedometer2 me-1"></i>Влияние на ресурсы:</strong> <span class="text-light">${formatMarkdownText(obj.performance_impact)}</span></div>`;
      }
      if (obj.recommendation) {
        html += `
          <div class="p-2 mb-2 rounded dialogue-block uai-recommendation-box bg-dark bg-opacity-50 border border-warning border-opacity-25">
            <strong class="text-warning"><i class="bi bi-lightbulb me-1"></i>Рекомендация эксперта:</strong> <span class="text-light">${formatMarkdownText(obj.recommendation)}</span>
          </div>
        `;
      }
      if (Array.isArray(obj.action_steps) && obj.action_steps.length > 0) {
        html += `
          <div class="dialogue-block mt-2">
            <strong class="text-info small text-uppercase fw-bold"><i class="bi bi-list-check me-1"></i>Рекомендуемые действия:</strong>
            <div class="mt-1 small text-light">
              ${obj.action_steps.map(s => {
                const sStr = typeof s === 'object' ? JSON.stringify(s) : String(s);
                if (isCommandLineString(sStr)) {
                  return `<div class="mb-1.5">${renderInteractiveCommandWidget(sStr, 'powershell')}</div>`;
                }
                return `<li class="ms-3 mb-1">${escapeHtml(sStr)}</li>`;
              }).join('')}
            </div>
          </div>
        `;
      }
      const directCmd2 = obj.execution_command || obj.powershell_command || obj.command || (obj.action && obj.action.execution_command);
      if (directCmd2 && typeof directCmd2 === 'string') {
        html += `
          <div class="dialogue-block mt-2">
            <strong class="text-info small text-uppercase fw-bold"><i class="bi bi-play-circle-fill me-1"></i>Команда действия:</strong>
            ${renderInteractiveCommandWidget(directCmd2, 'powershell')}
          </div>
        `;
      }
      if (Array.isArray(obj.possible_causes) && obj.possible_causes.length > 0) {
        html += `
          <div class="dialogue-block mt-2">
            <strong class="text-warning small text-uppercase fw-bold"><i class="bi bi-exclamation-circle me-1"></i>Возможные причины:</strong>
            <ul class="mb-0 ps-3 mt-1 small text-light">
              ${obj.possible_causes.map(c => `<li class="mb-1">${escapeHtml(c)}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      const devAdv = obj.developer_advice || obj.developer_tips || obj.dev_advice;
      if (devAdv) {
        html += `
          <div class="uai-dev-advice-wrapper mt-3 pt-2 border-top border-secondary border-opacity-25">
            <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
              <button class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5 py-1 px-3 rounded-pill uai-btn-toggle-dev" 
                      type="button" data-bs-toggle="collapse" data-bs-target="#uai-dev-advice-collapse" aria-expanded="true">
                <i class="bi bi-code-slash"></i>
                <strong class="small">Советы разработчику &amp; Автоматизация</strong>
                <i class="bi bi-chevron-down ms-1"></i>
              </button>
              <div class="d-flex align-items-center gap-1.5">
                <span class="badge border border-info text-info small" style="font-size: 0.72rem;">
                  <i class="bi bi-cpu me-1"></i>API &amp; Scripting
                </span>
              </div>
            </div>
            <div class="collapse show" id="uai-dev-advice-collapse">
              <div class="p-3 rounded uai-dev-advice-box">
                ${renderDevAdviceContent(devAdv)}
              </div>
            </div>
          </div>
        `;
      }

      // 3. Fallback: аккуратный вывод свойств без сырого JSON
      if (!html) {
        html = '<div class="dialogue-generic-props">';
        for (const [key, val] of Object.entries(obj)) {
          if (val !== null && val !== undefined && key !== 'canonical_key' && key !== 'status') {
            if (typeof val === 'string' && (key.toLowerCase().includes('command') || key.toLowerCase().includes('cmd') || isCommandLineString(val))) {
              html += `<div class="mb-2"><strong class="text-info">${escapeHtml(key)}:</strong>${renderInteractiveCommandWidget(val, 'powershell')}</div>`;
            } else if (Array.isArray(val)) {
              html += `<div class="mb-2"><strong class="text-info">${escapeHtml(key)}:</strong><ul class="mb-0 ps-3 mt-1 small text-light">${val.map(item => `<li>${escapeHtml(typeof item === 'object' ? JSON.stringify(item) : String(item))}</li>`).join('')}</ul></div>`;
            } else if (typeof val === 'object') {
              html += `<div class="mb-2"><strong class="text-info">${escapeHtml(key)}:</strong><div class="ps-3 mt-1 small text-light">${Object.entries(val).map(([k, v]) => `<div><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</div>`).join('')}</div></div>`;
            } else {
              html += `<div class="mb-1.5"><strong class="text-info">${escapeHtml(key)}:</strong> <span class="text-light">${escapeHtml(String(val))}</span></div>`;
            }
          }
        }
        html += '</div>';
      }

      return html;
    }

    return parseModelResponse(raw);
  }

  /**
   * Универсальный вызов модального окна AI-анализатора для строки или сущности.
   * @param {Object} options Объект конфигурации диалога
   */
  let currentModalOptions = null;
  function show(options) {
    currentModalOptions = options;
    const rawType = options?.tableType || 'generic';
    const normalizedType = normalizeTableType(rawType);
    const panelId = options?.panelId || 'panel-root';

    const opts = Object.assign({
      title: 'Детали записи',
      subtitle: '',
      icon: '🔍',
      panelId: panelId,
      badges: [],
      metadata: [],
      rawTitle: 'Данные / Путь',
      rawContent: '',
      tableType: normalizedType,
      model: '',
      provider: 'gemini',
      systemInstruction: '',
      requestData: {},
      autoRun: false,
      actions: []
    }, options, { tableType: normalizedType, panelId: panelId });

    // Множество вопросов, на которые уже был получен ответ (для деактивации в блоке быстрых вопросов)
    const answeredQuestions = new Set();

    function normalizeQuestionText(txt) {
      if (!txt) return '';
      return String(txt).trim().toLowerCase().replace(/^[«"'\s]+|[»"'\s]+$/g, '');
    }

    function markQuestionInUIAsAnswered(questionText) {
      const norm = normalizeQuestionText(questionText);
      if (!norm) return;
      answeredQuestions.add(norm);

      const container = document.getElementById('uai-chat-quick-buttons');
      if (!container) return;

      container.querySelectorAll('.chat-prompt-link').forEach(link => {
        const linkNorm = normalizeQuestionText(link.dataset.prompt || link.textContent);
        if (linkNorm === norm) {
          link.classList.add('disabled', 'answered');
          link.classList.remove('selected', 'active');
          link.setAttribute('aria-disabled', 'true');
          link.setAttribute('tabindex', '-1');
          link.style.pointerEvents = 'none';
          link.title = 'Ответ на этот вопрос уже получен';

          const row = link.closest('.chat-prompt-row');
          if (row) {
            row.classList.add('answered');
            const bullet = row.querySelector('.chat-prompt-bullet');
            if (bullet) {
              bullet.innerHTML = '<i class="bi bi-check2 text-success" title="Ответ получен" style="font-size: 0.95rem;"></i>';
            }
          }
        }
      });
    }

    // Единый словарь метаданных строки для использования во всех обработчиках
    const metaDict = {};
    (opts.metadata || []).forEach(m => {
      if (m && m.label && (m.value !== undefined && m.value !== null)) {
        metaDict[m.label] = m.value;
      }
    });

    const modalEl = ensureModalElement();

    // Icon & Title
    const iconEl = document.getElementById('uai-modal-icon');
    if (iconEl) iconEl.textContent = opts.icon;

    const titleEl = document.getElementById('uai-modal-title');
    if (titleEl) titleEl.textContent = opts.title;

    // Badges
    const badgesContainer = document.getElementById('uai-modal-badges');
    if (badgesContainer) {
      badgesContainer.innerHTML = (opts.badges || []).map(b => {
        const cls = b.class || 'badge border text-secondary';
        return `<span class="${cls}">${escapeHtml(b.text)}</span>`;
      }).join('');
    }

    // Panel & Type Badges in System Section
    const panelBadge = document.getElementById('uai-modal-panel-badge');
    const typeBadge = document.getElementById('uai-modal-type-badge');
    const customBadge = document.getElementById('uai-modal-custom-badge');
    const providerSelect = document.getElementById('uai-modal-provider-select');
    const modelInput = document.getElementById('uai-modal-model-input');
    const systemTextarea = document.getElementById('uai-modal-system-instruction');
    const systemStatus = document.getElementById('uai-modal-system-status');
    const saveSystemBtn = document.getElementById('btn-uai-modal-save-system');
    const resetSystemBtn = document.getElementById('btn-uai-modal-reset-system');

    if (panelBadge) panelBadge.textContent = `Панель: #${opts.panelId}`;
    if (typeBadge) typeBadge.textContent = `Тип: ${opts.tableType}`;
    if (providerSelect && opts.provider) providerSelect.value = opts.provider;
    if (modelInput) modelInput.value = opts.model || '';

    // Актуализируем визуальное состояние переключателя режима
    updateModeButtonsUI();

    const btnModelOnly = document.getElementById('btn-mode-model-only');
    const btnModelWiki = document.getElementById('btn-mode-model-wikillm');
    if (btnModelOnly) {
      btnModelOnly.onclick = () => {
        if (getAssistantMode() === 'model_only') return;
        setAssistantMode('model_only');
        executeDiagnostics(true, false);
      };
    }
    if (btnModelWiki) {
      btnModelWiki.onclick = () => {
        if (getAssistantMode() === 'model_wikillm') return;
        setAssistantMode('model_wikillm');
        checkWikiLLMKnowledge();
      };
    }

    // Очистка предыдущего диалога дополнительных вопросов
    const existingThread = document.getElementById('uai-qa-conversation-thread');
    if (existingThread) existingThread.innerHTML = '';

    // Metadata Grid
    const metaContainer = document.getElementById('uai-modal-metadata-grid');
    if (metaContainer) {
      metaContainer.innerHTML = (opts.metadata || []).map(m => {
        const colSize = m.fullWidth ? 'col-sm-12' : 'col-sm-6';
        let valHtml = '';
        if (m.html) {
          valHtml = m.html;
        } else if (m.isCode) {
          valHtml = `<span class="font-monospace text-info small" style="word-break: break-all;">${escapeHtml(m.value || '-')}</span>`;
        } else {
          valHtml = `<span class="text-body">${escapeHtml(m.value || '-')}</span>`;
        }
        return `
          <div class="${colSize}">
            <strong class="text-secondary">${escapeHtml(m.label)}:</strong> ${valHtml}
          </div>
        `;
      }).join('');
    }

    // Сброс сворачиваемых спойлеров (скрыты по умолчанию)
    const collapseRaw = document.getElementById('collapseRawData');
    if (collapseRaw) collapseRaw.classList.remove('show');
    const collapseSys = document.getElementById('collapseSysInstruction');
    if (collapseSys) collapseSys.classList.remove('show');
    const collapseDev = document.getElementById('collapseDevAdvice');
    if (collapseDev) collapseDev.classList.remove('show');
    const btnToggleDev = document.getElementById('btn-toggle-dev-advice');
    if (btnToggleDev) btnToggleDev.style.display = 'none';
    const devContentReset = document.getElementById('uai-modal-dev-content');
    if (devContentReset) devContentReset.innerHTML = '';

    // Кнопка спойлера и блок сырого контента
    const btnToggleRaw = document.getElementById('btn-toggle-raw-data');
    const rawContainer = document.getElementById('uai-modal-raw-container');
    const rawTitleEl = document.getElementById('uai-modal-raw-title');
    const rawContentEl = document.getElementById('uai-modal-raw-content');
    if (rawContainer && rawTitleEl && rawContentEl) {
      if (opts.rawContent && typeof opts.rawContent === 'string' && opts.rawContent.trim()) {
        rawTitleEl.textContent = opts.rawTitle || 'Контекст / Данные';
        rawContentEl.textContent = opts.rawContent;
        if (btnToggleRaw) btnToggleRaw.style.display = 'inline-block';
      } else {
        if (btnToggleRaw) btnToggleRaw.style.display = 'none';
      }
    }

    // Загрузка системной инструкции для текущего типа / конкретной панели
    let currentTemplateData = null;
    const currentLang = getCurrentLang();
    const queryParts = [];
    if (opts.panelId) queryParts.push(`panel_id=${encodeURIComponent(opts.panelId)}`);
    if (currentLang) queryParts.push(`lang=${encodeURIComponent(currentLang)}`);
    const panelQuery = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';

    async function loadSystemInstruction() {
      try {
        const data = await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(opts.tableType)}${panelQuery}`, {}, 15000);
        if (data) {
          currentTemplateData = data;
          if (systemTextarea) {
            systemTextarea.value = opts.systemInstruction || data.system_instruction || '';
          }
          if (customBadge) {
            customBadge.style.display = data.is_customized ? 'inline-block' : 'none';
            if (data.is_customized) {
              customBadge.textContent = data.table_type === opts.panelId ? 'Панель (Кастом)' : 'Тип (Кастом)';
            }
          }
          if (systemStatus) {
            if (data.is_customized) {
              systemStatus.textContent = data.table_type === opts.panelId
                ? `Индивидуальная инструкция панели #${opts.panelId}`
                : `Пользовательская системная инструкция типа «${opts.tableType}»`;
            } else {
              systemStatus.textContent = `Стандартная системная инструкция: «${data.name || opts.tableType}»`;
            }
          }
        }
      } catch (e) {
        console.warn('[AIModalDialog] Ошибка загрузки системной инструкции:', e);
      }
    }

    loadSystemInstruction();

    // Сохранение системной инструкции прямо из модального окна (приоритетно для panel_id)
    if (saveSystemBtn) {
      saveSystemBtn.onclick = async () => {
        const instruction = systemTextarea ? systemTextarea.value : '';
        try {
          const promptTmpl = currentTemplateData?.prompt_template || '{title}\n{subtitle}\n{metadata}\n{raw_data}';
          const name = currentTemplateData?.name || (opts.panelId ? `Панель ${opts.panelId}` : opts.tableType);

          await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(opts.tableType)}${panelQuery}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              table_type: opts.tableType,
              name: name,
              system_instruction: instruction,
              prompt_template: promptTmpl
            })
          }, 6000);

          if (customBadge) {
            customBadge.style.display = 'inline-block';
            customBadge.textContent = opts.panelId ? 'Панель (Кастом)' : 'Кастомная';
          }
          if (systemStatus) {
            systemStatus.textContent = opts.panelId
              ? `Инструкция для панели #${opts.panelId} сохранена!`
              : 'Системная инструкция успешно сохранена!';
            systemStatus.className = 'text-success small';
            setTimeout(() => {
              if (systemStatus) {
                systemStatus.textContent = opts.panelId
                  ? `Индивидуальная инструкция панели #${opts.panelId} активна`
                  : 'Пользовательская инструкция активна';
                systemStatus.className = 'text-secondary small';
              }
            }, 3000);
          }
          if (window.showToast) window.showToast('Системная инструкция обновлена', 'success');
        } catch (err) {
          alert(`Ошибка сохранения инструкции: ${err.message}`);
        }
      };
    }

    // Сброс системной инструкции к дефолтной
    if (resetSystemBtn) {
      resetSystemBtn.onclick = async () => {
        const resetTargetTitle = opts.panelId ? `панели «#${opts.panelId}»` : `«${opts.tableType}»`;
        if (!confirm(`Сбросить системную инструкцию для ${resetTargetTitle} к значению по умолчанию?`)) return;
        try {
          const data = await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(opts.tableType)}/reset${panelQuery}`, {
            method: 'POST'
          }, 6000);
          if (data) {
            currentTemplateData = data;
            if (systemTextarea) systemTextarea.value = data.system_instruction || '';
            if (customBadge) customBadge.style.display = 'none';
            if (systemStatus) {
              systemStatus.textContent = 'Инструкция сброшена к системной по умолчанию';
              systemStatus.className = 'text-info small';
            }
          }
        } catch (err) {
          alert(`Ошибка сброса инструкции: ${err.message}`);
        }
      };
    }

    const refreshBtn = document.getElementById('btn-uai-modal-refresh');
    if (refreshBtn) {
      refreshBtn.style.display = 'none';
      refreshBtn.onclick = () => executeDiagnostics(true);
    }

    // AI Diagnostic section
    const aiExplanation = document.getElementById('uai-modal-ai-explanation');

    function renderPromptCallout() {
      if (!aiExplanation) return;
      aiExplanation.innerHTML = `
        <div class="p-3 text-center rounded uai-callout-box">
          <div class="text-secondary small mb-2">
            <i class="bi bi-info-circle me-1"></i>В базе знаний WikiLLM пока нет сохранённого описания для «${escapeHtml(opts.title)}».
          </div>
          <button type="button" class="btn btn-sm btn-primary d-inline-flex align-items-center gap-1.5" id="btn-uai-modal-run-ai">
            <i class="bi bi-robot"></i> Запросить AI-анализ с системной инструкцией
          </button>
        </div>
      `;
      const runBtn = document.getElementById('btn-uai-modal-run-ai');
      if (runBtn) {
        runBtn.onclick = () => executeDiagnostics(false);
      }
    }

    function renderQuickButtons(questions = []) {
      const container = document.getElementById('uai-chat-quick-buttons');
      if (!container) return;
      container.innerHTML = '';
      container.className = 'd-flex flex-column gap-1.5 my-2 w-100';

      const entityName = opts.title || 'компонента';
      const defaultQuestions = [
        `Каковы риски стабильности при работе «${entityName}»?`,
        `Безопасно ли принудительно отключить «${entityName}»?`,
        `Какие действия рекомендуется выполнить администратору?`
      ];
      const list = (Array.isArray(questions) && questions.length > 0) ? questions : defaultQuestions;
      list.forEach(qText => {
        const row = document.createElement('div');
        row.className = 'chat-prompt-row';

        const bullet = document.createElement('span');
        bullet.className = 'chat-prompt-bullet';
        bullet.textContent = '•';

        const link = document.createElement('a');
        link.href = '#';
        link.className = 'chat-prompt-link ui-quick-prompt-btn text-decoration-none border-bottom border-primary border-opacity-50';
        link.dataset.prompt = qText;
        link.textContent = `«${qText}»`;

        const isAnswered = answeredQuestions.has(normalizeQuestionText(qText));
        if (isAnswered) {
          link.classList.add('disabled', 'answered');
          link.setAttribute('aria-disabled', 'true');
          link.setAttribute('tabindex', '-1');
          link.style.pointerEvents = 'none';
          link.title = 'Ответ на этот вопрос уже получен';
          row.classList.add('answered');
          bullet.innerHTML = '<i class="bi bi-check2 text-success" title="Ответ получен" style="font-size: 0.95rem;"></i>';
        } else {
          link.title = 'Задать этот вопрос модели ИИ (одноразовый ответ)';
        }

        link.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          // Если вопрос уже обработан и ответ получен, он заблокирован и больше недоступен для выбора
          if (link.classList.contains('disabled') || link.getAttribute('aria-disabled') === 'true' || isAnswered) {
            return;
          }
          // 1. Помещаем наводящий вопрос в текстовое поле ввода
          if (chatInput) {
            chatInput.value = qText;
            chatInput.focus();
          }
          // 2. Подсвечиваем активный выбранный вопрос
          container.querySelectorAll('.chat-prompt-link').forEach(l => {
            l.classList.remove('selected', 'active');
          });
          link.classList.add('selected', 'active');
          // 3. Отправляем в модель именно вновь сформулированный дополнительный вопрос
          sendProcessChatMessage(qText, true);
        };

        row.appendChild(bullet);
        row.appendChild(link);
        container.appendChild(row);
      });

      // Кнопка принудительной генерации других 3 вопросов
      const refreshRow = document.createElement('div');
      refreshRow.className = 'mt-1';
      const refreshBtn = document.createElement('a');
      refreshBtn.href = '#';
      refreshBtn.className = 'uai-quick-question-refresh';
      refreshBtn.title = 'Сгенерировать другие вопросы';
      refreshBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i><span>Сгенерировать другие вопросы</span>';
      refreshBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        fetchDynamicQuickQuestions(opts);
      };
      refreshRow.appendChild(refreshBtn);
      container.appendChild(refreshRow);
    }

    async function fetchDynamicQuickQuestions(options) {
      const container = document.getElementById('uai-chat-quick-buttons');
      if (container) {
        container.innerHTML = `
          <div class="text-secondary small py-1 px-1 d-inline-flex align-items-center gap-2" style="font-size: 0.95rem;">
            <div class="spinner-border spinner-border-sm text-primary" style="width: 0.95rem; height: 0.95rem;" role="status"></div>
            <span>Генерация трех актуальных вопросов...</span>
          </div>
        `;
      }

      const metaDict = {};
      (options.metadata || []).forEach(m => {
        if (m.label && (m.value !== undefined && m.value !== null)) {
          metaDict[m.label] = m.value;
        }
      });

      const currentModel = modelInput ? modelInput.value.trim() : '';
      const currentProvider = providerSelect ? providerSelect.value : 'gemini';

      try {
        const resp = await safeApiFetch('/api/v1/diagnostics/suggest-questions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            table_type: options.tableType || 'generic',
            panel_id: options.panelId || undefined,
            title: options.title || '',
            subtitle: options.subtitle || '',
            metadata: Object.assign({}, metaDict, options.requestData || {}),
            raw_data: options.rawContent || '',
            model: currentModel || undefined,
            provider: currentProvider || undefined,
            lang: currentLang || undefined,
            use_wikillm: (getAssistantMode() !== 'model_only'),
            force_refresh: (getAssistantMode() === 'model_only')
          })
        }, 15000);

        if (resp && Array.isArray(resp.questions) && resp.questions.length > 0) {
          renderQuickButtons(resp.questions);
        } else {
          renderQuickButtons([]);
        }
      } catch (err) {
        console.debug('Запрос 3 вопросов завершился fallback:', err);
        renderQuickButtons([]);
      }
    }

    let cachedWikiData = null;

    function renderDiagnosticResult(data, isFromWikiLLM = false) {
      if (!aiExplanation) return;
      if (Array.isArray(data.suggested_quick_questions) && data.suggested_quick_questions.length > 0) {
        renderQuickButtons(data.suggested_quick_questions);
      }

      const isVerified = Boolean(isFromWikiLLM || data.is_verified || data.source === 'wikillm');
      const isHeuristic = data.source === 'heuristic';
      const isGemini = data.source === 'gemini';
      const isProcess = (opts.tableType === 'process' || (opts.panelId && opts.panelId.includes('process')));

      const effGeneralSummary = data.general_summary || (cachedWikiData && (cachedWikiData.general_summary || cachedWikiData.summary)) || (isVerified && isProcess && data.summary) || '';
      const effDev = data.developer || (cachedWikiData && cachedWikiData.developer) || 'Неизвестен';
      const effCat = data.category || (cachedWikiData && cachedWikiData.category) || 'Процесс Windows';
      const hasGeneral = Boolean(effGeneralSummary && (data.has_wikillm_general_data || isVerified || cachedWikiData || isProcess));

      let wikillmGeneralCard = '';
      if (hasGeneral && effGeneralSummary) {
        wikillmGeneralCard = `
          <div class="card border-success bg-dark bg-opacity-75 p-2.5 mb-2.5 rounded shadow-sm" id="uai-wikillm-card">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-1 mb-1">
              <span class="badge border border-success text-success p-1 px-2 d-inline-flex align-items-center gap-1.5 small">
                <i class="bi bi-shield-check"></i> База знаний WikiLLM (Справочные данные о программе)
              </span>
              <span class="small text-secondary fw-semibold">${escapeHtml(effDev)} (${escapeHtml(effCat)})</span>
            </div>
            <div class="small text-light">
              <div class="mb-1"><strong class="text-success"><i class="bi bi-info-circle me-1"></i>О программе, назначение и применение:</strong></div>
              <div id="uai-wikillm-text">${formatMarkdownText(effGeneralSummary)}</div>
            </div>
          </div>
        `;
      }

      let sourceBadge = '';
      if (data.source === 'wikillm_resource_analysis') {
        sourceBadge = `<div class="badge border border-info text-info p-1 px-2 mb-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-speedometer2"></i> Анализ текущего потребления и состояния ресурсов (Live Telemetry)</div>`;
      } else if (isVerified) {
        sourceBadge = `<div class="badge border border-success text-success p-1 px-2 mb-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-shield-check"></i> База знаний WikiLLM (L1 Exact Cache)</div>`;
      } else if (isGemini) {
        sourceBadge = `<div class="badge border border-info text-info p-1 px-2 mb-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-stars"></i> AI Экспертный анализ (Web Grounding)</div>`;
      } else {
        sourceBadge = `<div class="badge border border-secondary text-secondary p-1 px-2 mb-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-cpu"></i> Системный экспертный анализ (Телеметрия)</div>`;
      }

      const actionBlock = (isProcess && (data.has_wikillm_general_data || isVerified || cachedWikiData)) ? `
        <div class="p-2 mt-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2" id="uai-approval-container">
          <div class="small text-success">
            <i class="bi bi-check-circle-fill me-1"></i>Справочные данные зафиксированы в WikiLLM. Анализ ресурсов сформирован по актуальной телеметрии.
          </div>
          <div class="d-flex align-items-center gap-1.5">
            <button type="button" class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5" id="btn-uai-reanalyze">
              <i class="bi bi-arrow-clockwise"></i> Обновить срез телеметрии
            </button>
          </div>
        </div>
      ` : (data.has_wikillm_general_data && data.source === 'wikillm_resource_analysis') ? `
        <div class="p-2 mt-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2" id="uai-approval-container">
          <div class="small text-success">
            <i class="bi bi-check-circle-fill me-1"></i>Общие данные зафиксированы в WikiLLM. Анализ ресурсов сформирован по актуальной телеметрии.
          </div>
          <div class="d-flex align-items-center gap-1.5">
            <button type="button" class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5" id="btn-uai-reanalyze">
              <i class="bi bi-arrow-clockwise"></i> Обновить срез телеметрии
            </button>
          </div>
        </div>
      ` : isVerified ? `
        <div class="p-2 mt-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2" id="uai-approval-container">
          <div class="small text-secondary">
            <i class="bi bi-database-check text-success me-1"></i>Справочные данные из локальной базы WikiLLM.
          </div>
          <button type="button" class="btn btn-sm btn-primary d-inline-flex align-items-center gap-1.5" id="btn-uai-improve-ai">
            <i class="bi bi-robot"></i> Запустить полный ИИ-анализ записи
          </button>
        </div>
      ` : `
        <div class="p-2 mt-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2" id="uai-approval-container">
          <div class="small text-secondary">
            <i class="bi bi-patch-question me-1 text-warning"></i>Результат анализа сформирован. Одобрить для базы знаний WikiLLM?
          </div>
          <div class="d-flex align-items-center gap-1.5">
            <button type="button" class="btn btn-sm btn-outline-secondary d-inline-flex align-items-center gap-1.5" id="btn-uai-reanalyze">
              <i class="bi bi-arrow-clockwise"></i> Повторить
            </button>
            <button type="button" class="btn btn-sm btn-outline-success d-inline-flex align-items-center gap-1.5" id="btn-uai-approve-wikillm">
              <i class="bi bi-hand-thumbs-up"></i> Одобрить и сохранить в WikiLLM
            </button>
          </div>
        </div>
      `;

      // Если модель вернула развернутый текстовый отчет без структурированного summary
      const isFullMarkdownReport = !data.summary && (data.raw_markdown || data.raw_response || data.analysis_report || data.answer || (typeof data === 'string'));
      if (isFullMarkdownReport) {
        const fullReportText = typeof data === 'string'
          ? data
          : (data.raw_markdown || data.raw_response || data.analysis_report || data.answer || JSON.stringify(data, null, 2));
        aiExplanation.innerHTML = `
          ${sourceBadge}
          <div class="dialogue-block mb-3 text-light" style="line-height: 1.6;">
            ${parseModelResponse(fullReportText)}
          </div>
          ${actionBlock}
        `;
        attachInteractiveCommandHandlers(aiExplanation);
        return;
      }

      aiExplanation.innerHTML = `
        ${wikillmGeneralCard}
        ${sourceBadge}
        <div class="mb-2"><strong class="text-info"><i class="bi bi-cpu me-1"></i>${(isProcess || data.has_wikillm_general_data || data.source === 'wikillm_resource_analysis') ? 'Анализ текущего потребления ресурсов:' : 'Назначение:'}</strong> ${formatMarkdownText(data.summary)}</div>
        <div class="mb-2"><strong class="text-secondary"><i class="bi bi-building me-1"></i>Разработчик / Категория:</strong> ${escapeHtml(data.developer || 'Неизвестен')} (${escapeHtml(data.category || 'Компонент')})</div>
        <div class="mb-2"><strong class="text-warning"><i class="bi bi-shield-lock me-1"></i>Оценка безопасности:</strong> ${formatMarkdownText(data.security_verdict)}</div>
        <div class="mb-2"><strong class="text-info"><i class="bi bi-speedometer2 me-1"></i>Влияние на ресурсы:</strong> ${formatMarkdownText(data.performance_impact)}</div>
        <div class="p-2 mb-2 rounded uai-recommendation-box">
          <strong class="text-warning"><i class="bi bi-lightbulb me-1"></i>Рекомендация:</strong> ${formatMarkdownText(data.recommendation)}
        </div>
        ${data.action_steps && data.action_steps.length > 0 ? `
          <h6 class="uai-action-steps-title text-uppercase text-muted fw-bold mb-1">Рекомендуемые действия:</h6>
          <div class="ps-1">
            ${data.action_steps.map(s => {
              const sStr = typeof s === 'object' ? JSON.stringify(s) : String(s);
              if (isCommandLineString(sStr)) {
                return `<div class="mb-1.5">${renderInteractiveCommandWidget(sStr, 'powershell')}</div>`;
              }
              return `<li class="ms-3 mb-1">${escapeHtml(sStr)}</li>`;
            }).join('')}
          </div>
        ` : ''}
        ${data.developer_advice ? `
          <div class="uai-dev-advice-wrapper mt-3 pt-2 border-top border-secondary border-opacity-25">
            <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
              <button class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5 py-1 px-3 rounded-pill uai-btn-toggle-dev" 
                      type="button" data-bs-toggle="collapse" data-bs-target="#uai-dev-advice-collapse" aria-expanded="true">
                <i class="bi bi-code-slash"></i>
                <strong class="small">Советы разработчику &amp; Автоматизация</strong>
                <i class="bi bi-chevron-down ms-1"></i>
              </button>
              <div class="d-flex align-items-center gap-1.5">
                <span class="badge border border-info text-info small" style="font-size: 0.72rem;">
                  <i class="bi bi-cpu me-1"></i>API &amp; Scripting
                </span>
              </div>
            </div>
            <div class="collapse show" id="uai-dev-advice-collapse">
              <div class="p-3 rounded uai-dev-advice-box">
                ${renderDevAdviceContent(data.developer_advice)}
              </div>
            </div>
          </div>
        ` : ''}
        ${actionBlock}
      `;

      attachInteractiveCommandHandlers(aiExplanation);

      // Синхронизация спойлера "Советы разработчику" в нижней панели
      const devToggleBtn = document.getElementById('btn-toggle-dev-advice');
      const devContentEl = document.getElementById('uai-modal-dev-content');
      if (data.developer_advice) {
        if (devToggleBtn) devToggleBtn.style.display = 'inline-block';
        if (devContentEl) {
          devContentEl.innerHTML = renderDevAdviceContent(data.developer_advice);
          attachInteractiveCommandHandlers(devContentEl);
        }
        const saveInstBtn = document.getElementById('btn-uai-dev-save-instrument') || document.getElementById('btn-uai-dev-save-kb');
        if (saveInstBtn) {
          saveInstBtn.onclick = () => extractAndSaveDeveloperAdviceInstruments(data, opts, saveInstBtn);
        }
      } else {
        if (devToggleBtn) devToggleBtn.style.display = 'none';
        if (devContentEl) devContentEl.innerHTML = '';
      }

      const improveBtn = document.getElementById('btn-uai-improve-ai');
      if (improveBtn) {
        improveBtn.onclick = () => executeDiagnostics(true);
      }

      const reanalyzeBtn = document.getElementById('btn-uai-reanalyze');
      if (reanalyzeBtn) {
        reanalyzeBtn.onclick = () => executeDiagnostics(true);
      }

      const approveBtn = document.getElementById('btn-uai-approve-wikillm');
      if (approveBtn) {
        approveBtn.onclick = () => approveInWikiLLM(data, opts);
      }

      if (refreshBtn) {
        refreshBtn.style.display = 'inline-flex';
      }
    }

    // Проверка наличия знаний в WikiLLM перед запросом к LLM
    function renderDiagnosticResultWithPlaceholders(data) {
      if (!aiExplanation) return;
      if (Array.isArray(data.suggested_quick_questions) && data.suggested_quick_questions.length > 0) {
        renderQuickButtons(data.suggested_quick_questions);
      }

      cachedWikiData = data;
      const generalSummary = data.general_summary || data.summary || '';
      const devText = data.developer || 'Неизвестен';
      const catText = data.category || 'Процесс Windows';

      const wikillmGeneralCard = `
        <div class="card border-success bg-dark bg-opacity-75 p-2.5 mb-2.5 rounded shadow-sm" id="uai-wikillm-card">
          <div class="d-flex align-items-center justify-content-between flex-wrap gap-1 mb-1">
            <span class="badge border border-success text-success p-1 px-2 d-inline-flex align-items-center gap-1.5 small">
              <i class="bi bi-shield-check"></i> База знаний WikiLLM (Справочные данные о программе)
            </span>
            <span class="small text-secondary fw-semibold">${escapeHtml(devText)} (${escapeHtml(catText)})</span>
          </div>
          <div class="small text-light">
            <div class="mb-1"><strong class="text-success"><i class="bi bi-info-circle me-1"></i>О программе, назначение и применение:</strong></div>
            <div id="uai-wikillm-text">${formatMarkdownText(generalSummary)}</div>
          </div>
        </div>
      `;

      const sourceBadge = `<div class="badge border border-info text-info p-1 px-2 mb-2 d-inline-flex align-items-center gap-1.5"><i class="bi bi-speedometer2"></i> Анализ текущего потребления и состояния ресурсов (Live Telemetry)</div>`;

      const spinnerPlaceholder = (text) => `
        <div class="d-inline-flex align-items-center gap-2 text-info py-0.5">
          <div class="spinner-border spinner-border-sm text-info" style="width: 0.85rem; height: 0.85rem;" role="status"></div>
          <span class="text-secondary fst-italic small">${text}</span>
        </div>
      `;

      aiExplanation.innerHTML = `
        ${wikillmGeneralCard}
        ${sourceBadge}
        <div class="mb-2">
          <strong class="text-info"><i class="bi bi-cpu me-1"></i>Анализ текущего потребления ресурсов:</strong>
          <div class="mt-0.5" id="uai-dyn-summary">${spinnerPlaceholder('Выполняется экспресс-анализ текущего потребления параметров телеметрии...')}</div>
        </div>
        <div class="mb-2">
          <strong class="text-secondary"><i class="bi bi-building me-1"></i>Разработчик / Категория:</strong> ${escapeHtml(devText)} (${escapeHtml(catText)})
        </div>
        <div class="mb-2">
          <strong class="text-warning"><i class="bi bi-shield-lock me-1"></i>Оценка безопасности текущей сессии:</strong>
          <div class="mt-0.5" id="uai-dyn-security">${spinnerPlaceholder('Проверка прав, путей запуска и активных сетевых сокетов...')}</div>
        </div>
        <div class="mb-2">
          <strong class="text-info"><i class="bi bi-speedometer2 me-1"></i>Влияние на ресурсы:</strong>
          <div class="mt-0.5" id="uai-dyn-performance">${spinnerPlaceholder('Срез по подсистемам: ЦП, ОЗУ, Дисковый ввод-вывод, Сокеты...')}</div>
        </div>
        <div class="p-2 mb-2 rounded uai-recommendation-box">
          <strong class="text-warning"><i class="bi bi-lightbulb me-1"></i>Рекомендация:</strong>
          <div class="ms-1 d-inline-block" id="uai-dyn-recommendation">${spinnerPlaceholder('Формирование вердикта администратору...')}</div>
        </div>
        <div class="mb-2">
          <h6 class="uai-action-steps-title text-uppercase text-muted fw-bold mb-1">Рекомендуемые действия:</h6>
          <div class="ps-1" id="uai-dyn-actions">${spinnerPlaceholder('Определение практических шагов оптимизации...')}</div>
        </div>
        ${data.developer_advice ? `
          <div class="uai-dev-advice-wrapper mt-3 pt-2 border-top border-secondary border-opacity-25">
            <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
              <button class="btn btn-sm btn-outline-info d-inline-flex align-items-center gap-1.5 py-1 px-3 rounded-pill uai-btn-toggle-dev" 
                      type="button" data-bs-toggle="collapse" data-bs-target="#uai-dev-advice-collapse" aria-expanded="true">
                <i class="bi bi-code-slash"></i>
                <strong class="small">Советы разработчику &amp; Автоматизация</strong>
                <i class="bi bi-chevron-down ms-1"></i>
              </button>
              <div class="d-flex align-items-center gap-1.5">
                <span class="badge border border-info text-info small" style="font-size: 0.72rem;">
                  <i class="bi bi-cpu me-1"></i>API &amp; Scripting
                </span>
              </div>
            </div>
            <div class="collapse show" id="uai-dev-advice-collapse">
              <div class="p-3 rounded uai-dev-advice-box">
                ${renderDevAdviceContent(data.developer_advice)}
              </div>
            </div>
          </div>
        ` : ''}
        <div class="p-2 mt-2 rounded d-flex align-items-center justify-content-between flex-wrap gap-2 text-secondary small" id="uai-approval-container">
          <div><i class="bi bi-hourglass-split me-1 text-info"></i>Общие данные загружены из WikiLLM. Ожидается ответ модели по текущему инстансу...</div>
        </div>
      `;
    }

    async function checkWikiLLMKnowledge() {
      if (!aiExplanation) return;
      if (getAssistantMode() === 'model_only') {
        // В режиме «только модель» сразу выполняем прямой запрос к модели
        executeDiagnostics(true, false);
        return;
      }
      aiExplanation.innerHTML = `
        <div class="d-flex align-items-center gap-2 py-2 text-secondary">
          <div class="spinner-border spinner-border-sm" role="status"></div>
          <span>Проверка локальной базы знаний WikiLLM...</span>
        </div>
      `;

      const metaDict = {};
      (opts.metadata || []).forEach(m => {
        if (m.label && (m.value !== undefined && m.value !== null)) {
          metaDict[m.label] = m.value;
        }
      });

      try {
        const data = await safeApiFetch('/api/v1/diagnostics/explain', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            table_type: opts.tableType,
            panel_id: opts.panelId,
            system_instruction: systemTextarea ? systemTextarea.value : '',
            title: opts.title,
            subtitle: opts.subtitle,
            metadata: Object.assign({}, metaDict, opts.requestData || {}),
            raw_data: opts.rawContent || '',
            cache_only: true,
            web_search: false
          })
        }, 4000);

        if (data && (data.is_verified || data.source === 'wikillm') && (data.general_summary || data.summary)) {
          cachedWikiData = data;
          const isProcess = (opts.tableType === 'process' || (opts.panelId && opts.panelId.includes('process')));
          if (isProcess) {
            renderDiagnosticResultWithPlaceholders(data);
            executeDiagnostics(true, false, true);
          } else {
            renderDiagnosticResult(data, true);
          }
        } else {
          const autoEnrichToggle = document.getElementById('toggle-auto-enrich-on-miss');
          if (autoEnrichToggle && autoEnrichToggle.checked) {
            executeDiagnostics(false, true);
          } else {
            renderPromptCallout();
          }
        }
      } catch (err) {
        const autoEnrichToggle = document.getElementById('toggle-auto-enrich-on-miss');
        if (autoEnrichToggle && autoEnrichToggle.checked) {
          executeDiagnostics(false, true);
        } else {
          renderPromptCallout();
        }
      }
    }

    checkWikiLLMKnowledge();
    fetchDynamicQuickQuestions(opts);

    // Привязка кнопки настройки шаблона промпта
    const editPromptBtn = document.getElementById('btn-uai-modal-edit-prompt');
    if (editPromptBtn) {
      editPromptBtn.onclick = () => openPromptEditor(opts.tableType, opts.panelId);
    }

    // Выполнение диагностического запроса к AI с передачей модели, провайдера и системной инструкции
    async function executeDiagnostics(forceRefresh = false, autoSave = false, isHybridProcess = false) {
      const aiExplanation = document.getElementById('uai-modal-ai-explanation');
      if (!aiExplanation) return;

      const currentSysInstruction = systemTextarea ? systemTextarea.value.trim() : '';
      const currentModel = modelInput ? modelInput.value.trim() : '';
      const currentProvider = providerSelect ? providerSelect.value : 'gemini';

      if (!isHybridProcess) {
        aiExplanation.innerHTML = `
          <div class="d-flex align-items-center gap-2 py-2 text-info">
            <div class="spinner-border spinner-border-sm" role="status"></div>
            <span>Выполняется ${forceRefresh ? 'углубленный' : 'экспертный'} AI-анализ для «${escapeHtml(opts.title)}» (терпеливое ожидание ответа модели)...</span>
          </div>
        `;
      }

      const metaDict = {};
      (opts.metadata || []).forEach(m => {
        if (m.label && (m.value !== undefined && m.value !== null)) {
          metaDict[m.label] = m.value;
        }
      });

      try {
        // Запрос к модели без клиентского таймаута: терпеливо ждем ответа, какой бы он ни был
        const data = await safeApiFetch('/api/v1/diagnostics/explain', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            table_type: opts.tableType,
            panel_id: opts.panelId,
            lang: currentLang,
            system_instruction: currentSysInstruction || undefined,
            model: currentModel || undefined,
            provider: currentProvider || undefined,
            title: opts.title,
            subtitle: opts.subtitle,
            prompt: opts.prompt || undefined,
            question: opts.question || undefined,
            metadata: Object.assign({}, metaDict, opts.requestData || {}),
            raw_data: opts.rawContent || '',
            web_search: true,
            force_refresh: (getAssistantMode() === 'model_only') ? true : Boolean(forceRefresh),
            use_wikillm: (getAssistantMode() !== 'model_only')
          })
        }, 0);

        if (!data || data.error || !data.summary) {
          throw {
            message: data?.error?.message || 'Модель не вернула диагностическое заключение',
            errorData: data
          };
        }

        if (cachedWikiData) {
          if (!data.general_summary) {
            data.general_summary = cachedWikiData.general_summary || cachedWikiData.summary;
          }
          if (!data.developer || data.developer === 'Неизвестен') data.developer = cachedWikiData.developer;
          if (!data.category || data.category === 'Диагностика') data.category = cachedWikiData.category;
          data.has_wikillm_general_data = true;
        }

        renderDiagnosticResult(data, false);
        try {
          window.dispatchEvent(new CustomEvent('ai-modal:explained', {
            detail: {
              title: opts.title,
              summary: data.summary,
              source: data.source || 'gemini',
              panelId: opts.panelId,
              data: data
            }
          }));
        } catch (_) {}
        if (getAssistantMode() !== 'model_only' && autoSave && data && data.summary && !data.error && data.source !== 'not_found' && data.source !== 'heuristic' && !isModelErrorText(data.summary)) {
          approveInWikiLLM(data, opts);
        }
      } catch (err) {
        // При ошибке: в WikiLLM НЕ записываем, выводим сообщение с расшифровкой и сырым JSON ответа
        const errInfo = decipherModelError(err);
        if (isHybridProcess) {
          const approvalContainer = document.getElementById('uai-approval-container');
          if (approvalContainer) {
            approvalContainer.className = 'card border-danger bg-dark bg-opacity-75 p-2.5 mt-2 text-light';
            approvalContainer.innerHTML = `
              <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                <div class="small text-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>Сбой анализа телеметрии: ${escapeHtml(errInfo.friendlyReason || err.message || 'Ошибка модели')}</div>
                <button type="button" class="btn btn-xs btn-outline-danger" id="btn-uai-modal-retry"><i class="bi bi-arrow-clockwise"></i> Повторить</button>
              </div>
            `;
            const retryBtn = document.getElementById('btn-uai-modal-retry');
            if (retryBtn) retryBtn.onclick = () => executeDiagnostics(true, false, true);
            return;
          }
        }
        aiExplanation.innerHTML = `
          <div class="card border-danger bg-dark bg-opacity-75 p-3 mb-2 text-light">
            <div class="d-flex align-items-center justify-content-between mb-2 flex-wrap gap-2">
              <div class="d-flex align-items-center gap-2 text-danger fw-bold">
                <i class="bi bi-exclamation-triangle-fill fs-5"></i>
                <span>Ошибка получения AI-анализа</span>
              </div>
              <button type="button" class="btn btn-sm btn-outline-danger d-inline-flex align-items-center gap-1" id="btn-uai-modal-retry">
                <i class="bi bi-arrow-clockwise"></i> Повторить
              </button>
            </div>
            ${errInfo.friendlyReason ? `
              <div class="alert alert-danger py-2 px-3 mb-2 small text-danger-emphasis">
                <strong><i class="bi bi-info-circle me-1"></i>Суть ошибки:</strong> ${escapeHtml(errInfo.friendlyReason)}
              </div>
            ` : ''}
            <div class="small text-secondary mb-1">
              <strong>Сообщение:</strong> <span class="text-light">${escapeHtml(errInfo.message)}</span>
            </div>
            ${errInfo.jsonString ? `
              <div class="mt-2">
                <div class="small text-secondary mb-1"><strong>Ответ модели / Детали ошибки (JSON):</strong></div>
                <pre class="bg-black p-2 rounded text-danger small mb-0 border border-secondary border-opacity-50" style="max-height: 180px; overflow: auto; font-size: 0.75rem; white-space: pre-wrap; word-break: break-all;"><code>${escapeHtml(errInfo.jsonString)}</code></pre>
              </div>
            ` : ''}
          </div>
        `;

        const retryBtn = document.getElementById('btn-uai-modal-retry');
        if (retryBtn) {
          retryBtn.onclick = () => executeDiagnostics(forceRefresh, autoSave);
        }

        const refreshBtn = document.getElementById('btn-uai-modal-refresh');
        if (refreshBtn) {
          refreshBtn.style.display = 'inline-flex';
        }
      }
    }

    // Извлечение и сохранение инструментов агента в ai_instruments.db
    async function extractAndSaveDeveloperAdviceInstruments(aiData, options, buttonEl) {
      const advice = aiData ? aiData.developer_advice : null;
      if (!advice) return;
      const origHtml = buttonEl ? buttonEl.innerHTML : '';
      if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Извлечение...';
      }
      try {
        const targetEntity = options.tableType && options.title ? `${options.tableType}:${options.title}` : (options.title || '');
        const resp = await safeApiFetch('/api/v1/ai-instruments/extract-from-advice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: typeof advice === 'object' ? JSON.stringify(advice) : String(advice),
            target_entity: targetEntity,
            title_prefix: `Инструмент: ${options.title || 'Система'}`
          })
        }, 8000);

        if (resp && resp.status === 'ok') {
          if (buttonEl) {
            buttonEl.className = 'btn btn-xs btn-success py-0 px-2 rounded';
            buttonEl.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>Сохранено инструментов: ${resp.extracted_count} (ai_instruments.db)`;
          }
          if (window.showToast) {
            window.showToast(`Сохранено ${resp.extracted_count} инструментов в ai_instruments.db`, 'success');
          }
        } else {
          throw new Error(resp?.detail || 'Не удалось извлечь инструменты');
        }
      } catch (err) {
        if (buttonEl) {
          buttonEl.disabled = false;
          buttonEl.innerHTML = origHtml;
        }
        alert(`Ошибка сохранения в ai_instruments.db: ${err.message}`);
      }
    }

    // Сохранение и верификация знаний в WikiLLM
    async function approveInWikiLLM(aiData, options) {
      if (!aiData || aiData.error || !aiData.summary || aiData.source === 'not_found' || aiData.source === 'heuristic' || isModelErrorText(aiData.summary)) {
        console.warn('[AIModalDialog] Запись в WikiLLM отменена: данные некорректны или содержат ошибку');
        return;
      }
      const approveBtn = document.getElementById('btn-uai-approve-wikillm');
      const container = document.getElementById('uai-approval-container');
      if (approveBtn) approveBtn.disabled = true;

      try {
        const isProcApprove = (options.tableType === 'process' || (options.panelId && options.panelId.includes('process')));
        let cleanTitle = options.title || '';
        let cleanSummary = aiData.general_summary || aiData.summary || '';
        let cleanPerf = aiData.performance_impact || '';
        if (isProcApprove) {
          cleanTitle = cleanTitle.replace(/[\s\[\(]+PID[:\s]*\d+[\s\]\)]*/gi, '').trim();
          if (!cleanTitle) cleanTitle = (options.title || '').split(' ')[0].trim();
          cleanPerf = 'Штатный профиль приложения (из базы знаний WikiLLM)';
        }

        const payload = {
          canonical_key: aiData.canonical_key || undefined,
          table_type: options.tableType || 'generic',
          title: cleanTitle,
          subtitle: options.subtitle || '',
          summary: cleanSummary,
          general_summary: cleanSummary,
          category: aiData.category || 'system',
          security_verdict: aiData.security_verdict || '',
          performance_impact: cleanPerf,
          recommendation: aiData.recommendation || '',
          action_steps: aiData.action_steps || [],
          developer_advice: aiData.developer_advice || '',
          possible_causes: [],
          tags: [options.tableType || 'generic', options.panelId || 'panel_data', 'user_approved'],
          model_name: (modelInput ? modelInput.value.trim() : '') || 'gemini'
        };

        let respData;
        try {
          respData = await safeApiFetch('/api/v1/diagnostics/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          }, 6000);
        } catch (_) {
          respData = await safeApiFetch('/api/windows/wikillm/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          }, 6000);
        }

        if (respData && respData.success) {
          if (container) {
            container.className = 'p-2 mt-2 rounded uai-verified-box d-flex align-items-center justify-content-between flex-wrap gap-2';
            container.innerHTML = `
              <div class="small text-success fw-bold">
                <i class="bi bi-check-circle-fill me-1"></i>Знание верифицировано и сохранено в WikiLLM (${escapeHtml(respData.canonical_key)})
              </div>
              <span class="badge border border-success text-success">L1 Exact Cache O(1)</span>
            `;
          }
          if (window.showToast) {
            window.showToast(`Знание «${options.title}» зафиксировано в WikiLLM`, 'success');
          }
        } else {
          throw new Error(respData?.detail || 'Не удалось сохранить знание');
        }
      } catch (err) {
        if (approveBtn) approveBtn.disabled = false;
        alert(`Ошибка сохранения в WikiLLM: ${err.message}`);
      }
    }

    if (opts.autoRun === true) {
      executeDiagnostics();
    }

    // Интерактивный диалоговый чат по процессу (01_FRONTEND.md)
    const chatContainer = document.getElementById('uai-chat-messages-container');
    const chatInput = document.getElementById('uai-chat-input');
    const chatSendBtn = document.getElementById('uai-chat-send-btn');
    const quickButtons = document.getElementById('uai-chat-quick-buttons');

    async function sendProcessChatMessage(question, forceRefresh = false) {
      const qText = (question || (chatInput ? chatInput.value : '') || '').trim();
      if (!qText) return;
      if (chatInput) chatInput.value = qText;

      // Контейнер диалога в секции интерактивного чата (вне aiExplanation, чтобы не затирался ответом основного анализа)
      let threadContainer = document.getElementById('uai-qa-conversation-thread');
      if (!threadContainer) {
        const chatSection = document.getElementById('uai-modal-chat-section');
        if (chatSection) {
          threadContainer = document.createElement('div');
          threadContainer.id = 'uai-qa-conversation-thread';
          threadContainer.className = 'mt-2';
          chatSection.appendChild(threadContainer);
        } else {
          const explanationEl = document.getElementById('uai-modal-ai-explanation');
          threadContainer = document.createElement('div');
          threadContainer.id = 'uai-qa-conversation-thread';
          threadContainer.className = 'mt-3 pt-2 border-top border-info border-opacity-25';
          if (explanationEl && explanationEl.parentNode) {
            explanationEl.parentNode.insertBefore(threadContainer, explanationEl.nextSibling);
          }
        }
      }
      if (!threadContainer) return;

      // Одноразовый вопрос: очищаем предыдущую карточку перед показом нового ответа
      threadContainer.innerHTML = '';

      // Карточка диалога Q&A в основном окне
      const qaCard = document.createElement('div');
      qaCard.className = 'card uai-qa-card rounded p-3 mb-3 shadow-sm';
      qaCard.innerHTML = `
        <div class="d-flex align-items-center justify-content-between mb-2 flex-wrap gap-2">
          <h6 class="fw-semibold text-body mb-0 d-flex align-items-center gap-2">
            <span class="text-info fs-6">💬</span>
            <span>${escapeHtml(qText)}</span>
          </h6>
          <span class="uai-qa-status-badge" style="display: none;"></span>
        </div>
        <div class="chat-content text-body mt-2" style="line-height: 1.55; white-space: pre-wrap; word-break: break-word;">
          <div class="d-flex align-items-center gap-2 text-info py-2 uai-qa-loading">
            <div class="spinner-border spinner-border-sm text-info" role="status" style="width: 0.9rem; height: 0.9rem;"></div>
            <span>Ожидание ответа...</span>
          </div>
        </div>
        <div class="uai-qa-footer mt-2 pt-2 border-top" style="display: none;"></div>
      `;
      threadContainer.appendChild(qaCard);
      qaCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      const contentEl = qaCard.querySelector('.chat-content');
      const statusBadge = qaCard.querySelector('.uai-qa-status-badge');
      const footerEl = qaCard.querySelector('.uai-qa-footer');

      try {
        const currentSysInstruction = systemTextarea ? systemTextarea.value.trim() : '';
        const payload = {
          table_type: opts.tableType || 'generic',
          panel_id: opts.panelId || undefined,
          canonical_key: opts.canonical_key || undefined,
          name: opts.title,
          path: opts.subtitle,
          title: opts.title,
          subtitle: opts.subtitle,
          prompt: qText,
          question: qText,
          stream: true,
          force_refresh: (getAssistantMode() === 'model_only') ? true : Boolean(forceRefresh),
          use_wikillm: (getAssistantMode() !== 'model_only'),
          system_instruction: currentSysInstruction || undefined,
          model: (modelInput ? modelInput.value.trim() : '') || undefined,
          provider: (providerSelect ? providerSelect.value : 'gemini'),
          metadata: Object.assign({}, metaDict, opts.requestData || {}),
          raw_data: opts.rawContent || '',
          enrich_wikillm: false
        };

        let res = null;
        try {
          res = await window.fetch('/api/v1/diagnostics/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } catch (_) {
          res = await window.fetch('/api/v1/chat/software-explain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }

        if (!res.ok) {
          let errDetail = `HTTP ${res.status}`;
          let errJson = null;
          try {
            errJson = await res.json();
            if (errJson && errJson.detail) {
              errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
            } else if (errJson && errJson.error) {
              errDetail = typeof errJson.error === 'string' ? errJson.error : JSON.stringify(errJson.error);
            }
          } catch (_) {}
          throw { message: errDetail, errorData: errJson || { status: res.status, statusText: res.statusText } };
        }

        let fullAnswerText = '';
        let wasEnriched = false;
        let responseSource = 'gemini';

        if (res.headers.get('content-type')?.includes('text/event-stream')) {
          contentEl.innerHTML = '';
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let streamBuf = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            streamBuf += decoder.decode(value, { stream: true });
            const lines = streamBuf.split('\n\n');
            streamBuf = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const raw = line.substring(6).trim();
                if (raw === '[DONE]') break;
                try {
                  const chunkObj = JSON.parse(raw);
                  if (chunkObj.error) {
                    throw chunkObj.error;
                  }
                  if (chunkObj.chunk) {
                    if (isModelErrorText(chunkObj.chunk)) {
                      throw { message: chunkObj.chunk, errorData: chunkObj };
                    }
                    fullAnswerText += chunkObj.chunk;
                    renderLiveStreamContent(contentEl, fullAnswerText);
                    qaCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                  }
                  if (chunkObj.status === 'done') {
                    if (isModelErrorText(fullAnswerText) || isModelErrorText(chunkObj.dialogue)) {
                      throw { message: fullAnswerText || chunkObj.dialogue, errorData: chunkObj };
                    }
                    wasEnriched = Boolean(chunkObj.enriched);
                    if (chunkObj.source) responseSource = chunkObj.source;
                    if (chunkObj.dialogue) {
                      fullAnswerText = chunkObj.dialogue;
                    }
                  }
                } catch (parseErr) {
                  if (parseErr && (parseErr.message || parseErr.error)) {
                    throw parseErr;
                  }
                  if (isModelErrorText(raw)) {
                    throw { message: raw };
                  }
                  fullAnswerText += raw;
                  contentEl.innerHTML += escapeHtml(raw).replace(/\n/g, '<br>');
                }
              }
            }
          }

          // При завершении стриминга форматируем накопленный JSON в читаемый диалог
          if (fullAnswerText) {
            if (isModelErrorText(fullAnswerText)) {
              throw { message: fullAnswerText };
            }
            contentEl.innerHTML = convertJsonToDialogue(fullAnswerText);
            contentEl.style.whiteSpace = 'normal';
          }
        } else {
          const respData = await res.json();
          if (respData.error) {
            throw respData.error;
          }
          const rawAnswer = respData.dialogue || respData.answer || respData.summary || respData.recommendation || respData;
          fullAnswerText = typeof rawAnswer === 'object' ? JSON.stringify(rawAnswer) : String(rawAnswer);
          if (isModelErrorText(fullAnswerText)) {
            throw { message: fullAnswerText, errorData: respData };
          }
          wasEnriched = Boolean(respData.enriched);
          if (respData.source) responseSource = respData.source;
          contentEl.innerHTML = convertJsonToDialogue(rawAnswer);
          contentEl.style.whiteSpace = 'normal';
        }

        // Активируем обработчики команд PowerShell и карточек готовых инструментов
        attachInteractiveCommandHandlers(contentEl);

        if (statusBadge) {
          statusBadge.className = 'badge border border-info text-info small d-inline-flex align-items-center gap-1';
          statusBadge.innerHTML = '<i class="bi bi-robot me-1"></i>Ответ модели';
          statusBadge.style.display = 'inline-flex';
        }

        // Помечаем вопрос как отвеченный, чтобы он стал неактивным и больше не был доступен для выбора
        markQuestionInUIAsAnswered(qText);
      } catch (chatErr) {
        // При ошибке: в WikiLLM НЕ записываем, выводим сообщение с расшифровкой и сырым JSON ответа
        const chatErrInfo = decipherModelError(chatErr);
        if (statusBadge) {
          statusBadge.className = 'badge border border-danger text-danger small d-inline-flex align-items-center gap-1';
          statusBadge.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Сбой ответа';
          statusBadge.style.display = 'inline-flex';
        }
        contentEl.innerHTML = `
          <div class="alert alert-danger py-2 px-3 mb-2 small text-danger-emphasis">
            <strong><i class="bi bi-exclamation-triangle-fill me-1"></i>Ошибка ответа модели:</strong> ${escapeHtml(chatErrInfo.message)}
            ${chatErrInfo.friendlyReason ? `<div class="mt-1">${escapeHtml(chatErrInfo.friendlyReason)}</div>` : ''}
          </div>
          ${chatErrInfo.jsonString ? `
            <div class="mt-1">
              <div class="small text-secondary mb-1"><strong>Ответ модели / Детали ошибки (JSON):</strong></div>
              <pre class="bg-black p-2 rounded text-danger small mb-0 border border-secondary border-opacity-50" style="max-height: 140px; overflow: auto; font-size: 0.75rem; white-space: pre-wrap; word-break: break-all;"><code>${escapeHtml(chatErrInfo.jsonString)}</code></pre>
            </div>
          ` : ''}
          <div class="mt-2">
            <button type="button" class="btn btn-sm btn-outline-danger d-inline-flex align-items-center gap-1 btn-retry-chat">
              <i class="bi bi-arrow-clockwise"></i> Повторить вопрос
            </button>
          </div>
        `;
        const retryBtn = contentEl.querySelector('.btn-retry-chat');
        if (retryBtn) {
          retryBtn.onclick = () => {
            qaCard.remove();
            sendProcessChatMessage(qText);
          };
        }
      }
    }

    if (chatSendBtn) {
      chatSendBtn.onclick = () => sendProcessChatMessage();
    }
    if (chatInput) {
      chatInput.onkeydown = (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          sendProcessChatMessage();
        }
      };
    }
    if (quickButtons) {
      quickButtons.querySelectorAll('button[data-question]').forEach(b => {
        b.onclick = () => {
          const qVal = b.getAttribute('data-question');
          if (chatInput) {
            chatInput.value = qVal;
            chatInput.focus();
          }
          opts.prompt = qVal;
          opts.question = qVal;
          sendProcessChatMessage(qVal, true);
        };
      });
    }

    // Custom Footer Actions
    const actionsContainer = document.getElementById('uai-modal-custom-actions');
    if (actionsContainer) {
      actionsContainer.innerHTML = '';
      (opts.actions || []).forEach(act => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `btn btn-sm ${act.class || 'btn-outline-secondary'}`;
        btn.innerHTML = `${act.icon ? `<i class="bi ${act.icon} me-1"></i>` : ''}${escapeHtml(act.label)}`;
        btn.onclick = () => act.onClick && act.onClick(opts);
        actionsContainer.appendChild(btn);
      });
    }

    // Открытие окна через Bootstrap Modal API
    if (window.bootstrap && window.bootstrap.Modal) {
      const bsModal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      bsModal.show();
    }
  }

  /**
   * Открывает диалог редактирования расширенного шаблона промпта для выбранного типа таблицы или панели.
   * @param {string} tableType Тип таблицы / сущности
   * @param {string} [panelId] Опциональный идентификатор панели
   */
  async function openPromptEditor(tableType, panelId) {
    const promptModalEl = ensurePromptModalElement();
    const typeSelect = document.getElementById('uai-prompt-type-select');
    const nameInput = document.getElementById('uai-prompt-name-input');
    const systemInput = document.getElementById('uai-prompt-system-input');
    const templateInput = document.getElementById('uai-prompt-template-input');
    const statusMsg = document.getElementById('uai-prompt-status-msg');
    const saveBtn = document.getElementById('btn-uai-prompt-save');
    const resetBtn = document.getElementById('btn-uai-prompt-reset');

    const targetType = normalizeTableType(tableType || 'generic');
    const currentLang = getCurrentLang();

    // Динамическая загрузка полного списка шаблонов промптов с бэкенда
    try {
      const templatesList = await safeApiFetch(`/api/v1/diagnostics/prompts?lang=${encodeURIComponent(currentLang)}`, {}, 15000);
      if (Array.isArray(templatesList) && templatesList.length > 0 && typeSelect) {
        typeSelect.innerHTML = templatesList.map(t => {
          const isCustom = t.is_customized ? ' ✏️' : '';
          return `<option value="${escapeHtml(t.table_type)}">${escapeHtml(t.table_type)} (${escapeHtml(t.name || t.table_type)})${isCustom}</option>`;
        }).join('');
      }
    } catch (e) {
      console.warn('[AIModalDialog] Failed to fetch prompts list dynamically:', e);
    }

    if (typeSelect) {
      // Если передана конкретная панель, добавляем опцию для индивидуального промпта панели
      if (panelId && panelId.trim()) {
        const cleanPanel = panelId.trim();
        let hasPanelOpt = false;
        for (let i = 0; i < typeSelect.options.length; i++) {
          if (typeSelect.options[i].value === cleanPanel) {
            hasPanelOpt = true;
            break;
          }
        }
        if (!hasPanelOpt) {
          const pOpt = document.createElement('option');
          pOpt.value = cleanPanel;
          pOpt.textContent = `Панель #${cleanPanel} (Индивидуальный)`;
          typeSelect.insertBefore(pOpt, typeSelect.firstChild);
        }
        typeSelect.value = cleanPanel;
      } else {
        let found = false;
        for (let i = 0; i < typeSelect.options.length; i++) {
          if (typeSelect.options[i].value === targetType) {
            typeSelect.selectedIndex = i;
            found = true;
            break;
          }
        }
        if (!found) {
          const opt = document.createElement('option');
          opt.value = targetType;
          opt.textContent = `${targetType} (Пользовательский шаблон)`;
          typeSelect.appendChild(opt);
          typeSelect.value = targetType;
        }
      }
    }

    async function loadTemplate(tType) {
      const isPanel = tType && (tType.startsWith('panel-') || tType === panelId);
      const query = isPanel
        ? `?panel_id=${encodeURIComponent(tType)}&lang=${encodeURIComponent(currentLang)}`
        : `?lang=${encodeURIComponent(currentLang)}`;
      const reqType = isPanel ? normalizeTableType(tableType || 'generic') : normalizeTableType(tType);

      if (statusMsg) statusMsg.style.display = 'none';
      try {
        const data = await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(reqType)}${query}`, {}, 15000);
        if (data) {
          if (nameInput) nameInput.value = data.name || '';
          if (systemInput) systemInput.value = data.system_instruction || '';
          if (templateInput) templateInput.value = data.prompt_template || '';
          if (statusMsg && data.is_customized) {
            statusMsg.className = 'small mt-2 text-warning';
            statusMsg.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Загружен пользовательский шаблон (отличается от системного).';
            statusMsg.style.display = 'block';
          }
        }
      } catch (e) {
        console.error('Ошибка загрузки шаблона промпта:', e);
      }
    }

    if (typeSelect) {
      typeSelect.onchange = () => loadTemplate(typeSelect.value);
    }

    if (saveBtn) {
      saveBtn.onclick = async () => {
        const selectedValue = typeSelect ? typeSelect.value : targetType;
        const isPanel = selectedValue && (selectedValue.startsWith('panel-') || selectedValue === panelId);
        const reqType = isPanel ? normalizeTableType(tableType || 'generic') : normalizeTableType(selectedValue);
        const query = isPanel ? `?panel_id=${encodeURIComponent(selectedValue)}` : '';

        try {
          await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(reqType)}${query}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              table_type: selectedValue,
              name: nameInput ? nameInput.value : '',
              system_instruction: systemInput ? systemInput.value : '',
              prompt_template: templateInput ? templateInput.value : ''
            })
          }, 6000);
          if (statusMsg) {
            statusMsg.className = 'small mt-2 text-success';
            statusMsg.innerHTML = '<i class="bi bi-check-circle me-1"></i>Шаблон промпта успешно сохранен!';
            statusMsg.style.display = 'block';
            setTimeout(() => { if (statusMsg) statusMsg.style.display = 'none'; }, 3000);
          }
        } catch (err) {
          if (statusMsg) {
            statusMsg.className = 'small mt-2 text-danger';
            statusMsg.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>Ошибка сохранения: ${escapeHtml(err.message)}`;
            statusMsg.style.display = 'block';
          }
        }
      };
    }

    if (resetBtn) {
      resetBtn.onclick = async () => {
        const currentType = normalizeTableType(typeSelect ? typeSelect.value : 'generic');
        if (!confirm(`Сбросить шаблон для «${currentType}» к значению по умолчанию?`)) return;
        try {
          const data = await safeApiFetch(`/api/v1/diagnostics/prompts/${encodeURIComponent(currentType)}/reset`, {
            method: 'POST'
          }, 6000);
          if (data) {
            if (nameInput) nameInput.value = data.name || '';
            if (systemInput) systemInput.value = data.system_instruction || '';
            if (templateInput) templateInput.value = data.prompt_template || '';
          }
          if (statusMsg) {
            statusMsg.className = 'small mt-2 text-info';
            statusMsg.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Шаблон сброшен к системному по умолчанию.';
            statusMsg.style.display = 'block';
            setTimeout(() => { if (statusMsg) statusMsg.style.display = 'none'; }, 3000);
          }
        } catch (err) {
          if (statusMsg) {
            statusMsg.className = 'small mt-2 text-danger';
            statusMsg.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>Ошибка сброса: ${escapeHtml(err.message)}`;
            statusMsg.style.display = 'block';
          }
        }
      };
    }

    await loadTemplate(typeSelect ? typeSelect.value : targetType);

    if (window.bootstrap && window.bootstrap.Modal) {
      const bsPromptModal = window.bootstrap.Modal.getOrCreateInstance(promptModalEl);
      bsPromptModal.show();
    }
  }

  function ensurePromptModalElement() {
    let promptEl = document.getElementById(PROMPT_MODAL_ID);
    if (!promptEl) {
      promptEl = document.createElement('div');
      promptEl.id = PROMPT_MODAL_ID;
      promptEl.className = 'modal fade';
      promptEl.tabIndex = -1;
      promptEl.setAttribute('aria-hidden', 'true');
      promptEl.innerHTML = `
        <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
          <div class="modal-content shadow-lg">
            <div class="modal-header py-2 px-3">
              <div class="d-flex align-items-center gap-2">
                <span class="fs-5 text-warning">⚙️</span>
                <h5 class="modal-title fw-bold text-warning mb-0">Редактор шаблона промпта</h5>
              </div>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
            </div>
            <div class="modal-body py-3 px-3">
              <div class="row g-2 mb-3">
                <div class="col-sm-6">
                  <label class="form-label small text-secondary fw-bold mb-1">Тип таблицы / сущности</label>
                  <select class="form-select form-select-sm" id="uai-prompt-type-select">
                    <option value="user_account">user_account (Учетные записи и сессии Windows)</option>
                    <option value="security_event">security_event (События безопасности Windows)</option>
                    <option value="process">process (Процессы Windows)</option>
                    <option value="service">service (Службы Windows)</option>
                    <option value="software">software (Установленное ПО)</option>
                    <option value="task">task (Задачи планировщика)</option>
                    <option value="startup">startup (Автозагрузка)</option>
                    <option value="network">network (Сетевые соединения)</option>
                    <option value="registry">registry (Реестр Windows)</option>
                    <option value="disk">disk (Диски и тома)</option>
                    <option value="cpu">cpu (Процессор CPU)</option>
                    <option value="gpu">gpu (Видеокарта GPU)</option>
                    <option value="file_event">file_event (Файловые события)</option>
                    <option value="website">website (Мониторинг сайтов)</option>
                    <option value="rag_doc">rag_doc (RAG База знаний)</option>
                    <option value="generic">generic (Общий шаблон)</option>
                  </select>
                </div>
                <div class="col-sm-6">
                  <label class="form-label small text-secondary fw-bold mb-1">Название шаблона</label>
                  <input type="text" class="form-control form-control-sm" id="uai-prompt-name-input" placeholder="Название шаблона">
                </div>
              </div>

              <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <label class="form-label small text-secondary fw-bold mb-0">Системная инструкция (System Instruction)</label>
                  <span class="badge bg-secondary-subtle text-secondary small" style="font-size: 0.72rem;">Роль и поведение ИИ</span>
                </div>
                <textarea class="form-control form-control-sm font-monospace" id="uai-prompt-system-input" rows="4" placeholder="Роль, экспертный контекст и правила поведения модели..."></textarea>
                <div class="form-text small text-secondary" style="font-size: 0.75rem;">
                  Системная инструкция задаёт контекст роли эксперта, ограничения и формат ответа ИИ для выбранного типа сущности.
                </div>
              </div>

              <div class="mb-2">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <label class="form-label small text-secondary fw-bold mb-0">Шаблон текста промпта (Prompt Template)</label>
                  <div class="d-flex gap-1" id="uai-prompt-variables-bar">
                    <button type="button" class="btn btn-xs btn-outline-info py-0 px-1 font-monospace" style="font-size: 0.75rem;" onclick="window.AIModalDialog.insertVariable('{title}')">{title}</button>
                    <button type="button" class="btn btn-xs btn-outline-info py-0 px-1 font-monospace" style="font-size: 0.75rem;" onclick="window.AIModalDialog.insertVariable('{subtitle}')">{subtitle}</button>
                    <button type="button" class="btn btn-xs btn-outline-info py-0 px-1 font-monospace" style="font-size: 0.75rem;" onclick="window.AIModalDialog.insertVariable('{metadata}')">{metadata}</button>
                    <button type="button" class="btn btn-xs btn-outline-info py-0 px-1 font-monospace" style="font-size: 0.75rem;" onclick="window.AIModalDialog.insertVariable('{raw_data}')">{raw_data}</button>
                  </div>
                </div>
                <textarea class="form-control form-control-sm font-monospace" id="uai-prompt-template-input" rows="8" placeholder="Текст промпта с плейсхолдерами..."></textarea>
                <div class="form-text small text-secondary" style="font-size: 0.75rem;">
                  Используйте переменные <code>{title}</code>, <code>{subtitle}</code>, <code>{metadata}</code>, <code>{raw_data}</code> для автоматической подстановки контекста строки таблицы.
                </div>
              </div>

              <div id="uai-prompt-status-msg" class="small mt-2" style="display: none;"></div>
            </div>
            <div class="modal-footer py-2 px-3 d-flex justify-content-between">
              <button type="button" class="btn btn-sm btn-outline-danger" id="btn-uai-prompt-reset">
                <i class="bi bi-arrow-counterclockwise me-1"></i>Сбросить по умолчанию
              </button>
              <div class="d-flex gap-2">
                <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                <button type="button" class="btn btn-sm btn-primary" id="btn-uai-prompt-save">
                  <i class="bi bi-check2 me-1"></i>Сохранить промпт
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
      promptEl.addEventListener('hide.bs.modal', () => {
        if (promptEl.contains(document.activeElement) && typeof document.activeElement.blur === 'function') {
          document.activeElement.blur();
        }
      });
      document.body.appendChild(promptEl);
    }
    return promptEl;
  }

  function insertVariable(varText) {
    const templateInput = document.getElementById('uai-prompt-template-input');
    if (!templateInput) return;
    const start = templateInput.selectionStart || 0;
    const end = templateInput.selectionEnd || 0;
    const val = templateInput.value;
    templateInput.value = val.substring(0, start) + varText + val.substring(end);
    templateInput.focus();
    templateInput.selectionStart = templateInput.selectionEnd = start + varText.length;
  }

  /**
   * Сквозной метод вызова диалога для панелей tab-software-scanner:
   * AIModalDialog.open({ program: progData, panelId: 'software-table' })
   * @param {Object} options Объект вызова с программой/процессом и ID панели
   */
  function open(options) {
    if (!options) return;
    const program = options.program || options;
    const panelId = options.panelId || 'software-table';

    const name = program.name || program.title || program.process_name || 'Неизвестный процесс';
    const pid = program.pid || program.process_id || null;
    const path = program.path || program.exe_path || program.executable_path || '';
    const cmdline = program.cmdline || program.command_line || '';
    const cpu = program.cpu_percent != null ? `${program.cpu_percent}%` : null;
    const ram = program.memory_mb != null ? `${program.memory_mb} МБ` : (program.memory_rss_bytes ? `${Math.round(program.memory_rss_bytes / 1048576)} МБ` : null);
    const publisher = program.publisher || program.company || program.vendor || (program.is_signed ? 'Подписан' : (program.is_signed === false ? 'Не подписан' : ''));
    const risk = program.risk_level || program.risk || 'Low';

    const meta = [];
    if (pid) meta.push({ label: 'PID', value: String(pid), isCode: true });
    if (path) meta.push({ label: 'Исполняемый файл', value: path, isCode: true, fullWidth: true });
    if (cmdline) meta.push({ label: 'Командная строка', value: cmdline, isCode: true, fullWidth: true });
    if (publisher) meta.push({ label: 'Цифровая подпись / Издатель', value: publisher });
    if (cpu) meta.push({ label: 'Нагрузка CPU', value: cpu });
    if (ram) meta.push({ label: 'Оперативная память', value: ram });
    if (risk) meta.push({ label: 'Оценка риска', value: risk });

    const actions = [];
    if (pid) {
      actions.push({
        label: '🚫 Завершить процесс',
        class: 'btn-outline-danger',
        icon: 'bi-x-circle-fill',
        onClick: async () => {
          if (!confirm(`Принудительно завершить процесс ${name} (PID ${pid})?`)) return;
          try {
            const res = await safeApiFetch('/api/v1/processes/kill', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ pid: Number(pid), force: true })
            });
            if (window.showToast) window.showToast(res.message || `Процесс ${pid} завершен`, 'success');
            else alert(res.message || `Процесс ${pid} завершен`);
          } catch (err) {
            alert(`Ошибка завершения процесса: ${err.message}`);
          }
        }
      });
    }

    if (path) {
      actions.push({
        label: '🔥 Заблокировать в Брандмауэре',
        class: 'btn-outline-warning',
        icon: 'bi-shield-slash-fill',
        onClick: async () => {
          if (!confirm(`Создать запрещающее правило в Брандмауэре для "${path}"?`)) return;
          try {
            const res = await safeApiFetch('/api/v1/security/firewall/block', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: path, name: `AI-Block-${name}` })
            });
            if (window.showToast) window.showToast(res.message || `Правило брандмауэра добавлено`, 'success');
            else alert(res.message || `Правило брандмауэра добавлено`);
          } catch (err) {
            alert(`Ошибка добавления правила: ${err.message}`);
          }
        }
      });
    }

    actions.push({
      label: '💾 Сохранить в WikiLLM',
      class: 'btn-outline-success',
      icon: 'bi-database-add',
      onClick: async () => {
        try {
          const payload = {
            title: name,
            category: 'software',
            content_pattern: `${name} ${path}`,
            summary: `Процесс ${name} (PID: ${pid || 'N/A'}, путь: ${path || 'N/A'}). Уровень риска: ${risk}.`
          };
          await safeApiFetch('/api/v1/wikillm/articles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (window.showToast) window.showToast(`Профиль "${name}" сохранен в WikiLLM`, 'success');
          else alert(`Профиль "${name}" сохранен в WikiLLM`);
        } catch (err) {
          alert(`Ошибка сохранения в WikiLLM: ${err.message}`);
        }
      }
    });

    return show({
      title: name,
      subtitle: path || (pid ? `PID: ${pid}` : ''),
      icon: '🤖',
      panelId: panelId,
      tableType: 'software',
      metadata: meta,
      rawContent: cmdline || (typeof program === 'object' ? JSON.stringify(program, null, 2) : String(program)),
      rawTitle: 'Командная строка и параметры',
      autoRun: true,
      actions: actions
    });
  }

  const modalApi = {
    show: show,
    open: open,
    openPromptEditor: openPromptEditor,
    insertVariable: insertVariable,
    escapeHtml: escapeHtml,
    formatMarkdownText: formatMarkdownText,
    normalizeTableType: normalizeTableType,
    parseModelResponse: parseModelResponse,
    renderReadyToolWidget: renderReadyToolWidget
  };

  // Немедленный глобальный экспорт до настройки слушателей событий
  if (typeof window !== 'undefined') {
    window.AIModalDialog = modalApi;
    window.AITableModal = modalApi;
  }

  // Предотвращение блокировки WAI-ARIA aria-hidden при закрытии модальных окон Bootstrap
  if (typeof document !== 'undefined') {
    document.addEventListener('hide.bs.modal', function(e) {
      if (e.target && e.target.contains(document.activeElement) && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
      }
    }, true);

    document.addEventListener('click', function(e) {
      const dismissBtn = e.target && e.target.closest ? e.target.closest('[data-bs-dismiss="modal"]') : null;
      if (dismissBtn && typeof dismissBtn.blur === 'function') {
        dismissBtn.blur();
      }
    }, true);
  }
})();
