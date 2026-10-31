/**
 * =============================================================================
 * Название: Панель дерева каналов журналов Windows
 * =============================================================================
 * Описание:
 *   Сканирование доступных источников и каналов событий Windows, группировка
 *   по категориям, отображение количества записей и интерактивные подсказки.
 *
 * Файл: apps/windows/api/webgui/tab_system_logs/panel_channels/panel.js
 * Пакет: windows/api/webgui/tab_system_logs
 * Автор: hypo69
 * Updated: 2026-10-31 18:33:00
 * =============================================================================
 */

import { escapeHtml } from '../common/ui_utils.js';

let currentChannel = 'System';
let currentFilePath = '';
let cachedChannels = [];
let globalTooltipEl = null;
let savedChannelSelectCallback = null;

export function getCurrentChannel() {
  return currentChannel;
}

export function getCurrentFilePath() {
  return currentFilePath;
}

export function setCurrentChannel(channel, filePath = '') {
  currentChannel = channel;
  currentFilePath = filePath;
}

export function getCachedChannels() {
  return cachedChannels;
}

/**
 * Получает или создает всплывающий элемент тултипа для описания журнала.
 * @returns {HTMLElement} Элемент подсказки.
 */
function getOrCreateTooltipEl() {
  if (!globalTooltipEl) {
    globalTooltipEl = document.createElement('div');
    globalTooltipEl.className = 'slc-tooltip-popup';
    document.body.appendChild(globalTooltipEl);
  }
  return globalTooltipEl;
}

/**
 * Позиционирует тултип рядом с курсором мыши с контролем границ окна.
 * @param {MouseEvent} e - Событие мыши.
 * @param {HTMLElement} tip - Элемент тултипа.
 */
function positionTooltip(e, tip) {
  const margin = 12;
  let x = e.clientX + margin;
  let y = e.clientY + margin;

  const tipRect = tip.getBoundingClientRect();
  if (x + tipRect.width > window.innerWidth) {
    x = e.clientX - tipRect.width - margin;
  }
  if (y + tipRect.height > window.innerHeight) {
    y = e.clientY - tipRect.height - margin;
  }

  tip.style.left = `${Math.max(10, x)}px`;
  tip.style.top = `${Math.max(10, y)}px`;
}

/**
 * Отображает всплывающее описание канала при наведении курсора.
 * @param {MouseEvent} e - Событие мыши.
 * @param {Object} channel - Метаданные канала.
 */
export function showChannelTooltip(e, channel) {
  const tip = getOrCreateTooltipEl();
  const countFormatted = (channel.record_count || 0).toLocaleString();
  const descText = channel.description || 'Служебный журнал операционной системы Windows.';
  const typeLabel = channel.source_type === 'channel' ? 'Windows Event Channel' : 'Log File';

  tip.innerHTML = `
    <div class="slc-tooltip-title">
      <i class="bi bi-info-circle text-info"></i>
      <span>${escapeHtml(channel.display_name)}</span>
    </div>
    <div style="color: #cbd5e1; margin-bottom: 0.35rem;">${escapeHtml(descText)}</div>
    <div class="slc-tooltip-meta">
      <span><strong class="text-info">${countFormatted}</strong> записей</span>
      <span class="text-muted font-monospace">${typeLabel}</span>
    </div>
  `;

  tip.classList.add('show');
  positionTooltip(e, tip);
}

/**
 * Скрывает всплывающую подсказку описания канала.
 */
export function hideChannelTooltip() {
  if (globalTooltipEl) {
    globalTooltipEl.classList.remove('show');
  }
}

/**
 * Выполняет сканирование источников и каналов событий операционной системы.
 * @param {boolean} [force=false] - Принудительное сканирование с обновлением на бэкенде.
 */
export async function performSystemScan(force = false) {
  try {
    const response = await fetch(`/api/v1/system_logs/scan?force=${force}`);
    if (!response.ok) return;
    const data = await response.json();

    cachedChannels = data.channels || [];
    const activeChannels = cachedChannels.filter((c) => (c.record_count || 0) > 0);
    const sourcesBadge = document.getElementById('slc-stat-sources');
    const countBadge = document.getElementById('slc-channel-count-badge');

    if (sourcesBadge) {
      sourcesBadge.textContent = `${activeChannels.length.toLocaleString()} active / ${data.total_sources.toLocaleString()} sources`;
    }
    if (countBadge) {
      countBadge.textContent = String(activeChannels.length);
    }

    renderChannelsTree(savedChannelSelectCallback);
  } catch (err) {
    console.warn('[SystemLogs] Ошибка сканирования источников журналов:', err);
  }
}

/**
 * Отрисовывает дерево каналов в боковой панели с фильтрацией и счетчиками записей.
 * @param {Function} [onChannelSelect] - Функция обратного вызова при выборе канала.
 */
export function renderChannelsTree(onChannelSelect) {
  if (onChannelSelect) {
    savedChannelSelectCallback = onChannelSelect;
  }
  const handler = onChannelSelect || savedChannelSelectCallback;
  const container = document.getElementById('slc-channel-tree-container');
  const filterInput = document.getElementById('slc-channel-filter-input');
  const filterText = filterInput ? filterInput.value.trim().toLowerCase() : '';

  if (!container) return;
  container.innerHTML = '';

  const filtered = cachedChannels.filter((c) => {
    // Исключаем пустые каналы с 0 записей
    if (Number(c.record_count) === 0) return false;

    if (!filterText) return true;
    return (
      c.channel_name.toLowerCase().includes(filterText) ||
      c.display_name.toLowerCase().includes(filterText) ||
      (c.description && c.description.toLowerCase().includes(filterText)) ||
      (c.category && c.category.toLowerCase().includes(filterText))
    );
  });

  // Группировка каналов по категориям
  const grouped = {};
  filtered.forEach((c) => {
    const cat = c.category || 'Windows Event Log';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(c);
  });

  const categoryIcons = {
    'Windows Event Log': '🛡️',
    'Windows OS Logs': '📁',
    'Application Logs': '💻',
    'AI-Windows-Admin Logs': '🤖',
  };

  Object.keys(grouped).forEach((catName) => {
    const catHeader = document.createElement('div');
    catHeader.className = 'd-flex justify-content-between align-items-center px-2 py-1 mt-2 mb-1 rounded bg-dark border border-secondary text-info small fw-bold';
    const icon = categoryIcons[catName] || '📜';
    catHeader.innerHTML = `
      <span>${icon} ${escapeHtml(catName)}</span>
      <span class="badge bg-secondary font-monospace">${grouped[catName].length}</span>
    `;
    container.appendChild(catHeader);

    grouped[catName].slice(0, 400).forEach((c) => {
      const item = document.createElement('div');
      const isActive = (c.channel_name === currentChannel && !currentFilePath) || (currentFilePath && currentFilePath === c.location);
      item.className = `slc-tree-item ${isActive ? 'active' : ''}`;

      let subBadge = '0';
      let badgeStyle = 'bg-dark text-secondary';
      if (c.record_count > 0) {
        subBadge = c.record_count >= 1000 ? `${(c.record_count / 1000).toFixed(1)}k` : String(c.record_count);
        badgeStyle = c.record_count > 1000 ? 'bg-primary text-white' : 'bg-dark text-info border border-secondary';
      } else if (c.source_type !== 'channel') {
        subBadge = 'FILE';
      }

      item.innerHTML = `
        <span class="text-truncate me-2" style="max-width: 175px;">${escapeHtml(c.display_name)}</span>
        <span class="badge ${badgeStyle} font-monospace" style="font-size: 0.72rem; min-width: 32px; text-align: right;">${subBadge}</span>
      `;

      item.onmouseenter = (e) => showChannelTooltip(e, c);
      item.onmousemove = (e) => {
        const tip = getOrCreateTooltipEl();
        if (tip.classList.contains('show')) positionTooltip(e, tip);
      };
      item.onmouseleave = () => hideChannelTooltip();

      item.onclick = () => {
        hideChannelTooltip();
        if (c.source_type === 'channel') {
          currentChannel = c.channel_name;
          currentFilePath = '';
        } else {
          currentChannel = c.display_name;
          currentFilePath = c.location;
        }
        const statChan = document.getElementById('slc-stat-channel');
        if (statChan) statChan.textContent = c.display_name;
        renderChannelsTree(handler);
        if (typeof handler === 'function') {
          handler(currentChannel, currentFilePath);
        }
      };
      container.appendChild(item);
    });
  });
}
