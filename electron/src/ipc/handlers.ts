import { ipcMain, dialog } from 'electron';
import { PythonBridge } from './python-bridge';

let bridge: PythonBridge | null = null;

/** Register all IPC handlers. Call once from main.ts. */
export function setupIpcHandlers(): void {
  setupPythonHandlers();
  setupDbHandlers();
  setupDialogHandlers();
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
// Dialog handlers
// ---------------------------------------------------------------------------

function setupDialogHandlers(): void {
  ipcMain.handle(
    'dialog:openFile',
    async (
      _event,
      options: {
        title?: string;
        filters?: { name: string; extensions: string[] }[];
        defaultPath?: string;
      },
    ) => {
      const result = await dialog.showOpenDialog({
        properties: ['openFile'],
        title: options.title,
        filters: options.filters,
        defaultPath: options.defaultPath,
      });
      return result.canceled ? null : result.filePaths[0];
    },
  );

  ipcMain.handle(
    'dialog:saveFile',
    async (
      _event,
      options: {
        title?: string;
        filters?: { name: string; extensions: string[] }[];
        defaultPath?: string;
      },
    ) => {
      const result = await dialog.showSaveDialog({
        title: options.title,
        filters: options.filters,
        defaultPath: options.defaultPath,
      });
      return result.canceled ? null : result.filePath;
    },
  );
}

// ---------------------------------------------------------------------------
// Database handlers — placeholder implementations (wired to real DB in F0.S05)
// ---------------------------------------------------------------------------

function setupDbHandlers(): void {
  ipcMain.handle('db:projects:list', async () => []);
  ipcMain.handle('db:projects:create', async (_e, _data) => null);
  ipcMain.handle('db:projects:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:projects:delete', async (_e, _id) => null);
  ipcMain.handle('db:surveys:list', async (_e, _projectId) => []);
  ipcMain.handle('db:surveys:create', async (_e, _data) => null);
  ipcMain.handle('db:surveys:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:surveys:delete', async (_e, _id) => null);
  ipcMain.handle('db:heaps:list', async (_e, _surveyId) => []);
  ipcMain.handle('db:heaps:create', async (_e, _data) => null);
  ipcMain.handle('db:heaps:update', async (_e, _id, _data) => null);
  ipcMain.handle('db:heaps:bulkCreate', async (_e, _heaps) => []);
}
