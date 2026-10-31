/**
 * =============================================================================
 * Process Name: Windows WebGUI - AI Modal Dialog Component Facade
 * =============================================================================
 * Description:
 *   Единый JS-фасад компонента AI Modal Dialog (01_FRONTEND.md).
 *   Обеспечивает доступность класса и объекта AIModalDialog.
 *
 * File: ai_modal_dialog.js
 * Project: ai-windows-admin
 * Package: apps.windows.api.webgui.ai_modal_dialog
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 05:56:00
 * =============================================================================
 */

export class AIModalDialog {
  static open(options) {
    if (typeof window !== 'undefined' && window.AIModalDialog && typeof window.AIModalDialog.open === 'function') {
      return window.AIModalDialog.open(options);
    }
    console.warn('[AIModalDialog] window.AIModalDialog еще не готов');
  }

  static show(options) {
    if (typeof window !== 'undefined' && window.AIModalDialog && typeof window.AIModalDialog.show === 'function') {
      return window.AIModalDialog.show(options);
    }
    console.warn('[AIModalDialog] window.AIModalDialog еще не готов');
  }
}

if (typeof window !== 'undefined') {
  if (!window.AIModalDialog) {
    const script = document.createElement('script');
    script.src = '/html/ai_modal_dialog/main.js?v=20261031_v2';
    document.head.appendChild(script);
  }
}
