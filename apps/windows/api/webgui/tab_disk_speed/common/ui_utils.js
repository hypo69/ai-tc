/**
 * =============================================================================
 * Process Name: Windows Disk Speed Tab - Common Utilities
 * =============================================================================
 * Description:
 *   Утилиты копирования результатов бенчмарка в формате Markdown.
 *
 * File: common/ui_utils.js
 * Project: ai-tc
 * Package: windows/api/webgui/tab_disk_speed/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

/**
 * Копирование результатов в формате Markdown таблицы.
 */
export function copyResultsAsMarkdown() {
  const s8r = document.getElementById('val-seq1m_q8t1-read')?.textContent || '0';
  const s8w = document.getElementById('val-seq1m_q8t1-write')?.textContent || '0';
  const s1r = document.getElementById('val-seq1m_q1t1-read')?.textContent || '0';
  const s1w = document.getElementById('val-seq1m_q1t1-write')?.textContent || '0';
  const r32r = document.getElementById('val-rnd4k_q32t16-read')?.textContent || '0';
  const r32w = document.getElementById('val-rnd4k_q32t16-write')?.textContent || '0';
  const r1r = document.getElementById('val-rnd4k_q1t1-read')?.textContent || '0';
  const r1w = document.getElementById('val-rnd4k_q1t1-write')?.textContent || '0';

  const disk = document.getElementById('bench-drive-select')?.value || 'C:';

  const md = [
    `### ai-tc DiskSpd Benchmark (${disk})`,
    '',
    '| Профиль | Read (MB/s) | Write (MB/s) |',
    '| :--- | :---: | :---: |',
    `| **SEQ1M Q8T1** | ${s8r} MB/s | ${s8w} MB/s |`,
    `| **SEQ1M Q1T1** | ${s1r} MB/s | ${s1w} MB/s |`,
    `| **RND4K Q32T16** | ${r32r} MB/s | ${r32w} MB/s |`,
    `| **RND4K Q1T1** | ${r1r} MB/s | ${r1w} MB/s |`,
    '',
    `*Дата замера: ${new Date().toLocaleString('ru-RU')}*`,
  ].join('\n');

  navigator.clipboard.writeText(md).then(() => {
    if (window.toast) window.toast.success('Скопировано', 'Таблица скопирована в буфер обмена');
  });
}
