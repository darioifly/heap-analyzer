import { ipcMain } from 'electron';
import { PythonBridge } from './python-bridge';

let bridge: PythonBridge | null = null;

/** Register all IPC handlers. Call once from main.ts. */
export function setupIpcHandlers(): void {
  setupPythonHandlers();
  setupDbHandlers();
}

// ---------------------------------------------------------------------------
// Python subprocess handlers
// ---------------------------------------------------------------------------

function setupPythonHandlers(): void {
  ipcMain.handle(
    'python:execute',
    async (event, command: string, args: string[]) => {
      bridge = new PythonBridge();

      bridge.on('progress', (data) => {
        event.sender.send('python:progress', data);
      });

      bridge.on('warning', (data) => {
        event.sender.send('python:warning', data);
      });

      return bridge.execute(command, args);
    },
  );

  ipcMain.handle('python:cancel', async () => {
    bridge?.cancel();
  });
}

// ---------------------------------------------------------------------------
// Database handlers — placeholder implementations (full in F0.S05)
// ---------------------------------------------------------------------------

function setupDbHandlers(): void {
  ipcMain.handle('db:projects:list', async () => []);
  ipcMain.handle('db:projects:create', async (_e, _data) => null);
  ipcMain.handle('db:projects:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:projects:delete', async (_e, _id) => null);
  ipcMain.handle('db:surveys:list', async (_e, _projectId) => []);
  ipcMain.handle('db:surveys:create', async (_e, _data) => null);
  ipcMain.handle('db:surveys:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:heaps:list', async (_e, _surveyId) => []);
  ipcMain.handle('db:heaps:create', async (_e, _data) => null);
  ipcMain.handle('db:heaps:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:heaps:bulkCreate', async (_e, _heaps) => []);
}
