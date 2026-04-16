import { app, BrowserWindow } from 'electron';
import path from 'path';
import { initDatabase, DatabaseService } from './database/db';
import { setupIpcHandlers } from './ipc/handlers';

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const DEV_SERVER_URL = 'http://localhost:5173';

let dbService: DatabaseService;

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'Heap Analyzer',
    backgroundColor: '#1a1a2e',
    darkTheme: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    win.loadURL(DEV_SERVER_URL);
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, '../../dist/frontend/index.html'));
  }

  return win;
}

app.whenReady().then(() => {
  // Initialize database
  const dbPath = path.join(app.getPath('userData'), 'heap-analyzer.db');
  const db = initDatabase(dbPath);
  dbService = new DatabaseService(db);

  // Register IPC handlers with real DB
  setupIpcHandlers(dbService);

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
