import { ipcMain } from 'electron';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';

/** Register cross-section IPC handlers. */
export function setupCrossSectionHandlers(dbService: DatabaseService): void {
  // Create a cross section: run Python extraction, persist result
  ipcMain.handle(
    'crossSection:create',
    async (
      event,
      { surveyId, lineGeoJSON, label }: { surveyId: number; lineGeoJSON: string; label?: string },
    ) => {
      const survey = dbService.getSurvey(surveyId);
      if (!survey) throw new Error(`Survey ${surveyId} not found`);
      if (!survey.dsm_path || !survey.dtm_path) {
        throw new Error('Survey has no DSM/DTM data — run processing first');
      }

      const geom = JSON.parse(lineGeoJSON);
      const coordsJson = JSON.stringify(geom.coordinates);

      const bridge = new PythonBridge();
      bridge.on('progress', (data) => {
        event.sender.send('python:progress', data);
      });

      const result = await bridge.execute('cross-section', [
        '--dsm', survey.dsm_path,
        '--dtm', survey.dtm_path,
        '--line', coordsJson,
      ]);

      const data = result.data as Record<string, unknown>;

      const row = dbService.createCrossSection({
        survey_id: surveyId,
        label: label ?? null,
        line_geojson: lineGeoJSON,
        profile_json: JSON.stringify({
          distance: data.distance,
          dsm_z: data.dsm_z,
          dtm_z: data.dtm_z,
        }),
        section_area: data.section_area as number,
        length: data.length as number,
        max_height: data.max_height as number,
        band_width: 1.0,
      });

      return row;
    },
  );

  // List cross sections for a survey (without profile_json for bandwidth)
  ipcMain.handle(
    'crossSection:list',
    (_event, { surveyId }: { surveyId: number }) => {
      return dbService.listCrossSections(surveyId);
    },
  );

  // Get a single cross section with full profile data
  ipcMain.handle(
    'crossSection:get',
    (_event, { id }: { id: number }) => {
      return dbService.getCrossSection(id);
    },
  );

  // Update label or band_width
  ipcMain.handle(
    'crossSection:update',
    (_event, { id, patch }: { id: number; patch: { label?: string; band_width?: number } }) => {
      return dbService.updateCrossSection(id, patch);
    },
  );

  // Delete a cross section
  ipcMain.handle(
    'crossSection:delete',
    (_event, { id }: { id: number }) => {
      dbService.deleteCrossSection(id);
      return { ok: true };
    },
  );

  // Recompute profile (after base elevation change)
  ipcMain.handle(
    'crossSection:recompute',
    async (event, { id }: { id: number }) => {
      const section = dbService.getCrossSection(id);
      if (!section) throw new Error(`CrossSection ${id} not found`);

      const survey = dbService.getSurvey(section.survey_id);
      if (!survey?.dsm_path || !survey?.dtm_path) {
        throw new Error('Survey has no DSM/DTM data');
      }

      const geom = JSON.parse(section.line_geojson);
      const coordsJson = JSON.stringify(geom.coordinates);

      const bridge = new PythonBridge();
      bridge.on('progress', (data) => {
        event.sender.send('python:progress', data);
      });

      const result = await bridge.execute('cross-section', [
        '--dsm', survey.dsm_path,
        '--dtm', survey.dtm_path,
        '--line', coordsJson,
      ]);

      const data = result.data as Record<string, unknown>;

      return dbService.updateCrossSection(id, {
        profile_json: JSON.stringify({
          distance: data.distance,
          dsm_z: data.dsm_z,
          dtm_z: data.dtm_z,
        }),
        section_area: data.section_area as number,
        length: data.length as number,
        max_height: data.max_height as number,
      });
    },
  );
}
