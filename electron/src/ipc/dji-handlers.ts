import { ipcMain } from 'electron';
import fs from 'fs/promises';
import path from 'path';
import { PythonBridge } from './python-bridge';
import type { DatabaseService, Survey } from '../database/db';

/** Asset manifest returned by scan-dji-terra. Matches the Python Pydantic model. */
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

export interface ScanDjiFolderRequest {
  folderPath: string;
}

export type ScanDjiFolderResponse =
  | { ok: true; manifest: DJITerraManifest }
  | { ok: false; code: string; message: string };

export interface ImportDjiSurveyRequest {
  projectId: number;
  folderPath: string;
  manifest: DJITerraManifest;
  useDjiDsm: boolean;
  copyFiles: boolean;
  surveyDate: string; // ISO YYYY-MM-DD
  operator: string;
}

export interface ImportDjiSurveyResponse {
  surveyId: number;
}

/** Register DJI Terra import IPC handlers. */
export function setupDjiHandlers(dbService: DatabaseService): void {
  ipcMain.handle(
    'dji:scanFolder',
    async (_event, request: ScanDjiFolderRequest): Promise<ScanDjiFolderResponse> => {
      try {
        const bridge = new PythonBridge();
        const result = await bridge.execute('scan-dji-terra', [
          '--folder',
          request.folderPath,
        ]);
        const manifest = result.data as unknown as DJITerraManifest;
        return { ok: true, manifest };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        // Extract any emitted error code if the Python bridge surfaced one;
        // otherwise fall back to a generic failure code.
        const codeMatch = msg.match(/\[([A-Z_]+)\]/);
        const code = codeMatch ? codeMatch[1] : 'DJI_SCAN_FAILED';
        return { ok: false, code, message: msg };
      }
    },
  );

  ipcMain.handle(
    'dji:importSurvey',
    async (
      _event,
      request: ImportDjiSurveyRequest,
    ): Promise<ImportDjiSurveyResponse> => {
      const { projectId, folderPath, manifest, useDjiDsm, copyFiles } = request;

      // Resolve effective paths — either original DJI paths or copies inside the
      // project folder. The project folder is a sibling of the system data dir;
      // we colocate copies under <parent of DJI folder>/heap-analyzer-import-<id>.
      let lasPath = manifest.las_path;
      let tiffPath = manifest.orthophoto_path;
      let dsmPath: string | null = useDjiDsm ? manifest.dsm_path : null;

      if (copyFiles) {
        const parentDir = path.dirname(folderPath);
        const destDir = path.join(
          parentDir,
          `heap-analyzer-import-${Date.now()}`,
        );
        await fs.mkdir(destDir, { recursive: true });

        const lasCopy = path.join(destDir, path.basename(manifest.las_path));
        const tiffCopy = path.join(destDir, path.basename(manifest.orthophoto_path));
        await fs.copyFile(manifest.las_path, lasCopy);
        await fs.copyFile(manifest.orthophoto_path, tiffCopy);
        lasPath = lasCopy;
        tiffPath = tiffCopy;

        if (useDjiDsm) {
          const dsmCopy = path.join(destDir, path.basename(manifest.dsm_path));
          await fs.copyFile(manifest.dsm_path, dsmCopy);
          dsmPath = dsmCopy;
        }
      }

      // Bundle the precomputed DSM path into processing_params so the pipeline
      // reads it via ProcessingConfig.precomputed_dsm_path.
      const processingParams = dsmPath
        ? JSON.stringify({ precomputed_dsm_path: dsmPath })
        : null;

      const created: Survey = dbService.createSurvey({
        project_id: projectId,
        survey_date: request.surveyDate,
        operator: request.operator || null,
        las_path: lasPath,
        tiff_path: tiffPath,
        processing_params: processingParams,
        processing_status: 'pending',
        dsm_path: null,
        dtm_path: null,
        ndsm_path: null,
        label_map_path: null,
        tiles_path: null,
        ndsm_heatmap_path: null,
        base_elevation: null,
        potree_path: null,
        source_type: 'dji_terra',
        dji_folder_path: folderPath,
      });

      return { surveyId: created.id };
    },
  );
}
