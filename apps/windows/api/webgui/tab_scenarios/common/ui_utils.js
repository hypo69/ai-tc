/**
 * =============================================================================
 * Название: Вспомогательные утилиты интерфейса вкладки сценариев
 * =============================================================================
 * Описание:
 *   Экранирование HTML, универсальное форматирование Markdown с сохранением HTML,
 *   разбор управляющих тегов ответов и константы иконок состояний.
 *
 * Файл: apps/windows/api/webgui/tab_scenarios/common/ui_utils.js
 * Пакет: windows/api/webgui/tab_scenarios
 * Автор: hypo69
 * Updated: 2026-10-31 19:55:00
 * =============================================================================
 */

export const categoryIcons = {
  quick: '⚡',
  logs: '📜',
  diagnostics: '🖥️',
  security: '🛡️',
  network: '🌐',
  ai: '🤖',
};

export const statusIcons = {
  ok: '✅',
  warn: '⚠️',
  error: '❌',
  skipped: '⏭️',
};

/**
 * Безопасное экранирование специальных символов HTML.
 * @param {string} str - Исходная строка.
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
 * Преобразование HTML сущностей обратно в символы.
 * @param {string} str - Экранированная строка.
 * @returns {string}
 */
export function unescapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'");
}

/**
 * Универсальное и безопасное преобразование Markdown в HTML для чата ассистента.
 * Корректно сохраняет существующие безопасные фрагменты HTML (h6, code, div и т.д.),
 * защищает блоки кода от повторного экранирования и форматирует заголовки, списки, таблицы.
 *
 * @param {string} text - Исходный текст (Markdown или смешанный Markdown/HTML).
 * @returns {string} Итоговая HTML-разметка.
 */
export function formatMarkdown(text) {
  if (!text) return '';
  let str = String(text);

  // 1. Извлечение и защита многострочных кодовых блоков (```...```)
  const codeBlocks = [];
  str = str.replace(/```(\w+)?\s*([\s\S]*?)```/g, (match, lang, code) => {
    const rawCode = unescapeHtml(code).trim();
    const normalizedLang = (lang || '').toLowerCase().trim();
    const displayLang = normalizedLang || (rawCode.startsWith('{') || rawCode.startsWith('[') ? 'json' : '');
    const blockHtml = `<pre class="uai-code-block p-2 rounded small my-2 font-monospace ${displayLang ? 'language-' + displayLang : ''}" style="overflow-x: auto;"><code>${escapeHtml(rawCode)}</code></pre>`;
    codeBlocks.push(blockHtml);
    return `\n\n@@@UAI_CODE_BLOCK_${codeBlocks.length - 1}@@@\n\n`;
  });

  // 2. Извлечение и защита инлайн-кода `код`
  const inlineCodes = [];
  str = str.replace(/`([^`\n]+)`/g, (match, inline) => {
    const cleanInline = unescapeHtml(inline).trim();
    inlineCodes.push(`<code class="text-primary bg-body-secondary px-1 rounded font-monospace small">${escapeHtml(cleanInline)}</code>`);
    return `@@@UAI_INLINE_CODE_${inlineCodes.length - 1}@@@`;
  });

  // 3. Защита уже существующих валидных HTML-тегов и плейсхолдеров
  const rawHtmlSnippets = [];
  str = str.replace(
    /(?:###__[A-Z0-9_]+__###|<\/?(?:div|span|h[1-6]|p|blockquote|code|table|thead|tbody|tr|th|td|ul|ol|li|hr|br|strong|em|a|i|button|pre|textarea|select|option|label)[^>]*>)/gi,
    (match) => {
      rawHtmlSnippets.push(match);
      return `@@@UAI_RAW_HTML_${rawHtmlSnippets.length - 1}@@@`;
    }
  );

  // 4. Безопасное экранирование спецсимволов HTML в оставшемся тексте
  str = str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  // Возвращаем символ '>' в начале строк для корректной работы цитат
  str = str.replace(/^(\s*)&gt;/gm, '$1>');

  // 5. Парсинг Markdown таблиц (| col1 | col2 |)
  str = str.replace(/((?:^[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$))+)/gm, (tableBlock) => {
    const rows = tableBlock.trim().split('\n').map(r => r.trim()).filter(Boolean);
    if (rows.length < 2) return tableBlock;
    if (!/^[ \t]*\|(?:\s*:?-+:?\s*\|)+[ \t]*$/.test(rows[1])) {
      return tableBlock;
    }
    const parseCells = (row) => {
      const inner = row.replace(/^[ \t]*\|/, '').replace(/\|[ \t]*$/, '');
      return inner.split('|').map(c => c.trim());
    };

    const headerCells = parseCells(rows[0]);
    const theadHtml = '<thead><tr>' + headerCells.map(c => `<th class="py-1 px-2">${c}</th>`).join('') + '</tr></thead>';

    let tbodyHtml = '<tbody>';
    for (let r = 2; r < rows.length; r++) {
      const cells = parseCells(rows[r]);
      tbodyHtml += '<tr>' + cells.map(c => `<td class="py-1 px-2">${c}</td>`).join('') + '</tr>';
    }
    tbodyHtml += '</tbody>';

    return `\n<div class="table-responsive my-2"><table class="table table-sm table-bordered uai-markdown-table mb-0">${theadHtml}${tbodyHtml}</table></div>\n`;
  });

  // 6. Блоки цитат и callout (> 💡, > ⚠️, > ❌, > ...)
  str = str.replace(/((?:^[ \t]*>[^\n]*(?:\r?\n|$))+)/gm, (bqBlock) => {
    const rawLines = bqBlock.split('\n')
      .map(l => l.replace(/^[ \t]*>[ \t]?/, '').trim())
      .filter(Boolean);
    if (rawLines.length === 0) return '';

    return `<blockquote class="border-start border-primary border-3 ps-2 my-1 text-body bg-body-secondary py-1 rounded-end">${rawLines.join('<br>')}</blockquote>`;
  });

  // 7. Заголовки ######, #####, ####, ###, ##, #
  str = str.replace(/^[ \t]*######[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.8rem;">$1</h6>');
  str = str.replace(/^[ \t]*#####[ \t]+(.*$)/gm, '<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.85rem;">$1</h6>');
  str = str.replace(/^[ \t]*####[ \t]+(.*$)/gm, '<h6 class="fw-bold text-primary mt-2 mb-1" style="font-size: 0.95rem;">$1</h6>');
  str = str.replace(/^[ \t]*###[ \t]+(.*$)/gm, '<h6 class="fw-bold text-primary mt-2.5 mb-1.5 fs-6">$1</h6>');
  str = str.replace(/^[ \t]*##[ \t]+(.*$)/gm, '<h5 class="fw-bold text-body mt-3 mb-2">$1</h5>');
  str = str.replace(/^[ \t]*#[ \t]+(.*$)/gm, '<h4 class="fw-bold text-body mt-3 mb-2">$1</h4>');

  // 8. Горизонтальные разделители ---, ***, ___
  str = str.replace(/^[ \t]*(?:---|\*\*\*|___)[ \t]*$/gm, '<hr class="uai-divider my-2 border-secondary border-opacity-25">');

  // 9. Ссылки [текст](url)
  str = str.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary text-decoration-underline">$1</a>');

  // 10. Жирный и курсив
  str = str.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  str = str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  str = str.replace(/(^|[^*])\*([^*]+?)\*([^*]|$)/g, '$1<em>$2</em>$3');

  // 11. Списки (нумерованные и маркированные)
  str = str.replace(/^[ \t]*(\d+)\.[ \t]+(.*$)/gm, '<div class="ms-2 mb-1 d-flex align-items-start gap-1.5"><span class="badge bg-secondary font-monospace" style="font-size: 0.72rem;">$1</span><span>$2</span></div>');
  str = str.replace(/^[ \t]*[-*•][ \t]+(.*$)/gm, '<li class="ms-3 mb-1">$1</li>');

  // 12. Переносы строк
  str = str.replace(/\n/g, '<br>');

  // 13. Очистка избыточных <br> вокруг блочных элементов
  str = str.replace(/(?:<br\s*\/?>\s*)*(<\/?(?:div|blockquote|table|thead|tbody|tr|th|td|h[1-6]|ul|ol|li|hr|pre)[^>]*>)(?:<br\s*\/?>\s*)*/gi, '$1');

  // 14. Восстановление исходного безопасного HTML
  rawHtmlSnippets.forEach((snippet, idx) => {
    str = str.replace(`@@@UAI_RAW_HTML_${idx}@@@`, snippet);
  });

  // 15. Восстановление инлайн-кода
  inlineCodes.forEach((codeHtml, idx) => {
    str = str.replace(`@@@UAI_INLINE_CODE_${idx}@@@`, codeHtml);
  });

  // 16. Восстановление блоков кода
  codeBlocks.forEach((blockHtml, idx) => {
    str = str.replace(`@@@UAI_CODE_BLOCK_${idx}@@@`, blockHtml);
  });

  return str;
}

/**
 * Извлечение блоков [CHAT] и [VOICE] из текста ответа и очистка управляющих тегов действий.
 * @param {string} rawText - Исходный ответ модели.
 * @returns {{chatText: string, voiceText: string}} Очищенные тексты для чата и озвучивания.
 */
export function parseChatAndVoice(rawText) {
  if (!rawText) return { chatText: '', voiceText: '' };
  let text = String(rawText);
  let voiceText = '';

  if (text.includes('[CHAT]') || text.includes('[VOICE]')) {
    const voiceMatch = text.match(/\[VOICE\]([\s\S]*?)(?:\[\/VOICE\]|(?=\[CHAT\])|$)/i);
    if (voiceMatch) {
      voiceText = voiceMatch[1].trim();
    }
    const chatMatch = text.match(/\[CHAT\]([\s\S]*?)(?:\[\/CHAT\]|(?=\[VOICE\])|$)/i);
    if (chatMatch) {
      text = chatMatch[1].trim();
    } else {
      text = text.replace(/\[VOICE\][\s\S]*?(?:\[\/VOICE\]|(?=\[CHAT\])|$)/gi, '').trim();
    }
  }

  // Очистка блоков действий от отображения в голосовом тексте
  text = text.replace(/```(?:action|json:action)[\s\S]*?```/gi, '').trim();
  text = text.replace(/\[ACTION:[\s\S]*?\]/gi, '').trim();

  // Удаление оставшихся служебных тегов
  text = text.replace(/\[\/?CHAT\]/gi, '').replace(/\[\/?VOICE\]/gi, '').trim();
  return { chatText: text, voiceText: voiceText || text };
}
