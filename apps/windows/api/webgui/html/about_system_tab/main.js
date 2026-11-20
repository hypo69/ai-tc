/* =============================================================================
 * File: main.js
 * Project: ai-tc
 * Package: windows/api/webgui/html/about_system_tab
 * Author: hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 * Ленивая загрузка данных о системе.
 * При первом открытии вкладки отправляется запрос GET /api/v1/about-system/bundle.
 * Результат выводится в консоль через logger.console() и отображается в UI.
 */

let hasLoadedAboutSystem = false;

/**
 * Инициализирует вкладку "About System".
 * Вызывается LazyTabLoader после загрузки HTML‑разметки.
 */
export async function initAboutSystemTab() {
  if (hasLoadedAboutSystem) {
    logger.console('About‑System: данные уже загружены – запрос пропущен');
    return;
  }
  try {
    logger.console('About‑System: отправляем запрос /api/v1/about-system/bundle');
    const response = await fetch('/api/v1/about-system/bundle', {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      // Явный таймаут 10 сек (см. CODE_STANDARD.md)
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    logger.console('About‑System: получен ответ', data);
    const container = document.getElementById('about-system-content');
    if (container) {
      container.innerHTML = `<pre style="font-family: monospace;">${JSON.stringify(data, null, 2)}</pre>`;
    }
    hasLoadedAboutSystem = true;
  } catch (err) {
    logger.console(`About‑System: ошибка загрузки – ${err}`);
    const container = document.getElementById('about-system-content');
    if (container) {
      container.innerHTML = `<div class="alert alert-danger">Не удалось загрузить данные о системе.</div>`;
    }
  }
}
