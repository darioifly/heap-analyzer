import { ipcMain, dialog, shell } from 'electron';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';
import { setupEditingHandlers } from './editing-handlers';
import { setupElevationHandlers } from './elevation-handlers';
import { setupPotreeHandlers } from './potree-handlers';
import { setupCrossSectionHandlers } from './cross-section-handlers';
import { setupVlmHandlers } from './vlm-handlers';
import { setupComparisonHandlers } from './comparison-handlers';
import { setupReportHandlers } from './report-handlers';
import { setupExportHandlers } from './export-handlers';
import { setupSettingsHandlers } from './settings-handlers';

let bridge: PythonBridge | null = null;

/** Register all IPC handlers. Call once from main.ts after DB init. */
export function setupIpcHandlers(dbService: DatabaseService): void {
  setupPythonHandlers();
  setupDbHandlers(dbService);
  setupDialogHandlers();
  setupShellHandlers();
  setupEditingHandlers(dbService);
  setupElevationHandlers(dbService);
  setupPotreeHandlers(dbService);
  setupCrossSectionHandlers(dbService);
  setupVlmHandlers(dbService);
  setupComparisonHandlers(dbService);
  setupReportHandlers(dbService);
  setupExportHandlers(dbService);
  setupSettingsHandlers();
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
    'dialog:openDirectory',
    async (
      _event,
      options: {
        title?: string;
        defaultPath?: string;
      },
    ) => {
      const result = await dialog.showOpenDialog({
        properties: ['openDirectory'],
        title: options.title,
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
// Shell handlers
// ---------------------------------------------------------------------------

function setupShellHandlers(): void {
  ipcMain.handle('shell:showItemInFolder', async (_event, fullPath: string) => {
    shell.showItemInFolder(fullPath);
  });
}

// ---------------------------------------------------------------------------
// Database handlers — wired to real DatabaseService
// ---------------------------------------------------------------------------

function setupDbHandlers(db: DatabaseService): void {
  // Projects
  ipcMain.handle('db:projects:list', () => db.listProjects());
  ipcMain.handle('db:projects:create', (_e, data) => {
    console.log('[IPC] db:projects:create called with:', JSON.stringify(data));
    try {
      const result = db.createProject(data);
      console.log('[IPC] db:projects:create success:', JSON.stringify(result));
      return result;
    } catch (err) {
      console.error('[IPC] db:projects:create FAILED:', err);
      throw err;
    }
  });
  ipcMain.handle('db:projects:update', (_e, id: number, data) => db.updateProject(id, data));
  ipcMain.handle('db:projects:delete', (_e, id: number) => db.deleteProject(id));

  // Surveys
  ipcMain.handle('db:surveys:list', (_e, projectId: number) => db.listSurveys(projectId));
  ipcMain.handle('db:surveys:create', (_e, data) => db.createSurvey(data));
  ipcMain.handle('db:surveys:update', (_e, id: number, data) => db.updateSurvey(id, data));
  ipcMain.handle('db:surveys:delete', (_e, id: number) => db.deleteSurvey(id));

  // Heaps
  ipcMain.handle('db:heaps:list', (_e, surveyId: number) => db.listHeaps(surveyId));
  ipcMain.handle('db:heaps:create', (_e, data) => db.createHeap(data));
  ipcMain.handle('db:heaps:update', (_e, id: number, data) => db.updateHeap(id, data));
  ipcMain.handle('db:heaps:bulkCreate', (_e, heaps) => db.bulkCreateHeaps(heaps));
}
