/**
 * =============================================================================
 * Process Name: Windows Chat - UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные утилиты для форматирования сообщений, парсинга разметки
 *   Markdown и генерации кратких заголовков сессий чата.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_chat/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

export const STORAGE_KEY_SESSIONS = 'ai_tc_chat_sessions_v2';
export const STORAGE_KEY_ACTIVE_SESSION_ID = 'ai_tc_active_session_id';
export const STORAGE_KEY_SIDEBAR_COLLAPSED = 'ai_tc_chat_sidebar_collapsed';
export const LEGACY_STORAGE_KEY = 'ai_tc_chat_history';
export const CACHE_TAG = 'chat';

/**
 * Преобразует текст с базовой разметкой Markdown или блоками кода в безопасный HTML.
 * @param {string} text - Исходный текст.
 * @returns {string} Форматированная HTML-строка.
 */
export function parseContentToHtml(text) {
  if (!text) return '';

  let cleaned = text.trim();
  const codeBlockRegex = /^```(?:html|xml)?\s*([\s\S]*?)\s*```$/i;
  const match = cleaned.match(codeBlockRegex);
  if (match) {
    cleaned = match[1];
  }

  if (window.marked && typeof window.marked.parse === 'function') {
    return window.marked.parse(cleaned);
  }

  return cleaned
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

/**
 * Генерирует лаконичный заголовок диалога на основе первого запроса пользователя.
 * @param {string} prompt - Текст запроса.
 * @returns {string} Человекочитаемый заголовок сессии.
 */
export function generateSessionTitle(prompt) {
  if (!prompt || typeof prompt !== 'string') return 'Новый чат';

  let clean = prompt
    .replace(/^```[\s\S]*?```/g, '')
    .replace(/<[^>]*>/g, '')
    .replace(/[*_#`[\]()]/g, '')
    .trim();

  if (!clean) return 'Новый чат';

  // Выбираем первую строку или первое предложение
  const firstLine = clean.split('\n')[0].trim();
  const sentenceMatch = firstLine.match(/^(.+?)(?:[.!?]|$)/);
  let text = sentenceMatch ? sentenceMatch[1].trim() : firstLine;

  if (text.length > 36) {
    text = text.substring(0, 36).trim();
    const lastSpace = text.lastIndexOf(' ');
    if (lastSpace > 15) {
      text = text.substring(0, lastSpace);
    }
    text += '...';
  }

  // Переводим первый символ в верхний регистр
  return text.charAt(0).toUpperCase() + text.slice(1);
}
