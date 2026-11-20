/**
 * =============================================================================
 * Process Name: Windows MCP Servers - Server Editor Modal Panel
 * =============================================================================
 * Description:
 *   Модуль диалогового окна настройки и регистрации MCP серверов:
 *   переключение типов транспорта (stdio / network), готовые пресеты (Playwright,
 *   Filesystem, Memory, SQLite, Fetch, SSE), валидация JSON env/args,
 *   сохранение и экспресс-проверка соединения из формы.
 *
 * File: panel.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_mcp/panel_modal_server
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { state, apiFetch } from '../common/ui_utils.js';
import { refreshServers } from '../panel_servers/panel.js';

/**
 * Переключение видимости блоков формы в зависимости от выбранного транспорта.
 */
export function onTransportChange() {
  const transport = document.getElementById('mcp-server-transport')?.value || 'stdio';
  const stdioContainer = document.getElementById('mcp-stdio-container');
  const networkContainer = document.getElementById('mcp-network-container');

  if (transport === 'stdio') {
    stdioContainer?.classList.remove('d-none');
    networkContainer?.classList.add('d-none');
  } else {
    stdioContainer?.classList.add('d-none');
    networkContainer?.classList.remove('d-none');
  }
}

/**
 * Применение параметров готового пресета к полям формы.
 * @param {'playwright' | 'filesystem' | 'memory' | 'sqlite' | 'fetch' | 'sse'} presetKey
 */
export function applyPreset(presetKey) {
  const presets = {
    playwright: {
      id: 'playwright',
      name: 'Playwright Browser MCP',
      description: 'Управление веб-браузером, навигация, клики, скриншоты и парсинг страниц через Playwright.',
      transport: 'stdio',
      command: 'npx',
      args: '@playwright/mcp@latest',
      env: ''
    },
    filesystem: {
      id: 'filesystem',
      name: 'Filesystem MCP',
      description: 'Безопасное чтение, запись и навигация по каталогам и файлам на диске.',
      transport: 'stdio',
      command: 'npx',
      args: '-y @modelcontextprotocol/server-filesystem ./data',
      env: ''
    },
    memory: {
      id: 'memory',
      name: 'Knowledge Graph Memory MCP',
      description: 'Хранилище графа знаний и ассоциативная память для ИИ-агентов.',
      transport: 'stdio',
      command: 'npx',
      args: '-y @modelcontextprotocol/server-memory',
      env: ''
    },
    sqlite: {
      id: 'sqlite',
      name: 'SQLite Database MCP',
      description: 'Выполнение запросов, исследование схемы и инспекция таблиц SQLite базы данных.',
      transport: 'stdio',
      command: 'uvx',
      args: 'mcp-server-sqlite --db-path ./data/database.sqlite',
      env: ''
    },
    fetch: {
      id: 'fetch',
      name: 'Fetch / Web Request MCP',
      description: 'Преобразование HTML веб-страниц в Markdown и выполнение HTTP-запросов.',
      transport: 'stdio',
      command: 'uvx',
      args: 'mcp-server-fetch',
      env: ''
    },
    sse: {
      id: 'remote_mcp',
      name: 'Remote SSE MCP Server',
      description: 'Удаленный MCP-сервер, доступный по протоколу Server-Sent Events (SSE).',
      transport: 'sse',
      url: 'http://localhost:8080/sse'
    }
  };

  const p = presets[presetKey];
  if (!p) return;

  const idEl = document.getElementById('mcp-server-id');
  const nameEl = document.getElementById('mcp-server-name');
  const descEl = document.getElementById('mcp-server-desc');
  const transportEl = document.getElementById('mcp-server-transport');
  const cmdEl = document.getElementById('mcp-server-command');
  const argsEl = document.getElementById('mcp-server-args');
  const urlEl = document.getElementById('mcp-server-url');
  const envEl = document.getElementById('mcp-server-env');

  if (idEl && document.getElementById('mcp-form-mode')?.value === 'create') idEl.value = p.id;
  if (nameEl) nameEl.value = p.name || '';
  if (descEl) descEl.value = p.description || '';
  if (transportEl) transportEl.value = p.transport || 'stdio';
  if (cmdEl) cmdEl.value = p.command || '';
  if (argsEl) argsEl.value = p.args || '';
  if (urlEl) urlEl.value = p.url || '';
  if (envEl) envEl.value = p.env || '';

  onTransportChange();
}

/**
 * Открытие диалогового окна создания нового MCP сервера.
 */
export function openCreateModal() {
  const form = document.getElementById('mcp-server-form');
  if (form) form.reset();

  const titleText = document.getElementById('mcp-modal-title-text');
  if (titleText) titleText.textContent = 'Добавление нового MCP сервера';

  const modeInput = document.getElementById('mcp-form-mode');
  if (modeInput) modeInput.value = 'create';

  const idInput = document.getElementById('mcp-server-id');
  if (idInput) {
    idInput.removeAttribute('readonly');
    idInput.classList.remove('bg-secondary');
  }

  const presetContainer = document.getElementById('mcp-preset-container');
  if (presetContainer) presetContainer.classList.remove('d-none');

  const enabledCheckbox = document.getElementById('mcp-server-enabled');
  if (enabledCheckbox) enabledCheckbox.checked = true;

  applyPreset('playwright');
}

/**
 * Открытие диалогового окна редактирования существующего MCP сервера.
 * @param {string} serverId - Идентификатор сервера
 */
export function openEditModal(serverId) {
  const server = state.servers.find(s => s.id === serverId);
  if (!server) return;

  const titleText = document.getElementById('mcp-modal-title-text');
  if (titleText) titleText.textContent = `Редактирование: ${server.name || server.id}`;

  const modeInput = document.getElementById('mcp-form-mode');
  if (modeInput) modeInput.value = 'edit';

  const presetContainer = document.getElementById('mcp-preset-container');
  if (presetContainer) presetContainer.classList.add('d-none');

  const idInput = document.getElementById('mcp-server-id');
  if (idInput) {
    idInput.value = server.id;
    idInput.setAttribute('readonly', 'true');
    idInput.classList.add('bg-secondary');
  }

  const nameInput = document.getElementById('mcp-server-name');
  if (nameInput) nameInput.value = server.name || '';

  const descInput = document.getElementById('mcp-server-desc');
  if (descInput) descInput.value = server.description || '';

  const transportInput = document.getElementById('mcp-server-transport');
  if (transportInput) transportInput.value = server.transport || 'stdio';

  const cmdInput = document.getElementById('mcp-server-command');
  if (cmdInput) cmdInput.value = server.command || '';

  const argsInput = document.getElementById('mcp-server-args');
  if (argsInput) {
    argsInput.value = Array.isArray(server.args) ? server.args.join(' ') : (server.args || '');
  }

  const urlInput = document.getElementById('mcp-server-url');
  if (urlInput) urlInput.value = server.url || '';

  const envInput = document.getElementById('mcp-server-env');
  if (envInput) {
    envInput.value = server.env ? JSON.stringify(server.env, null, 2) : '';
  }

  const enabledCheckbox = document.getElementById('mcp-server-enabled');
  if (enabledCheckbox) enabledCheckbox.checked = server.enabled !== false;

  onTransportChange();

  const modalEl = document.getElementById('mcpServerModal');
  if (modalEl && window.bootstrap) {
    const modal = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
    modal.show();
  }
}

/**
 * Сохранение параметров сервера (создание или обновление).
 * @param {Event} [event]
 */
export async function saveServer(event) {
  if (event) event.preventDefault();

  const mode = document.getElementById('mcp-form-mode')?.value || 'create';
  const serverId = document.getElementById('mcp-server-id')?.value.trim();
  const name = document.getElementById('mcp-server-name')?.value.trim();
  const description = document.getElementById('mcp-server-desc')?.value.trim();
  const transport = document.getElementById('mcp-server-transport')?.value || 'stdio';
  const enabled = document.getElementById('mcp-server-enabled')?.checked ?? true;
  const command = document.getElementById('mcp-server-command')?.value.trim();
  const argsRaw = document.getElementById('mcp-server-args')?.value.trim();
  const url = document.getElementById('mcp-server-url')?.value.trim();
  const envRaw = document.getElementById('mcp-server-env')?.value.trim();

  if (!serverId) {
    window.showToast?.('Укажите ID сервера', 'warning') || alert('Укажите ID сервера');
    return;
  }

  // Парсинг аргументов
  let args = [];
  if (argsRaw) {
    if (argsRaw.startsWith('[') && argsRaw.endsWith(']')) {
      try {
        args = JSON.parse(argsRaw);
      } catch {
        args = argsRaw.split(/\s+/).filter(Boolean);
      }
    } else {
      args = argsRaw.split(/\s+/).filter(Boolean);
    }
  }

  // Парсинг переменных окружения
  let env = {};
  if (envRaw) {
    try {
      env = JSON.parse(envRaw);
    } catch (err) {
      const msg = 'Ошибка формата JSON в переменных окружения: ' + err.message;
      window.showToast?.(msg, 'danger') || alert(msg);
      return;
    }
  }

  const payload = {
    id: serverId,
    name: name || serverId,
    description: description,
    transport: transport,
    enabled: enabled,
    command: command,
    args: args,
    url: url,
    env: env
  };

  const saveBtn = document.getElementById('mcp-btn-save-server');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Сохранение...';
  }

  try {
    const endpoint = mode === 'create'
      ? '/api/v1/admin/mcp/servers'
      : `/api/v1/admin/mcp/servers/${encodeURIComponent(serverId)}`;

    const method = mode === 'create' ? 'POST' : 'PUT';

    const res = await apiFetch(endpoint, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }

    const modalEl = document.getElementById('mcpServerModal');
    if (modalEl && window.bootstrap) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      modal?.hide();
    }

    await refreshServers();
  } catch (err) {
    const msg = `Ошибка сохранения MCP сервера: ${err.message}`;
    window.showToast?.(msg, 'danger') || alert(msg);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = 'Сохранить';
    }
  }
}

/**
 * Тестирование конфигурации сервера непосредственно из формы редактирования.
 */
export async function testCurrentForm() {
  const serverId = document.getElementById('mcp-server-id')?.value.trim() || 'test_server';
  const transport = document.getElementById('mcp-server-transport')?.value || 'stdio';
  const command = document.getElementById('mcp-server-command')?.value.trim();
  const argsRaw = document.getElementById('mcp-server-args')?.value.trim();
  const url = document.getElementById('mcp-server-url')?.value.trim();
  const envRaw = document.getElementById('mcp-server-env')?.value.trim();

  let args = [];
  if (argsRaw) {
    if (argsRaw.startsWith('[') && argsRaw.endsWith(']')) {
      try { args = JSON.parse(argsRaw); } catch { args = argsRaw.split(/\s+/).filter(Boolean); }
    } else {
      args = argsRaw.split(/\s+/).filter(Boolean);
    }
  }

  let env = {};
  if (envRaw) {
    try {
      env = JSON.parse(envRaw);
    } catch (e) {
      window.showToast?.('Неверный формат JSON в env', 'danger') || alert('Неверный формат JSON в env');
      return;
    }
  }

  const testBtn = document.getElementById('btn-test-modal-server');
  if (testBtn) {
    testBtn.disabled = true;
    testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Тест...';
  }

  try {
    const res = await apiFetch('/api/v1/admin/mcp/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: serverId,
        transport: transport,
        command: command,
        args: args,
        url: url,
        env: env
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      window.showToast?.(`✅ Подключение успешно! (${data.latency_ms} ms)\nНайдено инструментов: ${data.tools_count}`, 'success');
    } else {
      window.showToast?.(`❌ Ошибка проверки подключения:\n${data.message}`, 'danger');
    }
  } catch (err) {
    window.showToast?.(`❌ Ошибка запроса: ${err.message}`, 'danger');
  } finally {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerHTML = '<i class="bi bi-play-circle"></i> Проверить подключение';
    }
  }
}
