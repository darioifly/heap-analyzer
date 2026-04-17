/**
 * IPC handlers for base elevation override and ground sampling (F3.S02).
 *
 * Channels:
 *   elevation:recomputeAll  — batch recalc all heaps with new base elevation
 *   elevation:sampleGround  — sample DSM in user-drawn ground polygons
 */

import { ipcMain } from 'electron';
import { PythonBridge } from './python-bridge';
import type { DatabaseService, Heap } from '../database/db';

/** Metrics returned by Python recompute-all-heaps command. */
interface RecomputeAllResult {
  heaps: Array<{
    id: number;
    metrics: {
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
    };
  }>;
  base_elevation: number;
}

/** Ground sampling result from Python sample-ground command. */
interface GroundSampleResult {
  mean_elevation: number;
  std_elevation: number;
  num_pixels: number;
  per_polygon: Array<{
    mean: number | null;
    std: number | null;
    num_pixels: number;
  }>;
}

/** Register elevation IPC handlers. */
export function setupElevationHandlers(db: DatabaseService): void {
  // -------------------------------------------------------------------------
  // elevation:recomputeAll — batch recalc with new base elevation
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'elevation:recomputeAll',
    async (
      _event,
      args: { surveyId: number; baseElevation: number },
    ) => {
      console.error('[F3.S02] elevation:recomputeAll', args.surveyId, 'base=', args.baseElevation);

      const survey = db.getSurvey(args.surveyId);
      if (!survey) {
        throw new Error(`Survey ${args.surveyId} not found`);
      }
      if (!survey.ndsm_path) {
        throw new Error(`Survey ${args.surveyId} has no nDSM — process it first`);
      }

      // Get all non-excluded heaps
      const heaps = db.listHeaps(args.surveyId).filter((h) => !h.is_excluded);
      if (heaps.length === 0) {
        throw new Error('No heaps to recompute');
      }

      // Determine original base elevation from current heaps or survey
      const originalBase = getOriginalBaseElevation(db, args.surveyId, heaps);

      // Build heaps JSON for Python
      const heapsInput = heaps.map((h) => ({
        id: h.id,
        polygon_geojson: typeof h.polygon === 'string'
          ? JSON.parse(h.polygon) as Record<string, unknown>
          : h.polygon,
      }));

      // Call Python recompute-all-heaps
      const bridge = new PythonBridge();
      const result = await bridge.execute('recompute-all-heaps', [
        '--ndsm', survey.ndsm_path,
        '--heaps-json', JSON.stringify(heapsInput),
        '--base-elevation', String(args.baseElevation),
        '--original-base-elevation', String(originalBase),
      ]);

      const data = result.data as unknown as RecomputeAllResult;

      // Atomic transaction: update all heaps + survey base_elevation
      const rawDb = db.getDb();
      const txn = rawDb.transaction(() => {
        for (const heapResult of data.heaps) {
          const m = heapResult.metrics;
          db.updateHeap(heapResult.id, {
            volume: m.volume_m3,
            planimetric_area: m.planimetric_area_m2,
            surface_area: m.surface_area_m2,
            max_height: m.max_height_m,
            mean_height: m.mean_height_m,
            base_elevation: m.base_elevation_m,
            centroid_e: m.centroid_e,
            centroid_n: m.centroid_n,
            bbox_min_e: m.bbox_min_e,
            bbox_min_n: m.bbox_min_n,
            bbox_max_e: m.bbox_max_e,
            bbox_max_n: m.bbox_max_n,
          });
        }
        // Store base_elevation on the survey row
        db.updateSurvey(args.surveyId, {
          base_elevation: args.baseElevation,
        });
      });
      txn();

      // Return fresh heaps list for frontend refresh
      const updatedHeaps = db.listHeaps(args.surveyId);
      return {
        heaps: updatedHeaps,
        baseElevation: args.baseElevation,
      };
    },
  );

  // -------------------------------------------------------------------------
  // elevation:sampleGround — sample DSM in ground polygons
  // -------------------------------------------------------------------------
  ipcMain.handle(
    'elevation:sampleGround',
    async (
      _event,
      args: { surveyId: number; polygonsGeoJSON: Record<string, unknown>[] },
    ) => {
      console.error('[F3.S02] elevation:sampleGround', args.surveyId);

      const survey = db.getSurvey(args.surveyId);
      if (!survey) {
        throw new Error(`Survey ${args.surveyId} not found`);
      }
      if (!survey.dsm_path) {
        return { error: 'DSM not available' };
      }

      // Call Python sample-ground
      const bridge = new PythonBridge();
      const result = await bridge.execute('sample-ground', [
        '--dsm', survey.dsm_path,
        '--polygons-json', JSON.stringify(args.polygonsGeoJSON),
      ]);

      return result.data as unknown as GroundSampleResult;
    },
  );
}

/** Get the original base elevation from existing heaps or survey. */
function getOriginalBaseElevation(
  db: DatabaseService,
  surveyId: number,
  heaps: Heap[],
): number {
  // First, try the survey-level base_elevation
  const survey = db.getSurvey(surveyId);
  if (survey?.base_elevation != null) {
    return survey.base_elevation;
  }
  // Fallback: use the first heap's base_elevation
  if (heaps.length > 0 && heaps[0].base_elevation != null) {
    return heaps[0].base_elevation;
  }
  console.error('[F3.S02] Warning: no original base_elevation found, using 0.0');
  return 0.0;
}
