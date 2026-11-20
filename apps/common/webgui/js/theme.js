/**
 * =============================================================================
 * Process Name: Windows Js - Theme Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля theme и интеграции с ThemeEngine.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/js/theme.js?v=20261004_v17" type="module"></script>
 *
 *   JavaScript Import:
 *     import { getThemeMode, getResolvedTheme, setTheme, themeEngine } from '/windows/api/webgui/js/theme.js';
 *
 * File: theme.js
 * Project: ai-tc
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

import {
  themeEngine,
  ThemeEngine,
  THEME_STORAGE_KEY,
  CUSTOM_THEMES_STORAGE_KEY,
  THEMES_CATALOG_STORAGE_KEY,
  CUSTOM_OVERRIDES_STORAGE_KEY,
  DEFAULT_THEME_MODE,
  BUILTIN_THEMES,
} from './theme-engine.js';

/**
 * Получает сохранённый режим темы пользователя.
 * @returns {string}
 */
export function getThemeMode() {
  return themeEngine.getSavedMode();
}

/**
 * Разрешает эффективную тему оформления ('light' | 'dark' | 'brick' | 'terminal').
 * @param {string} [mode]
 * @returns {string}
 */
export function getResolvedTheme(mode = getThemeMode()) {
  return themeEngine.resolveTheme(mode);
}

/**
 * Устанавливает тему оформления и применяет её ко всем элементам интерфейса.
 * @param {string} mode
 */
export function setTheme(mode) {
  themeEngine.applyTheme(mode);
}

/**
 * Инициализирует менеджер тем и слушатели событий при загрузке страницы.
 */
export function initTheme() {
  themeEngine.init();
}

/**
 * Создает дочернюю тему на базе стандартной темы.
 * @param {Object} params
 * @returns {Object}
 */
export function createChildTheme(params) {
  return themeEngine.createChildTheme(params);
}

/**
 * Обновляет дочернюю тему.
 * @param {string} id
 * @param {Object} params
 * @returns {Object}
 */
export function updateChildTheme(id, params) {
  return themeEngine.updateChildTheme(id, params);
}

/**
 * Удаляет дочернюю тему.
 * @param {string} id
 * @returns {boolean}
 */
export function deleteChildTheme(id) {
  return themeEngine.deleteChildTheme(id);
}

/**
 * Сбрасывает параметры дочерней темы к родительской.
 * @param {string} id
 * @returns {Object|null}
 */
export function resetChildThemeToParent(id) {
  return themeEngine.resetChildThemeToParent(id);
}

/**
 * Возвращает список всех дочерних тем.
 * @returns {Array<Object>}
 */
export function getCustomThemes() {
  return themeEngine.getCustomThemes();
}

/**
 * Возвращает дочернюю тему по ID.
 * @param {string} id
 * @returns {Object|null}
 */
export function getChildTheme(id) {
  return themeEngine.getChildTheme(id);
}

/**
 * Возвращает список всех стандартных тем.
 * @returns {Array<Object>}
 */
export function getStandardThemes() {
  return themeEngine.getStandardThemes();
}

/**
 * Проверяет, является ли тема стандартной.
 * @param {string} id
 * @returns {boolean}
 */
export function isBuiltinTheme(id) {
  return themeEngine.isBuiltinTheme(id);
}

/**
 * Проверяет, является ли тема дочерней.
 * @param {string} id
 * @returns {boolean}
 */
export function isChildTheme(id) {
  return themeEngine.isChildTheme(id);
}

/**
 * Применяет кастомные переопределения токенов оформления.
 * @param {Object<string, string>} tokens
 * @param {boolean} [save=true]
 */
export function applyCustomOverrides(tokens, save = true) {
  themeEngine.applyCustomOverrides(tokens, save);
}

/**
 * Сбрасывает сохраненные кастомные переопределения оформления.
 */
export function clearCustomOverrides() {
  themeEngine.clearCustomOverrides();
}

/**
 * Возвращает сохраненные кастомные переопределения оформления.
 * @returns {Object<string, string>|null}
 */
export function getCustomOverrides() {
  return themeEngine.getCustomOverrides();
}

/**
 * Применяет тему во временном режиме предварительного просмотра без сохранения в LocalStorage.
 * @param {string} mode
 */
export function previewTheme(mode) {
  themeEngine.previewTheme(mode);
}

/**
 * Восстанавливает сохраненную тему пользователя и сбрасывает временные стили.
 */
export function restoreUserTheme() {
  themeEngine.restoreUserTheme();
}

// Экспорт синглтона и констант
export {
  themeEngine,
  ThemeEngine,
  THEME_STORAGE_KEY,
  CUSTOM_THEMES_STORAGE_KEY,
  THEMES_CATALOG_STORAGE_KEY,
  CUSTOM_OVERRIDES_STORAGE_KEY,
  DEFAULT_THEME_MODE,
  BUILTIN_THEMES,
};

// Экспорт в глобальный объект window
if (typeof window !== 'undefined') {
  window.setTheme = setTheme;
  window.getThemeMode = getThemeMode;
  window.getResolvedTheme = getResolvedTheme;
  window.initTheme = initTheme;
  window.createChildTheme = createChildTheme;
  window.updateChildTheme = updateChildTheme;
  window.deleteChildTheme = deleteChildTheme;
  window.resetChildThemeToParent = resetChildThemeToParent;
  window.getCustomThemes = getCustomThemes;
  window.getChildTheme = getChildTheme;
  window.getStandardThemes = getStandardThemes;
  window.isBuiltinTheme = isBuiltinTheme;
  window.isChildTheme = isChildTheme;
  window.applyCustomOverrides = applyCustomOverrides;
  window.clearCustomOverrides = clearCustomOverrides;
  window.getCustomOverrides = getCustomOverrides;
  window.previewTheme = previewTheme;
  window.restoreUserTheme = restoreUserTheme;
  window.themeEngine = themeEngine;
  window.ThemeEngine = ThemeEngine;
}

