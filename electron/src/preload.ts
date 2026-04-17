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
    deleteSurvey: (id: number): Promise<void> => ipcRenderer.invoke('db:surveys:delete', id),

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

  shell: {
    /** Show a file in its parent folder in the system file manager. */
    showItemInFolder: (fullPath: string): Promise<void> =>
      ipcRenderer.invoke('shell:showItemInFolder', fullPath),
  },

  editing: {
    /** Create a new heap from a drawn polygon. */
    createHeap: (args: {
      surveyId: number;
      polygonGeoJSON: Record<string, unknown>;
    }): Promise<Record<string, unknown>> =>
      ipcRenderer.invoke('editing:createHeap', args),

    /** Recompute metrics for an existing heap after polygon modification. */
    recomputeHeap: (args: {
      heapId: number;
      polygonGeoJSON: Record<string, unknown>;
      surveyId: number;
    }): Promise<Record<string, unknown>> =>
      ipcRenderer.invoke('editing:recomputeHeap', args),

    /** Delete a heap by ID. */
    deleteHeap: (args: { heapId: number }): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke('editing:deleteHeap', args),

    /** Split a heap using a cutting line. Returns new heaps. */
    splitHeap: (args: {
      heapId: number;
      lineGeoJSON: Record<string, unknown>;
      surveyId: number;
    }): Promise<Record<string, unknown>[]> =>
      ipcRenderer.invoke('editing:splitHeap', args),

    /** Merge multiple heaps into one. Returns merged heap. */
    mergeHeaps: (args: {
      heapIds: number[];
      surveyId: number;
    }): Promise<Record<string, unknown>> =>
      ipcRenderer.invoke('editing:mergeHeaps', args),

    /** Restore a snapshot of heaps for undo/redo. */
    restoreSnapshot: (args: {
      surveyId: number;
      deleteHeapIds: number[];
      heaps: Array<Record<string, unknown>>;
    }): Promise<Record<string, unknown>[]> =>
      ipcRenderer.invoke('editing:restoreSnapshot', args),
  },

  elevation: {
    /** Recompute all heaps with a new base elevation. */
    recomputeAll: (args: {
      surveyId: number;
      baseElevation: number;
    }): Promise<{ heaps: Record<string, unknown>[]; baseElevation: number }> =>
      ipcRenderer.invoke('elevation:recomputeAll', args),

    /** Sample DSM elevation within ground-reference polygons. */
    sampleGround: (args: {
      surveyId: number;
      polygonsGeoJSON: Record<string, unknown>[];
    }): Promise<{
      mean_elevation: number;
      std_elevation: number;
      num_pixels: number;
      per_polygon: Array<{ mean: number | null; std: number | null; num_pixels: number }>;
    }> =>
      ipcRenderer.invoke('elevation:sampleGround', args),
  },

  tiles: {
    /** Get the base URL of the tile server. */
    getBaseUrl: (): Promise<string> => ipcRenderer.invoke('tiles:getBaseUrl'),

    /** Get tile metadata for a survey. Returns null if not available. */
    getMetadata: (surveyId: number): Promise<Record<string, unknown> | null> =>
      ipcRenderer.invoke('tiles:getMetadata', surveyId),
  },

  dialog: {
    /** Open native file picker dialog. Returns selected file path or null if canceled. */
    openFile: (options: {
      title?: string;
      filters?: { name: string; extensions: string[] }[];
      defaultPath?: string;
    }): Promise<string | null> => ipcRenderer.invoke('dialog:openFile', options),

    /** Open native save dialog. Returns selected path or null if canceled. */
    saveFile: (options: {
      title?: string;
      filters?: { name: string; extensions: string[] }[];
      defaultPath?: string;
    }): Promise<string | null> => ipcRenderer.invoke('dialog:saveFile', options),
  },
});
