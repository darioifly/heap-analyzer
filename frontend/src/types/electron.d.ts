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
      shell: {
        showItemInFolder: (fullPath: string) => Promise<void>;
      };
      tiles: {
        getBaseUrl: () => Promise<string>;
        getMetadata: (surveyId: number) => Promise<{
          crs: string;
          bounds: [number, number, number, number];
          origin: [number, number];
          resolutions: number[];
          tileSize: number;
          minZoom: number;
          maxZoom: number;
        }>;
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
        openDirectory: (options: {
          title?: string;
          defaultPath?: string;
        }) => Promise<string | null>;
      };
      report: {
        generate: (params: {
          surveyId: number;
          format: 'pdf' | 'csv' | 'pdf+csv';
          destinationDir: string;
          logoPath: string | null;
          companyName: string | null;
          notes: string | null;
          onlyConfirmed: boolean;
        }) => Promise<{ success: boolean; outputPaths: string[] }>;
        cancel: () => Promise<void>;
        onProgress: (callback: (data: {
          type: string;
          phase: string;
          percent: number;
          message: string;
        }) => void) => void;
        removeProgressListeners: () => void;
        openPath: (fullPath: string) => Promise<void>;
      };
      elevation: {
        recomputeAll: (args: {
          surveyId: number;
          baseElevation: number;
        }) => Promise<{ heaps: Record<string, unknown>[]; baseElevation: number }>;
        sampleGround: (args: {
          surveyId: number;
          polygonsGeoJSON: Record<string, unknown>[];
        }) => Promise<{
          mean_elevation: number;
          std_elevation: number;
          num_pixels: number;
          per_polygon: Array<{ mean: number | null; std: number | null; num_pixels: number }>;
        }>;
      };
      crossSection: {
        create: (args: { surveyId: number; lineGeoJSON: string; label?: string }) => Promise<Record<string, unknown>>;
        list: (args: { surveyId: number }) => Promise<Record<string, unknown>[]>;
        get: (args: { id: number }) => Promise<Record<string, unknown>>;
        update: (args: { id: number; patch: { label?: string; band_width?: number } }) => Promise<Record<string, unknown>>;
        delete: (args: { id: number }) => Promise<{ ok: boolean }>;
        recompute: (args: { id: number }) => Promise<Record<string, unknown>>;
      };
      potree: {
        convert: (params: { surveyId: number }) => Promise<Record<string, unknown>>;
        getStatus: (params: { surveyId: number }) => Promise<{
          available: boolean;
          potreePath?: string;
          metadata?: Record<string, unknown>;
        }>;
      };
      comparison: {
        run: (params: {
          surveyAId: number;
          surveyBId: number;
          iouThreshold?: number;
          stabilityThreshold?: number;
        }) => Promise<{ comparisonId: number; result: Record<string, unknown> }>;
        get: (params: { id: number }) => Promise<{
          id: number;
          surveyAId: number;
          surveyBId: number;
          results: Record<string, unknown> | null;
          createdAt: string;
        } | null>;
        listForSurvey: (params: { surveyId: number }) => Promise<Array<{
          id: number;
          surveyAId: number;
          surveyBId: number;
          results: Record<string, unknown> | null;
          createdAt: string;
        }>>;
        onProgress: (callback: (data: {
          type: string;
          phase: string;
          percent: number;
          message: string;
        }) => void) => void;
        removeProgressListeners: () => void;
      };
      vlm: {
        gpuInfo: () => Promise<{
          cuda_available: boolean;
          cuda_version: string | null;
          device_name: string | null;
          vram_total_mb: number | null;
          vram_free_mb: number | null;
        }>;
        listModels: () => Promise<Array<{
          name: string;
          display_name: string;
          hf_id: string;
          vram_required_mb: number;
          description: string;
          is_downloaded: boolean;
          warns_if_insufficient: boolean;
        }>>;
        isDownloaded: (params: { modelName: string }) => Promise<boolean>;
        download: (params: { modelName: string }) => Promise<{ success: boolean }>;
        cancelDownload: () => Promise<{ success: boolean }>;
        onDownloadProgress: (callback: (data: {
          model_name: string;
          phase: string;
          percent: number;
          message: string;
        }) => void) => void;
        removeDownloadListeners: () => void;
      };
      export: {
        geo: (params: {
          surveyId: number;
          format: 'geojson' | 'shapefile' | 'both';
          outputDir: string;
          basename?: string;
        }) => Promise<{ paths: string[]; crs: string; count: number }>;
      };
      dji: {
        scanFolder: (params: { folderPath: string }) => Promise<
          | {
              ok: true;
              manifest: {
                orthophoto_path: string;
                dsm_path: string;
                las_path: string;
                crs: string | null;
                survey_date: string | null;
                bbox: [number, number, number, number] | null;
                has_ground_classification: boolean;
                pipeline_complete: boolean;
                warnings: string[];
              };
            }
          | { ok: false; code: string; message: string }
        >;
        importSurvey: (params: {
          projectId: number;
          folderPath: string;
          manifest: {
            orthophoto_path: string;
            dsm_path: string;
            las_path: string;
            crs: string | null;
            survey_date: string | null;
            bbox: [number, number, number, number] | null;
            has_ground_classification: boolean;
            pipeline_complete: boolean;
            warnings: string[];
          };
          useDjiDsm: boolean;
          copyFiles: boolean;
          surveyDate: string;
          operator: string;
          /** Optional flat-DTM elevation (m a.s.l.). null = auto strategy. */
          manualBaseElevation: number | null;
        }) => Promise<{ surveyId: number }>;
      };
      settings: {
        load: () => Promise<Record<string, unknown>>;
        save: (patch: Record<string, unknown>) => Promise<Record<string, unknown>>;
        reset: () => Promise<Record<string, unknown>>;
        getProcessingSchema: () => Promise<{
          fields: Array<{
            name: string;
            type: string;
            default: unknown;
            description: string;
          }>;
        }>;
      };
      logging: {
        rendererError: (payload: { message: string; stack?: string; context?: string }) => void;
      };
      editing: {
        createHeap: (args: {
          surveyId: number;
          polygonGeoJSON: Record<string, unknown>;
        }) => Promise<Record<string, unknown>>;
        recomputeHeap: (args: {
          heapId: number;
          polygonGeoJSON: Record<string, unknown>;
          surveyId: number;
        }) => Promise<Record<string, unknown>>;
        deleteHeap: (args: { heapId: number }) => Promise<{ ok: boolean }>;
        splitHeap: (args: {
          heapId: number;
          lineGeoJSON: Record<string, unknown>;
          surveyId: number;
        }) => Promise<Record<string, unknown>[]>;
        mergeHeaps: (args: {
          heapIds: number[];
          surveyId: number;
        }) => Promise<Record<string, unknown>>;
        restoreSnapshot: (args: {
          surveyId: number;
          deleteHeapIds: number[];
          heaps: Array<Record<string, unknown>>;
        }) => Promise<Record<string, unknown>[]>;
      };
    };
  }
}

export {};
