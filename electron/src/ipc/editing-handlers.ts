/**
 * IPC handlers for heap polygon editing operations (F3.S01).
 *
 * Operations: createHeap, recomputeHeap, deleteHeap, splitHeap, mergeHeaps, restoreSnapshot.
 * All operations call Python engine for volume recomputation and persist to DB.
 * Split and merge are atomic via better-sqlite3 transactions.
 */

import { ipcMain } from 'electron';
import { PythonBridge } from './python-bridge';
import type { DatabaseService, Heap, Survey } from '../database/db';

/** Metrics returned by Python recompute-heap command. */
interface RecomputeMetrics {
  volume_m3: number;
  planimetric_area_m2: number;
  surface_area_m2: number;
  max_height_m: number;
  mean_height_m: number;
  base_elevation_m: number;
  centroid_e: number;
  centroid_n: number;
  bbox_min_e: number;
  bbox_min_n: number;
  bbox_max_e: number;
  bbox_max_n: number;
  polygon_geojson: Record<string, unknown>;
}

/** Call Python recompute-heap and return metrics. */
async function callRecompute(
  ndsmPath: string,
  polygonGeoJSON: Record<string, unknown>,
  baseElevation: number,
): Promise<RecomputeMetrics> {
  const bridge = new PythonBridge();
  const result = await bridge.execute('recompute-heap', [
    '--ndsm', ndsmPath,
    '--polygon-json', JSON.stringify(polygonGeoJSON),
    '--base-elevation', String(baseElevation),
  ]);
  return result.data as unknown as RecomputeMetrics;
}

/** Convert Python metrics to DB heap row fields. */
function metricsToDbFields(
  metrics: RecomputeMetrics,
  polygonGeoJSON: Record<string, unknown>,
): Partial<Heap> {
  return {
    polygon: JSON.stringify(polygonGeoJSON),
    volume: metrics.volume_m3,
    planimetric_area: metrics.planimetric_area_m2,
    surface_area: metrics.surface_area_m2,
    max_height: metrics.max_height_m,
    mean_height: metrics.mean_height_m,
    base_elevation: metrics.base_elevation_m,
    centroid_e: metrics.centroid_e,
    centroid_n: metrics.centroid_n,
    bbox_min_e: metrics.bbox_min_e,
    bbox_min_n: metrics.bbox_min_n,
    bbox_max_e: metrics.bbox_max_e,
    bbox_max_n: metrics.bbox_max_n,
    is_manually_confirmed: 1,
  };
}

/** Get survey and validate ndsm_path exists. */
function getSurveyOrThrow(db: DatabaseService, surveyId: number): Survey {
  const survey = db.getSurvey(surveyId);
  if (!survey) {
    throw new Error(`Survey ${surveyId} not found`);
  }
  if (!survey.ndsm_path) {
    throw new Error(`Survey ${surveyId} has no nDSM — process it first`);
  }
  return survey;
}

/** Get base elevation from existing heaps, falling back to 0.0. */
function getBaseElevation(db: DatabaseService, surveyId: number): number {
  const heaps = db.listHeaps(surveyId);
  if (heaps.length > 0 && heaps[0].base_elevation != null) {
    return heaps[0].base_elevation;
  }
  console.error('[F3.S01] Warning: no base_elevation found, using 0.0');
  return 0.0;
}

/** Register all editing IPC handlers. */
export function setupEditingHandlers(db: DatabaseService): void {
  // -------------------------------------------------------------------------
  // editing:createHeap — draw a new heap polygon
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:createHeap',
    async (
      _event,
      args: { surveyId: number; polygonGeoJSON: Record<string, unknown> },
    ) => {
      console.error('[F3.S01] editing:createHeap', args.surveyId);
      const survey = getSurveyOrThrow(db, args.surveyId);
      const baseElevation = getBaseElevation(db, args.surveyId);

      const metrics = await callRecompute(
        survey.ndsm_path!,
        args.polygonGeoJSON,
        baseElevation,
      );

      const fields = metricsToDbFields(metrics, args.polygonGeoJSON);
      const nextLabel = `Cumulo ${db.listHeaps(args.surveyId).length + 1}`;

      const heap = db.createHeap({
        survey_id: args.surveyId,
        label: nextLabel,
        polygon: fields.polygon!,
        volume: fields.volume ?? null,
        planimetric_area: fields.planimetric_area ?? null,
        surface_area: fields.surface_area ?? null,
        max_height: fields.max_height ?? null,
        mean_height: fields.mean_height ?? null,
        base_elevation: fields.base_elevation ?? null,
        centroid_e: fields.centroid_e ?? null,
        centroid_n: fields.centroid_n ?? null,
        bbox_min_e: fields.bbox_min_e ?? null,
        bbox_min_n: fields.bbox_min_n ?? null,
        bbox_max_e: fields.bbox_max_e ?? null,
        bbox_max_n: fields.bbox_max_n ?? null,
        material_category: null,
        material_confidence: null,
        vlm_reasoning: null,
        is_manually_confirmed: 1,
        is_excluded: 0,
      });
      return heap;
    },
  );

  // -------------------------------------------------------------------------
  // editing:recomputeHeap — update polygon + recalculate metrics
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:recomputeHeap',
    async (
      _event,
      args: {
        heapId: number;
        polygonGeoJSON: Record<string, unknown>;
        surveyId: number;
      },
    ) => {
      console.error('[F3.S01] editing:recomputeHeap', args.heapId);
      const survey = getSurveyOrThrow(db, args.surveyId);
      const baseElevation = getBaseElevation(db, args.surveyId);

      const metrics = await callRecompute(
        survey.ndsm_path!,
        args.polygonGeoJSON,
        baseElevation,
      );

      const fields = metricsToDbFields(metrics, args.polygonGeoJSON);
      const updated = db.updateHeap(args.heapId, fields);
      if (!updated) {
        throw new Error(`Heap ${args.heapId} not found`);
      }
      return updated;
    },
  );

  // -------------------------------------------------------------------------
  // editing:deleteHeap — remove a heap
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:deleteHeap',
    async (_event, args: { heapId: number }) => {
      console.error('[F3.S01] editing:deleteHeap', args.heapId);
      db.deleteHeap(args.heapId);
      return { ok: true };
    },
  );

  // -------------------------------------------------------------------------
  // editing:splitHeap — split one heap into N parts
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:splitHeap',
    async (
      _event,
      args: {
        heapId: number;
        lineGeoJSON: Record<string, unknown>;
        surveyId: number;
      },
    ) => {
      console.error('[F3.S01] editing:splitHeap', args.heapId);
      const survey = getSurveyOrThrow(db, args.surveyId);
      const baseElevation = getBaseElevation(db, args.surveyId);

      const heap = db.getHeap(args.heapId);
      if (!heap) throw new Error(`Heap ${args.heapId} not found`);

      const polygonGeoJSON = typeof heap.polygon === 'string'
        ? JSON.parse(heap.polygon) as Record<string, unknown>
        : heap.polygon;

      // Call Python split
      const splitBridge = new PythonBridge();
      const splitResult = await splitBridge.execute('split-polygon', [
        '--polygon-json', JSON.stringify(polygonGeoJSON),
        '--line-json', JSON.stringify(args.lineGeoJSON),
      ]);
      const parts = (splitResult.data as { parts: Record<string, unknown>[] }).parts;

      // Recompute metrics for each part
      const partMetrics: RecomputeMetrics[] = [];
      for (const part of parts) {
        const m = await callRecompute(survey.ndsm_path!, part, baseElevation);
        partMetrics.push(m);
      }

      // Atomic transaction: delete original + insert new parts
      const rawDb = db.getDb();
      const txn = rawDb.transaction(() => {
        db.deleteHeap(args.heapId);
        const newHeaps: Heap[] = [];
        for (let i = 0; i < parts.length; i++) {
          const fields = metricsToDbFields(partMetrics[i], parts[i]);
          const newHeap = db.createHeap({
            survey_id: args.surveyId,
            label: `${heap.label || 'Cumulo'} (${i + 1}/${parts.length})`,
            polygon: fields.polygon!,
            volume: fields.volume ?? null,
            planimetric_area: fields.planimetric_area ?? null,
            surface_area: fields.surface_area ?? null,
            max_height: fields.max_height ?? null,
            mean_height: fields.mean_height ?? null,
            base_elevation: fields.base_elevation ?? null,
            centroid_e: fields.centroid_e ?? null,
            centroid_n: fields.centroid_n ?? null,
            bbox_min_e: fields.bbox_min_e ?? null,
            bbox_min_n: fields.bbox_min_n ?? null,
            bbox_max_e: fields.bbox_max_e ?? null,
            bbox_max_n: fields.bbox_max_n ?? null,
            material_category: heap.material_category,
            material_confidence: null,
            vlm_reasoning: null,
            is_manually_confirmed: 1,
            is_excluded: 0,
          });
          newHeaps.push(newHeap);
        }
        return newHeaps;
      });

      return txn();
    },
  );

  // -------------------------------------------------------------------------
  // editing:mergeHeaps — merge N heaps into one
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:mergeHeaps',
    async (
      _event,
      args: { heapIds: number[]; surveyId: number },
    ) => {
      console.error('[F3.S01] editing:mergeHeaps', args.heapIds);
      const survey = getSurveyOrThrow(db, args.surveyId);
      const baseElevation = getBaseElevation(db, args.surveyId);

      const heaps = args.heapIds.map((id) => {
        const h = db.getHeap(id);
        if (!h) throw new Error(`Heap ${id} not found`);
        return h;
      });

      const polygons = heaps.map((h) =>
        typeof h.polygon === 'string'
          ? JSON.parse(h.polygon) as Record<string, unknown>
          : h.polygon,
      );

      // Call Python merge
      const mergeBridge = new PythonBridge();
      const mergeResult = await mergeBridge.execute('merge-polygons', [
        '--polygons-json', JSON.stringify(polygons),
      ]);
      const mergedPolygon = (mergeResult.data as { merged: Record<string, unknown> }).merged;

      // Recompute metrics
      const metrics = await callRecompute(
        survey.ndsm_path!,
        mergedPolygon,
        baseElevation,
      );

      // Atomic transaction: delete originals + insert merged
      const rawDb = db.getDb();
      const txn = rawDb.transaction(() => {
        for (const id of args.heapIds) {
          db.deleteHeap(id);
        }
        const fields = metricsToDbFields(metrics, mergedPolygon);
        return db.createHeap({
          survey_id: args.surveyId,
          label: `Cumuli uniti (${args.heapIds.length})`,
          polygon: fields.polygon!,
          volume: fields.volume ?? null,
          planimetric_area: fields.planimetric_area ?? null,
          surface_area: fields.surface_area ?? null,
          max_height: fields.max_height ?? null,
          mean_height: fields.mean_height ?? null,
          base_elevation: fields.base_elevation ?? null,
          centroid_e: fields.centroid_e ?? null,
          centroid_n: fields.centroid_n ?? null,
          bbox_min_e: fields.bbox_min_e ?? null,
          bbox_min_n: fields.bbox_min_n ?? null,
          bbox_max_e: fields.bbox_max_e ?? null,
          bbox_max_n: fields.bbox_max_n ?? null,
          material_category: heaps[0].material_category,
          material_confidence: null,
          vlm_reasoning: null,
          is_manually_confirmed: 1,
          is_excluded: 0,
        });
      });

      return txn();
    },
  );

  // -------------------------------------------------------------------------
  // editing:restoreSnapshot — restore heaps for undo/redo
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'editing:restoreSnapshot',
    async (
      _event,
      args: {
        surveyId: number;
        deleteHeapIds: number[];
        heaps: Array<Record<string, unknown>>;
      },
    ) => {
      console.error('[F3.S01] editing:restoreSnapshot', args.surveyId);

      const rawDb = db.getDb();
      const txn = rawDb.transaction(() => {
        // Delete specified heaps
        for (const id of args.deleteHeapIds) {
          db.deleteHeap(id);
        }
        // Re-insert snapshot heaps
        const restored: Heap[] = [];
        for (const heapData of args.heaps) {
          const heap = db.createHeap(heapData as Omit<Heap, 'id' | 'created_at' | 'updated_at'>);
          restored.push(heap);
        }
        return restored;
      });

      return txn();
    },
  );
}

