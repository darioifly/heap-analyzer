export interface ProgressMessage {
  type: "progress";
  phase: string;
  percent: number;
  message: string;
}

export interface WarningMessage {
  type: "warning";
  message: string;
}

export interface ResultMessage {
  type: "result";
  data: Record<string, unknown>;
}

export interface ErrorMessage {
  type: "error";
  code: string;
  message: string;
}

declare global {
  interface Window {
    api: {
      python: {
        execute: (command: string, args: string[]) => Promise<ResultMessage>;
        cancel: () => Promise<void>;
        onProgress: (callback: (data: ProgressMessage) => void) => void;
        onWarning: (callback: (data: WarningMessage) => void) => void;
        removeAllListeners: () => void;
      };
      db: {
        listProjects: () => Promise<Record<string, unknown>[]>;
        createProject: (data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        updateProject: (id: number, data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        deleteProject: (id: number) => Promise<void>;
        listSurveys: (projectId: number) => Promise<Record<string, unknown>[]>;
        createSurvey: (data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        updateSurvey: (id: number, data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        deleteSurvey: (id: number) => Promise<void>;
        listHeaps: (surveyId: number) => Promise<Record<string, unknown>[]>;
        createHeap: (data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        updateHeap: (id: number, data: Record<string, unknown>) => Promise<Record<string, unknown>>;
        bulkCreateHeaps: (heaps: Record<string, unknown>[]) => Promise<Record<string, unknown>[]>;
      };
      dialog: {
        openFile: (options: {
          title?: string;
          filters?: { name: string; extensions: string[] }[];
          defaultPath?: string;
        }) => Promise<string | null>;
        saveFile: (options: {
          title?: string;
          filters?: { name: string; extensions: string[] }[];
          defaultPath?: string;
        }) => Promise<string | null>;
      };
    };
  }
}

export {};
