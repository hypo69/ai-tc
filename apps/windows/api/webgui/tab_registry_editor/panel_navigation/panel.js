/**
 * Модуль навигации по ульям (hives) и путям реестра.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/panel_navigation/panel.js
 * Updated: 2026-10-17 01:55:00
 */

let currentHive = 'HKEY_LOCAL_MACHINE';
let currentPath = 'SOFTWARE';

export function getCurrentHive() {
  return currentHive;
}

export function getCurrentPath() {
  return currentPath;
}

export function setCurrentHive(hive) {
  currentHive = hive;
}

export function setCurrentPath(path) {
  currentPath = path;
}

/**
 * Переход к указанному разделу реестра.
 * @param {string} hive - Улей реестра (HKLM, HKCU и т.д.).
 * @param {string} path - Путь к ключу.
 * @param {Function} [onLoadKey] - Функция загрузки содержимого ключа.
 */
export async function navigateTo(hive, path, onLoadKey) {
  currentHive = hive;
  currentPath = (path || '').trim().replace(/^[\\\/]+|[\\\/]+$/g, '');

  const hiveSelect = document.getElementById('reg-hive-select');
  const pathInput = document.getElementById('reg-path-input');
  if (hiveSelect) hiveSelect.value = currentHive;
  if (pathInput) pathInput.value = currentPath;

  if (onLoadKey) {
    await onLoadKey(currentHive, currentPath);
  }
}

/**
 * Переход на один уровень вверх в дереве разделов.
 * @param {Function} [onNavigate] - Функция перехода.
 */
export function goUp(onNavigate) {
  if (!currentPath) return;
  const parts = currentPath.split('\\');
  parts.pop();
  const newPath = parts.join('\\');
  if (onNavigate) {
    onNavigate(currentHive, newPath);
  }
}

/**
 * Копирует текущий полный путь раздела реестра в буфер обмена.
 */
export function copyCurrentPath() {
  const full = `${currentHive}\\${currentPath}`.replace(/\\+$/, '');
  if (navigator.clipboard) {
    navigator.clipboard.writeText(full).then(() => {
      const btn = document.getElementById('btn-reg-copy-path');
      if (btn) {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check me-1"></i> Скопировано!';
        setTimeout(() => { btn.innerHTML = orig; }, 1500);
      }
    });
  }
}
