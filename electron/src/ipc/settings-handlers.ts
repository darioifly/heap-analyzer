import { ipcMain, dialog } from 'electron';
import { loadSettings, saveSettings, resetSettings } from '../services/settings';
import { PythonBridge } from './python-bridge';

/** Register settings IPC handlers and renderer-error logger. */
export function setupSettingsHandlers(): void {
  ipcMain.handle('settings:load', () => loadSettings());

  ipcMain.handle('settings:save', (_e, patch: Record<string, unknown>) => saveSettings(patch));

  ipcMain.handle('settings:reset', () => resetSettings());

  ipcMain.handle('settings:getProcessingSchema', async () => {
    const bridge = new PythonBridge();
    const result = await bridge.execute('config-schema', []);
    return result.data;
  });

  // Renderer error log sink — fire-and-forget from ErrorBoundary.
  ipcMain.on('log:renderer-error', (_e, payload: {
    message: string;
    stack?: string;
    context?: string;
  }) => {
    // eslint-disable-next-line no-console
    console.error(
      '[renderer-error]',
      payload.context || '',
      payload.message,
      payload.stack || '',
    );
  });
}

/** Exported for dialog wiring used by settings UI browse buttons. */
export async function settingsSelectDirectory(defaultPath?: string): Promise<string | null> {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    defaultPath,
  });
  return result.canceled ? null : result.filePaths[0];
}
