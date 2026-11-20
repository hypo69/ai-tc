/**
 * =============================================================================
 * Process Name: ai-tc Electron Shell - Main Process
 * =============================================================================
 * Description:
 *   Главный процесс десктопной оболочки Electron (Chromium + Node.js runtime)
 *   для системы ai-tc (Test Computer & Windows System Diagnostics).
 *   Обеспечивает:
 *   - Запуск окна Chromium с каноническим URL интерфейса ai-tc (/tc)
 *   - Иконку окна и системного трея (красная дрель red_drill.png / favicon.ico)
 *   - Развёртывание на весь экран (maximize) при старте
 *   - Нативное меню приложения и контекстный системный трей
 *   - Безопасную изоляцию профиля Chromium и дискового кэша
 *
 * File: main.js
 * Package: apps/windows/electron
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 06:45:00
 * =============================================================================
 */

const { app, BrowserWindow, ipcMain, shell, Tray, Menu } = require('electron');
const path = require('path');
const fs = require('fs');

// Корень проекта: apps/windows/electron -> 3 уровня вверх
const PROJECT_ROOT_DIR = path.resolve(__dirname, '..', '..', '..');
const ROOT_DATA_DIR = path.resolve(PROJECT_ROOT_DIR, 'data');

// Настройка путей пользовательского профиля и кэша Chromium
const defaultProfileDir = path.resolve(ROOT_DATA_DIR, 'chromium', 'profiles');
const defaultCacheDir = path.resolve(ROOT_DATA_DIR, 'chromium', 'cache');

const chromiumProfileDir = process.env.AI_TC_CHROMIUM_PROFILE || defaultProfileDir;
const chromiumCacheDir = process.env.AI_TC_CHROMIUM_CACHE || defaultCacheDir;

try {
  app.setPath('userData', path.resolve(chromiumProfileDir));
} catch (err) {
  console.warn('[Electron] Ошибка установки userData:', err);
}

try {
  app.commandLine.appendSwitch('disk-cache-dir', path.resolve(chromiumCacheDir));
} catch (err) {
  console.warn('[Electron] Ошибка установки disk-cache-dir:', err);
}

// Определение целевого URL веб-интерфейса
let BACKEND_URL = process.env.AI_TC_BACKEND_URL || 'http://127.0.0.1:8000/tc';

// Проверяем аргументы командной строки на наличие явного URL
for (let i = 0; i < process.argv.length; i++) {
  const arg = process.argv[i];
  if (arg.startsWith('http://') || arg.startsWith('https://')) {
    BACKEND_URL = arg;
    break;
  }
  if (arg === '--url' && process.argv[i + 1]) {
    BACKEND_URL = process.argv[i + 1];
    break;
  }
}

let mainWindow = null;
let tray = null;
let isQuitting = false;

/**
 * Возвращает путь к иконке приложения (красная дрель).
 * @returns {string}
 */
function getAppIconPath() {
  const candidates = [
    path.join(PROJECT_ROOT_DIR, 'apps', 'windows', 'api', 'webgui', 'assets', 'red_drill.ico'),
    path.join(PROJECT_ROOT_DIR, 'apps', 'windows', 'api', 'webgui', 'assets', 'red_drill.png'),
    path.join(PROJECT_ROOT_DIR, 'apps', 'windows', 'api', 'webgui', 'favicon.ico'),
    path.join(PROJECT_ROOT_DIR, 'apps', 'windows', 'api', 'webgui', 'assets', 'favicon.ico'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) {
      return c;
    }
  }
  return '';
}

/**
 * Создает нативное верхнее меню окна.
 */
function createApplicationMenu() {
  const template = [
    {
      label: 'Файл',
      submenu: [
        {
          label: 'Открыть в браузере',
          click: () => {
            shell.openExternal(BACKEND_URL);
          },
        },
        { type: 'separator' },
        {
          label: 'Выход',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            isQuitting = true;
            app.quit();
          },
        },
      ],
    },
    {
      label: 'Правка',
      submenu: [
        { role: 'undo', label: 'Отменить' },
        { role: 'redo', label: 'Повторить' },
        { type: 'separator' },
        { role: 'cut', label: 'Вырезать' },
        { role: 'copy', label: 'Копировать' },
        { role: 'paste', label: 'Вставить' },
        { role: 'selectAll', label: 'Выделить всё' },
      ],
    },
    {
      label: 'Вид',
      submenu: [
        { role: 'reload', label: 'Перезагрузить' },
        { role: 'forceReload', label: 'Принудительная перезагрузка' },
        { role: 'toggleDevTools', label: 'Инструменты разработчика (DevTools)' },
        { type: 'separator' },
        { role: 'resetZoom', label: 'Масштаб по умолчанию' },
        { role: 'zoomIn', label: 'Увеличить' },
        { role: 'zoomOut', label: 'Уменьшить' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'Полноэкранный режим' },
      ],
    },
    {
      label: 'Окно',
      submenu: [
        { role: 'minimize', label: 'Свернуть' },
        {
          label: 'Свернуть в системный трей',
          accelerator: 'CmdOrCtrl+W',
          click: () => {
            if (mainWindow) {
              mainWindow.hide();
            }
          },
        },
      ],
    },
    {
      label: 'Справка',
      submenu: [
        {
          label: 'О системе ai-tc',
          click: () => {
            if (mainWindow) {
              const url = BACKEND_URL.split('#')[0] + '#tab-about-system';
              mainWindow.loadURL(url);
            }
          },
        },
      ],
    },
  ];

  const appMenu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(appMenu);
}

/**
 * Разворачивает и фокусирует главное окно приложения.
 */
function showMainWindow() {
  if (!mainWindow) {
    createWindow();
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  if (!mainWindow.isVisible()) {
    mainWindow.show();
  }
  mainWindow.maximize();
  mainWindow.setAlwaysOnTop(true);
  mainWindow.focus();
  mainWindow.setAlwaysOnTop(false);
}

/**
 * Инициализирует и настраивает системный трей с иконкой красной дрели.
 */
function createTray() {
  if (tray) return;

  const iconPath = getAppIconPath();
  if (!iconPath) return;

  try {
    tray = new Tray(iconPath);
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Развернуть ai-tc (на весь экран)',
        click: () => {
          showMainWindow();
        },
      },
      { type: 'separator' },
      {
        label: 'Выход',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setToolTip('ai-tc — Test Computer (Electron Shell)');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
      showMainWindow();
    });
    tray.on('double-click', () => {
      showMainWindow();
    });
  } catch (err) {
    console.error('[Electron] Ошибка создания системного трея:', err);
  }
}

/**
 * Создаёт главное окно приложения BrowserWindow.
 */
function createWindow() {
  const iconPath = getAppIconPath();

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: 'ai-tc — Test Computer & System Diagnostics',
    icon: iconPath || undefined,
    autoHideMenuBar: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.maximize();
  createApplicationMenu();

  mainWindow.once('ready-to-show', () => {
    mainWindow.maximize();
    mainWindow.show();
    mainWindow.focus();
  });

  setTimeout(() => {
    if (mainWindow && !mainWindow.isVisible()) {
      mainWindow.maximize();
      mainWindow.show();
      mainWindow.focus();
    }
  }, 2500);

  // Автоматический retry при первом старте сервера
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, _errorDescription, validatedURL) => {
    if (errorCode === -102 || errorCode === -105 || errorCode === -106) {
      setTimeout(() => {
        if (mainWindow) {
          mainWindow.loadURL(validatedURL);
        }
      }, 500);
    }
  });

  mainWindow.loadURL(BACKEND_URL);

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      if (tray && process.platform === 'win32') {
        try {
          tray.displayBalloon({
            title: 'ai-tc',
            content: 'Приложение свёрнуто в системный трей и продолжает работать.',
          });
        } catch (_) {}
      }
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// -----------------------------------------------------------------------------
// Регистрация IPC-обработчиков
// -----------------------------------------------------------------------------
ipcMain.handle('engine:get-info', async () => {
  return {
    engine_id: 'electron',
    versions: process.versions,
    backend_url: BACKEND_URL,
    app_icon: getAppIconPath(),
  };
});

ipcMain.handle('shell:open-external', async (_event, url) => {
  if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
    await shell.openExternal(url);
    return true;
  }
  return false;
});

ipcMain.handle('window:reload', async () => {
  if (mainWindow) {
    mainWindow.reload();
  }
});

ipcMain.handle('window:toggle-devtools', async () => {
  if (mainWindow) {
    mainWindow.webContents.toggleDevTools();
  }
});

// -----------------------------------------------------------------------------
// Жизненный цикл приложения
// -----------------------------------------------------------------------------
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (_event, commandLine) => {
    if (mainWindow) {
      showMainWindow();
      for (const arg of commandLine) {
        if (arg.startsWith('http://') || arg.startsWith('https://')) {
          mainWindow.loadURL(arg);
          break;
        }
      }
    }
  });

  app.whenReady().then(() => {
    createWindow();
    createTray();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      } else {
        showMainWindow();
      }
    });
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
});
