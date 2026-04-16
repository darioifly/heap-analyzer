import { contextBridge, ipcRenderer } from 'electron';

/** Progress message emitted during Python processing phases. */
export interface ProgressMessage {
  type: 'progress';
  phase: string;
  percent: number;
  message: string;
}

/** Warning message — non-fatal issue during processing. */
export interface WarningMessage {
  type: 'warning';
  message: string;
}

/** Final result message carrying processed data. */
export interface ResultMessage {
  type: 'result';
  data: Record<string, unknown>;
}

/** Error message — processing failed. */
export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

contextBridge.exposeInMainWorld('api', {
  python: {
    /**
     * Execute a heap-analyzer CLI command and return the final result.
     * Progress events are delivered via onProgress callbacks.
     */
    execute: (command: string, args: string[]): Promise<ResultMessage> =>
      ipcRenderer.invoke('python:execute', command, args),

    /** Cancel a running Python process. */
    cancel: (): Promise<void> => ipcRenderer.invoke('python:cancel'),

    /** Register a callback for progress events during processing. */
    onProgress: (callback: (data: ProgressMessage) => void): void => {
      ipcRenderer.on('python:progress', (_event, data: ProgressMessage) => callback(data));
    },

    /** Register a callback for warning events during processing. */
    onWarning: (callback: (data: WarningMessage) => void): void => {
      ipcRenderer.on('python:warning', (_event, data: WarningMessage) => callback(data));
    },

    /** Remove all python event listeners (call on component unmount). */
    removeAllListeners: (): void => {
      ipcRenderer.removeAllListeners('python:progress');
      ipcRenderer.removeAllListeners('python:warning');
    },
  },

  db: {
    // Projects
    listProjects: (): Promise<unknown[]> => ipcRenderer.invoke('db:projects:list'),
    createProject: (data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:projects:create', data),
    updateProject: (id: number, data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:projects:update', id, data),
    deleteProject: (id: number): Promise<void> => ipcRenderer.invoke('db:projects:delete', id),

    // Surveys
    listSurveys: (projectId: number): Promise<unknown[]> =>
      ipcRenderer.invoke('db:surveys:list', projectId),
    createSurvey: (data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:surveys:create', data),
    updateSurvey: (id: number, data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:surveys:update', id, data),

    // Heaps
    listHeaps: (surveyId: number): Promise<unknown[]> =>
      ipcRenderer.invoke('db:heaps:list', surveyId),
    createHeap: (data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:heaps:create', data),
    updateHeap: (id: number, data: Record<string, unknown>): Promise<unknown> =>
      ipcRenderer.invoke('db:heaps:update', id, data),
    bulkCreateHeaps: (heaps: Record<string, unknown>[]): Promise<unknown[]> =>
      ipcRenderer.invoke('db:heaps:bulkCreate', heaps),
  },
});
