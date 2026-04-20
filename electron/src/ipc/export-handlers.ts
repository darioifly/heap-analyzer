import { ipcMain } from 'electron';
import path from 'path';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';

/** Register GIS (GeoJSON / Shapefile) export IPC handlers. */
export function setupExportHandlers(dbService: DatabaseService): void {
  ipcMain.handle(
    'export:geo',
    async (
      _event,
      payload: {
        surveyId: number;
        format: 'geojson' | 'shapefile' | 'both';
        outputDir: string;
        basename?: string;
      },
    ) => {
      const survey = dbService.getSurvey(payload.surveyId);
      if (!survey) throw new Error(`Survey ${payload.surveyId} not found`);
      if (survey.processing_status !== 'completed') {
        throw new Error('Rilievo non elaborato');
      }

      const project = dbService.getProject(survey.project_id);
      const crs = project?.crs || 'EPSG:32632';

      const heaps = dbService.listHeaps(payload.surveyId);
      if (heaps.length === 0) {
        throw new Error('Nessun cumulo disponibile per l\'esportazione');
      }

      // Build DB-enriched heap records for Python
      const heapsPayload = heaps.map((h) => ({
        id: h.id,
        label: h.label,
        polygon_geojson: h.polygon ? JSON.parse(h.polygon) : null,
        volume: h.volume,
        planimetric_area: h.planimetric_area,
        surface_area: h.surface_area,
        max_height: h.max_height,
        mean_height: h.mean_height,
        base_elevation: h.base_elevation,
        centroid_e: h.centroid_e,
        centroid_n: h.centroid_n,
        material_category: h.material_category,
        material_confidence: h.material_confidence,
        is_manually_confirmed: h.is_manually_confirmed === 1,
        is_excluded: h.is_excluded === 1,
      }));

      // Locate results.json from the processing output directory
      const outputDir = path.dirname(survey.dsm_path || survey.las_path);
      const resultsPath = path.join(outputDir, 'results.json');

      const basename = payload.basename || `cumuli_${survey.survey_date}`;

      const bridge = new PythonBridge();
      const args: string[] = [
        '--results', resultsPath,
        '--format', payload.format,
        '--output-dir', payload.outputDir,
        '--basename', basename,
        '--crs', crs,
        '--heaps-json', JSON.stringify(heapsPayload),
        '--survey-date', survey.survey_date,
      ];

      const result = await bridge.execute('export-geo', args);
      const data = result.data as { paths: string[]; crs: string; count: number };
      return {
        paths: data.paths,
        crs: data.crs,
        count: data.count,
      };
    },
  );
}
