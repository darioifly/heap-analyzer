import { ipcMain } from 'electron';
import path from 'path';
import fs from 'fs';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';

/** Register Potree-related IPC handlers. */
export function setupPotreeHandlers(dbService: DatabaseService): void {
  // Convert LAS/LAZ to Potree 2.0 format
  ipcMain.handle(
    'potree:convert',
    async (event, { surveyId }: { surveyId: number }) => {
      const survey = dbService.getSurvey(surveyId);
      if (!survey) throw new Error(`Survey ${surveyId} not found`);
      if (!survey.las_path) throw new Error('Survey has no LAS file');

      // Output directory: same parent as DSM, under potree/
      const outputBase = survey.dsm_path
        ? path.dirname(survey.dsm_path)
        : path.dirname(survey.las_path);
      const outputDir = path.join(outputBase, 'potree');

      const bridge = new PythonBridge();
      bridge.on('progress', (data) => {
        event.sender.send('python:progress', data);
      });

      const result = await bridge.execute('export-pointcloud', [
        '--las', survey.las_path,
        '--output', outputDir,
      ]);

      // Update survey with potree_path on success
      const potreePath = (result.data as Record<string, unknown>).output_dir as string;
      dbService.updateSurvey(surveyId, { potree_path: potreePath });

      return result.data;
    },
  );

  // Check Potree conversion status for a survey
  ipcMain.handle(
    'potree:getStatus',
    (_event, { surveyId }: { surveyId: number }) => {
      const survey = dbService.getSurvey(surveyId);
      if (!survey) throw new Error(`Survey ${surveyId} not found`);

      if (!survey.potree_path) {
        return { available: false };
      }

      const metadataPath = path.join(survey.potree_path, 'metadata.json');
      if (!fs.existsSync(metadataPath)) {
        return { available: false };
      }

      const metadata = JSON.parse(
        fs.readFileSync(metadataPath, 'utf8'),
      ) as Record<string, unknown>;

      return {
        available: true,
        potreePath: survey.potree_path,
        metadata,
      };
    },
  );
}
