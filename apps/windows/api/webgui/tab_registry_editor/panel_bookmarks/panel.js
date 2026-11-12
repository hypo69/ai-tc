/**
 * Модуль панели закладок часто используемых веток реестра.
 * Файл: apps/windows/api/webgui/tab_registry_viewer/panel_bookmarks/panel.js
 * Updated: 2026-10-17 01:55:00
 */

/**
 * Загружает и отрисовывает кнопки закладок реестра.
 * @param {Function} onNavigate - Коллбек перехода по ветке и пути.
 */
export async function loadBookmarks(onNavigate) {
  const container = document.getElementById('reg-bookmarks-container');
  if (!container) return;

  try {
    const res = await fetch('/api/registry/bookmarks');
    if (!res.ok) throw new Error('Bookmarks API error');
    const data = await res.json();
    const bookmarks = data?.bookmarks || [];

    container.innerHTML = `
      <span class="text-muted small me-2"><i class="bi bi-bookmark-star-fill text-warning me-1"></i> Закладки:</span>
    ` + bookmarks.map(b => `
      <button class="reg-bookmark-btn" data-hive="${b.hive}" data-path="${b.path}" title="${b.description || ''}">
        <span>${b.icon || '📌'}</span> ${b.title}
      </button>
    `).join('');

    container.querySelectorAll('.reg-bookmark-btn').forEach(btn => {
      btn.onclick = () => {
        const h = btn.getAttribute('data-hive');
        const p = btn.getAttribute('data-path');
        if (onNavigate) onNavigate(h, p);
      };
    });
  } catch (e) {
    console.warn('[RegistryViewerTab] Failed to load bookmarks:', e);
  }
}
