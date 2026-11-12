/**
 * =============================================================================
 * Process Name: Common WebGUI - File Editor WebAssembly Bridge
 * =============================================================================
 * Description:
 *   Клиентский мост к скомпилированному ядру WebAssembly (file_editor_core.wasm).
 *   Выполняет операции над файловыми буферами напрямую в линейной памяти Wasm:
 *   вычисление FNV-1a хеша, подсчет строк, проверку бинарности, декодирование
 *   типов данных Data Inspector (8/16/32/64 бит) и извлечение дерева символов
 *   (Outline) для языков VS Code.
 *
 * File: wasm_bridge.js
 * Project: ai-assistant
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 17:07:00
 * =============================================================================
 */

let wasmInstance = null;
let wasmInitPromise = null;

/**
 * Загружает и инстанциирует бинарный модуль `file_editor_core.wasm`.
 * @returns {Promise<WebAssembly.Instance|null>}
 */
export async function initWasmEngine() {
  if (wasmInstance) return wasmInstance;
  if (wasmInitPromise) return wasmInitPromise;

  wasmInitPromise = (async () => {
    try {
      const response = await fetch('/api/v1/file-editor/wasm');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const wasmBytes = await response.arrayBuffer();
      const { instance } = await WebAssembly.instantiate(wasmBytes, {});
      wasmInstance = instance;
      return wasmInstance;
    } catch (err) {
      console.warn('[WasmBridge] Переключение на встроенный резервный вычислитель:', err);
      return null;
    }
  })();

  return wasmInitPromise;
}

/**
 * Конвертирует строку Base64 в типизированный массив `Uint8Array`.
 * @param {string} base64Str
 * @returns {Uint8Array}
 */
export function base64ToUint8Array(base64Str) {
  if (!base64Str) return new Uint8Array(0);
  const clean = base64Str.includes(',') ? base64Str.split(',')[1] : base64Str;
  try {
    const binaryString = atob(clean);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  } catch (_) {
    return new Uint8Array(0);
  }
}

/**
 * Конвертирует типизированный массив `Uint8Array` в строку Base64.
 * @param {Uint8Array} bytes
 * @returns {string}
 */
export function uint8ArrayToBase64(bytes) {
  if (!bytes || bytes.length === 0) return '';
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const sub = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, sub);
  }
  return btoa(binary);
}

/**
 * Выполняет анализ буфера в линейной памяти WebAssembly.
 * @param {Uint8Array} bytes
 * @returns {{hashHex: string, linesCount: number, isBinary: boolean, durationMs: string, usedWasm: boolean}}
 */
export function analyzeBufferWithWasm(bytes) {
  const t0 = performance.now();
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(0);

  if (wasmInstance && wasmInstance.exports) {
    const { memory, fnv1a_hash, count_lines, is_binary_buffer } = wasmInstance.exports;
    const maxLen = Math.min(data.length, memory.buffer.byteLength);
    const memView = new Uint8Array(memory.buffer, 0, maxLen);
    memView.set(data.subarray(0, maxLen));

    const rawHash = fnv1a_hash(0, maxLen) >>> 0;
    const lines = count_lines(0, maxLen) >>> 0;
    const isBin = is_binary_buffer(0, Math.min(maxLen, 8192)) === 1;
    const dt = (performance.now() - t0).toFixed(2);

    return {
      hashHex: rawHash.toString(16).padStart(8, '0'),
      linesCount: lines,
      isBinary: isBin,
      durationMs: dt,
      usedWasm: true,
    };
  }

  // Резервный расчёт при отсутствии Wasm-экземпляра
  let h = 2166136261;
  let lines = 1;
  let isBin = false;
  for (let i = 0; i < data.length; i++) {
    const b = data[i];
    h ^= b;
    h = Math.imul(h, 16777619) >>> 0;
    if (b === 10) lines++;
    if (i < 8192 && b === 0) isBin = true;
  }
  const dt = (performance.now() - t0).toFixed(2);
  return {
    hashHex: (h >>> 0).toString(16).padStart(8, '0'),
    linesCount: lines,
    isBinary: isBin,
    durationMs: dt,
    usedWasm: false,
  };
}

/**
 * Декодирует числовые типы данных (Data Inspector) в точке смещения буфера.
 * @param {Uint8Array} bytes
 * @param {number} offset
 * @returns {Object}
 */
export function inspectBytesAt(bytes, offset) {
  if (!bytes || offset < 0 || offset >= bytes.length) {
    return {
      offsetHex: '0x0000',
      binary: '00000000',
      uint8: 0,
      int8: 0,
      uint16: '—',
      int16: '—',
      uint32: '—',
      int32: '—',
      float32: '—',
      ascii: '.',
    };
  }

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const rem = bytes.length - offset;
  const u8 = view.getUint8(offset);
  const i8 = view.getInt8(offset);

  return {
    offsetHex: '0x' + offset.toString(16).toUpperCase().padStart(4, '0'),
    binary: u8.toString(2).padStart(8, '0'),
    uint8: u8,
    int8: i8,
    uint16: rem >= 2 ? view.getUint16(offset, true) : 'EOF',
    int16: rem >= 2 ? view.getInt16(offset, true) : 'EOF',
    uint32: rem >= 4 ? view.getUint32(offset, true) : 'EOF',
    int32: rem >= 4 ? view.getInt32(offset, true) : 'EOF',
    float32: rem >= 4 ? Number(view.getFloat32(offset, true)).toPrecision(5) : 'EOF',
    ascii: u8 >= 32 && u8 <= 126 ? String.fromCharCode(u8) : '.',
  };
}

/**
 * Извлекает структурные символы (Outline) для навигации по коду и документам.
 * @param {string} text
 * @param {string} ext
 * @returns {Array<{name: string, kind: string, line: number, icon: string}>}
 */
export function extractOutlineSymbols(text, ext) {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const symbols = [];
  const lowerExt = (ext || '').toLowerCase();

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;
    const lineNum = i + 1;

    if (['md', 'markdown', 'mdx'].includes(lowerExt) && trimmed.startsWith('#')) {
      symbols.push({
        name: trimmed.replace(/^#+\s*/, ''),
        kind: 'heading',
        line: lineNum,
        icon: 'bi-hash',
      });
    } else if (['py', 'pyi', 'pyw'].includes(lowerExt)) {
      const mClass = trimmed.match(/^class\s+([A-Za-z0-9_]+)/);
      const mDef = trimmed.match(/^(?:async\s+)?def\s+([A-Za-z0-9_]+)/);
      if (mClass) symbols.push({ name: mClass[1], kind: 'class', line: lineNum, icon: 'bi-box' });
      else if (mDef) symbols.push({ name: mDef[1], kind: 'function', line: lineNum, icon: 'bi-braces' });
    } else if (['js', 'mjs', 'cjs', 'ts', 'tsx', 'jsx'].includes(lowerExt)) {
      const mFn = trimmed.match(/^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)/);
      const mCls = trimmed.match(/^(?:export\s+)?class\s+([A-Za-z0-9_]+)/);
      if (mCls) symbols.push({ name: mCls[1], kind: 'class', line: lineNum, icon: 'bi-box' });
      else if (mFn) symbols.push({ name: mFn[1], kind: 'function', line: lineNum, icon: 'bi-braces' });
    } else if (lowerExt === 'rs') {
      const mFn = trimmed.match(/^(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)/);
      const mSt = trimmed.match(/^(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)/);
      if (mSt) symbols.push({ name: mSt[1], kind: 'struct', line: lineNum, icon: 'bi-diagram-2' });
      else if (mFn) symbols.push({ name: mFn[1], kind: 'function', line: lineNum, icon: 'bi-braces' });
    } else if (['json', 'yaml', 'yml', 'toml'].includes(lowerExt)) {
      const mKey = trimmed.match(/^["']?([A-Za-z0-9_.-]+)["']?\s*[:=]/);
      if (mKey && symbols.length < 60) {
        symbols.push({ name: mKey[1], kind: 'key', line: lineNum, icon: 'bi-key' });
      }
    }
  }
  return symbols;
}
