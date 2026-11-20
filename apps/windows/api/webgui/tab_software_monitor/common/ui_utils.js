/**
 * =============================================================================
 * Process Name: Windows Software Scanner - UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные утилиты динамической загрузки скриптов с дедупликацией,
 *   асинхронной подгрузки HTML-фрагментов и безопасного экранирования HTML.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: apps/windows/api/webgui/tab_software_scanner/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

const pendingSubPaneLoads = new Map();

/**
 * Экранирует HTML-сущности для защиты от XSS.
 * @param {*} str - Исходная строка.
 * @returns {string} Экранированная строка.
 */
export function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Загружает внешний JavaScript-скрипт с дедупликацией DOM-тегов.
 * @param {string} src - Путь к скрипту.
 * @returns {Promise<void>}
 */
export function loadScript(src) {
  return new Promise((resolve) => {
    const cleanSrc = src.split('?')[0];
    const existing = document.querySelector(`script[src^="${cleanSrc}"]`);
    if (existing) {
      resolve();
      return;
    }
    const s = document.createElement('script');
    s.type = 'module';
    s.src = src;
    s.onload = () => resolve();
    s.onerror = (err) => {
      console.warn(`[SoftwareHub] Не удалось загрузить скрипт ${src}:`, err);
      resolve();
    };
    document.body.appendChild(s);
  });
}

/**
 * Асинхронно подгружает HTML разметку и модуль скрипта для субпанели.
 * @param {string} containerId - ID контейнера.
 * @param {string} htmlUrl - URL разметки.
 * @param {string|null} jsUrl - URL скрипта.
 * @param {string|null} initFnName - Имя глобальной функции инициализации.
 */
export async function loadSubPane(containerId, htmlUrl, jsUrl, initFnName) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (pendingSubPaneLoads.has(containerId)) {
    return await pendingSubPaneLoads.get(containerId);
  }

  const loadPromise = (async () => {
    const hasRealContent = container.children && container.children.length > 0;
    if (!hasRealContent) {
      try {
        const res = await fetch(`${htmlUrl}?v=${Date.now()}`);
        if (!res.ok) {
          console.warn(`[SoftwareHub] Сбой загрузки HTML ${htmlUrl}: HTTP ${res.status}`);
          return;
        }
        container.innerHTML = await res.text();
      } catch (err) {
        console.warn(`[SoftwareHub] Ошибка загрузки HTML для ${containerId}:`, err);
        return;
      }
    }

    if (jsUrl) {
      try {
        await loadScript(`${jsUrl}?v=${Date.now()}`);
        if (initFnName && typeof window[initFnName] === 'function') {
          try {
            window[initFnName]();
          } catch (err) {
            console.debug(`[SoftwareHub] Ошибка вызова ${initFnName}:`, err);
          }
        }
      } catch (err) {
        console.warn(`[SoftwareHub] Ошибка скрипта для ${containerId}:`, err);
      }
    }
  })();

  pendingSubPaneLoads.set(containerId, loadPromise);
  try {
    await loadPromise;
  } finally {
    pendingSubPaneLoads.delete(containerId);
  }
}
