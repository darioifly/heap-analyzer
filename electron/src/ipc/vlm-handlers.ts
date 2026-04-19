/**
 * IPC handlers for VLM model management.
 */

import { ipcMain } from 'electron';
import type { DatabaseService } from '../database/db';
import {
  getGpuInfo,
  listModels,
  isModelDownloaded,
  downloadModel,
  cancelDownload,
} from '../services/vlm-service';

/** Register VLM IPC handlers. */
export function setupVlmHandlers(_dbService: DatabaseService): void {
  ipcMain.handle('vlm:gpuInfo', async () => {
    return getGpuInfo();
  });

  ipcMain.handle('vlm:listModels', async () => {
    return listModels();
  });

  ipcMain.handle(
    'vlm:isDownloaded',
    async (_event, { modelName }: { modelName: string }) => {
      return isModelDownloaded(modelName);
    },
  );

  ipcMain.handle(
    'vlm:download',
    async (event, { modelName }: { modelName: string }) => {
      await downloadModel(modelName, event.sender);
      return { success: true };
    },
  );

  ipcMain.handle('vlm:cancelDownload', async () => {
    cancelDownload();
    return { success: true };
  });
}
