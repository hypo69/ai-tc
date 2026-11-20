/**
 * =============================================================================
 * Process Name: Windows AI Agents - Common UI Utilities & State
 * =============================================================================
 * Description:
 *   Реактивное состояние, сетевой клиент fetchJson, всплывающие уведомления
 *   и загрузка данных реестра ИИ-агентов, доступных инструментов и провайдеров.
 *
 * File: ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_agents/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Глобальное реактивное состояние вкладки ИИ-агентов.
 */
export const state = {
  agents: [],
  tools: [],
  providers: {},
  currentFilter: 'all',
  activeSandboxAgent: null,
  lastGeneratedSpec: null,
  isEventsBound: false
};

/**
 * Выполнение HTTP JSON запроса через обертку window.api или стандартный fetch.
 * @param {string} endpoint - Путь к API эндпоинту
 * @param {RequestInit} [options={}] - Параметры запроса fetch
 * @returns {Promise<any>} Распарсенный ответ JSON
 */
export async function fetchJson(endpoint, options = {}) {
  if (window.api && typeof window.api.fetch === 'function') {
    return await window.api.fetch(endpoint, options);
  }
  const response = await fetch(endpoint, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return await response.json();
}

/**
 * Получение человекочитаемого отображаемого имени провайдера.
 * @param {string} provKey - Идентификатор провайдера (gemini, foundry, ollama и т.д.)
 * @returns {string} Имя провайдера
 */
export function getProviderDisplayName(provKey) {
  return state.providers[provKey]?.name ?? provKey;
}

/**
 * Отображение всплывающего уведомления toast.
 * @param {string} message - Текст уведомления
 * @param {'info' | 'success' | 'warning' | 'danger'} [type='info'] - Тип уведомления Bootstrap
 */
export function showToast(message, type = 'info') {
  if (typeof window.showModelsNotification === 'function') {
    window.showModelsNotification(message, type);
    return;
  }
  if (typeof window.showToast === 'function') {
    window.showToast(message, type);
    return;
  }
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} position-fixed bottom-0 end-0 m-3 shadow`;
  alertDiv.style.zIndex = '9999';
  alertDiv.textContent = message;
  document.body.appendChild(alertDiv);
  setTimeout(() => alertDiv.remove(), 3500);
}
