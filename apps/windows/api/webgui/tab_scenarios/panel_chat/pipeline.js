/**
 * =============================================================================
 * Название: Визуализатор цепочки рассуждений (Matrix Reasoning) и интерактивный раннер команд
 * =============================================================================
 * Описание:
 *   Универсальный парсер и визуализатор ответов языковых моделей для вкладки сценариев.
 *   Обрабатывает смешанные ответы (Markdown + HTML), выделяет шаги рассуждений ReAct,
 *   рендерит карточки готовых действий (Ready Tools / Action Cards) и интерактивные
 *   консоли PowerShell / CMD с возможностью исполнения на локальном хосте.
 *
 * Файл: apps/windows/api/webgui/tab_scenarios/panel_chat/pipeline.js
 * Пакет: windows/api/webgui/tab_scenarios
 * Автор: hypo69
 * Updated: 2026-10-31 19:55:00
 * =============================================================================
 */

import { escapeHtml, unescapeHtml, formatMarkdown } from '../common/ui_utils.js';

/**
 * Проверяет, является ли строка строкой статуса рассуждений (Reasoning Step).
 * @param {string} line - Строка текста.
 * @returns {boolean}
 */
export function isInvestigationStatusLine(line) {
  if (!line) return false;
  const s = String(line).trim();
  if (!s) return false;
  if (/^>\s*[*_]?[💡⚙️🛠️✨📝🏁🔍🧠⚡]/.test(s)) return true;
  if (/^[>*\s﻿ ​]*[💡⚙️🛠️✨📝🏁🔍🧠⚡]/.test(s)) return true;
  if (/^[>*\s﻿ ​]*(?:WikiLLM Toolbox:|Запуск зонда|Шаг рассуждения|Модель синтезировала|Синтез решения|Завершение расследования)/i.test(s)) return true;
  return false;
}

/**
 * Проверяет, является ли строка заголовком блока данных инструмента (Telemetry Data).
 * @param {string} line - Строка текста.
 * @returns {boolean}
 */
export function isInvestigationDataLine(line) {
  if (!line) return false;
  const s = String(line).trim();
  if (!s) return false;
  return /^[>*\s﻿ ​]*(?:📊|Данные от|\*\*Данные|Полученные факты|Telemetry preview)/i.test(s);
}

/**
 * Рендерит отдельный шаг рассуждения или блок данных в матричном стиле.
 * @param {Object} st - Объект шага ({ type: 'status'|'data', text?: string, title?: string, data?: string }).
 * @returns {string} HTML-разметка шага.
 */
export function renderMatrixStepHtml(st) {
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
    } else if (rawText.includes('📝') || rawText.includes('Формирование') || rawText.includes('Отчет')) {
      badgeType = 'uai-mb-synth';
      badgeIcon = 'bi-file-earmark-text';
      badgeText = 'SYNTHESIS';
    } else if (rawText.includes('🏁') || rawText.includes('завершено') || rawText.includes('Завершение')) {
      badgeType = 'uai-mb-done';
      badgeIcon = 'bi-check2-circle';
      badgeText = 'COMPLETE';
    }

    let cleanText = escapeHtml(rawText)
      .replace(/^[>*\s﻿ ​]*(?:[💡⚙️🛠️✨📝🏁🔍🧠⚡]\s*)+/g, '')
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
      .replace(/^[>*\s﻿ ​]*(?:[📊\s]*)+/g, '')
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
 * @param {HTMLElement} containerEl - Контейнер ответа.
 * @param {string} rawStreamText - Текущий накопленный текст ответа.
 */
export function renderLiveStreamContent(containerEl, rawStreamText) {
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
          data: dataBuffer.join('\n').trim(),
        });
      }
      currentTitle = trimmed.replace(/^[>*\s﻿ ​]+/, '');
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
            data: dataBuffer.join('\n').trim(),
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
            data: dataBuffer.join('\n').trim(),
          });
        }
        inData = false;
        dataBuffer = [];
      } else {
        dataBuffer.push(line.replace(/^[>*\s﻿ ​]+/, ''));
        continue;
      }
    }

    if (isInvestigationStatusLine(trimmed)) {
      liveSteps.push({
        type: 'status',
        text: trimmed.replace(/^[>*\s﻿ ​]+/, ''),
      });
      continue;
    }

    dialogueLines.push(line);
  }

  if (inData && dataBuffer.length > 0) {
    liveSteps.push({
      type: 'data',
      title: currentTitle || 'Данные инструмента',
      data: dataBuffer.join('\n').trim(),
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
            <span class="badge uai-matrix-steps-count font-monospace">${liveSteps.length} ШАГОВ</span>
            <span class="uai-matrix-title font-monospace"><i class="bi bi-terminal-fill me-1"></i>[MATRIX REASONING] Цепочка решения задачи &bull; Зондирование хоста</span>
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
    outHtml += `<div>${formatMarkdown(dialogueText)}<span class="uai-matrix-cursor">▌</span></div>`;
  } else if (liveSteps.length === 0) {
    outHtml += `<div>${escapeHtml(rawStreamText).replace(/\n/g, '<br>')}<span class="uai-matrix-cursor">▌</span></div>`;
  }

  containerEl.innerHTML = outHtml;
}

/**
 * Проверяет, является ли строка исполняемой системной командой Windows.
 * @param {string} str - Проверяемая строка.
 * @returns {boolean}
 */
export function isCommandLineString(str) {
  if (!str || typeof str !== 'string') return false;
  const s = str.trim();
  if (!s) return false;
  return /^(?:powershell(?:\.exe)?\s+|pwsh(?:\.exe)?\s+|(?:Stop|Get|Start|Restart|Set|New|Remove|Test|Invoke|Select|Where)-[A-Za-z]+|cmd(?:\.exe)?(?:\s+\/c)?\s+|net(?:\.exe)?\s+(?:user|localgroup|start|stop|use|share|session)|taskkill\b|sc(?:\.exe)?\s+|reg(?:\.exe)?\s+|wmic\b|sfc\b|dism\b|gpupdate\b|ipconfig\b|route\b)/i.test(s) ||
         /\b(?:Stop-Process|Get-Process|Restart-Service|Start-Service|Set-Service|Get-Service|Get-CimInstance|Get-WmiObject|Get-WinEvent|New-Item|Set-Acl|Get-Acl|New-SmbShare|Get-SmbShare|Get-SmbSession)\b/i.test(s) ||
         /^\$(?:user|p|svc|acl|rule|path)\s*=/i.test(s);
}

/**
 * Рендерит интерактивный терминал запуска команды PowerShell / CMD.
 * @param {string} cmdText - Текст команды.
 * @param {string} lang - Язык оболочки (powershell, pwsh, cmd).
 * @returns {string} HTML виджета.
 */
export function renderInteractiveCommandWidget(cmdText, lang = 'powershell') {
  if (!cmdText) return '';
  const cleanCmd = String(cmdText).trim();
  const lineCount = cleanCmd.split('\n').length;
  const rows = Math.min(Math.max(lineCount, 2), 10);
  const escapedCmd = escapeHtml(cleanCmd);
  const termId = 'sc-term-cmd-' + Math.random().toString(36).substring(2, 9);
  const shellDefault = (lang && lang.toLowerCase() === 'cmd') ? 'cmd' : (lang && lang.toLowerCase() === 'pwsh' ? 'pwsh' : 'powershell');
  const shellTitle = shellDefault === 'cmd' ? 'CMD Console' : (shellDefault === 'pwsh' ? 'PowerShell Core' : 'PowerShell Console');

  return `
    <div class="uai-code-runner-box my-2" id="${termId}-card" data-term-id="${termId}">
      <div class="uai-terminal-window" id="${termId}">
        <div class="uai-terminal-header" id="${termId}-header">
          <div class="d-flex align-items-center gap-2">
            <span class="uai-terminal-dot uai-dot-red"></span>
            <span class="uai-terminal-dot uai-dot-yellow"></span>
            <span class="uai-terminal-dot uai-dot-green"></span>
            <span class="uai-terminal-title font-monospace ms-1" id="${termId}-title"><i class="bi bi-terminal-fill me-1 text-info"></i>${escapeHtml(shellTitle)}</span>
          </div>
          <div class="d-flex align-items-center gap-1.5">
            <button type="button" class="btn btn-sm uai-term-btn uai-btn-copy-cmd" id="${termId}-btn-copy" title="Скопировать команду в буфер обмена">
              <i class="bi bi-clipboard me-1"></i>Копировать
            </button>
            <button type="button" class="btn btn-sm uai-term-btn-run uai-btn-run-cmd" id="${termId}-btn-run" title="Выполнить команду на хосте">
              <i class="bi bi-play-fill me-1"></i>Запустить
            </button>
          </div>
        </div>
        <div class="uai-terminal-body" id="${termId}-body" style="background-color: #000000 !important; padding: 0 !important;">
          <textarea class="font-monospace uai-cmd-input border-0" id="${termId}-input" rows="${rows}" spellcheck="false" placeholder="Введите команду..." style="background-color: #000000 !important; color: #ffffff !important; font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace !important; font-weight: 600 !important; font-size: 0.88rem !important; line-height: 1.45 !important; width: 100% !important; padding: 0.6rem 0.8rem !important; border: none !important; outline: none !important; resize: vertical !important; white-space: pre-wrap !important;">${escapedCmd}</textarea>
        </div>
      </div>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mt-1">
        <div class="small text-muted uai-cmd-hint" id="${termId}-hint" style="font-size: 0.76rem;">
          <i class="bi bi-shield-check me-1 text-success"></i>Безопасный запуск на хосте (${shellTitle})
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
 * Рендерит карточку готового действия решения (Action Card / Ready Tool Card).
 * @param {Object} toolObj - Параметры действия (title, description, execution_command, risk, shell).
 * @returns {string} HTML карточки действия.
 */
export function renderReadyActionWidget(toolObj) {
  if (!toolObj) return '';
  const title = toolObj.title || toolObj.tool_title || 'Действие решения';
  const description = toolObj.description || toolObj.description_ru || '';
  const cmd = (toolObj.execution_command || toolObj.command || toolObj.probe_script || '').trim();
  if (!cmd) return '';

  const actionId = toolObj.action_id || 'act-' + Math.random().toString(36).substring(2, 8);
  const termId = 'sc-action-' + Math.random().toString(36).substring(2, 9);
  const risk = (toolObj.risk || 'safe').toLowerCase();
  const riskBadge = risk === 'danger'
    ? '<span class="badge bg-danger small px-2 py-0.5"><i class="bi bi-exclamation-octagon-fill me-1"></i>Опасно</span>'
    : (risk === 'caution' || risk === 'warning'
      ? '<span class="badge bg-warning text-dark small px-2 py-0.5"><i class="bi bi-exclamation-triangle-fill me-1"></i>Внимание</span>'
      : '<span class="badge bg-primary bg-opacity-25 border border-primary text-info small px-2 py-0.5"><i class="bi bi-terminal-fill me-1"></i>PowerShell Action</span>');

  const isCmdLike = (toolObj.shell === 'cmd') || /^(?:cmd\b|net\b|reg\b|taskkill\b|sc\b)/i.test(cmd);
  const shellTitle = isCmdLike ? 'CMD Console' : 'PowerShell Console';
  const lineCount = cmd.split('\n').length;
  const rows = Math.min(Math.max(lineCount, 2), 10);
  const escapedCmd = escapeHtml(cmd);

  return `
    <div class="uai-ready-tool-card uai-code-runner-box my-3 p-3 rounded border border-primary border-opacity-25 bg-body-tertiary" id="${termId}-card" data-action-id="${escapeHtml(actionId)}" data-term-id="${termId}">
      <div class="uai-tool-card-header d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
        <div class="d-flex align-items-center gap-2">
          <span class="fs-5 text-warning">⚡</span>
          <div>
            <div class="fw-bold text-primary uai-tool-title">${escapeHtml(title)}</div>
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
            <span class="uai-terminal-title font-monospace ms-1" id="${termId}-title"><i class="bi bi-terminal-fill me-1 text-info"></i>${escapeHtml(shellTitle)}</span>
          </div>
          <div class="d-flex align-items-center gap-1.5">
            <button type="button" class="btn btn-sm uai-term-btn uai-btn-copy-cmd" id="${termId}-btn-copy" title="Скопировать команду в буфер обмена">
              <i class="bi bi-clipboard me-1"></i>Копировать
            </button>
            <button type="button" class="btn btn-sm uai-term-btn-run uai-btn-run-cmd" id="${termId}-btn-run" title="Выполнить действие на хосте">
              <i class="bi bi-play-fill me-1"></i>Запустить
            </button>
          </div>
        </div>
        <div class="uai-terminal-body" id="${termId}-body" style="background-color: #000000 !important; padding: 0 !important;">
          <textarea class="font-monospace uai-cmd-input border-0" id="${termId}-input" rows="${rows}" spellcheck="false" placeholder="Введите команду..." style="background-color: #000000 !important; color: #ffffff !important; font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace !important; font-weight: 600 !important; font-size: 0.88rem !important; line-height: 1.45 !important; width: 100% !important; padding: 0.6rem 0.8rem !important; border: none !important; outline: none !important; resize: vertical !important; white-space: pre-wrap !important;">${escapedCmd}</textarea>
        </div>
      </div>
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mt-1">
        <div class="small text-muted uai-cmd-hint" id="${termId}-hint" style="font-size: 0.76rem;">
          <i class="bi bi-shield-check me-1 text-success"></i>Безопасное выполнение действия системы (${shellTitle})
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
 * @param {HTMLElement} rootEl - Корневой элемент контейнера.
 */
export function attachInteractiveCommandHandlers(rootEl) {
  if (!rootEl) return;
  const boxes = rootEl.querySelectorAll('.uai-code-runner-box, .uai-ready-tool-card');
  boxes.forEach(box => {
    if (box.dataset.handlerAttached === 'true') return;
    box.dataset.handlerAttached = 'true';

    const textarea = box.querySelector('.uai-cmd-input');
    const copyBtn = box.querySelector('.uai-btn-copy-cmd');
    const runBtn = box.querySelector('.uai-btn-run-cmd');
    const outputContainer = box.querySelector('.uai-cmd-output-container');
    const outputPre = box.querySelector('.uai-cmd-output');
    const badge = box.querySelector('.uai-cmd-result-badge');

    if (copyBtn && textarea) {
      copyBtn.onclick = () => {
        const textToCopy = textarea.value;
        navigator.clipboard.writeText(textToCopy).then(() => {
          const origHtml = copyBtn.innerHTML;
          copyBtn.innerHTML = '<i class="bi bi-check2 text-success me-1"></i>Скопировано';
          setTimeout(() => { copyBtn.innerHTML = origHtml; }, 2000);
        }).catch(() => {
          textarea.select();
          document.execCommand('copy');
        });
      };
    }

    if (runBtn && textarea) {
      runBtn.onclick = async () => {
        const cmdToRun = textarea.value.trim();
        if (!cmdToRun) return;

        const origRunHtml = runBtn.innerHTML;
        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Запуск...';

        if (outputContainer) outputContainer.style.display = 'block';
        if (outputPre) outputPre.textContent = 'Выполнение команды на локальном хосте...';
        if (badge) {
          badge.className = 'badge bg-warning text-dark small';
          badge.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Выполняется';
        }

        try {
          const resp = await window.fetch('/api/v1/diagnostics/execute-powershell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              command: cmdToRun,
              timeout_sec: 35,
              shell: 'powershell',
              as_admin: false,
            }),
          });

          if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${resp.status}`);
          }

          const result = await resp.json();
          if (badge) {
            if (result.success) {
              badge.className = 'badge bg-success small';
              badge.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>Код 0 (${result.execution_time_ms} мс)`;
            } else {
              badge.className = 'badge bg-danger small';
              badge.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>Код ${result.returncode} (${result.execution_time_ms} мс)`;
            }
          }

          let outText = '';
          if (result.stdout && result.stdout.trim()) outText += result.stdout;
          if (result.stderr && result.stderr.trim()) {
            if (outText) outText += '\n[Ошибки stderr]:\n';
            outText += result.stderr;
          }
          if (!outText) {
            outText = result.success ? '(Команда выполнена успешно, вывод отсутствует)' : '(Команда завершилась с ошибкой, вывод пуст)';
          }

          if (outputPre) outputPre.textContent = outText;
        } catch (err) {
          if (badge) {
            badge.className = 'badge bg-danger small';
            badge.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Сбой запроса';
          }
          if (outputPre) outputPre.textContent = `Ошибка отправки запроса: ${err.message}`;
        } finally {
          runBtn.disabled = false;
          runBtn.innerHTML = origRunHtml;
        }
      };
    }
  });
}

/**
 * Универсальный парсер ответа модели: распознает шаги расследования WikiLLM Matrix Reasoning,
 * готовые действия (Action Cards), интерактивные консоли PowerShell/CMD и форматирует Markdown.
 *
 * @param {string} rawText - Текст ответа модели.
 * @returns {string} Итоговый безопасный HTML диалога.
 */
export function parseModelResponse(rawText) {
  if (!rawText) return '';
  let text = String(rawText);

  // 1. Очистка ритуальных вступительных клише
  const greetingsRegex = /^(?:Приветствую[^\.\n]*[\.\n]*|Здравствуйте[^\.\n]*[\.\n]*|Как эксперт[^\.\n]*[\.\n]*|Я провел анализ[^\.\n]*[\.\n]*|Я проанализировал[^\.\n]*[\.\n]*)/i;
  text = text.replace(greetingsRegex, '').trim();

  // 2. Извлечение готовых инструментов и действий (блоки ```action { ... } ```)
  const actionCards = [];
  text = text.replace(/```(?:action|json:action)\s*(\{[\s\S]*?\})\s*```/gi, (match, jsonStr) => {
    try {
      const parsed = JSON.parse(jsonStr.trim());
      if (parsed && (parsed.execution_command || parsed.command || parsed.probe_script)) {
        actionCards.push(parsed);
        return `###__ACTION_CARD_PLACEHOLDER_${actionCards.length - 1}__###`;
      }
    } catch (_) {}
    return match;
  });

  // Поиск вызовов инструментов create_custom_tool в ```tool_call или ```json
  text = text.replace(/```(?:tool_call|json)?\s*(\{[\s\S]*?"(?:tool_name|create_custom_tool|action_id)"[\s\S]*?\})\s*```/gi, (match, jsonStr) => {
    try {
      const parsed = JSON.parse(jsonStr.trim());
      const tName = parsed.tool_name || parsed.action_id || '';
      const args = parsed.arguments || parsed;
      if (tName || args.probe_script || args.execution_command) {
        actionCards.push({
          title: args.tool_title || args.title || tName || 'Действие решения',
          description: args.description_ru || args.description || '',
          execution_command: args.probe_script || args.execution_command || args.command || '',
          action_id: args.tool_name || tName || 'action_' + actionCards.length,
          risk: args.risk || 'safe',
        });
        return `###__ACTION_CARD_PLACEHOLDER_${actionCards.length - 1}__###`;
      }
    } catch (_) {}
    return match;
  });

  // 3. Выделение шагов расследования (> 💡 ..., > ⚙️ ..., > 🛠️ ..., > 📊 ..., > 🏁 ...)
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
          data: dataBuffer.join('\n').trim(),
        });
      }
      currentStepTitle = trimmed.replace(/^[>*\s﻿ ​]+/, '');
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
            data: dataBuffer.join('\n').trim(),
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
            data: dataBuffer.join('\n').trim(),
          });
        }
        inDataBlock = false;
        dataBuffer = [];
      } else {
        dataBuffer.push(line.replace(/^[>*\s﻿ ​]+/, ''));
        continue;
      }
    }

    if (isInvestigationStatusLine(trimmed)) {
      investigationSteps.push({
        type: 'status',
        text: trimmed.replace(/^[>*\s﻿ ​]+/, ''),
      });
      continue;
    }

    remainingLines.push(line);
  }

  if (inDataBlock && dataBuffer.length > 0) {
    investigationSteps.push({
      type: 'data',
      title: currentStepTitle || 'Данные инструмента',
      data: dataBuffer.join('\n').trim(),
    });
  }

  let parsedMainText = remainingLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();

  // 4. Поиск блоков команд Windows (powershell, pwsh, ps1, cmd, bat)
  const cmdWidgets = [];
  parsedMainText = parsedMainText.replace(/```(?:powershell|pwsh|ps1|cmd|bat|batch|bash|sh)?\s*([\s\S]*?)```/gi, (match, code) => {
    const rawCode = unescapeHtml(code).trim();
    if (!rawCode) return match;

    const lowerMatch = match.toLowerCase();
    const isCmdLang = lowerMatch.startsWith('```cmd') || lowerMatch.startsWith('```bat') || lowerMatch.startsWith('```batch');
    const isPsLang = lowerMatch.startsWith('```powershell') || lowerMatch.startsWith('```pwsh') || lowerMatch.startsWith('```ps1');
    const isSystemCmd = isCmdLang || isPsLang || isCommandLineString(rawCode);

    if (isSystemCmd) {
      const widgetHtml = renderInteractiveCommandWidget(rawCode, isCmdLang ? 'cmd' : 'powershell');
      cmdWidgets.push(widgetHtml);
      return `\n\n###__CMD_RUNNER_PLACEHOLDER_${cmdWidgets.length - 1}__###\n\n`;
    }

    // Если это обычный блок кода (например, JSON, Python, XML), оставляем его для стандартной подсветки
    return match;
  });

  // 5. Преобразование Markdown в безопасный HTML
  let formattedHtml = formatMarkdown(parsedMainText);

  // Очистка избыточных <br> вокруг плейсхолдеров
  formattedHtml = formattedHtml.replace(/(?:<br\s*\/?>\s*)+###__CMD_RUNNER_PLACEHOLDER_/gi, '###__CMD_RUNNER_PLACEHOLDER_');
  formattedHtml = formattedHtml.replace(/###__CMD_RUNNER_PLACEHOLDER_(\d+)__(?:<br\s*\/?>\s*)+/gi, '###__CMD_RUNNER_PLACEHOLDER_$1__');
  formattedHtml = formattedHtml.replace(/(?:<br\s*\/?>\s*)+###__ACTION_CARD_PLACEHOLDER_/gi, '###__ACTION_CARD_PLACEHOLDER_');
  formattedHtml = formattedHtml.replace(/###__ACTION_CARD_PLACEHOLDER_(\d+)__(?:<br\s*\/?>\s*)+/gi, '###__ACTION_CARD_PLACEHOLDER_$1__');

  // 6. Подстановка готовых виджетов интерактивных команд
  cmdWidgets.forEach((widgetHtml, idx) => {
    formattedHtml = formattedHtml.replace(`###__CMD_RUNNER_PLACEHOLDER_${idx}__###`, widgetHtml);
  });

  // 7. Подстановка готовых карточек действий
  actionCards.forEach((actionObj, idx) => {
    const actionHtml = renderReadyActionWidget(actionObj);
    formattedHtml = formattedHtml.replace(`###__ACTION_CARD_PLACEHOLDER_${idx}__###`, actionHtml);
  });

  // 8. Сборка итогового HTML
  let outHtml = '';
  if (investigationSteps.length > 0) {
    let matrixStepsHtml = '';
    investigationSteps.forEach(st => {
      matrixStepsHtml += renderMatrixStepHtml(st);
    });

    outHtml += `
      <div class="uai-matrix-terminal mb-3">
        <div class="uai-matrix-header">
          <div class="d-flex align-items-center gap-2">
            <span class="uai-matrix-indicator"></span>
            <span class="badge uai-matrix-steps-count font-monospace">${investigationSteps.length} ШАГОВ</span>
            <span class="uai-matrix-title font-monospace"><i class="bi bi-terminal-fill me-1"></i>[MATRIX REASONING] Цепочка рассуждений &bull; Инструменты WikiLLM</span>
          </div>
          <span class="uai-matrix-toggle-hint small font-monospace"><i class="bi bi-chevron-down"></i> Детали</span>
        </div>
        <div class="uai-matrix-body">
          ${matrixStepsHtml}
        </div>
      </div>
    `;
  }

  outHtml += `<div>${formattedHtml}</div>`;
  return outHtml;
}
