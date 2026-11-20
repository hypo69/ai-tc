/**
 * =============================================================================
 * Process Name: Windows App Internals - Command Template Wizard & Parser
 * =============================================================================
 * Description:
 *   Интерактивный мастер (Wizard) и парсер параметризованных команд для языковых
 *   моделей (LLM) и агентов. Умеет строить и парсить команды с плейсхолдерами вида:
 *     net user {user_name} /active:{yes|no}
 *     sc.exe config {service_name} start={auto|demand|disabled}
 *     taskkill.exe /PID {pid:int} /F
 *   Предоставляет:
 *     1. Живой парсинг введенного шаблона команды и извлечение аргументов.
 *     2. Конструктор параметров (текст, выбор enum, число, флаг, путь к файлу).
 *     3. Интерактивную панель тестирования подстановки значений (Live Preview).
 *     4. Проверку выполнения команды на хосте с консольным выводом.
 *     5. Сохранение параметризованного инструмента в базу u177424397_tool_chains (Hostinger MariaDB).
 *
 * File: command_wizard.js
 * Package: windows/api/webgui/tab_app_internals/panel_instruments_db
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:01:00
 * =============================================================================
 */

import { notifyUser } from '../common/ui_utils.js?v=20261112_v1';

let wizardModalInstance = null;
let currentParsedData = null;
let debounceParseTimer = null;
let onWizardSaveCallback = null;

/**
 * Инициализация мастера команд: привязка глобальных событий и кнопок панели.
 * @param {Function} [onSaveCallback] - Функция обратного вызова при успешном сохранении
 */
export function initCommandWizard(onSaveCallback) {
  onWizardSaveCallback = onSaveCallback;
  bindWizardEvents();
}

/**
 * Открытие модального окна мастера создания команд для модели.
 * @param {string} [initialTemplate=''] - Начальный шаблон команды
 * @param {object|null} [existingTool=null] - Существующий инструмент для редактирования
 */
export function openCommandWizardModal(initialTemplate = '', existingTool = null) {
  const modalEl = document.getElementById('inst-command-wizard-modal');
  if (!modalEl) return;

  const rawInput = document.getElementById('wizard-raw-command-input');
  const toolIdInp = document.getElementById('wizard-meta-tool-id');
  const nameInp = document.getElementById('wizard-meta-name');
  const typeSel = document.getElementById('wizard-meta-type');
  const entitySel = document.getElementById('wizard-meta-entity');
  const riskSel = document.getElementById('wizard-meta-risk');
  const descInp = document.getElementById('wizard-meta-desc');
  const tagsInp = document.getElementById('wizard-meta-tags');
  const execOutput = document.getElementById('wizard-exec-output-box');

  if (execOutput) {
    execOutput.style.display = 'none';
    execOutput.textContent = '';
  }

  if (existingTool) {
    if (rawInput) rawInput.value = existingTool.command || initialTemplate || '';
    if (toolIdInp) toolIdInp.value = existingTool.tool_id || '';
    if (nameInp) nameInp.value = existingTool.name || '';
    if (typeSel) typeSel.value = existingTool.tool_type || 'cmd';
    if (entitySel) entitySel.value = existingTool.target_entity || 'system';
    if (riskSel) riskSel.value = existingTool.risk_level || 'safe';
    if (descInp) descInp.value = existingTool.description || '';
    if (tagsInp) tagsInp.value = Array.isArray(existingTool.tags) ? existingTool.tags.join(', ') : (existingTool.tags || '#agent_tool');
  } else {
    const defaultSample = initialTemplate || 'net user {user_name} /active:{yes|no}';
    if (rawInput) rawInput.value = defaultSample;
    if (toolIdInp) toolIdInp.value = '';
    if (nameInp) nameInp.value = '';
    if (typeSel) typeSel.value = 'cmd';
    if (entitySel) entitySel.value = 'user';
    if (riskSel) riskSel.value = 'safe';
    if (descInp) descInp.value = '';
    if (tagsInp) tagsInp.value = '#agent_tool';
  }

  // Запуск парсинга команды
  parseWizardCommand(rawInput?.value || '');

  // Открытие Bootstrap модального окна
  if (window.bootstrap && window.bootstrap.Modal) {
    wizardModalInstance = window.bootstrap.Modal.getOrCreateInstance
      ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
      : new window.bootstrap.Modal(modalEl);
    wizardModalInstance.show();
  } else {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
  }
}

/**
 * Привязка событий внутри модального окна мастера.
 */
function bindWizardEvents() {
  const rawInput = document.getElementById('wizard-raw-command-input');
  if (rawInput && !rawInput._bound) {
    rawInput._bound = true;
    rawInput.addEventListener('input', () => {
      clearTimeout(debounceParseTimer);
      debounceParseTimer = setTimeout(() => {
        parseWizardCommand(rawInput.value);
      }, 200);
    });
  }

  // Кнопки быстрой вставки токенов
  document.querySelectorAll('.wizard-insert-token-btn').forEach((btn) => {
    if (!btn._bound) {
      btn._bound = true;
      btn.addEventListener('click', () => {
        const token = btn.getAttribute('data-token');
        if (token && rawInput) {
          insertTextAtCursor(rawInput, token);
          parseWizardCommand(rawInput.value);
        }
      });
    }
  });

  // Кнопки готовых пресетов команд
  document.querySelectorAll('.wizard-preset-btn').forEach((btn) => {
    if (!btn._bound) {
      btn._bound = true;
      btn.addEventListener('click', () => {
        const presetCmd = btn.getAttribute('data-cmd');
        if (presetCmd && rawInput) {
          rawInput.value = presetCmd;
          parseWizardCommand(presetCmd);
        }
      });
    }
  });

  // Кнопка сохранения инструмента в базу
  const saveBtn = document.getElementById('wizard-btn-save-to-db');
  if (saveBtn && !saveBtn._bound) {
    saveBtn._bound = true;
    saveBtn.addEventListener('click', handleSaveFromWizard);
  }

  // Кнопка тестового выполнения команды
  const testBtn = document.getElementById('wizard-btn-execute-test');
  if (testBtn && !testBtn._bound) {
    testBtn._bound = true;
    testBtn.addEventListener('click', handleExecuteFromWizard);
  }

  // Кнопка копирования итоговой подставленной команды
  const copyBtn = document.getElementById('wizard-btn-copy-sample');
  if (copyBtn && !copyBtn._bound) {
    copyBtn._bound = true;
    copyBtn.addEventListener('click', () => {
      const sampleEl = document.getElementById('wizard-sample-command-preview');
      if (sampleEl && sampleEl.textContent) {
        navigator.clipboard.writeText(sampleEl.textContent.trim());
        const origText = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Скопировано';
        setTimeout(() => {
          copyBtn.innerHTML = origText;
        }, 1800);
      }
    });
  }
}

/**
 * Синтаксический анализ команды через серверный REST API.
 * @param {string} rawCommand - Шаблон команды
 */
async function parseWizardCommand(rawCommand) {
  const cmd = (rawCommand || '').trim();
  const paramsTableBody = document.getElementById('wizard-params-table-body');
  const schemaViewer = document.getElementById('wizard-schema-json-preview');
  const normTemplateEl = document.getElementById('wizard-normalized-template-preview');

  if (!cmd) {
    if (paramsTableBody) {
      paramsTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-secondary py-3">Введите команду для извлечения параметров</td></tr>`;
    }
    if (schemaViewer) schemaViewer.textContent = '{\n  "properties": {}\n}';
    if (normTemplateEl) normTemplateEl.textContent = '—';
    updateLivePreviewCommand();
    return;
  }

  try {
    const res = await fetch('/api/v1/ai-instruments/wizard/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const result = data.result;
    currentParsedData = result;

    // Автозаполнение метаданных (если пользователь не заполнил вручную)
    autoFillMetadata(result);

    // Отображение нормализованного шаблона
    if (normTemplateEl) {
      normTemplateEl.textContent = result.normalized_template;
    }

    // Отображение JSON Schema для LLM
    if (schemaViewer) {
      schemaViewer.textContent = JSON.stringify(result.parameters_schema || {}, null, 2);
    }

    // Отрисовка таблицы параметров
    renderParametersTable(result.parameters || []);

    // Построение интерактивных полей для Live Preview подстановки
    renderLivePreviewControls(result.parameters || []);

    // Обновление итоговой подставленной команды
    updateLivePreviewCommand();
  } catch (err) {
    console.error('[CommandWizard] Ошибка парсинга команды:', err);
    // Клиентский fallback парсинг при временном сбое сети
    fallbackClientParse(cmd);
  }
}

/**
 * Отрисовка таблицы обнаруженных параметров команды.
 * @param {Array<object>} parameters - Список параметров
 */
function renderParametersTable(parameters) {
  const tbody = document.getElementById('wizard-params-table-body');
  const countBadge = document.getElementById('wizard-params-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${parameters.length} параметров`;

  if (!parameters.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-secondary py-3 small">
          <i class="bi bi-info-circle me-1"></i>В команде нет параметров. Используйте фигурные скобки, например: <code>{user_name}</code> или <code>{yes|no}</code>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = parameters
    .map((p, idx) => {
      const typeBadge =
        p.param_type === 'enum'
          ? '<span class="ui-badge ui-badge-info">enum (выбор)</span>'
          : p.param_type === 'integer'
          ? '<span class="ui-badge ui-badge-warning">int (число)</span>'
          : p.param_type === 'boolean'
          ? '<span class="ui-badge ui-badge-success">bool (флаг)</span>'
          : '<span class="ui-badge ui-badge-secondary">string (текст)</span>';

      const optionsStr = p.options && p.options.length ? p.options.join(', ') : '—';
      const flagInfo = p.flag_prefix ? `<code class="text-info me-1">${escapeHtml(p.flag_prefix)}</code>` : '';

      return `
        <tr>
          <td>
            <div class="fw-bold font-monospace text-primary">${flagInfo}${escapeHtml(p.name)}</div>
            <small class="text-secondary">${escapeHtml(p.raw_token)}</small>
          </td>
          <td>${typeBadge}</td>
          <td><span class="small font-monospace">${escapeHtml(optionsStr)}</span></td>
          <td>
            <input type="text" class="form-control form-control-sm wizard-param-desc-input" data-param-idx="${idx}" value="${escapeHtml(p.description || '')}" placeholder="Описание для модели...">
          </td>
          <td class="text-center">
            <span class="badge ${p.required ? 'bg-primary-subtle text-primary' : 'bg-secondary-subtle text-secondary'}">
              ${p.required ? 'Обязательный' : 'Опционально'}
            </span>
          </td>
        </tr>
      `;
    })
    .join('');

  // Привязка обновления описаний параметров
  tbody.querySelectorAll('.wizard-param-desc-input').forEach((input) => {
    input.addEventListener('change', () => {
      const idx = parseInt(input.getAttribute('data-param-idx'), 10);
      if (currentParsedData && currentParsedData.parameters && currentParsedData.parameters[idx]) {
        currentParsedData.parameters[idx].description = input.value.trim();
        // Обновляем схему JSON
        if (currentParsedData.parameters_schema?.properties?.[currentParsedData.parameters[idx].name]) {
          currentParsedData.parameters_schema.properties[currentParsedData.parameters[idx].name].description = input.value.trim();
          const schemaViewer = document.getElementById('wizard-schema-json-preview');
          if (schemaViewer) {
            schemaViewer.textContent = JSON.stringify(currentParsedData.parameters_schema, null, 2);
          }
        }
      }
    });
  });
}

/**
 * Отрисовка интерактивных контролов ввода для проверки подстановки значений (Live Preview).
 * @param {Array<object>} parameters - Список параметров
 */
function renderLivePreviewControls(parameters) {
  const container = document.getElementById('wizard-live-preview-controls');
  if (!container) return;

  if (!parameters.length) {
    container.innerHTML = `<div class="col-12 text-secondary small fst-italic py-1">Параметры для ввода отсутствуют</div>`;
    return;
  }

  container.innerHTML = parameters
    .map((p) => {
      const label = `${p.flag_prefix || ''}${p.name}`;
      if (p.param_type === 'enum' && p.options && p.options.length) {
        const optionsHtml = p.options
          .map((opt) => `<option value="${escapeHtml(opt)}" ${opt === p.default ? 'selected' : ''}>${escapeHtml(opt)}</option>`)
          .join('');
        return `
          <div class="col-md-6 col-lg-4">
            <label class="form-label form-label-sm fw-semibold mb-1 font-monospace text-truncate d-block" title="${escapeHtml(label)}">
              ${escapeHtml(label)}:
            </label>
            <select class="form-select form-select-sm wizard-live-param-input" data-param-name="${escapeHtml(p.name)}">
              ${optionsHtml}
            </select>
          </div>
        `;
      }

      // Текстовый или числовой ввод
      const sampleVal = p.default || (p.name.includes('user') ? 'Administrator' : p.name.includes('service') ? 'Spooler' : p.param_type === 'integer' ? '1' : 'test_val');
      return `
        <div class="col-md-6 col-lg-4">
          <label class="form-label form-label-sm fw-semibold mb-1 font-monospace text-truncate d-block" title="${escapeHtml(label)}">
            ${escapeHtml(label)}:
          </label>
          <input type="text" class="form-control form-control-sm wizard-live-param-input" data-param-name="${escapeHtml(p.name)}" value="${escapeHtml(sampleVal)}">
        </div>
      `;
    })
    .join('');

  // Обработчики изменения значений подстановки
  container.querySelectorAll('.wizard-live-param-input').forEach((inp) => {
    inp.addEventListener('input', updateLivePreviewCommand);
    inp.addEventListener('change', updateLivePreviewCommand);
  });
}

/**
 * Обновление текста готовой команды в Live Preview с подставленными значениями.
 */
function updateLivePreviewCommand() {
  const sampleEl = document.getElementById('wizard-sample-command-preview');
  if (!sampleEl) return;

  const template = currentParsedData?.normalized_template || document.getElementById('wizard-raw-command-input')?.value || '';
  if (!template) {
    sampleEl.textContent = '—';
    return;
  }

  const values = {};
  document.querySelectorAll('.wizard-live-param-input').forEach((inp) => {
    const pName = inp.getAttribute('data-param-name');
    if (pName) {
      values[pName] = inp.value;
    }
  });

  let builtCommand = template;
  for (const [k, v] of Object.entries(values)) {
    builtCommand = builtCommand.replaceAll(`{${k}}`, v);
  }

  sampleEl.textContent = builtCommand;
}

/**
 * Автозаполнение метаданных инструмента на основе рекомендаций парсера.
 * @param {object} parsedResult - Данные из сервера
 */
function autoFillMetadata(parsedResult) {
  const toolIdInp = document.getElementById('wizard-meta-tool-id');
  const nameInp = document.getElementById('wizard-meta-name');
  const typeSel = document.getElementById('wizard-meta-type');
  const entitySel = document.getElementById('wizard-meta-entity');
  const riskSel = document.getElementById('wizard-meta-risk');
  const tagsInp = document.getElementById('wizard-meta-tags');

  if (toolIdInp && (!toolIdInp.value || toolIdInp.value.startsWith('inst_'))) {
    if (parsedResult.suggested_tool_id) toolIdInp.value = parsedResult.suggested_tool_id;
  }
  if (nameInp && !nameInp.value) {
    if (parsedResult.suggested_name) nameInp.value = parsedResult.suggested_name;
  }
  if (typeSel && parsedResult.suggested_tool_type) {
    typeSel.value = parsedResult.suggested_tool_type;
  }
  if (entitySel && parsedResult.suggested_target_entity) {
    entitySel.value = parsedResult.suggested_target_entity;
  }
  if (riskSel && parsedResult.suggested_risk_level) {
    riskSel.value = parsedResult.suggested_risk_level;
  }
  if (tagsInp && (!tagsInp.value || tagsInp.value === '#agent_tool')) {
    if (parsedResult.suggested_tags && parsedResult.suggested_tags.length) {
      tagsInp.value = parsedResult.suggested_tags.join(', ');
    }
  }
}

/**
 * Сохранение сконструированного инструмента в базу данных u177424397_tool_chains (Hostinger MariaDB).
 */
async function handleSaveFromWizard() {
  const saveBtn = document.getElementById('wizard-btn-save-to-db');
  const toolId = document.getElementById('wizard-meta-tool-id')?.value.trim() || '';
  const name = document.getElementById('wizard-meta-name')?.value.trim() || '';
  const toolType = document.getElementById('wizard-meta-type')?.value || 'cmd';
  const targetEntity = document.getElementById('wizard-meta-entity')?.value || 'system';
  const riskLevel = document.getElementById('wizard-meta-risk')?.value || 'safe';
  const desc = document.getElementById('wizard-meta-desc')?.value.trim() || '';
  const tagsRaw = document.getElementById('wizard-meta-tags')?.value || '';

  // В базу данных сохраняем нормализованный шаблон команды (например, net user {user_name} /active:{active})
  const command = currentParsedData?.normalized_template || document.getElementById('wizard-raw-command-input')?.value.trim() || '';

  if (!name || !command) {
    notifyUser('Укажите название инструмента и текст команды', 'warning');
    return;
  }

  const tags = tagsRaw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => (t.startsWith('#') ? t : `#${t}`));

  const payload = {
    tool_id: toolId || undefined,
    name,
    tool_type: toolType,
    command,
    description: desc || `Параметризованная команда для модели: ${command}`,
    target_entity: targetEntity,
    parameters_schema: currentParsedData?.parameters_schema || {},
    risk_level: riskLevel,
    author_agent: 'command_wizard',
    tags: tags.length ? tags : ['#agent_tool', '#wizard_generated'],
  };

  if (saveBtn) saveBtn.disabled = true;

  try {
    const res = await fetch('/api/v1/ai-instruments/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      notifyUser(`Команда '${name}' (${data.tool_id}) сохранена в базе u177424397_tool_chains (Hostinger MariaDB)!`, 'success');
      if (typeof onWizardSaveCallback === 'function') {
        onWizardSaveCallback(data.item);
      }
      if (wizardModalInstance) {
        wizardModalInstance.hide();
      }
    } else {
      throw new Error(data.detail || 'Не удалось сохранить команду');
    }
  } catch (err) {
    notifyUser(`Ошибка сохранения: ${err.message}`, 'danger');
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * Тестовое выполнение сформированной команды с реальными параметрами на хосте Windows.
 */
async function handleExecuteFromWizard() {
  const testBtn = document.getElementById('wizard-btn-execute-test');
  const execOutput = document.getElementById('wizard-exec-output-box');
  const sampleEl = document.getElementById('wizard-sample-command-preview');
  const toolType = document.getElementById('wizard-meta-type')?.value || 'cmd';

  const commandToRun = sampleEl?.textContent.trim();
  if (!commandToRun || commandToRun === '—') {
    notifyUser('Сначала сформируйте команду для запуска', 'warning');
    return;
  }

  if (execOutput) {
    execOutput.style.display = 'block';
    execOutput.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Выполнение команды на хосте...`;
  }

  if (testBtn) testBtn.disabled = true;

  try {
    // Временно сохраняем/запускаем через API execute
    // Собираем значения параметров
    const values = {};
    document.querySelectorAll('.wizard-live-param-input').forEach((inp) => {
      const pName = inp.getAttribute('data-param-name');
      if (pName) values[pName] = inp.value;
    });

    // Сначала сохраняем временный инструмент для проверки
    const tempToolId = `inst_test_${Math.random().toString(36).slice(2, 8)}`;
    const tempPayload = {
      tool_id: tempToolId,
      name: `Тест мастера: ${commandToRun.slice(0, 30)}`,
      tool_type: toolType,
      command: currentParsedData?.normalized_template || commandToRun,
      description: 'Временный запуск из мастера команд',
      target_entity: 'system',
      parameters_schema: currentParsedData?.parameters_schema || {},
      risk_level: 'safe',
      author_agent: 'wizard_test',
    };

    await fetch('/api/v1/ai-instruments/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tempPayload),
    });

    const execRes = await fetch('/api/v1/ai-instruments/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool_id: tempToolId,
        parameters: values,
        timeout_sec: 15,
        as_admin: false,
      }),
    });

    const resData = await execRes.json();
    // Удаляем временный тестовый инструмент
    try {
      await fetch(`/api/v1/ai-instruments/${tempToolId}`, { method: 'DELETE' });
    } catch (_) {}

    if (execOutput) {
      const isSuccess = resData.success && resData.exit_code === 0;
      const statusClass = isSuccess ? 'text-success' : 'text-danger';
      const outputText = resData.stdout || resData.stderr || 'Команда завершилась без вывода в stdout/stderr';

      execOutput.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1">
          <span class="fw-bold ${statusClass}">
            <i class="bi ${isSuccess ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-1"></i>
            Код возврата: ${resData.exit_code} (${resData.duration_ms?.toFixed(1) || 0} ms)
          </span>
          <button type="button" class="btn btn-xs btn-outline-secondary py-0" onclick="document.getElementById('wizard-exec-output-box').style.display='none'">
            Закрыть
          </button>
        </div>
        <pre class="bg-black text-light p-2 rounded mb-0 font-monospace small" style="max-height: 180px; overflow-y: auto;">${escapeHtml(outputText)}</pre>
      `;
    }
  } catch (err) {
    if (execOutput) {
      execOutput.innerHTML = `<div class="text-danger small"><i class="bi bi-x-circle me-1"></i>Сбой выполнения: ${escapeHtml(err.message)}</div>`;
    }
  } finally {
    if (testBtn) testBtn.disabled = false;
  }
}

/**
 * Локальный клиентский парсер для мгновенного отклика при отсутствии связи.
 * @param {string} cmd - Сырая команда
 */
function fallbackClientParse(cmd) {
  const tokenRegex = /\{([a-zA-Z0-9_\-.:=|,]+)\}/g;
  const parameters = [];
  let normTemplate = cmd;
  let match;

  while ((match = tokenRegex.exec(cmd)) !== null) {
    const rawToken = match[0];
    const inner = match[1];
    const isEnum = inner.includes('|') || inner.includes(',');
    let name = inner;
    let options = [];
    let pType = 'string';

    if (isEnum) {
      pType = 'enum';
      const splitChar = inner.includes('|') ? '|' : ',';
      options = inner.split(splitChar).map((s) => s.trim());
      name = options[0] ? `choice_${options.join('_').slice(0, 15)}` : 'choice';
    } else if (inner.includes(':')) {
      const parts = inner.split(':');
      name = parts[0];
      pType = parts[1];
    }

    parameters.push({
      name,
      param_type: pType,
      options,
      default: options[0] || '',
      description: `Параметр ${name}`,
      required: true,
      raw_token: rawToken,
      flag_prefix: '',
    });

    normTemplate = normTemplate.replace(rawToken, `{${name}}`);
  }

  currentParsedData = {
    raw_template: cmd,
    normalized_template: normTemplate,
    parameters,
    parameters_schema: { type: 'object', properties: {} },
  };

  renderParametersTable(parameters);
  renderLivePreviewControls(parameters);
  updateLivePreviewCommand();
}

/**
 * Вставка текста в позицию курсора внутри поля textarea/input.
 * @param {HTMLElement} el - Элемент ввода
 * @param {string} text - Текст для вставки
 */
function insertTextAtCursor(el, text) {
  const start = el.selectionStart || 0;
  const end = el.selectionEnd || 0;
  const val = el.value;
  el.value = val.substring(0, start) + text + val.substring(end);
  el.selectionStart = el.selectionEnd = start + text.length;
  el.focus();
}

/**
 * Экранирование HTML символов.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
