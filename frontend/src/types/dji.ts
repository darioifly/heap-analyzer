/**
 * Types shared by the DJI Terra import flow (scanner + dialog).
 *
 * Keep in sync with:
 *  - Python: `heap_analyzer.io.dji_terra_scanner.DJITerraManifest`
 *  - Electron: `electron/src/ipc/dji-handlers.ts` `DJITerraManifest`
 */

export interface DJITerraManifest {
  orthophoto_path: string;
  dsm_path: string;
  las_path: string;
  crs: string | null;
  survey_date: string | null; // ISO YYYY-MM-DD
  bbox: [number, number, number, number] | null;
  has_ground_classification: boolean;
  pipeline_complete: boolean;
  warnings: string[];
}

export interface DjiScanSuccess {
  ok: true;
  manifest: DJITerraManifest;
}

export interface DjiScanFailure {
  ok: false;
  code: string;
  message: string;
}

export type DjiScanResponse = DjiScanSuccess | DjiScanFailure;

export interface DjiImportRequest {
  projectId: number;
  folderPath: string;
  manifest: DJITerraManifest;
  useDjiDsm: boolean;
  copyFiles: boolean;
  surveyDate: string;
  operator: string;
}

export interface DjiImportResponse {
  surveyId: number;
}
