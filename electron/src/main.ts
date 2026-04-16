import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import fs from 'fs';
import { initDatabase, DatabaseService } from './database/db';
import { setupIpcHandlers } from './ipc/handlers';
import { TileServer } from './services/tile-server';

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const DEV_SERVER_URL = 'http://localhost:5173';

let dbService: DatabaseService;
let tileServer: TileServer;

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

app.whenReady().then(async () => {
  // Initialize database
  const dbPath = path.join(app.getPath('userData'), 'heap-analyzer.db');
  const db = initDatabase(dbPath);
  dbService = new DatabaseService(db);

  // Register IPC handlers with real DB
  setupIpcHandlers(dbService);

  // Start tile server
  tileServer = new TileServer(dbService);
  await tileServer.start();

  // Tile-related IPC handlers
  ipcMain.handle('tiles:getBaseUrl', () => tileServer.getBaseUrl());

  ipcMain.handle('tiles:getMetadata', async (_event, surveyId: number) => {
    const survey = dbService.getSurvey(surveyId);
    if (!survey || !survey.tiles_path) {
      return null;
    }
    const metadataPath = path.join(survey.tiles_path, 'metadata.json');
    if (!fs.existsSync(metadataPath)) {
      return null;
    }
    const raw = fs.readFileSync(metadataPath, 'utf8');
    return JSON.parse(raw) as Record<string, unknown>;
  });

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
