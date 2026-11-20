/**
 * =============================================================================
 * Process Name: ai-tc Electron Shell - Preload Bridge
 * =============================================================================
 * Description:
 *   Безопасный IPC-мост (`contextBridge`) между главным процессом Electron
 *   (Node.js runtime) и общим веб-интерфейсом WebGUI (`window.aiEngineBridge`).
 *   Предоставляет единый контракт Engine Adapter API в браузерном контексте.
 *
 * File: preload.js
 * Package: apps/windows/electron
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 06:45:00
 * =============================================================================
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aiEngineBridge', {
  engineId: 'electron',
  isElectron: true,
  getInfo: () => ipcRenderer.invoke('engine:get-info'),
  openExternal: (url) => ipcRenderer.invoke('shell:open-external', url),
  reload: () => ipcRenderer.invoke('window:reload'),
  toggleDevTools: () => ipcRenderer.invoke('window:toggle-devtools'),
});
