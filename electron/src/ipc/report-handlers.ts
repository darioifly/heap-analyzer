import { ipcMain, shell } from 'electron';
import path from 'path';
import { PythonBridge } from './python-bridge';
import type { DatabaseService } from '../database/db';

/** Active report bridge for cancellation support. */
let activeBridge: PythonBridge | null = null;

/** Register report generation IPC handlers. */
export function setupReportHandlers(dbService: DatabaseService): void {
  ipcMain.handle(
    'report:generate',
    async (
      event,
      payload: {
        surveyId: number;
        format: 'pdf' | 'csv' | 'pdf+csv';
        destinationDir: string;
        logoPath: string | null;
        companyName: string | null;
        notes: string | null;
        onlyConfirmed: boolean;
      },
    ) => {
      const survey = dbService.getSurvey(payload.surveyId);
      if (!survey) throw new Error(`Survey ${payload.surveyId} not found`);
      if (survey.processing_status !== 'completed') {
        throw new Error('Survey non elaborato');
      }

      // Find the results.json path
      const outputDir = path.dirname(survey.dsm_path || survey.las_path);
      const resultsPath = path.join(outputDir, 'results.json');

      // Get project info for site name and categories
      const project = dbService.getProject(survey.project_id);
      const siteName = project?.name || 'Sito';
      const categories: string[] = project?.material_categories
        ? JSON.parse(project.material_categories)
        : [];

      // Get heap DB data for classifications
      const heaps = dbService.listHeaps(payload.surveyId);
      const heapDbData = heaps.map((h) => ({
        heap_id: h.id,
        material_category: h.material_category,
        material_confidence: h.material_confidence,
        classified_by: null,
        is_manually_confirmed: h.is_manually_confirmed === 1,
        notes: null,
      }));

      const outputPaths: string[] = [];

      // Generate PDF if needed
      if (payload.format === 'pdf' || payload.format === 'pdf+csv') {
        const pdfName = `report_${survey.survey_date}_${siteName.replace(/\s+/g, '_')}.pdf`;
        const pdfPath = path.join(payload.destinationDir, pdfName);

        const bridge = new PythonBridge();
        activeBridge = bridge;

        bridge.on('progress', (data) => {
          event.sender.send('report:progress', data);
        });

        const args: string[] = [
          '--results', resultsPath,
          '--tiff', survey.tiff_path,
          '--output', pdfPath,
          '--site-name', siteName,
          '--survey-date', survey.survey_date,
        ];

        if (payload.logoPath) {
          args.push('--logo', payload.logoPath);
        }
        if (payload.companyName) {
          args.push('--company', payload.companyName);
        }
        if (payload.notes) {
          args.push('--notes', payload.notes);
        }
        if (payload.onlyConfirmed) {
          args.push('--only-confirmed');
        }
        if (survey.operator) {
          args.push('--operator', survey.operator);
        }
        if (heapDbData.length > 0) {
          args.push('--heaps-json', JSON.stringify(heapDbData));
        }
        if (categories.length > 0) {
          args.push('--categories-json', JSON.stringify(categories));
        }

        await bridge.execute('generate-report', args);
        activeBridge = null;
        outputPaths.push(pdfPath);
      }

      // Generate CSV if needed
      if (payload.format === 'csv' || payload.format === 'pdf+csv') {
        const csvName = `cumuli_${survey.survey_date}_${siteName.replace(/\s+/g, '_')}.csv`;
        const csvPath = path.join(payload.destinationDir, csvName);

        const bridge = new PythonBridge();
        activeBridge = bridge;

        bridge.on('progress', (data) => {
          event.sender.send('report:progress', {
            ...data,
            phase: 'export',
          });
        });

        await bridge.execute('export-csv', [
          '--results', resultsPath,
          '--output', csvPath,
          '--survey-date', survey.survey_date,
        ]);
        activeBridge = null;
        outputPaths.push(csvPath);
      }

      return { success: true, outputPaths };
    },
  );

  ipcMain.handle('report:cancel', async () => {
    activeBridge?.cancel();
    activeBridge = null;
  });

  // Open file with system default viewer
  ipcMain.handle('shell:openPath', async (_event, fullPath: string) => {
    const error = await shell.openPath(fullPath);
    if (error) {
      throw new Error(`Impossibile aprire il file: ${error}`);
    }
  });
}
