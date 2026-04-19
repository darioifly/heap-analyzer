import { ipcMain } from 'electron';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';
import path from 'path';

/** Register comparison IPC handlers. */
export function setupComparisonHandlers(dbService: DatabaseService): void {
  // Run a comparison between two surveys
  ipcMain.handle(
    'comparison:run',
    async (
      event,
      {
        surveyAId,
        surveyBId,
        iouThreshold,
        stabilityThreshold,
      }: {
        surveyAId: number;
        surveyBId: number;
        iouThreshold?: number;
        stabilityThreshold?: number;
      },
    ) => {
      const surveyA = dbService.getSurvey(surveyAId);
      const surveyB = dbService.getSurvey(surveyBId);

      if (!surveyA) throw new Error(`Survey A (${surveyAId}) not found`);
      if (!surveyB) throw new Error(`Survey B (${surveyBId}) not found`);

      // Find results.json for each survey
      const getResultsPath = (survey: { dsm_path: string | null }): string => {
        if (!survey.dsm_path) throw new Error('Survey has no processed data');
        const outputDir = path.dirname(survey.dsm_path);
        return path.join(outputDir, 'results.json');
      };

      const resultsAPath = getResultsPath(surveyA);
      const resultsBPath = getResultsPath(surveyB);

      const args = [
        '--results-a', resultsAPath,
        '--results-b', resultsBPath,
      ];

      if (iouThreshold !== undefined) {
        args.push('--iou-threshold', String(iouThreshold));
      }
      if (stabilityThreshold !== undefined) {
        args.push('--stability-threshold', String(stabilityThreshold));
      }

      const bridge = new PythonBridge();
      bridge.on('progress', (data) => {
        event.sender.send('comparison:progress', data);
      });

      const result = await bridge.execute('compare', args);
      const resultData = result.data as Record<string, unknown>;

      // Persist to DB
      const comparison = dbService.createComparison(
        surveyAId,
        surveyBId,
        JSON.stringify(resultData),
      );

      return {
        comparisonId: comparison.id,
        result: resultData,
      };
    },
  );

  // Get a comparison by ID
  ipcMain.handle(
    'comparison:get',
    (_event, { id }: { id: number }) => {
      const db = dbService.getDb();
      const row = db.prepare('SELECT * FROM comparisons WHERE id = ?').get(id) as {
        id: number;
        survey_a_id: number;
        survey_b_id: number;
        results: string | null;
        created_at: string;
      } | undefined;

      if (!row) return null;

      return {
        id: row.id,
        surveyAId: row.survey_a_id,
        surveyBId: row.survey_b_id,
        results: row.results ? JSON.parse(row.results) : null,
        createdAt: row.created_at,
      };
    },
  );

  // List comparisons involving a survey
  ipcMain.handle(
    'comparison:listForSurvey',
    (_event, { surveyId }: { surveyId: number }) => {
      const rows = dbService.listComparisons(surveyId);
      return rows.map((row) => ({
        id: row.id,
        surveyAId: row.survey_a_id,
        surveyBId: row.survey_b_id,
        results: row.results ? JSON.parse(row.results) : null,
        createdAt: row.created_at,
      }));
    },
  );
}
