import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mocks — avoid loading real better-sqlite3 / Electron.
// ---------------------------------------------------------------------------

type Handler = (
  event: unknown,
  payload: Record<string, unknown>,
) => Promise<unknown>;

const registered: Record<string, Handler> = {};

vi.mock('electron', () => ({
  ipcMain: {
    handle: (channel: string, handler: Handler) => {
      registered[channel] = handler;
    },
  },
}));

const executeMock = vi.fn();
vi.mock('./python-bridge', () => ({
  PythonBridge: class {
    execute = executeMock;
  },
}));

import { setupDjiHandlers } from './dji-handlers';
import type { DatabaseService, Survey } from '../database/db';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  for (const k of Object.keys(registered)) delete registered[k];
  executeMock.mockReset();
});

function makeDbStub(): DatabaseService {
  return {
    createSurvey: vi.fn((data: unknown) => ({
      ...(data as Record<string, unknown>),
      id: 42,
      created_at: 't',
      updated_at: 't',
    } as unknown as Survey)),
  } as unknown as DatabaseService;
}

describe('DJI IPC handlers', () => {
  it('registers both dji:scanFolder and dji:importSurvey', () => {
    setupDjiHandlers(makeDbStub());
    expect(registered['dji:scanFolder']).toBeTypeOf('function');
    expect(registered['dji:importSurvey']).toBeTypeOf('function');
  });

  it('dji:scanFolder returns a typed manifest on success', async () => {
    setupDjiHandlers(makeDbStub());
    executeMock.mockResolvedValue({
      type: 'result',
      data: {
        orthophoto_path: '/dji/map/result.tif',
        dsm_path: '/dji/map/dsm.tif',
        las_path: '/dji/models/pc/0/terra_las/cloud_merged.las',
        crs: 'EPSG:32633',
        survey_date: '2026-03-30',
        bbox: [0, 0, 100, 100],
        has_ground_classification: true,
        pipeline_complete: true,
        warnings: [],
      },
    });

    const response = await registered['dji:scanFolder'](null, { folderPath: '/dji' });
    expect(response).toEqual({
      ok: true,
      manifest: {
        orthophoto_path: '/dji/map/result.tif',
        dsm_path: '/dji/map/dsm.tif',
        las_path: '/dji/models/pc/0/terra_las/cloud_merged.las',
        crs: 'EPSG:32633',
        survey_date: '2026-03-30',
        bbox: [0, 0, 100, 100],
        has_ground_classification: true,
        pipeline_complete: true,
        warnings: [],
      },
    });
  });

  it('dji:scanFolder surfaces Python errors as { ok: false }', async () => {
    setupDjiHandlers(makeDbStub());
    executeMock.mockRejectedValue(new Error('[DJI_INCOMPLETE] DSM non trovato'));

    const response = (await registered['dji:scanFolder'](null, {
      folderPath: '/broken',
    })) as { ok: false; code: string; message: string };

    expect(response.ok).toBe(false);
    expect(response.code).toBe('DJI_INCOMPLETE');
    expect(response.message).toContain('DSM non trovato');
  });

  it('dji:importSurvey stores source_type=dji_terra and the folder path', async () => {
    const db = makeDbStub();
    setupDjiHandlers(db);

    const result = (await registered['dji:importSurvey'](null, {
      projectId: 7,
      folderPath: '/dji-root',
      manifest: {
        orthophoto_path: '/dji-root/map/result.tif',
        dsm_path: '/dji-root/map/dsm.tif',
        las_path: '/dji-root/cloud.las',
        crs: 'EPSG:32633',
        survey_date: '2026-03-30',
        bbox: null,
        has_ground_classification: true,
        pipeline_complete: true,
        warnings: [],
      },
      useDjiDsm: true,
      copyFiles: false,
      surveyDate: '2026-03-30',
      operator: 'Mario',
    })) as { surveyId: number };

    expect(result.surveyId).toBe(42);
    const createCall = vi.mocked(db.createSurvey).mock.calls[0][0];
    expect(createCall.source_type).toBe('dji_terra');
    expect(createCall.dji_folder_path).toBe('/dji-root');
    expect(createCall.las_path).toBe('/dji-root/cloud.las');
    expect(createCall.tiff_path).toBe('/dji-root/map/result.tif');
    // When useDjiDsm is true, the DSM path is threaded through ProcessingConfig.
    expect(createCall.processing_params).toContain('precomputed_dsm_path');
    expect(createCall.processing_params).toContain('/dji-root/map/dsm.tif');
  });

  it('dji:importSurvey omits precomputed DSM when useDjiDsm is false', async () => {
    const db = makeDbStub();
    setupDjiHandlers(db);

    await registered['dji:importSurvey'](null, {
      projectId: 1,
      folderPath: '/dji',
      manifest: {
        orthophoto_path: '/dji/ortho.tif',
        dsm_path: '/dji/dsm.tif',
        las_path: '/dji/cloud.las',
        crs: 'EPSG:32632',
        survey_date: '2026-03-30',
        bbox: null,
        has_ground_classification: false,
        pipeline_complete: true,
        warnings: [],
      },
      useDjiDsm: false,
      copyFiles: false,
      surveyDate: '2026-03-30',
      operator: '',
    });

    const createCall = vi.mocked(db.createSurvey).mock.calls[0][0];
    expect(createCall.processing_params).toBeNull();
  });

  it('dji:importSurvey threads manualBaseElevation into processing_params', async () => {
    const db = makeDbStub();
    setupDjiHandlers(db);

    await registered['dji:importSurvey'](null, {
      projectId: 1,
      folderPath: '/dji',
      manifest: {
        orthophoto_path: '/dji/ortho.tif',
        dsm_path: '/dji/dsm.tif',
        las_path: '/dji/cloud.las',
        crs: 'EPSG:32633',
        survey_date: '2026-03-30',
        bbox: null,
        has_ground_classification: true,
        pipeline_complete: true,
        warnings: [],
      },
      useDjiDsm: true,
      copyFiles: false,
      surveyDate: '2026-03-30',
      operator: '',
      manualBaseElevation: 215.911,
    });

    const createCall = vi.mocked(db.createSurvey).mock.calls[0][0];
    expect(createCall.processing_params).not.toBeNull();
    const parsed = JSON.parse(createCall.processing_params as string);
    expect(parsed.manual_base_elevation).toBe(215.911);
    expect(parsed.precomputed_dsm_path).toBe('/dji/dsm.tif');
  });

  it('dji:importSurvey skips manual_base_elevation when null', async () => {
    const db = makeDbStub();
    setupDjiHandlers(db);

    await registered['dji:importSurvey'](null, {
      projectId: 1,
      folderPath: '/dji',
      manifest: {
        orthophoto_path: '/dji/ortho.tif',
        dsm_path: '/dji/dsm.tif',
        las_path: '/dji/cloud.las',
        crs: null,
        survey_date: null,
        bbox: null,
        has_ground_classification: false,
        pipeline_complete: true,
        warnings: [],
      },
      useDjiDsm: false,
      copyFiles: false,
      surveyDate: '2026-04-01',
      operator: '',
      manualBaseElevation: null,
    });

    const createCall = vi.mocked(db.createSurvey).mock.calls[0][0];
    expect(createCall.processing_params).toBeNull();
  });
});
